# Independent review, part 2: abstract, figures, replies to the co-author, readability

Continues `FABLE-REVIEW.md`. Read-only pass over `paper/latex/main.tex` at commit `53909b0` (588 lines), the compiled `main.pdf` (2026-09-11 21:36), `main-submission.pdf` page 1, `ZICHONG-COMMENTS.md`, `ZICHONG-VERIFICATION.md`, `ZICHONG-RESPONSE.md`, `report/medagentbench-disclosure-check.md`, and `VENUE-AND-COAUTHOR-STYLE.md`. Nothing was edited. Line numbers are `main.tex` at `53909b0`.

## 0. Status of part 1

The scores, the four tension resolutions (T1 to T4), and the ranked fixes in `FABLE-REVIEW.md` stand. Re-checked against the current source:

- F2 (T3) has been applied: the six restating limitations are now label, one sentence, and pointer (lines 537 to 555). The ranking sentence closing "Disclosed refreeze cycle" survived, as recommended.
- D2 (line 444 "what the abstract means by three demonstrated dynamically"), D3 (line 376 and 555 pointing at each other), D4 (line 563 "across six executable classes"), D5 (line 563 "nobody has been checking"), D6 (line 259 orphan lettered paragraph), D7 (line 470 bibliographic parenthetical), D9 (line 142, 568, 573 placeholders) are all still present.
- F8 (abstract sentences 5 to 7) is superseded by §1 below, which replaces the whole abstract.
- Table word counts in part 1 are stale; another agent is compressing Tables I and IV. Nothing below depends on them.

One correction to part 1's ledger: the abstract replacement below frees about 10 body lines (bold 9pt, 257 to 190 words), and the Figure 1 caption cut in §2 frees about 3 more. Part 1's net of "+45 freed, -10 to -13 spent" becomes roughly +58, so the placeholders, the orientation sentence, and the legibility fix are funded twice over.

## 1. The abstract

### Replacement, 190 words

> Tool-using agents are entering settings where a wrong action has a real cost, and the benchmarks certifying them execute each tool call in simulation and grade what the call reports having done, assuming the tool did what its interface advertises. The audits we survey inspect tasks, gold solutions, and graders, never that assumption; a defect behind it is present on every rerun. We treat each tool's advertised surfaces as an executable contract, check the implementation against it, and trace which task verdicts read state a defective tool should have written. Across 34 mutating tools in four benchmarks we confirm eight defect instances at pinned commits, one headline-eligible class in each. Against injected defects the checker raised no false positive in 25 flags; its recall is low, and 29 of 33 misses trace to the probe corpus, not the taxonomy. The clearest case is a clinical benchmark whose interface tells the agent each write executed, under a no-write design its paper documents and its interface does not, and whose grader takes that message as evidence: its action success rate records whether a request was well formed, not whether any record changed.

Six sentences, five-part order kept (stakes, gap, approach, setting and result, example). Numerals follow the venue file's own recommendation (`VENUE-AND-COAUTHOR-STYLE.md` line 181): small counts in words, tallies and rates as digits.

### Which sentence makes a researcher read on, and why

The last one. Three reasons.

1. It is the only sentence the title does not predict. Everything before it a reader can infer from "Do Agent Benchmarks Do What They Say?"; the last sentence tells them which benchmark, what the tool says, what the code does, and what the published number therefore measures.
2. It names a number a reader may have reused. "Action success rate" is a column in a NEJM AI table. A researcher who has cited it now has a reason to keep reading that is theirs, not the paper's.
3. It is quotable in one clause, which is what gets a paper cited: "its action success rate records whether a request was well formed, not whether any record changed." The citing sentence writes itself.

It also survives the co-author's objection in the same breath it makes the claim: "under a no-write design its paper documents and its interface does not" concedes the documented design before asserting the defect, so a MedAgentBench author reading the abstract meets the concession first.

