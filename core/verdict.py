"""The verdict lattice. Referenced from spec/PREDICATE-GRAMMAR.md and CLAUDE.md's counting rule.

Three verdicts per clause: CONFORMS, VIOLATES, UNTESTABLE. A tool's overall verdict rolls up
from its clause verdicts. UNTESTABLE must never be silently dropped from a denominator -- that
is the whole point of the untestable reason enum in spec/schema.json.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional


class Verdict(str, Enum):
    CONFORMS = "CONFORMS"
    VIOLATES = "VIOLATES"
    UNTESTABLE = "UNTESTABLE"


# The six executable defect classes (GATE.md sec 2, ARCHITECTURE-FINAL.md sec on defect classes).
class DefectClass(str, Enum):
    PHANTOM_EFFECT = "phantom_effect"
    UNENFORCED_PRECONDITION = "unenforced_precondition"
    IGNORED_ARGUMENT = "ignored_argument"
    PARTIAL_EFFECT = "partial_effect"
    INVARIANT_BREAK = "invariant_break"
    RESET_LEAK = "reset_leak"


# Mirrors spec/schema.json $defs.untestable.reason enum. Kept as a plain set (not the schema
# itself) so core/ has no schema-parsing dependency; spec/validate.py cross-checks against the
# schema directly.
UNTESTABLE_REASONS = frozenset(
    {
        "no_reset_path",
        "nondeterministic_env",
        "unreachable_precondition_state",
        "requires_network",
        "no_observable_state",
        "adapter_unsupported",
        # Not in spec/schema.json's $defs.untestable.reason enum: that enum is for clauses an
        # adapter author statically declares untestable in a contract's `untestable:` block
        # (schema.json, a document this project may not edit -- see CLAUDE.md). This reason is
        # produced at RUNTIME by adapters/contract_check.py when core/predicates.py's
        # PredicateTypeError fires: a snapshot path resolved but a comparison/arithmetic op hit a
        # value of the wrong type (e.g. `post.balance > pre.balance` where balance is null).
        # Kept distinct from "no_observable_state" so the two causes are never silently merged --
        # see core/predicates.py's PredicateTypeError docstring.
        "predicate_type_error",
    }
)


@dataclass(frozen=True)
class Witness:
    """Concrete evidence backing a VIOLATES verdict: the probe call and the observed delta."""

    args: dict
    diff: Any = None
    result: Any = None


@dataclass(frozen=True)
class ClauseVerdict:
    verdict: Verdict
    clause_id: str
    defect_class: Optional[DefectClass] = None
    witness: Optional[Witness] = None
    reason_code: Optional[str] = None

    def __post_init__(self):
        if self.verdict == Verdict.UNTESTABLE:
            if self.reason_code is None:
                raise ValueError(f"{self.clause_id}: UNTESTABLE verdict requires a reason_code")
            if self.reason_code not in UNTESTABLE_REASONS:
                raise ValueError(f"{self.clause_id}: unknown untestable reason_code {self.reason_code!r}")
        elif self.reason_code is not None:
            raise ValueError(f"{self.clause_id}: reason_code is only valid on an UNTESTABLE verdict")


def tool_verdict(clause_verdicts: list[ClauseVerdict]) -> Verdict:
    """Roll up a tool's clause verdicts into one overall verdict.

    Counting rule (CLAUDE.md, PREDICATE-GRAMMAR.md sec 2.3): VIOLATES if any clause violates,
    else UNTESTABLE if any clause is untestable, else CONFORMS. UNTESTABLE is never dropped --
    a tool with nine CONFORMS clauses and one UNTESTABLE clause is not reported as fully conforming.
    """
    if not clause_verdicts:
        raise ValueError("cannot roll up an empty set of clause verdicts")
    verdicts = {cv.verdict for cv in clause_verdicts}
    if Verdict.VIOLATES in verdicts:
        return Verdict.VIOLATES
    if Verdict.UNTESTABLE in verdicts:
        return Verdict.UNTESTABLE
    return Verdict.CONFORMS


def verdict_counts(clause_verdicts: list[ClauseVerdict]) -> dict[Verdict, int]:
    """Per-verdict counts across a set of clause verdicts. Every clause counts exactly once;
    nothing is dropped from the denominator regardless of the tool-level rollup."""
    counts = {Verdict.CONFORMS: 0, Verdict.VIOLATES: 0, Verdict.UNTESTABLE: 0}
    for cv in clause_verdicts:
        counts[cv.verdict] += 1
    return counts
