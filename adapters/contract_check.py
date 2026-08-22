"""A minimal, generic, tool-agnostic contract checker -- enough machinery to make Gate 1b a real
claim ("the framework rediscovers both tau2 findings from contracts alone") rather than a bug
list with a contract file next to it.

This is NOT the static/dynamic checker scheduled in ARCHITECTURE-FINAL.md sec 7 for Aug 31 - Sep
1 (site enumeration, mutation probing, UNTESTABLE reason-code assignment across a whole tool
surface, etc.). It is the smallest thing that can take one `Contract` (core/model.py) plus one
observed (pre, post, args, result) tuple and produce `ClauseVerdict`s (core/verdict.py) by
*evaluating the contract's own predicates* -- core/predicates.py, core/frame.py,
core/canonical.py -- against the real snapshots an adapter produced. Every clause id in a
verdict traces back to a YAML clause; nothing here references a tool name.

Two entry points, mirroring the two places a contract makes a falsifiable claim about a single
call:

  check_effects(contract, pre, post, args, result)
      Effect-clause conformance, plus the Phantom/Partial Effect distinction described in
      ARCHITECTURE-FINAL.md sec 3.4 -- gated on `success_signal.biconditional` being explicitly
      opted into by the contract (never assumed).

  check_precondition_enforcement(contract, pre, post, args, error)
      Unenforced Precondition detection: evaluate every declared precondition against this call;
      if any is violated, compare the contract's `on_precondition_violation.expect` against what
      actually happened (did the call signal an error? was the state delta empty?).

Both return `ClauseVerdict`s from core/verdict.py and raise nothing tool-specific -- the two
Gate 1b tests differ only in which contract and which args they pass in.
"""
from __future__ import annotations

from typing import Any, Optional

from core.canonical import CanonicalConfig, diff
from core.model import Contract
from core.predicates import PathError, PredicateTypeError, compile_predicate, evaluate
from core.verdict import ClauseVerdict, DefectClass, Verdict, Witness

__all__ = ["to_result_binding", "check_effects", "check_precondition_enforcement"]


def to_result_binding(raw: Any, success: bool, error: Optional[str]) -> Any:
    """adapters.base.ToolResult -> the `result` binding PREDICATE-GRAMMAR.md sec 1 specifies:
    "the tool's return value, canonicalized; result.error is present iff the call raised". A
    ToolResult already separates "raised" (error is not None) from "the returned value" (raw);
    this just re-shapes that into the single `result` mapping a predicate expects."""
    if success:
        return raw
    return {"error": error}


def _clause_verdict(
    clause_id: str,
    predicate_src: str,
    pre: Any,
    post: Any,
    args: Any,
    result: Any,
    *,
    on_false: DefectClass,
    cfg: Optional[CanonicalConfig] = None,
) -> ClauseVerdict:
    """Evaluate one predicate; CONFORMS if True, VIOLATES (tagged `on_false`, with a witness) if
    False, UNTESTABLE if a snapshot path did not resolve (PREDICATE-GRAMMAR.md sec 2.3 -- a
    missing path is never silently False) or if evaluation raised TypeError on a path that DID
    resolve (core/predicates.py's PredicateTypeError -- e.g. a comparison against a null field;
    kept as its own reason_code, deliberately never merged into no_observable_state, so the two
    causes are counted separately)."""
    compiled = compile_predicate(predicate_src)
    try:
        ok = evaluate(compiled, pre, post, args, result)
    except PathError:
        return ClauseVerdict(verdict=Verdict.UNTESTABLE, clause_id=clause_id, reason_code="no_observable_state")
    except PredicateTypeError:
        return ClauseVerdict(verdict=Verdict.UNTESTABLE, clause_id=clause_id, reason_code="predicate_type_error")
    if ok:
        return ClauseVerdict(verdict=Verdict.CONFORMS, clause_id=clause_id)
    return ClauseVerdict(
        verdict=Verdict.VIOLATES,
        clause_id=clause_id,
        defect_class=on_false,
        witness=Witness(args=args, diff=diff(pre, post, cfg), result=result),
    )


