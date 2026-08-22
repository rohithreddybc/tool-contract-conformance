"""Tests for core/canonical.py. Run with: python -m unittest discover tests"""
import unittest

from core.canonical import VOLATILE_SENTINEL, CanonicalConfig, canonical_equal, canonicalize, diff


class TestSortedKeys(unittest.TestCase):
    def test_mapping_keys_are_sorted(self):
        snap = {"z": 1, "a": 2, "m": 3}
        canon = canonicalize(snap, CanonicalConfig())
        self.assertEqual(list(canon.keys()), ["a", "m", "z"])

    def test_insertion_order_is_not_semantic(self):
        c1 = canonicalize({"z": 1, "a": 2}, CanonicalConfig())
        c2 = canonicalize({"a": 2, "z": 1}, CanonicalConfig())
        self.assertEqual(c1, c2)


class TestVolatileMasking(unittest.TestCase):
    def test_volatile_path_is_masked(self):
        snap = {"reservation": {"id": "r1", "created_at": "2024-01-01T00:00:00"}}
        cfg = CanonicalConfig(volatile_paths=("state.reservation.created_at",))
        canon = canonicalize(snap, cfg)
        self.assertEqual(canon["reservation"]["created_at"], VOLATILE_SENTINEL)
        self.assertEqual(canon["reservation"]["id"], "r1")

    def test_masking_makes_otherwise_different_snapshots_equal(self):
        cfg = CanonicalConfig(volatile_paths=("state.created_at",))
        a = canonicalize({"created_at": "t1", "x": 1}, cfg)
        b = canonicalize({"created_at": "t2", "x": 1}, cfg)
        self.assertEqual(a, b)

    def test_volatile_pattern_matching_nothing_does_not_raise(self):
        cfg = CanonicalConfig(volatile_paths=("state.nonexistent.path",))
        canonicalize({"x": 1}, cfg)  # must not raise FrameMatchError


class TestFloatTolerance(unittest.TestCase):
    def test_default_is_exact(self):
        cfg = CanonicalConfig()
        self.assertNotEqual(canonicalize({"x": 1.0001}, cfg), canonicalize({"x": 1.0002}, cfg))

    def test_canonicalize_never_mutates_numbers(self):
        # Regression: canonicalize() used to bucket floats with round(node / tol) * tol -- a
        # quantization, not a tolerance. Canonicalization is structural only now; tolerance is a
        # comparison concern handled by canonical_equal()/diff(). A value survives canonicalize()
        # unchanged regardless of the declared tolerance.
        cfg = CanonicalConfig(float_tolerance=0.01)
        self.assertEqual(canonicalize({"x": 1.001}, cfg), {"x": 1.001})
        self.assertEqual(canonicalize({"x": 1.004}, cfg), {"x": 1.004})

    def test_bucket_edge_values_closer_than_tolerance_compare_equal(self):
        # Regression for the bucketing bug: round(node / tol) * tol puts 0.014999 and 0.015001
        # in different buckets (0.01 vs 0.02) at tol=0.01 even though they are 2e-6 apart --
        # well within the declared tolerance. canonical_equal must say these are equal.
        cfg = CanonicalConfig(float_tolerance=0.01)
        self.assertTrue(canonical_equal({"x": 0.014999}, {"x": 0.015001}, cfg))

    def test_bucket_edge_values_are_reported_unchanged_by_canonicalize(self):
        cfg = CanonicalConfig(float_tolerance=0.01)
        self.assertEqual(canonicalize({"x": 0.014999}, cfg), {"x": 0.014999})
        self.assertEqual(canonicalize({"x": 0.015001}, cfg), {"x": 0.015001})

    def test_equal_int_and_float_compare_equal_under_tolerance(self):
        # Regression: round(node / tol) * tol only matched isinstance(node, float), so an int
        # left untouched (100) and an equal float rounded to its own bucket (100.0 at
        # tol=0.3 -> round(100.0/0.3)*0.3 == 333*0.3 == 99.89999999999999) compared UNEQUAL --
        # enabling tolerance created a diff where tolerance 0 correctly reported none.
        cfg = CanonicalConfig(float_tolerance=0.3)
        self.assertTrue(canonical_equal({"x": 100}, {"x": 100.0}, cfg))

    def test_int_and_float_untouched_by_canonicalize(self):
        cfg = CanonicalConfig(float_tolerance=0.3)
        self.assertEqual(canonicalize({"x": 100}, cfg), {"x": 100})
        self.assertEqual(canonicalize({"x": 100.0}, cfg), {"x": 100.0})

    def test_values_further_than_tolerance_still_differ(self):
        cfg = CanonicalConfig(float_tolerance=0.01)
        self.assertFalse(canonical_equal({"x": 1.0}, {"x": 1.02}, cfg))

    def test_bool_is_not_treated_as_a_number_under_tolerance(self):
        # A large tolerance must never forgive a boolean flip: True/False are not "numbers"
        # for tolerance purposes even though bool subclasses int in Python.
        cfg = CanonicalConfig(float_tolerance=1.0)
        self.assertFalse(canonical_equal({"x": True}, {"x": False}, cfg))

    def test_canonical_equal_with_default_config_is_exact(self):
        self.assertFalse(canonical_equal({"x": 1.0}, {"x": 1.0000001}))
        self.assertTrue(canonical_equal({"x": 1.0}, {"x": 1.0}))


