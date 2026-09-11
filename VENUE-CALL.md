# Venue call, 2026-09-11

Decision memo. No manuscript edits were made. Everything below about a venue was read on its own page today; where a page could not be read, that is said.

## Recommendation: submit to SE4AgenticAI (option B), deadline 2026-10-10

Withdraw the IDM special session as the target and make the switch today, not on the 2026-09-20 decision date in `STRENGTHEN-PLAN.md`. The one action this needs before anything else is Wenbin Zhang's agreement, since the six-section data-mining shape was his request; the shape itself stays, so the ask is small.

## 1. Why B and not A

The paper's five contributions are all named, in the workshop's own words, on its topic list: "Testing, verification, validation", "Evaluation approaches and frameworks", "Observability, accountability, audit trails, and reproducibility", "Standardized agent-tool protocols (e.g., MCP, A2A)", "Reproducibility and traceability". The IDM list (read today at `bigdataieee.org/BigData2026/calls/special-data-mining/`) has forty-odd entries and none of them is testing, evaluation, benchmarks, or validity; the nearest are "Large Language Models (LLMs)", "IoT, Autonomous Systems and Agents", and "Data ... Cleaning". At A the paper is an SE testing paper asking a data-mining committee to accept a bridge paragraph as the reason it belongs.

That matters more than usual because of what the paper honestly discloses. Recall of 0.020 to 0.359, an escape rate of at least 0.956, and zero verdict flips read differently to the two audiences. A testing reviewer reads them as a mutation-analysis result with a mechanical miss decomposition and a pre-registered plan, which is the normal shape of a careful SE evaluation. A data-mining reviewer who already doubts the paper belongs in the session reads them as "the proposed method does not work", and the disclosed weaknesses become the reason to reject a paper that was already off-topic. The paper cannot fix that by writing; it is a property of who reads it.

On standing: the gap between A and B is smaller than "main proceedings versus workshop" suggests. The 18.4% figure is the main research track's. The IDM special session is a separately organised session with its own reviewing, listed alongside the workshops on the conference site, whose papers "will be included in the official IEEE BigData 2026 conference proceedings". Workshop papers go to the "Workshop Proceedings published by the IEEE Computer Society Press" (call for workshop proposals, read today), which for IEEE BigData means the same Xplore volume series. On a CV the difference is one word in the citation. For an author with 0 acceptances and 9 rejections, an accepted, Xplore-indexed, DOI-backed paper with a public artifact and coordinated disclosure on record is worth more than a coin flip at a session where the flip is weighted against the paper.

