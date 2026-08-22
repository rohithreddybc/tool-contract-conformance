# Response to the methodology review — 2026-08-21

Instrument: `academic-paper-reviewer`, methodology-focus mode, 2-seat panel (Journal-Fit + Methodology), no-contract path, `criteria_binding_unavailable` on both seats. Design-stage verdict: Major Revision of the design, before drafting. One Critical, five Major.

Every finding is accepted. Two are accepted with a modification to the proposed repair, and both modifications are recorded with reasons. Nothing here is deferred to drafting.

---

## W1 (Critical) — `eff.seats_released` is grounded in a surface the agent never sees

**The finding.** The worked contract in `spec/PREDICATE-GRAMMAR.md` §5 grounds the seat-release effect in `surface: tool_return`, quoting `logger.warning("Seats release not implemented for cancellation!!!")` at `airline/tools.py:367`. But the tool *returns* the reservation object at line 368. The warning goes to the harness log. No agent is ever conditioned on it, so it is not "a success/failure string the tool returns to the agent" — it is a maintainer annotation, and under the schema's own justification the clause should be `inferred: true` and excluded from every headline count. The validator cannot catch this: check 4 verifies the quote occurs at the cited location, which a log line trivially satisfies.

Accepted without reservation. This is my error, introduced when I wrote the example, and it is the exact construct-validity failure the mechanism exists to prevent.

**The decisive question — answered empirically, 2026-08-21.** The reviewer's preferred repair (a) was to find a genuine agent-visible grounding. I searched every agent-visible surface in tau2 airline at `c3398666`:

- `cancel_reservation` docstring: "Cancel the whole reservation." / "Returns: The updated reservation." / "Raises: ValueError: If the reservation is not found." Nothing about seat inventory.
- `data/tau2/domains/airline/policy.md`, the agent's system prompt: `grep -in "seat|cancel|availab"` returns 17 hits. Line 41 states available seats are listed per flight date; line 47 that availability is listed per cabin. The "Cancel flight" section, lines 133-149, covers eligibility rules and refunds. **Nothing states that cancellation returns seats to inventory.**

Repair (a) fails. There is no agent-visible statement of seat-release semantics anywhere in tau2 airline.

**Decision — repair (c), with a modification.** Add a new advertised surface `maintainer_annotation` to the closed list, placed explicitly *outside* the agent-conditioning argument and *outside* headline counts. Grounding then has three tiers rather than two:

| Tier | Surfaces | Headline count | What it means |
|---|---|---|---|
| Agent-visible | `docstring`, `schema`, `prompt_template`, `tool_return`, `readme`, `external_standard` | yes | the agent was conditioned on this text; a violation corrupts the measurement by the paper's central argument |
| Maintainer-annotated | `maintainer_annotation` | no, reported separately | the maintainer wrote the intended semantics down in code — a comment, a log line, a TODO — but the agent never sees it |
| Inferred | none | no, reported separately | we inferred it; nobody wrote it anywhere |

Why this rather than a bare `inferred: true`: the two are not the same epistemic object, and collapsing them discards information that favors the finding. `# Release seats` followed by `logger.warning("Seats release not implemented for cancellation!!!")` and the line-689 TODO are the maintainer's own record of intended behavior. That is materially stronger than an inference we made, and materially weaker than something the agent read. Three tiers report exactly that. A reviewer can disagree with where the line falls and still see every clause's grounding.

**Consequence for Finding 3, stated plainly.** Its Partial Effect is a *maintainer-annotated* violation, not an agent-visible one. It does not enter headline counts. This is a real demotion and the paper says so rather than arguing around it — the alternative is a headline number a reviewer can dismantle by reading one log line.

**Consequence for Gate 1b.** The success criterion changes from "rediscovers both tau2 findings from contracts alone" to "rediscovers both, with Finding 3 correctly classified as maintainer-annotated." Rediscovery via a non-headline clause is still rediscovery; silently counting it as headline would not be.

**Validator rule, new.** Check 8: a `tool_return` or `prompt_template` quote must be shown to reach the agent-visible message stream — for `tool_return`, the quoted string must appear in a `return` expression or in a raised exception's message, not in a `logger.*` call. Mechanical and cheap. It is what would have caught this.

