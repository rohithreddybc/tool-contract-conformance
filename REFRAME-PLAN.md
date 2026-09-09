# Reframe plan: the MedAgentBench central example after C2

Written 2026-09-09 against `paper/latex/main.tex` (574 lines, compiles to exactly 10 pages) and
`paper/main.md`. Planning only; neither file has been touched. Line numbers below are current
`main.tex` lines unless marked `md:`.

Inputs: `ZICHONG-COMMENTS.md` (C1 to C5), `report/medagentbench-disclosure-check.md` (verdict b),
`MEETING-2026-09-02-WANG.md`, `FINDINGS-VERIFIED.md` Findings 1 and 4, `GATE.md`, and
`experiments/numbers_audit.py` (currently exits 0; confirmed by running it).

## 0. The decision in four sentences

The missing write is not the defect and the paper stops saying it is. MedAgentBench's paper
documents the no-write design in its own evaluation section with an engineering reason, and our
criterion says a simplification is benign exactly when it is advertised. The defect is the one
thing that criterion still catches: the agent-visible return string asserts execution without
qualification, nothing the agent reads says otherwise, and the write-task grader then accepts
that string as its evidence of record (Finding 4). Finding 1 keeps its class, tier and row;
the paper concedes the disclosure in its own words, moves the defect claim onto the string, and
drops every sentence that presented the missing write as something nobody had said.

This is a concession. Say it as one. The paper currently reads, to anyone who has read
MedAgentBench §2.4, as either unaware of that section or as claiming something it contradicts,
and the standing rule puts a false claim about someone else's code above a weak paper.

---

## 1. What the finding now is

### 1.1 What the paper claims from now on

- **Finding 1 (Phantom Effect, agent-visible tier, row unchanged).** The rule is "success signal
  true and advertised effect delta absent." The signal is the string injected at
  `__init__.py:91`, "POST request accepted and executed successfully"; the advertised effect is
  a FHIR write, carried by the tool schemas translated from the FHIR API and by the word
  "executed"; the delta is absent because no POST reaches the environment. Every element of
  the rule is established on surfaces the agent conditions on. The class, the tier tag
  `agent-visible (prompt_template, tool_return)`, the commit, the line range, and the
  "Surfaced by: manual" cell all stay exactly as they are.
- **What the paper concedes, in its own words, where the example is introduced (§I).**
  MedAgentBench's paper states that only GET requests are sent to the environment so the
  environment need not be re-initialised per task (§2.4), that a POST receives a JSON-loadable
  sanity check after which the harness "indicate[s] success of execution to the agent system"
  (§2.4.3), and that write tasks are graded by rule-based checks on the POST payload (§2.4.1).
  The no-write design is therefore a documented evaluation choice by the maintainers, not an
  oversight, and the paper says so before it says anything else about the benchmark.
- **Why the concession does not dissolve the finding.** The criterion in §III is scoped to
  "what the interface tells the agent." The paper's §2.4 is not part of that interface: the
  agent conditions on the prompt template (call syntax only, Appendix A.2 of their paper), the
  tool schemas (FHIR), and the return string. On that surface the claim of execution is
  unqualified, and it is stronger than the paper's own paraphrase. This is the same line
  tau2-bench's maintainers draw at `airline/tools.py:689` versus `:367`, and the paper already
  uses that contrast; it now applies it to its own central example.
- **Finding 4 is untouched and carries more weight.** The grader gates `extract_posts` on the
  literal "POST request accepted" and never reads FHIR state for a write. That is a claim about
  the evaluator's oracle, not about whether the design was disclosed, and C2 does not reach it.
  The 60 / 90 / 150 / 0 classification, "undefined, never zero," and the Ungrounded Oracle
  property all stand as written.
- **The construct-validity argument about Action SR survives and sharpens.** The disclosure
  lives in §2.4 of the MedAgentBench paper. It does not live in the column label "Action SR,"
  in Table 3, in the NEJM AI abstract's 69.67% headline, or on any leaderboard. A score
  consumer reads the label, not §2.4. The paper already scopes this as consumer-side label
  validity and touches it only where MedAgentBench forces it; the reframing is exactly the
  case that forces it.
