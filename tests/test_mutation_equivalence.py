"""Validates the sec 3 / ARCHITECTURE-FINAL.md sec 5 precision-control generators empirically:
every mutant mutation/equivalence.py can produce is run against toy/bank.py across a battery of
probe calls (success and failure paths, across every mutating tool) and its observable behaviour
-- return value (or raised message, except for the `reword` kind, which deliberately changes
message text that no predicate ever reads) plus resulting state -- is diffed bit-for-bit against
the unmutated ToyBank. A generator that ever changes behaviour on any probe here would be a
precision-control bug: it would make the corresponding real-corpus mutant a false positive waiting
to happen, not a true equivalence.
"""
from __future__ import annotations

import pathlib
import unittest
from collections import Counter

from mutation.equivalence import (
    REFACTOR_KINDS,
    TRIVIAL_KINDS,
    arithmetic_equivalent,
    enumerate_equivalence_sites,
    extract_guard_into_helper,
    reorder_independent_writes,
    rename_local_variable,
    reword_raise_message,
    select_equivalence_mutants,
)
from mutation.sites import find_function, load_class_from_source
from toy.bank import MUTATING_TOOLS, ToyBank

SOURCE = pathlib.Path(__file__).resolve().parent.parent / "toy" / "bank.py"

# One success-path and (mostly) one failure-path probe per tool -- exercises both the effect and
# the precondition-enforcement code paths each generator must leave untouched.
PROBES = [
    ("deposit", {"account_id": "acc_alice", "amount": 10.0}),
    ("deposit", {"account_id": "no_such", "amount": 10.0}),
    ("withdraw", {"account_id": "acc_bob", "amount": 5.0}),
    ("withdraw", {"account_id": "acc_bob", "amount": 9999.0}),
    ("transfer", {"from_account": "acc_alice", "to_account": "acc_bob", "amount": 10.0}),
    ("transfer", {"from_account": "acc_carol", "to_account": "acc_bob", "amount": 1.0}),
    ("freeze_account", {"account_id": "acc_alice"}),
    ("freeze_account", {"account_id": "acc_carol"}),
    ("unfreeze_account", {"account_id": "acc_carol"}),
    ("unfreeze_account", {"account_id": "acc_alice"}),
    ("reserve_item", {"item_id": "widget", "qty": 2, "account_id": "acc_alice"}),
    ("reserve_item", {"item_id": "widget", "qty": 999, "account_id": "acc_alice"}),
    ("release_item", {"item_id": "widget", "qty": 1}),
    ("release_item", {"item_id": "widget", "qty": 999}),
    ("acquire_lock", {"lock_id": "printer", "holder": "alice"}),
    ("release_lock", {"lock_id": "printer", "holder": "alice"}),
    ("resize_inventory", {"item_id": "widget", "delta": 3, "mode": "add"}),
    ("resize_inventory", {"item_id": "widget", "delta": 1, "mode": "multiply"}),
    ("tag_item", {"item_id": "widget", "tag": "new"}),
    ("tag_item", {"item_id": "widget", "tag": "hardware"}),
]


def _source() -> str:
    return SOURCE.read_text(encoding="utf-8")


def _run(cls, tool: str, args: dict):
    bank = cls()
    try:
        result = getattr(bank, tool)(**args)
        return ("ok", result, bank.state)
    except Exception as e:  # noqa: BLE001 -- comparing to the real ToyError's message, generically
        return ("err", str(e), bank.state)


