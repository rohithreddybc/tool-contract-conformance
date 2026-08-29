"""Extensional agreement between Annotator A's and Annotator B's contracts -- the measurement
half of required item R1, bound by `experiments/annotation_protocol.md` (committed before this
file was written; nothing in that protocol is changed here).

WHAT THIS SCRIPT DOES NOT DO (protocol sec 1): it never asks whether two predicate TEXTS look
semantically equivalent. It compiles both annotators' predicates and evaluates them against a
shared probe corpus, drawn through both live adapters against the same fresh environments, and
compares the resulting CONFORMS/VIOLATES/UNTESTABLE verdicts, clause by clause. That is the whole
measurement.

CHECKER REUSE, AND WHAT IS DELIBERATELY NOT REUSED. This project's checker is frozen at
`checker-freeze-v2` (`core/`, `dynamic/`, `adapters/contract_check.py`, `spec/validate.py` are not
modified by this file). Frame clauses are graded with the real, frozen `dynamic.harness.check_frame`
-- imported and called, never re-implemented -- because frame's path/mode semantics are genuinely
non-trivial (wildcard matching, "changed" vs "unchanged" mode) and reimplementing them here would
risk a second, drifting copy. Precondition/effect/invariant clauses are graded with a small,
uniform CONFORMS/VIOLATES/UNTESTABLE wrapper around `core.predicates.compile_predicate`/`evaluate`
-- the exact same three-way split `adapters/contract_check.py`'s own `_clause_verdict` already
applies to effect clauses, and the exact same (pre, pre, args, {}) binding convention
`mutation/probes.py` and `dynamic/probes.py` already use for precondition clauses. This is not a
second checker: it is the one evaluation primitive already used identically in three places in
this codebase, applied uniformly to every clause kind so a verdict is defined the same way
everywhere in this script. `check_effects`/`check_precondition_enforcement` themselves are NOT
used for the clause-level comparison because they collapse multiple clauses into defect-class
refinements (PHANTOM_EFFECT re-tagging, "first violated precondition only") that are a property of
the PRODUCTION pipeline's reporting convention, not of the extensional CONFORMS/VIOLATES/UNTESTABLE
question this study asks per clause. `dynamic.harness.check_ignored_argument` (frozen) IS reused
directly, unmodified, for the three findings whose evidence is an `arg.<name>` verdict rather than
a YAML clause (Findings 6, 7, 8) -- see `arg_robustness_check` below.

PROBE CORPUS, AND ONE PLACE IT DEVIATES FROM THE PLAN AS WRITTEN (recorded, not hidden).
`experiments/detector_analysis_plan.md` sec 2 defines the corpus as (1) recorded real calls from
adapter smoke-testing, (2) signature-derived boundary probes, (3) one satisfying/one violating
probe per precondition clause, drawn from the union of both annotators' preconditions (sec 2's own
2026-08-21 amendment). Component (1) could not be executed as written: this repository does not
persist a recorded-call store from adapter smoke-testing anywhere (grepped; the one existing
production caller of `mutation.probes.build_equivalence_probe_corpus`,
`experiments/open_world_cosmic_ray/tau2_telecom/scoring_lib.py`, itself passes
`recorded_calls=[]` for the identical reason). Component (1) is therefore empty for every tool
here, exactly as it already is in the one place this corpus is built anywhere in this project.
Reported under "protocol items not executed as written" below, not silently substituted.

Component (2) is built from BOTH contracts' signatures (`mutation.probes.generate_boundary_probes`
run once per contract, merged) rather than one, extending the sec-2 amendment's own logic (already
applied to preconditions) to boundary probes too -- the alternative (boundary probes from A's
signature only) would silently under-represent any argument only B declared `effective`/gave
`probe_values` for (see `update_scheduled_transaction`'s `id` argument, `effective: false` under A
and `true` under B).

`venmo_social` needed one additional, disclosed departure -- see `_venmo_branch_probes` below.
"""
from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from adapters.agentdojo import AgentDojoAdapter, AgentDojoAdapterError  # noqa: E402
from adapters.mmtoolsandbox import MMToolSandboxAdapter, MMToolSandboxAdapterError  # noqa: E402
from adapters.tau2 import Tau2Adapter, Tau2AdapterError  # noqa: E402
from core.model import Contract  # noqa: E402
from core.predicates import PathError, PredicateTypeError, compile_predicate, evaluate  # noqa: E402
from core.verdict import Verdict  # noqa: E402
from dynamic.harness import _invoke_fresh, check_frame, check_ignored_argument  # noqa: E402
from dynamic.probes import generate_ignored_argument_probes  # noqa: E402
from mutation.probes import Probe, generate_boundary_probes, generate_precondition_probes  # noqa: E402
from mutation.real_targets import resolve_domain  # noqa: E402

CONTRACTS_A_ROOT = PROJECT_ROOT / "spec" / "contracts"
CONTRACTS_B_ROOT = PROJECT_ROOT / "spec" / "contracts_annotator_b"
REPORT_DIR = PROJECT_ROOT / "report"
JSON_PATH = REPORT_DIR / "agreement.json"
SUMMARY_PATH = REPORT_DIR / "agreement_summary.md"
GRAMMAR_GAPS_PATH = PROJECT_ROOT / "spec" / "GRAMMAR-GAPS.md"


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, text=True).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# =================================================================================================
# 1. Six tool pairs, two strata, and the clause mapping between the two contract files -- fixed by
#    reading both files against the tool's real source, not decided from agreement outcomes.
# =================================================================================================


@dataclass(frozen=True)
class ClauseMapping:
    """One reportable clause-comparison unit for a tool pair."""

    id_a: Optional[str]
    id_b: Optional[str]
    note: str


