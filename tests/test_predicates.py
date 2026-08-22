"""Tests for core/predicates.py. Run with: python -m unittest discover tests"""
import unittest

from core.predicates import PathError, PredicateError, PredicateTypeError, compile_predicate, evaluate


def ev(src, pre=None, post=None, args=None, result=None):
    compiled = compile_predicate(src)
    return evaluate(compiled, pre or {}, post or {}, args or {}, result or {})


class TestWhitelist(unittest.TestCase):
    """Every rejected AST node kind is actually rejected."""

    def test_import_is_a_syntax_error(self):
        with self.assertRaises(PredicateError):
            compile_predicate("import os")

    def test_lambda_rejected(self):
        with self.assertRaises(PredicateError):
            compile_predicate("(lambda: 1)()")

    def test_named_expr_walrus_rejected(self):
        with self.assertRaises(PredicateError):
            compile_predicate("(x := 1)")

    def test_fstring_rejected(self):
        with self.assertRaises(PredicateError):
            compile_predicate("f'{pre}'")

    def test_yield_rejected(self):
        with self.assertRaises(PredicateError):
            compile_predicate("(yield 1)")

    def test_await_rejected(self):
        with self.assertRaises(PredicateError):
            compile_predicate("(await pre)")

    def test_dunder_attribute_rejected(self):
        with self.assertRaises(PredicateError):
            compile_predicate("pre.__class__")

    def test_disallowed_callee_rejected(self):
        with self.assertRaises(PredicateError):
            compile_predicate("open('x')")

    def test_call_on_non_bare_name_rejected(self):
        with self.assertRaises(PredicateError):
            compile_predicate("pre.customers.keys()")

    def test_bitwise_binop_rejected(self):
        with self.assertRaises(PredicateError):
            compile_predicate("pre.x & 1")

    def test_exponentiation_rejected(self):
        # Regression: ast.Pow used to be in ALLOWED_BINOPS. `pre.x ** 10 ** 10 ** 10` compiles,
        # passes the whitelist, and hangs the process with no timeout anywhere in the evaluation
        # path. No shipped contract uses exponentiation.
        with self.assertRaises(PredicateError):
            compile_predicate("pre.x ** 2")

    def test_starred_call_arg_rejected(self):
        with self.assertRaises(PredicateError):
            compile_predicate("len(*pre.x)")

    def test_keyword_call_arg_rejected(self):
        with self.assertRaises(PredicateError):
            compile_predicate("sorted(pre.x, key=str)")

    def test_bytes_constant_rejected(self):
        with self.assertRaises(PredicateError):
            compile_predicate("pre.x == b'y'")

    def test_allowed_builtin_call_compiles(self):
        compile_predicate("len(pre.x) == 0")

    def test_error_names_offending_construct(self):
        with self.assertRaises(PredicateError) as cm:
            compile_predicate("import os")
        # syntax errors don't carry a node, so just check something informative was raised
        self.assertTrue(str(cm.exception))

    def test_error_names_call_construct(self):
        with self.assertRaises(PredicateError) as cm:
            compile_predicate("eval('1')")
        self.assertIn("call", str(cm.exception))


class TestFreeNames(unittest.TestCase):
    """PREDICATE-GRAMMAR.md sec 2.1: every free name must be a binding or a comprehension binder."""

    def test_unbound_names_rejected_and_named_in_message(self):
        # the exact v1-draft clause the grammar doc calls out as broken
        src = "post.flights[f].available_seats == pre.flights[f].available_seats + booked_seats"
        with self.assertRaises(PredicateError) as cm:
            compile_predicate(src)
        message = str(cm.exception)
        self.assertIn("f", message)

    def test_bound_comprehension_passes(self):
        src = (
            "all(\n"
            "  post.flights[f].available_seats == pre.flights[f].available_seats + args.n_seats\n"
            "  for f in args.reservation.flights\n"
            ")"
        )
        compiled = compile_predicate(src)
        pre = {"flights": {"HAT1": {"available_seats": 3}}}
        post = {"flights": {"HAT1": {"available_seats": 5}}}
        args = {"reservation": {"flights": ["HAT1"]}, "n_seats": 2}
        self.assertTrue(evaluate(compiled, pre, post, args, {}))

    def test_free_name_in_generator_iterable_rejected(self):
        with self.assertRaises(PredicateError):
            compile_predicate("any(x == 1 for x in undeclared_thing)")

    def test_builtin_callee_name_is_not_a_free_name(self):
        # 'len' is a Name node too, in Call.func position, but is not subject to free-name checks
        compile_predicate("len(pre.x) == len(post.x)")

    def test_dict_comp_binder_visible_in_key_and_value(self):
        src = "sum(v for k, v in [(1, 2)] if k == 1)"
        # tuple-unpacking binder target
        compile_predicate(src)

    def test_second_generator_sees_first_generators_binder(self):
        src = "any(y for x in [pre.a] for y in x)"
        compiled = compile_predicate(src)
        self.assertTrue(evaluate(compiled, {"a": [1]}, {}, {}, {}))

    def test_earlier_generator_iterable_cannot_see_later_binder(self):
        # 'y' is only bound by the *second* generator; using it in the *first* generator's
        # iterable is a free-name error even though 'y' is a binder somewhere in the expression
        with self.assertRaises(PredicateError):
            compile_predicate("any(x for x in y for y in [1])")