The numerals sentence (34, eight, 25, 29 of 33) does a different job. It tells the reader this is an audit with denominators, and it puts the instrument's weakness ("its recall is low") on page 1, where a reviewer meets it as disclosure rather than on page 7 as discovery. That is the sentence that keeps the weak recall numbers from reading as an ambush.

### Support for every claim in it

| Claim | Source |
|---|---|
| "what the call reports having done" | line 162, 176; the widened class Zichong's C1 asked for |
| "never that assumption" | line 178 to 179, scoped to the four cited audits |
| "present on every rerun" | line 162, 212, 298; the surviving half of the C3 fix |
| 34 mutating tools, four benchmarks, eight instances | Table III totals, line 423 |
| "one headline-eligible class in each" | Table III HL column reads 1, 1, 1, 1 (lines 418 to 421); exact, not "at least" |
| "at pinned commits" | Table IV commit column |
| 25 flags, no false positive | line 525 (TP=25, FP=0, pooled toy plus real) |
| "its recall is low" | Table V, Wilson lower bounds 0.000 to 0.359 |
| 29 of 33 misses to the probe corpus | line 523 |
| no-write design documented, interface silent | line 182, 470; `report/medagentbench-disclosure-check.md` lines 29 to 38 |
| grader takes the message as evidence | line 470 "admitting evidence only when it matches Finding 1's success string" |
| "records whether a request was well formed, not whether any record changed" | line 470, resting on MedAgentBench's own §2.4.1 |

The last row is the strongest claim in the abstract and the one to defend. It is a description of what the grader computes, not a consequence claim, so it sits below the score-at-risk certainty ceiling C3 set. Keep it.

### What was dropped, and why

- The three data-quality sentences ("published data that the field aggregates ... does not average out ... travels with the number"). Part 1 already asked for one; the replacement keeps six words of it ("present on every rerun") because that is the half C3 left standing.
- "presents a specification language, a static and dynamic conformance checker, and a dependency analysis". An artefact list mid-abstract; the venue sample ends on ideas, not deliverables (venue file, finding 3). The method sentence now names the three stages as verbs.
- "widely used". Unsupported by anything in the paper and a prevalence-adjacent word.
- "validate the checker against injected defects" without a result. Replaced by the result.

### One thing to decide

The C1 reply (line 167) opens "The opening now says a benchmark grades what a call reports having done, either by reading the state it left or by reading the result it returned." The replacement abstract keeps "what the call reports having done" and drops the two-arm gloss, which the introduction's first paragraph still carries (line 176). Either change the reply's "The opening" to "The introduction", or restore ", in state or in its return," after "having done" in the abstract (+6 words, 196). I would change the reply; the abstract reads better without the gloss and the class term is the one the paper defines.

## 2. Figures

**Verdict: two is right. Do not add a third. Upgrade both in place at zero footprint.** The venue sample runs 2 to 13 figures per paper, and the two-figure paper (DP-TabICL) is a method paper without curves, the shape closest to this one. Every candidate third figure is either a picture of the weakest numbers or a mechanism Figure 2 can carry in one of its boxes.

### Figure 1, read as a reader on page 1

Column 2, top of page 1 (`main-submission.pdf` p. 1). What I see: three stacked boxes labelled Interface, Implementation, Evaluator, with generic contents (`docstring, schema, prompt, return`; `tool(args), pre -> post`; `state / transcript -> verdict`), two red arrows whose 4pt labels I cannot read at print size, a dashed blue arrow with another unreadable label, and a floating "Benchmark audits: inspect bands 1 & 3 only" in the top-left corner. Below it, a five-line caption that carries the worked instance in prose because the picture does not.

Does it earn page 1? Half. The concept (audits read the outer bands; nothing tests band 2 against band 1) is the thesis, and a picture of it belongs on page 1. But the picture is a diagram of a sentence the introduction states three times, and the paper's best material, the string `POST request accepted and executed successfully` from a real repository, sits 4 cm below it in body text.

Fix, same footprint: put the MedAgentBench instance into the bands and make the generic labels the band titles.

