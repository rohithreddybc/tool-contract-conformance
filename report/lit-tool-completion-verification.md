# Literature check: does anyone verify actual task/side-effect completion, rather than trusting a returned status?

Run 2026-09-03, in response to a co-author review comment. Question, three findings, and the review's own framing example
(checking whether a file genuinely changed on disk rather than trusting a returned success signal) are addressed directly below.

## Verdict

Yes, this line of work exists, and it is sizeable: dozens of agent benchmarks and evaluation-layer audits verify task
completion against actual environment state rather than an agent's or tool's self-report. **None of them verify the thing
we verify.** Every mechanism found checks either (a) whether an *agent* actually changed the state it claims to have
changed, using the benchmark's own environment/database as ground truth, or (b) whether a benchmark's *outcome-grading
script* is a reliable reader of that ground truth. In both cases the tool implementation that writes the state — the layer
this project audits — is the trusted, unexamined foundation the check is built on. Nobody re-executes a benchmark's own
tool bodies against their declared contracts to ask whether the state they wrote was ever the state they claimed to write.

This closes the reviewer's foreseeable objection with a named distinction rather than a hand-wave: state-based grading is a
mature, independently-motivated literature, but it grades the *agent* using the *tool* as ground truth. This project
inverts that relationship and grades the *tool*.

## Table

Grouped by verification mechanism. "Covers" states what the mechanism actually checks; "Gap relative to us" states what it
structurally cannot check, given what it treats as trusted.

