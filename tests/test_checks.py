"""Tests for static_check/checks.py.

Two layers: synthetic snippets (fast, no repo dependency) that isolate one check's rule at a
time, and the acceptance-criterion tests that run the checks against the real pinned-commit
sources and require them to flag FINDINGS-VERIFIED.md Findings 2, 3, 5, 6, and 7 with no
tool-specific special-casing anywhere in checks.py itself.

Run with: python -m unittest discover tests
"""
import unittest
from pathlib import Path

from static_check.checks import run_checks_on_module

REPO_ROOT = Path(__file__).resolve().parent.parent
TAU2_SRC = REPO_ROOT / ".tau2-src-c3398666" / "src" / "tau2" / "domains"
AGENTDOJO_SRC = REPO_ROOT / "repos" / "agentdojo" / "src" / "agentdojo" / "default_suites" / "v1" / "tools"
MMTOOLSANDBOX_SRC = REPO_ROOT / "repos" / "mmtoolsandbox" / "mmtoolsandbox" / "tools" / "mini"


def _flags_for(text: str, label: str = "synthetic.py"):
    return run_checks_on_module(label, text)


class TestConstantSuccessReturn(unittest.TestCase):
    def test_flags_literal_return_after_state_write(self):
        src = (
            "class T:\n"
            "    def do_thing(self, x):\n"
            "        self.state.value = x\n"
            "        return {'status': 'ok'}\n"
        )
        flags = [f for f in _flags_for(src) if f.check == "constant_success_return"]
        self.assertEqual(len(flags), 1)
        self.assertEqual(flags[0].qualname, "T.do_thing")

    def test_does_not_flag_return_that_depends_on_args(self):
        src = (
            "class T:\n"
            "    def do_thing(self, x):\n"
            "        self.state.value = x\n"
            "        return {'status': 'ok', 'value': x}\n"
        )
        flags = [f for f in _flags_for(src) if f.check == "constant_success_return"]
        self.assertEqual(flags, [])

    def test_does_not_flag_non_mutating_function(self):
        src = "class T:\n    def get_thing(self):\n        return {'status': 'ok'}\n"
        flags = [f for f in _flags_for(src) if f.check == "constant_success_return"]
        self.assertEqual(flags, [])


class TestDeadGuard(unittest.TestCase):
    def test_flags_commented_out_if_raise(self):
        src = (
            "class T:\n"
            "    def refuel(self, line):\n"
            "        # if line.status != ACTIVE:\n"
            "        #     raise ValueError('must be active')\n"
            "        line.amount += 1\n"
        )
        flags = [f for f in _flags_for(src) if f.check == "dead_guard"]
        self.assertEqual(len(flags), 1)
        self.assertEqual(flags[0].line, 3)
        self.assertEqual(flags[0].end_line, 4)

    def test_does_not_flag_a_lone_explanatory_comment(self):
        src = (
            "class T:\n"
            "    def refuel(self, line):\n"
            "        # this line intentionally left without a check\n"
            "        line.amount += 1\n"
        )
        flags = [f for f in _flags_for(src) if f.check == "dead_guard"]
        self.assertEqual(flags, [])

    def test_does_not_flag_live_guard(self):
        src = (
            "class T:\n"
            "    def refuel(self, line):\n"
            "        if line.status != 'ACTIVE':\n"
            "            raise ValueError('must be active')\n"
            "        line.amount += 1\n"
        )
        flags = [f for f in _flags_for(src) if f.check == "dead_guard"]
        self.assertEqual(flags, [])


