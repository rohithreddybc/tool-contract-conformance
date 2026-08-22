#!/usr/bin/env python
"""Contract linter -- the eight checks in spec/PREDICATE-GRAMMAR.md sec 6.

    python spec/validate.py spec/contracts/**/*.yaml [--repo-root REPO] [--state-schema FILE]

Exit code is non-zero if any check fails. Check 4 (provenance) and check 8 (agent-visibility)
are SKIPPED per file if --repo-root is not given or the repo is unavailable at that path,
rather than passing silently. Check 5 (synthetic evaluation) is SKIPPED if --state-schema is
not given. Skips print an informational line but do not affect the exit code.

One line per failure: <file>:<clause_id>: <check> — <message>
"""
from __future__ import annotations

import argparse
import ast
import glob
import json
import subprocess
import sys
from pathlib import Path

import jsonschema
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.frame import FrameSyntaxError, parse_pattern  # noqa: E402
from core.predicates import PredicateError, compile_predicate, evaluate  # noqa: E402

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.json"

# Heuristic word list for check 6's second half: a provenance quote for advertised_deferred
# must itself say the effect is deferred. This is deliberately a short, auditable list rather
# than free-text NLP -- see spec/GRAMMAR-GAPS.md if it ever needs extending.
DEFERRAL_WORDS = ("defer", "async", "lag", "later", "eventually", "pending", "not implemented", "not applied")

PREFIX_BY_KIND = {"preconditions": "pre.", "effects": "eff.", "invariants": "inv.", "frame": "frame."}


class Reporter:
    def __init__(self):
        self.failures: list[str] = []
        self.skips: list[str] = []

    def fail(self, file: str, clause_id: str, check: str, message: str) -> None:
        self.failures.append(f"{file}:{clause_id}: {check} — {message}")

    def skip(self, file: str, check: str, message: str) -> None:
        self.skips.append(f"{file}: {check} — SKIPPED: {message}")


def expand_args(patterns: list[str]) -> list[str]:
    """Accept literal paths or glob patterns (recursive **, for shells that don't expand it)."""
    files: list[str] = []
    for pattern in patterns:
        p = Path(pattern)
        if p.is_file():
            files.append(str(p))
            continue
        files.extend(glob.glob(pattern, recursive=True))
    seen = set()
    out = []
    for f in files:
        norm = str(Path(f))
        if norm not in seen:
            seen.add(norm)
            out.append(norm)
    return out


def _iter_clauses(doc: dict):
    """Yield (kind, clause_dict) for every clause-bearing array in the document."""
    for kind in ("preconditions", "effects", "invariants", "frame"):
        for c in doc.get(kind, []):
            yield kind, c


# ---------------------------------------------------------------------------
# Check 1: document validates against spec/schema.json
# ---------------------------------------------------------------------------


def check1_schema(path: str, doc: dict, schema: dict, rep: Reporter) -> bool:
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(doc), key=lambda e: [str(p) for p in e.path])
    for e in errors:
        loc = "/".join(str(p) for p in e.path) or "(document)"
        rep.fail(path, "(document)", "check1_schema", f"{loc}: {e.message}")
    return not errors


# ---------------------------------------------------------------------------
# Check 2: every predicate parses, whitelisted-only, no free names
# ---------------------------------------------------------------------------


def check2_predicates(path: str, doc: dict, rep: Reporter) -> bool:
    ok = True

    def try_compile(clause_id: str, src: str) -> None:
        nonlocal ok
        try:
            compile_predicate(src)
        except PredicateError as e:
            ok = False
            rep.fail(path, clause_id, "check2_predicate", str(e))

    for kind, c in _iter_clauses(doc):
        if kind == "frame":
            continue
        try_compile(c.get("id", kind), c["predicate"])

    ss = doc.get("success_signal")
    if ss:
        try_compile("success_signal", ss["predicate"])

    reset = doc.get("reset")
    if reset:
        try_compile("reset", reset["predicate"])

    return ok


