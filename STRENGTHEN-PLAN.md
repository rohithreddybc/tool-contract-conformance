# Strengthening plan, 2026-09-10 to 2026-09-27

Planning document. Nothing in `paper/` was edited while writing it. Every claim below about the code or the reports was checked against the file named, not taken from the assessment that prompted this plan; where the assessment and the repository disagree, the repository is reported and the disagreement is marked.

The short version. Build the recorded-calls corpus, but only from a source you do not author and only into the arms it can honestly change: the open-world tau2 arm and the miss decomposition. Do not touch the checker, do not rescore recall, do not run a third refreeze. Run the agent-impact experiment over its whole pre-registered frame, which takes about half an hour and whose result is already determined by the task file. Do not record agent trajectories. Do not add a fifth benchmark. Keep the venue, with one dated decision point at which the workshop takes over. The weak detection numbers are the true numbers; the paper defends them, and after this plan it defends them with a cleaner causal story than it has today.

---

## 1. What was verified, and where the assessment was off

**The corpus was never built.** `mutation/probes.py:56` is a pass-through; every production caller passes `recorded_calls=[]`: `experiments/decompose_closed_world_misses.py:179`, `experiments/open_world_cosmic_ray/tau2_telecom/scoring_lib.py:116`, `experiments/open_world_cosmic_ray/toy/scoring_lib.py:108`, and `experiments/agreement.py` (which says so in its own protocol-deviation block). No recorded-call store exists anywhere in the project. Confirmed.

**What the corpus actually feeds.** This is where the assessment overstates. The §2 equivalence corpus is used in exactly three places: the open-world liveness screen (§4.1 of the detector plan), the closed-world miss *diagnostic* (`decompose_closed_world_misses.py`, a post hoc script), and the agreement study's shared probe set. It never drives the checker. The checker's own probes come from `dynamic/probes.py`, a deliberately disjoint generator, and that separation is load-bearing for the plan's §4.3 decomposition (both module docstrings say so at length). Consequences:

- The tau2 open-world zero denominator: caused by the missing corpus. Correct.
- The 29 `probe_corpus_unreachable` misses: the label means the equivalence corpus could not establish that the mutant was behaviourally live at all, so the diagnostic cannot say whether the checker missed a live mutant or scored an inert one. It does not mean the checker's probes failed to reach the site. A completed corpus would convert some of the 29 into `clause_gap`, `probe_gap`, or (for M-INVAR) `invariant_clause_not_evaluated_by_classifier`. **It would not change a single recall figure**, because recall is what the checker detected under its own prober. The paper's current sentence, "the frozen probe corpus owns 29 ... never driving the mutated path into an observable state," is slightly stronger than the evidence and should be reworded whether or not the corpus is built (§7 below).
- The `reserve_car_rental` agreement flip: **not** caused by the missing corpus. `experiments/agreement.py:73,593,602` runs the arg.* robustness check through `dynamic.probes.generate_ignored_argument_probes` and the frozen `check_ignored_argument`, that is, the checker's own prober. The flip traces to Annotator B not declaring `probe_values` for an ISO-format string argument, so the prober harvested `'Paris'` off the snapshot. The corpus explains why the agreement study needed hand-built *witness probes* on three tools; it does not explain the flip. The Threats paragraph "Real-benchmark escape rate" attributes the flip to the corpus and is wrong on that item. This is a claim-accuracy fix and is mandatory regardless of anything else in this plan.

**All 29 unreachable misses are tau2** (`report/miss_decomposition.json`): airline `book_reservation`, `update_reservation_flights`, `update_reservation_baggages`; retail `modify_pending_order_items`, `return_delivered_order_items`, `exchange_delivered_order_items`, `cancel_pending_order`, `modify_pending_order_payment`; telecom `send_payment_request`. Corpus sizes on those rows are 5 to 17 type-generic probes. Every one of those tools has benchmark-authored gold calls in tau2's own task files (10 to 41 calls per tool, 4 to 33 distinct argument sets). A tau2-only corpus therefore covers the whole population that matters.

