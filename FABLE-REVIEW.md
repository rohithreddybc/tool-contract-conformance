# Independent review: "Do Agent Benchmarks Do What They Say?"

Target as reviewed: IEEE BigData 2026, Intelligent Data Mining special session. Read-only pass over `paper/latex/main.tex` (589 lines) and the compiled `main.pdf` (10 pages, 2026-09-11 build), against `VENUE-AND-COAUTHOR-STYLE.md`, `ZICHONG-COMMENTS.md`, `ZICHONG-VERIFICATION.md`, `VENUE-CALL.md`, `STRENGTHEN-PLAN.md` and the four-pass review skill. Nothing was edited.

## 0. What the evidence on disk does and does not support

The task brief describes evidence the file does not yet contain, and in two places the brief's numbers contradict the file. State this before anything built on it.

| Brief says | `VENUE-AND-COAUTHOR-STYLE.md` on disk (1,241 words, written 20:22 today) |
|---|---|
| Four session papers measured | Three papers measured, Paper 4 "(pending)". All three are **BigData 2024 main-track**, not Intelligent Data Mining session papers; the file says so and says no session paper list could be found. |
| Venue abstracts run 175 to 190 words | The file's own counts: 275, 220, 207. Our abstract is 257 by my count (`main.tex` lines 161-163), 259 by the brief's. On the file's numbers ours is **inside** the sample range, not 70 words over it. |
| No venue paper enumerates or bolds challenges, 0 of 4 | BanglaDialecto enumerates two challenges with bold inline lead-ins, "(a) ... (b) ...", in its Section III, not its introduction. So 0 of 3 in the introduction, 1 of 3 in the paper. |
| Zichong Wang and Wenbin Zhang conventions across eight papers | Part 2 "(pending)". Nothing on disk. The RQ-in-3-of-3 and three-contributions-in-4-of-4 counts are unverified by me. |
| RQ framing in 1 of 4; limitations section in 1 of 4; thematic related-work subsections in 4 of 4 | Consistent with the three papers measured (0 of 3 RQ; 1 of 3 dedicated limitations paragraph; the related-work count is not in the file). |

I proceed on the brief's stated facts where the file is silent, marking them unverified, and on the file where the two disagree. None of the four tension decisions below turns on the disputed numbers; I checked each against the case where the brief is right and the case where the file is right.

One more caveat that changes the scores: `VENUE-CALL.md` (today) recommends withdrawing this session as the target in favour of the SE4AgenticAI workshop. I score for the session as instructed and give the alternative in one line.

## 1. Scores

| Axis | Score | One line |
|---|---|---|
| Novelty | 7 | Target novelty (the tool body, graded against its own advertised surface) is real and defended against the two closest preprints; technique novelty is conceded in §II.C, correctly. |
| Technical soundness | 7 | Deterministic, pinned, pre-registered, with a `--verify` re-derivation; docked because the flagship finding is the one the checker never ran on (no MedAgentBench contract), and the real-benchmark open-world arm has no denominator. |
| Evidence strength | 5 | The audit evidence is strong and mechanistic (quoted source, line numbers, pinned commits). The instrument evidence is weak: recall lower bounds of 0.000 to 0.359, escape rate at least 0.956 on the toy domain, zero verdict flips. |
| Integrity | 9 | Best in class: every count carries its denominator, exclusions are labelled, the refreeze is disclosed. Docked one point because internal provenance notes leak into the compiled bibliography (§5, D1) and the keyword "data cleaning" is not earned by the body. |
| Venue fit | 4 | The session's topic list has no entry for testing, evaluation, benchmark validity or audits; the paper reaches it through one bridge paragraph and two keywords. The paper's own venue memo reaches the same conclusion. |
| Writing and readability | 6 | Sentence-level prose is good and specific; the results section is a wall of numbers each followed by two disclaimers, and the thesis is restated four times before page 3. |
| Reproducibility | 9 | Zenodo DOI, offline `make reproduce-results`, numbers audit, pinned upstream commits, a pinned copy of the missing `refsol.py`. |
| Significance | 6 | An existence proof on four benchmarks, one of them with published NEJM AI numbers whose "Action SR" the paper shows measures payload well-formedness. No prevalence claim, by design, which caps the reach. |

