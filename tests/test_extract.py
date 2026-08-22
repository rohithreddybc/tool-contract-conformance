"""Tests for static_check/extract.py.

Synthetic-snippet tests isolate the grounding-tier and review-marking guarantees without a repo
dependency. The real-source tests confirm the two guarantees the build spec calls out by name:
(1) drafted output validates against spec/schema.json and every check spec/validate.py runs
(where check4/check8 need a --repo-root, exercised directly here rather than through the CLI),
and (2) a maintainer-only annotation (a logger.warning, never returned or raised) is never
drafted as tool_return -- reproducing the exact trap PREDICATE-GRAMMAR.md sec 5 documents against
its own first draft (cancel_reservation's "Seats release not implemented" log line).

Run with: python -m unittest discover tests
"""
import json
import unittest
from pathlib import Path

import jsonschema
import yaml

from static_check.extract import draft_contract

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "spec" / "schema.json"
TAU2_SRC = REPO_ROOT / ".tau2-src-c3398666" / "src" / "tau2" / "domains"
AGENTDOJO_SRC = REPO_ROOT / "repos" / "agentdojo" / "src" / "agentdojo" / "default_suites" / "v1" / "tools"

with open(SCHEMA_PATH, "r", encoding="utf-8") as _fh:
    SCHEMA = json.load(_fh)


def _validate_against_schema(doc: dict) -> list[str]:
    validator = jsonschema.Draft202012Validator(SCHEMA)
    return [e.message for e in validator.iter_errors(doc)]


class TestDraftMarking(unittest.TestCase):
    """Synthetic source: every drafted clause must be inferred:true and id-suffixed _draft, and
    the contract must validate, regardless of which repo it came from."""

    SRC = (
        "class Widget:\n"
        "    def do_thing(self, amount: float, note: str) -> dict:\n"
        "        '''\n"
        "        Applies a thing.\n"
        "        Checks: amount must be positive, note must not be empty.\n"
        "\n"
        "        Args:\n"
        "            amount: how much to apply.\n"
        "            note: a note.\n"
        "\n"
        "        Raises:\n"
        "            ValueError: If amount is not positive.\n"
        "        '''\n"
        "        if amount <= 0:\n"
        "            raise ValueError('amount must be positive')\n"
        "        self.total += amount\n"
        "        return {'message': f'applied {amount}'}\n"
    )

    def setUp(self):
        self.contract = draft_contract(
            source_text=self.SRC,
            file_path="widget.py",
            qualname="Widget.do_thing",
            benchmark="synthetic",
            commit="0123456",
        )

    def test_validates_against_schema(self):
        errors = _validate_against_schema(self.contract)
        self.assertEqual(errors, [], f"schema errors: {errors}")

    def test_every_clause_is_inferred_and_draft_suffixed(self):
        clauses = list(self.contract.get("preconditions", [])) + list(self.contract.get("effects", []))
        self.assertGreater(len(clauses), 0)
        for c in clauses:
            self.assertTrue(c["inferred"], f"{c['id']} must be inferred:true")
            self.assertTrue(c["id"].endswith("_draft"), f"{c['id']} must be _draft-suffixed")

    def test_predicates_are_placeholder_true_and_compile(self):
        from core.predicates import compile_predicate

        clauses = list(self.contract.get("preconditions", [])) + list(self.contract.get("effects", []))
        for c in clauses:
            self.assertEqual(c["predicate"], "True")
            compile_predicate(c["predicate"])  # must not raise

    def test_biconditional_is_never_auto_set(self):
        ss = self.contract.get("success_signal")
        self.assertIsNotNone(ss)
        self.assertFalse(ss.get("biconditional", False))

    def test_contract_notes_flag_it_as_a_draft(self):
        self.assertIn("AUTO-DRAFTED", self.contract["notes"])
        self.assertIn("NOT headline-eligible", self.contract["notes"])

    def test_precondition_from_checks_label_splits_on_comma(self):
        texts = {c["text"] for c in self.contract["preconditions"]}
        self.assertIn("amount must be positive", texts)
        self.assertIn("note must not be empty", texts)

    def test_signature_args_carry_docstring_provenance(self):
        args = self.contract["signature"]["args"]
        self.assertEqual(args["amount"]["type"], "float")
        self.assertIn("provenance", args["amount"])
        self.assertEqual(args["amount"]["provenance"]["surface"], "docstring")


