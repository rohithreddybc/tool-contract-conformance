"""Adapter-driven mutant invocation -- the wiring the pre-registered plan calls for but does not
itself specify at the mechanism level (it commits to STATISTICS and SCORING RULES; how a mutant
of a REAL benchmark tool gets executed is an implementation decision). Nothing in
mutation/{operators,sites,equivalence,probes,score}.py is modified by this module; every function
here only imports and calls them.

Three pieces:

    build_function_patch_source   -- one FunctionDef in, one decorator-free `def ...: ...`
                                      source string out. Works for any of the six defect
                                      operators (mutation/operators.py) and for the four
                                      single-function equivalence generators
                                      (mutation/equivalence.py) alike, since every one of them is
                                      already documented as a pure `ast.FunctionDef ->
                                      ast.FunctionDef` transform. NOT used for
                                      `extract_guard_into_helper`, which adds a class member and
                                      cannot be expressed as one function's replacement -- see
                                      `EQUIVALENCE_TRANSFORMS`' docstring.

    MutatedAdapter                 -- wraps a live base Adapter so that every fresh_env() it
                                      hands out already has ONE tool patched to a mutant's
                                      implementation, via the new adapters.base.Adapter.patch_tool
                                      surface (adapters/base.py, adapters/tau2.py, adapters/
                                      agentdojo.py, adapters/mmtoolsandbox.py, toy/adapter.py --
                                      new this experiment, described in each's own docstring).
                                      Passing a MutatedAdapter anywhere an Adapter is expected
                                      (dynamic.harness.run_contract, is_behaviorally_live_adapter)
                                      requires zero changes to either.

    is_behaviorally_live_adapter   -- mutation/score.py's `is_behaviorally_live`, generalised from
                                      "two zero-arg-constructible classes" (the toy-only shape) to
                                      "two live Adapters", so the SAME sec 4.1 survival definition
                                      applies uniformly to toy and real tools. mutation/score.py's
                                      own `is_behaviorally_live` is untouched; this is a parallel
                                      function, not an edit.
"""
from __future__ import annotations

import ast
import copy
from typing import Any, Callable, Optional

from adapters.base import Adapter, EnvHandle, SourceRef, ToolRef, ToolResult
from adapters.contract_check import to_result_binding
from core.canonical import CanonicalConfig, canonical_equal
from mutation.equivalence import (
    arithmetic_equivalent,
    rename_local_variable,
    reorder_independent_writes,
    reword_raise_message,
)
from mutation.operators import apply_operator
from mutation.sites import find_function

__all__ = [
    "build_function_patch_source",
    "EQUIVALENCE_TRANSFORMS",
    "build_equivalence_patch_source",
    "MutatedAdapter",
    "is_behaviorally_live_adapter",
]


def build_function_patch_source(module_source: str, tool: str, operator: str, params: dict) -> str:
    """Parse `module_source`, apply defect `operator` (mutation.operators.apply_operator) to the
    FunctionDef named `tool`, strip its decorator_list (nothing on the receiving end re-executes
    a decorator -- adapters/_tau2_worker.py's `_cmd_patch_tool` copies the marker attributes
    (`__tool__`, ...) it needs directly onto the new function object instead), and return the
    unparsed function source alone -- NOT the whole module. This is deliberately a narrower
    product than mutation.sites.materialize_mutant_source (whole-module replace-and-unparse,
    built for `load_class_from_source`'s "exec a fresh module, get a class" toy-only path); a
    live Adapter's `patch_tool` only ever needs the one function."""
    tree = ast.parse(module_source)
    original = find_function(tree, tool)
    mutated = apply_operator(operator, original, **params)
    mutated.decorator_list = []
    ast.fix_missing_locations(mutated)
    return ast.unparse(mutated)


# sec 3 / W5's precision-control generators that are single-FunctionDef-in/out transforms, and
# therefore expressible as a `patch_tool` snippet exactly like the six defect operators.
# `extract_guard_into_helper` is deliberately NOT here: it adds a sibling class member
# (mutation/equivalence.py's own docstring: "whole-MODULE transform, since it adds a class
# member"), which the single-function patch contract this experiment's adapters.patch_tool
# implements cannot express for a live tau2/AgentDojo/MM-ToolSandbox object -- reported as a
# scope note in report/mutation_summary.md rather than silently generalised to something it
# cannot safely express (it is still exercised, unmodified, by its own dedicated unit tests in
# tests/test_mutation_equivalence.py against the toy class-loading path).
EQUIVALENCE_TRANSFORMS: "dict[str, Callable]" = {
    "reorder": reorder_independent_writes,
    "arithmetic": arithmetic_equivalent,
    "rename": rename_local_variable,
    "reword": reword_raise_message,
}


