"""Shared scoring logic for the toy-domain open-world (cosmic-ray) run. Imported by both
precompute.py (run once, ambient/unmutated bank.py) and test_command.py (run once per cosmic-ray
mutation, against whatever bank.py currently contains on disk).

PROJECT_ROOT is added to sys.path so this can import the real project's core/, adapters/,
mutation/, dynamic/ machinery unmodified -- it never imports toy.bank (the real project copy);
it always imports the "bank" module that's already on sys.path from THIS directory (either the
pristine copy, at precompute time, or cosmic-ray's currently-mutated copy, at test-command time).
"""
from __future__ import annotations

import copy
import importlib.util
import itertools
import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(r"C:\Users\rohit\Documents\Research Papers\ResearchPaper20-ToolContractConformance")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from adapters.base import Adapter, EnvHandle, SourceRef, ToolRef, ToolResult  # noqa: E402
from adapters.contract_check import to_result_binding  # noqa: E402
from core.canonical import CanonicalConfig, canonical_equal  # noqa: E402
from core.model import Contract  # noqa: E402
from dynamic.harness import run_contract  # noqa: E402
from mutation.probes import build_equivalence_probe_corpus  # noqa: E402

CFG = CanonicalConfig(volatile_paths=("state.audit_log.[].seq",))
CONTRACTS_DIR = PROJECT_ROOT / "spec" / "contracts" / "toy"
BANK_PATH = Path(__file__).resolve().parent / "bank.py"

_counter = itertools.count()