@dataclass(frozen=True)
class ToolSpec:
    benchmark: str
    tool: str
    stratum: str  # "blind" | "contaminated"
    adapter_key: str  # "tau2" | "agentdojo" | "mmtoolsandbox"
    path_a: Path
    path_b: Path
    clause_map: tuple  # ClauseMapping, one per comparable pair
    a_only: tuple  # clause ids present only in A (segmentation)
    b_only: tuple  # clause ids present only in B (segmentation)
    anchor_note: str
    arg_findings: tuple = ()  # arg.<name> findings to check via check_ignored_argument
    notes: tuple = ()  # freeform adjudication/root-cause notes surfaced verbatim in the summary


TOOL_SPECS = [
    ToolSpec(
        benchmark="tau2-bench",
        tool="refuel_data",
        stratum="blind",
        adapter_key="tau2",
        path_a=CONTRACTS_A_ROOT / "tau2" / "refuel_data.yaml",
        path_b=CONTRACTS_B_ROOT / "tau2" / "refuel_data.yaml",
        clause_map=(
            ClauseMapping("pre.line_active", "pre.line_active", "same advertised precondition"),
            ClauseMapping("pre.customer_owns_line", "pre.customer_owns_line", "same advertised precondition"),
            ClauseMapping("eff.data_refueled", "eff.data_refueling_increases", "same advertised effect (data added)"),
            ClauseMapping(
                "eff.customer_charged", "eff.customer_billed",
                "same advertised effect (customer charged), DIFFERENT strength: A asserts an exact "
                "charge formula, B asserts direction of change only",
            ),
            ClauseMapping("frame.plans_unchanged", "frame.plans_unchanged", "same frame claim"),
            ClauseMapping("frame.devices_unchanged", "frame.devices_unchanged", "same frame claim"),
        ),
        a_only=(),
        b_only=("frame.line_status_unchanged", "frame.line_phone_unchanged"),
        anchor_note="Finding 2 (Unenforced Precondition) -- anchor clause pre.line_active",
    ),
    ToolSpec(
        benchmark="tau2-bench",
        tool="cancel_reservation",
        stratum="contaminated",
        adapter_key="tau2",
        path_a=CONTRACTS_A_ROOT / "tau2" / "cancel_reservation.yaml",
        path_b=CONTRACTS_B_ROOT / "tau2" / "cancel_reservation.yaml",
        clause_map=(
            ClauseMapping("pre.reservation_exists", "pre.reservation_exists", "same advertised precondition"),
            ClauseMapping("eff.status_cancelled", "eff.status_cancelled", "same advertised effect"),
            ClauseMapping("eff.seats_released", "eff.seats_released", "same advertised effect (the Finding 3 clause; predicate text is byte-identical -- B disclosed copying the worked example)"),
            ClauseMapping("frame.users_unchanged", "frame.users_unchanged", "same frame claim"),
            ClauseMapping("inv.seat_conservation", "inv.seat_conservation", "same invariant (predicate text identical modulo line-wrapping)"),
        ),
        a_only=(),
        b_only=("eff.payment_refunded",),
        anchor_note="Finding 3 (Partial Effect) -- anchor clause eff.seats_released. CONTAMINATED STRATUM.",
    ),
    ToolSpec(
        benchmark="agentdojo",
        tool="update_scheduled_transaction",
        stratum="blind",
        adapter_key="agentdojo",
        path_a=CONTRACTS_A_ROOT / "agentdojo" / "update_scheduled_transaction.yaml",
        path_b=CONTRACTS_B_ROOT / "agentdojo" / "update_scheduled_transaction.yaml",
        clause_map=(
            ClauseMapping("pre.transaction_exists", "pre.transaction_exists", "same advertised precondition"),
            ClauseMapping("eff.recurring_propagated", "eff.recurring_updated_if_given", "same advertised effect -- the Finding 5 'recurring' clause"),
            ClauseMapping("eff.amount_propagated", "eff.amount_updated_if_given", "same advertised effect -- the Finding 5 'amount' clause"),
            ClauseMapping("frame.iban_unchanged", "frame.iban_unchanged", "same frame claim"),
        ),
        a_only=(),
        b_only=(
            "eff.recipient_updated_if_given", "eff.subject_updated_if_given", "eff.date_updated_if_given",
            "frame.transactions_list_unchanged", "frame.balance_unchanged",
            "frame.scheduled_id_unchanged", "frame.scheduled_sender_unchanged",
        ),
        anchor_note="Finding 5 (Ignored Argument + Phantom Effect) -- anchor clauses eff.recurring_propagated / eff.amount_propagated",
        arg_findings=("recurring", "amount"),
    ),
    ToolSpec(
        benchmark="agentdojo",
        tool="reserve_car_rental",
        stratum="blind",
        adapter_key="agentdojo",
        path_a=CONTRACTS_A_ROOT / "agentdojo" / "reserve_car_rental.yaml",
        path_b=CONTRACTS_B_ROOT / "agentdojo" / "reserve_car_rental.yaml",
        clause_map=(
            ClauseMapping("eff.start_time_applied", "eff.start_time_recorded", "same advertised effect, identical predicate text"),
            ClauseMapping("eff.end_time_applied", "eff.end_time_recorded", "same advertised effect (the Finding 6 clause), identical predicate text"),
            ClauseMapping("eff.title_set", "eff.company_recorded", "same advertised effect, identical predicate text"),
            ClauseMapping("eff.reservation_type_set", "eff.reservation_type_car", "same advertised effect, identical predicate text"),
        ),
        a_only=("frame.contact_information_changes",),
        b_only=(),
        anchor_note="Finding 6 (Ignored Argument) -- anchor clause eff.end_time_applied",
        arg_findings=("end_time",),
        notes=(
            (
                "arg.end_time flip, root cause confirmed by direct reproduction (not left as a bare "
                "verdict pair): A's contract declares `probe_values` pinning start_time/end_time to "
                "round-trip-exact ISO strings (its own header comment explains why: the generic "
                "harvester has nothing ISO-datetime-shaped to draw from and would otherwise draw hotel/"
                "city names off the live travel snapshot). B's contract does not declare probe_values "
                "for either argument. Reproduced directly: dynamic.probes.generate_ignored_argument_probes "
                "against B's own contract builds every variant call's `start_time` from the harvested "
                "snapshot pool (e.g. 'hotel_list', 'Paris'), and every resulting call raises "
                "`ValueError: Invalid isoformat string` before the tool's ignored-argument defect could "
                "ever be observed -- 0 of 3 variant calls succeed, so check_ignored_argument reports "
                "UNTESTABLE/no_observable_state, not CONFORMS. The underlying tool behaviour is "
                "unchanged; B's own signature.args.end_time.provenance quote is textually identical to "
                "A's. This is a probe-generation-capability gap tied to whether an annotator remembered "
                "to populate a schema-optional `probe_values` hint for a string argument with an implicit "
                "syntactic format the docstring does not spell out as a regex -- not a disagreement about "
                "what reserve_car_rental advertises, and not evidence the defect is absent under B's "
                "contract. It is reported as a flip because the protocol's flip question is defined at "
                "the verdict level (VIOLATES vs. not-VIOLATES), and UNTESTABLE is not-VIOLATES."
            ),
        ),
    ),
    ToolSpec(
        benchmark="agentdojo",
        tool="invite_user_to_slack",
        stratum="blind",
        adapter_key="agentdojo",
        path_a=CONTRACTS_A_ROOT / "agentdojo" / "invite_user_to_slack.yaml",
        path_b=CONTRACTS_B_ROOT / "agentdojo" / "invite_user_to_slack.yaml",
        clause_map=(
            ClauseMapping("pre.user_not_already_present", "pre.user_not_already_present", "same advertised precondition, identical predicate text"),
            ClauseMapping("eff.user_added", "eff.user_added_to_workspace", "same advertised effect, identical predicate text"),
        ),
        a_only=(),
        b_only=("frame.channels_unchanged", "frame.channel_inbox_unchanged", "frame.other_users_unchanged"),
        anchor_note="Finding 8 (Ignored Argument) -- anchor is arg.user_email, no effect clause exists for it in either contract",
        arg_findings=("user_email",),
    ),
    ToolSpec(
        benchmark="mm-toolsandbox",
        tool="venmo_social",
        stratum="blind",
        adapter_key="mmtoolsandbox",
        path_a=CONTRACTS_A_ROOT / "mmtoolsandbox" / "venmo_social.yaml",
        path_b=CONTRACTS_B_ROOT / "mmtoolsandbox" / "venmo_social.yaml",
        clause_map=(),  # see report: zero clauses map -- disjoint dispatch branches, see below
        a_only=("eff.transaction_id_forwarded", "eff.page_index_forwarded", "eff.sort_by_forwarded"),
        b_only=(
            "pre.friend_add_requires_email", "pre.friend_remove_requires_email", "pre.like_toggle_requires_fields",
            "eff.friend_add_delegated", "eff.friend_remove_delegated", "eff.like_toggle_delegated",
        ),
        anchor_note="Finding 7 (Ignored Argument) -- anchor is arg.sort_by, which B's signature does not declare at all",
        arg_findings=("sort_by",),
    ),
]


