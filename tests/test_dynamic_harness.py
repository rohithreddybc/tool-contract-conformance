"""Tests for the Reset Leak and Invariant Break gap fix in dynamic/harness.py.

Before this fix, `run_contract` never called `Adapter.reset()` and nothing evaluated a
contract's `invariants:` clauses -- confirmed by grep, not assumed (see
experiments/run_mutation_closed_world.py's pre-fix `run_reset_operator` docstring for the
Reset Leak half, and the mutation run's suspiciously-total 0.000 M-INVAR recall for the
Invariant Break half). Every VIOLATES-producing test below is a genuine fail-before/pass-after
regression test: on the pre-fix harness, `check_reset` and `check_invariants` did not exist at
all, so these mutants could not have been flagged by ANY code path. Every CONFORMS-producing test
is the matching negative control -- the checker's strongest claim (zero false positives) must
survive this fix, so a genuinely clean tool or a genuinely-held invariant must never be flagged.
"""
from __future__ import annotations

import unittest
from dataclasses import replace
from pathlib import Path

from adapters.base import Adapter, EnvHandle, SourceRef, ToolResult
from core.model import Contract
from core.verdict import DefectClass, Verdict
from dynamic.harness import RESET_CLAUSE_ID, check_invariants, check_reset, run_contract
from dynamic.probes import Probe
from mutation.adapter_invoke import MutatedAdapter, build_function_patch_source
from toy.adapter import ToyAdapter

CONTRACTS_DIR = Path(__file__).resolve().parent.parent / "spec" / "contracts" / "toy"
BANK_SOURCE_PATH = Path(__file__).resolve().parent.parent / "toy" / "bank.py"


def _toy_contract(tool: str) -> Contract:
    return Contract.from_yaml(CONTRACTS_DIR / f"{tool}.yaml")


def _bank_source() -> str:
    return BANK_SOURCE_PATH.read_text(encoding="utf-8")


ACQUIRE_PROBE = Probe(tool="acquire_lock", args={"lock_id": "printer", "holder": "alice"}, origin="test")


class _NoResetAdapter(Adapter):
    """A concrete Adapter whose `reset()` override reproduces the abstract base's own documented
    fallback (`adapters/base.py`: "raise NotImplementedError") -- exercises `check_reset`'s
    `no_reset_path` UNTESTABLE path for an adapter that genuinely cannot run the check. (Python's
    ABC machinery refuses to instantiate a subclass that leaves `reset` unoverridden at all, so
    this is the realistic shape: an adapter under construction that has stubbed every OTHER
    method but not yet wired up its benchmark's reset path.)"""

    def list_tools(self):
        raise NotImplementedError

    def fresh_env(self, scenario_id: str) -> EnvHandle:
        return EnvHandle(env_id="x", domain="toy", scenario_id=scenario_id)

    def snapshot(self, env: EnvHandle) -> dict:
        return {"accounts": {}}

    def invoke(self, env: EnvHandle, tool: str, args: dict) -> ToolResult:
        return ToolResult(raw={}, success=True, error=None)

    def reset(self, env: EnvHandle) -> None:
        raise NotImplementedError

    def source(self, tool: str) -> SourceRef:
        raise NotImplementedError


# =================================================================================================
# check_reset
# =================================================================================================


class TestCheckResetNegativeControls(unittest.TestCase):
    """The real, hand-verified-clean toy adapter must never be flagged."""

    def test_deposit_reset_conforms(self):
        cv = check_reset(ToyAdapter(), _toy_contract("deposit"), "default")
        self.assertIsNotNone(cv)
        self.assertEqual(cv.verdict, Verdict.CONFORMS)
        self.assertEqual(cv.clause_id, RESET_CLAUSE_ID)
        self.assertIsNone(cv.defect_class)

    def test_acquire_lock_reset_conforms_after_a_real_mutating_call(self):
        cv = check_reset(ToyAdapter(), _toy_contract("acquire_lock"), "default", effect_probe=ACQUIRE_PROBE)
        self.assertEqual(cv.verdict, Verdict.CONFORMS)

    def test_release_lock_reset_conforms_via_run_contract(self):
        rows = run_contract(ToyAdapter(), _toy_contract("release_lock"), "default")
        reset_rows = [r for r in rows if r["kind"] == "reset"]
        self.assertEqual(len(reset_rows), 1)
        self.assertEqual(reset_rows[0]["verdict"], "CONFORMS")
        self.assertEqual(reset_rows[0]["clause_id"], RESET_CLAUSE_ID)

    def test_no_reset_block_makes_no_claim(self):
        contract = replace(_toy_contract("deposit"), reset=None)
        self.assertIsNone(check_reset(ToyAdapter(), contract, "default"))

    def test_adapter_without_reset_support_is_untestable_not_a_false_positive(self):
        cv = check_reset(_NoResetAdapter(), _toy_contract("deposit"), "default")
        self.assertEqual(cv.verdict, Verdict.UNTESTABLE)
        self.assertEqual(cv.reason_code, "no_reset_path")


