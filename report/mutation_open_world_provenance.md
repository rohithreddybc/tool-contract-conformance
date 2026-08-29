# Open-world (cosmic-ray) arm — provenance

## Completion status

- **toy**: complete. cosmic-ray enumerated 379 work items against `toy/bank.py`'s 11 mutating
  tools; 368 completed (the remainder timed out or were reported INCOMPETENT by cosmic-ray's own
  bookkeeping — see `session.sqlite`), all scored with full sec 4.3 escape classification.
- **tau2 telecom**: **partial, stopped on a wall-clock time budget, not a data-dependent
  criterion.** cosmic-ray enumerated 465 work items against the 5 in-scope telecom tools; **281
  completed** (60%) before the run was stopped to keep the overall experiment within a practical
  time budget — each work item here spawns a brand-new `.venv-tau2` interpreter (litellm import
  alone costs several seconds), and 465 of them serialized, one at a time (the `local` distributor
  has no concurrency), does not fit the time available. The stopping point (281/465) was fixed by
  elapsed wall-clock time alone, decided before looking at which mutations had already scored
  live/detected/escaped — it was not chosen because the numbers looked any particular way. The
  plan does not commit to a specific open-world sample size the way it commits to ~25 mutants per
  closed-world class, so reporting the actual N achieved, with the stopping reason stated, is
  consistent with the "no substitution, report the actual number" discipline used elsewhere in
  this experiment. `n_mutations_scored` in `mutation_scores.json` carries the exact count (281,
  not 465) into every downstream computation and every denominator.

Generation scripts ship in the artifact at `experiments/open_world_cosmic_ray/{toy,tau2_telecom}/`
(`scoring_lib.py`, `precompute.py`, `test_command.py`, `cr.toml`) — copies of what actually ran,
so the ordering and mechanism are auditable from git history rather than taken on trust
(detector_analysis_plan.md sec 3/sec 8).

## Why the target files are copies, never `repos/` or `.tau2-src-c3398666` directly

cosmic-ray's `local` distributor (`cosmic_ray/mutating.py`, confirmed by reading the installed
8.7.0 source, not assumed) mutates `module-path` **in place on disk**, runs the test command, then
restores the original bytes via a context manager. Even though it restores the file afterward,
this means cosmic-ray *writes* to whatever path `module-path` names for the duration of every
single mutation. Pointing it at anything under `repos/` or `.tau2-src-c3398666/` (both git-ignored
benchmark checkouts this project treats as read-only, matching CLAUDE.md's "nothing under repos/
modified") would violate that even if every restore succeeded, and a crash mid-run could leave a
real, tracked-elsewhere checkout genuinely corrupted. So:

- **toy**: `toy/bank.py` is copied verbatim to `experiments/open_world_cosmic_ray/toy/bank.py`
  before `cosmic-ray init`; cosmic-ray's `module-path` points at that copy, never at the real
  `toy/bank.py` the rest of this project imports.
- **tau2 telecom**: `repos/tau2/src` (5.3 MB, no `data/`) is copied verbatim to a scratch
  `<work>/tau2_cr/src` directory; cosmic-ray's `module-path` points at
  `<work>/tau2_cr/src/tau2/domains/telecom/tools.py`. The copy's `tau2` package is made importable
  under `.venv-tau2`'s interpreter by prepending `<work>/tau2_cr/src` to `PYTHONPATH` (verified
  empirically: `tau2.__file__` resolves to the copy, not the editable-installed
  `.tau2-src-c3398666` checkout, once that variable is set) — this SHADOWS the real install for
  the duration of the run without reinstalling anything. `TAU2_DATA_DIR` is set to
  `.tau2-src-c3398666/data` (750 MB, read-only, never copied) so the copy's code still finds real
  fixture data.

## What "behaviorally live" means here, and how it was scored

Per sec 4.1, exactly as `mutation/score.py`'s `is_behaviorally_live` defines it for the toy class-
loading path, generalized to a live process instead of two Python classes: `precompute.py` runs
once, before cosmic-ray touches anything, against the pristine copy, and caches (a) the sec-2
equivalence probe corpus for every in-scope tool (`mutation/probes.py`, unmodified — recorded
calls empty, see the main report for why) and (b) each probe's canonicalized (post-state, result)
pair. `test_command.py` runs once per cosmic-ray mutation (a brand-new OS process every time,
per `cosmic_ray.testing.run_tests`), re-runs every cached probe against whatever the target file
currently contains, and diffs against the cached original — a live mutant is one that differs on
at least one probe, on at least one in-scope tool.

Checker detection ("VIOLATES fired") reuses `dynamic.harness.run_contract` verbatim, against an
in-process `Adapter` shim (`InlineToyAdapter` / `InlineTau2Adapter` in `scoring_lib.py`) built
around whatever the target file currently contains — the SAME checker code path the closed-world
arm and `dynamic/harness.py`'s own `run_all()` use, never a reimplementation.

Escape classification (sec 4.3) reuses `mutation.score.classify_escape` verbatim, given a witness
(the first probe that revealed liveness) captured at scoring time.