- **The proposed repair is on the interface side, and the paper says it is cheap.** Under
  "either side of a divergence may be repaired," the finding resolves if the return string says
  what §2.4.3 says (for example, "POST payload accepted; not executed, evaluation checks the
  payload only") or if the prompt template does. This goes into the 2026-09-10 disclosure text
  to the MedAgentBench maintainers as the proposed fix, ahead of any code change. A reviewer
  who says "so the fix is one string" is agreeing with the paper; the substance is that 300
  write-tagged cases were scored with zero of them state-grounded, and that no cheap fix to
  the string changes a published number.

### 1.2 What the paper stops claiming

- That the missing write was undiscovered, undisclosed, hidden, overlooked, or an
  implementation error. It was chosen and documented.
- That "the loss such stubbing can cause is not hypothetical." Two faults in one sentence:
  "stubbing" implies an accident of mock fidelity (it was a decision) and "loss" asserts a
  consequence score-at-risk only bounds (C3).
- That "five prior audits reported nothing" on this benchmark as if they had looked. `GATE.md`
  records BenchGuard deployed on ScienceAgentBench and BIXBench and Tool-Veritas on four
  families including tau2 Retail; it records no surveyed audit examining MedAgentBench at all.
  The by-construction claim (their category schemas have no entry for a success signal
  decoupled from state; 0 of 6 classes across 27 categories) is true and stays. The empirical
  claim that they missed it is not established and goes.
- That "every write action in this benchmark is a no-op that reports success to the agent" as
  the paragraph's punchline. The sentence is true; its rhetorical job was discovery, and that
  job no longer exists. It is replaced, not softened (see §2, row c).
- The word "fabricated" as the name of the defect in §I. It remains as a mechanism description
  in Table IV, §II, and §V (the string is composed by the harness; no execution produced it),
  because changing it there costs table space for no gain in accuracy. In §I the precise term
  is "unqualified": the defect is that the string is unqualified on the agent's surface, not
  that it was composed.

### 1.3 One pre-existing exposure the reframe rests on, stated so it is not discovered later

There is no MedAgentBench contract under `spec/contracts/` (only `agentdojo`, `mmtoolsandbox`,
`tau2`, `toy`), so validator check 8 has never run on Finding 1's `tool_return` grounding. The
headline tag rests on `FINDINGS-VERIFIED.md`'s manual reading that `session.inject(...)` with
role `user` reaches the agent's message stream. That reading is correct by inspection, and
`CLAUDE.md`'s headline rule ("passes validator check 8") is satisfied vacuously, not
mechanically. This plan does not fix it and does not need to, but the executor should know the
reframed §I leans harder on `tool_return` than the old one did, and that `prompt_template` in the
tier cell contributes call syntax only. Write the prose to rest on the return string and the
FHIR-derived schema, never on the prompt.

---

## 2. Knock-on claims: survives, scope, or cut

Every quoted sentence is from `main.tex` at the line given. Replacement wording is drop-in and
uses no em dash. Word deltas feed §5.

| # | Sentence (location) | Verdict | Why, and replacement |
|---|---|---|---|
| a | "One result shapes the whole argument regardless: MedAgentBench's grader admits evidence only when it matches its own tool's fabricated success string, so five prior audits reported nothing (§II, §V), the same cross-layer blindness this paper is built to catch." (212) | **Cut** | "Reported nothing" implies they audited MedAgentBench; `GATE.md` shows none did. The positive content (grader gates on the tool's own string) moves into §I paragraph 3's last sentence (row c) and is already in §II's single-layer paragraph (row g). Nothing of value is lost by cutting; a false implication is. |
| b | Abstract: "among them a clinical benchmark whose write path performs no write and whose grader confirms that write from the agent's own transcript." (150) | **Scope** | True but leads with the design choice as the discovery. Replace with: "among them a clinical benchmark whose interface tells the agent each write executed, under a no-write design its paper documents but its interface does not, and whose grader accepts that message as evidence of the write." (+13 words) |
| c | "Every write action in this benchmark is a no-op that reports success to the agent." (167) | **Cut and replace the paragraph** | Full replacement of paragraph 3 (line 167), about 165 words against the current 122: <br><br> "One shipped benchmark exhibits the divergence directly. MedAgentBench \cite{medagentbench25} evaluates language-model agents against a simulated electronic health record, and its paper documents a deliberate simplification: only GET requests reach the environment, and a POST instead receives a JSON-loadable sanity check after which the harness ``indicate[s] success of execution to the agent system'' (\S\,2.4, \S\,2.4.3 of that paper). Nothing the agent reads carries that disclosure. The prompt template states call syntax only, the tool schemas are translated from the FHIR API, and the branch handling every write (\texttt{src/server/tasks/medagentbench/\_\_init\_\_.py}, lines 85--91 at commit \texttt{9926011}) parses the payload into a local variable, never reads it again, and injects into the agent's transcript the unqualified string ``POST request accepted and executed successfully''; no code in the repository performs the write (\texttt{git grep send\_post\_request} returns nothing at the pinned commit; \texttt{FINDINGS-VERIFIED.md}). The defect this paper reports is therefore not the missing write, which the maintainers chose and documented, but the agent-visible claim that it happened, on which the benchmark's own write-task grader then relies as its evidence of record (Fig.~\ref{fig:concept}, right; \S\,\ref{sec:experiments})." <br><br> Keep `lines 85--91`, `9926011`, and the `git grep` clause verbatim: the numbers audit extracts line ranges and commit hashes and cross-checks them. Drop "with every \texttt{requests.post} call site in the client-side model transport" (detail is in the artifact) and "the worked instance drawn on the right of Fig. 1" (the figure pointer moves to the end). |
| d | "The loss such stubbing can cause is not hypothetical." (167) | **Cut** | Replaced by the first sentence of row c: "One shipped benchmark exhibits the divergence directly." The divergence is a verified fact; the loss is a bound. Say the fact. |
| e | "\paragraph{MedAgentBench (Findings 1 and 4) is the paper's central chain ...} Finding 1 is the no-op POST branch of §I and Fig. 1. Finding 4 makes it undetectable: ..." (456) | **Scope** | Replace the first two sentences with: "Finding 1 is the unqualified execution claim of \S\,\ref{sec:intro}: the POST branch performs no write, a design MedAgentBench's paper discloses to its readers and its interface does not disclose to the agent, so the finding is the agent-visible claim, not the omission. Finding 4 makes the omission unobservable from inside the benchmark: the grader reconstructs each write from the transcript, admitting evidence only when it matches Finding 1's success string, so no FHIR read ever verifies the write." Then, after the existing §2.4.1 quotation, replace "i.e. the transcript-reconstruction mechanism above. They faithfully measure whether the agent emitted a well-formed POST request, not whether any clinical record changed, not what a leaderboard reader takes ``action success rate'' to mean." with: "i.e. the transcript-reconstruction mechanism above, so the numbers are exactly what that section describes: whether the agent emitted a well-formed POST request, not whether any clinical record changed. The disclosure sits in the paper's evaluation section, not in the label ``action success rate'' a leaderboard reader sees." (+25 words net). Every number, the NEJM AI volume and issue, the "touched only once" clause, and the refsol.py pin stay verbatim; the audit pins them. |
| f | "The file containing the POST branch is unchanged at our pinned commit, touched only once, so every Action SR value was produced under an implementation in which no write occurs." (456) | **Survives** | A fact about the code lineage; the disclosure makes it uncontroversial rather than damaging. Add nothing. |
| g | "\paragraph{Single-layer audits cannot see cross-layer defects} ... BenchGuard's EVAL-MISMATCH and Tool-Veritas's reward-basis mismatch plausibly cover the grader-side class, yet neither found this instance, because a check confined to one layer cannot see a defect that requires comparing two." (245) | **Scope** (also C4) | "Neither found this instance" is unsupported: neither was run on MedAgentBench as far as `GATE.md` records. Retitle the paragraph "A single-layer audit finds each layer consistent here" and replace the second sentence with: "BenchGuard's EVAL-MISMATCH and Tool-Veritas's reward-basis mismatch are the nearest categories on the grader side; neither schema has an entry for a success signal decoupled from state, so neither could report this instance whether or not it were run on the benchmark, and a check confined to one layer finds each layer consistent with itself. That the benchmark's own paper documents the no-write design (\S\,\ref{sec:intro}) changes nothing here: an audit of task artifacts reads what the artifacts say, and the artifacts agree." (+35 words). Optional strengthening, only if verified against arXiv 2607.02577: if Tool-Veritas's four families do not include MedAgentBench, say "neither was run on MedAgentBench" outright. |
| h | Fig. 1 worked-instance node: "the interface reports success, the implementation never writes, and the evaluator gates on that reported string rather than on stored state. Each band agrees with its neighbour, so no single-layer audit sees a defect." (191) | **Scope** (also C4) | "the interface tells the agent the write executed, the implementation performs none, and the evaluator gates on that reported string rather than on stored state. Each band agrees with its neighbour, so a check that reads one band at a time finds nothing inconsistent." Same length to within a word; the node has a fixed 6.2 cm text width inside a `\resizebox`, so keep it that way or the figure grows. Do not add the "paper documents it" parenthetical here; §I carries it. |
| i | Fig. 1 caption: "state-based graders read band 2's output as ground truth" (193) | **Scope** (C1) | "graders read band 2's output, as state or as transcript, as ground truth". Keeps the transcript-grading design inside the class the figure describes. |
| j | §III benign-simplification, third consequence: "except where MedAgentBench's construct-validity result forces the question (§II)." (317) | **Scope** | "except where MedAgentBench forces it: a design disclosed in a paper and on no surface the agent reads is flagged by the same rule that clears line 689 (\S\,\ref{sec:intro}, \S\,\ref{sec:experiments})." (+15 words). This is the one place the criterion is stated, and the reader needs to see it applied to the example the objection targets. |
| k | Conclusion: "disclose every deliberate simplification on the surface an agent reads, since an undisclosed one is indistinguishable from a bug." (549) | **Survives, sharpen** | "disclose every deliberate simplification on the surface an agent reads, not only in the paper that describes the benchmark, since on that surface an undisclosed one is indistinguishable from a bug." (+12 words). After the reframe this is the paper's thesis sentence; it should name the contrast the central example turns on. |
| l | Table IV row 1: "``\ldots executed successfully'' fabricated; payload never re-read." (442) | **Survives** | Accurate as a mechanism description; table space is the scarcest resource in the paper. Leave the cell alone. |
| m | Abstract: "Those audits inspect tasks, gold solutions and graders, but not the tool implementation, so a benchmark whose tool reports success without changing any state can score it as correct." (150) | **Survives** | Already describes the reframed defect (reports success without changing state), and is neutral on whether the design was disclosed. |
| n | `md:127` "To be precise: the numbers are not wrong." and the surrounding paragraph in `paper/main.md` | **Scope** | Mirror row e; keep "the numbers are not wrong" (it is now the correct register) and add the disclosure sentence. |

Grep list for the executor, all in `main.tex`, to confirm nothing is left behind after the edits:
`stubbing`, `not hypothetical`, `no-op`, `five prior audits`, `reported nothing`, `neither found`,
`no single-layer`, `all stop`, `None of them`, `propagates into every`, `replicates on every`,
`corrupts a published number`. Each should return zero hits or a deliberately retained line.

---

## 3. Is the paper stronger or weaker?

Stronger on the argument, weaker on the sound bite, and the trade is the right one because the
sound bite was never safe.

**The case that it is stronger, which I hold.** The paper's thesis is not "benchmarks have
bugs." It is that the agent-facing interface is the measurement surface, that a divergence
between what that surface says and what the implementation does corrupts the measurement, and
that disclosure counts only when it happens on that surface. An ordinary bug (tau2's
`refuel_data`) illustrates the first two points and says nothing about the third; nobody chose
it. MedAgentBench after the reframe illustrates all three: the maintainers chose the
simplification, documented it for human readers with a reason, left the one surface that
determines agent behaviour saying the opposite, and then built a grader that takes that
surface's word. That is the purest available instance of "disclosed is not advertised," and it
makes the benign-simplification principle load-bearing rather than a defensive paragraph. It
also converts the maintainers' most likely reply ("we said so in §2.4") into the paper's own
point: saying so in §2.4 is not saying so to the agent, and the grader did not read §2.4 either.
The score consequence is unchanged in every number: 300 write-tagged cases, 0 state-grounded,
Action SR labelled as action success. The title, "Do Agent Benchmarks Do What They Say?",
fits better than before, since this benchmark says one thing in its paper and another to its
agent.

**The case that it is weaker, stated fairly.** "A clinical benchmark performs no writes" was the
most quotable sentence in the draft, and it goes. A reader skimming for a headline now gets a
two-clause claim (the interface asserts execution; the paper admits none occurs) instead of a
one-clause one. Some reviewers will read "the maintainers documented it" and discount Finding 1
to a wording complaint, and the paper cannot stop them; it can only put Finding 4 and the
0-of-300 grounding result immediately behind it, which §V already does.

**What the old headline would have cost.** It was a claim the paper's own criterion does not
support, in a section any MedAgentBench author or reader would check first. The worst outcome
named in the brief is a paper that keeps such a claim. Losing a sentence is cheaper than losing
the review.

**How the abstract should lead as a result.** Keep the five-part order Wang set. The stakes and
gap sentences stay. The headline sentence (row b) leads with the interface-versus-paper
disagreement, not the missing write, and names the grader in the same breath. Do not put the
word "disclosed" or "documented" anywhere in the abstract except in that one subordinate clause;
the abstract's job is the divergence, and the concession belongs in §I where the quote can sit
next to it.

---

## 4. C1, C3, C4, C5 in the same pass

### C1. The class of evaluation designs

Decision: the opening describes the class by what both designs share, which is that the verdict
is computed from the tool layer's output, read either as changed state or as returned results.
Under that description tau2 (state hash, per-task assertions) and MedAgentBench (transcript
gated on the return string) are two ends of one class, and the shared assumption, that the
output is faithful to the interface, is the one the paper tests. Fig. 1 already says
"state / transcript → verdict"; the prose catches up with the figure.

- Abstract sentence 2 (150): "execute its tool calls against a simulated environment and read
  the resulting state" becomes "execute its tool calls against a simulated environment and grade
  what those calls report having done, as changed state or as returned results." (+9)
- §I paragraph 1 (163): "A benchmark scores an agent by executing its tool calls against a
  simulated environment and reading the state those calls leave behind, assuming each call
  changed the world the way its interface said. That assumption sits underneath every
  leaderboard position and model-selection decision the field builds on the resulting number."
  becomes "A benchmark scores an agent by executing its tool calls against a simulated
  environment and grading what those calls report having done, whether by reading the state
  they left behind or by reading the results they returned, assuming in either case that each
  call did what its interface said. That assumption sits underneath every leaderboard position
  and model-selection decision built on such a benchmark's number." (+14). The last clause is
  the scoping C1 asks for: "every leaderboard position" becomes every one built on a benchmark
  of this class.
- Fig. 1 caption: row i above.
- §III paragraph 1 (284): "Every deterministic evaluator surveyed in §II reads state that tools
  wrote" is already scoped to state-based evaluators and survives; MedAgentBench is handled by
  the Ungrounded Oracle paragraph that follows. No change.

### C3. Certainty of the consequence claims

Decision: distinguish presence from effect everywhere. A deterministic defect is present on every
rerun; that is a fact. Whether it changed any verdict is what score-at-risk bounds; that is
never asserted. Wording:

- Abstract (150): "a defect at this layer propagates into every downstream use of the number
  it produced" becomes "a defect at this layer does not average out: it is present on every
  rerun, and whatever exposure it creates travels with the number into every downstream use."
  (+10)
- §I data-quality paragraph (200): "a defect in that instrument propagates into every downstream
  use and, unlike noise, replicates on every rerun" becomes "a defect in that instrument is,
  unlike noise, present on every rerun, so the exposure it creates travels with the number into
  every downstream use; what that exposure could amount to is what score-at-risk bounds, without
  asserting that any verdict changed." (+25). The sentence carries no at-risk figure, so the
  audit's lexical rule does not fire on it; it still avoids "wrong" and "misgraded" by design.
- §I (167): "The loss such stubbing can cause is not hypothetical." Cut (row d).
- §III paragraph 1 (284): "a defective one corrupts a published number silently and reproducibly
  rather than filing an issue" becomes "a defect in one enters a published number silently and
  on every rerun rather than filing an issue." (0). Zichong did not flag this sentence; it has
  the same fault and a reviewer will find it.
- Conclusion (549): "an at-risk bound is a due-diligence flag, not a correction to any published
  score" already has the right certainty. No change.

### C4. Categorical claims about prior work

Decision: every claim about prior work is scoped to the set the paper checked (`GATE.md` §2,
the cited works) and is stated as a property of their published category schemas, which is
checkable, never as a report of what they did or did not find on a benchmark they may not have
run. The abstract already does this ("the audits we survey do not test"); the three survivors
are brought to the same form.

- §I paragraph 2 (165): "Prior audits examine task instructions, gold solutions, evaluation
  scripts, environment configurations, graders, and judges \cite{...}, but all stop one layer
  above the tool body and treat its implementation as ground truth: a grader inspecting sandbox
  state inherits any defect in the tool that wrote it. None of them tests the
  interface-to-state-transition contract itself." becomes "The benchmark audits we survey
  examine task instructions, gold solutions, evaluation scripts, environment configurations,
  graders, and judges \cite{...}; each of these stops one layer above the tool body and treats
  its implementation as ground truth, so a grader inspecting sandbox state inherits any defect
  in the tool that wrote it. None of these tests the interface-to-state-transition contract
  itself; \S\,\ref{sec:relwork} maps their categories." (+7). "Each of these" over a cited,
  checked set is what the co-author asked for in round one ("most" unless every case was
  checked; every case here was checked, so "each of these" is honest and "all" is not).
- Fig. 1 node (191): row h. "so a check that reads one band at a time finds nothing
  inconsistent" is definitional, not empirical.
- §II single-layer paragraph (245): row g, including the retitle.
- §V.B baseline (2) (418): "The five surveyed task/grader-layer audits map zero of six defect
  classes across 27 categories (GATE.md §2) ... a checkable property of published designs, not
  a performance claim" is already in the correct form and is the model for the others. No change.

### C5. Where the introduction's centre of gravity sits

Diagnosis. The introduction has three candidate centres: the motivation (untested tool layer),
contribution 1 (score-at-risk), and the closing paragraph (the checker mostly confirmed; we did
not invent the technique; one result shapes everything). The first two are compatible: the
motivation says published numbers rest on an untested layer, and score-at-risk is the
deliverable that connects a defect at that layer to the numbers it can reach. The third pulls
away from both, and it is the one the reframe empties out anyway (its "one result" sentence is
row a).

Decision: do not reorder the contribution list. Reordering would put it out of step with
§IV.C ("the paper's central deliverable is not a violation count but a trace"), Fig. 2, and the
abstract's approach sentence, all of which end on the trace as the consequence layer; three
edits to fix a mismatch that one cut resolves. Instead make the worked example visibly need
contribution 1, and cut the closing paragraph to the one honest sentence that belongs early.

- The reframed §I paragraph 3 (row c) ends on the grader relying on the string as evidence of
  record. That is the output of the trace's step 2 (field to evaluator, read sites classified
  by provenance), which is what turns Finding 4 from an observation into the 60/90/150/0
  result. The example now demonstrates contribution 1 rather than sitting beside it.
- Closing paragraph (212). Replace the whole 139-word paragraph with: "The checker's role in
  these findings is confirmation and score-tracing rather than discovery: \S\,\ref{sec:experiments}'s
  Surfaced-by column shows seven of eight findings surfaced manually, one by static check, and
  the paper's claim rests on the audit result and the criterion behind it, not on the checker
  having found the defects first. The rest of the paper proceeds section by section: related
  work, notation and taxonomy, method, experiments, and conclusion." (about 65 words, so
  minus 74). Keep the phrase "seven of eight findings surfaced manually, one by static check"
  verbatim from the current text so the md/tex numeric equivalence check sees the same tokens.