**Overall: 6 of 10, borderline.** Weak accept on merit in a pool that understands mutation analysis; at this session the fit score dominates.

**Acceptance probability at the Intelligent Data Mining session: about 30%.** The mechanism: a reviewer who has already decided the paper is off-topic reads recall of 0.020 and an escape rate of 0.956 as "the method does not work", and the ten disclosed limitations as the reasons why. At SE4AgenticAI, where the topic list names testing and verification, the same paper is roughly 60 to 65%, because the same numbers read as a careful evaluation. That is the single largest lever on this paper and it is not a writing lever.

## 2. The four tensions

### T1. Bold challenges: the co-author's request wins. Keep them.

The evidence against is absence in a sample of three or four main-track papers, and absence is not a prohibition. The evidence for is a named co-author's explicit request, the ICDM 2023 paper he supplied, and the FairGEM NeurIPS paper, all measured. A co-author who reviews in this community is a better estimator of what this session's PC rewards than three main-track papers that are not from the session. The format is also inside what the template and the review skill already allow: bold run-in labels of 5, 4 and 9 words, each followed by unbolded prose (Pass 4, 7d).

The paragraph earns its place on content grounds too, which is the test that matters. The three challenges map one-to-one onto Method stages A, B, C (§IV's first paragraph says so), so they are the reader's key to the method section, not a convention satisfied. They are also specific to this paper's angle: "no contract exists to check against" is not a difficulty a state-based grader faces.

One weakness, and I would leave it: the third challenge's explanation is a single 16-word sentence where the exemplar gives three or four. Adding one costs 1.5 lines the paper does not have, and the score-at-risk paragraph three lines later explains it anyway. Right as it stands.

### T2. RQ framing: the venue wins. Do not add it.

Three reasons, any one sufficient. First, the RQ-framed papers in the co-author's record are, on the brief's description, method papers with baselines and ablations, where RQ1 "does it beat the baselines" and RQ2 "which component matters" are the natural spine. This paper's experiments are a findings ledger plus five pre-registered arms whose licence is fixed in `detector_analysis_plan.md`; recasting arms as questions invites the reader to answer them, and the honest answer to "does the checker detect defects?" is the 0.020 row. Second, the co-author has not asked for it. Where Zichong Wang made requests, they were C1 to C5, all about claim support; a convention in his own papers is not an instruction for this one. Third, RQ headers cost four to six lines of a paper with none to spare, for a navigational benefit that one orienting sentence buys more cheaply (fix F7 below).

### T3. The ten limitations: keep all ten headings; cut the six that restate results to one sentence each.

This is not a split. The venue convention (1 of 4 with a dedicated section) loses on the merits: for a paper whose instrument numbers are this weak, Threats is the only section that converts "0.020" from a failure into a measured, pre-registered result with a named cause. The author's three methodological rejections were for defects reviewers found, not for defects the author disclosed. And Pass 2 rule 7 does not say "have fewer limitations"; it says a fact stated where it is a fact reads as description, and the same sentence under a Threats heading reads as confession.

Apply that test to the ten. Four are new information at that point in the paper and stay at full length: **Subprocess exception boundary**, **Anchor-driven benchmark selection**, **Frame-grammar expressiveness gap**, **Repository history limits**. Six restate a result the reader met two pages earlier, sometimes verbatim:

| Threat | Already stated at | Restated words |
|---|---|---|
| Taxonomy coverage | §V.E.f (0.956, the three-way decomposition) | 77 |
| Real-benchmark escape rate | §V.E.g (465 / 2,325 / zero live) and the 29-of-33 sentence after Table VI | 76 |
| Sample size shortfall | §V.E.e ("only M-PRECOND and M-IGNARG met the ~25-per-class target") | 63 |
| No real-tool reset site | the paragraph after Table VI, including the sentence "the honest report is 'no data,' not a rate of zero", which appears in both places | 57 |
| Provisional replay sample size | §V.E.h ("five per finding", "all 1,120 ... issue the same one", "nothing in the benchmark prevents an agent") | 68 |
| Disclosed refreeze cycle | §IV.B, and the two point at each other (D3 below) | 77 |

Reduce each of the six to its bold label, one sentence of the limitation itself, and a section pointer. Worked example, first entry:

> Current (77 words): "**Taxonomy coverage.** The taxonomy is not the space of possible defects, and the open-world arm measures the gap rather than closing it. The open-world arm on the toy domain found the checker missing a Wilson lower bound of 0.956 of behaviourally live mutants, decomposed above into unwritten-clause, unreached-state, and checker-crash causes. Six classes, even perfectly detected, would still miss most of what an operator with no knowledge of the taxonomy can break, a limitation the paper's own numbers state."
>
> Replacement (38 words): "**Taxonomy coverage.** Six classes are not the space of defects: on the toy domain (§V.E.f) the checker misses a lower bound of 0.956 of live mutants, most of them through clauses the taxonomy never wrote."

Same treatment for the other five. The ranking sentence that closes "Disclosed refreeze cycle" is the best sentence in the subsection and stays. Net: roughly 20 lines freed, every limitation still present, every number still in the paper once. A data-mining reviewer now meets 0.956 once, in results, with its cause, rather than twice.

Do not add the eleventh threat that `ZICHONG-VERIFICATION.md` names (the flagship finding rests on source reading, not validator check 8). It is stated in §V.E.b where it is a fact. Under a Threats heading it becomes the hostile reviewer's fourth point, handed over.

### T4. Five contributions against the co-author's three: three wins, findings first.

The count is not the reason; the structure is. Items 1 and 3 of the current list are both "the method" (score-at-risk is stage C of the pipeline item 3 describes), item 4 is the evaluation of item 3, and items 2 and 5 are the two things a reader will cite. Five items with no hierarchy is what left C5 half-open: `ZICHONG-VERIFICATION.md` still records that the list leads with dependency analysis while the motivation, the worked example, the title and the conclusion all lead with the audit result. Three items, findings first, closes C5 and matches the title.

Replacement for lines 216-226 (`The contributions:` through the roadmap sentence):

> The contributions:
> 1. **An audit result.** Four shipped benchmarks tell an agent things their implementations do not do: eight verified instances at pinned commits, four headline-eligible benchmark-class cells, seven surfaced by source reading and one by static check, all confirmed under contract and disclosed to every maintainer (§V).
> 2. **A criterion and a taxonomy.** Six defect classes defined as checker rules over `(pre, post, args, result)`, and a benign-simplification criterion that separates a disclosed simplification from an undisclosed divergence by whether the agent can see it; Phantom Effect and Partial Effect have no counterpart in any surveyed audit taxonomy (§III).
> 3. **A method with a validated instrument.** Contracts whose every clause cites the advertised surface it operationalizes, a static and dynamic checker, and a score-at-risk trace from a confirmed defect to the task verdicts that read the state it should have written, each bound tagged by evaluator basis; precision and recall against taxonomy-shaped and off-taxonomy injected defects under a pre-registered plan (§IV, §V).
>
> The paper proceeds through related work, notation and taxonomy, method, experiments, and conclusion.

This absorbs the "confirmation rather than discovery" sentence into item 1 as a clause, which is where the skill says it belongs (Pass 1, rule 5), so the introduction's last substantive words are the contribution list. The current closing paragraph (lines 226) goes; its second sentence ("What the paper establishes ...") is now item 1. Saves about four lines.

## 3. Read as a reader

**Where it holds.** The title. Page 1, column 2: the MedAgentBench paragraph is the best writing in the paper, and it is good because it is specific: `__init__.py` lines 85-91, `git grep send_post_request` returning nothing, the unqualified string quoted. The benign-simplification principle in §III, set off as a block quote, is a real idea stated in two sentences. "Eight bugs in one copied helper is one bug." The `!!!` in Table IV row 3. The §V.E.b paragraph that walks from the POST branch to a 71.33% "Action SR" in NEJM AI. The last sentence of the conclusion. These are the passages a reader will quote.

**Where it loses one, in page order.**

1. **Abstract, sentences 5 to 7.** "Benchmark scores are published data that the field aggregates ... A defect at this layer therefore does not average out: it is present on every rerun. Whatever exposure it creates travels with the number into every downstream use." Three sentences to make one point the reader accepted at sentence 4. Replace all three with: "Because a score is reused as data in leaderboards and model selection, a defect at this layer does not average out: it is present on every rerun and travels with the number." Abstract goes from 257 to about 235 words. Do not cut to 190; that costs the closing example, which is the abstract's reason to exist.

2. **Introduction, the data-quality paragraph** (line 212). "the context the data-quality dimensions literature judges a product against [7]. This paper audits that provenance, formalized for a query by dependency-analysis research [8]." This is the one paragraph in the paper written at a programme committee rather than to a reader; both citations are introduced and never used again. It is also the bridge to the session, so it cannot go while the session is the target. Make it one sentence in the session's own words and move the `bunemantan01` citation to §IV.C where dependency analysis is defined, as `VENUE-CALL.md` already proposes.

3. **The thesis is restated four times before §III.** Intro paragraph 2 ("stops one layer above the tool body"), Fig. 1 caption ("neither tests band 2 against band 1"), §II.B's lettered paragraph ("A check confined to one layer finds each layer consistent with itself"), §III's opening ("Consistency between a broken tool and its grader is not validity"). The reader who is with you at the first has heard it; the reader who is not is not persuaded by the fourth. Cut the Fig. 1 caption to two sentences (it repeats intro paragraph 3 nearly verbatim, and at five lines it is a paragraph in the wrong place) and cut the §II.B paragraph's first three sentences, which repeat the intro. Keep the §III line; it is the best of the four.

4. **§III, third consequence** (line 331): "scoped to **agent-side measurement validity**, audited throughout, not **consumer-side label validity**. The line-689 update is a true negative because the agent sees it, whether or not any score consumer does, except where MedAgentBench forces it. There, a design disclosed in a paper and on no surface the agent reads is flagged by the same rule that clears line 689." I stopped here and re-read three times. "Except where MedAgentBench forces it" reads as an exception to the rule, when the next sentence says the rule applies unchanged. Replacement for the last two sentences: "Line 689 is a true negative because the agent sees the disclosure. MedAgentBench's no-write design is disclosed in a paper and on no surface the agent reads, so the same rule flags it." Drop the two bolded terms; they are defined here and used nowhere else.

5. **§IV.B** opens with a confession the reader has no context for: "All six defect classes now have a real code path, but four did not until a post-freeze mutation sweep exposed the gap." In Method this reads as "the method was broken". Keep the fact, lead with the state: "All six classes have a code path under `checker-freeze-v2`; the refreeze that added four of them is disclosed under Threats." Then the list of what was missing.

6. **§V.E, no orientation.** The subsection opens on "a) Confirmed findings" and runs nine lettered paragraphs to "i) Sensitivity analysis" with no sentence saying what the sequence is. This is the passage where RQ framing would have helped and where one sentence does the same job (F7).

7. **§V.E.e, Precision.** Six sentences: one number and five disclaimers ("This denominator is ... it says nothing about ... This number licenses nothing about ... unlike the AGORA+ reference point ... That pooled sample also is not"). Each hedge is correct; five in a row read as a paper apologising for its own result. Keep the first and the second; fold the rest into "The shortfall against the pre-registered 25-per-class target is under Threats."

8. **The count arithmetic in §V.E.a.** Twelve VIOLATES rows collapse to eight instances populating seven cells, plus an unadjudicated eighth cell, of which four are headline-eligible, with four exclusions in a table footnote. A reader will not reconstruct this and will trust Table III's "8 (4)" instead. Say that: "Table III's 8 (4) is the count; the derivation is in the findings ledger" and cut the sentence about the seventh cell and the eighth candidate.

9. **Threats**, as in T3: the reader meets each weak number for the second time.

## 4. Does it read as written by a person?

Mostly, in the introduction and the MedAgentBench passages, for the reason above: specificity that only someone who ran `git grep` would have. The results section is where it stops sounding like a person and starts sounding like a person following a checklist. Not because of paragraph rhythm: I measured it (53 prose paragraphs, mean 120 words, sd 63; sentence-length means from 16 to 40 words, within-paragraph sd from 4 to 23), and the rhythm varies. The tells are elsewhere.

**The verdict frame "X, not Y".** 45 instances of ", not " and 29 of "rather than" in 589 lines. Paragraph openings: "Oracle grounding is a first-class output, not a footnote." "MM-ToolSandbox reports what it can compute and nothing it cannot." "Contract authoring is measured, not trusted." Paragraph titles: "Result-state disagreement is a signal, not a class", "Evaluation impact: a null, not a gap". Once per section this is a voice; forty-five times it is a template. The fix is not to remove the contrast but to let half of them state the positive alone. "Oracle grounding is computed per grader function" says the same thing without the pre-empted objection.

**The paper calls itself honest.** "reports origin honestly" (line 444); "the honest report is 'no data'" (523 and 543, the same sentence twice); "checking rather than merely claiming reproducibility" (380); "reported rather than hidden" (539); "stated here rather than left for a reviewer to find" (553). A person being honest shows the number; a person told to be honest says so. Cut all five adverbial claims to honesty; the numbers do the work. Line 553 also addresses a reviewer directly, which the paper does nowhere else (Pass 4, 7a).

**Procedural hedging.** "licenses" as a verb five times (436 twice, 525, 531): "licenses nothing about recall", "what that does and does not license is taken up under Threats". This is pre-registration vocabulary leaking into prose. A person writes "supports" or "shows". Likewise "disclosed here as applied post hoc" appears at 440 and 533 for the same rule, and "seed 1, zero discarded" at 440 and 531 for the same replay. Duplicated disclosure reads as generated from a ledger, because it was.

**The rule of three.** "three challenges", "three bodies of work", "three grounding tiers", "three consequences follow", "three static steps", "three comparison points" (then four). Eighteen occurrences of "three". Each is real, and together they are a pattern a detector scores. Leave the challenges and the steps; the rest can lose the count word ("Consequences follow" is fine; "The clauses fall into grounding tiers:" is fine).

**Where it is a person, keep it.** The lettered paragraph titles in §V.E that state a conclusion ("tau2-telecom produced no usable escape rate") are a person's; so is the conclusion's last sentence; so is "eight bugs in one copied helper is one bug". Do not sand those.

## 5. Defects (not style)

D1. **Internal provenance notes are printed in the bibliography.** Compiled page 10: [9] "iCLR 2024; publisher-confirmed, Scopus pending"; [10] "aCL 2024 (Camera Ready); Scopus pending"; [11], [12] "publisher-confirmed, Scopus pending"; [14] "Scopus-confirmed; D&B track sub-label unconfirmed"; [16] "under review for KDD 2026; not corroborated by dblp or ACM DL"; [17] "no venue claim on the abstract page"; [18] "independently confirmed"; [19] "self-listed as NeurIPS 2025 ...; not independently confirmed"; [22] "v5. Preprint. Referred to in text as the Agentic Benchmark Checklist"; [23] "distinct artifact and codebase from τ²-bench [13] (§II)"; [6] "preprint version (arXiv:2501.14654) read directly; Table 3 cited from that version"; [38] "not peer-reviewed". A reviewer reads "Scopus pending" as an unfinished submission, and "iCLR"/"aCL" are BibTeX case-mangling visible in print. These notes belong in `REFERENCES.md`, which already has them. Stripping them frees 8 to 10 scriptsize lines, about 6 to 7 body lines. Separately, every entry prints surnames only, no initials ("Long, Du, Xu et al."); IEEE style expects "J. Long". That also reads as unfinished.

D2. **Dangling reference to a sentence the abstract no longer has.** Line 444: "This is what the abstract means by three demonstrated dynamically: reproduction under contract, not discovery." The abstract does not say "three demonstrated dynamically" or anything like it. Replace with: "This is the sense in which three of the four headline cells are demonstrated dynamically: reproduction under contract, not discovery."

D3. **Circular cross-reference.** §IV.B line 376: "the gap was fixed at the cost of one disclosed refreeze cycle (... detailed once under Threats)". Threats line 555: "§IV's Conformance Checker subsection details the four taxonomy claims a mutation sweep ... found uncoded". Each says the other holds the detail. §IV.B is the one that lists the four items, so it keeps them and drops "detailed once under Threats"; Threats keeps its pointer.

D4. **Conclusion overstates the class count.** Line 563: "Four benchmarks yielded verified defects across six executable classes." Table II: two of the six are mutation-only, field-observed count zero. Replace with "verified defects in four of six executable classes".

D5. **Unscoped universal in the last sentence.** "only as trustworthy as the layer nobody has been checking." After a paper that scoped every such claim (C4), the last line hands the reviewer the one it did not. Replace with "as the layer its own audits have not been checking." Keeps the cadence.

D6. **Orphan lettered paragraph.** §II.B renders a `\paragraph` as "a) A single-layer audit finds each layer consistent here:" with no b). Under IEEEtran a lettered run-in with no sibling reads as an editing artifact. Make it a plain paragraph (and see reader point 3 for what it should lose).

