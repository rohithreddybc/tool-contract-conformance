#!/usr/bin/env python
"""Contract-coverage metric -- ARCHITECTURE-FINAL.md sec 5 ("Contract-coverage metric") and
experiments/detector_analysis_plan.md sec 6. Per tool:

  1. The fraction of advertised-surface sentences operationalized into clauses.
  2. The fraction of state-writing statements covered by some effect or frame clause.
  3. Whether `success_signal.biconditional: true` was adopted, and with what justification.

Sentence unit. experiments/annotation_protocol.md sec 2 fixes the *clause* segmentation rule:

    1. One clause per advertised-surface sentence that asserts a checkable property. A sentence
       asserting two independent properties yields two clauses.
    2. A sentence asserting a property over a collection yields one clause with a bounded
       comprehension, not one clause per element.
    3. Prose that is not checkable yields no clause and is recorded as uncovered.

...and its own "Unit reconciliation" paragraph states the relationship this module must honor:
"spec/coverage.py reports the fraction of advertised-surface sentences operationalized. That
denominator and this protocol's clause unit are related by rule 1: a sentence maps to zero, one,
or several clauses." This module's sentence extraction therefore reuses
static_check/extract.py's `parse_docstring` unchanged -- the same "Checks:"/"Logic:" comma-split
that operationalizes rule 1 when drafting a clause is used here to count the denominator, so the
two numbers cannot silently diverge (the reuse *is* the reconciliation, not a second
implementation of the same rule that could drift from the first). No conflict between the two
documents was found; see this build's final report for the explicit check.

Because coverage is computed against ALREADY-AUTHORED, human-reviewed contracts (not this
extractor's own drafts), "operationalized" is tested structurally: an extracted sentence at
(file, line) counts as covered iff some clause anywhere in the contract -- precondition, effect,
frame, invariant, on_precondition_violation, reset, or a per-argument signature provenance --
cites that same (file, line). This is a location match, not a semantic one; it undercounts a
clause that paraphrases an advertised sentence without citing its exact line, and that
undercounting is a known, stated limitation (see `LIMITATIONS` below), not a hidden one.

State-write coverage is similarly a coarse static approximation: a state-writing statement (an
attribute/subscript assignment, augmented assignment, or mutating-method call) is "covered" if
its field-name identifier appears anywhere in the text of some effect predicate or frame path.
This is a textual heuristic, not a semantic one -- it does not check that the clause actually
constrains that write correctly, only that some clause mentions the field at all.

CLI:
    python spec/coverage.py <contract.yaml> [<contract.yaml> ...] --repo-root REPO [--json]
"""
from __future__ import annotations

import argparse
import ast
import glob
import json
import re
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.model import Contract, Provenance  # noqa: E402
from static_check.checks import _iter_functions  # noqa: E402 -- reuse the class/module function walk
from static_check.extract import _docstring_raw_lines, parse_docstring  # noqa: E402 -- reuse, do not re-split sentences a second way

__all__ = ["sentence_coverage", "state_write_coverage", "biconditional_adoption", "coverage_report", "main"]

LIMITATIONS = (
    "Sentence coverage is a (file, line) provenance-citation match, not a semantic check: a "
    "clause that paraphrases an advertised sentence without citing its exact source line is "
    "undercounted as uncovered. State-write coverage is a textual identifier match against "
    "effect predicates and frame paths: a clause that mentions a field name is counted as "
    "covering every write to that field, even if the predicate does not actually constrain that "
    "particular write correctly. Both are static approximations, reported as such."
)

_MUTATING_METHOD_NAMES = frozenset(
    {"append", "extend", "remove", "pop", "update", "insert", "clear", "add", "discard", "setdefault"}
)
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


# ---------------------------------------------------------------------------
# Locating the tool's AST node from a Contract (no qualname stored on Contract itself --
# matched by bare tool name + the source range the contract itself cites)
# ---------------------------------------------------------------------------


