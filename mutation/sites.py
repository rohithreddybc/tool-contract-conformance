"""Programmatic mutation-site enumeration and seeded selection.

experiments/detector_analysis_plan.md sec 3 / ARCHITECTURE-FINAL.md sec 5: sites are enumerated
across every conformant tool's AST, never hand-picked, and the tools carrying confirmed findings
are excluded from the corpus -- they are anchor cases, and mutating them would let the checker
rediscover what it already found. Both rules are implemented here as generic parameters
(`excluded_tools`), not baked in for any one benchmark.

This module walks *source* (a module's text), finds each named tool's FunctionDef, and classifies
its top-level statements into candidate sites for the six operators in mutation/operators.py using
exactly the structural predicates operators.py exports (`is_guard`, `is_state_write`) -- so a site
this module reports is always one operators.py can actually mutate.
"""
from __future__ import annotations

import ast
import random
from dataclasses import dataclass, field
from typing import Optional

from mutation.operators import apply_operator, is_guard, is_state_write

__all__ = [
    "MutationSite",
    "MutantModule",
    "find_function",
    "enumerate_sites",
    "select_sites",
    "materialize_mutant_source",
    "load_class_from_source",
]


@dataclass(frozen=True)
class MutationSite:
    """One candidate mutation site. `tool` is the function/method name it targets; `operator` is
    one of mutation.operators.OPERATORS; `params` are the keyword arguments `apply_operator`
    needs (body_index, mode, arg_name, if_index, branch, branch_index -- operator-dependent);
    `detail` is a short human-readable description for reporting, never used for matching."""

    tool: str
    operator: str
    params: dict = field(default_factory=dict)
    lineno: int = 0
    detail: str = ""

    def apply(self, source: str) -> str:
        """Convenience: materialize the mutated module source for this one site. See
        `materialize_mutant_source`."""
        return materialize_mutant_source(source, self.tool, self.operator, self.params)


@dataclass(frozen=True)
class MutantModule:
    """A materialized mutant: the full mutated module source plus the site that produced it, for
    reporting and re-derivation."""

    site: MutationSite
    source: str


# ---------------------------------------------------------------------------------------------
# Finding and replacing a named function/method anywhere in a module's AST.
# ---------------------------------------------------------------------------------------------


class _Finder(ast.NodeVisitor):
    def __init__(self, name: str):
        self.name = name
        self.found: list[ast.FunctionDef] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802 (ast visitor naming)
        if node.name == self.name:
            self.found.append(node)
        self.generic_visit(node)


def find_function(tree: ast.Module, name: str) -> ast.FunctionDef:
    """The unique FunctionDef named `name` anywhere in `tree`. Raises ValueError if it is
    missing or ambiguous (more than one method/function sharing the name) -- callers should pass
    a name that is unique within the module, which every toy/bank.py tool name is."""
    finder = _Finder(name)
    finder.visit(tree)
    if not finder.found:
        raise ValueError(f"no function named {name!r} found")
    if len(finder.found) > 1:
        raise ValueError(f"function name {name!r} is ambiguous ({len(finder.found)} matches)")
    return finder.found[0]


class _Replacer(ast.NodeTransformer):
    def __init__(self, name: str, replacement: ast.FunctionDef):
        self.name = name
        self.replacement = replacement
        self.count = 0

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:  # noqa: N802
        if node.name == self.name:
            self.count += 1
            return self.replacement
        self.generic_visit(node)
        return node


def materialize_mutant_source(source: str, tool: str, operator: str, params: dict) -> str:
    """Parse `source`, replace the FunctionDef named `tool` with the result of applying
    `operator` (see mutation.operators.apply_operator) to it, and return the mutated module as
    source text (via ast.unparse). The original `source` string is untouched; this always
    returns a new string."""
    tree = ast.parse(source)
    original = find_function(tree, tool)
    mutated = apply_operator(operator, original, **params)
    replacer = _Replacer(tool, mutated)
    new_tree = replacer.visit(tree)
    if replacer.count != 1:
        raise ValueError(f"expected to replace exactly one {tool!r}, replaced {replacer.count}")
    ast.fix_missing_locations(new_tree)
    return ast.unparse(new_tree)


def load_class_from_source(source: str, class_name: str, module_name: str = "_mutant_module") -> type:
    """Exec mutated module source in a fresh namespace and return the named class -- the runnable
    counterpart of `materialize_mutant_source`, used by mutation/score.py to actually instantiate
    a mutant and invoke its tools against a live state dict."""
    namespace: dict = {"__name__": module_name}
    code = compile(source, f"<{module_name}>", "exec")
    exec(code, namespace)  # noqa: S102 -- mutant module is our own AST-transformed source, not attacker input
    if class_name not in namespace:
        raise ValueError(f"{class_name!r} not defined in mutated module")
    return namespace[class_name]


# ---------------------------------------------------------------------------------------------
# Enumeration
# ---------------------------------------------------------------------------------------------