- Where the cut material goes. "We did not invent design by contract, contract inference, or
  benchmark auditing" is already the opening claim of §II.C ("mature contract-checking and
  oracle machinery ... none targets the tool-to-agent boundary"); nothing to move. "One result
  shapes the whole argument" is row a; its content is in §I paragraph 3 and §II. The full
  confirmation-versus-discovery discussion already lives in §V.B baseline (1) and the
  Surfaced-by column; the introduction keeps one sentence of it, which satisfies the earlier
  internal review's request that the distinction be surfaced early without giving it the last
  word.
- Contribution 5 gets no change; "eight verified instances confirmed at a pinned commit" is
  already honest about confirmation, and adding "seven surfaced manually" there would duplicate
  the closing sentence.
- Paragraph count. After the cut the introduction is: stakes, prior audits, worked example,
  three challenges, data-quality framing, approach plus contributions, closing. Wang's four-beat
  template is met in order; the paragraph count stays above four, which `WANG-REVIEW-AUDIT.md`
  already records as the accepted partial. Do not spend this pass on merging paragraphs.

---

## 5. Page budget

The PDF is 10 pages. Page 9 ends with the Conclusion and the AI-tools placeholder; page 10 holds
the disclosure placeholder and the 50 references under `\balance`, both columns full. There is
no slack, and the two placeholders will add roughly 127 words (63 and 64 in the commented prior
wording) when written, which is a pre-existing debt this plan does not create but must not
worsen. Estimates use about 9.5 words per line and 55 lines per column.

