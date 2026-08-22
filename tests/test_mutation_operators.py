"""Behavioural tests for the six AST mutation operators, run against toy/bank.py -- CLAUDE.md's
build spec calls for exactly this: "debug detectors independently of benchmark quirks" on a toy
domain. Every test here materializes a real mutant module (mutation/sites.py), execs it, and
observes the concrete behavioural difference (or absence of one) against a fresh toy/bank.py
instance, rather than asserting on the mutated AST's shape.
"""
from __future__ import annotations

import copy
import pathlib
import unittest

from mutation.operators import MutationError, is_guard, is_state_write, m_ignarg, m_invar, m_partial, m_phantom, m_precond, m_reset
from mutation.sites import enumerate_sites, find_function, load_class_from_source, materialize_mutant_source
from toy.bank import MUTATING_TOOLS, ToyBank

SOURCE = pathlib.Path(__file__).resolve().parent.parent / "toy" / "bank.py"


def _source() -> str:
    return SOURCE.read_text(encoding="utf-8")


def _sites():
    return enumerate_sites(_source(), MUTATING_TOOLS, reset_names=("reset",))


def _first(sites, operator, tool, **params):
    for s in sites:
        if s.operator == operator and s.tool == tool and all(s.params.get(k) == v for k, v in params.items()):
            return s
    raise AssertionError(f"no site found: {operator} {tool} {params}")


class TestMPhantom(unittest.TestCase):
    def test_deposit_becomes_a_noop_that_reports_success(self):
        sites = _sites()
        site = _first(sites, "M-PHANTOM", "deposit")
        Cls = load_class_from_source(site.apply(_source()), "ToyBank")
        bank = Cls()
        before = copy.deepcopy(bank.state)
        result = bank.deposit(account_id="acc_alice", amount=10.0)
        # Signature/return preserved: still a dict keyed the same way, still no exception.
        self.assertIn("account_id", result)
        self.assertIn("balance", result)
        # But the effect never landed.
        self.assertEqual(before, bank.state)

    def test_reset_with_no_return_statement_stubs_to_return_none(self):
        # reset() has no `return` at all -- exercises m_phantom's no-Return fallback branch.
        tree_source = _source()
        mutated = materialize_mutant_source(tree_source, "reset", "M-PHANTOM", {})
        Cls = load_class_from_source(mutated, "ToyBank")
        bank = Cls()
        before = copy.deepcopy(bank.state)
        bank.deposit(account_id="acc_alice", amount=10.0)
        self.assertIsNone(bank.reset())  # stub returns None, matching the real reset()'s -> None
        # reset() is now a phantom no-op: state after "reset" is the post-deposit state, not the
        # initial one -- the mutant is trivially detectable by mutation/score.py's survival check.
        self.assertNotEqual(bank.state["accounts"]["acc_alice"]["balance"], before["accounts"]["acc_alice"]["balance"])

    def test_scrubs_locals_the_removed_body_would_have_computed(self):
        # release_lock's return references `lock["held_by"]`/`lock["count"]` -- both locals that
        # only exist because of statements m_phantom deletes. Must not raise NameError.
        sites = _sites()
        site = _first(sites, "M-PHANTOM", "release_lock")
        Cls = load_class_from_source(site.apply(_source()), "ToyBank")
        bank = Cls()
        result = bank.release_lock(lock_id="printer", holder="nobody")  # no precondition holds
        self.assertEqual(result, {"lock_id": "printer", "held_by": None, "count": None})

    def test_scrubbing_does_not_break_a_builtin_call_wrapping_an_undefined_local(self):
        # Regression test: tag_item returns {"tags": list(item["tags"])}. A first cut of the
        # scrub replaced only the undefined `item["tags"]` leaf, leaving `list(None)` -- which
        # compiles but raises TypeError at call time ("NoneType object is not iterable"),
        # defeating M-PHANTOM's whole point (a mutant that *looks* like a clean success). The
        # fix scrubs at the level of the whole dict VALUE, so `list(...)` never sees a bare None
        # as its argument -- the entire value collapses to None instead.
        sites = _sites()
        site = _first(sites, "M-PHANTOM", "tag_item")
        Cls = load_class_from_source(site.apply(_source()), "ToyBank")
        bank = Cls()
        result = bank.tag_item(item_id="widget", tag="new-tag")  # must not raise
        self.assertEqual(result, {"item_id": "widget", "tags": None})
        self.assertEqual(bank.state["items"]["widget"]["tags"], ["hardware"])  # untouched


