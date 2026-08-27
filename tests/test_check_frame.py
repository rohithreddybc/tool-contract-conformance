"""Tests for dynamic/harness.py's check_frame -- GAP 1 in CLAUDE.md's checker-freeze-v1 build
note: 35 shipped contracts declare `frame:` clauses, and before this fix nothing dynamically
evaluated one (core/frame.py::match_paths was only ever called for canonicalization masking and
static validation -- see check_frame's module-section docstring in dynamic/harness.py). Every
VIOLATES-producing test below is a fail-before/pass-after regression test: on the pre-fix
harness, check_frame did not exist, so none of these could have been flagged by any code path.
Every CONFORMS-producing test is the matching negative control.

Uses the real shipped toy/deposit.yaml contract as a fixture (four real frame clauses, one real
effect clause) with synthetic (pre, post, args, result) tuples, mirroring
tests/test_contract_check.py's own style, rather than a synthetic contract, wherever a shipped
contract's own clause shape suffices -- synthetic contracts (via dataclasses.replace) are used
only for the two shapes deposit.yaml does not itself carry: an unmatchable frame path and a
mode: "changed" clause.

Run with: python -m unittest discover tests
"""
from __future__ import annotations

import unittest
from dataclasses import replace
from pathlib import Path

from adapters.contract_check import check_effects
from core.model import Contract, FrameClause
from core.verdict import DefectClass, Verdict
from dynamic.harness import check_frame

CONTRACTS_DIR = Path(__file__).resolve().parent.parent / "spec" / "contracts" / "toy"


def _deposit() -> Contract:
    return Contract.from_yaml(CONTRACTS_DIR / "deposit.yaml")


def _by_id(rows) -> dict:
    return {cv.clause_id: (cv, extra) for cv, extra in rows}


class TestNotApplicable(unittest.TestCase):
    def test_contract_with_no_frame_clauses_produces_no_rows(self):
        contract = replace(_deposit(), frame=())
        self.assertEqual(check_frame(contract, {}, {}, {}, {}), [])


class TestModeUnchangedConforms(unittest.TestCase):
    """The negative control: a call that changes exactly what it advertises (and nothing else)
    must conform on every frame clause, regardless of what effect_verdicts says."""

    def test_clean_deposit_conforms_on_every_frame_clause(self):
        contract = _deposit()
        pre = {"accounts": {"a": {"balance": 10.0, "owner": "alice", "frozen": False}}, "items": {}, "locks": {}}
        post = {"accounts": {"a": {"balance": 20.0, "owner": "alice", "frozen": False}}, "items": {}, "locks": {}}
        args = {"account_id": "a", "amount": 10.0}
        result = {"account_id": "a", "balance": 20.0}
        effect_verdicts = check_effects(contract, pre, post, args, result)
        self.assertTrue(all(v.verdict == Verdict.CONFORMS for v in effect_verdicts))

        rows = check_frame(contract, pre, post, args, result, effect_verdicts=effect_verdicts)
        by_id = _by_id(rows)
        self.assertEqual(len(by_id), 4)
        for clause_id, (cv, extra) in by_id.items():
            self.assertEqual(cv.verdict, Verdict.CONFORMS, f"{clause_id}: {cv}")
            self.assertIsNone(extra)


class TestModeUnchangedViolatesWithEffectFailure(unittest.TestCase):
    """A frame violation co-occurring with a failed effect clause -- the pre-registered mapping's
    first branch: VIOLATES / DefectClass.PARTIAL_EFFECT, the existing definition (collateral
    damage alongside a missed advertised effect)."""

    def test_owner_silently_swapped_alongside_a_missed_balance_increase_is_partial_effect(self):
        contract = _deposit()
        pre = {"accounts": {"a": {"balance": 10.0, "owner": "alice", "frozen": False}}, "items": {}, "locks": {}}
        # balance did NOT increase (eff.balance_increased fails) AND owner silently changed
        # (frame.owner_unchanged fails too).
        post = {"accounts": {"a": {"balance": 10.0, "owner": "mallory", "frozen": False}}, "items": {}, "locks": {}}
        args = {"account_id": "a", "amount": 10.0}
        result = {"account_id": "a", "balance": 10.0}
        effect_verdicts = check_effects(contract, pre, post, args, result)
        self.assertTrue(any(v.verdict == Verdict.VIOLATES for v in effect_verdicts))

        rows = check_frame(contract, pre, post, args, result, effect_verdicts=effect_verdicts)
        by_id = _by_id(rows)
        cv, extra = by_id["frame.owner_unchanged"]
        self.assertEqual(cv.verdict, Verdict.VIOLATES)
        self.assertEqual(cv.defect_class, DefectClass.PARTIAL_EFFECT)
        self.assertIsNotNone(cv.witness)
        self.assertIsNone(extra)
        # A sibling frame clause the mutation never touched must still conform -- the fix must
        # not sweep every OTHER frame clause into VIOLATES just because one broke.
        cv2, extra2 = by_id["frame.items_unchanged"]
        self.assertEqual(cv2.verdict, Verdict.CONFORMS)
        self.assertIsNone(extra2)


