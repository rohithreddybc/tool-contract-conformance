# Paper Outline + Evidence Map

Mode: `academic-paper` outline-only (Phase 0 → Phase 2; Phase 1 skipped, sources supplied from `GATE.md` and `REFERENCES.md`).
Generated 2026-08-21. Inputs: `ARCHITECTURE-FINAL.md`, `GATE.md`, `FINDINGS-VERIFIED.md`, `REFERENCES.md`, `CLAUDE.md`.

---

## Phase 0 — Paper Configuration Record

| Field | Value |
|---|---|
| Title (working) | Executable Tool-Contract Conformance Testing for Agentic Benchmarks |
| Paper type | Systems / measurement framework (CS-SE) |
| Venue | IEEE BigData 2026, Intelligent Data Mining special session |
| Deadline | 2026-09-27 (backstop: ML on Big Data, 2026-09-30) |
| Length | Up to 10 pages, IEEE two-column `conference` class |
| Authors | Rohith Reddy; Wenbin Zhang |
| Citation format | IEEE numeric |
| Output format | LaTeX (`.tex` + `.bib`), PDF via pdflatex |
| Abstract | **English only.** The skill default is bilingual zh-TW + EN; IEEE BigData is an English-only venue, so the zh-TW abstract is dropped. Change this if you want it for other reasons. |
| Target word count | ~8,200 words body + references, ≈ 1,000 words/page at IEEE two-column with 3 figures and 5 tables |
| Existing materials | Prior-work gate complete; 3 findings verified; no results yet |
| Mandatory inclusions | Data Availability, Ethics Declaration, CRediT Author Contributions, Conflict of Interest, Funding, AI-use statement, Limitations |

Correct any row before drafting begins; the outline below assumes these values.

---

## Title candidates

The working title names the machinery, which `GATE.md` §6 says is the losing framing. Three alternatives that name the target instead:

1. **Auditing the Instrument: Tool-Contract Conformance in Agentic Benchmarks** — leads with measurement validity.
2. **Scores at Risk: When Benchmark Tools Violate Their Own Advertised Semantics** — leads with the consequence; strongest for a Data Mining audience that cares about measurement quality.
3. **The Unaudited Layer: Executable Tool-Contract Conformance Testing for Agentic Benchmarks** — keeps the method term but subordinates it.

Recommend 2 with the method phrase in the subtitle. Decide before Section I is drafted, since the introduction's first paragraph inherits it.

---

## Section-by-section outline with page budget

Total 10.0 pages. Slack is held in §VII and §X, the two sections that shrink without losing the argument.

### I. Introduction — 1.0 pg

**Move 1 (territory).** Agentic benchmarks now decide which models ship. They score an agent by executing its tool calls against a simulated environment and reading the resulting state.

**Move 2 (gap).** That reading assumes the tool that wrote the state did what its interface said. No published benchmark audit tests that assumption. Prior audits examine tasks, instructions, gold solutions, graders and judges — every layer except the tool body.

**Move 3 (occupy).** We test the interface → implementation → state-transition contract directly, and we trace the consequence: which task verdicts depend on state a defective tool was responsible for producing.

**Opening example (do not bury this).** MedAgentBench's POST branch parses the agent's payload, discards it, and replies `"POST request accepted and executed successfully"`. Every write in a clinical-agent benchmark is a no-op that reports success. Three lines of quoted code in the introduction, cited to file and line.

**Contributions, in this order** — the order is load-bearing per `GATE.md` §6:
1. Score-at-risk dependency analysis: a per-benchmark bound on how many task verdicts depend on defective tool state.
2. Six executable defect classes over the state-transition contract; Phantom Effect, Partial Effect and Reset Leak have no counterpart in any surveyed taxonomy.
3. A provenance-bound contract format and a static + dynamic conformance checker.
4. Open-world-validated detection — precision and recall against both taxonomy-shaped and off-taxonomy injected defects.
5. Confirmed findings across N benchmarks, with coordinated disclosure and maintainer responses.