class TestUnusedParameter(unittest.TestCase):
    def test_flags_parameter_never_referenced(self):
        src = "def f(a, b):\n    return {'a': a}\n"
        flags = {f.check: f for f in _flags_for(src) if f.check == "unused_parameter"}
        self.assertIn("unused_parameter", flags)
        self.assertIn("'b'", flags["unused_parameter"].message)
        self.assertIn("never referenced", flags["unused_parameter"].message)

    def test_flags_parameter_read_only_inside_fstring_return(self):
        src = "def f(a, b):\n    x = a + 1\n    return f'ok {b}'\n"
        flags = [f for f in _flags_for(src) if f.check == "unused_parameter"]
        self.assertEqual(len(flags), 1)
        self.assertIn("'b'", flags[0].message)
        self.assertIn("f-string", flags[0].message)

    def test_does_not_flag_parameter_forwarded_as_a_live_call_argument_in_a_return(self):
        # regression test for the first-draft false positive: a parameter forwarded live as a
        # call keyword argument inside a `return` is operative, not cosmetic.
        src = "def f(user_email):\n    return dispatch(user_email=user_email)\n"
        flags = [f for f in _flags_for(src) if f.check == "unused_parameter"]
        self.assertEqual(flags, [])

    def test_does_not_flag_parameter_used_in_assignment(self):
        src = "class T:\n    def f(self, a):\n        self.x = a\n        return {'ok': True}\n"
        flags = [f for f in _flags_for(src) if f.check == "unused_parameter"]
        self.assertEqual(flags, [])

    def test_logger_only_use_is_cosmetic(self):
        src = "import logging\nlogger = logging.getLogger(__name__)\ndef f(a):\n    logger.info(f'got {a}')\n    return {'ok': True}\n"
        flags = [f for f in _flags_for(src) if f.check == "unused_parameter"]
        self.assertEqual(len(flags), 1)
        self.assertIn("'a'", flags[0].message)


class TestTruthinessGuard(unittest.TestCase):
    def test_flags_bare_truthiness_on_optional_bool(self):
        src = "def f(recurring):\n    if recurring:\n        x = 1\n    return x\n"
        # give recurring an annotation via a second, annotated definition
        src = "def f(recurring: bool | None = None):\n    if recurring:\n        x = 1\n    return {'ok': True}\n"
        flags = [f for f in _flags_for(src) if f.check == "truthiness_guard"]
        self.assertEqual(len(flags), 1)
        self.assertIn("recurring", flags[0].message)

    def test_flags_negated_form(self):
        src = "def f(amount: float | None = None):\n    if not amount:\n        return {'ok': False}\n    return {'ok': True}\n"
        flags = [f for f in _flags_for(src) if f.check == "truthiness_guard"]
        self.assertEqual(len(flags), 1)

    def test_does_not_flag_explicit_none_check(self):
        src = "def f(amount: float | None = None):\n    if amount is not None:\n        x = amount\n    return {'ok': True}\n"
        flags = [f for f in _flags_for(src) if f.check == "truthiness_guard"]
        self.assertEqual(flags, [])

    def test_does_not_flag_param_with_no_falsy_meaningful_type(self):
        src = "class Foo: pass\ndef f(thing: 'Foo'):\n    if thing:\n        x = 1\n    return {'ok': True}\n"
        flags = [f for f in _flags_for(src) if f.check == "truthiness_guard"]
        self.assertEqual(flags, [])

    def test_does_not_flag_compare_expression(self):
        src = "def f(amount: float):\n    if amount <= 0:\n        raise ValueError('x')\n    return {'ok': True}\n"
        flags = [f for f in _flags_for(src) if f.check == "truthiness_guard"]
        self.assertEqual(flags, [])


class TestUnpairedStateWrite(unittest.TestCase):
    def test_flags_missing_inverse_write(self):
        src = (
            "class T:\n"
            "    def book_reservation(self, n):\n"
            "        self.flight.available_seats -= n\n"
            "        self.db.reservations[1] = 'r'\n"
            "    def cancel_reservation(self, rid):\n"
            "        self.db.reservations[rid].status = 'cancelled'\n"
        )
        flags = [f for f in _flags_for(src) if f.check == "unpaired_state_write"]
        cancel_flags = [f for f in flags if f.qualname == "T.cancel_reservation"]
        self.assertEqual(len(cancel_flags), 1)
        self.assertIn("available_seats", cancel_flags[0].message)

    def test_does_not_flag_when_field_is_referenced_in_both(self):
        src = (
            "class T:\n"
            "    def book_reservation(self, n):\n"
            "        self.flight.available_seats -= n\n"
            "    def cancel_reservation(self, n):\n"
            "        self.flight.available_seats += n\n"
        )
        flags = [f for f in _flags_for(src) if f.check == "unpaired_state_write"]
        self.assertEqual(flags, [])

    def test_no_flag_when_no_paired_function_exists(self):
        src = "class T:\n    def book_reservation(self, n):\n        self.flight.available_seats -= n\n"
        flags = [f for f in _flags_for(src) if f.check == "unpaired_state_write"]
        self.assertEqual(flags, [])

    def test_pairing_works_at_module_scope_too(self):
        src = (
            "def create_widget(store):\n"
            "    store.widgets.append(1)\n"
            "def delete_widget(store):\n"
            "    pass\n"
        )
        flags = [f for f in _flags_for(src) if f.check == "unpaired_state_write" and f.qualname == "delete_widget"]
        self.assertEqual(len(flags), 1)
        self.assertIn("widgets", flags[0].message)


