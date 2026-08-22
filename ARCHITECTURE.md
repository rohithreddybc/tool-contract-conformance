# Executable Tool-Contract Conformance Testing for Agentic Benchmarks
## Architecture & Schedule — IEEE BigData 2026 (Intelligent Data Mining), deadline Sep 27 2026

---

## 0. Positioning determination (done first; everything follows from it)

Verified via web search 2026-08-21 (independent of the separate verification pass):

- **2607.02577 exists** — actual title "Benchmarking the Benchmarks: A Validity Audit of Tool-Calling Evaluation" (the "Tool-Veritas" name refers to a benchmark artifact inside it). Audits tau2-bench, LiveMCPBench, MCP-Atlas. **Scope: the grading layer** — evaluator–human disagreements (92 found), taxonomy of brittle state matching, trajectory lock-in, reward-basis mismatch, rubric drift, judge variance. It asks *does the evaluator grade the state correctly*. It does **not** test whether tool implementations conform to their advertised executable semantics.
- **2601.04688 (ToolGate) exists** — Hoare-style contracts (pre/postconditions) for **runtime enforcement** inside an agent framework: gate invocation, verify commits, prevent hallucinated state. Prospective safety mechanism, not adversarial testing of benchmark code. Cite as formalism precedent; we repurpose the formalism as a test oracle.
- BenchGuard / Auto Benchmark Audit / SafeAudit: unverified at this pass. Treat as taxonomy-level and breadth-level audits respectively. Positioning below is robust whether or not they exist as described.

**Determination: no collision on the core claim.** The stack has three layers: (1) tool interface/docs, (2) tool implementation + environment state transitions, (3) evaluator. Tool-Veritas covers layer 3. ToolGate covers contracts at agent runtime. Nobody systematically tests **layer 1 → layer 2 conformance in benchmark code** — the interface→implementation→state-transition contract. That is the paper.

**Narrowed contribution statement (write the intro around this):**
1. A contract specification for mutating tool interfaces whose clauses are *provenance-bound* (every clause cites the docstring/schema line it operationalizes — we test advertised semantics, never inferred intent).
2. A static+dynamic conformance checker with a **mutation-validated** detector suite (precision/recall reported, the methodological differentiator no prior audit has).
3. Cross-benchmark measurement (4–6 benchmarks) + an agent-impact experiment showing defects change *agent evaluation outcomes*, not just code quality.

**Consequences:** drop MCP-Atlas from candidates (2607.02577 already covers it; attribution already flagged as messy — double reason). Related-work section gets a layer diagram (tools vs evaluator vs runtime enforcement) so reviewers see the boundary in one figure. If BenchGuard's 14-subcategory taxonomy exists, map our 6 classes into it in a table ("theirs classifies, ours executes"); if it doesn't, the taxonomy section stands alone. Both versions of that paragraph get drafted.

---

## 1. System architecture

```
conformance/
├── spec/
│   ├── schema.json              # JSON Schema for contract files (the format, §2)
│   └── contracts/<bench>/<tool>.yaml
├── core/
│   ├── model.py                 # Contract, Clause, Probe, Finding, Verdict dataclasses
│   ├── state.py                 # canonical state snapshot + structural diff engine
│   └── verdict.py               # CONFORMS / VIOLATES(witness) / UNTESTABLE(reason)
├── adapters/
│   ├── base.py                  # BenchmarkAdapter ABC (the plug-in seam, below)
│   ├── medagentbench.py
│   ├── tau2.py
│   └── <bench3..6>.py
├── static_check/
│   ├── extract.py               # docstring/signature/schema → draft clauses (human-reviewed)
│   └── checks.py                # AST checks: constant-success returns, dead guards,
│                                #   args unused in body, unpaired state writes
├── dynamic/
│   ├── harness.py               # snapshot → invoke → snapshot → evaluate clauses
│   └── probes.py                # per-defect-class probe generators (§2 mapping)
├── mutation/
│   ├── operators.py             # 6 operators, AST-level (§3)
│   ├── sites.py                 # programmatic mutation-site enumeration
│   └── score.py                 # precision/recall + Wilson CIs
├── report/
│   ├── findings.jsonl           # machine-readable report (deliverable 6)
│   ├── report_schema.json
│   └── render.py                # findings.jsonl → LaTeX tables/figures (only path to paper numbers)
├── experiments/
│   ├── affected_tasks.py        # trace analysis: which tasks traverse defective tools
│   ├── ab_run.py                # buggy vs patched runs (§4)
│   ├── analysis_plan.md         # PRE-REGISTERED, committed before any run
│   └── patches/<bench>/*.diff   # minimal one-hunk fixes
└── repro/
    ├── run_all.sh               # regenerates every paper number offline from pinned inputs
    └── env/                     # lockfiles + benchmark commits as submodules @ pinned SHAs
```