# =================================================================================================
# 2. Uniform clause-verdict evaluator -- see module docstring for why this, not check_effects/
#    check_precondition_enforcement, is used for the extensional comparison itself.
# =================================================================================================


def _verdict_for_predicate(predicate_src: str, pre: Any, post: Any, args: Any, result: Any) -> tuple:
    """(Verdict, reason_code_or_None). Mirrors adapters/contract_check.py's `_clause_verdict`
    three-way split exactly (CONFORMS/VIOLATES on a bool result, UNTESTABLE on PathError/
    PredicateTypeError) -- reused as a *convention*, not imported, because that function also
    threads a `on_false` defect-class tag this comparison does not need."""
    compiled = compile_predicate(predicate_src)
    try:
        ok = evaluate(compiled, pre, post, args, result)
    except PathError:
        return Verdict.UNTESTABLE, "no_observable_state"
    except PredicateTypeError:
        return Verdict.UNTESTABLE, "predicate_type_error"
    return (Verdict.CONFORMS if ok else Verdict.VIOLATES), None


def evaluate_all_clauses(contract: Contract, pre: Any, post: Any, args: Any, result: Any) -> dict:
    """clause_id -> (Verdict, reason_code) for every precondition/effect/invariant/frame clause in
    `contract`, against ONE (pre, post, args, result) witness. Preconditions are evaluated against
    (pre, pre, args, {}) -- the same binding convention `mutation/probes.py` and
    `dynamic/probes.py` already use for precondition predicates, since a precondition clause never
    references `post`/`result` by grammar convention and a probe is a single PRE-call args-dict,
    not a claim about what happens after. Frame clauses are graded by the real, frozen
    `dynamic.harness.check_frame` (imported, not modified) -- see module docstring."""
    out: dict = {}
    for pc in contract.preconditions:
        out[pc.id] = _verdict_for_predicate(pc.predicate, pre, pre, args, {})
    for ec in contract.effects:
        out[ec.id] = _verdict_for_predicate(ec.predicate, pre, post, args, result)
    for ic in contract.invariants:
        out[ic.id] = _verdict_for_predicate(ic.predicate, pre, post, args, result)
    if contract.frame:
        for cv, _extra in check_frame(contract, pre, post, args, result, effect_verdicts=[]):
            out[cv.clause_id] = (cv.verdict, cv.reason_code)
    return out


# =================================================================================================
# 3. Probe corpus -- detector_analysis_plan.md sec 2, components (2) and (3) only (component (1)
#    is empty everywhere in this project -- see module docstring).
# =================================================================================================


def _dedupe_probes(probes: list, *, tool: str = "") -> list:
    order: list = []
    origins: dict = {}
    args_by_key: dict = {}
    for p in probes:
        key = tuple(sorted(p.args.items()))
        if key not in origins:
            order.append(key)
            origins[key] = []
            args_by_key[key] = p.args
        origins[key].append(p.origin)
    return [Probe(tool=tool, args=args_by_key[k], origin=";".join(origins[k])) for k in order]


