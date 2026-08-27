"""Regression pin for the MM-ToolSandbox `set_wifi_status` false positive (final pass before
checker-freeze-v1): the sweep flagged `pre.not_low_battery_when_turning_on` as VIOLATES with an
`IndexError: index 0 is out of bounds` instead of the contract's declared error signal.

Root cause, confirmed by reading `repos/mmtoolsandbox/mmtoolsandbox/common/execution_context.py`
directly (not assumed): `adapters/_mmtoolsandbox_worker.py`'s `_cmd_fresh_env` used to hand every
tool_sandbox call a bare `ExecutionContext()`, whose `SETTING` table starts with ONLY the all-None
"headguard" row `ExecutionContext.get_database(...)` -- what every real tool reads through --
drops by default. `mmtoolsandbox/tools/tool_sandbox/setting.py`'s `get_boolean_settings`/
`set_boolean_settings` (code this project does not own or modify) then indexes into a genuinely
EMPTY dataframe and raises IndexError. A real MM-ToolSandbox scenario never reaches this state:
`mmtoolsandbox/datasets/scenarios.py`'s `_create_base_scenarios` seeds this exact table via
`setting_initial_database_state` (the dataset's own "base" collection) before any tool runs. This
is not a MM-ToolSandbox defect -- it is this adapter under-initializing its own environment, and
(separately) exposing the internal headguard row to the checker as if it were real state.

Two fixes, both in `adapters/_mmtoolsandbox_worker.py`:
  1. `_cmd_fresh_env` now seeds `SETTING` with the real "base" initial row (same call the
     benchmark's own base scenario makes) instead of leaving the table artificially empty.
  2. `_cmd_snapshot` now drops the headguard row (`ExecutionContext.drop_headguard`, the same
     public classmethod `get_database` uses) from every namespace before returning, so a snapshot
     never invents a row the underlying store does not actually have.

A third, narrower fix lives in `spec/contracts/mmtoolsandbox/set_wifi_status.yaml`: with a real
seeded SETTING row, `pre.state_actually_changes`'s own violate-probe becomes reachable for the
first time (previously permanently masked by the phantom all-null row, under which the clause's
predicate could never evaluate False). That precondition's real violation raises ValueError, not
the contract's previously-declared `error_type: PermissionError` -- accurate only for the OTHER
precondition (`pre.not_low_battery_when_turning_on`). Left in place, this fix would have traded
one false positive for another. `error_type` was removed from the contract's
`on_precondition_violation.expect` (error_signal/state_delta claims, which hold for both
preconditions, are untouched) -- see that file's own comment.

Run with: python -m unittest discover tests
"""
from __future__ import annotations

import unittest
from pathlib import Path

from adapters.mmtoolsandbox import MMToolSandboxAdapter, MMToolSandboxAdapterError
from core.canonical import diff
from core.model import Contract
from core.verdict import Verdict
from dynamic.harness import run_contract

CONTRACTS_DIR = Path(__file__).resolve().parent.parent / "spec" / "contracts" / "mmtoolsandbox"


def _new_adapter_or_skip() -> MMToolSandboxAdapter:
    try:
        adapter = MMToolSandboxAdapter()
    except MMToolSandboxAdapterError as e:
        raise unittest.SkipTest(f"mm-toolsandbox adapter venv not provisioned: {e}")
    try:
        adapter._send({"cmd": "ping"})
    except MMToolSandboxAdapterError as e:
        adapter.close()
        raise unittest.SkipTest(f"mm-toolsandbox worker did not start: {e}")
    return adapter


class TestFreshEnvSeedsRealSettingsRow(unittest.TestCase):
    def setUp(self):
        self.adapter = _new_adapter_or_skip()

    def tearDown(self):
        self.adapter.close()

    def test_setting_table_is_exactly_one_real_row_not_a_null_headguard(self):
        env = self.adapter.fresh_env("tool_sandbox")
        snap = self.adapter.snapshot(env)
        setting_rows = snap["SETTING"]
        self.assertEqual(len(setting_rows), 1, f"expected exactly one real SETTING row, got {setting_rows}")
        row = setting_rows[0]
        # The dataset's own "base" collection (mmtoolsandbox/datasets/initial_database_states/
        # base.py's setting_initial_database_state) -- a real row, not the all-None headguard.
        self.assertIsNotNone(row["device_id"])
        self.assertEqual(row["wifi"], True)
        self.assertEqual(row["cellular"], True)
        self.assertEqual(row["location_service"], True)
        self.assertEqual(row["low_battery_mode"], False)

    def test_untouched_namespaces_snapshot_as_genuinely_empty_not_a_phantom_row(self):
        """The headguard-drop fix in `_cmd_snapshot` is namespace-generic, not SETTING-specific:
        REMINDER/CALENDARS were never seeded and must report as an empty list, never a length-1
        all-null row this adapter invented for JSON stability."""
        env = self.adapter.fresh_env("tool_sandbox")
        snap = self.adapter.snapshot(env)
        self.assertEqual(snap["REMINDER"], [])
        self.assertEqual(snap["CALENDARS"], [])


class TestSetWifiStatusLowBatteryPrecondition(unittest.TestCase):
    """Exact regression pin for the reported defect: turning wifi on while low battery mode is
    active must be rejected with the contract's declared PermissionError, never crash the worker
    with an IndexError from an under-initialized environment."""

    def setUp(self):
        self.adapter = _new_adapter_or_skip()
        self.contract = Contract.from_yaml(CONTRACTS_DIR / "set_wifi_status.yaml")

    def tearDown(self):
        self.adapter.close()

    def test_turning_wifi_on_during_low_battery_raises_permission_error_not_indexerror(self):
        env = self.adapter.fresh_env("tool_sandbox")
        low_battery = self.adapter.invoke(env, "set_low_battery_mode_status", {"on": True})
        self.assertTrue(low_battery.success, low_battery.error)

        pre = self.adapter.snapshot(env)
        result = self.adapter.invoke(env, "set_wifi_status", {"on": True})
        post = self.adapter.snapshot(env)

        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)
        self.assertNotIn("IndexError", result.error)
        self.assertTrue(result.error.startswith("PermissionError"), result.error)
        self.assertEqual(diff(pre, post), {}, "a rejected call must leave no state delta")

    def test_run_contract_reports_no_violates_for_set_wifi_status(self):
        """The checker's strongest claim is zero false positives -- pin the whole contract run,
        not just the one precondition, so a future regression anywhere in this tool's clauses
        is caught the same way this one was found: by reading sweep output."""
        rows = run_contract(self.adapter, self.contract, "tool_sandbox", seed=0)
        violates = [r for r in rows if r["verdict"] == Verdict.VIOLATES.value]
        self.assertEqual(violates, [], f"set_wifi_status must not VIOLATES on a clean run: {violates}")


if __name__ == "__main__":
    unittest.main()