# ---------------------------------------------------------------------------
# Check 3: every frame path parses under sec 3
# ---------------------------------------------------------------------------


def check3_frame_paths(path: str, doc: dict, rep: Reporter) -> bool:
    ok = True
    for c in doc.get("frame", []):
        try:
            parse_pattern(c["path"])
        except FrameSyntaxError as e:
            ok = False
            rep.fail(path, c.get("id", "frame"), "check3_frame_path", str(e))
    return ok


# ---------------------------------------------------------------------------
# Check 4: every provenance quote occurs at its cited file:line, in the pinned commit
# ---------------------------------------------------------------------------

_git_show_cache: dict[tuple, list[str] | None] = {}


def _git_show(repo_root: str, commit: str, file: str) -> list[str] | None:
    key = (repo_root, commit, file)
    if key in _git_show_cache:
        return _git_show_cache[key]
    try:
        out = subprocess.run(
            ["git", "-C", repo_root, "show", f"{commit}:{file}"],
            capture_output=True, text=True, timeout=30,
        )
    except OSError:
        _git_show_cache[key] = None
        return None
    lines = out.stdout.splitlines() if out.returncode == 0 else None
    _git_show_cache[key] = lines
    return lines


def _repo_available(repo_root: str) -> bool:
    try:
        out = subprocess.run(
            ["git", "-C", repo_root, "rev-parse", "--git-dir"],
            capture_output=True, text=True, timeout=10,
        )
    except OSError:
        return False
    return out.returncode == 0


def check4_provenance(path: str, doc: dict, rep: Reporter, repo_root: str | None) -> bool:
    if not repo_root:
        rep.skip(path, "check4_provenance", "no --repo-root supplied")
        return True
    if not _repo_available(repo_root):
        rep.skip(path, "check4_provenance", f"repo unavailable at {repo_root}")
        return True

    commit = doc.get("commit")
    ok = True

    def check_prov(clause_id: str, prov: dict | None) -> None:
        nonlocal ok
        if not prov:
            return
        file, line, quote = prov.get("file"), prov.get("line"), prov.get("quote")
        if not file or not line:
            return
        lines = _git_show(repo_root, commit, file)
        if lines is None:
            ok = False
            rep.fail(path, clause_id, "check4_provenance", f"{file} not found at commit {commit}")
            return
        if line < 1 or line > len(lines):
            ok = False
            rep.fail(path, clause_id, "check4_provenance", f"{file}:{line} out of range at commit {commit}")
            return
        if quote not in lines[line - 1]:
            ok = False
            rep.fail(path, clause_id, "check4_provenance", f"quote {quote!r} not found at {file}:{line}")

    for kind, c in _iter_clauses(doc):
        check_prov(c.get("id", kind), c.get("provenance"))
    ss = doc.get("success_signal")
    if ss:
        check_prov("success_signal", ss.get("provenance"))
    reset = doc.get("reset")
    if reset:
        check_prov("reset", reset.get("provenance"))
    opv = doc.get("on_precondition_violation")
    if opv:
        check_prov("on_precondition_violation", opv.get("provenance"))
    for name, a in doc.get("signature", {}).get("args", {}).items():
        check_prov(f"signature.{name}", a.get("provenance"))

    return ok


# ---------------------------------------------------------------------------
# Check 5: every predicate evaluates without error against a synthetic snapshot
# ---------------------------------------------------------------------------

_SYNTH_BY_TYPE = {"str": "x", "int": 1, "float": 1.0, "bool": True}


