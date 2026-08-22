#!/usr/bin/env python
"""Draft contract clauses from a tool's docstring, signature, and body, for human review.

This is NOT a contract author. It is a static reading assistant: it locates the advertised
surfaces `spec/schema.json` recognizes (docstring prose, `:param:`/Args: descriptions, `Raises:`
bullets, and return/raise statements that might ground `tool_return`), assigns each a grounding
tier, and emits a schema-valid draft `Contract` document. Every clause it emits carries
`inferred: true` and a `_draft` id suffix -- the two schema-native, always-honored markers that
keep a drafted clause out of every headline count (`core/model.py: headline_tier()` returns
`INFERRED` whenever `inferred` is true, before it even looks at the provenance surface) until a
human reviews it, corrects the placeholder `True` predicate, and flips `inferred` to `false`.
Nothing this module writes is ever, by construction, headline-eligible on its own.

Grounding-tier correctness (the other half of the acceptance bar): a quote that sits inside a
`logger.*` call, a `print` call, or a bare comment is tiered `maintainer_annotation`, never
`tool_return` -- reusing spec/validate.py's own check-8 classifier (`_classify_tool_return`)
rather than re-implementing the "is this actually agent-visible" judgment call a second, possibly
divergent, way. A quote inside an actual `return` expression or the message of a `raise` is
tiered `tool_return`. Docstring, Args:/`:param:`, and Raises: text is tiered `docstring` --
structurally agent-visible, since it ships with the tool's own definition.

CLI:
    python static_check/extract.py <file> <qualname> --benchmark B --commit C [-o out.yaml]

`qualname` is the function name, or `ClassName.method_name` for a class method (matches
static_check/checks.py's qualname convention). Prints YAML to stdout, or writes to `-o`.
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from spec.validate import _classify_tool_return  # noqa: E402 -- reuse check 8's classifier, do not duplicate

__all__ = ["draft_contract", "main"]

_SECTION_HEADERS = ("Args", "Arguments", "Returns", "Return", "Raises", "Note", "Notes")
_INLINE_LABELS = ("Checks", "Logic")  # tau2's own convention -- generic, not tool-specific: any
# docstring in any of the three repos that uses this "Label: prose" shape is handled the same way.


# ---------------------------------------------------------------------------
# Docstring reading, verbatim, with file line numbers preserved throughout
# ---------------------------------------------------------------------------


def _docstring_raw_lines(func: ast.AST, source_lines: list[str]) -> list[tuple[int, str]]:
    """(lineno, raw_text) for every physical line the docstring literal spans, numbered against
    the real file -- never de-indented or re-flowed, so every drafted quote is guaranteed to be a
    literal substring of its cited line (spec/validate.py check 4's requirement)."""
    body = getattr(func, "body", None)
    if not body:
        return []
    first = body[0]
    if not (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str)):
        return []
    start, end = first.lineno, getattr(first, "end_lineno", first.lineno)
    return [(ln, source_lines[ln - 1]) for ln in range(start, end + 1) if 0 < ln <= len(source_lines)]


def _strip_quotes_and_label(raw: str) -> str:
    s = raw.strip()
    for q in ('"""', "'''"):
        if s.startswith(q):
            s = s[len(q) :]
        if s.endswith(q) and len(s) >= len(q):
            s = s[: -len(q)]
    return s.strip()


def _split_reST_param(line: str) -> Optional[tuple[str, str]]:
    m = re.match(r"^:param\s+(\w+):\s*(.*)$", line)
    return (m.group(1), m.group(2).strip()) if m else None


def _split_reST_raises(line: str) -> Optional[tuple[str, str]]:
    m = re.match(r"^:raises?\s+([\w.]+):\s*(.*)$", line)
    return (m.group(1), m.group(2).strip()) if m else None


def _split_google_bullet(line: str) -> Optional[tuple[str, str]]:
    """`name: description` or `ExcType: description`, Google-style Args:/Raises: bullet."""
    m = re.match(r"^([A-Za-z_][A-Za-z0-9_.]*)\s*(?:\([^)]*\))?:\s*(.*)$", line)
    return (m.group(1), m.group(2).strip()) if m else None


class ParsedDocstring:
    """Structured, line-numbered read of one docstring. `summary` and `logic` are prose sentences
    drafted as candidate effect clauses; `checks` are prose phrases drafted as candidate
    preconditions; `raises` are (exc_type, description) drafted as candidate preconditions (an
    advertised exception implies an advertised precondition); `params` is name -> (lineno, desc)
    for signature.args provenance."""

    def __init__(self) -> None:
        self.summary: list[tuple[int, str]] = []
        self.checks: list[tuple[int, str]] = []
        self.logic: list[tuple[int, str]] = []
        self.raises: list[tuple[int, str, str]] = []
        self.params: dict[str, tuple[int, str]] = {}


