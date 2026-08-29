# paper/latex — Overleaf project

This directory holds the LaTeX conversion of `paper/main.md`, the working draft for
*Scores at Risk: When Benchmark Tools Violate Their Own Advertised Semantics* (IEEE BigData
2026, Intelligent Data Mining special session). It is a format conversion, not an edit: the
drafted prose (abstract, sections I–XI) is reproduced verbatim, sections are in their
original order, and no number, citation key, file path, line number, or commit hash has been
changed from the Markdown source.

**Resync status (2026-08-29):** `paper/main.md` is now complete — abstract plus all eleven
sections. This conversion was re-run against that finished draft: the abstract and §§IV, VI,
VII, VIII, X, XI (previously red `\pendingblock` stubs) are now real prose, and Table II
(score-at-risk), the §VII recall and mutant-pool tables, and the §VIII trajectory-replay table
are rendered as `booktabs` tables. Two genuine placeholders remain, both named in
`paper/main.md` itself: `N1` (Table III, per-benchmark totals — `report/render.py` does not
exist yet) and `N12` (the disclosure log, dated 2026-09-10, in the future). `N7` (the
dual-annotation agreement result in §V) is also still open. One inconsistency present in the
earlier stub-era draft (a "12 evaluated models" / "11 evaluated models" mismatch in §II, and
the abstract's own former "4 vs 5" discrepancy) is resolved in the current `main.md` and no
longer appears here.

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
2026-08-29, running the standard four-pass sequence (`pdflatex` → `bibtex` → `pdflatex` →
`pdflatex`):

- **Compiles cleanly.** No LaTeX errors, no undefined references, no undefined citations, in
  the final pass.
- **14 pages**, two-column, IEEEtran `conference` class, references included, no appendix.
  This is **4 pages over** the venue's 10-page limit now that the full manuscript is drafted
  (up from 9 pages when six sections were still red stubs). Closing that gap is a separate,
  deliberately unstarted cut pass — see the cut-list analysis delivered alongside this
  conversion; nothing has been cut from `main.tex` to hit 10 pages yet.
- **All 32 citation keys used in the text resolve** against `references.bib` and appear in
  the rendered bibliography. No citation key is missing a bibliography entry.
- A handful of `Overfull \hbox` warnings remain, all under 13pt (under two-tenths of an inch)
  after two fixes made during the resync: Table II's `not_computable_appworld_unreachable`
  cell was overflowing its column by 132pt (nearly 2 inches) and the §VIII trajectory-replay
  table was overflowing by up to 70pt in single-column form. Both are fixed — the Table II
  identifiers now break at underscores via the existing `\brk` macro, and the §VIII table
  moved to `table*`. The remaining sub-13pt overfulls are cosmetic (dense inline math in
  Table I, a few long monospaced tokens) and pre-date this resync.
- The MedAgentBench, tau2-bench, AgentDojo, and MM-ToolSandbox papers each have their commit
  or table citation reproduced from `paper/main.md`; the `\S` section-reference macro,
  `\cite`, `\ref`, and `\label` cross-references were all checked and resolve.

## What is deliberately incomplete

`paper/main.md` is now fully drafted (abstract plus all eleven sections), so `main.tex` no
longer carries `\pendingblock` stubs for whole sections. What remains genuinely outstanding is
exactly what `paper/main.md` itself still marks as open, reproduced via the `\pending{Nk}{...}`
macro (red, inline) rather than guessed or filled in:

| Marker | Location | What it names |
|---|---|---|
| N1 | §IX (Table III, per-benchmark totals) | `report/render.py` — this script does not exist yet; Table III is rendered as a red placeholder float (`tab:table3`), not real content |
| N7 | §V (dual-annotation agreement result) | `experiments/annotation_protocol.md` protocol run — not yet executed |
| N12 | §IX (coordinated-disclosure log) | disclosure log dated 2026-09-10 — in the future relative to this draft |

Three figures named in the Markdown source have not been drawn and are rendered as boxed red
placeholders (Figure 1 in §II, Figure 2 in §IV) or as the Table III placeholder float above;
§V's worked-contract listing and §VIII's verdict-flip discussion do not require a figure and
have none pending. See "Known rough edges" below for their current footprint and why their
final size is not yet known.

The **abstract** is drafted, reproduced verbatim from `paper/main.md`. The stub-era comment
block that used to carry the abstract's "committed shape" (what it had to lead with, promise,
and never claim) has been removed from `main.tex` now that the real text satisfies it; a short
comment records that the shape was met and that an earlier headline-count inconsistency in
that block (4 vs. 5, and 7 vs. 4) is resolved in the current source.

No appendix is used anywhere in this project. The venue's CFP forbids one, and `PAPER-OUTLINE.md`
already reassigns everything that would have gone there (patch diffs, the permutation test) to
the artifact repository or drops it entirely.

## Numbers, and where each one comes from

Every number below is reproduced from `paper/main.md` exactly as written; none was changed
during conversion.

- **§I contribution 5, §IX's opening sentence, and the abstract** are now consistent: eight
  verified instances, four headline-eligible benchmark-class cells across four benchmarks. The
  stub-era discrepancy this section used to document (three different headline counts — 4, 5,
  and 7 — across the abstract placeholder, §I, and §IX) is resolved in the current
  `paper/main.md`; nothing here needed reconciling with `report/findings.jsonl` during this
  resync because the drafted prose already agrees with itself.
- **§IX's findings table** lists 8 numbered instances, of which two are explicitly marked
  non-headline in the table itself: instance 3 (tau2-bench, Partial Effect) is
  maintainer-annotated, and instance 4 (MedAgentBench, Ungrounded Oracle) is an evaluator
  property rather than one of the six tool-layer classes.
- **One numeric fix was needed during this resync.** §II's "published numbers" paragraph said
  MedAgentBench's Table 3 covers "all 11 evaluated models" in one sentence and "the 12
  evaluated models" two sentences later — a leftover from the stub-era draft. The current
  `paper/main.md` states 12 in both places; `main.tex` now matches it (12/12).

Other headline figures carried through unchanged, with their source of record:

- MedAgentBench Action SR range: 0.00%–71.33% across 12 models (Gemini-1.5 Pro highest,
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
  their column by a small amount (under 13pt / 0.2in), pre-dating this resync. A short layout
  pass — slightly rebalancing column widths, or dropping to `\scriptsize` in the findings
  table — would clear these; they do not affect content or pagination today.
- **Figures 1 and 2, and Table III, are not drawn.** The Markdown source specifies what each
  should show (the three-layer positioning diagram in §II; the worked tau2 dependency graph in
  §IV; per-benchmark totals in §IX's Table III) but none exists as an image, TikZ source, or
  rendered table yet. All three are rendered as boxed red `\pending{...}` floats with a real
  `\caption`/`\label` so cross-references resolve and the float correctly gets its own
  figure/table number (an earlier version of the Table III placeholder sat outside any float
  and silently inherited the preceding real table's number — fixed during this resync). Their
  final size is genuinely unknown: Table III as real data is likely *smaller* than its current
  red explanatory box, while Figures 1 and 2 as drawn diagrams could be larger or smaller than
  their current placeholder boxes. The current 14-page count should not be read as a tight
  estimate of the true figure/table footprint.
- **10-page limit: 4 pages over.** See the cut-list analysis delivered alongside this
  conversion for specific, costed candidate cuts. No cuts have been made to `main.tex` itself.
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