- Interface band: **Interface** (what the agent reads). `"POST request accepted and executed successfully"`, tool return, `__init__.py:85-91`.
- Implementation band: **Implementation** (what the call does). Payload parsed into a local, never read; no write in the repository (`git grep send_post_request`: nothing).
- Evaluator band: **Evaluator** (what the score reads). `refsol.py` gates on that string; 0 of 300 write cases read FHIR state.

Drop the three arrow labels (part 1, D8/F15); with them gone the bands can take `\footnotesize` text without `\resizebox`. Caption to two sentences:

> Fig. 1. The tool contract sits between the two bands benchmark audits read (§II), and graders read band 2's output as ground truth. MedAgentBench's write path, instantiated: the interface reports a write, the implementation performs none, and the grader accepts the report.

Net: caption from five lines to two; the figure now shows the finding instead of describing the category the finding belongs to. A researcher who reads only the title, the abstract, and Figure 1 gets the whole paper.

### Figure 2, read as a reader

Page 4, column 1, under Tables I and II. Three boxes A, B, C and a Validation box, text at about 4pt after `\resizebox`. The caption says the stages match "§IV's three subsections in order", which is the figure admitting it carries the section's table of contents.

Keep it: a data-mining reviewer expects a method overview and every venue paper has one. Make it earn its place by giving each box the challenge it answers (§I, bold labels) and one number from the paper, so the figure previews results rather than headings:

- **A. Contract** (no contract exists). Authored from advertised surfaces; every clause cites file and line; 31 contracts across three benchmarks, none for MedAgentBench.
- **B. Checker** (simplification is not defect). Static scan proposes sites; dynamic run snapshots `pre` and `post`; benign-simplification rule decides; UNTESTABLE stays in every denominator.
- **C. Score-at-risk** (a violation does not name the scores it reached). Defect to field to evaluator to tasks; `refuel_data`: one clause, 1,135 of 2,285 tasks; MedAgentBench: transcript-graded, undefined.
- **Validation.** 25 flags, 0 false positives; 29 of 33 misses traced to the probe corpus; 10 gold replays, 0 flips.

Set the four boxes at natural width with `font=\scriptsize` (about 2.6 cm each), no `\resizebox`; they fit a column at the current height. The recall lower bounds do not go in the figure: a method overview that prints 0.000 is a reviewer's exhibit.

Placement: if Tables I and II shrink in the pass now under way, `[!t]` on Figure 2 so it leads page 4 rather than sitting under two tables.

### Candidate third figures, and why each loses

| Candidate | Would show | Claim supported | Cost | Verdict |
|---|---|---|---|---|
| Score-at-risk trace diagram | VIOLATES clause, AST-derived paths, evaluator read sites by provenance, task enumeration; tau2 telecom and MedAgentBench as two branches | Challenge 3; "bases do not pool" | 12 to 15 lines | The §IV.C text calls this "the central deliverable" and it has no picture, which is a real gap. But at zero slack it costs exactly the lines F4 needs for the placeholders. Fold its two branches into Figure 2 box C, as above. |
| Code figure: POST branch beside the `refsol.py` gate | Lines 85 to 91 and the grader's string match | Finding 1 and 4 | 10 lines | Was on page 1 before Figure 1 replaced it. The Figure 1 upgrade gets most of it at no cost. |
| Miss decomposition (33 real-tool misses; 225 toy escapes) | Stacked bars: probe corpus, clause gap, crash | Threats | 8 lines | A chart of the weakest arm. The prose at lines 523 and 527 already gives the split. No. |
| Recall by operator, bar chart of Wilson LBs | Five bars from 0.000 to 0.359 | Nothing Table V does not | 8 lines | Table V does it, and a bar chart of those values draws the eye to them. No. |

## 3. The five replies to Zichong

Register first, since it applies to all five: no verdict openers, no thanks, each reply says what changed and where, and they read in one voice. Commit `e52c576` did that job. The remaining faults are accuracy, not tone.

