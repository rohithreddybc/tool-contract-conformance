"""Regression pin for the "17 of 19 tau2 contracts silently skipped" defect (final pass before
checker-freeze-v1).

`dynamic/harness.py` used to hand-maintain `TAU2_DOMAIN_BY_TOOL = {"cancel_reservation":
"airline", "refuel_data": "telecom"}` and `_iter_tau2_contracts` `continue`d past any contract
whose tool was not a key in that table -- silently, with no row, no warning, no trace. Every one
of the 17 tau2 contracts authored after that table was written (tests/test_new_tau2_contracts.py)
was therefore never dynamically exercised even though it loads, validates, and is counted
everywhere else. `report/findings.jsonl` covered 2 tau2 tools while the project claims 19.

Fixed two ways, both pinned here:
  1. Domain is derived from `contract.source.file` (`mutation.real_targets.resolve_domain`,
     which already existed and already generalised away from this exact hand-maintained table --
     see that function's docstring) instead of a second table that must be remembered on every
     new contract.
  2. A contract `resolve_domain` cannot route is no longer silently dropped: `_iter_tau2_contracts`
     / `_iter_contracts_by_live_domain` yield `(contract, None)` rather than skipping, and
     `dynamic.harness._unroutable_row` turns that into a loud UNTESTABLE row with the registered
     `adapter_unsupported` reason code (`core.verdict.UNTESTABLE_REASONS`) instead of an absent
     row.

Run with: python -m unittest discover tests
"""
from __future__ import annotations

import dataclasses
import unittest
from pathlib import Path

from adapters.agentdojo import AgentDojoAdapter, AgentDojoAdapterError
from adapters.mmtoolsandbox import MMToolSandboxAdapter, MMToolSandboxAdapterError
from core.model import Contract, SourceRef
from core.verdict import UNTESTABLE_REASONS, Verdict
from dynamic.harness import _iter_contracts_by_live_domain, _iter_tau2_contracts, _unroutable_row
from mutation.real_targets import resolve_domain

CONTRACTS_ROOT = Path(__file__).resolve().parent.parent / "spec" / "contracts"
TAU2_REPO = CONTRACTS_ROOT.parent.parent / "repos" / "tau2"

