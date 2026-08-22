# GATE.md — Day 1 Prior-Work Gate

Run date: 2026-08-21. Decision required before any project code is written.

**Question:** do BenchGuard, Auto Benchmark Audit (ABA), or Tool-Veritas already define tool-contract violations — unenforced precondition, phantom effect, ignored argument, partial effect?

**Verdict: PROCEED, with a sharpened framing.** None of the three audits tool implementation source code. All three stop at the layer above it. But the framing must change: "contracts for tools" and "auditing benchmarks" are both occupied. What is unoccupied is the conjunction — the benchmark's own tool layer as an unaudited measurement instrument.

---

## 1. Existence check

All five cited preprints exist at the given identifiers. Verified by direct fetch of the arXiv abstract pages on 2026-08-21.

| ID | Title | Date | Notes |
|---|---|---|---|
| 2607.02577 | Benchmarking the Benchmarks: A Validity Audit of Tool-Calling Evaluation | 2026-06-30 | The "Tool-Veritas" paper. Tool-Veritas is the benchmark it proposes, not the paper title. |
| 2604.24955 | BenchGuard: Who Guards the Benchmarks? Automated Auditing of LLM Agent Benchmarks | 2026-04-27 | COLM 2026 acceptance is NOT confirmed on the arXiv page. Treat venue as unverified. |
| 2605.26079 | Automated Benchmark Auditing for AI Agents and Large Language Models | 2026-05-25 (v2 2026-05-26) | The ABA paper. |
| 2601.04688 | ToolGate: Contract-Grounded and Verified Tool Execution for LLMs | 2026-01-08 | |
| 2603.18245 | Who Tests the Testers? Systematic Enumeration and Coverage Audit of LLM Agent Tool Call Safety | 2026-03-18 (v2 2026-08-15) | The SafeAudit paper. |

Two corrections to the working assumptions carried into this project:

- BenchGuard was deployed on **ScienceAgentBench and BIXBench** — scientific/bioinformatics agent benchmarks — not on tool-calling benchmarks. Its 14 subcategories are about task artifacts, not tools.
- Tool-Veritas audits **four benchmark families** including tau2-bench Retail, and reports 11 disagreements there. It found none of our three defects, because it never looks at tool source.

## 2. Category mapping onto our six defect classes

Our classes: Phantom Effect (PE), Unenforced Precondition (UP), Ignored Argument (IA), Partial Effect (PART), Invariant Break (INV), Reset Leak (RL).

### BenchGuard, Appendix A — all 14 subcategories

| Code | Definition (verbatim) | Covers ours? |
|---|---|---|
| GT-LOGIC | "Gold uses incorrect algorithm, computes wrong metric, or applies logical opposite" | No |
| GT-DATA | "Gold uses wrong input files or columns, drops data, or covers only partial scope" | No |
| GT-FMT | "Gold output format does not match the specification" | No |
| EVAL-JUDGE-BIAS | "LLM judge rigidly anchored to one implementation, rejecting valid alternatives" | No |
| EVAL-MISMATCH | "Eval checks something different from what the specification requests" | No |
| EVAL-COVERAGE | "Eval does not handle all valid output formats, types, or equivalent names" | No |
| EVAL-TOLERANCE | "Numerical tolerances too strict or too lenient" | No |
| EVAL-STOCHASTIC | "Eval assumes deterministic output for inherently non-deterministic computation" | No |
| INST-INCOMPLETE | "Essential information missing, preventing a unique correct solution" | No |
| INST-CONTRADICT | "Instruction conflicts with the gold program or evaluation script" | No |
| INST-INFEASIBLE | "Task cannot be solved with the provided information" | No |
| ENV-DEP | "Required packages unavailable or version conflicts" | No |
| ENV-PATH | "Hardcoded absolute paths that do not match the evaluation environment" | No |
| ENV-RESOURCE | "Requires network access, external APIs, or exceeds time/compute limits" | No |

Scope, per the paper: BenchGuard audits the four artifacts per task — instructions, ground-truth reference solutions, evaluation scripts, environment configurations. It does not audit tool implementation source code.

Coverage of our six classes: **0 of 6.**

The nearest miss is INST-CONTRADICT — instruction versus gold program. Ours is docstring versus implementation. Same *shape* of defect (declared intent diverges from executed behavior), different artifact pair, and the artifact pair is the whole point: theirs is checkable from task metadata, ours requires reading the tool body.

### Auto Benchmark Audit — the three-axis issue schema

| Axis | Definition (verbatim) | Covers ours? |
|---|---|---|
| Instruction | "The prompt is missing critical information, is ambiguous, or is misleading in a way that drives failures." | No |
| Environment | "The runtime environment — container image, resources, installed tools, filesystem — conflicts with what the task instructions assume or require, blocking the approach the prompt instructs." | No |
| Evaluation | "The test suite does not fairly and completely evaluate correct solutions: too narrow (rejects valid alternatives), too broad (accepts trivially wrong outputs), or misaligned with the stated objective." | No |

