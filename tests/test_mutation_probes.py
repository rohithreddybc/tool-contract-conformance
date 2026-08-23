"""Tests for the sec 2 equivalence probe corpus generator (mutation/probes.py), built and run
against the toy domain's shipped contracts."""
from __future__ import annotations

import unittest
from pathlib import Path

from core.model import Contract
from mutation.probes import Probe, build_equivalence_probe_corpus, generate_boundary_probes, generate_precondition_probes
from toy.adapter import ToyAdapter

CONTRACTS_DIR = Path(__file__).resolve().parent.parent / "spec" / "contracts" / "toy"


class TestBoundaryProbes(unittest.TestCase):
    def test_one_valid_domain_invalid_and_zero_empty_probe_per_parameter(self):
        contract = Contract.from_yaml(CONTRACTS_DIR / "deposit.yaml")
        probes = generate_boundary_probes(contract)
        subkinds = {p.origin.split(":", 2)[2] for p in probes}
        self.assertEqual(subkinds, {"valid", "domain_invalid", "zero_empty"})
        # 2 params x 3 subkinds
        self.assertEqual(len(probes), 6)
        for p in probes:
            self.assertEqual(set(p.args), {"account_id", "amount"})

    def test_zero_empty_is_type_appropriate(self):
        contract = Contract.from_yaml(CONTRACTS_DIR / "resize_inventory.yaml")
        probes = generate_boundary_probes(contract)
        zero_probes = {p.origin: p.args for p in probes if p.origin.endswith(":zero_empty")}
        self.assertEqual(zero_probes["boundary:item_id:zero_empty"]["item_id"], "")
        self.assertEqual(zero_probes["boundary:delta:zero_empty"]["delta"], 0)

    def test_declared_probe_values_are_used_verbatim(self):
        # resize_inventory.yaml declares signature.args.mode.probe_values: [add, remove, set]
        contract = Contract.from_yaml(CONTRACTS_DIR / "resize_inventory.yaml")
        probes = generate_boundary_probes(contract)
        mode_values = {p.args["mode"] for p in probes if p.origin.startswith("boundary:mode:")}
        self.assertEqual(mode_values, {"add", "remove", "set"})

    def test_other_params_held_at_their_own_valid_value(self):
        # A probe isolating one parameter's boundary must not simultaneously stress another.
        contract = Contract.from_yaml(CONTRACTS_DIR / "transfer.yaml")
        probes = generate_boundary_probes(contract)
        amount_domain_invalid = next(p for p in probes if p.origin == "boundary:amount:domain_invalid")
        self.assertEqual(amount_domain_invalid.args["from_account"], "probe_value")
        self.assertEqual(amount_domain_invalid.args["to_account"], "probe_value")


class TestPreconditionProbes(unittest.TestCase):
    def setUp(self):
        self.adapter = ToyAdapter()
        env = self.adapter.fresh_env("default")
        self.pre = self.adapter.snapshot(env)

    def test_finds_a_satisfying_and_a_violating_candidate_for_every_clause_when_possible(self):
        contract = Contract.from_yaml(CONTRACTS_DIR / "deposit.yaml")
        candidates = [
            {"account_id": "acc_alice", "amount": 10.0},  # satisfies everything
            {"account_id": "no_such", "amount": 10.0},  # violates pre.account_exists
            {"account_id": "acc_carol", "amount": 10.0},  # violates pre.account_not_frozen
            {"account_id": "acc_alice", "amount": -5.0},  # violates pre.amount_positive
        ]
        probes = generate_precondition_probes(contract, self.pre, candidates)
        by_clause_kind = {(p.origin.split(":")[0], p.origin.split(":", 1)[1]) for p in probes}
        for clause in ("pre.account_exists", "pre.account_not_frozen", "pre.amount_positive"):
            self.assertIn(("precondition_satisfy", clause), by_clause_kind)
            self.assertIn(("precondition_violate", clause), by_clause_kind)

    def test_a_path_error_candidate_is_skipped_not_counted_as_violating(self):
        # A candidate whose args reference a nonexistent account makes `pre.accounts[id].frozen`
        # raise PathError for the frozen-clause -- must be skipped, never miscounted as "violates".
        contract = Contract.from_yaml(CONTRACTS_DIR / "deposit.yaml")
        candidates = [{"account_id": "no_such_account", "amount": 10.0}]
        probes = generate_precondition_probes(contract, self.pre, candidates)
        frozen_probes = [p for p in probes if "account_not_frozen" in p.origin]
        # Only the *exists* clause is genuinely violated by this candidate; the frozen clause is
        # untestable against it and must not appear as a false "violate".
        self.assertFalse(any(p.origin.startswith("precondition_violate:pre.account_not_frozen") for p in frozen_probes))

    def test_no_candidates_yields_no_precondition_probes(self):
        contract = Contract.from_yaml(CONTRACTS_DIR / "deposit.yaml")
        self.assertEqual(generate_precondition_probes(contract, self.pre, []), [])


