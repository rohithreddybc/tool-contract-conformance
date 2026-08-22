"""Gate 1a and Gate 1b for the tau2-bench adapter. Run with: python -m unittest discover tests

Gate 1a (CLAUDE.md): one complete fresh_env -> snapshot -> invoke -> snapshot -> reset ->
snapshot cycle on airline, with the diff between the two post-invoke snapshots non-empty for a
mutating call and the post-reset snapshot equal to the initial one.

Gate 1b (CLAUDE.md): Findings 2 and 3 (FINDINGS-VERIFIED.md) rediscovered THROUGH THE ADAPTER,
using the existing cancel_reservation contract and the new refuel_data contract, with both
detected by evaluating contract clauses against real pre/post snapshots -- never by a
hard-coded assertion about either specific tool. adapters/contract_check.py is the generic
(tool-agnostic) clause evaluator that makes this possible; these tests differ from each other
only in which contract file and which probe args they supply.

Skipped in full (both classes) if adapters.tau2.Tau2Adapter can't find a provisioned tau2
virtualenv -- see adapters/tau2.py's module docstring for how to provision one. This keeps
`python -m unittest discover tests` clean on a machine that hasn't set up .venv-tau2, without
silently asserting Gate 1a/1b passed.
"""
import unittest
from pathlib import Path

from adapters.contract_check import check_effects, check_precondition_enforcement, to_result_binding
from adapters.tau2 import Tau2Adapter, Tau2AdapterError
from core.canonical import diff
from core.model import Contract
from core.verdict import DefectClass, Verdict

CONTRACTS_DIR = Path(__file__).resolve().parent.parent / "spec" / "contracts" / "tau2"


def _new_adapter_or_skip() -> Tau2Adapter:
    try:
        adapter = Tau2Adapter()
    except Tau2AdapterError as e:
        raise unittest.SkipTest(f"tau2 adapter venv not provisioned: {e}")
    try:
        adapter._send({"cmd": "ping"})  # fail fast if the worker can't even boot
    except Tau2AdapterError as e:
        adapter.close()
        raise unittest.SkipTest(f"tau2 worker did not start: {e}")
    return adapter