D7. **Bibliographic metadata in running text.** Line 470: "(arXiv table, read directly; published in NEJM AI, vol. 2, iss. 9)". The bib entry [6] carries this. Cut the parenthetical.

D8. **Fig. 1 and Fig. 2 label legibility.** After `\resizebox{\columnwidth}`, the `\tiny` arrow labels ("this work: advertised → implemented", "state-based graders: read as ground truth") and Fig. 2's stage text render below 5pt in the PDF. IEEE's print floor is about 6pt. Either drop the arrow labels (the caption carries them) or set the pictures at natural width with `font=\scriptsize`.

D9. **Placeholders.** "AFFILIATION TO CONFIRM" in the author block; two red "[To be completed before submission.]" paragraphs under Conclusion, which will cost 3 and 5 lines at their prior wording. Zenodo concept-DOI question and eleven Scopus confirmations are open per `CHECKPOINT-2026-09-10.md`.

D10. **Keyword "data cleaning".** The body does no data cleaning. A session reviewer assigning fit sees the keyword on page 1 and then does not find the topic. If the session stays the target, the bridge paragraph has to use the phrase in a sentence that is true ("an audit of the tool layer is data cleaning applied to the instrument that produces the score"), or the keyword goes.

Zichong's five comments: C2, C3, C4 closed as `ZICHONG-VERIFICATION.md` found. C1 is now closed too; the two state-only sentences it flagged (§III opening, conclusion) both read "state or the result a call returned" / "what a grader reads" in the current source. C5 closes with T4.

