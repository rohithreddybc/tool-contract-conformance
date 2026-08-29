# Resume state — paused 2026-08-29 01:21, resume 05:21

## Where the paper is

Complete draft, all eleven sections plus abstract. Compiles clean under pdflatex:
**14 pages against a hard 10-page limit** (references counted, no appendix).
390 tests pass. Numbers audit: 75 pass, 2 fail (both known and listed below).

Round-3 full reviewer panel returned **Major Revision**, 8 required items, 6 suggested.
No finding questioned the truth of any claim — only completeness, internal
consistency, and length.

## The eight required items

| # | Item | Status |
|---|---|---|
| R1 | Dual-annotation study (§V, N7) promised but never executed | **Critical, not started.** Blind annotator-B agent was dispatched and stopped at pause; it produced no files. Plan: a blind agent instance authors contracts for six tools with no access to existing contracts or findings, then compare extensionally. Must be disclosed as two LLM-agent annotations, one blind — NOT independent human annotation |
| R2 | §IX headline arithmetic fails visibly: 7 cells − 2 stated exclusions ≠ 4 | Not started. Third compression (AgentDojo Phantom, dropped because the biconditional re-tag never fires under the fixture) is explained only in an HTML comment. Also: instance count ambiguous (8 vs 9 with `update_user_info`), and the clause→instance→cell mapping is never stated |
| R3 | Cut 14 pages to 10 | Not started. Cut list exists; see below |
| R4 | `report/render.py` does not exist; Table III never generated | Not started. Agent dispatched and stopped; produced no files |
| R5 | v1 open-world tau2 result (281/465, 33 live, ≥0.325, invalidated by stale cache) absent from the manuscript | Not started. Two sentences in §VII |
| R6 | Abstract's MedAgentBench sentence overreaches §IV's own decomposition | Not started. §IV says 60 transcript-grounded / 90 mixed / 150 no write oracle / 0 state-grounded; the abstract says "its only grader" and "measures whether a well-formed request was emitted", which is not true of the 150 |
| R7 | Closed-world misses undecomposed | Not started. The probe-corpus failure that zeroed the tau2 open-world arm is a live alternative explanation for part of the miss rate — the paper may be overstating its own weakness |
| R8 | Ledger inconsistencies + bibliography | Not started. §IV "broken on exactly one argument" contradicts `eff.amount_propagated` VIOLATES; §VI "every table rendered from findings.jsonl" is false for MedAgentBench (zero rows, static findings); `suspend_line arg.reason` VIOLATES row is unmentioned anywhere; ten references unconfirmed |

## The page problem, which is worse than it looked

14 pages, not the ~12 I estimated from word count. The measured cut list recovers
only **~1–1.3 pages** even including typesetting tightening:

1. §VI refreeze + expressiveness-gap paragraphs (~0.25p) — near-zero cost, both retold in §VII/§X
2. §V worked-contract YAML listing (~0.2p) — prose already narrates it
3. §II contract-inference paragraph compression (~0.2p) — no citation dropped
4. §X final refreeze paragraph → pointer (~0.12p) — third telling
5. §I "one result deserves a preview" → one sentence (~0.05p)

**That leaves ~2.7–3 pages unaccounted for.** Every section runs 15–35% over its
own outline budget; this is systemic overshoot, not a few fat passages. Closing it
needs either a broad compression pass across protected sections or a venue with a
larger limit. Do NOT solve it by cutting §X's ten limitations or §II's eight
disposal sentences — both were bought with real work and both answer specific
reviewers.

## Standing constraints that survive any cut

- §III taxonomy, §IV score-at-risk, §IX findings: the contribution, never cut
- §VII: both mutation arms, Wilson lower bounds, escape decomposition, pool table
- Every score-at-risk figure keeps its basis tag; never pool across bases
- MedAgentBench hedges are load-bearing armor: "the numbers are not wrong",
  "measures emitted-request well-formedness"
- Checker is frozen at `checker-freeze-v2` (5824376). Any change to `core/`,
  `dynamic/`, `adapters/contract_check.py` or `spec/validate.py` is refreeze
  cycle two and needs an explicit decision

## Known-good state

- `checker-freeze-v1` = 57b019d, `checker-freeze-v2` = 5824376,
  agent-experiment pre-registration = ec5dbf4
- `report/findings.jsonl` 440 rows, 12 VIOLATES, regenerated under v2
- `report/score_at_risk.jsonl` 1208 rows, `--verify` clean, contract-derived
- Headline: **4 headline-eligible cells across 4 benchmarks**, 8 instances
- Two audit failures are legitimate: `report/render.py` missing (R4 fixes it),
  `[N12]` disclosure log dated 2026-09-10 (cannot exist yet)