**Explicitly not claimed** (one sentence, prevents the incremental-contract-checker reading): we did not invent design by contract, contract inference, or benchmark auditing.

---

### II. Background and Related Work — 1.25 pg

**Figure 1 — the three-layer diagram.** Tool interface (docstring, schema, prompt text) / tool implementation + state transition / evaluator. Each prior work is drawn as a bracket over the layers it inspects. Ours is the only bracket over the middle layer. This figure does more positioning work than any paragraph and must be drafted first.

Four paragraphs, one per cluster:

| Cluster | Works | Disposal sentence source |
|---|---|---|
| Benchmark auditing | BenchGuard, ABA, SafeAudit | `GATE.md` §5 bullet 2 — all audit task artifacts; a tool returning success without acting is invisible because the artifacts they inspect are mutually consistent |
| Tool-calling evaluator validity | Tool-Veritas | `GATE.md` §5 bullet 1 — it audits whether the verdict matches the outcome; we audit whether the state the verdict reads was ever correctly written |
| Contracts for agent runtime | ToolGate, Agent Behavioral Contracts | `GATE.md` §5 bullet 3 — the contract is their trusted input and our object under test |
| Contract inference and API oracles (SE) | ConTract, IcePICK, AGORA+, jContractor, Jass, frame specs, Segura, RESTler | `GATE.md` §5 bullet 4 — same technique family, different SUT; in production a fault costs an outage, in a benchmark it costs a number nobody can tell is wrong |

**Opening move for §I, from the second literature sweep.** LiveClawBench (arXiv:2604.13072) independently names our symptom: agent-benchmark mocks "reduced to endpoint-level stubs that remove sessions, artifacts, state transitions, and downstream side effects." Open with that — the field has noticed that benchmark mocks discard state transitions, and nobody has measured which shipped benchmarks do it or what it costs their scores. Someone else stating the problem is worth more than any motivation we construct, and it pre-empts the reading that we went looking for a problem to find. It does not collide: LiveClawBench builds better mocks prospectively and audits nothing.

**Name-collision disposals. The full table is `GATE.md` §8 — do not duplicate it here; the two required in this section are:**

1. Tool-Veritas lists "implementation-specification mismatch" among LLM-judge failures; it appears once in its related-work section, denotes judges scoring final answers rather than verified tool use, is never defined as a failure class, and has no case study. Cite the location precisely — a reviewer who knows that paper will check.
2. The 34-fault agentic-AI taxonomy (arXiv:2603.06847) has a "Tool Invocation" category glossed as "violations of API contracts." Same shape of collision, same disposal: it classifies faults observed in deployed agent systems, where the contract is assumed correct and the *agent* violates it. We invert that — the tool violates its own contract, and the victim is the measurement rather than the task.

**Also required in §II or §X: the construct-validity survey.** A NeurIPS 2025 Datasets and Benchmarks survey of 445 benchmarks with 29 reviewers diagnoses construct-mapping failures across the field. Cite it to position our evidence as mechanistic and deterministic rather than another construct-mapping critique — the distinction that separates this paper from that literature, and the citation most worth getting right.

**Honest concession, one sentence.** The checking technique is not new. What is new is the target, the defect classes that target implies, and the demonstrated effect on published scores.

---

### III. The Benchmark Tool Layer as a Measurement Instrument — 1.0 pg

The conceptual core. Short, and it earns the rest of the paper.

- **Instrument framing.** A benchmark tool is not application code that happens to be simulated. It is the write path of a measuring device. A defect in it does not degrade a service; it corrupts a published number, silently and reproducibly.
- **Why the defect is invisible downstream.** Tool-Veritas's deterministic gates "inspect observable properties of the sandbox state." If the tool that wrote the state is defective, a gate reading that state inherits the defect and reports agreement. Consistency between a broken tool and a grader reading its output is not validity.
- **Defect taxonomy, Table I.** Six classes, each defined as a checker rule over `(pre, post, args, result)`, never as prose. Columns: class, operational definition, advertised surface it contradicts, field-observed or mutation-only.

