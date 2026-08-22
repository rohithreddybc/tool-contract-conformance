"""Tests for core/model.py's headline_tier() helper. Run with: python -m unittest discover tests

spec/PREDICATE-GRAMMAR.md sec 6, 'Headline eligibility': a clause is agent_visible iff its
provenance surface is agent-visible AND check 8 passed for it. The check-8 outcome is threaded
in by the caller (spec/validate.py owns that check), never recomputed here.
"""
import unittest

from core.model import Clause, HeadlineTier, Provenance, headline_tier


def _clause(surface=None, inferred=False, line=1, quote="q") -> Clause:
    prov = Provenance(surface=surface, quote=quote, file="f.py", line=line) if surface else None
    return Clause(id="eff.x", text="t", predicate="True", provenance=prov, inferred=inferred)


class TestHeadlineTier(unittest.TestCase):
    def test_inferred_clause_is_always_inferred_tier(self):
        c = _clause(surface="docstring", inferred=True)
        self.assertEqual(headline_tier(c, check8_passed=True), HeadlineTier.INFERRED)

    def test_no_provenance_is_inferred_tier(self):
        c = _clause(surface=None)
        self.assertEqual(headline_tier(c, check8_passed=True), HeadlineTier.INFERRED)

    def test_maintainer_annotation_surface_is_maintainer_annotated_tier(self):
        c = _clause(surface="maintainer_annotation")
        # check8_passed is irrelevant for this surface -- both should land the same way.
        self.assertEqual(headline_tier(c, check8_passed=True), HeadlineTier.MAINTAINER_ANNOTATED)
        self.assertEqual(headline_tier(c, check8_passed=False), HeadlineTier.MAINTAINER_ANNOTATED)

    def test_agent_visible_surface_with_check8_pass_is_agent_visible_tier(self):
        c = _clause(surface="docstring")
        self.assertEqual(headline_tier(c, check8_passed=True), HeadlineTier.AGENT_VISIBLE)

    def test_agent_visible_surface_with_check8_fail_is_not_headline(self):
        # This is the exact defect case: surface tag says tool_return, but check 8 rejected the
        # quote as a logger call, not a return/raise. Must not be reported as agent_visible.
        c = _clause(surface="tool_return")
        self.assertEqual(headline_tier(c, check8_passed=False), HeadlineTier.MAINTAINER_ANNOTATED)

    def test_tool_return_surface_with_check8_pass_is_agent_visible(self):
        c = _clause(surface="tool_return")
        self.assertEqual(headline_tier(c, check8_passed=True), HeadlineTier.AGENT_VISIBLE)


if __name__ == "__main__":
    unittest.main()
