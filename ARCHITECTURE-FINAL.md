# Architecture — FINAL

Supersedes `ARCHITECTURE.md`, which is retained as the v1 draft. This version folds in the Day-1 gate (`GATE.md`), the verified findings (`FINDINGS-VERIFIED.md`), an adversarial methodology review, and an engineering feasibility review that inspected the actual cloned repositories.

Target: IEEE BigData 2026, Intelligent Data Mining special session. Deadline 2026-09-27, 10 pages. Backstop ML on Big Data, 2026-09-30. 37 days from 2026-08-21.

---

## 0. What changed from v1, and why

Six structural changes. Each is forced by evidence, not preference.

| # | Change | Forced by |
|---|---|---|
| 1 | **Headline contribution moves from the checker to defect-to-score dependency analysis.** | ConTract, IcePICK and AGORA+ already own contract-checking machinery. Without this change the paper is an application paper in a framework costume. |
| 2 | **MedAgentBench demoted to a static/qualitative anchor case.** No dynamic harness for it. | Its POST branch has no standalone callable, lives inside an async Session loop coupled to AgentBench's controller/worker HTTP stack; the repo has zero `reset` occurrences; it needs a Docker-hosted HAPI FHIR server; and its grading logic (`refsol.py`) is not in the repository at all. |
| 3 | **tau2-bench is the workhorse**, scoped to airline + retail + telecom = 19 mutating tools. | These are plain pydantic DBs with `load()`, `model_dump()`, `get_hash()` — snapshot and reset are near-free. Two of the three known findings live here. |
| 4 | **Mutation validation gains an open-world arm.** | Self-authored mutants against self-authored contracts make P/R near-tautological. Recall 0.8 in a closed world licenses nothing. |
| 5 | **Tier 1 becomes trajectory replay with no model in the evidence path.** | "Temperature 0 is deterministic" is false on real APIs, and selecting tasks from observed traces rebuilds the post-hoc-rule defect this design rules out. |
| 6 | **Gate 1 splits into 1a/1b and lands Aug 29-30, not Aug 27.** | Adapter work and contract-authoring labor were double-booked into the same three days. |

---

## 1. Contribution, restated

Lead with the target and the consequence. Never with the machinery.

**Primary contribution — score-at-risk analysis.** Given a benchmark, trace: defective tool → state fields it should have written → state fields the evaluator reads → tasks whose verdict depends on those fields. Output is a per-benchmark bound: *these N tasks have verdicts that depend on state a defective tool was responsible for producing.* No prior work has this, because in ConTract, IcePICK and AGORA+ the system under test is production software, not a measurement instrument. This is the framework contribution and it must be section 3 of the paper, not a script in an appendix.

**Supporting contributions.**
2. Six executable defect classes over the interface → implementation → state-transition contract, defined as checker rules rather than prose. Phantom Effect, Partial Effect and Reset Leak have no counterpart in any surveyed taxonomy.
3. A provenance-bound contract format for mutating tool interfaces.
4. Open-world-validated detection: precision and recall reported against both taxonomy-shaped and off-taxonomy injected defects.
5. Confirmed findings across N benchmarks, with maintainer responses.
6. Machine-readable conformance report format.

**One-sentence disposal of the nearest name collision**, required in related work: Tool-Veritas lists "implementation-specification mismatch" among LLM-judge failures; it appears once, in related work, and denotes judges scoring final answers rather than verified tool use — an evaluator artifact, not a tool-body defect.

---

## 2. Scope decisions, made now rather than discovered later

**Benchmarks.** Floor of 3, target 4, stretch 5. tau2-bench (dynamic, full), MedAgentBench (static anchor), then AgentDojo and MM-ToolSandbox as dynamic benchmarks 3 and 4. MCP-Atlas dropped — Tool-Veritas covers it and its attribution is messy.

**tau2 domains.** airline, retail, telecom only. 19 mutating tools. banking_knowledge and mock are stretch: banking_knowledge needs `uv sync --extra knowledge`, and its default `alltools` retrieval config wants an OpenAI key plus live embedding computation cached at `data/.embeddings_cache` — a non-reproducible network side channel. If it is ever included, pin `no_knowledge` or `bm25`.

