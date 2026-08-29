"""Tests for report/render.py. Run with: python -m unittest discover tests

Covers the two things CLAUDE.md's task description flagged as already having caused errors:
(1) MedAgentBench has zero rows in findings.jsonl and must still appear, sourced from
FINDINGS-VERIFIED.md; (2) headline-eligible vs. reported-but-excluded must be shown explicitly,
never left for a reader to compute by subtraction. Also covers the --verify round trip
(analysis/score_at_risk.py's convention), the LaTeX/Markdown rendering, and the "toy" domain's
exclusion from Table III.
"""
import json
import tempfile
import unittest
from pathlib import Path

from report.render import (
    DISPLAY_NAME,
    HEADLINE_TIER,
    LEDGER_BENCHMARKS,
    BenchmarkRow,
    ClassEntry,
    build_ledger_row,
    build_medagentbench_row,
    build_rows,
    load_findings,
    main,
    render_latex,
    render_markdown,
    verify,
    write_outputs,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
REAL_FINDINGS = REPO_ROOT / "report" / "findings.jsonl"


def write_jsonl(path: Path, rows: list) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    return path


def mkrow(benchmark, tool, clause_id, defect_class, headline_tier, verdict="VIOLATES"):
    return {
        "benchmark": benchmark,
        "tool": tool,
        "clause_id": clause_id,
        "defect_class": defect_class,
        "headline_tier": headline_tier,
        "verdict": verdict,
        "commit": "0000000",
        "contract_declared_untestable": False,
        "kind": "effect",
        "probe_origin": "effect_happy_path",
        "reason_code": None,
        "scenario_id": "default",
        "witness": None,
    }


# =============================================================================================
# Real-ledger acceptance tests
# =============================================================================================


class TestRealLedgerBenchmarkCoverage(unittest.TestCase):
    """These run against the actual report/findings.jsonl shipped in this repo."""

    def test_toy_is_excluded_from_table_iii(self):
        self.assertNotIn("toy", LEDGER_BENCHMARKS)

    def test_all_four_audited_benchmarks_present(self):
        rows = build_rows()
        benchmarks = {r.benchmark for r in rows}
        self.assertEqual(benchmarks, {"medagentbench", "tau2-bench", "agentdojo", "mm-toolsandbox"})

    def test_medagentbench_has_no_findings_jsonl_rows_but_is_still_reported(self):
        all_rows = load_findings(REAL_FINDINGS)
        self.assertEqual([r for r in all_rows if r["benchmark"] == "medagentbench"], [])
        row = build_medagentbench_row()
        self.assertGreater(row.tools_audited, 0)
        self.assertGreater(row.classes_reported, 0)
        self.assertIn("FINDINGS-VERIFIED.md", row.source)

    def test_medagentbench_source_is_explicit_about_static_provenance(self):
        row = build_medagentbench_row()
        self.assertIn("static", row.source.lower())
        for c in row.classes:
            self.assertIn("FINDINGS-VERIFIED.md", c.source)

    def test_tau2_and_agentdojo_and_mmtoolsandbox_tool_counts_match_contract_counts(self):
        # These figures are independently pinned in ARCHITECTURE-FINAL.md / FINDINGS-VERIFIED.md:
        # 19 tau2 contracts, 7 AgentDojo contracts, 5 MM-ToolSandbox contracts.
        rows = {r.benchmark: r for r in build_rows()}
        self.assertEqual(rows["tau2-bench"].tools_audited, 19)
        self.assertEqual(rows["agentdojo"].tools_audited, 7)
        self.assertEqual(rows["mm-toolsandbox"].tools_audited, 5)

    def test_medagentbench_reflects_three_tool_definitions_one_code_path(self):
        # ARCHITECTURE-FINAL.md "Realistic tool counts": three POST tool definitions, one
        # shared implementation -- this is the reporting-granularity rule applied to
        # MedAgentBench itself.
        row = build_medagentbench_row()
        self.assertEqual(row.tools_audited, 3)
        self.assertEqual(row.mutating_tools, 3)
        self.assertEqual(row.independent_implementations, 1)

    def test_every_row_distinguishes_headline_from_reported(self):
        for row in build_rows():
            self.assertGreaterEqual(row.classes_reported, row.classes_headline)
            for c in row.classes:
                if not c.headline:
                    self.assertTrue(c.reason)

    def test_agentdojo_reports_phantom_effect_though_absent_from_ledger(self):
        all_rows = load_findings(REAL_FINDINGS)
        agentdojo_violates = [
            r for r in all_rows
            if r["benchmark"] == "agentdojo" and r["verdict"] == "VIOLATES"
        ]
        self.assertFalse(any(r["defect_class"] == "phantom_effect" for r in agentdojo_violates))
        row = {r.benchmark: r for r in build_rows()}["agentdojo"]
        names = {c.name: c for c in row.classes}
        self.assertIn("Phantom Effect", names)
        self.assertFalse(names["Phantom Effect"].headline)

    def test_tau2_reports_suspend_line_ignored_argument_as_non_headline(self):
        # findings.jsonl carries a VIOLATES row for suspend_line/arg.reason at headline_tier
        # "inferred" (FINDINGS-VERIFIED.md "Candidates, not yet confirmed": behavior confirmed,
        # classification contested). It must be reported, never silently dropped to match the
        # older hand-curated seven-cell count, and never headline-eligible.
        row = {r.benchmark: r for r in build_rows()}["tau2-bench"]
        ignored_argument = [c for c in row.classes if c.name == "Ignored Argument"]
        self.assertEqual(len(ignored_argument), 1)
        self.assertFalse(ignored_argument[0].headline)
        self.assertIn("suspend_line", ignored_argument[0].tools)

    def test_headline_total_is_four_cells(self):
        # RESUME-STATE.md "known-good state": 4 headline-eligible cells across 4 benchmarks.
        rows = build_rows()
        self.assertEqual(sum(r.classes_headline for r in rows), 4)
        for row in rows:
            self.assertEqual(row.classes_headline, 1)


# =============================================================================================
# Synthetic-fixture unit tests (isolated from the real ledger's future edits)
# =============================================================================================


class TestBuildLedgerRowSynthetic(unittest.TestCase):
    def test_tools_audited_counts_distinct_tools_regardless_of_verdict(self):
        rows = [
            mkrow("tau2-bench", "tool_a", "pre.x", "unenforced_precondition", "agent_visible"),
            mkrow("tau2-bench", "tool_b", "eff.y", None, "agent_visible", verdict="CONFORMS"),
        ]
        row = build_ledger_row("tau2-bench", rows)
        self.assertEqual(row.tools_audited, 2)
        self.assertEqual(row.mutating_tools, 2)
        # only tool_a has a VIOLATES row
        self.assertEqual(row.independent_implementations, 1)

    def test_eight_bugs_in_one_tool_is_one_implementation_and_one_class(self):
        # Uses "mm-toolsandbox" rather than "agentdojo" deliberately: agentdojo carries a
        # hardcoded supplemental class (Phantom Effect, narrative-only) that would make this
        # synthetic fixture's class count 2 regardless of the mechanical logic under test.
        rows = [
            mkrow("mm-toolsandbox", "shared_helper", f"eff.field_{i}", "ignored_argument", "agent_visible")
            for i in range(8)
        ]
        row = build_ledger_row("mm-toolsandbox", rows)
        self.assertEqual(row.independent_implementations, 1)
        self.assertEqual(row.classes_reported, 1)
        self.assertEqual(row.classes_headline, 1)

    def test_maintainer_annotated_class_is_reported_but_not_headline(self):
        rows = [
            mkrow("tau2-bench", "cancel_x", "eff.z", "partial_effect", "maintainer_annotated"),
        ]
        row = build_ledger_row("tau2-bench", rows)
        self.assertEqual(row.classes_reported, 1)
        self.assertEqual(row.classes_headline, 0)
        self.assertFalse(row.classes[0].headline)

    def test_class_becomes_headline_if_any_instance_is_agent_visible(self):
        rows = [
            mkrow("tau2-bench", "tool_a", "eff.a", "ignored_argument", "inferred"),
            mkrow("tau2-bench", "tool_b", "eff.b", "ignored_argument", "agent_visible"),
        ]
        row = build_ledger_row("tau2-bench", rows)
        self.assertEqual(row.classes_reported, 1)
        self.assertTrue(row.classes[0].headline)
        self.assertEqual(set(row.classes[0].tools), {"tool_a", "tool_b"})

    def test_conforms_only_benchmark_has_no_defect_classes(self):
        rows = [mkrow("tau2-bench", "tool_a", "pre.x", None, "agent_visible", verdict="CONFORMS")]
        row = build_ledger_row("tau2-bench", rows)
        self.assertEqual(row.classes_reported, 0)
        self.assertEqual(row.independent_implementations, 0)

    def test_unknown_defect_class_falls_back_to_raw_string(self):
        rows = [mkrow("tau2-bench", "tool_a", "eff.x", "some_new_class", "agent_visible")]
        row = build_ledger_row("tau2-bench", rows)
        self.assertEqual(row.classes[0].name, "some_new_class")


class TestClassEntryAndBenchmarkRow(unittest.TestCase):
    def test_to_dict_is_json_serializable(self):
        row = BenchmarkRow(
            benchmark="tau2-bench",
            tools_audited=19,
            mutating_tools=19,
            independent_implementations=2,
            classes=(
                ClassEntry("Unenforced Precondition", True, ("refuel_data",), "agent_visible",
                           "report/findings.jsonl"),
                ClassEntry("Partial Effect", False, ("cancel_reservation",),
                           "maintainer-annotated", "report/findings.jsonl",
                           short_reason="maintainer-annotated"),
            ),
            source="report/findings.jsonl (test)",
        )
        json.dumps(row.to_dict())  # must not raise
        self.assertEqual(row.classes_reported, 2)
        self.assertEqual(row.classes_headline, 1)
        self.assertEqual(row.display_name, "tau2-bench")


# =============================================================================================
# Rendering
# =============================================================================================


class TestRenderMarkdown(unittest.TestCase):
    def test_markdown_includes_all_benchmarks_and_totals_row(self):
        rows = build_rows()
        md = render_markdown(rows)
        for row in rows:
            self.assertIn(row.display_name, md)
        self.assertIn("Total", md)
        self.assertIn("Excluded (reported, not headline)", md)

    def test_markdown_shows_headline_count_alongside_reported_count(self):
        rows = build_rows()
        md = render_markdown(rows)
        for row in rows:
            self.assertIn(f"{row.classes_reported} ({row.classes_headline})", md)


class TestRenderLatex(unittest.TestCase):
    def test_latex_is_a_complete_table_environment(self):
        tex = render_latex(build_rows())
        self.assertIn(r"\begin{table}", tex)
        self.assertIn(r"\end{table}", tex)
        self.assertIn(r"\label{tab:table3}", tex)
        self.assertIn(r"\toprule", tex)
        self.assertIn(r"\bottomrule", tex)

    def test_latex_escapes_underscores_in_the_excluded_note(self):
        tex = render_latex(build_rows())
        # the note text must not carry a bare, unescaped underscore that would error LaTeX
        # (findings.jsonl-derived tool names like update_scheduled_transaction can appear
        # nowhere in this table, but the guard is cheap and protects future data changes)
        for line in tex.splitlines():
            if "footnotesize" in line:
                stripped = line.replace(r"\_", "")
                self.assertNotIn("_", stripped)

    def test_latex_matches_markdown_numbers(self):
        rows = build_rows()
        tex = render_latex(rows)
        for row in rows:
            self.assertIn(f"{row.tools_audited}", tex)
            self.assertIn(f"{row.classes_reported} ({row.classes_headline})", tex)


# =============================================================================================
# --verify round trip (analysis/score_at_risk.py's convention)
# =============================================================================================


class TestVerify(unittest.TestCase):
    def test_verify_round_trips_against_freshly_written_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_tex = Path(tmp) / "table3.tex"
            out_md = Path(tmp) / "table3.md"
            rows = build_rows()
            write_outputs(rows, out_tex, out_md)
            self.assertEqual(verify(out_tex, out_md), 0)

    def test_verify_fails_when_output_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_tex = Path(tmp) / "missing.tex"
            out_md = Path(tmp) / "missing.md"
            self.assertEqual(verify(out_tex, out_md), 1)

    def test_verify_fails_on_tampered_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_tex = Path(tmp) / "table3.tex"
            out_md = Path(tmp) / "table3.md"
            rows = build_rows()
            write_outputs(rows, out_tex, out_md)
            with open(out_md, "a", encoding="utf-8") as fh:
                fh.write("\n| Rogue | 1 | 1 | 1 | 1 (1) | hand-edited |\n")
            self.assertEqual(verify(out_tex, out_md), 1)

    def test_main_verify_flag_exits_zero_against_shipped_tables(self):
        # exercises the CLI entry point directly against the real shipped output.
        from report.render import OUT_MD, OUT_TEX
        self.assertEqual(main(["--verify", "--out-tex", str(OUT_TEX), "--out-md", str(OUT_MD)]), 0)


if __name__ == "__main__":
    unittest.main()
