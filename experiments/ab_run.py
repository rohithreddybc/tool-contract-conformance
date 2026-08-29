"""Agent-impact experiment, Tier 1 -- ARCHITECTURE-FINAL.md sec 6, bound by
experiments/analysis_plan.md (committed, pre-registered, read in full before this file was
written; nothing in that plan is changed here).

WHAT THIS SCRIPT IS: trajectory replay with no model in the EVIDENCE path. It (1) statically
enumerates every tau2 task whose gold solution invokes a tool with a confirmed VIOLATES clause
(sec 6 of the plan -- exhaustive, no exclusions, no selection on observed behaviour), (2)
constructs and mechanically verifies the two one-hunk patches CLAUDE.md's build instructions
name (telecom refuel_data, airline cancel_reservation), (3) sources ONE action sequence per
affected task, and (4) for every trajectory obtained, replays it against both the as-shipped and
the patched tools using tau2's OWN evaluator (tau2.evaluator.evaluator_env.EnvironmentEvaluator,
via adapters.tau2.Tau2Adapter.replay_and_score) and reports the defect-exercise rate and any
verdict flip, exactly as plan sec 2-3 defines them.

DEVIATION FROM THE PRE-REGISTERED PLAN, RECORDED HERE (also in report/ab_summary.md's generated
output every run) -- experiments/analysis_plan.md sec 4 specifies "one recording per task" via
tau2's own orchestrator (a real LLMAgent + UserSimulator call through litellm). This project runs
with no model and no API credentials anywhere (CLAUDE.md) -- a prior run of this exact script
(commit 94adf1e, see report/ab_summary.md's git history) confirmed the orchestrator path cannot
complete here: `record_trajectory` failed on every attempted task with
`OpenAIException - Missing credentials`. Rather than block indefinitely on an API key this
project will never hold, the action sequence is instead sourced from each affected task's OWN
reference solution (`task.evaluation_criteria.actions` -- tau2's own gold trajectory, the same
one `EnvironmentEvaluator.calculate_reward` itself replays to build the target/gold environment)
via `Tau2Adapter.record_reference_trajectory` (`adapters/_tau2_worker.py`'s
`_cmd_record_reference_trajectory`). This is a STRENGTHENING of the plan's own determinism claim,
not a weaker substitute: plan sec 5 says "The model selected which trajectory exists; it plays no
part in the comparison" -- here no model selects the trajectory either, so the model is removed
from the evidence path entirely, including at recording time. It is still a deviation from a
committed, pre-registered document and is reported as one, per run, in both this docstring and
`report/ab_summary.md`'s generated "Deviation from pre-registration" section -- see
`run_reference_mode` below and `RUN_REFERENCE_MODE_DEVIATION_NOTE`.

The ORIGINAL model-based path (`attempt_trajectory_recording`, calling
`Tau2Adapter.record_trajectory`) is left fully intact below and is not deleted -- CLAUDE.md's
build instructions for this run ask for it to be kept, unused, so that a future run with real
credentials (should this project's no-API-key policy ever change) has a working path to fall
back to without reconstructing it. `main()` below does not call it.

MedAgentBench is excluded (FINDINGS-VERIFIED.md Finding 4: its grader reads the transcript, not
FHIR state, so a patch would be invisible to it -- ARCHITECTURE-FINAL.md sec 6 already routes
the flagship A/B to tau2 for this reason, and CLAUDE.md's build instructions repeat it
verbatim). AgentDojo (F5, F6, F8) and MM-ToolSandbox (F7) are in the plan's exercise-predicate
table but CLAUDE.md's patch list names only the two tau2 findings, so this build's replay is
scoped to those two; the AgentDojo/MM-ToolSandbox predicates are documented in
experiments/analysis_plan.md sec 2 but no A/B harness for them exists here. Tier 2 is cut per
CLAUDE.md's explicit instruction (no descriptive plot, no hypothesis test, nothing built).

SAMPLE SIZE (plan sec 5, "no N set for F2's 1120 affected tasks... never stop on the data"). The
default here (no environment overrides) is to run EVERY affected task for every finding -- the
plan's own stated preference, since trajectory sourcing is deterministic and mechanical replay
has no model latency to budget around. Two environment variables exist purely to bound the cost
of this module's OWN unit-test smoke check (tests/test_ab_run.py sets them so
`python -m unittest discover tests` does not spend ~30 minutes inside one smoke test on every
invocation) and are NOT used for the run whose numbers are reported in the paper:
  - AB_REFERENCE_SAMPLE_N: if set, cap each finding's run at min(N, population), via a seeded
    random.Random(AB_REFERENCE_SEED).sample() over the full, file-order task-id list -- the seed
    is fixed BEFORE any task is run, never chosen after seeing outcomes.
  - AB_REFERENCE_SEED: seed for the above (default 20260828, this project's build date).
Every run -- sampled or full -- records which mode it used, the population size, the selected N,
and the seed (if any) in report["reference_mode"]["task_selection"], and prints it in
report/ab_summary.md, so a sampled smoke run can never be mistaken for the full-population run.

Run with: python -m experiments.ab_run
Writes report/ab_results.json (structured) and report/ab_summary.md (narrative).
"""
from __future__ import annotations

