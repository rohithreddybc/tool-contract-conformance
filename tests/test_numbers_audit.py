"""Tests for experiments/numbers_audit.py. Run with: python -m unittest discover tests

All tests operate on synthetic fixtures (temp files, or hand-written manuscript snippets passed
directly to the extraction/check functions) rather than on the real paper/main.md, so they stay
green regardless of the manuscript's current drafting state -- this project's numbers_audit.py
run against the real draft is a separate, non-test invocation (`python
experiments/numbers_audit.py`), and the manuscript itself is out of scope for this test file to
touch or depend on structurally.

Five scenarios are required by CLAUDE.md's audit-script mandate and covered explicitly below:
  * test_internal_consistency_catches_two_conflicting_values
  * test_artifact_crosscheck_catches_contradiction
  * test_external_figure_crosscheck_catches_contradiction
  * test_placeholder_discipline_catches_nonexistent_artifact
  * test_clean_manuscript_produces_no_fail
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import experiments.numbers_audit as na


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class TestNumberWordParsing(unittest.TestCase):
    def test_digit_and_word_agree(self):
        self.assertEqual(na.parse_num("42"), 42.0)
        self.assertEqual(na.parse_num("eight"), 8.0)
        self.assertEqual(na.parse_num("Eight"), 8.0)

    def test_compound_word(self):
        self.assertEqual(na.parse_num("thirty-five"), 35.0)
        self.assertEqual(na.parse_num("Thirty-five"), 35.0)
        self.assertEqual(na.parse_num("seventeen"), 17.0)

    def test_unrecognized_word_is_none(self):
        self.assertIsNone(na.parse_num("banana"))


class TestExtraction(unittest.TestCase):
    def test_placeholder_extraction_ignores_nested_brackets(self):
        text = "before [NOT YET DRAFTED, fills [N2: analysis/score_at_risk.py]] after"
        placeholders = na.extract_placeholders(text)
        keys = [p.key for p in placeholders]
        self.assertIn("N2", keys)
        n2 = next(p for p in placeholders if p.key == "N2")
        self.assertEqual(n2.body, "analysis/score_at_risk.py")

    def test_percentage_and_hash_census(self):
        text = "Result was 42.5% on commit `abc1234` per Table II."
        self.assertEqual(na.extract_percentages(text), [(1, "42.5%")])
        self.assertEqual(na.extract_commit_hashes(text), [(1, "abc1234")])
        self.assertEqual(na.extract_table_refs(text), [(1, "Table II")])


class TestConceptCompoundWords(unittest.TestCase):
    """Regression test for the regex-precedence bug this script's own development caught:
    NUM's word-alternation must be grouped before the "-<word>" compound suffix is attached, or
    "Thirty-five shipped frame clauses" silently extracts only "five"."""

    def test_compound_number_extracted_whole(self):
        text = "Thirty-five shipped frame clauses were schema-valid."
        matches = na.extract_concept_matches(text)
        frame_matches = [m for m in matches if m.concept == "frame_clause_count"]
        self.assertEqual(len(frame_matches), 1)
        self.assertEqual(frame_matches[0].value, 35.0)
        self.assertEqual(frame_matches[0].raw.lower(), "thirty-five")


# ---------------------------------------------------------------------------
# Scenario 1: internal consistency catches two conflicting values for one quantity
# (the 7-vs-5-vs-4 headline-count bug this script exists to prevent a recurrence of)
# ---------------------------------------------------------------------------

class TestInternalConsistency(unittest.TestCase):
    def test_catches_two_conflicting_values(self):
        text = (
            "4 HEADLINE-ELIGIBLE tool-layer cells across 4 benchmarks are reported here.\n\n"
            "Later, Across 4 shipped benchmarks we confirmed 8 finding instances, falling "
            "into 7 benchmark-class cells, of which **5 are headline-eligible**, a change "
            "from the earlier count.\n"
        )
        matches = na.extract_concept_matches(text)
        report = na.Report()
        consensus = na.check_internal_consistency(matches, report)

        headline_findings = [f for f in report.findings
                              if "headline_cell_count" in f.claim]
        self.assertTrue(headline_findings, "expected a finding about headline_cell_count")
        self.assertEqual(headline_findings[0].verdict, na.FAIL)
        self.assertIn("4.0", headline_findings[0].detail)
        self.assertIn("5.0", headline_findings[0].detail)
        # consensus still resolves to *something* usable downstream (majority/first value)
        self.assertIn(consensus["headline_cell_count"], (4.0, 5.0))

    def test_single_value_passes(self):
        text = "4 HEADLINE-ELIGIBLE tool-layer cells across 4 benchmarks are reported here."
        matches = na.extract_concept_matches(text)
        report = na.Report()
        na.check_internal_consistency(matches, report)
        headline_findings = [f for f in report.findings
                              if f.claim.startswith("quantity 'headline_cell_count'")]
        self.assertEqual(len(headline_findings), 1)
        self.assertEqual(headline_findings[0].verdict, na.PASS)


# ---------------------------------------------------------------------------
# Scenario 2: a claim contradicting a generated artifact is caught
# ---------------------------------------------------------------------------

class TestArtifactCrosscheck(unittest.TestCase):
    def test_catches_contradiction_with_findings_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            findings_jsonl = write(tmp_path / "findings.jsonl", "\n".join([
                json.dumps({"benchmark": "bench-a", "defect_class": "ignored_argument",
                            "verdict": "VIOLATES", "headline_tier": "agent_visible"}),
                json.dumps({"benchmark": "bench-b", "defect_class": "phantom_effect",
                            "verdict": "VIOLATES", "headline_tier": "agent_visible"}),
                # a maintainer-annotated VIOLATES must NOT count toward the headline total
                json.dumps({"benchmark": "bench-c", "defect_class": "partial_effect",
                            "verdict": "VIOLATES", "headline_tier": "maintainer_annotated"}),
            ]))
            findings_verified = write(tmp_path / "FINDINGS-VERIFIED.md",
                                       "no MedAgentBench static bonus text here\n")

            with mock.patch.object(na, "FINDINGS_JSONL", findings_jsonl), \
                 mock.patch.object(na, "FINDINGS_VERIFIED_MD", findings_verified):
                report = na.Report()
                # manuscript (falsely) claims 4 headline-eligible cells; the fixture artifact
                # only supports 2
                na.check_findings_jsonl_headline_cells({"headline_cell_count": 4.0}, report)

            self.assertEqual(len(report.findings), 1)
            finding = report.findings[0]
            self.assertEqual(finding.verdict, na.FAIL)
            self.assertEqual(finding.expected, "2")
            self.assertIn("4", finding.found)

    def test_matching_claim_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            findings_jsonl = write(tmp_path / "findings.jsonl", "\n".join([
                json.dumps({"benchmark": "bench-a", "defect_class": "ignored_argument",
                            "verdict": "VIOLATES", "headline_tier": "agent_visible"}),
            ]))
            findings_verified = write(tmp_path / "FINDINGS-VERIFIED.md", "nothing relevant\n")
            with mock.patch.object(na, "FINDINGS_JSONL", findings_jsonl), \
                 mock.patch.object(na, "FINDINGS_VERIFIED_MD", findings_verified):
                report = na.Report()
                na.check_findings_jsonl_headline_cells({"headline_cell_count": 1.0}, report)
            self.assertEqual(report.findings[0].verdict, na.PASS)

    def test_missing_artifact_is_unverifiable_not_pass(self):
        missing = Path(tempfile.gettempdir()) / "does-not-exist-numbers-audit-test.jsonl"
        self.assertFalse(missing.exists())
        with mock.patch.object(na, "FINDINGS_JSONL", missing):
            report = na.Report()
            na.check_findings_jsonl_headline_cells({"headline_cell_count": 4.0}, report)
        self.assertEqual(report.findings[0].verdict, na.UNVERIFIABLE)


# ---------------------------------------------------------------------------
# Scenario 3: an external figure contradicting EXTERNAL-VERIFICATION.md is caught
# ---------------------------------------------------------------------------

class TestExternalFigureCrosscheck(unittest.TestCase):
    ACTION_SR_FIXTURE = (
        "Some prose. Table 3 reports it for all 3 evaluated models:\n\n"
        "| Model | Action SR |\n"
        "|---|---|\n"
        "| Model A | 10.00% |\n"
        "| Model B | 50.00% |\n"
        "| Model C | 90.00% |\n\n"
        "More prose follows the table.\n"
    )

    def test_catches_contradicted_range(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = write(Path(tmp) / "EXTERNAL-VERIFICATION.md", self.ACTION_SR_FIXTURE)
            with mock.patch.object(na, "EXTERNAL_VERIFICATION_MD", fixture):
                report = na.Report()
                # manuscript (falsely) claims the range is 0.00-71.33%; the fixture's real
                # range is 10.00-90.00%
                na.check_external_verification(
                    {"action_sr_min": 0.0, "action_sr_max": 71.33}, report)
            min_finding = next(f for f in report.findings if "minimum" in f.claim)
            max_finding = next(f for f in report.findings if "maximum" in f.claim)
            self.assertEqual(min_finding.verdict, na.FAIL)
            self.assertEqual(min_finding.expected, "10.0")
            self.assertEqual(max_finding.verdict, na.FAIL)
            self.assertEqual(max_finding.expected, "90.0")

    def test_matching_range_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = write(Path(tmp) / "EXTERNAL-VERIFICATION.md", self.ACTION_SR_FIXTURE)
            with mock.patch.object(na, "EXTERNAL_VERIFICATION_MD", fixture):
                report = na.Report()
                na.check_external_verification(
                    {"action_sr_min": 10.0, "action_sr_max": 90.0}, report)
            min_finding = next(f for f in report.findings if "minimum" in f.claim)
            max_finding = next(f for f in report.findings if "maximum" in f.claim)
            self.assertEqual(min_finding.verdict, na.PASS)
            self.assertEqual(max_finding.verdict, na.PASS)

    def test_row_count_vs_prose_mismatch_is_surfaced(self):
        """Regression fixture modeled on a real discrepancy this script found in the project's
        own EXTERNAL-VERIFICATION.md: the Action SR table there has 12 rows while its own prose,
        one paragraph above, says 'all 11 evaluated models'. This is a defect in the external
        source-of-truth file itself, independent of anything paper/main.md claims, so it is
        surfaced as INFO (visible, but does not gate a manuscript commit on a file this script
        is not permitted to edit) rather than FAIL -- the manuscript-facing FAIL is a separate,
        consensus-gated check (see test_catches_contradicted_range and the real run's
        'evaluated-model count claim' finding, which does gate on this)."""
        fixture_text = self.ACTION_SR_FIXTURE.replace("all 3 evaluated models",
                                                        "all 99 evaluated models")
        with tempfile.TemporaryDirectory() as tmp:
            fixture = write(Path(tmp) / "EXTERNAL-VERIFICATION.md", fixture_text)
            with mock.patch.object(na, "EXTERNAL_VERIFICATION_MD", fixture):
                report = na.Report()
                na.check_external_verification({}, report)
            row_count_finding = next(f for f in report.findings if "self-consistency" in
                                      f.claim)
            self.assertEqual(row_count_finding.verdict, na.INFO)
            self.assertIn("MISMATCH", row_count_finding.found)

    def test_manuscript_claim_contradicting_table_is_still_a_hard_fail(self):
        """Even though the source file's own self-consistency check is informational (previous
        test), a manuscript claim that contradicts the actual table-derived model count must
        still FAIL -- that is the check with a direct manuscript-facing claim to gate on."""
        with tempfile.TemporaryDirectory() as tmp:
            fixture = write(Path(tmp) / "EXTERNAL-VERIFICATION.md", self.ACTION_SR_FIXTURE)
            with mock.patch.object(na, "EXTERNAL_VERIFICATION_MD", fixture):
                report = na.Report()
                # manuscript claims 11 models; the fixture table actually has 3 rows
                na.check_external_verification({"medagentbench_model_count": 11.0}, report)
            model_count_finding = next(f for f in report.findings
                                        if "evaluated-model count" in f.claim)
            self.assertEqual(model_count_finding.verdict, na.FAIL)
            self.assertEqual(model_count_finding.expected, "3.0")


# ---------------------------------------------------------------------------
# Scenario 4: a placeholder naming a nonexistent artifact is caught
# ---------------------------------------------------------------------------

class TestPlaceholderDiscipline(unittest.TestCase):
    def test_catches_nonexistent_path(self):
        text = "Results appear in Table IX [N99: analysis/does_not_exist_anywhere.py]."
        report = na.Report()
        na.check_placeholder_discipline(text, report)
        self.assertEqual(len(report.findings), 1)
        self.assertEqual(report.findings[0].verdict, na.FAIL)
        self.assertIn("MISSING", report.findings[0].found)

    def test_catches_placeholder_with_no_path_token_at_all(self):
        text = "Results appear here [N50: a manual process with no file attached]."
        report = na.Report()
        na.check_placeholder_discipline(text, report)
        self.assertEqual(len(report.findings), 1)
        self.assertEqual(report.findings[0].verdict, na.FAIL)
        self.assertIn("no path-like token found", report.findings[0].found)

    def test_existing_path_passes(self):
        # spec/coverage.py is a real, committed artifact in this repository
        text = "See the coverage metric [N40: spec/coverage.py]."
        report = na.Report()
        na.check_placeholder_discipline(text, report)
        self.assertEqual(len(report.findings), 1)
        self.assertEqual(report.findings[0].verdict, na.PASS)

    def test_bare_basename_resolves_via_fallback_search(self):
        # "findings.jsonl" alone (no directory) should still resolve, because
        # report/findings.jsonl exists uniquely in this repository -- this is the same fixup
        # this script's own author needed after the first run against the real manuscript
        # falsely flagged "[N1: report/render.py <- findings.jsonl]" as two broken paths
        # instead of one.
        text = "Totals appear in Table III [N1: report/render.py <- findings.jsonl]."
        report = na.Report()
        na.check_placeholder_discipline(text, report)
        by_claim = {f.claim: f for f in report.findings}
        findings_jsonl_finding = next(f for f in report.findings if "findings.jsonl" in f.claim)
        self.assertEqual(findings_jsonl_finding.verdict, na.PASS)


# ---------------------------------------------------------------------------
# Scenario 5: a clean manuscript passes
# ---------------------------------------------------------------------------

class TestCleanManuscriptPasses(unittest.TestCase):
    def test_clean_manuscript_produces_no_fail(self):
        clean_manuscript = (
            "# A Clean Manuscript\n\n"
            "## III. Some Section\n\n"
            "Table I defines six defect classes, each as an executable checker rule. "
            "Six executable defect classes are enumerated in Table I, all consistent with "
            "each other.\n\n"
            "See the generated coverage report [N40: spec/coverage.py] for details once "
            "later sections land.\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            manuscript_path = write(Path(tmp) / "clean.md", clean_manuscript)
            report = na.run_audit(manuscript_path)

        failed = report.failed()
        self.assertEqual(
            failed, [],
            msg="clean manuscript produced FAIL verdict(s): " +
            "; ".join(f"{f.claim} (expected {f.expected!r}, found {f.found!r})"
                      for f in failed),
        )

    def test_clean_manuscript_exits_zero_via_main(self):
        clean_manuscript = (
            "## III. Some Section\n\n"
            "Table I defines six defect classes. Six executable defect classes are listed.\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            manuscript_path = write(Path(tmp) / "clean.md", clean_manuscript)
            exit_code = na.main(["--manuscript", str(manuscript_path)])
        self.assertEqual(exit_code, 0)


# ---------------------------------------------------------------------------
# Check 5 (lexical rule) -- direct coverage, since it is otherwise dormant on the
# current stub-only draft
# ---------------------------------------------------------------------------

class TestLexicalRule(unittest.TestCase):
    def test_missing_at_risk_or_depend_is_caught(self):
        text = ("50% of tasks are affected by the defect (whole_state_hash), a "
                "figure worth noting.\n")
        report = na.Report()
        na.check_lexical_rule(text, report)
        fails = [f for f in report.findings if f.verdict == na.FAIL]
        self.assertTrue(any("at risk" in f.claim or "depend" in f.claim for f in fails))

    def test_forbidden_word_is_caught(self):
        text = ("50% of tasks are at risk (whole_state_hash), meaning those verdicts are "
                "misgraded outright.\n")
        report = na.Report()
        na.check_lexical_rule(text, report)
        fails = [f for f in report.findings if f.verdict == na.FAIL]
        self.assertTrue(any("misgraded" in f.claim for f in fails))

    def test_missing_basis_tag_is_caught(self):
        text = "50% of tasks are at risk, a figure that depends on the tool's write path.\n"
        report = na.Report()
        na.check_lexical_rule(text, report)
        fails = [f for f in report.findings if f.verdict == na.FAIL]
        self.assertTrue(any("basis tag" in f.claim for f in fails))

    def test_compliant_sentence_passes(self):
        text = ("50% of tasks are at risk (whole_state_hash), a figure that depends on the "
                "tool's write path.\n")
        report = na.Report()
        na.check_lexical_rule(text, report)
        self.assertTrue(any(f.verdict == na.PASS for f in report.findings))
        self.assertFalse(any(f.verdict == na.FAIL for f in report.findings))

    def test_no_score_at_risk_sentence_is_informational_not_failing(self):
        text = "This paragraph has no percentages or basis tags at all.\n"
        report = na.Report()
        na.check_lexical_rule(text, report)
        self.assertTrue(all(f.verdict != na.FAIL for f in report.findings))


# ---------------------------------------------------------------------------
# Item R4 (round-5 panel): the numbers audit must also gate paper/latex/main.tex,
# the file actually submitted, not just paper/main.md. Two things are covered:
# (a) a numeric-token equivalence check between the two files, and (b) the
# script must not crash under a non-UTF-8 Windows console codepage.
# ---------------------------------------------------------------------------

class TestDetexForNumericScan(unittest.TestCase):
    def test_strips_comments_and_scopes_to_document_body(self):
        tex = (
            "% header narration with 999 unrelated numbers\n"
            "\\documentclass{article}\n"
            "\\begin{document}\n"
            "Six \\texttt{executable} defect classes appear here. % trailing comment 123\n"
            "\\end{document}\n"
            "% footer narration with 888\n"
        )
        result = na.detex_for_numeric_scan(tex)
        self.assertIn("Six executable defect classes", result)
        self.assertNotIn("999", result)
        self.assertNotIn("888", result)
        self.assertNotIn("123", result)

    def test_unwraps_text_formatting_macros_and_escapes(self):
        tex = ("\\begin{document}\n"
               "\\textbf{Precision} is \\texttt{50\\%} and the bound is $\\geq$0.867, "
               "\\S\\,IV discusses \\texttt{cancel\\_reservation}.\n"
               "\\end{document}\n")
        result = na.detex_for_numeric_scan(tex)
        self.assertIn("Precision is 50% and the bound is \u22650.867", result)
        self.assertIn("\u00a7IV", result)
        self.assertIn("cancel_reservation", result)


class TestTexNumericEquivalence(unittest.TestCase):
    def test_catches_divergence_between_md_and_tex(self):
        md_text = "There are six executable defect classes described here.\n"
        tex_text = ("\\begin{document}\n"
                    "There are seven executable defect classes described here.\n"
                    "\\end{document}\n")
        with tempfile.TemporaryDirectory() as tmp:
            tex_path = write(Path(tmp) / "main.tex", tex_text)
            report = na.Report()
            na.check_manuscript_tex_numeric_equivalence(md_text, tex_path, report)
        fails = [f for f in report.findings if f.verdict == na.FAIL]
        self.assertTrue(any("defect_class_count" in f.claim for f in fails),
                         msg=f"no FAIL for defect_class_count in {report.findings}")

    def test_matching_values_pass(self):
        md_text = "There are six executable defect classes described here.\n"
        tex_text = ("\\begin{document}\n"
                    "There are six executable defect classes described here.\n"
                    "\\end{document}\n")
        with tempfile.TemporaryDirectory() as tmp:
            tex_path = write(Path(tmp) / "main.tex", tex_text)
            report = na.Report()
            na.check_manuscript_tex_numeric_equivalence(md_text, tex_path, report)
        matched = [f for f in report.findings if "defect_class_count" in f.claim]
        self.assertTrue(matched)
        self.assertTrue(all(f.verdict == na.PASS for f in matched))

    def test_concept_in_only_one_file_is_informational_not_failing(self):
        md_text = "There are six executable defect classes described here.\n"
        tex_text = "\\begin{document}\nNo matching sentence appears here at all.\n\\end{document}\n"
        with tempfile.TemporaryDirectory() as tmp:
            tex_path = write(Path(tmp) / "main.tex", tex_text)
            report = na.Report()
            na.check_manuscript_tex_numeric_equivalence(md_text, tex_path, report)
        self.assertFalse(any(f.verdict == na.FAIL for f in report.findings))
        self.assertTrue(any(f.verdict == na.INFO and "defect_class_count" in f.found
                             for f in report.findings))

    def test_missing_tex_file_is_unverifiable(self):
        missing = Path(tempfile.gettempdir()) / "does-not-exist-main-tex-test.tex"
        self.assertFalse(missing.exists())
        report = na.Report()
        na.check_manuscript_tex_numeric_equivalence(
            "six executable defect classes", missing, report)
        self.assertEqual(report.findings[0].verdict, na.UNVERIFIABLE)

    def test_wired_into_run_audit(self):
        """run_audit() must actually invoke the cross-file check, not just expose it."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            md_path = write(tmp_path / "main.md",
                             "There are six executable defect classes described here.\n")
            tex_path = write(tmp_path / "main.tex",
                              "\\begin{document}\nThere are nine executable defect classes "
                              "described here.\n\\end{document}\n")
            report = na.run_audit(md_path, tex_path)
        fails = [f for f in report.failed() if "defect_class_count" in f.claim]
        self.assertTrue(fails, "run_audit did not surface the cross-file divergence")


