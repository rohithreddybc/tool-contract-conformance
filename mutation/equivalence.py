"""Semantics-preserving mutant generators -- the sec 3 / ARCHITECTURE-FINAL.md sec 5 precision
controls: mutants that must NOT be flagged by a correct detector, used to measure false positives.

Per the review repair (W5) both documents encode: "Replace half of v1's log-string and
variable-name controls -- those are undetectable by construction and prove nothing -- with
semantics-preserving refactorings of ADVERTISED behavior: reorder independent writes, extract a
guard into a helper, arithmetically equivalent expressions." At least half of what this module
produces must be one of those three refactoring kinds; the remainder may be trivial edits
(variable rename, error-message reword), which are kept only because the plan explicitly allows
up to half to be them, not because they carry any evidentiary weight on their own.

Three refactoring generators + two trivial-edit generators, all still generic AST transforms (no
benchmark vocabulary):

    reorder_independent_writes  -- swap two adjacent top-level writes with disjoint targets
    extract_guard_into_helper   -- pull one `if test: raise` guard into a new helper method,
                                    called from the same position (whole-MODULE transform, since
                                    it adds a class member -- see its docstring)
    arithmetic_equivalent       -- `a - b` -> `a + (-b)`, `a + b` -> `b + a` (IEEE-754 exact)
    rename_local_variable       -- trivial edit: consistently rename one non-parameter local
    reword_raise_message        -- trivial edit: change a raised exception's message text

Every one of these is validated empirically, not just asserted: tests/test_mutation_equivalence.py
runs each generated mutant against the toy domain across a battery of probe calls and diffs its
observable behaviour (return value + resulting state) against the unmutated tool, bit-for-bit.
"""
from __future__ import annotations

import ast
import builtins as _builtins
import copy
from dataclasses import dataclass, field
from typing import Optional

from mutation.operators import is_state_write
from mutation.sites import find_function, _Replacer  # reuse -- do not reimplement module splicing

__all__ = [
    "EquivalenceSite",
    "REFACTOR_KINDS",
    "TRIVIAL_KINDS",
    "reorder_independent_writes",
    "extract_guard_into_helper",
    "arithmetic_equivalent",
    "rename_local_variable",
    "reword_raise_message",
    "enumerate_equivalence_sites",
    "select_equivalence_mutants",
]

REFACTOR_KINDS = ("reorder", "extract_guard", "arithmetic")
TRIVIAL_KINDS = ("rename", "reword")


@dataclass(frozen=True)
class EquivalenceSite:
    """One candidate semantics-preserving mutant. `kind` is one of REFACTOR_KINDS or
    TRIVIAL_KINDS -- select_equivalence_mutants uses this tag to enforce the >=50% refactor mix.
    `apply(source)` returns the full mutated module source, uniformly across all five kinds
    (some, like extract_guard_into_helper, must operate on the whole module; the others are
    wrapped to the same shape so callers never need to special-case one kind)."""

    tool: str
    kind: str
    params: dict = field(default_factory=dict)
    lineno: int = 0
    detail: str = ""

    def apply(self, source: str) -> str:
        if self.kind == "extract_guard":
            return extract_guard_into_helper(source, self.tool, **self.params)
        tree = ast.parse(source)
        original = find_function(tree, self.tool)
        fn = {
            "reorder": reorder_independent_writes,
            "arithmetic": arithmetic_equivalent,
            "rename": rename_local_variable,
            "reword": reword_raise_message,
        }[self.kind]
        mutated = fn(original, **self.params)
        if mutated is None:
            raise ValueError(f"{self.kind} produced no mutant for {self.tool}{self.params}")
        replacer = _Replacer(self.tool, mutated)
        new_tree = replacer.visit(tree)
        if replacer.count != 1:
            raise ValueError(f"expected to replace exactly one {self.tool!r}, replaced {replacer.count}")
        ast.fix_missing_locations(new_tree)
        return ast.unparse(new_tree)


# ---------------------------------------------------------------------------------------------
# reorder_independent_writes
# ---------------------------------------------------------------------------------------------