def check5_synthetic_eval(path: str, doc: dict, rep: Reporter, state_schema_path: str | None) -> bool:
    if not state_schema_path:
        rep.skip(path, "check5_synthetic_eval", "no --state-schema supplied")
        return True

    with open(state_schema_path, "r", encoding="utf-8") as fh:
        spec_doc = json.load(fh)

    # --state-schema is a literal synthetic snapshot (optionally wrapped as
    # {"snapshot": ..., "result": ...} to also supply a synthetic tool return); it is not a
    # JSON-Schema meta-schema. See spec/GRAMMAR-GAPS.md for why.
    if isinstance(spec_doc, dict) and "snapshot" in spec_doc:
        snapshot = spec_doc["snapshot"]
        result = spec_doc.get("result", {})
    else:
        snapshot = spec_doc
        result = {}

    args = {
        name: _SYNTH_BY_TYPE.get(a.get("type"))
        for name, a in doc.get("signature", {}).get("args", {}).items()
    }

    ok = True

    def try_eval(clause_id: str, src: str) -> None:
        nonlocal ok
        try:
            compiled = compile_predicate(src)
            evaluate(compiled, snapshot, snapshot, args, result)
        except PredicateError as e:
            ok = False
            rep.fail(path, clause_id, "check5_synthetic_eval", f"raised against synthetic snapshot: {e}")

    for kind, c in _iter_clauses(doc):
        if kind == "frame":
            continue
        try_eval(c.get("id", kind), c["predicate"])
    ss = doc.get("success_signal")
    if ss:
        try_eval("success_signal", ss["predicate"])

    return ok


# ---------------------------------------------------------------------------
# Check 6: biconditional and advertised_deferred carry the provenance they require
# ---------------------------------------------------------------------------


def check6_biconditional_deferred(path: str, doc: dict, rep: Reporter) -> bool:
    ok = True

    ss = doc.get("success_signal")
    if ss and ss.get("biconditional"):
        if not ss.get("justification"):
            ok = False
            rep.fail(path, "success_signal", "check6_biconditional", "biconditional:true with no justification")
        if not ss.get("provenance"):
            ok = False
            rep.fail(path, "success_signal", "check6_biconditional", "biconditional:true with no provenance")

    for c in doc.get("effects", []):
        if not c.get("advertised_deferred"):
            continue
        cid = c.get("id", "effects")
        prov = c.get("provenance")
        if not prov:
            ok = False
            rep.fail(path, cid, "check6_deferred", "advertised_deferred:true with no provenance")
            continue
        quote = (prov.get("quote") or "").lower()
        if not any(w in quote for w in DEFERRAL_WORDS):
            ok = False
            rep.fail(path, cid, "check6_deferred", f"provenance quote does not mention the deferral: {prov.get('quote')!r}")

    return ok


# ---------------------------------------------------------------------------
# Check 7: clause ids are unique and match their kind prefix
# ---------------------------------------------------------------------------


def check7_clause_ids(path: str, doc: dict, rep: Reporter) -> bool:
    ok = True
    seen: dict[str, str] = {}
    for kind, c in _iter_clauses(doc):
        cid = c.get("id", "")
        expected = PREFIX_BY_KIND[kind]
        if not cid.startswith(expected):
            ok = False
            rep.fail(path, cid or "(missing id)", "check7_clause_ids", f"{kind} clause id must start with {expected!r}")
        if cid in seen:
            ok = False
            rep.fail(path, cid, "check7_clause_ids", f"duplicate clause id, also used under {seen[cid]}")
        else:
            seen[cid] = kind
    return ok


# ---------------------------------------------------------------------------
# Check 8: agent-visibility of the claimed surface (PREDICATE-GRAMMAR.md sec 6.8)
#
# check4 already proves the quote occurs verbatim at the cited file:line. That is necessary
# but not sufficient -- a maintainer log line satisfies check4 trivially while never reaching
# the agent. Check 8 classifies *what kind of statement* the cited line actually is, for the
# two surfaces where "occurs at this location" and "the agent sees this" can diverge:
#
#   tool_return      -- must be inside a `return` expression or the message of a `raise`,
#                        never inside a logger.* call, a `print`, or a bare comment.
#   prompt_template   -- weaker test: the cited file must not plausibly be a .py module living
#                        inside the tool package (a WARN/skip is emitted, not a failure, when
#                        reachability cannot be determined either way).
#
# Every other surface (docstring, schema, readme, external_standard, maintainer_annotation) is
# not tested here -- their agent-visibility is structural (docstring text ships with the tool
# schema; maintainer_annotation is never claimed to be agent-visible in the first place) and is
# not the failure mode check 8 exists to catch.
# ---------------------------------------------------------------------------

