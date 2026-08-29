#!/usr/bin/env python
"""R7 (Major Revision item) -- decompose every missed closed-world real-tool mutant.

Reads report/mutation_closed_world_raw.jsonl (produced by experiments/run_mutation_closed_world.py,
scored under checker-freeze-v2) and, for every real-tool defect mutant that
experiments/build_mutation_report.classify_defect_mutant labels "missed" (the checker evaluated at
least one clause and reported CONFORMS, never VIOLATES), attempts the detector_analysis_plan.md
sec 4.3 three-way decomposition (clause_gap / probe_gap / canonicalization_gap) using the SAME
mechanism already built for the open-world arm:

  1. Build the mutant exactly as the generation script did (mutation.adapter_invoke.
     build_function_patch_source, same operator + site_params recorded in the raw jsonl row).
  2. Screen the mutant for behavioural liveness (sec 4.1) against the FROZEN sec-2 equivalence
     probe corpus (mutation.probes.build_equivalence_probe_corpus) -- deliberately NOT the
     checker's own probe generation (dynamic/probes.py, reached only through
     dynamic.harness.run_contract), because sec 4.3 requires the two probe sources to stay
     disjoint or "probe gaps would be invisible by construction." This is the same corpus
     already frozen and used for the open-world arm (report/mutation_open_world_provenance.md).
  3. If NO probe in that corpus exposes a behavioural difference, the miss is bucketed
     "probe_corpus_unreachable" -- this is NOT the sec-4.3 "probe_gap" cause (which presumes a
     confirmed behavioural difference the checker's own clause logic failed to flag); it is the
     same corpus-reachability failure already diagnosed for the tau2 open-world arm
     (mutation_open_world_provenance.md's "v2 rerun" section: recorded-real-calls has no
     artifact, and the type-generic boundary/precondition placeholders fail tau2's entity-keyed
     existence checks before reaching any write). We cannot tell, from this corpus alone, whether
     the mutant is genuinely inert or merely unreached.
  4. If a probe DOES expose a difference, the FIRST such probe's (pre, post_mut, args, result_mut,
     error_mut) is fed to mutation.score.classify_escape verbatim -- the exact function already
     used to decompose open-world escapes -- with unmasked_cfg=CanonicalConfig() (no masking) and
     masked_cfg = the SAME CanonicalConfig() the real-tool closed-world run actually used (see
     CFG_BY_BENCHMARK below, copied from experiments/run_mutation_closed_world.py). Because no
     real benchmark declares ANY volatile path (only toy's TOY_CANONICAL_CONFIG does), masked_cfg
     and unmasked_cfg are structurally IDENTICAL for every real-tool row scored here, so
     canonicalization_gap is mechanically unreachable in this slice -- reported, not silently
     produced as a zero that could be mistaken for an empirical finding.

M-INVAR is a special case, kept separate from the other three operators' full decomposition: every
M-INVAR clause is an `invariants:` clause, and mutation.score.classify_escape only ever inspects
`contract.effects` and `contract.preconditions` (never `contract.invariants`) and only ever calls
adapters.contract_check.check_effects / check_precondition_enforcement (never
dynamic.harness.check_invariants, which needs a SECOND tool call from a sibling contract -- a
two-call companion-sequence shape classify_escape's single-witness signature cannot express at
all). Applying classify_escape to an M-INVAR miss as-is would mechanically report clause_gap for
100% of them, regardless of whether an invariant clause actually covers the changed behaviour --
that would not be a decomposition, it would be a mislabelled constant. So M-INVAR misses are only
run through the liveness screen (step 2-3 above); if a probe exposes a difference, the miss is
reported "invariant_clause_not_evaluated_by_classifier" rather than mis-routed into clause_gap.
Fixing this for real would mean teaching classify_escape (or a genuinely new function) to run
check_invariants with a companion sequence, which is out of scope here per CLAUDE.md's "reuse
[the existing machinery], not writing a second classifier" -- reported as a known limitation,
not worked around.

HARD CONSTRAINT: this script imports and calls core/, dynamic/, adapters/contract_check.py, and
spec/validate.py, but modifies none of them (checker-freeze-v2, 5824376). mutation/ and
experiments/ are outside the freeze and untouched here too -- this is a NEW, read-only-of-those
script. Does not modify report/mutation_scores.json or report/mutation_summary.md, or repos/.

Output: report/miss_decomposition.json (machine-readable, one row per attempted mutant) and
report/miss_decomposition.md (narrative summary), per the task's instruction to write NEW files.
"""
from __future__ import annotations

