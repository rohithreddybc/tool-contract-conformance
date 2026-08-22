"""The restricted predicate evaluator. PREDICATE-GRAMMAR.md sec 1, 2, 2.1, 2.3.

compile_predicate() parses a predicate string, rejects anything outside the whitelist,
rewrites dotted access to subscripting, and rejects free names -- all at contract-authoring
time. evaluate() runs the compiled expression against the four bindings and turns a missing
snapshot path into PathError rather than a silent False (sec 2.3).
"""
from __future__ import annotations

import ast
import builtins as _builtins
from dataclasses import dataclass
from typing import Any

PATH_ROOTS = frozenset({"pre", "post", "args", "result"})

ALLOWED_BUILTINS = frozenset(
    {"len", "sum", "min", "max", "abs", "round", "sorted", "any", "all", "set", "int", "float", "str", "bool"}
)

ALLOWED_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow)
ALLOWED_UNARYOPS = (ast.UAdd, ast.USub, ast.Not)
ALLOWED_CMPOPS = (ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn)
ALLOWED_CONST_TYPES = (str, int, float, bool, type(None))


class PredicateError(Exception):
    """Raised at compile time for a disallowed construct, or wraps a runtime path failure."""

    def __init__(self, message: str, node: ast.AST | None = None):
        col = getattr(node, "col_offset", None)
        located = f"{message} (col {col})" if col is not None else message
        super().__init__(located)
        self.node = node


class PathError(PredicateError):
    """A snapshot/args/result path did not resolve. Caller maps this to UNTESTABLE /
    no_observable_state -- see PREDICATE-GRAMMAR.md sec 2.3. Never silently False."""


@dataclass
class CompiledPredicate:
    source: str
    code: Any
    tree: ast.Expression


def _reject(node: ast.AST, what: str):
    raise PredicateError(f"disallowed construct: {what}", node)


# ---------------------------------------------------------------------------
# Phase 1: whitelist walk over the *original* tree (Attribute still present).
# ---------------------------------------------------------------------------


def _check_whitelist(node: ast.AST) -> None:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, complex) or not isinstance(node.value, ALLOWED_CONST_TYPES):
            _reject(node, f"constant of type {type(node.value).__name__}")
        return

    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        for elt in node.elts:
            _check_whitelist(elt)
        return

    if isinstance(node, ast.Dict):
        for k, v in zip(node.keys, node.values):
            if k is not None:
                _check_whitelist(k)
            _check_whitelist(v)
        return

    if isinstance(node, ast.Name):
        return  # legality of the identifier itself is decided by the free-name pass

    if isinstance(node, ast.Attribute):
        if node.attr.startswith("__") and node.attr.endswith("__"):
            _reject(node, f"dunder attribute .{node.attr}")
        _check_whitelist(node.value)
        return

    if isinstance(node, ast.Subscript):
        _check_whitelist(node.value)
        _check_whitelist(node.slice)
        return

    if isinstance(node, ast.Slice):
        for part in (node.lower, node.upper, node.step):
            if part is not None:
                _check_whitelist(part)
        return

    if isinstance(node, ast.BoolOp):
        for v in node.values:
            _check_whitelist(v)
        return

    if isinstance(node, ast.UnaryOp):
        if not isinstance(node.op, ALLOWED_UNARYOPS):
            _reject(node, f"unary operator {type(node.op).__name__}")
        _check_whitelist(node.operand)
        return

    if isinstance(node, ast.BinOp):
        if not isinstance(node.op, ALLOWED_BINOPS):
            _reject(node, f"binary operator {type(node.op).__name__}")
        _check_whitelist(node.left)
        _check_whitelist(node.right)
        return

    if isinstance(node, ast.Compare):
        for op in node.ops:
            if not isinstance(op, ALLOWED_CMPOPS):
                _reject(node, f"comparison operator {type(op).__name__}")
        _check_whitelist(node.left)
        for c in node.comparators:
            _check_whitelist(c)
        return

    if isinstance(node, ast.IfExp):
        _check_whitelist(node.test)
        _check_whitelist(node.body)
        _check_whitelist(node.orelse)
        return

    if isinstance(node, (ast.GeneratorExp, ast.ListComp, ast.SetComp)):
        _check_comprehension_generators(node.generators)
        _check_whitelist(node.elt)
        return

    if isinstance(node, ast.DictComp):
        _check_comprehension_generators(node.generators)
        _check_whitelist(node.key)
        _check_whitelist(node.value)
        return

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in ALLOWED_BUILTINS:
            _reject(node, "call to a callee that is not a bare allowed builtin")
        if node.keywords:
            _reject(node, "keyword arguments")
        for a in node.args:
            if isinstance(a, ast.Starred):
                _reject(a, "starred call argument")
            _check_whitelist(a)
        return

    _reject(node, type(node).__name__)


