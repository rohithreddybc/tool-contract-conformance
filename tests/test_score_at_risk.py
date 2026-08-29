"""Tests for analysis/score_at_risk.py. Run with: python -m unittest discover tests

Two layers, matching the module's own two layers: synthetic-predicate unit tests for the
generic AST utilities (path extraction, comprehension-binding resolution, helper-call
resolution), and acceptance tests against the real pinned inputs (the two shipped tau2
contracts, the pinned MedAgentBench refsol.py, the AgentDojo v1 banking/travel suites) that
check score_at_risk.py reproduces the numbers FINDINGS-VERIFIED.md and REVIEW-RESPONSE.md
already establish by hand -- W2's "never report zero" rule and W6's containment relation in
particular.
"""
import json
import unittest
from pathlib import Path

from analysis.score_at_risk import (
    KNOWN_AGENTDOJO_DEFECTS,
    KNOWN_MMTOOLSANDBOX_DEFECTS,
    KNOWN_TAU2_DEFECTS,
    ReadProfile,
    _direct_function_index,
    _maximal_paths,
    _module_function_index,
    _profile_function,
    agentdojo_defect_write_fields,
    agentdojo_task_classes,
    agentdojo_task_profile,
    build_agentdojo_rows,
    build_all_rows,
    build_medagentbench_rows,
    build_mmtoolsandbox_rows,
    build_tau2_rows,
    collection_names,
    extract_state_paths,
    leaf_field_names,
    medagentbench_defect_fields,
    medagentbench_oracle_profile,
    mmtoolsandbox_defect_write_fields,
    tau2_defect_write_fields,
    terminal_field_names,
    transitive_read_profile,
    verify,
    write_rows,
    AGENTDOJO_TASKS_FILE,
    MEDAGENTBENCH_REFSOL,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


# =============================================================================================
# Generic AST utilities
# =============================================================================================


class TestExtractStatePaths(unittest.TestCase):
    def test_direct_post_indexing(self):
        paths = extract_state_paths("post.flights['AA1'].available_seats == 5", frozenset({"post"}))
        self.assertIn(("post", "flights", "AA1", "available_seats"), paths)

    def test_wildcard_for_nonconstant_key(self):
        paths = extract_state_paths("post.flights[args.flight_number].available_seats == 5", frozenset({"post"}))
        self.assertIn(("post", "flights", "*", "available_seats"), paths)

    def test_comprehension_bound_variable_extends_the_rooted_path(self):
        # Regression test: an earlier version of extract_state_paths only followed literal
        # pre./post.-rooted chains and silently dropped 'data_refueling_gb' here, because it is
        # reached through the comprehension binder `l2`, not directly off `post`.
        src = "any(l2.data_refueling_gb == 1 for l2 in post.lines)"
        paths = extract_state_paths(src, frozenset({"post"}))
        self.assertIn(("post", "lines", "*", "data_refueling_gb"), paths)

    def test_nested_comprehension_preserves_outer_binding(self):
        src = "any(any(b.total_due == 0 for b in post.bills) for l in pre.lines)"
        paths = extract_state_paths(src, frozenset({"post"}))
        self.assertIn(("post", "bills", "*", "total_due"), paths)

    def test_only_requested_roots_are_collected(self):
        paths = extract_state_paths("post.x.y == pre.x.y", frozenset({"post"}))
        self.assertTrue(all(p[0] == "post" for p in paths))
        self.assertFalse(any(p[0] == "pre" for p in paths))


class TestMaximalPaths(unittest.TestCase):
    def test_prefixes_are_dropped(self):
        paths = {("post", "a"), ("post", "a", "b"), ("post", "c")}
        self.assertEqual(_maximal_paths(paths), [("post", "a", "b"), ("post", "c")])


class TestLeafFieldNamesAndCollections(unittest.TestCase):
    def test_leaf_field_names_excludes_wildcards_and_other_roots(self):
        paths = {("post", "lines", "*", "data_refueling_gb"), ("pre", "lines", "*", "data_refueling_gb")}
        self.assertEqual(leaf_field_names(paths, "post"), frozenset({"lines", "data_refueling_gb"}))

    def test_collection_names_is_first_segment_after_root(self):
        maximal = [("post", "lines", "*", "data_refueling_gb"), ("post", "bills", "*", "total_due")]
        self.assertEqual(collection_names(maximal, "post"), frozenset({"lines", "bills"}))


class TestTerminalFieldNames(unittest.TestCase):
    def test_terminal_field_is_the_trailing_non_wildcard_segment(self):
        maximal = [("post", "lines", "*", "data_refueling_gb"), ("post", "bills", "*", "total_due")]
        self.assertEqual(terminal_field_names(maximal, "post"), frozenset({"data_refueling_gb", "total_due"}))

    def test_nested_wrapper_object_does_not_leak_the_middle_collection_name(self):
        # Regression check for the exact shape agentdojo_defect_write_fields() hits: a wrapper
        # object (bank_account) containing a collection (scheduled_transactions) containing the
        # actually-compared field (recurring), three levels deep. collection_names() would only
        # strip 'bank_account' and leave 'scheduled_transactions' in the set;
        # terminal_field_names() must strip both intermediate segments.
        maximal = [("post", "bank_account", "scheduled_transactions", "*", "recurring")]
        fields = terminal_field_names(maximal, "post")
        self.assertEqual(fields, frozenset({"recurring"}))
        self.assertNotIn("bank_account", fields)
        self.assertNotIn("scheduled_transactions", fields)

    def test_trailing_wildcard_falls_back_to_the_last_named_segment(self):
        # cancel_reservation.yaml's eff.seats_released shape: the final subscript key is a
        # non-constant expression, so the maximal path ends in '*' rather than a field name.
        maximal = [("post", "flights", "*", "dates", "*", "available_seats", "*")]
        self.assertEqual(terminal_field_names(maximal, "post"), frozenset({"available_seats"}))


class TestProfileFunctionAndTransitiveResolution(unittest.TestCase):
    def _index(self, src: str) -> dict:
        import ast

        tree = ast.parse(src)
        return _direct_function_index(tree)

    def test_attribute_names_collected(self):
        idx = self._index("def f(x):\n    return x.foo.bar\n")
        prof = _profile_function(idx["f"])
        self.assertEqual(prof.attribute_names, frozenset({"foo", "bar"}))

    def test_dotted_string_constant_contributes_segments(self):
        idx = self._index("def f():\n    return {'root.reservation.end_time'}\n")
        prof = _profile_function(idx["f"])
        self.assertIn("end_time", prof.attribute_names)
        self.assertIn("reservation", prof.attribute_names)

    def test_non_dotted_string_constant_is_not_captured(self):
        idx = self._index("def f():\n    return 'http://example/fhir'\n")
        prof = _profile_function(idx["f"])
        self.assertNotIn("http", prof.attribute_names)

    def test_transitive_resolution_follows_one_hop_helper_call(self):
        idx = self._index(
            "def helper(x):\n    return x.data_refueling_gb\n"
            "def caller(x):\n    return helper(x)\n"
        )
        prof = transitive_read_profile("caller", idx)
        self.assertIn("data_refueling_gb", prof.attribute_names)

    def test_transitive_resolution_is_cycle_safe(self):
        idx = self._index("def a():\n    return b()\n" "def b():\n    return a()\n")
        # Must terminate rather than recurse forever.
        prof = transitive_read_profile("a", idx)
        self.assertIsInstance(prof, ReadProfile)

    def test_class_methods_with_the_same_name_do_not_collide(self):
        import ast

        tree = ast.parse(
            "class A:\n    def utility(self):\n        return self.foo\n"
            "class B:\n    def utility(self):\n        return self.bar\n"
        )
        classes = {n.name: n for n in ast.iter_child_nodes(tree) if isinstance(n, ast.ClassDef)}
        idx_a = _direct_function_index(classes["A"])
        idx_b = _direct_function_index(classes["B"])
        self.assertEqual(_profile_function(idx_a["utility"]).attribute_names, frozenset({"foo"}))
        self.assertEqual(_profile_function(idx_b["utility"]).attribute_names, frozenset({"bar"}))


# =============================================================================================
# tau2-bench acceptance tests -- against the real shipped contracts and pinned task files.
# =============================================================================================


class TestTau2DefectWriteFields(unittest.TestCase):
    def test_cancel_reservation_seats_released_is_maintainer_annotated_and_not_headline(self):
        kd = next(k for k in KNOWN_TAU2_DEFECTS if k.tool == "cancel_reservation")
        fields, max_paths, tier = tau2_defect_write_fields(kd)
        self.assertIn("available_seats", fields)
        self.assertEqual(tier.value, "maintainer_annotated")  # W1's re-tiering, not headline

    def test_refuel_data_fields_include_the_comprehension_bound_attributes(self):
        kd = next(k for k in KNOWN_TAU2_DEFECTS if k.tool == "refuel_data")
        fields, max_paths, tier = tau2_defect_write_fields(kd)
        self.assertIn("data_refueling_gb", fields)
        self.assertIn("total_due", fields)
        self.assertEqual(tier.value, "agent_visible")  # docstring-grounded, headline-eligible


class TestBuildTau2Rows(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = build_tau2_rows()
        cls.summaries = {(r["domain"], r["tool"]): r for r in cls.rows if r["kind"] == "summary"}

    def test_airline_summary_matches_the_hand_computed_numbers(self):
        s = self.summaries[("airline", "cancel_reservation")]
        self.assertEqual(s["n_tasks_total"], 50)
        self.assertEqual(s["n_at_risk"], 50)  # every airline task uses DB reward-basis
        self.assertEqual(s["n_experiment_frame"], 7)  # gold actions call cancel_reservation
        self.assertTrue(s["experiment_frame_subset_of_at_risk"])

    def test_telecom_summary_matches_the_hand_computed_numbers(self):
        s = self.summaries[("telecom", "refuel_data")]
        self.assertEqual(s["n_tasks_total"], 2285)
        self.assertEqual(s["n_experiment_frame"], 1120)
        self.assertTrue(s["experiment_frame_subset_of_at_risk"])

    def test_every_at_risk_task_row_carries_full_traceability(self):
        for r in self.rows:
            if r["kind"] != "task_verdict":
                continue
            for key in ("benchmark", "tool", "clause_id", "evaluator_read_site", "task_id"):
                self.assertIn(key, r)
                self.assertTrue(r[key] not in (None, ""), f"{key} missing/empty in {r}")


# =============================================================================================
# MedAgentBench acceptance tests -- W2's mandated verdict.
# =============================================================================================


class TestMedAgentBenchOracleGrounding(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import ast

        cls.index = _module_function_index(str(MEDAGENTBENCH_REFSOL))

    def test_task3_is_transcript_grounded_unconditional_write(self):
        p = medagentbench_oracle_profile("task3", self.index)
        self.assertEqual(p["grounding"], "transcript_grounded")

    def test_task5_is_mixed_conditional_write(self):
        p = medagentbench_oracle_profile("task5", self.index)
        self.assertEqual(p["grounding"], "mixed")

    def test_task1_has_no_write_oracle_despite_calling_check_has_post(self):
        # task1 calls check_has_post() as a negative gate ("must not have POSTed") but never
        # extract_posts() -- it must not be classified alongside task3/task8's write-content
        # oracles.
        p = medagentbench_oracle_profile("task1", self.index)
        self.assertEqual(p["grounding"], "no_write_oracle")
        self.assertTrue(p["calls_check_has_post"])
        self.assertFalse(p["calls_extract_posts"])

    def test_task3_defect_fields_include_resource_type(self):
        fields = medagentbench_defect_fields("task3", self.index)
        self.assertIn("resourceType", fields)
        self.assertIn("subject", fields)

    def test_no_grader_is_state_grounded(self):
        # The point of Finding 4: nothing verifies a write by reading it back from FHIR.
        for grader in [f"task{i}" for i in range(1, 11)]:
            p = medagentbench_oracle_profile(grader, self.index)
            self.assertNotEqual(p["grounding"], "state_grounded")


class TestBuildMedAgentBenchRows(unittest.TestCase):
    def test_summary_never_reports_zero_and_matches_finding4s_table(self):
        rows = build_medagentbench_rows()
        summary = next(r for r in rows if r["kind"] == "summary")
        self.assertEqual(summary["oracle_grounding_breakdown"]["transcript_grounded"], 60)
        self.assertEqual(summary["oracle_grounding_breakdown"]["mixed"], 90)
        self.assertEqual(summary["oracle_grounding_breakdown"]["no_write_oracle"], 150)
        self.assertEqual(summary["oracle_grounding_breakdown"]["state_grounded"], 0)
        self.assertIn("oracle not state-grounded: 60 tasks", summary["verdict"])
        self.assertEqual(summary["score_at_risk_status"], "undefined_transcript_grounded")

    def test_no_task_verdict_row_claims_a_computed_at_risk_bound(self):
        # W2: never silently report a field-intersection "at risk" count for a
        # transcript-grounded or mixed oracle.
        rows = build_medagentbench_rows()
        for r in rows:
            if r["kind"] == "task_verdict":
                self.assertIsNone(r["at_risk"])
                self.assertNotEqual(r["score_at_risk_status"], "computed")


# =============================================================================================
# AgentDojo acceptance tests -- W6's containment relation, including its one real failure.
# =============================================================================================


class TestAgentDojoTaskProfile(unittest.TestCase):
    def test_banking_usertask6_reads_recurring_and_is_state_grounded(self):
        classes = {c.name: c for c in agentdojo_task_classes("banking")}
        helper_index = _module_function_index(str(AGENTDOJO_TASKS_FILE["banking"]))
        profile = agentdojo_task_profile(classes["UserTask6"], helper_index)
        self.assertIn("recurring", profile["attribute_names"])
        self.assertEqual(profile["grounding"], "state_grounded")
        self.assertNotIn("update_scheduled_transaction", profile["gold_tool_calls"])
        self.assertIn("schedule_transaction", profile["gold_tool_calls"])

    def test_banking_usertask2_calls_update_scheduled_transaction_but_does_not_read_recurring(self):
        classes = {c.name: c for c in agentdojo_task_classes("banking")}
        helper_index = _module_function_index(str(AGENTDOJO_TASKS_FILE["banking"]))
        profile = agentdojo_task_profile(classes["UserTask2"], helper_index)
        self.assertIn("update_scheduled_transaction", profile["gold_tool_calls"])
        self.assertNotIn("recurring", profile["attribute_names"])

    def test_travel_helper_resolution_picks_up_end_time_via_check_new_reservation(self):
        classes = {c.name: c for c in agentdojo_task_classes("travel")}
        helper_index = _module_function_index(str(AGENTDOJO_TASKS_FILE["travel"]))
        profile = agentdojo_task_profile(classes["UserTask0"], helper_index)
        self.assertIn("end_time", profile["attribute_names"])


class TestAgentDojoDefectWriteFields(unittest.TestCase):
    # Step 1, now contract-driven exactly as tau2_defect_write_fields() is -- the whole point of
    # closing this module's own documented "manually-seeded substitute" caveat. Pinned against
    # FINDINGS-VERIFIED.md Finding 5 / Finding 6's own source citations, same as before, but the
    # field names below now come from walking spec/contracts/agentdojo/*.yaml's own violated
    # effect clause, not from a hand-typed string.
    def test_recurring_propagated_derives_recurring_from_the_contract(self):
        kd = next(k for k in KNOWN_AGENTDOJO_DEFECTS if k.tool == "update_scheduled_transaction")
        self.assertEqual(kd.clause_id, "eff.recurring_propagated")
        fields, max_paths, tier = agentdojo_defect_write_fields(kd)
        self.assertIn("recurring", fields)
        self.assertEqual(tier.value, "agent_visible")  # docstring-grounded, headline-eligible

    def test_end_time_applied_derives_end_time_from_the_contract(self):
        kd = next(k for k in KNOWN_AGENTDOJO_DEFECTS if k.tool == "reserve_car_rental")
        # eff.end_time_propagated (the pre-fix, hand-typed clause id) does not exist in
        # reserve_car_rental.yaml -- the real clause is eff.end_time_applied. Getting this wrong
        # was itself part of the debt this module now closes.
        self.assertEqual(kd.clause_id, "eff.end_time_applied")
        fields, max_paths, tier = agentdojo_defect_write_fields(kd)
        self.assertEqual(fields, frozenset({"end_time"}))
        self.assertEqual(tier.value, "agent_visible")


class TestBuildAgentDojoRows(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = build_agentdojo_rows()
        cls.summaries = {r["tool"]: r for r in cls.rows if r["kind"] == "summary"}
        cls.defects = {r["tool"]: r for r in cls.rows if r["kind"] == "defect"}

    def test_finding5_experiment_frame_is_not_contained_in_at_risk(self):
        # A genuine, mechanically-verified W6 containment failure, not a bug: every banking task
        # whose gold solution calls update_scheduled_transaction only touches amount/recipient,
        # never recurring; the one task whose oracle reads .recurring (UserTask6) reaches it
        # through a *different* tool (schedule_transaction). Both populations must still be
        # reported, and the containment field must say so honestly. Unchanged by the switch to
        # contract-driven field derivation: terminal_field_names() still isolates 'recurring'
        # (plus the harmless, never-matched selector field 'id') rather than the noisy
        # 'scheduled_transactions' collection name a naive collection_names() strip would leave
        # in, which would have inflated n_at_risk well past 1.
        s = self.summaries["update_scheduled_transaction"]
        self.assertEqual(s["n_at_risk"], 1)
        self.assertEqual(s["n_experiment_frame"], 4)
        self.assertFalse(s["experiment_frame_subset_of_at_risk"])

    def test_finding6_experiment_frame_is_empty_and_trivially_contained(self):
        # FINDINGS-VERIFIED.md Finding 6: "No shipped v1 user task exercises this tool through
        # its ground truth" -- reproduced here mechanically, not merely quoted.
        s = self.summaries["reserve_car_rental"]
        self.assertEqual(s["n_experiment_frame"], 0)
        self.assertTrue(s["experiment_frame_subset_of_at_risk"])

    def test_defect_rows_carry_a_headline_tier_and_real_predicate_derived_paths(self):
        for tool, clause_id in (
            ("update_scheduled_transaction", "eff.recurring_propagated"),
            ("reserve_car_rental", "eff.end_time_applied"),
        ):
            d = self.defects[tool]
            self.assertEqual(d["clause_id"], clause_id)
            self.assertEqual(d["headline_tier"], "agent_visible")
            self.assertTrue(all(p.startswith("post.") for p in d["write_paths"]))


# =============================================================================================
# MM-ToolSandbox acceptance tests -- Step 1 only, Steps 2/3 blocked on AppWorld.
# =============================================================================================


class TestMMToolSandboxDefectWriteFields(unittest.TestCase):
    def test_sort_by_forwarded_derives_sort_by_from_the_contract(self):
        kd = next(k for k in KNOWN_MMTOOLSANDBOX_DEFECTS if k.tool == "venmo_social")
        self.assertEqual(kd.clause_id, "eff.sort_by_forwarded")
        fields, max_paths, tier = mmtoolsandbox_defect_write_fields(kd)
        self.assertEqual(fields, frozenset({"sort_by"}))
        self.assertEqual(tier.value, "agent_visible")
        # The nested boundary_calls[*].kwargs.sort_by shape is exactly the case
        # terminal_field_names() exists for: collection_names() would have stripped only
        # 'boundary_calls' and left 'kwargs' in the match set.
        self.assertTrue(any(p[-1] == "sort_by" for p in max_paths))


class TestBuildMMToolSandboxRows(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = build_mmtoolsandbox_rows()

    def test_defect_row_is_contract_derived(self):
        d = next(r for r in self.rows if r["kind"] == "defect")
        self.assertEqual(d["benchmark"], "mm-toolsandbox")
        self.assertEqual(d["tool"], "venmo_social")
        self.assertEqual(d["clause_id"], "eff.sort_by_forwarded")
        self.assertEqual(d["field_names"], ["sort_by"])
        self.assertEqual(d["headline_tier"], "agent_visible")

    def test_summary_never_claims_a_computed_at_risk_bound(self):
        # No local, offline evaluator or task file exists for the AppWorld-tier scenarios that
        # exercise venmo_social (FINDINGS-VERIFIED.md's git-lfs blocker), so Steps 2/3 cannot
        # run. The summary must say so explicitly rather than silently report zero -- the same
        # W2 discipline the MedAgentBench "never print zero" rule already enforces for a
        # different reason.
        s = next(r for r in self.rows if r["kind"] == "summary")
        self.assertEqual(s["score_at_risk_status"], "not_computable_appworld_unreachable")
        self.assertIsNone(s["n_at_risk"])
        self.assertIsNone(s["n_experiment_frame"])
        self.assertNotEqual(s["score_at_risk_status"], "computed")

    def test_no_task_verdict_rows_are_emitted(self):
        self.assertFalse(any(r["kind"] == "task_verdict" for r in self.rows))


# =============================================================================================
# Whole-pipeline / --verify
# =============================================================================================


class TestBuildAllRowsAndVerify(unittest.TestCase):
    def test_every_row_is_json_serializable_and_has_a_kind(self):
        rows = build_all_rows()
        self.assertGreater(len(rows), 0)
        for r in rows:
            self.assertIn("kind", r)
            json.dumps(r)  # must not raise

    def test_every_row_traces_to_benchmark_and_tool(self):
        rows = build_all_rows()
        for r in rows:
            self.assertIn("benchmark", r)
            self.assertIn("tool", r)

    def test_all_four_contract_bearing_and_case_study_benchmarks_are_present(self):
        # tau2-bench, AgentDojo, and MM-ToolSandbox all now derive Step 1 from shipped
        # contracts; MedAgentBench remains the static case study by design (zero contracts,
        # FINDINGS-VERIFIED.md's own framing note).
        rows = build_all_rows()
        benchmarks = {r["benchmark"] for r in rows}
        self.assertEqual(benchmarks, {"tau2-bench", "medagentbench", "agentdojo", "mm-toolsandbox"})

    def test_verify_round_trips_against_freshly_written_rows(self):
        import tempfile

        rows = build_all_rows()
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "score_at_risk.jsonl"
            write_rows(rows, out)
            self.assertEqual(verify(out), 0)

    def test_verify_fails_on_tampered_output(self):
        import tempfile

        rows = build_all_rows()
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "score_at_risk.jsonl"
            write_rows(rows, out)
            with open(out, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"kind": "bogus"}) + "\n")
            self.assertEqual(verify(out), 1)

    def test_verify_fails_when_output_missing(self):
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "does_not_exist.jsonl"
            self.assertEqual(verify(out), 1)


if __name__ == "__main__":
    unittest.main()