**Adapter interface** (`adapters/base.py`) — the entire per-benchmark cost lives here, ~200–400 LOC each:

```
class BenchmarkAdapter:
    list_tools() -> list[ToolRef]            # name, source file:lines, docstring, signature
    fresh_env(scenario_id) -> EnvHandle      # isolated, deterministic seed
    snapshot(env) -> dict                    # canonical JSON of full mutable state
    invoke(env, tool, args) -> ToolResult    # raw return + parsed success signal
    reset(env) -> None                       # benchmark's own reset path (tests Reset Leak)
    source(tool) -> SourceRef                # for static checks + finding attribution
```

**Data flow:** docstrings/schemas → `extract.py` drafts clauses → human review + provenance annotation → `contracts/*.yaml` → (a) `static_check` flags candidate sites, (b) `dynamic/harness` executes probes against fresh envs → per-clause verdicts → `findings.jsonl` (each finding: benchmark, pinned commit, tool, clause id, probe args, pre/post snapshots, verdict, source-line evidence) → `render.py` → tables. **No paper number exists outside `render.py` output**; `repro/run_all.sh` regenerates everything offline (deposit repo + Zenodo DOI, benchmark repos as pinned submodules, no network calls in the pipeline).

---

## 2. Contract specification format (the intellectual core)

One YAML file per mutating tool, validated by `spec/schema.json`. A contract states what the tool *advertises*; the checker verifies implementation and state transitions against it.

```yaml
tool: cancel_reservation
benchmark: tau2-bench
commit: c3398666
source: domains/airline/tools.py:360-380
signature:
  args:
    reservation_id: {type: str, effective: true}   # 'effective' = advertised to influence outcome
preconditions:
  - id: pre.reservation_exists
    text: "reservation must exist"                  # verbatim/near-verbatim from source
    provenance: {file: tools.py, line: 363, kind: docstring}
    predicate: "args.reservation_id in state.reservations"
effects:                                            # postconditions as delta assertions
  - id: eff.seats_released
    text: "cancelling releases the reserved seats"
    provenance: {file: tools.py, line: 365, kind: docstring}
    predicate: "post.flights[f].available_seats == pre.flights[f].available_seats + booked_seats"
frame:                                              # what must NOT change (catches Partial Effect)
  - "state.customers.*.payment_methods"
success_signal:
  predicate: "result.status == 'success'"
  biconditional: true                               # success ⟺ all effects applied (catches Phantom Effect)
on_precondition_violation:
  expect: {error_signal: true, state_delta: none}   # catches Unenforced Precondition
invariants:                                         # env-level, checked across call sequences
  - id: inv.seat_conservation
    predicate: "sum(seats_booked) + available == capacity"
reset:
  predicate: "snapshot_after_reset == initial_snapshot"   # catches Reset Leak
```

**Predicate language:** restricted Python expressions over `(pre, post, args, result)` bound to canonical snapshots — evaluated with `eval` on a whitelisted AST (no attribute access outside snapshot dicts, no calls except a small stdlib of `len/sum/in`). Deliberately not a new DSL: reviewable, executable, no parser to defend.

