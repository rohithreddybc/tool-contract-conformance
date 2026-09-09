# Audit: Wang review action items vs. current `paper/latex/main.tex`

Read-only audit. No changes made to `paper/latex/main.tex` or `paper/main.md`. Checked against
`MEETING-2026-09-02-WANG.md` (fifteen action items, four tensions) and
`claude skills/ieee-data-mining-format/exemplar-conventions.md` (the ICDM 2023 model paper).
`main.tex` read in full (573 lines); word counts and citation counts below were computed directly
from the file, not estimated.

## Summary table

| # | Item | Status | Evidence (one line) |
|---|---|---|---|
| 1 | Rewrite abstract to five-part structure | DONE | Stakes -> gap -> why serious -> approach -> setting/result, in that order; no "must"; 0 digit numerals |
| 2 | Rewrite introduction to mirror abstract in four paragraphs | PARTIAL | The four functional beats are present but spread across seven prose paragraphs plus a figure and a contributions list, not four paragraphs |
| 3 | Search for prior work on verifying tool-task completion | DONE | Related Work \S B cites Agent-Diff, Gao and Zhou, Advani, Tool-Veritas with the same venue caveats the search verified |
| 4 | Cut related work to two or three subsections, three to five works each | PARTIAL | Three subsections (within range); A has ~6 citations, B has 5, but C carries ~25 distinct citation keys in one paragraph |
| 5 | Remove Table 1 | SUPERSEDED | Table compressed from nine rows to six per the tension-section compromise, not deleted |
| 6 | Merge background into a preliminaries and notation section | DONE | \S III "Notations and Preliminaries" absorbs the former standalone background section |
| 7 | Restructure Sections 3-5 to setup, method, experiments | DONE | III Notations and Preliminaries, IV Method, V Experiments |
| 8 | Add the standard experiment subsections | DONE | Setup, Baselines, Metrics, Implementation/Data Availability, Main Results all present; no ablation subsection, matching the tension's rationale |
| 9 | Replace page-1 code listing with a concept figure | DONE | No `\begin{lstlisting}` remains; Fig. 1 (tikz concept diagram) is on page 1 |
| 10 | Add a methodology overview figure | DONE | Fig. 2 (tikz pipeline diagram) opens \S IV, stage order matches subsection order |
| 11 | Compress the conclusion to one paragraph | DONE | Conclusion is one paragraph (239 words); AI-tools and disclosure statements are separate `\paragraph`s, not part of it |
| 12 | Move data availability into the experiment section | DONE | "Implementation Details and Data Availability" subsection, immediately after implementation details, inside \S V |
| 13 | Lengthen the short paragraphs at the end of Section 1 | DONE | Post-contributions material is one continuous 121-word paragraph, not several one/two-sentence ones |
| 14 | Remove bolded lead sentences | PARTIAL | Removed from the paragraphs Wang flagged in Section 1, but Threats to Validity (\S V.F) still opens nine of its ten paragraphs with a bolded lead sentence used as emphasis, not a heading |
| 15 | Fix the step numbering | DONE | "First, ... Second, ... Third, ..." in \S I, no orphan "step one" |

---

## Detail on PARTIAL / NOT DONE / SUPERSEDED items

### Item 2 — Introduction mirroring the abstract in four paragraphs (PARTIAL)

