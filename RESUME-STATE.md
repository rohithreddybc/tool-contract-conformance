# State — 2026-08-29, after round 3 revisions

## The paper

Complete. **10 pages**, IEEE two-column, references counted, no appendix. Compiles
clean: zero errors, zero undefined references, 32 of 32 citations resolving.
416 tests pass. Numbers audit: one failure, `[N12]`, a disclosure log dated
2026-09-10 that cannot exist yet.

Round-3 full panel returned Major Revision with eight required items. **All eight
are closed.** A round-4 panel is running against the finished draft.

## What the eight items produced

| # | Item | Outcome |
|---|---|---|
| R1 | Dual-annotation study, promised but never run | Run. A blind agent authored contracts for six tools. **Blind stratum agrees 98/98.** One finding flips, root-caused to a missing `probe_values` annotation, not a disagreement about advertised semantics. One tool contaminated and excluded — see below |
| R2 | §VIII arithmetic failed by subtraction | Full chain visible: 12 ledger rows → 8 instances → 7 cells → 4 headline-eligible, all three compressions stated |
| R3 | 14 pages against a 10-page limit | **10 pages.** Mechanism relocated to the artifact with in-line pointers; §V and §VI compressed from ~1400 words to 557 |
| R4 | `report/render.py` did not exist | Written. Table III generated, `--verify` round-trips |
| R5 | v1 open-world result absent from the paper | Disclosed: 281/465 scored, 33 live, ≥0.325, invalidated by a stale cache |
| R6 | Abstract overreached §IV's own decomposition | Leads with the claim true of all 300 cases: no grader reads the record back |
| R7 | Closed-world misses undecomposed | **29 of 33 are probe unreachability; only 2 are clause gaps.** The paper had been understating itself |
| R8 | Sentences the ledger falsified | Four corrected; precision denominator scoped to mutation-arm flags |

## Three findings worth carrying forward

**The paper was conceding more weakness than the evidence supports.** M-INVAR's
0.000 recall reads as a taxonomy failure and is not — no probe ever reached a
mutated invariant path. Only 2 of 33 misses are gaps the checker owns.

**One missing artifact explains three separate weak results.** The pre-registered
recorded-real-calls corpus (`detector_analysis_plan.md` §2, item 1) was never
built; every production caller passes an empty list. It causes the tau2
open-world zero denominator, the `reserve_car_rental` agreement flip, and 29 of
33 closed-world misses. §IX names it as the highest-value future work.

**Our own annotation protocol cannot produce a blind annotation for one tool.**
It requires reading `PREDICATE-GRAMMAR.md`, whose §5 is a complete worked example
of `cancel_reservation` including its grounding correction. Disclosed, that tool
excluded from the blind stratum, and reported as a defect in the protocol.

## Open, and honest about it

- **`[N12]`** — the disclosure log. Maintainer disclosure is scheduled for
  2026-09-10; the artifact cannot exist before then. Fallback text for
  non-response needs drafting before submission, not at the deadline.
- **`invite_user_to_slack`'s `frame.other_users_unchanged`** violates on every
  probe under annotator B's contract. Either a real unadvertised side effect or
  an over-broad frame path. Neither confirmed nor dismissed.
- **Two sub-questions** from the miss decomposition: whether closed-world mutants
  were liveness-screened before entering the recall denominator, and whether the
  six watchdog timeouts are exchangeable with misses for the printed bounds.
  Both stated as open in §VII.
- **Venue.** IEEE BigData Intelligent Data Mining (Sep 27) is the plan of record.
  SE4AgenticAI (Oct 10, 8–10 pages) is the better topical fit — its reviewers know
  the ConTract and IcePICK lineage this paper positions against. No workshop
  allows more than 10 pages; that was checked and my earlier assumption was wrong.

## Constraints that still bind

- Checker frozen at `checker-freeze-v2` (b2a39e1). Changing `core/`, `dynamic/`,
  `adapters/contract_check.py` or `spec/validate.py` is refreeze cycle two.
- `paper/tables/` is generated only.
- Never cut §IX's ten limitations or §II's eight disposals.
- Every score-at-risk figure keeps its basis tag; never pool across bases.
- The MedAgentBench hedges are armor: "the numbers are not wrong", "measures
  emitted-request well-formedness", "no grader reads the record back".
- Run `PYTHONUTF8=1 python experiments/numbers_audit.py` before every commit to
  `paper/`.
