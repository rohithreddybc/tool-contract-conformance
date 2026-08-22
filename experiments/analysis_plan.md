# Agent-Impact Experiment — Pre-Registered Analysis Plan

**Committed before any trajectory is recorded.** Commit hash cited in §VIII. No trajectory, flip, or exercise count exists in the repository at the time of this commit — see `PROVENANCE.md` for what the git history does and does not prove.

Repairs the validated CRITICAL from the full review panel: the chain *confirmed defect → at-risk task → wrong score* is not closed for any finding, and may not be closeable. This document commits, in advance, what each possible outcome means — including the outcome where nothing flips.

---

## 1. The problem this plan exists to handle

tau2 grades by comparing the state produced by a gold execution against the state produced by the agent's execution. **Both are produced by the same tool implementations.** A defect exercised identically in both worlds cancels: the comparison is symmetric, so a broken tool that breaks equally on both sides yields no verdict difference at all.

A verdict therefore flips only when the recorded agent exercises the defect **asymmetrically** against gold — refuelling a suspended line the gold solution never touches, or booking and cancelling where gold only books. A competent agent may never do this. The no-re-roll rule in §4 forbids hunting for a trajectory that does, because that would be selection on the outcome.

So three distinct quantities exist, and the paper has been conflating the first with the third:

| Quantity | Question | Status |
|---|---|---|
| **At risk** | Does any task's verdict depend on a state field a defective tool was responsible for? | Computed, `analysis/score_at_risk.py` |
| **Exercised** | Did the recorded trajectory actually drive the tool into its defective path? | **New. Defined below. Was missing.** |
| **Flipped** | Did the benchmark's own evaluator return a different verdict under the patched tool? | Pending |

At-risk over-approximates exercised, which over-approximates flipped. Reporting only the first and the third invites the reading that the gap between them is a null result, when much of it is structural.

## 2. Defect-exercise rate — a first-class reported number

For each confirmed finding, a **mechanical trigger predicate** over the recorded trajectory, evaluated with no model in the loop. A trajectory exercises the defect iff at least one recorded call satisfies it.

| Finding | Trigger predicate |
|---|---|
| F2 — telecom `refuel_data`, unenforced Active-line precondition | a `refuel_data` call whose `line_id` resolves to a line whose status is not `Active` at call time |
| F3 — airline `cancel_reservation`, seats not released | a `cancel_reservation` call on a reservation whose flights had `available_seats` decremented earlier in the same trajectory |
| F5 — AgentDojo `update_scheduled_transaction` | a call passing `recurring=False`, or any advertised field whose supplied value is falsy for its type |
| F6 — AgentDojo `reserve_car_rental` | a call where `end_time` is supplied and differs from `start_time` |
| F7 — MM-ToolSandbox `venmo_social` | a `comment`/`list` call supplying `sort_by` |
| F8 — AgentDojo `invite_user_to_slack` | any call (the parameter is required, so every call discards a supplied value) |

F1 and F4 have no entry: MedAgentBench is excluded from this experiment by Finding 4, whose grader cannot observe the patch. That exclusion is a result reported in §IV, not a gap in this plan.

**Reported per finding:** tasks at risk, trajectories recorded, trajectories exercising the defect, verdicts flipped. Four numbers, always together, never one without the others.

## 3. Every outcome cell is interpreted here, in advance

| Exercise | Flip | Committed interpretation |
|---|---|---|
| Zero | — | The defect is latent under competent agent behaviour on shipped tasks. **This is a finding about conditional validity, not a null result**: the score is correct today because no agent happens to take the broken path, and nothing in the benchmark prevents one from doing so. Report the exercise rate and say exactly this |
| Some | Zero | The symmetric-oracle structure absorbs the defect — gold and agent break identically. **Also a finding**, and a sharper one: it quantifies how much of the at-risk bound the evaluator's own design neutralizes, which no prior work has measured |
| Some | Some | The headline case. Report flips with per-task state diffs and trajectory hashes |

**If the total flip count across all findings is zero, §VIII opens with this sentence, committed verbatim now:**