_LOGGER_METHODS = frozenset({"debug", "info", "warning", "warn", "error", "exception", "critical", "log"})


def _dotted_call_name(call: ast.Call) -> str:
    """Best-effort dotted name for a Call's callee: 'logger.warning', 'self.logger.warning',
    'print'. Falls back to '<expr>' for a callee that is not a plain dotted name (e.g. the
    result of another call), which is enough to name the enclosing statement as "not a return
    or raise" even when the callee itself can't be rendered exactly."""
    parts: list[str] = []
    node = call.func
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    else:
        parts.append("<expr>")
    return ".".join(reversed(parts))


def _is_logger_call(dotted: str) -> bool:
    parts = dotted.split(".")
    if len(parts) < 2:
        return False
    if parts[-1] not in _LOGGER_METHODS:
        return False
    return any("log" in p.lower() for p in parts[:-1])


def _enclosing_statement(tree: ast.Module, line: int) -> ast.stmt | None:
    """The smallest ast.stmt whose source-line span contains `line`."""
    best: ast.stmt | None = None
    best_span: int | None = None
    for node in ast.walk(tree):
        if not isinstance(node, ast.stmt):
            continue
        start = getattr(node, "lineno", None)
        end = getattr(node, "end_lineno", start)
        if start is None or end is None or not (start <= line <= end):
            continue
        span = end - start
        if best is None or span < best_span:
            best, best_span = node, span
    return best


def _classify_tool_return(source: str, line: int) -> tuple[bool, str]:
    """(passes, description) for a tool_return quote cited at `line` in `source`. `description`
    names the enclosing construct, for use in both pass and fail messages."""
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return False, f"a file that does not parse as Python ({e})"

    # A comment or blank line is never itself an AST node -- check the raw line text before
    # falling back to AST containment, or a comment sitting inside a multi-line statement's
    # span (e.g. inside a function body) would be misclassified as that enclosing statement.
    src_lines = source.splitlines()
    raw = src_lines[line - 1].strip() if 0 < line <= len(src_lines) else ""
    if raw.startswith("#"):
        return False, "a comment"
    if not raw:
        return False, "a blank line"

    stmt = _enclosing_statement(tree, line)
    if stmt is None:
        return False, "no enclosing executable statement"

    if isinstance(stmt, ast.Return):
        return True, "a return expression"
    if isinstance(stmt, ast.Raise):
        return True, "the message of a raise"
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
        dotted = _dotted_call_name(stmt.value)
        if _is_logger_call(dotted):
            return False, f"a {dotted} call"
        if dotted == "print":
            return False, "a print call"
        return False, f"a {dotted} call"
    return False, f"a {type(stmt).__name__} statement"


def _prompt_template_reachability(file: str) -> tuple[bool | None, str]:
    """Weak reachability test for prompt_template provenance.

    True  -- the cited file is not a .py module, so it plausibly IS agent-visible text (a
              prompt/template asset rather than implementation code).
    False -- the cited file is a .py module that lives under a tool implementation package
              (named tools.py, matching the source most contracts cite for the tool itself);
              treated as not agent-visible.
    None  -- a .py file elsewhere. Reachability genuinely cannot be determined from the path
              alone (it might build and emit a prompt string). Accepted with a WARN, not failed.
    """
    normalized = file.replace("\\", "/")
    if not normalized.endswith(".py"):
        return True, "cited file is not a .py module"
    if normalized.endswith("tools.py") or "/tools.py" in normalized:
        return False, "cited file is a .py module under the tool package"
    return None, "cited file is a .py module; reachability could not be determined"


