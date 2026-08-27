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

check_effects' IGNORED_ARGUMENT tagging (added for the AgentDojo/MM-ToolSandbox adapters, whose
field-observed defects are predominantly this class -- FINDINGS-VERIFIED.md Findings 5, 6, 7, 8)
-----------------------------------------------------------------------------------------------
tau2's two Gate 1b findings are shaped as "an effect didn't happen" (Partial Effect) and "a
precondition wasn't enforced" (Unenforced Precondition). Findings 5/6/7/8 are differently shaped:
"an argument's own value never reaches state" -- e.g. `post...recurring == args.recurring`
failing precisely because `args.recurring` was truthiness-guarded out of the write path
(`update_scheduled_transaction`, banking_client.py:144). That shape was always expressible as an
ordinary effect clause (nothing about the schema or the predicate grammar needed to change --
`args` is already a first-class binding, PREDICATE-GRAMMAR.md sec 1), but `check_effects` always
tagged a violation PARTIAL_EFFECT, which would mislabel exactly the clauses this project's own
taxonomy calls Ignored Argument. `_effective_arg_value_uses` (below) decides the tag generically,
from the predicate's own AST via core/predicates.compile_predicate -- never by pattern-matching
the predicate string or by a tool/clause-id special case -- so this stays a tool-agnostic
checker, unchanged in spirit from the rest of this module.

The rule: a clause is tagged IGNORED_ARGUMENT (instead of the PARTIAL_EFFECT default) iff its
predicate contains an `==`/`!=` comparison where one side IS, or is a shallow +/-/*/-arithmetic
combination of, an `args.<name>` reference for some `<name>` the contract's own `signature.args`
declares `effective: true`. This deliberately does NOT fire when `args.<name>` is used only as a
Subscript KEY selecting which record to inspect -- `pre.reservations[args.reservation_id].cabin`
never trips it, because `args.reservation_id` there is a selector, not a value the interface
claims to have written. Checked against `spec/contracts/tau2/cancel_reservation.yaml`'s
`eff.seats_released` (uses `args.reservation_id` only as a selector, several layers of Subscript
deep) and `refuel_data.yaml`'s `eff.data_refueled` (uses `args.gb_amount` as a value, inside a
`+`) before being trusted here -- see tests/test_contract_check.py.
"""
from __future__ import annotations

import ast
from typing import Any, Optional

from core.canonical import CanonicalConfig, diff
from core.model import Contract
from core.predicates import PathError, PredicateTypeError, compile_predicate, evaluate
from core.verdict import ClauseVerdict, DefectClass, Verdict, Witness

__all__ = ["to_result_binding", "check_effects", "check_precondition_enforcement"]


def _effective_arg_value_uses(predicate_src: str, effective_names: frozenset) -> frozenset:
    """Names in `effective_names` that appear as a VALUE operand of an ==/!= comparison inside
    `predicate_src` -- see module docstring section above for the selector-vs-value distinction
    and why it matters. Returns the empty frozenset if none do (or if `effective_names` is
    empty, cheaply short-circuited by the caller)."""
    if not effective_names:
        return frozenset()

    def value_names(node: ast.AST) -> set:
        # Deliberately shallow: descends through +/-/*/-/unary only, and only recognizes the
        # exact post-rewrite shape `args.<name>` produces (Subscript(Name('args'), Constant)).
        # Does NOT descend into an arbitrary Subscript's `.slice` or `.value` -- that is exactly
        # what keeps a selector use (`pre.foo[args.bar]`) from being misread as a value use.
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == "args":
            if isinstance(node.slice, ast.Constant):
                return {node.slice.value}
            return set()
        if isinstance(node, ast.BinOp):
            return value_names(node.left) | value_names(node.right)
        if isinstance(node, ast.UnaryOp):
            return value_names(node.operand)
        return set()

    compiled = compile_predicate(predicate_src)
    found: set = set()
    for node in ast.walk(compiled.tree):
        if isinstance(node, ast.Compare) and any(isinstance(op, (ast.Eq, ast.NotEq)) for op in node.ops):
            for side in (node.left, *node.comparators):
                found |= value_names(side)
    return frozenset(found) & effective_names


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
    effective_names = frozenset(name for name, spec in contract.signature.args.items() if spec.effective)
    verdicts = [
        _clause_verdict(
            ec.id,
            ec.predicate,
            pre,
            post,
            args,
            result,
            on_false=(
                DefectClass.IGNORED_ARGUMENT
                if _effective_arg_value_uses(ec.predicate, effective_names)
                else DefectClass.PARTIAL_EFFECT
            ),
            cfg=cfg,
        )
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
    delta be empty? -- and, when declared, must the raised exception be a SPECIFIC type?) against
    what actually happened. A call is expected to be constructed by the CALLER so that at least
    one precondition is deliberately violated -- this function only grades the outcome, it does
    not choose the probe.

    `expect.error_type` (schema.json on_precondition_violation.expect.error_type, GAP 2 in
    CLAUDE.md's build note): 23 shipped contracts declare a specific expected exception type
    (e.g. "ValueError") and, before this fix, this function never read it -- a tool that raised
    the WRONG exception still reported CONFORMS as long as it raised something and left no delta.
    Checked here against `error`'s own type-name prefix: every concrete adapter that formats an
    error string from a live exception does so as `f"{type(e).__name__}: {e}"`
    (adapters/_tau2_worker.py, adapters/_agentdojo_worker.py, adapters/_mmtoolsandbox_worker.py,
    and agentdojo's own `functions_runtime.py:run_function`, which the AgentDojo worker calls
    through) -- so `error.split(":", 1)[0].strip()` recovers the raised class's `__name__`
    without needing the adapter boundary (adapters/base.py's `ToolResult`) to carry a second,
    dedicated field. toy/adapter.py is the one adapter that does NOT follow this convention (it
    catches a single internal `ToyError` and stores only `str(e)`, discarding the type name), but
    no toy contract declares `error_type`, so this is a real but currently inert gap, not a false
    negative in the shipped contract set -- recorded here rather than silently assumed away.
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
    if expect.error_type is not None and actual_error_signal:
        actual_error_type = error.split(":", 1)[0].strip()
        if actual_error_type != expect.error_type:
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
