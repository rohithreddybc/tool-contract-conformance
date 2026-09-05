# Restructure plan — response to Wang's structural review of 2026-09-02

Written 2026-09-03; revised the same day after the item-3 literature search returned (`report/lit-tool-completion-verification.md`). Inputs: `MEETING-2026-09-02-WANG.md` (15 items, 4 tensions), `ieee-data-mining-paper-structure.md`, `paper/latex/main.tex` as committed at `10df1cf`, `PAPER-OUTLINE.md`, both `CLAUDE.md` files, the literature report. This is a plan. It edits nothing.

Measured state of the manuscript this plan starts from, so every estimate below can be checked:

| Quantity | Value | How measured |
|---|---|---|
| Pages | **10, exactly** (references on p. 10, no appendix) | `main.log` |
| Sections | 10 (I Intro, II Background+RW, III Instrument, IV Score-at-risk, V Contract spec, VI Checker, VII Detector validation, VIII Findings+Disclosure, IX Threats, X Conclusion) | `main.aux` |
| Prose words, body | 6,757; abstract 253 | script over `main.tex`, floats excluded |
| Table words | Table I disposals 504, Table V findings 494, others 118–176 | same |
| Hard-coded section cross-references `\S\,<roman>` | **67** (VII: 14, VIII: 11, IV: 7, III: 7, II: 6, I: 5, IX/V/VI: 3 each) | grep |
| Bold paragraph leads `\textbf{…}` at paragraph start | **39** | grep |
| Intro paragraphs | 9; the last three are 26, 32, 30 words | script |
| Bibliography | 43 entries, 41 cited, ~3 printed lines each at `\scriptsize`, no `url` fields (little compaction room) | `main.bbl`, `references.bib` |
| Commit hashes cited | `089ed46 1e8e932 54b74d4 9926011 9dacc79 dee7170 fc776b6` | grep |
| `numbers_audit.py` | exit 0, zero FAIL, three UNVERIFIABLE by design | run 2026-09-03 |
| Figures | none drawn; two specified in commented-out blocks (§II three-layer diagram, §IV tau2 dependency graph) | `main.tex` L244–256, L343–355 |

**What the literature search changed (2026-09-03).** Wang's instinct was right: state-based verification of task completion is a substantial literature (WebArena ICLR 2024, AppWorld ACL 2024, OSWorld NeurIPS 2024 D&B, AndroidWorld ICLR 2025, plus 2026 preprints). Two hits are close enough to shape the paper: **Agent-Diff** (arXiv:2602.11224, *under review* for KDD 2026 — preprint only, never to be cited as accepted) defines a "state-diff contract" and diffs replica-API state before and after an agent acts; **Gao and Zhou** (arXiv:2605.10448, preprint, no venue) audit whether a benchmark's outcome check is backed by stored evidence of the claimed state change. The distinction survives and is sharp: every one of these grades the *agent* using the benchmark's tool and environment layer as trusted ground truth; none re-executes the tool bodies against their own declared contracts. *They grade the agent using the tool; we grade the tool.* That inversion is now the sentence Related Work exists to carry. Consequences for this plan: Related Work needs a third subsection rather than a trim, the closest-prior-art table gains two rows, seven bibliography entries are added, the page budget worsens by about 3.4 column-inches (§4), and a hand-verification step is scheduled *before* the related-work rewrite (§3, 09-08), since nothing from the report enters the manuscript until the closest hits are read directly.

---

## 1. Strategy, and why the order is what it is

Three facts drive the order.

**The gate is real and it is about content, not shape.** Wang wants the abstract and introduction checked before anything else moves. So the first five days touch only those two objects, plus preparatory work that changes no prose anywhere. Nothing after §I is rewritten until the gate clears or until 2026-09-11, whichever comes first. The gate-wait days are not idle: they hold the literature hand-verification, the Scopus pass, and drafting in `paper/drafts/`, none of which touches `main.tex`.

**Renumbering is the one change that must happen exactly once.** The canonical six-section shape collapses ten sections into six, and 67 hard-coded `\S\,VII`-style references stop meaning anything the moment a section moves. Doing this incrementally, as sections shift one at a time, would mean re-reading 67 references on every move. The plan therefore converts every hard-coded numeral to a `\ref{sec:…}` label on Day 1, before any section moves, as a content-free mechanical commit. After that, every move renumbers itself and the compile catches any dangling reference. This is the single change that makes "small steady changes" safe instead of reckless.

**The page budget is net positive and the paper is at the limit.** Wang's additions plus the enlarged Related Work cost about 1.3 pages; his removals recover about 0.4. The 0.9-page difference has to come from somewhere, and §4 names where, line by line, in order. A compile-and-measure checkpoint on 2026-09-18 is the arbiter; the reserve list is pre-ordered so no cut is chosen under deadline pressure. With the enlarged Related Work the reserve is no longer optional; §4.4 says which items are expected to be spent.

The spine, in order: mechanical prep → abstract → introduction → [Wang gate] → literature hand-verification → related work → preliminaries → method → experiments → conclusion → page checkpoint → second Wang read → disclosure content → freeze. Every section move is a *move*, not a rewrite: text relocates with its numbers, bounds, tags, and hashes intact, and only glue prose is new.

**Model tiers (CLAUDE.md).** Cheap model: the Day-1 label conversion, bold-lead sweeps, `\paragraph` conversions, disclosure-package assembly, REFERENCES.md bookkeeping. Mid-tier: section moves and glue prose. High-capability model only for: the abstract, intro P1–P3, the Related Work inversion sentence and Subsection B, the Baselines-and-reference-points subsection (§6, T1), and the 09-23 final read.

**`paper/main.md` is frozen at its current state** as of Day 1, with a header line saying `main.tex` is now the structural source of record. The numbers audit reads `main.md` for artifact cross-checks and compares tracked quantities between the two files; since no number changes, this stays green. Backporting the restructure to `main.md` is post-submission work, if at all.

**No number from the new literature enters the manuscript unless it is logged in `EXTERNAL-VERIFICATION.md`.** The audit cannot cross-check a figure quoted from a paper it has never seen. The report's drop-in paragraph quotes Advani's "45–76 % of failures"; the recommendation is to cite Advani *without* the percentage. A related-work sentence does not need the number, and a number the audit cannot check is a liability.

---

## 2. Dependency graph