> Across N recorded trajectories on M affected tasks, no verdict changed under the patched tools; the defects documented in §VI are latent under the agent behaviour these benchmarks actually elicit, and we report the exercise rates that show why.

The paper then argues conditional validity: a benchmark whose correctness depends on agents not taking available paths is measuring something other than what it claims, and the defect remains a live hazard for any agent that does take them. That argument is written before the data exist so it cannot be accused of being invented to survive them.

**What is not permitted:** re-recording trajectories after seeing flip counts; adding tasks after seeing exercise rates; reclassifying a defect as out of scope because it failed to flip; reporting flips without exercise rates.

## 4. Trajectory recording

- **One recording per task. The first completed recording is kept.** No re-rolls, no selection among recordings, no discarding a trajectory for being uninteresting. A recording is discarded only for infrastructure failure — API error, timeout, harness crash — and each discard is logged with its cause and count.
- The trajectory hash is logged with every recorded run and printed in the artifact.
- Fixed model, fixed prompts, fixed seeds, temperature 0, recorded once.
- **Telecom trajectories record user-simulator tool calls as well as agent calls.** Established empirically: telecom's user simulator holds 15 WRITE tools against a separate `TelecomUserDB`, and `make_payment` bridges into the agent-facing database via `sync_tools()` after every call by either party. Replaying agent calls alone would under-specify the world on the one in-scope domain where F2 lives. Airline and retail register no user tools.

## 5. Tier 1 — trajectory replay. Primary. No model in the evidence path.

Re-execute the identical recorded action sequence against as-shipped and patched tools; compare the benchmark's own verdict. The model selected which trajectory exists; it plays no part in the comparison, and that is the precise scope of the determinism claim.

Where a patch changes mid-trajectory observations so replay diverges, fall back to temperature 0 with k=3 per condition, count only flips stable across all three replicates, and verify trajectory-prefix identity to the divergence point. **Report how many tasks needed the fallback** — a large number weakens the determinism claim and the reader is entitled to see it.

Flip direction (fail→pass and pass→fail) is reported separately. A defect that makes tasks *easier* is as much a measurement error as one that makes them harder.

## 6. Task selection — static, committed here, applied without exception

A task is in the experiment frame iff **its reference solution invokes a tool with a confirmed VIOLATES clause.** Enumerated exhaustively from the benchmark's own task definitions. No exclusions, no additions, no selection on observed behaviour.

This frame **does not nest inside** the at-risk population, and the paper says so. `analysis/score_at_risk.py` reports `experiment_frame_subset_of_at_risk = False` for AgentDojo F5: the four tasks whose gold calls `update_scheduled_transaction` all vary `amount` or `recipient`, never `recurring`, while the one task whose oracle reads `.recurring` reaches it through a different, non-defective tool. Argument-specific defects make the two frames overlap rather than contain. Both populations are reported with their intersection.

## 7. Tier 2 — descriptive only

Per-task paired success-proportion deltas with exact binomial CIs. One plot. Labelled effect-magnitude illustration.

**No p-values, no hypothesis tests, in any tier.** McNemar on ~15 tasks yields 3-6 discordant pairs; the test is powerless and, given this author's rejection history, an underpowered NHST is a magnet rather than a shield. If a test is demanded in review, a permutation test on task-level deltas goes in the appendix.

No cross-benchmark pooling. No model comparisons. No significance language in the abstract.

## 8. Patches

tau2's findings have genuine one-hunk patches: uncomment `telecom/tools.py:629-630`; add the seat release at `airline/tools.py:366`. AgentDojo's are similarly small.

Patches repair the **implementation** side of each divergence. That is a methodological choice, not a judgment of fault: a divergence between advertisement and implementation can be repaired from either side, and a maintainer who fixes the docstring instead has equally restored conformance. The implementation side is patched because it is the side that changes the state the evaluator reads, which is what this experiment measures. Stated in §VIII so the choice is not mistaken for an accusation.

MedAgentBench receives no patch and no A/B — Finding 4 establishes the grader cannot observe one.
