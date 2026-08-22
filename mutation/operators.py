"""The six AST-level mutation operators, one per defect class, as specified in
ARCHITECTURE.md sec 5 / ARCHITECTURE-FINAL.md sec 5 ("Closed-world arm (as v1)"):

    M-PHANTOM   replace mutation body with a success-return stub (signature/return preserved)
    M-PRECOND   delete or negate one guard clause
    M-IGNARG    rebind one effective argument to a constant/default inside the body
    M-PARTIAL   delete one of >=2 state writes in the effect block
    M-INVAR     remove the compensating write in a paired operation (e.g., release without decrement)
    M-RESET     remove one field assignment from the reset routine

Every operator here is a pure, generic `ast.FunctionDef -> ast.FunctionDef` transform: no
benchmark name, no tool name, and no domain vocabulary appears anywhere in this module. Each
function takes a deep-copyable FunctionDef plus the small amount of structural information
mutation/sites.py already had to compute to *find* the site (a statement index, an argument
name, ...) and returns a new, mutated FunctionDef. Callers are responsible for splicing the
result back into a module (mutation/sites.py and the (not-yet-built) real-corpus generator do
this by replacing the matching top-level/class-body FunctionDef node and recompiling).

M-INVAR's site-selection rule, spelled out because it is a modeling decision translating prose
("the compensating write in a paired operation") into something mechanical: a write statement
that sits directly inside the body or orelse of a top-level `if` which is NOT itself a
precondition guard (i.e. does not raise) is treated as a candidate compensating write, and the
operator deletes it. This is a structural criterion (conditional effect-write vs. unconditional
effect-write), not a semantic one -- it will also admit sites that are conditional but not
literally "paired" in the strict prose sense (e.g. an argument-dispatch branch), alongside true
compensating pairs like toy/bank.py's release_lock. Recorded here and in the top-level build
report rather than silently narrowed to hand-picked pairs, which would violate "no
per-benchmark tuning".
"""
from __future__ import annotations

import ast
import builtins as _builtins
import copy

__all__ = [
    "OPERATORS",
    "MutationError",
    "is_guard",
    "is_state_write",
    "default_for_annotation",
    "m_phantom",
    "m_precond",
    "m_ignarg",
    "m_partial",
    "m_invar",
    "m_reset",
    "apply_operator",
]

OPERATORS = ("M-PHANTOM", "M-PRECOND", "M-IGNARG", "M-PARTIAL", "M-INVAR", "M-RESET")

_MUTATING_METHODS = frozenset({"append", "extend", "update", "pop", "remove", "insert", "clear"})


class MutationError(Exception):
    """Raised when a requested site does not exist in the given function (e.g. a stale index
    after the source changed) -- never silently no-ops."""


# ---------------------------------------------------------------------------------------------
# Structural predicates shared with mutation/sites.py (site enumeration must agree with what the
# operators can actually act on, so both import these rather than duplicating the rules).
# ---------------------------------------------------------------------------------------------


def is_guard(stmt: ast.stmt) -> bool:
    """True iff `stmt` is a precondition guard: a top-level `if` with no `else`/`elif` whose
    body raises. This is M-PRECOND's target shape and also what M-INVAR's rule excludes."""
    if not isinstance(stmt, ast.If):
        return False
    if stmt.orelse:
        return False
    return any(isinstance(s, ast.Raise) for s in stmt.body)


def is_state_write(stmt: ast.stmt) -> bool:
    """True iff `stmt` mutates something reached through a subscript/attribute path (a state
    write), as opposed to a plain local-variable binding like `account = state[...].get(...)`.

        account["balance"] = ...        -> True   (Subscript target)
        lock.count = ...                -> True   (Attribute target)
        account = state["accounts"][id] -> False  (Name target -- a local lookup, not a write)
        state["audit_log"].append(...)  -> True   (call to a known mutating method)
    """
    if isinstance(stmt, (ast.Assign, ast.AugAssign)):
        targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
        return any(isinstance(t, (ast.Subscript, ast.Attribute)) for t in targets)
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
        call = stmt.value
        if isinstance(call.func, ast.Attribute) and call.func.attr in _MUTATING_METHODS:
            return True
    return False