class TestMPrecond(unittest.TestCase):
    def test_delete_mode_lets_a_precondition_violating_call_through(self):
        sites = _sites()
        # withdraw's guard ordering: 0 exists, 1 frozen, 2 amount>0, 3? -- find the balance guard
        # structurally (its test compares .balance) rather than hard-coding an index.
        source = _source()
        func = find_function(__import__("ast").parse(source), "withdraw")
        balance_guard_index = next(
            i for i, s in enumerate(func.body)
            if is_guard(s) and "balance" in __import__("ast").dump(s.test)
        )
        site = _first(sites, "M-PRECOND", "withdraw", body_index=balance_guard_index, mode="delete")
        Cls = load_class_from_source(site.apply(source), "ToyBank")
        bank = Cls()
        result = bank.withdraw(account_id="acc_bob", amount=99999.0)  # would legitimately raise
        self.assertEqual(result["balance"], 50.0 - 99999.0)  # overdraft allowed through

    def test_negate_mode_inverts_the_condition(self):
        sites = _sites()
        site = _first(sites, "M-PRECOND", "freeze_account", mode="negate")
        Cls = load_class_from_source(site.apply(_source()), "ToyBank")
        bank = Cls()
        # freeze_account's guards are (account exists), (not already frozen). Negating either
        # flips which calls succeed vs raise relative to the real tool -- assert *some* call's
        # outcome differs from the real ToyBank, without assuming which guard was negated.
        real = ToyBank()
        outcomes_differ = False
        for account_id in ("acc_alice", "acc_carol", "no_such_account"):
            mutant_raised = err = None
            try:
                Cls().freeze_account(account_id=account_id)
            except Exception as e:  # noqa: BLE001
                mutant_raised = True
            real_raised = None
            try:
                ToyBank().freeze_account(account_id=account_id)
            except Exception:
                real_raised = True
            if bool(mutant_raised) != bool(real_raised):
                outcomes_differ = True
        self.assertTrue(outcomes_differ, "negating a guard must change accept/reject behaviour for at least one probe")

    def test_wrong_index_is_rejected(self):
        source = _source()
        import ast

        func = find_function(ast.parse(source), "deposit")
        with self.assertRaises(MutationError):
            m_precond(func, body_index=len(func.body) - 1)  # the return statement, not a guard


class TestMIgnarg(unittest.TestCase):
    def test_shadowed_argument_no_longer_influences_the_effect(self):
        sites = _sites()
        site = _first(sites, "M-IGNARG", "resize_inventory", arg_name="delta")
        Cls = load_class_from_source(site.apply(_source()), "ToyBank")
        bank = Cls()
        result = bank.resize_inventory(item_id="gadget", delta=3, mode="add")
        # delta is shadowed to 0 (int default) -- qty must NOT have moved by the caller's delta.
        self.assertEqual(result["qty"], 5)  # gadget's initial qty, unchanged despite delta=3

    def test_default_for_annotation_covers_declared_types(self):
        from mutation.operators import default_for_annotation
        import ast

        src = "def f(a: str, b: int, c: float, d: bool, e): pass"
        func = ast.parse(src).body[0]
        defaults = {a.arg: default_for_annotation(a) for a in func.args.args}
        self.assertEqual(defaults, {"a": "", "b": 0, "c": 0.0, "d": False, "e": None})

    def test_unknown_argument_name_is_rejected(self):
        import ast

        func = find_function(ast.parse(_source()), "deposit")
        with self.assertRaises(MutationError):
            m_ignarg(func, arg_name="does_not_exist")


