<!--
paper/main.md — working draft, IEEE BigData 2026 (Intelligent Data Mining special session).
Target: 10 pages IEEE two-column, references inside the limit, no appendix.
Drafted sections: I, II, III, V, IX. Sections IV, VI, VII, VIII, X, XI are stubs that
name the artifact that must generate their content; do not draft them by hand.
Placeholder convention: [Nk: generating script] per PAPER-OUTLINE.md evidence map.
Citation keys match REFERENCES.md; keys marked (*) in the reference list are not yet
logged there and must be added before the bibliography is frozen.
-->

# Scores at Risk: When Benchmark Tools Violate Their Own Advertised Semantics

**Subtitle:** Executable Tool-Contract Conformance Testing for Agentic Benchmarks

Rohith Reddy, Wenbin Zhang

---

## Abstract

<!-- PLACEHOLDER — drafted last, after report/render.py tables exist.
Committed shape (PAPER-OUTLINE.md, abstract rule):
  - leads with the compressed count: 7 unique benchmark-class cells across 4 benchmarks,
    8 instances reported alongside;
  - states the MedAgentBench construct-validity result (write-path no-op + transcript-grounded
    grader; measured quantity is emitted-request well-formedness) — NEVER names NEJM AI here;
  - promises score-at-risk bounds with their basis tags [N2: analysis/score_at_risk.py];
  - promises validated detection (closed-world recall at Wilson lower bounds [N3: mutation/score.py],
    open-world escape rate [N4: mutation/score.py + cosmic-ray run]);
  - promises NO verdict flips (§VIII may null by construction; null framing is pre-registered
    in experiments/analysis_plan.md);
  - benchmark count N filled last [N11: per ARCHITECTURE-FINAL.md §9 risk 3].
Two variants exist per REVIEW-RESPONSE.md Journal-Fit W2 (N=2 floor, N=4 target); the
Sep 6 kill gate outcome (cleared 2026-08-21: 8 findings across 4 environments) selects the target variant. -->

**Keywords** — agentic benchmarks, tool calling, measurement validity, design by contract, conformance testing, data quality. <!-- finalize with abstract -->

---

## I. Introduction

Agentic benchmarks now help decide which language models ship. A benchmark scores an agent by executing its tool calls against a simulated environment and reading the state those calls leave behind. The simulation is load-bearing: every verdict rests on the assumption that a tool call changed the world the way the tool's interface said it would. The field has begun to notice that this assumption is fragile. LiveClawBench names, as its own motivating problem, that agent-benchmark mocks are commonly "reduced to endpoint-level stubs that remove sessions, artifacts, state transitions, and downstream side effects" [liveclawbench26]. That observation was made prospectively, as a reason to build higher-fidelity mocks for new benchmarks. Nobody has measured which already-shipped benchmarks discard state transitions, or what the loss costs their published scores.

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

No published benchmark audit can see this defect. Prior audits examine task instructions, gold solutions, evaluation scripts, environment configurations, graders, and judges [benchguard26], [aba26], [toolveritas26], [safeaudit26]. All of them stop at the layer above the tool body, and all of them treat the tool implementation as ground truth. A deterministic grader that inspects sandbox state inherits any defect in the tool that wrote that state, and reports agreement. The contract that runs from a tool's interface, through its implementation, to the state transition it performs is tested by none of them.

That untested contract is a data-quality problem of direct concern to this community. Benchmark scores are published measurement data: the field mines them, aggregates them into leaderboards, and consumes them in model-selection and deployment decisions. A defect in the instrument that generates a score propagates into every downstream use of the number, and unlike noise it replicates perfectly, because every rerun of a defective tool corrupts the measurement in exactly the same way. Auditing the process that generates this data is data quality work in the most literal sense.

This paper tests the interface → implementation → state-transition contract directly. For each mutating tool in a benchmark we author an executable contract from the tool's own advertised surfaces (docstring, schema, prompt text, return strings), check the implementation and its state transitions against that contract, and then trace the consequence: which task verdicts depend on state a defective tool was responsible for producing. The contributions, in order of importance:

1. **Score-at-risk dependency analysis**: a static, per-benchmark bound on how many task verdicts depend on state a defective tool should have written, each row tagged with the evaluator basis that produced it (§IV).
2. **Six executable defect classes** over the state-transition contract, defined as checker rules rather than prose (§III). Phantom Effect, Partial Effect, and Reset Leak have no counterpart in any surveyed audit taxonomy.
3. **A provenance-bound contract format** in which every clause cites the advertised surface it operationalizes, and a static plus dynamic conformance checker (§V, §VI).
4. **Open-world-validated detection**: precision and recall reported against both taxonomy-shaped and off-taxonomy injected defects, under a pre-registered analysis plan (§VII).
5. **Confirmed findings**: seven unique benchmark-class defect cells across four shipped benchmarks, eight instances, verified by direct source reading at pinned commits, with coordinated disclosure to all maintainers (§IX).

We did not invent design by contract, contract inference, or benchmark auditing, and we claim none of them. §II concedes the checking technique and rests the paper's novelty on the target and on the consequence for published scores.

One result deserves a preview because it shapes the whole argument. MedAgentBench's grader for write tasks reconstructs the write from the agent's own transcript, admitting evidence only when it is followed by the literal success string the harness fabricates. The defective tool and the grader that should catch it are mutually consistent. Each layer looks correct when audited alone, which is why five prior audits, several of them applied to closely related artifacts, reported nothing (§II, §IX).

---

## II. Background and Related Work

*[Figure 1 — three-layer diagram: tool interface (docstring, schema, prompt text) / tool implementation and state transition / evaluator. Each prior work drawn as a bracket over the layers it inspects; this work is the only bracket over the middle layer, and Finding 4 is drawn as the arc connecting the middle and evaluator layers. Draft this figure before revising this section; it carries the positioning.]*

**Benchmark auditing.** BenchGuard audits the four artifacts that define a task: instructions, ground-truth reference solutions, evaluation scripts, and environment configurations, across 14 defect subcategories [benchguard26]. The Automated Benchmark Audit framework works the same territory with a three-axis schema over instructions, environments, and evaluation [aba26], and SafeAudit meta-audits the coverage of safety test suites [safeaudit26]. Mapping our six defect classes against their categories yields zero overlap in 27 categories [C6 → `GATE.md` §2]. The nearest miss, BenchGuard's INST-CONTRADICT, checks instruction against gold program, both task metadata, where ours requires reading the tool body. The structural point is common to all three: a tool that returns success without acting is invisible to an audit of task artifacts, because the artifacts they inspect remain mutually consistent.

**Tool-calling evaluator validity.** Tool-Veritas audits whether benchmark verdicts match true task outcomes across four benchmark families, including tau2-bench Retail, through execution traces, evaluator outputs, and final verdicts [toolveritas26]. Its deterministic gates "inspect observable properties of the sandbox state", which is exactly the trust relation we test: it audits whether the verdict matches the outcome, while we audit whether the state the verdict reads was ever correctly written. A gate reading state produced by a defective tool inherits the defect. One of its terms requires explicit disposal: "implementation-specification mismatch" appears once in that paper, in its Section 2 related work, where it denotes LLM judges scoring final answers rather than verified tool use. It is an evaluator artifact, never defined as a failure class, and carries no case study. The collision is in the name only.

**Contracts at the agent runtime.** ToolGate specifies each tool as a Hoare-style contract whose precondition gates invocation and whose postcondition gates commitment [toolgate26]. Agent Behavioral Contracts formalizes runtime enforcement on the agent side [abc26], Contract2Tool learns preconditions and effects to help agents select tools [contract2tool26], and ContractBench asks whether agents preserve observation contracts across a pipeline [contractbench26]. All four share one direction of trust: the contract is the trusted input and the agent is the system under test. We invert the relation and test the contract against the implementation that advertises it. ToolFuzz is the nearest engineering neighbor: it tests whether production LangChain tools behave as their documentation promises, using agent-response correctness as the oracle and the documentation as ground truth [toolfuzz25]. Our object is a benchmark's own simulated tool, our observable is the state transition rather than the response, and the documentation is precisely what we do not trust. Either side of a divergence may be the faulty one. ContractGuard's "forging a tool's effects" is an adversarial-security concern, an attacker defeating a permission gate, unrelated to the benign implementation divergence studied here [contractguard26]. A recent 34-fault taxonomy of agentic-AI failures includes a "Tool Invocation" category glossed as covering violations of API contracts [faulttaxonomy26]. It is mined from issue trackers of deployed agent frameworks, where the contract is assumed correct and the agent violates it. We study the inverse case, where the tool violates its own contract and the victim is the measurement rather than the task.

