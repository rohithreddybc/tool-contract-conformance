"""Benchmark adapter interface -- ARCHITECTURE-FINAL.md sec 2 ("Adapter process model") and
sec 3. Every benchmark adapter implements `Adapter`. This is Gate 1a/1b's contract: tau2-bench
is the first (and, in this milestone, only) implementation -- see adapters/tau2.py.

Why a subprocess boundary shows up here at all: ARCHITECTURE-FINAL.md sec 2 calls out that
different benchmarks pin incompatible Python versions (tau2-bench requires >=3.12,<3.14; this
dev machine's ambient interpreter, used to run `python -m unittest discover tests`, is 3.11.7)
and mandates that `dynamic/harness.py` talk to each adapter as a subprocess over JSON on stdio
rather than sharing one interpreter. `dynamic/harness.py` itself is not built in this milestone
(out of scope -- see adapters/tau2.py's module docstring), but the boundary has to exist from
day one or it becomes a retrofit, so it is owned here: `Adapter` and every dataclass below are
importable, and this whole module is *usable*, under any interpreter the harness runs on,
because nothing here imports a benchmark package. adapters/tau2.py is the concrete client that
speaks the wire protocol to a tau2-specific worker process running under tau2's own interpreter.

Dataclasses here are the wire format across that boundary: every field is JSON-shaped
(str/int/float/bool/None/dict/list, or a nested dataclass of the same), so they round-trip
through `dataclasses.asdict()` / `json.dumps()` / `json.loads()` without a custom encoder.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

from core.model import SourceRef  # reuse -- do not redefine file/start_line/end_line here.

__all__ = ["ToolRef", "EnvHandle", "ToolResult", "Adapter"]


@dataclass(frozen=True)
class ToolRef:
    """One tool as enumerated by `Adapter.list_tools()`.

    `mutates_state` is the authoritative field for the mutating-tool count -- CLAUDE.md's
    counting rule, grounded in tau2's own `environment/toolkit.py:64-90`: use `mutates_state`,
    NOT the `ToolType` tag, because a WRITE-tagged tool can signal an action without touching
    the database (and, symmetrically, a non-WRITE tool could in principle be marked
    mutates_state=True, though no in-scope tau2 domain does this as of commit c3398666 -- see
    adapters/tau2.py's module docstring for the audit). `tool_type` is carried alongside for
    reporting only; never filter on it.
    """

    name: str
    domain: str
    source: SourceRef
    docstring: str
    signature: str
    mutates_state: bool
    tool_type: str


@dataclass(frozen=True)
class EnvHandle:
    """Opaque handle to one live environment instance produced by `Adapter.fresh_env()`.

    `env_id` is meaningful only to the adapter that produced it (for a subprocess-backed
    adapter, it keys a dict of live objects held in the worker process) -- callers must treat it
    as an opaque token and never construct one by hand.
    """

    env_id: str
    domain: str
    scenario_id: str


@dataclass(frozen=True)
class ToolResult:
    """A tool invocation's raw return plus the parsed success signal.

    `raw` is the tool's return value, canonicalized to a JSON-shaped structure (a pydantic
    model return is `.model_dump(mode="json")`-ed by the adapter before this dataclass is
    built; see adapters/tau2.py `_to_jsonable`).

    `success` is `error is None` -- i.e. "the call did not raise". It is deliberately NOT a
    claim that the contract's own `success_signal` predicate holds; that predicate is a
    function of (pre, post, args, result) and is evaluated separately by the checker
    (adapters/contract_check.py), against the *contract's* stated semantics, not the adapter's
    generic notion of "didn't except".
    """

    raw: Any
    success: bool
    error: Optional[str] = None


class Adapter(ABC):
    """Benchmark adapter interface. See ARCHITECTURE-FINAL.md sec 2-3 and
    spec/PREDICATE-GRAMMAR.md sec 1 for what `snapshot()` must produce: JSON-shaped state (no
    live objects, no methods), stable under core/canonical.py's canonicalization rules.
    """

    @abstractmethod
    def list_tools(self) -> list[ToolRef]:
        """Enumerate every tool across every in-scope domain, tagged with `mutates_state`."""
        raise NotImplementedError

    @abstractmethod
    def fresh_env(self, scenario_id: str) -> EnvHandle:
        """Construct a new environment instance deterministically. Calling this twice with the
        same `scenario_id` must produce byte-identical initial snapshots."""
        raise NotImplementedError

    @abstractmethod
    def snapshot(self, env: EnvHandle) -> dict:
        """Canonical JSON of the environment's full mutable state."""
        raise NotImplementedError

    @abstractmethod
    def invoke(self, env: EnvHandle, tool: str, args: dict) -> ToolResult:
        """Call `tool` with `args` against the live environment behind `env`, mutating it."""
        raise NotImplementedError

    @abstractmethod
    def reset(self, env: EnvHandle) -> None:
        """Reset `env` via the benchmark's own reset path, in place."""
        raise NotImplementedError

    @abstractmethod
    def source(self, tool: str) -> SourceRef:
        """Static source location of `tool`, for finding attribution. `tool` may be a bare
        name if it is unique across in-scope domains, or "domain:tool_name" to disambiguate
        (several tau2 tool names, e.g. "transfer_to_human_agents", recur across domains)."""
        raise NotImplementedError

    # -- mutation-experiment-only extensions -------------------------------------------------
    # Added for experiments/run_mutation_*.py (detector_analysis_plan.md): swap ONE tool's live
    # implementation for a mutant's, so the frozen checker (adapters/contract_check.py, core/)
    # can be run against it completely unmodified via dynamic.harness.run_contract. Neither
    # method is abstract -- these are new, additive capabilities the four concrete adapters below
    # implement; nothing in the checker itself calls them.

    def patch_tool(self, env: EnvHandle, tool: str, mutant_source: str) -> None:
        """Install `mutant_source` -- a standalone, decorator-free `def <tool>(...): ...`
        snippet, typically produced by one of mutation/operators.py's six functions or one of
        mutation/equivalence.py's single-function refactor generators, unparsed and stripped of
        its decorator_list -- as the live implementation of `tool`.

        Scope varies by adapter and is documented on each override: some scope the patch to just
        `env` (discarded once that EnvHandle is discarded, so `unpatch_tool` is a no-op there);
        others must patch a process-wide shared object (a cached suite/module), in which case the
        patch persists across every EnvHandle until `unpatch_tool` undoes it. Callers that need
        adapter-agnostic behaviour should always call `unpatch_tool` when done with one mutant,
        never rely on which scoping a given adapter happens to use.
        """
        raise NotImplementedError(f"{type(self).__name__} does not support patch_tool")

    def unpatch_tool(self, tool: str) -> None:
        """Undo a prior process-wide `patch_tool` call for `tool`, restoring the original
        implementation. A no-op for an adapter whose `patch_tool` scopes to one EnvHandle only
        (see that override's docstring) -- always safe to call regardless."""
        return None
