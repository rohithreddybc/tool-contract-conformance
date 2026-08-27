"""Shared scoring logic for the tau2-bench telecom open-world (cosmic-ray) run. Runs under
.venv-tau2's interpreter with PYTHONPATH already pointing this process's `tau2` import at
<this dir>/src (a COPY of repos/tau2/src -- see build_open_world.md / the final report for why a
copy, never repos/tau2 itself, is what cosmic-ray is pointed at) and TAU2_DATA_DIR pointing at
the real, untouched, read-only .tau2-src-c3398666/data directory (never written to).

Mirrors cr_toy/scoring_lib.py's shape exactly (fresh-module-per-call discipline, same
behavioral-liveness definition, same checker-reuse idiom) -- see that file's docstrings for the
rationale; not repeated here.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

PROJECT_ROOT = Path(r"C:\Users\rohit\Documents\Research Papers\ResearchPaper20-ToolContractConformance")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from adapters.base import Adapter, EnvHandle, SourceRef, ToolResult  # noqa: E402
from adapters.contract_check import to_result_binding  # noqa: E402
from core.canonical import CanonicalConfig, canonical_equal  # noqa: E402
from core.model import Contract  # noqa: E402
from dynamic.harness import run_contract  # noqa: E402
from mutation.probes import build_equivalence_probe_corpus  # noqa: E402

CFG = CanonicalConfig()
CONTRACTS_DIR = PROJECT_ROOT / "spec" / "contracts" / "tau2"

# telecom tools this run covers: every contracted, non-anchor telecom tool. refuel_data is the
# confirmed-finding anchor (FINDINGS-VERIFIED.md Finding 2) and is excluded, matching sec 3's
# rule applied consistently to the open-world arm too (see the final report for this being a
# judgment call the plan does not make explicit for the open-world side).
TELECOM_TOOLS = ("disable_roaming", "enable_roaming", "resume_line", "send_payment_request", "suspend_line")


def _fresh_telecom_env():
    """A brand-new TelecomEnvironment, built from whatever tau2 copy this PROCESS imported (see
    module docstring). No reload/fresh-module trickery is needed here the way cr_toy/scoring_lib.py
    needs it for `bank.py`: cosmic-ray spawns a brand-new subprocess per test-command invocation
    (cosmic_ray.testing.run_tests), and that subprocess only ever imports
    tau2.domains.telecom.environment/tools ONCE, at whatever content is on disk at that moment --
    there is no stale-bytecode or stale-sys.modules hazard within a single, single-import
    process. `importlib.reload()` was tried here first and removed: it re-executes a module's
    top level in place without re-executing modules IT imports from (tools.py would not actually
    be re-read), and repeated reloads within one process can leave two different class objects
    for the same name coexisting -- worse than doing nothing, and unnecessary given the
    fresh-process guarantee."""
    from tau2.domains.telecom.environment import get_environment_manual_policy

    return get_environment_manual_policy()


class InlineTau2Adapter(Adapter):
    """In-process Adapter around whatever tau2 copy is currently importable (see module
    docstring) -- the checker-reuse counterpart of cr_toy's InlineToyAdapter. Only the methods
    dynamic.harness.run_contract calls are implemented."""

    def __init__(self):
        self._envs: dict = {}

    def list_tools(self):
        raise NotImplementedError

    def fresh_env(self, scenario_id: str) -> EnvHandle:
        import uuid

        env_id = uuid.uuid4().hex
        self._envs[env_id] = _fresh_telecom_env()
        return EnvHandle(env_id=env_id, domain="telecom", scenario_id=scenario_id)

    def snapshot(self, env: EnvHandle) -> dict:
        e = self._envs[env.env_id]
        snap = e.tools.db.model_dump(mode="json")
        user_tools = getattr(e, "user_tools", None)
        if user_tools is not None:
            snap["user_db"] = user_tools.db.model_dump(mode="json")
        return snap

    def invoke(self, env: EnvHandle, tool: str, args: dict) -> ToolResult:
        e = self._envs[env.env_id]
        try:
            raw = e.make_tool_call(tool, requestor="assistant", **args)
            e.sync_tools()
            return ToolResult(raw=_to_jsonable(raw), success=True, error=None)
        except Exception as ex:  # noqa: BLE001
            return ToolResult(raw=None, success=False, error=f"{type(ex).__name__}: {ex}")

    def reset(self, env: EnvHandle) -> None:
        self._envs[env.env_id] = _fresh_telecom_env()

    def source(self, tool: str) -> SourceRef:
        raise NotImplementedError


def _to_jsonable(value):
    from pydantic import BaseModel

    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {k: _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def build_probe_corpus_for_tool(tool: str) -> list:
    contract = Contract.from_yaml(CONTRACTS_DIR / f"{tool}.yaml")
    adapter = InlineTau2Adapter()
    env = adapter.fresh_env("telecom")
    pre = adapter.snapshot(env)
    corpus = build_equivalence_probe_corpus(contract, recorded_calls=[], pre=pre)
    return [{"args": p.args, "origin": p.origin} for p in corpus]


def run_probes_against_current_tau2(tool: str, probes: list) -> list:
    adapter = InlineTau2Adapter()
    out = []
    for p in probes:
        env = adapter.fresh_env("telecom")
        result = adapter.invoke(env, tool, p["args"])
        post = adapter.snapshot(env)
        binding = to_result_binding(result.raw, result.success, result.error)
        out.append({"post": post, "result": binding, "error": result.error})
    return out


def is_behaviorally_live(original_records: list, mutant_records: list, cfg: CanonicalConfig = CFG) -> bool:
    for orig, mut in zip(original_records, mutant_records):
        if not canonical_equal(orig["post"], mut["post"], cfg):
            return True
        if not canonical_equal(orig["result"], mut["result"], cfg):
            return True
    return False


def first_differing_probe(original_records: list, mutant_records: list, probes: list, cfg: CanonicalConfig = CFG):
    """Sec 4.3 witness -- see cr_toy/scoring_lib.py's identical function for the rationale."""
    for i, (orig, mut) in enumerate(zip(original_records, mutant_records)):
        if not canonical_equal(orig["post"], mut["post"], cfg) or not canonical_equal(orig["result"], mut["result"], cfg):
            return {
                "probe_index": i, "args": probes[i]["args"], "post_mut": mut["post"],
                "result_mut": mut["result"], "error_mut": mut.get("error"),
            }
    return None


def classify_escape_for_tool(tool: str, witness: dict, pre_state) -> str:
    from mutation.score import classify_escape

    contract = Contract.from_yaml(CONTRACTS_DIR / f"{tool}.yaml")
    return classify_escape(
        contract, pre_state, witness["post_mut"], witness["args"], witness["result_mut"],
        error_mut=witness.get("error_mut"), masked_cfg=CFG, unmasked_cfg=CanonicalConfig(),
    )


def checker_detects(tool: str) -> dict:
    contract = Contract.from_yaml(CONTRACTS_DIR / f"{tool}.yaml")
    adapter = InlineTau2Adapter()
    try:
        rows = run_contract(adapter, contract, "telecom", cfg=CFG, seed=20260902)
        detected = any(r["verdict"] == "VIOLATES" for r in rows)
        return {"detected": detected, "error": None}
    except Exception as e:  # noqa: BLE001
        return {"detected": None, "error": f"{type(e).__name__}: {e}"}