## In-scope tools

- **toy**: all 11 mutating tools (`toy.bank.MUTATING_TOOLS`) — no anchor exclusions apply (no toy
  tool carries a confirmed finding).
- **tau2 telecom**: every contracted, non-anchor telecom tool — `disable_roaming`,
  `enable_roaming`, `resume_line`, `send_payment_request`, `suspend_line`. `refuel_data` is
  excluded (FINDINGS-VERIFIED.md Finding 2, the confirmed anchor). Applying the same anchor
  exclusion used for the closed-world arm to the open-world arm is a judgment call the plan does
  not make explicit for this arm; recorded here rather than silently assumed.

## Known operational gotchas hit and fixed while building this

- **Stale `.pyc` for the toy copy.** A manual (non-cosmic-ray) test run showed a mutation as
  "not live" even though the mutated line was confirmed present on disk, because `import bank`
  served a cached-compiled pre-mutation bytecode file (two successive writes landed inside one
  mtime tick). Fixed by loading `bank.py` via `importlib.util.spec_from_file_location` with a
  unique module name every call, bypassing both `sys.modules` and the `__pycache__` bytecode
  cache entirely — see `scoring_lib.py`'s `load_bank_module` docstring. `cosmic_ray.testing.
  run_tests` also sets `PYTHONDONTWRITEBYTECODE=1` for the test-command subprocess it spawns, for
  the identical reason, and that alone was NOT sufficient to catch this during ad hoc manual
  testing that ran the script directly.
- **`pending_work_items` is randomly ordered** (`cosmic_ray/work_db.py`: `.order_by(func.random
  ())`), confirmed by reading the source after an initial attempt to align `cosmic-ray dump`'s
  listing order with a sequential per-invocation counter produced a contradiction (the mutation
  `dump` named at index N did not match the tool the Nth test-command invocation actually saw
  live). This is why escape-classification witnesses are captured DURING scoring (inside
  `test_command.py`, at the moment the mutation is actually in effect) rather than reconstructed
  afterward from the session database — there is no reliable way to map a post-hoc index back to
  a specific historical invocation.
- **A single scoring call hung indefinitely during the closed-world arm's own subprocess-adapter
  use** (zero CPU consumed by the parent process — genuinely blocked I/O, not a spin loop; exact
  root cause not fully diagnosed). `experiments/run_mutation_closed_world.py`'s
  `_detected_with_watchdog` was added in response: a 45s wall-clock budget per mutant, after which
  the wedged adapter's subprocess is force-killed (which unblocks the hung read with an EOF/error)
  and a fresh adapter replaces it for every subsequent mutant. One mutant is lost to a `TIMEOUT`
  reason code; the run does not stall indefinitely on the next one. This same class of hang was
  not observed in the (equally subprocess-heavy) open-world tau2 run, which spawns a brand-new
  process per mutation rather than reusing one long-lived worker across hundreds of calls.

---

## v2 rerun, 2026-08-28: the tau2-telecom arm produces no usable escape rate

Recorded by the session owner. `build_mutation_report.py` emits "See the caveat below" for this case and then prints no caveat — a dangling reference in generated output, and a generator bug worth fixing before the artifact is deposited.

**The result.** 465 mutations scored, 2325 (mutation, tool) pairs, **0 behaviourally live**. Escape rate undefined, denominator zero.

**This is not a statement about the checker.** A mutant counts as behaviourally live only if it produces a canonicalized difference on at least one probe from the frozen equivalence corpus (`detector_analysis_plan.md` §4.1). Zero live means the corpus never drove any mutated tool into a state where its mutation could show — so the arm measures the probe corpus, not the detector.

**Why, specifically.** §2 of the plan defines the corpus as three parts: recorded real calls, signature-derived boundary probes, and precondition satisfy/violate probes. **Part 1 has no artifact** — no recorded-call corpus exists anywhere in this project independent of the checker's own probe generator, and borrowing from `dynamic/probes.py` would violate the §4.3 separation that makes the clause-gap/probe-gap decomposition measurable at all. That leaves parts 2 and 3, whose values are type-generic placeholders. On tau2's entity-keyed tools those fail existence checks (`customer_id="probe_value"` matches no customer) and raise before reaching any write.

**What changed from v1.** v1 reported 33 live and 16 escapes on this arm. That run used a precompute cache built 2026-08-27 01:26, before the v2 checker existed; the cache was archived, not reused, and the v2 precompute produced a corpus that reaches even less of the code. Whether v1's 33 were genuine or artefacts of a stale cache is now unresolvable, which is itself a reason the archived file was kept.

**How the paper must report this.** The open-world arm yields a usable escape rate on the toy domain only. For tau2-telecom the honest statement is that the arm could not be run to a meaningful conclusion, with the reason named. It must not be reported as a low escape rate, and it must not be quietly omitted — a denominator of zero is not evidence of a well-covered taxonomy.

**What would fix it.** A recorded-call corpus captured from real benchmark runs, kept strictly separate from `dynamic/probes.py`. That is the missing §2 item 1 and it is the single highest-value piece of future work for this experiment.
