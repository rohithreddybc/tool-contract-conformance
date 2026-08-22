"""Tests for spec/validate.py check 8 (agent-visibility of the claimed surface).
Run with: python -m unittest discover tests

PREDICATE-GRAMMAR.md sec 6.8: a tool_return quote must occur inside a `return` expression or
the message of a `raise` -- never inside a logger.* call, a bare comment, or a print. This is
the check that catches the exact defect the worked contract in sec 5 originally contained: the
first draft grounded eff.seats_released in tool_return quoting the logger.warning at
airline/tools.py:367, which check 4 (quote occurs at that location) happily passed while never
being agent-visible.
"""
import unittest
from pathlib import Path

from spec.validate import Reporter, _classify_tool_return, check8_agent_visibility

REPO_ROOT = str(Path(__file__).resolve().parent.parent / "repos" / "tau2")
PINNED_COMMIT = "c3398666"
TOOLS_FILE = "src/tau2/domains/airline/tools.py"


def _clause_doc(surface: str, file: str, line: int, quote: str, clause_id: str = "eff.seats_released") -> dict:
    """Minimal contract-shaped doc with one effect clause carrying the given provenance --
    enough for check8_agent_visibility, which only reads provenance surface/file/line."""
    return {
        "commit": PINNED_COMMIT,
        "effects": [
            {
                "id": clause_id,
                "text": "irrelevant to this check",
                "predicate": "True",
                "provenance": {"surface": surface, "file": file, "line": line, "quote": quote},
            }
        ],
    }


class TestClassifyToolReturn(unittest.TestCase):
    """Unit-level: the AST classifier itself, against synthetic source, no git plumbing."""

    def test_quote_inside_return_passes(self):
        source = (
            "def f(x):\n"
            "    return x  # the returned value\n"
        )
        passes, desc = _classify_tool_return(source, 2)
        self.assertTrue(passes)
        self.assertEqual(desc, "a return expression")

    def test_quote_inside_raise_passes(self):
        source = (
            "def f(x):\n"
            "    if not x:\n"
            "        raise ValueError('reservation not found')\n"
        )
        passes, desc = _classify_tool_return(source, 3)
        self.assertTrue(passes)
        self.assertEqual(desc, "the message of a raise")

    def test_quote_inside_logger_warning_fails_and_names_the_call(self):
        source = (
            "def f(x):\n"
            "    logger.warning('not implemented!!!')\n"
            "    return x\n"
        )
        passes, desc = _classify_tool_return(source, 2)
        self.assertFalse(passes)
        self.assertEqual(desc, "a logger.warning call")

    def test_quote_inside_print_fails(self):
        source = "print('debug only')\n"
        passes, desc = _classify_tool_return(source, 1)
        self.assertFalse(passes)
        self.assertEqual(desc, "a print call")

    def test_quote_inside_bare_comment_fails(self):
        source = (
            "def f(x):\n"
            "    # not actually released\n"
            "    return x\n"
        )
        passes, desc = _classify_tool_return(source, 2)
        self.assertFalse(passes)
        self.assertEqual(desc, "a comment")


class TestCheck8AgainstRealRepo(unittest.TestCase):
    """Integration-level: the real tau2 airline/tools.py at the pinned commit, via the same
    git-show plumbing check 4 uses. Skipped if the repo clone isn't present locally."""

    @classmethod
    def setUpClass(cls):
        if not Path(REPO_ROOT, ".git").exists():
            raise unittest.SkipTest(f"repos/tau2 not available at {REPO_ROOT}")

    def test_tool_return_at_return_statement_passes(self):
        # line 368 in the pinned commit is `return reservation`.
        doc = _clause_doc("tool_return", TOOLS_FILE, 368, "return reservation")
        rep = Reporter()
        ok = check8_agent_visibility("test.yaml", doc, rep, REPO_ROOT)
        self.assertTrue(ok, rep.failures)
        self.assertEqual(rep.failures, [])

    def test_real_logger_warning_at_367_is_rejected_naming_the_node_type(self):
        doc = _clause_doc(
            "tool_return", TOOLS_FILE, 367, "Seats release not implemented for cancellation!!!"
        )
        rep = Reporter()
        ok = check8_agent_visibility("test.yaml", doc, rep, REPO_ROOT)
        self.assertFalse(ok)
        self.assertEqual(len(rep.failures), 1)
        message = rep.failures[0]
        self.assertIn("eff.seats_released", message)
        self.assertIn("check8_agent_visibility", message)
        self.assertIn(
            "tool_return quote at tools.py:367 occurs in a logger.warning call, "
            "not a return or raise",
            message,
        )
        self.assertIn("re-tier to maintainer_annotation or mark inferred", message)

    def test_maintainer_annotation_at_same_line_367_passes(self):
        # Same file, same line, same quote as the rejected case above -- only the surface
        # differs. maintainer_annotation is not tested by check 8 at all (see the module
        # comment in spec/validate.py), so it passes regardless of what kind of statement the
        # cited line is.
        doc = _clause_doc(
            "maintainer_annotation",
            TOOLS_FILE,
            367,
            "Seats release not implemented for cancellation!!!",
        )
        rep = Reporter()
        ok = check8_agent_visibility("test.yaml", doc, rep, REPO_ROOT)
        self.assertTrue(ok, rep.failures)
        self.assertEqual(rep.failures, [])


if __name__ == "__main__":
    unittest.main()