| Class | Checker rule |
|---|---|
| Phantom Effect | success signal true ∧ effect delta absent |
| Unenforced Precondition | precondition predicate false ∧ (no error signal ∨ state mutated) |
| Ignored Argument | vary an effective argument across probes; **post-state** invariant to it |
| *(separate signal, not a class)* | **Result–state disagreement**: the result varies with an argument whose effect on state is absent. Reported as an aggravating signal on the finding it accompanies, never as a class of its own |
| Partial Effect | ≥1 effect predicate holds ∧ ≥1 fails on the same call |
| Invariant Break | environment invariant false after a legal call sequence |
| Reset Leak | snapshot after reset ≠ initial snapshot |

- **Why the Ignored Argument rule is state-only.** The first draft required post-state *and* result to be invariant to the argument. That conjunctive rule fails on Finding 6: `reserve_car_rental` discards `end_time` from state but interpolates it into the success string, so the result *does* vary and the rule would not fire — the checker as originally specified would have missed one of its own anchor findings, and precisely the case where the misreporting result is what makes the defect egregious. The rule is therefore state-only, and result–state disagreement is reported as a separate aggravating signal. The M-IGNARG mutation operator inherits this definition and must inject state-drop with and without result-echo variants.

- **Anchor honesty, one sentence** (`ARCHITECTURE-FINAL.md` §11.3). Field-observed: Phantom Effect, Unenforced Precondition, Partial Effect, and — as of the AgentDojo and MM-ToolSandbox audits — Ignored Argument, now the most common class in the set with four instances. **Invariant Break and Reset Leak remain mutation-only, with no field instance anywhere.** Say it here rather than let a reviewer count. Note the direction of travel: Ignored Argument was mutation-only until two benchmarks were added, which is the argument for breadth over depth in the remaining schedule.

---

### IV. Score-at-Risk Dependency Analysis — 1.25 pg

**The framework contribution. Give it a full section and a figure, not a subsection.**

Three steps, all static, no model in the loop:

1. **Defect → field.** From violated effect clauses, the state fields the tool should have written and did not.
2. **Field → evaluator.** Parse the benchmark's own evaluation code for the fields it reads. In tau2 this is the DB hash and per-task assertions; `evaluator_env.py` constructs fresh gold and predicted environments and compares resulting state, so tool defects propagate into the reward directly.
3. **Evaluator → tasks.** Enumerate tasks whose verdict depends on any field in the intersection.

**Figure 2** — the dependency graph for one worked tau2 example, from `cancel_reservation`'s unreleased seats through `available_seats` to the affected task set.

**Table II** — score-at-risk per benchmark: tasks at risk / total, by defect class, each row traceable to tool, clause and evaluator read site.

**The bound is a bound.** State plainly that at-risk is not the same as misgraded; §VIII demonstrates the bound is not vacuous on a sample. This sentence is the difference between a defensible claim and an overreach.

**Task-selection rule, defined here and only here.** A task is affected iff its reference solution invokes a tool with a confirmed VIOLATES clause. Exhaustive, no exclusions, committed by hash before any run. Selecting on observed traces is forbidden.

---

### V. Contract Specification — 1.25 pg