def _write_root(stmt: ast.stmt) -> Optional[str]:
    """The base variable name a state-write statement writes through, e.g. `src["balance"] = ..`
    -> "src", `state["audit_log"].append(...)` -> "state". None if it cannot be determined (not a
    write, or the target isn't a simple Name-rooted path)."""
    if isinstance(stmt, ast.Assign):
        target = stmt.targets[0]
    elif isinstance(stmt, ast.AugAssign):
        target = stmt.target
    elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call) and isinstance(stmt.value.func, ast.Attribute):
        target = stmt.value.func.value  # the object `.append(...)` etc. is called on
    else:
        return None
    while isinstance(target, (ast.Attribute, ast.Subscript)):
        target = target.value
    return target.id if isinstance(target, ast.Name) else None


def reorder_independent_writes(func: ast.FunctionDef, pair_index: int = 0) -> Optional[ast.FunctionDef]:
    """Swap two ADJACENT top-level state writes whose target roots differ (e.g. transfer's
    `src["balance"] -= amount` / `dst["balance"] += amount` -- disjoint objects, so applying them
    in either order produces the same final state). `pair_index` selects the n-th such adjacent
    pair, for tools with more than one. Returns None if no such pair exists at that index -- a
    conservative, root-disjointness check, not a full data-flow analysis (documented in the
    module docstring's generator list): it does not prove independence for a tool where one
    write's VALUE expression reads through the other write's target under a different local
    variable name, though no toy/bank.py tool does that."""
    new_func = copy.deepcopy(func)
    pairs = [
        i for i in range(len(new_func.body) - 1)
        if is_state_write(new_func.body[i]) and is_state_write(new_func.body[i + 1])
        and _write_root(new_func.body[i]) is not None
        and _write_root(new_func.body[i + 1]) is not None
        and _write_root(new_func.body[i]) != _write_root(new_func.body[i + 1])
    ]
    if pair_index >= len(pairs):
        return None
    i = pairs[pair_index]
    new_func.body[i], new_func.body[i + 1] = new_func.body[i + 1], new_func.body[i]
    ast.fix_missing_locations(new_func)
    return new_func


# ---------------------------------------------------------------------------------------------
# extract_guard_into_helper -- whole-module transform (adds a class member)
# ---------------------------------------------------------------------------------------------


def _guard_free_names(guard: ast.If) -> list[str]:
    """Every name the guard's test/raise reads that is neither `self` nor a builtin -- exactly
    the arguments the extracted helper needs, beyond `self`. This is NOT restricted to `tool`'s
    own declared parameters: a guard commonly reads a local bound earlier in the body (e.g.
    `account = self.state["accounts"].get(account_id)`, then `if account["frozen"]: raise ...`),
    and such a local must be passed to the helper by the same name too -- it is guaranteed to be
    in scope at the guard's original call site, because the unmutated code required exactly that
    to run at all. An earlier version of this function filtered to parameters only, which silently
    dropped every such local and produced a helper that raised NameError on the very first call
    (see tests/test_mutation_equivalence.py's regression coverage)."""
    used = sorted(
        {
            n.id
            for n in ast.walk(guard)
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
        }
        - {"self"}
        - set(dir(_builtins))
    )
    return used


