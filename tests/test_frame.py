"""Tests for core/frame.py. Run with: python -m unittest discover tests"""
import unittest

from core.frame import FrameMatchError, FrameSyntaxError, get_path, match_paths, parse_pattern


class TestSegmentKinds(unittest.TestCase):
    """Each of the four frame segment kinds matches correctly."""

    def test_identifier_segment(self):
        snap = {"customers": {"a": 1}, "other": 2}
        self.assertEqual(match_paths("state.customers", snap), [("customers",)])

    def test_star_segment_matches_every_mapping_key(self):
        snap = {"customers": {"a": {"x": 1}, "b": {"x": 2}}}
        paths = match_paths("state.customers.*", snap)
        self.assertEqual(sorted(paths), [("customers", "a"), ("customers", "b")])

    def test_bracket_segment_matches_every_sequence_index(self):
        snap = {"items": [{"n": 1}, {"n": 2}, {"n": 3}]}
        paths = match_paths("state.items.[]", snap)
        self.assertEqual(sorted(paths), [("items", 0), ("items", 1), ("items", 2)])

    def test_double_star_matches_any_depth_including_zero(self):
        snap = {"audit_log": "top", "customers": {"a": {"audit_log": "nested"}}}
        paths = match_paths("state.**.audit_log", snap)
        self.assertEqual(sorted(paths), [("audit_log",), ("customers", "a", "audit_log")])

    def test_star_only_descends_into_mappings(self):
        snap = {"items": [1, 2, 3]}
        # '*' expects a mapping; a list at this level yields no match
        with self.assertRaises(FrameMatchError):
            match_paths("state.items.*", snap)

    def test_bracket_only_descends_into_sequences(self):
        snap = {"customers": {"a": 1}}
        with self.assertRaises(FrameMatchError):
            match_paths("state.customers.[]", snap)


class TestNoMatchIsAnError(unittest.TestCase):
    def test_pattern_matching_nothing_raises(self):
        with self.assertRaises(FrameMatchError):
            match_paths("state.does_not_exist", {"customers": {}})

    def test_require_match_false_returns_empty_list_instead(self):
        self.assertEqual(match_paths("state.does_not_exist", {"customers": {}}, require_match=False), [])


class TestStateRootStripping(unittest.TestCase):
    def test_leading_state_prefix_is_stripped(self):
        self.assertEqual(parse_pattern("state.customers.*"), ["customers", "*"])

    def test_no_state_prefix_still_works(self):
        self.assertEqual(parse_pattern("customers.*"), ["customers", "*"])

    def test_bare_state_matches_the_root(self):
        snap = {"a": 1}
        self.assertEqual(match_paths("state", snap), [()])


class TestSyntax(unittest.TestCase):
    def test_empty_pattern_rejected(self):
        with self.assertRaises(FrameSyntaxError):
            parse_pattern("")

    def test_invalid_segment_rejected(self):
        with self.assertRaises(FrameSyntaxError):
            parse_pattern("state.customers.***")

    def test_invalid_identifier_rejected(self):
        with self.assertRaises(FrameSyntaxError):
            parse_pattern("state.9customers")


class TestGetPath(unittest.TestCase):
    def test_resolves_a_concrete_path(self):
        snap = {"customers": {"a": {"x": 42}}}
        self.assertEqual(get_path(snap, ("customers", "a", "x")), 42)


if __name__ == "__main__":
    unittest.main()
