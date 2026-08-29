<!--
paper/main.md — working draft, IEEE BigData 2026 (Intelligent Data Mining special session).
Target: 10 pages IEEE two-column, references inside the limit, no appendix.
Complete draft, all ten sections plus abstract. Cut to fit the page limit on 2026-08-29
by relocating mechanism to the deposited artifact (see paper/latex/main.tex header comment
for the six relocations); no claim, number, limitation, or disposal was removed, only
its supporting mechanics. §VIII (formerly a standalone Evaluation Impact section) is now
folded into §VII as its closing paragraph; sections renumbered accordingly (old IX/X/XI
are now VIII/IX/X).
Placeholder convention: [Nk: generating script] per PAPER-OUTLINE.md evidence map.
Citation keys match REFERENCES.md; keys marked (*) in the reference list are not yet
logged there and must be added before the bibliography is frozen.
-->

# Scores at Risk: When Benchmark Tools Violate Their Own Advertised Semantics

**Subtitle:** Executable Tool-Contract Conformance Testing for Agentic Benchmarks

Rohith Reddy, Wenbin Zhang

---

## Abstract

Agentic benchmarks score an agent by executing tool calls against a simulated environment and reading the resulting state, assuming the tool did what its interface advertised. No published benchmark audit tests that assumption; existing audits inspect tasks, gold solutions, and graders, never the tool implementation. We author executable contracts from each tool's advertised surfaces (docstring, schema, prompt text, return value), check implementations and state transitions against those contracts with a static and dynamic checker, and trace which task verdicts depend on state a defective tool should have written. Across four benchmarks we confirm four headline-eligible tool-layer defect cells, from eight verified instances: three demonstrated dynamically and one, MedAgentBench's Phantom Effect, statically. Its write path is a no-op; no grader reads the record back, and where a write oracle exists at all it reconstructs the write from the agent's own transcript, gated on a success string the harness fabricates. Score-at-risk bounds are basis-tagged rather than pooled: an exact-field evaluator puts 1,135 of 2,285 telecom task verdicts at risk, while a coarser whole-database-hash basis puts all 50 airline tasks at risk by construction. Detection on the mutation arm is precise (≥0.867, zero false positives over 25 flags) but recall is weak at Wilson lower bounds on real tools; an open-world mutation arm gives an escape rate ≥0.956 on a toy domain and an undefined rate, zero live mutants, on tau2. A pre-registered trajectory-replay check on ten affected tasks exercises the defect zero times and records zero verdict flips.

<!-- COMMITTED SHAPE (source of record, PAPER-OUTLINE.md abstract rule) — retained after drafting, not a placeholder.
  - leads with the count that survives inspection: 4 HEADLINE-ELIGIBLE tool-layer cells
    across 4 benchmarks, counted from report/findings.jsonl, which is the artifact of record.
    Superseded twice: this block said 7 cells, then 5. AgentDojo's Phantom Effect cell went
    on 2026-08-26 because the biconditional re-tag never fires -- the fixture masks one half
    of the defect, so both halves are confirmed in separate calls but never simultaneously.
    A probe-and-fixture gap, reported as one; a fixture chosen to make it fire would be
    tuning the instrument to produce the result.
    Two of the seven cannot carry a headline — tau2's Partial Effect is maintainer_annotation
    grounded and excluded by our own tiering rule, and MedAgentBench's Ungrounded Oracle is an
    evaluator-layer property, not one of the six tool-layer classes. Both are reported, adjacent
    and labelled, never folded into the headline. 8 instances reported alongside.
    A 7 survives only until a reviewer asks which seven. See FINDINGS-VERIFIED.md;
  - states the MedAgentBench construct-validity result (write-path no-op + transcript-grounded
    grader; measured quantity is emitted-request well-formedness) — NEVER names NEJM AI here;
  - promises score-at-risk bounds with their basis tags [N2: analysis/score_at_risk.py];
  - promises validated detection (closed-world recall at Wilson lower bounds [N3: mutation/score.py],
    open-world escape rate [N4: mutation/score.py + cosmic-ray run]);
  - promises NO verdict flips (§VII may null by construction; null framing is pre-registered
    in experiments/analysis_plan.md);
  - benchmark count N filled last [N11: per ARCHITECTURE-FINAL.md §9 risk 3].
Two variants exist per REVIEW-RESPONSE.md Journal-Fit W2 (N=2 floor, N=4 target); the
Sep 6 kill gate outcome (cleared 2026-08-21: 8 instances across 4 environments, 4 of them
headline-eligible per report/findings.jsonl) selects the target variant.
DRAFTED 2026-08-29: N=4 target variant selected (kill gate cleared 8/4 on 2026-08-21).
Word count 245. Numbers sourced from report/findings.jsonl, report/score_at_risk.jsonl,
report/mutation_summary.md, report/ab_summary.md — see drafting notes for the per-number
citation. -->

**Keywords** — agentic benchmarks, tool calling, measurement validity, design by contract, conformance testing, data quality.

---

## I. Introduction

Agentic benchmarks now help decide which language models ship. A benchmark scores an agent by executing its tool calls against a simulated environment and reading the state those calls leave behind, on the assumption that each call changed the world the way the tool's interface said it would. That assumption is fragile: LiveClawBench names, as its own motivating problem, that agent-benchmark mocks are commonly "reduced to endpoint-level stubs that remove sessions, artifacts, state transitions, and downstream side effects" [liveclawbench26] — a prospective observation, offered as a reason to build higher-fidelity mocks for new benchmarks, not a measurement of which already-shipped benchmarks discard state transitions or what the loss costs their published scores.

The loss can be total. MedAgentBench [medagentbench25] evaluates language-model agents against a simulated electronic health record. Its harness handles every write request an agent emits in one branch of one function (`src/server/tasks/medagentbench/__init__.py`, lines 85–91 at commit `9926011`, abridged):

```python
elif r.startswith('POST'):
    try:
        payload = json.loads('\n'.join(r.split('\n')[1:]))
    ...
    else:
        session.inject({"role": "user", "content":
            "POST request accepted and executed successfully. ..."})
```

The payload is parsed into a local variable and never read again. No code anywhere in the repository performs the write: `git grep send_post_request` returns nothing at the pinned commit, and every `requests.post` call site lives in the client-side model transport [C1, C2 → `FINDINGS-VERIFIED.md`]. Every write action in this clinical-agent benchmark is a no-op that reports success to the agent.

No published benchmark audit can see this defect. Prior audits examine task instructions, gold solutions, evaluation scripts, environment configurations, graders, and judges [benchguard26], [aba26], [toolveritas26], [safeaudit26], but all of them stop at the layer above the tool body and treat its implementation as ground truth: a deterministic grader that inspects sandbox state inherits any defect in the tool that wrote it, and reports agreement anyway. None of them tests the contract that runs from a tool's interface, through its implementation, to the state transition it performs.

That untested contract is a data-quality problem of direct concern to this community. Benchmark scores are published measurement data that the field mines, aggregates into leaderboards, and consumes in model-selection and deployment decisions. A defect in the instrument that generates a score propagates into every downstream use of the number, and unlike noise it replicates perfectly: every rerun of a defective tool corrupts the measurement the same way. Auditing the process that generates this data is data-quality work in the most literal sense.

This paper tests the interface → implementation → state-transition contract directly: for each mutating tool in a benchmark, we author an executable contract from the tool's own advertised surfaces (docstring, schema, prompt text, return strings), check the implementation and its state transitions against it, and trace the consequence — which task verdicts depend on state a defective tool was responsible for producing. The contributions, in order of importance:

1. **Score-at-risk dependency analysis**: a static, per-benchmark bound on how many task verdicts depend on state a defective tool should have written, each row tagged with the evaluator basis that produced it (§IV).
2. **Six executable defect classes** over the state-transition contract, defined as checker rules rather than prose (§III). Phantom Effect, Partial Effect, and Reset Leak have no counterpart in any surveyed audit taxonomy.
3. **A provenance-bound contract format** in which every clause cites the advertised surface it operationalizes, and a static plus dynamic conformance checker (§V, §VI).
4. **Open-world-validated detection**: precision and recall reported against both taxonomy-shaped and off-taxonomy injected defects, under a pre-registered analysis plan (§VII).
5. **Confirmed findings**: four headline-eligible benchmark-class defect cells across four shipped benchmarks, from eight verified instances, each read directly at a pinned commit by someone other than whoever surfaced it, with coordinated disclosure to all maintainers (§VIII).

We did not invent design by contract, contract inference, or benchmark auditing, and claim none of them: §II concedes the checking technique and rests the paper's novelty on the target and the consequence for published scores.

One result shapes the whole argument. MedAgentBench's grader for write tasks reconstructs the write from the agent's own transcript, admitting evidence only when it is followed by the literal success string the harness fabricates, so the defective tool and the grader that should catch it are mutually consistent. Each layer looks correct when audited alone, which is why five prior audits, several of them applied to closely related artifacts, reported nothing (§II, §VIII).

---

## II. Background and Related Work

*[Figure 1 — three-layer diagram: tool interface (docstring, schema, prompt text) / tool implementation and state transition / evaluator. Each prior work drawn as a bracket over the layers it inspects; this work is the only bracket over the middle layer, and Finding 4 is drawn as the arc connecting the middle and evaluator layers. Draft this figure before revising this section; it carries the positioning.]*

**Every audit adjacent to this one stops one layer short, or points its contract the other way.** Three families examine only the artifacts above the tool body — task instructions, gold solutions, evaluation scripts, environment configurations — and treat the tool's implementation as ground truth; a fourth family applies contract vocabulary but keeps the contract itself as the trusted input and the agent as the system under test, the opposite direction from this paper. The table below disposes of each by name, with the two that share this project's own audited artifacts — the checklist that already names a tau-bench defect, and the construct-validity literature's genre of judgment call — given the fullest treatment, since a reviewer of either would ask first whether we duplicate it. The structural point is common to all of them: a tool that returns success without acting is invisible to an audit of task artifacts or of agent-side contracts, because the artifacts or contracts they inspect remain mutually consistent with each other.

**Table: prior work disposed of, by collision and disposition.**

| Work(s) | Claim or apparent collision | Disposal |
|---|---|---|
| BenchGuard [benchguard26], Automated Benchmark Audit [aba26], SafeAudit [safeaudit26] | Audit the four task artifacts (14 subcategories), a three-axis instruction/environment/evaluation schema, and safety-suite coverage, respectively | Zero overlap in 27 categories [C6 → `GATE.md` §2]; nearest miss, BenchGuard's INST-CONTRADICT, checks instruction against gold program, both task metadata, where ours requires reading the tool body |
| Tool-Veritas [toolveritas26] | Audits verdict-vs-outcome across four benchmark families, incl. tau2-bench Retail, via execution traces; coins "implementation-specification mismatch" | Audits whether the verdict matches the outcome; we audit whether the state the verdict reads was ever correctly written, so a gate reading a defective tool's output inherits the defect regardless. The mismatch term denotes LLM-judge scoring of final answers, never defined as a failure class, no case study — collision in the name only |
| ToolGate [toolgate26], Agent Behavioral Contracts [abc26], Contract2Tool [contract2tool26], ContractBench [contractbench26] | Contract vocabulary at the agent runtime, over preconditions/postconditions, runtime enforcement, tool selection, and observation-contract preservation | All four share one direction of trust — the contract is trusted input, the agent is under test — and we invert it, testing the contract against the implementation that advertises it |
| ToolFuzz [toolfuzz25] | Nearest engineering neighbor: tests whether production LangChain tools behave as their documentation promises | Oracle is agent-response correctness with documentation as ground truth; our object is a benchmark's own simulated tool, our observable the state transition, and the documentation is precisely what we do not trust — either side of a divergence may be the faulty one |
| ContractGuard [contractguard26] | "Forging a tool's effects" | An adversarial-security concern, an attacker defeating a permission gate, unrelated to the benign implementation divergence studied here |
| 34-fault agentic-AI taxonomy [faulttaxonomy26] | "Tool Invocation" category glossed as covering violations of API contracts, mined from deployed-framework issue trackers | Contract assumed correct, agent violates it; we study the inverse — the tool violates its own contract and the victim is the measurement rather than the task |
| Agentic Benchmark Checklist [abcchecklist25] | Reports τ-bench [taubench24] counts empty responses as successful — a grading-rubric defect — inside a January 2024–March 2025 collection window | tau2-bench [tau2bench25], the artifact we audit, released June 2025 after that window closed, with a different grading design (assertion functions and database checks, no substring matching in our domains); `git log -S` confirms the code carrying both our tau2-bench findings unchanged since the repository's first commit [`EXTERNAL-VERIFICATION.md` Task 1]. Different benchmark, codebase, and layer: theirs a ground-truth/rubric defect, ours tool-implementation defects |
| Construct-validity review [constructvalidity25] | 445 LLM benchmarks, 29 expert reviewers, pervasive failures to map test items onto capability constructs | Our evidence sits outside that genre of judgment call: a tool either honors its declared contract on a given call or it does not, the checker rule is executable, the witness a pair of state snapshots |

**Contract inference and API oracles.** The checking technique here is not new. Design by contract with runtime verification is decades old [jcontractor05], [jass01]; ConTract infers implicit API contracts over pointer state transitions, with 127 developer-confirmed inconsistencies [contract26]; IcePICK supplies a first-order executable contract language [icepick26]; AGORA+ detects REST invariants at 80% reported precision [agora25]. Frame specifications formalize what a call must not change [frames25]; contracts have been synthesized for stateful modules [cogent23] and studied for deep-learning APIs [dlcontract23]; our Ignored Argument and Partial Effect detectors are metamorphic relations in all but name [segura18], [segura16], [chen18], and stateful sequence exploration is established for REST APIs [restler19], [godefroid20]. None examines an agentic benchmark harness, and none of their fault models contain a success signal decoupled from state, an effect applied without its inverse, or state leaking across episodes. What distinguishes this work is the cost of a fault: in production it costs an outage; in a benchmark it costs a number nobody can tell is wrong.

**The published numbers this defect sits under.** MedAgentBench's paper reports "Action SR", the write-task success rate, for all 12 evaluated models in its Table 3 [medagentbench25]: it ranges 0.00% to 71.33%, best Gemini-1.5 Pro, two models at 0.00%. The abstract headlines 69.67% overall SR for Claude 3.5 Sonnet v2 — a weighted blend of Query SR and this same Action SR, so the number the authors foreground inherits the construct-validity problem for its write half. We cite the arXiv table, read directly; the same paper is published in NEJM AI (vol. 2, iss. 9), evidence these numbers reach a clinical audience. The file containing the POST branch of §I has been touched by exactly one commit (January 2025) and is unchanged at our pinned commit, so every Action SR value was produced under an implementation in which no write occurs. The paper's own §2.4.1 describes "rule-based sanity checks to verify the correctness of the payload of POST requests" — the transcript-reconstruction mechanism §VIII traces, gated on the fabricated success string. To be precise: the numbers are not wrong. They faithfully measure whether the agent emitted a well-formed POST request, not whether any clinical record changed, which is what "action success rate" is taken to mean by anyone reading a clinical-agent leaderboard.

**Why every prior audit missed it.** The tool defect (Finding 1) and the grader design (Finding 4) are mutually consistent: the grader's gate condition is the literal success string the harness injects at `__init__.py:91`, consumed by `extract_posts`, so the tool reports a write that did not happen and the grader accepts exactly that report as its evidence. Audited alone, each layer is coherent — the tool returns what it says it returns, and the grader correctly detects what it looks for. BenchGuard's EVAL-MISMATCH category and Tool-Veritas's reward-basis mismatch plausibly cover the grader-side class of this defect, yet neither audit found this instance: single-layer audits are blind to cross-layer consistency defects by construction, insufficient when the layers agree with each other about a world that does not exist. This mutual-consistency result, rather than the checker machinery, is the paper's central intellectual claim. We distinguish the evaluator-side property here, which §IV names Ungrounded Oracle, from Tool-Veritas's reward-basis mismatch and hallucinated-completion categories: those concern whether the verdict matches the outcome, ours the provenance of the oracle's evidence.