| # | Answers the comment | Accurate about what changed | Reads as a colleague | Action |
|---|---|---|---|---|
| C1 | 2 of 3 points | Yes | Yes, though "Both are fixed." is clipped | Add one sentence |
| C2 | Yes | One overstatement | Yes; the best of the five | Fix the last sentence |
| C3 | Yes | Yes | Yes | None |
| C4 | Yes | First sentence is wrong | Yes | Rewrite the first sentence |
| C5 | Yes | Last sentence overstates | Yes; the history reads as context | Depends on T4 |

### C1 (line 167)

Verified: abstract line 162 and introduction line 176 are two-armed; the preliminaries (line 298, "whether as stored state or as the result a call returned") and the conclusion (line 563, "what a grader reads") are fixed as the reply says. `ZICHONG-VERIFICATION.md` marked this PARTIAL on an earlier build; it is closed now.

Not answered: his third point, that the "every leaderboard position" claim was too broad. The widening resolves it, since a benchmark that grades what a call reports having done is by definition assuming the call did it, but the reply does not say so and he will look for it. Append:

> The sentence about every leaderboard position now applies to that widened class, where it holds by definition: a benchmark that grades what a call reports having done is assuming the call did it.

And see §1's last item: if the new abstract is adopted, "The opening now says" becomes "The introduction now says".

### C2 (line 179)

Verified against `report/medagentbench-disclosure-check.md`: §2.4 carries the GET-only decision and the re-initialisation reason (lines 29 to 32 of the report), §2.4.3 carries the JSON-loadable sanity check and the success indication (lines 35 to 38). The reply attributes both correctly. "The write-task grader admits evidence only when it matches that string" matches line 470.

Overstated: "Two other claims rested on the old framing and are gone, including the one about five prior audits." Only one claim went. The second change was a disclosure added, not a claim removed: no contract exists for MedAgentBench, so validator check 8 never ran on the finding (line 470). `ZICHONG-RESPONSE.md` gets this right; the in-source reply does not. Replacement for the last sentence:

> One other claim rested on the old framing and is gone, the one about five prior audits, which our own gate file never supported. And because agent visibility now carries the finding, the paper says plainly that the validator's visibility check never ran on it: no contract exists for MedAgentBench, so that classification is a hand reading at the pinned commit.

"We went back to their paper before changing anything" is the right first sentence. Keep everything else.

### C3 (line 214)

Verified: "not hypothetical" has zero matches in the source; "present on every rerun" survives at lines 162, 212, 298; line 212 now separates presence ("present on every rerun") from effect ("what that exposure could amount to is what score-at-risk bounds, without asserting that any verdict changed"). "The text was running two things together" is an accurate self-diagnosis. Right as it stands.

One phrase he named, "into every downstream use", survives at line 212 attached to exposure rather than loss. The reply does not mention it. If he re-reads closely he may notice; a clause would pre-empt it: "the downstream-use phrase survives but now attaches to exposure, not loss." Optional.

### C4 (line 178)

"All three are gone." is not true, and he will see that from the next sentence in the same paragraph. Two of the three survive in scoped form: "Each of these stops one layer above the tool body" and "None of these tests the interface-to-state-transition contract itself" (line 179), both now bound to the four cited audits. That scoping is the right fix, and part 1 and `ZICHONG-VERIFICATION.md` both pass it; "gone" is the wrong word for it. The figure caption's "neither tests band 2 against band 1" is likewise scoped, not removed. Replacement for the whole reply:

> All three are now scoped to the four audits we cite, and the figure caption names the two categories it means. What remains beyond that scoping is narrower and checkable: none of those taxonomies has a category for a success signal decoupled from state, 27 categories mapped in the gate file, which is a claim about their published schemas rather than about what they would have found.

The 27-category claim is supported at line 432 and Table I.

### C5 (line 224)