def parse_docstring(doc_lines: list[tuple[int, str]]) -> ParsedDocstring:
    result = ParsedDocstring()
    section: Optional[str] = None  # None while in the summary block; else the active header text

    for lineno, raw in doc_lines:
        text = _strip_quotes_and_label(raw)
        if not text:
            continue

        header = next((h for h in _SECTION_HEADERS if text.rstrip(":") == h), None)
        if header:
            section = header
            continue

        if section in ("Args", "Arguments"):
            pair = _split_reST_param(text) or _split_google_bullet(text)
            if pair:
                result.params[pair[0]] = (lineno, pair[1])
            continue

        if section == "Raises":
            pair = _split_reST_raises(text) or _split_google_bullet(text)
            if pair:
                result.raises.append((lineno, pair[0], pair[1]))
            continue

        if section in ("Returns", "Return", "Note", "Notes"):
            continue  # free text only, per schema.json signature.returns comment -- not checked

        # Still in the summary block (section is None): look for tau2's inline "Checks:"/"Logic:"
        # convention on this physical line before falling back to a generic summary sentence.
        pair = _split_reST_param(text)
        if pair:  # a :param: appearing before any Args: header, seen in some reST docstrings
            result.params[pair[0]] = (lineno, pair[1])
            continue
        matched_label = False
        for label in _INLINE_LABELS:
            prefix = label + ":"
            if text.startswith(prefix):
                remainder = text[len(prefix) :].strip()
                bucket = result.checks if label == "Checks" else result.logic
                for phrase in _split_clauses(remainder):
                    bucket.append((lineno, phrase))
                matched_label = True
                break
        if not matched_label:
            result.summary.append((lineno, text))

    return result


def _split_clauses(remainder: str) -> list[str]:
    """Split a 'Checks: A, B.' / 'Logic: A and B.' remainder into independent checkable phrases.
    annotation_protocol.md sec 2 rule 1: a sentence asserting two independent properties yields
    two clauses. Comma is the observed separator (tau2's own convention); ' and ' is handled too
    since it is the generic English equivalent."""
    remainder = remainder.rstrip(".").strip()
    if not remainder:
        return []
    parts = re.split(r",\s*|\s+and\s+", remainder)
    return [p.strip() for p in parts if p.strip()]


# ---------------------------------------------------------------------------
# Grounding-tier assignment (reuses spec/validate.py's check-8 classifier)
# ---------------------------------------------------------------------------


def _classify_body_quote(source_text: str, line: int) -> str:
    """surface for a quote found inside the function BODY (as opposed to the docstring): the same
    return/raise-vs-logger/comment distinction validator check 8 enforces, applied at draft time
    so the extractor cannot generate a clause check 8 will later reject. Returns 'tool_return' or
    'maintainer_annotation' -- never anything else, since a body quote is never 'docstring'."""
    passes, _desc = _classify_tool_return(source_text, line)
    return "tool_return" if passes else "maintainer_annotation"


# ---------------------------------------------------------------------------
# AST-level helpers
# ---------------------------------------------------------------------------


def _find_function(tree: ast.Module, qualname: str) -> ast.AST:
    if "." in qualname:
        cls_name, method_name = qualname.split(".", 1)
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name == cls_name:
                for sub in node.body:
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)) and sub.name == method_name:
                        return sub
        raise ValueError(f"{qualname!r} not found (class {cls_name!r} or method {method_name!r} missing)")
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == qualname:
            return node
    raise ValueError(f"function {qualname!r} not found at module scope")


def _string_value_expressions(value: Optional[ast.AST]):
    """Yield each top-level string-producing sub-expression of a return/raise value: a bare
    string `Constant`, or a whole `JoinedStr` (f-string) taken as one unit -- recursing through
    Dict values, Call args/keywords, and List/Tuple/Set elements, but never descending into a
    JoinedStr's own `FormattedValue.format_spec` (which holds format-spec text like '.2f', not
    advertised content). Treating an f-string as one unit, rather than walking every nested
    Constant fragment inside it, is what keeps one f-strung success message from exploding into
    a dozen near-meaningless single-word clause drafts."""
    if value is None:
        return
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        if value.value.strip() and "\n" not in value.value:
            yield value
        return
    if isinstance(value, ast.JoinedStr):
        yield value
        return
    if isinstance(value, ast.Dict):
        for v in value.values:
            yield from _string_value_expressions(v)
        return
    if isinstance(value, (ast.List, ast.Tuple, ast.Set)):
        for e in value.elts:
            yield from _string_value_expressions(e)
        return
    if isinstance(value, ast.Call):
        for a in value.args:
            yield from _string_value_expressions(a)
        for kw in value.keywords:
            yield from _string_value_expressions(kw.value)
        return
    return