**Contract inference and API oracles.** The checking technique in this paper is not new, and we do not claim it is. Design by contract with runtime verification is decades old [jcontractor05], [jass01], and its modern line runs directly through our method: ConTract infers implicit API contracts over pointer state transitions and checks implementations against them, with 127 developer-confirmed inconsistencies [contract26]. IcePICK closes the oracle gap with a first-order executable contract language for API specifications [icepick26], and AGORA+ detects invariants over REST request/response pairs at 80% reported precision [agora25]. Frame specifications formalize what a call must not change [frames25], contracts have been synthesized for stateful modules [cogent23] and studied for deep-learning APIs [dlcontract23], and our Ignored Argument and Partial Effect detectors are metamorphic relations in all but name [segura18], [segura16], [chen18], with stateful sequence exploration long established for REST APIs [restler19], [godefroid20]. What distinguishes this work is the system under test and the cost model of a fault. In production software a contract violation costs an outage or a bug report. In a benchmark the same violation costs a number in a published table that nobody can tell is wrong. None of the works above examine an agentic benchmark harness, and the defect classes that matter there (a success signal decoupled from any state change, an effect applied without its inverse, state leaking across episodes) do not appear in their fault models.

**The audit that touched a related artifact.** The Agentic Benchmark Checklist reports that τ-bench counts empty responses as successful, a grading-rubric defect: some tasks ship empty ground truth, and the substring-matching evaluator is gameable [abcchecklist25]. That audit examined the original tau-bench [taubench24] inside its stated collection window of January 2024 to March 2025. tau2-bench [tau2bench25], the artifact we audit, was first released in June 2025, after that window closed, with a different grading design (assertion functions and database checks, no substring matching in the domains we audit), and `git log -S` confirms the code carrying both of our tau2-bench findings has existed unchanged since that repository's first commit [`EXTERNAL-VERIFICATION.md` Task 1]. Different benchmark, different codebase, different layer: theirs is a ground-truth and rubric defect, ours are tool-implementation defects. No prior audit, including this one, overlaps our findings.

**Construct validity.** A recent systematic review of 445 LLM benchmarks by 29 expert reviewers diagnoses pervasive failures to map test items onto well-defined capability constructs [constructvalidity25]. Our evidence sits deliberately outside that genre of judgment call: a tool either honors its declared contract on a given call or it does not, the checker rule is executable, and the witness is a pair of state snapshots. Where that literature argues about what a benchmark measures, we demonstrate mechanically that one thing a benchmark measures is not the thing its own interface declares.

**The published numbers this defect sits under.** MedAgentBench's paper reports "Action SR", the success rate on the 150 write tasks, for all 11 evaluated models in its Table 3 [medagentbench25]. Action SR ranges 0.00% to 71.33% across the 11 evaluated models: the best is Gemini-1.5 Pro at 71.33%, and two models score 0.00%. The paper's own abstract goes further and headlines 69.67% overall SR for Claude 3.5 Sonnet v2; overall SR is a weighted blend of Query SR and this same Action SR, so the number the benchmark authors chose to foreground inherits the construct-validity problem for its write half. We cite the arXiv table, which we read directly. The same paper is published in NEJM AI (vol. 2, iss. 9), which is evidence that these numbers reach a clinical audience. The file containing the POST branch of §I has been touched by exactly one commit in its history (January 2025) and is unchanged at our pinned commit, so every one of those Action SR values was produced under an implementation in which no write occurs. The paper's own §2.4.1 describes "rule-based sanity checks to verify the correctness of the payload of POST requests", which is the transcript-reconstruction mechanism we trace in §IX: the grader recovers the intended write from the agent's message text, gated on the fabricated success string. To be precise about what this means: the numbers are not wrong. They faithfully measure whether the agent emitted a well-formed POST request. What they do not measure is whether any clinical record changed, which is what "action success rate" is taken to mean by anyone reading a clinical-agent leaderboard.

