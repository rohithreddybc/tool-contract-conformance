# `refsol.py` provenance

This directory holds a pinned copy of MedAgentBench's grading solution file, together with its
SHA-256. It is third-party code, and this note records where it came from and under what terms,
which the previous state of this directory did not.

## Where it comes from

- Project: MedAgentBench, <https://github.com/stanfordmlgroup/MedAgentBench>
- Upstream licence: MIT, per the repository's own licence file.
- The file is **not** in that repository. `README.md:45` directs users to download it from a
  Stanford Medicine Box share and place it at `src/server/tasks/medagentbench/refsol.py`.
- Copy held here: `refsol.py`, 15,541 bytes, SHA-256 in `refsol.py.sha256`.

## Why a copy is pinned here

`src/server/tasks/medagentbench/__init__.py` imports it dynamically and exits if it is absent,
and `eval.py` dispatches `getattr(refsol, task_id)` per case, so the grading behaviour this audit
describes cannot be reproduced without it. The Box share is unhashed and unversioned, so
reproducibility for this one file cannot rest on upstream git history.

## The open question, stated plainly

The maintainers chose to distribute this file through a request link rather than in the
repository. That is a plausible contamination control, since it is the file that decides whether
a task passed. Republishing it in a public repository and a Zenodo deposit defeats that control
permanently, regardless of the MIT licence permitting redistribution.

Licensing is not the obstacle; the upstream project is MIT and MIT allows redistribution with the
copyright and permission notice carried along. The question is whether redistribution is the
right thing to do when the authors have deliberately gated it.

Three options, none of them taken yet:

1. Remove the copy and ship only the SHA-256 plus the retrieval instruction above. Reproduction
   then needs one manual download, which is what upstream already asks of every user.
2. Keep the copy and obtain written permission from the MedAgentBench authors, recording it here.
3. Keep the copy and argue the case in print, stating the contamination trade-off explicitly.

Option 1 is the default if nobody decides otherwise. A Zenodo deposit is immutable, so removing
the file means publishing a new version rather than deleting anything.

## Attribution

MedAgentBench is by Jiang, Black, Geng, Park, Zou, Ng and Chen, arXiv:2501.14654, published in
NEJM AI vol. 2 iss. 9. Copyright remains with its authors under the MIT licence linked above.

## Status

The copy was removed on 2026-09-12 (option 1 above). What ships is the SHA-256 in
`refsol.py.sha256` and the retrieval instruction: obtain `refsol.py` from the Box link at
`README.md:45` of the MedAgentBench repository and verify it against that hash before use.
Upstream asks the same of every user, so reproduction costs one manual download and the
maintainers keep the gate they chose.
