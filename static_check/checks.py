#!/usr/bin/env python
"""AST-only candidate-defect-site checks. Nothing here executes benchmark code -- every check
is a pure function over a parsed `ast.Module` (plus the raw source text, for the two checks that
need comment tokens or verbatim line text). That is what lets this module run against tau2-bench
source under this repo's 3.11.7 interpreter even though tau2 itself requires Python >=3.12.

Five checks, one per bullet in the build spec (CLAUDE.md-adjacent instructions, not committed
to a root .md per the "do not touch any root-level .md file" constraint -- this module docstring
is the durable record of what each check does and why):

  constant_success_return   A mutating function whose success-path `return` is a literal,
                             independent of any parameter or state (a syntactic *candidate* for
                             Phantom Effect -- MedAgentBench Finding 1's shape, though
                             MedAgentBench is out of scope for this build's target repos).

  dead_guard                A commented-out `if ...: <raise|return|assignment>` block inside a
                             function body -- FINDINGS-VERIFIED.md Finding 2's exact shape
                             (telecom/tools.py:629-630).

  unused_parameter           A declared parameter that is never read anywhere in the function
                             body, OR is read only inside a `return` value or a logger/print
                             call (i.e. only in what the caller/agent is shown, never in a
                             computation that could affect state or control flow). The second
                             half is what makes this one check cover both Finding 6 (`end_time`
                             is echoed in the success message and nowhere else) and Finding 7
                             (`sort_by` is never referenced at all) -- a purely "never appears as
                             a Name at all" test would catch Finding 7 but miss Finding 6.

  truthiness_guard           `if <param>:` / `if not <param>:` where `<param>`'s declared type
                             annotation admits a meaningful falsy value (bool, int, float, str,
                             with or without `| None` / `Optional[...]`) -- Finding 5's shape:
                             `recurring: bool | None` guarded by `if recurring:` can be set True
                             but never set False through the interface.

  unpaired_state_write       Within one scope (a class, for tau2's tool classes; a module, for
                             agentdojo/mmtoolsandbox's flat tool functions), a function pair
                             whose names match a generic verb-antonym heuristic (book/cancel,
                             add/remove, ...) where the "positive" function writes a state field
                             (attribute/subscript assignment, augmented assignment, or a
                             mutating-method call such as .append/.remove) that the "negative"
                             function never references at all -- Finding 3's shape exactly:
                             `book_reservation` decrements `available_seats`;
                             `cancel_reservation` never mentions `available_seats`.

Every check returns a list of `Flag`. Flags are candidates for human triage, not verdicts --
none of the five defect classes named in a flag's `defect_class_hint` is asserted true; that is
what distinguishes this module from `adapters/contract_check.py`, which evaluates a *contract's*
own predicates against *observed* (pre, post, args, result) tuples.

CLI:
    python static_check/checks.py <file-or-dir> [<file-or-dir> ...] [--json]

Directories are scanned recursively for `*.py`. A file that fails to parse as Python (or fails
to decode as UTF-8) is skipped, not fatal to the run.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.verdict import DefectClass  # noqa: E402  -- reuse the six-class enum, do not redefine it
from spec.validate import _dotted_call_name, _is_logger_call  # noqa: E402  -- reuse check 8's classifier

__all__ = [
    "Flag",
    "run_checks_on_module",
    "check_constant_success_return",
    "check_dead_guard",
    "check_unused_parameters",
    "check_truthiness_guards",
    "check_unpaired_state_writes",
    "main",
]

CHECK_NAMES = (
    "constant_success_return",
    "dead_guard",
    "unused_parameter",
    "truthiness_guard",
    "unpaired_state_write",
)


@dataclass(frozen=True)
class Flag:
    check: str
    file: str
    qualname: str  # "ClassName.method_name", or a bare function name at module scope
    line: int
    end_line: int
    message: str
    snippet: str
    defect_class_hint: Optional[str] = None  # a core.verdict.DefectClass value, or None

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Shared traversal helpers
# ---------------------------------------------------------------------------


def _iter_functions(tree: ast.Module):
    """Yield (qualname, class_node_or_None, func_node) for every def/async def at module scope
    or one level inside a class -- matches every layout observed across the three target repos:
    tau2's tool classes are flat (methods, no nested classes); agentdojo/mmtoolsandbox tool
    files are flat module-level functions."""
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node.name, None, node
        elif isinstance(node, ast.ClassDef):
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    yield f"{node.name}.{sub.name}", node, sub


def _param_names(func) -> list[str]:
    a = func.args
    names = [p.arg for p in a.posonlyargs] + [p.arg for p in a.args] + [p.arg for p in a.kwonlyargs]
    return [n for n in names if n not in ("self", "cls")]


def _param_annotation_text(func, name: str) -> Optional[str]:
    a = func.args
    for p in list(a.posonlyargs) + list(a.args) + list(a.kwonlyargs):
        if p.arg == name and p.annotation is not None:
            try:
                return ast.unparse(p.annotation)
            except Exception:
                return None
    return None


def _snippet(source_lines: list[str], start: int, end: int, max_lines: int = 6) -> str:
    end = min(end, start + max_lines - 1)
    start = max(1, start)
    end = min(end, len(source_lines))
    return "\n".join(source_lines[start - 1 : end])


# ---------------------------------------------------------------------------
# Check 1: constant-success returns
# ---------------------------------------------------------------------------

_MUTATING_METHOD_NAMES = frozenset(
    {"append", "extend", "remove", "pop", "update", "insert", "clear", "add", "discard", "setdefault"}
)


def _is_pure_literal(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return all(_is_pure_literal(e) for e in node.elts)
    if isinstance(node, ast.Dict):
        return all((k is None or _is_pure_literal(k)) and _is_pure_literal(v) for k, v in zip(node.keys, node.values))
    return False


def _function_mutates(func) -> bool:
    """True if the function body writes to an attribute or subscript target anywhere, or calls a
    mutating-shaped method (`.append(...)`, `.remove(...)`, ...) on an attribute chain. A local
    plain-name reassignment does not count -- it is not a state write."""
    for node in ast.walk(func):
        if isinstance(node, (ast.Assign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(t, (ast.Attribute, ast.Subscript)) for t in targets):
                return True
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in _MUTATING_METHOD_NAMES:
                return True
    return False


def check_constant_success_return(file: str, qualname: str, func, source_lines: list[str]) -> list[Flag]:
    if not _function_mutates(func):
        return []
    flags = []
    for node in ast.walk(func):
        if isinstance(node, ast.Return) and node.value is not None and _is_pure_literal(node.value):
            end = getattr(node, "end_lineno", node.lineno)
            flags.append(
                Flag(
                    check="constant_success_return",
                    file=file,
                    qualname=qualname,
                    line=node.lineno,
                    end_line=end,
                    message=(
                        f"{qualname} mutates state elsewhere in its body, but this `return` is a "
                        f"literal constant -- independent of pre-call state, arguments, or whether "
                        f"the mutation actually happened"
                    ),
                    snippet=_snippet(source_lines, node.lineno, end),
                    defect_class_hint=DefectClass.PHANTOM_EFFECT.value,
                )
            )
    return flags


# ---------------------------------------------------------------------------
# Check 2: dead / commented-out guards
# ---------------------------------------------------------------------------

_COMMENT_GUARD_START = re.compile(r"^\s*#\s*(if|elif)\b.*:\s*$")
_COMMENT_GUARD_BODY = re.compile(
    r"^\s*#\s*(raise\b|return\b|continue\b|break\b|pass\b|self\.|[A-Za-z_][A-Za-z0-9_.\[\]]*\s*[+\-*/]?=[^=])"
)


def check_dead_guard(file: str, qualname: str, func, source_lines: list[str]) -> list[Flag]:
    """Purely textual: Python's `ast` module discards comments, so a commented-out guard is
    invisible to any AST walk. This scans the function's own line range for a comment matching
    `# if ...:` immediately followed (within the same contiguous comment block) by a comment that
    looks like the guard's would-be body (a raise, return, or assignment). This is exactly
    FINDINGS-VERIFIED.md Finding 2's shape at telecom/tools.py:629-630."""
    start, end = func.lineno, getattr(func, "end_lineno", func.lineno)
    flags: list[Flag] = []
    i = start
    while i <= end:
        line = source_lines[i - 1] if 0 < i <= len(source_lines) else ""
        if _COMMENT_GUARD_START.match(line):
            block = [line]
            j = i + 1
            while j <= end and j <= len(source_lines) and source_lines[j - 1].strip().startswith("#"):
                block.append(source_lines[j - 1])
                j += 1
            if len(block) >= 2 and any(_COMMENT_GUARD_BODY.match(l) for l in block[1:]):
                flags.append(
                    Flag(
                        check="dead_guard",
                        file=file,
                        qualname=qualname,
                        line=i,
                        end_line=j - 1,
                        message=(
                            f"{qualname}: a commented-out conditional guard spans lines {i}-{j - 1}; "
                            f"the surrounding code runs as though the guard were never written"
                        ),
                        snippet="\n".join(block),
                        defect_class_hint=DefectClass.UNENFORCED_PRECONDITION.value,
                    )
                )
            i = j
        else:
            i += 1
    return flags