**Counting rule for mutating tools.** Use `mutates_state=True`, not the `ToolType.WRITE` tag. `environment/toolkit.py:64-90` documents `mutates_state` as authoritative and notes WRITE tools that signal an action without touching the database. The tag-only count misses two tools in banking_knowledge. State this rule in the paper — it is a small methodological point that signals we read the harness rather than grepping it.

**Realistic tool counts.** tau2: 19 (3 domains) / 31 (all 5). MedAgentBench: 3 tool definitions but **one** unique code path — all three POST tools route through the same branch. The honest number for MedAgentBench is one mutating behavior, and the paper must say so. The v1 estimate of "25-40 tools" was reachable only by silently including banking_knowledge.

**Adapter process model.** MedAgentBench targets Python 3.9; tau2 requires `>=3.12,<3.14`; the harness runs 3.11.7. Adapters cannot share an interpreter. `dynamic/harness.py` talks to each adapter as a subprocess over JSON on stdio.

**Confirmed in practice 2026-08-21, with three corrections the plan did not anticipate.** The boundary is genuinely required — tau2 will not import under 3.11. It also needs a *third* file per adapter, not two: a harness-side client and a benchmark-side worker cannot be one module when they run under different interpreters, so `adapters/tau2.py` is paired with `adapters/_tau2_worker.py`. Two Windows-specific traps: Python prepends a script's own directory to `sys.path`, so `import tau2` inside `adapters/_tau2_worker.py` resolved to our own `adapters/tau2.py` until that entry was stripped; and tau2's policy loader raises `UnicodeDecodeError` under Windows' cp1252 default, requiring `PYTHONUTF8=1`. Finally, an editable install pointed at a git worktree is fragile — the worktree can vanish with the scratch directory — so the tau2 source is a durable `git archive` copy at `.tau2-src-c3398666/`, leaving `repos/tau2` untouched.

**Telecom has two databases, which the plan missed.** An agent-facing `TelecomDB` and a separate `TelecomUserDB`, bridged by `TelecomEnvironment.sync_tools()`. "Snapshot = full mutable state" therefore means both. The adapter merges user state under a `user_db` key rather than nesting the main DB, so existing contract paths (`pre.lines`, `pre.reservations`) keep working. See §6 — this also changes what trajectory replay must record.

---

## 3. Contract format v2

Same YAML-per-tool shape as v1, with four repairs.

**3.1 Advertised-surface enumeration (replaces the informal provenance rule).** v1 required every clause to cite a docstring, schema or README line. That rule excludes its own flagship finding: MedAgentBench's advertised POST semantics live in a prompt template (`__init__.py:18`) and in a runtime success message shown to the agent (`__init__.py:91`) — neither is a docstring.

`spec/schema.json` therefore enumerates a closed list of advertised surfaces, committed before any contract is authored:

- `docstring` — tool docstring
- `schema` — JSON tool schema / function-calling definition
- `prompt_template` — text in the system or task prompt describing tool behavior
- `tool_return` — a success/failure string the tool returns to the agent
- `readme` — repository documentation
- `external_standard` — a cited external specification the tool claims to implement (e.g. FHIR POST semantics)

Clauses grounded in any of these count as advertised. Clauses grounded in none are `inferred: true` and excluded from headline counts, reported separately.

The load-bearing argument, stated once in the paper: **maintainer intent is irrelevant to the measurement claim.** The agent is conditioned only on what the interface tells it. A docstring that was "aspirational" still corrupts the measurement, because the agent believed it and the evaluator scored the resulting state.

**3.2 Inter-annotator agreement on predicates.** Grounding a clause is objective; *translating* it into a predicate is not. "Releases the reserved seats" — which flights, which cabin? With low kappa plus a post-hoc rule a known failure mode, single-annotator predicate authoring is the first thing a methods reviewer attacks. Dual-annotate a 20% clause sample for predicate-level semantic agreement, with a written adjudication protocol committed before annotation. Report the agreement number whatever it is.

**3.3 The predicate language is a DSL; treat it as one.** The v1 example was not evaluable — `post.flights[f].available_seats == pre.flights[f].available_seats + booked_seats` has `f` and `booked_seats` unbound, and the frame pattern `state.customers.*.payment_methods` is a second, undefined grammar. Repairs:

- explicit binders and bounded comprehension in the whitelist: `all(post.flights[f].available_seats == pre.flights[f].available_seats + n_seats for f in args.reservation.flights)`
- frame-pattern grammar defined in `spec/schema.json`, not by example
- a CI check that every shipped contract parses and evaluates against a synthetic snapshot — run before Gate 1b, not after

Still no parser to defend: restricted Python over `(pre, post, args, result)` on a whitelisted AST. But it is a small language and the paper should say so plainly rather than claim it isn't one.

**3.4 Biconditional success is per-contract, not default.** tau2 airline `tools.py:689` — "Do not make flight database update here, assume it takes time to be updated" — is a maintainer *advertising* deferred effect. A default biconditional misclassifies it as Phantom or Partial. Idempotent no-op successes and batch partial-success returns are further legitimate counterexamples. So: `biconditional: true` requires a provenance-cited justification, and an `advertised_deferred` effect annotation exists for the deferred case.

Turn this into a selling point. Show that the checker correctly does *not* flag the flight-change path, while still flagging `cancel_reservation`, whose docstring advertises immediate release. A detector that knows when not to fire is more credible than one that fires everywhere.

**3.5 Verdict lattice.** Unchanged: CONFORMS / VIOLATES (with minimal witness) / UNTESTABLE (with reason code). UNTESTABLE stays in all denominators.

---

## 4. Score-at-risk analysis (`analysis/score_at_risk.py`)

Promoted from v1's `experiments/affected_tasks.py`. This is the paper's spine.

Three steps, all static, no model involved:

1. **Defect → field.** From the contract's violated effect clauses, the set of state fields the tool should have written but did not (or wrote partially).
2. **Field → evaluator.** Parse the benchmark's own evaluation code for the state fields it reads. In tau2 this is the DB hash and the per-task assertions; in MedAgentBench it is whatever `refsol.py` queries.
3. **Evaluator → tasks.** Enumerate tasks whose verdict depends on any field in the intersection.

Output per benchmark: number of tasks at risk, out of total; broken down by defect class; each row traceable to a tool, a clause, and an evaluator read site.

This is a *bound*, not a claim that every such task is misgraded. Say so explicitly. The bound is the contribution; the agent experiment (§6) then demonstrates that the bound is not vacuous on a sample.

### What the real graders turned out to be — implemented 2026-08-21, three corrections

**tau2's evaluator is two mechanisms with incompatible granularity, and one of them makes the bound nearly vacuous.** `get_db_hash()` (`toolkit.py:242-244`) hashes the *entire* domain database, so every field any defective tool writes is trivially "read by the evaluator" — under that basis, all 50 airline `cancel_reservation` tasks are at risk, which is true and almost uninformative. `env_assertions` instead call one named, statically parseable function per task and give real per-field granularity. Empirically the two do not blend: airline is DB-hash exclusively, telecom is assertion exclusively. Every row is therefore tagged `whole_state_hash` / `collection_only` / `exact_field`, and **no headline number may be quoted without its basis tag.** A whole-state-hash "100% at risk" is a statement about the evaluator's coarseness, not about the defect's reach.

**For MedAgentBench a naive field intersection fails in the opposite direction from the one W2 predicted.** W2 anticipated it returning zero. It would in fact return roughly 100%, because the grader reconstructs the write's claimed content from the transcript and therefore "reads" every field the tool was supposed to write. Both numbers are wrong; the oracle-grounding gate is the fix, not any field count. Classification keys on `extract_posts()` — an earlier version that also keyed on `check_has_post()` wrongly implicated five pure read tasks, and is regression-tested against.

**Predicate paths bound through comprehensions were invisible to the first path walker** (`for l2 in post.lines: l2.data_refueling_gb`), which would have silently dropped `refuel_data`'s actual written fields — the telecom finding's entire field set. `extract_state_paths` now threads comprehension bindings explicitly.

**The experiment frame does not nest inside the at-risk population.** See `REVIEW-RESPONSE.md` W6 — argument-specific defects make the two frames overlap rather than contain, and the code reports the relation rather than assuming it.

**Task selection rule for §6 is defined here and only here**, statically: a task is affected iff its reference solution invokes a tool with a confirmed VIOLATES clause. Enumerated exhaustively, no exclusions, committed before any run. Selecting on observed traces is forbidden — that is the post-hoc rule that sank a prior paper.

---

## 5. Mutation validation v2