**Refreeze boundary.** `RESUME-STATE.md` names the frozen set: `core/`, `dynamic/`, `adapters/contract_check.py`, `spec/validate.py`. `mutation/`, `experiments/`, and the adapter workers are outside it. Unused site pools after v2: M-PRECOND 76, M-IGNARG 56, M-PHANTOM 0, M-PARTIAL 0, M-INVAR 0, M-RESET 0. A third closed-world rescoring could draw fresh sites for only two of six operators.

**The agent-experiment frame is one call.** Evaluated statically over all 1,120 F2 frame tasks in `tasks.json` at the pinned commit: the frame contains exactly two distinct assistant-side gold sequences, and exactly one distinct `refuel_data` call, `{customer_id: C1001, line_id: L1002, gb_amount: 2.0}`, repeated 1,120 times across persona and ticket variants. L1002 is `Active` in the default database and no initialization action or gold action changes its status. The trigger predicate is false on all 1,120 tasks. The 8 tasks whose gold touches a suspended line (`resume_line` after `send_payment_request`) never refuel, so they are outside the frame. The N=5 result was, in effect, already exhaustive over gold behaviour.

**Page budget.** `main-submission.pdf` is 10 pages and page 10 is full to the final reference line. The two red placeholders (AI use, coordinated disclosure) are each one line; their previous full wording (kept in comments, and in `paper/main.md` lines 283 and 320) runs roughly 3 and 5 lines. The manuscript therefore carries a hidden debt of about 6 to 8 lines before this plan adds anything.

---

## 2. Item A: the recorded-calls corpus

**Recommendation: do, in a narrowed form.** Build the corpus from tau2's own gold reference actions, feed it to the open-world tau2 arm and the miss decomposition, and nowhere else.

### What building it involves

The plan's §2 item 1 reads "every recorded real call captured during adapter smoke-testing." No such capture happened, and capturing one now, by hand, after seeing which mutants were missed, is exactly the tuning the plan forbids. The only source that removes the author's hand is one authored upstream and fixed at the pinned commit: the assistant-side calls in `evaluation_criteria.actions` and `initial_state.initialization_actions` of tau2's task files. The construction rule, stated once and committed before any rerun:

> For each contracted tau2 tool, the recorded-call component is every assistant-side call to that tool appearing in the pinned task files of its domain, deduplicated by argument set, in file order. No call is added, removed, or edited.

Work, in order:

1. `experiments/recorded_calls.py` (new, in `experiments/`, outside the freeze): reads the three task files, emits `report/recorded_calls_tau2.json` keyed by tool. Half a day, including a test that the file is byte-stable.
2. Thread it through the two callers: `decompose_closed_world_misses.py:179` and `open_world_cosmic_ray/tau2_telecom/{precompute,scoring_lib}.py`. Airline and retail tasks have no per-task `initial_state`, so their gold calls replay against the domain's default database with the existing `fresh_env(domain)`; no adapter change. Telecom gold calls for the five in-scope tools (`enable_roaming`, `send_payment_request`, `resume_line` present; `disable_roaming` only via initialization actions; `suspend_line` has none) also target default-database entities, so a first cut needs no per-task environment. Half a day.
3. Tag `corpus-complete-v1` on the commit that lands the rule and the file, before anything is rescored.
4. Rerun the miss decomposition (33 mutants, minutes to an hour).
5. Rerun the tau2 open-world arm: 465 cosmic-ray work items, each a fresh interpreter; v2 completed all 465, so budget one overnight run. Precompute grows with the corpus; still small.
6. Regenerate `report/mutation_summary.md` via `build_mutation_report.py`; fix its dangling "See the caveat below" while there, since the provenance file already flags it.

Total: two working days plus one overnight run, with a third day of slack for the adapter-boundary hangs the provenance file documents.

### What it would likely change, and what stays the same