- **Format.** One YAML file per mutating tool, validated by `spec/schema.json`. Worked example: `cancel_reservation`, annotated, as Figure 3 or a code listing.
- **Clause kinds.** preconditions, effects (delta assertions), frame (what must not change), success_signal, on_precondition_violation, invariants, reset.
- **Advertised-surface enumeration** — the construct-validity mechanism, and the answer to a prior rejection. Closed list committed before authoring: `docstring`, `schema`, `prompt_template`, `tool_return`, `readme`, `external_standard`. Clauses grounded in none are `inferred: true` and excluded from headline counts.
- **The intent argument, one sentence.** Maintainer intent is irrelevant to the measurement claim. The agent is conditioned only on the interface; an aspirational docstring still corrupts the measurement because the agent believed it and the evaluator scored the resulting state.
- **Predicate language.** Restricted Python over `(pre, post, args, result)` on a whitelisted AST, with explicit binders and bounded comprehension. Concede in one sentence that this is a small DSL rather than claiming it is not.
- **Biconditional success is opt-in, not default,** with a cited justification. Show the checker correctly declining to flag tau2's `airline/tools.py:689` deferred-update path while still flagging `cancel_reservation`. A detector that knows when not to fire is the credibility argument.
- **Verdict lattice.** CONFORMS / VIOLATES (minimal witness) / UNTESTABLE (reason code). UNTESTABLE stays in every denominator.
- **Inter-annotator agreement.** Dual-annotated 20% clause sample, written adjudication protocol committed before annotation, agreement reported whatever it is.

---

### VI. Conformance Checker — 0.75 pg

Deliberately the shortest technical section. Length here signals the wrong contribution.

- Adapter interface: `list_tools`, `fresh_env`, `snapshot`, `invoke`, `reset`, `source`. Subprocess boundary over JSON — benchmarks disagree on Python version (MedAgentBench 3.9, tau2 ≥3.12).
- Static checks: constant-success returns, dead guards, arguments unused in body, unpaired state writes.
- Dynamic harness: snapshot → invoke → snapshot → evaluate clauses against fresh environments.
- Machine-readable report: `findings.jsonl` schema, one row per clause verdict with benchmark, pinned commit, tool, clause id, probe arguments, pre/post snapshots, source-line evidence. This is deliverable 6 and the reproducibility spine — every table in the paper is rendered from it by `report/render.py`.

---

### VII. Detector Validation — 1.25 pg

- **Closed-world arm.** Six AST operators, one per class, at programmatically enumerated sites in conformant tools. The three known-defective tools are excluded. `checker-freeze-v1` tag applied before mutant generation; ordering auditable from git history.
- **Open-world arm — the answer to the circularity objection.** A standard mutation tool (mutmut / cosmic-ray) whose operators know nothing of our taxonomy. Report **escape rate**: of surviving non-equivalent mutants, what fraction the checker misses. This measures whether six classes cover the defect space.
- **Contract-coverage metric.** Fraction of advertised-surface sentences operationalized; fraction of state-writing statements covered by some effect or frame clause. High recall with low coverage is a shallow-contract warning, reported rather than hidden.
- **Statistics.** Mutants within a tool share a contract and a style; they are not independent trials. Per-tool breakdowns, tool-clustered intervals, every recall claim stated at the Wilson lower bound. Never a bare point estimate.
- **Equivalent-mutant controls.** Semantics-preserving refactorings of advertised behavior — reordered independent writes, guard extracted to a helper, equivalent arithmetic. Not log-string or variable-name edits, which are undetectable by construction and prove nothing.
- **Wild precision.** Confirmed VIOLATES / all VIOLATES from the manual triage pass. Matters more than precision on mutants.
- **Baseline.** AGORA+ reports 80% precision on REST invariant detection; use it as the external reference point for the Invariant Break detector rather than reporting our number in a vacuum.

---

### VIII. Evaluation Impact — 1.0 pg

- **Tier 1, primary, no model in the evidence path.** Trajectory replay: record one agent trajectory per affected task, re-execute the identical action sequence against as-shipped and patched tools, show the benchmark's own evaluator scoring the two worlds differently, with pre/post diffs. Report exact counts of verdict flips with per-task evidence.
- **Divergence fallback.** Where a patch changes mid-trajectory observations, temp-0 with k=3 per condition, counting only flips stable across all replicates, with trajectory-prefix identity verified to the divergence point. Report how many tasks needed this.
- **Tier 2, descriptive only.** Per-task paired success-proportion deltas with exact binomial CIs. One plot. **No p-values anywhere in this section** — with ~15 tasks a significance test is decoration, and an underpowered NHST invites the exact critique this design exists to avoid.
- **Patch honesty.** tau2's two findings have genuine one-hunk patches (uncomment `telecom/tools.py:629-630`; add the seat release at `airline/tools.py:366`). MedAgentBench has none — `send_post_request` does not exist anywhere in the repository, so any patch is a reference implementation of the advertised write path, labeled as such, diffed in the appendix, with the caveat that we defined the counterfactual.