**Closed-world arm (as v1).** Six AST operators, one per defect class, applied at programmatically enumerated sites in conformant tools. The three known-defective tools are excluded from the corpus. `checker-freeze-v1` tag applied before mutant generation; the freeze tag and generation script ship in the artifact so ordering is auditable from git history.

**Corpus reality check.** MedAgentBench contributes essentially nothing: one no-op branch with no guards, no argument-conditioned branching, no paired writes, no reset routine. Five of six operators have no site there. The corpus is drawn from tau2's mutating tools plus the toy domain. Delete v1's claim that "recall reported per benchmark demonstrates transfer" — there is nothing to transfer to. Report cross-*domain* transfer within tau2 instead, which is real.

**Open-world arm (new, and the answer to the circularity objection).** Run **cosmic-ray 8.7.0** over the same tools. Tool choice settled empirically on 2026-08-21, not by preference: mutmut 3.7.0 refuses to run on Windows outright — "To run mutmut on Windows, please use the WSL" — and WSL is not installed on the dev machine. cosmic-ray runs natively; a 40-job smoke run on a synthetic tool gave 32 killed / 8 survived. Two operational notes that cost an hour to find and will cost a day if rediscovered in September: the `test-command` must use **absolute** paths, because workers execute in a cloned temp directory where a relative `.venv/Scripts/python.exe` does not resolve and every job silently returns `INCOMPETENT`; and the environment is built with `uv venv`, because `python -m venv` cannot bootstrap pip on this machine. These operators know nothing about our taxonomy. Report the checker's **escape rate**: of surviving non-equivalent mutants, what fraction does the conformance checker miss? This is the only honest measure of whether our six classes cover the defect space, and it is the direct answer to "you validated your detector on defects you designed it to find."

**Contract-coverage metric (new), generated by `spec/coverage.py`.** Per tool, report the fraction of advertised-surface sentences operationalized into clauses, and the fraction of state-writing statements covered by some effect or frame clause. Low coverage with high recall is a shallow-contract warning, and reporting it pre-empts the reviewer who would otherwise infer it.

**Held-out contracts (new, cheap).** Have one independent person author contracts for ~10 held-out tools; show recall transfers. Half a day of someone else's time buys a genuine external-validity claim.

**Statistics.** Mutants within a tool share a contract and a code style — they are not independent trials. Report per-tool breakdowns and tool-clustered intervals, and state every recall claim at the Wilson lower bound, never the point estimate. 20/25 detected is Wilson [0.61, 0.91]; "recall ≥ 0.8" is compatible with true recall 0.62. Say the interval.

**Equivalent-mutant controls.** Replace half of v1's log-string and variable-name controls — those are undetectable by construction and prove nothing — with semantics-preserving refactorings of *advertised* behavior: reorder independent writes, extract a guard into a helper, equivalent arithmetic. The real false-positive threats are snapshot canonicalization (timestamps, autogenerated IDs, dict ordering) and environment nondeterminism; document the canonicalization rules in the paper.

**Wild precision.** The Sep 7-8 manual triage produces a reported number: confirmed VIOLATES / all VIOLATES on real benchmarks. That is precision in the wild, and it matters more than precision on mutants.

---

## 6. Agent-impact experiment v2

**Tier 1 — trajectory replay. Primary. No model in the evidence path.**

Record one agent trajectory per affected task. Re-execute the identical action sequence against as-shipped tools and against patched tools. Show the benchmark's own evaluator scoring the two resulting worlds differently, with pre/post state diffs. This is deterministic in the strict sense: the same action sequence, two tool implementations, two verdicts.

Where a patch changes mid-trajectory observations so replay diverges, fall back to temp-0 with k=3 per condition, count only flips stable across all three replicates, and verify trajectory-prefix identity up to the divergence point. Report how many tasks needed the fallback.

**Replay must record every environment-mutating actor, not only the agent.** Established empirically 2026-08-21, not assumed: airline and retail register no user tools, but telecom's user simulator holds 15 WRITE tools against a separate `TelecomUserDB`, and `make_payment` bridges into the agent-facing database through `sync_tools()`, which runs after every call by either party — a bill flips Awaiting Payment → Paid via a user-only call. Replaying the agent's action sequence alone would under-specify the world on the one in-scope domain where Finding 2 lives. Telecom trajectories record user-tool calls. See `adapters/NOTES.md`.