**Why every prior audit missed it.** The tool defect (Finding 1) and the grader design (Finding 4) are mutually consistent. The grader's gate condition is the literal success string the harness injects at `__init__.py:91`, consumed by `extract_posts` in the grading module. The tool reports a write that did not happen, and the grader accepts exactly that report as its evidence. Audited alone, each layer is coherent: the tool returns what it says it returns, and the grader correctly detects what it looks for. BenchGuard's EVAL-MISMATCH category and Tool-Veritas's reward-basis mismatch plausibly cover the grader-side class of this defect, yet neither audit found this instance, and the reason is structural rather than accidental: single-layer audits are blind to cross-layer consistency defects by construction. Checking each layer separately is insufficient when the layers agree with each other about a world that does not exist. This mutual-consistency result, rather than the checker machinery, is the paper's central intellectual claim. We distinguish the evaluator-side property involved here, which §IV names Ungrounded Oracle, from Tool-Veritas's reward-basis mismatch and hallucinated-completion categories: those concern whether the verdict matches the outcome, while ours concerns the provenance of the oracle's evidence. A grader reading the agent's transcript can be perfectly consistent with everything it observes and still be measuring the wrong thing.

**tau2-bench's numbers.** The pinned commit we audit sits inside the code lineage that produced tau2-bench's own published per-domain pass^1 results and the numbers on the live public leaderboard linked from the repository's README, and both audited defects have been present, unpatched, across that entire span [tau2bench25], [`EXTERNAL-VERIFICATION.md` Task 2]. We claim no causal link from either defect to any specific published tau2 number here. Whether a task verdict depends on the affected state is exactly the question the score-at-risk analysis of §IV exists to answer, and asserting it from outside that analysis would overreach.

The honest summary of this section: the checking technique is mature SE, the audit target is unoccupied, and the field's own newest benchmark work names our symptom while auditing nothing [liveclawbench26]. What is new here is the target, the defect classes that target implies, the cross-layer blindness result, and the traced consequence for published scores.

---

## III. The Benchmark Tool Layer as a Measurement Instrument

A benchmark tool is not application code that happens to be simulated. It is the write path of a measuring device. When production software has a defective write path, a service degrades and someone files an issue. When a benchmark tool has one, a published number is corrupted silently and reproducibly, and the number keeps being cited either way. This section fixes the object under test, the defect classes, and the principle that separates a defect from a legitimate simplification.

**Why the defect is invisible downstream.** Every deterministic evaluator in the surveyed literature reads state that tools wrote. Tool-Veritas's gates "inspect observable properties of the sandbox state" [toolveritas26], and tau2-bench's evaluator compares final database state between gold and predicted runs [C11]. If the tool that wrote the state is defective, a gate reading that state inherits the defect and reports agreement. Consistency between a broken tool and a grader reading its output is not validity. This is why the tool layer needs its own audit rather than better downstream checks.

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

Four of the six classes are field-observed in shipped benchmarks (§IX). **Invariant Break and Reset Leak have no field-observed instance anywhere in our findings.** They exist in this paper only as injected mutants, and every count in §VII and §IX keeps that distinction visible. We note the direction of travel rather than hide it: Ignored Argument was itself mutation-only until the third and fourth benchmarks were audited, and it is now the most common class in the finding set, with four instances. Breadth of audit, not depth on one artifact, is what converted it.

**Result–state disagreement is a signal, not a class.** The Ignored Argument rule is deliberately state-only. An earlier draft required both the post-state and the result to be invariant under the argument, and that conjunctive rule fails on a real case: AgentDojo's `reserve_car_rental` discards `end_time` from state but interpolates it into the success string, so the result varies with the argument and the conjunctive rule would never fire (§IX, Finding 6). The checker as first specified would have missed one of its own anchor findings, in precisely the case where the misreporting return message makes the defect worse. The rule is therefore state-only, and a result that varies with an argument whose effect on state is absent is reported as an aggravating signal on the finding it accompanies. The corresponding mutation operator inherits this definition and injects state-drop variants both with and without a result echo.

**The benign-simplification principle.** The strongest objection a maintainer can raise is that these are intentional simplifications of a simulation that never claimed fidelity. The answer is a criterion, stated once and applied uniformly:

> A simplification is benign exactly when it is advertised. The defect is never the simplification; it is the undisclosed divergence between what the interface tells the agent and what the implementation does.

