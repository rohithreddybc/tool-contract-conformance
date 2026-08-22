"""Tests for mutation/sites.py: enumeration correctness, the exclusion rule
(detector_analysis_plan.md sec 3 / CLAUDE.md -- tools carrying confirmed findings never enter the
mutation corpus), and seeded-selection determinism/no-substitution."""
from __future__ import annotations

import pathlib
import unittest
from collections import Counter

from mutation.operators import OPERATORS
from mutation.sites import enumerate_sites, materialize_mutant_source, select_sites
from toy.bank import MUTATING_TOOLS

SOURCE = pathlib.Path(__file__).resolve().parent.parent / "toy" / "bank.py"


def _source() -> str:
    return SOURCE.read_text(encoding="utf-8")


class TestEnumerateSites(unittest.TestCase):
    def test_every_operator_has_at_least_one_site_on_the_toy_domain(self):
        sites = enumerate_sites(_source(), MUTATING_TOOLS, reset_names=("reset",))
        counts = Counter(s.operator for s in sites)
        for op in OPERATORS:
            self.assertGreater(counts[op], 0, f"{op} has zero sites on toy/bank.py -- diversity requirement not met")

    def test_exact_expected_counts(self):
        # Hand-verified against toy/bank.py's actual guard/write/argument structure (see the
        # build report) -- pinned so a silent structural drift in toy/bank.py is caught here
        # rather than discovered later as an unexplained corpus-size change.
        sites = enumerate_sites(_source(), MUTATING_TOOLS, reset_names=("reset",))
        counts = Counter(s.operator for s in sites)
        self.assertEqual(counts["M-PHANTOM"], 11)  # one per mutating tool
        self.assertEqual(counts["M-PRECOND"], 76)  # 38 guards x {delete, negate}
        self.assertEqual(counts["M-IGNARG"], 23)  # every declared, used, effective argument
        self.assertEqual(counts["M-PARTIAL"], 8)  # transfer(2) + reserve_item(2) + release_item(2) + acquire_lock(2)
        self.assertEqual(counts["M-INVAR"], 2)  # release_lock's held_by clear + resize_inventory's add-branch write
        self.assertEqual(counts["M-RESET"], 5)  # reset()'s 5 field assignments

    def test_excluded_tools_contribute_zero_sites(self):
        # Demonstrates the exclusion mechanism CLAUDE.md/detector_analysis_plan.md sec 3 require
        # for the real corpus ("tools carrying confirmed findings are excluded") -- toy/bank.py
        # has no confirmed findings itself, so this exercises the *mechanism* generically by
        # excluding an arbitrary toy tool and checking it vanishes from every operator's pool.
        all_sites = enumerate_sites(_source(), MUTATING_TOOLS, reset_names=("reset",))
        excluded_sites = enumerate_sites(
            _source(), MUTATING_TOOLS, reset_names=("reset",), excluded_tools=frozenset({"transfer"})
        )
        self.assertTrue(any(s.tool == "transfer" for s in all_sites))
        self.assertFalse(any(s.tool == "transfer" for s in excluded_sites))
        # Nothing else should be affected -- same count minus exactly transfer's sites.
        transfer_count = sum(1 for s in all_sites if s.tool == "transfer")
        self.assertEqual(len(excluded_sites), len(all_sites) - transfer_count)

    def test_excluded_tools_does_not_filter_reset_routine(self):
        # A reset routine is not itself "a tool carrying a confirmed finding" in this project's
        # finding taxonomy -- excluding a mutating tool by name must not accidentally also
        # exclude reset() if its name were ever to collide (it doesn't here, but the mechanism
        # should not silently over-filter).
        sites = enumerate_sites(
            _source(), MUTATING_TOOLS, reset_names=("reset",), excluded_tools=frozenset(MUTATING_TOOLS)
        )
        self.assertTrue(sites)
        self.assertTrue(all(s.operator == "M-RESET" for s in sites))

    def test_every_enumerated_site_actually_materializes(self):
        # The strongest correctness check available without running each mutant: every single
        # site this module reports must be one mutation/operators.py can actually apply, end to
        # end through the same code path a mutant runner would use.
        sites = enumerate_sites(_source(), MUTATING_TOOLS, reset_names=("reset",))
        source = _source()
        for site in sites:
            mutated = materialize_mutant_source(source, site.tool, site.operator, site.params)
            self.assertIsInstance(mutated, str)
            compile(mutated, "<mutant>", "exec")  # must at least be syntactically valid Python


class TestSelectSites(unittest.TestCase):
    def setUp(self):
        self.sites = enumerate_sites(_source(), MUTATING_TOOLS, reset_names=("reset",))

    def test_seeded_selection_is_deterministic(self):
        a = select_sites(self.sites, "M-PRECOND", k=10, seed=42)
        b = select_sites(self.sites, "M-PRECOND", k=10, seed=42)
        self.assertEqual(a, b)

    def test_different_seeds_can_differ(self):
        a = select_sites(self.sites, "M-PRECOND", k=10, seed=1)
        b = select_sites(self.sites, "M-PRECOND", k=10, seed=2)
        self.assertNotEqual(a, b)

    def test_never_substitutes_from_another_operator_when_pool_is_small(self):
        # M-INVAR has only 2 sites on the toy domain -- asking for 25 must return exactly 2, all
        # M-INVAR, never padded with sites from another operator (detector_analysis_plan.md sec
        # 3 / ARCHITECTURE-FINAL.md sec 5: "the actual number is reported and no substitution
        # from another class is made").
        selected = select_sites(self.sites, "M-INVAR", k=25, seed=7)
        self.assertEqual(len(selected), 2)
        self.assertTrue(all(s.operator == "M-INVAR" for s in selected))

    def test_selection_never_exceeds_k(self):
        selected = select_sites(self.sites, "M-PRECOND", k=5, seed=3)
        self.assertLessEqual(len(selected), 5)

    def test_selection_is_a_subset_of_the_enumerated_pool(self):
        pool_ids = {(s.tool, s.operator, tuple(sorted(s.params.items()))) for s in self.sites if s.operator == "M-PARTIAL"}
        selected = select_sites(self.sites, "M-PARTIAL", k=100, seed=11)
        for s in selected:
            self.assertIn((s.tool, s.operator, tuple(sorted(s.params.items()))), pool_ids)


if __name__ == "__main__":
    unittest.main()