### 5.1 Additions and cuts from §§2 to 4

| Edit | Words | Lines |
|---|---|---|
| Abstract: C1 sentence 2 (+9), C3 sentence 5 (+10), headline sentence (+13) | +32 | +3.5 |
| §I ¶1, C1 | +14 | +1.5 |
| §I ¶2, C4 | +7 | +1 |
| §I ¶3, full replacement (row c) | +45 | +5 |
| §I data-quality ¶, C3 | +25 | +2.5 |
| §I closing ¶, C5 | −74 | −8 |
| Fig. 1 node and caption | 0 | 0 |
| §II single-layer ¶ (row g) | +35 | +3.5 |
| §III ¶1, C3 | 0 | 0 |
| §III benign-simplification tail (row j) | +15 | +1.5 |
| §V central chain (row e) | +25 | +2.5 |
| Conclusion (row k) | +12 | +1.5 |
| **Net** | **+136** | **about +14** |

A quarter column. It has to be displaced, and the displacements must change no number, bound,
denominator, citation, limitation, or table row.

### 5.2 Displacement reserve, in the order to draw on it

| # | Cut | Location | Words | Why it is safe |
|---|---|---|---|---|
| 1 | "This is a prospective observation, not a measurement of what shipped benchmarks discard or cost." | §I ¶2 (165) | −16 | §II.C's last sentence makes the same distinction ("names our symptom while auditing nothing"). |
| 2 | "A framework reporting the sweep that found its own holes earns more trust than one presented as complete; the cost, one refreeze cycle, is stated plainly rather than absorbed into the total." | Threats, refreeze paragraph (541) | −34 | Rhetorical; the limitation itself, and the ranking sentence after it, stay. §IV.B already says "one disclosed refreeze cycle." |
| 3 | "This is the strongest number in this section and licenses nothing about recall: a detector that never lies about what it catches can still catch very little of what it should, and unlike the AGORA+ reference point above, it structurally cannot false-positive against a clause it never wrote." → "This number licenses nothing about recall, and unlike the AGORA+ reference point it structurally cannot false-positive against a clause it never wrote." | §V Precision paragraph | −25 | Same claim, same citation, no number touched. |
| 4 | "``Score-at-risk'' borrows value-at-risk's shape without its probability content, a static reachability over-approximation and not a probability distribution." | §IV.C (373 region) | −22 | The next sentence ("It says a verdict could have been computed wrong ... not that the verdict was wrong") carries the same content. Check the survivor still satisfies the lexical rule; it does ("could have been ... not that"). |
| 5 | "and a check built against a wrong surface inherits the error" and ", not a maintainer to ask" | §I three-challenges ¶ (198) | −15 | Both are flourishes on challenges that are fully stated without them. |
| 6 | "The four findings sets are existence proofs that the defect classes occur in shipped, audited artifacts, not a survey of frequency." | Threats, anchor-driven (535) | −22 | The Conclusion says it verbatim in substance ("anchor-driven audits are existence proofs, not a survey"). The limitation paragraph stays. |
| 7 | Abstract: ", its docstring, schema, prompt text and return value," | 150 | −8 | §I lists the four surfaces twice already. Use only if the abstract itself spills. |

