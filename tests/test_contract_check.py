"""Tests for adapters/contract_check.py's reason_code mapping -- specifically the
PredicateTypeError -> predicate_type_error UNTESTABLE mapping (core/predicates.py's fix for the
TypeError-misreported-as-PathError bug: a TypeError on a path that resolved perfectly used to be
folded into PathError and reported as UNTESTABLE/no_observable_state, which would silently turn
a real VIOLATES into an untestable clause). Uses the real shipped toy/deposit.yaml contract
rather than a synthetic one, since the bug's whole point is that it can happen on a real
contract's real effect clause with no compile-time warning.

Run with: python -m unittest discover tests
"""
import unittest
from pathlib import Path

from adapters.contract_check import check_effects, check_precondition_enforcement
from core.model import Contract
from core.verdict import DefectClass, Verdict

CONTRACTS_DIR = Path(__file__).resolve().parent.parent / "spec" / "contracts" / "toy"
TAU2_CONTRACTS_DIR = Path(__file__).resolve().parent.parent / "spec" / "contracts" / "tau2"


class TestPredicateTypeErrorMapping(unittest.TestCase):
    def setUp(self):
        self.contract = Contract.from_yaml(CONTRACTS_DIR / "deposit.yaml")

    def test_type_error_on_resolved_path_is_untestable_with_its_own_reason_code(self):
        # `balance` resolves on both sides -- the path is fine -- but it is None, so
        # `post...balance == pre...balance + args.amount` raises TypeError on `None + 10.0`, not
        # a path failure. Before the fix this was misreported as UNTESTABLE/no_observable_state,
        # identically to a genuinely missing path; now it gets its own reason code.
        pre = {"accounts": {"acc_alice": {"balance": None, "frozen": False, "owner": "alice"}}}
        post = {"accounts": {"acc_alice": {"balance": None, "frozen": False, "owner": "alice"}}}
        args = {"account_id": "acc_alice", "amount": 10.0}
        result = {"account_id": "acc_alice", "balance": None}
        verdicts = check_effects(self.contract, pre, post, args, result)
        balance_verdict = next(v for v in verdicts if v.clause_id == "eff.balance_increased")
        self.assertEqual(balance_verdict.verdict, Verdict.UNTESTABLE)
        self.assertEqual(balance_verdict.reason_code, "predicate_type_error")

    def test_missing_path_is_still_no_observable_state_not_predicate_type_error(self):
        # Genuine path failure (KeyError, account does not exist) must still map to the
        # pre-existing reason code, kept separate and distinguishable from predicate_type_error.
        pre = {"accounts": {}}
        post = {"accounts": {}}
        args = {"account_id": "no_such_account", "amount": 10.0}
        result = {"account_id": "no_such_account", "balance": 10.0}
        verdicts = check_effects(self.contract, pre, post, args, result)
        balance_verdict = next(v for v in verdicts if v.clause_id == "eff.balance_increased")
        self.assertEqual(balance_verdict.verdict, Verdict.UNTESTABLE)
        self.assertEqual(balance_verdict.reason_code, "no_observable_state")

    def test_genuine_violation_on_a_resolved_numeric_path_still_reports_violates(self):
        # Sanity check the fix did not disturb the ordinary numeric-comparison path: a real
        # mismatch on fully-resolved, well-typed values is still VIOLATES, not UNTESTABLE.
        pre = {"accounts": {"acc_alice": {"balance": 10.0, "frozen": False, "owner": "alice"}}}
        post = {"accounts": {"acc_alice": {"balance": 10.0, "frozen": False, "owner": "alice"}}}
        args = {"account_id": "acc_alice", "amount": 10.0}
        result = {"account_id": "acc_alice", "balance": 10.0}
        verdicts = check_effects(self.contract, pre, post, args, result)
        balance_verdict = next(v for v in verdicts if v.clause_id == "eff.balance_increased")
        self.assertEqual(balance_verdict.verdict, Verdict.VIOLATES)