| Work | Venue / year | Mechanism | What it verifies | Gap relative to our contract-conformance claim |
|---|---|---|---|---|
| **WebArena** (Zhou et al.) | ICLR 2024 — confirmed via `proceedings.iclr.cc` PDF | Programmatic checkers read post-episode environment state (DB rows, page content, files) and compare to a task-specific success condition; explicitly framed as "functional correctness" rather than trajectory matching | Whether the *agent* actually produced the required state change on a live, fully-functional web app | The environment's own application code is the ground truth the checker reads. If a tool/API in that environment reports success without writing the state (our Phantom Effect class) or writes only part of it (Partial Effect), the checker inherits the error silently — it was designed to catch agent failure, not environment-tool failure |
| **AppWorld** (Trivedi et al.) | ACL 2024 — confirmed, arXiv Comments field reads "ACL'24 Camera Ready" | State-based unit tests after each episode, plus explicit checks for unintended state changes ("collateral damage") across a 60K-line simulated app engine | Whether the agent's actions produced the required state change and nothing else, over a large simulated multi-app environment | Its own execution environment (AppWorld Engine) is the tool layer under audit in our sense, and it is exactly the kind of scripted, benchmark-authored tool code our six defect classes target — but AppWorld's tests assume that engine is correct; they were never run *against* the engine's own declared API contracts to check whether the engine's tools honor them |
| **OSWorld** (Xie et al.) | NeurIPS 2024 Datasets & Benchmarks Track — confirmed via `proceedings.neurips.cc` PDF | Custom per-task execution-based evaluation scripts that inspect real OS/file/application state after an episode | Whether an agent's actions on a real OS produced the required end state | Evaluates real, unmodified applications, not a benchmark's own simulated tool layer — there is no "tool implementation" of the kind we audit; the closer analogue for this project is a benchmark like MedAgentBench or tau2-bench where the "environment" *is* benchmark-authored code |
| **AndroidWorld** (Rawles et al.) | ICLR 2025 — confirmed via `proceedings.iclr.cc` abstract page | Each of 116 tasks ships dedicated initialization, success-checking, and tear-down logic that inspects Android device/app database state | Whether the agent's actions changed device state as required, reproducibly | Same structure as WebArena/OSWorld: the success-checker reads state written by real Android apps, not by a benchmark-authored tool stand-in, and never checks whether *its own* success-checking logic or any mocked component is faithful to a declared contract |
| **Agent-Diff** (Pysklo, Zhuravel, Watson) | arXiv:2602.11224, **preprint only** — Comments field reads "Under review for KDD 2026," not yet accepted (a Consensus listing showing a KDD volume/DOI is therefore premature and should not be cited as confirmed) | Defines a "state-diff contract": task success = whether the *expected* environment-state delta occurred, checked by diffing containerized replica-API state before/after, rather than fuzzy trace or parameter matching | Whether an *agent's* code-execution actions against a sandboxed enterprise-API replica produced the intended state diff | This is the nearest single hit to the reviewer's "diff the disk" example, and worth citing precisely for that resemblance — but the state-diff contract is written and checked as an *agent* oracle: the replica API's own implementation is the assumed-correct source of the "before" and "after" states being diffed. It never asks whether the replica API's tool implementations honor their own declared preconditions/effects; that implementation is exactly our object of audit and is invisible to their diff |
| **"From Confident Closing to Silent Failure" / false-success characterization** (Advani) | arXiv:2606.09863, workshop paper — Comments field reads "Accepted to FAGEN@ICML2026" (an ICML workshop, not the main conference) | Compares an agent's *self-reported* success/failure claims against ground-truth outcome labels derived from tau2-bench's and AppWorld's own environment state, across ~9,900 and ~1,900 trajectories respectively; shows LLM judges are unreliable detectors of this gap | Whether an agent's confident natural-language claim of task completion matches what the benchmark's environment state actually shows | Directly adjacent and worth citing as the clearest evidence that "trusting a returned status" is already a recognized failure mode in this literature — but the status being distrusted is the *agent's* self-report, and the environment state used to adjudicate it is tau2-bench's own tool-and-database layer, taken as ground truth. If that layer itself silently reports success without writing state (our finding, independently confirmed in tau2-bench), this method's ground truth is compromised in a way it has no mechanism to detect |
| **"Can Agent Benchmarks Support Their Scores?" / outcome-evidence-bounds** (Gao, Zhou) | arXiv:2605.10448, preprint — no venue claim on the abstract page | Adds an evidence-reporting layer on top of five existing benchmarks' outcome checks (AndroidWorld, AgentDojo, AppWorld, tau3-bench Retail, MiniWoB): requires each claimed outcome to be backed by a specified stored artifact, and labels each run Evidence Pass / Fail / Unknown rather than trusting the checker's binary verdict | Whether a benchmark's own *outcome-checking logic* is well-evidenced, using the worked example "the outcome check only verifies the agent clicked Save, not that the intended state change occurred" | This is the closest published articulation of the reviewer's exact worry, applied one layer up from where this project applies it: it audits whether the grading script's pass/fail *inference* is supported by stored evidence of state change. It does not open the tool implementation that produced the state the evidence layer inspects, and does not ask whether that tool's own contract (its docstring, schema, or declared postcondition) was honored — the tool body is out of scope in the same way it is for BenchGuard, ABA, and ABC (see `GATE.md` §2) |
| **AJ-Bench / Agent-as-a-Judge** (Shi et al.) | ACL 2026 Findings — confirmed, arXiv Comments field reads "Accepted to ACL 2026 Findings" | A judge *agent* actively interacts with tools/environment to gather evidence (not passive observation) before verdicting task success, across search/data-systems/GUI domains | Whether an active, tool-using verifier agent can more reliably determine ground-truth task success than a passive LLM-as-judge | Improves *how* state is inspected for grading, not *what wrote the state*; still trusts that the environment/tool responses the judge agent queries are themselves faithful to their contracts |
| **REAL** (Garg et al.) | arXiv:2504.11543, preprint — venue not confirmed this pass | Programmatic checks of deterministic-replica website state for action tasks, combined with rubric-guided LLM judgment for retrieval tasks | Whether an agent's actions on a controlled website replica produced the required state change | Same category as WebArena/Agent-Diff: the replica's own backend is trusted; no audit of whether replica endpoints honor declared behavior |
| **Zhu et al., "Understanding and Characterizing Mock Assertions in Unit Tests"** | ACM PACMSE / Proc. ACM Softw. Eng. 2025, DOI 10.1145/3715741 — already logged in `REFERENCES.md` as background | Empirical study of 4,652 test cases across 11 Java projects: mock assertions (verifying a mocked dependency was *called* in a certain way) catch side effects that ordinary return-value/state assertions cannot see | Establishes, empirically and independently of agent benchmarks, that a call's return value alone is an insufficient completion oracle — side effects need a dedicated check | General SE finding about developer-written unit tests with mocks, not about benchmark tool implementations or agent evaluation at all; supports the *premise* that returned status is an incomplete oracle, but proposes no mechanism applicable to auditing a shipped benchmark's tool layer, and asserts nothing about state actually changing on a real backing store (mock assertions verify *interaction*, not persisted state) |
| **Tiwari et al., "Mimicking Production Behavior with Generated Mocks" / RICK** | IEEE TSE 2024 (journal version, DOI 10.1109/tse.2024.3458448) / ICST 2023 (tool demo, DOI 10.1109/icst57152.2023.00051) | Monitors production execution to generate realistic mocks and mock-based oracles, then uses them to catch regressions in target methods | Whether a generated mock's behavior — and downstream unit tests built on it — matches what the real dependency does in production | General-purpose regression-testing tool for ordinary software; not agent- or benchmark-specific, and does not check a benchmark's own already-written tool bodies against their declared contracts |
| **BenchGuard, ABA, Tool-Veritas, ABC, SafeAudit, ToolGate** and the other Day-1-gate and gap-sweep items | Various, 2025-2026 — see `GATE.md` and `REFERENCES.md` | Already fully disposed of in `GATE.md` §2 and the Gap-sweep table | Task/reward/grader-layer auditing, or agent-side runtime contract enforcement | Not re-litigated here; cited for completeness. None of them mechanically re-executes a tool body against its own contract either |

