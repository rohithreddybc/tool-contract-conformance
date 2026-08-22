"""Tests for core/canonical.py. Run with: python -m unittest discover tests"""
import unittest

from core.canonical import VOLATILE_SENTINEL, CanonicalConfig, canonicalize, diff


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

    def test_tolerance_rounds_nearby_floats_to_the_same_bucket(self):
        cfg = CanonicalConfig(float_tolerance=0.01)
        a = canonicalize({"x": 1.001}, cfg)
        b = canonicalize({"x": 1.004}, cfg)
        self.assertEqual(a, b)


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

    def test_diff_respects_volatile_masking(self):
        cfg = CanonicalConfig(volatile_paths=("state.created_at",))
        pre = {"created_at": "t1", "x": 1}
        post = {"created_at": "t2", "x": 1}
        self.assertEqual(diff(pre, post, cfg), {})


if __name__ == "__main__":
    unittest.main()