- Recall table (Table IV): unchanged, every cell. Precision: unchanged. Toy open-world: unchanged. Agreement study: unchanged (do not rerun; see below).
- Closed-world miss decomposition: the 29 split. M-IGNARG, M-PARTIAL, and M-INVAR mutants are exposed by any valid call, and gold calls are valid, so most of those 23 should become live and be classified. M-PRECOND's 6 need a call that *violates* the deleted guard with real entity ids; gold calls satisfy their guards, so those 6 may stay unreachable. Expect the taxonomy's `clause_gap` count to go up, not down. The M-INVAR eight will become "live but unclassifiable by the mechanical classifier," which is honest and unflattering.
- tau2 open-world: from "no usable number" to a defined escape rate, most likely high, as the toy arm's 0.956 was. The §7 committed framing already covers that outcome. If gold calls still expose no live mutant on those five tools, the arm stays undefined and the paper says so with the stronger fact that even the benchmark's own gold calls could not expose one; that is a result about `suspend_line` and `disable_roaming` having no or few gold calls, and it is reportable.
- Nothing in the abstract changes: it carries no numerals.

### What it breaks

`report/mutation_summary.md`, `report/miss_decomposition.{json,md}`, `report/mutation_open_world_tau2_raw.jsonl` (keep the v2 file, rename to `_v2`, as was done for v1). `paper/tables/` is regenerated by `report/render.py`; Table IV itself does not move. In prose: the tau2-telecom escape paragraph (§V.E), the sentence after Table IV on the 29 misses, the Threats paragraphs "Real-benchmark escape rate" and "Disclosed refreeze cycle" (its ranking sentence), and the Implementation Details paragraph (a tag to cite). `paper/main.md` mirrors every one of those. `experiments/numbers_audit.py` reruns; expect it to catch 465/2,325/0, 29, and 2 wherever they appear. Zenodo needs a new version; the paper cites `10.5281/zenodo.22182792`, and the record page reports the release as `...793`, which is the Zenodo pattern for a concept DOI one below its first version. Verify on `zenodo.org/records/22182793` that `...792` is the concept DOI before assuming the cited number survives a new version.

### Refreeze

No, on one condition: the checker and its prober are not touched and the closed-world sample is not rescored. The plan says the corpus "is frozen with the checker," so completing it is a change to a frozen artifact even if it is not a checker change. Name it for what it is: a corpus-completion cycle, tagged, dated, counted as one, and disclosed in the same sentence style the paper already uses three times (gold-trajectory substitution, post hoc comparability rule, one refreeze). A reviewer who sees a fourth disclosure of the same shape sees a habit; a reviewer who finds an undisclosed corpus change sees a problem.

Do not rescore the closed-world arm against the new corpus, and do not remove any mutant from the recall denominator as "inert." That would be equivalence adjudication after seeing which mutants were missed, the single largest degree of freedom W5 identified, and a shrinking denominator is the one change here that would move recall in the paper's favour.

### Is running it now defensible as pre-registered work finally executed?

Partly, and only under conditions. The honest position:

- It *is* a pre-registered component, named in a plan committed before any mutant was scored, and its absence is already disclosed in the paper and in three report files.
- It is *also* being executed after the v2 results were seen, and the paper must say that in those words. "The recorded-call component was empty in every run reported before 2026-09-1x; it was completed on that date from the benchmark's own gold actions under a rule committed at `corpus-complete-v1`, and the open-world tau2 arm and the miss decomposition were rerun. The checker and the closed-world sample were not." One sentence, in Threats.
- The defence against the tuning reading is structural, not rhetorical. The source is upstream-authored and fixed at the pinned commit, so the author chose nothing. The arms it changes are the ones whose numbers are expected to get *worse* for the taxonomy (more clause gaps, a high real escape rate). The arm a reviewer would attack (recall) does not move. A change that cannot improve the headline and is expected to hurt the taxonomy claim is hard to read as tuning.
- What would make it indefensible: hand-written calls, any call chosen because it reaches a missed site, any feed into `dynamic/probes.py`, any denominator change, or reporting the post-completion escape rate without the pre-completion "no data" beside it.