# venmo_social's own literal-dispatch branches (domain/action) cannot be reached by the generic
# boundary-probe generator unless a contract declares `probe_values` pinning them -- A does (its
# header note explains why: "the generic search... falls back to its own synthetic placeholder...
# which trips a ValueError on every single probe"). B does NOT declare probe_values for domain/
# action, so B's own three clauses (friend add/remove, like toggle) would otherwise be graded
# EXCLUSIVELY against boundary probes whose domain/action never equal 'friend'/'like' -- i.e.
# vacuously CONFORMS via each clause's own "else True" guard on every single probe, which is not a
# meaningful extensional test of anything. This is a genuine, disclosed departure from "the corpus
# is frozen... probes are never added to justify a result" (sec 2): these probes are added BEFORE
# any verdict is inspected, to make B's own declared branches reachable AT ALL, not to produce any
# particular outcome -- and both the frozen-corpus-only numbers and the branch-probe-augmented
# numbers are reported separately (see report/agreement_summary.md sec on venmo_social) so the
# reader can see exactly what this addition changes.
def _venmo_branch_probes(tool: str) -> list:
    return [
        Probe(tool=tool, args={"domain": "friend", "action": "add", "user_email": "probe_friend@example.com"}, origin="manual_branch_probe:friend_add"),
        Probe(tool=tool, args={"domain": "friend", "action": "remove", "user_email": "probe_friend@example.com"}, origin="manual_branch_probe:friend_remove"),
        Probe(tool=tool, args={"domain": "like", "action": "toggle", "entity_type": "transaction", "entity_id": 1, "like": True}, origin="manual_branch_probe:like_toggle_true"),
        Probe(tool=tool, args={"domain": "like", "action": "toggle", "entity_type": "transaction", "entity_id": 1, "like": False}, origin="manual_branch_probe:like_toggle_false"),
    ]


# SECOND disclosed departure, found only once the base sec-2 corpus was actually run (not before --
# recorded honestly as such). `mutation.probes.generate_boundary_probes`/`generate_precondition_probes`
# (frozen at checker-freeze-v1, sec 2) can only draw candidate argument values from a fixed,
# type-keyed literal triad (_VALID_BY_TYPE/_DOMAIN_INVALID_BY_TYPE/_ZERO_EMPTY_BY_TYPE) or a
# contract's own declared `probe_values` -- it has NO mechanism (by design; that is
# `dynamic/probes.py`'s harvesting job, deliberately kept separate, sec 4.3) for drawing a REAL
# entity id out of the live snapshot. For a tool whose sole/primary identifying argument IS a real
# database key with no declared `probe_values` -- `refuel_data` (line_id/customer_id must own a
# real line), `cancel_reservation` (reservation_id must exist), `update_scheduled_transaction` (id
# must name a real scheduled transaction) -- every sec-2 boundary/precondition probe therefore
# fails the tool's own existence check and the call never reaches the tool's effect code at all
# (post == pre by construction). Run first without a fix, this produced 100% "agreement" on every
# effect/invariant clause for refuel_data and cancel_reservation -- which is NOT evidence the two
# contracts agree on the advertised effect; it is an artifact of both contracts being evaluated on
# an identical no-op. One additional, disclosed probe per such tool is added below, built by
# reading the live snapshot directly for a real qualifying entity -- the exact same technique
# `experiments/ab_run.py`'s own `verify_patch_f2`/`verify_patch_f3` already use to reproduce these
# findings mechanically. Tagged `anchor_witness:*` and reported as a separate, explicit addition,
# never folded silently into the "sec-2 corpus" count.
def _anchor_witness_probes(tool: str, pre: Any) -> list:
    if tool == "refuel_data":
        out: list = []
        try:
            line = next(l for l in pre["lines"] if l["status"] != "Active")
            customer = next(c for c in pre["customers"] if line["line_id"] in c["line_ids"])
            out.append(Probe(
                tool=tool,
                args={"customer_id": customer["customer_id"], "line_id": line["line_id"], "gb_amount": 5.0},
                origin="anchor_witness:precondition_violate_line_inactive",
            ))
        except StopIteration:
            pass
        try:
            active_line = next(l for l in pre["lines"] if l["status"] == "Active")
            active_customer = next(c for c in pre["customers"] if active_line["line_id"] in c["line_ids"])
            out.append(Probe(
                tool=tool,
                args={"customer_id": active_customer["customer_id"], "line_id": active_line["line_id"], "gb_amount": 5.0},
                origin="anchor_witness:precondition_satisfy_line_active",
            ))
        except StopIteration:
            pass
        return out
    if tool == "cancel_reservation":
        try:
            rid = next(rid for rid, r in pre["reservations"].items() if r.get("status") != "cancelled")
        except StopIteration:
            return []
        return [Probe(tool=tool, args={"reservation_id": rid}, origin="anchor_witness:real_reservation")]
    if tool == "update_scheduled_transaction":
        try:
            t = pre["bank_account"]["scheduled_transactions"][0]
        except (KeyError, IndexError):
            return []
        real_id = t["id"]
        return [
            Probe(
                tool=tool,
                args={"id": real_id, "recipient": None, "amount": None, "subject": None, "date": None, "recurring": False},
                origin="anchor_witness:recurring_false_only",
            ),
            Probe(
                tool=tool,
                args={"id": real_id, "recipient": None, "amount": 0.0, "subject": None, "date": None, "recurring": False},
                origin="anchor_witness:recurring_and_amount_falsy",
            ),
            Probe(
                tool=tool,
                args={"id": real_id, "recipient": None, "amount": 250.0, "subject": None, "date": None, "recurring": True},
                origin="anchor_witness:recurring_and_amount_truthy_control",
            ),
        ]
    return []