---

### IX. Findings and Coordinated Disclosure — 0.75 pg

- **Table III** — per benchmark: tools audited, mutating tools, independent implementations, unique defect classes. Not a raw bug count; eight bugs in one copied helper is one bug.
- Worked findings: the three verified, plus whatever the checker surfaces. Each with file, line, quoted code, and a clean-clone reproduction command.
- Disclosure timeline, maintainer responses, and — if silence — the fact of silence with the date sent. Non-response is reportable data.

---

### X. Threats to Validity — 0.5 pg

Four named threats, each with the mitigation already built in, not invented at writing time:

1. **Construct validity** — is a docstring clause the tool's advertised semantics? Advertised-surface enumeration, `inferred` exclusion, dual annotation, the intent argument.
2. **Detector circularity** — open-world escape rate, contract-coverage metric, held-out contracts authored independently.
3. **External validity** — N benchmarks is not the population; MedAgentBench contributes one mutating code path, not three tools, and cannot support cross-benchmark mutation transfer claims.
4. **Bound interpretation** — score-at-risk counts dependency, not confirmed misgrading.

---

### XI. Conclusion — 0.25 pg

Two paragraphs. What the instrument framing buys the field; what a benchmark maintainer should do differently on Monday.

---

### Back matter — 0.75 pg

References (IEEE numeric, ~35 entries), Data Availability (Zenodo DOI), Ethics, CRediT, Conflict of Interest, Funding, AI-use statement.

---

## Page budget summary

| § | Section | Pages |
|---|---|---|
| I | Introduction | 1.00 |
| II | Background and Related Work (Fig. 1) | 1.25 |
| III | Tool Layer as Measurement Instrument (Table I) | 1.00 |
| IV | Score-at-Risk Analysis (Fig. 2, Table II) | 1.25 |
| V | Contract Specification (Fig. 3) | 1.25 |
| VI | Conformance Checker | 0.75 |
| VII | Detector Validation (Table IV) | 1.25 |
| VIII | Evaluation Impact (Table V, Fig. 4) | 1.00 |
| IX | Findings and Disclosure (Table III) | 0.75 |
| X | Threats to Validity | 0.50 |
| XI | Conclusion | 0.25 |
| — | References and back matter | 0.75 |
| | **Total** | **10.00** |

Overflow order if the draft runs long: §VI to 0.5, §IX to 0.5, §III to 0.75. Do not cut §IV or §VII — they carry the contribution and the methodology defense respectively.

---

## Evidence map

Every claim, its evidence source, and its status. **Status `NONE` means the claim currently has no evidence and cannot be written until the named artifact exists.**

### Claims with evidence in hand