def extract_guard_into_helper(source: str, tool: str, body_index: int, helper_suffix: str = "extracted") -> str:
    """Pull the guard at `tool`'s `body[body_index]` (an `if test: raise ...`, same shape
    M-PRECOND targets) out into a new helper method `_check_<tool>_<helper_suffix>` on the same
    class, called from the guard's original position. Behaviour is unchanged: the helper method
    contains the exact same `if test: raise ...`, just reached through one more call frame --
    this is the textbook "extract guard into a helper" refactor named in ARCHITECTURE-FINAL.md
    sec 5. Operates on the whole module (not just the one FunctionDef) because it adds a class
    member, which mutation/operators.py's single-function replace model cannot express."""
    tree = ast.parse(source)
    func = find_function(tree, tool)
    if not (0 <= body_index < len(func.body)):
        raise ValueError(f"body_index {body_index} out of range for {tool!r}")
    guard = func.body[body_index]
    if not (isinstance(guard, ast.If) and not guard.orelse and any(isinstance(s, ast.Raise) for s in guard.body)):
        raise ValueError(f"body[{body_index}] of {tool!r} is not a simple raising guard")

    needed = _guard_free_names(guard)
    helper_name = f"_check_{tool}_{helper_suffix}"

    helper_args = ast.arguments(
        posonlyargs=[], args=[ast.arg(arg="self")] + [ast.arg(arg=n) for n in needed],
        vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[],
    )
    helper_func = ast.FunctionDef(
        name=helper_name, args=helper_args, body=[copy.deepcopy(guard)], decorator_list=[],
        returns=None, lineno=func.lineno, col_offset=func.col_offset,
    )

    call_stmt = ast.Expr(
        value=ast.Call(
            func=ast.Attribute(value=ast.Name(id="self", ctx=ast.Load()), attr=helper_name, ctx=ast.Load()),
            args=[ast.Name(id=n, ctx=ast.Load()) for n in needed],
            keywords=[],
        )
    )
    ast.copy_location(call_stmt, guard)
    ast.fix_missing_locations(call_stmt)

    class _Rewriter(ast.NodeTransformer):
        """Single pass: insert the helper method right before `tool` in its class body, and
        replace the guard with a call to it -- done together so `tool`'s FunctionDef object is
        only ever visited (and replaced) once."""

        def visit_ClassDef(self, node: ast.ClassDef) -> ast.ClassDef:  # noqa: N802
            self.generic_visit(node)
            for i, member in enumerate(node.body):
                if isinstance(member, ast.FunctionDef) and member.name == tool:
                    node.body.insert(i, helper_func)
                    break
            return node

        def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:  # noqa: N802
            if node is guard_owner[0]:
                node.body[body_index] = call_stmt
            return node

    # Identity-match the exact FunctionDef object `find_function` returned, so a same-named
    # method elsewhere (there is none in toy/bank.py, but this must not silently guess) is
    # never touched.
    guard_owner = [func]
    new_tree = _Rewriter().visit(tree)
    ast.fix_missing_locations(new_tree)
    return ast.unparse(new_tree)


# ---------------------------------------------------------------------------------------------
# arithmetic_equivalent
# ---------------------------------------------------------------------------------------------


def arithmetic_equivalent(func: ast.FunctionDef, body_index: int) -> Optional[ast.FunctionDef]:
    """Rewrite the Assign at `body_index` whose value is `a + b` or `a - b` into an IEEE-754
    bit-identical equivalent form: `a + b` -> `b + a` (float/int addition is exactly commutative),
    `a - b` -> `a + (-b)` (subtraction is defined as correctly-rounded addition of the negation,
    so this is exact, not approximate). Returns None if body_index does not name such a
    statement."""
    new_func = copy.deepcopy(func)
    if not (0 <= body_index < len(new_func.body)):
        return None
    stmt = new_func.body[body_index]
    if not (isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.BinOp)):
        return None
    op = stmt.value.op
    left, right = stmt.value.left, stmt.value.right
    if isinstance(op, ast.Add):
        stmt.value = ast.BinOp(left=right, op=ast.Add(), right=left)
    elif isinstance(op, ast.Sub):
        stmt.value = ast.BinOp(left=left, op=ast.Add(), right=ast.UnaryOp(op=ast.USub(), operand=right))
    else:
        return None
    ast.fix_missing_locations(new_func)
    return new_func


# ---------------------------------------------------------------------------------------------
# Trivial edits -- included only because the plan permits up to half of the pool to be these;
# they carry no evidentiary weight on their own (module docstring).
# ---------------------------------------------------------------------------------------------


def rename_local_variable(func: ast.FunctionDef, old_name: str, new_name: Optional[str] = None) -> Optional[ast.FunctionDef]:
    """Consistently rename one non-parameter local variable throughout `func`. Returns None if
    `old_name` is a parameter (renaming a parameter would change the call signature, which is not
    what this control is meant to test) or is not actually bound anywhere in the body."""
    param_names = {a.arg for a in func.args.args}
    if old_name in param_names:
        return None
    bound_anywhere = any(
        isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store) and n.id == old_name
        for n in ast.walk(func)
    )
    if not bound_anywhere:
        return None
    new_name = new_name or f"{old_name}_renamed"
    new_func = copy.deepcopy(func)
    for node in ast.walk(new_func):
        if isinstance(node, ast.Name) and node.id == old_name:
            node.id = new_name
    ast.fix_missing_locations(new_func)
    return new_func


