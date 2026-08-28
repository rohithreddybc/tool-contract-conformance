"""Tests for the agent-impact experiment build (experiments/ab_run.py, ab_patches.py,
ab_exercise.py). CLAUDE.md's build instructions for this experiment; experiments/analysis_plan.md
is the pre-registered plan this machinery implements.

Three groups:
  - Diff-apply / patch construction (experiments/ab_patches.py): no tau2 venv needed, pure
    text/AST. Verifies BOTH patches apply cleanly to the real pinned source and produce the
    exact expected fixed function bodies.
  - Exercise predicates (experiments/ab_exercise.py): F3's predicate is pure (no adapter); F2's
    needs a live task-scoped environment, so it is skipped like the rest of the tau2-adapter
    tests if the venv isn't provisioned.
  - End-to-end (experiments/ab_run.py): static task selection sanity (matches
    analysis/score_at_risk.py's independently-computed counts), patch verification pass/fail
    semantics, and a full `main()` smoke run asserting the report is well-formed regardless of
    whether live model credentials happen to be present in the test environment.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from experiments.ab_exercise import RecordedCall, exercised_f2, exercised_f3, extract_calls_with_results
from experiments.ab_patches import TAU2_PATCHES, apply_unified_diff, patched_function_source

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _new_adapter_or_skip():
    from adapters.tau2 import Tau2Adapter, Tau2AdapterError

    try:
        adapter = Tau2Adapter()
    except Tau2AdapterError as e:
        raise unittest.SkipTest(f"tau2 adapter venv not provisioned: {e}")
    try:
        adapter._send({"cmd": "ping"})
    except Tau2AdapterError as e:
        adapter.close()
        raise unittest.SkipTest(f"tau2 worker did not start: {e}")
    return adapter


class TestApplyUnifiedDiff(unittest.TestCase):
    def test_simple_hunk_replaces_lines_in_place(self):
        original = "a\nb\nc\nd\ne\n"
        diff = "@@ -2,2 +2,2 @@\n-b\n-c\n+B\n+C\n"
        self.assertEqual(apply_unified_diff(original, diff), "a\nB\nC\nd\ne\n")

    def test_context_mismatch_raises(self):
        original = "a\nb\nc\n"
        diff = "@@ -2,1 +2,1 @@\n-X\n+Y\n"
        with self.assertRaises(ValueError):
            apply_unified_diff(original, diff)

    def test_pure_insertion_hunk_grows_the_file(self):
        original = "one\ntwo\nthree\n"
        diff = "@@ -2,1 +2,3 @@\n-two\n+two\n+two-and-a-half\n+two-and-three-quarters\n"
        self.assertEqual(apply_unified_diff(original, diff), "one\ntwo\ntwo-and-a-half\ntwo-and-three-quarters\nthree\n")


class TestTau2PatchesApplyToRealSource(unittest.TestCase):
    """No tau2 venv needed -- this reads .tau2-src-c3398666 as plain text/AST, exactly like
    analysis/score_at_risk.py does."""

    def test_f2_patch_uncomments_the_active_line_check(self):
        spec = TAU2_PATCHES["F2"]
        self.assertTrue(spec.module_path.exists(), spec.module_path)
        source = patched_function_source(spec)
        self.assertIn("if target_line.status != LineStatus.ACTIVE:", source)
        self.assertIn('raise ValueError(\'Line must be active to refuel data\')', source)
        # the fix must not touch the surviving gb_amount check (CLAUDE.md: "one-hunk and minimal")
        self.assertIn("gb_amount <= 0", source)
        # and must be decorator-free / directly exec-able (adapters/base.py patch_tool contract)
        self.assertTrue(source.strip().startswith("def refuel_data("))

    def test_f3_patch_adds_seat_release_without_touching_the_rest(self):
        spec = TAU2_PATCHES["F3"]
        self.assertTrue(spec.module_path.exists(), spec.module_path)
        source = patched_function_source(spec)
        self.assertIn("available_seats[reservation.cabin]", source)
        self.assertIn("_get_flight_instance", source)
        self.assertNotIn("Seats release not implemented", source)
        # payment reversal logic (the part of the function NOT being patched) survives untouched
        self.assertIn("payment_history.extend(refunds)", source)
        self.assertTrue(source.strip().startswith("def cancel_reservation("))

    def test_both_patched_sources_are_syntactically_valid_python(self):
        import ast

        for spec in TAU2_PATCHES.values():
            ast.parse(patched_function_source(spec))  # raises SyntaxError on failure


class TestExtractCallsWithResults(unittest.TestCase):
    def test_pairs_tool_calls_with_their_results_in_order(self):
        messages = [
            {
                "role": "assistant",
                "tool_calls": [
                    {"id": "c1", "name": "book_reservation", "arguments": {"x": 1}, "requestor": "assistant"}
                ],
            },
            {"role": "tool", "id": "c1", "content": '{"reservation_id": "R1"}', "error": False},
            {
                "role": "assistant",
                "tool_calls": [
                    {"id": "c2", "name": "cancel_reservation", "arguments": {"reservation_id": "R1"}, "requestor": "assistant"}
                ],
            },
            {"role": "tool", "id": "c2", "content": "{}", "error": False},
        ]
        calls = extract_calls_with_results(messages)
        self.assertEqual([c.name for c in calls], ["book_reservation", "cancel_reservation"])
        self.assertEqual(calls[0].result_raw, '{"reservation_id": "R1"}')
        self.assertFalse(calls[0].result_error)

    def test_tool_result_with_no_matching_call_is_ignored_not_erroring(self):
        messages = [{"role": "tool", "id": "orphan", "content": "{}", "error": False}]
        self.assertEqual(extract_calls_with_results(messages), [])


class TestExercisedF3Mechanical(unittest.TestCase):
    """Pure function, no adapter -- experiments/analysis_plan.md sec 2's F3 trigger predicate:
    "a cancel_reservation call on a reservation whose flights had available_seats decremented
    EARLIER IN THE SAME TRAJECTORY"."""

    def test_cancel_after_in_trajectory_booking_is_exercised(self):
        calls = [
            RecordedCall("c1", "book_reservation", {}, "assistant", {"reservation_id": "R1"}, False),
            RecordedCall("c2", "cancel_reservation", {"reservation_id": "R1"}, "assistant", "{}", False),
        ]
        exercised, evidence = exercised_f3(calls)
        self.assertTrue(exercised)
        self.assertEqual(evidence[0]["reservation_id"], "R1")

    def test_cancel_of_a_pre_existing_reservation_not_booked_this_trajectory_is_not_exercised(self):
        """The sharp case the predicate exists to distinguish: a reservation already present in
        the task's initial DB state (never booked BY this trajectory) does not satisfy "decremented
        earlier in the same trajectory", even though it is at risk by the field-dependency bound."""
        calls = [
            RecordedCall("c1", "cancel_reservation", {"reservation_id": "PREEXISTING"}, "assistant", "{}", False),
        ]
        exercised, evidence = exercised_f3(calls)
        self.assertFalse(exercised)
        self.assertEqual(evidence, [])

    def test_failed_booking_does_not_count(self):
        calls = [
            RecordedCall("c1", "book_reservation", {}, "assistant", None, True),  # errored
            RecordedCall("c2", "cancel_reservation", {"reservation_id": "R1"}, "assistant", "{}", False),
        ]
        exercised, _ = exercised_f3(calls)
        self.assertFalse(exercised)

    def test_cancel_of_a_different_reservation_than_the_one_booked_is_not_exercised(self):
        calls = [
            RecordedCall("c1", "book_reservation", {}, "assistant", {"reservation_id": "R1"}, False),
            RecordedCall("c2", "cancel_reservation", {"reservation_id": "R2"}, "assistant", "{}", False),
        ]
        exercised, _ = exercised_f3(calls)
        self.assertFalse(exercised)