Work units, with what each blocks and why.

| Unit | Wang items | Blocked by | Blocks | Why the edge exists |
|---|---|---|---|---|
| **W0** Mechanical prep: `pre-restructure` tag, 67 refs → labels, protected-content check script, freeze `main.md` | 7 (mechanically) | — | everything | Section moves are unsafe until refs are symbolic; the check script is what lets each later day verify itself |
| **W1** Abstract, five-part | 1 | W0 | W2, gate | The intro mirrors the abstract's order; writing the intro first would mean writing it twice |
| **W2** Introduction, four paragraphs + challenges + roadmap; listing out, figure in | 2, 9, 11, 13 | W1, W9 | gate, W6 | The listing cannot come out until the figure that replaces it exists, or page 1 renders with a hole |
| **W3** Literature search — **returned 2026-09-03** | 3 | — | W3b | Done; results in `report/lit-tool-completion-verification.md`, Scopus queries listed there |
| **W3b** Hand verification of the closest hits (Agent-Diff, Gao & Zhou, Advani) + Scopus venue pass on all new entries | 3 | W3 | W4, W5, W9 (bracket labels) | Constraint from the coordinator: nothing from the report enters the manuscript until read directly. Also fixes which works are "closest", which decides the table rows |
| **W4** Related work → three lettered subsections | 4 | W3b, gate | W6 (boundary only) | The line between "related work" and "background" (which paragraphs move to Preliminaries) is drawn when RW is rewritten |
| **W5** Table I decision and compression | 5 | W3b, W4 | W4 (same commit) | The disposals that leave the table become the works that give each subsection its density; the two edits are one edit |
| **W6** Preliminaries and Notation (§III new) | 5, 6, 7 | W2, W4 | W7 | Notation is defined once here; the method section cannot be assembled until the symbols it relies on live in one place |
| **W7** Method (§IV new): contracts → checker → score-at-risk; step numbering fixed | 7, 13 | W6 | W8, W10 | Experiments' "implementation details" point at the method; the pipeline figure draws the method's subsection order |
| **W8** Experiments (§V new): the standard subsections; data availability moved; Threats folded in | 8, 10, 12 | W7, T1 decision | W11, checkpoint | The baseline slot cannot be written until T1 is settled with Wang |
| **W9** Concept figure, page 1 | 9 | W1 (framing); W3b for the bracket labels | W2 | see W2; the left-margin brackets name the state-based graders, so their names must be verified first (the figure ships on 09-06 with the four ICLR/ACL/NeurIPS benchmarks already publisher-confirmed; the preprint names are added on 09-11) |
| **W10** Methodology overview figure | 10 | W7 (subsection order) | checkpoint | The figure's stage order must match the method's subsection order or it misleads |
| **W11** Conclusion to one paragraph; relocate the maintainer-recommendation sentence | 11 | W8 | freeze | It names the final structure and the final result; written last so it is written once |
| **W12** Cross-cutting sweeps: bold leads → `\paragraph` or plain; short-paragraph scan; "must" scan | 12, 14, 15 | all section moves | freeze | Sweeping before the moves means sweeping twice |
| **W13** Disclosure content into Experiments per the pre-committed rule | — | 09-10 send; responses | freeze | Content arrives from outside on the maintainers' schedule |
| **CP** Page checkpoint, apply gives in order | — | W8, W10 | W11, W12 | The last big additions land in W8/W10; measuring earlier measures the wrong thing |

Critical path: W0 → W1 → W2 → gate → W3b → W4/W5 → W6 → W7 → W8 → CP → W11/W12 → freeze. W9, W10 and W13 run beside it. The gate is the only wait state; §3 fills it with W3b and drafting so a slow reply costs nothing until 09-11.

---

## 3. Day-by-day schedule, 2026-09-03 → 2026-09-27

Each day is one bounded unit that compiles and passes the standard gate on its own. **Standard gate (every commit to `paper/`):** (a) `pdflatex → bibtex → pdflatex → pdflatex` with zero errors, zero undefined references or citations; (b) page count recorded in the commit message; (c) `python experiments/numbers_audit.py` exits 0; (d) `python experiments/protected_content_check.py` exits 0 (written on Day 1, §7); (e) `git diff --stat` touches only the files the day names. Prose days add: (f) the `humanize` skill in formal register over the *new* prose only, per the parent `CLAUDE.md`.

**Page-count rule.** The two Wang deliverables (09-07 and 09-20) are sent at exactly 10 pages. Between 09-11 and 09-18 the count may float to 10.5 while sections are in transit, with the excess and the reserve item that will pay for it named in the commit message. From 09-18 onward, never above 10.