**Provenance rule (the construct-validity firewall):** every clause carries a `provenance` pointer to the docstring/schema/README text it operationalizes. Clauses without textual grounding are marked `inferred: true` and **excluded from all headline counts** — reported separately. A maintainer cannot dispute "your docstring says X, the code does not-X" the way they can dispute inferred intent. This directly answers the construct-validity objection this design anticipates.

**Verdict lattice:** every clause resolves to CONFORMS, VIOLATES (with a minimal witness: probe args + pre/post diff), or UNTESTABLE (with reason code: no reset path, nondeterministic env, unreachable precondition state). UNTESTABLE is reported in all denominators — no silent dropping.

**Defect taxonomy → clause mapping (executable definitions):**

| Defect class | Operational definition (checker rule) |
|---|---|
| Phantom Effect | `success_signal` true ∧ effects delta absent |
| Unenforced Precondition | precondition predicate false ∧ (no error signal ∨ state mutated) |
| Ignored Argument | vary an `effective: true` arg over probe set; post-state ∧ result invariant to it |
| Partial Effect | ≥1 effect predicate holds ∧ ≥1 fails on the same call |
| Invariant Break | env invariant predicate false after a legal call sequence |
| Reset Leak | snapshot after adapter.reset ≠ initial snapshot |

Known findings as sanity anchors: MedAgentBench POST branch (`src/server/tasks/medagentbench/__init__.py` L85–91) = Phantom Effect; tau2 `refuel_data` (telecom/tools.py L608, guard commented at L629–630) = Unenforced Precondition; tau2 `cancel_reservation` (airline/tools.py L367, cf. book L315, TODO L689) = Partial Effect + Invariant Break. The framework must rediscover all three from contracts alone — that is the integration gate (Aug 27, §5).

---

## 3. Mutation operators & non-circular precision/recall

One operator per defect class, applied at the AST level to **known-correct tools** (tools that pass full conformance in audited benchmarks, plus a purpose-built ~10-tool toy domain with hand-verified semantics):

| Operator | Transformation |
|---|---|
| M-PHANTOM | replace mutation body with success-return stub (signature/return preserved) |
| M-PRECOND | delete or negate one guard clause |
| M-IGNARG | rebind one effective argument to a constant/default inside the body |
| M-PARTIAL | delete one of ≥2 state writes in the effect block |
| M-INVAR | remove the compensating write in a paired operation (e.g., release without decrement) |
| M-RESET | remove one field assignment from the reset routine |

**Anti-circularity protocol** (the risk: a checker that only refinds the 3 known bugs):
1. **Site enumeration is programmatic** (`sites.py` walks ASTs for guards, writes, arg uses) across all conformant tools; mutant sample drawn by seeded random selection, not hand-picked. The 3 known-defective tools are **excluded** from the mutation corpus.
2. **Freeze-then-mutate:** checker + contracts are tagged (`checker-freeze-v1`) *before* the mutant set is generated. Any post-hoc checker change invalidates the sample; scoring reruns on freshly drawn sites from the unused pool. The freeze tag and generation script are in the artifact — reviewers can verify ordering from git history.
3. **Equivalent-mutant control:** include mutants that alter only *unadvertised* behavior (e.g., log strings, internal variable names, effects with no contract clause). These must NOT be flagged; they feed the precision denominator. Precision = true-detections / all-flags; recall = detected / injected-nonequivalent; per class, with Wilson 95% CIs.
4. **No per-benchmark tuning:** operators are generic AST transforms; recall reported per benchmark to demonstrate transfer.

Budget: ~25 mutants/class ≈ 150 mutants + ~30 equivalence controls. Checker runs are seconds each; whole matrix reruns in minutes (also the repro story).

---

## 4. Buggy-vs-patched agent experiment (minimum viable, deliverable 5)

**Purpose:** show defects change *agent evaluation outcomes* — this converts a bug report into an agent-evaluation paper. Keep the inferential surface minimal (the methodological surface is the exposed one).