class TestOrderSensitivity(unittest.TestCase):
    def test_sequences_are_order_sensitive_by_default(self):
        cfg = CanonicalConfig()
        a = canonicalize({"items": [1, 2, 3]}, cfg)
        b = canonicalize({"items": [3, 2, 1]}, cfg)
        self.assertNotEqual(a, b)

    def test_declared_path_is_order_insensitive(self):
        cfg = CanonicalConfig(unordered_paths=("state.items",))
        a = canonicalize({"items": [1, 2, 3]}, cfg)
        b = canonicalize({"items": [3, 2, 1]}, cfg)
        self.assertEqual(a, b)


class TestConfigSerializable(unittest.TestCase):
    def test_round_trips_through_dict(self):
        cfg = CanonicalConfig(volatile_paths=("state.x",), float_tolerance=0.5, unordered_paths=("state.y",))
        d = cfg.to_dict()
        import json

        json.dumps(d)  # must be JSON-serializable
        cfg2 = CanonicalConfig.from_dict(d)
        self.assertEqual(cfg, cfg2)


class TestDiff(unittest.TestCase):
    def test_diff_reports_changed_leaf(self):
        pre = {"status": "open", "id": "r1"}
        post = {"status": "cancelled", "id": "r1"}
        changes = diff(pre, post)
        self.assertIn("status", changes)
        self.assertEqual(changes["status"], {"pre": "open", "post": "cancelled"})
        self.assertNotIn("id", changes)

    def test_diff_reports_added_key(self):
        changes = diff({}, {"new_field": 1})
        self.assertEqual(changes["new_field"], {"pre": None, "post": 1})

    def test_diff_empty_for_identical_snapshots(self):
        snap = {"a": {"b": [1, 2, 3]}}
        self.assertEqual(diff(snap, snap), {})

    def test_diff_is_tolerance_aware(self):
        cfg = CanonicalConfig(float_tolerance=0.01)
        pre = {"balance": 0.014999}
        post = {"balance": 0.015001}
        self.assertEqual(diff(pre, post, cfg), {})

    def test_diff_reports_int_vs_equal_float_as_no_change_under_tolerance(self):
        cfg = CanonicalConfig(float_tolerance=0.3)
        self.assertEqual(diff({"x": 100}, {"x": 100.0}, cfg), {})

    def test_diff_length_differing_lists_names_the_removed_element(self):
        # Regression: _diff used to only recurse into equal-length lists, so removing one of
        # three elements produced a single change entry containing both full lists instead of
        # naming the removed element.
        pre = {"flights": ["AB1", "CD2", "EF3"]}
        post = {"flights": ["AB1", "CD2"]}
        changes = diff(pre, post)
        self.assertEqual(changes, {"flights.2": {"pre": "EF3", "post": None}})

    def test_diff_length_differing_lists_names_the_added_element(self):
        pre = {"flights": ["AB1", "CD2"]}
        post = {"flights": ["AB1", "CD2", "EF3"]}
        changes = diff(pre, post)
        self.assertEqual(changes, {"flights.2": {"pre": None, "post": "EF3"}})

    def test_diff_length_differing_lists_common_prefix_still_diffed_individually(self):
        pre = {"flights": ["AB1", "XX9", "EF3"]}
        post = {"flights": ["AB1", "CD2"]}
        changes = diff(pre, post)
        self.assertEqual(
            changes,
            {"flights.1": {"pre": "XX9", "post": "CD2"}, "flights.2": {"pre": "EF3", "post": None}},
        )

    def test_diff_respects_volatile_masking(self):
        cfg = CanonicalConfig(volatile_paths=("state.created_at",))
        pre = {"created_at": "t1", "x": 1}
        post = {"created_at": "t2", "x": 1}
        self.assertEqual(diff(pre, post, cfg), {})


if __name__ == "__main__":
    unittest.main()
