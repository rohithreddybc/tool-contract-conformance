#!/usr/bin/env python
"""Closed-world mutation arm -- experiments/detector_analysis_plan.md sec 3, ARCHITECTURE-FINAL.md
sec 5 ("Closed-world arm (as v1)"). Generates and scores the mutant corpus described there:

  - six operators (mutation/operators.py), one per defect class, ~25 mutants per class drawn by
    seeded random selection (mutation/sites.py's select_sites) from sites enumerated across every
    conformant tool -- toy (11 tools) plus the real benchmarks (tau2-bench, AgentDojo,
    MM-ToolSandbox), EXCLUDING every tool carrying a confirmed finding (anchor cases,
    mutation/real_targets.py's `anchor_exclusions`, read from report/findings.jsonl).
  - ~30 semantics-preserving precision controls (mutation/equivalence.py), at least half
    refactorings of advertised behaviour (reorder/arithmetic; see mutation/adapter_invoke.py's
    module docstring for why extract_guard_into_helper is out of scope for THIS script).

A mutant of a real tool is scored by literally patching the live tool implementation inside its
benchmark's subprocess worker (adapters/base.py's new `patch_tool`, wired into
adapters/{tau2,agentdojo,mmtoolsandbox}.py + their _*_worker.py counterparts, and toy/adapter.py
for the in-process toy domain) and running the SAME frozen checker
(dynamic.harness.run_contract, adapters/contract_check.py, core/) against it, unmodified.
"Detected" = the checker reports VIOLATES on at least one clause for that mutant.

SEED: committed here (this is the generation script; detector_analysis_plan.md sec 3: "Seed
committed here", sec 8: "the generation script ship in the artifact so a reviewer can verify the
ordering from git history"). Chosen once, before any site was drawn, and never touched again --
changing it after seeing a result would be exactly the kind of post-hoc freedom sec 5's
pre-registration exists to close off.

Output: report/mutation_closed_world_raw.jsonl -- one row per scored mutant (defect or control),
consumed by experiments/build_mutation_report.py. This script does no statistics of its own
(Wilson intervals, pooling, precision/recall) -- that is entirely build_mutation_report.py's job,
per CLAUDE.md's "generated artifacts are generated only" discipline applied to this experiment's
own outputs, not just paper/tables/.
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from adapters.agentdojo import AgentDojoAdapter, AgentDojoAdapterError  # noqa: E402
from adapters.mmtoolsandbox import MMToolSandboxAdapter, MMToolSandboxAdapterError  # noqa: E402
from adapters.tau2 import Tau2Adapter, Tau2AdapterError  # noqa: E402
from core.canonical import CanonicalConfig  # noqa: E402
from dynamic.harness import TOY_CANONICAL_CONFIG, run_contract  # noqa: E402
from mutation.adapter_invoke import (  # noqa: E402
    EQUIVALENCE_TRANSFORMS,
    MutatedAdapter,
    build_equivalence_patch_source,
    build_function_patch_source,
)
from mutation.equivalence import enumerate_equivalence_sites, select_equivalence_mutants  # noqa: E402
from mutation.operators import OPERATORS  # noqa: E402
from mutation.real_targets import RealTarget, enumerate_eligible_targets  # noqa: E402
from mutation.sites import enumerate_sites, find_function, select_sites  # noqa: E402
from toy.adapter import ToyAdapter  # noqa: E402
import ast  # noqa: E402

SEED = 20260902  # committed at generation time -- see module docstring
K_PER_CLASS = 25
N_CONTROLS = 30
OUT_PATH = PROJECT_ROOT / "report" / "mutation_closed_world_raw.jsonl"

# --- checker-freeze-v2 refreeze only (detector_analysis_plan.md sec 8) --------------------------
# "Scoring reruns on freshly drawn sites from the unused pool." V1_BACKUP_PATH is v1's raw jsonl,
# preserved with a `_v1` suffix (CLAUDE.md's refreeze instruction) BEFORE this script overwrites
# OUT_PATH. Every site v1 already drew is excluded from this run's draw pool, per operator /
# equivalence-kind-group, so a fresh seeded draw over the remainder cannot reproduce v1's sample.
#
# MECHANICAL FALLBACK, decided here before any mutant is scored (not after seeing detection
# outcomes -- this is a site-availability rule, not a results-dependent one): for a small number
# of classes the entire enumerated site pool is smaller than or equal to what v1 already drew
# (M-RESET: 5 sites total, all 5 drawn by v1; M-INVAR: 10 sites total, all 10 drawn; the
# reorder+arithmetic refactor-kind precision-control pool: 12 sites total, all 12 drawn -- see
# this run's own `operator_pool_size`/`equivalence_pool_size` output rows for the exact numbers).
# For exactly those classes, excluding v1's sites leaves an UNUSED pool of size zero, and drawing
# nothing would defeat the entire reason this refreeze exists for M-RESET/M-INVAR specifically
# (sec 8's own "fewer than 25 available, report the actual number" discipline already accepts a
# smaller-than-K sample; it does not anticipate a REFREEZE where the honest unused-pool answer is
# exactly 0). The rule applied uniformly, by pool arithmetic alone: if the unused pool for a class
# is non-empty, draw only from it (true fresh sites); if it is empty, fall back to the FULL
# current pool for that class only (unavoidable overlap with v1, flagged per-class in this run's
# output via `reused_full_pool: true` and reported in report/mutation_summary.md's v1-vs-v2
# section) so that class still gets a real sample scored against the fixed checker instead of
# silently going to n=0. No class in between these two extremes exists in this corpus: every
# other operator's unused pool is comfortably non-empty (checked against the v1 pool sizes above).
V1_BACKUP_PATH = PROJECT_ROOT / "report" / "mutation_closed_world_raw_v1.jsonl"


def _params_key(params: dict) -> tuple:
    return tuple(sorted((params or {}).items()))


def load_v1_used_keys(path: Path = V1_BACKUP_PATH) -> "tuple[set, set]":
    """(defect_keys, equivalence_keys) already drawn under checker-freeze-v1, read from the
    preserved v1 raw jsonl. defect_keys: (benchmark, tool, operator, params-tuple) -- matches
    MutationSite's own identity exactly, since a site's (tool, operator, params) triple is unique
    within one module (mutation/sites.py never emits two sites with the same triple for the same
    tool). equivalence_keys: (benchmark, tool, equivalence_kind) only -- the v1 raw jsonl never
    logged an equivalence mutant's params (see run_precision_controls' output row, unchanged
    before this refreeze), so exclusion for equivalence controls is necessarily coarser: it drops
    every site of that (tool, kind), not just the one instance v1 happened to draw. This run logs
    `site_params` for equivalence rows too (see run_precision_controls below) so a THIRD freeze
    would not have this limitation."""
    defect_keys: set = set()
    equivalence_keys: set = set()
    if not path.exists():
        return defect_keys, equivalence_keys
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("kind") == "defect_mutant" and row.get("operator") and row.get("tool") and row.get("benchmark"):
                defect_keys.add((row["benchmark"], row["tool"], row["operator"], _params_key(row.get("site_params"))))
            elif row.get("kind") == "equivalence_mutant" and row.get("tool") and row.get("benchmark"):
                equivalence_keys.add((row["benchmark"], row["tool"], row.get("equivalence_kind")))
    return defect_keys, equivalence_keys


def _unused_or_fallback(pool_all: list, unused: list) -> "tuple[list, bool]":
    """The mechanical fallback rule documented above: draw from `unused` unless it is empty, in
    which case fall back to the full `pool_all` (v1-overlap unavoidable, flagged by the caller).
    Returns (draw_pool, reused_full_pool)."""
    if unused:
        return unused, False
    return pool_all, True

CFG_BY_BENCHMARK = {
    "toy": TOY_CANONICAL_CONFIG,
    "tau2-bench": CanonicalConfig(),
    "agentdojo": CanonicalConfig(),
    "mm-toolsandbox": CanonicalConfig(),
}


def _reset_names_present(module_source: str, candidates=("reset",)) -> tuple:
    tree = ast.parse(module_source)
    out = []
    for name in candidates:
        try:
            find_function(tree, name)
            out.append(name)
        except ValueError:
            pass
    return tuple(out)


def build_targets():
    """Live base adapters (one per benchmark, kept alive for the whole run) + the eligible
    RealTarget list. Returns (adapters_by_benchmark, targets, availability_notes)."""
    adapters_by_benchmark = {"toy": ToyAdapter()}
    notes = []
    domain_by_tool = {}

    try:
        tau2 = Tau2Adapter()
        tau2.list_tools()  # cheap availability probe, matches run_all()'s discipline
        adapters_by_benchmark["tau2-bench"] = tau2
    except Tau2AdapterError as e:
        notes.append({"benchmark": "tau2-bench", "available": False, "detail": str(e)})

    try:
        ad = AgentDojoAdapter()
        domain_by_tool["agentdojo"] = {t.name: t.domain for t in ad.list_tools()}
        adapters_by_benchmark["agentdojo"] = ad
    except AgentDojoAdapterError as e:
        notes.append({"benchmark": "agentdojo", "available": False, "detail": str(e)})

    try:
        mm = MMToolSandboxAdapter()
        domain_by_tool["mm-toolsandbox"] = {t.name: t.domain for t in mm.list_tools()}
        adapters_by_benchmark["mm-toolsandbox"] = mm
    except MMToolSandboxAdapterError as e:
        notes.append({"benchmark": "mm-toolsandbox", "available": False, "detail": str(e)})

    all_targets = enumerate_eligible_targets(domain_by_tool)
    skipped = getattr(enumerate_eligible_targets, "last_skipped", [])
    for b, t, reason in skipped:
        notes.append({"benchmark": b, "tool": t, "available": False, "detail": reason})

    # Drop targets whose benchmark's adapter never came up (source read still succeeded, but
    # there is nothing live to score against).
    targets = [t for t in all_targets if t.benchmark in adapters_by_benchmark]
    for t in all_targets:
        if t.benchmark not in adapters_by_benchmark:
            notes.append({"benchmark": t.benchmark, "tool": t.tool, "available": False, "detail": "adapter unavailable"})

    return adapters_by_benchmark, targets, notes


def _rebuild_adapter(benchmark: str):
    """A fresh live adapter for `benchmark`, same construction `build_targets` used. Used only by
    the watchdog below, to replace an adapter whose subprocess worker has stopped responding."""
    if benchmark == "toy":
        return ToyAdapter()
    if benchmark == "tau2-bench":
        return Tau2Adapter()
    if benchmark == "agentdojo":
        return AgentDojoAdapter()
    if benchmark == "mm-toolsandbox":
        return MMToolSandboxAdapter()
    raise ValueError(f"unknown benchmark {benchmark!r}")


def _sibling_contracts_by_target(targets: "list[RealTarget]") -> dict:
    """`(benchmark, tool) -> tuple of every OTHER eligible target's contract sharing that SAME
    (benchmark, scenario_id)` -- the `sibling_contracts` shape `dynamic.harness.run_contract`'s
    `check_invariants` needs for its companion-sequence search (see that function's module-section
    docstring in dynamic/harness.py). Built from the SAME eligible-target list this script already
    enumerates (`build_targets`), not a second contract-loading pass -- mirrors
    `dynamic.harness._with_siblings`'s grouping rule exactly (grouped by scenario_id, since a tau2
    contract's scenario_id is one specific domain and a companion from a different domain could
    never resolve against a `fresh_env(scenario_id)` built for this one)."""
    by_scenario: dict = {}
    for t in targets:
        by_scenario.setdefault((t.benchmark, t.scenario_id), []).append(t)
    out: dict = {}
    for ts in by_scenario.values():
        for t in ts:
            out[(t.benchmark, t.tool)] = tuple(o.contract for o in ts if o.tool != t.tool)
    return out


def _detected_with_watchdog(adapters_by_benchmark, target: RealTarget, patch_source: str, seed: int, timeout: float = 45.0, sibling_contracts: tuple = ()) -> dict:
    """`_detected`, run on a background thread with a hard wall-clock budget. A subprocess-backed
    adapter's `_send` blocks on `stdout.readline()`; a sufficiently pathological mutant (observed
    empirically once during this run, cause not fully diagnosed -- a hang with zero CPU consumed
    by the orchestrator process, i.e. genuinely blocked I/O, not a spin loop) can wedge that read
    forever, and Python has no cross-platform way to interrupt a blocked thread directly. What
    DOES work: killing the underlying subprocess from another thread closes its stdout pipe,
    which makes the blocked `readline()` return `""` (EOF) and raise cleanly -- so the watchdog
    here does not try to cancel the worker thread, it forcibly closes (and replaces) the
    benchmark's adapter out from under it, and the worker thread's own `_detected` catches the
    resulting exception like any other adapter failure. One mutant is lost to a TIMEOUT error;
    the run continues with a fresh adapter for every mutant after it."""
    import threading

    box: dict = {}

    def _run():
        box["result"] = _detected(adapters_by_benchmark, target, patch_source, seed, sibling_contracts=sibling_contracts)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        # NOT base.close(): close() sends a "shutdown" RPC through the SAME lock the wedged
        # worker thread is holding while blocked inside _send's readline() -- since
        # threading.Lock is not reentrant across threads, close() would just block acquiring
        # that lock, turning "the watchdog's recovery path" into a second hang. Killing the raw
        # subprocess handle directly, bypassing the client's lock/RPC protocol entirely, is the
        # only reliable way out: the wedged readline() then returns "" (EOF), the worker
        # thread's own `with self._lock:` block exits via the resulting exception (releasing
        # the lock), and `_detected`'s except-clause reports a normal adapter-failure row.
        base = adapters_by_benchmark.get(target.benchmark)
        proc = getattr(base, "_proc", None)
        if proc is not None:
            try:
                proc.kill()
            except Exception:
                pass
        try:
            adapters_by_benchmark[target.benchmark] = _rebuild_adapter(target.benchmark)
        except Exception as e:  # noqa: BLE001
            return {"detected": None, "n_rows": 0, "verdict_counts": {},
                    "error": f"TIMEOUT after {timeout}s AND adapter restart failed: {type(e).__name__}: {e}"}
        t.join(5.0)  # let the wedged worker thread unwind after its pipe closes; daemon, safe to leave if not
        return {"detected": None, "n_rows": 0, "verdict_counts": {}, "error": f"TIMEOUT after {timeout}s -- adapter restarted"}
    result = box.get("result", {"detected": None, "n_rows": 0, "verdict_counts": {}, "error": "watchdog: worker thread finished with no result"})
    _recover_adapter_after_error(adapters_by_benchmark, target.benchmark, result)
    return result


def _recover_adapter_after_error(adapters_by_benchmark: dict, benchmark: str, result: dict) -> None:
    """Refreeze-cycle addition, found DURING this rerun (not present in checker-freeze-v1's
    version of this script, which never needed it): a subprocess-backed adapter (tau2-bench,
    AgentDojo, MM-ToolSandbox -- never "toy", which is in-process and has no wire protocol to
    desync) that raises ONE error can be left in a permanently DESYNCED state for every mutant
    scored against it for the rest of the run, not just the one that failed.

    Empirically observed here: adapters/tau2.py's `_send` reads one reply line per request and
    strips exactly one leading `_REPLY_MARKER` ("\\x01") byte before `json.loads`. Starting at one
    specific mutant (M-IGNARG on `modify_pending_order_address`, this run), every SUBSEQUENT
    tau2-bench call -- across every remaining operator, not just that one tool -- failed with
    "tau2 worker sent non-JSON output" and a `repr()` still showing a LEADING `\\x01` in the
    string `json.loads` choked on. If the marker-stripping branch fires but the line still starts
    with the marker afterward, exactly one byte of stray protocol framing was written somewhere
    upstream and every following reply is now off-by-one in the pipe -- a permanent desync of a
    STATEFUL, long-lived worker process kept alive for the whole run (`build_targets` constructs
    one adapter per benchmark and reuses it across all ~100+ mutants), not a per-mutant fluke: 18
    consecutive tau2-bench calls failed the same way immediately after the first one this run
    (confirmed from report/mutation_closed_world_raw.jsonl's row order), which is why M-INVAR's
    real-tools scope -- the operator this refreeze exists to produce real data for -- came back
    8/8 errors on the first attempt.

    This is a reliability bug in adapters/tau2.py's wire protocol (or in whatever tau2-side code
    occasionally double-writes the reply marker) -- CLAUDE.md requires stopping and reporting
    before touching that file; see the run's final report. What CAN be fixed here, entirely
    within this experiment script and without changing the checker/adapter code at all, is not
    letting one corrupted persistent connection poison every mutant scored after it: ANY reported
    error against a subprocess-backed benchmark now triggers the SAME adapter-rebuild recovery the
    watchdog above already uses for a hang, defensively, before the next mutant -- cheap relative
    to losing an entire operator's real-tools data to one early failure, and consistent with
    sec 3's "report the actual number" discipline (a mutant that still errors after a fresh
    adapter is a real, reportable failure; one that only errored because of an already-corrupted
    connection is not)."""
    if benchmark == "toy" or not result.get("error"):
        return
    old = adapters_by_benchmark.get(benchmark)
    try:
        if old is not None and hasattr(old, "close"):
            old.close()
    except Exception:
        pass
    try:
        adapters_by_benchmark[benchmark] = _rebuild_adapter(benchmark)
    except Exception:
        pass  # leave the (possibly still-broken) old adapter in place; next mutant reports its own error


def _detected(adapters_by_benchmark, target: RealTarget, patch_source: str, seed: int, sibling_contracts: tuple = ()) -> dict:
    """Patch `target.tool` to `patch_source`, run the frozen checker against it, report whether
    any clause verdict came back VIOLATES. Never raises -- a patch/invoke/checker failure is
    itself a reportable outcome (`error` populated, `detected=None`), not a crash of the whole
    corpus run.

    `sibling_contracts` (see `_sibling_contracts_by_target` above) is forwarded to
    `run_contract` so `check_invariants`'s companion-sequence search can actually run for a
    target whose own invariant clauses need a second tool's call first (toy's
    acquire_lock/release_lock pair is the shipped example) -- without it, M-INVAR recall would
    still be limited to whatever a single legal call can exercise, silently under-counting
    exactly the gap this checker fix exists to close."""
    base = adapters_by_benchmark[target.benchmark]
    mutant = MutatedAdapter(base, target.tool, patch_source)
    try:
        rows = run_contract(
            mutant, target.contract, target.scenario_id, cfg=CFG_BY_BENCHMARK[target.benchmark], seed=seed,
            sibling_contracts=sibling_contracts,
        )
        verdicts = [r["verdict"] for r in rows]
        detected = "VIOLATES" in verdicts
        return {"detected": detected, "n_rows": len(rows), "verdict_counts": _count(verdicts), "error": None}
    except Exception as e:  # noqa: BLE001 -- see docstring
        return {"detected": None, "n_rows": 0, "verdict_counts": {}, "error": f"{type(e).__name__}: {e}"}
    finally:
        try:
            mutant.close()
        except Exception:
            pass


def _count(values: list) -> dict:
    out: dict = {}
    for v in values:
        out[v] = out.get(v, 0) + 1
    return out


def run_defect_operators(adapters_by_benchmark, targets: "list[RealTarget]", out_fh) -> None:
    siblings_by_target = _sibling_contracts_by_target(targets)
    module_source_cache: dict = {}

    def source_for(target: RealTarget) -> str:
        if target.source_path not in module_source_cache:
            module_source_cache[target.source_path] = target.source_path.read_text(encoding="utf-8")
        return module_source_cache[target.source_path]

    # -- enumerate M-PHANTOM/M-PRECOND/M-IGNARG/M-PARTIAL/M-INVAR sites, per contracted tool ---
    # M-RESET is handled entirely separately below: it does not target a contracted tool at all
    # (it targets a benchmark's shared "reset" routine), so reset_names=() here always.
    all_sites = []  # list of (target, MutationSite)
    site_errors = []
    for target in targets:
        try:
            source = source_for(target)
            sites = enumerate_sites(source, [target.tool], reset_names=(), excluded_tools=frozenset())
            all_sites.extend((target, s) for s in sites)
        except Exception as e:  # noqa: BLE001
            site_errors.append({"benchmark": target.benchmark, "tool": target.tool, "detail": f"{type(e).__name__}: {e}"})

    for err in site_errors:
        out_fh.write(json.dumps({"kind": "site_enumeration_error", **err}) + "\n")

    # -- seeded draw per operator, from the POOLED (toy + real) site list -------------------
    # select_sites (mutation/sites.py, frozen, unmodified) does its own operator filter + seeded
    # shuffle over a flat MutationSite list; the (target, site) pairing is recovered afterwards
    # via id() (MutationSite instances are only ever constructed once, by enumerate_sites, and
    # never copied), the same idiom run_precision_controls uses for EquivalenceSite below.
    site_to_target = {id(s): t for (t, s) in all_sites}
    bare_all_sites = [s for (_, s) in all_sites]
    defect_keys_v1, _ = load_v1_used_keys()
    for operator in OPERATORS:
        if operator == "M-RESET":
            continue  # see run_reset_operator below
        pool_sites = [s for s in bare_all_sites if s.operator == operator]

        def _site_key(s):
            t = site_to_target[id(s)]
            return (t.benchmark, t.tool, s.operator, _params_key(s.params))

        unused_sites = [s for s in pool_sites if _site_key(s) not in defect_keys_v1]
        draw_pool, reused_full_pool = _unused_or_fallback(pool_sites, unused_sites)
        chosen_sites = select_sites(draw_pool, operator, K_PER_CLASS, SEED)
        chosen = [(site_to_target[id(s)], s) for s in chosen_sites]

        for target, site in chosen:
            source = source_for(target)
            try:
                patch_source = build_function_patch_source(source, site.tool, site.operator, dict(site.params))
            except Exception as e:  # noqa: BLE001
                out_fh.write(json.dumps({
                    "kind": "defect_mutant", "operator": operator, "benchmark": target.benchmark,
                    "tool": target.tool, "is_toy": target.is_toy, "site_detail": site.detail,
                    "site_params": site.params, "detected": None, "error": f"patch_build: {type(e).__name__}: {e}",
                }) + "\n")
                continue
            result = _detected_with_watchdog(
                adapters_by_benchmark, target, patch_source, SEED,
                sibling_contracts=siblings_by_target.get((target.benchmark, target.tool), ()),
            )
            out_fh.write(json.dumps({
                "kind": "defect_mutant", "operator": operator, "benchmark": target.benchmark,
                "tool": target.tool, "is_toy": target.is_toy, "site_detail": site.detail,
                "site_params": site.params, **result,
            }) + "\n")
        out_fh.write(json.dumps({
            "kind": "operator_pool_size", "operator": operator, "pool_size": len(pool_sites),
            "unused_pool_size": len(unused_sites), "reused_full_pool": reused_full_pool,
            "drawn": len(chosen), "requested": K_PER_CLASS,
        }) + "\n")

    run_reset_operator(adapters_by_benchmark, targets, source_for, out_fh, defect_keys_v1)


def run_reset_operator(adapters_by_benchmark, targets: "list[RealTarget]", source_for, out_fh, defect_keys_v1: set = frozenset()) -> None:
    """M-RESET, scored through `dynamic.harness.check_reset` (added alongside this change -- see
    that function's docstring in dynamic/harness.py). BEFORE this fix, `run_contract` never
    called `Adapter.reset()` at all and nothing evaluated a contract's `reset:` clause; every
    M-RESET mutant this section drew was reported UNTESTABLE with reason
    `no_reset_path_checker`, structurally, without ever being run -- see this function's git
    history for that version's full docstring. That was correct UNDER checker-freeze-v1: CLAUDE.md
    is explicit that finding a gap like this means "stop and report", not quietly patch a new
    check around it without a refreeze. This IS the refreeze's fix.

    `reset` is not itself a contracted tool (mutation/sites.py's `reset_names=` sites target the
    reset ROUTINE, not an agent-visible tool), so a mutant here has no contract of its own to run
    `run_contract` against. It is instead patched in as `tool="reset"` (toy/adapter.py's
    `patch_tool` was loosened alongside this fix to accept `"reset"` in addition to
    `MUTATING_TOOLS`, precisely for this) and scored against EVERY eligible contracted tool
    sharing that module -- since `reset()` restores the WHOLE environment, a dropped field-restore
    is only witnessed by whichever contract's own probe actually touches that field. "Detected" =
    any VIOLATES row from any of them, mirroring `_detected`'s own "any VIOLATES row" convention
    for every other operator.

    Confirmed empirically (unchanged by this fix): only the toy domain's module source contains a
    function literally named "reset" among this corpus's eligible tools' own modules, so this
    section's site pool remains toy-only -- real-benchmark M-RESET recall is still N/A, not 0/0,
    and the report must keep saying so (this function no longer manufactures that distinction
    itself; see experiments/build_mutation_report.py's own updated M-RESET handling)."""
    seen_modules: dict = {}  # source_path -> (benchmark, is_toy, source_text, [witness targets])
    witnesses_by_path: dict = {}
    for target in targets:
        witnesses_by_path.setdefault(target.source_path, []).append(target)
        if target.source_path not in seen_modules:
            try:
                source = source_for(target)
            except Exception:  # noqa: BLE001
                continue
            reset_names = _reset_names_present(source)
            if reset_names:
                seen_modules[target.source_path] = (target.benchmark, target.is_toy, source)

    pool = []  # (benchmark, is_toy, source, source_path, MutationSite)
    for source_path, (benchmark, is_toy, source) in seen_modules.items():
        reset_names = _reset_names_present(source)
        sites = enumerate_sites(source, [], reset_names=reset_names, excluded_tools=frozenset())
        pool.extend((benchmark, is_toy, source, source_path, s) for s in sites)

    bare = [s for (_, _, _, _, s) in pool]
    site_index = {id(s): (b, t, src, path) for (b, t, src, path, s) in pool}

    def _reset_site_key(s):
        b, _, _, _ = site_index[id(s)]
        return (b, s.tool, s.operator, _params_key(s.params))

    unused_bare = [s for s in bare if _reset_site_key(s) not in defect_keys_v1]
    draw_pool, reused_full_pool = _unused_or_fallback(bare, unused_bare)
    chosen_sites = select_sites(draw_pool, "M-RESET", K_PER_CLASS, SEED)

    for site in chosen_sites:
        benchmark, is_toy, source, source_path = site_index[id(site)]
        witness_targets = witnesses_by_path.get(source_path, [])
        try:
            patch_source = build_function_patch_source(source, site.tool, site.operator, dict(site.params))
        except Exception as e:  # noqa: BLE001
            out_fh.write(json.dumps({
                "kind": "defect_mutant", "operator": "M-RESET", "benchmark": benchmark, "tool": site.tool,
                "is_toy": is_toy, "site_detail": site.detail, "site_params": site.params,
                "detected": None, "n_rows": 0, "verdict_counts": {}, "error": f"patch_build: {type(e).__name__}: {e}",
            }) + "\n")
            continue

        base = adapters_by_benchmark[benchmark]
        mutant = MutatedAdapter(base, site.tool, patch_source)
        detected = False
        n_rows = 0
        verdict_counts: dict = {}
        error = None
        try:
            for wt in witness_targets:
                siblings = tuple(o.contract for o in witness_targets if o.tool != wt.tool)
                rows = run_contract(
                    mutant, wt.contract, wt.scenario_id, cfg=CFG_BY_BENCHMARK[benchmark], seed=SEED,
                    sibling_contracts=siblings,
                )
                n_rows += len(rows)
                for r in rows:
                    verdict_counts[r["verdict"]] = verdict_counts.get(r["verdict"], 0) + 1
                if any(r["verdict"] == "VIOLATES" for r in rows):
                    detected = True
        except Exception as e:  # noqa: BLE001 -- a patch/invoke/checker failure is itself a
            # reportable outcome, not a crash of the whole corpus run, matching `_detected`.
            detected = None
            error = f"{type(e).__name__}: {e}"
        finally:
            try:
                mutant.close()
            except Exception:
                pass

        out_fh.write(json.dumps({
            "kind": "defect_mutant", "operator": "M-RESET", "benchmark": benchmark, "tool": site.tool,
            "is_toy": is_toy, "site_detail": site.detail, "site_params": site.params,
            "detected": detected, "n_rows": n_rows, "verdict_counts": verdict_counts, "error": error,
        }) + "\n")
    out_fh.write(json.dumps({
        "kind": "operator_pool_size", "operator": "M-RESET", "pool_size": len(bare),
        "unused_pool_size": len(unused_bare), "reused_full_pool": reused_full_pool,
        "drawn": len(chosen_sites), "requested": K_PER_CLASS,
    }) + "\n")


def run_precision_controls(adapters_by_benchmark, targets: "list[RealTarget]", out_fh) -> None:
    module_source_cache: dict = {}

    def source_for(target: RealTarget) -> str:
        if target.source_path not in module_source_cache:
            module_source_cache[target.source_path] = target.source_path.read_text(encoding="utf-8")
        return module_source_cache[target.source_path]

    all_sites = []  # (target, EquivalenceSite)
    for target in targets:
        try:
            source = source_for(target)
            sites = enumerate_equivalence_sites(source, [target.tool])
            # extract_guard_into_helper is a whole-module (adds-a-class-member) transform, out
            # of scope for the single-function live-patch mechanism this script uses -- see
            # mutation/adapter_invoke.py's module docstring. Filtered out here, not upstream in
            # mutation/equivalence.py, which stays untouched and still fully exercises it via
            # tests/test_mutation_equivalence.py against the toy class-loading path.
            sites = [s for s in sites if s.kind in EQUIVALENCE_TRANSFORMS]
            all_sites.extend((target, s) for s in sites)
        except Exception:  # noqa: BLE001
            continue

    # select_equivalence_mutants shuffles two typed pools (refactor/trivial) with `random.Random
    # (seed)`; reproduce the same selection over (target, site) pairs by pairing each
    # EquivalenceSite object with its target through a dict keyed by id(), since
    # select_equivalence_mutants itself only ever sees and returns EquivalenceSite objects.
    site_to_target = {id(s): t for (t, s) in all_sites}
    bare_sites_all = [s for (_, s) in all_sites]

    # Refreeze-only unused-pool exclusion (see the module-level note above run_defect_operators'
    # equivalent logic). Equivalence rows in v1's raw jsonl never logged `site_params` (that gap
    # is closed below, for a future third freeze), so exclusion here is coarser: (benchmark,
    # tool, kind), not (benchmark, tool, kind, params) -- it drops every site of a (tool, kind)
    # v1 touched at all, not just the one instance v1 drew. Applied PER KIND-GROUP (refactor vs
    # trivial), independently, because select_equivalence_mutants' own >=50%-refactor floor
    # depends on the refactor pool's size specifically -- the same zero-unused fallback rule
    # applies to each group on its own terms. v1 drew all 12 of the 12 available refactor-kind
    # (reorder+arithmetic) sites in this corpus, so the refactor group falls back to the full
    # pool here (flagged via `reused_full_pool` in the emitted `equivalence_pool_size` row),
    # while the much larger trivial-kind pool (167 sites, 12 used) draws fresh as normal.
    _, equivalence_keys_v1 = load_v1_used_keys()

    def _eq_site_key(s):
        t = site_to_target[id(s)]
        return (t.benchmark, t.tool, s.kind)

    refactor_all = [s for s in bare_sites_all if s.kind in ("reorder", "arithmetic")]
    trivial_all = [s for s in bare_sites_all if s.kind in ("rename", "reword")]
    refactor_unused = [s for s in refactor_all if _eq_site_key(s) not in equivalence_keys_v1]
    trivial_unused = [s for s in trivial_all if _eq_site_key(s) not in equivalence_keys_v1]
    refactor_pool, refactor_reused_full = _unused_or_fallback(refactor_all, refactor_unused)
    trivial_pool, trivial_reused_full = _unused_or_fallback(trivial_all, trivial_unused)
    bare_sites = refactor_pool + trivial_pool
    refactor_pool_size = len(refactor_pool)
    # N_CONTROLS (~30, sec 3) assumed a refactor pool large enough to fill >=50% of it; with
    # extract_guard_into_helper out of scope for this script (see the filter above), the actual
    # reorder+arithmetic pool across all 36 eligible tools is smaller than that. Rather than
    # backfill the shortfall with trivial edits (which would silently violate the >=50% floor --
    # exactly the W5 failure mode the floor exists to prevent), N is capped here, MECHANICALLY
    # and BEFORE any mutant is drawn, so the floor is always met exactly: this is a formula
    # applied deterministically to a pool size known in advance, not a choice made after seeing
    # which mutants got flagged.
    n_controls = min(N_CONTROLS, 2 * refactor_pool_size)
    chosen = select_equivalence_mutants(bare_sites, n=n_controls, seed=SEED, min_refactor_fraction=0.5)

    for site in chosen:
        target = site_to_target[id(site)]
        source = source_for(target)
        try:
            patch_source = build_equivalence_patch_source(source, site.tool, site.kind, dict(site.params))
        except Exception as e:  # noqa: BLE001
            patch_source = None
            build_error = f"{type(e).__name__}: {e}"
        else:
            build_error = None if patch_source is not None else "transform returned None (no applicable site)"

        if patch_source is None:
            out_fh.write(json.dumps({
                "kind": "equivalence_mutant", "equivalence_kind": site.kind, "benchmark": target.benchmark,
                "tool": target.tool, "is_toy": target.is_toy, "site_params": site.params,
                "detected": None, "error": build_error,
            }) + "\n")
            continue

        result = _detected_with_watchdog(adapters_by_benchmark, target, patch_source, SEED)
        out_fh.write(json.dumps({
            "kind": "equivalence_mutant", "equivalence_kind": site.kind, "benchmark": target.benchmark,
            "tool": target.tool, "is_toy": target.is_toy, "site_params": site.params, **result,
        }) + "\n")

    out_fh.write(json.dumps({
        "kind": "equivalence_pool_size", "pool_size": len(bare_sites), "drawn": len(chosen),
        "requested": N_CONTROLS, "n_controls_used": n_controls,
        "refactor_pool_size": refactor_pool_size,
        "trivial_pool_size": len([s for s in bare_sites if s.kind in ("rename", "reword")]),
        "refactor_pool_size_all": len(refactor_all), "refactor_unused_pool_size": len(refactor_unused),
        "refactor_reused_full_pool": refactor_reused_full,
        "trivial_pool_size_all": len(trivial_all), "trivial_unused_pool_size": len(trivial_unused),
        "trivial_reused_full_pool": trivial_reused_full,
    }) + "\n")


def main() -> int:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    adapters_by_benchmark, targets, notes = build_targets()
    print(f"seed={SEED}  eligible targets={len(targets)}  benchmarks={sorted(adapters_by_benchmark)}")
    for n in notes:
        print("NOTE:", n)

    try:
        with open(OUT_PATH, "w", encoding="utf-8") as out_fh:
            out_fh.write(json.dumps({"kind": "run_header", "seed": SEED, "k_per_class": K_PER_CLASS,
                                       "n_controls": N_CONTROLS, "n_targets": len(targets),
                                       "targets": [{"benchmark": t.benchmark, "tool": t.tool, "is_toy": t.is_toy} for t in targets],
                                       "notes": notes}) + "\n")
            print("enumerating + scoring defect operators...")
            run_defect_operators(adapters_by_benchmark, targets, out_fh)
            out_fh.flush()
            print("enumerating + scoring precision controls...")
            run_precision_controls(adapters_by_benchmark, targets, out_fh)
    finally:
        for name, a in adapters_by_benchmark.items():
            if hasattr(a, "close"):
                try:
                    a.close()
                except Exception:
                    pass

    print(f"wrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
