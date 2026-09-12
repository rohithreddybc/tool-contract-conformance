Submit this paper to the IEEE BigData 2026 Intelligent Data Mining special session by 2026-09-27. The venue is decided; VENUE-CALL.md is superseded and no venue is reopened. The goal is not acceptance, which no file can show and which would keep this session running forever; it is clearing the defect classes that produce a reject or major revision at this venue, each checkable in a file: an unsupported claim, a weak result hidden or softened, a broken invariant, an unanswered co-author, prose that reads as generated.

Claims first. Every sentence about another system, another paper, or our own results is checkable against a primary source at a pinned commit; one that fails is corrected in print, not hedged. A claim that something does not exist is a search obligation, and the search is recorded where it was run. A claim that prior work missed something needs evidence that prior work examined our target; where only its taxonomy was read, the sentence says so. Headline counts contain agent-visible clauses only; maintainer annotations stay in their own tier. A false claim about someone else's code is worse than a weak paper. Findings from the reviewer panel now running are handled the same way: verified against the source before any edit, accepted only where the evidence supports the change, declined with a written reason where the evidence or the settled list below does not allow it.

Weak results are the true results. Low recall, the zero-denominator tau2 open-world arm, and zero verdict flips are reported once, in Experiments, with their mechanical cause, never softened and never repeated under a Threats heading where a reviewer mines them. If the recorded-calls corpus is completed, it is built purely by rule from the benchmark's own gold calls, tagged before any rerun, the checker diff is empty, no closed-world mutant is rescored or dropped from a denominator, and the pre-completion "no usable number" is reported beside whatever replaces it.

Invariants, checked before every commit touching paper/: exactly 10 pages including references and no appendix; template spacing and the float and table settings unchanged; anything added names what it displaces; numbers_audit.py exits 0; zero em dashes in main.tex; paper/tables/ generated, never hand-edited; the ten Threats limitations, the eight findings rows with their Surfaced-by column, the six disposal rows, the per-benchmark totals and the taxonomy table all stay; \reviewfalse is set in the submission copy, and no \pending, "TO CONFIRM" or "To be completed" text survives in it.

Zichong Wang's five comments stay verbatim in the source with a reply beside each, and no reply claims more than was done. A co-author request after the 2026-09-20 content freeze is handled as wording; anything larger is declined and noted for camera-ready. Prose is in venue register and reads as a person wrote it: no verdict-label openings, no formulaic transitions, no bolded full sentences, no contractions, hedged where the evidence is partial and plain where it is not.

The artifact runs for a stranger: make reproduce-results passes offline on a clean clone; the six defect classes stay a liftable one-page table of checker rules; every finding stays quotable and checkable by commit, file, line and quoted evidence. The submission-ready PDF is also the preprint: it goes to arXiv in the submission week, not after notification, and the arXiv identifier is recorded in RESUME-STATE.md and linked from the four disclosure issues.

Needs the author before submission: Zichong Wang's affiliation; the AI-use and coordinated-disclosure paragraphs, the latter filled from report/disclosure_log.md under its committed rule, with silence recorded as silence and nothing inferred from it; confirmation that 10.5281/zenodo.22182792 is the concept DOI; the eleven Scopus venue confirmations; the CyberChair required fields.

Settled, not relitigated: no verdict flip is demonstrable without choosing tasks after seeing which flip, so the null stands with its cause; the recorded-calls corpus feeds the open-world arm and the miss diagnostic only and moves no recall cell; no third refreeze; no fifth benchmark; MedAgentBench's no-write design is documented in its own paper, so the defect rests on the agent-visible success string and the grader that takes it as evidence.

---

Note to the author

Why "acceptance" is rephrased again. A stop hook fires when a condition holds in the files. "Guarantee acceptance" and "nothing a reviewer could flag" never hold in any file, so the session would either never stop or would stop on a fiction. The defect classes named in the first paragraph are the ones that produced your three methodological rejections and the panel's likely majors; each one is a file check. That is the strongest version of the ask that can be enforced.

Added beyond your list, with the reason:

1. Panel handling. The panel lands mid-session and your list said nothing about what to do with a finding that contradicts the settled list or asks for evidence the paper does not have. Without a rule, the session either relitigates settled items or edits on a reviewer's say-so. The rule is the one that resolved Zichong's C2: source first, then concede or decline in writing.

2. Corpus-completion conditions. Your settled list says the corpus will not improve recall but does not say whether it is being built, and STRENGTHEN-PLAN.md's 2026-09-15 go/no-go is still live. Built the wrong way, it is the post hoc rule that cost you a paper. If the decision is now "not built," replace that sentence with "the recorded-calls corpus is not built and the v2 no-usable-number text stands," which is even easier to check.

3. The Zenodo concept-DOI confirmation. CHECKPOINT-2026-09-10.md lists it; your list did not. It is a number printed in the paper that may be one digit off.

4. \reviewfalse and no surviving placeholders in the submission PDF. Mechanical, and the one thing a rushed final compile gets wrong; the review PDF currently sits next to the submission PDF with the same basename stem.

5. The 2026-09-20 freeze rule for co-author requests, from STRENGTHEN-PLAN.md §9. I assumed the freeze date still holds. If it has moved, change the date, not the rule.

6. The arXiv clause is made checkable by requiring the identifier be recorded. Posting is a public action and yours to take, not the session's; the session's checkable half is that the submission PDF is preprint-ready.

Where your list is weaker than it could be:

- "Prose reads as a person wrote it" is the least checkable clause you asked for. I tied it to the four tells GOAL.md already names plus the humanize formal-register rules; a hook can verify those and nothing further. Do not expect it to catch rhythm.
- "Citations: the defect classes stay adoptable, findings stay quotable" is already guaranteed by the tables-stay invariant, so I kept it to one clause rather than a paragraph. Expanding it would be padding true of the current draft.
- Two repository files now contradict the decided venue: VENUE-CALL.md recommends SE4AgenticAI, and CLAUDE.md still names ML on Big Data as the backstop. The goal says VENUE-CALL.md is superseded, but a future session reads the file, not the goal; put a one-line header on it and drop the backstop line from CLAUDE.md.
- Not in the goal because no file check exists: uploading the Overleaf zip replaces the copy there and removes Zichong's inline comments from his view. Decide that deliberately before anyone uploads.
