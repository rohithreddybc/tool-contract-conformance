# State — 2026-08-31, after the round-6 verification pass

## The paper

Complete and submission-shaped. **10 pages**, IEEE two-column, references counted, no
appendix. Compiles clean: zero errors, zero undefined references. **424 tests pass.**
**Numbers audit: zero FAIL** (three UNVERIFIABLE rows remain by design — the §IV, §VII
and §VIII numeric-claim status rows, which the audit reports rather than adjudicates).

All eight round-3 items are closed, and the round-4, -5 and -6 panel items on top of
them. This pass verified those closures from a clean read rather than taking the state
document's word for it, and corrected two things it found.

## What this pass changed

**The freeze hashes the paper cited were not commits.** `checker-freeze-v1` and
`checker-freeze-v2` are annotated tags, so `8f9b2ff` and `b2a39e1` are tag *object*
hashes; `git cat-file -t` on either returns `tag`, not `commit`. A reviewer running
`git rev-parse checker-freeze-v2` — the natural check for the pre-registration ordering
claim in §VII — lands on `54b74d4` and finds no agreement with the paper. The manuscript,
`PROVENANCE.md` and this file now cite the commits (`9dacc79`, `54b74d4`), and
`PROVENANCE.md` records the correction instead of quietly rewording it.

**The AI-use disclosure was uncommitted and cost a page.** A back-matter statement had
been drafted into `paper/latex/main.tex` but never committed, and it pushed the paper to
11 pages (one reference spilling onto page 11). §V also carried a separate run-in
disclosure. The two are merged into one back-matter statement covering drafting, the
checker and analysis code, both annotator sets, and the numeric analyses; the
data-availability paragraph was trimmed to pay for it. Back at 10 pages, disclosure
intact. `paper/main.md` now carries the same back matter, which it had been missing.

## Verified this pass, unchanged

- `spec/validate.py` over all 48 contracts: all checks pass (the 144 skips are the
  documented offline subset — checks 4, 5 and 8 need `repos/` and `--state-schema`)
- `report/render.py --verify`: 4 benchmark rows match Table III on disk
- `analysis/score_at_risk.py --verify`: 1,208 rows match
- Table III sources MedAgentBench from `FINDINGS-VERIFIED.md`, not the ledger, and says
  so in the row; the excluded-cells line under the table makes 8 classes → 4 headline
  visible without subtraction

## Two open items from the last state document were already closed

Do not reopen them.

- **`[N12]`** is not a hole. `report/disclosure_log.md` is a committed stub whose
  reporting rule was fixed *before* any response is known, and §VIII states that rule in
  prose (substance if responded, neutral non-response otherwise, contested findings
  marked). Nothing in the paper depends on what happens on 2026-09-10.
- **`invite_user_to_slack`'s `frame.other_users_unchanged`** was adjudicated in
  `report/rev5_adjudication.md`: **(b) over-broad frame path**, unsatisfiable by
  construction because the path resolves over the pre/post union and so includes the one
  index the tool is advertised to append. A grammar gap, not a benchmark defect.

## Open

- **`trajectory_hash` is not stable across runs, so it cannot serve as the identity
  anchor the analysis plan intends.** `experiments/analysis_plan.md` §4 promises the hash
  is "logged with every recorded run and printed in the artifact." It is logged. But
  `adapters/_tau2_worker.py:363` hashes the canonical JSON of the recorded messages, and
  those messages carry a per-message `timestamp` field, so re-running the *identical*
  deterministic gold replay produces ten different hashes. Confirmed by running the suite
  twice: every `trajectory_hash` in `report/ab_results.json` changed, while every
  substantive field (exercised, flipped, verdict) stayed byte-identical. **Nothing in the
  paper is wrong because of this** — no hash is printed in the manuscript, and the §VIII
  result (0 exercised, 0 flipped) reproduces exactly. The fix (exclude volatile fields
  from the hashed payload) touches `adapters/_tau2_worker.py` and would rewrite
  `report/ab_results.json`, so it wants a human decision rather than an autonomous edit.
- **Running `pytest` dirties tracked artifacts.** `tests/test_ab_run.py` regenerates
  `report/ab_results.json` and `report/ab_summary.md`, so the working tree is dirty after
  any test run and that churn can be staged by accident. Run `git checkout report/ab_*`
  after testing, or scope the test to a temp directory.
- **Venue.** IEEE BigData Intelligent Data Mining (Sep 27) remains the plan of record.
  SE4AgenticAI (Oct 10, 8–10 pages) is the better topical fit — its reviewers know the
  ConTract and IcePICK lineage this paper positions against. No workshop allows more than
  10 pages. **This is the one decision outstanding that a human has to make.**
- **Two sub-questions** from the miss decomposition (whether closed-world mutants were
  liveness-screened before entering the recall denominator, and whether the six watchdog
  timeouts are exchangeable with misses for the printed bounds) remain stated as open in
  §VII, deliberately.

## Constraints that still bind

- Checker frozen at `checker-freeze-v2`, commit `54b74d4` (tag object `b2a39e1` — cite
  the commit). Changing `core/`, `dynamic/`, `adapters/contract_check.py` or
  `spec/validate.py` is refreeze cycle two.
- `paper/tables/` is generated only, by `report/render.py`.
- Never cut §IX's ten limitations or §II's eight disposals.
- Every score-at-risk figure keeps its basis tag; never pool across bases.
- The MedAgentBench hedges are armor: "the numbers are not wrong", "measures
  emitted-request well-formedness", "no grader reads the record back".
- Run `PYTHONUTF8=1 python experiments/numbers_audit.py` before every commit to `paper/`.
