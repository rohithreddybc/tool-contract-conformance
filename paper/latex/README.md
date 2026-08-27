# paper/latex — Overleaf project

This directory holds the LaTeX conversion of `paper/main.md`, the working draft for
*Scores at Risk: When Benchmark Tools Violate Their Own Advertised Semantics* (IEEE BigData
2026, Intelligent Data Mining special session). It is a format conversion, not an edit: the
drafted prose (sections I, II, III, V, IX) is reproduced verbatim, sections are in their
original order, and no number, citation key, file path, line number, or commit hash has been
changed from the Markdown source.

## Uploading to Overleaf

1. Zip the three files in this directory (`main.tex`, `references.bib`, this `README.md` is
   optional to include) or upload them individually into a new Overleaf project.
2. Set the compiler to **pdfLaTeX** and the main document to `main.tex`.
3. Overleaf ships `IEEEtran.cls`, `booktabs`, `listings`, `hyperref`, `xcolor`, and `balance`
   already, so no class file or package needs to be vendored alongside these two files.
4. Overleaf's default build runs pdfLaTeX → BibTeX → pdfLaTeX → pdfLaTeX automatically; no
   manual "Recompile from scratch" should be needed unless the bibliography looks stale after
   editing `references.bib`, in which case use Overleaf's "Recompile from scratch" once.

## What compiles today

Verified locally with MiKTeX (`pdfLaTeX`, MiKTeX-pdfTeX 4.23; `BibTeX`, MiKTeX-BibTeX 4.2) on
2026-08-26, running the standard four-pass sequence (`pdflatex` → `bibtex` → `pdflatex` →
`pdflatex`):

- **Compiles cleanly.** No LaTeX errors, no undefined references, no undefined citations, in
  the final pass.
- **9 pages**, two-column, IEEEtran `conference` class. This is well under the 10-page budget,
  but six of the paper's eleven sections are still placeholder stubs (see below); the page
  count will grow substantially once §IV, §VI, §VII, and §VIII carry real tables and prose,
  and the 10-page ceiling becomes the binding constraint the outline already plans around.
- **All 32 citation keys used in the text resolve** against `references.bib` and appear in
  the rendered bibliography. No citation key is missing a bibliography entry.
- A handful of `Overfull \hbox` warnings remain (each under 13pt, i.e. under two-tenths of an
  inch), from long monospaced file paths inside table cells and from a few dense inline-math
  spans in Table I. These are cosmetic and typical of an early draft; none causes text to run
  off the page or lose content. They are candidates for a layout pass before submission,
  listed in "Known rough edges" below.
- The MedAgentBench, tau2-bench, AgentDojo, and MM-ToolSandbox papers each have their commit
  or table citation reproduced from `paper/main.md`; the `\S` section-reference macro,
  `\cite`, `\ref`, and `\label` cross-references were all checked and resolve.

## What is deliberately incomplete

Per `PAPER-OUTLINE.md`, sections IV, VI, VII, VIII, X, and XI are stubs in the Markdown source
that name the artifact (script, protocol, or log) that must generate their content. They are
**not drafted here**, by instruction. Each stub is reproduced as a compiling, visibly red
placeholder block using the `\pendingblock{...}` macro (defined in the preamble), so the PDF
cannot be mistaken for a finished paper:

| Section | Status | Generating artifact |
|---|---|---|
| IV. Score-at-Risk Dependency Analysis | stub | `analysis/score_at_risk.py` |
| VI. The Conformance Checker | stub | `core/`, `adapters/`, `static_check/checks.py`, dynamic harness, frozen at `checker-freeze-v1` |
| VII. Detector Validation | stub | `experiments/detector_analysis_plan.md` (pre-registered), `mutation/score.py`, `spec/coverage.py` |
| VIII. Evaluation Impact | stub | `experiments/analysis_plan.md` (pre-registered), `experiments/ab_run.py` |
| X. Threats to Validity | stub | drafted after §IV and §VII numbers exist |
| XI. Conclusion | stub | written last |

Every individual `[Nk: artifact]` marker inside those stubs, and inside the finished sections
where one still appears (for example N1, N7, N12), is preserved and rendered in red via
`\pending{Nk}{artifact}` — nothing was filled in or guessed.