Three consequences follow. First, tau2-bench's own maintainers already draw this line. At `airline/tools.py:689` they advertise a deferred flight-database update in the surface the behavior is visible from, and the checker correctly does not flag it. At line 367 they merely log that seat release is not implemented, in a warning the agent never sees, and the checker flags it. The distinction between disclosed and undisclosed divergence is theirs before it is ours. Second, either side of a divergence may be repaired. A maintainer who replies that the docstring was aspirational and fixes the docstring has restored conformance exactly as completely as one who fixes the code, and §IX counts such a response as a resolved finding. This converts the audit from an accusation into a specification of what disclosure would make a simulation honest. Third, the advertised surface is the right baseline even against the position that a benchmark is a formal game owing fidelity only to itself, because the agent's behavior is the measured quantity and that behavior is conditioned on the interface text. A divergence corrupts the measurement upstream of any oracle, whether or not a grader reads the affected field. And internal consistency between what the agent is told and what the grader rewards itself requires interface–implementation conformance.

**One evaluator-layer property, kept outside the taxonomy.** MedAgentBench's write graders exhibit a property we name Ungrounded Oracle: the evaluator's oracle for a state change reads the actor's claim rather than the state. It is field-observed and it is load-bearing in §II, but it is not a seventh class. The six classes are typed over `(pre, post, args, result)` at the tool boundary, while oracle grounding is typed over grader source code, a different object checked by a different procedure. §IV emits it as a per-task classification of the benchmark's evaluator rather than as a row in Table I.

---

## IV. Score-at-Risk Dependency Analysis

*[NOT YET DRAFTED. Content generated by `analysis/score_at_risk.py` → [N2: analysis/score_at_risk.py]. Must include: the three-step static analysis (defect → field → evaluator → tasks); the per-task oracle-grounding classification (state_grounded / transcript_grounded / mixed) that replaces a zero or hundred-percent field intersection for MedAgentBench (REVIEW-RESPONSE.md W2); basis tags on every at-risk figure (whole_state_hash / collection_only / exact_field), never pooled (X8); the experiment-frame relation stated as overlapping populations, not nested, with the mechanical counterexample from AgentDojo Finding 5 (W6); the bound-not-misgrading sentence; the task-selection rule (reference solution invokes a tool with a confirmed VIOLATES clause, committed by hash before any run); Figure 2 (worked tau2 dependency graph); Table II.]*

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

The tiers exist because the two lower ranks are different epistemic objects: a maintainer's own `# Release seats` comment above an unimplemented release is materially stronger evidence of intended semantics than our inference, and materially weaker than text the agent read. Headline eligibility is derived by the report generator from a clause's provenance, never hand-set, and a validator check enforces the boundary mechanically: a `tool_return` quote must occur in a `return` expression or a raised exception's message, never in a `logger.*` call. That check exists because the first draft of our own flagship contract grounded its decisive clause in a log line, exactly the error the mechanism is for.

Maintainer intent is irrelevant to the measurement claim, and one sentence disposes of it: the agent is conditioned only on what the interface tells it, so an aspirational docstring corrupts the measurement anyway, because the agent believed it and the evaluator scored the resulting state.

**The predicate language.** Predicates are restricted Python over exactly four bindings, `pre`, `post`, `args`, `result`, evaluated on canonicalized JSON-shaped snapshots under a whitelisted AST: literals, path access, comparisons, boolean and restricted arithmetic operators, a fixed set of pure builtins, and comprehensions with mandatory explicit binders. A free name, a non-whitelisted node, or a path that does not resolve is a located authoring error, and an unresolvable path makes the clause UNTESTABLE rather than silently false. Frame clauses use a small path-pattern grammar (`*`, `[]`, `**`) over the same snapshots. This is a small DSL, and we say so plainly rather than pretend otherwise. Readers who know IcePICK's executable contract language [icepick26] will recognize the shape. What we claim for it is narrow: it is reviewable by eye, executes without a parser we must defend, and is expressive enough for all six defect classes.

**Worked example.** The contract for tau2-bench's `cancel_reservation` (excerpt; the authoritative copy is `spec/contracts/tau2/cancel_reservation.yaml`):