def _partial_sites(tool: str, func: ast.FunctionDef) -> list[MutationSite]:
    write_indices = [i for i, s in enumerate(func.body) if is_state_write(s)]
    if len(write_indices) < 2:
        return []
    return [
        MutationSite(
            tool=tool, operator="M-PARTIAL", params={"body_index": i}, lineno=func.body[i].lineno,
            detail=f"delete top-level write #{n + 1}/{len(write_indices)}: {ast.dump(func.body[i])[:60]}",
        )
        for n, i in enumerate(write_indices)
    ]


def _precond_sites(tool: str, func: ast.FunctionDef) -> list[MutationSite]:
    sites: list[MutationSite] = []
    for i, stmt in enumerate(func.body):
        if not is_guard(stmt):
            continue
        for mode in ("delete", "negate"):
            sites.append(
                MutationSite(
                    tool=tool, operator="M-PRECOND", params={"body_index": i, "mode": mode},
                    lineno=stmt.lineno, detail=f"{mode} guard at body[{i}]",
                )
            )
    return sites


def _invar_sites(tool: str, func: ast.FunctionDef) -> list[MutationSite]:
    sites: list[MutationSite] = []
    for i, stmt in enumerate(func.body):
        if not isinstance(stmt, ast.If) or is_guard(stmt):
            continue
        for branch_name in ("body", "orelse"):
            for j, inner in enumerate(getattr(stmt, branch_name)):
                if not is_state_write(inner):
                    continue
                sites.append(
                    MutationSite(
                        tool=tool, operator="M-INVAR",
                        params={"if_index": i, "branch": branch_name, "branch_index": j},
                        lineno=inner.lineno,
                        detail=f"delete conditional write in body[{i}].{branch_name}[{j}]",
                    )
                )
    return sites


def _ignarg_sites(tool: str, func: ast.FunctionDef) -> list[MutationSite]:
    sites: list[MutationSite] = []
    param_names = {a.arg for a in func.args.args} - {"self"}
    used_names = {n.id for n in ast.walk(func) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
    for name in sorted(param_names & used_names):
        sites.append(
            MutationSite(
                tool=tool, operator="M-IGNARG", params={"arg_name": name},
                lineno=func.lineno, detail=f"shadow argument {name!r} to its type default",
            )
        )
    return sites


def _phantom_site(tool: str, func: ast.FunctionDef) -> list[MutationSite]:
    return [
        MutationSite(
            tool=tool, operator="M-PHANTOM", params={}, lineno=func.lineno,
            detail="collapse whole body to its final return",
        )
    ]


def _reset_sites(tool: str, func: ast.FunctionDef) -> list[MutationSite]:
    return [
        MutationSite(
            tool=tool, operator="M-RESET", params={"body_index": i}, lineno=stmt.lineno,
            detail=f"delete reset field assignment at body[{i}]",
        )
        for i, stmt in enumerate(func.body)
        if is_state_write(stmt)
    ]


def enumerate_sites(
    source: str,
    tool_names: "list[str] | tuple[str, ...]",
    *,
    reset_names: "list[str] | tuple[str, ...]" = ("reset",),
    excluded_tools: frozenset = frozenset(),
) -> list[MutationSite]:
    """Every candidate site across `tool_names` (M-PHANTOM/M-PRECOND/M-IGNARG/M-PARTIAL/M-INVAR)
    and `reset_names` (M-RESET only), parsed once from `source`.

    `excluded_tools` implements CLAUDE.md / detector_analysis_plan.md sec 3's rule: tools
    carrying confirmed findings never enter the mutation corpus. It is checked against
    `tool_names` only -- a reset routine is never itself "a tool carrying a confirmed finding"
    in this project's finding taxonomy, so `reset_names` is not filtered by it.
    """
    tree = ast.parse(source)
    sites: list[MutationSite] = []

    for name in tool_names:
        if name in excluded_tools:
            continue
        func = find_function(tree, name)
        sites += _phantom_site(name, func)
        sites += _precond_sites(name, func)
        sites += _ignarg_sites(name, func)
        sites += _partial_sites(name, func)
        sites += _invar_sites(name, func)

    for name in reset_names:
        func = find_function(tree, name)
        sites += _reset_sites(name, func)

    return sites


def select_sites(sites: list[MutationSite], operator: str, k: int, seed: int) -> list[MutationSite]:
    """Seeded random draw of up to `k` sites for one operator, per detector_analysis_plan.md
    sec 3 ("Sample ... drawn by seeded random selection from the enumerated site pool") --
    never hand-picked. Returns fewer than `k` (never more, never a substitution from another
    operator) when the pool is smaller, matching sec 3's "the actual number is reported and no
    substitution from another class is made"."""
    pool = [s for s in sites if s.operator == operator]
    rng = random.Random(seed)
    rng.shuffle(pool)
    return pool[:k]