def _locate_function(tree: ast.Module, contract: Contract) -> ast.AST:
    end_line = contract.source.end_line
    candidates = [func for _q, _cls, func in _iter_functions(tree) if func.name == contract.tool]
    for func in candidates:
        if getattr(func, "end_lineno", func.lineno) == end_line:
            return func
    if candidates:
        return candidates[0]
    raise ValueError(f"could not locate tool {contract.tool!r} (source.end_line={end_line}) in the given source")


# ---------------------------------------------------------------------------
# Sentence coverage
# ---------------------------------------------------------------------------


def _all_provenance_lines(contract: Contract) -> set[tuple[str, int]]:
    """Every (file, line) cited anywhere in the contract's provenance."""
    out: set[tuple[str, int]] = set()

    def add(prov: Optional[Provenance]) -> None:
        if prov is not None and prov.file and prov.line:
            out.add((prov.file, prov.line))

    for c in list(contract.preconditions) + list(contract.effects) + list(contract.invariants) + list(contract.frame):
        add(c.provenance)
    if contract.success_signal is not None:
        add(contract.success_signal.provenance)
    if contract.on_precondition_violation is not None:
        add(contract.on_precondition_violation.provenance)
    if contract.reset is not None:
        add(contract.reset.provenance)
    for spec in contract.signature.args.values():
        add(spec.provenance)
    return out


def sentence_coverage(contract: Contract, source_text: str) -> dict:
    tree = ast.parse(source_text)
    source_lines = source_text.splitlines()
    func = _locate_function(tree, contract)
    doc_lines = _docstring_raw_lines(func, source_lines)
    parsed = parse_docstring(doc_lines)

    units: list[dict] = []
    for lineno, phrase in parsed.checks:
        units.append({"kind": "checks", "line": lineno, "text": phrase})
    for lineno, phrase in parsed.logic:
        units.append({"kind": "logic", "line": lineno, "text": phrase})
    for lineno, text in parsed.summary:
        units.append({"kind": "summary", "line": lineno, "text": text})
    for lineno, exc_type, desc in parsed.raises:
        units.append({"kind": "raises", "line": lineno, "text": desc or exc_type})

    provenance_lines = _all_provenance_lines(contract)
    file = contract.source.file
    covered = [u for u in units if (file, u["line"]) in provenance_lines]
    uncovered = [u for u in units if (file, u["line"]) not in provenance_lines]

    total = len(units)
    n_covered = len(covered)
    return {
        "tool": contract.tool,
        "sentence_total": total,
        "sentence_operationalized": n_covered,
        "sentence_fraction": (n_covered / total) if total else None,
        "covered": covered,
        "uncovered": uncovered,
    }


# ---------------------------------------------------------------------------
# State-write coverage
# ---------------------------------------------------------------------------


def _rightmost_field(node: ast.AST) -> Optional[str]:
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Subscript):
        return _rightmost_field(node.value)
    return None