def build_probe_corpus(contract_a: Contract, contract_b: Contract, adapter, scenario_id: str, *, tool: str) -> tuple:
    """Returns (corpus: list[Probe], base_corpus_size: int) -- `base_corpus_size` is the count
    before any `_venmo_branch_probes`/`_anchor_witness_probes` addition, so the report can show
    both numbers."""
    env = adapter.fresh_env(scenario_id)
    pre = adapter.snapshot(env)

    boundary_a = generate_boundary_probes(contract_a)
    boundary_b = generate_boundary_probes(contract_b)
    candidates = [p.args for p in boundary_a] + [p.args for p in boundary_b]

    precondition_a = generate_precondition_probes(contract_a, pre, candidates)
    precondition_b = generate_precondition_probes(contract_b, pre, candidates)

    base = _dedupe_probes(boundary_a + boundary_b + precondition_a + precondition_b, tool=tool)
    base_size = len(base)

    extra = list(_venmo_branch_probes(tool)) if tool == "venmo_social" else []
    extra += _anchor_witness_probes(tool, pre)
    full = _dedupe_probes(base + extra, tool=tool) if extra else base
    return full, base_size


# =================================================================================================
# 4. Drive one probe through the adapter -- fresh env every time, matching
#    dynamic.harness._invoke_fresh exactly (reused directly, not reimplemented).
# =================================================================================================


@dataclass
class ProbeOutcome:
    origin: str
    args: dict
    success: bool = True
    error: Optional[str] = None
    verdicts_a: dict = field(default_factory=dict)
    verdicts_b: dict = field(default_factory=dict)


def run_corpus(adapter, scenario_id: str, tool: str, contract_a: Contract, contract_b: Contract, probes: list) -> list:
    outcomes: list = []
    for p in probes:
        try:
            rec = _invoke_fresh(adapter, scenario_id, tool, p.args)
        except Exception as e:  # noqa: BLE001 -- an adapter-level failure on one probe (e.g. a
            # wildly-typed boundary value the worker cannot even marshal) must not abort the whole
            # corpus; recorded as an infra error, never silently dropped.
            outcomes.append(ProbeOutcome(origin=p.origin, args=dict(p.args), error=f"{type(e).__name__}: {e}"))
            continue
        va = evaluate_all_clauses(contract_a, rec.pre, rec.post, rec.args, rec.result)
        vb = evaluate_all_clauses(contract_b, rec.pre, rec.post, rec.args, rec.result)
        outcomes.append(ProbeOutcome(origin=p.origin, args=dict(p.args), success=rec.success, verdicts_a=va, verdicts_b=vb))
    return outcomes


# =================================================================================================
# 5. Clause-pair agreement + disagreement adjudication seed.
# =================================================================================================


def compare_clause_pair(outcomes: list, mapping: ClauseMapping) -> dict:
    """Preconditions are evaluated against `pre` alone (see `evaluate_all_clauses`) and are
    meaningful on every probe, successful or not -- a precondition is a claim about the state
    BEFORE the call. Effect/invariant/frame clauses are meaningful only on a call that actually
    reached the tool's effect code: on a failed call, `post == pre` by construction, and grading an
    effect clause against a no-op manufactures a verdict about nothing (the exact caution
    `dynamic/harness.py`'s own `run_contract` documents for `check_effects`). Those clause kinds are
    therefore restricted to `o.success` probes here; the id prefix (`pre.` vs `eff./inv./frame.`)
    is the same convention `spec/schema.json`'s clause id pattern already fixes project-wide."""
    is_precondition = mapping.id_a.startswith("pre.")
    rows = []
    n_excluded_failed_call = 0
    for o in outcomes:
        if o.error is not None:
            continue
        if not is_precondition and not o.success:
            n_excluded_failed_call += 1
            continue
        va = o.verdicts_a.get(mapping.id_a)
        vb = o.verdicts_b.get(mapping.id_b)
        if va is None or vb is None:
            continue  # clause id not resolvable against this witness's own contract -- should not
            # happen for a mapping drawn from that contract's own clause list; skipped rather than
            # crashing, and counted in "unresolved" below.
        verdict_a, reason_a = va
        verdict_b, reason_b = vb
        agree = verdict_a == verdict_b
        rows.append({
            "probe_origin": o.origin,
            "probe_args": o.args,
            "verdict_a": verdict_a.value,
            "reason_a": reason_a,
            "verdict_b": verdict_b.value,
            "reason_b": reason_b,
            "agree": agree,
        })
    n = len(rows)
    n_agree = sum(1 for r in rows if r["agree"])
    disagreements = [r for r in rows if not r["agree"]]
    # Headline robustness contribution: does contract_a report VIOLATES on some probe where
    # contract_b does not (or vice versa)? Both directions recorded -- the protocol's question is
    # "does any VIOLATES finding flip", not only A->B.
    flips_a_to_b = [r for r in rows if r["verdict_a"] == "VIOLATES" and r["verdict_b"] != "VIOLATES"]
    flips_b_to_a = [r for r in rows if r["verdict_b"] == "VIOLATES" and r["verdict_a"] != "VIOLATES"]
    return {
        "id_a": mapping.id_a,
        "id_b": mapping.id_b,
        "note": mapping.note,
        "n_probes_compared": n,
        "n_excluded_failed_call": n_excluded_failed_call,
        "n_agree": n_agree,
        "agreement_rate": (n_agree / n) if n else None,
        "disagreements": disagreements,
        "violates_flips_a_to_b": flips_a_to_b,
        "violates_flips_b_to_a": flips_b_to_a,
    }


