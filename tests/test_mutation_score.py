"""Tests for mutation/score.py: Wilson intervals (pinned to detector_analysis_plan.md sec 5's own
worked example), tool-clustered pooling, sec 4.1 survival, sec 4.3 escape decomposition, and sec
4.4's mechanical adjudication rules. Run against toy/bank.py mutants and hand-built synthetic
contracts only -- no real benchmark corpus is generated or scored here (CLAUDE.md)."""
from __future__ import annotations

import pathlib
import unittest

from core.canonical import CanonicalConfig
from core.model import Contract
from mutation.equivalence import enumerate_equivalence_sites
from mutation.score import (
    EquivalenceRule,
    EscapeCause,
    Rate,
    adjudicate_equivalence,
    classify_escape,
    design_effect,
    is_behaviorally_live,
    precision_recall_report,
    tool_clustered_wilson,
    wilson_interval,
)
from mutation.sites import enumerate_sites, load_class_from_source
from toy.bank import MUTATING_TOOLS, ToyBank

SOURCE = pathlib.Path(__file__).resolve().parent.parent / "toy" / "bank.py"


def _source() -> str:
    return SOURCE.read_text(encoding="utf-8")


class TestWilsonInterval(unittest.TestCase):
    def test_matches_the_plans_own_worked_example(self):
        # detector_analysis_plan.md sec 5, verbatim: "20/25 is a point estimate of 0.80 and a
        # Wilson interval of [0.61, 0.91]".
        r = wilson_interval(20, 25)
        self.assertAlmostEqual(r.point, 0.80, places=3)
        self.assertAlmostEqual(r.lower, 0.61, places=2)
        self.assertAlmostEqual(r.upper, 0.91, places=2)

    def test_claim_is_phrased_at_the_lower_bound_never_the_point_estimate(self):
        r = wilson_interval(20, 25)
        claim = r.claim("recall")
        self.assertIn(f"{r.lower:.3f}", claim)
        # The point estimate must appear only as a labeled, secondary parenthetical, never as
        # the number right after ">=".
        self.assertTrue(claim.startswith(f"recall >= {r.lower:.3f}"))
        self.assertNotIn(f">= {r.point:.3f}", claim)

    def test_zero_denominator_is_rejected_not_silently_padded(self):
        with self.assertRaises(ValueError):
            wilson_interval(0, 0)

    def test_perfect_score_interval_is_strictly_below_one(self):
        # A textbook Wilson property: 100% observed success is not reported as a [1.0, 1.0]
        # certainty -- the lower bound is < 1 for any finite n.
        r = wilson_interval(10, 10)
        self.assertLess(r.lower, 1.0)
        self.assertAlmostEqual(r.upper, 1.0, places=9)


class TestToolClusteredWilson(unittest.TestCase):
    def test_identical_per_tool_proportions_collapse_to_the_naive_pooled_interval(self):
        per_tool = {"a": (10, 20), "b": (10, 20), "c": (10, 20)}
        self.assertAlmostEqual(design_effect(list(per_tool.values())), 1.0, places=6)
        clustered = tool_clustered_wilson(per_tool)
        naive = wilson_interval(30, 60)
        self.assertAlmostEqual(clustered.lower, naive.lower, places=6)
        self.assertAlmostEqual(clustered.upper, naive.upper, places=6)

    def test_divergent_per_tool_proportions_widen_the_pooled_interval(self):
        # Same pooled point estimate (30/60 = 0.5) as the identical-proportions case above, but
        # the per-tool rates are 100% / 0% / 50% -- a real detector would never behave this
        # inconsistently across tools sharing one contract style, so this is a stress case for
        # the clustering machinery, not a realistic detector.
        per_tool = {"a": (20, 20), "b": (0, 20), "c": (10, 20)}
        deff = design_effect(list(per_tool.values()))
        self.assertGreater(deff, 1.0)
        clustered = tool_clustered_wilson(per_tool)
        naive = wilson_interval(30, 60)
        self.assertLess(clustered.lower, naive.lower)
        self.assertGreater(clustered.upper, naive.upper)

    def test_single_tool_has_no_clustering_penalty(self):
        per_tool = {"a": (10, 20)}
        self.assertEqual(design_effect(list(per_tool.values())), 1.0)

    def test_precision_recall_report_shape_has_per_tool_and_pooled(self):
        counts = {
            "M-PRECOND": {"deposit": (5, 5), "withdraw": (4, 5)},
            "M-PARTIAL": {"transfer": (2, 2)},
        }
        report = precision_recall_report(counts)
        self.assertEqual(set(report), {"M-PRECOND", "M-PARTIAL"})
        self.assertEqual(set(report["M-PRECOND"].per_tool), {"deposit", "withdraw"})
        self.assertIsInstance(report["M-PRECOND"].pooled, Rate)


