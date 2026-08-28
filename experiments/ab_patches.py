"""One-hunk patches for the agent-impact experiment (CLAUDE.md sec "Build the agent-impact
experiment", requirement 5). Two patches, both tau2-bench, both restoring only the
advertised-but-unenforced semantics FINDINGS-VERIFIED.md documents:

  - telecom refuel_data   (Finding 2, Unenforced Precondition): uncomment tools.py:629-630.
  - airline cancel_reservation (Finding 3, Partial Effect): add the seat release at
    tools.py:366, mirroring book_reservation's own decrement (tools.py:314-315) in reverse.

MedAgentBench gets no patch here (FINDINGS-VERIFIED.md Finding 4 -- the grader reads the
transcript, not FHIR state, so a patch would be invisible to it; ARCHITECTURE-FINAL.md sec 6
already routes the A/B to tau2 for exactly this reason).

The diff files under experiments/patches/ are the authoritative, human-auditable record of each
patch -- one hunk, minimal, restoring only the docstring's own advertised precondition/effect.
This module makes them load-bearing rather than decorative: `patched_function_source()` applies
the diff text to the REAL pinned source (.tau2-src-c3398666, the same durable checkout
adapters/tau2.py's worker imports from) and extracts the one function that changed, so the
function body actually installed via Adapter.patch_tool is mechanically derived from the diff
file on disk, not a hand-copied duplicate that could drift from it.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PATCHES_DIR = Path(__file__).resolve().parent / "patches"
TAU2_SRC = PROJECT_ROOT / ".tau2-src-c3398666" / "src" / "tau2"

__all__ = [
    "Hunk",
    "parse_unified_diff",
    "apply_unified_diff",
    "PatchSpec",
    "TAU2_PATCHES",
    "patched_module_source",
    "patched_function_source",
]


# ============================================================================================
# Minimal unified-diff parser/applier. No third-party dependency, no shelling out to `patch`
# (not guaranteed present on Windows, ARCHITECTURE-FINAL.md sec 5's own operational-notes
# section is full of exactly this kind of Windows gotcha). Deliberately narrow: single-file
# diffs, '---'/'+++'/'@@' headers, no fuzz -- context and removed lines must match the original
# byte-for-byte, which is what "one-hunk and minimal" (CLAUDE.md) buys us: if the pinned
# checkout ever drifted from what FINDINGS-VERIFIED.md quotes, this raises instead of silently
# patching the wrong lines.
# ============================================================================================


class Hunk(NamedTuple):
    old_start: int  # 1-based line number in the original file where this hunk begins
    old_len: int
    new_start: int
    new_len: int
    lines: list  # list[(tag, text)] where tag in (' ', '-', '+'), text WITHOUT trailing \n


_HUNK_HEADER = re.compile(r"^@@ -(\d+),(\d+) \+(\d+),(\d+) @@")


def parse_unified_diff(diff_text: str) -> list[Hunk]:
    """Parse a unified diff's hunks. Ignores the '---'/'+++' file-header lines (this module
    always knows which file it's patching from PatchSpec.module_path, so the header text is
    documentation only, never trusted for path resolution)."""
    lines = diff_text.splitlines()
    hunks: list[Hunk] = []
    i = 0
    while i < len(lines):
        m = _HUNK_HEADER.match(lines[i])
        if not m:
            i += 1
            continue
        old_start, old_len, new_start, new_len = (int(x) for x in m.groups())
        i += 1
        body: list = []
        while i < len(lines) and not lines[i].startswith("@@") and not lines[i].startswith("--- "):
            line = lines[i]
            if line == "":
                # A fully blank line in the diff file (no leading ' ') is a blank CONTEXT line
                # that lost its marker to editor trailing-whitespace stripping -- treat it as
                # ' ' with empty text rather than erroring, since that is the only sane reading.
                body.append((" ", ""))
            else:
                tag, text = line[0], line[1:]
                if tag not in (" ", "-", "+"):
                    raise ValueError(f"unrecognized diff line (expected ' '/'-'/'+' prefix): {line!r}")
                body.append((tag, text))
            i += 1
        hunks.append(Hunk(old_start, old_len, new_start, new_len, body))
    if not hunks:
        raise ValueError("no @@ hunk header found in diff text")
    return hunks


def apply_unified_diff(original: str, diff_text: str) -> str:
    """Apply every hunk in `diff_text` to `original`, returning the patched text. Raises
    ValueError (not a silent best-effort patch) the instant a context or removed line does not
    match the original exactly -- this is deliberately strict, per this module's docstring."""
    hunks = parse_unified_diff(diff_text)
    orig_lines = original.split("\n")
    out: list = []
    cursor = 0  # 0-based index into orig_lines, "already emitted up to here"
    for hunk in hunks:
        start = hunk.old_start - 1
        if start < cursor:
            raise ValueError(f"hunks out of order or overlapping at line {hunk.old_start}")
        out.extend(orig_lines[cursor:start])
        cursor = start
        for tag, text in hunk.lines:
            if tag in (" ", "-"):
                if cursor >= len(orig_lines):
                    raise ValueError(f"hunk expects a line at position {cursor + 1} but the file ended")
                if orig_lines[cursor] != text:
                    raise ValueError(
                        f"diff context/removal mismatch at original line {cursor + 1}: "
                        f"file has {orig_lines[cursor]!r}, diff expects {text!r}"
                    )
                cursor += 1
            if tag in (" ", "+"):
                out.append(text)
    out.extend(orig_lines[cursor:])
    return "\n".join(out)


