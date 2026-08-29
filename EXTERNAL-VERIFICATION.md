# EXTERNAL-VERIFICATION.md — Panel-Mandated External Checks

Three external-verification tasks flagged by the peer-review panel as must-fix. Completed 2026-08-22. Each section states the verdict first, then the evidence.

---

## Task 1 — Open question X6: does the ABC checklist's tau-bench finding overlap our tau2-bench findings?

**Verdict: no overlap. Disposal, not deferral.** The ABC checklist (arXiv:2507.02825, "Establishing Best Practices for Building Rigorous Agentic Benchmarks") audited the **original tau-bench** (Yao et al., arXiv:2406.12045, released 2024-06-17, code at `github.com/sierra-research/tau-bench`), not **tau2-bench** (Barres et al., arXiv:2506.07982, released 2025-06-09, code at `github.com/sierra-research/tau2-bench`), the artifact this project audits at commit `c3398666`. These are two different papers, two different repositories, and — decisively — two different grading mechanisms. The overlap risk named in `GATE.md` §8 and `PAPER-OUTLINE.md` X6 is closed: cite ABC as a disposal, not as prior art requiring deferral.

### (a) What ABC reports, quoted verbatim

Source: PDF pages read directly (not paraphrased) from `arxiv.org/pdf/2507.02825` (v5, 2025-08-07), pages 1, 2, and 22 (Table 9).

Abstract (page 1):
> "we show that many agentic benchmarks have issues in task setup or reward design. For example, SWE-bench-Verified uses insufficient test cases, while τ-bench counts empty responses as successful."

Introduction (page 2):
> "In addition, we find that in τ-bench, a trivial agent that returns empty responses is considered successful on intentionally impossible tasks (e.g., changing a non-refundable ticket). This trivial agent achieves a 38% success rate and outperforms a GPT-4o-based agent [86]."

> "Issues in task design or implementation often breaks task validity... τ-bench allows a trivial agent to pass 38% of tasks without knowledge of airline-ticketing rules."

**Table 9 — "Assessment Report of τ-Bench"** (page 22), the actual per-check evidence behind the summary claims, with **Score 0** (failing) rows quoted verbatim:

| Check | Score | Reason (verbatim) |
|---|---|---|
| O.b.1 | 0 | "The benchmark does not specify how negation modifiers are handled, which may lead to incorrect evaluations." |
| O.b.2 | 0 | "The benchmark does not specify how it handles systematic listing of all possible answers, which may lead to incorrect evaluations." |
| O.b.3 | 0 | "A part of tasks has empty ground truth, which may lead to guessing." |
| O.g.3 | 0 | "A part of tasks has empty ground truth, which may lead to trivial state modifications." |

The defect, stated precisely: some tasks ship with **empty ground truth**, which (i) lets a trivial/empty-response agent pass by guessing, and (ii) lets the benchmark's **substring/list-matching response check** be defeated by an agent that lists every possible answer. Both are properties of the **task/ground-truth data and the grading rubric's string-matching design**, not of any tool's implementation body.

### (b) Version evidence — the disposal

Four independent, converging signals, all confirmed directly rather than inferred:

1. **Naming.** ABC writes "τ-bench" and "tau-Bench" throughout (abstract, intro, Table 3, Table 9 caption) — never "τ²-bench" or "tau2-bench." Table 9's own caption reads "Assessment Report of $\tau$-Bench," matching the original benchmark's own paper title exactly.
2. **Evaluation-design fingerprint.** ABC's Table 3 lists τ-bench's "Evaluation Design" as **"Substring Matching, State Matching"** — the original tau-bench's documented reward mechanism (database-state match plus a substring check on the agent's final response). tau2-bench's own paper (arXiv:2506.07982 §3.3) describes an entirely different mechanism for the domains we audited: "DB check, status assertions, natural language assertions, communication info check, and action matching... In telecom, only assertion functions are used to evaluate task success." No substring/list-matching response check exists in tau2-bench's telecom or airline grading path.
3. **Collection provenance.** ABC's Table 2 (page 17) sources its "Tau-bench" entry to **"Anthropic | Claude 3.7 Sonnet and Claude Code"** — an industry announcement from February 2025. ABC's own stated collection window (Appendix A, page 16) is **"between January 2024 and March 2025."** tau2-bench's first commit is dated 2025-06-10 and its paper was submitted 2025-06-09 — both **after** ABC's collection window closed. ABC could not have assessed tau2-bench; it did not yet exist during the assessment period.
4. **Repository history, checked directly.** `repos/tau2` (local clone) has a linear commit history starting at `37199f3` "release," dated 2025-06-10, with README self-identifying as "$\tau^2$-Bench: Evaluating Conversational Agents in a Dual-Control Environment" and citing arXiv:2506.07982. `git log -S` on the exact strings implicated in our Finding 2 ("Line must be active to refuel data") and Finding 3 ("Seats release not implemented") each return only that single first commit — these tools have existed unchanged since the repository's inception, over a year before our pinned commit `c3398666` (2026-08-14), and entirely within the period *after* ABC's window.

