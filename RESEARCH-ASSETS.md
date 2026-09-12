# Research assets: what exists, where, and what it is for

Index so this work is not redone. Read this before starting any research pass.

## Venue and co-author conventions

| File | Contents | Use it for |
|---|---|---|
| `VENUE-AND-COAUTHOR-STYLE.md` | Four IEEE BigData Intelligent Data Mining session papers measured in full, plus the writing conventions of Zichong Wang and Wenbin Zhang across eight of their own papers. Carries explicit honesty flags where a count could not be verified. | Any question about what this venue's papers look like, or how either co-author builds a paper. Do not re-measure. |
| `C:\Users\rohit\Documents\Peer reviews\my review skills\` | The `paper-review-lessons` skill, four passes, junctioned into the skills directory so edits take effect immediately. | Reviewing any paper. Invoke as `/paper-review-lessons`. |
| `...\my review skills\ieee-data-mining-model-paper.pdf` | Wang, Narasimhan, Yao, Zhang, ICDM 2023. Supplied by Wenbin Zhang as the structural model. | Worked example of the grain of detail a derived checklist needs. |
| `...\my review skills\fairgem-neurips-2025-model-paper.pdf` | Wang, Yin, Zhang, NeurIPS 2025. Supplied by Zhang. Measurements already recorded in that folder's `SKILL.md`. | The three-bolded-challenges convention and the contributions-end-on-outcome rule. |

Key measured facts, so they need not be re-derived: venue abstracts run 175 to 190 words; no venue paper enumerates or bolds challenges in the introduction, 0 of 4; research-question framing appears in 1 of 4 venue papers but 3 of 3 Zichong Wang papers; a dedicated limitations section appears in 1 of 4; Zichong Wang uses exactly three bulleted contributions in 4 of 4 of his papers; Wenbin Zhang numbers contributions inline as i) ii) iii) in 3 of 3 of his.

The third Scholar profile supplied by the author is **Zhipeng Yin**, not a named co-author of this paper, but the same reviewer whose eight comments on Paper 7 produced the internal-coherence rules, and the "Yin" of the FairGEM paper.

## Co-author review on this paper

| File | Contents |
|---|---|
| `ZICHONG-COMMENTS.md` | Zichong Wang's five comments, verbatim, with locations. |
| `ZICHONG-RESPONSE.md` | Covering note to him. Detailed replies live beside his comments in the manuscript. |
| `ZICHONG-VERIFICATION.md` | Adversarial check of whether the paper answers each comment, plus a ranked hostile-reviewer list. |
| `paper/latex/main.tex` | His comments and our replies are in the source as `\zichong{}` and `\response{}` pairs, behind `\ifreview`. `\reviewtrue` prints them; `\reviewfalse` is the submission build. |
| `C:\Users\rohit\Documents\Peer reviews\my review skills\MEETING-2026-09-02-WANG.md` | The earlier Wenbin Zhang review meeting, reconstructed from a recording. |

## Decisions and plans

| File | Contents |
|---|---|
| `FABLE-REVIEW.md` | Independent venue review: scores, the four style tensions resolved, ranked fixes. Written before a rate limit cut the run short, so check it is complete before relying on the later sections. |
| `STRENGTHEN-PLAN.md` | What can and cannot be done about the weak results, with a dated schedule. |
| `VENUE-CALL.md` | The venue decision memo, IDM against SE4AgenticAI. |
| `REFRAME-PLAN.md` | The MedAgentBench reframing after the disclosure check. |
| `CHECKPOINT-2026-09-10.md` | State, open items, and decisions recorded so they are not relitigated. |
| `report/medagentbench-disclosure-check.md` | The verification that MedAgentBench documents its no-write design, with quotes. |
| `report/lit-tool-completion-verification.md` | The literature search on prior completion-verification work, with venue-confirmation status. |

## Settled, do not reopen

MedAgentBench documents its no-write design in its own paper, so the defect rests on the agent-visible success string. No verdict flip is demonstrable without breaching the pre-registered selection rule. The recorded-calls corpus would not move any recall cell; the checker's prober is separate. No third refreeze. No fifth benchmark.