def _state_writing_statements(func: ast.AST) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    for node in ast.walk(func):
        if isinstance(node, (ast.Assign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                if isinstance(t, ast.Attribute):
                    out.append((node.lineno, t.attr))
                elif isinstance(t, ast.Subscript):
                    name = _rightmost_field(t.value)
                    if name:
                        out.append((node.lineno, name))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in _MUTATING_METHOD_NAMES:
            name = _rightmost_field(node.func.value)
            if name:
                out.append((node.lineno, name))
    return out


def _referenced_field_names(contract: Contract) -> set[str]:
    names: set[str] = set()
    for e in contract.effects:
        names |= set(_IDENT.findall(e.predicate))
    for f in contract.frame:
        names |= set(_IDENT.findall(f.path))
    return names


def state_write_coverage(contract: Contract, source_text: str) -> dict:
    tree = ast.parse(source_text)
    func = _locate_function(tree, contract)
    writes = _state_writing_statements(func)
    referenced = _referenced_field_names(contract)

    covered = [{"line": ln, "field": f} for ln, f in writes if f in referenced]
    uncovered = [{"line": ln, "field": f} for ln, f in writes if f not in referenced]

    total = len(writes)
    n_covered = len(covered)
    return {
        "tool": contract.tool,
        "state_write_total": total,
        "state_write_covered": n_covered,
        "state_write_fraction": (n_covered / total) if total else None,
        "covered": covered,
        "uncovered": uncovered,
    }


# ---------------------------------------------------------------------------
# Biconditional adoption
# ---------------------------------------------------------------------------


def biconditional_adoption(contract: Contract) -> dict:
    ss = contract.success_signal
    adopted = bool(ss and ss.biconditional)
    return {
        "tool": contract.tool,
        "biconditional": adopted,
        "justification": ss.justification if (ss and adopted) else None,
    }


# ---------------------------------------------------------------------------
# Report assembly / CLI
# ---------------------------------------------------------------------------


def coverage_report(contract_path: str, repo_root: str) -> dict:
    contract = Contract.from_yaml(contract_path)
    source_path = Path(repo_root) / contract.source.file
    source_text = source_path.read_text(encoding="utf-8")
    return {
        "contract": contract_path,
        "tool": contract.tool,
        "benchmark": contract.benchmark,
        "sentence": sentence_coverage(contract, source_text),
        "state_write": state_write_coverage(contract, source_text),
        "biconditional": biconditional_adoption(contract),
    }


def _expand(patterns: list[str]) -> list[str]:
    files: list[str] = []
    for pattern in patterns:
        p = Path(pattern)
        if p.is_file():
            files.append(str(p))
        else:
            files.extend(glob.glob(pattern, recursive=True))
    seen: set[str] = set()
    out: list[str] = []
    for f in files:
        norm = str(Path(f))
        if norm not in seen:
            seen.add(norm)
            out.append(norm)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Contract-coverage metric (ARCHITECTURE-FINAL.md sec 5).")
    ap.add_argument("contracts", nargs="+", help="contract YAML files or glob patterns")
    ap.add_argument("--repo-root", required=True, help="root the contract's source.file is relative to")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    files = _expand(args.contracts)
    if not files:
        print("no contract files matched", file=sys.stderr)
        return 2

    reports = []
    for f in files:
        try:
            reports.append(coverage_report(f, args.repo_root))
        except Exception as e:  # noqa: BLE001 -- report the failure per-file, keep going
            reports.append({"contract": f, "error": str(e)})

    if args.json:
        print(json.dumps({"limitations": LIMITATIONS, "reports": reports}, indent=2))
        return 0

    total_sent, total_sent_cov = 0, 0
    total_sw, total_sw_cov = 0, 0
    n_biconditional = 0
    for r in reports:
        if "error" in r:
            print(f"{r['contract']}: ERROR: {r['error']}")
            continue
        s, w, b = r["sentence"], r["state_write"], r["biconditional"]
        print(
            f"{r['tool']:30s} sentence {s['sentence_operationalized']}/{s['sentence_total']}"
            f"  state-write {w['state_write_covered']}/{w['state_write_total']}"
            f"  biconditional={b['biconditional']}"
        )
        total_sent += s["sentence_total"]
        total_sent_cov += s["sentence_operationalized"]
        total_sw += w["state_write_total"]
        total_sw_cov += w["state_write_covered"]
        n_biconditional += int(b["biconditional"])

    print()
    if total_sent:
        print(f"aggregate sentence coverage:   {total_sent_cov}/{total_sent} ({total_sent_cov / total_sent:.1%})")
    if total_sw:
        print(f"aggregate state-write coverage: {total_sw_cov}/{total_sw} ({total_sw_cov / total_sw:.1%})")
    print(f"biconditional:true adopted by {n_biconditional}/{len(reports)} contract(s)")
    print(f"\nlimitations: {LIMITATIONS}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