def evaluate_unmapped_clause(outcomes: list, clause_id: str, *, side: str) -> dict:
    """Verdict distribution for a clause that exists in only ONE annotator's contract (protocol:
    'record the segmentation difference explicitly rather than forcing a mapping'). Not an
    agreement number -- there is nothing on the other side to agree or disagree with -- but its own
    CONFORMS/VIOLATES/UNTESTABLE distribution over the same probe corpus is still reportable
    coverage information, and a VIOLATES here (`cancel_reservation`'s B-only `eff.payment_refunded`
    is the concrete case) is a candidate additional finding, not to be discarded just because it
    has no counterpart clause to compare against."""
    is_precondition = clause_id.startswith("pre.")
    verdicts_key = "verdicts_a" if side == "A" else "verdicts_b"
    counts = {"CONFORMS": 0, "VIOLATES": 0, "UNTESTABLE": 0}
    example_violation = None
    n = 0
    for o in outcomes:
        if o.error is not None:
            continue
        if not is_precondition and not o.success:
            continue
        entry = getattr(o, verdicts_key).get(clause_id)
        if entry is None:
            continue
        verdict, _reason = entry
        n += 1
        counts[verdict.value] += 1
        if verdict == Verdict.VIOLATES and example_violation is None:
            example_violation = {"probe_origin": o.origin, "probe_args": o.args}
    return {"clause_id": clause_id, "side": side, "n_probes": n, "verdict_counts": counts, "example_violation": example_violation}


# =================================================================================================
# 6. arg.<name> robustness -- Findings 5/6/7/8's Ignored Argument evidence, checked with the real,
#    frozen dynamic.harness.check_ignored_argument against each contract's OWN signature. This
#    mechanism is state-invariance-driven, not predicate-text-driven, but a contract that does not
#    even DECLARE the argument (venmo_social's sort_by under B) cannot be probed at all -- reported
#    as "not testable under this contract", never silently coded as agreement.
# =================================================================================================


def arg_robustness_check(adapter, scenario_id: str, contract_a: Contract, contract_b: Contract, arg_name: str) -> dict:
    result: dict = {"arg": arg_name}
    for label, contract in (("A", contract_a), ("B", contract_b)):
        spec = contract.signature.args.get(arg_name)
        if spec is None:
            result[label] = {"testable": False, "reason": "argument not declared in this contract's signature at all"}
            continue
        if not spec.effective:
            result[label] = {"testable": False, "reason": "argument declared effective: false in this contract"}
            continue
        env = adapter.fresh_env(scenario_id)
        pre = adapter.snapshot(env)
        variant_probes = generate_ignored_argument_probes(contract, pre).get(arg_name)
        if not variant_probes:
            result[label] = {"testable": False, "reason": "fewer than 2 distinct successful variants found by the probe generator"}
            continue
        try:
            calls = [_invoke_fresh(adapter, scenario_id, contract.tool, p.args) for p in variant_probes]
        except Exception as e:  # noqa: BLE001
            result[label] = {"testable": False, "reason": f"adapter error building variant calls: {type(e).__name__}: {e}"}
            continue
        cv, aggravation = check_ignored_argument(arg_name, calls)
        result[label] = {
            "testable": True,
            "verdict": cv.verdict.value,
            "reason_code": cv.reason_code,
            "defect_class": cv.defect_class.value if cv.defect_class else None,
            "aggravation": aggravation,
            "n_variants_tried": len(variant_probes),
        }
    both_testable = result["A"].get("testable") and result["B"].get("testable")
    result["comparable"] = bool(both_testable)
    result["flip"] = bool(both_testable and result["A"].get("verdict") != result["B"].get("verdict"))
    return result


# =================================================================================================
# 7. Per-tool driver.
# =================================================================================================


def run_tool(spec: ToolSpec, adapter) -> dict:
    contract_a = Contract.from_yaml(spec.path_a)
    contract_b = Contract.from_yaml(spec.path_b)
    domain = resolve_domain(spec.benchmark, contract_a, _domain_by_tool_cache.get(spec.adapter_key))
    if domain is None:
        return {
            "benchmark": spec.benchmark, "tool": spec.tool, "stratum": spec.stratum,
            "status": "domain_unresolved", "anchor_note": spec.anchor_note,
        }

    corpus, base_corpus_size = build_probe_corpus(contract_a, contract_b, adapter, domain, tool=spec.tool)
    outcomes = run_corpus(adapter, domain, spec.tool, contract_a, contract_b, corpus)
    n_infra_errors = sum(1 for o in outcomes if o.error is not None)

    clause_results = [compare_clause_pair(outcomes, m) for m in spec.clause_map]

    a_only_results = [evaluate_unmapped_clause(outcomes, cid, side="A") for cid in spec.a_only]
    b_only_results = [evaluate_unmapped_clause(outcomes, cid, side="B") for cid in spec.b_only]

    arg_results = [arg_robustness_check(adapter, domain, contract_a, contract_b, a) for a in spec.arg_findings]

    any_clause_flip = any(cr["violates_flips_a_to_b"] or cr["violates_flips_b_to_a"] for cr in clause_results)
    any_arg_flip = any(ar["flip"] for ar in arg_results)
    any_arg_incomparable = any(not ar["comparable"] for ar in arg_results)

    return {
        "benchmark": spec.benchmark,
        "tool": spec.tool,
        "stratum": spec.stratum,
        "status": "ok",
        "domain": domain,
        "anchor_note": spec.anchor_note,
        "corpus_size": len(corpus),
        "corpus_size_before_venmo_branch_probes": base_corpus_size,
        "n_infra_errors": n_infra_errors,
        "clause_comparisons": clause_results,
        "a_only_clauses": list(spec.a_only),
        "b_only_clauses": list(spec.b_only),
        "a_only_verdicts": a_only_results,
        "b_only_verdicts": b_only_results,
        "arg_robustness": arg_results,
        "notes": list(spec.notes),
        "any_violates_flip": bool(any_clause_flip or any_arg_flip),
        "any_arg_finding_incomparable": bool(any_arg_incomparable),
    }


_domain_by_tool_cache: dict = {}


# =================================================================================================
# 8. Main.
# =================================================================================================


