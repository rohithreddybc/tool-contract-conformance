# Repository provenance

The paper makes ordering claims that a reviewer is invited to check against git history. This file states exactly what that history does and does not prove, because the answer is not the flattering one.

## The repository was initialized after most of the work existed

`git init` ran on **2026-08-21**, and commit `5f088cb` imported the entire project as a single tree: the prior-work gate, the findings ledger, the contract spec, the checker, the adapters, the analysis modules, the mutation machinery, and both pre-registration artifacts. Everything before that date was developed without version control.

**A squashed import cannot demonstrate that the pre-registration preceded the analysis.** `detector_analysis_plan.md` §8 promises that "a reviewer can verify the ordering from git history rather than taking our word for it," and for everything inside `5f088cb` that promise is not kept. This was raised by a methodology reviewer, it is correct, and it is recorded here rather than quietly left for someone else to notice.

No history was rewritten to manufacture a better-looking sequence. Backdating commits would be trivial and would make every other ordering claim in the paper worthless.

## What is still verifiable, and why

The ordering claims that carry methodological weight are about what happens **after** the artifacts were committed, and those remain checkable:

| Claim | Verifiable? | How |
|---|---|---|
| The detector analysis plan was committed before any mutant was **scored** | **Yes** | No mutant corpus, score, or result exists in `5f088cb` or in any commit up to `checker-freeze-v1`. The mutation code was built and exercised on the toy domain only; `CLAUDE.md` forbade real-corpus generation in that milestone |
| The agent-experiment analysis plan was committed before any trajectory was **recorded** | **Yes**, prospectively | No recorded trajectory exists in the repository. The plan lands before the first recording, in its own commit |
| The task-selection rule was fixed before selection | **Yes**, prospectively | Same commit as above |
| The plans were *authored* before the checker was written | **No** | Squashed. The paper must not claim this |

The distinction matters. Pre-registration protects against choosing an analysis after seeing the data. The data here are mutant scores and verdict flips, and **none of them exist yet**. The window that would have been closed by a late plan is still open; the window that a squashed import closed is the weaker claim about authoring order, and the paper drops it.

## Rules from this point

1. **No squashing.** Every subsequent change lands as its own commit.
2. **`checker-freeze-v1` is tagged when the checker is frozen**, before the first real mutant is generated. The tag is cited in §VII.
3. **`experiments/analysis_plan.md` lands in its own commit** before any trajectory is recorded, and that hash is cited in §VIII.
4. **Scoring and recording commits come after their plan commits, always**, and the paper cites hashes rather than asserting sequence.
5. If the checker changes after the freeze tag, the refreeze rule in `detector_analysis_plan.md` §8 applies and the number of refreeze cycles is reported.

## What the paper says about this

One sentence in the artifact/reproducibility section, not buried: the repository was initialized partway through the work, so authoring order is not reconstructible from history; the pre-registration claims the paper makes are about scoring and recording order, which are.

A reviewer who checks will find this file before they find the gap.