| # | Claim | Evidence | Status |
|---|---|---|---|
| C1 | MedAgentBench's POST branch discards the payload and reports success | `FINDINGS-VERIFIED.md` F1; `__init__.py:85-91` at `9926011`, quoted | VERIFIED |
| C2 | No FHIR write path exists in MedAgentBench | `git grep send_post_request` returns nothing; 7 `requests.post` hits all under `src/client/` | VERIFIED |
| C3 | tau2 `refuel_data` declares an Active-line precondition and does not enforce it | `FINDINGS-VERIFIED.md` F2; docstring `telecom/tools.py:613`, guard commented at `629-630`, mutation at `641`, charge at `643` | VERIFIED |
| C4 | tau2 `cancel_reservation` does not release seats booked by `book_reservation` | `FINDINGS-VERIFIED.md` F3; decrement at `airline/tools.py:315`, `logger.warning("Seats release not implemented...")` at `367` | VERIFIED |
| C5 | The maintainer acknowledges the same gap on flight change | `airline/tools.py:689` TODO, quoted | VERIFIED |
| C6 | No prior audit covers any of the six classes | `GATE.md` §2 — 14 BenchGuard + 3 ABA + 10 Tool-Veritas categories mapped, 0 of 6 | VERIFIED |
| C7 | "Implementation-specification mismatch" is an evaluator artifact, not a tool defect | `GATE.md` §2, single occurrence in Tool-Veritas §2 Related Work, undefined, no case study | VERIFIED |
| C8 | ToolGate treats the contract as trusted input | `GATE.md` §2; ToolGate abstract — precondition "gates tool invocation" | VERIFIED |
| C9 | Contract checking is not novel in SE | `REFERENCES.md` — ConTract DSN 2026, IcePICK ICST 2026, AGORA+ TOSEM 2025, jContractor 2005, Jass 2001 | VERIFIED |
| C10 | tau2 state is snapshotable and resettable in-process | `environment/db.py` — `load`, `model_dump`, `get_hash`; `toolkit.py:242` `get_db_hash` | VERIFIED |
| C11 | tau2's evaluator compares environment state between gold and predicted runs | `evaluator/evaluator_env.py:85,97` — fresh environments per comparison | VERIFIED |
| C12 | tau2 has 19 mutating tools across airline, retail and telecom | count by `mutates_state=True`, per `toolkit.py:64-90` | VERIFIED — recount and pin in the artifact before printing |
| C13 | MedAgentBench's three POST tool definitions share one code path | `data/medagentbench/funcs_v1.json` + the single branch at `__init__.py:85-91` | VERIFIED |

### Claims awaiting a generating artifact

Each placeholder carries the script that must produce it. The numbers-audit script checks every one of these against `paper/tables/` before any commit to `paper/`.

| ID | Claim slot | Generated by | Status |
|---|---|---|---|
| N1 | Tools audited, mutating tools, independent implementations, unique defect classes per benchmark (Table III) | `report/render.py` ← `findings.jsonl` | PENDING |
| N2 | Tasks at risk / total per benchmark, by defect class (Table II) | `analysis/score_at_risk.py` | PENDING |
| N3 | Closed-world recall per defect class with tool-clustered Wilson intervals (Table IV) | `mutation/score.py` | PENDING |
| N4 | Open-world escape rate on surviving non-equivalent mutants | `mutation/score.py` + mutmut run | PENDING |
| N5 | Contract-coverage metric per tool | `spec/coverage.py` — **not yet named in `ARCHITECTURE-FINAL.md` §1 file tree; add it** | PENDING |
| N6 | Wild precision: confirmed VIOLATES / all VIOLATES | manual triage, Sep 9-10 | PENDING |
| N7 | Inter-annotator agreement on the 20% predicate sample | annotation protocol, Phase 2 | PENDING |
| N8 | Verdict flips under trajectory replay, per task (Table V) | `experiments/ab_run.py` Tier 1 | PENDING |
| N9 | Tasks requiring the k=3 divergence fallback | `experiments/ab_run.py` | PENDING |
| N10 | Per-task paired success-proportion deltas with binomial CIs (Fig. 4) | `experiments/ab_run.py` Tier 2 | PENDING |
| N11 | Number of benchmarks audited (N in the abstract) | filled last, per `ARCHITECTURE-FINAL.md` §9 risk 3 | PENDING |
| N12 | Maintainer responses received | disclosure, from 2026-09-10 | PENDING |

### Claims with NO evidence source — resolve or delete