class TestWindowsEncodingFix(unittest.TestCase):
    def test_script_does_not_crash_under_legacy_console_codepage(self):
        """Regression test for the reported bug: paper/latex/main.tex and paper/main.md are
        full of characters (>=, section-sign, en dashes) that a plain Windows console codepage
        (e.g. cp1252) cannot encode, so printing a report row that echoes manuscript prose
        verbatim (check_lexical_rule's excerpts, in particular) used to raise
        UnicodeEncodeError and crash before the exit code even mattered. The script now
        reconfigures stdout/stderr to UTF-8 at import time regardless of the invoking
        environment; this drives that exact code path end to end under a forced legacy
        encoding and asserts it does not crash."""
        import os
        import subprocess

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            md_path = write(tmp_path / "main.md",
                             "50% of tasks are at risk (whole_state_hash), a figure "
                             "\u22650.867 that depends on the tool's write path \u00a7IV.\n")
            tex_path = write(tmp_path / "main.tex",
                              "\\begin{document}\n50\\% of tasks are at risk "
                              "(whole\\_state\\_hash), a figure $\\geq$0.867 that depends on "
                              "the tool's write path \\S\\,IV.\n\\end{document}\n")
            repo_root = Path(__file__).resolve().parent.parent
            env = dict(os.environ)
            env["PYTHONIOENCODING"] = "cp1252"
            env.pop("PYTHONUTF8", None)
            result = subprocess.run(
                [sys.executable, str(repo_root / "experiments" / "numbers_audit.py"),
                 "--manuscript", str(md_path), "--tex-manuscript", str(tex_path)],
                cwd=str(repo_root), env=env, capture_output=True, timeout=120)

        self.assertNotIn(b"UnicodeEncodeError", result.stderr)
        self.assertNotIn(b"Traceback", result.stderr)
        # exit code is either 0 (clean) or 1 (a real FAIL row) -- never a crash (2, or a
        # nonstandard code from an unhandled exception)
        self.assertIn(result.returncode, (0, 1),
                       msg=f"stderr: {result.stderr.decode('utf-8', errors='replace')}")


if __name__ == "__main__":
    unittest.main()