class TestMissingPaths(unittest.TestCase):
    """PREDICATE-GRAMMAR.md sec 2.3: a missing path raises PathError, never False."""

    def test_missing_top_level_key_raises_path_error(self):
        compiled = compile_predicate("pre.customers")
        with self.assertRaises(PathError):
            evaluate(compiled, {}, {}, {}, {})

    def test_missing_path_does_not_silently_return_false(self):
        compiled = compile_predicate("pre.customers.missing_field == 'x'")
        with self.assertRaises(PathError):
            evaluate(compiled, {"customers": {}}, {}, {}, {})

    def test_membership_check_is_the_documented_workaround(self):
        compiled = compile_predicate("'k' in pre.customers")
        self.assertFalse(evaluate(compiled, {"customers": {}}, {}, {}, {}))
        self.assertTrue(evaluate(compiled, {"customers": {"k": 1}}, {}, {}, {}))

    def test_index_out_of_range_raises_path_error(self):
        compiled = compile_predicate("pre.items[5] == 1")
        with self.assertRaises(PathError):
            evaluate(compiled, {"items": [1, 2]}, {}, {}, {})


class TestPredicateTypeError(unittest.TestCase):
    """core/predicates.py:267 -- TypeError must not be misreported as PathError/no_observable_
    state when the path resolved perfectly and the failure is a comparison/arithmetic type
    mismatch. PREDICATE-GRAMMAR.md sec 2.3 is about paths that do not resolve; this is a
    different, separately-countable failure."""

    def test_comparison_against_null_raises_predicate_type_error_not_path_error(self):
        # `balance` resolves on both sides -- the path is fine. `None > 0` is a TypeError, and
        # must not be silently recorded as an unresolved path.
        compiled = compile_predicate("post.balance > pre.balance")
        pre = {"balance": 0}
        post = {"balance": None}
        with self.assertRaises(PredicateTypeError):
            evaluate(compiled, pre, post, {}, {})
        # and it must NOT be a PathError (PredicateTypeError does not subclass PathError)
        try:
            evaluate(compiled, pre, post, {}, {})
        except PredicateTypeError:
            pass
        except PathError:
            self.fail("TypeError on a resolved path must not be raised as PathError")

    def test_predicate_type_error_is_not_a_path_error(self):
        self.assertFalse(issubclass(PredicateTypeError, PathError))
        self.assertTrue(issubclass(PredicateTypeError, PredicateError))

    def test_subscripting_a_number_still_raises_something_catchable(self):
        # The genuine ambiguity the fix does not paper over: subscripting a non-container is
        # ALSO a TypeError (`pre.foo.bar` where `foo` is a number is `int.__getitem__`, not a
        # KeyError). It now lands in PredicateTypeError too, not PathError -- deliberately: both
        # causes are TypeErrors and are counted together under predicate_type_error, distinct
        # from genuine KeyError/IndexError path failures.
        compiled = compile_predicate("pre.foo.bar")
        with self.assertRaises(PredicateTypeError):
            evaluate(compiled, {"foo": 5}, {}, {}, {})

    def test_missing_key_still_raises_path_error_not_predicate_type_error(self):
        # KeyError/IndexError are unaffected by this fix -- still PathError.
        compiled = compile_predicate("pre.customers")
        with self.assertRaises(PathError):
            evaluate(compiled, {}, {}, {}, {})


class TestNonBooleanResult(unittest.TestCase):
    """core/predicates.py:269 -- a predicate must evaluate to bool. Silent bool() coercion would
    let e.g. `len(post.reservations)` (author meant `== 0`) report CONFORMS on every non-empty
    collection -- the inverse of the intent, with no error anywhere."""

    def test_truthy_non_bool_result_raises(self):
        compiled = compile_predicate("len(post.reservations)")
        with self.assertRaises(PredicateError):
            evaluate(compiled, {}, {"reservations": [1, 2, 3]}, {}, {})

    def test_falsy_non_bool_result_also_raises(self):
        # The coercion bug is not just "non-empty coerces True" -- ANY non-bool return is a
        # contract-authoring error, including one that happens to coerce False, because that
        # correctness only holds by accident of the current data.
        compiled = compile_predicate("len(post.reservations)")
        with self.assertRaises(PredicateError):
            evaluate(compiled, {}, {"reservations": []}, {}, {})

    def test_genuine_boolean_result_still_passes(self):
        compiled = compile_predicate("len(post.reservations) == 0")
        self.assertTrue(evaluate(compiled, {}, {"reservations": []}, {}, {}))
        self.assertFalse(evaluate(compiled, {}, {"reservations": [1]}, {}, {}))


class TestDottedRewrite(unittest.TestCase):
    def test_dotted_access_is_subscripting(self):
        # NOTE: this test previously called evaluate() on the bare non-boolean expression
        # "pre.customers" and asserted `is not None` -- which passed only because evaluate()
        # used to coerce any truthy non-bool result to True with `bool(value)`. That is exactly
        # the silent-coercion bug TestNonBooleanResult now guards against (a real contract
        # author's mistake -- e.g. `len(post.reservations)` instead of `== 0` -- would have
        # reported CONFORMS silently). Rewritten to compare dotted vs subscript access through a
        # genuinely boolean predicate instead of relying on truthy coercion of a bare path.
        snap = {"customers": {"a": 1}}
        dotted = compile_predicate("pre.customers.a == 1")
        subscripted = compile_predicate("pre['customers']['a'] == 1")
        self.assertTrue(evaluate(dotted, snap, {}, {}, {}))
        self.assertTrue(evaluate(subscripted, snap, {}, {}, {}))
        self.assertTrue(
            evaluate(compile_predicate("pre.customers == pre['customers']"), snap, {}, {}, {})
        )

    def test_result_error_membership(self):
        compiled = compile_predicate("'error' not in result")
        self.assertTrue(evaluate(compiled, {}, {}, {}, {}))
        self.assertFalse(evaluate(compiled, {}, {}, {}, {"error": "boom"}))


if __name__ == "__main__":
    unittest.main()
