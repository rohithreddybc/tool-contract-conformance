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

from adapters.contract_check import check_effects
from core.model import Contract
from core.verdict import Verdict

CONTRACTS_DIR = Path(__file__).resolve().parent.parent / "spec" / "contracts" / "toy"


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


if __name__ == "__main__":
    unittest.main()