Given the author's prior rejection for a post hoc rule, the framing above is worth more than any number this produces. If at any point the corpus cannot be built purely by rule, stop and report the null as it stands.

### Displacement

Net text change is close to zero: the "Real-benchmark escape rate" threat shrinks by about two lines, the tau2 paragraph is replaced at roughly equal length, the decomposition sentence grows by about two lines. See the line ledger in §8.

### What not to do with the corpus

Do not rerun the agreement study. Its result is reported with the hand-built witnesses disclosed before outcomes; a second version adds churn to a sensitivity analysis and cannot fix the one flip, whose cause is elsewhere. Do not feed the corpus to the checker: that is a v3 refreeze with fresh sites for two of six operators, motivated by observed misses, and it is the one path in this plan that would actually look like tuning.

---

## 3. Item B: the checker's recall, and a third refreeze

**Recommendation: do not.** Leave `checker-freeze-v2` as the last freeze. The recall table stands.

The only way recall moves is a change to the prober or the checker, and the plan's §8 then invalidates the sample. Four operators have no unused sites, so a v3 run would reuse pools for four of six operators, which the paper already discloses once as an exception and would now have to disclose as the rule. The motivation would be the observed misses. The closed-world arm licenses only "detects violations of the clauses we wrote," and low recall on that narrow claim, with a mechanical decomposition of why, is a defensible result. A higher recall obtained after a data-driven prober change is not.

M-INVAR 0.000 and M-RESET "no data" stay as they are; the paper's existing sentences on both are correct and the corpus does not touch either.

---

## 4. Item C: demonstrated impact

### Can a flip be demonstrated without breaching the task-selection rule?

No, not on tau2's shipped tasks, and the reason is now mechanical rather than a matter of sample size.

The rule (`analysis_plan.md` §6): a task is in the frame iff its reference solution invokes a tool with a confirmed VIOLATES clause, enumerated exhaustively, no additions, no selection on observed behaviour; §3 forbids adding tasks after seeing exercise rates. Under that rule:

- F3 (airline): no flip is possible by construction. Gold and agent execute the same defective tool; the whole-state hash comparison is symmetric. Already stated.
- F2 (telecom): the frame is 1,120 tasks with one distinct `refuel_data` call on a line that is `Active` in every one of them. A gold replay cannot exercise the defect. An agent could exercise it only by refuelling a line the task never mentions (L1003 or L1009, the two suspended lines in the default database), that is, by an error unrelated to the task. The 8 tasks that do place a line in suspension never refuel in gold and are outside the frame; even an agent that refuelled there would be exercising the defect on a task whose assertions do not read the refuelled field.

Selecting the 8 suspended-line tasks, or stratifying the frame by initial line status, would be selection on the trigger's reachability. That is a static property rather than an observed behaviour, but it is chosen after learning that the rest of the frame cannot flip, which is the post hoc rule in a different coat. Do not do it.

### What to do instead

**C1. Run the full frame. Do.** `ab_run.py` already defaults to `full_population`; N=5 was a smoke cap. Roughly 30 minutes. The outcome is known in advance from the static pass (0 exercised, 0 flipped over 1,127 trajectories), and knowing it does not make the run post hoc: the frame rule was pre-registered, the run is the plan executed as written, and it *removes* a disclosed deviation rather than adding one. Fix the volatile `timestamp` in the hashed payload at `adapters/_tau2_worker.py:363` in the same commit, since `ab_results.json` is rewritten anyway and the adapter worker is outside the freeze; disclose in one clause.