class TestCheckResetDetectsLeak(unittest.TestCase):
    """The exact gap CLAUDE.md's build note describes: an M-RESET mutant (mutation/operators.py's
    m_reset) that drops the `locks` field's restore. Fails on the pre-fix harness (no code path
    could have produced RESET_LEAK at all); passes now."""

    def test_dropped_locks_restore_is_flagged_reset_leak(self):
        patch_source = build_function_patch_source(_bank_source(), "reset", "M-RESET", {"body_index": 3})
        mutant = MutatedAdapter(ToyAdapter(), "reset", patch_source)
        try:
            cv = check_reset(mutant, _toy_contract("acquire_lock"), "default", effect_probe=ACQUIRE_PROBE)
            self.assertEqual(cv.verdict, Verdict.VIOLATES)
            self.assertEqual(cv.defect_class, DefectClass.RESET_LEAK)
            self.assertEqual(cv.clause_id, RESET_CLAUSE_ID)
            self.assertIn("locks.printer.held_by", cv.witness.diff)
            self.assertIn("locks.printer.count", cv.witness.diff)
        finally:
            mutant.close()

    def test_dropped_locks_restore_is_flagged_via_run_contract(self):
        """Same mutant, exercised through the real `run_contract` entry point the mutation-scoring
        experiment actually calls -- "detected" for the pre-registered plan means a VIOLATES row
        appears among `run_contract`'s output, not that `check_reset` was called directly."""
        patch_source = build_function_patch_source(_bank_source(), "reset", "M-RESET", {"body_index": 3})
        mutant = MutatedAdapter(ToyAdapter(), "reset", patch_source)
        try:
            rows = run_contract(mutant, _toy_contract("acquire_lock"), "default")
            reset_rows = [r for r in rows if r["kind"] == "reset"]
            self.assertEqual(len(reset_rows), 1)
            self.assertEqual(reset_rows[0]["verdict"], "VIOLATES")
            self.assertEqual(reset_rows[0]["defect_class"], "reset_leak")
        finally:
            mutant.close()


# =================================================================================================
# check_invariants
# =================================================================================================


class TestCheckInvariantsNotApplicable(unittest.TestCase):
    def test_contract_with_no_invariants_produces_no_rows(self):
        contract = _toy_contract("tag_item")
        self.assertEqual(contract.invariants, ())
        self.assertEqual(check_invariants(ToyAdapter(), contract, "default"), [])


class TestCheckInvariantsSingleCallConforms(unittest.TestCase):
    """Most shipped invariants (every *_nonnegative clause) constrain `post` alone and are fully
    testable from one legal call -- the length-1 degenerate case of "a legal call sequence"."""

    def test_deposit_balance_nonnegative_conforms(self):
        probe = Probe(tool="deposit", args={"account_id": "acc_alice", "amount": 10.0}, origin="test")
        result = check_invariants(ToyAdapter(), _toy_contract("deposit"), "default", own_probe=probe)
        self.assertEqual(len(result), 1)
        cv, label = result[0]
        self.assertEqual(cv.clause_id, "inv.balance_nonnegative")
        self.assertEqual(cv.verdict, Verdict.CONFORMS)
        self.assertEqual(label, "single_call")

    def test_no_probe_and_no_companions_is_untestable_not_a_false_conform(self):
        # own_probe=None and no siblings: no legal sequence can be built at all -- must degrade
        # to UNTESTABLE, never silently CONFORMS (which would overclaim, exactly like a missing
        # snapshot path must never be silently False -- PREDICATE-GRAMMAR.md sec 2.3).
        result = check_invariants(ToyAdapter(), _toy_contract("deposit"), "default", own_probe=None)
        self.assertEqual(len(result), 1)
        cv, label = result[0]
        self.assertEqual(cv.verdict, Verdict.UNTESTABLE)
        self.assertEqual(cv.reason_code, "no_observable_state")
        self.assertEqual(label, "invariant_sequence_not_found")


