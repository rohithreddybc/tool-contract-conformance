# Co-author review meeting, 2026-09-02 — Zichong Wang

Present: Rohith Reddy Bellibatlu, Zichong Wang (Stevens, `zwang253@stevens.edu`). Wang read the
full draft on Monday before the call.

Reconstructed from a recording whose automatic transcript is unreliable. Where the transcript
was ambiguous the reading is marked **[uncertain]** and should be confirmed with Wang rather
than acted on blind.

**Verdict: major revision, structural.** Not a disagreement with the research. Every item below
is about the shape of the paper, not its findings, its numbers, or its claims. Wang did not
dispute a single result.

**Schedule agreed.** Rohith rewrites and returns a draft by Monday 2026-09-07 or Tuesday
2026-09-08. Work abstract first, then introduction, send those two for a check before
continuing into the later sections. Submission deadline is 2026-09-27, so roughly 25 days
remain. Contact by group chat or direct message, either is fine.

**Reference paper.** Wang sent <https://ieeexplore.ieee.org/document/10415714> as the structural
model to follow. IEEE format, ten pages including references, same constraints as ours. He is
also sending the PDF.

---

## 1. Abstract — rewrite from scratch

The current abstract states the method in detail. Wang's point is that an abstract is not a
summary of what was done step by step; it is an argument for why the reader should care. He
described the current version as going straight into detail with no motivation in front of it.

Required order:

1. **Why agents matter, and their broader impact.** Open here, not with the method. Agents are
   increasingly used in consequential settings, for example helping clinicians assess patient
   state and supporting decisions. This part needs no citation or evidence. It establishes
   stakes.
2. **What existing work fails to do.** Existing evaluation checks that the tool reported
   completion, not that the task was actually completed.
3. **Why that gap has to be closed.** Make the reader believe it is a serious limitation. Wang
   was specific about wording: do not write "must". Scientific writing carries necessity through
   the argument, not through the word. The reader should conclude it, not be told it.
4. **How we address it, at a high level.** One or two sentences. Not step one, step two, step
   three.
5. **Experimental setting and headline result, briefly.**

Because the venue allows ten pages, the abstract can run a little longer than usual.

## 2. Introduction — the abstract, expanded, in the same order

Wang described the introduction as an extended version of the abstract, following the same
sequence.

- **Paragraph 1.** Why the problem matters and its broader impact.
- **Paragraph 2.** Limitations of existing work, what we set out to do, and what made it hard.
  The challenge statement matters and is currently missing.
- **Paragraph 3.** How we address it, with more detail than the abstract carries.
- **Final paragraph.** Contributions.

## 3. Remove the code listing from page 1

Two separate objections.

It renders badly. The listing is cut off, and a truncated code block reads as a display problem
rather than as evidence.

More importantly it is the wrong altitude. Code-level detail belongs in the methodology section,
where the specific defect can be explained properly. The introduction should give the reader the
shape of the idea.

**Replace it with a concept figure.** Wang pointed to ACL and EMNLP convention, where page one
carries a clean diagram showing the high-level idea. He called this optional but clearly better,
and Rohith agreed the paper currently reads as dense.

## 4. Related work — cut it down and give it a clear mission

Currently around five threads. Wang considers that too many and wants roughly two, with the rest
merged or dropped. **[uncertain: the transcript garbles the exact number he wanted kept; two to
three is the safe reading.]**

The section needs explicit bolded subsections, each with a stated purpose. Related work exists to
let a reviewer judge whether the proposed work is novel, so it must be organised around overlap
with our contribution rather than as a general survey.

**Subsection A: how existing agent benchmarks evaluate tool tasks.** Show that they read the
final returned state or completion signal and stop there. This needs **three to five works, not
one or two.**

**Subsection B: other ways to verify that a tool task actually completed.** Wang believes other
approaches exist, for example checking whether a file genuinely changed rather than trusting a
returned signal. He has not verified this and asked Rohith to search. **This is the action item
he cared most about.** His reasoning: a reviewer will ask why our approach was chosen when other
verification methods exist. If such work exists we must compare against it and justify the
choice. If it does not, that strengthens the paper, but we need to have looked.

**Wording.** Prefer "most existing work" over "all existing work" unless every case has been
checked. (Note: the manuscript already scopes this correctly as "none of the audits we survey",
so this is a caution rather than a correction.)

## 5. Background belongs with notation, not on its own

Related work stays an independent section because it carries the novelty argument. Background is
lower-stakes, and some reviewers skip it. Merge it into a preliminaries and notation section
rather than giving it standalone status.