```yaml
effects:
  - id: eff.status_cancelled
    text: "the reservation is marked cancelled"
    predicate: "post.reservations[args.reservation_id].status == 'cancelled'"
    provenance: {surface: docstring, line: 342, quote: "Cancel the whole reservation"}
  - id: eff.seats_released
    text: "cancelling releases the seats the booking reserved"
    predicate: >
      all(post.flights[f.flight_number].dates[f.date].available_seats[...]
          == pre.flights[...].available_seats[...] + len(...passengers)
          for f in pre.reservations[args.reservation_id].flights)
    provenance: {surface: maintainer_annotation, line: 367,
                 quote: "Seats release not implemented for cancellation!!!"}
```

The two effect clauses sit in different tiers. `eff.status_cancelled` is grounded in the docstring the agent reads. `eff.seats_released` is grounded only in the maintainer's own log line: a search of every agent-visible surface in the domain, including the tool docstring and the agent's policy prompt, found no statement that cancellation returns seats to inventory. The violation is real and corroborated by two maintainer annotations, and it is not headline-eligible, which §IX states rather than argues around.

**A detector that knows when not to fire.** Biconditional success (success signal ⟺ full advertised effect) is opt-in per contract and requires a provenance-cited justification, because two legitimate patterns would otherwise be misclassified. tau2's flight-change path advertises a deferred database update in a maintainer-visible deferral annotation at `airline/tools.py:689`, and the checker, given the `advertised_deferred` annotation, correctly declines to flag it while still flagging `cancel_reservation`. And tau2's airline policy prompt states outright that "The API does not check that cancellation rules are met", an agent-visible surface advertising non-enforcement, so the Unenforced Precondition detector must not fire on cancellation eligibility while still firing on `refuel_data`, whose docstring advertises a check the implementation comments out. Both true negatives are exercised in our test suite. A checker credible enough to indict a benchmark must first demonstrate restraint on the cases the benchmark discloses.

**Verdict lattice.** Every clause check resolves to CONFORMS, VIOLATES with a minimal witness (probe arguments plus the pre/post snapshot pair), or UNTESTABLE with a reason code. UNTESTABLE clauses stay in every reported denominator.

**Contract authoring is measured, not trusted.** Translating an advertised sentence into a predicate is a judgment call, so it is dual-annotated and the agreement is reported extensionally: both annotators' predicates are compiled and evaluated against a shared, pre-committed probe corpus, and agreement is counted at the verdict level per clause, with UNTESTABLE-versus-anything counted as disagreement. All clauses on finding-bearing tools are dual-annotated, plus a seeded random sample of at least 30% of the rest, and the two strata are reported separately because both annotators know the findings. The protocol, including the clause segmentation rule, the adjudication procedure, and the annotator checklist, was committed before annotation began (`experiments/annotation_protocol.md`). The headline robustness question it answers is whether any VIOLATES finding flips under the second annotator's contracts. Agreement results: [N7: experiments/annotation_protocol.md protocol run]. The paper will state whether the second annotator is the co-author, and will not describe them as independent if so.

---

## VI. The Conformance Checker

*[NOT YET DRAFTED — deliberately the shortest technical section (~0.5 pg per the 2026-08-21 cuts). Content from `core/`, `adapters/`, `static_check/checks.py`, and the dynamic harness, drafted at `checker-freeze-v1`. Covers: adapter interface (list_tools, fresh_env, snapshot, invoke, reset, source) over a subprocess JSON boundary; static checks (constant-success returns, dead guards, unused parameters, unpaired writes); dynamic snapshot→invoke→snapshot loop; `findings.jsonl` report schema, the reproducibility spine that `report/render.py` renders every table from. Adapter mechanics and Python-version details go to the artifact, not here.]*

---

## VII. Detector Validation

*[NOT YET DRAFTED. All numbers generated under the pre-registered plan committed at `checker-freeze-v1` (`experiments/detector_analysis_plan.md`; cite the commit hash). Fills: [N3: mutation/score.py] closed-world recall per class with tool-clustered, design-effect-adjusted Wilson intervals, claims stated at the interval lower bound; [N4: mutation/score.py + cosmic-ray run] open-world escape rate, raw and adjudicated, decomposed into clause/probe/canonicalization gaps, framed as a lower bound on taxonomy incompleteness; [N5: spec/coverage.py] contract-coverage metric per tool plus biconditional adoption count; [N6: manual triage Sep 9-10] wild precision (confirmed VIOLATES / all VIOLATES). Baseline reference point: AGORA+ 80% precision on REST invariants [agora25]. No hypothesis tests anywhere in this section.]*

