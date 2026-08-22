"""Mutation validation machinery -- ARCHITECTURE-FINAL.md sec 5, experiments/detector_analysis_plan.md.

    mutation/operators.py    -- the six AST-level defect-class operators
    mutation/sites.py        -- programmatic site enumeration and seeded selection
    mutation/equivalence.py  -- semantics-preserving mutant generators (sec 3 precision controls)
    mutation/probes.py       -- the sec 2 equivalence probe corpus generator (kept separate from
                                 any future checker-driving probe generation -- see its docstring)
    mutation/score.py        -- Wilson-interval precision/recall, survival, escape decomposition

Built and tested against toy/ only in this milestone. No mutant is generated or scored against a
real benchmark tool here -- that happens after `checker-freeze-v1` is tagged, per CLAUDE.md and
detector_analysis_plan.md's own freeze-then-mutate ordering.
"""