def check8_agent_visibility(path: str, doc: dict, rep: Reporter, repo_root: str | None) -> bool:
    if not repo_root:
        rep.skip(path, "check8_agent_visibility", "no --repo-root supplied")
        return True
    if not _repo_available(repo_root):
        rep.skip(path, "check8_agent_visibility", f"repo unavailable at {repo_root}")
        return True

    commit = doc.get("commit")
    ok = True

    def check_prov(clause_id: str, prov: dict | None) -> None:
        nonlocal ok
        if not prov:
            return
        surface = prov.get("surface")
        if surface not in ("tool_return", "prompt_template"):
            return  # not this check's concern -- see module comment above
        file, line = prov.get("file"), prov.get("line")
        if not file or not line:
            return

        fname = Path(file).name

        if surface == "tool_return":
            lines = _git_show(repo_root, commit, file)
            if lines is None:
                return  # check4 already reports the missing file; don't double-report here
            source = "\n".join(lines)
            passes, desc = _classify_tool_return(source, line)
            if not passes:
                ok = False
                rep.fail(
                    path, clause_id, "check8_agent_visibility",
                    f"tool_return quote at {fname}:{line} occurs in {desc}, not a return or "
                    "raise — re-tier to maintainer_annotation or mark inferred",
                )
        else:  # prompt_template
            reachable, desc = _prompt_template_reachability(file)
            if reachable is False:
                ok = False
                rep.fail(
                    path, clause_id, "check8_agent_visibility",
                    f"prompt_template quote at {fname}:{line}: {desc} — re-tier to "
                    "maintainer_annotation or mark inferred",
                )
            elif reachable is None:
                rep.skip(
                    path, "check8_agent_visibility",
                    f"{clause_id}: prompt_template reachability at {fname}:{line} could not be "
                    f"determined ({desc}) — WARN, accepted",
                )

    for kind, c in _iter_clauses(doc):
        check_prov(c.get("id", kind), c.get("provenance"))
    ss = doc.get("success_signal")
    if ss:
        check_prov("success_signal", ss.get("provenance"))
    reset = doc.get("reset")
    if reset:
        check_prov("reset", reset.get("provenance"))
    opv = doc.get("on_precondition_violation")
    if opv:
        check_prov("on_precondition_violation", opv.get("provenance"))
    for name, a in doc.get("signature", {}).get("args", {}).items():
        check_prov(f"signature.{name}", a.get("provenance"))

    return ok


# ---------------------------------------------------------------------------


def validate_file(path: str, schema: dict, repo_root: str | None, state_schema_path: str | None, rep: Reporter) -> None:
    with open(path, "r", encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)

    check1_schema(path, doc, schema, rep)
    check2_predicates(path, doc, rep)
    check3_frame_paths(path, doc, rep)
    check4_provenance(path, doc, rep, repo_root)
    check5_synthetic_eval(path, doc, rep, state_schema_path)
    check6_biconditional_deferred(path, doc, rep)
    check7_clause_ids(path, doc, rep)
    check8_agent_visibility(path, doc, rep, repo_root)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Validate tool contracts against PREDICATE-GRAMMAR.md sec 6.")
    ap.add_argument("files", nargs="+")
    ap.add_argument("--repo-root", default=None)
    ap.add_argument("--state-schema", default=None)
    args = ap.parse_args(argv)

    files = expand_args(args.files)
    if not files:
        print("no contract files matched", file=sys.stderr)
        return 2

    with open(SCHEMA_PATH, "r", encoding="utf-8") as fh:
        schema = json.load(fh)

    rep = Reporter()
    for f in files:
        validate_file(f, schema, args.repo_root, args.state_schema, rep)

    for line in rep.skips:
        print(line)
    for line in rep.failures:
        print(line)

    if rep.failures:
        print(f"\n{len(rep.failures)} failure(s) across {len(files)} file(s)", file=sys.stderr)
        return 1

    print(f"all checks passed ({len(files)} file(s), {len(rep.skips)} skipped check(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