**Design:** within-task paired comparison. `affected_tasks.py` identifies tasks whose reference solution or observed traces traverse a defective tool (expect 10–20 across MedAgentBench + tau2). Two conditions: as-shipped vs minimally patched (one-hunk diffs in `experiments/patches/`, restoring only the advertised semantics — diffs printed in appendix). Same agent scaffold, same fixed mid-tier model, same prompts.

**Two-tier analysis, pre-registered in `experiments/analysis_plan.md` (committed Sep 9, hash cited in paper):**
- **Tier 1 — deterministic, primary.** Temperature 0, one run per (task, condition). Outcome: does the benchmark's own evaluator score the identical agent behavior differently, or does the defect change the reachable state so the score flips? Report **exact counts of score flips with per-task trace evidence**. This is mechanistic ("defect D on task T flips the grade; here is the pre/post diff"), not statistical — zero inferential surface, and it is the headline.
- **Tier 2 — stochastic, supporting.** Temperature 0.7, 4 seeds × N tasks × 2 conditions (≈80–160 short runs, cheap model). **Unit of analysis = task** (aggregate seeds within task to a success proportion first — this avoids the repeated-measures error from the prior rejection). Paired across conditions; report per-task deltas, a sign/McNemar test on task-level direction, exact CI on the discordant pairs. With ~15 tasks this only detects large effects — say so explicitly and frame Tier 2 as effect-magnitude illustration, not discovery.

**Defensibility rules:** no cross-benchmark pooling; no model comparisons; no significance language in the abstract; the causal claim rests on Tier 1 mechanism, statistics only characterize variability.

---

## 5. Day-by-day schedule (Aug 21 → Sep 27, 37 days)

| Dates | Work | Gate |
|---|---|---|
| Aug 21–22 | Contract schema v1 + `core/` model + verdict lattice. Read 2607.02577 and ToolGate fully; draft both variants of related-work paragraphs. | Schema frozen enough to author contracts |
| Aug 23–25 | MedAgentBench + tau2 adapters; contracts for all mutating tools in both (est. 25–40 tools); dynamic harness MVP | Adapters snapshot/invoke/reset reliably |
| Aug 26–27 | End-to-end run on both benchmarks | **GATE 1: framework rediscovers all 3 known findings from contracts alone. Do not proceed until it does.** |
| Aug 28–29 | Static checker (`extract.py`, `checks.py`); toy reference domain (10 tools) | |
| Aug 30–31 | Mutation operators + site enumeration; tag `checker-freeze-v1`; generate mutant corpus; score P/R | **GATE 2: recall ≥ ~0.8/class or diagnose+refreeze with fresh sites** |
| Sep 1–2 | Benchmark 3: AgentDojo (1-day timeboxed adapter spike Sep 1; commit or swap by noon Sep 2) | |
| Sep 3–4 | Benchmark 4: MM-ToolSandbox (same timebox protocol; contract authoring is the bulk — 500+ tools means *sample* mutating tools, state the sampling frame) | |
| Sep 5–6 | Stretch: benchmarks 5–6 (AgentBench FC, AppWorld) only if 3–4 landed clean; else harden 1–4 | |
| Sep 7–8 | Findings triage: manually confirm every VIOLATES with a minimal repro; write reason codes for every UNTESTABLE | **GATE 3: findings.jsonl v1 frozen** |
| Sep 9 | Commit pre-registered `analysis_plan.md` + patches; identify affected tasks | |
| Sep 10 | **Coordinated disclosure emails to all maintainers** (findings + repros + patches). Checker frozen for good. | |
| Sep 10–12 | Agent A/B experiment: Tier 1 then Tier 2 runs | |
| Sep 13–15 | Paper: intro, related work (layer-diagram figure), spec section, taxonomy — parallel with any experiment stragglers | |
| Sep 16–18 | Paper: results sections generated via `render.py`; mutation P/R tables; A/B section | |
| Sep 19 | Full draft complete | **GATE 4** |
| Sep 20–21 | Artifact: Zenodo deposit, `run_all.sh` clean-machine offline test, pinned submodules, lockfiles | |
| Sep 22 | Number audit: every paper number regenerated from deposited artifact only; diff against draft | |
| Sep 23–25 | Revision; internal/simulated review pass; fold in maintainer responses received to date ("no response by Sep 25" is itself reportable) | |
| Sep 26 | Buffer / camera-prep | |
| Sep 27 | **Submit IEEE BigData** | Backstop: ML on Big Data, Sep 30 |