class TestCheckInvariantsPairedSequenceDetectsBreak(unittest.TestCase):
    """The scenario CLAUDE.md's build note names specifically: toy/bank.py's release_lock has an
    M-INVAR site (the conditional `held_by = None` clear-on-zero write) whose OWN precondition
    (`pre.locks[id].held_by == args.holder`) can never be satisfied from a truly fresh env --
    `held_by` starts `None` and no probe-generated string ever equals `None` -- so this defect is
    untestable by ANY single-call check, effect or invariant alike (see the first assertion
    below). Only a length-2 sequence (acquire_lock first, to actually create a held lock, then
    release_lock) can expose it. This is the test that fails on the pre-fix harness (no
    invariant evaluator existed at all, and no sequence prober existed either) and passes now."""

    def _mutant(self):
        patch_source = build_function_patch_source(
            _bank_source(), "release_lock", "M-INVAR", {"if_index": 6, "branch": "body", "branch_index": 0}
        )
        return MutatedAdapter(ToyAdapter(), "release_lock", patch_source)

    def test_release_lock_own_single_call_check_cannot_reach_the_defect(self):
        """Confirms the premise: without a companion sequence, release_lock's own effect clauses
        are UNTESTABLE (a probe gap, not a clause gap) -- the paired-sequence path below is doing
        genuinely new work, not incidentally duplicating what a single-call check already covers."""
        rows = run_contract(ToyAdapter(), _toy_contract("release_lock"), "default")
        effect_rows = [r for r in rows if r["kind"] == "effect" and r["probe_origin"] == "effect_happy_path_not_found"]
        self.assertTrue(effect_rows, "expected release_lock's own effect happy-path search to fail from a fresh env")
        self.assertTrue(all(r["verdict"] == "UNTESTABLE" for r in effect_rows))

    def test_dropped_held_by_clear_is_flagged_invariant_break(self):
        mutant = self._mutant()
        try:
            result = check_invariants(
                mutant, _toy_contract("release_lock"), "default",
                sibling_contracts=(_toy_contract("acquire_lock"),), own_probe=None,
            )
        finally:
            mutant.close()
        by_id = {cv.clause_id: (cv, label) for cv, label in result}
        cv, label = by_id["inv.held_iff_count_positive"]
        self.assertEqual(cv.verdict, Verdict.VIOLATES)
        self.assertEqual(cv.defect_class, DefectClass.INVARIANT_BREAK)
        self.assertTrue(label.startswith("paired_sequence:"))
        # count_nonnegative genuinely still holds under this mutant (count reaches exactly 0,
        # never negative) -- must NOT be swept into a false VIOLATES just because a sibling
        # clause on the same tool broke.
        cv2, _ = by_id["inv.count_nonnegative"]
        self.assertEqual(cv2.verdict, Verdict.CONFORMS)

    def test_dropped_held_by_clear_is_flagged_via_run_contract(self):
        mutant = self._mutant()
        try:
            rows = run_contract(
                mutant, _toy_contract("release_lock"), "default",
                sibling_contracts=(_toy_contract("acquire_lock"),),
            )
        finally:
            mutant.close()
        inv_rows = {r["clause_id"]: r for r in rows if r["kind"] == "invariant"}
        self.assertEqual(inv_rows["inv.held_iff_count_positive"]["verdict"], "VIOLATES")
        self.assertEqual(inv_rows["inv.held_iff_count_positive"]["defect_class"], "invariant_break")

    def test_unmutated_pair_conforms_no_false_positive(self):
        """Same companion sequence, real (unmutated) release_lock -- must CONFORM on every
        invariant clause. This is the precision-preserving negative control: the fix must not
        invent a violation where none exists."""
        result = check_invariants(
            ToyAdapter(), _toy_contract("release_lock"), "default",
            sibling_contracts=(_toy_contract("acquire_lock"),), own_probe=None,
        )
        for cv, _label in result:
            self.assertEqual(cv.verdict, Verdict.CONFORMS, f"{cv.clause_id}: {cv}")

    def test_acquire_lock_side_of_the_pair_also_conforms_no_false_positive(self):
        """The companion contract's OWN invariant check (acquire_lock, paired with release_lock in
        the other call order) must likewise not be disturbed by this fix."""
        result = check_invariants(
            ToyAdapter(), _toy_contract("acquire_lock"), "default",
            sibling_contracts=(_toy_contract("release_lock"),),
            own_probe=ACQUIRE_PROBE,
        )
        for cv, _label in result:
            self.assertEqual(cv.verdict, Verdict.CONFORMS, f"{cv.clause_id}: {cv}")