**tau2-bench's numbers.** The pinned commit we audit sits inside the code lineage that produced tau2-bench's own published per-domain pass^1 results and the numbers on the live public leaderboard linked from the repository's README, and both audited defects have been present, unpatched, across that entire span [tau2bench25], [`EXTERNAL-VERIFICATION.md` Task 2]. We claim no causal link from either defect to any specific published tau2 number here. Whether a task verdict depends on the affected state is exactly the question the score-at-risk analysis of §IV exists to answer, and asserting it from outside that analysis would overreach.

The honest summary of this section: the checking technique is mature SE, the audit target is unoccupied, and the field's own newest benchmark work names our symptom while auditing nothing [liveclawbench26]. What is new here is the target, the defect classes that target implies, the cross-layer blindness result, and the traced consequence for published scores.

---

## III. The Benchmark Tool Layer as a Measurement Instrument

A benchmark tool is not application code that happens to be simulated. It is the write path of a measuring device. When production software has a defective write path, a service degrades and someone files an issue. When a benchmark tool has one, a published number is corrupted silently and reproducibly, and the number keeps being cited either way. This section fixes the object under test, the defect classes, and the principle that separates a defect from a legitimate simplification.

**Why the defect is invisible downstream.** Every deterministic evaluator in the surveyed literature reads state that tools wrote — tau2-bench's own evaluator compares final database state between gold and predicted runs [C11] — so a defective tool's output is inherited by any gate reading it (§I, §II). Consistency between a broken tool and a grader reading its output is not validity; that is why the tool layer needs its own audit rather than better downstream checks.

**The defect taxonomy.** Table I defines six defect classes, each as an executable checker rule over the tuple `(pre, post, args, result)`: the canonical state snapshots before and after a call, the call's arguments, and its return value. The classes are typed at the tool boundary. Prose descriptions are glosses; the rule is the definition.

**Table I — Six executable defect classes.**

| Class | Checker rule (over `pre`, `post`, `args`, `result`) | Contradicted surface | Status |
|---|---|---|---|
| Phantom Effect | success signal true ∧ advertised effect delta absent | success signal, effects | field-observed |
| Unenforced Precondition | precondition predicate false ∧ (no error signal ∨ state mutated) | preconditions | field-observed |
| Ignored Argument | post-state invariant under variation of an argument advertised as effective | signature, effects | field-observed |
| Partial Effect | ≥1 advertised effect predicate holds ∧ ≥1 fails on the same call | effects, frame | field-observed |
| Invariant Break | environment invariant false after a legal call sequence | invariants | mutation-only |
| Reset Leak | snapshot after reset ≠ initial snapshot | reset | mutation-only |

Four of the six classes are field-observed in shipped benchmarks (§VIII). **Invariant Break and Reset Leak have no field-observed instance anywhere in our findings**: they exist only as injected mutants, and every count in §VII and §VIII keeps that distinction visible. We note the direction of travel rather than hide it: Ignored Argument was itself mutation-only until the third and fourth benchmarks were audited, and it is now the most common class in the finding set, with four instances. Breadth of audit, not depth on one artifact, is what converted it.

**Result–state disagreement is a signal, not a class.** The Ignored Argument rule is deliberately state-only. An earlier draft required both the post-state and the result to be invariant under the argument, and that conjunctive rule fails on a real case: AgentDojo's `reserve_car_rental` discards `end_time` from state but interpolates it into the success string, so the result varies with the argument and the conjunctive rule would never fire (§VIII, Finding 6) — missing one of the checker's own anchor findings, in precisely the case where the misreporting return message makes the defect worse. The rule is therefore state-only, and a result that varies with an argument whose effect on state is absent is reported as an aggravating signal on the finding it accompanies. The corresponding mutation operator inherits this definition and injects state-drop variants both with and without a result echo.

**The benign-simplification principle.** The strongest objection a maintainer can raise is that these are intentional simplifications of a simulation that never claimed fidelity. The answer is a criterion, stated once and applied uniformly:

> A simplification is benign exactly when it is advertised. The defect is never the simplification; it is the undisclosed divergence between what the interface tells the agent and what the implementation does.

Three consequences follow. First, tau2-bench's own maintainers already draw this line: at `airline/tools.py:689` they advertise a deferred flight-database update in the surface the behavior is visible from, and the checker correctly does not flag it, while at line 367 they merely log that seat release is not implemented, in a warning the agent never sees, and the checker flags it — the distinction between disclosed and undisclosed divergence is theirs before it is ours. Second, either side of a divergence may be repaired: a maintainer who fixes an aspirational docstring restores conformance exactly as completely as one who fixes the code, and §VIII counts such a response as a resolved finding, converting the audit from an accusation into a specification of what disclosure would make a simulation honest. Third, the advertised surface is the right baseline even against the position that a benchmark owes fidelity only to itself, because the agent's behavior is the measured quantity and is conditioned on the interface text: a divergence corrupts the measurement upstream of any oracle, and internal consistency between what the agent is told and what the grader rewards requires interface–implementation conformance.

**One evaluator-layer property, kept outside the taxonomy.** MedAgentBench's write graders exhibit a property we name Ungrounded Oracle: the evaluator's oracle for a state change reads the actor's claim rather than the state. It is field-observed and load-bearing in §II, but it is not a seventh class. The six classes are typed over `(pre, post, args, result)` at the tool boundary, while oracle grounding is typed over grader source code, a different object checked by a different procedure. §IV emits it as a per-task classification of the benchmark's evaluator rather than as a row in Table I.

---

## IV. Score-at-Risk Dependency Analysis

The paper's central deliverable is not a violation count but a trace: given a confirmed defect, which task verdicts could have been computed on state that defect corrupted. `analysis/score_at_risk.py` performs the trace as three static steps, no model anywhere in the pipeline, over the 1,208 rows written to `report/score_at_risk.jsonl`. A `--verify` flag re-derives every row from the same pinned inputs and diffs it against the file on disk, so the trace is checked before it is trusted, not merely reproducible in principle.