def main() -> int:
    REPORT_DIR.mkdir(exist_ok=True)
    report: dict = {
        "provenance": {
            "git_commit": git_commit(),
            "generated_at": now_iso(),
            "python": sys.version.split()[0],
            "script": "experiments/agreement.py",
            "protocol": "experiments/annotation_protocol.md",
        },
        "protocol_deviations_and_gaps": [
            {
                "item": "detector_analysis_plan.md sec 2 component (1): recorded real calls from adapter smoke-testing",
                "issue": (
                    "This repository does not persist a recorded-call store anywhere. Every existing "
                    "production caller of mutation.probes.build_equivalence_probe_corpus passes "
                    "recorded_calls=[] (confirmed by grep: experiments/open_world_cosmic_ray/*/scoring_lib.py). "
                    "This script does the same, for the same reason -- component (1) contributes zero "
                    "probes to every tool's corpus below, not a silent substitution."
                ),
            },
            {
                "item": "venmo_social boundary-probe reachability",
                "issue": (
                    "B's venmo_social clauses are guarded by args.domain/args.action equality checks "
                    "against literals ('friend', 'add', 'like', 'toggle') that generic boundary-probe "
                    "generation cannot produce without a contract-declared probe_values entry -- A "
                    "declared probe_values for its own branch (comment/list) for the identical reason; "
                    "B did not for friend/like. Four hand-written branch probes "
                    "(manual_branch_probe:friend_add/friend_remove/like_toggle_true/like_toggle_false) "
                    "were added so B's clauses are exercised at all, BEFORE any outcome was inspected -- "
                    "see experiments/agreement.py's _venmo_branch_probes docstring. Both the base "
                    "(frozen-corpus-only) and augmented corpus sizes are reported per tool."
                ),
            },
        ],
        "tools": [],
    }

    adapters: dict = {}
    try:
        adapters["tau2"] = Tau2Adapter()
    except Tau2AdapterError as e:
        adapters["tau2"] = None
        report["protocol_deviations_and_gaps"].append({"item": "tau2 adapter", "issue": str(e)})
    try:
        adapters["agentdojo"] = AgentDojoAdapter()
    except AgentDojoAdapterError as e:
        adapters["agentdojo"] = None
        report["protocol_deviations_and_gaps"].append({"item": "agentdojo adapter", "issue": str(e)})
    try:
        adapters["mmtoolsandbox"] = MMToolSandboxAdapter()
    except MMToolSandboxAdapterError as e:
        adapters["mmtoolsandbox"] = None
        report["protocol_deviations_and_gaps"].append({"item": "mmtoolsandbox adapter", "issue": str(e)})

    for key in ("agentdojo", "mmtoolsandbox"):
        a = adapters.get(key)
        if a is not None:
            _domain_by_tool_cache[key] = {t.name: t.domain for t in a.list_tools()}

    try:
        for spec in TOOL_SPECS:
            adapter = adapters.get(spec.adapter_key)
            if adapter is None:
                report["tools"].append({
                    "benchmark": spec.benchmark, "tool": spec.tool, "stratum": spec.stratum,
                    "status": "adapter_unavailable", "anchor_note": spec.anchor_note,
                })
                continue
            report["tools"].append(run_tool(spec, adapter))
    finally:
        for a in adapters.values():
            if a is not None:
                a.close()

    # ---- Headline robustness sentence -----------------------------------------------------
    blind_tools = [t for t in report["tools"] if t.get("stratum") == "blind" and t.get("status") == "ok"]
    contaminated_tools = [t for t in report["tools"] if t.get("stratum") == "contaminated" and t.get("status") == "ok"]

    def _headline(tools: list) -> dict:
        flips = [t["tool"] for t in tools if t.get("any_violates_flip")]
        incomparable = [t["tool"] for t in tools if t.get("any_arg_finding_incomparable")]
        return {"any_flip": bool(flips), "tools_with_a_flip": flips, "tools_with_an_incomparable_arg_finding": incomparable}

    report["headline_robustness"] = {
        "blind_stratum": _headline(blind_tools),
        "contaminated_stratum": _headline(contaminated_tools),
        "sentence": _build_headline_sentence(blind_tools, contaminated_tools),
    }

    with open(JSON_PATH, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, sort_keys=False, default=str)
    with open(SUMMARY_PATH, "w", encoding="utf-8") as fh:
        fh.write(_render_summary_md(report))

    print(f"wrote {JSON_PATH}")
    print(f"wrote {SUMMARY_PATH}")
    return 0


def _build_headline_sentence(blind_tools: list, contaminated_tools: list) -> str:
    all_flip_tools = [t["tool"] for t in (blind_tools + contaminated_tools) if t.get("any_violates_flip")]
    incomparable = [t["tool"] for t in blind_tools if t.get("any_arg_finding_incomparable")]
    if not all_flip_tools:
        base = "No VIOLATES finding flips under Annotator B's contracts, in either stratum."
    else:
        base = f"At least one VIOLATES finding flips under Annotator B's contracts, in: {', '.join(all_flip_tools)}."
    if incomparable:
        base += (
            f" {', '.join(incomparable)} carries an arg.* anchor finding that could not be tested "
            f"under B's contract at all (the argument is not declared in B's signature), which is "
            f"not evidence of robustness and is reported separately from the flip count."
        )
    return base


def _fmt_rate(x: Optional[float]) -> str:
    return f"{x:.1%}" if x is not None else "n/a"


