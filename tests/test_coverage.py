"""Tests for spec/coverage.py against the two real, human-authored tau2 contracts.

These pin down the numbers reported in this build's final report so a future change to either
the contracts or the coverage logic shows up as a failing test rather than a silently drifting
number. Run with: python -m unittest discover tests
"""
import unittest
from pathlib import Path

from core.model import Contract
from spec.coverage import biconditional_adoption, sentence_coverage, state_write_coverage

REPO_ROOT = Path(__file__).resolve().parent.parent
TAU2_SRC_ROOT = REPO_ROOT / ".tau2-src-c3398666"
CONTRACTS_DIR = REPO_ROOT / "spec" / "contracts" / "tau2"


@unittest.skipUnless(TAU2_SRC_ROOT.exists(), "durable tau2 source copy not present")
class TestCoverageAgainstRealContracts(unittest.TestCase):
    def _load(self, name: str) -> tuple[Contract, str]:
        contract = Contract.from_yaml(CONTRACTS_DIR / name)
        source_text = (TAU2_SRC_ROOT / contract.source.file).read_text(encoding="utf-8")
        return contract, source_text

    def test_refuel_data_sentence_coverage(self):
        contract, text = self._load("refuel_data.yaml")
        r = sentence_coverage(contract, text)
        self.assertEqual(r["sentence_total"], 6)
        self.assertEqual(r["sentence_operationalized"], 5)
        # the one uncovered unit is the generic summary sentence, not double-counted against the
        # Checks:/Logic: lines that already operationalize the same information
        self.assertEqual(len(r["uncovered"]), 1)
        self.assertEqual(r["uncovered"][0]["kind"], "summary")

    def test_refuel_data_state_write_coverage(self):
        contract, text = self._load("refuel_data.yaml")
        r = state_write_coverage(contract, text)
        self.assertEqual(r["state_write_total"], r["state_write_covered"])  # fully covered

    def test_refuel_data_biconditional_not_adopted(self):
        contract, _text = self._load("refuel_data.yaml")
        self.assertFalse(biconditional_adoption(contract)["biconditional"])

    def test_cancel_reservation_biconditional_adopted_with_justification(self):
        contract, _text = self._load("cancel_reservation.yaml")
        b = biconditional_adoption(contract)
        self.assertTrue(b["biconditional"])
        self.assertTrue(b["justification"])

    def test_cancel_reservation_state_write_partial(self):
        contract, text = self._load("cancel_reservation.yaml")
        r = state_write_coverage(contract, text)
        uncovered_fields = {u["field"] for u in r["uncovered"]}
        self.assertIn("payment_history", uncovered_fields)  # no clause mentions the refund write


if __name__ == "__main__":
    unittest.main()