class TestTau2AdapterGate1a(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.adapter = _new_adapter_or_skip()

    @classmethod
    def tearDownClass(cls):
        cls.adapter.close()

    def test_list_tools_mutating_counts_match_expectation(self):
        tools = self.adapter.list_tools()
        by_domain: dict[str, int] = {}
        for t in tools:
            if t.mutates_state:
                by_domain[t.domain] = by_domain.get(t.domain, 0) + 1

        # ARCHITECTURE-FINAL.md sec 2 / CLAUDE.md: 19 mutating tools across airline+retail+telecom,
        # counted by mutates_state -- NOT the ToolType.WRITE tag (environment/toolkit.py:64-90 is
        # explicit that these can diverge). Grepped directly against the pinned checkout: none of
        # the three in-scope domains' tools.py declares an explicit mutates_state= override, so for
        # THESE three domains the WRITE-tag count and the mutates_state count happen to coincide --
        # unlike banking_knowledge, which is why CLAUDE.md asks for this to be checked rather than
        # assumed. Per-domain actual counts, so a future discrepancy is visible immediately rather
        # than hidden behind a bare total:
        self.assertEqual(by_domain, {"airline": 6, "retail": 7, "telecom": 6})
        self.assertEqual(sum(by_domain.values()), 19)

    def test_gate_1a_cycle_on_airline(self):
        env = self.adapter.fresh_env("airline")
        pre = self.adapter.snapshot(env)

        reservation_id = next(
            rid for rid, r in pre["reservations"].items() if r.get("status") != "cancelled"
        )
        result = self.adapter.invoke(env, "cancel_reservation", {"reservation_id": reservation_id})
        self.assertTrue(result.success, result.error)

        post = self.adapter.snapshot(env)
        delta = diff(pre, post)
        self.assertNotEqual(delta, {}, "cancel_reservation mutates state; the diff must be non-empty")

        self.adapter.reset(env)
        post_reset = self.adapter.snapshot(env)
        self.assertEqual(diff(pre, post_reset), {}, "reset must restore exactly the initial snapshot")
        self.assertEqual(post_reset, pre)

    def test_source_resolves_and_disambiguates(self):
        # src/tau2/domains/airline/tools.py:338-368 at c3398666 -- matches the corrected
        # cancel_reservation.yaml `source:` block exactly (spec/PREDICATE-GRAMMAR.md sec 5).
        src = self.adapter.source("airline:cancel_reservation")
        self.assertEqual(src.file, "src/tau2/domains/airline/tools.py")
        self.assertEqual(src.start_line, 338)
        self.assertEqual(src.end_line, 368)

        # Several tool names recur across domains (e.g. transfer_to_human_agents); a bare name
        # must raise rather than silently pick one.
        with self.assertRaises(Tau2AdapterError):
            self.adapter.source("transfer_to_human_agents")


class TestTau2AdapterGate1b(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.adapter = _new_adapter_or_skip()

    @classmethod
    def tearDownClass(cls):
        cls.adapter.close()

    def test_finding_3_partial_effect_on_cancel_reservation(self):
        """FINDINGS-VERIFIED.md Finding 3: cancelling a reservation marks it cancelled but never
        releases the seats it held. Detected here by evaluating BOTH effect clauses of the
        existing cancel_reservation.yaml contract against a real pre/post snapshot pair -- the
        test asserts on clause verdicts, never on `available_seats` or `status` directly."""
        contract = Contract.from_yaml(CONTRACTS_DIR / "cancel_reservation.yaml")

        env = self.adapter.fresh_env("airline")
        pre = self.adapter.snapshot(env)
        reservation_id = next(
            rid for rid, r in pre["reservations"].items() if r.get("status") != "cancelled"
        )
        args = {"reservation_id": reservation_id}

        tr = self.adapter.invoke(env, "cancel_reservation", args)
        self.assertTrue(tr.success, tr.error)
        post = self.adapter.snapshot(env)
        result = to_result_binding(tr.raw, tr.success, tr.error)

        verdicts = {v.clause_id: v for v in check_effects(contract, pre, post, args, result)}

        self.assertEqual(verdicts["eff.status_cancelled"].verdict, Verdict.CONFORMS)

        seats = verdicts["eff.seats_released"]
        self.assertEqual(seats.verdict, Verdict.VIOLATES)
        self.assertEqual(seats.defect_class, DefectClass.PARTIAL_EFFECT)
        self.assertIsNotNone(seats.witness)
        self.assertNotEqual(seats.witness.diff, {})

    def test_finding_2_unenforced_precondition_on_refuel_data(self):
        """FINDINGS-VERIFIED.md Finding 2: refuel_data's docstring declares an Active-line
        precondition (tools.py:613) whose enforcing branch is commented out (629-630). Detected
        here by evaluating refuel_data.yaml's declared preconditions against a real call that
        deliberately targets a non-Active line, and comparing the contract's own
        on_precondition_violation expectation to what actually happened -- never by asserting on
        LineStatus or data_refueling_gb directly."""
        contract = Contract.from_yaml(CONTRACTS_DIR / "refuel_data.yaml")

        env = self.adapter.fresh_env("telecom")
        pre = self.adapter.snapshot(env)
        line = next(l for l in pre["lines"] if l["status"] != "Active")
        customer = next(c for c in pre["customers"] if line["line_id"] in c["line_ids"])
        args = {"customer_id": customer["customer_id"], "line_id": line["line_id"], "gb_amount": 5.0}

        tr = self.adapter.invoke(env, "refuel_data", args)
        post = self.adapter.snapshot(env)
        result = to_result_binding(tr.raw, tr.success, tr.error)

        verdict = check_precondition_enforcement(contract, pre, post, args, result, tr.error)

        self.assertIsNotNone(
            verdict, "probing a non-Active line must violate a declared precondition of refuel_data.yaml"
        )
        self.assertEqual(verdict.clause_id, "pre.line_active")
        self.assertEqual(verdict.verdict, Verdict.VIOLATES)
        self.assertEqual(verdict.defect_class, DefectClass.UNENFORCED_PRECONDITION)
        self.assertNotEqual(verdict.witness.diff, {})

        # The defect is a SELECTIVE omission (CLAUDE.md): the call neither raises nor is a
        # no-op -- both halves of the contract's on_precondition_violation.expect are violated
        # by the real implementation, which is exactly what the VIOLATES verdict above encodes.
        self.assertTrue(tr.success, "refuel_data does not actually raise on a non-Active line -- that is the defect")


if __name__ == "__main__":
    unittest.main()