The asymmetric cost is the timeline. IDM notifies on 2026-11-01 (the session page; the 10-24 date is the main track's). By then every fitting SE venue this autumn has closed: FORGE 2027 and AST 2027 on 2026-10-30, ICSE NIER and MSR on 2026-10-23, SE4AgenticAI on 2026-10-10. A rejection from A therefore does not mean "then B"; it means the paper waits until 2027 with its disclosure timeline and pinned commits ageing. A rejection from B, which is unlikely, means the same wait, but B's acceptance odds are the odds of a second-year workshop with a thirteen-member PC reading a paper squarely on its topic list.

Plainly: submitting to A is a poor use of the cycle. The paper is not too weak for A; it is invisible to A's topic list, and its honest numbers are the kind of thing an off-topic reviewer uses to close the case.

Two things about B were not confirmable today and should be settled by one email to Paulo Alencar before 2026-10-10: whether 2025's papers appeared in Xplore (the 2025 workshop page returns 404, so this could not be checked), and whether review is single- or double-blind (the page does not say; the paper names its authors and cites its own Zenodo DOI).

## 2. Third options, checked

All sixty-odd IEEE BigData 2026 workshops were read from the official list. The ones with any topical claim:

| Venue | Deadline | Fit | Verdict |
|---|---|---|---|
| BPOD 2026 (Benchmarking, Performance Tuning and Optimization for Big Data and Big Models) | 2026-10-01 | "Benchmarking and comparative studies ... large models". Benchmarking of systems performance, not benchmark validity. | Worse than B. |
| S2AI 2026 (Secure and Safe AI Agents for Big Data Infrastructures) | 2026-10-01, abstract 09-24 | Agent security; "integration challenges with external tools" is the only hook. | Worse than B. |
| WLLFM 2026 (Large Language and Foundation Models) | 2026-10-26 | Generic LLM workshop; Xplore stated explicitly. | Worse than B; fallback only. |
| "Building Trustworthy AI Pipelines for Big Data: Verification, Provenance, and Reproducibility" | unknown | Name fits; no CFP page exists yet. | Cannot be recommended unseen. |
| TRUSTMORE 2026 (Trustworthy Multimodal Agents) | unknown | OpenReview page had no content today. | Cannot be recommended unseen. |

Outside BigData, two are worth naming and rejecting for now:

- **AST 2027** (ICSE co-located; 2026-10-30; 10+2 pages, IEEE template, IEEE and ACM DLs; theme "Testing in the Age of AI: Governance, Compliance, and Oversight"; double-blind). The best topical fit of anything found: it is a testing conference and this is a conformance-testing paper. It is also where a mutation-testing expert reads recall 0.020 to 0.359 with the most scrutiny, and double-blind would require stripping the author-named artifact, the DOI, and `FINDINGS-VERIFIED.md` references. A stronger line that may not happen, for an author whose three methodological rejections argue for banking one acceptance first.
- **FORGE 2027** (ACM, ICSE co-located; 2026-10-30; 10+2 pages). Better standing than either A or B, but its scope is foundation models for software engineering, and none of the four audited benchmarks is an SE benchmark. Partial fit; not this paper.

arXiv-first then a stronger venue next cycle: not recommended. The disclosure clock started 2026-09-10 and the paper's value is highest while the pinned commits are current and the maintainer responses are fresh. Post the preprint the same week as the B submission, as the architecture already commits to, rather than instead of it.

The corpus-completion work and any maintainer responses are the seed of a follow-on paper for AST 2028 or ISSTA (2027-01-11 deadline is too soon). That is the route to the stronger line, with an acceptance already on record.

## 3. What changes in the paper for B

Small. The venue was chosen for the paper, not the paper for the venue, so most of this is removing scaffolding built for A.

**Cut the data-quality bridge.** The paragraph in §I beginning "That untested contract is also a data-quality problem" exists to justify the IDM submission. Cut its first sentence (the `wangstrong96` data-quality-dimensions framing) outright. Keep the provenance sentence (`bunemantan01`) but move it to §IV.C, where score-at-risk is defined, since dependency analysis is what that subsection does and the citation earns its place there. Keep "present on every rerun ... travels with the number" in §I; it survived Zichong's objection and it is the paper's stakes sentence, not a venue sentence. Net about four lines freed, which pays most of the six-to-eight-line hidden debt for the two placeholder paragraphs that `STRENGTHEN-PLAN.md` §1 identifies. Run `numbers_audit.py` and check `REFERENCES.md` after removing `wangstrong96`.

**Title.** Keep it. "Do Agent Benchmarks Do What They Say? An Executable-Contract Audit of Tool-Using Agent Environments" is already an SE title, and the co-author has reviewed it under that name.

**Keywords.** Replace `data quality` with `agentic AI`; replace `measurement validity` with `mutation analysis`. Both are workshop vocabulary and the line does not wrap. Keep `design by contract` and `conformance testing`.

**Abstract.** Leave the argument as it is. The one sentence that reads as a data-product framing ("Benchmark scores are published data that the field aggregates into leaderboards") works equally well for an SE reader and should stay. Do not add an "executable conformance testing" flourish; the abstract carries no numbers and no venue words now, which is the right state.

**Related work.** No emphasis change. §II.C (contract inference, API oracles, testing lineage, metamorphic relations, PolDet and iDFlakies) is the subsection an SE reviewer reads first, and it is already the one that concedes technique novelty and claims target novelty, which is the right posture for that reader. Do not add an MCP or A2A citation to match the workshop's "standardized agent-tool protocols" bullet unless one is already verified in `REFERENCES.md`; a citation added for fit is the kind of thing a reviewer at this workshop notices.

**Structure.** Keep the six-section shape. It costs nothing at B and undoing it would reopen a co-author decision. Keep Threats to Validity exactly; an SE committee expects it and will read every one of its ten limitations as evidence of competence rather than as a critique list.

**One sentence to add**, in §V.C or the paragraph after Table IV, if it is not already explicit: that the recall figures are the checker's mutation score under the frozen prober, that they are reported rather than tuned, and that the confirmed-findings ledger is independent of them. The paper says this in pieces; a testing reviewer wants it in one place.

**Page limit.** 8 to 10 pages including references; the paper is at 10 with the reference list ending on the last line. The bridge cut and the placeholder fill roughly net out; the line ledger in `STRENGTHEN-PLAN.md` §8 still governs.

**Schedule.** The 2026-09-15 go/no-go on the corpus and the 2026-09-20 content freeze keep their dates. The 13 extra days are slack for Wang's read and for maintainer responses, not for new experiments. Update `CLAUDE.md` line 3 and `RESUME-STATE.md` line 73 to the new venue once Wang agrees; drop the ML on Big Data backstop from both.

## 4. If A after all

The single highest-leverage change is the one `STRENGTHEN-PLAN.md` §5 already names: rewrite the bridge paragraph to use the session's own topic words verbatim ("Autonomous Systems and Agents", "Large Language Models", "Data Cleaning") and swap the keywords line to match, so that the reviewer assigning fit sees the session's vocabulary on page 1. Nothing else in the paper can move a reviewer who has decided it does not belong, and that is the reason A is the poor bet.