import json
import sys
import traceback
from collections import Counter
from pathlib import Path
from typing import Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from adapters.agentdojo import AgentDojoAdapter, AgentDojoAdapterError  # noqa: E402
from adapters.contract_check import to_result_binding  # noqa: E402
from adapters.mmtoolsandbox import MMToolSandboxAdapter, MMToolSandboxAdapterError  # noqa: E402
from adapters.tau2 import Tau2Adapter, Tau2AdapterError  # noqa: E402
from core.canonical import CanonicalConfig, canonical_equal  # noqa: E402
from experiments.build_mutation_report import DEFECT_OPERATORS, classify_defect_mutant  # noqa: E402
from mutation.adapter_invoke import MutatedAdapter, build_function_patch_source  # noqa: E402
from mutation.probes import build_equivalence_probe_corpus  # noqa: E402
from mutation.real_targets import enumerate_eligible_targets  # noqa: E402
from mutation.score import EscapeCause, classify_escape  # noqa: E402

RAW_PATH = PROJECT_ROOT / "report" / "mutation_closed_world_raw.jsonl"
OUT_JSON = PROJECT_ROOT / "report" / "miss_decomposition.json"
OUT_MD = PROJECT_ROOT / "report" / "miss_decomposition.md"

# Copied verbatim from experiments/run_mutation_closed_world.py's CFG_BY_BENCHMARK (real-tools
# rows only -- toy is out of scope for this decomposition, R7 is about the real-tools recall
# numbers §VII actually reports).
CFG_BY_BENCHMARK = {
    "tau2-bench": CanonicalConfig(),
    "agentdojo": CanonicalConfig(),
    "mm-toolsandbox": CanonicalConfig(),
}

FULLY_DECOMPOSABLE_OPERATORS = ("M-PRECOND", "M-IGNARG", "M-PARTIAL")
LIVENESS_ONLY_OPERATORS = ("M-INVAR",)