The **abstract** is also a structured placeholder in the Markdown source, not a stub with a
missing number. Its committed shape (what it must lead with, what it must promise, what it
must never claim) is reproduced twice in `main.tex`: once as a visible red note in the
compiled PDF, and once as an HTML-comment-equivalent LaTeX comment block carrying the full
verbatim text of the source comment, so the constraints on the eventual abstract are not lost
in translation. Nobody should compile this file and mistake the abstract placeholder for a
finished abstract.

No appendix is used anywhere in this project. The venue's CFP forbids one, and `PAPER-OUTLINE.md`
already reassigns everything that would have gone there (patch diffs, the permutation test) to
the artifact repository or drops it entirely.

## Numbers, and where each one comes from

Every number below is reproduced from `paper/main.md` exactly as written; none was changed
during conversion.

- **§I contribution 5 and §IX** both state the finding count as **"seven unique
  benchmark-class defect cells across four shipped benchmarks, eight instances."**
- **§IX's findings table** lists 8 numbered instances, of which two are explicitly marked
  non-headline in the table itself: instance 3 (tau2-bench, Partial Effect) is
  maintainer-annotated, and instance 4 (MedAgentBench, Ungrounded Oracle) is an evaluator
  property rather than one of the six tool-layer classes.
- **The abstract's own internal HTML comment** (reproduced verbatim in `main.tex`) states, in
  its first bullet, that the count "that survives inspection" is **4 headline-eligible
  tool-layer cells across 4 benchmarks**, counted from `report/findings.jsonl`, and explains
  that the block previously said 7, then 5, before settling on 4. The same comment's closing
  sentence, describing the kill-gate outcome, then states **"8 instances across 4 environments,
  5 of them headline-eligible"** — a different number in the same comment block.

**This is a source-of-record discrepancy, not a conversion error.** `CLAUDE.md` for this
project fixes the headline count at 4 cells across 4 benchmarks and instructs that any
disagreement in the draft be flagged rather than silently corrected. Three different figures
(4, 5, 7) appear across the current draft for what should be the same headline count, in three
different places (the abstract's own placeholder comment gives both 4 and 5; §I and §IX give
7). All three are reproduced in this LaTeX conversion exactly as they stand in `paper/main.md`,
because the conversion task is a format change, not a fact-check, and `paper/main.md` was not
to be modified. **Before the abstract is drafted for real, §I's contribution list and §IX's
opening sentence need to be reconciled with whichever count the finalized
`report/findings.jsonl` supports.**

Other headline figures carried through unchanged, with their source of record:

- MedAgentBench Action SR range: 0.00%–71.33% across 11 models (Gemini-1.5 Pro highest,
  two models at 0.00%), and the headline 69.67% overall SR for Claude 3.5 Sonnet v2 — both
  from the arXiv table (`medagentbench25`), read directly, per §II.
- "Four of the eight instances are Ignored Argument" (§IX).
- Two of ten MedAgentBench task families (60 of 300 cases) grade writes unconditionally
  through the transcript-reconstruction path (§IX).
- Zero overlap across 27 categories when the six defect classes are mapped against prior
  audit taxonomies [C6] (§II).
- AGORA+'s 80% reported precision on REST invariants, cited as an external baseline (§II,
  and referenced again in the §VII stub).

## Citation keys with no bibliography source

None. All 32 citation keys used in `paper/main.md`'s body text have a corresponding entry in
`references.bib`, and all 32 resolve in the compiled bibliography. The keys are:

`aba26`, `abc26`, `abcchecklist25`, `agentdojo24`, `agora25`, `benchguard26`, `chen18`,
`cogent23`, `constructvalidity25`, `contract26`, `contract2tool26`, `contractbench26`,
`contractguard26`, `dlcontract23`, `faulttaxonomy26`, `frames25`, `godefroid20`, `icepick26`,
`jass01`, `jcontractor05`, `liveclawbench26`, `medagentbench25`, `mmtoolsandbox26`,
`restler19`, `safeaudit26`, `segura16`, `segura18`, `tau2bench25`, `taubench24`, `toolfuzz25`,
`toolgate26`, `toolveritas26`.