def build_equivalence_patch_source(module_source: str, tool: str, kind: str, params: dict) -> Optional[str]:
    """Single-function counterpart of `build_function_patch_source`, for the precision-control
    pool. Returns None if the transform reports no mutant is possible for these params (mirrors
    mutation.equivalence's own generators, which return None rather than raising for that case)."""
    tree = ast.parse(module_source)
    original = find_function(tree, tool)
    transform = EQUIVALENCE_TRANSFORMS[kind]
    mutated = transform(original, **params)
    if mutated is None:
        return None
    mutated.decorator_list = []
    ast.fix_missing_locations(mutated)
    return ast.unparse(mutated)


class MutatedAdapter(Adapter):
    """Delegates every Adapter method to `base`, except that `fresh_env`/`reset` always leave
    `tool` patched to `mutant_source` on the handle they return. See adapters/base.py's
    `patch_tool` docstring for why this is enough regardless of whether the underlying adapter
    scopes its patch to one EnvHandle (tau2, toy) or process-wide (AgentDojo, MM-ToolSandbox) --
    either way, every env this class hands out has the mutant installed before a caller can
    invoke anything on it. Always call `close()` (or use as a context manager) when done scoring
    one mutant: for a process-wide-patch adapter this is the only thing that restores the
    original implementation before the next mutant is tried."""

    def __init__(self, base: Adapter, tool: str, mutant_source: str):
        self._base = base
        self._tool = tool
        self._mutant_source = mutant_source

    def list_tools(self) -> "list[ToolRef]":
        return self._base.list_tools()

    def fresh_env(self, scenario_id: str) -> EnvHandle:
        env = self._base.fresh_env(scenario_id)
        self._base.patch_tool(env, self._tool, self._mutant_source)
        return env

    def snapshot(self, env: EnvHandle) -> dict:
        return self._base.snapshot(env)

    def invoke(self, env: EnvHandle, tool: str, args: dict) -> ToolResult:
        return self._base.invoke(env, tool, args)

    def reset(self, env: EnvHandle) -> None:
        self._base.reset(env)
        self._base.patch_tool(env, self._tool, self._mutant_source)

    def source(self, tool: str) -> SourceRef:
        return self._base.source(tool)

    def __enter__(self) -> "MutatedAdapter":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def close(self) -> None:
        self._base.unpatch_tool(self._tool)


def is_behaviorally_live_adapter(
    base_adapter: Adapter,
    mutant_adapter: Adapter,
    scenario_id: str,
    tool: str,
    probe_args_list: "list[dict]",
    cfg: Optional[CanonicalConfig] = None,
) -> bool:
    """mutation.score.is_behaviorally_live, generalised from two zero-arg-constructible classes
    to two live Adapters -- same sec 4.1 definition ("a canonicalized post-state or a
    canonicalized result differing from the unmutated tool on at least one probe"), same
    fresh-instance-per-probe discipline (a fresh_env() per probe per adapter, never a shared,
    accumulating environment), applied uniformly to toy and real tools alike. Does not import or
    modify mutation.score; the two functions are independent implementations of the same rule
    (score.py's stays the frozen, tested, toy-class-shaped original)."""
    cfg = cfg or CanonicalConfig()
    for args in probe_args_list:
        orig_env = base_adapter.fresh_env(scenario_id)
        orig_result = base_adapter.invoke(orig_env, tool, args)
        orig_post = base_adapter.snapshot(orig_env)

        mut_env = mutant_adapter.fresh_env(scenario_id)
        mut_result = mutant_adapter.invoke(mut_env, tool, args)
        mut_post = mutant_adapter.snapshot(mut_env)

        if not canonical_equal(orig_post, mut_post, cfg):
            return True
        orig_binding = to_result_binding(orig_result.raw, orig_result.success, orig_result.error)
        mut_binding = to_result_binding(mut_result.raw, mut_result.success, mut_result.error)
        if not canonical_equal(orig_binding, mut_binding, cfg):
            return True
    return False
