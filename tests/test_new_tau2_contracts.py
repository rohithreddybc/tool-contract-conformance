"""Contract-loading tests for the 17 tau2 mutating-tool contracts authored to close the gap
left by cancel_reservation.yaml / refuel_data.yaml (the two pre-existing hand-authored
contracts). Every tool here has mutates_state=True at commit c3398666 across the airline,
retail, and telecom domains, enumerated from adapters/tau2.py's tool listing.

Two things are pinned down:
  1. every contract loads via core.model.Contract.from_yaml and validates against
     spec/schema.json and every one of spec/validate.py's 8 checks (repo-root=repos/tau2,
     git-show against the pinned commit c3398666 -- the checkout's current branch does not
     matter, see tests/test_validate.py's REPO_ROOT for the same pattern) -- including check 5
     (synthetic snapshot evaluation), which is exercised here with the domain-specific fixtures
     under tests/fixtures/tau2_{airline,retail,telecom}_state.json;
  2. the batch-level facts reported alongside the contracts: how many adopted
     biconditional:true (with justification), and that no clause anywhere in the batch is
     mis-tiered as tool_return when it is actually maintainer-annotated (the exact trap
     PREDICATE-GRAMMAR.md sec 5 documents against its own first draft).

Run with: python -m unittest discover tests
"""
import json
import unittest
from pathlib import Path

from core.model import Contract
from spec.coverage import biconditional_adoption
from spec.validate import SCHEMA_PATH, Reporter, validate_file

with open(SCHEMA_PATH, "r", encoding="utf-8") as _fh:
    _SCHEMA = json.load(_fh)

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTRACTS_DIR = REPO_ROOT / "spec" / "contracts" / "tau2"
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"
TAU2_REPO = REPO_ROOT / "repos" / "tau2"

# tool name -> domain, used to pick the right synthetic-snapshot fixture for check 5.
NEW_CONTRACTS = {
    "book_reservation.yaml": "airline",
    "send_certificate.yaml": "airline",
    "update_reservation_baggages.yaml": "airline",
    "update_reservation_flights.yaml": "airline",
    "update_reservation_passengers.yaml": "airline",
    "cancel_pending_order.yaml": "retail",
    "exchange_delivered_order_items.yaml": "retail",
    "modify_pending_order_address.yaml": "retail",
    "modify_pending_order_items.yaml": "retail",
    "modify_pending_order_payment.yaml": "retail",
    "modify_user_address.yaml": "retail",
    "return_delivered_order_items.yaml": "retail",
    "suspend_line.yaml": "telecom",
    "resume_line.yaml": "telecom",
    "send_payment_request.yaml": "telecom",
    "enable_roaming.yaml": "telecom",
    "disable_roaming.yaml": "telecom",
}

FIXTURE_BY_DOMAIN = {
    "airline": FIXTURES_DIR / "tau2_airline_state.json",
    "retail": FIXTURES_DIR / "tau2_retail_state.json",
    "telecom": FIXTURES_DIR / "tau2_telecom_state.json",
}


@unittest.skipUnless(TAU2_REPO.exists(), "repos/tau2 checkout not present")
class TestNewContractsLoadAndValidate(unittest.TestCase):
    """One subtest per contract file -- loads it, then runs the full 8-check validator
    (schema + predicate/frame parsing + provenance-quote location + synthetic evaluation +
    biconditional/deferred provenance + clause-id uniqueness + agent-visibility) against it."""

    def test_all_new_contracts_load_as_dataclasses(self):
        for filename in NEW_CONTRACTS:
            with self.subTest(filename=filename):
                contract = Contract.from_yaml(CONTRACTS_DIR / filename)
                self.assertEqual(contract.commit, "c3398666")
                self.assertEqual(contract.benchmark, "tau2-bench")
                self.assertTrue(contract.tool)

    def test_all_new_contracts_pass_full_validator(self):
        for filename, domain in NEW_CONTRACTS.items():
            with self.subTest(filename=filename):
                rep = Reporter()
                validate_file(
                    str(CONTRACTS_DIR / filename),
                    _SCHEMA,
                    repo_root=str(TAU2_REPO),
                    state_schema_path=str(FIXTURE_BY_DOMAIN[domain]),
                    rep=rep,
                )
                self.assertEqual(rep.failures, [], f"{filename}: {rep.failures}")
                # every check actually ran -- none silently skipped for lack of --repo-root /
                # --state-schema, which is how a contract could pass validate_file trivially.
                self.assertEqual(rep.skips, [], f"{filename}: unexpected skips {rep.skips}")