# ---------------------------------------------------------------------------
# Check 3: declared parameters never operatively read
# ---------------------------------------------------------------------------


def _add_parents(root: ast.AST) -> None:
    for node in ast.walk(root):
        for child in ast.iter_child_nodes(node):
            child.parent = node  # type: ignore[attr-defined]


def _enclosing_stmt(node: ast.AST):
    n = getattr(node, "parent", None)
    while n is not None and not isinstance(n, ast.stmt):
        n = getattr(n, "parent", None)
    return n


def _is_cosmetic_name_use(name_node: ast.Name) -> bool:
    """A read whose only role is to show a value to the caller/agent or to the log, never to
    compute state or control flow.

    A logger/print statement is cosmetic wholesale -- the same reason a log line is
    `maintainer_annotation` rather than `tool_return` in spec/validate.py's check 8: it never
    reaches the agent and never touches state either.

    A `return` statement is cosmetic ONLY where the name is interpolated into an f-string
    (`ast.JoinedStr`) -- i.e. baked into a message, as `end_time` is in FINDINGS-VERIFIED.md
    Finding 6 (`f"... to {end_time} has been made successfully."`). A name *forwarded live* as a
    call argument inside a `return` (e.g. `return _get("venmo_add_friend")(user_email=user_email)`,
    common in thin dispatch wrappers) is a real, operative use of the argument and must not be
    classified as cosmetic merely because the enclosing statement happens to be a `return` --
    that was this check's first-draft false-positive mode, caught by running it against
    mmtoolsandbox's venmo_social before freezing the rule."""
    stmt = _enclosing_stmt(name_node)
    if stmt is None:
        return False
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
        dotted = _dotted_call_name(stmt.value)
        if _is_logger_call(dotted) or dotted == "print" or dotted.endswith(".print"):
            return True
        return False
    if isinstance(stmt, ast.Return):
        node: Optional[ast.AST] = name_node
        while node is not None and node is not stmt:
            if isinstance(node, ast.JoinedStr):
                return True
            node = getattr(node, "parent", None)
        return False
    return False