**C2. Report the structure of the frame.** The sentence that does the work is not "N=1,127" but "the 1,120 telecom frame tasks are persona and ticket variants of one scenario and contain one distinct refuel call, on an active line." That converts the Threats paragraph "Provisional replay sample size" from an apology into a mechanism, and it is the honest reading of Table V's 1,135 / 2,285 row, which a reviewer who opens `tasks.json` will find. Say it before they do.

**C3. Report the null and argue it is the correct result. Do.** The pre-committed interpretation (§3 of the plan) already says it: the score is correct today because no gold path takes the broken one, and nothing in the benchmark prevents an agent from doing so. After C1 and C2 the argument gains a sharper edge: tau2's task generator never composes line suspension with a data refuel, so the benchmark cannot observe an agent violating the precondition its own docstring states. That is a statement about what the benchmark measures, not about a missing experiment, and it belongs in the paper as the answer to "what changes if every defect is repaired": on the shipped tasks, nothing, and the paper can now say exactly why.

**C4. Agent trajectory recording. Do not.** It is the pre-registered design and executing it would remove the "no model credentials" sentence, which reads as an excuse. But the expected information gain is near zero: on this frame, an exercise requires an off-task error, and the tau2 default agent (`gpt-4.1-2025-04-14`) on a two-call scenario with the line id in the ticket will not make it. Picking a weaker model to raise the chance is model selection for effect. The cost is credentials, a few hundred dollars over 1,120 episodes or a seeded subsample, and an end-to-end path (`record_trajectory` through litellm) that has never completed in this project. Two to three days of the seventeen for a null the paper can already state mechanically. Replace the credentials sentence with the structural one from C2, which is a better sentence.

**C5. AgentDojo and MM-ToolSandbox predicates.** No harness exists (`ab_run.py` docstring). Building one is out of scope in the time and would not change the story: F6 has no task exercising the tool, F5's at-risk task reaches the field through a non-defective tool, F7 is not computable offline.

### Displacement

The rewritten Threats paragraph is shorter than the current one by about three lines. The A/B paragraph loses "seed 1" and "N=5 per finding is provisional" and gains the frame-structure sentence; net about +1.

---

## 5. Item D: venue

The three candidates, checked today on the venue pages:

| Venue | Deadline | Notification | Pages | Fit |
|---|---|---|---|---|
| IDM special session (current target) | Sep 27 | Nov 1 | 10 | Topic list names "Large Language Models (LLMs)", "IoT, Autonomous Systems and Agents", "Data Cleaning", "Knowledge Discovery"; nothing on benchmarks or measurement validity. Proceedings. |
| ML on Big Data special session (`CLAUDE.md` backstop) | Sep 30 | Oct 31 | 10 full | Pure ML topics (dimensionality reduction, architectures, statistical approaches). Worse fit than IDM. Three days of slack. |
| SE4AgenticAI workshop (2nd, IEEE BigData) | Oct 10 | Oct 31 | 8 to 10 incl. refs | Topic list names "testing, verification, validation", "evaluation approaches and frameworks including LLMs as judges", "standardized agent-tool protocols (MCP, A2A)", "reproducibility and traceability", "observability, accountability, audit trails". Four of the paper's five contributions are on that list by name. |

Notifications for IDM (Nov 1) land after the workshop deadline, so the workshop is an alternative, not a fallback after rejection. The decision has to be made once.

**Recommendation: keep IDM, with one dated switch condition.** The paper has been shaped to the six-section data-mining form at the co-author's request, the data-quality bridge is written, and the 13 extra days would go to work this plan recommends against. Beyond framing, two cheap moves for fit: (1) align the IEEEkeywords line with the session's own vocabulary (`large language models`, `autonomous agents`) by swapping, not adding, so the line does not wrap; (2) in the venue-bridge paragraph of §I, name the two IDM topics the paper sits under in the session's words. Neither costs a line.

Switch to SE4AgenticAI if, on Sep 20, Wang's read asks for a structural change, or if the Sep 15 go/no-go fails on Item A and the paper would otherwise submit with a known claim-accuracy fix still pending. Drop ML on Big Data from the plan of record; `CLAUDE.md` should be updated to say so, since it is the one place the old backstop is still authoritative.