def check_effects(
    contract: Contract,
    pre: Any,
    post: Any,
    args: Any,
    result: Any,
    *,
    cfg: Optional[CanonicalConfig] = None,
) -> list[ClauseVerdict]:
    """Evaluate every effect clause. When `success_signal.biconditional` is true (opt-in only,
    per ARCHITECTURE-FINAL.md sec 3.4 and schema.json successSignal.biconditional), refine the
    defect class generically:

      - EVERY (non-UNTESTABLE) effect clause violates  -> Phantom Effect (nothing advertised
        landed, yet the interface signals success).
      - SOME but not all violate                        -> Partial Effect (the mutation is
        applied, its declared companion effect is not -- FINDINGS-VERIFIED.md Finding 3's shape
        exactly: eff.status_cancelled CONFORMS, eff.seats_released VIOLATES).

    Without biconditional opt-in, violations are reported as plain Partial Effect (the weaker,
    always-safe reading: an effect clause not holding after a call that mutated *something*),
    since Phantom Effect is specifically a claim about the success signal's biconditional
    reading and this contract never made that claim.
    """
    verdicts = [
        _clause_verdict(ec.id, ec.predicate, pre, post, args, result, on_false=DefectClass.PARTIAL_EFFECT, cfg=cfg)
        for ec in contract.effects
    ]

    biconditional = bool(contract.success_signal and contract.success_signal.biconditional)
    testable = [v for v in verdicts if v.verdict != Verdict.UNTESTABLE]
    all_violate = biconditional and bool(testable) and all(v.verdict == Verdict.VIOLATES for v in testable)
    if all_violate:
        verdicts = [
            ClauseVerdict(
                verdict=v.verdict,
                clause_id=v.clause_id,
                defect_class=DefectClass.PHANTOM_EFFECT if v.verdict == Verdict.VIOLATES else v.defect_class,
                witness=v.witness,
                reason_code=v.reason_code,
            )
            for v in verdicts
        ]
    return verdicts


def check_precondition_enforcement(
    contract: Contract,
    pre: Any,
    post: Any,
    args: Any,
    result: Any,
    error: Optional[str],
    *,
    cfg: Optional[CanonicalConfig] = None,
) -> Optional[ClauseVerdict]:
    """Probe-based Unenforced Precondition detection. Evaluate every declared precondition
    against this one call; if none is violated, this call is not informative for enforcement
    (returns None -- CONFORMS-by-omission would overclaim). If contract declares no
    `on_precondition_violation` expectation at all, this defect class cannot be reported for this
    tool (schema.json: "Absence of this block means the contract makes no claim") -- returns
    None.

    Otherwise: compare the declared expectation (must the call signal an error? must the state
    delta be empty?) against what actually happened. A call is expected to be constructed by the
    CALLER so that at least one precondition is deliberately violated -- this function only
    grades the outcome, it does not choose the probe.
    """
    if contract.on_precondition_violation is None:
        return None

    violated_ids: list[str] = []
    for pc in contract.preconditions:
        compiled = compile_predicate(pc.predicate)
        try:
            held = evaluate(compiled, pre, post, args, result)
        except (PathError, PredicateTypeError):
            continue  # untestable for this clause; does not block grading other clauses
        if not held:
            violated_ids.append(pc.id)

    if not violated_ids:
        return None

    expect = contract.on_precondition_violation.expect
    actual_error_signal = error is not None
    actual_delta = diff(pre, post, cfg)
    actual_no_delta = actual_delta == {}

    enforced = True
    if expect.error_signal and not actual_error_signal:
        enforced = False
    if expect.state_delta == "none" and not actual_no_delta:
        enforced = False

    clause_id = violated_ids[0]
    if enforced:
        return ClauseVerdict(verdict=Verdict.CONFORMS, clause_id=clause_id)
    return ClauseVerdict(
        verdict=Verdict.VIOLATES,
        clause_id=clause_id,
        defect_class=DefectClass.UNENFORCED_PRECONDITION,
        witness=Witness(args=args, diff=actual_delta, result=result),
    )