def check_unused_parameters(file: str, qualname: str, func, source_lines: list[str]) -> list[Flag]:
    params = _param_names(func)
    if not params:
        return []
    _add_parents(func)
    operative = {p: False for p in params}
    seen_any = {p: False for p in params}
    for node in ast.walk(func):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in params:
            seen_any[node.id] = True
            if not _is_cosmetic_name_use(node):
                operative[node.id] = True
    flags = []
    for p in params:
        if operative[p]:
            continue
        if not seen_any[p]:
            detail = "never referenced anywhere in the function body"
        else:
            detail = (
                "referenced only inside an f-string interpolated into a `return` value, or inside "
                "a logger/print call -- never used to compute a state write or control flow"
            )
        flags.append(
            Flag(
                check="unused_parameter",
                file=file,
                qualname=qualname,
                line=func.lineno,
                end_line=func.lineno,
                message=f"{qualname}: declared parameter '{p}' is {detail}",
                snippet=_snippet(source_lines, func.lineno, func.lineno),
                defect_class_hint=DefectClass.IGNORED_ARGUMENT.value,
            )
        )
    return flags


# ---------------------------------------------------------------------------
# Check 4: truthiness guards on parameters with a meaningful falsy value
# ---------------------------------------------------------------------------

_FALSY_MEANINGFUL_TYPES = frozenset({"bool", "int", "float", "str"})