class TestBuildCorpus(unittest.TestCase):
    def setUp(self):
        self.adapter = ToyAdapter()
        env = self.adapter.fresh_env("default")
        self.pre = self.adapter.snapshot(env)

    def test_recorded_call_is_included_verbatim(self):
        contract = Contract.from_yaml(CONTRACTS_DIR / "deposit.yaml")
        recorded = [{"account_id": "acc_alice", "amount": 10.0}]
        corpus = build_equivalence_probe_corpus(contract, recorded, self.pre)
        self.assertTrue(any(p.args == recorded[0] and "recorded" in p.origin for p in corpus))

    def test_no_duplicate_args_dicts_and_every_probe_is_json_shaped(self):
        contract = Contract.from_yaml(CONTRACTS_DIR / "transfer.yaml")
        recorded = [{"from_account": "acc_alice", "to_account": "acc_bob", "amount": 10.0}]
        corpus = build_equivalence_probe_corpus(contract, recorded, self.pre)
        seen = set()
        for p in corpus:
            key = tuple(sorted(p.args.items()))
            self.assertNotIn(key, seen, f"duplicate args-dict in corpus: {p.args}")
            seen.add(key)
            for v in p.args.values():
                self.assertIsInstance(v, (str, int, float, bool))

    def test_merged_origin_preserves_multiple_roles_for_one_probe(self):
        # detector_analysis_plan.md sec 2's third bullet and the recorded/boundary bullets can
        # legitimately produce the SAME args-dict for different reasons; the corpus must not
        # silently forget that (see mutation/probes.py's dedup comment).
        contract = Contract.from_yaml(CONTRACTS_DIR / "deposit.yaml")
        recorded = [{"account_id": "acc_alice", "amount": 10.0}]
        corpus = build_equivalence_probe_corpus(contract, recorded, self.pre)
        recorded_probe = next(p for p in corpus if p.args == recorded[0])
        self.assertIn("recorded", recorded_probe.origin)
        self.assertIn("precondition_satisfy:", recorded_probe.origin)

    def test_every_tool_in_the_toy_corpus_produces_a_nonempty_corpus(self):
        for path in sorted(CONTRACTS_DIR.glob("*.yaml")):
            contract = Contract.from_yaml(path)
            corpus = build_equivalence_probe_corpus(contract, [], self.pre)
            self.assertTrue(corpus, f"{contract.tool}: empty corpus even with boundary probes only")


class TestSeparationFromCheckerProbes(unittest.TestCase):
    """detector_analysis_plan.md sec 4.3 requires this generator to be a genuinely separate code
    path from whatever eventually drives the checker's own probing (dynamic/probes.py, not built
    in this milestone). This test pins that fact mechanically so it fails loudly the day someone
    adds dynamic/probes.py and it turns out to import from here (or vice versa)."""

    def test_probes_module_does_not_import_the_checker(self):
        import ast
        import mutation.probes as probes_module

        source = Path(probes_module.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_modules = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        } | {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        self.assertNotIn("adapters.contract_check", imported_modules)
        self.assertFalse(any(m.startswith("dynamic") for m in imported_modules if m))

    def test_the_two_probe_generators_share_no_generation_logic(self):
        """detector_analysis_plan.md sec 4.3 is only measurable if these two stay separate.

        The escape decomposition distinguishes a clause gap (no contract clause covers the changed
        behaviour) from a probe gap (a clause covers it, but the checker's probes never drove the
        tool into the exposing state). If one probe set both screened equivalence and drove the
        checker, every probe gap would be invisible by construction and the decomposition would
        silently collapse into a two-way split.

        This test replaces an earlier one that asserted dynamic/probes.py did not exist. That was a
        tripwire for a module that had not been written yet; it fired when the module landed, which
        is what it was for. The obligation it was standing in for is the separation itself, so that
        is what is now pinned -- in both directions.
        """
        import ast

        import dynamic.probes as checker_probes
        import mutation.probes as equivalence_probes

        def imported_modules(module) -> set:
            tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
            direct = {
                alias.name
                for node in ast.walk(tree)
                if isinstance(node, ast.Import)
                for alias in node.names
            }
            froms = {
                node.module
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom) and node.module
            }
            return {m for m in direct | froms if m}

        equivalence_imports = imported_modules(equivalence_probes)
        checker_imports = imported_modules(checker_probes)

        self.assertFalse(
            any(m.startswith("dynamic") for m in equivalence_imports),
            "the equivalence corpus must not draw on the checker's probe generator",
        )
        self.assertFalse(
            any(m.startswith("mutation") for m in checker_imports),
            "the checker's probes must not draw on the equivalence corpus",
        )

        # Sharing core primitives is fine and expected; sharing generation logic is not.
        shared = equivalence_imports & checker_imports
        self.assertTrue(
            shared <= {"core.model", "core.predicates", "__future__", "dataclasses", "typing"},
            f"unexpected shared dependency between the two probe generators: {shared}",
        )


if __name__ == "__main__":
    unittest.main()