def load_jsonl(path: Path) -> list:
    with open(path, "r", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def build_adapter(benchmark: str):
    if benchmark == "tau2-bench":
        return Tau2Adapter()
    if benchmark == "agentdojo":
        return AgentDojoAdapter()
    if benchmark == "mm-toolsandbox":
        return MMToolSandboxAdapter()
    raise ValueError(f"unknown benchmark {benchmark!r}")


def find_liveness_witness(base_adapter, mutant_adapter, scenario_id: str, tool: str, probes: list, cfg: CanonicalConfig) -> "tuple[Optional[dict], int, int]":
    """Mirrors mutation.adapter_invoke.is_behaviorally_live_adapter's exact sec-4.1 comparison
    (fresh env per probe, per adapter; compare canonicalized post-state OR canonicalized result),
    but -- unlike that function, which only returns a bool -- also captures the PRE-call snapshot
    on the mutant side, args, post-call snapshot, and error, which classify_escape needs as its
    witness. Returns (witness_or_None, n_probes_attempted, n_probes_with_invoke_error)."""
    n_attempted = 0
    n_invoke_errors = 0
    for probe in probes:
        n_attempted += 1
        args = probe.args
        try:
            orig_env = base_adapter.fresh_env(scenario_id)
            orig_result = base_adapter.invoke(orig_env, tool, args)
            orig_post = base_adapter.snapshot(orig_env)

            mut_env = mutant_adapter.fresh_env(scenario_id)
            mut_pre = mutant_adapter.snapshot(mut_env)
            mut_result = mutant_adapter.invoke(mut_env, tool, args)
            mut_post = mutant_adapter.snapshot(mut_env)
        except Exception:  # noqa: BLE001 -- a wedged/desynced adapter on ONE probe must not abort
            # the whole mutant's screen; the caller rebuilds fresh adapters per mutant regardless.
            n_invoke_errors += 1
            continue

        orig_binding = to_result_binding(orig_result.raw, orig_result.success, orig_result.error)
        mut_binding = to_result_binding(mut_result.raw, mut_result.success, mut_result.error)

        live = (not canonical_equal(orig_post, mut_post, cfg)) or (not canonical_equal(orig_binding, mut_binding, cfg))
        if live:
            return (
                {
                    "probe_origin": probe.origin,
                    "args": args,
                    "pre": mut_pre,
                    "post_mut": mut_post,
                    "result_mut": mut_binding,
                    "error_mut": (mut_result.error if not mut_result.success else None),
                },
                n_attempted,
                n_invoke_errors,
            )
    return None, n_attempted, n_invoke_errors


def score_one_miss(target, operator: str, site_params: dict, benchmark: str, tool: str) -> dict:
    source = target.source_path.read_text(encoding="utf-8")
    try:
        patch_source = build_function_patch_source(source, tool, operator, dict(site_params))
    except Exception as e:  # noqa: BLE001
        return {"cause": "patch_build_error", "detail": f"{type(e).__name__}: {e}"}

    cfg = CFG_BY_BENCHMARK[benchmark]
    base_adapter = None
    mutant_base = None
    mutant_adapter = None
    try:
        base_adapter = build_adapter(benchmark)
        mutant_base = build_adapter(benchmark)
        mutant_adapter = MutatedAdapter(mutant_base, tool, patch_source)

        seed_env = base_adapter.fresh_env(target.scenario_id)
        pre0 = base_adapter.snapshot(seed_env)
        probes = build_equivalence_probe_corpus(target.contract, recorded_calls=[], pre=pre0)
        probe_args_list = [p.args for p in probes]

        witness, n_attempted, n_invoke_errors = find_liveness_witness(
            base_adapter, mutant_adapter, target.scenario_id, tool, probes, cfg
        )

        base_row = {
            "n_probes_in_corpus": len(probes),
            "n_probes_attempted": n_attempted,
            "n_probe_invoke_errors": n_invoke_errors,
            "probe_origins_in_corpus": [p.origin for p in probes],
        }

        if witness is None:
            return {**base_row, "cause": "probe_corpus_unreachable"}

        if operator in LIVENESS_ONLY_OPERATORS:
            return {
                **base_row,
                "cause": "invariant_clause_not_evaluated_by_classifier",
                "witness_probe_origin": witness["probe_origin"],
                "witness_args": witness["args"],
            }

        cause = classify_escape(
            target.contract,
            witness["pre"],
            witness["post_mut"],
            witness["args"],
            witness["result_mut"],
            error_mut=witness["error_mut"],
            unmasked_cfg=CanonicalConfig(),
            masked_cfg=cfg,
        )
        return {
            **base_row,
            "cause": cause,
            "witness_probe_origin": witness["probe_origin"],
            "witness_args": witness["args"],
        }
    except Exception as e:  # noqa: BLE001 -- a scoring crash is itself a reportable outcome
        return {"cause": "scoring_error", "detail": f"{type(e).__name__}: {e}\n{traceback.format_exc(limit=6)}"}
    finally:
        for obj in (mutant_adapter,):
            if obj is not None:
                try:
                    obj.close()
                except Exception:
                    pass
        for obj in (mutant_base, base_adapter):
            if obj is not None and hasattr(obj, "close"):
                try:
                    obj.close()
                except Exception:
                    pass


def main() -> int:
    rows = load_jsonl(RAW_PATH)
    defects = [r for r in rows if r.get("kind") == "defect_mutant" and not r.get("is_toy")]
    missed = [r for r in defects if classify_defect_mutant(r) == "missed"]
    in_scope = [r for r in missed if r["operator"] in FULLY_DECOMPOSABLE_OPERATORS + LIVENESS_ONLY_OPERATORS]

    print(f"{len(defects)} real-tool defect_mutant rows, {len(missed)} classified 'missed', "
          f"{len(in_scope)} in scope for this decomposition "
          f"(operators: {FULLY_DECOMPOSABLE_OPERATORS + LIVENESS_ONLY_OPERATORS})")

    needed_benchmarks = {r["benchmark"] for r in in_scope}
    domain_by_tool: dict = {}
    probe_adapters = {}  # short-lived adapters used ONLY to build domain_by_tool, closed immediately after
    try:
        if "agentdojo" in needed_benchmarks:
            ad = AgentDojoAdapter()
            domain_by_tool["agentdojo"] = {t.name: t.domain for t in ad.list_tools()}
            probe_adapters["agentdojo"] = ad
        if "mm-toolsandbox" in needed_benchmarks:
            mm = MMToolSandboxAdapter()
            domain_by_tool["mm-toolsandbox"] = {t.name: t.domain for t in mm.list_tools()}
            probe_adapters["mm-toolsandbox"] = mm
    finally:
        for a in probe_adapters.values():
            try:
                a.close()
            except Exception:
                pass

    all_targets = enumerate_eligible_targets(domain_by_tool)
    target_by_bt = {(t.benchmark, t.tool): t for t in all_targets}

    results = []
    for i, row in enumerate(in_scope):
        b, tool, op = row["benchmark"], row["tool"], row["operator"]
        params = row.get("site_params") or {}
        print(f"[{i + 1}/{len(in_scope)}] {op} {b}/{tool} {params} ...", flush=True)
        target = target_by_bt.get((b, tool))
        if target is None:
            outcome = {"cause": "target_not_found"}
        else:
            outcome = score_one_miss(target, op, params, b, tool)
        results.append({
            "operator": op, "benchmark": b, "tool": tool, "site_params": params,
            "site_detail": row.get("site_detail"), **outcome,
        })
        print(f"    -> {outcome.get('cause')}", flush=True)

    # -- also carry forward the rows we deliberately did NOT attempt, for a complete accounting --
    excluded = [
        {
            "operator": r["operator"], "benchmark": r["benchmark"], "tool": r["tool"],
            "site_params": r.get("site_params"), "cause": "operator_out_of_scope_for_this_script",
        }
        for r in missed
        if r["operator"] not in FULLY_DECOMPOSABLE_OPERATORS + LIVENESS_ONLY_OPERATORS
    ]

    cause_counts_by_operator: dict = {}
    for r in results:
        cause_counts_by_operator.setdefault(r["operator"], Counter())[r["cause"]] += 1

    out = {
        "generated_by": "experiments/decompose_closed_world_misses.py",
        "source_raw": str(RAW_PATH.relative_to(PROJECT_ROOT)),
        "n_real_defect_rows": len(defects),
        "n_missed_real": len(missed),
        "operators_fully_decomposed": list(FULLY_DECOMPOSABLE_OPERATORS),
        "operators_liveness_only": list(LIVENESS_ONLY_OPERATORS),
        "operators_excluded": sorted({r["operator"] for r in excluded}),
        "results": results,
        "excluded_rows": excluded,
        "cause_counts_by_operator": {op: dict(c) for op, c in cause_counts_by_operator.items()},
        "cause_counts_overall": dict(Counter(r["cause"] for r in results)),
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, default=str)
    print(f"wrote {OUT_JSON}")

    write_markdown(out)
    print(f"wrote {OUT_MD}")
    return 0


def write_markdown(out: dict) -> None:
    lines = []
    lines.append("# Closed-world miss decomposition (R7)")
    lines.append("")
    lines.append(f"Generated by `experiments/decompose_closed_world_misses.py` from "
                 f"`{out['source_raw']}`. Real-tool `defect_mutant` rows: {out['n_real_defect_rows']}; "
                 f"classified `missed` by `experiments.build_mutation_report.classify_defect_mutant`: "
                 f"{out['n_missed_real']}.")
    lines.append("")
    lines.append("## Overall cause counts (in-scope operators only)")
    lines.append("")
    lines.append("| Cause | Count |")
    lines.append("|---|---:|")
    for cause, n in sorted(out["cause_counts_overall"].items(), key=lambda kv: -kv[1]):
        lines.append(f"| {cause} | {n} |")
    lines.append("")
    lines.append("## By operator")
    lines.append("")
    for op in out["operators_fully_decomposed"] + out["operators_liveness_only"]:
        counts = out["cause_counts_by_operator"].get(op, {})
        if not counts:
            continue
        lines.append(f"### {op}")
        lines.append("")
        lines.append("| Cause | Count |")
        lines.append("|---|---:|")
        for cause, n in sorted(counts.items(), key=lambda kv: -kv[1]):
            lines.append(f"| {cause} | {n} |")
        lines.append("")
    if out["excluded_rows"]:
        lines.append(f"## Excluded from this decomposition: {len(out['excluded_rows'])} row(s)")
        lines.append("")
        lines.append("Operators: " + ", ".join(out["operators_excluded"]) +
                      " -- not attempted by this script at all (see module docstring for M-RESET/"
                      "M-PHANTOM/other exclusions, if any appear here).")
        lines.append("")
    with open(OUT_MD, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