class TestMPartial(unittest.TestCase):
    def test_deletes_one_of_transfers_two_writes_leaving_the_other_intact(self):
        sites = _sites()
        transfer_partial_sites = [s for s in sites if s.operator == "M-PARTIAL" and s.tool == "transfer"]
        self.assertEqual(len(transfer_partial_sites), 2)
        outcomes = []
        for site in transfer_partial_sites:
            Cls = load_class_from_source(site.apply(_source()), "ToyBank")
            bank = Cls()
            bank.transfer(from_account="acc_alice", to_account="acc_bob", amount=10.0)
            outcomes.append((bank.state["accounts"]["acc_alice"]["balance"], bank.state["accounts"]["acc_bob"]["balance"]))
        # One mutant leaves alice's debit applied but bob's credit missing; the other the reverse.
        self.assertIn((90.0, 50.0), outcomes)
        self.assertIn((100.0, 60.0), outcomes)

    def test_rejects_a_non_write_index(self):
        import ast

        func = find_function(ast.parse(_source()), "transfer")
        # index 0 in transfer's body is a guard/lookup-adjacent statement chain start, not itself
        # a write -- use the true first statement (a local lookup) to prove non-writes are refused.
        with self.assertRaises(MutationError):
            m_partial(func, body_index=0)


class TestMInvar(unittest.TestCase):
    def test_release_lock_leaks_the_holder(self):
        sites = _sites()
        site = _first(sites, "M-INVAR", "release_lock")
        Cls = load_class_from_source(site.apply(_source()), "ToyBank")
        bank = Cls()
        bank.acquire_lock(lock_id="printer", holder="alice")
        bank.release_lock(lock_id="printer", holder="alice")
        # count correctly reaches 0, but held_by is never cleared -- a real, permanent leak.
        self.assertEqual(bank.state["locks"]["printer"]["count"], 0)
        self.assertEqual(bank.state["locks"]["printer"]["held_by"], "alice")

    def test_rejects_a_guard_as_an_invar_site(self):
        import ast

        func = find_function(ast.parse(_source()), "withdraw")
        guard_index = next(i for i, s in enumerate(func.body) if is_guard(s))
        with self.assertRaises(MutationError):
            m_invar(func, if_index=guard_index, branch="body", branch_index=0)


class TestMReset(unittest.TestCase):
    def test_deleting_the_accounts_reassignment_leaks_across_reset(self):
        sites = _sites()
        # Try every M-RESET site and confirm at least one reproduces the documented accounts-leak
        # (module docstring / ARCHITECTURE.md's Reset Leak shape) -- there are 5 sites (one per
        # field assignment in reset()), and this asserts on the observable behaviour, not on
        # which body_index happens to correspond to "accounts" today.
        leaked = False
        for s in [s for s in sites if s.operator == "M-RESET"]:
            Cls = load_class_from_source(s.apply(_source()), "ToyBank")
            bank = Cls()
            bank.deposit(account_id="acc_alice", amount=10.0)
            bank.reset()
            if bank.state["accounts"]["acc_alice"]["balance"] != 100.0:
                leaked = True
        self.assertTrue(leaked, "at least one M-RESET site must leave a post-deposit balance across reset()")

    def test_rejects_out_of_range_index(self):
        import ast

        func = find_function(ast.parse(_source()), "reset")
        with self.assertRaises(MutationError):
            m_reset(func, body_index=999)


class TestStructuralPredicates(unittest.TestCase):
    def test_is_guard_true_only_for_raising_no_else_ifs(self):
        import ast

        raising = ast.parse("if x:\n    raise ValueError('x')").body[0]
        self.assertTrue(is_guard(raising))
        with_else = ast.parse("if x:\n    raise ValueError('x')\nelse:\n    y = 1").body[0]
        self.assertFalse(is_guard(with_else))
        non_raising = ast.parse("if x:\n    y = 1").body[0]
        self.assertFalse(is_guard(non_raising))

    def test_is_state_write_distinguishes_lookup_from_write(self):
        import ast

        lookup = ast.parse("account = state['accounts'][id]").body[0]
        self.assertFalse(is_state_write(lookup))
        subscript_write = ast.parse("account['balance'] = 1").body[0]
        self.assertTrue(is_state_write(subscript_write))
        attr_write = ast.parse("lock.count = 1").body[0]
        self.assertTrue(is_state_write(attr_write))
        append_call = ast.parse("state['log'].append(1)").body[0]
        self.assertTrue(is_state_write(append_call))
        plain_call = ast.parse("print(1)").body[0]
        self.assertFalse(is_state_write(plain_call))


if __name__ == "__main__":
    unittest.main()