The history sentence reads as context, not excuse. Three things make it so: the fact is stated once and neutrally ("an internal review round asked us to say early"); "before you saw the draft" answers the question a co-author would otherwise ask (whose review, and did my comment cause it), which is why commit `53909b0` added it; and the next sentence takes the fault ("we think the placement was the mistake rather than the honesty"). Keep it as written.

What is overstated is the close. "The contribution list no longer calls itself ordered by importance, which is what had put it at odds with the motivation." The label is gone (line 216 reads "The contributions:"), but the list still leads with dependency analysis, which is the thing his comment named. Deleting the label removes the contradiction in print, not the emphasis a reader takes from item 1. And "the introduction ends on what the paper establishes" is one sentence early: the last sentence is the roadmap.

Both resolve if part 1's T4 is applied (three items, findings first, confirmation clause absorbed into item 1). The reply's last two sentences then become:

> The list is now three items and leads with the audit result, which is what the title, the worked example, and the conclusion lead with. The confirmation-versus-discovery point is a clause inside that first item, so the introduction's last substantive words are the contributions.

If T4 is not applied, the reply must not claim the ordering problem is resolved. Then:

> The list keeps its order but no longer calls itself ordered by importance. If you still read item 1 as the primary claim, say so and we will lead with the findings.

## 4. Is it interesting to read

Pages 1 and 2, yes. The title, the MedAgentBench paragraph (line 182), and the benign-simplification block quote (line 328) hold attention the way the author wants, and they do it inside venue register: every one of them is specific to a file, a line, or a string in someone else's code. Pages 5 to 8 read as a ledger read aloud. The pattern is consistent: the paper is interesting wherever it reports what it found and dull wherever it explains its own procedure. Part 1's §3 already lists nine losses; the three below are the ones it did not name, in page order.

**1. §II opening, line 249.** One 58-word sentence that is a table of contents.

> Current: "Locating that cross-layer blindness precisely means placing this audit against three bodies of work: how agent benchmarks grade tool-using tasks today, a separate literature that already verifies task completion against recorded state rather than a returned status, and the contract-checking lineage this paper's technique borrows with a different target."
>
> Replacement: "Three literatures border this audit, and each takes the tool layer on trust: the benchmarks that grade by the state a call leaves, the work that verifies completion against that state, and the contract-checking lineage whose technique we borrow for a different target."

Opens on the claim the three subsections each end on, so the reader knows what to look for.

**2. §V.A, line 403.** Python version numbers in the setup paragraph.

> Current: "The four benchmarks cannot share an interpreter: tau2-bench requires Python 3.12 or later, MM-ToolSandbox requires 3.11 or 3.12, and the checker itself runs on 3.11.7. Each adapter therefore drives its benchmark in that benchmark's own environment across a subprocess boundary, which is why exceptions absorbed at that boundary bound the recall figures reported below."
>
> Replacement: "Because the four benchmarks cannot share one Python interpreter, each adapter drives its benchmark across a subprocess boundary, and exceptions absorbed at that boundary bound every recall figure below."

The version numbers belong in the artifact. Saves two lines and keeps the one fact the Threats section needs.

**3. §V.E.i, line 533.** The sensitivity-analysis opener is the sentence a reader is most likely to re-read twice.

> Current: "Contract authoring is measured, not trusted, but narrower than independent replication: both annotator sets are agent sessions on the same model family, and only B authored blind, since A already knew which tools carried confirmed findings."
>
> Replacement: "Two annotator sets wrote contracts for the same six tools against one pre-committed probe corpus. Both are agent sessions on one model family and only B wrote blind, so what this measures is whether a sentence turns into the same predicate twice, not whether two people would agree."

States what was done, then what it can show. The current version states the caveat before the reader knows what is being caveated.

## 5. What I did not check

I did not compile the paper with the replacement abstract or the figure changes, so the line savings in §0 are estimates from word counts at 9pt bold and from the caption lengths. I did not re-verify any finding against the audited repositories. I did not check the review build (`main-review.pdf`, 2026-09-09) for how the replies render; the analysis in §3 is from source. Tables I and IV were being edited by another agent while this was written and were not read.
