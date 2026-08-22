"""Dataclasses mirroring spec/schema.json. No validation logic here -- that is spec/validate.py's
job. Construction is best-effort dict unpacking (missing required keys raise plain KeyError);
schema conformance is checked separately before a Contract is ever built from untrusted YAML.

ClauseVerdict lives in core/verdict.py (the verdict lattice owns it); re-exported here so
Finding's field type is reachable from this module too, per the build spec.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

import yaml

from core.verdict import ClauseVerdict  # re-export, see module docstring

__all__ = [
    "SourceRef",
    "Provenance",
    "ArgSpec",
    "Signature",
    "Clause",
    "EffectClause",
    "FrameClause",
    "SuccessSignal",
    "PreconditionViolationExpectation",
    "OnPreconditionViolation",
    "Reset",
    "Untestable",
    "Contract",
    "Finding",
    "ClauseVerdict",
    "HeadlineTier",
    "AGENT_VISIBLE_SURFACES",
    "headline_tier",
]


class HeadlineTier(str, Enum):
    """spec/PREDICATE-GRAMMAR.md sec 6, 'Headline eligibility'. Derived, never hand-set:
    every clause is placed into exactly one of these three tiers by `headline_tier()` below,
    from the clause's own provenance plus the outcome of spec/validate.py check 8. Nothing in
    this module sets a tier directly."""

    AGENT_VISIBLE = "agent_visible"
    MAINTAINER_ANNOTATED = "maintainer_annotated"
    INFERRED = "inferred"


# Mirrors the agent-visible half of spec/schema.json $defs.advertisedSurface's closed list.
# 'maintainer_annotation' is deliberately excluded -- it is the other named tier.
AGENT_VISIBLE_SURFACES = frozenset(
    {"docstring", "schema", "prompt_template", "tool_return", "readme", "external_standard"}
)


def headline_tier(clause, check8_passed: bool) -> "HeadlineTier":
    """Derive a clause's headline-eligibility tier.

    A clause is `AGENT_VISIBLE` iff its provenance surface is in the agent-visible tier
    (`AGENT_VISIBLE_SURFACES`) AND `check8_passed` is True. `check8_passed` is the outcome of
    spec/validate.py's check 8 for THIS clause's provenance -- it is a required argument
    precisely so this function cannot silently assume a tool_return or prompt_template quote is
    agent-visible just because its surface tag says so; the caller must have actually run check
    8 (or, for surfaces check 8 does not test -- docstring, schema, readme, external_standard --
    pass True, since those are not what check 8 exists to catch; see spec/validate.py's
    check8_agent_visibility for which surfaces it tests).

    `inferred: true` and a `maintainer_annotation` surface both mean the same thing for
    reporting purposes -- never headline -- but are kept as distinct tiers because they carry
    different evidential weight (PREDICATE-GRAMMAR.md sec 6 'Headline eligibility'; schema.json
    advertisedSurface description).
    """
    if clause.inferred or clause.provenance is None:
        return HeadlineTier.INFERRED
    surface = clause.provenance.surface
    if surface == "maintainer_annotation":
        return HeadlineTier.MAINTAINER_ANNOTATED
    if surface in AGENT_VISIBLE_SURFACES and check8_passed:
        return HeadlineTier.AGENT_VISIBLE
    # Agent-visible surface tag but check 8 did not confirm agent-visibility for this specific
    # quote (failed, or was never run). Not headline-eligible until the contract is re-tiered or
    # the check is actually run -- report it alongside maintainer_annotation rather than let it
    # fall through silently.
    return HeadlineTier.MAINTAINER_ANNOTATED


@dataclass(frozen=True)
class SourceRef:
    file: str
    start_line: int
    end_line: int
    note: Optional[str] = None

    @staticmethod
    def from_dict(d: dict) -> "SourceRef":
        return SourceRef(file=d["file"], start_line=d["start_line"], end_line=d["end_line"], note=d.get("note"))


@dataclass(frozen=True)
class Provenance:
    surface: str
    quote: str
    file: Optional[str] = None
    line: Optional[int] = None
    standard: Optional[str] = None

    @staticmethod
    def from_dict(d: dict) -> "Provenance":
        return Provenance(
            surface=d["surface"],
            quote=d["quote"],
            file=d.get("file"),
            line=d.get("line"),
            standard=d.get("standard"),
        )


@dataclass(frozen=True)
class ArgSpec:
    type: str
    effective: bool
    provenance: Optional[Provenance] = None
    probe_values: tuple = ()

    @staticmethod
    def from_dict(d: dict) -> "ArgSpec":
        prov = d.get("provenance")
        return ArgSpec(
            type=d["type"],
            effective=d["effective"],
            provenance=Provenance.from_dict(prov) if prov else None,
            probe_values=tuple(d.get("probe_values", [])),
        )


@dataclass(frozen=True)
class Signature:
    args: dict  # name -> ArgSpec
    returns: Optional[str] = None

    @staticmethod
    def from_dict(d: dict) -> "Signature":
        return Signature(
            args={name: ArgSpec.from_dict(spec) for name, spec in d.get("args", {}).items()},
            returns=d.get("returns"),
        )


@dataclass(frozen=True)
class Clause:
    id: str
    text: str
    predicate: str
    provenance: Optional[Provenance] = None
    inferred: bool = False
    annotators: tuple = ()

    @staticmethod
    def from_dict(d: dict) -> "Clause":
        prov = d.get("provenance")
        return Clause(
            id=d["id"],
            text=d["text"],
            predicate=d["predicate"],
            provenance=Provenance.from_dict(prov) if prov else None,
            inferred=d.get("inferred", False),
            annotators=tuple(d.get("annotators", [])),
        )


@dataclass(frozen=True)
class EffectClause(Clause):
    advertised_deferred: bool = False

    @staticmethod
    def from_dict(d: dict) -> "EffectClause":
        base = Clause.from_dict(d)
        return EffectClause(
            id=base.id,
            text=base.text,
            predicate=base.predicate,
            provenance=base.provenance,
            inferred=base.inferred,
            annotators=base.annotators,
            advertised_deferred=d.get("advertised_deferred", False),
        )


@dataclass(frozen=True)
class FrameClause:
    id: str
    path: str
    text: Optional[str] = None
    provenance: Optional[Provenance] = None
    inferred: bool = False
    mode: str = "unchanged"

    @staticmethod
    def from_dict(d: dict) -> "FrameClause":
        prov = d.get("provenance")
        return FrameClause(
            id=d["id"],
            path=d["path"],
            text=d.get("text"),
            provenance=Provenance.from_dict(prov) if prov else None,
            inferred=d.get("inferred", False),
            mode=d.get("mode", "unchanged"),
        )


@dataclass(frozen=True)
class SuccessSignal:
    predicate: str
    biconditional: bool = False
    justification: Optional[str] = None
    provenance: Optional[Provenance] = None

    @staticmethod
    def from_dict(d: dict) -> "SuccessSignal":
        prov = d.get("provenance")
        return SuccessSignal(
            predicate=d["predicate"],
            biconditional=d.get("biconditional", False),
            justification=d.get("justification"),
            provenance=Provenance.from_dict(prov) if prov else None,
        )


@dataclass(frozen=True)
class PreconditionViolationExpectation:
    error_signal: bool
    state_delta: str  # 'none' | 'any'
    error_type: Optional[str] = None

    @staticmethod
    def from_dict(d: dict) -> "PreconditionViolationExpectation":
        return PreconditionViolationExpectation(
            error_signal=d["error_signal"],
            state_delta=d["state_delta"],
            error_type=d.get("error_type"),
        )


@dataclass(frozen=True)
class OnPreconditionViolation:
    expect: PreconditionViolationExpectation
    provenance: Optional[Provenance] = None

    @staticmethod
    def from_dict(d: dict) -> "OnPreconditionViolation":
        prov = d.get("provenance")
        return OnPreconditionViolation(
            expect=PreconditionViolationExpectation.from_dict(d["expect"]),
            provenance=Provenance.from_dict(prov) if prov else None,
        )


@dataclass(frozen=True)
class Reset:
    predicate: str
    provenance: Optional[Provenance] = None
    scope: str = "unknown"

    @staticmethod
    def from_dict(d: dict) -> "Reset":
        prov = d.get("provenance")
        return Reset(
            predicate=d["predicate"],
            provenance=Provenance.from_dict(prov) if prov else None,
            scope=d.get("scope", "unknown"),
        )


@dataclass(frozen=True)
class Untestable:
    clause_id: str
    reason: str
    note: Optional[str] = None

    @staticmethod
    def from_dict(d: dict) -> "Untestable":
        return Untestable(clause_id=d["clause_id"], reason=d["reason"], note=d.get("note"))


@dataclass(frozen=True)
class Contract:
    contract_version: str
    tool: str
    benchmark: str
    commit: str
    source: SourceRef
    signature: Signature
    preconditions: tuple = ()
    effects: tuple = ()
    frame: tuple = ()
    success_signal: Optional[SuccessSignal] = None
    on_precondition_violation: Optional[OnPreconditionViolation] = None
    invariants: tuple = ()
    reset: Optional[Reset] = None
    untestable: tuple = ()
    notes: Optional[str] = None

    @staticmethod
    def from_dict(d: dict) -> "Contract":
        opv = d.get("on_precondition_violation")
        reset = d.get("reset")
        ss = d.get("success_signal")
        return Contract(
            contract_version=d["contract_version"],
            tool=d["tool"],
            benchmark=d["benchmark"],
            commit=d["commit"],
            source=SourceRef.from_dict(d["source"]),
            signature=Signature.from_dict(d["signature"]),
            preconditions=tuple(Clause.from_dict(c) for c in d.get("preconditions", [])),
            effects=tuple(EffectClause.from_dict(c) for c in d.get("effects", [])),
            frame=tuple(FrameClause.from_dict(c) for c in d.get("frame", [])),
            success_signal=SuccessSignal.from_dict(ss) if ss else None,
            on_precondition_violation=OnPreconditionViolation.from_dict(opv) if opv else None,
            invariants=tuple(Clause.from_dict(c) for c in d.get("invariants", [])),
            reset=Reset.from_dict(reset) if reset else None,
            untestable=tuple(Untestable.from_dict(u) for u in d.get("untestable", [])),
            notes=d.get("notes"),
        )

    @staticmethod
    def from_yaml(path) -> "Contract":
        with open(path, "r", encoding="utf-8") as fh:
            d = yaml.safe_load(fh)
        return Contract.from_dict(d)

    def all_clauses(self) -> list:
        """Every id-bearing clause in the contract (preconditions, effects, invariants, frame),
        for uniqueness checks and reporting -- see spec/validate.py check 7."""
        return list(self.preconditions) + list(self.effects) + list(self.invariants) + list(self.frame)


@dataclass(frozen=True)
class Finding:
    """One reportable finding: a clause's verdict against a specific tool, with enough
    provenance to trace it back to a tool, a clause, and (via witness) an evaluator read site."""

    benchmark: str
    tool: str
    commit: str
    clause_id: str
    clause_verdict: ClauseVerdict
    provenance: Optional[Provenance] = None
    notes: Optional[str] = None