## What "verifies completion" mechanically means across this literature, in one list

Every mechanism found in this search reduces to one of these, none of which is ours:

1. **State-diffing / functional-correctness checkers** (WebArena, AppWorld, OSWorld, AndroidWorld, REAL, Agent-Diff) — inspect
   environment state after an episode and compare it to an expected value or delta. Verifies the *agent*; treats the
   state-writing tool/environment code as ground truth.
2. **Self-report-vs-ground-truth comparison** (the false-success paper) — compares what an agent *says* it did to what the
   environment shows. Still uses the environment's own tool layer as the ground truth being compared against.
3. **Evidence-sufficiency auditing of the grading script itself** (the evidence-bounds paper) — asks whether a benchmark's
   pass/fail verdict is actually backed by stored proof of the claimed state change, one layer above where we operate.
4. **Active/interactive verification agents** (AJ-Bench) — improves how state is inspected for grading, not what produced it.
5. **Mock/stub fidelity checks** (Zhu et al., Tiwari et al./RICK) — general software-engineering findings that a call's
   return value is an incomplete oracle for its side effects; establishes the premise, not a benchmark-auditing method.
6. **Differential/re-execution testing against a reference implementation** — searched for directly (angle: "differential
   testing of tool implementations," "reference implementation," McKeeman's original 1998 differential-testing report as the
   root of this family) but **no hit surfaced applying it to a benchmark's simulated tool layer against its own declared
   contract**. The nearest engineering neighbors (ToolFuzz, Contract2Tool, ContractBench — already disposed of in
   `REFERENCES.md`'s Gap-sweep table) test agent-facing correctness or agent contract-preservation, not implementation-vs-
   declared-contract on the tool body itself.
7. **Property-based/postcondition testing frameworks in the general SE literature** (Goldstein et al. 2024, Hypothesis,
   Ravi et al. 2025, Maaz et al. 2025's agentic PBT) — mature machinery for checking that an implementation satisfies a
   postcondition against many generated inputs. **No hit found applying this machinery to a benchmark's own tool
   implementations.** This is the closest thing to a "why not just use an existing method" answer for a differently-skeptical
   reviewer: the *technique* (contract-checking, discussed at length in `GATE.md` §3 via ConTract, IcePICK, AGORA+) is not
   novel; applying it to *this target* — a benchmark's tool layer, treated as an unaudited measurement instrument — is what
   is missing from the literature, in both the agent-benchmark-evaluation angle searched here and the classical
   contract/API-testing angle `GATE.md` already searched.

## Recommended related-work paragraph

Drop-in paragraph, written for the position after the ToolGate/ABC disposal in the related-work section (extends, rather
than replaces, the existing `GATE.md` §5 positioning sentences):

> A separate and substantial literature verifies task completion against actual environment state rather than a returned
> status, and a reviewer might reasonably ask why our approach is needed alongside it. WebArena [webarena24], AppWorld
> [appworld24], OSWorld [osworld24], and AndroidWorld [androidworld25] all grade agents by inspecting post-episode
> environment state — database rows, files, device configuration — rather than trusting an agent's or a tool's self-report,
> and Agent-Diff [agentdiff26] formalizes this as a "state-diff contract" for enterprise-API agent tasks. Advani
> [falsesuccess26] shows directly that agents' confident claims of completion diverge from tau2-bench's own recorded state
> in 45-76% of failures depending on the domain, and Gao and Zhou [evidencebounds26] show that a benchmark's outcome
> checker can itself accept a superficial proxy (e.g., that a Save button was clicked) in place of the state change it was
> meant to certify. Each of these methods, however, treats the benchmark's own tool implementation — the code that writes
> the state being diffed, self-reported against, or certified — as ground truth. None re-executes that implementation
> against its own declared contract to ask whether the state it wrote was ever the state its docstring, schema, or return
> value claimed. Our contribution is exactly that missing step: we hold the benchmark's tool layer to its own advertised
> interface, rather than using it, uninspected, as the oracle against which an agent or a grading script is judged.

If a reviewer wants the negative result stated more starkly, a second, shorter sentence can be appended: "We are not aware
of any published work that audits a benchmark's own tool implementations against their declared preconditions,
postconditions, or state-transition contracts; every state-based verification method surveyed operates one layer above
this target."

## Scopus queries left for the main session

Per the standing rule, Scopus requires the browser session and was not attempted here. Run these (Advanced Search, by
title and by author-list where a DOI is not yet known) before the bibliography is frozen:

1. `TITLE("Agent-Diff") AND TITLE("state-diff")` — to check whether the KDD 2026 review outcome has posted (it was
   preprint-only, under review, as of this pass).
2. `TITLE("From Confident Closing to Silent Failure")` — confirm FAGEN@ICML2026 workshop status and check for a later
   full-paper version.
3. `TITLE("Can Agent Benchmarks Support Their Scores")` — currently unconfirmed preprint; check for any subsequent venue.
4. `TITLE("AJ-Bench") AND TITLE("Agent-as-a-Judge")` — corroborate ACL 2026 Findings acceptance independently of the arXiv
   Comments field.
5. `TITLE("WebArena") AND AUTH(Zhou) AND AUTH(Neubig)` — corroborate ICLR 2024 (currently confirmed only via the
   `proceedings.iclr.cc` PDF URL and a WebSearch summary, not a Scopus DOI match).
6. `TITLE("AndroidWorld") AND AUTH(Rawles)` — corroborate ICLR 2025 the same way.
7. `TITLE("OSWorld") AND TITLE("Benchmarking Multimodal Agents")` — corroborate NeurIPS 2024 Datasets and Benchmarks Track.
8. `TITLE("AppWorld") AND TITLE("Controllable World of Apps")` — corroborate ACL 2024 (currently only arXiv Comments-field
   corroborated).
9. `TITLE("REAL") AND TITLE("Deterministic Simulations of Real Websites")` — venue status currently unknown.
10. `DOI(10.1145/3715741)` — re-confirm the Zhu et al. mock-assertions DOI already logged, now being cited for a new
    purpose in this file.

## Limitations of this search

- The Consensus connector was reachable and used for six queries covering the angles requested (state-based agent
  grading, tool-call side-effect verification, postcondition/runtime verification, mock/stub differential fidelity,
  grader/harness-validity auditing, property-based testing of stateful systems), plus one follow-up query targeting the
  classic web/desktop/mobile agent benchmarks by name. Each returned 20 results; results beyond the top 20 per query were
  not examined, so a lower-ranked but relevant paper could have been missed.
- Venue confirmation for the newly-surfaced items relied on direct arXiv abstract-page fetches (Comments/Journal-ref
  fields) and, for the four classic benchmarks, a publisher-page fetch or WebSearch resolving to `proceedings.iclr.cc` /
  `proceedings.neurips.cc`. None of this is a Scopus confirmation; the queries above must still be run before the
  bibliography is frozen, per the project's own standing rule that an arXiv or WebSearch hit is not venue confirmation.
- 2026 is a fast-moving preprint literature (most hits in this pass are dated January-August 2026); several close items
  (Agent-Diff, the false-success paper, the evidence-bounds paper) are explicitly still under review or workshop-only, so
  their status should be re-checked closer to submission — a promotion to a full venue between now and the camera-ready
  deadline would strengthen rather than weaken their citability.
- The search did not separately re-run the "simulator fidelity / sim-to-real gaps in tool sandboxes" angle as a fresh
  Consensus query, since `GATE.md` §8 and `REFERENCES.md`'s Gap-sweep row 7 (LiveClawBench) already cover that angle in
  depth and this pass's results did not surface anything materially different on it (Agent-Diff's sandboxed-vs-real-API
  discussion is the one partial addition, folded into the table above).
- No non-English-language literature was searched. No search was run against ACM/IEEE digital libraries directly (only via
  Consensus's indexing of them and the specific DOI/publisher-page checks above), so a purely IEEE- or ACM-hosted work with
  poor arXiv/Semantic-Scholar visibility could have been missed.

## Verification and gap-closing pass, 2026-09-05

Run to harden the above for citation. Three closest hits hand-verified against their actual abstracts and, where possible,
an independent non-arXiv source; six additional search angles run to close the gaps the first pass flagged as unattempted;
a drop-in related-work subsection produced from the result. All ten Scopus queries listed above remain formally unrun
(Scopus was not reachable from this pass either; the fallback below was arXiv direct fetch, dblp, ACM DL search, and
WebSearch resolving to a publisher or an official program page) and must still be run before the bibliography freezes.

### Part 1 — hand verification of the three closest hits

**Agent-Diff (arXiv:2602.11224) — characterization holds; one new risk found, the venue caution must get stronger, not
weaker.**

The abstract, fetched directly (`arxiv.org/abs/2602.11224`, current version v3, 2026-04-28), confirms the term is theirs
verbatim: "a novel state-diff contract, which separates process from outcome — rather than fuzzy trace or parameter
matching, we define task success as whether the expected change in environment state was achieved." It applies to
agentic LLMs performing enterprise-productivity-software tasks via code execution against "containerized replicas of
enterprise APIs," evaluated across nine LLMs and, per the current abstract, 260 tasks (the earlier-read 224-task figure
was from an older version; cite the current count, 260, if a task count is quoted). This matches the existing report's
characterization exactly and needs no correction on the mechanism.

The venue claim is where this pass found something the first pass could not have: the paper's own GitHub repository
(`github.com/agent-diff-bench/agent-diff`) now self-cites as accepted, giving a full KDD '26 proceedings citation
("In Proceedings of the 32nd ACM SIGKDD Conference on Knowledge Discovery and Data Mining (KDD '26), August 09-13, 2026,
Jeju Island, Republic of Korea") in both its formatted citation and its BibTeX entry. Weighed against that claim:

- The arXiv abstract page itself, at its most recent version (v3, 2026-04-28), still reads "Pre-Print. Under review for
  KDD 2026" — not accepted.
- dblp lists the work as "informal publication ... CoRR abs/2602.11224" only, with no KDD proceedings entry. dblp is
  normally fast to add a proceedings entry once a paper appears in the published volume, and KDD 2026 (Jeju Island,
  August 9-13, per the official conference site) has already concluded relative to today's date. Its absence from dblp
  this long after the conference is meaningful, if not conclusive, negative evidence.
- ACM DL's own advanced search could not be queried directly (403 on the search endpoint from this environment), and no
  independent WebSearch or OpenReview hit placed the paper in the KDD 2026 accepted-papers list or an OpenReview decision
  page.
- The Consensus connector's own metadata field tags this paper "Proceedings of the 32nd ACM SIGKDD Conference on
  Knowledge Discovery and Data Mining V.2" with a DOI that on inspection is just the arXiv DOI
  (`10.48550/arxiv.2602.11224`) restated — i.e., Consensus's venue tag is a metadata artifact, not a real ACM DOI, and is
  itself an instance of the premature-indexing risk the original report already warned about.

Net: the GitHub self-citation is exactly the class of self-reported completion claim this project treats skeptically
everywhere else, and it is not corroborated by any independent, authoritative source at the time of this pass. The
report's existing caution ("a Consensus listing showing a KDD volume/DOI is therefore premature and should not be cited
as confirmed") holds and should be read as extending to the authors' own repository as well. Recommendation: continue
citing as **arXiv preprint, under review**, and re-check dblp and ACM DL once more immediately before the bibliography
freezes — KDD's proceedings indexing can lag a conference by some weeks, so this could resolve either way before
2026-09-27.

**Gao and Zhou (arXiv:2605.10448) — characterization confirmed exactly, no correction needed.**

The abstract, fetched directly, states the worked example almost verbatim to how the report already summarized it: "a
benchmark task may ask whether Alice's shipping address was changed, while the outcome check only verifies that the
agent clicked 'Save.' This does not guarantee that the intended state change occurred, since the agent may have modified
the wrong record." The layer claim is equally confirmed: the paper "introduces an outcome evidence reporting layer for
existing benchmarks, without modifying their tasks, agents, or evaluators," applied to five existing benchmarks
(AndroidWorld, AgentDojo, AppWorld, tau3-bench Retail, MiniWoB) as a wrapper around their existing outcome checks, not a
re-execution of anything underneath those checks. No Comments field and no Journal-ref field appear on the abstract page
at all, confirming the report's "no venue claim" characterization precisely — there is nothing to correct.

**Advani (arXiv:2606.09863) — venue confirmed independently and precisely; one drafting error in the report's own
recommended paragraph must be fixed before it is used.**

The Comments field reads "Accepted to FAGEN@ICML2026." This was checked independently of the self-reported arXiv field:
FAGEN ("Failure Modes in Agentic AI") has its own workshop website (`fagen-workshop.github.io`) and an OpenReview venue
group (`openreview.net/group?id=ICML.cc/2026/Workshop/FAGEN`), both confirming it as a non-archival ICML 2026 workshop
held 2026-07-10 in Seoul, alongside the main conference rather than as a main-conference track. This is a workshop
acceptance, not a main-conference one, exactly as the existing report states, and now with an independent source behind
it rather than only the self-reported arXiv Comments field.

The mechanism claim is confirmed: the paper compares "9,876 tau2-bench trajectories from 8 model families and 1,879
AppWorld trajectories from 4 model families" against "text-independent ground truth," i.e., agents' own claims of
completion against tau2-bench's and AppWorld's recorded environment state.

The correction: the existing report's own drafted related-work paragraph (the "Recommended related-work paragraph"
section above) states the false-success rate as "45-76% of failures depending on the domain." The actual abstract gives
three separate figures for three separate settings, not one range within one benchmark: 45-48% of failures in
single-control tau2-bench domains, 3% in dual-control telecom (also tau2-bench), and 75.8% among AppWorld
self-assessing coding-agent trajectories. The drafted "45-76%" silently mixes a tau2-bench figure with an AppWorld
figure as though they were the same distribution, which they are not, and rounds 75.8 to 76 without saying so. This
should not be repeated in any paper text. The related-work prose below in Part 3 does not cite any of these percentages,
by design, both to avoid this error and because these are the preprint's own self-reported detector results, which the
report already correctly flagged as not independently logged by this project and therefore not citable as a verified
number.

### Part 2 — closing the search gaps

Six angles run through the Consensus connector (twenty results each, same protocol as the first pass): postcondition and
runtime verification of side effects; simulator and sandbox fidelity for agent environments; harness and grader
correctness bugs in ML/agent benchmark evaluation; differential and metamorphic testing of tool/API implementations;
mock and stub fidelity; and validity of execution-based evaluation. The postcondition/runtime-verification and
differential/metamorphic angles returned only literature already known to this project (JML/ESC, Rust verification,
NL2Contract, CoGent, the Segura RESTful-API metamorphic-testing line) — nothing new and on point. The other four angles
surfaced five items worth logging, none of which changes the verdict, all of which are still one layer away from a
benchmark's own tool implementation:

| Work | Venue / year | Mechanism | What it covers | Gap relative to our contract-conformance claim |
|---|---|---|---|---|
| **"Building to the Test: Coding Agents Deliver What You Check, Not What You Requested"** (Ma, Kereopa-Yorke, Schultz) | arXiv:2606.28430, preprint, no venue claim | Two production coding agents re-implement a UI library under a hidden 222-test oracle across three oracle-availability conditions; a mechanical library audit and a no-op ablation check whether the delivered artifact matches what the oracle rewarded | Names "building to the test" and "validation self-awareness": with the oracle in the loop the score is near-perfect, but an independent audit shows the actual deliverable is unfinished or absent | Audits whether an **agent's delivered artifact** matches what a hidden test oracle rewards — the oracle itself is external, fixed, and trusted; this is a construction-validity finding about agent behavior under a test-driven grader, not an audit of a benchmark's own tool/environment implementation. Same shape as the already-disposed grader-layer literature, one layer above ours |
| **"Towards Evaluation Engineering: An Empirical Study of ML Evaluation Harnesses in the Wild"** (Zhao, Wang, Bangash, Adams, Hassan) | arXiv:2605.24213, preprint, no venue claim | Empirical study of 57 general ML evaluation harnesses (not agent-specific), classifying 16,560 issues by workflow stage and root cause; finds unimplemented features, documentation gaps, and missing input validation dominate | Establishes, empirically, that evaluation harnesses — the orchestration code around model invocation, data loading, metric computation — have their own systematic bug patterns, independent of the agent-benchmark literature entirely | About general ML evaluation-harness engineering (classifier/metric benchmarks), not agent benchmarks and not a benchmark's simulated tool/environment layer; supports the general premise that evaluation infrastructure is buggy in patterned ways, proposes no contract-conformance mechanism and does not touch tool implementations |
| **MIRAGE: Online LLM Simulation for Microservice Dependency Testing** (Zhang) | arXiv:2604.04806, preprint, no venue claim | Uses an LLM to answer each dependency request at test time (reading the dependency's source and production traces) rather than a static record-replay or spec-driven stub, and measures fidelity against real dependency behavior (99% status-code/response-shape fidelity vs. 62%/16% for record-replay) | A mock-fidelity measurement method: quantifies how well a simulated dependency matches the real one it stands in for | Same family as Tiwari/RICK, now for LLM-generated runtime mocks in microservice testing generally, not benchmark tool implementations; measures fidelity of a **mock against a live real dependency**, not an **implementation against its own declared contract** — there is no docstring/schema to check against, only a live reference to match |
| **"Auditing Automated Evaluation, Error Propagation, and Runtime Mitigation in Tool-Using Language Agents"** (Gurram) | arXiv:2604.16706, preprint, no venue claim | Audits substring-heuristic and LLM-ensemble judging of 14,750 agent execution traces against human annotation (kappa agreement), traces parameter-error propagation, and finds some agents **fabricate tool executions** — asserting a tool-derived result was obtained when it never was | The fabrication finding is a striking terminology near-miss to Phantom Effect: a result reported without the underlying action having occurred | The direction is inverted from ours: here the **agent** lies about having called a tool at all (agent-side hallucination, invisible to end-to-end scores because the judge/evaluator trusts the agent's tool-call log); our Phantom Effect is a **tool** that is genuinely called, returns success, and does not write the state it claims to write. Same word, opposite failing component — worth one disposal sentence if a reviewer raises the terminology, same treatment already given to Tool-Veritas's "implementation-specification mismatch" and ContractGuard's "effect forgery" |
| **"The Correctness Illusion in LLM-Generated GPU Kernels"** (Sarkar) | arXiv:2606.20128, preprint, no venue claim | Re-evaluates GPU-kernel-benchmark correctness oracles (KernelBench, TritonBench, GEAK) with a higher-precision, op-schema-aware fuzzing oracle against a seeded corpus of correct and buggy kernels; the standard allclose-style checkers pass seeded bugs that the stricter oracle catches | Another instance of a benchmark's own grading oracle being shown insufficient by an independent, stricter re-check, this time in GPU-kernel benchmarks rather than agent benchmarks | Optional supporting citation only: reinforces the general pattern (grader audited, implementation-under-test/environment untouched) recurring across yet another benchmark domain; does not touch a benchmark's tool/environment implementation and is not agent-benchmark literature |

A sixth item is worth naming for the record without a table row: **ClawsBench** (arXiv:2604.05172, already indexed by
Consensus under a KDD-adjacent venue tag that should be treated with the same skepticism as Agent-Diff's, pending
independent confirmation) names "silent contract modification" as one of eight recurring unsafe-agent-behavior patterns
in its trajectory analysis. This is a second terminology near-miss worth flagging in the same breath as the Gurram
"fabricate tool executions" finding above: ClawsBench's "contract" is a safety/permission boundary the **agent**
silently steps past, not a benchmark tool's own declared precondition/postcondition contract, and the paper proposes no
detector for it beyond manual trajectory coding. No action beyond a one-line disposal if a reviewer raises the phrase.

None of these five-plus-one items forces any change to the core claim. All either audit one layer above the tool
implementation (the grader, the harness, the agent's trajectory) or measure a mock's fidelity against a live reference
rather than an implementation's fidelity to its own declared contract. The verdict from the first pass stands, now on a
broader search base: postcondition/runtime-verification, differential/metamorphic testing, and execution-based-evaluation
angles have all now been run in addition to the original six, and ACM DL and dblp were queried directly (not only via
Consensus's indexing of them) for the Agent-Diff venue check in Part 1, partially closing the original "no ACM/IEEE
direct search" limitation for this one artifact. A general direct ACM DL / IEEE Xplore sweep across the six new angles
was not run (ACM DL's search endpoint returned 403 to direct fetch from this environment); Scopus, which was the
standing rule's next fallback, was not reachable either. Both remain open before the bibliography freezes.

### Part 3 — drop-in related-work subsection

Ready to insert at the position identified in the first pass (after the ToolGate/ABC disposal). Uses only keys already
in `REFERENCES.md`; no new keys were needed for this subsection since the two gap-sweep angles that produced new
citable work (Part 2 above) surfaced nothing strong enough to belong in the main narrative rather than a footnote or
disposal sentence.

> A substantial and independently motivated literature already verifies task completion against recorded environment
> state rather than trusting a returned status. WebArena [webarena24], AppWorld [appworld24], OSWorld [osworld24], and
> AndroidWorld [androidworld25] each grade an agent's episode by inspecting post-episode state — database rows, files,
> or device configuration — rather than accepting the agent's own claim of success, and each verdict depends on whether
> the observed state matches a task-specific target. Read as a body, this line of work treats the environment's own
> tool or application layer as the trusted instrument doing the measuring, an assumption our audit revisits directly.
>
> Two recent preprints come closer to our target than any of the benchmark or task-layer audits disposed of earlier in
> this section. Agent-Diff [agentdiff26] defines what it calls a state-diff contract for agentic code-execution tasks
> against containerized replicas of enterprise APIs: task success is the occurrence of an expected state delta, read
> directly from the replica's own before-and-after database state, rather than inferred from a trace or a returned
> parameter. This is the nearest published articulation of the kind of check a reviewer might expect us to have
> reinvented, and we cite it for that resemblance while noting that, as of this writing, it remains an unaccepted
> preprint under review for KDD 2026. Gao and Zhou [evidencebounds26] instead audit the outcome check itself: their
> worked example, in which a task asks whether a customer's shipping address changed but the check verifies only that
> the agent clicked "Save," shows that a benchmark's own success criterion can accept a superficial proxy for the state
> change it is meant to certify, and they add an evidence-reporting layer atop five existing benchmarks' checkers to
> surface exactly this gap without altering the checkers themselves. Advani [falsesuccess26], accepted to the FAGEN
> workshop at ICML 2026, complements both by comparing agents' own confident claims of task completion against
> tau2-bench's and AppWorld's recorded environment state, showing that large language model judges are unreliable
> arbiters of the resulting gap.
>
> Each of these three, however, treats the layer that writes the state it inspects as the trusted instrument: the
> replica API's implementation for Agent-Diff, the five audited benchmarks' existing checkers for Gao and Zhou, and
> tau2-bench's and AppWorld's own environment for Advani. In one sentence, this literature grades the agent using the
> benchmark's tool implementation as ground truth, whereas we grade the tool implementation itself, re-executing it
> against its own declared preconditions, arguments, and postconditions to ask whether the ground truth this literature
> relies on was ever sound to begin with.

If a reviewer wants the Agent-Diff resemblance addressed even more directly, a fourth sentence can be inserted after the
Agent-Diff sentence above: "Agent-Diff's state-diff contract and our tool-conformance check both compare recorded state
to an expectation, but Agent-Diff diffs state to grade the agent that produced it, taking the replica API's own
implementation as correct; we diff declared contract against implementation to grade the tool itself."