@unittest.skipUnless(TAU2_SRC.exists(), "tau2 pinned-commit source copy not present")
class TestAcceptanceFinding2AndFinding3(unittest.TestCase):
    """FINDINGS-VERIFIED.md Findings 2 and 3, tau2-bench @ c3398666."""

    def test_finding_2_dead_guard_at_refuel_data(self):
        text = (TAU2_SRC / "telecom" / "tools.py").read_text(encoding="utf-8")
        flags = run_checks_on_module("telecom/tools.py", text)
        hits = [f for f in flags if f.check == "dead_guard" and f.qualname == "TelecomTools.refuel_data"]
        self.assertEqual(len(hits), 1, f"expected exactly one dead_guard flag on refuel_data, got {flags}")
        self.assertEqual(hits[0].line, 629)
        self.assertEqual(hits[0].end_line, 630)

    def test_finding_3_unpaired_write_at_cancel_reservation(self):
        text = (TAU2_SRC / "airline" / "tools.py").read_text(encoding="utf-8")
        flags = run_checks_on_module("airline/tools.py", text)
        hits = [
            f
            for f in flags
            if f.check == "unpaired_state_write" and f.qualname == "AirlineTools.cancel_reservation"
        ]
        self.assertEqual(len(hits), 1)
        self.assertIn("available_seats", hits[0].message)


@unittest.skipUnless(AGENTDOJO_SRC.exists(), "agentdojo pinned-commit clone not present")
class TestAcceptanceFinding5AndFinding6(unittest.TestCase):
    """FINDINGS-VERIFIED.md Findings 5 and 6, agentdojo @ 089ed468."""

    def test_finding_5_truthiness_guard_on_recurring(self):
        text = (AGENTDOJO_SRC / "banking_client.py").read_text(encoding="utf-8")
        flags = run_checks_on_module("banking_client.py", text)
        hits = [
            f
            for f in flags
            if f.check == "truthiness_guard"
            and f.qualname == "update_scheduled_transaction"
            and "'recurring'" in f.message
        ]
        self.assertEqual(len(hits), 1, f"expected one truthiness_guard flag on recurring, got {flags}")

    def test_finding_6_end_time_unused(self):
        text = (AGENTDOJO_SRC / "travel_booking_client.py").read_text(encoding="utf-8")
        flags = run_checks_on_module("travel_booking_client.py", text)
        hits = [
            f
            for f in flags
            if f.check == "unused_parameter" and f.qualname == "reserve_car_rental" and "'end_time'" in f.message
        ]
        self.assertEqual(len(hits), 1, f"expected one unused_parameter flag on end_time, got {flags}")
        self.assertIn("f-string", hits[0].message)


@unittest.skipUnless(MMTOOLSANDBOX_SRC.exists(), "mmtoolsandbox pinned-commit clone not present")
class TestAcceptanceFinding7(unittest.TestCase):
    """FINDINGS-VERIFIED.md Finding 7, mmtoolsandbox @ 1e8e9324."""

    def test_finding_7_sort_by_never_referenced(self):
        text = (MMTOOLSANDBOX_SRC / "venmo.py").read_text(encoding="utf-8")
        flags = run_checks_on_module("mini/venmo.py", text)
        hits = [
            f
            for f in flags
            if f.check == "unused_parameter" and f.qualname == "venmo_social" and "'sort_by'" in f.message
        ]
        self.assertEqual(len(hits), 1, f"expected one unused_parameter flag on sort_by, got {flags}")
        self.assertIn("never referenced", hits[0].message)


if __name__ == "__main__":
    unittest.main()