class TestCheckInvariantsCompanionOrdering(unittest.TestCase):
    """Regression test for a false-positive bug found and fixed while building this feature: an
    early version of `check_invariants` also tried a "contract's own call FIRST, companion
    SECOND" sequence. That ordering's witness is the (pre, post, args, result) of the
    COMPANION's own call, which is not valid evidence for a clause declared on `contract` -- on
    the real toy domain it made `transfer`'s `inv.total_balance_conserved` (a real, conforming
    invariant) come back VIOLATES, because the witness it picked up was actually deposit's own
    call (which genuinely does not conserve the total -- depositing adds money, that is the
    point of deposit). `transfer` and `deposit` share the identical `inv.balance_nonnegative`
    clause, which is exactly what made `deposit` a "companion" of `transfer` under
    `_shares_invariant_clause`, so this is not a contrived case."""

    def test_transfer_paired_with_deposit_does_not_false_positive(self):
        transfer = _toy_contract("transfer")
        deposit = _toy_contract("deposit")
        probe = Probe(
            tool="transfer",
            args={"from_account": "acc_alice", "to_account": "acc_bob", "amount": 10.0},
            origin="test",
        )
        result = check_invariants(ToyAdapter(), transfer, "default", sibling_contracts=(deposit,), own_probe=probe)
        by_id = {cv.clause_id: cv for cv, _label in result}
        self.assertEqual(by_id["inv.total_balance_conserved"].verdict, Verdict.CONFORMS)
        self.assertEqual(by_id["inv.balance_nonnegative"].verdict, Verdict.CONFORMS)


class TestToyDomainNoFalsePositives(unittest.TestCase):
    """Task-level sanity sweep: every shipped, hand-verified-clean toy contract, run through the
    SAME `run_all`-shaped call `run_contract` gets in production (full sibling wiring included),
    against the real unmutated `ToyAdapter`, must report zero VIOLATES anywhere -- reset and
    invariant rows included. This is the check that caught the companion-ordering bug above; kept
    as a standing regression test rather than a one-off, since the whole point of adding two new
    checker paths is that they must never cost the checker's zero-false-positive claim."""

    def test_no_violates_anywhere_in_the_toy_domain(self):
        from dynamic.harness import _iter_toy_contracts, _with_siblings

        adapter = ToyAdapter()
        violations = []
        for contract, scenario_id, siblings in _with_siblings(_iter_toy_contracts()):
            rows = run_contract(adapter, contract, scenario_id, sibling_contracts=siblings)
            violations.extend(
                (contract.tool, r["kind"], r["clause_id"]) for r in rows if r["verdict"] == "VIOLATES"
            )
        self.assertEqual(violations, [])


class TestRunContractFrameWiring(unittest.TestCase):
    """check_frame (GAP 1) wired into run_contract: deposit.yaml's four real frame clauses must
    surface as kind="frame" rows against the real, unmutated ToyAdapter, and a mutant that drops
    an unrelated field's isolation must be caught the same way check_reset/check_invariants'
    mutants are caught elsewhere in this file -- through run_contract, not just check_frame
    directly."""

    def test_deposit_produces_four_conforming_frame_rows(self):
        rows = run_contract(ToyAdapter(), _toy_contract("deposit"), "default")
        frame_rows = [r for r in rows if r["kind"] == "frame"]
        self.assertEqual(len(frame_rows), 4)
        for r in frame_rows:
            self.assertEqual(r["verdict"], "CONFORMS", r)
            self.assertFalse(r["contract_declared_untestable"])

    def test_mutant_that_leaks_into_an_unrelated_account_field_is_flagged_via_run_contract(self):
        # M-INVAR-shaped hand mutant: patch deposit to also silently flip the account's frozen
        # flag. eff.balance_increased still holds (deposit still credits correctly), so this is
        # the "everything advertised landed, plus something extra" branch --
        # frame.frozen_flag_unchanged must come back VIOLATES with the aggravating signal, never
        # silently absorbed as a plain CONFORMS.
        # Preserves toy/bank.py's real deposit() precondition-checking exactly (still raises
        # ToyError, not a bare KeyError, for every declared precondition -- run_contract's own
        # probe search deliberately calls deposit with precondition-VIOLATING args too, e.g. an
        # account_id that does not exist, and those calls must still fail cleanly) and adds
        # exactly one extra mutating line: silently flip the account's frozen flag on success.
        patch_source = (
            "def deposit(self, account_id, amount):\n"
            "    account = self.state['accounts'].get(account_id)\n"
            "    if account is None:\n"
            "        raise ToyError(f'unknown account: {account_id}')\n"
            "    if account['frozen']:\n"
            "        raise ToyError(f'account is frozen: {account_id}')\n"
            "    if amount <= 0:\n"
            "        raise ToyError('amount must be positive')\n"
            "    account['balance'] = account['balance'] + amount\n"
            "    account['frozen'] = True\n"
            "    return {'account_id': account_id, 'balance': account['balance']}\n"
        )
        mutant = MutatedAdapter(ToyAdapter(), "deposit", patch_source)
        try:
            rows = run_contract(mutant, _toy_contract("deposit"), "default")
        finally:
            mutant.close()
        frame_rows = {r["clause_id"]: r for r in rows if r["kind"] == "frame"}
        flagged = frame_rows["frame.frozen_flag_unchanged"]
        self.assertEqual(flagged["verdict"], "VIOLATES")
        self.assertIsNone(flagged["defect_class"])
        self.assertEqual(flagged["aggravating_signal"], "unadvertised_side_effect")
        # A sibling frame clause this mutant never touches must still conform.
        self.assertEqual(frame_rows["frame.items_unchanged"]["verdict"], "CONFORMS")