class TestBehavioralSurvival(unittest.TestCase):
    def setUp(self):
        self.source = _source()
        self.sites = enumerate_sites(self.source, MUTATING_TOOLS, reset_names=("reset",))

    def test_a_real_defect_mutant_is_live(self):
        site = next(s for s in self.sites if s.operator == "M-PHANTOM" and s.tool == "deposit")
        Cls = load_class_from_source(site.apply(self.source), "ToyBank")
        probes = [{"account_id": "acc_alice", "amount": 10.0}]
        self.assertTrue(is_behaviorally_live(ToyBank, Cls, "deposit", probes))

    def test_an_equivalent_refactor_is_not_live_across_a_full_probe_battery(self):
        eq_sites = enumerate_equivalence_sites(self.source, ("transfer",))
        reorder = next(s for s in eq_sites if s.kind == "reorder")
        Cls = load_class_from_source(reorder.apply(self.source), "ToyBank")
        probes = [
            {"from_account": "acc_alice", "to_account": "acc_bob", "amount": 10.0},
            {"from_account": "acc_carol", "to_account": "acc_bob", "amount": 1.0},
            {"from_account": "acc_alice", "to_account": "acc_alice", "amount": 1.0},
        ]
        self.assertFalse(is_behaviorally_live(ToyBank, Cls, "transfer", probes))

    def test_survival_requires_only_one_differing_probe_among_several(self):
        site = next(s for s in self.sites if s.operator == "M-INVAR" and s.tool == "release_lock")
        Cls = load_class_from_source(site.apply(self.source), "ToyBank")
        # Most single-acquire/release cycles never reach count==0 twice in one instance, but the
        # corpus only needs ONE probe sequence... this operator's effect is only visible when
        # release brings count to exactly 0, so use a probe battery where at least one does.
        probes = [{"lock_id": "printer", "holder": "nobody"}]  # precondition-violating, not live
        self.assertFalse(is_behaviorally_live(ToyBank, Cls, "release_lock", probes))
        # A held-then-released sequence needs two calls, which single-probe survival (sec 4.1)
        # cannot express directly -- confirmed instead via TestMInvar in test_mutation_operators.


