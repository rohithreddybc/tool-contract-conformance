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


def _detected_with_watchdog(adapters_by_benchmark, target: RealTarget, patch_source: str, seed: int, timeout: float = 45.0) -> dict:
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
        box["result"] = _detected(adapters_by_benchmark, target, patch_source, seed)

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
    return box.get("result", {"detected": None, "n_rows": 0, "verdict_counts": {}, "error": "watchdog: worker thread finished with no result"})


def _detected(adapters_by_benchmark, target: RealTarget, patch_source: str, seed: int) -> dict:
    """Patch `target.tool` to `patch_source`, run the frozen checker against it, report whether
    any clause verdict came back VIOLATES. Never raises -- a patch/invoke/checker failure is
    itself a reportable outcome (`error` populated, `detected=None`), not a crash of the whole
    corpus run."""
    base = adapters_by_benchmark[target.benchmark]
    mutant = MutatedAdapter(base, target.tool, patch_source)
    try:
        rows = run_contract(mutant, target.contract, target.scenario_id, cfg=CFG_BY_BENCHMARK[target.benchmark], seed=seed)
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
    for operator in OPERATORS:
        if operator == "M-RESET":
            continue  # see run_reset_operator below
        pool_sites = [s for s in bare_all_sites if s.operator == operator]
        chosen_sites = select_sites(bare_all_sites, operator, K_PER_CLASS, SEED)
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
            result = _detected_with_watchdog(adapters_by_benchmark, target, patch_source, SEED)
            out_fh.write(json.dumps({
                "kind": "defect_mutant", "operator": operator, "benchmark": target.benchmark,
                "tool": target.tool, "is_toy": target.is_toy, "site_detail": site.detail,
                "site_params": site.params, **result,
            }) + "\n")
        out_fh.write(json.dumps({
            "kind": "operator_pool_size", "operator": operator, "pool_size": len(pool_sites),
            "drawn": len(chosen), "requested": K_PER_CLASS,
        }) + "\n")

    run_reset_operator(targets, source_for, out_fh)


def run_reset_operator(targets: "list[RealTarget]", source_for, out_fh) -> None:
    """M-RESET cannot be scored by `dynamic.harness.run_contract` at all: that function never
    calls `Adapter.reset()` and neither it nor `adapters/contract_check.py` implements any
    evaluator for a contract's `reset:` clause (spec/schema.json documents the clause and its
    `no_reset_path` UNTESTABLE reason code; nothing in the currently-wired dynamic checker reads
    it -- confirmed by grep, not assumed). This is a genuine gap in the FROZEN checker's actual
    coverage, discovered while wiring this experiment -- CLAUDE.md is explicit that finding such
    a gap means "stop and report", not quietly add a new check_reset() function after
    checker-freeze-v1 (which would itself trigger sec 8's refreeze rule and change what
    "detected" means for every other operator too). So: every M-RESET mutant this section draws
    is reported as UNTESTABLE with reason `no_reset_path_checker`, never as a false "not
    detected" -- the corpus and its denominator are still fully reported (sec 5: "UNTESTABLE
    stays in all denominators with reason codes"), just never fed into run_contract.

    A second, independent consequence of the same design (adapters reset by reconstructing a
    whole fresh environment -- see adapters/_tau2_worker.py, _agentdojo_worker.py,
    _mmtoolsandbox_worker.py, and toy/bank.py's own `reset()` -- confirmed empirically: only the
    toy domain's module source contains a function literally named "reset" among this corpus's
    36 eligible tools' own modules) is that M-RESET's site pool is toy-only in this corpus. Sites
    are enumerated ONCE per distinct module (not once per contracted tool that happens to share
    that module) to avoid counting the same reset() field assignment many times over.
    """
    seen_modules: dict = {}  # source_path -> (benchmark, is_toy, source_text)
    for target in targets:
        if target.source_path not in seen_modules:
            try:
                source = source_for(target)
            except Exception:  # noqa: BLE001
                continue
            reset_names = _reset_names_present(source)
            if reset_names:
                seen_modules[target.source_path] = (target.benchmark, target.is_toy, source)

    pool = []  # (benchmark, is_toy, source, MutationSite)
    for source_path, (benchmark, is_toy, source) in seen_modules.items():
        reset_names = _reset_names_present(source)
        sites = enumerate_sites(source, [], reset_names=reset_names, excluded_tools=frozenset())
        pool.extend((benchmark, is_toy, source, s) for s in sites)

    bare = [s for (_, _, _, s) in pool]
    site_index = {id(s): (b, t, src) for (b, t, src, s) in pool}
    chosen_sites = select_sites(bare, "M-RESET", K_PER_CLASS, SEED)

    for site in chosen_sites:
        benchmark, is_toy, source = site_index[id(site)]
        out_fh.write(json.dumps({
            "kind": "defect_mutant", "operator": "M-RESET", "benchmark": benchmark, "tool": site.tool,
            "is_toy": is_toy, "site_detail": site.detail, "site_params": site.params,
            "detected": None, "n_rows": 0, "verdict_counts": {}, "error": "UNTESTABLE:no_reset_path_checker",
        }) + "\n")
    out_fh.write(json.dumps({
        "kind": "operator_pool_size", "operator": "M-RESET", "pool_size": len(bare),
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
    bare_sites = [s for (_, s) in all_sites]
    refactor_pool_size = len([s for s in bare_sites if s.kind in ("reorder", "arithmetic")])
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
                "tool": target.tool, "is_toy": target.is_toy, "detected": None, "error": build_error,
            }) + "\n")
            continue

        result = _detected_with_watchdog(adapters_by_benchmark, target, patch_source, SEED)
        out_fh.write(json.dumps({
            "kind": "equivalence_mutant", "equivalence_kind": site.kind, "benchmark": target.benchmark,
            "tool": target.tool, "is_toy": target.is_toy, **result,
        }) + "\n")

    out_fh.write(json.dumps({
        "kind": "equivalence_pool_size", "pool_size": len(bare_sites), "drawn": len(chosen),
        "requested": N_CONTROLS, "n_controls_used": n_controls,
        "refactor_pool_size": refactor_pool_size,
        "trivial_pool_size": len([s for s in bare_sites if s.kind in ("rename", "reword")]),
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