def load_bank_module():
    """Load bank.py fresh off disk EVERY call, bypassing both `sys.modules` caching and the
    on-disk `__pycache__` bytecode cache entirely (a unique module name each call defeats the
    former; `importlib.util.spec_from_file_location` + `exec_module`, never a plain `import
    bank` statement, defeats the latter). This is not paranoia: an earlier manual run of this
    exact script hit a real stale-`.pyc` bug -- `import bank` silently kept serving a
    cached-compiled PRE-mutation version because two successive writes to bank.py landed within
    the same mtime tick, which is precisely the hazard cosmic_ray.testing.run_tests' own
    `PYTHONDONTWRITEBYTECODE=1` exists to avoid for ITS subprocess; loading by explicit path
    removes the dependency on that env var (or on mtime resolution) being enough on its own."""
    name = f"_cr_toy_bank_{next(_counter)}_{time.time_ns()}"
    spec = importlib.util.spec_from_file_location(name, BANK_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_toy_tool_names() -> list:
    return list(load_bank_module().MUTATING_TOOLS)


class InlineToyAdapter(Adapter):
    """Same shape as toy/adapter.py's ToyAdapter, but built around a `bank` module imported from
    wherever the CALLER's sys.path currently points (the cosmic-ray-mutated copy, for the
    test-command's use) rather than the real project's toy/bank.py. Only the methods
    dynamic.harness.run_contract actually calls are needed."""

    def __init__(self, bank_module):
        self._bank_module = bank_module
        self._envs: dict = {}

    def list_tools(self):
        raise NotImplementedError  # not needed by run_contract

    def fresh_env(self, scenario_id: str) -> EnvHandle:
        import uuid

        env_id = uuid.uuid4().hex
        self._envs[env_id] = self._bank_module.ToyBank()
        return EnvHandle(env_id=env_id, domain="toy", scenario_id=scenario_id)

    def snapshot(self, env: EnvHandle) -> dict:
        return copy.deepcopy(self._envs[env.env_id].state)

    def invoke(self, env: EnvHandle, tool: str, args: dict) -> ToolResult:
        bank = self._envs[env.env_id]
        fn = getattr(bank, tool)
        try:
            raw = fn(**args)
        except self._bank_module.ToyError as e:
            return ToolResult(raw=None, success=False, error=str(e))
        return ToolResult(raw=raw, success=True, error=None)

    def reset(self, env: EnvHandle) -> None:
        self._envs[env.env_id].reset()

    def source(self, tool: str) -> SourceRef:
        raise NotImplementedError  # not needed by run_contract


def build_probe_corpus_for_tool(tool: str) -> list:
    """The sec 2 equivalence probe corpus for `tool`, built from the REAL project's contract
    (spec/contracts/toy/<tool>.yaml -- frozen at checker-freeze-v1, never regenerated per-run)
    and a pristine PRE snapshot from a fresh, freshly-imported `bank` module instance. Item 1
    (recorded real calls) is empty -- see experiments/run_mutation_closed_world.py's module
    docstring / the final report for why."""
    bank_module = load_bank_module()

    contract = Contract.from_yaml(CONTRACTS_DIR / f"{tool}.yaml")
    pre = bank_module.ToyBank().state
    corpus = build_equivalence_probe_corpus(contract, recorded_calls=[], pre=pre)
    return [{"args": p.args, "origin": p.origin} for p in corpus]


def run_probes_against_current_bank(tool: str, probes: list, bank_module=None) -> list:
    """[(post_state, result_binding), ...] canonicalization-ready pairs, one per probe in
    `probes`, invoking `tool` against a FRESH ToyBank() from whatever `bank.py` currently
    contains on disk (see `load_bank_module`'s docstring). Callers that already loaded the
    module once for this invocation (test_command.py, scoring several tools per call) should
    pass it in rather than re-parsing bank.py from scratch for every tool."""
    bank_module = bank_module or load_bank_module()

    out = []
    for p in probes:
        instance = bank_module.ToyBank()
        try:
            raw = getattr(instance, tool)(**p["args"])
            success, error = True, None
        except bank_module.ToyError as e:
            raw, success, error = None, False, str(e)
        except Exception as e:  # noqa: BLE001 -- a mutant can raise something the original
            # never would (NameError/TypeError from a bad AST-adjacent edit); that is itself a
            # real behavioural difference, not something to let crash the whole test-command.
            raw, success, error = None, False, f"{type(e).__name__}: {e}"
        post = instance.state
        result = to_result_binding(raw, success, error)
        out.append({"post": post, "result": result, "error": error})
    return out


def is_behaviorally_live(original_records: list, mutant_records: list, cfg: CanonicalConfig = CFG) -> bool:
    for orig, mut in zip(original_records, mutant_records):
        if not canonical_equal(orig["post"], mut["post"], cfg):
            return True
        if not canonical_equal(orig["result"], mut["result"], cfg):
            return True
    return False


def first_differing_probe(original_records: list, mutant_records: list, probes: list, cfg: CanonicalConfig = CFG):
    """Sec 4.3's classify_escape needs one concrete witness (args, pre, post_mut, result_mut,
    error_mut), not just the sec 4.1 boolean -- this returns the FIRST probe (by corpus order)
    at which the mutant's canonicalized post-state or result differs from the original, or None
    if none does. `pre` is the tool's fixed initial state (deterministic, same for every probe:
    every probe here runs against a FRESH ToyBank()), read once from `original_records[0]`'s
    caller rather than re-derived -- callers pass it in separately (see PRE_STATE below)."""
    for i, (orig, mut) in enumerate(zip(original_records, mutant_records)):
        if not canonical_equal(orig["post"], mut["post"], cfg) or not canonical_equal(orig["result"], mut["result"], cfg):
            return {
                "probe_index": i, "args": probes[i]["args"], "post_mut": mut["post"],
                "result_mut": mut["result"], "error_mut": mut.get("error"),
            }
    return None


def classify_escape_for_tool(tool: str, witness: dict, pre_state) -> str:
    """Sec 4.3's three-way decomposition, via mutation.score.classify_escape (frozen, imported
    unmodified) -- called ONLY for a confirmed escape (a live mutant the checker did not flag),
    using the FIRST differing probe `first_differing_probe` found as the witness call."""
    from mutation.score import classify_escape

    contract = Contract.from_yaml(CONTRACTS_DIR / f"{tool}.yaml")
    return classify_escape(
        contract, pre_state, witness["post_mut"], witness["args"], witness["result_mut"],
        error_mut=witness.get("error_mut"), masked_cfg=CFG, unmasked_cfg=CanonicalConfig(),
    )


def checker_detects(tool: str, bank_module=None) -> dict:
    """Run the FROZEN checker (dynamic.harness.run_contract, unmodified) against whatever
    bank.py currently contains on disk, wrapped in InlineToyAdapter. Returns {"detected": bool,
    "error": str|None}."""
    bank_module = bank_module or load_bank_module()

    contract = Contract.from_yaml(CONTRACTS_DIR / f"{tool}.yaml")
    adapter = InlineToyAdapter(bank_module)
    try:
        rows = run_contract(adapter, contract, "default", cfg=CFG, seed=20260902)
        detected = any(r["verdict"] == "VIOLATES" for r in rows)
        return {"detected": detected, "error": None}
    except Exception as e:  # noqa: BLE001
        return {"detected": None, "error": f"{type(e).__name__}: {e}"}