*[Figure 2 — the worked tau2 dependency graph: `cancel_reservation`'s `eff.seats_released` clause, the `post.flights.*.dates.*.available_seats` path it fails to restore, the whole-database hash that reads that path, and the 50 airline tasks the hash mechanism marks at risk by construction. Draft alongside the final Table II render.]*

**Step 1, defect to field.** From a contract's VIOLATES clause, the predicate's own compiled AST — never the predicate's source string — yields the state paths the tool should have written and did not, or wrote unconditionally when a precondition should have blocked the write. **Step 2, field to evaluator.** The benchmark's own evaluation code is parsed the same way, by AST rather than by pattern match, for the state paths it reads, and each read site is classified by provenance: does it read live simulator state, or does it read the agent's own transcript. **Step 3, evaluator to tasks.** Every task whose verdict depends on a field in the Step 1/Step 2 intersection is enumerated from the benchmark's own pinned task-definition file, exhaustively, with no exclusion.

**Every at-risk figure carries a basis tag, and the tags are never pooled.** tau2's airline domain grades `cancel_reservation` by comparing a full database hash between the gold and predicted runs (`toolkit.py:242-244`); any field a defective tool writes is, by construction, read by that mechanism, so all 50 airline tasks in the affected reward basis come back at risk. That is a measurement of the evaluator's coarseness, not of the defect's reach, and Table II tags it `whole_state_hash` rather than let it stand next to a sharper number. Telecom grades `refuel_data` through per-task assertion functions instead, and the intersection is exact: 1,135 of 2,285 tasks read a field the defective precondition lets through unconditionally, 1,120 of them on the specific written attribute (`exact_field`) and 15 more on the containing collection alone (`collection_only`). A single benchmark carries both bases on different tools, and no project-wide percentage is stated across them — only per-basis counts, each with its own denominator.

**Table II — score-at-risk by defect, with basis and grounding.**

| Benchmark : tool | Defect class | Basis | At risk / total | Experiment frame | Oracle grounding |
|---|---|---|---|---|---|
| tau2 airline : `cancel_reservation` | Partial Effect | whole_state_hash | 50 / 50 | 7 | state_grounded |
| tau2 telecom : `refuel_data` | Unenforced Precondition | exact_field (1120) + collection_only (15) | 1135 / 2285 | 1120 | state_grounded |
| AgentDojo banking : `update_scheduled_transaction` | Ignored Argument | exact_field | 1 / 16 | 4 | state_grounded |
| AgentDojo travel : `reserve_car_rental` | Ignored Argument | exact_field | 1 / 20 | 0 | mixed |
| MedAgentBench : post-write | Phantom Effect | transcript (not a state basis) | undefined | n/a | 60 transcript / 90 mixed / 150 no-oracle / 0 state (of 300) |
| MM-ToolSandbox : `venmo_social` | Ignored Argument | not computable | `not_computable_appworld_unreachable` | not computable | not computable |

**The bound is a bound, in one direction only.** At-risk is an over-approximation of misgrading via the state-dependency mechanism, and it holds only where the oracle is state-grounded. It says a task's verdict could have been computed wrong because its evaluator reads a field the defective tool controls; it does not say the verdict was wrong, and it says nothing about failure modes outside that mechanism. §VII checks whether the bound is vacuous on a drawn sample and finds that, on the trajectories it recorded, it is not exercised.

**Oracle grounding is a first-class output, not a footnote, because a naive field-intersection returns the wrong answer for MedAgentBench, in the wrong direction.** Its write graders reconstruct the intended write from the agent's own transcript, gated on the fabricated success string of Finding 1 (§I, §VIII). Field intersection alone cannot see this: the field the grader checks and the field the tool should have written share the same name, so a rule that only asks whether names match would call nearly every one of the 300 cases at risk — the opposite error from the naive zero a state-only reading might otherwise produce. The real classification is computed per grader function from whether it calls the transcript-reconstruction routine, the live-state routine, both, or neither: of 300 write-tagged cases, 60 are graded unconditionally from the transcript, 90 read live state only to gate whether a write is required and then grade the write itself from the transcript, 150 have no write oracle at all, and zero are graded by reading the write back from FHIR state. Score-at-risk is undefined for the 60 and indeterminate for the 90 — never zero, never inflated, a distinct verdict emitted by name: "oracle not state-grounded." The evaluator property is Ungrounded Oracle (§III); this classification is what makes it a result rather than an aside.

**The experiment frame overlaps the at-risk population; it does not nest inside it.** The natural expectation — that a stricter selection rule, a task whose own gold solution invokes the defective tool, is always a subset of the field-dependency population — is wrong: `experiment_frame_subset_of_at_risk` is computed, not asserted, and it is `False` for AgentDojo's Finding 5. `update_scheduled_transaction` is broken on every argument at falsy values — `amount` at `0`, `date`/`subject`/`recipient` at the empty string, `recurring` at `False` — but `recurring` is the one argument for which a falsy value is a legitimate advertised input, which is why it alone carries task risk here: four tasks' gold solutions call the tool but only to vary `amount` or `recipient`, so none of them lands in the at-risk set field dependency computes. The one task whose oracle does read `.recurring`, `UserTask6`, reaches that field through a different, non-defective tool, `schedule_transaction` — so it is at risk by the field-dependency rule and outside the experiment frame by the gold-invocation rule. Argument-specific defects make the two rules select different populations by construction: field dependency cannot see which argument path a task exercises, and gold-invocation cannot see which field the oracle reads. The relation is stated as overlap, never containment, and both populations are reported with their own denominators.

**MM-ToolSandbox reports what it can compute and nothing it cannot.** Step 1 identifies the `sort_by` field `venmo_social` drops (Finding 7). Steps 2 and 3 do not run: the AppWorld-tier scenarios that exercise this tool are graded inside the `appworld` package, which this project cannot clone. Table II's row reads `not_computable_appworld_unreachable`, not a zero and not an omission — a null population is data about what a static, offline audit can reach, not a claim that no task is at risk.

---

## V. The Contract Specification

A contract is one YAML document per mutating tool, validated against a committed JSON Schema (`spec/schema.json`). Its clause kinds mirror the contract the interface already makes informally: `preconditions`, `effects` (delta assertions), `frame` (what must not change), `success_signal`, `on_precondition_violation`, `invariants`, and `reset`. Every normative clause must cite its provenance: the file, line, and verbatim quote of the advertised surface it operationalizes, and the build fails if the quote has drifted from the pinned commit.

**Grounding tiers.** Which text counts as "advertised" is the construct-validity question, so the answer is a closed list committed before any contract was authored, with three tiers.

**Table: grounding tiers (schema `advertisedSurface`).**

| Tier | Surfaces | In headline counts | Meaning |
|---|---|---|---|
| Agent-visible | `docstring`, `schema`, `prompt_template`, `tool_return`, `readme`, `external_standard` | yes | the agent was conditioned on this text; a violation corrupts the measurement by §III's argument |
| Maintainer-annotated | `maintainer_annotation` | no, reported separately | the maintainer wrote the intended semantics into the code (a comment, a log line, a TODO) but no agent ever sees it |
| Inferred | none (`inferred: true`) | no, reported separately | we inferred the semantics; nobody wrote them anywhere |

The tiers reflect different epistemic objects: a maintainer's own comment above an unimplemented feature is stronger evidence of intended semantics than our inference, and weaker than text the agent read. Headline eligibility is derived from a clause's provenance, never hand-set, and enforced by a validator check added after our own flagship contract first grounded its decisive clause in a log line — the full check enumeration is in the artifact. Maintainer intent is otherwise irrelevant to the measurement claim: the agent is conditioned only on the interface, so an aspirational docstring corrupts the measurement exactly as a bug would, because the agent believed it and the evaluator scored the resulting state.

**The predicate language, verdict lattice, and a worked example.** Predicates are restricted Python over exactly four bindings (`pre`, `post`, `args`, `result`) on canonicalized JSON-shaped snapshots under a whitelisted AST, with a small path-pattern grammar for frame clauses; the full grammar, binder rules, and frame-path syntax are in the artifact (readers who know IcePICK's executable contract language [icepick26] will recognize the shape). Every clause check resolves to CONFORMS, VIOLATES with a minimal witness (probe arguments plus the pre/post snapshot pair), or UNTESTABLE with a reason code, and UNTESTABLE clauses stay in every reported denominator — an unresolvable path is a located authoring error, never a silent false. tau2-bench's `cancel_reservation` contract illustrates the tiers directly: one effect clause is grounded in the docstring the agent reads, the other only in the maintainer's own log line, and the latter — a real, corroborated violation — is not headline-eligible (§VIII).

**A detector that knows when not to fire.** Biconditional success (success signal ⟺ full advertised effect) is opt-in per contract and requires a provenance-cited justification, because two legitimate patterns would otherwise be misclassified. tau2's flight-change path advertises a deferred database update at `airline/tools.py:689` (§III), and the checker, given the `advertised_deferred` annotation, correctly declines to flag it while still flagging `cancel_reservation`. And tau2's airline policy prompt states outright that "The API does not check that cancellation rules are met", an agent-visible surface advertising non-enforcement, so the Unenforced Precondition detector must not fire on cancellation eligibility while still firing on `refuel_data`, whose docstring advertises a check the implementation comments out. Both true negatives are exercised in our test suite. A checker credible enough to indict a benchmark must first demonstrate restraint on the cases the benchmark discloses.

**Contract authoring is measured, not trusted.** Translating an advertised sentence into a predicate is a judgment call, so it is dual-annotated and the agreement is reported extensionally: both annotators' predicates are compiled and evaluated against a shared, pre-committed probe corpus, and agreement is counted at the verdict level per clause, with UNTESTABLE-versus-anything counted as disagreement. All clauses on finding-bearing tools are dual-annotated, plus a seeded random sample of at least 30% of the rest, and the two strata are reported separately because both annotators know the findings. The protocol was committed before annotation began (`experiments/annotation_protocol.md`); its headline question is whether any VIOLATES finding flips under the second annotator's contracts. Run across six tools (`experiments/agreement.py`, commit `eaf1bdd5`): the blind stratum agrees completely wherever a probe call succeeds — 98 of 98 comparisons across 16 mapped clause pairs. One finding flips: `reserve_car_rental`'s `arg.end_time` is VIOLATES under Annotator A and UNTESTABLE under B, because A's contract pins `start_time`/`end_time` to parseable ISO strings and B's does not, so every probe B's contract can build dies in `datetime.fromisoformat()` before reaching effect code; both annotators independently noted the underlying defect. `venmo_social`'s `arg.sort_by` is incomparable rather than agreeing, since B's contract never declares that argument. Demonstrability depends on the contract's own annotation, not on whether the defect exists. Both annotators are LLM-agent instances, not independent human raters; B authored its six contracts blind, with no access to existing contracts or findings.

---

## VI. The Conformance Checker

Checking an implementation against a stated contract is not new; we apply the technique, we do not extend it. The checker has a static half — five AST-only checks over unexecuted source text, each flagging a candidate site for a person to read rather than asserting a verdict — and a dynamic half, which produces verdicts: snapshot a fresh environment, invoke the tool, snapshot again, and evaluate every clause against the resulting `(pre, post, args, result)` tuple. Ignored Argument and Invariant Break run the same primitive across several calls instead of one. Four adapters (tau2-bench, AgentDojo, MM-ToolSandbox, and a synthetic toy domain) share one common interface and run as subprocesses; MedAgentBench has no adapter and is checked statically (§I), since nothing in its harness is callable or resettable outside its controller stack. Adapter mechanics and the subprocess boundary are in the artifact.

42 contracts are authored against these four adapters and pass all eight validator checks of §V with zero skips. UNTESTABLE stays in every denominator this paper reports — a deliberate anti-flattery commitment, not a corpus narrowed to whatever the checker happens to handle.

The checker did not arrive at that state complete, and all six classes now have real code paths only because a mutation-corpus sweep, run after `checker-freeze-v1`, said otherwise: Reset Leak and Invariant Break each had a defect class, an operator, and a schema field, but no code that ever produced their verdict; thirty-five shipped frame clauses were schema-valid but never evaluated; and a routing table left seventeen of nineteen tau2 contracts silently never dynamically exercised, though they validated and counted everywhere else. All four are fixed, and the checker was refrozen as `checker-freeze-v2` before any number in §VII was scored — one disclosed refreeze cycle rather than two. One expressiveness gap is left open rather than patched: the frame-path grammar cannot exclude a single key from a wildcard match (§IX).

Every dynamically checked clause verdict is one row of `report/findings.jsonl`, deliverable 6; MedAgentBench contributes zero rows, since both its findings are static and entered via `FINDINGS-VERIFIED.md` instead. Table III is rendered from both sources.

---

## VII. Detector Validation

The pre-registered plan fixes, before any mutant existed, what each arm can and cannot license (`experiments/detector_analysis_plan.md`, committed at tag `checker-freeze-v1`, commit `57b019d`). The closed-world arm asks whether the checker detects a defect of a class we authored; a good result licenses the sentence "the checker detects violations of the clauses we wrote," never "the checker detects tool-contract defects." The open-world arm asks whether the checker notices a defect nobody designed for its taxonomy; a good result licenses only a lower bound on the taxonomy's incompleteness, never a claim of coverage. Every rate below is stated at its Wilson lower bound with its denominator printed beside it, per §5 and §7 of the plan. Toy-domain numbers, from the domain the checker's own authors wrote with this taxonomy in mind, are reported for debugging and never enter a headline; the headline is real-tools recall only, drawn from tau2-bench, AgentDojo, and MM-ToolSandbox.

**Real-tools closed-world recall.**

| Operator | n drawn | detected | missed | untestable | error | Recall (Wilson LB) |
|---|---|---|---|---|---|---|
| M-PHANTOM | 7 | 5 | 0 | 0 | 2 | ≥0.359 |
| M-PRECOND | 7 | 1 | 6 | 0 | 0 | ≥0.020 |
| M-IGNARG | 21 | 4 | 12 | 1 | 4 | ≥0.066 |
| M-PARTIAL | 8 | 1 | 7 | 0 | 0 | ≥0.018 |
| M-INVAR | 8 | 0 | 8 | 0 | 0 | ≥0.000 |
| M-RESET | n/a | n/a | n/a | n/a | n/a | no data |

These bounds do not indict the taxonomy on their own. `experiments/decompose_closed_world_misses.py` traces the cause of all 33 real-tool misses: 29 `probe_corpus_unreachable` (the frozen corpus never drove the mutated path), 2 genuine `clause_gap`, 1 `probe_gap`, 1 `target_not_found` — only 2 of 33 misses are a taxonomy gap the checker itself owns; the per-operator sub-breakdown and the watchdog-timeout exchangeability question are in the artifact. M-INVAR's 0.000, decomposed by liveness screening only (`operators_liveness_only`) rather than the full three-way classifier, reads as "no probe ever reached a mutated invariant path," not "the checker cannot detect invariant breaks." M-RESET has no real-tool site to draw at all: no tool-implementation file in any of the three real benchmarks defines a state-restoring function, so the honest report is "no data," not a rate of zero. Biconditional success, the mechanism M-PHANTOM's detector depends on, is opt-in per contract, adopted on 18 of 19 tau2-bench, 1 of 7 AgentDojo, and 0 of 5 MM-ToolSandbox contracts; where not adopted, Phantom Effect cannot fire at all — a second, more visible reason M-PHANTOM's recall sits at 0.359 rather than higher.

**Precision.** Zero false positives across every flag the checker raised against an injected mutant in the closed-world arm, on a pooled toy-plus-real sample of 25 flags (TP=25, FP=0; 24 semantics-preserving controls scored alongside): precision ≥0.867 at the Wilson lower bound. This denominator is mutation-arm flags only; it says nothing about the field findings of §VIII, which were confirmed by direct source reading, not by this count. This is the strongest number in the section, and it licenses nothing about the recall figures above: a detector that never lies about what it does catch can still catch very little of what it should. For context, AGORA+ reports 80% precision on REST invariant detection [agora25]; this checker's pooled precision sits above that figure, on a design that structurally cannot false-positive against a clause it never wrote, an asymmetry the comparison does not correct for.

**Achieved N against pre-registered N.** Only M-PRECOND and M-IGNARG met the ~25-per-class target, counting real and toy sites together as the pre-registration's draw target does (the recall table above, by contrast, reports real-tool sites only, which is why its own n-drawn column reads 7 and 21 for these same two operators rather than 25). The rest are §8's no-reuse refreeze rule meeting a structurally small pool, not a scoring shortfall: M-PHANTOM admits one mutation site per tool, so 35 exist across the entire real-tool corpus and the first freeze had already drawn 25 of them, leaving 10 for the second; M-PARTIAL's pool of 36 left 11; M-INVAR and M-RESET, at pools of 10 and 5, had nothing left to draw and fell back to rescoring the first freeze's own sites against the second freeze's checker, the one documented exception to the no-reuse rule. The full per-operator pool table (full pool, v1 drew, v2 unused, v2 drew, against the pre-registered target) is in the artifact.

**One refreeze cycle.** The numbers above are scored under `checker-freeze-v2` (commit `5824376`), not the first freeze: a mutation sweep against `checker-freeze-v1` found four taxonomy claims the checker had been carrying as closed with no code behind them, detailed in §VI, and the checker was refrozen before any number here was scored.

**Open-world escape rate, toy.** cosmic-ray scored 368 mutations across 4,048 (mutation, tool) pairs; 229 were behaviourally live, and the checker missed a Wilson lower bound of 0.956 of them (point estimate 0.983), decomposed as 119 of 225 escapes tracing to a clause the taxonomy never wrote, 86 to a clause whose probes never drove the tool into the exposing state, and 20 to the checker crashing before evaluation. Only the mechanical declared-volatile-field adjudication rule ran in this automated pass — the interface-invisibility and second-annotator rules both need a human annotator and are documented in the artifact — which makes 0.956 conservative in the direction of overstating the checker's blindness. Per the committed framing, this is a lower bound on the taxonomy's incompleteness, not evidence against the closed-world numbers above.

**tau2-telecom produced no usable escape rate.** cosmic-ray scored 465 mutations across 2,325 (mutation, tool) pairs against the domain's five non-anchor tools, and zero were behaviourally live, so the escape-rate denominator is zero and this arm did not run to a conclusion. The cause is the probe corpus, not the detector: its recorded-real-call component has no artifact anywhere in the project, and the two components that do exist are type-generic placeholders that fail existence checks on tau2's entity-keyed tools and raise before any mutation could show (mechanism detail in the artifact). A zero denominator is not evidence of a well-covered taxonomy, and this arm is reported as an open question, not a result. A precompute cache built before `checker-freeze-v2` existed had already produced a v1 run on this same arm — 281 of 465 mutations scored, 33 behaviourally live, escape rate ≥0.325 — a more favorable number than v2's undefined rate, yet it is not reported as a result: the cache predated the v2 checker, so whether those 33 live mutants were genuine or artifacts of the stale cache is now unresolvable, and the run is disclosed rather than quietly dropped in the direction that would have flattered us to keep.

**Evaluation impact: a null, not a gap.** Two tau2-bench findings carry mechanically verified one-hunk patches: cancelling a reservation leaves `seats_after` at 0 unpatched and restores it to 3 patched; refuelling a suspended line succeeds unpatched and raises `ValueError` patched. Ten trajectories replayed from each finding's own gold reference solution (five per finding, seed 1, zero discarded for infrastructure failure) all land in a single outcome cell: at risk, not exercised — zero trajectories trip either finding's trigger predicate, and zero verdicts flip. For F3 (airline `cancel_reservation`), no flip was possible by construction: the evaluator compares gold-run state against agent-run state, and both sides execute the identical, still-defective tool, so the symmetric-oracle structure absorbs the defect regardless of the exercise rate. For F2 (telecom `refuel_data`), a flip was possible in principle and did not occur, because none of the five sampled gold trajectories calls the tool on an inactive line. Per the pre-registered interpretation (`experiments/analysis_plan.md`), this is a finding about conditional validity, not a null result: the score is correct today because no agent happens to take the broken path, and nothing in the benchmark prevents one from doing so. N=5 per finding is provisional — F3's affected population of 7 tasks makes it near-exhaustive, F2's population of 1,120 does not (§IX) — so the null cannot separate a defect latent under every gold trajectory from one an undersized sample simply missed. The experiment design, the full per-finding outcome-cell table, and the evaluator-basis exercise/flip breakdown are in the deposited artifact.

---

## VIII. Findings and Coordinated Disclosure

Across four shipped benchmarks, the ledger's twelve VIOLATES clause rows collapse to eight confirmed finding instances, which fall into seven benchmark-class cells, of which **four are headline-eligible**. The compressed count leads deliberately: this project's reporting rule counts unique defect classes per benchmark, because eight bugs in one copied helper are one bug, and a reviewer will compress the count this way whether or not we do. We compress it three times, because three of the seven cells cannot carry a headline on our own rules. tau2-bench's Partial Effect is grounded in a `logger.warning` the agent never sees, which makes it maintainer-annotated rather than agent-visible. MedAgentBench's Ungrounded Oracle is a property of the evaluator, not one of the six tool-layer classes. AgentDojo's Phantom Effect cell is real in the contract but unconfirmed in practice: the biconditional re-tag on `update_scheduled_transaction` fires only when both the `recurring` and `amount` effects violate on the same call, and the banking fixture never does that, so it never fires. Confirming it would mean choosing a fixture built to make it fire, which is tuning the instrument to produce the result. All three are reported here in full, labelled, and excluded from the headline. Four of the eight instances are Ignored Argument. Every finding was verified by direct source reading at a pinned commit by someone other than whoever first surfaced it, and each carries a clean-clone reproduction command in the artifact. Per-benchmark totals (tools audited, mutating tools, independent implementations, unique defect classes) appear in Table III [N1: report/render.py ← findings.jsonl].

**Table: confirmed findings (instance level), with quoted evidence.**

| # | Benchmark @ commit | Tool : line | Class | Tier | Quoted evidence and disposition |
|---|---|---|---|---|---|
| 1 | MedAgentBench @ `9926011` | POST branch, `__init__.py:85-91` | Phantom Effect | agent-visible (`prompt_template`, `tool_return`) | Fabricated return: "POST request accepted and executed successfully"; payload parsed, never re-read. Chain continues below. |
| 2 | tau2-bench @ `c3398666` | `refuel_data`, `telecom/tools.py:607-657` | Unenforced Precondition | agent-visible (`docstring`) | Docstring: "Line status must be Active." Check present in source, commented out; sibling `gb_amount` check survives — a selective, not absent, omission. |
| 3 | tau2-bench @ `c3398666` | `cancel_reservation`, `airline/tools.py:315, 363-368` | Partial Effect | **maintainer-annotated: not headline-eligible** | Log line: "Seats release not implemented for cancellation!!!" (367), TODO at 689. Seats never restored; reset confirmed per-episode, so drift does not cross tasks (Reset Leak label withdrawn). |
| 4 | MedAgentBench @ `9926011` | write graders, `refsol.py` (SHA-256-pinned; not in repo) | Ungrounded Oracle (evaluator property, §III) | grader source | Gate string "POST request accepted" consumed by `extract_posts`; 60/300 cases graded unconditionally from transcript, 90 more gate on live state but still grade from transcript. |
| 5 | AgentDojo @ `089ed46` | `update_scheduled_transaction`, `banking_client.py:115-151` | Ignored Argument + Phantom Effect | agent-visible (`docstring`) | `recurring: bool \| None` behind a truthiness guard: settable `True`, never `False`. Returns "Transaction ... updated." unconditionally. Sibling `update_user_info` repeats the guard on four string fields without the phantom signal — same class, Finding 5's count, not a ninth instance. |
| 6 | AgentDojo @ `089ed46` | `reserve_car_rental`, `travel_booking_client.py:382-400` | Ignored Argument | agent-visible (`docstring`) | `end_time` discarded from state but interpolated into the success message (the aggravating signal of §III). No shipped task's ground truth exercises this tool — excluded from any score-impact claim. |
| 7 | MM-ToolSandbox @ `1e8e932` | `venmo_social`, `mini/venmo.py:464-470` | Ignored Argument | agent-visible (`docstring`) | `sort_by` documented twice in the docstring, never forwarded in the comment-listing branch; the correct forwarding pattern appears 250 lines above in the same file. |
| 8 | AgentDojo @ `089ed46` | `invite_user_to_slack`, `slack.py:93-103` | Ignored Argument | agent-visible (`docstring`) | Docstring: invite "should be sent" to `user_email`; body never reads the mandatory parameter. Surfaced by the static checker's full-repository scan before a human confirmed it. |

A third tau2-bench candidate stays below the reporting threshold: `suspend_line`'s `arg.reason` VIOLATES in the ledger at the inferred tier — a required `reason` is logged and never persisted, but whether the docstring advertises persistence rather than a log entry is contested — unadjudicated, listed in the artifact, not counted among the eight.

**MedAgentBench (Findings 1 and 4) is the paper's central chain.** Finding 1 is the no-op POST branch quoted in §I. Finding 4 is what makes it undetectable from inside the benchmark: the grading module reconstructs each write from the conversation transcript, admitting evidence only when followed by the fabricated success string of Finding 1 (§II) — no grader ever issues a FHIR read to verify the write. Patching the tool to perform real writes would change no score, because no grader observes the state a patch would repair, and that is why §VII attempts no A/B experiment on this benchmark.

Two classes recur across the other three benchmarks: an interface tells the agent a call has an effect, and the implementation either drops it silently (Ignored Argument, five of eight instances) or reports success regardless (Phantom Effect, stacked on Finding 5). Both are cross-layer in the same sense as Findings 1 and 4 — a single-layer read of the tool or the interface alone finds nothing wrong, because each layer is internally consistent with itself.

All four benchmarks are cited at the specific commits audited [medagentbench25], [tau2bench25], [agentdojo24], [mmtoolsandbox26]. Instance-level evidence, including verbatim quotes and line numbers for every claim above, is in the findings ledger and reproducible from clean clones with the commands shipped in the artifact.

**Coordinated disclosure.** We disclose all findings to the four maintainer teams on 2026-09-10, seventeen days before submission, with per-finding reproduction commands and proposed repairs. Under §III's principle, a repair to either side of a divergence resolves a finding, and a documentation fix counts exactly as a code fix does. Maintainer responses, and for any team that does not respond, the fact and date of non-response, are reported here: [N12: disclosure log, from 2026-09-10].

---

## IX. Threats to Validity

**The taxonomy is not the space of possible defects, and the open-world arm measures the gap rather than closing it.** §VII's open-world arm on the toy domain found the checker missing a Wilson lower bound of 0.956 of behaviourally live mutants, decomposed there into unwritten-clause, unreached-state, and checker-crash causes. Six classes, even perfectly detected on the defects they name, would still miss most of what an operator with no knowledge of this taxonomy can break — the paper's own limitation, stated in its own numbers, not inferred from outside them.

**The equivalent real-benchmark run produced no usable number at all, and the absence is reported rather than hidden** (§VII). cosmic-ray's 465 mutations against tau2-telecom's five non-anchor tools yielded zero behaviourally live mutants, so the escape-rate denominator is zero; the cause is the probe corpus, not the checker. The same missing artifact — no production caller ever supplies a recorded real call — also explains the `reserve_car_rental` agreement flip (§V) and 29 of §VII's 33 real-tool misses, which makes a recorded-real-calls corpus this project's single highest-value piece of future work rather than a generic limitation.

**Sample sizes fall short of the pre-registration for four of six mutation operators, and the shortfall is structural, not a scoring choice.** §VII's achieved-N table shows only M-PRECOND and M-IGNARG meeting the ~25-real-tool-site target; the rest exhausted a structurally small corpus under §8's no-reuse refreeze rule, not a scoring shortfall. Achieved N is reported beside the pre-registered target in every case, never silently absorbed into a rate.

**M-RESET has no real-tool site at all** (§VII): reset logic lives in the adapter layer, which reconstructs environments wholesale rather than repairing them in place, so only the synthetic toy domain colocates reset with its tools for the operator to enumerate. The honest report is "no data," not a recall of zero, and Reset Leak's field-observed count anywhere in this project's findings is zero.

**The subprocess boundary absorbs exceptions the checker never sees, and whether that matters is unverified.** A real bug on the toy domain during the closed-world v2 run showed the mechanism directly: an adapter's `invoke()` caught only its own declared error type, so a probe built to violate a deleted guard drove the tool past the missing check into code that assumed the check held, and the resulting raw exception aborted the mutant instead of registering as a violation. Toy is a debug domain and never enters the headline, but the same subprocess boundary sits between the checker and every real adapter, and it swallows arbitrary exceptions before the harness can classify them. Whether an absorbed crash on a real tool would score as a detected violation or a silent non-detection has not been checked, which bounds what every real-tools recall number in §VII means — a bound left unresolved rather than argued away.

**The agent-experiment sample is provisional at N=5 per finding** (§VII), **and a null at that size proves less than it looks like it proves.** F3's affected population of 7 tasks makes 5 close to exhaustive; F2's population of 1,120 does not, so zero of ten trajectories exercising either trigger predicate cannot separate a defect latent under every gold trajectory from one an undersized sample simply missed.

**Benchmark selection is anchor-driven, not a sample of a population.** tau2-bench and MedAgentBench entered this study because their defects were already known before the four-benchmark protocol existed; AgentDojo and MM-ToolSandbox were added afterward to test whether the taxonomy generalized beyond the two anchors. No prevalence claim — what fraction of shipped benchmarks carry a given defect class, or how common Ignored Argument is across agentic benchmarks generally — is supportable from four benchmarks chosen this way. The four findings sets are existence proofs that the defect classes occur in shipped, audited artifacts, not a survey of how often they occur.

**The frame-path grammar cannot express one of its own most natural clauses.** `spec/GRAMMAR-GAPS.md` records that no wildcard segment can exclude a single key, so a frame clause meaning "no other reservation is modified" cannot be written without also colliding with the tool's own advertised effect on the one reservation it is supposed to change. The shipped `cancel_reservation` contract substitutes a weaker, fully expressible claim about an unrelated collection, and the distance between the two is a real coverage hole in the frame mechanism, named here rather than hidden behind a narrower example.

**Repository history cannot support every ordering claim this paper might like to make.** `git init` ran on 2026-08-21, after most of the design work already existed, and the first commit imported the project as a single tree. A squashed import cannot demonstrate that any pre-registration preceded the design decisions it was meant to freeze, and the paper does not claim that it does. What remains verifiable is narrower, and it is what the paper actually relies on: `checker-freeze-v1` predates the first scored mutant, and `experiments/analysis_plan.md` predates the first recorded trajectory, both checkable from commits made after the import. The distinction is stated here rather than left for a reviewer to discover (`PROVENANCE.md`).

**One refreeze cycle is disclosed rather than folded into the final numbers.** §VI details the four taxonomy claims a mutation sweep against `checker-freeze-v1` found uncoded, all fixed before `checker-freeze-v2` scored any number in §VII. A framework that reports the sweep that found its own holes earns more trust than one presented as complete from the start, and the cost of finding them — one refreeze cycle rather than zero — is stated plainly rather than absorbed into the total.

---

## X. Conclusion

This paper tested a layer no published benchmark audit reaches: the tool implementation that produces the state a grader reads. Four benchmarks yielded eight verified instances across six executable defect classes, four of them headline-eligible under a grounding rule that excludes what no agent ever saw. The score-at-risk analysis traced what those defects could have cost in published verdicts, tagged by evaluator basis rather than pooled into one number, and the open-world arm measured how much of the defect space six classes still miss. None of this establishes how common these defects are across agentic benchmarks generally: four anchor-driven audits are existence proofs, not a survey, and the paper does not claim otherwise. Benchmark scores are published measurement data that the field mines and reuses in leaderboards and model-selection decisions, and an instrument defect at this layer propagates into every downstream use of the number it produced. Run a conformance checker like this one in continuous integration, against the tool layer specifically, not only against tasks and gold solutions; state every deliberate simplification on the surface an agent actually reads — a docstring, a schema, a returned string — because an undisclosed one is indistinguishable from a bug, both to the agent conditioned on it and to the grader scoring the result; and never let a grader's success condition be satisfied by a string the harness itself fabricates, the single pattern that let a construct-validity failure survive five prior audits in the most clinically consequential benchmark in this study. A benchmark's published numbers are only as trustworthy as the layer nobody has been checking.

---

## References

<!-- IEEE numeric on conversion; keys match REFERENCES.md except (*) entries, which must be
added to REFERENCES.md before the bibliography is frozen. Venue statuses below are as
confirmed in REFERENCES.md on 2026-08-21/22. -->

- [liveclawbench26] (*) LiveClawBench: Benchmarking LLM Agents on Complex, Real-World Assistant Tasks. arXiv:2604.13072, 2026. Preprint.
- [medagentbench25] Jiang et al. MedAgentBench: A Realistic Virtual EHR Environment to Benchmark Medical LLM Agents. arXiv:2501.14654 (v2 2025-02-12); also NEJM AI 2(9), 2025, DOI 10.1056/AIdbp2500144. Table 3 cited from the arXiv version, read directly.
- [tau2bench25] Barres, Dong, Ray, Si, Narasimhan. τ²-Bench: Evaluating Conversational Agents in a Dual-Control Environment. arXiv:2506.07982, 2025. Preprint.
- [taubench24] Yao, Shinn, Razavi, Narasimhan. τ-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains. arXiv:2406.12045, 2024. Preprint.
- [agentdojo24] (*) Debenedetti et al. AgentDojo: A Dynamic Environment to Evaluate Attacks and Defenses for LLM Agents. arXiv:2406.13352, 2024. DOI 10.48550/arxiv.2406.13352. Verified via Consensus 2026-08-23; venue confirmation (NeurIPS 2024 D&B track) pending Scopus/publisher check.
- [mmtoolsandbox26] (*) Ma et al. MM-ToolSandBox: A Unified Framework for Evaluating Visual Tool-Calling Agents. arXiv:2607.11818, 2026. DOI 10.48550/arxiv.2607.11818. Verified via Consensus 2026-08-23; preprint.
- [benchguard26] Tu, Wang, Lu, Huang, Qu, Mostafavi. BenchGuard: Who Guards the Benchmarks? Automated Auditing of LLM Agent Benchmarks. COLM 2026 (confirmed on the official accepted-papers page). arXiv:2604.24955.
- [aba26] Wang, Bianchi, Zhu, Nie, Kwon, Dhingra, Zou. Automated Benchmark Auditing for AI Agents and Large Language Models. arXiv:2605.26079, 2026. Preprint.
- [toolveritas26] Bhat, Vaghasiya, Mohsin, Aali. Benchmarking the Benchmarks: A Validity Audit of Tool-Calling Evaluation. arXiv:2607.02577, 2026. Preprint.
- [safeaudit26] Chen, Yan, Zhang, Zhang. Who Tests the Testers? Systematic Enumeration and Coverage Audit of LLM Agent Tool Call Safety. arXiv:2603.18245, 2026. Preprint.
- [toolgate26] Liu et al. ToolGate: Contract-Grounded and Verified Tool Execution for LLMs. arXiv:2601.04688, 2026. Preprint.
- [abc26] Bhardwaj. Agent Behavioral Contracts: Formal Specification and Runtime Enforcement for Reliable Autonomous AI Agents. Zenodo, DOI 10.5281/zenodo.18775393, 2026. Preprint.
- [contract2tool26] (*) Contract2Tool: Learning Preconditions and Effects for Reliable Tool-Augmented LLM Agents. arXiv:2606.07904, 2026. Preprint.
- [contractbench26] (*) ContractBench: Can LLM Agents Preserve Observation Contracts? arXiv:2605.17281, 2026. Preprint.
- [toolfuzz25] (*) ToolFuzz — Automated Agent Tool Testing. arXiv:2503.04479, 2025. Preprint.
- [contractguard26] (*) The Gate Is Only as Honest as Its Contracts: ContractGuard for the Contract Layer of Risk-Aware Causal Gating. arXiv:2606.18550, 2026. Preprint.
- [faulttaxonomy26] (*) Characterizing Faults in Agentic AI: A Taxonomy of Types, Symptoms, and Root Causes. arXiv:2603.06847, 2026. Preprint.
- [abcchecklist25] (*) Establishing Best Practices for Building Rigorous Agentic Benchmarks. arXiv:2507.02825 (v5), 2025. Preprint.
- [constructvalidity25] (*) Measuring what Matters: Construct Validity in Large Language Model Benchmarks. NeurIPS 2025 Datasets & Benchmarks Track. arXiv:2511.04703.
- [contract26] Deng, Ma, Gao, Sun. Efficient Bug Detection by Inferring Implicit API Contract of Pointer State Transition. IEEE DSN 2026. DOI 10.1109/dsn69566.2026.00035. Scopus-confirmed.
- [icepick26] Ribeiro, Mamede, Ferreira. Systematic API Testing Through Model Checking and Executable Contracts. IEEE ICST 2026. DOI 10.1109/icst69053.2026.00060. Scopus-confirmed.
- [agora25] Alonso, Ernst, Segura, Ruiz-Cortés. Test Oracle Generation for REST APIs. ACM TOSEM 35(1), 2025. DOI 10.1145/3726524. Scopus-confirmed.
- [jcontractor05] Karaorman, Abercrombie. jContractor: Introducing Design-by-Contract to Java Using Reflective Bytecode Instrumentation. Formal Methods in System Design 27(3), 2005. DOI 10.1007/s10703-005-3400-1.
- [jass01] Bartetzko, Fischer, Möller, Wehrheim. Jass — Java with Assertions. ENTCS 55(2), 2001. DOI 10.1016/s1571-0661(04)00247-6.
- [frames25] Cheon et al. Enhancing Design-by-Contract with Frame Specifications. ICSOFT 2025, SCITEPRESS. DOI 10.5220/0013578400003964.
- [dlcontract23] Ahmed, Cruz, Imtiaz, Khairunnesa, Rajan. Design by Contract for Deep Learning APIs. ESEC/FSE 2023. DOI 10.1145/3611643.3616247.
- [cogent23] Ghosal, Jonsson, Rümmer. An Active Learning Approach to Synthesizing Program Contracts. LNCS 14323, 2023. DOI 10.1007/978-3-031-47115-5_8.
- [segura18] Segura, Parejo, Troya, Ruiz-Cortés. Metamorphic Testing of RESTful Web APIs. IEEE TSE 44(11), 2018. DOI 10.1109/tse.2017.2764464.
- [segura16] Segura, Fraser, Sanchez, Ruiz-Cortés. A Survey on Metamorphic Testing. IEEE TSE 42(9), 2016. DOI 10.1109/tse.2016.2532875.
- [chen18] Chen et al. Metamorphic Testing: A Review of Challenges and Opportunities. ACM Computing Surveys 51(1), 2019. DOI 10.1145/3143561.
- [restler19] Atlidakis, Godefroid, Polishchuk. RESTler: Stateful REST API Fuzzing. ICSE 2019. DOI 10.1109/icse.2019.00083.
- [godefroid20] Godefroid, Lehmann, Polishchuk. Differential Regression Testing for REST APIs. ISSTA 2020. DOI 10.1145/3395363.3397374.

<!--
Back matter (Data Availability with Zenodo DOI, funding/acknowledgment line if any):
deferred. EXTERNAL-VERIFICATION.md Task 3 found no CFP requirement for CRediT / ethics /
data-availability statements; recheck the CyberChair submission portal's required fields
at submission time before adding or omitting them.

DRAFT METADATA (skill: academic-paper, Phase 4, sections I/II/III/V/IX only)
| Section | Outline budget (pg) | Words drafted | ~Pages @ ~1000 w/pg + floats |
|---|---|---|---|
| I   | 1.00 | ~950  | ~1.0 |
| II  | 1.25 | ~1400 | ~1.4 (trim pass due; Fig. 1 not yet placed) |
| III | 1.00 | ~1050 | ~1.05 incl. Table I |
| V   | 0.90 | ~1000 | ~1.0 incl. tier table + listing (trim pass due) |
| IX  | 0.75 | ~1000 | ~1.0 incl. findings table (over budget; see report) |
Em dashes: 0. Binary-contrast constructions: 2 (both mandated: the benign-simplification
principle; "the numbers are not wrong"). No p-values, no significance language.
-->