Reserve total: −142 words, which covers the +136 with about half a line to spare. Draw items 1
to 4 first (−97) and recompile; if the intro still pushes a line onto page 2 that page 2 cannot
absorb, take 5 and 6.

### 5.3 The placeholders, named so they are not forgotten

The AI-tools and disclosure statements are outside this plan but will cost about 13 lines when
written, and page 10 has nowhere to put them. Recommendation, to be decided with the co-authors
rather than executed here: write each at about 35 words (state the fact and point at
`report/disclosure_log.md`; the reporting rule for non-response is already in that file and
need not be repeated in the paper), and take the remaining lines from Threats' refreeze ranking
sentence and the Precision paragraph's AGORA+ clause if item 3 above was not already used.
Template spacing is not to be touched; that was tried and reverted.

---

## 6. Execution order and checks

1. Edit `main.tex` in this order, so that each step's compile is attributable: §I ¶3 (row c) and
   row d; §I closing ¶ (C5); abstract (rows b, C1, C3); §I ¶1 and ¶2 (C1, C4); data-quality ¶
   (C3); Fig. 1 node and caption (rows h, i); §II single-layer ¶ (row g); §III ¶1 (C3) and
   benign-simplification tail (row j); §V central chain (row e); Conclusion (row k); then the
   reserve items in §5.2 order until the compile returns 10 pages.