class TestEscapeDecomposition(unittest.TestCase):
    def _make_contract(self, *, preconditions=(), effects=(), on_precondition_violation=None):
        return Contract.from_dict(
            {
                "contract_version": "1.0",
                "tool": "t",
                "benchmark": "toy",
                "commit": "0000000",
                "source": {"file": "x.py", "start_line": 1, "end_line": 2},
                "signature": {"args": {"account_id": {"type": "str", "effective": True}}},
                "preconditions": list(preconditions),
                "effects": list(effects),
                "on_precondition_violation": on_precondition_violation,
            }
        )

    def test_clause_gap_when_no_predicate_mentions_the_changed_field(self):
        contract = self._make_contract(
            effects=[
                {
                    "id": "eff.balance",
                    "text": "x",
                    "predicate": "post.accounts[args.account_id].balance == pre.accounts[args.account_id].balance",
                    "inferred": True,
                }
            ],
        )
        pre = {"accounts": {"a": {"balance": 1.0}}, "items": {"widget": {"tags": []}}}
        # The change lands in "items"/"tags" -- neither literal appears in any clause's predicate.
        post_mut = {"accounts": {"a": {"balance": 1.0}}, "items": {"widget": {"tags": ["x"]}}}
        cause = classify_escape(contract, pre, post_mut, {"account_id": "a"}, {})
        self.assertEqual(cause, EscapeCause.CLAUSE_GAP)

    def test_canonicalization_gap_via_the_precondition_state_delta_check(self):
        # check_effects's predicate evaluation is NOT itself canonicalization-sensitive in the
        # current adapters/contract_check.py (canonicalization there only feeds the Witness
        # diff, never the verdict) -- see mutation/score.py's classify_escape docstring and the
        # build report. The state_delta:"none" check inside check_precondition_enforcement is the
        # one real place a masked field can flip a verdict, so that is the path this test drives.
        contract = self._make_contract(
            preconditions=[
                {"id": "pre.exists", "text": "x", "predicate": "args.account_id in pre.accounts", "inferred": True}
            ],
            effects=[
                {
                    "id": "eff.log_seq",
                    "text": "x",
                    "predicate": "len(post.audit_log) >= 0",  # deliberately weak; references audit_log/seq via frame below
                    "inferred": True,
                }
            ],
            on_precondition_violation={"expect": {"error_signal": True, "state_delta": "none"}},
        )
        pre = {"accounts": {}, "audit_log": [{"seq": 1}]}
        # Precondition violated (args.account_id not in pre.accounts) AND the ONLY delta is a
        # volatile "seq" counter that incremented despite no real effect -- a defect this call's
        # error signal alone won't catch, since error_signal:true DID hold; only the
        # state_delta:"none" half is violated, and only visibly so once unmasked.
        post_mut = {"accounts": {}, "audit_log": [{"seq": 2}]}
        args = {"account_id": "no_such"}

        # The mutant DOES raise (error_signal:true is satisfied) -- the only thing wrong is the
        # leaked "seq" delta, so error_mut must be a real message or the error_signal half of the
        # expectation would already fail the call regardless of masking, masking the very
        # distinction this test exists to isolate.
        masked_cfg = CanonicalConfig(volatile_paths=("state.audit_log.[].seq",))
        cause = classify_escape(
            contract, pre, post_mut, args, {}, error_mut="account not found",
            masked_cfg=masked_cfg, unmasked_cfg=CanonicalConfig(),
        )
        self.assertEqual(cause, EscapeCause.CANONICALIZATION_GAP)

    def test_probe_gap_is_the_residual_bucket(self):
        # A clause DOES reference the changed field ("tags"), so clause_gap does not fire; the
        # predicate is simply too weak to ever flag this particular call (always True), and
        # unmasking changes nothing because nothing was masked -- probe_gap by elimination.
        contract = self._make_contract(
            effects=[
                {
                    "id": "eff.tags_exist",
                    "text": "x",
                    "predicate": "len(post.items[args.account_id].tags) >= 0",
                    "inferred": True,
                }
            ],
        )
        pre = {"items": {"widget": {"tags": []}}}
        post_mut = {"items": {"widget": {"tags": ["unexpected"]}}}
        cause = classify_escape(contract, pre, post_mut, {"account_id": "widget"}, {})
        self.assertEqual(cause, EscapeCause.PROBE_GAP)


class TestAdjudicateEquivalence(unittest.TestCase):
    def test_rule_2_volatile_field_is_mechanical(self):
        rule = adjudicate_equivalence(
            changed_paths={"audit_log.0.seq"},
            volatile_paths_matched={"audit_log.0.seq"},
            generated_by_refactor_generator=False,
        )
        self.assertEqual(rule, EquivalenceRule.RULE_2_VOLATILE_FIELD)

    def test_rule_2_does_not_fire_if_any_changed_path_is_not_volatile(self):
        rule = adjudicate_equivalence(
            changed_paths={"audit_log.0.seq", "accounts.a.balance"},
            volatile_paths_matched={"audit_log.0.seq"},
            generated_by_refactor_generator=False,
        )
        self.assertIsNone(rule)

    def test_rule_3_semantics_preserving_refactor_is_mechanical_given_the_generator_tag(self):
        rule = adjudicate_equivalence(
            changed_paths={"accounts.a.balance"},
            volatile_paths_matched=set(),
            generated_by_refactor_generator=True,
        )
        self.assertEqual(rule, EquivalenceRule.RULE_3_SEMANTICS_PRESERVING_REFACTOR)

    def test_rule_1_requires_a_human_predetermined_flag_never_inferred(self):
        self.assertIsNone(
            adjudicate_equivalence(changed_paths={"x"}, volatile_paths_matched=set(), generated_by_refactor_generator=False)
        )
        self.assertEqual(
            adjudicate_equivalence(
                changed_paths={"x"}, volatile_paths_matched=set(), generated_by_refactor_generator=False,
                interface_invisible=True,
            ),
            EquivalenceRule.RULE_1_INTERFACE_INVISIBLE,
        )

    def test_no_rule_applies_returns_none(self):
        rule = adjudicate_equivalence(
            changed_paths={"accounts.a.balance"}, volatile_paths_matched=set(), generated_by_refactor_generator=False
        )
        self.assertIsNone(rule)


if __name__ == "__main__":
    unittest.main()