import json
import os
import random
import subprocess
import sys
from collections import defaultdict
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
    reward_basis_by_task: dict = {}
    for t in tasks:
        ec = t.get("evaluation_criteria") or {}
        actions = ec.get("actions") or []
        if any(a.get("name") == tool for a in actions):
            affected.append(t["id"])
            # RewardType.DB vs RewardType.ENV_ASSERTION -- the evaluator-basis tag CLAUDE.md's
            # build instructions require every scored row to carry (see classify_evaluator_basis
            # below): DB compares gold-execution end state against agent-execution end state
            # (symmetric; a defect exercised identically on both sides cancels), ENV_ASSERTION
            # runs a named assertion function against the agent-execution end state alone (no
            # gold comparison at all, so a defect that changes that state changes the verdict
            # directly). Read straight off this task's own on-disk evaluation_criteria, same
            # field analysis/score_at_risk.py's build_tau2_rows() already reads.
            reward_basis_by_task[t["id"]] = sorted(ec.get("reward_basis") or [])
    return {
        "domain": domain,
        "tool": tool,
        "n_tasks_total": len(tasks),
        "n_affected": len(affected),
        "task_ids": affected,
        "reward_basis_by_task": reward_basis_by_task,
        "selection_rule": (
            "gold reference solution (evaluation_criteria.actions) invokes this tool -- "
            "exhaustive over the full on-disk task file, no exclusions"
        ),
    }


def classify_evaluator_basis(reward_basis: list) -> str:
    """Tags a task's scoring row with what kind of oracle actually gates its reward, mirroring
    analysis/score_at_risk.py's own oracle-grounding classification (CLAUDE.md: 'Tag every row
    with its basis, exactly as analysis/score_at_risk.py does'). Only DB and ENV_ASSERTION matter
    here -- tau2.evaluator.evaluator_env.EnvironmentEvaluator.calculate_reward (the evaluator this
    script calls, unmodified, via replay_and_score) is the only reward component this experiment
    computes; COMMUNICATE/ACTION/NL_ASSERTION, if present in a task's reward_basis, are graded by
    OTHER tau2 evaluator classes this script never invokes; see adapters/_tau2_worker.py's
    _cmd_replay_and_score docstring."""
    basis = set(reward_basis)
    has_db = "DB" in basis
    has_env = "ENV_ASSERTION" in basis
    if has_db and has_env:
        return "mixed_db_and_env_assertion"
    if has_db:
        return "gold_vs_agent_db_comparison"  # airline-style: symmetric, no flip possible by construction (plan sec 1)
    if has_env:
        return "per_task_state_assertion"  # telecom-style: absolute state, no gold comparison
    return "other_basis_not_scored_by_EnvironmentEvaluator:" + ",".join(sorted(basis))


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
# 3b. Model-free trajectory recording -- the deviation this run's module docstring records. Holds
#    the action sequence fixed at each affected task's own reference solution
#    (task.evaluation_criteria.actions) instead of driving a real LLMAgent/UserSimulator, via
#    Tau2Adapter.record_reference_trajectory (adapters/_tau2_worker.py's
#    _cmd_record_reference_trajectory). Deterministic and free of model latency: "one recording
#    per task, no re-rolls" (plan sec 4) is satisfied trivially since there is only one possible
#    recording. Returns the identical wire shape attempt_trajectory_recording does (a "messages"
#    list on success), so score_trajectory below needs no branching on which path produced it.
# =================================================================================================