"Execution environment conflicts" is about container/resource/filesystem mismatch, not about tool semantics. Coverage: **0 of 6.**

ABA operates on "task definition — the instruction the agent would receive, the tests against which its solution would be graded, the evaluation configuration." Tool bodies are outside the manifest.

### Tool-Veritas (2607.02577) — evaluation-failure taxonomy

Deterministic evaluator failures: brittle state matching; trajectory lock-in; annotation errors; reward-basis mismatch; exact-match constraints; state over-specification.

LLM-judge failures: rubric drift; judge variance; hallucinated completion; implementation-specification mismatches.

Coverage: **0 of 6.**

The one genuinely alarming category name, "implementation-specification mismatch", was checked directly. It occurs once, in Section 2 Related Work, and refers to LLM judges scoring final answers rather than verified tool use — an evaluator artifact, not a tool body defect. It is never defined as a failure class and has no case study. This is a naming collision only, but a reviewer will trip on it, so the paper must dispose of it explicitly in one sentence.

What the paper does inspect: "complete execution traces, tool invocation logs, evaluator outputs, environment states, and final benchmark verdicts." All downstream artifacts. Its deterministic gates "inspect observable properties of the sandbox state" — that is, they assume the tool that wrote the state was correct. Our claim is precisely that this assumption is unsound, and that failure is invisible to a gate reading the state a broken tool produced.

### ToolGate (2601.04688) — the closest conceptual neighbor

Defines each tool as "a Hoare-style contract consisting of a precondition and a postcondition." This overlaps our vocabulary directly. But the direction of use is opposite: ToolGate's precondition "gates tool invocation" and its postcondition "determines whether the tool's result can be committed" — runtime enforcement that makes an *agent* safer, given contracts assumed correct. It never asks whether the tool's implementation honors its own declared contract. **The contract is the trusted input for ToolGate; it is the thing under test for us.**

### SafeAudit (2603.18245)

Meta-audits *coverage* of safety test suites via workflow enumeration and a "rule-resistance" metric. Does not read tool implementations. Coverage: 0 of 6.

## 3. Broader sweep (Consensus)

Two searches: design-by-contract runtime verification of API pre/postconditions; and metamorphic/differential testing of REST API side effects and state transitions. Full citations in REFERENCES.md.

The design-by-contract literature is mature (jContractor 2005, Jass 2001, frame specifications 2025). **We are not inventing contracts and must not imply we are.** Three results are close enough to be real reviewer ammunition:

- **ConTract (DSN 2026)** — infers implicit API contracts over *pointer state transitions*, synthesizes preconditions/postconditions, checks implementations, found 209 inconsistencies with 127 developer-confirmed. This is our method shape applied to C systems code. Distinguish on domain and on purpose: they find bugs in software; we measure the validity of an evaluation instrument.
- **IcePICK / Glacier (ICST 2026)** — first-order-logic executable contract language for API specs to close the oracle gap. Nearest neighbor to our contract format. Distinguish: their SUT is the API; our SUT is the benchmark's simulated tool layer, and the consequence we care about is a corrupted agent score, not a service fault.
- **AGORA+ (TOSEM 2025)** — Daikon-based invariant detection over API request/response pairs, 80% precision, 106 invariant types. Directly relevant to our Invariant Break detector and a good precision baseline to compare against.

Also cite: Segura's metamorphic testing of RESTful APIs and the metamorphic testing surveys (the Ignored-Argument and Partial-Effect detectors are metamorphic relations in all but name); RESTler for stateful sequence generation; Agent Behavioral Contracts (2026) as the agent-side analogue of ToolGate.

None of these examine agentic benchmark harnesses. The gap is real.

## 4. Narrowed contribution

Do not claim: contract specification for tools (ToolGate, ABC, IcePICK); automated benchmark auditing (BenchGuard, ABA); tool-calling evaluator validity (Tool-Veritas); safety-suite coverage (SafeAudit); design-by-contract itself (30 years old).

Claim exactly this:

1. **The benchmark tool layer is a measurement instrument that no prior audit reads.** Every one of the five prior works either audits the layer above the tools (tasks, environments, graders, judges) or enforces contracts at runtime for the agent's benefit. All of them treat the tool implementation as ground truth. Tool-Veritas makes this explicit and load-bearing: its deterministic gates read sandbox state written by tools it never inspects.
2. **Six executable defect classes over the interface -> implementation -> state-transition contract**, with detection procedures, not prose definitions. The state-persistence and side-effect layer is what the prior taxonomies lack; PE, PART and RL have no counterpart anywhere in the 14 + 3 + 10 categories surveyed above.
3. **Mutation-validated detection.** Prior audits report findings; none report precision and recall of their detectors against injected ground truth. This is the methodological differentiator, and it is the part that must be airtight.
4. **The evaluation consequence.** A buggy-vs-patched agent experiment on affected tasks converts "this benchmark has bugs" into "this benchmark's scores are wrong by X on these tasks." Without deliverable 5 this is a bug report and reviewers will say so.