# tool -> domain, independently enumerated from tests/test_new_tau2_contracts.py's own
# NEW_CONTRACTS table plus the 2 pre-existing contracts, so this test does not simply re-check
# resolve_domain against itself.
EXPECTED_TAU2_DOMAIN = {
    "cancel_reservation.yaml": "airline",
    "refuel_data.yaml": "telecom",
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


class TestTau2DomainDerivationCoversEveryShippedContract(unittest.TestCase):
    """Pure -- no live tau2 adapter needed, since domain derivation reads only
    `contract.source.file`, never talks to the subprocess worker."""

    def test_every_shipped_tau2_contract_resolves_a_domain(self):
        pairs = list(_iter_tau2_contracts())
        self.assertEqual(
            len(pairs), 19, f"expected all 19 shipped tau2 contracts to be yielded, got {len(pairs)}"
        )
        unrouted = [c.tool for c, domain in pairs if domain is None]
        self.assertEqual(unrouted, [], f"these tau2 contracts failed to route to a domain: {unrouted}")

    def test_resolved_domain_matches_the_independently_enumerated_table(self):
        by_filename = {p.name: p for p in sorted(CONTRACTS_ROOT.glob("tau2/*.yaml"))}
        self.assertEqual(set(by_filename), set(EXPECTED_TAU2_DOMAIN), "contract file set drifted from this test's own table")
        for filename, expected_domain in EXPECTED_TAU2_DOMAIN.items():
            contract = Contract.from_yaml(by_filename[filename])
            with self.subTest(filename=filename):
                self.assertEqual(resolve_domain("tau2-bench", contract), expected_domain)

    def test_old_two_tool_hand_maintained_table_is_gone(self):
        """The exact defect: a hand-maintained tool->domain dict that only the 2 original tools
        were keys of. If this ever comes back, every contract added afterwards is at risk of the
        same silent-skip regression."""
        import dynamic.harness as harness

        self.assertFalse(
            hasattr(harness, "TAU2_DOMAIN_BY_TOOL"),
            "TAU2_DOMAIN_BY_TOOL reappeared -- domain must be derived from contract.source.file, "
            "not hand-maintained per tool name (see this test module's docstring)",
        )


class TestUnroutableContractProducesALoudRow(unittest.TestCase):
    """No live adapter needed -- `_unroutable_row` only reads the contract object."""

    def _contract_with_bogus_source_file(self) -> Contract:
        contract = Contract.from_yaml(CONTRACTS_ROOT / "tau2" / "cancel_reservation.yaml")
        bogus_source = dataclasses.replace(contract.source, file="src/tau2/not_a_domains_path.py")
        return dataclasses.replace(contract, source=bogus_source)

    def test_resolve_domain_returns_none_for_an_unroutable_source_path(self):
        contract = self._contract_with_bogus_source_file()
        self.assertIsNone(resolve_domain("tau2-bench", contract))

    def test_unroutable_row_is_untestable_with_a_registered_reason_code(self):
        contract = self._contract_with_bogus_source_file()
        row = _unroutable_row(contract)
        self.assertEqual(row["verdict"], Verdict.UNTESTABLE.value)
        self.assertEqual(row["reason_code"], "adapter_unsupported")
        self.assertIn("adapter_unsupported", UNTESTABLE_REASONS)
        self.assertEqual(row["tool"], contract.tool)
        self.assertEqual(row["benchmark"], contract.benchmark)
        # Never absent, never silently continue()d past: this row is what a caller writes to
        # findings.jsonl instead of dropping the contract entirely.
        self.assertIsNotNone(row["clause_id"])


@unittest.skipUnless((CONTRACTS_ROOT.parent.parent / ".venv-agentdojo").exists(), "agentdojo venv not provisioned")
class TestAgentDojoDomainRoutingCoversEveryShippedContract(unittest.TestCase):
    def test_every_shipped_agentdojo_contract_resolves_a_domain(self):
        try:
            adapter = AgentDojoAdapter()
        except AgentDojoAdapterError as e:
            raise unittest.SkipTest(f"agentdojo adapter venv not provisioned: {e}")
        try:
            pairs = list(_iter_contracts_by_live_domain("agentdojo", adapter))
        finally:
            adapter.close()
        self.assertEqual(len(pairs), 7, f"expected all 7 shipped agentdojo contracts to be yielded, got {len(pairs)}")
        unrouted = [c.tool for c, domain in pairs if domain is None]
        self.assertEqual(unrouted, [], f"these agentdojo contracts failed to route to a live domain: {unrouted}")


@unittest.skipUnless((CONTRACTS_ROOT.parent.parent / ".venv-mmtoolsandbox").exists(), "mm-toolsandbox venv not provisioned")
class TestMMToolSandboxDomainRoutingCoversEveryShippedContract(unittest.TestCase):
    def test_every_shipped_mmtoolsandbox_contract_resolves_a_domain(self):
        try:
            adapter = MMToolSandboxAdapter()
        except MMToolSandboxAdapterError as e:
            raise unittest.SkipTest(f"mm-toolsandbox adapter venv not provisioned: {e}")
        try:
            pairs = list(_iter_contracts_by_live_domain("mmtoolsandbox", adapter))
        finally:
            adapter.close()
        self.assertEqual(len(pairs), 5, f"expected all 5 shipped mm-toolsandbox contracts to be yielded, got {len(pairs)}")
        unrouted = [c.tool for c, domain in pairs if domain is None]
        self.assertEqual(unrouted, [], f"these mm-toolsandbox contracts failed to route to a live domain: {unrouted}")


if __name__ == "__main__":
    unittest.main()