Verify on the workshop page, before Sep 20, that workshop papers enter the IEEE BigData proceedings volume in Xplore; the page fetched today does not state it.

---

## 6. Item E: a fifth benchmark

**Recommendation: do not.** Not feasible and not helpful.

Feasibility: the architecture's own estimate is a one-day adapter spike with a go/no-go checklist, then 30 to 45 minutes per tool for contracts, then manual confirmation of every VIOLATES, then coordinated disclosure. Disclosure today was sent with seventeen days' notice; a fifth team would get under ten. That is the one part of this that is not a scheduling problem.

Help: four benchmarks chosen anchor-first cannot support a prevalence claim, and five chosen the same way cannot either. The paper says this correctly in Threats. A fifth benchmark adds one row to Table III, one or two to Table V, and a finding row with quoted evidence: four to six lines the page does not have. The likely finding on a benchmark picked in a hurry is weaker than the eight already confirmed, so the addition lowers the mean quality of the ledger and adds nothing the limitation paragraph does not already concede. The generality argument the paper can make is the one it makes now: two non-anchor benchmarks each yielded a headline-eligible class, one of them the class that had been mutation-only until then. Leave it.

---

## 7. Mandatory items independent of strengthening

These are owed whatever else happens, and two of them cost lines.

1. **Write the two placeholder paragraphs.** AI use (about 3 lines) and coordinated disclosure (about 5 lines, with the disclosure-log rule, and the per-team status filled from `report/disclosure_log.md` on Sep 26). The previous wording is in `main.md` 283 and 320.
2. **Correct the agreement-flip attribution** in Threats, "Real-benchmark escape rate": the corpus explains the hand-built witnesses, not the flip. The flip is a `probe_values` annotation gap in the checker's own prober. The sensitivity paragraph in §V.E already states the mechanism correctly; only the Threats sentence is wrong.
3. **Reword the 29-misses sentence** after Table IV to what the diagnostic shows: for 29, the frozen equivalence corpus cannot establish liveness, so whether the checker missed a live mutant or scored an inert one is undecidable from that corpus. If Item A lands, this sentence is replaced by the new decomposition anyway.
4. **Confirm the disclosure actually went out today** and put the issue URLs in `report/disclosure_log.md`. The log's status column still reads `pending` for all four.
5. `AFFILIATION TO CONFIRM` for Zichong Wang; `\reviewfalse` for the submission copy; CyberChair required fields checked at submission time (the closing comment in `main.tex` already flags this).
6. Update `CLAUDE.md` and `RESUME-STATE.md` to the venue decision and the corpus-completion tag, so the repository's own instructions do not contradict the paper.

---

## 8. Line ledger

The paper is at exactly ten pages with the reference list ending on the last line; `arraystretch`, `tabcolsep`, and float spacing may not be touched further. Estimates are IEEE two-column lines.

| Change | Lines |
|---|---:|
| AI-use paragraph (from placeholder) | +2 |
| Coordinated-disclosure paragraph (from placeholder) | +4 |
| Closed-world decomposition sentence, post-corpus | +2 |
| tau2 open-world paragraph, replaced | +1 |
| Frame-structure sentence in the A/B paragraph | +2 |
| Corpus-completion disclosure clause (Threats) | +1 |
| **Additions** | **+12** |
| Threats "Provisional replay sample size" rewritten as mechanism | −3 |
| Threats "Real-benchmark escape rate" shortened, attribution fixed | −2 |
| Threats "Disclosed refreeze cycle", drop the three-way ranking sentence (the ranking moves into the corpus sentence) | −2 |
| A/B paragraph: "seed 1", "N=5 per finding is provisional", the credentials sentence | −2 |
| Baselines point (3), the AGORA+ scale reference, to a half-sentence | −2 |
| Sensitivity paragraph: the `venmo_social` segmentation detail to one clause (the mechanism is in `agreement_summary.md`) | −2 |
| **Cuts** | **−13** |

