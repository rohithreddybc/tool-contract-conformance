# Adversarial verification: does the paper answer Zichong's five comments?

Checked against `paper/latex/main.tex` as it currently stands (575 lines, read in full).
Read-only pass; no file other than this report was modified. Line numbers below refer to
`paper/latex/main.tex`.

## Verdict table

| # | Comment | Verdict |
|---|---|---|
| C1 | Opening conflates two evaluation designs | PARTIAL |
| C2 | MedAgentBench defect reframed as agent-visible claim, not missing write | PASS |
| C3 | Consequence certainty matches score-at-risk measure | PASS |
| C4 | Categorical claims about prior work are scoped | PASS |
| C5 | Introduction's centre of gravity is the positive claim | PARTIAL |

Two of five are not fully closed. Detail below.

---

## C1. PARTIAL

**What was fixed.** The class definition genuinely widened in the two places that matter
most. Abstract (line 150): "grade what those calls report having done, as changed state or
as returned results." Introduction paragraph 1 (line 163): "grading what those calls report
having done, whether by reading the state they left behind or by reading the results they
returned, assuming in either case that each call did what its interface said." Both are
two-armed and both appear before the MedAgentBench example, so the example no longer sits
outside the stated class. The method itself also carries the distinction through: Score-at-Risk
step "Field to evaluator" (line 369) explicitly classifies "each read site... by provenance,
live simulator state or agent transcript," and Table `scoreatrisk`'s MedAgentBench row is
tagged `transcript (not state)` rather than folded into the state-based rows. So the mechanism
is not broken.

**What was not fixed.** Two prose passages downstream still frame the paper's own motivation
in state-only terms, contradicting the widened definition and, more pointedly, contradicting
the paper's own central finding (MedAgentBench Finding 4, whose grader is transcript-based, not
state-based).

1. Section III opening (line 284): "A benchmark tool is not application code that happens to
   be simulated; it is the write path of a measuring device... Every deterministic evaluator
   surveyed in §II reads state that tools wrote, so a defective tool's output is inherited by
   any gate reading it... the tool layer needs its own audit." This is the paragraph that
   motivates why the tool layer needs auditing at all, and it is built entirely on "reads state
   that tools wrote" and "write path of a measuring device." It never mentions the
   transcript-reading arm, even though the very next section's flagship example depends on it.
   A reader who reaches §III right after the widened definition in §I could reasonably think
   the widening was abandoned.

2. Conclusion (line 549): "This paper tested a layer the benchmark audits we survey do not
   reach: the tool implementation that produces the state a grader reads." This is the paper's
   own one-sentence summary of what it tested, and it reverts to "the state a grader reads,"
   omitting the transcript case entirely. This is the last characterization of the paper's
   object of study a reader sees, and it is narrower than the class the paper spent the
   introduction widening.

**What it would take to fix.** Add the transcript arm to both sentences, matching the language
already used in §I and in Score-at-Risk step 2 ("state or transcript"). Both are short,
mechanical edits; the content needed to make them consistent already exists elsewhere in the
paper.

---

## C5. PARTIAL

