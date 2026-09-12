# Coordinated disclosure log

Stub committed 2026-08-30, ahead of the disclosure date, so that the manuscript's `[N12: report/disclosure_log.md]`
pointer (paper/main.md §VIII, "Coordinated disclosure") resolves to a real artifact path before the numbers audit
runs. This file is completed, not replaced, on and after 2026-09-10: rows are filled in as responses arrive, up to
the 2026-09-27 submission deadline; nothing here is deleted or renumbered afterward.

Reporting rule (fixed now, before any response is known, so the rule cannot be tuned to a result): a response
received by the submission deadline is reported with its substance below. A team that has not responded by the
deadline is recorded as non-responding, with the disclosure date and the fact of non-response stated neutrally --
no inference is drawn from silence, and no response is fabricated or approximated. A finding a maintainer disputes
is marked **contested** in the camera-ready revision of this file, with the maintainer's stated reasoning recorded
alongside it, per §III's benign-simplification principle (either side of a divergence may be the one that gets
repaired).

## Disclosure

All findings below go to the four maintainer teams before the 2026-09-27 submission, each with a per-finding
reproduction command and a proposed repair (`report/findings.jsonl`, `FINDINGS-VERIFIED.md`). Issue text is drafted
in `SUBMISSION-PACKAGE.md`. **Nothing has been filed yet**: as of 2026-09-11 no issue exists on any of the four
repositories, every row below reads pending, and no issue URL is recorded. An earlier version of this file stated
that disclosure had been sent on 2026-09-10. That was not correct and is corrected here. Each row gains its filing
date and issue URL when the issue is actually opened.

| Benchmark | Maintainer team / contact channel | Findings to disclose | Filed (date, issue URL) | Response status | Response substance | Contested? |
|---|---|---|---|---|---|---|
| MedAgentBench | GitHub issue tracker, project maintainers | 1, 4 | not yet filed | pending | -- | -- |
| tau2-bench | GitHub issue tracker, Sierra Research | 2, 3 (`suspend_line` candidate reported separately, unadjudicated) | not yet filed | pending | -- | -- |
| AgentDojo | GitHub issue tracker, project maintainers | 5, 6, 8 | not yet filed | pending | -- | -- |
| MM-ToolSandbox | Issues disabled on `apple-aiml-research/ml-mmtoolsandbox`; pull request or the authors via arXiv 2607.11818 | 7 | not yet filed | pending | -- | -- |

`pending` is a placeholder response status, not a finding of non-response; it is replaced by `responded` or
`non-responding` for each row no earlier than the disclosure date and no later than submission.