# ============================================================================================
# The two tau2 patches.
# ============================================================================================


@dataclass(frozen=True)
class PatchSpec:
    finding_id: str  # "F2" | "F3", matching FINDINGS-VERIFIED.md / experiments/analysis_plan.md
    domain: str
    tool: str
    module_path: Path  # absolute path into .tau2-src-c3398666, the pinned checkout the worker imports from
    diff_path: Path
    finding_citation: str


TAU2_PATCHES: dict = {
    "F2": PatchSpec(
        finding_id="F2",
        domain="telecom",
        tool="refuel_data",
        module_path=TAU2_SRC / "domains" / "telecom" / "tools.py",
        diff_path=PATCHES_DIR / "telecom_refuel_data.diff",
        finding_citation="FINDINGS-VERIFIED.md Finding 2",
    ),
    "F3": PatchSpec(
        finding_id="F3",
        domain="airline",
        tool="cancel_reservation",
        module_path=TAU2_SRC / "domains" / "airline" / "tools.py",
        diff_path=PATCHES_DIR / "airline_cancel_reservation.diff",
        finding_citation="FINDINGS-VERIFIED.md Finding 3",
    ),
}


def patched_module_source(spec: PatchSpec) -> str:
    """Read the pinned module source and apply the diff. Returns the FULL patched module text
    (not yet narrowed to one function)."""
    original = spec.module_path.read_text(encoding="utf-8")
    diff_text = spec.diff_path.read_text(encoding="utf-8")
    return apply_unified_diff(original, diff_text)


def patched_function_source(spec: PatchSpec) -> str:
    """The patched, decorator-free source of `spec.tool` alone -- exactly the string
    Adapter.patch_tool expects (adapters/base.py docstring; mirrors
    mutation/adapter_invoke.py's build_function_patch_source, which does the same
    parse -> transform -> strip-decorators -> unparse pipeline for a mutation operator instead
    of a diff)."""
    patched_module = patched_module_source(spec)
    tree = ast.parse(patched_module)
    fn = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == spec.tool:
            if fn is not None:
                raise ValueError(f"{spec.tool!r} is ambiguous in {spec.module_path}")
            fn = node
    if fn is None:
        raise ValueError(f"no function {spec.tool!r} found in patched {spec.module_path}")
    fn.decorator_list = []
    ast.fix_missing_locations(fn)
    return ast.unparse(fn)