## 5. Positioning sentences for the paper

- On Tool-Veritas: it audits whether the *verdict* matches the true outcome; we audit whether the *world state the verdict reads* was ever correctly written. Its deterministic state gates inherit any defect in the tool that produced the state.
- On BenchGuard and ABA: both audit task artifacts — instructions, gold solutions, graders, environments. Neither reads a tool body. A tool that returns success without acting is invisible to both, because the artifacts they inspect are all consistent.
- On ToolGate and ABC: contracts as runtime guardrails for the agent, with the contract trusted. We invert the relation and test the contract against the implementation.
- On ConTract, IcePICK, AGORA+: contract inference and executable oracles for production software, where the fault costs a service outage. In a benchmark the same fault costs something different and worse for the field — a number in a table that nobody can tell is wrong.

## 6. Residual risk

The framing survives, but it is thinner than it looked before this gate. Reviewers with an SE background will know ConTract and IcePICK and will ask what is technically new about the checker. The honest answer is: not the checking technique, but the target, the defect classes that target implies, and the demonstrated effect on published agent scores. The paper must lead with the target and the consequence, not with the machinery. If it leads with the machinery it will be read as an incremental contract-checker paper and rejected.

## 7. Not yet done

~~Scopus (browser, logged-in session) was not used in this pass.~~ **Closed 2026-08-21.** Scopus ran; BenchGuard's COLM 2026 acceptance is confirmed against the official accepted-papers page, the other four named preprints are confirmed preprint-only, and four already-printed bibliography rows were corrected. See `REFERENCES.md`.

---

## 8. Second sweep — Consensus, 2026-08-21

The Consensus connector was unavailable during the Day 1 pass and §3 above ran without it. It has now run across six angles: tool/environment-layer auditing, simulator and mock fidelity, oracles and metamorphic relations over stateful side effects, contract-based testing for LLM tool interfaces, benchmark construct validity, and a direct naming search for phantom-effect / no-op / success-without-state-change.

**The verdict does not change. One hit changes the paper's opening.**

### LiveClawBench (arXiv:2604.13072) — the closest work in the literature, and it helps us

It names, as its own motivating problem, that agent-benchmark mocks are commonly "reduced to endpoint-level stubs that remove sessions, artifacts, state transitions, and downstream side effects," and it builds higher-fidelity mocks in response.

That is our symptom, stated independently by someone else, and it is the strongest available evidence that the problem is real rather than an artifact of us going looking for it. It does not collide, because it acts **prospectively** — build better mocks — and never audits an already-published benchmark's tool bodies against their own declared contracts. No defect taxonomy, no detector, no validation of either.

**Use it in §I as motivation, not only in §II as a disposal.** "The field has noticed that benchmark mocks discard state transitions; nobody has gone and measured which shipped benchmarks do it, or what it costs their scores" is a better opening than any argument we would construct ourselves.

### Disposals required

| Work | Collision | Disposal |
|---|---|---|
| ToolFuzz (arXiv:2503.04479) | Nearest engineering neighbour — automated testing of agent tool *documentation* for over/under/ill-specification | Its oracle is agent-response correctness with documentation as ground truth, on production LangChain tools. Ours is implementation-versus-declared-contract on a benchmark's simulated tool, with state transitions as the observable — and the documentation is precisely what we do **not** trust |
| Contract2Tool (arXiv:2606.07904), ContractBench (arXiv:2605.17281) | Contract vocabulary applied to agent tools | Both treat the contract as trusted ground truth and put the **agent** under test. Extends the ToolGate line already disposed of in §2 — one shared sentence covers all three |
| ABC checklist (arXiv:2507.02825) | Task/reward-layer audit, **but it names a defect in tau-bench**, one of our two audited artifacts | Their finding is a grading-script defect: empty responses counted as success. Ours are tool-implementation defects. **Action: confirm no overlap before the tau2 findings section is drafted** — this is the one hit that touches our own evidence |
| ContractGuard (arXiv:2606.18550) | "Forging a tool's effects" sounds like Phantom Effect | Adversarial security — defeating a permission gate. Ours is benign implementation divergence. One line, only if a reviewer raises it |

### Angle 6 returned nothing, for the second time

No work names a defect class for success signals that do not correspond to state change. Two independent search engines, two nulls. The naming gap is real and the paper may say so.