**Cut order if behind (drop top-first):**
1. Benchmarks 5–6 (keep 4).
2. Tier 2 (stochastic) arm of the agent experiment — Tier 1 deterministic flips carry the claim.
3. Static checker demoted from "detector" to "candidate-flagging aid" (dynamic-only headline results; static becomes one paragraph).
4. Benchmark 4 (floor = 3 benchmarks + full mutation validation + Tier 1 experiment).
5. Below that floor: slip to Sep 30 backstop; nothing else is cuttable.
**Never cut:** mutation validation, provenance rule, reproducibility artifact, disclosure.

---

## 6. Top three risks to shipping

1. **Adapter/env integration blowup on benchmarks 3–4** (no clean reset, nondeterministic state, snapshot impossible). *Mitigation:* hard 1-day spike timebox per candidate with a go/no-go checklist (fresh_env? snapshot? deterministic replay?); ranked substitute list (AgentDojo → MM-ToolSandbox → AgentBench FC → AppWorld); paper framing written so N=3 benchmarks is a complete result, "we audit N" filled in last. Environments that fail the checklist become UNTESTABLE rows — reportable, not wasted.
2. **Mutation validation exposes checker weakness late (Gate 2 fails: low recall on classes without a known real-world anchor, e.g., Reset Leak, Ignored Argument).** *Mitigation:* Gate 2 sits Aug 31 — 27 days of runway; the toy domain exists precisely to debug detectors independent of benchmark quirks; freeze-then-mutate protocol permits refreeze cycles with fresh site draws, all logged in git so the ordering stays auditable.
3. **Late positioning damage** — the pending verification pass or a fresh read of 2607.02577 reveals overlap larger than its abstract suggests (e.g., it incidentally reports tool-layer bugs), or BenchGuard's taxonomy subsumes ours. *Mitigation:* full close-read of all five papers is scheduled Aug 21–22, before any code depends on framing; both variants of the related-work text drafted up front; the fallback contribution (benchmark-agnostic framework + mutation-validated detectors + agent-impact link) is orthogonal to any single audit's findings and is already the paper's spine, so a collision costs a paragraph, not the paper.

(Watched but not top-3: maintainers disputing semantics — "docstring was aspirational." The provenance rule plus verbatim quotation makes disputes reportable data, and disclosure at Sep 10 leaves 15 days to fold responses in.)

---

## 7. Model-effort allocation

| Tier | Work | Rationale |
|---|---|---|
| **High-capability (frontier), low volume** | Contract schema design; positioning/related-work analysis; anti-circularity protocol; pre-registered stats plan; review of every VIOLATES finding before freeze; intro/method prose | Small token counts, catastrophic if wrong; these are the reviewable surfaces |
| **Mid-tier, bulk** | Adapter implementation; drafting contract clauses from docstrings (every clause human/frontier-reviewed before headline inclusion); static-check rules; mutation site enumeration; LaTeX plumbing; results prose from generated tables | High volume, verifiable outputs — each artifact is checked by the deterministic pipeline or a review pass |
| **Cheapest-that-works** | The agent-under-test in the A/B experiment (it is a fixture, not an intelligence spend — fix one cheap model, temp/seeds pinned); any batch classification/formatting; disclosure email drafts | Correctness enforced downstream |
| **Zero LLM** | The entire measurement path: checker, harness, probes, mutation scoring, `render.py` | All headline numbers are deterministic code — cheap, offline-reproducible, and immune to judge-variance critiques (the exact failure mode 2607.02577 documents in others) |

Guiding rule: LLM inference appears nowhere in the evidence chain for any paper number. That is simultaneously the efficiency answer, the reproducibility answer, and a positioning point.