**Unexpected dividend.** `policy.md:149` states: "The API does not check that cancellation rules are met, so the agent must make sure the rules apply before calling the API!" That is an agent-visible surface *advertising* non-enforcement. It gives the Unenforced Precondition detector a second true-negative showcase alongside the deferred-effect one: the checker must not flag airline cancellation eligibility, because non-enforcement is exactly what the interface advertises, while still flagging `refuel_data`, whose docstring advertises a check it does not perform. That contrast belongs in §V.

---

## W2 (Major) — score-at-risk returns zero for the benchmark Finding 4 proves is most broken

Accepted, and the proposed repair is better than the problem. MedAgentBench's write graders read no server state, so the field→evaluator intersection is empty and Table II would print "0 tasks at risk" for the worst instrument in the study.

**Decision.** Step 2 of the dependency analysis gains a per-task **oracle-grounding classification**, computed statically from the grader source: `state_grounded` / `transcript_grounded` / `mixed`. Table II reports transcript-grounded write tasks as a distinct verdict — "oracle not state-grounded: N tasks; score-at-risk undefined, construct-validity finding applies" — never as zero.

This makes Ungrounded Oracle an output of contribution 1 rather than a prose aside, and it is computable with no runs. Add to §IV, and to `analysis/score_at_risk.py`.

**Disposal sentence required.** Distinguish Ungrounded Oracle from Tool-Veritas's reward-basis mismatch and hallucinated completion: those concern whether the verdict matches the outcome; ours concerns the *provenance of the oracle's evidence*. A grader reading the agent's transcript can be perfectly consistent with the outcome it observes and still be measuring the wrong thing.

---

## W3 (Major) — the agreement study is unoperationalized, and semantic agreement is the wrong measure

Accepted in full, including the reframing.

**Decision.** Replace judged semantic agreement with **extensional agreement**. Both annotators' predicates are compiled and evaluated against a shared probe corpus — the mutation corpus plus recorded real calls — and agreement is reported at the verdict level per clause. The headline robustness number is: *does any VIOLATES finding flip under the second annotator's contracts?* Deterministic, executable, and it measures the thing that actually matters. It also fits the project's stated preference for mechanistic over inferential evidence, which judged equivalence-of-predicates does not.

**Sample size.** 20% of ~100-150 clauses is 20-30 items — an interval too wide to defend. Dual-annotate **100% of clauses on the finding-bearing tools**, plus a stated fraction of the rest, and report the exact interval for the remainder as a gross-instability screen.