class TestErrorTypeEnforcement(unittest.TestCase):
    """GAP 2 (CLAUDE.md): `on_precondition_violation.expect.error_type` was parsed
    (core/model.py's `PreconditionViolationExpectation.error_type`) and schema-validated, but
    `check_precondition_enforcement` only ever tested `error_signal` and `state_delta` -- a tool
    that raised the WRONG exception type still reported CONFORMS as long as it raised something
    and left no delta. 23 shipped contracts declare `error_type`; `refuel_data.yaml` (tau2-bench
    telecom, FINDINGS-VERIFIED.md Finding 2's contract) declares `error_type: ValueError` and is
    used here as a real shipped fixture rather than a synthetic one."""

    def setUp(self):
        self.contract = Contract.from_yaml(TAU2_CONTRACTS_DIR / "refuel_data.yaml")
        # pre.line_active is violated (line L1 is Suspended, not Active); pre.customer_owns_line
        # references pre.customers, which this minimal fixture omits on purpose -- it raises
        # PathError and is skipped by check_precondition_enforcement's own per-clause guard, so
        # only pre.line_active is ever in play here. post == pre: a well-behaved reject leaves no
        # delta, matching state_delta: none.
        self.pre = {"lines": [{"line_id": "L1", "status": "Suspended"}]}
        self.post = {"lines": [{"line_id": "L1", "status": "Suspended"}]}
        self.args = {"customer_id": "C1", "line_id": "L1", "gb_amount": 5.0}

    def test_matching_error_type_conforms(self):
        cv = check_precondition_enforcement(
            self.contract, self.pre, self.post, self.args,
            result={"error": "ValueError: Line must be active to refuel data"},
            error="ValueError: Line must be active to refuel data",
        )
        self.assertIsNotNone(cv)
        self.assertEqual(cv.verdict, Verdict.CONFORMS)
        self.assertEqual(cv.clause_id, "pre.line_active")

    def test_wrong_error_type_is_flagged_unenforced_precondition(self):
        # The call DID raise, and DID leave no delta -- both of the previously-checked conditions
        # are satisfied. Only the exception's TYPE is wrong (a KeyError, not the docstring's
        # advertised ValueError). Before this fix this case reported CONFORMS.
        cv = check_precondition_enforcement(
            self.contract, self.pre, self.post, self.args,
            result={"error": "KeyError: 'L1'"},
            error="KeyError: 'L1'",
        )
        self.assertIsNotNone(cv)
        self.assertEqual(cv.verdict, Verdict.VIOLATES)
        self.assertEqual(cv.defect_class, DefectClass.UNENFORCED_PRECONDITION)
        self.assertEqual(cv.clause_id, "pre.line_active")

    def test_error_type_check_is_skipped_when_the_call_did_not_signal_an_error_at_all(self):
        # error is None (no exception raised); expect.error_signal already fails this
        # independently -- the error_type comparison must not crash on error.split(...) when
        # error is None.
        cv = check_precondition_enforcement(
            self.contract, self.pre, self.post, self.args, result={"ok": True}, error=None,
        )
        self.assertIsNotNone(cv)
        self.assertEqual(cv.verdict, Verdict.VIOLATES)
        self.assertEqual(cv.defect_class, DefectClass.UNENFORCED_PRECONDITION)

    def test_contract_without_declared_error_type_is_unaffected(self):
        # toy/deposit.yaml's on_precondition_violation has no error_type at all -- the added
        # check must be a pure no-op for every contract that never opted into it (23 of the
        # shipped contracts declare error_type; the rest, including every toy contract, do not).
        contract = Contract.from_yaml(CONTRACTS_DIR / "deposit.yaml")
        self.assertIsNone(contract.on_precondition_violation.expect.error_type)
        pre = {"accounts": {}}
        post = {"accounts": {}}
        args = {"account_id": "no_such_account", "amount": 10.0}
        cv = check_precondition_enforcement(
            contract, pre, post, args, result={"error": "unknown account"}, error="unknown account",
        )
        self.assertIsNotNone(cv)
        self.assertEqual(cv.verdict, Verdict.CONFORMS)


if __name__ == "__main__":
    unittest.main()