## 6. Ranked fixes, with the line ledger

The paper is 10 pages with the balanced reference columns ending near the bottom of page 10; I did not measure the remaining white space and the author's ledger says none, so the plan below is self-funding. Line counts are body lines (about 55 per column), estimated.

| # | Fix | Where | Lines | Why |
|---|---|---|---|---|
| F1 | Strip provenance notes from the bibliography; add author initials | `references.bib` | **+7** | D1. A reviewer's first impression of unfinished work; the notes already live in `REFERENCES.md`. |
| F2 | Compress the six restating Threats to label + one sentence + pointer (T3) | lines 537-555 | **+20** | Every limitation survives; each weak number appears once. |
| F3 | Three contributions, findings first; absorb the confirmation clause; drop the closing paragraph (T4) | lines 216-226 | **+4** | Closes C5; matches title, abstract, conclusion. |
| F4 | Fill the two back-matter placeholders at their prior wording | lines 568, 573 | **-8** | Required for submission. Funded by F1+F2. |
| F5 | Fix D2, D3, D4, D5, D6, D7 | as cited | **+3** | Each is a factual or structural error a careful reviewer can quote. |
| F6 | Cut duplicate disclosures: "seed 1, zero trajectories discarded" and "disclosed below as applied post hoc" from §V.D (kept in §V.E.h and §V.E.i); the duplicate "honest report is 'no data'" from line 543 (kept at 523 after F2 rewrites it) | line 440, 543 | **+3** | Same fact twice reads as generated. |
| F7 | One orienting sentence at the head of §V.E: "This subsection reports what was found (a, b), what it could have cost (c), and how well the instrument detects and holds (d to i)." | before line 444 | **-2** | Does the navigational work RQ headers would, for two lines. |
| F8 | Abstract: replace sentences 5 to 7 with one (reader point 1) | lines 161-163 | **+2** (bold 9pt) | 257 to ~235 words; keeps the closing example. |
| F9 | Fig. 1 caption to two sentences; §II.B paragraph loses its first three sentences (reader point 3) | lines 206, 259 | **+5** | The thesis stated twice, not four times. |
| F10 | Delete the RISED sentence in §IV.C ("Reporting dimensions separately ... [48]") | line 387 | **+3** | A clinical fairness citation attached to "report dimensions separately" reads as a courtesy citation; nothing later uses it. Update `REFERENCES.md`. |
| F11 | Precision paragraph: two hedges, not five (reader point 7) | line 525 | **+3** | Correct hedges, wrong dose. |
| F12 | §III third consequence rewrite; drop the two bolded terms (reader point 4) | line 331 | **+1** | The one passage I could not parse on first read. |
| F13 | Bridge paragraph to one sentence in the session's words; `bunemantan01` to §IV.C (reader point 2) | line 212 | **+3** | Only if the session stays the target; if the venue switches, cut it. |
| F14 | Cut five self-descriptions of honesty and the "reviewer" address; "licenses" to "supports" where it is prose (§4) | 380, 444, 523, 539, 553; 436, 525, 531 | **0** | Voice, no space. |
| F15 | Fig. 1 / Fig. 2 label size (D8) | lines 184-208, 350-368 | **0 to -3** | Print legibility. Do last; it is the one item that may cost lines. |

Net: about +45 freed, -10 to -13 spent. The paper can afford its placeholders, the orientation sentence and the legibility fix, and ends with slack of roughly half a column. Do F1 and F2 first; everything else is funded by them.

## 7. Right as it stands

- The six-section shape, the lettered related-work subsections each closing on a disposal, the Baselines slot filled with the honest analogue and a sentence saying why, data availability inside Experiments, a one-paragraph conclusion, no appendix. All match the measured checklist.
- The bold challenges paragraph (T1).
- The benign-simplification block quote and the MedAgentBench reframe. The finding that survives the benchmark's own strongest documented defence is stronger than the one it replaced, exactly as the skill predicted.
- The ten limitations as a set (T3 changes their length, not their number).
- Table IV with quoted evidence, and Table V refusing to pool bases. Keep the `not_computable_appworld_unreachable` cell; it is the paper's integrity in one row.
- The conclusion, after D4 and D5.
- Abstract length, on the evidence file's own numbers.

## 8. What I did not check

I did not re-verify any finding against the audited repositories at their pinned commits, did not run `numbers_audit.py`, did not confirm any bibliography venue against Scopus, and did not measure the white space on compiled page 10. The co-author style counts in the brief are unverified because the file that should carry them is unwritten.