| # | Claim | Problem | Action |
|---|---|---|---|
| ~~X1~~ | ~~"MedAgentBench's published write-task scores are affected"~~ | **RESOLVED 2026-08-21.** `refsol.py` obtained and pinned at `repro/env/refsol.py`. Write graders never read server state — they reconstruct the write from the agent's transcript via `extract_posts`, gated on the fabricated `"POST request accepted"` string. See Finding 4. | Claim replaced: not "scores are affected" but "scores cannot detect the defect, and measure message shape rather than clinical effect." Stronger, and needs no agent runs |
| ~~X2~~ | ~~Finding 3 is a Reset Leak~~ | **RESOLVED 2026-08-21, negatively.** `batch.py:409` → `build_text_orchestrator` → `build_environment` (`build.py:393`) → `FlightDB.load(...)` per simulation. Fresh database from disk every task, so seat drift cannot cross tasks. | Label withdrawn. Finding 3 is Partial Effect only. Consequence: Reset Leak has **no field-observed instance** — Table I must mark it mutation-only |
| X3 | "N benchmarks audited", N ≥ 4 | Only tau2 is a confirmed dynamic environment. MedAgentBench is static-only. Benchmarks 3-4 are unstarted spikes. | Do not write N until after the Sep 6 kill gate. Draft the abstract with N as a token |
| ~~X4~~ | ~~BenchGuard is COLM 2026~~ | **RESOLVED 2026-08-21, TRUE.** Verified on the official COLM 2026 accepted-papers page — exact title and author match among 856 entries. Not yet Scopus-indexed; COLM proceedings lag. The other four (Tool-Veritas, ABA, ToolGate, SafeAudit) are confirmed **preprint-only** — 0 Scopus hits by title, no journal-ref on arXiv. | Cite BenchGuard as COLM 2026. Cite the other four as preprints, explicitly. Four corrections to already-printed rows landed in `REFERENCES.md` — see below |
| X5 | Cross-benchmark mutation transfer | MedAgentBench has no site for 5 of 6 operators — no guards, no argument-conditioned branching, no paired writes, no reset routine | Delete the transfer claim. Report cross-*domain* transfer within tau2, which is real |
| X6 | Our tau2 findings are new | The ABC checklist (arXiv:2507.02825) reports a defect in tau-bench. Theirs reads as a grading-script defect — empty responses counted as success — and ours are tool-implementation defects, but this has not been checked against their actual text | **Read their tau-bench finding before §VI is drafted.** If it overlaps either of ours, cite and defer rather than claim novelty. This is the one prior-work hit that touches our own evidence |
| X7 | Annotator B is independent | Not yet named | Settle before dual annotation begins. If B is the co-author, the paper writes "second annotator", never "independent" |
| X8 | At-risk counts are comparable across benchmarks | **They are not.** tau2 airline grades by whole-database hash, so 50/50 tasks are "at risk" by construction; tau2 telecom grades by per-task assertions and gives 1135/2285. The first number measures the evaluator's coarseness, the second measures the defect's reach | **Numbers-audit rule:** no at-risk figure may be printed without its basis tag (`whole_state_hash` / `collection_only` / `exact_field`). Never pool across bases. A whole-state-hash 100% is not a finding |
| X9 | Experiment frame ⊆ at-risk population | **False, proven mechanically.** `experiment_frame_subset_of_at_risk = False` for AgentDojo Finding 5 — argument-specific defects make the two frames overlap, not nest | §IV states them as overlapping populations answering different questions, and reports the intersection. See `REVIEW-RESPONSE.md` W6 |

---

## Immediate next actions, in order

1. **Download and read `refsol.py`** (X1). Everything MedAgentBench contributes to §IV and §VIII depends on the answer, and it is a manual browser download — the one step that cannot be automated from here.
2. **Verify tau2 reset scope** (X2). One afternoon; decides a taxonomy label.
3. **Draft Figure 1**, the three-layer diagram. It carries §II and forces the positioning to be concrete before any prose is written.
4. **Add `spec/coverage.py`** to the `ARCHITECTURE-FINAL.md` file tree (N5) — the metric is specified but has no named generator.
5. **Scopus venue-confirmation pass** on the five unconfirmed entries in `REFERENCES.md` (X4), before the bibliography is frozen.