Two keys appear in `REFERENCES.md` but are **not** cited anywhere in `paper/main.md`'s body
text, and were therefore left out of `references.bib`: `armeta26` (the COMPSAC 2026
metamorphic-testing paper) and the artifact-repository rows (`medagentbench`, `tau2bench`,
`taubenchcom_leaderboard`), which are commit pointers and a live leaderboard rather than
citable works. Add them if a later revision of `main.md` cites them.

### Venue-confirmation status, preserved from `REFERENCES.md`

- **Confirmed peer-reviewed venues**, entered with real venue/year/DOI: `benchguard26` (COLM
  2026, confirmed on the official accepted-papers page), `medagentbench25` (NEJM AI, vol. 2,
  iss. 9 — the bibliography entry cites the peer-reviewed venue while the `note` field records
  that Table 3 was read from the arXiv preprint, per the source text), and the eleven
  SE/testing entries confirmed by Scopus DOI match (`contract26`, `icepick26`, `agora25`,
  `jcontractor05`, `jass01`, `dlcontract23`, `cogent23`, `segura18`, `segura16`, `restler19`,
  `godefroid20`), plus `frames25` (ICSOFT 2025, confirmed via the SCITEPRESS publisher page
  rather than Scopus).
- **Confirmed preprint-only**, entered as `@misc` with `eprint`/`archivePrefix`/`primaryClass`
  and a note stating the preprint status explicitly: `toolveritas26`, `aba26`, `safeaudit26`,
  `toolgate26`, per the instruction that these four must not be dressed up as published.
- **`chen18`** carries the correction from `REFERENCES.md`: the DOI resolves to **2019**, not
  2018, and the real title is "Metamorphic testing: A review of challenges and opportunities"
  (ACM Computing Surveys 51(1), art. 4) rather than the paraphrased title an earlier draft used.
- **`agentdojo24`**: the parent venue (NeurIPS 2024) is Scopus-confirmed, but the specific
  "Datasets and Benchmarks Track" label is not — Scopus does not tag NeurIPS sub-tracks. The
  entry is a `@misc` with a note stating exactly this, rather than asserting the track.
- **`constructvalidity25`**: self-listed as NeurIPS 2025 Datasets and Benchmarks Track but not
  yet Scopus- or publisher-confirmed; entered as `@misc` with a note saying so.
- All remaining entries (`contract2tool26`, `contractbench26`, `toolfuzz25`, `contractguard26`,
  `faulttaxonomy26`, `abcchecklist25`, `liveclawbench26`, `tau2bench25`, `taubench24`,
  `mmtoolsandbox26`) are preprints whose venue is simply not yet confirmed either way; each
  `@misc` note says so rather than guessing.

`NEJM AI` appears exactly once in the running prose (§II, factually, never in the abstract)
and once more in the `medagentbench25` bibliography entry's `journal` field, which is the
normal place a confirmed publication venue belongs.

## Known rough edges

- **Minor overfull hboxes.** A few table cells and one inline-math run in Table I overflow
  their column by a small amount (under 13pt / 0.2in). A short layout pass — slightly
  rebalancing column widths in Tables I and II, or dropping to `\scriptsize` in the findings
  table — would clear these; they do not affect content or pagination today.
- **Figures 1–4 are not drawn.** The Markdown source specifies what each should show (the
  three-layer positioning diagram in §II, the tau2 dependency graph in §IV, the worked
  contract listing in §V, and the verdict-flip plot in §VIII) but none exists as an image or
  TikZ source yet. §II's figure placeholder is rendered as a boxed red note; the other three
  figures are described only inside their section's `\pendingblock`.
- **Back matter** (Data Availability with a Zenodo DOI, funding/acknowledgment line) is
  deferred per the source comment: `EXTERNAL-VERIFICATION.md` Task 3 found no CFP requirement
  for these fields, but the camera-ready portal should be rechecked at submission time.
- **Author affiliations** are left blank in `\IEEEauthorblockA{}` for both authors; the
  Markdown source gives only names ("Rohith Reddy, Wenbin Zhang") with no affiliation, so none
  was invented.

## Files in this directory

- `main.tex` — the paper, `\documentclass[conference]{IEEEtran}`.
- `references.bib` — 32 BibTeX entries, one per citation key used in `main.tex`.
- `README.md` — this file.

Nothing under `repos/`, `spec/`, `paper/main.md`, or any root-level `.md` file was modified to
produce these three files.