class TestModeUnchangedViolatesWithEffectsHolding(unittest.TestCase):
    """The pre-registered mapping's second branch: every effect clause holds, yet a region
    advertised unchanged moved -- not cleanly any of the six classes. VIOLATES with
    defect_class=None, plus the unadvertised_side_effect aggravating signal, never folded into a
    class count."""

    def test_owner_silently_swapped_while_balance_increases_correctly_is_an_aggravating_signal_not_a_class(self):
        contract = _deposit()
        pre = {"accounts": {"a": {"balance": 10.0, "owner": "alice", "frozen": False}}, "items": {}, "locks": {}}
        # balance DOES increase by exactly amount (eff.balance_increased conforms) but owner is
        # ALSO silently swapped -- everything advertised landed, plus something that was not.
        post = {"accounts": {"a": {"balance": 20.0, "owner": "mallory", "frozen": False}}, "items": {}, "locks": {}}
        args = {"account_id": "a", "amount": 10.0}
        result = {"account_id": "a", "balance": 20.0}
        effect_verdicts = check_effects(contract, pre, post, args, result)
        self.assertTrue(all(v.verdict == Verdict.CONFORMS for v in effect_verdicts))

        rows = check_frame(contract, pre, post, args, result, effect_verdicts=effect_verdicts)
        by_id = _by_id(rows)
        cv, extra = by_id["frame.owner_unchanged"]
        self.assertEqual(cv.verdict, Verdict.VIOLATES)
        self.assertIsNone(cv.defect_class, "must not be folded into any of the six defect classes")
        self.assertIsNotNone(extra)
        self.assertEqual(extra["aggravating_signal"], "unadvertised_side_effect")
        self.assertIn("accounts.a.owner", extra["changed_paths"])

        # frozen/items/locks -- untouched by this mutant -- must still conform.
        for clause_id in ("frame.frozen_flag_unchanged", "frame.items_unchanged", "frame.locks_unchanged"):
            cv2, extra2 = by_id[clause_id]
            self.assertEqual(cv2.verdict, Verdict.CONFORMS, f"{clause_id}: {cv2}")
            self.assertIsNone(extra2)


class TestUnmatchedFramePathIsUntestableNeverVacuous(unittest.TestCase):
    """core/frame.py's own require_match contract: a pattern matching nothing is an error, never
    a vacuous pass. check_frame must catch it and degrade to UNTESTABLE rather than crash
    run_contract or silently report CONFORMS."""

    def test_pattern_matching_neither_pre_nor_post_is_untestable(self):
        contract = replace(
            _deposit(),
            frame=(FrameClause(id="frame.ghost", path="state.does_not_exist_anywhere"),),
        )
        pre = {"accounts": {}}
        post = {"accounts": {}}
        rows = check_frame(contract, pre, post, {}, {}, effect_verdicts=[])
        self.assertEqual(len(rows), 1)
        cv, extra = rows[0]
        self.assertEqual(cv.verdict, Verdict.UNTESTABLE)
        self.assertEqual(cv.reason_code, "no_observable_state")
        self.assertIsNone(extra)

    def test_pattern_matching_only_in_post_does_not_raise_and_is_reported_as_a_change(self):
        # A brand-new key appears in post that was entirely absent from pre -- match_paths(...,
        # pre) alone would raise FrameMatchError even though the pattern is meaningful (it
        # matched in post). Unioning across both snapshots must catch this as a genuine change,
        # not blow up.
        contract = replace(
            _deposit(),
            frame=(FrameClause(id="frame.new_order", path="state.orders", mode="unchanged"),),
        )
        pre = {"accounts": {}}
        post = {"accounts": {}, "orders": {"o1": {"status": "new"}}}
        rows = check_frame(contract, pre, post, {}, {}, effect_verdicts=[])
        self.assertEqual(len(rows), 1)
        cv, extra = rows[0]
        self.assertEqual(cv.verdict, Verdict.VIOLATES)
        self.assertIsNone(cv.defect_class)
        self.assertEqual(extra["aggravating_signal"], "unadvertised_side_effect")


class TestModeChanged(unittest.TestCase):
    """mode: "changed" is schema.json's own "occasionally the clearer way to state an advertised
    effect over a wildcard path" -- its violation (the region never actually changed) is ALWAYS
    Partial Effect, regardless of what any other effect clause did (see check_frame's
    module-section docstring for why the aggravating-signal branch is incoherent for this mode)."""

    def _contract(self) -> Contract:
        return replace(
            _deposit(),
            frame=(FrameClause(id="frame.balance_must_move", path="state.accounts.*.balance", mode="changed"),),
        )

    def test_balance_actually_moving_conforms(self):
        contract = self._contract()
        pre = {"accounts": {"a": {"balance": 10.0}}}
        post = {"accounts": {"a": {"balance": 20.0}}}
        rows = check_frame(contract, pre, post, {}, {}, effect_verdicts=[])
        cv, extra = rows[0]
        self.assertEqual(cv.verdict, Verdict.CONFORMS)
        self.assertIsNone(extra)

    def test_balance_not_moving_is_partial_effect_even_with_every_effect_clause_holding(self):
        contract = self._contract()
        pre = {"accounts": {"a": {"balance": 10.0}}}
        post = {"accounts": {"a": {"balance": 10.0}}}
        # Every (empty) effect_verdicts list "holds" vacuously -- must still be partial_effect,
        # never routed through the aggravating-signal branch (that framing is incoherent here).
        rows = check_frame(contract, pre, post, {}, {}, effect_verdicts=[])
        cv, extra = rows[0]
        self.assertEqual(cv.verdict, Verdict.VIOLATES)
        self.assertEqual(cv.defect_class, DefectClass.PARTIAL_EFFECT)
        self.assertIsNone(extra)


if __name__ == "__main__":
    unittest.main()