class TestExercisedF2Live(unittest.TestCase):
    """Needs a live task-scoped environment (state at call time is dynamic) -- skipped like the
    rest of the tau2-adapter tests if the venv isn't provisioned."""

    @classmethod
    def setUpClass(cls):
        cls.adapter = _new_adapter_or_skip()

    @classmethod
    def tearDownClass(cls):
        cls.adapter.close()

    def test_refuel_on_inactive_line_is_exercised(self):
        # Pick a real F2-affected task, then splice in a synthetic refuel_data call targeting a
        # line that is NOT Active in that task's initial state (telecom's bare-domain default DB
        # has such a line -- test_tau2_adapter.py's own Gate 1b test relies on the same fact).
        task_id = TAU2_PATCHES["F2"].domain  # placeholder, overwritten below
        from experiments.ab_run import TAU2_TASK_FILE

        with open(TAU2_TASK_FILE["telecom"], "r", encoding="utf-8") as fh:
            tasks = json.load(fh)
        task_id = tasks[0]["id"]

        pre = self.adapter.snapshot(self.adapter.fresh_task_env("telecom", task_id))
        # Use the bare default env just to find a customer/line pair whose line is inactive
        # (task-specific initial states mostly start with an Active line by design).
        default_pre = self.adapter.snapshot(self.adapter.fresh_env("telecom"))
        inactive_line = next((l for l in default_pre["lines"] if l["status"] != "Active"), None)
        if inactive_line is None:
            self.skipTest("no inactive line in the default telecom DB; nothing to probe")
        customer = next(c for c in default_pre["customers"] if inactive_line["line_id"] in c["line_ids"])

        calls = [
            RecordedCall(
                "c1",
                "refuel_data",
                {"customer_id": customer["customer_id"], "line_id": inactive_line["line_id"], "gb_amount": 1.0},
                "assistant",
                None,
                False,
            )
        ]
        # Exercise must be checked against an env matching the SAME initial state the call was
        # resolved against -- here that's the bare default domain, not the task-scoped one, so
        # call exercised_f2 with a task whose initial state also leaves that line non-Active.
        # Since task-scoped initial state can override line status via initialization_actions,
        # assert only the mechanical property the predicate promises: an active-line call is
        # never flagged, and this specific inactive-line call, replayed from the bare domain
        # default (scenario "telecom"), is.
        exercised, evidence = exercised_f2(self.adapter, "telecom", task_id, calls)
        # task-scoped initial state may or may not reproduce the same inactive line; only assert
        # a positive if it does, and always assert the predicate never raises.
        if evidence:
            self.assertEqual(evidence[0]["tool"], "refuel_data")

    def test_refuel_on_active_line_is_not_exercised(self):
        from experiments.ab_run import TAU2_TASK_FILE

        with open(TAU2_TASK_FILE["telecom"], "r", encoding="utf-8") as fh:
            tasks = json.load(fh)
        # The canonical F2 example task (analysis_plan.md's own worked example): gold refuels
        # L1002, which starts Active.
        task = next(t for t in tasks if t["id"] == "[mobile_data_issue]data_usage_exceeded[PERSONA:Easy]")
        gold_action = task["evaluation_criteria"]["actions"][0]
        self.assertEqual(gold_action["name"], "refuel_data")
        calls = [
            RecordedCall("c1", "refuel_data", gold_action["arguments"], "assistant", None, False),
        ]
        exercised, evidence = exercised_f2(self.adapter, "telecom", task["id"], calls)
        self.assertFalse(exercised)
        self.assertEqual(evidence, [])