**Also to be committed in the Aug 22-23 protocol, not merely scheduled:** the clause segmentation rule (and its relation to the coverage metric's "advertised-surface sentences", which is currently a second and different unit); the label space; the sampling frame and stratification; blinding — both annotators know the four findings, so agreement on those tools is contaminated upward and must be reported separately; and the second annotator's identity, with "independent" qualified if it is the co-author.

---

## W4 (Major) — pre-registration lands after the mutation numbers exist

Accepted. The schedule scores the closed-world arm Sep 2-3 and the open-world arm Sep 4, but commits `analysis_plan.md` on Sep 5, and `CLAUDE.md` scopes pre-registration to the agent experiment alone. Every statistical choice for the mutation arms is therefore formally free to be made after the data are seen.

**Decision.** Split into two committed artifacts:

1. `experiments/detector_analysis_plan.md` — interval method, per-tool reporting rule, escape-rate definition and denominator, equivalence-adjudication protocol. Committed **at `checker-freeze-v1`, before any mutant is scored.**
2. `experiments/analysis_plan.md` — the agent experiment. Sep 5 as planned.

One commit hash each, cited in §VII and §VIII respectively. `CLAUDE.md`'s pre-registration rule is widened to cover both.

---

## W5 (Major) — the escape-rate denominator is undefined and its filters re-admit analyst judgment

Accepted. Three distinct problems: "surviving" has no killing mechanism defined (there is no test suite here to survive); "non-equivalent" is adjudicated by us after seeing which mutants the checker missed, the largest single degree of freedom in the design; and a miss can mean a taxonomy gap, a probe-generation gap, or a canonicalization gap, which one number conflates.

**Decisions, all into `detector_analysis_plan.md`:**

1. **Survival, mechanically defined.** A mutant survives iff it produces a canonicalized post-state or result differing from the unmutated tool on at least one probe from a fixed, pre-committed probe corpus. This doubles as the equivalence screen and removes the judgment call.
2. **Equivalence adjudication rules written before scoring**, a sample dual-adjudicated, and **both raw and adjudicated escape rates reported.** The gap between them is itself informative.
3. **Escapes decomposed three ways** — clause gap, probe gap, canonicalization gap. This turns a potentially embarrassing number into the most interesting paragraph in §VII.
4. **Framing:** escape rate is a lower-bound incompleteness probe. It is never evidence of completeness.

---

## W6 (Minor, but decision-bearing) — two "affected task" definitions, and the bound's direction is unstated

Accepted. §IV's at-risk set is field-dependency-based; the experiment's sampling rule is reference-solution-based. These select different sets: an agent can reach a correct end state through a buggy tool on a task whose gold solution never calls it.

**Decision, and it had to change once the code ran.** The plan was to state the relation as experiment frame ⊆ at-risk population, a conservative sample. **That containment is false, and `analysis/score_at_risk.py` proves it mechanically** — `experiment_frame_subset_of_at_risk = False` for AgentDojo Finding 5.

Why: the four tasks whose gold solution calls `update_scheduled_transaction` all vary `amount` or `recipient`, never `recurring`. The one task whose oracle actually reads `.recurring` — `UserTask6` — reaches that field through a *different*, non-defective tool, `schedule_transaction`. So the experiment frame contains tasks outside the at-risk set, and the at-risk set contains a task outside the frame. Neither nests.

The cause is that Finding 5 is an **argument-specific** defect: the tool is correct on most argument paths and broken on one. Field-level dependency cannot see which argument path a task exercises, and gold-solution invocation cannot see which field the oracle reads. Two different questions, two different sets.

So §IV states the relation as **overlapping, not nested**, reports both populations with their intersection, and says plainly that argument-specific defects are why. This is a better paragraph than the one originally planned — a claimed containment that a reviewer could falsify by reading our own JSONL would have been much worse than an honest statement that the two frames answer different questions.

Direction and scope are unchanged: at-risk is an over-approximation of misgrading *via the state-dependency mechanism only*, and only for state-grounded oracles.

**Numbers-audit script gains a lexical rule:** any sentence carrying an N2-derived number must contain "at risk" or "depend", and must not contain "misgraded" or "wrong". Those words are reserved for N8 flip counts.

---

## E-W1 (Major, Journal-Fit seat) — no venue-bridge content anywhere

Accepted. The outline names the special session in its configuration record and never argues fit anywhere in the paper.

**Decision.** One framing paragraph in §I — benchmark scores are published measurement data that the field mines, aggregates, and reuses in leaderboards and model-selection decisions; an instrument defect propagates into every downstream use — and one sentence in §XI. Verify the session's actual CFP language rather than inferring it.

---

## Accepted, smaller

- **W7** — commit a no-re-roll trajectory rule ("one recording per task, first completed recording kept, trajectory hash logged") into the Sep 5 plan; enumerate every environment-mutating actor per domain during adapter work, including user-simulator tools, and include user-side calls in the recorded sequence if they exist; pre-specify how flip direction is reported.
- **W8** — `inv.seat_conservation`'s text claims a capacity equation while its predicate asserts only `available_seats >= 0`. Fix the example. Add text↔predicate fidelity to the annotator checklist. Its presence in the flagship example is evidence the translation risk is live, which is the argument for W3.
- **W9** — state where held-out tools come from. If the independent annotator re-authors already-contracted tools, that is extensional dual annotation and merges with W3; if they come from the toy domain, the external-validity claim is weaker and gets labelled. State whether that person is the co-author.
- **W10** — report `biconditional: true` adoption (n of 19, with justifications) alongside the coverage metric. Phantom Effect's detection surface is bounded by it.
- **W11 — RESOLVED 2026-08-21, and the reviewer was right.** mutmut 3.7.0 refuses to run on Windows: "To run mutmut on Windows, please use the WSL." `wsl.exe --status` reports WSL is not installed, so that fallback was unavailable too. cosmic-ray 8.7.0 runs natively — smoke run of 40 jobs on a synthetic tool: 32 killed, 8 survived, no crashes. **Open-world arm switches to cosmic-ray**, and the hand-rolled operator fallback is not needed. Two gotchas recorded in `ARCHITECTURE-FINAL.md` §5: absolute paths required in `test-command` (relative paths silently produce all-`INCOMPETENT` results), and `uv venv` required because `python -m venv` cannot bootstrap pip here. Discovering this on Sep 4 would have cost the arm.
- **Journal-Fit W2** — draft two abstract variants now, one at the N=2 floor and one at the N=4 target; let the Sep 6 kill gate pick. Do not write a plural-scoped title that the floor cannot support.
- **Journal-Fit W3** — verify IEEE BigData's actual back-matter requirements before budgeting 0.75 pages for CRediT and funding statements; reclaim any freed space for §VII.
- **Journal-Fit minor** — one authoritative copy of the backstop date.
- **Methodology minor** — `spec/coverage.py` still absent from the file tree; PREDICATE-GRAMMAR §2.2 key-vs-value iteration is an authoring trap and goes on the annotator checklist.

---

## Not accepted as stated

None. Two repairs were modified — W1 takes option (c) with a three-tier grounding model rather than a bare `inferred` flag, because the two tiers it would collapse are different epistemic objects; and W3's sample size is raised from 20% to 100% on finding-bearing tools rather than left at 20% with a reported interval.

---

## Repair order and cost

| Order | Repair | Deadline | Status |
|---|---|---|---|
| 1 | W1 — add `maintainer_annotation`, validator check 8, re-ground or re-tier `eff.seats_released` | before any contract is authored | **DONE 2026-08-21.** Schema tier added, check 8 implemented and tested both ways, contract re-tiered, `PREDICATE-GRAMMAR` §5-6 rewritten. 72 tests pass |
| 2 | W3 — annotation protocol contents, extensional agreement design | Aug 22-23 window | **DONE 2026-08-21.** `experiments/annotation_protocol.md` |
| 3 | W4 + W5 — one combined `detector_analysis_plan.md` | before `checker-freeze-v1` | **DONE 2026-08-21.** `experiments/detector_analysis_plan.md`. Survival defined mechanically, escapes decomposed three ways, framing committed in advance |
| 4 | W2 — oracle-grounding classification in `score_at_risk.py`, plus the disposal sentence | before §IV is drafted | open — waiting on the adapter, which supplies the state-field extraction it needs |
| 5 | W11 — mutation tooling feasibility | was Sep 4 | **DONE 2026-08-21.** cosmic-ray, not mutmut. See above |
| 6 | W6, E-W1, and the smaller items | during drafting | open — paragraphs, plus the CFP check |

Total roughly two to three days, almost all inside windows the schedule already reserves. Nothing here touches the architecture's spine: contracts → two-arm validation → dependency analysis → replay.

---

## Open questions returned to the reviewer, now answered

1. *Does any agent-visible surface in tau2 airline state that cancellation releases seats?* **No.** Verified against the docstring and `policy.md` at `c3398666`. Finding 3 is maintainer-annotated.
2. *What kills a mutant in the open-world arm?* Now defined: a canonicalized difference on at least one probe from a pre-committed corpus. See W5.
3. *Who is the second annotator, blind to the findings, and on which tools?* Open. Must be settled in the Aug 22-23 protocol.
4. *Can the tau2 user simulator mutate environment state?* **Yes, in telecom, and the experiment design depends on it.** Resolved 2026-08-21 during adapter work; recorded in `adapters/NOTES.md`.

   Airline and retail register no user tools at all — their user simulators cannot write. Telecom is different: its user simulator has 15 WRITE tools against a **separate** `TelecomUserDB`, and one of them, `make_payment`, bridges into the agent-facing `TelecomDB` through `TelecomEnvironment.sync_tools()`, which runs after every tool call by either party. Verified by live reproduction — a bill flips Awaiting Payment → Paid via a user-only call.

   **Consequence for Tier 1:** trajectory replay on telecom must record and replay user-tool calls, not just agent tool calls. Replaying the agent's sequence alone would under-specify the world on exactly the domain where Finding 2 lives. This is the concrete instance of the review's W7(ii) concern, and it was real.
5. *Which contracts justify `biconditional: true`?* Open until contracts are authored; the adoption rate is now a reported number per W10.