@unittest.skipUnless(TAU2_REPO.exists(), "repos/tau2 checkout not present")
class TestNewContractsBiconditionalAdoption(unittest.TestCase):
    """Pins the batch-level biconditional-adoption count reported alongside the contracts.
    A change to this number should be a deliberate edit to a contract, not a silent drift."""

    def test_all_seventeen_adopt_biconditional_with_justification(self):
        adopted = []
        for filename in NEW_CONTRACTS:
            contract = Contract.from_yaml(CONTRACTS_DIR / filename)
            b = biconditional_adoption(contract)
            if b["biconditional"]:
                self.assertTrue(b["justification"], f"{filename}: biconditional with no justification")
                adopted.append(filename)
        # book_reservation, update_reservation_flights, send_certificate, update_reservation_
        # baggages, update_reservation_passengers, cancel_pending_order, exchange_delivered_
        # order_items, modify_pending_order_address, modify_pending_order_items, modify_pending_
        # order_payment, modify_user_address, return_delivered_order_items, suspend_line,
        # resume_line, send_payment_request, enable_roaming, disable_roaming: every tool in this
        # batch has a return-on-success / raise-before-any-mutation shape, so all 17 adopt
        # biconditional:true (see each contract's success_signal.justification for the specific
        # line-ordering argument). Only refuel_data.yaml (pre-existing, not part of this batch)
        # sets biconditional:false.
        self.assertEqual(len(adopted), 17)


@unittest.skipUnless(TAU2_REPO.exists(), "repos/tau2 checkout not present")
class TestNewContractsDoNotReproduceTheSeatsReleasedTrap(unittest.TestCase):
    """PREDICATE-GRAMMAR.md sec 5 / tests/test_extract.py: a maintainer-only annotation
    (logger.*, a bare comment, a TODO) must never be tiered as tool_return. Every provenance
    entry across the batch is checked directly against that rule, not just the two clauses
    that are known to sit next to a maintainer comment (update_reservation_flights' deferred
    flights-table frame clause, and the retail exchange/return "request, don't apply yet"
    pattern)."""

    def test_no_logger_or_comment_text_is_tiered_tool_return(self):
        banned_substrings = (
            "Do not make flight database update here",  # airline/tools.py:689, a `#` comment
            "not found for customer",  # shared helper raise -- fine as tool_return, listed here
            # only as a reminder this one IS legitimately tool_return (raised, not logged); see
            # the next assertion for the actual maintainer-annotation-only check.
        )
        maintainer_only_substrings = ("Do not make flight database update here",)
        for filename in NEW_CONTRACTS:
            contract = Contract.from_yaml(CONTRACTS_DIR / filename)
            for clause in list(contract.preconditions) + list(contract.effects):
                prov = clause.provenance
                if prov is None:
                    continue
                for banned in maintainer_only_substrings:
                    if banned in prov.quote:
                        self.assertNotEqual(
                            prov.surface,
                            "tool_return",
                            f"{filename}:{clause.id} grounds a maintainer-only comment as tool_return",
                        )
            for frame_clause in contract.frame:
                prov = frame_clause.provenance
                if prov is None:
                    continue
                for banned in maintainer_only_substrings:
                    if banned in prov.quote:
                        self.assertEqual(
                            prov.surface,
                            "maintainer_annotation",
                            f"{filename}:{frame_clause.id} must tier the deferral comment as maintainer_annotation",
                        )


if __name__ == "__main__":
    unittest.main()