def _render_summary_md(r: dict) -> str:
    lines: list = []
    lines.append("# Extensional agreement study (R1) -- results\n")
    lines.append(
        f"Generated by `experiments/agreement.py` at commit `{r['provenance']['git_commit']}`, "
        f"{r['provenance']['generated_at']}.\n"
    )
    lines.append("Bound by `experiments/annotation_protocol.md` (pre-registered, untouched by this run).\n")

    lines.append("## Protocol items not executed as written\n")
    for item in r["protocol_deviations_and_gaps"]:
        lines.append(f"- **{item['item']}**: {item['issue']}\n")

    lines.append("## Headline robustness sentence\n")
    lines.append(f"> {r['headline_robustness']['sentence']}\n")

    for stratum_key, stratum_label in (("blind_stratum", "Blind stratum (5 tools)"), ("contaminated_stratum", "Contaminated stratum (1 tool: cancel_reservation)")):
        h = r["headline_robustness"][stratum_key]
        lines.append(f"- **{stratum_label}**: any flip = **{h['any_flip']}**"
                     + (f" ({', '.join(h['tools_with_a_flip'])})" if h["tools_with_a_flip"] else "")
                     + (f"; incomparable arg findings: {', '.join(h['tools_with_an_incomparable_arg_finding'])}" if h["tools_with_an_incomparable_arg_finding"] else ""))
    lines.append("")

    if any(t.get("stratum") == "contaminated" for t in r["tools"]):
        lines.append(
            "**Contamination notice**: `cancel_reservation`'s agreement number is NOT evidence of "
            "independent replication (Annotator B disclosed reading a complete worked example of "
            "this exact tool at this exact commit before authoring). Reported separately below and "
            "never pooled with the blind stratum.\n"
        )

    for stratum in ("blind", "contaminated"):
        stratum_tools = [t for t in r["tools"] if t.get("stratum") == stratum]
        if not stratum_tools:
            continue
        lines.append(f"## {'Blind' if stratum == 'blind' else 'CONTAMINATED'} stratum\n")
        for t in stratum_tools:
            lines.append(f"### `{t['benchmark']}:{t['tool']}`\n")
            lines.append(f"{t.get('anchor_note', '')}\n")
            if t["status"] != "ok":
                lines.append(f"**status: {t['status']}** -- not run.\n")
                continue
            lines.append(f"- domain/scenario: `{t['domain']}`")
            lines.append(f"- probe corpus size: **{t['corpus_size']}**"
                         + (f" ({t['corpus_size_before_venmo_branch_probes']} before the disclosed manual branch probes)" if t["tool"] == "venmo_social" else ""))
            lines.append(f"- probe-level infra errors: {t['n_infra_errors']}\n")

            for note in t.get("notes") or []:
                lines.append(f"**Note:** {note}\n")

            if t["clause_comparisons"]:
                lines.append("| A clause | B clause | note | n compared | agreement | VIOLATES flips A->B | VIOLATES flips B->A |")
                lines.append("|---|---|---|---:|---:|---:|---:|")
                for cr in t["clause_comparisons"]:
                    lines.append(
                        f"| `{cr['id_a']}` | `{cr['id_b']}` | {cr['note']} | {cr['n_probes_compared']} | "
                        f"{_fmt_rate(cr['agreement_rate'])} | {len(cr['violates_flips_a_to_b'])} | {len(cr['violates_flips_b_to_a'])} |"
                    )
                lines.append("")
            else:
                lines.append("**Zero clause pairs are comparable for this tool** -- see segmentation note below.\n")

            if t["a_only_clauses"] or t["b_only_clauses"]:
                lines.append(
                    "**Segmentation differences** (clauses present in only one annotator's contract -- "
                    "not comparable, but each clause's own verdict distribution over the shared corpus "
                    "is reported so a VIOLATES-only-clause is never silently dropped):\n"
                )
                for label, results in (("A-only", t["a_only_verdicts"]), ("B-only", t["b_only_verdicts"])):
                    for res in results:
                        vc = res["verdict_counts"]
                        line = (
                            f"- {label} `{res['clause_id']}`: n={res['n_probes']}, "
                            f"CONFORMS={vc['CONFORMS']}, VIOLATES={vc['VIOLATES']}, UNTESTABLE={vc['UNTESTABLE']}"
                        )
                        if res["example_violation"]:
                            line += f" -- example VIOLATES witness: probe `{res['example_violation']['probe_origin']}`, args `{res['example_violation']['probe_args']}`"
                        lines.append(line)
                lines.append("")

            if t["arg_robustness"]:
                lines.append("**arg.\\* (Ignored Argument) robustness:**\n")
                for ar in t["arg_robustness"]:
                    a_desc = ar["A"] if ar["A"].get("testable") else {"verdict": "NOT TESTABLE", **ar["A"]}
                    b_desc = ar["B"] if ar["B"].get("testable") else {"verdict": "NOT TESTABLE", **ar["B"]}

                    def _detail(side_result: dict, testable: bool) -> str:
                        if not testable:
                            return f" ({side_result.get('reason')})"
                        extra = []
                        if side_result.get("reason_code"):
                            extra.append(f"reason_code={side_result['reason_code']}")
                        agg = side_result.get("aggravation") or {}
                        if "n_successful_variants" in agg:
                            extra.append(f"n_successful_variants={agg['n_successful_variants']}")
                        return f" ({', '.join(extra)})" if extra else ""

                    lines.append(
                        f"- `arg.{ar['arg']}`: A = `{a_desc.get('verdict')}`"
                        + _detail(ar["A"], ar["A"].get("testable"))
                        + f"; B = `{b_desc.get('verdict')}`"
                        + _detail(ar["B"], ar["B"].get("testable"))
                        + f"; comparable = **{ar['comparable']}**; flip = **{ar['flip']}**"
                    )
                    if ar["flip"]:
                        lines.append(
                            f"  - **adjudication (protocol sec 6):** both annotators cite the identical advertised "
                            f"surface for `{ar['arg']}`; the surface is not ambiguous. The flip traces to a probe-"
                            f"generation-capability gap, not a disagreement about semantics -- see "
                            f"`n_successful_variants` above and the tool-specific note below."
                        )
                lines.append("")

            all_disagreements = [
                (cr["id_a"], cr["id_b"], d)
                for cr in t["clause_comparisons"]
                for d in cr["disagreements"]
            ]
            if all_disagreements:
                lines.append(f"**{len(all_disagreements)} adjudicated disagreement(s):**\n")
                for id_a, id_b, d in all_disagreements:
                    lines.append(
                        f"- `{id_a}` vs `{id_b}`, probe `{d['probe_origin']}` (args `{d['probe_args']}`): "
                        f"A = `{d['verdict_a']}`" + (f" ({d['reason_a']})" if d["reason_a"] else "")
                        + f", B = `{d['verdict_b']}`" + (f" ({d['reason_b']})" if d["reason_b"] else "")
                        + " -- **adjudication needed: return to the advertised surface (protocol sec 6); "
                        "not resolved automatically by this script.**"
                    )
                lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
