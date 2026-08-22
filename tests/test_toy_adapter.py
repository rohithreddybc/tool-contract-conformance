"""Toy domain conformance tests. Two things this file exists to prove:

1. ToyAdapter is a real, working adapters.base.Adapter implementation (list_tools / fresh_env /
   snapshot / invoke / reset / source), exercised through a full cycle exactly like Gate 1a in
   tests/test_tau2_adapter.py.
2. Every one of the 11 shipped toy contracts (spec/contracts/toy/*.yaml) is not just
   schema-valid (tests/test_validate.py covers that generically) but semantically correct against
   the real toy/bank.py implementation: a legitimate call CONFORMS on every effect clause, and a
   deliberately precondition-violating call is reported as an ENFORCED precondition (CONFORMS via
   check_precondition_enforcement) -- the toy domain is hand-verified to have no defects, so this
   is the "the checker agrees the reference implementation is clean" baseline that
   mutation/*.py's tests then perturb away from.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from adapters.contract_check import check_effects, check_precondition_enforcement, to_result_binding
from core.canonical import diff
from core.model import Contract
from core.verdict import Verdict
from toy.adapter import ToyAdapter
from toy.bank import MUTATING_TOOLS

CONTRACTS_DIR = Path(__file__).resolve().parent.parent / "spec" / "contracts" / "toy"


class TestToyAdapterCycle(unittest.TestCase):
    def setUp(self):
        self.adapter = ToyAdapter()

    def test_list_tools_matches_mutating_tools_table(self):
        tools = self.adapter.list_tools()
        names = {t.name for t in tools}
        self.assertEqual(names, set(MUTATING_TOOLS))
        self.assertTrue(all(t.mutates_state for t in tools))
        self.assertTrue(all(t.domain == "toy" for t in tools))

    def test_fresh_env_deterministic(self):
        env_a = self.adapter.fresh_env("default")
        env_b = self.adapter.fresh_env("default")
        self.assertEqual(self.adapter.snapshot(env_a), self.adapter.snapshot(env_b))

    def test_full_cycle_snapshot_invoke_snapshot_reset_snapshot(self):
        env = self.adapter.fresh_env("default")
        pre = self.adapter.snapshot(env)

        result = self.adapter.invoke(env, "deposit", {"account_id": "acc_alice", "amount": 25.0})
        self.assertTrue(result.success, result.error)

        post = self.adapter.snapshot(env)
        delta = diff(pre, post)
        self.assertNotEqual(delta, {}, "deposit mutates state; the diff must be non-empty")

        self.adapter.reset(env)
        post_reset = self.adapter.snapshot(env)
        self.assertEqual(diff(pre, post_reset), {}, "reset must restore exactly the initial snapshot")
        self.assertEqual(post_reset, pre)

    def test_source_resolves_every_mutating_tool(self):
        for name in MUTATING_TOOLS:
            src = self.adapter.source(name)
            self.assertEqual(src.file, "toy/bank.py")
            self.assertLess(src.start_line, src.end_line)


class TestToyContractsConform(unittest.TestCase):
    """One legitimate probe call per tool, checked against the shipped contract's own effect
    clauses -- never against a hard-coded field assertion (same discipline as
    tests/test_tau2_adapter.py's Gate 1b tests)."""

    def setUp(self):
        self.adapter = ToyAdapter()
        self.env = self.adapter.fresh_env("default")

    def _run(self, tool: str, args: dict):
        contract = Contract.from_yaml(CONTRACTS_DIR / f"{tool}.yaml")
        pre = self.adapter.snapshot(self.env)
        tr = self.adapter.invoke(self.env, tool, args)
        post = self.adapter.snapshot(self.env)
        result = to_result_binding(tr.raw, tr.success, tr.error)
        return contract, tr, pre, post, args, result

    def _assert_all_effects_conform(self, tool: str, args: dict):
        contract, tr, pre, post, args, result = self._run(tool, args)
        self.assertTrue(tr.success, f"{tool}{args} unexpectedly failed: {tr.error}")
        verdicts = check_effects(contract, pre, post, args, result)
        self.assertTrue(verdicts, f"{tool} contract has no effect clauses to check")
        for v in verdicts:
            self.assertEqual(
                v.verdict, Verdict.CONFORMS,
                f"{tool}.{v.clause_id} did not CONFORM on a legitimate call: {v}",
            )

    def test_deposit_conforms(self):
        self._assert_all_effects_conform("deposit", {"account_id": "acc_alice", "amount": 10.0})

    def test_withdraw_conforms(self):
        self._assert_all_effects_conform("withdraw", {"account_id": "acc_alice", "amount": 10.0})

    def test_transfer_conforms(self):
        self._assert_all_effects_conform(
            "transfer", {"from_account": "acc_alice", "to_account": "acc_bob", "amount": 10.0}
        )

    def test_freeze_account_conforms(self):
        self._assert_all_effects_conform("freeze_account", {"account_id": "acc_alice"})

    def test_unfreeze_account_conforms(self):
        self._assert_all_effects_conform("unfreeze_account", {"account_id": "acc_carol"})

    def test_reserve_item_conforms(self):
        self._assert_all_effects_conform(
            "reserve_item", {"item_id": "widget", "qty": 2, "account_id": "acc_alice"}
        )

    def test_release_item_conforms(self):
        self._assert_all_effects_conform("release_item", {"item_id": "widget", "qty": 1})

    def test_acquire_lock_conforms_fresh_and_reentrant(self):
        self._assert_all_effects_conform("acquire_lock", {"lock_id": "printer", "holder": "alice"})
        # Reentrant second acquisition by the same holder -- exercises the "already held by
        # holder" branch of acquire_lock's effect predicate, not just the fresh-acquire branch.
        self._assert_all_effects_conform("acquire_lock", {"lock_id": "printer", "holder": "alice"})

    def test_release_lock_conforms_down_to_zero(self):
        self._assert_all_effects_conform("acquire_lock", {"lock_id": "printer", "holder": "alice"})
        self._assert_all_effects_conform("acquire_lock", {"lock_id": "printer", "holder": "alice"})
        # count is now 2 -- releasing once must CONFORM with held_by still == holder (count>0 arm)
        self._assert_all_effects_conform("release_lock", {"lock_id": "printer", "holder": "alice"})
        # releasing again drives count to 0 -- must CONFORM with held_by cleared (count==0 arm),
        # exercising both arms of eff.held_by_cleared_when_count_zero's IfExp-shaped predicate.
        self._assert_all_effects_conform("release_lock", {"lock_id": "printer", "holder": "alice"})

    def test_resize_inventory_conforms_in_every_mode(self):
        self._assert_all_effects_conform("resize_inventory", {"item_id": "widget", "delta": 3, "mode": "add"})
        self._assert_all_effects_conform("resize_inventory", {"item_id": "widget", "delta": 2, "mode": "remove"})
        self._assert_all_effects_conform("resize_inventory", {"item_id": "widget", "delta": 5, "mode": "set"})

    def test_tag_item_conforms(self):
        self._assert_all_effects_conform("tag_item", {"item_id": "widget", "tag": "fragile"})


class TestToyContractsEnforcePreconditions(unittest.TestCase):
    """Deliberately violate one precondition per tool and confirm check_precondition_enforcement
    reports it as ENFORCED (CONFORMS) -- the toy domain is hand-verified to raise with no state
    delta on every guard, unlike tau2's refuel_data (FINDINGS-VERIFIED.md Finding 2)."""

    def setUp(self):
        self.adapter = ToyAdapter()
        self.env = self.adapter.fresh_env("default")

    def _assert_precondition_enforced(self, tool: str, args: dict):
        contract = Contract.from_yaml(CONTRACTS_DIR / f"{tool}.yaml")
        pre = self.adapter.snapshot(self.env)
        tr = self.adapter.invoke(self.env, tool, args)
        post = self.adapter.snapshot(self.env)
        result = to_result_binding(tr.raw, tr.success, tr.error)
        verdict = check_precondition_enforcement(contract, pre, post, args, result, tr.error)
        self.assertIsNotNone(verdict, f"{tool}{args} was expected to violate a declared precondition")
        self.assertEqual(verdict.verdict, Verdict.CONFORMS, f"{tool}: precondition not enforced: {verdict}")
        self.assertFalse(tr.success, f"{tool}{args} should have raised")
        self.assertEqual(diff(pre, post), {}, f"{tool}: a rejected call must not mutate state")

    def test_deposit_unknown_account(self):
        self._assert_precondition_enforced("deposit", {"account_id": "no_such_account", "amount": 5.0})

    def test_withdraw_insufficient_balance(self):
        self._assert_precondition_enforced("withdraw", {"account_id": "acc_bob", "amount": 999.0})

    def test_transfer_frozen_source(self):
        self._assert_precondition_enforced(
            "transfer", {"from_account": "acc_carol", "to_account": "acc_bob", "amount": 1.0}
        )

    def test_freeze_account_already_frozen(self):
        self._assert_precondition_enforced("freeze_account", {"account_id": "acc_carol"})

    def test_unfreeze_account_not_frozen(self):
        self._assert_precondition_enforced("unfreeze_account", {"account_id": "acc_alice"})

    def test_reserve_item_insufficient_available(self):
        self._assert_precondition_enforced("reserve_item", {"item_id": "widget", "qty": 999, "account_id": "acc_alice"})

    def test_release_item_over_release(self):
        self._assert_precondition_enforced("release_item", {"item_id": "widget", "qty": 999})

    def test_acquire_lock_held_by_other(self):
        r = self.adapter.invoke(self.env, "acquire_lock", {"lock_id": "printer", "holder": "alice"})
        self.assertTrue(r.success, r.error)
        self._assert_precondition_enforced("acquire_lock", {"lock_id": "printer", "holder": "bob"})

    def test_release_lock_not_held(self):
        self._assert_precondition_enforced("release_lock", {"lock_id": "printer", "holder": "alice"})

    def test_resize_inventory_bad_mode(self):
        self._assert_precondition_enforced("resize_inventory", {"item_id": "widget", "delta": 1, "mode": "multiply"})

    def test_tag_item_duplicate_tag(self):
        self._assert_precondition_enforced("tag_item", {"item_id": "widget", "tag": "hardware"})


if __name__ == "__main__":
    unittest.main()