2. Mirror every edit into `paper/main.md` at the corresponding lines (`md:32` abstract, `md:76`
   ¶1, `md:80` ¶3, `md:96` closing, `md:127` published numbers, `md:164` benign-simplification,
   `md:166` Ungrounded Oracle untouched, `md:277` central chain, `md:316` conclusion). The
   numbers audit reads `main.md` first and diffs numeric tokens against `main.tex`; a wording
   change that keeps the tokens is safe, a token that appears in one file and not the other is
   INFO, a token with different values is FAIL.
3. After each file: `PYTHONPATH=. python experiments/numbers_audit.py` must print "No FAIL
   verdicts" and exit 0 (it does today). Tokens the edits touch and must keep verbatim:
   `lines 85--91`, `9926011`, `seven of eight findings surfaced manually, one by static check`,
   the NEJM AI `vol.\ 2, iss.\ 9`, `0.00\% to 71.33\%`, `69.67\%`, `12 evaluated models`,
   `60/90/150/0`, `300`.
4. Em dashes: `grep -cP "\x{2014}" paper/latex/main.tex paper/main.md` and `grep -c -- "---"
   paper/latex/main.tex` outside the `85--91` line range must both stay at zero (current: 0
   and 0). Use commas,
   colons, semicolons, and parentheses as the rest of the draft does.