def _annotation_admits_falsy(annotation_text: Optional[str]) -> bool:
    if not annotation_text:
        return False
    tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", annotation_text)
    return any(t in _FALSY_MEANINGFUL_TYPES for t in tokens)


def check_truthiness_guards(file: str, qualname: str, func, source_lines: list[str]) -> list[Flag]:
    params = _param_names(func)
    if not params:
        return []
    annotations = {p: _param_annotation_text(func, p) for p in params}
    flags = []
    for node in ast.walk(func):
        if isinstance(node, ast.If):
            test = node.test
        elif isinstance(node, ast.IfExp):
            test = node.test
        else:
            continue

        target_name: Optional[str] = None
        negated = False
        if isinstance(test, ast.Name):
            target_name = test.id
        elif isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not) and isinstance(test.operand, ast.Name):
            target_name = test.operand.id
            negated = True

        if target_name is None or target_name not in params:
            continue
        ann = annotations.get(target_name)
        if not _annotation_admits_falsy(ann):
            continue

        flags.append(
            Flag(
                check="truthiness_guard",
                file=file,
                qualname=qualname,
                line=node.lineno,
                end_line=node.lineno,
                message=(
                    f"{qualname}: `if {'not ' if negated else ''}{target_name}:` is a bare "
                    f"truthiness test but '{target_name}' is declared '{ann}', which admits a "
                    f"meaningful falsy value (0, 0.0, '', or False) that this test cannot "
                    f"distinguish from 'not supplied'"
                ),
                snippet=_snippet(source_lines, node.lineno, node.lineno),
                defect_class_hint=DefectClass.IGNORED_ARGUMENT.value,
            )
        )
    return flags


# ---------------------------------------------------------------------------
# Check 5: unpaired state writes
# ---------------------------------------------------------------------------

# Generic English verb-antonym pairs used only to *name* candidate paired operations -- these are
# not tool names and are not tuned to any one benchmark. (verb_a, verb_b): verb_a is read as the
# "positive"/forward operation, verb_b as its presumed inverse, but the check itself is symmetric
# -- it reports a missing reference in either direction.
_ANTONYM_VERB_PAIRS = [
    ("book", "cancel"),
    ("reserve", "cancel"),
    ("schedule", "cancel"),
    ("create", "delete"),
    ("create", "remove"),
    ("add", "remove"),
    ("add", "delete"),
    ("open", "close"),
    ("start", "stop"),
    ("begin", "end"),
    ("enable", "disable"),
    ("activate", "deactivate"),
    ("activate", "suspend"),
    ("suspend", "resume"),
    ("lock", "unlock"),
    ("subscribe", "unsubscribe"),
    ("increase", "decrease"),
    ("increment", "decrement"),
    ("apply", "revert"),
    ("charge", "refund"),
    ("grant", "revoke"),
    ("connect", "disconnect"),
    ("mount", "unmount"),
    ("acquire", "release"),
]
_ALL_VERBS = {v for pair in _ANTONYM_VERB_PAIRS for v in pair}


def _split_verb(name: str) -> tuple[Optional[str], str]:
    for verb in _ALL_VERBS:
        prefix = verb + "_"
        if name.startswith(prefix):
            return verb, name[len(prefix) :]
    return None, name


def _is_paired(name_a: str, name_b: str) -> bool:
    va, rest_a = _split_verb(name_a)
    vb, rest_b = _split_verb(name_b)
    if va is None or vb is None or rest_a != rest_b or not rest_a:
        return False
    return (va, vb) in _ANTONYM_VERB_PAIRS or (vb, va) in _ANTONYM_VERB_PAIRS


def _rightmost_field(node: ast.AST) -> Optional[str]:
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Subscript):
        return _rightmost_field(node.value)
    return None


def _target_field_names(t: ast.AST) -> set[str]:
    out: set[str] = set()
    if isinstance(t, ast.Attribute):
        out.add(t.attr)
    elif isinstance(t, ast.Subscript):
        name = _rightmost_field(t.value)
        if name:
            out.add(name)
        if isinstance(t.value, ast.Attribute):
            out.add(t.value.attr)
    return out