def _joinedstr_skeleton(node: ast.JoinedStr) -> str:
    parts = []
    for v in node.values:
        if isinstance(v, ast.Constant) and isinstance(v.value, str):
            parts.append(v.value)
        elif isinstance(v, ast.FormattedValue):
            parts.append("{...}")
    return "".join(parts).strip()


def _longest_literal_fragment(expr: ast.AST) -> str:
    """A substring of `expr` guaranteed to be literal source text on `expr`'s own line -- used as
    the provenance `quote` (check 4 requires the quote to occur verbatim at file:line). For a
    plain Constant that is the whole string; for a JoinedStr it is the longest static (non-{})
    fragment, since the interpolated parts obviously do not appear verbatim in the source."""
    if isinstance(expr, ast.Constant):
        return expr.value.strip()
    if isinstance(expr, ast.JoinedStr):
        fragments = [
            v.value.strip() for v in expr.values if isinstance(v, ast.Constant) and isinstance(v.value, str) and v.value.strip()
        ]
        return max(fragments, key=len) if fragments else ""
    return ""


def _literal_lines(func: ast.AST, source_text: str) -> list[tuple[int, str, str, str]]:
    """(line, clause_text, kind, quote) for each candidate tool_return-grounded effect: one entry
    per string-producing expression reachable from a `return` value or a `raise` message (one
    entry per f-string, not one per fragment inside it -- see `_string_value_expressions`)."""
    out: list[tuple[int, str, str, str]] = []
    for node in ast.walk(func):
        if isinstance(node, ast.Return):
            kind, target = "return", node.value
        elif isinstance(node, ast.Raise):
            kind, target = "raise", node.exc
        else:
            continue
        for expr in _string_value_expressions(target):
            quote = _longest_literal_fragment(expr)
            if len(quote) < 3 or "\n" in quote:
                continue
            text = _joinedstr_skeleton(expr) if isinstance(expr, ast.JoinedStr) else expr.value.strip()
            if not text:
                continue
            out.append((expr.lineno, text[:200], kind, quote[:150]))
    return out


def _has_raise(func: ast.AST) -> bool:
    return any(isinstance(n, ast.Raise) for n in ast.walk(func))


# ---------------------------------------------------------------------------
# Draft assembly
# ---------------------------------------------------------------------------

_ID_SAFE = re.compile(r"[^a-z0-9_]+")


def _slug(text: str, max_len: int = 40) -> str:
    s = _ID_SAFE.sub("_", text.lower()).strip("_")
    s = re.sub(r"_+", "_", s)
    return (s[:max_len] or "clause").strip("_")


def _draft_signature_args(func: ast.AST, parsed: ParsedDocstring, file_path: str) -> dict:
    out: dict = {}
    a = func.args  # type: ignore[attr-defined]
    for p in list(a.posonlyargs) + list(a.args) + list(a.kwonlyargs):
        if p.arg in ("self", "cls"):
            continue
        type_text = "Any"
        if p.annotation is not None:
            try:
                type_text = ast.unparse(p.annotation)
            except Exception:
                type_text = "Any"
        entry: dict = {"type": type_text, "effective": True}
        if p.arg in parsed.params:
            lineno, desc = parsed.params[p.arg]
            if desc:
                entry["provenance"] = {
                    "surface": "docstring",
                    "file": file_path,
                    "line": lineno,
                    "quote": desc[:150],
                }
        out[p.arg] = entry
    return out


