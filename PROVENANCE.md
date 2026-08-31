# Repository provenance

The paper makes ordering claims that a reviewer is invited to check against git history. This file states exactly what that history does and does not prove, because the answer is not the flattering one.

## The repository was initialized after most of the work existed

`git init` ran on **2026-08-21**, and commit `fc776b6` imported the entire project as a single tree: the prior-work gate, the findings ledger, the contract spec, the checker, the adapters, the analysis modules, the mutation machinery, and both pre-registration artifacts. Everything before that date was developed without version control.

**A squashed import cannot demonstrate that the pre-registration preceded the analysis.** `detector_analysis_plan.md` §8 promises that "a reviewer can verify the ordering from git history rather than taking our word for it," and for everything inside `fc776b6` that promise is not kept. This was raised by a methodology reviewer, it is correct, and it is recorded here rather than quietly left for someone else to notice.

No history was rewritten to manufacture a better-looking sequence. Backdating commits would be trivial and would make every other ordering claim in the paper worthless.

**One rewrite did occur, and it is disclosed here rather than left to be discovered.** Before the repository was made public, `git filter-repo` removed a single file — the assistant working-instructions file, which carried private information about the author and no part of the method — from every commit, and reworded eight sentences of design rationale in four internal planning documents. Commit contents are otherwise byte-identical, the ordering of every commit is unchanged, and no dated claim moved. Because rewriting renames commits, the hashes cited in the paper are the post-rewrite ones; the pre-rewrite names were `5f088cb` (import), `57b019d` and `5824376` (the two freeze tags), `ec5dbf4` (agent-experiment pre-registration) and `eaf1bdd` (the agreement run). The three pre-registered documents — `experiments/detector_analysis_plan.md`, `experiments/analysis_plan.md` and `experiments/annotation_protocol.md` — were deliberately left untouched by the rewrite, since editing a pre-registration after the fact is precisely what pre-registration exists to prevent.

**Tag objects are not commits, and the paper cites the commits.** `checker-freeze-v1` and `checker-freeze-v2` are annotated tags, so each carries an object hash of its own, distinct from the commit it points at. The hashes cited in the paper and in this file are the commits: `9dacc79` for the first freeze and `54b74d4` for the second, reproducible with `git rev-parse checker-freeze-v1^{commit}`. Drafts before 2026-08-31 cited the tag object hashes (`8f9b2ff`, `b2a39e1`) while labelling them commits. That was wrong -- neither hash names a commit -- and it is corrected rather than quietly reworded, because a provenance claim a reviewer cannot resolve is worse than one that is merely awkward.

## What is still verifiable, and why

The ordering claims that carry methodological weight are about what happens **after** the artifacts were committed, and those remain checkable:

| Claim | Verifiable? | How |
|---|---|---|
| The detector analysis plan was committed before any mutant was **scored** | **Yes** | No mutant corpus, score, or result exists in `fc776b6` or in any commit up to `checker-freeze-v1`. The mutation code was built and exercised on the toy domain only; the build spec for that milestone forbade real-corpus generation |
| The agent-experiment analysis plan was committed before any trajectory was **recorded** | **Yes**, prospectively | No recorded trajectory exists in the repository. The plan lands before the first recording, in its own commit |
| The task-selection rule was fixed before selection | **Yes**, prospectively | Same commit as above |
| The plans were *authored* before the checker was written | **No** | Squashed. The paper must not claim this |

The distinction matters. Pre-registration protects against choosing an analysis after seeing the data. The data here are mutant scores and verdict flips, and **none of them exist yet**. The window that would have been closed by a late plan is still open; the window that a squashed import closed is the weaker claim about authoring order, and the paper drops it.

## `checker-freeze-v1` — tagged 2026-08-26 at `9dacc79`

The freeze happened, before any mutant was generated or scored. The precondition was verified rather than asserted: no mutant corpus, no mutant score and no scoring result exists at or before that commit. `mutation/` held operators, site enumeration, scoring and equivalence code exercised only against the toy reference domain, which is what the build spec permitted in that milestone.

Frozen state: 282 tests passing; 42 contracts passing all 8 validator checks with zero skips (19 tau2, 12 AgentDojo and MM-ToolSandbox, 11 toy); `report/findings.jsonl` at 207 rows across four benchmarks with 11 VIOLATES; 4 headline-eligible cells.

This is the commit §VII cites. It is what makes the ordering claim checkable: a reviewer can confirm from the tag alone that the analysis plan predates the data, which is the only pre-registration claim that matters and the one a squashed import could not support.

## Rules from this point

1. **No squashing.** Every subsequent change lands as its own commit.
2. **`checker-freeze-v1` is tagged when the checker is frozen**, before the first real mutant is generated. The tag is cited in §VII.
3. **`experiments/analysis_plan.md` lands in its own commit** before any trajectory is recorded, and that hash is cited in §VIII.
4. **Scoring and recording commits come after their plan commits, always**, and the paper cites hashes rather than asserting sequence.
5. If the checker changes after the freeze tag, the refreeze rule in `detector_analysis_plan.md` §8 applies and the number of refreeze cycles is reported.

## What the paper says about this

One sentence in the artifact/reproducibility section, not buried: the repository was initialized partway through the work, so authoring order is not reconstructible from history; the pre-registration claims the paper makes are about scoring and recording order, which are.

A reviewer who checks will find this file before they find the gap.