DEFAULT_REFERENCE_SEED = 20260828  # this project's build date -- fixed regardless of override,
# used only when AB_REFERENCE_SAMPLE_N is set without its own AB_REFERENCE_SEED.


def attempt_reference_trajectory_recording(adapter: Tau2Adapter, domain: str, task_id: str) -> dict:
    try:
        result = adapter.record_reference_trajectory(domain, task_id)
        return {"domain": domain, "task_id": task_id, "status": "recorded", "config": {"source": "reference_solution"}, **result}
    except Tau2AdapterError as e:
        return {
            "domain": domain,
            "task_id": task_id,
            "status": "failed",
            "config": {"source": "reference_solution"},
            "error": str(e),
        }


def select_tasks_to_run(task_ids: list) -> tuple:
    """Which of a finding's affected task_ids to actually record+score this run. Default (no
    environment overrides): every task -- plan sec 5's own stated preference, since sourcing a
    trajectory from a task's reference solution has no model latency to budget around.
    AB_REFERENCE_SAMPLE_N, if set, caps the run at min(N, population) via a seeded sample fixed
    BEFORE any task is run (never chosen after seeing outcomes) -- see this module's docstring
    for why this knob exists (bounding tests/test_ab_run.py's smoke check) and why it is not what
    produces this project's reported numbers. Returns (selected_task_ids, selection_metadata)."""
    n_population = len(task_ids)
    sample_n_raw = os.environ.get("AB_REFERENCE_SAMPLE_N")
    if sample_n_raw is None:
        return list(task_ids), {
            "mode": "full_population",
            "n_population": n_population,
            "n_selected": n_population,
            "seed": None,
        }
    seed = int(os.environ.get("AB_REFERENCE_SEED", DEFAULT_REFERENCE_SEED))
    n_sample = min(int(sample_n_raw), n_population)
    rng = random.Random(seed)
    selected = sorted(rng.sample(list(task_ids), n_sample))
    return selected, {
        "mode": "seeded_sample",
        "n_population": n_population,
        "n_selected": n_sample,
        "seed": seed,
    }


# =================================================================================================
# 4. Tier-1 scoring for one recorded trajectory (only reached if step 3 ever succeeds).
# =================================================================================================


def score_trajectory(
    adapter: Tau2Adapter,
    finding_id: str,
    domain: str,
    task_id: str,
    messages: list,
    *,
    reward_basis: Optional[list] = None,
) -> dict:
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
        "reward_basis": reward_basis,
        "evaluator_basis": classify_evaluator_basis(reward_basis or []),
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
# 4b. Outcome-cell table PER EVALUATOR BASIS (CLAUDE.md requirement 3: "Report per evaluator
#    basis, and expect them to behave differently") and pre/post state diffs for any flip
#    (CLAUDE.md requirement: "flip count with pre/post state diffs for any flip").
# =================================================================================================


def build_outcome_cells_by_basis(tier1_scoring: list) -> dict:
    """All four plan-sec-2/3 cells, always together, per (finding, evaluator_basis) key.
    'not_at_risk' is a fixed string, not a count: this run's population is the experiment frame
    (gold invokes the defective tool), which score_at_risk's independent field-dependency
    computation confirms is a SUBSET of the at-risk population for both F2 and F3 (see
    cross_check_against_score_at_risk / analysis/score_at_risk.py's experiment_frame_subset_of_at_risk)
    -- every task scored here is at risk by construction, so this cell is structurally empty
    rather than zero-and-uncomputed. Reported explicitly rather than omitted, per CLAUDE.md's
    "report all four cells"."""
    table: dict = defaultdict(
        lambda: {
            "not_at_risk": "n/a -- population pre-filtered to the experiment frame, a confirmed subset of at-risk",
            "at_risk_not_exercised": 0,
            "exercised_no_flip": 0,
            "flipped": 0,
        }
    )
    for row in tier1_scoring:
        key = f"{row['finding_id']}|{row['evaluator_basis']}"
        table[key][row["outcome_cell"]] += 1
    return {k: dict(v) for k, v in table.items()}