## 6. Remove Table 1

The disposal table comparing our work against prior work takes too much space for what it
returns. Wang's read is that extensive comparison tables are a survey-paper convention, and a
research paper does not spend that much room on them. He was direct: it should be removed.

## 7. Section structure from Section 3 onward

- **Section 3.** Background and preliminaries. Define the notation the rest of the paper uses,
  once, so later sections can rely on it.
- **Section 4.** Methodology. This is where the detail goes, including the code-level specifics
  currently sitting in the introduction. Add an overview figure showing the pipeline.
- **Section 5.** Experiments, with the standard subsections below.

## 8. Experiment section needs the standard components

Wang listed these explicitly:

- Experimental setup, including which benchmarks and data were used
- **Baselines.** Compare against existing work and show how much our approach improves on it
- Evaluation metrics, and how baselines were evaluated
- Implementation details: hyperparameters, preprocessing, configuration
- Main results, with every table and figure, each described in the text
- Ablation study or hyperparameter study if feasible

## 9. Conclusion is too long

It should be a single paragraph. It is currently split in two.

## 10. Data availability moves into the experiment section

Place it after implementation details, phrased as a short statement that the code is available,
with the link. Keep both the GitHub repository name and the DOI, since the repository name is
easier for a reader to find directly. No appendix, which matches the venue rule we already
verified.

## 11. Paragraph length and connective flow

The three short paragraphs at the end of Section 1, after the contributions list, are one or two
sentences each. Wang's objection is that very short paragraphs signal weak connection between
ideas, and read as unfinished. Lengthen them and make the transitions explicit.

## 12. Remove bolded lead sentences

Several paragraphs open with a bolded sentence used as emphasis. Wang says this is not standard
practice outside actual subheadings, and that readers do not give it the attention the author
intends. Remove it except where the bold text is a genuine subsection title.

## 13. Fix the step numbering

There is a "step one" with no corresponding "step two". Either commit to numbered steps
throughout or drop the numbering. As written it reads as an error.

---

## Action list, in Wang's priority order

| # | Item | Notes |
|---|---|---|
| 1 | Rewrite the abstract to the five-part structure | Send for check before continuing |
| 2 | Rewrite the introduction to mirror it in four paragraphs | Send with the abstract |
| 3 | Search for prior work on verifying tool-task completion | The item he stressed most |
| 4 | Cut related work to two or three subsections, 3 to 5 works each | |
| 5 | Remove Table 1 | |
| 6 | Merge background into a preliminaries and notation section | |
| 7 | Restructure Sections 3 to 5 to setup, method, experiments | |
| 8 | Add the standard experiment subsections | See item 8 above, and the caveat below |
| 9 | Replace the page-1 code listing with a concept figure | |
| 10 | Add a methodology overview figure | |
| 11 | Compress the conclusion to one paragraph | |
| 12 | Move data availability into the experiment section | |
| 13 | Lengthen the short paragraphs at the end of Section 1 | |
| 14 | Remove bolded paragraph leads | |
| 15 | Fix the step numbering | |

---

## Points of tension to resolve with Wang, not to action blindly

These are places where his advice, which is sound for a standard method paper, sits awkwardly
against what this paper is. Raise them rather than silently following or silently ignoring.

**Baselines.** This is the significant one. Wang's experiment template assumes a paper proposing
a method that beats prior methods on a shared task. This paper audits four artifacts and reports
what it found. There is no prior tool-contract checker to beat, which is the paper's own novelty
claim. Forcing a baseline comparison would either invent a strawman or undercut the claim that no
prior audit tests this layer. What we do have, and should present as the closest equivalent, is
the detector validation in the current Section 7: injected known defects, measured precision and
recall. That is the honest analogue and it should be framed as such.

**Removing Table 1.** Wang is right that it is expensive at ten pages. But that table is
currently the paper's defense against the most likely desk rejection, namely a reviewer asserting
that prior work already does this. Twelve works, each with a named and checkable distinction. A
compromise worth proposing: compress it to the three or four closest competitors rather than
deleting it, and move the rest into prose.

**Section 7's self-critical content.** The current draft deliberately reports weak recall, a null
replay result, and the fact that the checker confirmed rather than discovered most findings. A
restructure toward a conventional results section could quietly bury these. Keep them. They are
what makes the paper credible, and an internal review panel identified them as a strength.

**Prevalence language.** As the introduction is rewritten to open with broader impact, keep the
existing scoping. The paper claims existence, not prevalence, and Section 9 says so explicitly.
The motivation paragraph must not drift into implying that this is widespread.