def reword_raise_message(func: ast.FunctionDef, body_index: int) -> Optional[ast.FunctionDef]:
    """Change the string literal message of the Raise inside the guard at `body_index` -- text
    no predicate ever reads (predicates see `result.error is present`, never its content; see
    spec/PREDICATE-GRAMMAR.md sec 1), so this can never change any clause's verdict."""
    new_func = copy.deepcopy(func)
    if not (0 <= body_index < len(new_func.body)):
        return None
    stmt = new_func.body[body_index]
    if not isinstance(stmt, ast.If):
        return None
    raises = [s for s in stmt.body if isinstance(s, ast.Raise)]
    if not raises:
        return None
    call = raises[0].exc
    if not (isinstance(call, ast.Call) and call.args):
        return None
    call.args[0] = ast.Constant(value="rejected (reworded control message)")
    ast.fix_missing_locations(new_func)
    return new_func


# ---------------------------------------------------------------------------------------------
# Enumeration and mixed, quota-respecting selection
# ---------------------------------------------------------------------------------------------


def enumerate_equivalence_sites(source: str, tool_names: "list[str] | tuple[str, ...]") -> list[EquivalenceSite]:
    """Every candidate equivalence-mutant site across `tool_names`, across all five kinds."""
    tree = ast.parse(source)
    sites: list[EquivalenceSite] = []

    for name in tool_names:
        func = find_function(tree, name)

        pairs = [
            i for i in range(len(func.body) - 1)
            if is_state_write(func.body[i]) and is_state_write(func.body[i + 1])
            and _write_root(func.body[i]) is not None
            and _write_root(func.body[i + 1]) is not None
            and _write_root(func.body[i]) != _write_root(func.body[i + 1])
        ]
        for n in range(len(pairs)):
            sites.append(EquivalenceSite(tool=name, kind="reorder", params={"pair_index": n}, lineno=func.lineno))

        for i, stmt in enumerate(func.body):
            if isinstance(stmt, ast.If) and not stmt.orelse and any(isinstance(s, ast.Raise) for s in stmt.body):
                sites.append(EquivalenceSite(tool=name, kind="extract_guard", params={"body_index": i}, lineno=stmt.lineno))

        for i, stmt in enumerate(func.body):
            if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.BinOp) and isinstance(stmt.value.op, (ast.Add, ast.Sub)):
                sites.append(EquivalenceSite(tool=name, kind="arithmetic", params={"body_index": i}, lineno=stmt.lineno))

        param_names = {a.arg for a in func.args.args}
        local_names = sorted(
            {n.id for n in ast.walk(func) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)} - param_names
        )
        for local in local_names:
            sites.append(EquivalenceSite(tool=name, kind="rename", params={"old_name": local}, lineno=func.lineno))

        for i, stmt in enumerate(func.body):
            if isinstance(stmt, ast.If) and any(isinstance(s, ast.Raise) for s in stmt.body):
                sites.append(EquivalenceSite(tool=name, kind="reword", params={"body_index": i}, lineno=stmt.lineno))

    return sites


def select_equivalence_mutants(
    sites: list[EquivalenceSite], n: int, seed: int, min_refactor_fraction: float = 0.5
) -> list[EquivalenceSite]:
    """Seeded selection of up to `n` equivalence-preserving mutants with at least
    `min_refactor_fraction` drawn from REFACTOR_KINDS (sec 3 / W5: "at least half ... must be
    refactorings of advertised behaviour"). Fills the refactor quota first, then tops up with
    trivial-kind sites; if the refactor pool itself is smaller than the quota, reports fewer than
    `n` rather than silently backfilling the shortfall from trivial kinds (the same
    no-substitution discipline mutation/sites.py's select_sites applies)."""
    import random

    rng = random.Random(seed)
    refactor_pool = [s for s in sites if s.kind in REFACTOR_KINDS]
    trivial_pool = [s for s in sites if s.kind in TRIVIAL_KINDS]
    rng.shuffle(refactor_pool)
    rng.shuffle(trivial_pool)

    min_refactors = min(len(refactor_pool), max(1, round(n * min_refactor_fraction)) if n > 0 else 0)
    chosen = refactor_pool[:min_refactors]
    remaining = n - len(chosen)
    chosen += trivial_pool[:remaining]
    remaining = n - len(chosen)
    if remaining > 0:
        chosen += refactor_pool[min_refactors : min_refactors + remaining]
    return chosen[:n]