def draft_contract(
    *,
    source_text: str,
    file_path: str,
    qualname: str,
    tool_name: Optional[str] = None,
    benchmark: str,
    commit: str,
) -> dict:
    """Build one schema-valid draft `Contract` dict for the function named `qualname` in
    `source_text`. Raises ValueError if the function cannot be located."""
    tree = ast.parse(source_text)
    source_lines = source_text.splitlines()
    func = _find_function(tree, qualname)
    tool_name = tool_name or qualname.rsplit(".", 1)[-1]

    doc_lines = _docstring_raw_lines(func, source_lines)
    parsed = parse_docstring(doc_lines)

    decorator_line = func.decorator_list[0].lineno if getattr(func, "decorator_list", None) else func.lineno
    source_ref: dict = {
        "file": file_path,
        "start_line": decorator_line,
        "end_line": getattr(func, "end_lineno", func.lineno),
    }
    if getattr(func, "decorator_list", None):
        source_ref["note"] = "start_line is the decorator line; the decorator is itself part of the declared contract."

    preconditions = []
    seen_pre_ids: set = set()

    def add_precondition(lineno: int, text: str, quote: str, note_suffix: str = "") -> None:
        cid = f"pre.{_slug(text)}_draft"
        if cid in seen_pre_ids:
            cid = f"{cid}_{len(seen_pre_ids)}"
        seen_pre_ids.add(cid)
        preconditions.append(
            {
                "id": cid,
                "text": text + note_suffix,
                "predicate": "True",  # placeholder -- a human must author the real predicate
                "provenance": {"surface": "docstring", "file": file_path, "line": lineno, "quote": quote},
                "inferred": True,
            }
        )

    for lineno, phrase in parsed.checks:
        add_precondition(lineno, phrase, phrase)
    for lineno, exc_type, desc in parsed.raises:
        text = desc or f"raises {exc_type}"
        add_precondition(lineno, text, desc or exc_type, note_suffix=f" (raises {exc_type})")

    effects = []
    seen_eff_ids: set = set()

    def add_effect(lineno: int, text: str, quote: str, surface: str) -> None:
        cid = f"eff.{_slug(text)}_draft"
        if cid in seen_eff_ids:
            cid = f"{cid}_{len(seen_eff_ids)}"
        seen_eff_ids.add(cid)
        effects.append(
            {
                "id": cid,
                "text": text,
                "predicate": "True",  # placeholder -- a human must author the real predicate
                "provenance": {"surface": surface, "file": file_path, "line": lineno, "quote": quote},
                "inferred": True,
            }
        )

    for lineno, phrase in parsed.logic:
        add_effect(lineno, phrase, phrase, "docstring")
    for lineno, sentence in parsed.summary:
        add_effect(lineno, sentence, sentence, "docstring")

    # Body-derived candidates: string literals reachable from `return`/`raise`, correctly tiered.
    for lineno, text, kind, quote in _literal_lines(func, source_text):
        surface = _classify_body_quote(source_text, lineno)
        label = "return value" if kind == "return" else "raise message"
        add_effect(lineno, f"[{label}] {text}", quote, surface)

    contract: dict = {
        "contract_version": "1.0",
        "tool": tool_name,
        "benchmark": benchmark,
        "commit": commit,
        "source": source_ref,
        "signature": {"args": _draft_signature_args(func, parsed, file_path)},
        "notes": (
            "AUTO-DRAFTED by static_check/extract.py -- NOT a finding, NOT headline-eligible. "
            "Every clause below is inferred:true and id-suffixed _draft, the two schema-native "
            "markers headline_tier() (core/model.py) always resolves to INFERRED regardless of "
            "provenance surface. Every predicate is the placeholder literal True and MUST be "
            "replaced with a real predicate by a human annotator before this contract is used for "
            "anything. Any tool_return-tiered clause below must still be re-checked by "
            "spec/validate.py check 8 before it is trusted -- this extractor reuses check 8's own "
            "classifier, but a human must confirm the drafted 'text' actually says what the "
            "predicate the human writes will assert."
        ),
    }
    if preconditions:
        contract["preconditions"] = preconditions
    if effects:
        contract["effects"] = effects

    if _has_raise(func):
        contract["success_signal"] = {
            "predicate": "'error' not in result",
            "biconditional": False,  # never auto-set true -- ARCHITECTURE-FINAL.md sec 3.4 requires
            #                          a human-authored justification + provenance for biconditional
        }

    return contract


def _to_yaml_scalar(v) -> str:
    import yaml

    return yaml.safe_dump(v, sort_keys=False, default_flow_style=False, allow_unicode=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", help="path to the source file (relative path is also used as source.file)")
    ap.add_argument("qualname", help="function name, or ClassName.method_name")
    ap.add_argument("--benchmark", required=True)
    ap.add_argument("--commit", required=True)
    ap.add_argument("--tool-name", default=None, help="defaults to the last component of qualname")
    ap.add_argument("--source-file", default=None, help="repo-relative path to record in source.file (defaults to <file>)")
    ap.add_argument("-o", "--output", default=None, help="write YAML here instead of stdout")
    args = ap.parse_args(argv)

    text = Path(args.file).read_text(encoding="utf-8")
    contract = draft_contract(
        source_text=text,
        file_path=args.source_file or args.file,
        qualname=args.qualname,
        tool_name=args.tool_name,
        benchmark=args.benchmark,
        commit=args.commit,
    )
    rendered = _to_yaml_scalar(contract)
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