---

## VIII. Evaluation Impact

*[NOT YET DRAFTED. Tier 1 trajectory replay only (Tier 2 cut 2026-08-21): [N8: experiments/ab_run.py] verdict flips under replay against as-shipped vs. patched tools, per task, with the benchmark's own evaluator scoring both worlds; [N9: experiments/ab_run.py] tasks requiring the k=3 divergence fallback. Pre-registered in `experiments/analysis_plan.md` (cite commit hash); a null result is publishable under the committed framing and the abstract promises no flips. Runs on tau2-bench only: MedAgentBench's graders read no server state, so a patch there is unobservable by construction (Finding 4), and no A/B is attempted on it. Telecom replay records user-simulator tool calls as well as agent calls (the user simulator writes state). Patches: uncomment `telecom/tools.py:629-630`; add the seat release at `airline/tools.py:366`. Patch diffs ship in the artifact (no appendix at this venue).]*

---

## IX. Findings and Coordinated Disclosure

Across four shipped benchmarks we confirmed **seven unique benchmark-class defect cells, comprising eight finding instances**. The compressed count leads deliberately: this project's reporting rule counts unique defect classes per benchmark, because eight bugs in one copied helper are one bug, and a reviewer will compress the count this way whether or not we do. Four of the eight instances are Ignored Argument. Every finding was verified by direct source reading at a pinned commit by someone other than whoever first surfaced it, and each carries a clean-clone reproduction command in the artifact. Per-benchmark totals (tools audited, mutating tools, independent implementations, unique defect classes) appear in Table III [N1: report/render.py ← findings.jsonl].

**Table: confirmed findings (instance level).**

| # | Benchmark @ commit | Tool / path | Class | Grounding tier |
|---|---|---|---|---|
| 1 | MedAgentBench @ `9926011` | POST branch, `__init__.py:85-91` (three tool definitions, one code path) | Phantom Effect | agent-visible (`prompt_template`, `tool_return`) |
| 2 | tau2-bench @ `c3398666` | `refuel_data`, `src/tau2/domains/telecom/tools.py:607-657` | Unenforced Precondition | agent-visible (`docstring`) |
| 3 | tau2-bench @ `c3398666` | `cancel_reservation`, `src/tau2/domains/airline/tools.py:315, 363-368` | Partial Effect | **maintainer-annotated: not headline-eligible** |
| 4 | MedAgentBench @ `9926011` | write graders, `refsol.py` (SHA-256-pinned; not in the repository) | Ungrounded Oracle (evaluator property, §III) | grader source |
| 5 | AgentDojo @ `089ed46` | `update_scheduled_transaction`, `banking_client.py:115-151` | Ignored Argument + Phantom Effect | agent-visible (`docstring`) |
| 6 | AgentDojo @ `089ed46` | `reserve_car_rental`, `travel_booking_client.py:382-400` | Ignored Argument | agent-visible (`docstring`) |
| 7 | MM-ToolSandbox @ `1e8e932` | `venmo_social`, `mini/venmo.py:464-470` | Ignored Argument | agent-visible (`docstring`) |
| 8 | AgentDojo @ `089ed46` | `invite_user_to_slack`, `slack.py:93-103` | Ignored Argument | agent-visible (`docstring`) |

**MedAgentBench (Findings 1 and 4).** Finding 1 is the no-op POST branch quoted in §I. Finding 4 is what makes it undetectable from inside the benchmark: the grading module, distributed outside the repository and pinned here by SHA-256, reconstructs each write from the conversation transcript. Its `extract_posts` function admits an agent message as a write attempt only when the following message contains "POST request accepted", the literal string the harness fabricates at `__init__.py:91`, and no grader issues a FHIR read to verify any write. Two of the ten task families (60 of 300 cases) grade writes unconditionally through this path. Three more read the server only to decide whether a write is required, then grade the required write from the transcript. We do not claim a case count for those three without a server run. The pair of findings is the cross-layer result of §II: patching the tool to perform real writes would change no score, because no grader observes the state a patch would repair, and that is why §VIII attempts no A/B experiment on this benchmark.