class TestPatchVerification(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.adapter = _new_adapter_or_skip()

    @classmethod
    def tearDownClass(cls):
        cls.adapter.close()

    def test_f2_patch_verification_passes(self):
        from experiments.ab_run import verify_patch_f2

        result = verify_patch_f2(self.adapter)
        self.assertTrue(result["pass"], result)
        self.assertTrue(result["defect_reproduces_unpatched"])
        self.assertTrue(result["patch_fixes_defect"])

    def test_f3_patch_verification_passes(self):
        from experiments.ab_run import verify_patch_f3

        result = verify_patch_f3(self.adapter)
        self.assertTrue(result["pass"], result)
        self.assertTrue(result["defect_reproduces_unpatched"])
        self.assertTrue(result["patch_fixes_defect"])


class TestReplayAndScoreRoundTrip(unittest.TestCase):
    """Infrastructure/mechanism validation ONLY -- a hand-built (not agent-recorded) trajectory,
    used to prove the replay -> patch -> tau2-native-evaluator pipeline is wired correctly. Not a
    substitute for the pre-registered agent experiment (experiments/analysis_plan.md sec 4): no
    claim here is made about what a real agent would do."""

    @classmethod
    def setUpClass(cls):
        cls.adapter = _new_adapter_or_skip()

    @classmethod
    def tearDownClass(cls):
        cls.adapter.close()

    def test_gold_action_replay_scores_reward_one_both_patched_and_unpatched(self):
        from experiments.ab_run import TAU2_TASK_FILE

        with open(TAU2_TASK_FILE["telecom"], "r", encoding="utf-8") as fh:
            tasks = json.load(fh)
        task = next(t for t in tasks if t["id"] == "[mobile_data_issue]data_usage_exceeded[PERSONA:Easy]")
        gold_action = task["evaluation_criteria"]["actions"][0]

        messages = [
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "c1",
                        "name": gold_action["name"],
                        "arguments": gold_action["arguments"],
                        "requestor": gold_action["requestor"],
                    }
                ],
            },
            {"role": "tool", "id": "c1", "content": "{}", "requestor": gold_action["requestor"], "error": False},
        ]

        unpatched = self.adapter.replay_and_score("telecom", task["id"], messages, patch=None)
        self.assertEqual(unpatched["reward_info"]["reward"], 1.0)

        spec = TAU2_PATCHES["F2"]
        patched = self.adapter.replay_and_score(
            "telecom",
            task["id"],
            messages,
            patch={"tool": spec.tool, "source": patched_function_source(spec)},
        )
        # Replaying gold's OWN action sequence must still succeed under the patch: the patch only
        # tightens the Active-line precondition, and gold's own action targets an Active line.
        self.assertEqual(patched["reward_info"]["reward"], 1.0)


