# Checkpoint, 2026-09-10

Paused here to give Paper 21 priority. Everything below is committed; nothing is
half-finished in the working tree.

## Where the paper stands

Submission build at `01480a5`: **10 pages**, zero errors, zero undefined references,
zero em dashes, template spacing untouched, `numbers_audit.py` exits 0. Ten limitations,
eight findings rows, six disposal rows and the taxonomy table all intact.

Two PDFs are built and untracked in `paper/latex/`: `main.pdf` is the submission copy,
`main-review.pdf` shows Zichong's comments and the replies. The toggle is `\reviewtrue`
or `\reviewfalse` in the preamble. `paper/overleaf-tool-contract-conformance.zip` is
current.

**Overleaf has not been touched.** Uploading the zip replaces the copy there, which will
remove Zichong's `\zichong{}` comments from the Overleaf document, since ours carries them
behind the review toggle instead. That is a choice to make deliberately, not by accident.

## What changed in the last session

Zichong's five comments are answered, with his wording preserved verbatim in the source and
a reply beside each. The MedAgentBench concession is the substantive one: their paper
documents the no-write design in §2.4 and §2.4.3, verified against arXiv, so the defect now
rests on the unqualified success string the agent sees rather than on the missing write.

Three claims were corrected because the evidence contradicted them:

- The `reserve_car_rental` agreement flip was blamed on the missing recorded-calls corpus in
  two places. `report/agreement_summary.md` records the real cause, reproduced directly: no
  `probe_values` in annotator B's contract, so probes die in `datetime.fromisoformat`. Section V
  already said this, so the paper had been giving two causes for one event.
- The replay limitation claimed F2's population of 1,120 tasks made five replays
  non-exhaustive. Counted from tau2's `tasks_full.json` at the pinned commit, all 1,120 tasks
  issue the identical `refuel_data` call. Five replays exhaust gold behaviour. The null is
  definitive, not underpowered.
- A no-counterpart claim covering Reset Leak contradicted the PolDet concession in related work.

## Open, and all needing the author

| Item | Deadline |
|---|---|
| Venue decision: IDM special session, or SE4AgenticAI, whose topic list names testing and verification | **2026-09-20**, per `STRENGTHEN-PLAN.md` |
| Confirm `10.5281/zenodo.22182792` is the concept DOI; the record page shows the release as `...793` | before submission |
| Confirm whether SE4AgenticAI papers enter the IEEE BigData proceedings volume | before the venue decision |
| Zichong Wang's affiliation, currently `AFFILIATION TO CONFIRM` in the author block | before submission |
| The two back-matter placeholders, AI-use and coordinated disclosure. Prior wording is kept as comments above each | disclosure needs the 2026-09-10 responses |
| Eleven Scopus venue confirmations for the bibliography | before submission |

## Decided, so it does not get relitigated

- No verdict flip can be demonstrated. No shipped task composes a suspended line with a
  refuel, and selecting tasks that would flip means selecting after seeing which flip. Report
  the null and defend it.
- Do not build the recorded-calls corpus expecting better recall. It feeds the open-world arm,
  the miss diagnostic and the agreement study only; the checker's prober is separate, so no
  recall cell moves. Verified in the code.
- No third refreeze cycle. Four of six operators have no unused sites, and the motivation would
  be observed misses.
- No fifth benchmark. Too little disclosure notice, and it would not change the prevalence
  limitation.

## Reading order on resume

`STRENGTHEN-PLAN.md` for the dated schedule and the venue switch condition,
`ZICHONG-COMMENTS.md` and `ZICHONG-RESPONSE.md` for the co-author thread,
`ZICHONG-VERIFICATION.md` for the hostile-reviewer list worth clearing before submission.
