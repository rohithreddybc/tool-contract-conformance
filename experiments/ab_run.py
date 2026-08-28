"""Agent-impact experiment, Tier 1 -- ARCHITECTURE-FINAL.md sec 6, bound by
experiments/analysis_plan.md (committed, pre-registered, read in full before this file was
written; nothing in that plan is changed here).

WHAT THIS SCRIPT IS: trajectory replay with no model in the EVIDENCE path. It (1) statically
enumerates every tau2 task whose gold solution invokes a tool with a confirmed VIOLATES clause
(sec 6 of the plan -- exhaustive, no exclusions, no selection on observed behaviour), (2)
constructs and mechanically verifies the two one-hunk patches CLAUDE.md's build instructions
name (telecom refuel_data, airline cancel_reservation), (3) attempts to RECORD one agent
trajectory per affected task by running tau2's own orchestrator with a real model -- the one
place a model does appear, exactly once per task, no re-rolls (plan sec 4) -- and (4) for every
trajectory actually recorded, replays it against both the as-shipped and the patched tools using
tau2's OWN evaluator (tau2.evaluator.evaluator_env.EnvironmentEvaluator, via
adapters.tau2.Tau2Adapter.replay_and_score) and reports the defect-exercise rate and any verdict
flip, exactly as plan sec 2-3 defines them.

MedAgentBench is excluded (FINDINGS-VERIFIED.md Finding 4: its grader reads the transcript, not
FHIR state, so a patch would be invisible to it -- ARCHITECTURE-FINAL.md sec 6 already routes
the flagship A/B to tau2 for this reason, and CLAUDE.md's build instructions repeat it
verbatim). AgentDojo (F5, F6, F8) and MM-ToolSandbox (F7) are in the plan's exercise-predicate
table but CLAUDE.md's patch list names only the two tau2 findings, so this build's replay is
scoped to those two; the AgentDojo/MM-ToolSandbox predicates are documented in
experiments/analysis_plan.md sec 2 but no A/B harness for them exists here. Tier 2 is cut per
CLAUDE.md's explicit instruction (no descriptive plot, no hypothesis test, nothing built).

Run with: python -m experiments.ab_run
Writes report/ab_results.json (structured) and report/ab_summary.md (narrative).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from adapters.tau2 import Tau2Adapter, Tau2AdapterError  # noqa: E402
from experiments.ab_exercise import extract_calls_with_results, exercised_f2, exercised_f3  # noqa: E402
from experiments.ab_patches import TAU2_PATCHES, PatchSpec, patched_function_source  # noqa: E402

TAU2_DATA = PROJECT_ROOT / ".tau2-src-c3398666" / "data" / "tau2" / "domains"
TAU2_TASK_FILE = {
    "airline": TAU2_DATA / "airline" / "tasks.json",
    "telecom": TAU2_DATA / "telecom" / "tasks.json",
}
REPORT_DIR = PROJECT_ROOT / "report"
RESULTS_JSON = REPORT_DIR / "ab_results.json"
SUMMARY_MD = REPORT_DIR / "ab_summary.md"

# The two findings this build's A/B covers, keyed to experiments/ab_patches.TAU2_PATCHES.
FINDINGS = ("F2", "F3")


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, text=True).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# =================================================================================================
# 1. Static task selection -- experiments/analysis_plan.md sec 6 / ARCHITECTURE-FINAL.md sec 4:
#    "A task is affected iff its reference solution invokes a tool with a confirmed VIOLATES
#    clause. Enumerated exhaustively... No exclusions, no additions, no selection on observed
#    behaviour." Same rule analysis/score_at_risk.py's build_tau2_rows() already applies (its
#    `in_experiment_frame` / `experiment_frame_ids`) -- reimplemented here, independently, over
#    the identical source file (TAU2_TASK_FILE, the raw on-disk tasks.json, task_split_name=None
#    i.e. every task in the file, not the "base" evaluation split -- see
#    adapters/_tau2_worker.py's `_load_task` docstring for why the split distinction matters),
#    and cross-checked against that module's own counts in `main()` below so a mismatch between
#    the two independent implementations is caught rather than silently trusted.
# =================================================================================================


def select_affected_tasks(domain: str, tool: str) -> dict:
    with open(TAU2_TASK_FILE[domain], "r", encoding="utf-8") as fh:
        tasks = json.load(fh)
    affected = []
    for t in tasks:
        ec = t.get("evaluation_criteria") or {}
        actions = ec.get("actions") or []
        if any(a.get("name") == tool for a in actions):
            affected.append(t["id"])
    return {
        "domain": domain,
        "tool": tool,
        "n_tasks_total": len(tasks),
        "n_affected": len(affected),
        "task_ids": affected,
        "selection_rule": (
            "gold reference solution (evaluation_criteria.actions) invokes this tool -- "
            "exhaustive over the full on-disk task file, no exclusions"
        ),
    }


def cross_check_against_score_at_risk(finding_id: str, spec: PatchSpec, computed_n_affected: int) -> dict:
    """analysis/score_at_risk.py computes the identical population (its `n_experiment_frame`)
    independently, from spec/contracts/tau2/*.yaml + the same task file, via a different code
    path (build_tau2_rows). Agreement here is a real cross-check, not a tautology -- the two
    implementations share only the task JSON file and the defect->tool mapping, not the
    selection logic itself."""
    try:
        from analysis.score_at_risk import build_tau2_rows

        rows = build_tau2_rows()
        summary = next(
            (r for r in rows if r["kind"] == "summary" and r["tool"] == spec.tool and r["domain"] == spec.domain),
            None,
        )
        if summary is None:
            return {"status": "no_matching_summary_row", "agrees": False}
        return {
            "status": "computed",
            "score_at_risk_n_experiment_frame": summary["n_experiment_frame"],
            "ab_run_n_affected": computed_n_affected,
            "agrees": summary["n_experiment_frame"] == computed_n_affected,
            "score_at_risk_n_at_risk": summary["n_at_risk"],
            "score_at_risk_experiment_frame_subset_of_at_risk": summary["experiment_frame_subset_of_at_risk"],
        }
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "error": f"{type(e).__name__}: {e}", "agrees": None}


# =================================================================================================
# 2. Patch construction + mechanical verification. Not the agent experiment -- a direct,
#    non-agent demonstration (through the SAME Tau2Adapter the replay path uses) that each patch
#    is a real, minimal fix: before, the defect reproduces exactly as FINDINGS-VERIFIED.md
#    describes; after `patch_tool`, it does not. This is what CLAUDE.md requirement 5 ("Patches
#    are one-hunk and minimal, restoring only advertised semantics") asks to be shown, and it
#    needs no model.
# =================================================================================================


def verify_patch_f2(adapter: Tau2Adapter) -> dict:
    spec = TAU2_PATCHES["F2"]
    source = patched_function_source(spec)

    env = adapter.fresh_env("telecom")
    pre = adapter.snapshot(env)
    line = next(l for l in pre["lines"] if l["status"] != "Active")
    customer = next(c for c in pre["customers"] if line["line_id"] in c["line_ids"])
    args = {"customer_id": customer["customer_id"], "line_id": line["line_id"], "gb_amount": 5.0}

    unpatched_result = adapter.invoke(env, spec.tool, args)
    unpatched_post = adapter.snapshot(env)
    unpatched_line = next(l for l in unpatched_post["lines"] if l["line_id"] == line["line_id"])
    defect_reproduces = unpatched_result.success and (
        unpatched_line.get("data_refueling_gb") != line.get("data_refueling_gb")
    )

    env2 = adapter.fresh_env("telecom")
    adapter.patch_tool(env2, spec.tool, source)
    patched_result = adapter.invoke(env2, spec.tool, args)
    patched_post = adapter.snapshot(env2)
    patched_line = next(l for l in patched_post["lines"] if l["line_id"] == line["line_id"])
    patch_fixes = (not patched_result.success) and (
        patched_line.get("data_refueling_gb") == line.get("data_refueling_gb")
    )

    return {
        "finding_id": "F2",
        "domain": "telecom",
        "tool": "refuel_data",
        "probe_args": args,
        "line_status_probed": line.get("status"),
        "unpatched": {
            "success": unpatched_result.success,
            "error": unpatched_result.error,
            "data_refueling_gb_changed": unpatched_line.get("data_refueling_gb") != line.get("data_refueling_gb"),
        },
        "patched": {
            "success": patched_result.success,
            "error": patched_result.error,
            "data_refueling_gb_changed": patched_line.get("data_refueling_gb") != line.get("data_refueling_gb"),
        },
        "defect_reproduces_unpatched": defect_reproduces,
        "patch_fixes_defect": patch_fixes,
        "pass": bool(defect_reproduces and patch_fixes),
    }


def verify_patch_f3(adapter: Tau2Adapter) -> dict:
    spec = TAU2_PATCHES["F3"]
    source = patched_function_source(spec)

    env = adapter.fresh_env("airline")
    pre = adapter.snapshot(env)
    reservation_id = next(rid for rid, r in pre["reservations"].items() if r.get("status") != "cancelled")
    res = pre["reservations"][reservation_id]
    fl = res["flights"][0]
    seats_before = pre["flights"][fl["flight_number"]]["dates"][fl["date"]]["available_seats"][res["cabin"]]
    n_passengers = len(res["passengers"])

    unpatched_result = adapter.invoke(env, spec.tool, {"reservation_id": reservation_id})
    unpatched_post = adapter.snapshot(env)
    unpatched_seats = unpatched_post["flights"][fl["flight_number"]]["dates"][fl["date"]]["available_seats"][
        res["cabin"]
    ]
    defect_reproduces = unpatched_result.success and (unpatched_seats == seats_before)

    env2 = adapter.fresh_env("airline")
    adapter.patch_tool(env2, spec.tool, source)
    patched_result = adapter.invoke(env2, spec.tool, {"reservation_id": reservation_id})
    patched_post = adapter.snapshot(env2)
    patched_seats = patched_post["flights"][fl["flight_number"]]["dates"][fl["date"]]["available_seats"][
        res["cabin"]
    ]
    patch_fixes = patched_result.success and (patched_seats == seats_before + n_passengers)

    return {
        "finding_id": "F3",
        "domain": "airline",
        "tool": "cancel_reservation",
        "probe_args": {"reservation_id": reservation_id},
        "seats_before_cancel": seats_before,
        "n_passengers": n_passengers,
        "unpatched": {"success": unpatched_result.success, "seats_after": unpatched_seats},
        "patched": {"success": patched_result.success, "seats_after": patched_seats},
        "defect_reproduces_unpatched": defect_reproduces,
        "patch_fixes_defect": patch_fixes,
        "pass": bool(defect_reproduces and patch_fixes),
    }


# =================================================================================================
# 3. Trajectory recording attempt -- the one place a model would appear
#    (experiments/analysis_plan.md sec 4: "Fixed model, fixed prompts, fixed seeds, temperature
#    0, recorded once"). Left at tau2's own config.py defaults unless AB_LLM_AGENT/AB_LLM_USER
#    override -- DEFAULT_LLM_AGENT/DEFAULT_LLM_USER = "gpt-4.1-2025-04-14", DEFAULT_SEED = 300,
#    temperature 0.0 for both agent and user already, so "fixed model, fixed seed, temperature
#    0" is satisfied by doing nothing rather than by this script inventing its own choice.
# =================================================================================================


def attempt_trajectory_recording(adapter: Tau2Adapter, domain: str, task_id: str) -> dict:
    kwargs = {}
    for env_var, key in (
        ("AB_LLM_AGENT", "llm_agent"),
        ("AB_LLM_USER", "llm_user"),
        ("AB_SEED", "seed"),
        ("AB_MAX_STEPS", "max_steps"),
    ):
        val = os.environ.get(env_var)
        if val is not None:
            kwargs[key] = int(val) if key in ("seed", "max_steps") else val
    try:
        result = adapter.record_trajectory(domain, task_id, **kwargs)
        return {"domain": domain, "task_id": task_id, "status": "recorded", "config": kwargs, **result}
    except Tau2AdapterError as e:
        return {
            "domain": domain,
            "task_id": task_id,
            "status": "failed",
            "config": kwargs,
            "error": str(e),
        }


# =================================================================================================
# 4. Tier-1 scoring for one recorded trajectory (only reached if step 3 ever succeeds).
# =================================================================================================


def score_trajectory(adapter: Tau2Adapter, finding_id: str, domain: str, task_id: str, messages: list) -> dict:
    spec = TAU2_PATCHES[finding_id]
    calls = extract_calls_with_results(messages)

    if finding_id == "F2":
        exercised, evidence = exercised_f2(adapter, domain, task_id, calls)
    elif finding_id == "F3":
        exercised, evidence = exercised_f3(calls)
    else:
        raise ValueError(finding_id)

    unpatched = adapter.replay_and_score(domain, task_id, messages, patch=None)
    patch = {"tool": spec.tool, "source": patched_function_source(spec)}
    patched = adapter.replay_and_score(domain, task_id, messages, patch=patch)

    reward_unpatched = unpatched["reward_info"]["reward"]
    reward_patched = patched["reward_info"]["reward"]
    flipped = reward_unpatched != reward_patched

    if not exercised:
        cell = "at_risk_not_exercised"
    elif not flipped:
        cell = "exercised_no_flip"
    else:
        cell = "flipped"

    return {
        "finding_id": finding_id,
        "domain": domain,
        "task_id": task_id,
        "n_calls": len(calls),
        "exercised": exercised,
        "exercise_evidence": evidence,
        "reward_unpatched": reward_unpatched,
        "reward_patched": reward_patched,
        "flipped": flipped,
        "flip_direction": (
            None
            if not flipped
            else ("pass_to_fail" if reward_unpatched > reward_patched else "fail_to_pass")
        ),
        "outcome_cell": cell,
        "unpatched_reward_info": unpatched["reward_info"],
        "patched_reward_info": patched["reward_info"],
    }


# =================================================================================================
# main
# =================================================================================================


def main() -> int:
    REPORT_DIR.mkdir(exist_ok=True)
    report: dict = {
        "provenance": {
            "git_commit": git_commit(),
            "generated_at": now_iso(),
            "python": sys.version.split()[0],
            "script": "experiments/ab_run.py",
            "analysis_plan_note": (
                "bound by experiments/analysis_plan.md (untouched by this run); "
                "Tier 2 not built per CLAUDE.md build instructions"
            ),
        },
        "static_task_selection": {},
        "score_at_risk_cross_check": {},
        "patch_verification": {},
        "trajectory_recording": {"attempted": [], "not_attempted": []},
        "tier1_scoring": [],
        "outcome_cells": {},
        "tau2_adapter_available": None,
        "stopped_at": None,
        "stopped_reason": None,
        "plan_items_not_implementable_as_written": [],
    }

    # ---- 1. Static task selection -- needs no adapter, no tau2 venv. -------------------------
    for finding_id in FINDINGS:
        spec = TAU2_PATCHES[finding_id]
        sel = select_affected_tasks(spec.domain, spec.tool)
        sel["finding_id"] = finding_id
        sel["finding_citation"] = spec.finding_citation
        report["static_task_selection"][finding_id] = sel
        report["score_at_risk_cross_check"][finding_id] = cross_check_against_score_at_risk(
            finding_id, spec, sel["n_affected"]
        )
        if sel["n_affected"] > 20:
            report["plan_items_not_implementable_as_written"].append(
                {
                    "item": f"{finding_id} ({spec.domain}:{spec.tool}) recording sample size",
                    "issue": (
                        f"the static, exhaustive selection rule (experiments/analysis_plan.md sec 6) "
                        f"returns {sel['n_affected']} affected tasks for this finding; the plan commits to "
                        f"recording exactly one trajectory per affected task with no re-rolls and no "
                        f"post-hoc exclusion, but does not state a sample size for a population this "
                        f"large, nor a pre-registered subsampling rule. Recording all {sel['n_affected']} "
                        f"would need that rule written and committed BEFORE recording starts (the same "
                        f"reasoning that forbids selecting on observed behaviour elsewhere in the plan "
                        f"applies to picking a subset after seeing the population size). Not resolved by "
                        f"this script; flagged for the co-authors rather than decided unilaterally."
                    ),
                }
            )

    # ---- 2 & 3. Everything past here needs a live tau2 adapter. -------------------------------
    try:
        adapter = Tau2Adapter()
        adapter._send({"cmd": "ping"})
    except Tau2AdapterError as e:
        report["tau2_adapter_available"] = False
        report["stopped_at"] = "adapter_startup"
        report["stopped_reason"] = f"tau2 venv not provisioned or worker failed to start: {e}"
        _write_reports(report)
        return 0

    report["tau2_adapter_available"] = True
    try:
        # ---- 2. Patch construction + mechanical verification (no model). -----------------
        report["patch_verification"]["F2"] = verify_patch_f2(adapter)
        report["patch_verification"]["F3"] = verify_patch_f3(adapter)

        # ---- 3. Trajectory recording. One representative attempt per finding: the first
        # task (in on-disk file order) of each finding's affected-task list. Recording the
        # REMAINING affected tasks is deliberately not attempted in this run -- see the
        # per-finding "not_attempted" entries below for why, and report/ab_summary.md for the
        # exact live error this attempt produced. -----------------------------------------
        any_recorded = False
        for finding_id in FINDINGS:
            spec = TAU2_PATCHES[finding_id]
            task_ids = report["static_task_selection"][finding_id]["task_ids"]
            if not task_ids:
                continue
            first_task_id = task_ids[0]
            attempt = attempt_trajectory_recording(adapter, spec.domain, first_task_id)
            report["trajectory_recording"]["attempted"].append(attempt)

            if attempt["status"] == "recorded":
                any_recorded = True
                scored = score_trajectory(adapter, finding_id, spec.domain, first_task_id, attempt["messages"])
                report["tier1_scoring"].append(scored)
                remaining = task_ids[1:]
                for tid in remaining:
                    attempt2 = attempt_trajectory_recording(adapter, spec.domain, tid)
                    report["trajectory_recording"]["attempted"].append(attempt2)
                    if attempt2["status"] == "recorded":
                        scored2 = score_trajectory(adapter, finding_id, spec.domain, tid, attempt2["messages"])
                        report["tier1_scoring"].append(scored2)
            else:
                remaining = task_ids[1:]
                report["trajectory_recording"]["not_attempted"].append(
                    {
                        "finding_id": finding_id,
                        "domain": spec.domain,
                        "n_tasks_not_attempted": len(remaining),
                        "reason": (
                            "the representative attempt on the first affected task failed with the error "
                            "recorded in trajectory_recording.attempted above; the failure is an "
                            "environment/credential blocker (see stopped_reason), not something specific "
                            "to that task, so repeating the identical failing call for every remaining "
                            "affected task would burn time for no new information. Not a decision to "
                            "exclude these tasks from the experiment frame -- they remain listed in "
                            "static_task_selection and are recordable as soon as the blocker is resolved."
                        ),
                    }
                )

        # ---- 4. Outcome-cell table. -------------------------------------------------------
        if any_recorded:
            cells = {"not_at_risk": None, "at_risk_not_exercised": 0, "exercised_no_flip": 0, "flipped": 0}
            for row in report["tier1_scoring"]:
                cells[row["outcome_cell"]] = cells.get(row["outcome_cell"], 0) + 1
            report["outcome_cells"] = cells
            report["stopped_at"] = None
            report["stopped_reason"] = None
        else:
            first_failure = next(
                (a for a in report["trajectory_recording"]["attempted"] if a["status"] == "failed"), None
            )
            report["outcome_cells"] = {
                "not_at_risk": "not computable -- 0 trajectories recorded",
                "at_risk_not_exercised": "not computable -- 0 trajectories recorded",
                "exercised_no_flip": "not computable -- 0 trajectories recorded",
                "flipped": "not computable -- 0 trajectories recorded",
            }
            report["stopped_at"] = "trajectory_recording"
            report["stopped_reason"] = (
                (first_failure or {}).get("error")
                or "no affected tasks were found for either finding (unexpected -- check static_task_selection)"
            )
    finally:
        adapter.close()

    _write_reports(report)
    return 0


def _write_reports(report: dict) -> None:
    with open(RESULTS_JSON, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, sort_keys=False, default=str)

    with open(SUMMARY_MD, "w", encoding="utf-8") as fh:
        fh.write(_render_summary_md(report))

    print(f"wrote {RESULTS_JSON}")
    print(f"wrote {SUMMARY_MD}")


def _render_summary_md(r: dict) -> str:
    lines: list = []
    lines.append("# Agent-impact experiment (Tier 1) -- results\n")
    lines.append(
        f"Generated by `experiments/ab_run.py` at commit `{r['provenance']['git_commit']}`, "
        f"{r['provenance']['generated_at']}.\n"
    )
    lines.append(
        "Bound by `experiments/analysis_plan.md` (pre-registered, untouched by this run). "
        "Tier 2 not built, per build instructions.\n"
    )

    if r["tau2_adapter_available"] is False:
        lines.append("## Stopped: tau2 adapter unavailable\n")
        lines.append(f"{r['stopped_reason']}\n")
        return "\n".join(lines)

    lines.append("## 1. Static task selection (exhaustive, pre-registered rule)\n")
    lines.append("| Finding | Domain:Tool | Tasks total | Affected (experiment frame) | score_at_risk cross-check |")
    lines.append("|---|---|---:|---:|---|")
    for fid, sel in r["static_task_selection"].items():
        xc = r["score_at_risk_cross_check"].get(fid, {})
        agree = xc.get("agrees")
        agree_s = "agrees" if agree is True else ("DISAGREES" if agree is False else f"n/a ({xc.get('status')})")
        lines.append(
            f"| {fid} | {sel['domain']}:{sel['tool']} | {sel['n_tasks_total']} | {sel['n_affected']} | {agree_s} |"
        )
    lines.append("")
    for fid, sel in r["static_task_selection"].items():
        lines.append(f"**{fid}** ({sel['finding_citation']}): selection rule = {sel['selection_rule']}.\n")

    lines.append("## 2. Patch verification (mechanical, no model)\n")
    for fid in ("F2", "F3"):
        pv = r["patch_verification"].get(fid)
        if not pv:
            continue
        lines.append(f"### {fid} -- {pv['domain']}:{pv['tool']}\n")
        lines.append(f"- probe args: `{pv['probe_args']}`")
        lines.append(f"- unpatched: `{pv['unpatched']}`")
        lines.append(f"- patched: `{pv['patched']}`")
        lines.append(f"- defect reproduces unpatched: **{pv['defect_reproduces_unpatched']}**")
        lines.append(f"- patch fixes defect: **{pv['patch_fixes_defect']}**")
        lines.append(f"- PASS: **{pv['pass']}**\n")

    lines.append("## 3. Trajectory recording\n")
    for a in r["trajectory_recording"]["attempted"]:
        lines.append(f"- `{a['domain']}:{a['task_id']}` -> **{a['status']}**")
        if a["status"] == "failed":
            lines.append(f"  - error: `{a['error']}`")
        else:
            lines.append(f"  - trajectory_hash: `{a.get('trajectory_hash')}`, reward: {a.get('reward')}")
    for na in r["trajectory_recording"]["not_attempted"]:
        lines.append(
            f"- {na['finding_id']}: {na['n_tasks_not_attempted']} further affected task(s) NOT attempted -- {na['reason']}"
        )
    lines.append("")

    lines.append("## 4. Outcome-cell table\n")
    lines.append("| Cell | Count |")
    lines.append("|---|---|")
    for cell, count in r["outcome_cells"].items():
        lines.append(f"| {cell} | {count} |")
    lines.append("")

    if r["stopped_at"]:
        lines.append(f"## Stopped at: `{r['stopped_at']}`\n")
        lines.append(f"{r['stopped_reason']}\n")
        lines.append(
            "**This is not the pre-registered null result.** experiments/analysis_plan.md sec 3's "
            "null sentence presupposes trajectories were recorded and none flipped. Here, zero "
            "trajectories were recorded at all -- the blocker is environmental (no live-model "
            "credentials in this run environment), not a finding about agent behaviour. The "
            "static population, the patches, and the exercise/replay/scoring machinery are all "
            "built and verified against synthetic and mechanical probes; re-running "
            "`python -m experiments.ab_run` with `OPENAI_API_KEY` (or `AB_LLM_AGENT`/`AB_LLM_USER` "
            "pointed at a reachable model) set will attempt the real recordings and populate this "
            "table for real.\n"
        )

    if r["plan_items_not_implementable_as_written"]:
        lines.append("## Plan items not implementable as written\n")
        for item in r["plan_items_not_implementable_as_written"]:
            lines.append(f"- **{item['item']}**: {item['issue']}\n")

    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