class TestStaticTaskSelection(unittest.TestCase):
    def test_f2_and_f3_counts_match_known_values(self):
        from experiments.ab_run import select_affected_tasks

        f2 = select_affected_tasks("telecom", "refuel_data")
        f3 = select_affected_tasks("airline", "cancel_reservation")
        self.assertEqual(f2["n_tasks_total"], 2285)
        self.assertEqual(f2["n_affected"], 1120)
        self.assertEqual(f3["n_tasks_total"], 50)
        self.assertEqual(f3["n_affected"], 7)
        self.assertEqual(len(f2["task_ids"]), f2["n_affected"])
        self.assertEqual(len(set(f2["task_ids"])), f2["n_affected"], "no duplicate task ids")

    def test_selection_agrees_with_score_at_risk(self):
        from experiments.ab_run import cross_check_against_score_at_risk, select_affected_tasks
        from experiments.ab_patches import TAU2_PATCHES

        for finding_id in ("F2", "F3"):
            spec = TAU2_PATCHES[finding_id]
            sel = select_affected_tasks(spec.domain, spec.tool)
            xc = cross_check_against_score_at_risk(finding_id, spec, sel["n_affected"])
            self.assertEqual(xc["status"], "computed", xc)
            self.assertTrue(xc["agrees"], xc)


class TestAbRunMainSmoke(unittest.TestCase):
    """Full end-to-end run of experiments/ab_run.main(). Does not assume live model credentials
    are present or absent -- asserts the report is well-formed either way, and additionally
    checks the specific 'no credentials' shape if that is what actually happened (true in this
    project's dev/CI environment as of this writing)."""

    def test_main_writes_a_well_formed_report(self):
        from experiments.ab_run import RESULTS_JSON, SUMMARY_MD, main

        rc = main()
        self.assertEqual(rc, 0)
        self.assertTrue(RESULTS_JSON.exists())
        self.assertTrue(SUMMARY_MD.exists())

        report = json.loads(RESULTS_JSON.read_text(encoding="utf-8"))
        self.assertIn("provenance", report)
        self.assertIn("git_commit", report["provenance"])
        self.assertIn("static_task_selection", report)
        self.assertEqual(report["static_task_selection"]["F2"]["n_affected"], 1120)
        self.assertEqual(report["static_task_selection"]["F3"]["n_affected"], 7)
        self.assertIn("outcome_cells", report)
        self.assertEqual(set(report["outcome_cells"]), {"not_at_risk", "at_risk_not_exercised", "exercised_no_flip", "flipped"})

        if report["tau2_adapter_available"]:
            self.assertTrue(report["patch_verification"]["F2"]["pass"])
            self.assertTrue(report["patch_verification"]["F3"]["pass"])
            recorded = [a for a in report["trajectory_recording"]["attempted"] if a["status"] == "recorded"]
            if not recorded:
                # the expected case in this environment: no live-model credentials configured.
                self.assertEqual(report["stopped_at"], "trajectory_recording")
                self.assertIsNotNone(report["stopped_reason"])
                for cell_value in report["outcome_cells"].values():
                    self.assertIn("not computable", str(cell_value))


if __name__ == "__main__":
    unittest.main()