def _leaf_diff(a, b, path: str = "") -> list:
    """Every leaf position where two JSON-shaped snapshots disagree, as {"path", "before",
    "after"} dicts -- generic dict/list/scalar recursive diff, no benchmark-specific knowledge,
    used only to render a human-auditable diff for a flipped task (rare/possibly zero by design;
    see this module's docstring)."""
    if isinstance(a, dict) and isinstance(b, dict):
        out: list = []
        for k in sorted(set(a) | set(b)):
            out.extend(_leaf_diff(a.get(k), b.get(k), f"{path}.{k}" if path else str(k)))
        return out
    if a == b:
        return []
    return [{"path": path, "before": a, "after": b}]


def compute_flip_state_diff(adapter: Tau2Adapter, finding_id: str, domain: str, task_id: str, calls: list) -> dict:
    """Only called for a task whose outcome_cell is 'flipped' (CLAUDE.md: "flip count with
    pre/post state diffs for any flip"). Independently replays the SAME recorded calls, in order,
    against two fresh task-scoped environments -- one as-shipped, one patched -- and diffs their
    resulting snapshots. This is a second, direct mechanism check (raw DB snapshot comparison),
    deliberately not reusing tau2's own evaluator internals, so the reported diff is legible on
    its own rather than only through RewardInfo's pass/fail bit."""
    spec = TAU2_PATCHES[finding_id]
    patch_source = patched_function_source(spec)

    env_unpatched = adapter.fresh_task_env(domain, task_id)
    pre_unpatched = adapter.snapshot(env_unpatched)
    for call in calls:
        adapter.invoke(env_unpatched, call.name, call.arguments, requestor=call.requestor)
    post_unpatched = adapter.snapshot(env_unpatched)

    env_patched = adapter.fresh_task_env(domain, task_id)
    adapter.patch_tool(env_patched, spec.tool, patch_source)
    pre_patched = adapter.snapshot(env_patched)
    for call in calls:
        adapter.invoke(env_patched, call.name, call.arguments, requestor=call.requestor)
    post_patched = adapter.snapshot(env_patched)

    return {
        "finding_id": finding_id,
        "domain": domain,
        "task_id": task_id,
        "pre_state_diff_shipped_vs_patched": _leaf_diff(pre_unpatched, pre_patched),
        "post_state_diff_shipped_vs_patched": _leaf_diff(post_unpatched, post_patched),
    }


# =================================================================================================
# 3c. Model-free Tier-1 run -- replaces the (never-completable, no-credentials) LLM trajectory
#    loop for every affected task of every finding. See this module's docstring for the deviation
#    this records relative to experiments/analysis_plan.md sec 4.
# =================================================================================================

RUN_REFERENCE_MODE_DEVIATION_NOTE = (
    "experiments/analysis_plan.md sec 4 specifies ONE recorded trajectory per task, sourced from "
    "tau2's own orchestrator (a real LLMAgent + UserSimulator call through litellm). This project "
    "runs with no model and no API credentials anywhere (CLAUDE.md); a prior run of this script "
    "(commit 94adf1e) confirmed that path cannot complete here -- record_trajectory failed on "
    "every attempted task with 'OpenAIException - Missing credentials'. DEVIATION: this run "
    "instead sources the action sequence from each affected task's OWN reference solution "
    "(task.evaluation_criteria.actions -- tau2's own gold trajectory, the same one "
    "EnvironmentEvaluator.calculate_reward itself replays to build the target/gold environment), "
    "executes it once against a fresh, unpatched, task-scoped environment via "
    "Tau2Adapter.record_reference_trajectory, and replays the identical recorded calls against "
    "as-shipped and patched tools with tau2's own EnvironmentEvaluator, unmodified. This is a "
    "STRENGTHENING of the plan's own determinism claim, not a weaker substitute: plan sec 5 says "
    "'The model selected which trajectory exists; it plays no part in the comparison' -- here no "
    "model selects the trajectory either, so the model is removed from the evidence path "
    "entirely, including at recording time. It remains a deviation from a committed, "
    "pre-registered document and is recorded as such here, not silently substituted."
)