5. Compile: `pdflatex`, `bibtex`, `pdflatex`, `pdflatex` in `paper/latex/` (MiKTeX is on the
   path). Confirm `Output written on main.pdf (10 pages` in `main.log`, no undefined references
   or citations, and that Fig. 1 has not drifted later than the page it occupies now.
6. Grep list from §2 returns zero unintended hits.
7. Run `make reproduce-results` (or `python reproduce.py`) once at the end; it includes the
   audit, the table diffs, and the test suite, and nothing here touches a generated table.
8. Commit `paper/` only after step 7 is green.

### 6.1 Outside the manuscript, and time-critical

- **Disclosure text for MedAgentBench goes out 2026-09-10.** It must use the reframed language:
  concede §2.4 and §2.4.3 in the first paragraph, state that the report concerns the
  agent-visible return string and the grader's reliance on it, and propose the interface-side
  repair (qualify the string or the prompt template) as a full resolution under the paper's own
  criterion, with the Action SR label caveat as the second request. Sending the old framing
  tomorrow and reframing the paper next week would put the two on record contradicting each
  other. `report/disclosure_log.md` needs no row change (Findings 1 and 4 are still what is
  disclosed).
- `FINDINGS-VERIFIED.md` Finding 1's "Consequence" line ("every write action in MedAgentBench
  is a no-op that reports success") should gain a dated addendum recording the three disclosure
  passages and the reframed defect statement, so the ledger and the paper agree. This is a
  record file, not the manuscript; it is not under this plan's no-edit constraint, but leave it
  until the manuscript edits are done so the two are written from the same wording.
- `PAPER-OUTLINE.md:99` and `RESTRUCTURE-PLAN.md:230` both carry the "five prior audits missed
  this" framing. They are planning records; add a one-line pointer to this file rather than
  rewriting them.

---

## 7. What this plan deliberately does not do

- Does not change Finding 1's class, tier, commit, line range, or Surfaced-by cell; does not
  add a seventh class or promote Ungrounded Oracle; does not touch any of the eight findings
  rows, the six disposal rows, the taxonomy table, the ten limitations, any bound, denominator,
  basis tag, or citation key.
- Does not soften the benign-simplification principle to accommodate reader-facing disclosure.
  The principle is right as written; the paper had failed to apply it to its own example.
- Does not argue about the MedAgentBench authors' intent. Under the criterion, intent is
  irrelevant and the surface is everything; the paper should not speculate that "success" was
  meant to mean "payload accepted."
- Does not reorder the contributions (§4, C5).
- Does not touch template spacing.