class TestGeneratorsArePairwiseEquivalent(unittest.TestCase):
    """One targeted test per generator kind, each picking a concrete site and diffing full
    behaviour (state AND return/error) against the unmutated tool."""

    def _assert_identical_on_every_probe(self, cls, tool: str, *, ignore_message: bool = False):
        for probe_tool, args in PROBES:
            if probe_tool != tool:
                continue
            real = _run(ToyBank, tool, args)
            mut = _run(cls, tool, args)
            self.assertEqual(real[0], mut[0], f"{tool}{args}: ok/err status differs")
            self.assertEqual(real[2], mut[2], f"{tool}{args}: resulting state differs")
            if not (ignore_message and real[0] == "err"):
                self.assertEqual(real[1], mut[1], f"{tool}{args}: return value / message differs")

    def test_reorder_independent_writes_on_transfer(self):
        source = _source()
        import ast

        func = find_function(ast.parse(source), "transfer")
        mutated = reorder_independent_writes(func)
        self.assertIsNotNone(mutated)
        from mutation.sites import _Replacer

        tree = ast.parse(source)
        _Replacer("transfer", mutated).visit(tree)
        cls = load_class_from_source(ast.unparse(tree), "ToyBank", module_name="_eq_reorder")
        self._assert_identical_on_every_probe(cls, "transfer")

    def test_extract_guard_into_helper_on_withdraw(self):
        source = _source()
        sites = enumerate_equivalence_sites(source, ("withdraw",))
        guard_sites = [s for s in sites if s.kind == "extract_guard"]
        self.assertTrue(guard_sites)
        for site in guard_sites:  # every guard on withdraw, not just one
            mutated_source = extract_guard_into_helper(source, "withdraw", **site.params)
            cls = load_class_from_source(mutated_source, "ToyBank", module_name="_eq_extract")
            self._assert_identical_on_every_probe(cls, "withdraw")
            # And the refactor is real: a new helper method actually exists.
            self.assertTrue(any(name.startswith("_check_withdraw_") for name in vars(cls) if not name.startswith("__")))

    def test_arithmetic_equivalent_on_deposit_and_withdraw(self):
        import ast
        from mutation.sites import _Replacer

        for tool in ("deposit", "withdraw"):
            source = _source()
            func = find_function(ast.parse(source), tool)
            write_index = next(
                i for i, s in enumerate(func.body)
                if isinstance(s, ast.Assign) and isinstance(s.value, ast.BinOp)
            )
            mutated = arithmetic_equivalent(func, write_index)
            self.assertIsNotNone(mutated)
            tree = ast.parse(source)
            _Replacer(tool, mutated).visit(tree)
            cls = load_class_from_source(ast.unparse(tree), "ToyBank", module_name=f"_eq_arith_{tool}")
            self._assert_identical_on_every_probe(cls, tool)

    def test_rename_local_variable_on_deposit(self):
        import ast
        from mutation.sites import _Replacer

        source = _source()
        func = find_function(ast.parse(source), "deposit")
        mutated = rename_local_variable(func, old_name="account")
        self.assertIsNotNone(mutated)
        tree = ast.parse(source)
        _Replacer("deposit", mutated).visit(tree)
        cls = load_class_from_source(ast.unparse(tree), "ToyBank", module_name="_eq_rename")
        self._assert_identical_on_every_probe(cls, "deposit")

    def test_rename_refuses_a_parameter_name(self):
        import ast

        func = find_function(ast.parse(_source()), "deposit")
        self.assertIsNone(rename_local_variable(func, old_name="account_id"))  # a parameter

    def test_reword_raise_message_changes_text_but_nothing_else(self):
        import ast
        from mutation.sites import _Replacer

        source = _source()
        func = find_function(ast.parse(source), "withdraw")
        guard_index = next(
            i for i, s in enumerate(func.body)
            if isinstance(s, ast.If) and any(isinstance(r, ast.Raise) for r in s.body)
        )
        mutated = reword_raise_message(func, guard_index)
        self.assertIsNotNone(mutated)
        tree = ast.parse(source)
        _Replacer("withdraw", mutated).visit(tree)
        cls = load_class_from_source(ast.unparse(tree), "ToyBank", module_name="_eq_reword")
        # ignore_message=True: this generator's whole point is to change the message.
        self._assert_identical_on_every_probe(cls, "withdraw", ignore_message=True)


class TestSelectEquivalenceMutants(unittest.TestCase):
    def setUp(self):
        self.source = _source()
        self.sites = enumerate_equivalence_sites(self.source, MUTATING_TOOLS)

    def test_every_kind_has_at_least_one_site(self):
        counts = Counter(s.kind for s in self.sites)
        for kind in REFACTOR_KINDS + TRIVIAL_KINDS:
            self.assertGreater(counts[kind], 0, f"{kind} has zero sites on toy/bank.py")

    def test_selection_meets_the_thirty_and_half_refactor_quota(self):
        # sec 3 / W5: ~30 controls, at least half refactorings of advertised behaviour.
        selected = select_equivalence_mutants(self.sites, n=30, seed=20260821)
        self.assertEqual(len(selected), 30)
        refactor_count = sum(1 for s in selected if s.kind in REFACTOR_KINDS)
        self.assertGreaterEqual(refactor_count, 15)

    def test_selection_is_deterministic_under_a_fixed_seed(self):
        a = select_equivalence_mutants(self.sites, n=30, seed=5)
        b = select_equivalence_mutants(self.sites, n=30, seed=5)
        self.assertEqual(a, b)

    def test_full_selected_batch_is_behaviourally_equivalent_on_every_probe(self):
        # The end-to-end validation the build spec asks for: run the ENTIRE selected batch of ~30
        # controls against the toy domain and confirm none of them changes observable behaviour
        # on any probe (message text excluded only for the `reword` kind, by construction).
        selected = select_equivalence_mutants(self.sites, n=30, seed=20260821)
        self.assertEqual(len(selected), 30)
        mismatches = []
        for i, site in enumerate(selected):
            mutated_source = site.apply(self.source)
            cls = load_class_from_source(mutated_source, "ToyBank", module_name=f"_eq_batch_{i}")
            for probe_tool, args in PROBES:
                if probe_tool != site.tool:
                    continue
                real = _run(ToyBank, site.tool, args)
                mut = _run(cls, site.tool, args)
                state_ok = real[2] == mut[2]
                status_ok = real[0] == mut[0]
                message_ok = (site.kind == "reword" and real[0] == "err") or real[1] == mut[1]
                if not (state_ok and status_ok and message_ok):
                    mismatches.append((site, probe_tool, args))
        self.assertEqual(mismatches, [], f"{len(mismatches)} precision-control mutant(s) changed behaviour: {mismatches[:5]}")


if __name__ == "__main__":
    unittest.main()