**What was fixed.** The closing paragraph is now one sentence (line 212): "The checker's role
in these findings is confirmation and score-tracing rather than discovery: §V's Surfaced-by
column shows seven of eight findings surfaced manually, one by static check, and the paper's
claim rests on the audit result and the criterion behind it, not on the checker having found
the defects first." The "techniques we did not invent" material has indeed moved to Related
Work §II.C (line 269: "One line of prior work establishes mature contract-checking and oracle
machinery... but none targets the tool-to-agent boundary this paper does," and "Our Ignored
Argument and Partial Effect detectors are metamorphic relations in all but name"). Both of
these match what `ZICHONG-RESPONSE.md` claims was done.

**What was not fixed.** Two structural problems the comment raised survive.

1. **Contribution-list ordering still does not match the motivation.** The motivation
   paragraphs and the entire MedAgentBench worked example are about overlooked tool
   implementation defects. The contribution list (line 202, "in order of importance") still
   places dependency analysis first: item 1 is "Score-at-risk dependency analysis," item 5 is
   "Confirmed findings." This is exactly the mismatch the comment named ("the motivation
   emphasizes overlooked tool implementation defects, the contribution list places dependency
   analysis first"). Nothing in the diff between the old and new introduction touches this
   ordering; only the closing paragraph was shortened.

2. **The introduction still ends its substantive content on a hedge.** After the contribution
   list (the strongest positive-claim block in the introduction), the very next and last
   substantive sentence before the roadmap is the confirmation-vs-discovery disclaimer quoted
   above. It is shorter than whatever preceded it, but a reader still leaves the introduction
   having just read what the checker did *not* do, not what the paper found. Counting the
   introduction's seven paragraphs: paragraphs 1-3 are stakes/gap/example (positive framing),
   paragraph 4 states three challenges (neutral), paragraph 5 is data-quality motivation ending
   in a scope hedge, paragraph 6 is the five-item contribution list (positive), paragraph 7 is
   one hedge sentence plus the roadmap. The introduction's last word on its own contribution is
   still defensive, and the contribution list's first-listed item still does not match what the
   introduction spent three paragraphs motivating.

**What it would take to fix.** Reorder the contribution list so a defect-class or
confirmed-findings item leads, matching the motivation's emphasis, or rewrite the motivation to
foreground dependency analysis instead (the smaller change, since dependency analysis is
arguably the paper's most methodologically novel piece). Separately, either cut paragraph 7
entirely (its content already exists in §V's Surfaced-by column) or move it, so the
contribution list is the last thing the introduction says about what the paper does.

---

## C2. PASS

Every instance found states the defect is the agent-visible claim of execution, never the
missing write itself:

- Abstract (line 150): "a clinical benchmark whose interface tells the agent each write
  executed, under a no-write design its paper documents but its interface does not, and whose
  grader accepts that message as evidence of the write."
- Intro (line 167): "The defect this paper reports is therefore not the missing write, which
  the maintainers chose and documented, but the agent-visible claim that it happened."
- Figure 1's worked-instance box (line 191) and caption (line 194): frames it as the evaluator
  gating "on that reported string rather than on stored state."
- §V Main Results (line 456): "Finding 1 is the unqualified execution claim... so the finding
  is the agent-visible claim, not the omission."
- Taxonomy (Table `taxonomy`, line 297) and Table `findings` row 1 (line 442) both name the
  defect class Phantom Effect ("success signal true ∧ advertised effect delta absent"), a
  definition about the signal, not the absence of a write.

No surviving "no-op" or "missing write is the defect" sentence was found anywhere in the file
(searched explicitly for `no-op`, `missing write`, `absence of writ`, `does not write`, `never
writes`, `writes nothing`).

**Quotation and section-number check against `report/medagentbench-disclosure-check.md`:**
both dispositive quotes match verbatim.
- Line 167: "indicate[s] success of execution to the agent system" (§2.4, §2.4.3 cited) matches
  the disclosure-check's §2.4.3 quote "indicate success of execution to the agent system"
  (bracketed inflection only).
- Line 456: "rule-based sanity checks to verify the correctness of the payload of POST
  requests" (§2.4.1 cited) is an exact match to the disclosure-check's §2.4.1 quote.
- The disclosure-check's other dispositive quote, "we decide to only send GET requests to the
  environment," is not quoted verbatim anywhere in `main.tex`; it appears only as the paraphrase
  "only GET requests reach the environment" (line 167). The paraphrase is accurate, so this is
  not a factual problem, but it is the one strongest disclosure sentence the checker
  specifically flagged as unquoted, and a reviewer holding the source paper open could notice
  the asymmetry (see hostile-reviewer list below).

---

## C3. PASS

Every sentence found that touches consequences for scores keeps certainty at or below what
score-at-risk (an exposure bound) supports:

- Abstract (line 150): "a defect at this layer does not average out: it is present on every
  rerun, and whatever exposure it creates travels with the number into every downstream use."
  "Present on every rerun" is a claim about code determinism (true), not about verdict impact;
  "whatever exposure it creates" is conditional, not asserted.
- Intro (line 200): "a defect in that instrument is, unlike noise, present on every rerun, so
  the exposure it creates travels with the number into every downstream use; what that exposure
  could amount to is what score-at-risk bounds, without asserting that any verdict changed."
  This is the sentence the comment specifically named, and it now explicitly separates presence
  (deterministic) from effect (bounded, not asserted).
- §IV.C (line 373): "It says a verdict could have been computed wrong... not that the verdict
  was wrong."
- §V Main Results (line 456): "we claim no causal link from either defect to any specific
  published number," attached to the tau2-bench lineage claim.
- Conclusion (line 549): "the score-at-risk analysis traced what those defects could have cost
  in published verdicts... an at-risk bound is a due-diligence flag, not a correction to any
  published score."

No surviving "not hypothetical" sentence (searched explicitly; zero matches). No sentence
asserts a verdict changed, only that one could have.

---

## C4. PASS

All three instances the comment named are fixed, and I found no unscoped replacement elsewhere:

- "All stop one layer above the tool body" -> now "each of these stops one layer above the tool
  body" (line 165), where "these" refers to the four just-listed, cited audits
  (`benchguard26`, `aba26`, `toolveritas26`, `safeaudit26`).
- "None of them tests" -> "None of these tests the interface-to-state-transition contract
  itself" (line 165), same scoping, immediately followed by "§II maps their categories" as a
  pointer to the checked list.
- Figure 1's "no single-layer audit sees a defect" -> now "neither tests band 2 against band 1"
  (line 194), scoped to the two named categories in the same sentence (benchmark audits,
  graders), not a sweep over all prior work.

Other categorical-sounding language found elsewhere is likewise scoped to a checked, cited set:
"The five surveyed task/grader-layer audits map zero of six defect classes across 27 categories
(`GATE.md` §2)" (line 418), explicitly labeled "a checkable property of published designs, not
a performance claim"; "none targets the tool-to-agent boundary this paper does" (line 269),
scoped to the specific contract-checking citations in that sentence. The one legitimate
pinned-commit universal survives correctly: "the file containing the POST branch is unchanged
at our pinned commit, touched only once" (line 456) is a claim about one file's git history, not
about a body of literature, and is the kind of universal C4 says is fine.

---

## Additional checks

**MedAgentBench has no contract / validator check 8 never ran.** Disclosed and correctly
scoped, line 456: "No contract exists for this benchmark under `spec/contracts/`, so Finding
1's grounding rests on direct source reading, not validator check 8, recorded in
`FINDINGS-VERIFIED.md` at the pinned commit above." This is not, however, repeated in the
Threats to Validity subsection (§V.G, ten named threats, lines 521-541); the flagship finding's
weaker grounding basis is disclosed once, in Main Results, and not cross-referenced as a threat.
The comment only required disclosure, which is present, so this is not a failure, but it is a
gap worth naming: this is arguably the single most reviewer-visible validity threat in the
paper, and it currently has less prominence than the ten threats that made the dedicated
subsection.

**"Five prior audits" claim.** Gone in the form the comment attacked (a claim that five audits
examined MedAgentBench specifically and found nothing). What replaced it is narrower and
checkable: "neither schema has an entry for a success signal decoupled from state, so neither
could report this instance whether or not it ran on the benchmark" (line 245, about BenchGuard
and Tool-Veritas specifically) and "The five surveyed task/grader-layer audits map zero of six
defect classes across 27 categories" (line 418, a taxonomy-overlap count, not a claim about
what any audit examined). Also absent from the Conclusion (line 549), which makes no prior-audit
count claim at all.

**Load-bearing hedges, presence confirmed:**
- "no causal link" - line 456, attached to the tau2-bench defect-to-published-number claim.
- "not a survey" - line 549, attached to "anchor-driven audits are existence proofs, not a
  survey."
- "existence proofs" - same sentence, line 549.
- "due-diligence flag" - line 549, attached to the at-risk bound.
- "confirmation and score-tracing" - line 212, attached to the checker's role.

All five are present and still attached to the claims they originally qualified; none has been
orphaned or generalized past its original scope.

---

## Hostile-reviewer list (a reviewer who has read MedAgentBench's paper)

Ranked by damage, most first.

1. **Contribution list contradicts the paper's own motivation (C5).** The introduction spends
   three paragraphs and a full worked example on an overlooked tool-implementation defect, then
   lists "score-at-risk dependency analysis" as contribution 1 and "confirmed findings" as
   contribution 5, "in order of importance." A reviewer can quote the paper against itself here
   with no outside knowledge needed; this is the cheapest, highest-yield objection available and
   it was not touched by this revision pass.

2. **§III's motivating claim for the whole project is falsified by its own flagship finding
   (C1).** "Every deterministic evaluator surveyed in §II reads state that tools wrote" (line
   284) sets up the case for auditing the tool layer, but the paper's central example
   (MedAgentBench, Finding 4, Ungrounded Oracle) is graded from a transcript, not from state, and
   the paper says so itself two sections later. A reviewer who reads the paper start to finish,
   the way this task did, will hit this contradiction directly.

3. **The strongest disclosure sentence in MedAgentBench's own paper is paraphrased, not quoted,
   while a weaker one is quoted verbatim (C2 residual).** The paper quotes "indicate[s] success
   of execution" verbatim but only paraphrases "we decide to only send GET requests to the
   environment." Given how much argumentative weight rests on precise engagement with
   MedAgentBench's own words (the whole point of the reframe is that the paper takes that
   disclosure seriously), a MedAgentBench author reviewing this paper could ask why their central
   design-rationale sentence, the one with the actual engineering reason (avoiding a 90-second
   re-initialization), is not quoted.

4. **The flagship finding is the one finding the paper's own validator never checked.** Finding
   1's agent-visibility classification rests on "direct source reading," explicitly not on
   validator check 8, because no contract exists for MedAgentBench. A hostile reviewer can frame
   this as: the paper's best example is the one example its own machinery could not verify,
   undercutting the built-for-rigor framing of the checker elsewhere in the paper.

5. **Scope creep into consumer-side label validity.** §III's benign-simplification principle
   explicitly scopes the paper's claims to "agent-side measurement validity... not consumer-side
   label validity" (line 317). But the MedAgentBench paragraph in §V (line 456) argues "the
   disclosure sits in the paper's evaluation section, not in the label 'action success rate' a
   leaderboard reader sees," which is precisely a consumer-side label-validity claim. A reviewer
   could point out the paper defines away exactly the kind of argument it then makes two sections
   later.

6. **MedAgentBench's own authors can still say "we told you."** Even with the reframe, a
   MedAgentBench author could respond that the tool's generic success acknowledgment is a known
   simplification of a documented sanity-check step, and that any serious user of the benchmark
   reads the paper before using the numbers, so the practical stakes of "the agent doesn't see
   the disclosure" are lower than the paper implies for a benchmark whose primary consumers are
   researchers, not deployed autonomous systems. The paper's own hedges (no causal link,
   due-diligence flag) partially preempt this, but it remains available as a response, since
   nothing in the paper establishes that any published leaderboard decision was actually affected.