def _check_comprehension_generators(generators: list[ast.comprehension]) -> None:
    for gen in generators:
        if gen.is_async:
            _reject(gen.target, "async comprehension")
        _check_whitelist(gen.iter)
        _check_binder_target(gen.target)
        for cond in gen.ifs:
            _check_whitelist(cond)


def _check_binder_target(target: ast.AST) -> None:
    if isinstance(target, ast.Name):
        return
    if isinstance(target, (ast.Tuple, ast.List)):
        for elt in target.elts:
            _check_binder_target(elt)
        return
    _reject(target, "comprehension binder must be a name, or a tuple/list of names")


# ---------------------------------------------------------------------------
# Phase 2: rewrite dotted access into subscripting, everywhere in the tree.
# ---------------------------------------------------------------------------


class _AttributeRewriter(ast.NodeTransformer):
    def visit_Attribute(self, node: ast.Attribute) -> ast.Subscript:
        value = self.visit(node.value)
        new = ast.Subscript(value=value, slice=ast.Constant(value=node.attr), ctx=ast.Load())
        return ast.copy_location(new, node)


def _rewrite_attributes(node: ast.AST) -> ast.AST:
    return _AttributeRewriter().visit(node)


# ---------------------------------------------------------------------------
# Phase 3: free-name analysis on the rewritten tree, respecting comprehension binders.
# ---------------------------------------------------------------------------


def _binder_names(target: ast.AST) -> frozenset:
    if isinstance(target, ast.Name):
        return frozenset({target.id})
    if isinstance(target, (ast.Tuple, ast.List)):
        names = set()
        for elt in target.elts:
            names |= _binder_names(elt)
        return frozenset(names)
    return frozenset()


def _check_free_names(node: ast.AST, bound: frozenset) -> None:
    if isinstance(node, ast.Name):
        if node.id not in PATH_ROOTS and node.id not in bound:
            raise PredicateError(f"free name '{node.id}' is not bound", node)
        return

    if isinstance(node, (ast.GeneratorExp, ast.ListComp, ast.SetComp, ast.DictComp)):
        cur_bound = bound
        for gen in node.generators:
            _check_free_names(gen.iter, cur_bound)
            cur_bound = cur_bound | _binder_names(gen.target)
            for cond in gen.ifs:
                _check_free_names(cond, cur_bound)
        if isinstance(node, ast.DictComp):
            _check_free_names(node.key, cur_bound)
            _check_free_names(node.value, cur_bound)
        else:
            _check_free_names(node.elt, cur_bound)
        return

    if isinstance(node, ast.Call):
        # node.func is a bare allowed-builtin Name, already validated in the whitelist pass --
        # it is not a value reference and must not be checked against the four bindings.
        for a in node.args:
            _check_free_names(a, bound)
        return

    for child in ast.iter_child_nodes(node):
        _check_free_names(child, bound)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compile_predicate(src: str) -> CompiledPredicate:
    try:
        parsed = ast.parse(src, mode="eval")
    except SyntaxError as e:
        raise PredicateError(f"syntax error: {e.msg}") from e

    _check_whitelist(parsed.body)
    rewritten_body = _rewrite_attributes(parsed.body)
    tree = ast.Expression(body=rewritten_body)
    ast.fix_missing_locations(tree)
    _check_free_names(tree.body, frozenset())

    code = compile(tree, "<predicate>", "eval")
    return CompiledPredicate(source=src, code=code, tree=tree)


def evaluate(compiled: CompiledPredicate, pre: Any, post: Any, args: Any, result: Any) -> bool:
    safe_builtins = {name: getattr(_builtins, name) for name in ALLOWED_BUILTINS}
    # A single namespace, not separate globals/locals: comprehensions compile to a nested
    # scope that (per CPython) only sees the *globals* dict of an eval() call, not a
    # separately-passed locals dict -- passing pre/post/args/result as locals would make them
    # invisible inside `all(... for x in pre.foo)`.
    env = {"__builtins__": safe_builtins, "pre": pre, "post": post, "args": args, "result": result}
    try:
        value = eval(compiled.code, env)  # noqa: S307 -- restricted AST, see compile_predicate
    except (KeyError, IndexError, TypeError) as e:
        raise PathError(f"path did not resolve evaluating {compiled.source!r}: {e!r}") from e
    return bool(value)