| Date | Day | Unit | Work (bounded) | Day-specific verification |
|---|---|---|---|---|
| **Thu 09-03** | 1 | W0 | Tag `pre-restructure` at HEAD. Add `\label{sec:…}` to all ten sections; replace all 67 `\S\,<roman>` with `\S\,\ref{sec:…}`. Write `experiments/protected_content_check.py` (§7). Add the freeze line to `main.md`'s header. Log the literature report's candidates in `REFERENCES.md` with status "publisher/arXiv-checked, Scopus pending"; nothing enters `references.bib` yet. | Page count still 10. PDF text diff against `pre-restructure` shows *no* change in rendered section numerals. Audit 0. Check script 0 against the untouched paper (it must pass on the baseline or it is wrong). |
| **Fri 09-04** | 2 | W1 | Rewrite the abstract to the five-part order. Keep the three honest headline numbers (precision ≥0.867 / 0 FP over 25 flags; recall weak; replay zero flips) as one sentence each. No "must". ≤ 300 words. | Word count ≤ 300. `grep -c "must"` in abstract = 0. No frequency words (§6 T4 lexical rule). Audit 0 — the abstract is not pattern-locked (§7), so wording is free, numbers are not. |
| **Sat 09-05** | 3 | W2a | Intro P1 (broad impact, no citation, existence-scoped), P2 (LiveClawBench; the state-based-grading benchmarks in one sentence as "existing evaluation reads the state the tool wrote and stops there" — the four publisher-confirmed ones only; the MedAgentBench hook sentence with the published-number link; **the challenge statement**, three bolded numbered challenges), P3 (approach). Remove the `lstlisting`; leave a `\pending` box sized 3.5 × 2.2 in where Fig. 1 will go so pagination is honest. Keep the venue-bridge paragraph. | Challenges present and numbered. The three MedAgentBench hedges still present verbatim (check script). Page count ≤ 10.25 (box is placeholder-sized). |
| **Sun 09-06** | 4 | W2b + W9 | Intro P4: the contributions list **unchanged** (item 5 is pattern-locked, §7) followed by one merged 130-word paragraph replacing the three short ones (confirmation-not-discovery, technique conceded, the MedAgentBench single result), then a 60-word roadmap. Draw Fig. 1 (§5.1) as TikZ or PDF in `paper/latex/figures/`; insert. Left-margin bracket names limited to publisher-confirmed works until 09-11. | Every intro paragraph ≥ 3 sentences. "seven of eight findings surfaced manually" sentence present. Fig. 1 legible at 3.5 in. **Page count exactly 10.** |
| **Mon 09-07** | 5 | gate | Read-through of abstract + §I only; `humanize` formal pass on them; build the PDF; **send abstract, introduction, and Fig. 1 to Wang**, with the §8 confirmation list and a two-line summary of the item-3 result ("your instinct was right; the distinction survives; details Thursday"). Assemble the four disclosure packages from `FINDINGS-VERIFIED.md`: per-finding reproduction command + proposed repair (cheap model). | Sent. Packages drafted. |
| **Tue 09-08** | 6 | **W3b** | **Hand verification, before any related-work text exists.** Read Agent-Diff (arXiv:2602.11224) and Gao & Zhou (arXiv:2605.10448) directly, and Advani (arXiv:2606.09863) since it will be cited. Confirm by hand, with section/page quotes: (a) Agent-Diff's "state-diff contract" is an *agent* oracle over replica-API state; (b) the replica API's implementation is never checked against its declared behaviour; (c) Gao & Zhou's worked example (Save clicked, record unchanged) and that the tool body is out of their scope; (d) venue status of each — Agent-Diff *under review*, cite as preprint. Record all of it as `EXTERNAL-VERIFICATION.md` Task 4. Then run the report's ten Scopus queries through the logged-in browser session (never enter credentials; a login wall is reported, not worked around); update every new entry's status column in `REFERENCES.md`. | Task 4 entry exists with quotes. Ten Scopus rows logged with outcome. Nothing under `paper/latex/` changes today. |
| **Wed 09-09** | 7 | gate wait | Off-manuscript drafting only, from verified claims: RW Subsections A, B, C and the six table rows in `paper/drafts/related-work.md`, with the inversion sentence written by the high-capability model; the T1 Baselines paragraph in `paper/drafts/baselines.md`. Integrate Wang's reply to abstract/intro if received (one commit). Dry-run each disclosure reproduction command from a clean clone. | If Wang replied: standard gate, 10 pages. Reproduction commands run clean. Drafts cite only entries with a `REFERENCES.md` status. |
| **Thu 09-10** | 8 | W13 | **Disclosure day.** Send to the four maintainer teams. Fill `report/disclosure_log.md` rows (date, channel, findings). No restructuring today. | Audit 0 (the disclosure-date check reads the log). Log rows dated 2026-09-10. |
| **Fri 09-11** | 9 | W4 + W5 | Merge the draft: `\subsection`s **A. How agent benchmarks grade tool tasks** (WebArena, AppWorld, OSWorld, AndroidWorld, tau2-bench, AgentDojo: they read the state the tool wrote and stop there), **B. Verifying that a task actually completed, and auditing the verifiers** (Agent-Diff, Advani, Gao & Zhou, AJ-Bench, Tool-Veritas; closes with the inversion sentence and the cross-layer "why every prior audit missed it" paragraph), **C. Benchmark audits and contract checking** (BenchGuard/ABA/SafeAudit, ABC, ToolGate cluster, ToolFuzz, ConTract/IcePICK/AGORA+; the technique concession). Table I → six rows inside B (§6 T2). Seven new `.bib` entries, each with the venue exactly as confirmed. Fig. 1 bracket labels completed. The "In sum" paragraph deleted (its sentence lives in §I P4). Proceed even if Wang's reply is still out; framing feedback is propagated later. | Each subsection cites 3–6 works. All nine original disposal cite-keys still present, plus the seven new keys (check script). Agent-Diff's entry reads "preprint" and nothing else. "None of the audits we survey" scoping intact. Page count ≤ 10.5, excess named. |
| **Sat 09-12** | 10 | W6 | New §III Notations and Preliminaries: the tuple `(pre, post, args, result)`; verdict lattice; three grounding tiers; Table II taxonomy (moved, untouched); the benign-simplification principle as a boxed definition; result–state signal; Ungrounded Oracle; a 60-word "audited benchmarks and their evaluator designs" paragraph (absorbs the "tau2-bench's numbers" paragraph). Old §III's "invisible downstream" paragraph deleted (duplicate of §I/§II). | Taxonomy table 6 rows, unchanged. Every symbol used in §IV–§V is defined here (grep each). |
| **Sun 09-13** | 11 | slack 1 | Catch-up. If unused: Fig. 2 drawn. | — |
| **Mon 09-14** | 12 | W7a | New §IV Method skeleton: A The contract specification (old §V), B The conformance checker (old §VI), C Score-at-risk dependency analysis (old §IV). Pure moves. Replace "Step 1/2/3" run-ins with a three-item `enumerate` (item 13). | All seven commit hashes present. Score-at-risk table moved intact: six rows, basis tags, denominators (check script). |
| **Tue 09-15** | 13 | W7b + W10 | Insert Fig. 2 at the head of §IV; fold old §VI's snapshot-invoke-snapshot prose into its caption. Bold leads in §III–§IV → `\paragraph{}` where they name a sub-topic, plain text otherwise. | Fig. 2 stage order == §IV subsection order. |
| **Wed 09-16** | 14 | W8a | New §V Experiments skeleton, pure moves: A Experimental setup (Table VI totals + benchmarks/commits paragraph); B Baselines and reference points (empty slot, T1); C Evaluation metrics; D Implementation details + Data availability; E Main results (findings Table V, score-at-risk discussion, recall Table IV, evaluation-impact null); F Sensitivity analyses (miss decomposition; annotator A/B agreement); G Threats to validity (the ten limitations, verbatim, as `\paragraph{}` run-ins). Old §VIII opening paragraph's 8→4 accounting kept once (prose), Table VI footnote trimmed to a pointer. | Ten limitation lead phrases present. Eight findings rows + Surfaced-by column present. Recall table 6 operator rows. "a null, not a gap" paragraph present. Page count ≤ 10.5, excess named. |
| **Thu 09-17** | 15 | W8b | Write B (from the 09-09 draft, T1 wording), C glue, D (freeze commits `9dacc79`/`54b74d4`, cosmic-ray 8.7.0, seed 1, Python versions, probe-corpus provenance — every new number hand-checked against `PROVENANCE.md`/`ARCHITECTURE-FINAL.md` and listed in the commit message, because the audit's cross-file check cannot see tex-only numbers). Data availability: repo name + DOI, after D. Bold leads in §V → `\paragraph{}`. | Audit 0. New numbers listed in commit message with their source file. |
| **Fri 09-18** | 16 | **CP** | **Page checkpoint.** Compile, measure. Apply §4.3 gives G1–G12 in order until 10 pages; then reserve Z1–Z9 in order if still over. Stop at 10. | **Exactly 10 pages.** Check script 0. Audit 0. |
| **Sat 09-19** | 17 | W11 + W12 | Conclusion → one ~200-word paragraph; the "never let a grader's success condition be satisfied by a fabricated string" sentence moves to the end of §V.E's MedAgentBench paragraph. Whole-paper sweeps: no `\textbf{` at paragraph start outside `\paragraph`; no paragraph under three sentences; "must" scan on abstract + §I. | `grep -c '^\\textbf{' main.tex` = 0. Short-paragraph scan clean. 10 pages. |
| **Sun 09-20** | 18 | slack 2 / read | Full read-through against the checklist's six-section inventory. **Send the full draft to Wang** (the outline's own Sep-20 draft gate). Re-check Agent-Diff's status (a KDD decision may have posted; cite the confirmed state only). Confirm workshop fallback deadlines (SE4AgenticAI 10-10 known; verify BPOD and Trustworthy AI Pipelines). | Section inventory: exactly I–VI. Every table and figure discussed in prose by `\ref`. |
| **Mon 09-21** | 19 | Wang r2 | Integrate Wang's second-round structural feedback. Structural only; no new claims. | Standard gate, 10 pages. |
| **Tue 09-22** | 20 | W13 | Disclosure responses received so far → §V.E per the pre-committed rule (substance / neutral non-response / contested). Replace `\pending{N12}` with prose; log rows updated. `humanize` formal pass over all new prose (abstract, §I P1–P3, §II A–C glue, §III glue, §V.B, §V.D, conclusion). | `grep -c pending main.tex` body uses = 0. Audit 0. |
| **Wed 09-23** | 21 | verify | `make reproduce-results` offline (validate, tables, audit, tests); `git checkout report/ab_*` afterwards (known pytest side effect). Clean-clone compile. Overfull boxes ≤ 13 pt. Final read by the high-capability model against §7's must-not-change list. | All green. Zero FAIL, zero `\pending`. |
| **Thu 09-24** | 22 | slack 3 | Absorb any late Wang or maintainer input. | — |
| **Fri 09-25** | 23 | freeze | Final disclosure-log update. Final venue-status check on the three preprints. Tag `submission-candidate`. Prepare arXiv source from the same tag (outline: preprint goes up submission week). | Tagged. PDF at 10 pages from the tag. |
| **Sat 09-26** | 24 | submit | CyberChair portal fields checked (affiliations, required statements). **Submit.** | Submission receipt saved. |
| **Sun 09-27** | 25 | deadline | Nothing new. If 09-26 slipped, submit by noon. | — |

Three slack days (09-13, 09-20 partial, 09-24) plus the 09-26 buffer. The disclosure day carries no manuscript work by design. If W3b on 09-08 finds that either close hit *does* audit tool bodies against declared contracts, stop and report before 09-09: that would be a novelty-claim problem, not a scheduling one, and it goes to Wang before any further restructuring.

---

## 4. Page-budget arithmetic

Units: column-inches (ci). IEEEtran conference has two 3.5 in columns of 9.25 in, so **one page = 18.5 ci**. Measured density of this manuscript is ~940 words per non-reference page including headings and floats; solid prose runs ~70 words/ci. Prose deltas below use **60 words/ci**; figures and tables use their geometry; bibliography entries use the measured ~3 lines each at `\scriptsize` (~0.35 ci). Estimates carry ±15%; the 09-18 checkpoint, not this table, is the arbiter.

### 4.1 Additions (Wang's requests, plus the enlarged Related Work)

| # | Item | Estimate | ci | Running |
|---|---|---|---|---|
| A1 | Intro P1, broad impact, ~90 words (new; today's first paragraph is LiveClawBench, which moves to P2) | 90 w | +1.5 | +1.5 |
| A2 | Challenge statement, three bolded numbered challenges, ~120 words | 120 w | +2.0 | +3.5 |
| A3 | Three short end-of-intro paragraphs (88 w) → one 130-w paragraph + 60-w roadmap | +100 w | +1.7 | +5.2 |
| A4 | Fig. 1 concept figure, single column 3.5 × 2.2 in + 3-line caption + float skips | geometry | +2.7 | +7.9 |
| A5 | Fig. 2 pipeline figure, single column 3.5 × 2.6 in + 4-line caption (double-column would be +4.8) | geometry | +3.3 | +11.2 |
| A6 | Three RW `\subsection` headings | 3 heads | +0.6 | +11.8 |
| A7 | RW prose engaging the state-based-verification literature: Subsection A's one-sentence characterization of four benchmarks (~40 w), Subsection B's paragraph on Agent-Diff / Advani / Gao & Zhou / AJ-Bench plus the inversion sentence (~140 w) | 180 w | +3.0 | +14.8 |
| A8 | Seven new bibliography entries (WebArena, AppWorld, OSWorld, AndroidWorld, Agent-Diff, Advani, Gao & Zhou) | 7 × 0.35 | +2.5 | +17.3 |
| A9 | Seven Experiments `\subsection` headings | 7 heads | +1.6 | +18.9 |
| A10 | Baselines-and-reference-points paragraph, ~110 words | 110 w | +1.8 | +20.7 |
| A11 | Evaluation-metrics glue | +40 w | +0.7 | +21.4 |
| A12 | Implementation details, ~80 words | 80 w | +1.3 | +22.7 |
| A13 | Preliminaries glue and one-place notation definitions | +50 w | +0.8 | +23.5 |
| A14 | Abstract growth Wang permits | +30 w | +0.5 | **+24.0** |

**Additions: +24.0 ci ≈ +1.30 pages** (of which the literature result accounts for +3.4).

### 4.2 Removals Wang mandates

| # | Item | Estimate | ci | Running |
|---|---|---|---|---|
| R1 | Page-1 `lstlisting`: 9 framed `\scriptsize` lines + skips | geometry | −1.6 | −1.6 |
| R2 | Table I: 504 w `\scriptsize` `table*` (~4.5 ci) → **six-row** table (~3.4 ci: Agent-Diff, Gao & Zhou, Tool-Veritas, ToolFuzz, BenchGuard cluster, ABC) + five one-sentence disposals in prose (~1.8 ci). **Net +0.7.** Full removal with all disposals kept in prose would be about *+3.5* (the same words at body size cost more than at table size, and there are now more of them); full removal with disposals dropped would be −4.5 but violates the standing constraint (§7) | geometry | +0.7 | −0.9 |
| R3 | 39 bold leads: label-only lines removed (−); sub-topic leads → `\paragraph{}` run-ins (≈0) | mixed | −0.5 | −1.4 |
| R4 | Conclusion 399 w → ~200 w; one sentence relocated | −200 w | −2.5 | −3.9 |
| R5 | Merge-driven duplicates: old §III "invisible downstream" (−50 w), §II "In sum" (−60 w), §I MedAgentBench prose once Fig. 1 carries it (−40 w), "Step 1/2/3" run-ins folded into Fig. 2 caption (−30 w) | −180 w | −3.0 | **−6.9** |

**Removals: −6.9 ci ≈ −0.37 pages. Net after Wang's own list: +17.1 ci ≈ +0.92 pages. The paper is at the limit, so this must be paid.**

### 4.3 What gives — named, in application order (checkpoint 09-18)

| # | Item | ci | Running |
|---|---|---|---|
| G1 | The MedAgentBench narrative is told in §I, twice in §II, §III, §IV and §VIII. Consolidate to: Fig. 1 caption, one RW paragraph (why prior audits missed it), one Findings paragraph (chain + published numbers). Hedges verbatim; Action SR range, 69.67 %, "12 evaluated models" unchanged | −1.5 | −1.5 |
| G2 | Old §VIII opening paragraph vs Table VI footnote: the 8→4 accounting told once | −1.0 | −2.5 |
| G3 | Old §VII "Achieved N" and "One refreeze cycle" paragraphs restate old §VI and Threats limitation 9; single telling, numbers kept | −1.0 | −3.5 |
| G4 | SE-lineage paragraph 200 → 120 words; all fifteen citations kept (citations are cheap, prose is not) | −1.2 | −4.7 |
| G5 | "Experiment frame need not nest" paragraph −60 words around unchanged numbers and the `False` result | −0.9 | −5.6 |
| G6 | Result–state-signal paragraph and the consumer-side scope note, −70 words, claim intact | −1.1 | −6.7 |
| G7 | Agreement-study paragraph −60 words; every disclosure (post-hoc rule, contaminated stratum, the flip, n=2 of 9) kept | −0.9 | −7.6 |
| G8 | Old §VI checker prose absorbed by Fig. 2 caption (beyond R5) | −0.8 | −8.4 |
| G9 | Evaluation-impact paragraph −50 words; N, populations, "conditional validity" interpretation intact | −0.8 | −9.2 |
| G10 | Venue-bridge paragraph 100 → 60 words; the bridge (E-W1) is required, its length is not | −0.7 | −9.9 |
| G11 | "tau2-bench's numbers" paragraph 80 → 50 words when it moves to §V.A; the no-causal-link hedge kept verbatim | −0.5 | −10.4 |
| G12 | Bibliography: drop the 21 redundant `note = {Preprint.}` fields where `archivePrefix` already says arXiv; shorten the `medagentbench25` note. No entry, DOI, or venue removed | −0.5 | **−10.9** |

**After gives: +6.2 ci ≈ +0.34 pages still over.**

### 4.4 Reserve — ordered, stop when at 10 pages

With the enlarged Related Work, **Z1–Z6 are expected to be spent, and Z7 is likely.** Raise Z6 and Z7 with Wang on 09-07 so neither needs a round-trip on 09-18.

| # | Item | ci | Running |
|---|---|---|---|
| Z1 | Both figures capped at 1.8 in tall | −1.2 | −1.2 |
| Z2 | Table I to four rows (Agent-Diff, Gao & Zhou, Tool-Veritas, ToolFuzz); BenchGuard cluster and ABC to prose | −1.0 | −2.2 |
| Z3 | Table VI footnote folded into caption after G2 | −0.5 | −2.7 |
| Z4 | Threats paragraphs 5 and 9 tightened by 25 words each; the limitation's claim untouched | −0.8 | −3.5 |
| Z5 | Threats ranking paragraph merged into limitation 1's last sentence | −0.5 | −4.0 |
| Z6 | One of each duplicate-precedent pair dropped (`jcontractor05`/`jass01`; `restler19`/`godefroid20`; `segura16`/`segura18`) — **needs Wang**; not a disposal, so the standing rule allows it, but a citation change is a co-author's decision | −1.2 | −5.2 |
| Z7 | All ten Threats limitations tightened ~12 % with a strict rule: each keeps its lead phrase, every number, and its mitigation sentence | −1.6 | −6.8 |
| Z8 | Abstract held at ≤ 253 words | −0.5 | −7.3 |
| Z9 | Table V "Quoted evidence and disposition" cells: disposition prose in rows 5 and 7 trimmed ~40 words; quoted evidence untouched | −0.6 | **−7.9** |

The reserve closes the gap with about 1.7 ci to spare after Z9, or with Z7 only if Z9 is not needed; either way the margin is inside estimation error. Consequences: every word count in §4.1 is a **cap**, not a target; figure heights are caps; and Subsection B's paragraph is written to 140 words, not to comfort. If Wang insists on Table I's full removal (§6 T2 fallback), add +2.8 ci (nine disposals plus the two new ones as prose), which exhausts the reserve entirely and makes Z7 and Z9 mandatory; that is the number to put in front of him.

---

## 5. The two figures

### 5.1 Fig. 1 — concept figure, page 1, single column, 3.5 × 2.2 in (cap 1.8 in under Z1)

One figure does two jobs: Wang's page-1 "shape of the idea", and the commented-out §II three-layer positioning diagram, which the outline called the figure that "carries positioning work no paragraph fully replaces". Merging them is why A4 is affordable. The literature result makes the positioning half more valuable, not less: the figure can now show *where* the state-based graders sit.

**Layout.** Three horizontal bands, top to bottom, each a rounded rectangle spanning the column:

1. **Interface — what the agent reads.** Four small labelled chips inside: `docstring`, `schema`, `prompt text`, `return string`.
2. **Implementation — what the call does to the world.** A box `tool(args)` with a left-pointing `pre` snapshot and right-pointing `post` snapshot, and an arrow `pre → post` labelled *state transition*.
3. **Evaluator — what the score reads.** Two inlets: one from `post` labelled *state-grounded*, one from a `transcript` icon labelled *transcript-grounded*; output `verdict ✓/✗`.

**Left margin, three vertical brackets, top to bottom of the margin.** (i) "Benchmark audits" (BenchGuard, ABA, SafeAudit, ABC) spans bands 1 and 3 with a visible gap at band 2. (ii) "State-based graders" (WebArena, AppWorld, OSWorld, AndroidWorld; Agent-Diff and Gao & Zhou added 09-11 after verification) is a bracket on band 3 with an arrow *into* band 3 from band 2's `post`, labelled *reads state as ground truth* — they look at what the tool wrote, not at whether it wrote what it said. (iii) "This work" spans the two edges 1→2 and 2→3, drawn as the edges rather than the bands, labelled *advertised → implemented* and *implemented → scored*. The gap in (i) and the arrowhead direction in (ii) are the claim: everyone else consumes band 2's output; nobody tests band 2 against band 1.

**Right side, the worked instance in one accent colour, dashed.** Band 1: `"POST … executed successfully"` (return string). Band 2: `payload parsed, never read; post = pre`. Band 3: grader gated on the *same* string, reading the transcript; verdict ✓. A small label at the band-2/3 junction: *mutually consistent*.

**Caption (≤ 3 lines).** "The tool contract is the pair of edges: what the interface advertises must be what the implementation does, and what the implementation does is what the evaluator scores. Benchmark audits inspect bands 1 and 3; state-based graders read band 2's output as ground truth; neither tests band 2 against band 1. Right: MedAgentBench, where the tool's fabricated success string is also the grader's gate condition, so each band is internally consistent and no single-layer audit sees a defect."

**Claims it supports.** §I P2 (existing evaluation reads returned state and stops there — Wang's own phrasing for Subsection A); §II B's inversion sentence (they grade the agent using the tool; we grade the tool); §II B's cross-layer paragraph; the MedAgentBench chain in §V.E. Monochrome plus one accent; legible at 3.5 in; no text under 7 pt; bracket labels are short names only, citations stay in prose.

### 5.2 Fig. 2 — methodology overview, head of §IV, single column 3.5 × 2.6 in (cap 1.8 in under Z1; double column only if CP has 2 ci spare, which it will not)

Left-to-right pipeline, four stages, whose order **is** §IV's subsection order (A → B → C) with the validation arms as a side branch feeding §V.

1. **Advertised surfaces → Contract.** Inputs: `docstring, schema, prompt, return | README, external standard`. Output box: *one YAML contract per mutating tool*, listing clause kinds `pre · effects · frame · success_signal · invariants`. Each clause carries a provenance tag `file:line:"quote"` and a tier badge: **agent-visible** (headline-eligible), maintainer-annotated, inferred. Small note: *only agent-visible clauses enter headline counts*.
2. **Conformance checker.** Two lanes. Static: `5 AST checks → candidate sites (a person reads them)`. Dynamic: `fresh env → snapshot pre → invoke(args) → snapshot post → evaluate clauses` → verdict lattice `CONFORMS | VIOLATES + minimal witness | UNTESTABLE + reason (stays in denominators)`. Frozen-at marker on the box: `checker-freeze-v2, 54b74d4`.
3. **Score-at-risk trace, three static steps.** ① VIOLATES clause → written state paths (predicate AST). ② Grader source → read sites, provenance-classified `state / transcript / mixed`. ③ Tasks whose verdict depends on the intersection, from the pinned task file. Output row schema: `at-risk / total · basis {whole_state_hash, collection_only, exact_field} · oracle grounding`. Note: *bases never pooled*.
4. **Validation arms (side branch into stage 2, dashed).** Closed-world: six operators `M-PHANTOM … M-RESET` → recall (Wilson LB, design-effect adjusted) and precision. Open-world: `cosmic-ray` → escape rate (lower bound on taxonomy incompleteness). Replay: gold trajectories against as-shipped vs one-hunk-patched tools → verdict flips. Marker: `detector_analysis_plan.md @ 9dacc79, before any mutant`.

**Caption (≤ 4 lines).** Names the three subsections by letter, states that stages 1–3 are static and model-free, that stage 4 is where the numbers in §V come from, and that the two freeze markers are the pre-registration commits cited in §V.

**Claims it supports.** The method order; the "three steps" of score-at-risk (item 13 fixed structurally); the pre-registration ordering; the tier rule. It also lets old §VI shrink to a caption (G8).

---

## 6. The four tensions — resolutions

### T1. Baselines — the hardest judgment

**Does "detector validation as the honest analogue" survive a data-mining reviewer?** Partly. A reviewer who scans for a *Baselines* heading wants a comparison against something that already exists. Injected-defect precision and recall is a validation of our own instrument against our own mutants; put alone under a heading that says "Baselines", it invites two objections at once: "this is not a baseline, it is your sanity check", and, because recall sits at Wilson lower bounds of 0.02–0.36, "the method loses". So the analogue is necessary but not sufficient. The literature result adds a third objection to pre-empt: "why not compare against Agent-Diff or the state-based graders?" — the answer is that those systems are not competitors but *subjects*: their ground truth is the layer we audit, so a comparison would be category-confused.

**Recommendation.** Title the subsection **"Baselines and Reference Points"** and give it four explicit comparison rows, none invented, each labelled for what it is:

1. **Incumbent practice: manual source audit.** This is the genuine baseline, and it is already in the paper as the Surfaced-by column: seven of eight findings were found by a person reading source; the checker discovered one (`invite_user_to_slack`, static) and reproduced three of the four headline cells dynamically. The paper does not claim to beat the incumbent. It claims two things the incumbent cannot give: a precision-favoring flag (0 FP over 25 mutation-arm flags) and a mechanical trace from a defect to the verdicts it can reach. Stating the discovery rate as 1 of 8 in the baseline row makes the self-critical content structurally impossible to bury (T3).
2. **Prior audits and state-based graders on the same artifacts, by construction.** The five surveyed audits map zero of six defect classes across 27 categories (`GATE.md` §2), and all five reported nothing on MedAgentBench's tool layer; the state-based graders (§II A–B) read the defective layer's output as ground truth and so cannot flag it in principle. This is the novelty claim restated as a comparison. It must say *by construction, not by re-execution* — we did not run their tools; their schemas cannot express a success signal decoupled from state. Phrased that way it is not a strawman: it is a checkable property of published designs.
3. **External precision reference.** AGORA+'s 80 % on REST invariants, already cited, explicitly *not* a same-task comparison; a reference point from the nearest technique family.
4. **The injected-defect validation.** Closed-world recall and precision, open-world escape rate, replay flips: the honest analogue, introduced with one sentence: *no prior tool-contract checker exists for these benchmarks, so a head-to-head comparison would be against a system we would have to build ourselves.*

**Does this contradict the novelty claim?** No. The novelty claim is that no prior *audit* tests this layer; the authors' own manual reading is not prior work, and row 2 is the novelty claim itself. **Does it satisfy the template?** Yes: the heading exists, the reader finds what we compare against and how much we improve (precision, score-tracing) and where we do not (discovery), and the section says plainly why a conventional baseline does not apply, which is exactly the checklist's caveat for audit papers.

**Needs Wang's confirmation:** the heading wording and the inclusion of row 1 (a co-author may prefer "Reference points" without the word "Baselines"; the plan's view is that the word should be present because reviewers grep for it).

### T2. Table I

**Recommendation: compress, do not remove — and the search Wang asked for is the reason.** Six rows, retitled "Closest prior work and the distinction", inside Subsection B: **Agent-Diff** (a "state-diff contract" one layer up — the reviewer magnet, because the word *contract* appears in a neighbouring paper), **Gao & Zhou** (the closest articulation of Wang's own worry, applied to the grading script rather than the tool), Tool-Veritas (same audited artifact, tau2 retail), ToolFuzz (nearest engineering neighbour), the BenchGuard/ABA/SafeAudit cluster as one row, and ABC checklist (the τ-bench version-window disposal a reviewer who knows that paper will check). The remaining disposals (ToolGate cluster, ContractGuard, 34-fault taxonomy, construct-validity review, LiveClawBench, AJ-Bench, Advani, REAL) become one sentence or one clause each inside the lettered subsections, where they double as the works that give each subsection its density.

**Reasoning.** Four facts. (i) The arithmetic in §4.2 R2: the table is `\scriptsize` in three columns; the same words as body prose cost more than the table does, and full removal with all disposals kept in prose would cost about +3.5 ci, not save space. Full removal saves space only if the disposals are dropped, which the standing rule (`RESUME-STATE.md`: "Never cut §II's eight disposals") forbids. (ii) The table is the paper's defence against the likeliest desk rejection — "prior work already does this" — and each row is a named, checkable distinction. (iii) The item-3 search *grew* the set of works needing a named distinction from nine to eleven, two of them close enough that a reviewer will bring them up unprompted; a table is the compact way to hold six named distinctions. (iv) Wang's actual objection is that comparison matrices read as survey convention; six rows of nearest neighbours, two of them from the search he requested, read as positioning, which is what he says Related Work is for.

**What to tell Wang.** "Your Related Work brief is that the section exists to let a reviewer judge novelty. The search you asked for found the literature you suspected, and two papers in it are close enough that a reviewer will name them. The table's rows are that judgment, one competitor per row; we cut it to the six a reviewer would cite against us, led by the two your search surfaced, and moved the rest into the subsection prose. Full removal would cost about three column-inches, not save them, because the distinctions have to live somewhere."

**Fallback if he insists:** all eleven as prose across A–C; +2.8 ci paid from the reserve, which then runs to Z9 (§4.4).

### T3. Self-critical content — where each item lands

An internal panel called these a credibility strength; a conventional results section could bury them. Each gets a fixed address and a check-script assertion (§7).

| Item | New address | Assertion |
|---|---|---|
| Weak recall (Wilson LBs 0.000–0.359) | §V.E Main results: Table IV immediately followed by the "Recall as shipped is low" paragraph and the 2/29/2 miss decomposition; the diagnostic's post-hoc status stays in the first sentence | table + phrase "Recall as shipped is low" |
| Null replay result | §V.E, own `\paragraph{Evaluation impact: a null, not a gap}`; keep "conditional validity, not a null result", N=5 provisional, F3 near-exhaustive / F2 not; plus one sentence in the abstract's part 5 | phrase + abstract sentence |
| Seven of eight surfaced manually | three places: Table V Surfaced-by column; §I P4 merged paragraph ("confirmation and score-tracing, not discovery"); §V.B row 1 as the incumbent baseline | column header + both phrases |
| tau2 zero denominator and the stale-cache disclosure | §V.E, unchanged paragraph; Threats limitation 2 | phrase "zero were behaviourally live" |
| One refreeze cycle | Threats limitation 9 (single telling after G3), with the v1→v2 commits | both hashes |
| Post-hoc agreement scoping rule | §V.F Sensitivity analyses, unchanged disclosure | `dee7170`, `fc776b6` |

The abstract's last two sentences today carry weak recall and zero flips. The rewrite keeps both in part 5, compressed, never dropped: Wang's "headline result" for this paper *is* an honest one.

### T4. Prevalence language

The intro's new P1 and the abstract's first sentence open on stakes without a frequency claim. **Lexical rule, enforced by the check script on the abstract and §I P1–P3:** none of `widespread`, `pervasive`, `prevalent`, `commonly`, `most benchmarks`, `many benchmarks`; and, per Wang, no `must` used for necessity. The scoping sentences survive verbatim: "None of the audits we survey", Threats limitation 7 ("No prevalence claim … is supportable"), and the conclusion's "existence proofs, not a survey". The stakes paragraph is written about *what a defect at this layer does to a published number*, which is a mechanism claim, not a frequency claim. The new Subsection A carries a related risk: describing "how agent benchmarks grade tool tasks" over four named benchmarks must not slide into "all benchmarks grade this way"; the sentence is scoped to the works cited.

---

## 7. What must not change

The check script `experiments/protected_content_check.py` (Day 1, ~80 lines, exit non-zero on any miss) asserts each of these literally against `main.tex`, and is run at every commit to `paper/` alongside the numbers audit.

1. **The ten limitations** — each lead phrase present: taxonomy-not-the-space; tau2 no usable number; sample sizes short for four of six; M-RESET no site; subprocess boundary; N=5 provisional; anchor-driven selection; frame-path grammar gap; repository history; one refreeze cycle. Plus the ranking sentence (may merge under Z5, phrase kept).
2. **The eight findings rows** with their numbers 1–8, tools, classes, tiers, and the **Surfaced by** column header; the `suspend_line` footnote; Table VI totals row `34 / 34 / 8 / 8 (4)`.
3. **The taxonomy table**: six class names, six rules, status column (four field-observed, two mutation-only).
4. **Basis tags** `whole_state_hash`, `collection_only`, `exact_field` and the sentence "never pooled"; every score-at-risk row: 50/50, 1135/2285 (1120 + 15), 1/16, 1/20, undefined, not computable; 60/90/150/0 of 300.
5. **The MedAgentBench hedges, verbatim**: "They faithfully measure whether the agent emitted a well-formed POST request, not whether any clinical record changed"; "We claim no causal link from either defect to any specific published number"; "no grader reads the record back"; "Patching the tool to perform real writes would change no score".
6. **Every commit hash**: `089ed46 1e8e932 54b74d4 9926011 9dacc79 dee7170 fc776b6`; the two freeze tags by name.
7. **Every bound and denominator**: precision ≥0.867 (25 flags, 24 controls); recall LBs 0.359/0.020/0.066/0.018/0.000/no data with n-drawn and eff.-n; escape ≥0.956 (368/4,048/229/225 = 119+86+20); tau2 465/2,325/0; the withheld v1 run 281/465/33/≥0.325; 33 misses = 2+29+2; biconditional 18/19, 1/7, 0/5; agreement 98/98 over 16 pairs, n=2 of 9 and 2 of 11; replay 10/5/5, zero exercised, zero flips; Action SR 0.00 %–71.33 %, 69.67 %, 12 models.
8. **Pattern-locked sentences the numbers audit keys on** (`CONCEPT_PATTERNS`), kept verbatim or the pattern updated in the same commit with the change named: contribution 5 ("four headline-eligible benchmark-class defect cells across four shipped benchmarks, from eight verified instances"); "Six executable defect classes"; "Four of the six classes are field-observed"; "17 of 19 tau2 contracts were silently never dynamically exercised"; "all 12 evaluated models"; "seventeen days before submission"; "250 lines above in the same file".
9. **All nine original disposal cite-keys** remain cited: `benchguard26 aba26 safeaudit26 toolveritas26 toolgate26 abc26 contract2tool26 contractbench26 toolfuzz25 contractguard26 faulttaxonomy26 abcchecklist25 constructvalidity25`; from 09-11, the seven new keys as well, and **Agent-Diff's entry carries no venue** (a check: its `.bib` entry has no `booktitle`/`journal` and its note says preprint).
10. **Structural invariants**: no appendix; `paper/tables/` untouched by hand (Table VI's `.tex` is generated); the AI-use statement present; data-availability statement carries both the repository name and the DOI; no `\pending` in the body at freeze.
11. **Lexical rules** (T4): abstract and §I P1–P3 contain no frequency word and no necessity "must".
12. **No number from the new literature** appears in the manuscript unless `EXTERNAL-VERIFICATION.md` Task 4 records the table or sentence it was read from (a check: any percentage inside §II B must be listed there).

And two process invariants outside the script: `python experiments/numbers_audit.py` exits 0 before every commit touching `paper/`; the checker stays frozen at `checker-freeze-v2` (`54b74d4`) — nothing in this plan touches `core/`, `dynamic/`, `adapters/`, or `spec/`.

---

## 8. Decisions made here that need Wang's confirmation

Listed once so they can go in the 09-07 message with the abstract and intro.

1. **T1** heading "Baselines and Reference Points" with manual audit as row 1 (incumbent), and the state-based graders named as subjects rather than competitors.
2. **T2** Table I compressed to six rows led by Agent-Diff and Gao & Zhou rather than removed; arithmetic in §4.2 and §6.
3. **Related Work has three subsections** (A benchmarks' grading, B completion verification and its audits, C benchmark audits and contract checking) — the safe reading of his garbled number, and forced by the search result: the literature he asked us to find does not fit into two threads without one of them exceeding six works.
4. **Threats to Validity folds into Experiments as §V.G** to keep exactly six sections. Fallback: a standalone §VI before the Conclusion, at the cost of one heading and a seventh section.
5. **Bold leads become `\paragraph{}` run-in heads** where they name a sub-topic (the ten limitations, the labelled result paragraphs) and plain text elsewhere; run-in heads are genuine subheadings under IEEEtran, which is his stated exception.
6. **Item 13 ("step one with no step two")**: the only numbered steps in `main.tex` are §IV's Step 1/2/3, all present but set as bold run-ins inside one paragraph. Plan converts them to a three-item list and draws them in Fig. 2. Confirm this is the passage he meant.
7. **Z6 and Z7** (dropping one of each duplicate-precedent citation pair; tightening the ten limitations by ~12 % under the strict rule) pre-approved or vetoed now, so 09-18 needs no round-trip. With the enlarged Related Work both are expected to be needed.
8. **The published-number hook** moves from a full §II paragraph to one sentence in §I P2 plus the full paragraph in §V.E; the outline warned against moving it late, and the intro sentence is the compromise.
9. **Agent-Diff is cited as a preprint under review**, never as KDD 2026, unless a decision has posted and been confirmed by 09-25; and Advani is cited without its percentage unless the figure is logged in `EXTERNAL-VERIFICATION.md`.