### Overlap check, stated directly

ABC's finding is a **grading-rubric / ground-truth-data defect** in the original tau-bench's response-matching evaluator (empty ground truth, exploitable substring/list matching). Our Findings 2 and 3 are **tool-implementation defects** in tau2-bench's telecom and airline tool bodies (a commented-out precondition check in `refuel_data`; a missing seat-release effect in `cancel_reservation`), verified by direct source read at `src/tau2/domains/{telecom,airline}/tools.py`. Different benchmark, different codebase, different paper, different layer of the system (grader/ground-truth vs. tool body), different mechanism (string-matching gameability vs. unenforced precondition / incomplete effect). No overlap. Cite ABC in §II as disposal evidence per the existing `REFERENCES.md` row 10 entry, updated below to close out its open action item.

---

## Task 2 — Linking findings to consumed scores

### MedAgentBench (commit `9926011`)

**Version/date range.** The repository's `src/server/tasks/medagentbench/__init__.py` — the file containing Finding 1 (POST branch discards the payload) — has been touched by **exactly one commit in its entire history**: `8983d6e`, 2025-01-22, "src for v1." It has never been modified since. The pinned commit `9926011` (2025-11-21, "Update paper link," confirmed by direct read not to touch this file) inherits that same code unchanged. The benchmark has two published descriptions of this exact code state:

- **arXiv:2501.14654**, "MedAgentBench: A Realistic Virtual EHR Environment to Benchmark Medical LLM Agents," Jiang, Black, Geng, Park, Zou, Ng, Chen (Stanford), v1 submitted 2025-01-24 (repo code committed two days earlier, 2025-01-22 — consistent with a code-then-preprint release pattern), v2 2025-02-12.
- **NEJM AI**, Vol. 2, Issue 9, published 2025-08-14, DOI `10.1056/AIdbp2500144` — the peer-reviewed venue publication of the same paper. (Full text is paywalled; the arXiv preprint, read directly below, is the version-controlled twin. Journal issue/date confirmed via search; the peer-reviewed table could not be directly compared to the arXiv table due to the paywall — treat as the same reported numbers under the paper's own claim of correspondence, not independently re-verified here.)

**Published number.** The arXiv PDF was read directly (pages 1–8). **Table 3, "Success rate (SR) of state-of-the-art LLMs on MedAgentBench"** (page 7), reports three columns per model: Overall SR, Query SR, and **Action SR**. Section 2.5.1 defines the split precisely:

> "Among the 300 tasks in MedAgentBench, half (150) only require information retrieval via GET requests, while the other half require the modification of medical records through POST requests (often in combination with GET requests beforehand). We calculate task success rates for these two subgroups and name them as query SR and action SR respectively."

**Action SR is exactly the write-task success rate Task 2 asks about**, and Table 3 reports it for all 12 evaluated models (corrected 2026-08-28: an earlier version of this line said 11, while the table below has always listed 12 — caught by experiments/numbers_audit.py, not by re-reading):

| Model | Action SR |
|---|---|
| Claude 3.5 Sonnet v2 | 54.00% |
| GPT-4o | 56.00% |
| DeepSeek-V3 | 54.67% |
| Gemini-1.5 Pro | **71.33%** (best in column) |
| GPT-4o-mini | 53.33% |
| o3-mini | 48.67% |
| Qwen2.5 | 64.00% |
| Llama 3.3 | 42.67% |
| Gemini 2.0 Flash | 42.67% |
| Gemma2 | 0.00% |
| Gemini 2.0 Pro | 10.67% |
| Mistral v0.3 | 0.00% |

**The specific numbers Finding 4 affects.** Section 2.4.1 of the paper itself states the grading method:

> "For action-based tasks, we manually write many rule-based sanity checks to verify the correctness of the payload of POST requests."

This is precisely the mechanism `FINDINGS-VERIFIED.md` Finding 4 traces in `refsol.py`: `extract_posts` reconstructs the POST payload from the **agent's transcript text**, gated on the literal string `"POST request accepted"` — the fabricated success message that is itself Finding 1 — and never issues a FHIR read. **Table 3's Action SR column, for every one of the 11 rows above, is computed by this transcript-reconstruction path, not by reading FHIR server state.** The paper's own overall SR figure (headlined in the abstract as "69.67%" for Claude 3.5 Sonnet v2) is a weighted blend of Query SR and this same Action SR, so it inherits the same construct-validity problem for its write-task half.

Stated at the precision the task requires: **Table 3's Action SR column reports write-task success under the exact commit where the write path is a no-op (Finding 1) and the only grader for that path reads the agent's own transcript text rather than server state (Finding 4).**

### tau2-bench (commit `c3398666`)

**Version/date range.** The repository's first commit is `37199f3`, 2025-06-10 ("release"), one day after the τ²-bench paper (arXiv:2506.07982, Barres, Dong, Ray, Si, Narasimhan) was submitted (2025-06-09, v1, no later version). `git log -S` confirms the two tool bodies underlying our findings — `refuel_data` (telecom) and `cancel_reservation`'s missing seat release (airline) — have been present, unchanged, since that first commit. The pinned commit `c3398666` (2026-08-14) is over 14 months later, in the same continuous line of development; at that commit the README still self-identifies primarily as "τ-Bench" citing arXiv:2506.07982, and links a live leaderboard badge (`taubench.com`). By the current date (2026-08-22) the same repository has continued past this point into a "τ³-bench" branding with Voice/Knowledge extensions (confirmed by reading the current `origin/main` README, commit `a2c0247`, 2026-08-18) — the pinned commit sits inside the τ²-bench era, shortly before that further evolution.

**Published numbers produced under it.**

1. **The paper's own results (arXiv:2506.07982, §4.2, Figure 3, page 8).** Per-model pass^1 scores by domain, for four evaluated LLMs, under the exact code state that (per the git history above) contains both audited defects:

   | Model | Retail pass^1 | Airline pass^1 | Telecom pass^1 |
   |---|---|---|---|
   | gpt-4.1 | 74% | 56% | 34% |
   | o4-mini | 71% | 59% | 42% |
   | gpt-4.1-mini | 66% | 51% | 44% |
   | claude-3.7-sonnet | 79% | 69% | 49% |

   Quoted directly from the text: "gpt-4.1 pass^1 drops from 74%/56% for retail and airline respectively to 34% for telecom."

2. **A live, currently-consumed leaderboard.** The pinned commit's own README links `taubench.com` as "🏆 Live Leaderboard." Fetched directly: the site currently shows a **"τ²-bench Text (June 2025)"** tab with top current models (Qwen 3.5-397B 87.9%, Gemini 3.0 Pro 85.4%, Claude Opus 4.5 85.3%, pass^1, aggregated) run against this same benchmark codebase — i.e., a number the community consumes on an ongoing basis, not just a static paper table.

Unlike the MedAgentBench case, this task does not require (and this report does not claim) that a specific published number is provably composed of tasks exercising `refuel_data` or the seat-release gap — that causal step is the paper's own score-at-risk analysis (§IV in `PAPER-OUTLINE.md`), not established here. What is established, conservatively: the pinned commit is squarely inside the code lineage that produced both the τ²-bench paper's own domain-level pass^k table and the numbers currently shown on the benchmark's live public leaderboard, and the two defects have been present, unpatched, for the entire span between the paper's release and the pinned commit.

---

## Task 3 — IEEE BigData 2026 Intelligent Data Mining special session CFP

**Verdict: found and read directly.** `https://bigdataieee.org/BigData2026/calls/special-data-mining/` is live and is the "12th Special Session on Intelligent Data Mining," organized by Asst. Prof. Dr. Uraz Yavanoglu, submission deadline **2026-09-27** — matching `CLAUDE.md`'s stated project deadline exactly.

**Topics, verbatim, as listed on the page:**

> Demo Applications in Data Mining; Industrial Challenges in Data Mining; Future Directions and Challenges in Data Mining; Recent Theory, Trends, Technologies and Applications in Data Mining; HPCC and Hadoop; Sustainability; Biometrics; Neuroscience and Bioinformatics; Philosophy; NLP; Mathematics; Sensors, Networks, Devices; Mobile Computing; Algorithms; IoT, Autonomous Systems and Agents; Semantic Computing; Social Media, Social Networking, Social Data; Smart Cities & Energy; Data Classification, Regression, Cleaning; Information Security; Information Retrieval; Knowledge Discovery, Integration, Transformation; Scalable Computing, Cloud Computing; Deep Learning; Medical Imaging; GPU Applications; Homeland Security and Data Analysis; Data Security and Privacy; Graph Mining; Big Data and Services; Model Fine-Tuning Techniques; Large Language Models (LLMs); Data Warehouse, Clustering, Visualization; Data Mining, Data Science and Big Data.

**Does it name benchmark quality, evaluation, data quality, measurement validity, or reproducibility?** No. None of those five terms, or a clear paraphrase of any of them, appears in the topic list. "Data Classification, Regression, Cleaning" is the closest item (data quality-adjacent, but framed as a mining task, not an evaluation-integrity concern), and "IoT, Autonomous Systems and Agents" and "Large Language Models (LLMs)" are the closest bridge points for an agentic-benchmark paper — the paper's contribution is not directly named by this list and will need to be framed as an application of data mining / LLM-agent methodology under one of the general or LLM/agents bullets, not as a natural fit for a named evaluation-quality topic.

**Format requirements (special-session page).** Papers "submitted in PDF format using the standard two-column IEEE conference template." No page limit is restated on this page specifically — it defers to the main-conference format.

**Page limit and back matter (main CFP, `https://bigdataieee.org/BigData2026/calls/papers/`, read directly, cross-checked against `.../calls/submission/`).**

- **10 pages maximum, IEEE two-column format, references included in the 10-page count.**
- **No appendix is allowed.** ("No appendix is allowed" is stated explicitly on the main CFP page.)
- Main-track electronic submission deadline: **2026-08-21** (already past as of today, 2026-08-22 — the special session's **2026-09-27** deadline is the operative one for this project, as `CLAUDE.md` already assumes).
- Notification: 2026-10-24. Camera-ready: 2026-11-14. Conference: 2026-12-14 to 12-17, Phoenix, AZ.
- Formatting otherwise follows "IEEE Computer Society Proceedings Manuscript Formatting Guidelines."

**Back-matter expectations — the specific correction the panel asked about.** Neither the main CFP page nor the submission-instructions page nor the special-session page mentions any requirement for a CRediT author-contributions statement, a funding statement, an ethics statement, a conflict-of-interest declaration, a data-availability statement, or an AI-use disclosure. No author-guidelines or formatting-template page beyond these three was found on the conference site (checked the site's full navigation listing). This is consistent with `PAPER-OUTLINE.md`'s own suspicion: **the 0.75-page back-matter budget in `PAPER-OUTLINE.md`'s page-budget table appears to be inherited from journal/other-venue conventions (CRediT is an Elsevier/Springer-journal taxonomy) that this venue's own CFP does not require.** Recommend reclaiming most or all of that 0.75 pages for body content, keeping only a minimal, standard IEEE acknowledgment/funding line if applicable — but note this is an absence-of-evidence finding from the pages actually published now; IEEE sometimes adds boilerplate declarations at the camera-ready stage via the submission portal rather than the public CFP page, so recheck the CyberChair submission system's own required fields at submission time rather than treating this as final.

---

## Sources consulted for this file (in addition to what is already logged)

See `REFERENCES.md` for the updated entries. New sources this pass: original tau-bench paper (arXiv:2406.12045), τ²-bench paper (arXiv:2506.07982), MedAgentBench paper (arXiv:2501.14654) and its NEJM AI publication (DOI 10.1056/AIdbp2500144), the `taubench.com` live leaderboard, and the IEEE BigData 2026 main and special-session CFP pages.