**tau2-bench (Findings 2 and 3).** In `refuel_data`, the docstring declares "Line status must be Active" and advertises a `ValueError` when checks fail. The implementing check is present in the source and commented out, while the sibling `gb_amount` check survives, so a suspended or closed line can be refuelled and the customer billed. The omission is selective, which is what makes it a contract violation rather than absent validation. In `cancel_reservation`, booking decrements `available_seats`, cancellation refunds and marks the reservation cancelled but never increments seats back, and the maintainer logs exactly that ("Seats release not implemented for cancellation!!!") at line 367, with a matching TODO at line 689. Within an episode, seat inventory decreases monotonically regardless of cancellations. Finding 3 is Partial Effect only: we traced the reset path and confirmed each simulation loads a fresh database from disk, so the drift cannot cross tasks, and an earlier Reset Leak label was withdrawn. Its grounding also deserves plain statement: no agent-visible surface in the domain says cancellation releases seats, so the violation rests on the maintainers' own annotations, sits in the middle grounding tier, and is excluded from every headline count.

**AgentDojo (Findings 5, 6, 8).** `update_scheduled_transaction` documents six optional updatable fields but applies each behind a truthiness guard rather than a `None` check, so `recurring`, typed `bool | None`, can be switched on but never off. The tool then returns "Transaction ... updated." unconditionally, a Phantom Effect stacked on the Ignored Argument. A second tool in the same benchmark, `update_user_info`, repeats the truthiness pattern on four string fields and is counted as an additional instance of the same cell rather than a new finding, but it makes an instructive contrast: it returns the account's actual stored fields, so a caller can in principle notice the failure. The same defect class with and without the phantom success signal, in one codebase, shows the two classes are separable in real code. `reserve_car_rental` accepts an `end_time` parameter, writes `start_time` into both fields, and then interpolates the discarded `end_time` into its success message, actively misreporting the stored state (the aggravating signal of §III). No shipped user task exercises this tool through its ground truth, so this finding enters the defect counts and is excluded from any score-impact claim. `invite_user_to_slack` requires a `user_email` parameter whose docstring says where the invite "should be sent", and the body never reads it. The benchmark models inboxes, so the advertised behavior was expressible. This is the strongest Ignored Argument instance in the set, because the parameter is mandatory, and it was surfaced by our static checker in a full-repository scan rather than by hand, then confirmed by direct source read: the first finding the framework found before a human did.

**MM-ToolSandbox (Finding 7).** `venmo_social` declares `sort_by`, documents it twice in its own docstring, and never forwards it in the comment-listing branch, while forwarding the two sibling parameters documented beside it. The correct forwarding pattern appears 250 lines above in the same file. An agent that asks for a sorted listing receives an unsorted one and no indication its argument was dropped.

All four benchmarks are cited at the specific commits audited [medagentbench25], [tau2bench25], [agentdojo24], [mmtoolsandbox26]. Instance-level evidence, including verbatim quotes and line numbers for every claim above, is in the findings ledger and reproducible from clean clones with the commands shipped in the artifact.

**Coordinated disclosure.** We disclose all findings to the four maintainer teams on 2026-09-10, seventeen days before submission, with per-finding reproduction commands and proposed repairs. Under §III's principle, a repair to either side of a divergence resolves a finding, and a documentation fix counts exactly as a code fix does. Maintainer responses, and for any team that does not respond, the fact and date of non-response, are reported here: [N12: disclosure log, from 2026-09-10].

---

## X. Threats to Validity

*[NOT YET DRAFTED — drafted after §IV and §VII numbers exist, since each mitigation cites them. The four named threats and their built-in mitigations are fixed in PAPER-OUTLINE.md §X: construct validity (advertised-surface enumeration, tiering, dual annotation, the intent argument); detector circularity (open-world escape rate, coverage metric, held-out contracts); external validity (benchmark count, MedAgentBench contributes one mutating code path); bound interpretation (at-risk ≠ misgraded). Also carries the PROVENANCE.md sentence: the repository was initialized partway through the work, so authoring order is not reconstructible from history; the pre-registration claims are about scoring and recording order, which are.]*

---

## XI. Conclusion

*[NOT YET DRAFTED — two paragraphs, written last: what the instrument framing buys the field; what a benchmark maintainer should do differently on Monday. One venue-bridge sentence per REVIEW-RESPONSE.md E-W1.]*

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