class TestGroundingTierFromBody(unittest.TestCase):
    def test_return_value_is_tool_return(self):
        src = (
            "def f(x):\n"
            "    return {'message': f'did {x}'}\n"
        )
        contract = draft_contract(source_text=src, file_path="f.py", qualname="f", benchmark="s", commit="0000000")
        body_effects = [e for e in contract.get("effects", []) if e["provenance"]["surface"] == "tool_return"]
        self.assertEqual(len(body_effects), 1)

    def test_logger_message_is_never_drafted_as_tool_return(self):
        # a message that only ever appears inside logger.warning(...) is not reachable from
        # `_string_value_expressions` (which only walks Return/Raise) -- it must not appear as a
        # tool_return-tiered clause anywhere in the draft.
        src = (
            "import logging\n"
            "logger = logging.getLogger(__name__)\n"
            "def f(x):\n"
            "    logger.warning('this never reaches the agent')\n"
            "    return {'ok': True}\n"
        )
        contract = draft_contract(source_text=src, file_path="f.py", qualname="f", benchmark="s", commit="0000000")
        all_quotes = " ".join(
            e["provenance"].get("quote", "") for e in contract.get("effects", []) if e.get("provenance")
        )
        self.assertNotIn("this never reaches the agent", all_quotes)


@unittest.skipUnless(TAU2_SRC.exists(), "tau2 pinned-commit source copy not present")
class TestAgainstRealTau2Sources(unittest.TestCase):
    def test_refuel_data_validates_against_full_validator(self):
        from spec.validate import Reporter, validate_file
        import tempfile

        text = (TAU2_SRC / "telecom" / "tools.py").read_text(encoding="utf-8")
        contract = draft_contract(
            source_text=text,
            file_path="src/tau2/domains/telecom/tools.py",
            qualname="TelecomTools.refuel_data",
            tool_name="refuel_data",
            benchmark="tau2-bench",
            commit="c3398666e6559e3a063da3fc04b5acf7f941464e",
        )
        errors = _validate_against_schema(contract)
        self.assertEqual(errors, [], f"schema errors: {errors}")

        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as fh:
            yaml.safe_dump(contract, fh, sort_keys=False)
            path = fh.name
        try:
            rep = Reporter()
            validate_file(path, SCHEMA, repo_root=str(REPO_ROOT / "repos" / "tau2"), state_schema_path=None, rep=rep)
            self.assertEqual(rep.failures, [], f"validator failures: {rep.failures}")
        finally:
            Path(path).unlink(missing_ok=True)

    def test_cancel_reservation_does_not_reproduce_the_seats_released_trap(self):
        """PREDICATE-GRAMMAR.md sec 5: the first hand-authored draft of this contract grounded
        eff.seats_released in tool_return, quoting a logger.warning() call at line 367 -- that
        text is never returned or raised, so it must never surface as a tool_return-tiered
        clause here either."""
        text = (TAU2_SRC / "airline" / "tools.py").read_text(encoding="utf-8")
        contract = draft_contract(
            source_text=text,
            file_path="src/tau2/domains/airline/tools.py",
            qualname="AirlineTools.cancel_reservation",
            tool_name="cancel_reservation",
            benchmark="tau2-bench",
            commit="c3398666e6559e3a063da3fc04b5acf7f941464e",
        )
        tool_return_quotes = " ".join(
            e["provenance"].get("quote", "")
            for e in contract.get("effects", [])
            if e.get("provenance", {}).get("surface") == "tool_return"
        )
        self.assertNotIn("Seats release", tool_return_quotes)


@unittest.skipUnless(AGENTDOJO_SRC.exists(), "agentdojo pinned-commit clone not present")
class TestAgainstRealAgentdojoSource(unittest.TestCase):
    def test_update_scheduled_transaction_validates(self):
        text = (AGENTDOJO_SRC / "banking_client.py").read_text(encoding="utf-8")
        contract = draft_contract(
            source_text=text,
            file_path="src/agentdojo/default_suites/v1/tools/banking_client.py",
            qualname="update_scheduled_transaction",
            benchmark="agentdojo",
            commit="089ed468cf3ed0322acc66b0211f26d9d90dbf60",
        )
        errors = _validate_against_schema(contract)
        self.assertEqual(errors, [], f"schema errors: {errors}")
        args = contract["signature"]["args"]
        self.assertEqual(args["recurring"]["type"], "bool | None")


if __name__ == "__main__":
    unittest.main()