**Tier 2 — descriptive only.** Per-task paired success-proportion deltas with exact binomial CIs. One plot. Labeled as effect-magnitude illustration. **No p-values.** McNemar on ~15 tasks yields 3-6 discordant pairs; the test is powerless, and an underpowered NHST is a magnet, not a shield. If any test survives review, a permutation test on task-level deltas, appendix only.

**The patch problem, stated honestly.** tau2's two findings have genuine one-hunk patches: uncomment `telecom/tools.py:629-630`; add the seat release at `airline/tools.py:366`. MedAgentBench does not — `send_post_request` does not exist anywhere in the repo, so "restoring advertised semantics" means authoring the FHIR write path from scratch. Two consequences: the flagship A/B runs on tau2, and if a MedAgentBench patch is built at all it is labeled a *reference implementation of the advertised write path*, N lines, diffed in the appendix, with the caveat that we defined the counterfactual.

**Defensibility rules.** No cross-benchmark pooling. No model comparisons. No significance language anywhere in the abstract. The causal claim rests on Tier 1 mechanism; statistics only characterize variability.

---

## 7. Schedule v2

| Dates | Work | Gate |
|---|---|---|
| Aug 21 | **Resolve the MedAgentBench grading question** (§11). Verify the dev machine's Python toolchain actually works — two interpreters, Windows. | Blocking |
| Aug 22-23 | `spec/schema.json` incl. advertised-surface enumeration, frame grammar, binder syntax. `core/` model, verdict lattice, contract validator CI. Annotation protocol committed. | Schema frozen |
| Aug 24-25 | tau2 adapter (airline first, then retail/telecom). Subprocess adapter boundary in `core/`. | **GATE 1a Aug 25: one invoke/snapshot/reset cycle passes** |
| Aug 26-29 | Contracts for 19 tau2 mutating tools, dual-annotated 20% sample. MedAgentBench static contract for the POST path. | |
| Aug 29-30 | End-to-end run | **GATE 1b: framework rediscovers both tau2 findings from contracts alone, and the static checker flags the MedAgentBench POST path** |
| Aug 31-Sep 1 | Static checker; toy reference domain (10 tools) | |
| Sep 2-3 | Mutation: operators, site enumeration, `checker-freeze-v1`, closed-world corpus, scoring | |
| Sep 4 | Open-world arm (mutmut escape rate) + contract-coverage metric | **GATE 2: recall interval and escape rate both reportable, whatever they say** |
| Sep 5 | **Commit `analysis_plan.md` and the static task-selection rule.** Before findings freeze, not after. | Pre-registration real |
| Sep 6-8 | `score_at_risk.py`; benchmark 3 (AgentDojo), 1-day timeboxed spike with go/no-go checklist | **KILL GATE Sep 6** (see `CLAUDE.md`) |
| Sep 9-10 | Findings triage: manually confirm every VIOLATES with a minimal repro; reason-code every UNTESTABLE | **GATE 3: findings.jsonl frozen** |
| Sep 10 | **Coordinated disclosure to all maintainers.** Checker frozen for good. | |
| Sep 11-13 | Tier 1 trajectory replay; Tier 2 if time. Benchmark 4 only if benchmark 3 landed clean. | |
| Sep 14-17 | Paper: intro, related work with layer figure, score-at-risk section, spec, taxonomy | |
| Sep 18-20 | Results via `render.py`; mutation tables; A/B section | **GATE 4 Sep 20: full draft** |
| Sep 21-22 | Artifact: Zenodo, `run_all.sh` offline test on a clean machine, pinned submodules, lockfiles | |
| Sep 23 | Numbers audit: every paper number regenerated from the deposited artifact alone, diffed against the draft | |
| Sep 24-26 | Revision, simulated review pass, fold in maintainer responses ("no response by Sep 26" is itself reportable) | |
| Sep 27 | **Submit** | Backstop Sep 30 |

Gate 1 moved from Aug 27 to Aug 29-30 and split. v1 double-booked two adapters *and* contracts for 25-40 tools into three days; at 30-45 minutes of careful docstring-reading and predicate-writing per tool, 19 tools alone is 10-14 hours on top of standing up an unfamiliar environment.

---

## 8. Cut order

Drop top-first:

1. Benchmark 5 (never planned as load-bearing).
2. Tier 2 of the agent experiment entirely.
3. Benchmark 4.
4. Static checker demoted from detector to candidate-flagging aid; dynamic-only headline, static becomes one paragraph.
5. Held-out-contract external-validity arm.
6. **Floor:** tau2 dynamic + MedAgentBench static + one more dynamic benchmark, full mutation validation with both arms, score-at-risk, Tier 1. Below this, slip to the Sep 30 backstop.

**Never cut:** the open-world mutation arm, the advertised-surface rule, score-at-risk, the reproducibility artifact, disclosure.

Change from v1: MedAgentBench is not in the "3 benchmarks" floor as a dynamic environment. It is a static case study from the start, which is what it can actually support.

---

## 9. Risks

1. **The MedAgentBench grading question comes back wrong** (§11). If `refsol.py` grades write tasks purely on answer strings, patching changes nothing and Finding 1 has no score-at-risk consequence — it becomes a taxonomy example rather than an impact case. *Mitigation:* resolve on day one; the paper's spine is tau2 either way, and MedAgentBench's role is already reduced to a static anchor.
2. **Open-world escape rate is embarrassing** — mutmut finds classes of defect our six miss. *Mitigation:* this is a result, not a failure, provided it is reported. A taxonomy with a measured escape rate is more credible than one asserted complete. Budget one honest paragraph and, if a seventh class is obvious from the escapes, name it as future work rather than retrofitting the taxonomy after freeze.
3. **Benchmark 3 adapter blowup.** *Mitigation:* 1-day spike, go/no-go checklist (fresh_env? snapshot? deterministic replay? reset path?), ranked substitutes AgentDojo → MM-ToolSandbox → AgentBench FC → AppWorld. Failed candidates become UNTESTABLE rows — reportable, not wasted. The paper's benchmark count is filled in last.

Watched, not top three: maintainers disputing semantics. The advertised-surface rule plus verbatim quotation makes disputes reportable data, and Sep 10 disclosure leaves 16 days to fold responses in.

---

## 10. Model-effort allocation

| Tier | Work |
|---|---|
| **High-capability, low volume** | Contract schema design; positioning and related work; anti-circularity protocol; pre-registered analysis plan; review of every VIOLATES before freeze; intro and method prose |
| **Mid-tier, bulk** | Adapter implementation; drafting contract clauses from advertised surfaces (every clause reviewed before headline inclusion); static-check rules; mutation site enumeration; LaTeX plumbing; results prose from generated tables |
| **Cheapest-that-works** | The agent-under-test in Tier 2 (a fixture, not an intelligence spend — one cheap model, seeds pinned); batch classification and formatting; disclosure email drafts |
| **Zero LLM** | The entire measurement path: checker, harness, probes, score-at-risk analysis, mutation scoring, `render.py`. Tier 1 trajectory replay also sits here — replay executes a recorded action sequence, no inference. |

Rule: no LLM inference appears anywhere in the evidence chain for any paper number. That is simultaneously the efficiency answer, the reproducibility answer, and a positioning point against the judge-variance failures Tool-Veritas documents in others.

---

## 11. Open questions that block work

1. **How does MedAgentBench grade write tasks today?** `eval.py:8-16` calls `grader_func(case_data, results, fhir_api_base)` — the grader receives the FHIR base URL, so it *can* query post-state. If it does, every write task fails today and the published success rates are already impossible to achieve on write tasks. If it grades answer strings only, patching changes nothing. `refsol.py` is not in the repository — the README directs you to download it from a Stanford Box link, unhashed and unversioned. **This must be downloaded and read before the paper commits to any MedAgentBench impact claim**, and if it enters the artifact it needs a documented SHA256 with an explicit note that reproducibility for this one file rests on a manual snapshot rather than git history.
2. ~~**tau2 database reset scope between tasks.**~~ **Resolved 2026-08-21.** tau2 builds a fresh environment per simulation (`batch.py:409` → `build.py:393` → `FlightDB.load`), so seat drift cannot cross tasks. Finding 3 is Partial Effect only; the Reset Leak label is withdrawn, and Reset Leak now has no field-observed instance.
3. **Anchor honesty.** Reset Leak and Ignored Argument currently have no field-observed instance — they exist only as mutants. The taxonomy table must label each class field-observed or mutation-only. A reviewer will count anchors; better that we do it first.