Margin of one line. If the compile lands on eleven pages after the cuts, the fallback order is: fold the frame-structure sentence into the existing Table V caveat (−2), then shorten the preliminaries sentence "Ignored Argument was itself mutation-only until ..." (−1). Do not cut any Threats limitation outright, any disposal, or any finding row; those are the standing rule.

---

## 9. Schedule

Today is Wed Sep 10. Submission is Sun Sep 27, 11:59 pm PST.

| Date | Work | Gate |
|---|---|---|
| Wed 10 | Confirm disclosure sent; issue URLs into the log. Decide Items A and C1 (this document). Update `CLAUDE.md` venue line. | |
| Thu 11 | `experiments/recorded_calls.py` and the corpus file; rule committed; tag `corpus-complete-v1`. Thread into the decomposition script; rerun it. | Corpus rule committed before any rerun |
| Fri 12 | Thread into the tau2 open-world precompute and scoring; start the 465-item run overnight. Full-frame `ab_run.py` (30 min) with the hash fix; regenerate `ab_summary.md`. | |
| Sat 13 | Open-world results in. `build_mutation_report.py`; `render.py`; numbers audit dry run against the unchanged manuscript to list every number that will move. | |
| Sun 14 | Paper text: all §7 mandatory items; A/B paragraph; both Threats rewrites; tau2 paragraph; decomposition sentence; keywords. `main.md` mirrored. Compile, page check. | |
| **Mon 15** | **Go/no-go on Item A.** Go if: the corpus was built purely by rule, the checker diff is empty, the open-world run completed, the numbers audit passes, and the page count is ten. Otherwise the paper keeps the v2 "no usable number" text and the §7 fixes only; the corpus work is retained in the artifact as unreported future work. | **Go/no-go** |
| Tue 16 to Thu 18 | Full read against the co-author review lessons (claim-support pass on every rewritten sentence). Humanize pass, formal register, on the new prose only. Venue-fit keywords. | |
| Fri 19 | Zenodo new version; confirm the cited DOI is the concept DOI; `make reproduce-results` on a clean clone. | |
| **Sat 20** | **Content freeze.** Draft to Wang. After this point no number, claim, or paragraph changes except the disclosure-log rows and the disclosure paragraph's per-team status, which the committed rule allows up to the deadline. Venue switch decision, if any, is made today and not revisited. | **Freeze** |
| Sun 21 to Wed 24 | Verification only: reproduce on a second machine; numbers audit; reference venue confirmations against `REFERENCES.md`; PDF font and margin check; CyberChair field check. Wang's comments handled as wording only; anything larger is declined and noted for camera-ready. | |
| Thu 25 to Fri 26 | Disclosure responses folded in per the committed rule; final compile; final numbers audit; `\reviewfalse` confirmed. | |
| Sat 27 | Submit. Preprint and artifact link the same week, per the architecture's release commitment. | Submit |

If the Sep 15 gate fails on Item A, nothing else in the schedule moves; the corpus work stays in the artifact, unreported, and the paper ships with its current detection story plus the §7 corrections.

---

## 10. What the paper says afterwards

If everything above lands, the detection story changes shape without a single recall cell changing value. Today: recall is low, 29 misses are blamed on a corpus that does not exist, the real open-world arm has no number, and the replay null rests on five gold trajectories. After: recall is low, the misses decompose into named causes under a corpus the benchmark authored, the real open-world arm has a defined and probably high escape rate reported under a framing fixed before it existed, and the replay null is exhaustive and explained by a property of the task generator rather than by a sample size. The abstract does not change. Contribution 4 does not change. The Threats section gets shorter and more specific.

That is the strengthening available in seventeen days without choosing anything after seeing the data. The weak numbers are the true numbers; what improves is the account of why they are what they are, and that account is the part of the paper a methods reviewer reads twice.