Wang's prescription was four paragraphs: (1) why it matters, (2) limitations + challenge
statement, (3) how we address it, (4) contributions. The current introduction hits all four
functional beats — motivation, the challenge statement ("three things make that hard. First...
Second... Third..."), the approach, and the contributions list — but they are not compressed into
four paragraphs. Splitting the introduction at blank lines (excluding the figure block and the
`\label` line) gives seven prose blocks before the enumerate, of 95, 113, 122, 156, 71, and 74
words, plus a 121-word block after the contributions list:

1. Field stakes (95 words)
2. LiveClawBench + prior-audit limitation (113 words)
3. The MedAgentBench worked example (122 words) — this paragraph has no counterpart in Wang's
   four-part template at all
4. The three-challenges paragraph (156 words) — this is the "challenge statement" Wang said was
   missing, and it is now present, which is the substantive fix
5. The data-quality framing paragraph (71 words) — also has no counterpart in the template
6. "This paper meets those three challenges directly," leading into contributions (74 words)
7. Post-contributions synthesis (121 words)

What is missing relative to the letter of item 2 is compression to four paragraphs. What is
present, and is arguably the more important fix, is the challenge statement itself, which Wang
called out by name as "currently missing" and which now exists. The extra paragraphs (the worked
MedAgentBench example, the data-quality framing) carry evidentiary weight the paper needs and are
defensible additions, but they mean the introduction is a looser, longer version of the abstract
rather than a four-paragraph mirror of it. Call this a partial compliance: the content
requirement is met, the paragraph-count requirement is not.

### Item 4 — Related work density (PARTIAL)

Three subsections exist, matching "two or three" (the safe reading of an uncertain transcript).
Citation density per subsection, counted directly:

- **\S II.A** ("How Agent Benchmarks Grade Tool-Using Tasks"): 6 works cited by name (WebArena,
  AppWorld, OSWorld, AndroidWorld, tau2-bench, AgentDojo). One over Wang's stated ceiling of five,
  functionally compliant.
- **\S II.B** ("Verifying That a Task Actually Completed"): 5 works cited by name (Tool-Veritas,
  Agent-Diff, Gao and Zhou, Advani, the construct-validity review). Exactly matches "three to
  five."
- **\S II.C** ("Contract Inference, API Oracles, and the Testing Lineage"): approximately 25
  distinct citation keys in one paragraph (jcontractor05, jass01, contract26, icepick26, agora25,
  frames25, cogent23, dlcontract23, segura18, segura16, chen18, restler19, godefroid20,
  toolgate26, abc26, contract2tool26, contractbench26, contractguard26, faulttaxonomy26,
  kapoor24matter, betterbench24, utboost25, gyori15, idflakies19, liveclawbench26). This is five
  times Wang's stated ceiling for a subsection.

Subsection C is, in effect, the entire former "five threads" of related work that Wang objected
to, now merged into a single subsection instead of five separate ones. The subsection count went
down; the citation density inside the surviving subsections did not. A reviewer skimming \S II.C
will encounter the same wall-of-citations texture Wang's original complaint was about, just
without a subsection break in the middle of it.

### Item 5 — Remove Table 1 (SUPERSEDED)

The table was not removed. It was compressed from nine rows to six (per the file's own header
comment, "Table I (prior-work disposals) was compressed from nine rows to six, led by Agent-Diff
and Gao and Zhou"), with the remaining four disposals folded into one-sentence prose inside the
matching subsection. This is not what item 5 asked for, but it is exactly the compromise the
meeting record itself proposed as an alternative to outright deletion: "compress it to the three
or four closest competitors rather than deleting it, and move the rest into prose." The row count
landed at six rather than three or four, and the two combined rows (BenchGuard/ABA/SafeAudit in
one row) do some of that compression's work, but the net effect matches the compromise's intent
closely enough to call this superseded rather than not done: newer, better information (the
tension discussion itself) changed what the right answer was, and the paper followed it.

### Item 14 — Remove bolded lead sentences (PARTIAL)

The three short paragraphs at the end of Section 1 that originally opened with bold sentences
have been merged and delegated (see item 13). Elsewhere in the document, `\textbf{}` is used
correctly as genuine subsection/list-item labels (the contributions list, the pipeline stage
labels in Fig. 2, subsection titles). But Threats to Validity (\S V.F) still uses the pre-review
pattern throughout: nine of its ten paragraphs open with a bolded sentence used purely for
emphasis, e.g.:

> \textbf{The taxonomy is not the space of possible defects, and the open-world arm measures the
> gap rather than closing it.} The open-world arm on the toy domain found...

> \textbf{Sample sizes fall short of the pre-registration for four of six mutation operators, and
> the shortfall is structural, not a scoring choice.} The achieved-N accounting above shows...

These are not subsection titles; they are full sentences serving as topic-sentence emphasis
inside a flowing subsection, which is precisely the pattern Wang said readers do not give the
attention the author intends. This looks like an oversight rather than a deliberate exception:
the fix was applied to Section 1 (where Wang pointed) but not swept through the rest of the
document, where the same pattern recurs at higher density.

---

## The four tensions

**Baselines.** DONE, and matches the agreed resolution precisely. \S V.B ("Baselines and
Reference Points") opens by stating plainly that a defect class no prior audit checks for has no
shared-task competitor, then presents four comparison points, the first and central one being
"Incumbent practice: manual source audit," explicitly stating "We do not claim to beat this
baseline." This is the manual audit presented as the incumbent, not a straw competitor. The
detector-validation numbers Wang flagged as the honest analogue (precision/recall against
injected defects) are reported in \S V.C-E as planned, and referenced back into the baselines
subsection as comparison point (4).

**Removing Table 1.** Handled as a compromise rather than either extreme; see item 5 above. The
compromise's reasoning still holds: the table remains the paper's defense against a "prior work
already does this" desk rejection, now at lower page cost.

**Section V's self-critical content.** DONE, fully preserved. The low recall numbers (Table VI:
recall lower bounds of 0.359, 0.020, 0.066, 0.018, 0.000), the null replay result ("Evaluation
impact: a null, not a gap," reporting zero of ten trajectories flip a verdict), and the honest
"Surfaced by" column (seven manual, one static, zero dynamic) are all present, in the same
register the meeting record wanted kept. Nothing here has been quietly smoothed over in the
restructure.

**Prevalence language.** DONE. The abstract and introduction open with broader stakes (clinical
decision support, financial transactions) without generalizing to a prevalence claim about
benchmarks generally. The Threats to Validity subsection states directly: "No prevalence claim,
what fraction of shipped benchmarks carry a defect class or how common Ignored Argument is, is
supportable from four benchmarks chosen this way." The Conclusion repeats this: "four
anchor-driven audits are existence proofs, not a survey." The scoping Wang wanted protected has
not drifted.

---

## Exemplar-convention gaps (not raised by Wang, but visible against the ICDM model paper)

These are observations against `exemplar-conventions.md`, kept separate from Wang's own items
since he did not raise them.

- **Introduction has no closing roadmap sentence.** The exemplar treats "one sentence per
  remaining section, in section order" as a universal closing move. The current introduction
  ends on a substantive claim about MedAgentBench's grader, not a section map. No roadmap sentence
  exists anywhere in the introduction.
- **Results are not organized around explicit research questions.** The exemplar's Experiments
  section (and its universal rule) frames results as a small number of bold run-in "RQ1:", "RQ2:"
  questions, each answered by pointing at one table or figure. \S V's subsections (Confirmed
  findings, Score-at-risk, Real-tools closed-world recall, Precision, Achieved N, Open-world
  escape rate, Evaluation impact, Sensitivity analysis) are organized by finding type instead.
  This is a real structural gap relative to the model paper both co-authors are using as the
  target shape.
- **Conclusion is far longer than the exemplar's convention.** Item 11 (one paragraph) is
  satisfied, but the paragraph is 239 words against the exemplar's observed 85 words for the same
  slot — nearly three times as long. Zero digit numerals are used in either (matching the
  exemplar), but the length convention is not met.
- **Abstract is longer than the exemplar's convention.** 221 words against the exemplar's 161.
  The meeting record explicitly allows the abstract to "run a little longer than usual" given the
  ten-page limit, so this is a documented exception rather than an oversight, but 37% longer is
  worth flagging as more than "a little."
- **Contribution count is five, not three.** The exemplar's related rule is not prescriptive
  about count, but five is denser than the model paper's three, and two of the five ("Six
  executable defect classes" and "A provenance-bound contract format... and a static plus dynamic
  conformance checker") are close enough in substance that a reviewer could ask why they are not
  one contribution.
- **Index Terms carry six keyword phrases, not three.** Minor; the exemplar's convention is three.
- **Table cell density.** The exemplar's universal rule is that no table cell contains a sentence
  or clause. Table III (per-benchmark totals) and Table VI (recall) comply: every cell is a bare
  numeral. Table I (disposals) and Table IV (confirmed findings) do not: their "Disposal" and
  "Quoted evidence and disposition" columns carry full sentences and direct quotations by design,
  since the evidentiary function of those two tables is to show quoted source text. This is
  probably a defensible, deliberate exception given what those two tables exist to do, but it is a
  clear departure from the exemplar's density convention and should be a conscious choice, not an
  unexamined one.

---

## Risks a reviewer at this venue would plausibly raise, that Wang did not

Ranked by how much each could cost, kept short.

1. **`AFFILIATION TO CONFIRM` is still a live placeholder in the author block** (line 130). This
   is the single most visible unfinished element in the file. If it survives to submission it
   reads as an author who did not proofread the title page.
2. **A live `\pending{N12}{report/disclosure_log.md}` marker remains in the Coordinated Disclosure
   paragraph** (renders in red per the file's own `\pending` macro). Disclosure is scheduled for
   2026-09-10, seventeen days before the 2026-09-27 deadline, so there is time to resolve it, but
   nothing in the file itself guarantees this gets swept before submission, and a visibly
   unfinished red bracket in a submitted PDF is a bad first impression independent of its content.
3. **Related Work \S C's twenty-five-citation paragraph** (see item 4 above) reproduces, inside
   one subsection, the density problem the whole restructure was meant to fix. A reviewer who
   found the pre-restructure related work dense would very plausibly find this subsection dense
   for the same reason.
4. **No RQ framing in the results section**, given that the co-authors are explicitly using an
   RQ-organized paper as their structural model. A reviewer who has seen that convention used well
   elsewhere in this subfield may notice its absence here as a missed opportunity to make the
   dense Experiments section easier to navigate, not as an error, but as a place the paper could
   read more like its own stated model.