class TestContractDeclaredUntestable(unittest.TestCase):
    """GAP 3 (CLAUDE.md): contract.untestable was parsed and schema-validated but never read.
    Wired through in dynamic/harness.py's _row: a clause named in contract.untestable is reported
    UNTESTABLE with the author's own declared reason, overriding whatever the live check
    produced -- never silently dropped from the denominator, and never left to whatever the
    dynamic check happened to compute."""

    def test_declared_untestable_effect_clause_overrides_a_real_conforms(self):
        # run_contract emits SEVERAL rows for eff.balance_increased (one per precondition-satisfy
        # probe, one for the happy-path probe, one for the joint-falsy probe) -- an untestable
        # declaration must override EVERY one of them, never just whichever happens to be found
        # first/last.
        from core.model import Untestable

        contract = replace(_deposit_for_untestable_test(), untestable=(Untestable(clause_id="eff.balance_increased", reason="nondeterministic_env"),))
        rows = run_contract(ToyAdapter(), contract, "default")
        balance_rows = [r for r in rows if r["kind"] == "effect" and r["clause_id"] == "eff.balance_increased"]
        self.assertTrue(balance_rows)
        for r in balance_rows:
            self.assertEqual(r["verdict"], "UNTESTABLE", r)
            self.assertEqual(r["reason_code"], "nondeterministic_env")
            self.assertTrue(r["contract_declared_untestable"])

    def test_clause_not_named_in_untestable_is_unaffected(self):
        contract = _deposit_for_untestable_test()
        self.assertEqual(contract.untestable, ())
        rows = run_contract(ToyAdapter(), contract, "default")
        balance_rows = [r for r in rows if r["kind"] == "effect" and r["clause_id"] == "eff.balance_increased"]
        self.assertTrue(balance_rows)
        # None of these rows are contract-declared-untestable, and the real happy-path call --
        # the row that actually exercises the tool's effect -- conforms.
        self.assertTrue(all(not r["contract_declared_untestable"] for r in balance_rows))
        happy_path = next(r for r in balance_rows if r["probe_origin"] == "effect_happy_path")
        self.assertEqual(happy_path["verdict"], "CONFORMS")


def _deposit_for_untestable_test() -> Contract:
    return _toy_contract("deposit")


class TestRunAllSiblingWiring(unittest.TestCase):
    """`dynamic.harness._with_siblings` -- the helper `run_all` uses to build `sibling_contracts`
    for every contract from the shipped set, grouped by scenario_id."""

    def test_toy_contracts_group_into_one_scenario_and_exclude_self(self):
        from dynamic.harness import _iter_toy_contracts, _with_siblings

        grouped = _with_siblings(_iter_toy_contracts())
        self.assertEqual(len(grouped), 11)
        by_tool = {c.tool: siblings for c, _scenario, siblings in grouped}
        self.assertIn("acquire_lock", by_tool)
        sibling_tools = {s.tool for s in by_tool["acquire_lock"]}
        self.assertNotIn("acquire_lock", sibling_tools)
        self.assertIn("release_lock", sibling_tools)
        self.assertEqual(len(sibling_tools), 10)


if __name__ == "__main__":
    unittest.main()