_ANNOTATION_DEFAULTS = {"str": "", "int": 0, "float": 0.0, "bool": False}


def default_for_annotation(arg: ast.arg) -> object:
    """Type-appropriate zero/empty default read off the argument's own declared annotation --
    the "constant/default" M-IGNARG rebinds to. Purely structural: it reads only this function's
    own AST, never a benchmark's type system or docs. Falls back to None for an unannotated or
    unrecognised annotation, which is still a valid (and typically maximally disruptive)
    constant to shadow with."""
    ann = arg.annotation
    if isinstance(ann, ast.Name) and ann.id in _ANNOTATION_DEFAULTS:
        return _ANNOTATION_DEFAULTS[ann.id]
    return None


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise MutationError(msg)


def _delete_stmt(body: list, index: int) -> None:
    """Delete `body[index]` in place, backfilling with `pass` if that empties the block --
    Python's grammar forbids an empty suite (an `if`, `for`, function body, ...  with zero
    statements is a SyntaxError), and every one of M-PRECOND(delete)/M-PARTIAL/M-INVAR/M-RESET
    can legitimately delete a block's only statement (e.g. `if count == 0: held_by = None`, whose
    body is that single write)."""
    removed = body.pop(index)
    if not body:
        pass_stmt = ast.Pass()
        ast.copy_location(pass_stmt, removed)
        body.append(pass_stmt)


# ---------------------------------------------------------------------------------------------
# M-PHANTOM -- collapse the whole body to its own success return, dropping every guard and write.
# ---------------------------------------------------------------------------------------------


def _references_undefined_name(node: ast.AST, allowed: frozenset) -> bool:
    """True iff any Name loaded anywhere inside `node` is not in `allowed`."""
    return any(
        isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id not in allowed
        for n in ast.walk(node)
    )


def _scrub_return_value(value: ast.expr, allowed: frozenset) -> ast.expr:
    """Make a kept return expression runnable once every guard/write statement that computed its
    locals has been deleted. Scrubs at the level of whole sub-expressions, not individual Name
    leaves: for the common `{"k1": expr1, "k2": expr2, ...}` shape (every toy/bank.py tool
    returns a dict literal), each VALUE that references an undefined local is replaced by a bare
    `None` in full -- never a partial substitution like `list(None)`, which is well-typed AST but
    can raise at runtime (`list(None)` -- TypeError) and would turn a "phantom success" mutant
    into a crash, defeating the point of M-PHANTOM. A leaf-level scrub tried first and was wrong
    for exactly this reason (`list(item["tags"])` -> `list(None)`); this whole-value scrub is
    the fix, and the toy tag_item.M-PHANTOM regression test pins it.

    Non-dict return expressions get the same treatment one level up: if the *whole* expression
    references an undefined name, the whole thing becomes `None` (there is no smaller, always-
    safe unit to preserve without shape-specific knowledge)."""
    if isinstance(value, ast.Dict):
        new_values = [
            ast.Constant(value=None) if _references_undefined_name(v, allowed) else v
            for v in value.values
        ]
        value.values = new_values
        return value
    if _references_undefined_name(value, allowed):
        return ast.Constant(value=None)
    return value