def run_reference_mode(adapter: Tau2Adapter, report: dict) -> None:
    report["deviation_from_preregistration"] = {
        "document": "experiments/analysis_plan.md sec 4",
        "note": RUN_REFERENCE_MODE_DEVIATION_NOTE,
    }
    report["reference_mode"] = {"task_selection": {}, "discards": []}

    any_recorded = False
    for finding_id in FINDINGS:
        spec = TAU2_PATCHES[finding_id]
        sel = report["static_task_selection"][finding_id]
        task_ids_all = sel["task_ids"]
        selected_ids, sel_meta = select_tasks_to_run(task_ids_all)
        report["reference_mode"]["task_selection"][finding_id] = sel_meta

        for task_id in selected_ids:
            attempt = attempt_reference_trajectory_recording(adapter, spec.domain, task_id)
            report["trajectory_recording"]["attempted"].append(attempt)
            if attempt["status"] != "recorded":
                report["reference_mode"]["discards"].append(
                    {
                        "finding_id": finding_id,
                        "domain": spec.domain,
                        "task_id": task_id,
                        "cause": attempt.get("error"),
                    }
                )
                continue
            any_recorded = True
            reward_basis = sel["reward_basis_by_task"].get(task_id, [])
            scored = score_trajectory(
                adapter, finding_id, spec.domain, task_id, attempt["messages"], reward_basis=reward_basis
            )
            report["tier1_scoring"].append(scored)

    report["outcome_cells_by_basis"] = build_outcome_cells_by_basis(report["tier1_scoring"])

    report["flip_details"] = []
    for row in report["tier1_scoring"]:
        if row["outcome_cell"] == "flipped":
            spec = TAU2_PATCHES[row["finding_id"]]
            calls = extract_calls_with_results(
                next(
                    a["messages"]
                    for a in report["trajectory_recording"]["attempted"]
                    if a.get("task_id") == row["task_id"] and a.get("domain") == row["domain"] and a["status"] == "recorded"
                )
            )
            report["flip_details"].append(
                compute_flip_state_diff(adapter, row["finding_id"], row["domain"], row["task_id"], calls)
            )

    if not any_recorded:
        # Every attempt for every finding was an infrastructure discard (should not happen for a
        # deterministic, offline, no-model recording path, but not fabricated as a false success
        # if it somehow does).
        first_discard = next(iter(report["reference_mode"]["discards"]), None)
        report["stopped_at"] = "trajectory_recording"
        report["stopped_reason"] = (
            (first_discard or {}).get("cause")
            or "no affected tasks were selected for recording (unexpected -- check static_task_selection)"
        )


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
        "outcome_cells_by_basis": {},
        "reference_mode": {},
        "deviation_from_preregistration": {},
        "flip_details": [],
        "tau2_adapter_available": None,
        "stopped_at": None,
        "stopped_reason": None,
        "plan_items_not_implementable_as_written": [],
    }

    # ---- 1. Static task selection -- needs no adapter, no tau2 venv. -------------------------
    # Sample-size note (plan sec 5): a population > 20 no longer gets flagged as unresolved here
    # -- run_reference_mode()/select_tasks_to_run() below now states, per finding, whether this
    # run used the full population or a seeded sample (and the seed/N if so). See
    # report["reference_mode"]["task_selection"] and this module's docstring.
    for finding_id in FINDINGS:
        spec = TAU2_PATCHES[finding_id]
        sel = select_affected_tasks(spec.domain, spec.tool)
        sel["finding_id"] = finding_id
        sel["finding_citation"] = spec.finding_citation
        report["static_task_selection"][finding_id] = sel
        report["score_at_risk_cross_check"][finding_id] = cross_check_against_score_at_risk(
            finding_id, spec, sel["n_affected"]
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

        # ---- 3. Model-free trajectory recording + Tier-1 scoring, for every affected task of
        # every finding (or a seeded sample -- see select_tasks_to_run / this module's
        # docstring). Deviation from experiments/analysis_plan.md sec 4 recorded in
        # report["deviation_from_preregistration"] and RUN_REFERENCE_MODE_DEVIATION_NOTE above.
        # attempt_trajectory_recording (the real-model path) is left defined above, unused. -----
        run_reference_mode(adapter, report)

        # ---- 4. Outcome-cell table (overall, across evaluator bases -- see
        # report["outcome_cells_by_basis"] for the per-basis breakdown CLAUDE.md requires). ------
        if report["tier1_scoring"]:
            cells = {
                "not_at_risk": "n/a -- population is pre-filtered to the experiment frame (gold invokes the defective tool); see analysis/score_at_risk.py for the separate at-risk population",
                "at_risk_not_exercised": 0,
                "exercised_no_flip": 0,
                "flipped": 0,
            }
            for row in report["tier1_scoring"]:
                cells[row["outcome_cell"]] = cells.get(row["outcome_cell"], 0) + 1
            report["outcome_cells"] = cells
            report["stopped_at"] = None
            report["stopped_reason"] = None
        else:
            report["outcome_cells"] = {
                "not_at_risk": "not computable -- 0 trajectories recorded",
                "at_risk_not_exercised": "not computable -- 0 trajectories recorded",
                "exercised_no_flip": "not computable -- 0 trajectories recorded",
                "flipped": "not computable -- 0 trajectories recorded",
            }
            # run_reference_mode already set stopped_at/stopped_reason for this case.
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

    dev = r.get("deviation_from_preregistration") or {}
    if dev:
        lines.append("## 3. Deviation from pre-registration\n")
        lines.append(f"Document: `{dev.get('document')}`\n")
        lines.append(f"{dev.get('note')}\n")

    lines.append("## 4. Trajectory recording (model-free -- reference-solution action sequences)\n")
    ref_mode = r.get("reference_mode") or {}
    task_sel = ref_mode.get("task_selection") or {}
    lines.append("| Finding | Mode | Population | Selected (N) | Seed |")
    lines.append("|---|---|---:|---:|---|")
    for fid in ("F2", "F3"):
        sm = task_sel.get(fid)
        if not sm:
            continue
        lines.append(
            f"| {fid} | {sm['mode']} | {sm['n_population']} | {sm['n_selected']} | {sm.get('seed') if sm.get('seed') is not None else '-'} |"
        )
    lines.append("")

    n_recorded = sum(1 for a in r["trajectory_recording"]["attempted"] if a["status"] == "recorded")
    n_discarded = len(ref_mode.get("discards") or [])
    lines.append(f"- trajectories recorded: **{n_recorded}**")
    lines.append(f"- discarded for infrastructure failure: **{n_discarded}** (logged individually below; a discard is never a silent exclusion -- the task remains in static_task_selection)")
    if ref_mode.get("discards"):
        by_cause: dict = {}
        for d in ref_mode["discards"]:
            by_cause.setdefault(d.get("cause"), []).append(d)
        for cause, ds in by_cause.items():
            lines.append(f"  - `{cause}`: {len(ds)} task(s), e.g. `{ds[0]['domain']}:{ds[0]['task_id']}`")
    lines.append("")

    lines.append("## 5. Outcome-cell table (overall, across evaluator bases)\n")
    lines.append("| Cell | Count |")
    lines.append("|---|---|")
    for cell, count in r["outcome_cells"].items():
        lines.append(f"| {cell} | {count} |")
    lines.append("")

    lines.append("## 6. Outcome-cell table PER EVALUATOR BASIS\n")
    lines.append(
        "`gold_vs_agent_db_comparison` (airline: DB reward compares gold-execution end state "
        "against agent-execution end state; both sides here run the SAME tool implementation, so "
        "no flip is possible by construction -- a null here is evidence about the oracle's "
        "structure, not evidence the defect is harmless). `per_task_state_assertion` (telecom: "
        "ENV_ASSERTION reward runs a named assertion against the agent-execution end state alone, "
        "no gold comparison -- a flip here IS possible.)\n"
    )
    if r.get("outcome_cells_by_basis"):
        lines.append("| Finding\\|Basis | not_at_risk | at_risk_not_exercised | exercised_no_flip | flipped |")
        lines.append("|---|---|---:|---:|---:|")
        for key, cells in sorted(r["outcome_cells_by_basis"].items()):
            lines.append(
                f"| {key} | {cells.get('not_at_risk')} | {cells.get('at_risk_not_exercised', 0)} | "
                f"{cells.get('exercised_no_flip', 0)} | {cells.get('flipped', 0)} |"
            )
        lines.append("")
    else:
        lines.append("(no rows scored)\n")

    lines.append("## 7. Defect-exercise rate\n")
    lines.append("| Finding | Trajectories scored | Exercised | Exercise rate |")
    lines.append("|---|---:|---:|---:|")
    by_finding: dict = {}
    for row in r["tier1_scoring"]:
        by_finding.setdefault(row["finding_id"], []).append(row)
    for fid in ("F2", "F3"):
        rows = by_finding.get(fid, [])
        if not rows:
            continue
        n = len(rows)
        n_ex = sum(1 for row in rows if row["exercised"])
        rate = f"{n_ex / n:.1%}" if n else "n/a"
        lines.append(f"| {fid} | {n} | {n_ex} | {rate} |")
    lines.append("")

    lines.append("## 8. Flips\n")
    n_flipped = sum(1 for row in r["tier1_scoring"] if row["outcome_cell"] == "flipped")
    if n_flipped == 0 and r["tier1_scoring"]:
        lines.append(
            f"Across {len(r['tier1_scoring'])} recorded trajectories on "
            f"{len({(row['finding_id'], row['task_id']) for row in r['tier1_scoring']})} affected tasks, "
            "no verdict changed under the patched tools; the defects documented in FINDINGS-VERIFIED.md "
            "are latent under the reference-solution action sequences these benchmarks' own gold "
            "trajectories take, and the exercise rates in sec 7 show why "
            "(experiments/analysis_plan.md sec 3's committed null-result framing).\n"
        )
    elif n_flipped == 0:
        lines.append("No trajectories were scored, so no flip count exists.\n")
    else:
        lines.append(f"**{n_flipped} verdict(s) flipped.**\n")
        for row in r["tier1_scoring"]:
            if row["outcome_cell"] != "flipped":
                continue
            lines.append(f"### {row['finding_id']} -- `{row['domain']}:{row['task_id']}`\n")
            lines.append(f"- direction: **{row['flip_direction']}** (unpatched reward {row['reward_unpatched']} -> patched reward {row['reward_patched']})")
            lines.append(f"- evaluator basis: `{row['evaluator_basis']}`")
        for fd in r.get("flip_details") or []:
            lines.append(f"\n**State diff, `{fd['finding_id']}:{fd['domain']}:{fd['task_id']}` (as-shipped vs patched)**\n")
            lines.append("- pre-state diff (should be empty -- same task, same init state, patch not yet exercised):")
            lines.append(f"  `{fd['pre_state_diff_shipped_vs_patched']}`")
            lines.append("- post-state diff (after replaying the recorded calls):")
            lines.append(f"  `{fd['post_state_diff_shipped_vs_patched']}`")
        lines.append("")

    if r["stopped_at"]:
        lines.append(f"## Stopped at: `{r['stopped_at']}`\n")
        lines.append(f"{r['stopped_reason']}\n")

    if r["plan_items_not_implementable_as_written"]:
        lines.append("## Plan items not implementable as written\n")
        for item in r["plan_items_not_implementable_as_written"]:
            lines.append(f"- **{item['item']}**: {item['issue']}\n")

    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