def _written_fields(func) -> set[str]:
    """Best-effort set of state-field identifiers this function writes: attribute/subscript
    assignment or augmented-assignment targets, and the base attribute of a mutating-method call
    (`x.field.append(...)` -> "field")."""
    fields: set[str] = set()
    for node in ast.walk(func):
        if isinstance(node, (ast.Assign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                fields |= _target_field_names(t)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in _MUTATING_METHOD_NAMES:
            name = _rightmost_field(node.func.value)
            if name:
                fields.add(name)
    return fields


def _referenced_fields(func) -> set[str]:
    """Every attribute name mentioned anywhere in the function, read or write -- the superset used
    to test "does the paired function touch this field at all"."""
    return {node.attr for node in ast.walk(func) if isinstance(node, ast.Attribute)}


def check_unpaired_state_writes(
    file: str, scope_name: Optional[str], functions: list[tuple[str, ast.AST]], source_lines: list[str]
) -> list[Flag]:
    """`functions` is every (bare) function name and node sharing one scope -- a class's methods,
    or a module's top-level functions. Only fields that look like real state (skip private/dunder
    names) are reported, and each (pair, missing-field-set) is reported once against the function
    that fails to reference it."""
    writes = {name: _written_fields(node) for name, node in functions}
    refs = {name: _referenced_fields(node) | writes[name] for name, node in functions}
    flags: list[Flag] = []
    reported: set[tuple[str, str]] = set()
    for name_a, _node_a in functions:
        for name_b, node_b in functions:
            if name_a == name_b or not _is_paired(name_a, name_b):
                continue
            missing = {f for f in writes[name_a] if f not in refs[name_b] and not f.startswith("_")}
            key = (name_a, name_b)
            if missing and key not in reported:
                reported.add(key)
                qualname_b = f"{scope_name}.{name_b}" if scope_name else name_b
                qualname_a = f"{scope_name}.{name_a}" if scope_name else name_a
                flags.append(
                    Flag(
                        check="unpaired_state_write",
                        file=file,
                        qualname=qualname_b,
                        line=node_b.lineno,
                        end_line=node_b.lineno,
                        message=(
                            f"{qualname_b} looks like the paired inverse of {qualname_a} (verb "
                            f"pair), but never references field(s) {sorted(missing)} that "
                            f"{qualname_a} writes"
                        ),
                        snippet=_snippet(source_lines, node_b.lineno, node_b.lineno),
                        defect_class_hint=DefectClass.PARTIAL_EFFECT.value,
                    )
                )
    return flags


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def run_checks_on_module(file_label: str, source_text: str) -> list[Flag]:
    tree = ast.parse(source_text)
    source_lines = source_text.splitlines()
    funcs = list(_iter_functions(tree))

    flags: list[Flag] = []
    for qualname, _cls, func in funcs:
        flags += check_constant_success_return(file_label, qualname, func, source_lines)
        flags += check_dead_guard(file_label, qualname, func, source_lines)
        flags += check_unused_parameters(file_label, qualname, func, source_lines)
        flags += check_truthiness_guards(file_label, qualname, func, source_lines)

    by_scope: dict[Optional[str], list[tuple[str, ast.AST]]] = {}
    for qualname, cls, func in funcs:
        scope = cls.name if cls is not None else None
        by_scope.setdefault(scope, []).append((func.name, func))
    for scope, fs in by_scope.items():
        flags += check_unpaired_state_writes(file_label, scope, fs, source_lines)

    return flags


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="AST-only candidate-defect-site checks (executes nothing).")
    ap.add_argument("paths", nargs="+", help="Python source files, or directories scanned recursively for *.py")
    ap.add_argument("--json", action="store_true", help="Emit JSON instead of one line per flag")
    args = ap.parse_args(argv)

    files: list[Path] = []
    for raw in args.paths:
        p = Path(raw)
        if p.is_dir():
            files.extend(sorted(p.rglob("*.py")))
        else:
            files.append(p)

    all_flags: list[Flag] = []
    skipped = 0
    for p in files:
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            skipped += 1
            continue
        try:
            all_flags.extend(run_checks_on_module(str(p), text))
        except SyntaxError:
            skipped += 1
            continue

    if args.json:
        print(json.dumps([f.to_dict() for f in all_flags], indent=2))
    else:
        for f in all_flags:
            print(f"{f.file}:{f.line}: [{f.check}] {f.qualname}: {f.message}")
        print(f"\n{len(all_flags)} flag(s) across {len(files) - skipped} file(s), {skipped} skipped", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