def m_phantom(func: ast.FunctionDef) -> ast.FunctionDef:
    """Replace `func`'s entire body with just its final Return statement (by source position),
    keeping the signature untouched. If the function has no Return anywhere (e.g. a reset()-style
    procedure), the stub is `return None` -- still "signature/return preserved" in the sense that
    a caller observing only the return value sees no change, while every guard and every state
    write is gone. This is deliberately the strongest, most generic reading of "success-return
    stub": no benchmark-specific notion of what counts as a "success value" is needed because the
    mutant reuses the function's own real return expression verbatim.

    The kept return expression may reference a local variable computed by a guard/write statement
    that this operator just deleted (e.g. `return {"balance": account["balance"]}` after
    `account = ...` is gone). `_scrub_return_value` collapses any such now-undefined reference to
    `None` so the stub is always runnable -- parameters, `self`, and builtins are left alone,
    everything else the function itself ever bound is not."""
    new_func = copy.deepcopy(func)
    # "Undefined" means "a local this function bound and then had removed" -- NOT a builtin.
    # Builtins (list, len, str, ...) are always resolvable at call time (the mutant module still
    # execs with normal builtins in scope) and must be left alone.
    allowed = frozenset({"self"} | {a.arg for a in new_func.args.args} | set(dir(_builtins)))
    returns = [n for n in ast.walk(new_func) if isinstance(n, ast.Return)]
    if returns:
        final_return = max(returns, key=lambda r: (r.lineno, r.col_offset))
        stub_return = copy.deepcopy(final_return)
        if stub_return.value is not None:
            stub_return.value = _scrub_return_value(stub_return.value, allowed)
        new_func.body = [stub_return]
    else:
        new_func.body = [ast.Return(value=ast.Constant(value=None))]
    ast.fix_missing_locations(new_func)
    return new_func


# ---------------------------------------------------------------------------------------------
# M-PRECOND -- delete or negate one top-level guard.
# ---------------------------------------------------------------------------------------------


def m_precond(func: ast.FunctionDef, body_index: int, mode: str = "delete") -> ast.FunctionDef:
    """Delete (`mode="delete"`) or negate the test of (`mode="negate"`) the guard at
    `func.body[body_index]`. `body_index` must name a statement satisfying `is_guard`."""
    _require(mode in ("delete", "negate"), f"unknown M-PRECOND mode: {mode!r}")
    new_func = copy.deepcopy(func)
    _require(0 <= body_index < len(new_func.body), f"body_index {body_index} out of range")
    stmt = new_func.body[body_index]
    _require(is_guard(stmt), f"body_index {body_index} is not a guard: {ast.dump(stmt)[:80]}")
    if mode == "delete":
        _delete_stmt(new_func.body, body_index)
    else:
        stmt.test = ast.UnaryOp(op=ast.Not(), operand=stmt.test)
        ast.copy_location(stmt.test, stmt)
    ast.fix_missing_locations(new_func)
    return new_func


# ---------------------------------------------------------------------------------------------
# M-IGNARG -- shadow one effective argument to a constant at function entry.
# ---------------------------------------------------------------------------------------------


def m_ignarg(func: ast.FunctionDef, arg_name: str, constant: object = ...) -> ast.FunctionDef:
    """Insert `arg_name = <constant>` as the function's first statement, shadowing the caller's
    value for the rest of the body. `constant` defaults to `default_for_annotation` for the named
    parameter; pass an explicit value to override it."""
    new_func = copy.deepcopy(func)
    arg_node = next((a for a in new_func.args.args if a.arg == arg_name), None)
    _require(arg_node is not None, f"no such argument: {arg_name!r}")
    value = default_for_annotation(arg_node) if constant is ... else constant
    _require(isinstance(value, (str, int, float, bool, type(None))), f"unsupported constant type: {type(value)!r}")
    stub = ast.Assign(targets=[ast.Name(id=arg_name, ctx=ast.Store())], value=ast.Constant(value=value))
    anchor = new_func.body[0] if new_func.body else new_func
    ast.copy_location(stub, anchor)
    for node in ast.walk(stub):
        ast.copy_location(node, anchor)
    new_func.body.insert(0, stub)
    ast.fix_missing_locations(new_func)
    return new_func


# ---------------------------------------------------------------------------------------------
# M-PARTIAL -- delete one top-level (unconditional) state write.
# ---------------------------------------------------------------------------------------------


def m_partial(func: ast.FunctionDef, body_index: int) -> ast.FunctionDef:
    """Delete the top-level state-write statement at `func.body[body_index]`. Callers (see
    mutation/sites.py) are responsible for only offering an index when the function has >=2 such
    top-level writes, per ARCHITECTURE.md sec 5 -- this function itself only checks that the
    targeted statement is in fact a state write, not the >=2 cardinality rule, which is a
    site-selection property rather than something a single call can check."""
    new_func = copy.deepcopy(func)
    _require(0 <= body_index < len(new_func.body), f"body_index {body_index} out of range")
    stmt = new_func.body[body_index]
    _require(is_state_write(stmt), f"body_index {body_index} is not a state write: {ast.dump(stmt)[:80]}")
    _delete_stmt(new_func.body, body_index)
    ast.fix_missing_locations(new_func)
    return new_func


# ---------------------------------------------------------------------------------------------
# M-INVAR -- delete a state write nested one level inside a non-guard top-level `if`.
# ---------------------------------------------------------------------------------------------


def m_invar(func: ast.FunctionDef, if_index: int, branch: str, branch_index: int) -> ast.FunctionDef:
    """Delete the state-write statement at `func.body[if_index].<branch>[branch_index]`, where
    `branch` is "body" or "orelse" and `func.body[if_index]` is a non-guard `if` (see module
    docstring for the site-selection rule this encodes)."""
    _require(branch in ("body", "orelse"), f"unknown branch: {branch!r}")
    new_func = copy.deepcopy(func)
    _require(0 <= if_index < len(new_func.body), f"if_index {if_index} out of range")
    if_stmt = new_func.body[if_index]
    _require(isinstance(if_stmt, ast.If), f"if_index {if_index} is not an If")
    _require(not is_guard(if_stmt), f"if_index {if_index} is a precondition guard, not an M-INVAR site")
    branch_list = getattr(if_stmt, branch)
    _require(0 <= branch_index < len(branch_list), f"branch_index {branch_index} out of range")
    stmt = branch_list[branch_index]
    _require(is_state_write(stmt), f"target statement is not a state write: {ast.dump(stmt)[:80]}")
    _delete_stmt(branch_list, branch_index)
    ast.fix_missing_locations(new_func)
    return new_func


# ---------------------------------------------------------------------------------------------
# M-RESET -- delete one field assignment from a reset routine.
# ---------------------------------------------------------------------------------------------


def m_reset(func: ast.FunctionDef, body_index: int) -> ast.FunctionDef:
    """Delete the top-level field-assignment statement at `func.body[body_index]` of a reset
    routine. Mechanically identical to m_partial -- kept as a separate name because its intended
    site pool (functions named "reset"/"reset_*") and its reported defect class (Reset Leak,
    not Partial Effect) are different, and conflating the two names would hide that in call
    sites and in mutation/score.py's per-operator reporting."""
    new_func = copy.deepcopy(func)
    _require(0 <= body_index < len(new_func.body), f"body_index {body_index} out of range")
    stmt = new_func.body[body_index]
    _require(is_state_write(stmt), f"body_index {body_index} is not a field assignment: {ast.dump(stmt)[:80]}")
    _delete_stmt(new_func.body, body_index)
    ast.fix_missing_locations(new_func)
    return new_func


# ---------------------------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------------------------


def apply_operator(operator: str, func: ast.FunctionDef, **params) -> ast.FunctionDef:
    """Apply one of the six operators by name. `params` are forwarded to the matching function
    (e.g. body_index=, mode=, arg_name=, if_index=, branch=, branch_index=). Used by
    mutation/sites.py's MutationSite.apply() so the six functions above never need to be imported
    by name at call sites that only know an operator string."""
    dispatch = {
        "M-PHANTOM": lambda: m_phantom(func),
        "M-PRECOND": lambda: m_precond(func, **params),
        "M-IGNARG": lambda: m_ignarg(func, **params),
        "M-PARTIAL": lambda: m_partial(func, **params),
        "M-INVAR": lambda: m_invar(func, **params),
        "M-RESET": lambda: m_reset(func, **params),
    }
    _require(operator in dispatch, f"unknown operator: {operator!r}")
    return dispatch[operator]()
