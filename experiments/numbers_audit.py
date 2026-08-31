#!/usr/bin/env python
"""Numbers audit for paper/main.md -- CLAUDE.md's standing rule: "A script parses every numeric
claim in the manuscript and checks it against the generated tables. Run it before every commit
to paper/."

Two incidents motivate every check here, and both are recorded in the project history:

  1. The MedAgentBench Action SR range was drafted as "54.00-71.33%" when four of eleven models
     fall below 54.00 and two score 0.00%. A drafting pass caught it by chance -- this script is
     the mechanical backstop for the next time chance does not intervene (check 4).
  2. Three different headline-finding counts (7, 5, 4) were live in the manuscript at once,
     caught only when the LaTeX build was assembled (check 2).

This script does NOT understand English. It cannot verify a claim with no numeral in it, and it
cannot tell whether an argument is sound. What it can do, mechanically and cheaply, every time:

  1. Extract every numeric claim it can find in paper/main.md -- counts, percentages, intervals,
     line numbers, commit hashes, table references, and [Nk: ...] evidence placeholders -- and
     print what it found, so a human can see nothing was skipped.
  2. Flag the same tracked quantity (e.g. "the headline-eligible cell count") appearing with two
     different values anywhere in the manuscript: prose, the abstract's committed-shape comment
     block, section text, and tables are all in scope.
  3. Cross-check claims that name a generated artifact against that artifact: finding counts and
     headline-eligible cell counts against report/findings.jsonl and FINDINGS-VERIFIED.md;
     score-at-risk figures against report/score_at_risk.jsonl; recall/precision/escape rates
     against report/mutation_scores.json. A claim whose artifact does not exist yet is reported
     as UNVERIFIABLE, never as PASS.
  4. Cross-check external figures (e.g. the MedAgentBench Action SR range) against
     EXTERNAL-VERIFICATION.md, which records what was actually read from the source.
  5. Enforce the lexical rule from the methodology review: any sentence carrying a score-at-risk
     figure must say "at risk" or "depend", must not say "misgraded" or "wrong" (reserved for
     verdict-flip counts), and must carry a basis tag (whole_state_hash / collection_only /
     exact_field) if it states a percentage.
  6. Enforce placeholder discipline: every [Nk: ...] must name a real script or artifact path
     that exists in the repository.

Usage:
    python experiments/numbers_audit.py [--manuscript PATH]

Exit code is non-zero iff at least one check below resolved FAIL. UNVERIFIABLE and INFO rows do
not gate the exit code -- sections IV, VII, VIII, X and XI are stubs by design (see
paper/main.md's own header comment) and UNVERIFIABLE rows from them are expected, not a bug.
"""
from __future__ import annotations

import argparse
import json
import functools
import subprocess
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Callable, Optional

# ---------------------------------------------------------------------------
# Windows console encoding: this script prints non-ASCII characters (≥, §, en
# dashes, etc.) that pass through cleanly under PYTHONUTF8=1/PYTHONIOENCODING
# but raise UnicodeEncodeError on a plain Windows console using the default
# codepage. The gate must exit 0 (or FAIL for a real reason) regardless of the
# invoking shell's locale, so the stream encoding is fixed here rather than
# left to the caller's environment. reconfigure() is Python 3.7+; guarded for
# any stream that does not support it (e.g. when stdout is already replaced
# by a non-file-like object in a test harness).
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANUSCRIPT = PROJECT_ROOT / "paper" / "main.md"
DEFAULT_TEX_MANUSCRIPT = PROJECT_ROOT / "paper" / "latex" / "main.tex"
FINDINGS_VERIFIED_MD = PROJECT_ROOT / "FINDINGS-VERIFIED.md"
EXTERNAL_VERIFICATION_MD = PROJECT_ROOT / "EXTERNAL-VERIFICATION.md"
GATE_MD = PROJECT_ROOT / "GATE.md"
CLAUDE_MD = PROJECT_ROOT / "CLAUDE.md"
FINDINGS_JSONL = PROJECT_ROOT / "report" / "findings.jsonl"
SCORE_AT_RISK_JSONL = PROJECT_ROOT / "report" / "score_at_risk.jsonl"
MUTATION_SCORES_JSON = PROJECT_ROOT / "report" / "mutation_scores.json"


# ---------------------------------------------------------------------------
# Result plumbing
# ---------------------------------------------------------------------------

PASS = "PASS"
FAIL = "FAIL"
UNVERIFIABLE = "UNVERIFIABLE"
INFO = "INFO"


@dataclass
class Finding:
    section: str       # which of the six mandated checks this belongs to
    claim: str          # human-readable description of the claim
    location: str       # e.g. "paper/main.md:83"
    expected: str
    found: str
    verdict: str
    detail: str = ""


class Report:
    def __init__(self) -> None:
        self.findings: list[Finding] = []

    def add(self, section: str, claim: str, location: str, expected: str, found: str,
            verdict: str, detail: str = "") -> None:
        self.findings.append(Finding(section, claim, location, expected, found, verdict, detail))

    def failed(self) -> list[Finding]:
        return [f for f in self.findings if f.verdict == FAIL]

    def by_section(self) -> dict[str, list[Finding]]:
        out: dict[str, list[Finding]] = {}
        for f in self.findings:
            out.setdefault(f.section, []).append(f)
        return out



@functools.lru_cache(maxsize=None)
def _resolves_in_our_git(short_hash: str) -> bool:
    """True if `short_hash` names a commit in THIS repository.

    The paper cites two kinds of hash. Benchmark commits (MedAgentBench 9926011,
    tau2-bench c3398666) appear as full hashes in FINDINGS-VERIFIED.md, and the check
    above matches short forms against those. But the paper also cites its OWN commits --
    the two checker-freeze tags and the agent-experiment pre-registration -- and those
    live in git, not in any markdown file. Without this the audit reports every one of
    them as unknown, which is a false alarm that trains you to ignore the check.

    It is also the check that matters most. A draft once cited 35c2dbf and 94adf1e for
    the two freeze tags; the real hashes are 8f9b2ff and b2a39e1. A wrong hash on a
    pre-registration claim is falsifiable by a reviewer in one command, and nothing else
    in the audit would have caught it.
    """
    try:
        out = subprocess.run(
            ["git", "-C", str(PROJECT_ROOT), "rev-parse", "--verify", "--quiet", f"{short_hash}^{{commit}}"],
            capture_output=True, text=True, timeout=15,
        )
        return out.returncode == 0 and bool(out.stdout.strip())
    except Exception:
        return False

def line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Number-word support -- this manuscript spells out small counts in prose
# ("eight finding instances", "seventeen of nineteen tau2 contracts"), so a
# digit-only scanner would silently miss most of the claims worth checking.
# ---------------------------------------------------------------------------

_ONES = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19,
}
_TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
    "eighty": 80, "ninety": 90,
}
_NUMBER_WORDS = sorted(set(_ONES) | set(_TENS), key=len, reverse=True)


def word_to_number(token: str) -> Optional[float]:
    t = token.lower().strip()
    if t in _ONES:
        return float(_ONES[t])
    if t in _TENS:
        return float(_TENS[t])
    if "-" in t:
        a, b = t.split("-", 1)
        if a in _TENS and b in _ONES:
            return float(_TENS[a] + _ONES[b])
    return None


def parse_num(token: str) -> Optional[float]:
    token = token.strip()
    try:
        return float(token)
    except ValueError:
        return word_to_number(token)


# Regex fragment matching a digit count/percentage or a spelled-out number word (0-99, simple
# compounds like "thirty-five"). Used as a component of larger, hand-written concept patterns
# below -- never as a standalone "find every number" pass, because that produces too many false
# concept groupings to be useful for the internal-consistency check.
#
# NUM and PCT are each EXACTLY ONE capturing group, so a concept pattern with N of them in
# sequence has exactly N groups in the same order as its `concepts` list -- no group-index
# bookkeeping needed when a pattern mixes NUM and PCT.
_NUM_WORD_ALT = "|".join(re.escape(w) for w in _NUMBER_WORDS)
# _NUM_WORD_ALT must be wrapped in its own non-capturing group before the optional "-<word>"
# compound suffix is attached, or "|" reaches across the whole expression (regex has very low
# precedence for "|") and the suffix silently binds only to the last alternative -- which is how
# an earlier version of this pattern matched "five" out of "Thirty-five" instead of the whole
# compound.
_NUM_INNER = rf"(?:\d+(?:\.\d+)?|(?:{_NUM_WORD_ALT})(?:-(?:{_NUM_WORD_ALT}))?)"
NUM = rf"({_NUM_INNER})"
PCT = rf"({_NUM_INNER}%)"


# ---------------------------------------------------------------------------
# Check 1: extraction -- generic census, reported regardless of downstream checks
# ---------------------------------------------------------------------------

def extract_percentages(text: str) -> list[tuple[int, str]]:
    out = []
    for m in re.finditer(r"\d+(?:\.\d+)?%", text):
        out.append((line_of(text, m.start()), m.group(0)))
    return out


def extract_commit_hashes(text: str) -> list[tuple[int, str]]:
    out = []
    for m in re.finditer(r"`([0-9a-f]{6,40})`", text):
        out.append((line_of(text, m.start()), m.group(1)))
    return out


def extract_table_refs(text: str) -> list[tuple[int, str]]:
    out = []
    for m in re.finditer(r"Table\s+[IVXLC]+\b", text):
        out.append((line_of(text, m.start()), m.group(0)))
    return out


def extract_line_ranges(text: str) -> list[tuple[int, str]]:
    out = []
    for m in re.finditer(r"[A-Za-z0-9_./]+\.py:\d+(?:[-,]\d+)*", text):
        out.append((line_of(text, m.start()), m.group(0)))
    for m in re.finditer(r"\blines?\s+\d+[-–]\d+\b", text):
        out.append((line_of(text, m.start()), m.group(0)))
    return out


@dataclass
class Placeholder:
    key: str            # "N1", "N2", ...
    body: str            # raw text inside the brackets after "Nk:"
    line: int


def extract_placeholders(text: str) -> list[Placeholder]:
    out = []
    for m in re.finditer(r"\[N(\d+):\s*([^\[\]]+)\]", text):
        out.append(Placeholder(key=f"N{m.group(1)}", body=m.group(2).strip(),
                                line=line_of(text, m.start())))
    return out


@dataclass
class CitationMarker:
    key: str
    body: str
    line: int


def extract_citation_markers(text: str) -> list[CitationMarker]:
    out = []
    for m in re.finditer(r"\[(C\d+(?:,\s*C\d+)*)\s*(?:→|->)?\s*([^\]]*)\]", text):
        out.append(CitationMarker(key=m.group(1), body=m.group(2).strip(),
                                   line=line_of(text, m.start())))
    return out


def run_extraction_census(text: str, report: Report) -> None:
    pcts = extract_percentages(text)
    hashes = extract_commit_hashes(text)
    tables = extract_table_refs(text)
    lineranges = extract_line_ranges(text)
    placeholders = extract_placeholders(text)
    citations = extract_citation_markers(text)
    report.add("1-extraction", "percentage tokens found", "paper/main.md", "n/a",
                f"{len(pcts)} tokens: " + ", ".join(f"L{l}:{v}" for l, v in pcts), INFO)
    report.add("1-extraction", "commit-hash-like tokens found", "paper/main.md", "n/a",
                f"{len(hashes)} tokens: " + ", ".join(f"L{l}:{v}" for l, v in hashes), INFO)
    report.add("1-extraction", "table references found", "paper/main.md", "n/a",
                f"{len(tables)} refs: " + ", ".join(f"L{l}:{v}" for l, v in tables), INFO)
    report.add("1-extraction", "file:line / lines N-N citations found", "paper/main.md", "n/a",
                f"{len(lineranges)} citations: " + ", ".join(f"L{l}:{v}" for l, v in lineranges),
                INFO)
    report.add("1-extraction", "[Nk: ...] evidence placeholders found", "paper/main.md", "n/a",
                f"{len(placeholders)} placeholders: " +
                ", ".join(f"L{p.line}:{p.key}={p.body!r}" for p in placeholders), INFO)
    report.add("1-extraction", "[Ck ...] claim-id citation markers found", "paper/main.md",
                "n/a",
                f"{len(citations)} markers: " +
                ", ".join(f"L{c.line}:{c.key}->{c.body!r}" for c in citations), INFO)


# ---------------------------------------------------------------------------
# Check 2: internal consistency -- tracked quantities, each named once and
# extracted everywhere it is stated in the manuscript (prose, the abstract's
# committed-shape comment block, section text, tables). If the same key is
# ever found with two different values, that is exactly the 7-vs-5-vs-4 bug.
# ---------------------------------------------------------------------------

@dataclass
class ConceptMatch:
    concept: str
    value: float
    raw: str
    line: int


# Each entry: (concepts-in-group-order, regex). The regex must have exactly len(concepts)
# capturing groups, each built from NUM (or PCT). re.IGNORECASE + re.DOTALL(off) with \s+ used
# in place of literal spaces so a phrase wrapped across a markdown line break still matches.
CONCEPT_PATTERNS: list[tuple[list[str], str]] = [
    # --- headline-eligible cell count / benchmark count / instance count, all sources ---
    (["headline_cell_count", "benchmark_count"],
     rf"{NUM}\s+HEADLINE-ELIGIBLE tool-layer cells\s+across\s+{NUM}\s+benchmarks"),
    (["headline_cell_count", "benchmark_count", "finding_instance_count"],
     rf"{NUM} headline-eligible benchmark-class defect cells across {NUM} shipped benchmarks,\s*"
     rf"from\s+{NUM} verified instances"),
    (["finding_instance_count"],
     rf"{NUM}\s+instances reported alongside"),
    (["finding_instance_count", "benchmark_count", "headline_cell_count"],
     rf"cleared 2026-08-21:\s*{NUM}\s+instances across\s+{NUM}\s+environments,\s*{NUM}\s+of "
     rf"them\s+headline-eligible"),
    (["benchmark_class_cell_count"],
     rf"of the {NUM} cannot carry a headline"),
    (["benchmark_count", "finding_instance_count", "benchmark_class_cell_count",
      "headline_cell_count"],
     rf"Across {NUM} shipped benchmarks we confirmed {NUM} finding instances,\s*falling into "
     rf"{NUM} benchmark-class cells,\s*of which \*\*{NUM} are headline-eligible\*\*"),
    (["ignored_argument_instance_count", "finding_instance_count"],
     rf"{NUM} of the {NUM} instances are Ignored Argument"),
    # --- defect-class taxonomy size (must always be six) ---
    (["defect_class_count"], rf"{NUM} executable defect classes"),
    (["defect_class_count"], rf"[Dd]efines {NUM} defect classes"),
    (["field_observed_class_count", "defect_class_count"],
     rf"{NUM} of the {NUM} classes are field-observed"),
    (["defect_class_count"], rf"all {NUM} defect classes"),
    (["defect_class_count", "overlap_category_count", "total_mapped_category_count"],
     rf"our {NUM} defect classes against their categories yields {NUM} overlap in {NUM} "
     rf"categories"),
    # --- adapters / contracts / validator checks ---
    (["adapter_count"], rf"{NUM} adapters exist"),
    (["contracts_total", "adapter_count", "validator_checks_count"],
     rf"{NUM} contracts are authored against these {NUM} adapters and pass all {NUM} validator "
     rf"checks"),
    (["tau2_contracts_exercised_before_fix"], rf"a {NUM}-entry table"),
    (["tau2_contracts_skipped", "tau2_contracts_total"],
     rf"{NUM} of {NUM} tau2 contracts were silently never dynamically exercised"),
    (["frame_clause_count"], rf"{NUM} shipped frame clauses"),
    # --- benchguard/aba/tool-veritas category mapping (C6) ---
    (["benchguard_category_count"], rf"across {NUM} defect subcategories"),
    # --- MedAgentBench / Action SR external figures ---
    (["medagentbench_write_task_count"], rf"the {NUM} write tasks"),
    (["medagentbench_model_count"], rf"all {NUM} evaluated models"),
    (["action_sr_min", "action_sr_max", "medagentbench_model_count"],
     rf"Action SR ranges {PCT} to {PCT} across the {NUM} evaluated models"),
    (["action_sr_best"], rf"the best is Gemini-1\.5 Pro at {PCT}"),
    (["action_sr_zero_count", "action_sr_zero_value"], rf"{NUM} models score {PCT}"),
    (["overall_sr_claude"], rf"headlines {PCT} overall SR"),
    (["nejm_ai_volume", "nejm_ai_issue"], rf"NEJM AI \(vol\.\s*{NUM},\s*iss\.\s*{NUM}\)"),
    (["medagentbench_source_file_commit_count"],
     rf"touched by exactly {NUM} commit in its history"),
    # --- MedAgentBench finding-4 scope ---
    (["medagentbench_unconditional_families", "medagentbench_task_family_count",
      "medagentbench_unconditional_cases", "medagentbench_total_tasks"],
     rf"{NUM} of the {NUM} task families \({NUM} of {NUM} cases\) grade writes "
     rf"unconditionally"),
    # --- AgentDojo field counts (Finding 5 contrast case) ---
    (["agentdojo_update_scheduled_fields"], rf"documents {NUM} optional updatable fields"),
    (["agentdojo_update_user_info_fields"],
     rf"repeats the truthiness pattern on {NUM} string fields"),
    # --- MM-ToolSandbox line offset ---
    (["mmtoolsandbox_forwarding_line_offset"],
     rf"appears {NUM} lines above in the same file"),
    # --- disclosure lead time ---
    (["disclosure_lead_days"], rf"{NUM} days before submission"),
]

_COMPILED_CONCEPT_PATTERNS = [(concepts, re.compile(pat, re.IGNORECASE))
                              for concepts, pat in CONCEPT_PATTERNS]


def extract_concept_matches(text: str) -> list[ConceptMatch]:
    out: list[ConceptMatch] = []
    for concepts, rx in _COMPILED_CONCEPT_PATTERNS:
        for m in rx.finditer(text):
            groups = m.groups()
            assert len(groups) == len(concepts), (
                f"pattern for {concepts} has {len(groups)} groups, expected {len(concepts)}: "
                f"{rx.pattern}")
            for concept, raw in zip(concepts, groups):
                val_str = raw[:-1] if raw.endswith("%") else raw
                val = parse_num(val_str)
                if val is None:
                    continue
                out.append(ConceptMatch(concept=concept, value=val, raw=raw,
                                         line=line_of(text, m.start())))
    return out


def check_internal_consistency(matches: list[ConceptMatch], report: Report) -> dict[str, float]:
    """Group by concept; flag any concept with more than one distinct value. Returns the
    consensus value per concept (mode; first value if there is no majority) for downstream
    artifact cross-checks."""
    by_concept: dict[str, list[ConceptMatch]] = {}
    for m in matches:
        by_concept.setdefault(m.concept, []).append(m)

    consensus: dict[str, float] = {}
    for concept, ms in sorted(by_concept.items()):
        values = sorted({m.value for m in ms})
        locations = ", ".join(f"L{m.line}={m.raw}" for m in ms)
        if len(values) == 1:
            consensus[concept] = values[0]
            report.add("2-internal-consistency", f"quantity '{concept}' stated consistently",
                        "paper/main.md", f"single value ({values[0]:g})", locations, PASS)
        else:
            # majority vote as the consensus value for downstream checks; still a hard FAIL
            from collections import Counter
            counts = Counter(m.value for m in ms)
            consensus[concept] = counts.most_common(1)[0][0]
            report.add(
                "2-internal-consistency",
                f"quantity '{concept}' stated with conflicting values",
                "paper/main.md",
                "a single consistent value",
                locations,
                FAIL,
                detail=f"distinct values found: {values}",
            )
    return consensus


# ---------------------------------------------------------------------------
# Check 2b: numeric-token equivalence between paper/main.md and the submission
# artifact, paper/latex/main.tex. CLAUDE.md's standing rule ("a script parses
# every numeric claim in the manuscript") was previously enforced only against
# main.md, the file nobody submits -- main.tex is cut and reworded independently
# (see its own header comment) and could silently drift on a tracked headline
# number without this check ever seeing it. Rather than a literal text diff
# (the two files are deliberately not verbatim -- see CLAUDE.md), this reuses
# the same CONCEPT_PATTERNS that check 2 already trusts to find a tracked
# quantity in prose: a lightly de-TeXed projection of main.tex is scanned with
# the identical patterns, and any concept found in BOTH files with DIFFERENT
# consensus values is a FAIL. A concept found in only one file is not a
# failure -- main.tex deliberately relocates some supporting detail to the
# artifact (per its own header comment) and is not required to restate every
# number main.md does -- so that case is reported as INFO, not PASS or FAIL.
# ---------------------------------------------------------------------------

_TEX_TEXT_CMD_RE = re.compile(
    r"\\(?:texttt|textbf|textit|emph|text)\{([^{}]*)\}")
_TEX_LSTINLINE_RE = re.compile(r"\\lstinline\|([^|]*)\|")
_TEX_LINE_COMMENT_RE = re.compile(r"(?<!\\)%.*")
_TEX_BODY_RE = re.compile(r"\\begin\{document\}(.*)\\end\{document\}", re.DOTALL)


def detex_for_numeric_scan(tex_raw: str) -> str:
    """Strip just enough LaTeX markup that CONCEPT_PATTERNS (written against main.md's
    Markdown prose) also fires on main.tex's prose, without attempting a full LaTeX parse.
    Scope is deliberately narrow: unwrap the handful of text-formatting macros this
    manuscript actually uses around numbers, normalize the handful of math/spacing macros
    that appear next to figures, and drop everything outside \\begin{document}..\\end{document}
    (the file's own header/footer commentary is process narration, not manuscript content,
    and would otherwise pollute the number census with unrelated dates and page counts)."""
    m = _TEX_BODY_RE.search(tex_raw)
    body = m.group(1) if m else tex_raw
    body = _TEX_LINE_COMMENT_RE.sub("", body)
    body = body.replace("\\%", "%").replace("\\_", "_").replace("\\brk", "")
    body = body.replace("$\\geq$", "\u2265").replace("\\geq", "\u2265")
    body = body.replace("$\\leq$", "\u2264").replace("\\leq", "\u2264")
    body = re.sub(r"\\S\\,?", "\u00a7", body)
    for _ in range(3):  # a few passes: \textbf{\texttt{x}} nests one level in this manuscript
        body = _TEX_TEXT_CMD_RE.sub(r"\1", body)
    body = _TEX_LSTINLINE_RE.sub(r"\1", body)
    return body


def check_manuscript_tex_numeric_equivalence(md_text: str, tex_path: Path,
                                              report: Report) -> None:
    section = "2-internal-consistency"
    claim_prefix = "cross-file: quantity"
    if not tex_path.exists():
        report.add(section, f"{claim_prefix} equivalence check (main.md vs main.tex)",
                    str(tex_path), "file to exist", "file missing", UNVERIFIABLE)
        return

    tex_text = detex_for_numeric_scan(read_text(tex_path))
    md_matches = extract_concept_matches(md_text)
    tex_matches = extract_concept_matches(tex_text)

    def modes_by_concept(matches: list[ConceptMatch]) -> dict[str, tuple[float, list[ConceptMatch]]]:
        by: dict[str, list[ConceptMatch]] = {}
        for mm in matches:
            by.setdefault(mm.concept, []).append(mm)
        return {c: (Counter(x.value for x in ms).most_common(1)[0][0], ms)
                for c, ms in by.items()}

    md_modes = modes_by_concept(md_matches)
    tex_modes = modes_by_concept(tex_matches)

    for concept in sorted(set(md_modes) & set(tex_modes)):
        md_val, md_ms = md_modes[concept]
        tex_val, tex_ms = tex_modes[concept]
        verdict = PASS if md_val == tex_val else FAIL
        report.add(
            section, f"{claim_prefix} '{concept}' agrees between main.md and main.tex",
            f"{DEFAULT_MANUSCRIPT.name} vs {tex_path.name}",
            f"main.md={md_val:g}", f"main.tex={tex_val:g}", verdict,
            detail=(f"main.md: {', '.join(f'L{x.line}={x.raw}' for x in md_ms)}; "
                    f"main.tex (post-detex): {', '.join(f'L{x.line}={x.raw}' for x in tex_ms)}"))

    only_md = sorted(set(md_modes) - set(tex_modes))
    if only_md:
        report.add(section, "cross-file: quantities matched in main.md only (not cross-checked)",
                    str(tex_path), "n/a", ", ".join(only_md), INFO,
                    detail="expected where main.tex relocated supporting detail to the "
                    "artifact per its own header comment; not itself a failure")
    only_tex = sorted(set(tex_modes) - set(md_modes))
    if only_tex:
        report.add(section, "cross-file: quantities matched in main.tex only (not cross-checked)",
                    str(DEFAULT_MANUSCRIPT), "n/a", ", ".join(only_tex), INFO)


# ---------------------------------------------------------------------------
# Check 3: cross-check against generated artifacts
# ---------------------------------------------------------------------------

def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in read_text(path).splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def check_findings_jsonl_headline_cells(consensus: dict[str, float], report: Report) -> None:
    claim = "manuscript's headline-eligible cell count"
    if not FINDINGS_JSONL.exists():
        report.add("3-artifact-crosscheck", claim, str(FINDINGS_JSONL), "artifact to exist",
                    "file missing", UNVERIFIABLE)
        return
    rows = load_jsonl(FINDINGS_JSONL)
    cells = {(r["benchmark"], r.get("defect_class"))
             for r in rows
             if r.get("verdict") == "VIOLATES" and r.get("headline_tier") == "agent_visible"
             and r.get("defect_class")}

    # MedAgentBench is a static-only case study with no adapter (per FINDINGS-VERIFIED.md and
    # main.md §VI), so it never appears in findings.jsonl. Its Phantom Effect headline cell is
    # confirmed statically; check for that confirmation in FINDINGS-VERIFIED.md rather than
    # silently omitting it, so the count is comparable to the manuscript's claim.
    medagentbench_static_cell = False
    if FINDINGS_VERIFIED_MD.exists():
        fv_text = read_text(FINDINGS_VERIFIED_MD)
        if re.search(
            r"MedAgentBench\s*/\s*Phantom Effect\s*\|\s*Statically", fv_text
        ):
            medagentbench_static_cell = True
            cells.add(("medagentbench", "phantom_effect"))

    computed = len(cells)
    detail = (f"cells (from findings.jsonl, verdict=VIOLATES, headline_tier=agent_visible): "
              f"{sorted(cells)}; MedAgentBench static-case bonus applied: "
              f"{medagentbench_static_cell}")
    if "headline_cell_count" not in consensus:
        report.add("3-artifact-crosscheck", claim, "paper/main.md", str(computed),
                    "no headline-cell-count claim found in manuscript", INFO, detail=detail)
        return
    claimed = consensus["headline_cell_count"]
    verdict = PASS if claimed == computed else FAIL
    report.add("3-artifact-crosscheck", claim, str(FINDINGS_JSONL), str(computed),
                f"manuscript claims {claimed:g}", verdict, detail=detail)


def check_findings_verified_instance_count(consensus: dict[str, float], report: Report) -> None:
    claim = "manuscript's finding-instance count (8)"
    if not FINDINGS_VERIFIED_MD.exists():
        report.add("3-artifact-crosscheck", claim, str(FINDINGS_VERIFIED_MD),
                    "artifact to exist", "file missing", UNVERIFIABLE)
        return
    text = read_text(FINDINGS_VERIFIED_MD)
    headers = re.findall(r"^## Finding (\d+)\b", text, re.MULTILINE)
    computed = len(headers)
    if "finding_instance_count" not in consensus:
        report.add("3-artifact-crosscheck", claim, "paper/main.md", str(computed),
                    "no finding-instance-count claim found in manuscript", INFO)
        return
    claimed = consensus["finding_instance_count"]
    verdict = PASS if claimed == computed else FAIL
    report.add("3-artifact-crosscheck", claim, str(FINDINGS_VERIFIED_MD), str(computed),
                f"manuscript claims {claimed:g}", verdict,
                detail=f"'## Finding N' headers found: {headers}")


def check_findings_verified_cell_count(consensus: dict[str, float], report: Report) -> None:
    claim = "manuscript's benchmark-class cell count (7)"
    if not FINDINGS_VERIFIED_MD.exists():
        report.add("3-artifact-crosscheck", claim, str(FINDINGS_VERIFIED_MD),
                    "artifact to exist", "file missing", UNVERIFIABLE)
        return
    text = read_text(FINDINGS_VERIFIED_MD)
    m = re.search(r"(\d+) unique benchmark-class cells", text)
    if not m:
        report.add("3-artifact-crosscheck", claim, str(FINDINGS_VERIFIED_MD),
                    "'N unique benchmark-class cells' statement", "not found", UNVERIFIABLE)
        return
    computed = float(m.group(1))
    if "benchmark_class_cell_count" not in consensus:
        report.add("3-artifact-crosscheck", claim, "paper/main.md", f"{computed:g}",
                    "no benchmark-class-cell-count claim found in manuscript", INFO)
        return
    claimed = consensus["benchmark_class_cell_count"]
    verdict = PASS if claimed == computed else FAIL
    report.add("3-artifact-crosscheck", claim, str(FINDINGS_VERIFIED_MD), f"{computed:g}",
                f"manuscript claims {claimed:g}", verdict)


def check_contracts_and_adapters(consensus: dict[str, float], report: Report) -> None:
    contracts_dir = PROJECT_ROOT / "spec" / "contracts"
    if not contracts_dir.exists():
        report.add("3-artifact-crosscheck", "manuscript's '42 contracts' claim",
                    str(contracts_dir), "directory to exist", "directory missing", UNVERIFIABLE)
        return
    per_adapter = {}
    for sub in sorted(p for p in contracts_dir.iterdir() if p.is_dir()):
        per_adapter[sub.name] = len(list(sub.glob("*.yaml"))) + len(list(sub.glob("*.yml")))
    total = sum(per_adapter.values())
    adapter_count = len(per_adapter)

    if "contracts_total" in consensus:
        claimed = consensus["contracts_total"]
        verdict = PASS if claimed == total else FAIL
        report.add("3-artifact-crosscheck", "manuscript's total contract count",
                    str(contracts_dir), str(total), f"manuscript claims {claimed:g}", verdict,
                    detail=f"per-adapter counts: {per_adapter}")
    else:
        report.add("3-artifact-crosscheck", "manuscript's total contract count",
                    "paper/main.md", str(total), "no contract-count claim found in manuscript",
                    INFO, detail=f"per-adapter counts: {per_adapter}")

    if "adapter_count" in consensus:
        claimed = consensus["adapter_count"]
        verdict = PASS if claimed == adapter_count else FAIL
        report.add("3-artifact-crosscheck", "manuscript's adapter count", str(contracts_dir),
                    str(adapter_count), f"manuscript claims {claimed:g}", verdict,
                    detail=f"adapter directories: {sorted(per_adapter)}")

    tau2_count = per_adapter.get("tau2")
    if tau2_count is not None and "tau2_contracts_total" in consensus:
        claimed = consensus["tau2_contracts_total"]
        verdict = PASS if claimed == tau2_count else FAIL
        report.add("3-artifact-crosscheck", "manuscript's tau2 contract-count claim (19)",
                    str(contracts_dir / "tau2"), str(tau2_count), f"manuscript claims "
                    f"{claimed:g}", verdict)

    # derived internal-math check: exercised-before-fix + skipped-before-fix == total, iff both
    # figures were stated in the manuscript
    if {"tau2_contracts_exercised_before_fix", "tau2_contracts_skipped",
        "tau2_contracts_total"} <= consensus.keys():
        exercised = consensus["tau2_contracts_exercised_before_fix"]
        skipped = consensus["tau2_contracts_skipped"]
        tot = consensus["tau2_contracts_total"]
        verdict = PASS if exercised + skipped == tot else FAIL
        report.add("3-artifact-crosscheck",
                    "manuscript's own arithmetic: exercised + skipped == total tau2 contracts",
                    "paper/main.md", f"{exercised:g} + {skipped:g} == {tot:g}",
                    f"{exercised:g} + {skipped:g} = {exercised + skipped:g}", verdict)


def check_validator_checks_count(consensus: dict[str, float], report: Report) -> None:
    validate_py = PROJECT_ROOT / "spec" / "validate.py"
    claim = "manuscript's 'eight validator checks' claim"
    if not validate_py.exists():
        report.add("3-artifact-crosscheck", claim, str(validate_py), "file to exist",
                    "file missing", UNVERIFIABLE)
        return
    text = read_text(validate_py)
    numbers = sorted({int(n) for n in re.findall(r"#\s*Check\s+(\d+):", text)})
    computed = max(numbers) if numbers else 0
    if "validator_checks_count" not in consensus:
        report.add("3-artifact-crosscheck", claim, "paper/main.md", str(computed),
                    "no validator-check-count claim found in manuscript", INFO,
                    detail=f"'# Check N:' markers found: {numbers}")
        return
    claimed = consensus["validator_checks_count"]
    contiguous = numbers == list(range(1, computed + 1))
    verdict = PASS if (claimed == computed and contiguous) else FAIL
    report.add("3-artifact-crosscheck", claim, str(validate_py), str(computed),
                f"manuscript claims {claimed:g}", verdict,
                detail=f"'# Check N:' markers found: {numbers} (contiguous: {contiguous})")


def check_gate_md_category_mapping(consensus: dict[str, float], report: Report) -> None:
    claim = "manuscript's '27 categories' / '0 overlap' mapping claim (C6)"
    if not GATE_MD.exists():
        report.add("3-artifact-crosscheck", claim, str(GATE_MD), "file to exist",
                    "file missing", UNVERIFIABLE)
        return
    text = read_text(GATE_MD)

    def section(start_heading: str) -> str:
        i = text.find(start_heading)
        if i < 0:
            return ""
        j = text.find("\n### ", i + 1)
        if j < 0:
            j = text.find("\n## ", i + 1)
        return text[i: j if j > 0 else len(text)]

    benchguard_sec = section("### BenchGuard, Appendix A")
    benchguard_rows = re.findall(r"^\|\s*[A-Z][A-Z0-9-]+\s*\|", benchguard_sec, re.MULTILINE)
    benchguard_count = len(benchguard_rows)

    aba_sec = section("### Auto Benchmark Audit")
    aba_rows = re.findall(r"^\|\s*(?:Instruction|Environment|Evaluation)\s*\|", aba_sec,
                           re.MULTILINE)
    aba_count = len(aba_rows)

    tv_sec = section("### Tool-Veritas")
    det_m = re.search(r"Deterministic evaluator failures:\s*([^\n]+)", tv_sec)
    judge_m = re.search(r"LLM-judge failures:\s*([^\n]+)", tv_sec)
    tv_count = 0
    if det_m:
        tv_count += len([p for p in det_m.group(1).split(";") if p.strip()])
    if judge_m:
        tv_count += len([p for p in judge_m.group(1).rstrip(".").split(";") if p.strip()])

    total = benchguard_count + aba_count + tv_count
    detail = (f"BenchGuard rows={benchguard_count}, ABA axis rows={aba_count}, "
              f"Tool-Veritas categories={tv_count}, sum={total}")

    if "total_mapped_category_count" in consensus:
        claimed = consensus["total_mapped_category_count"]
        verdict = PASS if claimed == total else FAIL
        report.add("3-artifact-crosscheck", claim, str(GATE_MD), str(total),
                    f"manuscript claims {claimed:g}", verdict, detail=detail)
    else:
        report.add("3-artifact-crosscheck", claim, "paper/main.md", str(total),
                    "no category-mapping claim found in manuscript", INFO, detail=detail)

    if "benchguard_category_count" in consensus:
        claimed = consensus["benchguard_category_count"]
        verdict = PASS if claimed == benchguard_count else FAIL
        report.add("3-artifact-crosscheck", "manuscript's 'BenchGuard 14 subcategories' claim",
                    str(GATE_MD), str(benchguard_count), f"manuscript claims {claimed:g}",
                    verdict)


def check_score_at_risk_and_mutation_artifacts(text: str, report: Report) -> None:
    """§IV, §VII and §VIII are stubs in the current draft (no numeric claims naming these
    artifacts have appeared in body text yet). Report their existence/parseability so this check
    is visibly wired for the day content lands, without asserting anything false about content
    that is not there yet."""
    for path, label in ((SCORE_AT_RISK_JSONL, "report/score_at_risk.jsonl"),
                         (MUTATION_SCORES_JSON, "report/mutation_scores.json")):
        if not path.exists():
            report.add("3-artifact-crosscheck", f"{label} exists and is loadable", str(path),
                        "file to exist", "file missing", UNVERIFIABLE)
            continue
        try:
            if path.suffix == ".jsonl":
                rows = load_jsonl(path)
                found = f"{len(rows)} rows, parses cleanly"
            else:
                json.loads(read_text(path))
                found = "parses cleanly as JSON"
        except (json.JSONDecodeError, OSError) as exc:
            report.add("3-artifact-crosscheck", f"{label} exists and is loadable", str(path),
                        "valid JSON/JSONL", f"parse error: {exc}", FAIL)
            continue
        report.add("3-artifact-crosscheck", f"{label} exists and is loadable", str(path),
                    "file to exist and parse", found, PASS)

    # No score-at-risk-tagged numeric claim currently appears in body text (§IV/§VII/§VIII are
    # literally "[NOT YET DRAFTED]" placeholder blocks) -- confirm that rather than silently
    # skipping, so a future numeric claim in these sections is guaranteed to be checked once it
    # lands (the pattern list above has no matcher for score-at-risk percentages yet because none
    # exist to calibrate against).
    drafted_body = re.findall(
        r"^## (IV|VII|VIII)\..*?\n(.*?)(?=\n## |\Z)", text, re.MULTILINE | re.DOTALL)
    for sec_id, body in drafted_body:
        stripped = body.strip()
        is_stub = stripped.startswith("*[NOT YET DRAFTED")
        report.add("3-artifact-crosscheck",
                    f"section {sec_id} numeric-claim status", "paper/main.md",
                    "either a stub placeholder or checked numeric claims",
                    "stub placeholder, no numeric claims to cross-check yet" if is_stub else
                    "drafted -- add matching CONCEPT_PATTERNS entries if it carries new figures",
                    INFO if is_stub else UNVERIFIABLE)


# ---------------------------------------------------------------------------
# Check 4: external figures, against EXTERNAL-VERIFICATION.md
# ---------------------------------------------------------------------------

def parse_action_sr_table(text: str) -> list[tuple[str, float]]:
    rows = []
    for m in re.finditer(r"^\|\s*([^|]+?)\s*\|\s*\*{0,2}(\d+\.\d+)%\*{0,2}[^|]*\|\s*$", text,
                          re.MULTILINE):
        model = m.group(1).strip()
        if model in ("Model", "---") or set(model) <= {"-"}:
            continue
        rows.append((model, float(m.group(2))))
    return rows


def check_external_verification(consensus: dict[str, float], report: Report) -> None:
    section = "4-external-figures"
    if not EXTERNAL_VERIFICATION_MD.exists():
        report.add(section, "MedAgentBench Action SR figures", str(EXTERNAL_VERIFICATION_MD),
                    "file to exist", "file missing", UNVERIFIABLE)
        return
    text = read_text(EXTERNAL_VERIFICATION_MD)

    # Isolate the Action SR table specifically (the "| Model | Action SR |" block), not any
    # other percentage table that might appear later in the same file.
    m = re.search(r"\| Model \| Action SR \|.*?(?=\n\n)", text, re.DOTALL)
    table_text = m.group(0) if m else ""
    rows = parse_action_sr_table(table_text)

    if not rows:
        report.add(section, "MedAgentBench Action SR table parses", str(EXTERNAL_VERIFICATION_MD),
                    ">=1 model row", "0 rows parsed", FAIL)
        return

    values = [v for _, v in rows]
    computed_min, computed_max = min(values), max(values)
    best_model, best_value = max(rows, key=lambda r: r[1])
    zero_count = sum(1 for v in values if v == 0.0)
    model_count = len(rows)

    # Self-consistency of the EXTERNAL-VERIFICATION.md source-of-truth file itself: does its own
    # "for all N evaluated models" prose (immediately above the table) agree with the row count
    # of the table it introduces? This does NOT depend on anything paper/main.md claims -- it is
    # purely a data-quality check on the external-verification artifact -- so it is reported as
    # INFO rather than FAIL/PASS: it must not block a manuscript commit on a pre-existing defect
    # in a file this script's own constraints forbid it from editing, but a human must still see
    # it, because a self-inconsistent source-of-truth file is exactly the kind of thing check 4
    # exists to surface.
    prose_m = re.search(rf"all {NUM} evaluated models", text, re.IGNORECASE)
    prose_count = parse_num(prose_m.group(1)) if prose_m else None
    if prose_count is not None:
        agree = prose_count == model_count
        report.add(section, "EXTERNAL-VERIFICATION.md self-consistency: table row count vs its "
                   "own 'N evaluated models' prose", str(EXTERNAL_VERIFICATION_MD),
                   "table row count and prose model count agree",
                   f"table has {model_count} rows; prose says 'all {prose_m.group(1)} "
                   f"evaluated models'" + (" -- MATCH" if agree else " -- MISMATCH"),
                   INFO,
                   detail="Table rows: " + ", ".join(f"{n}={v:g}%" for n, v in rows) +
                   ("" if agree else " -- NEEDS HUMAN ATTENTION: source-of-truth file "
                    "disagrees with itself; not auto-fixed here per project constraints"))

    checks = [
        ("action_sr_min", computed_min, "Action SR minimum"),
        ("action_sr_max", computed_max, "Action SR maximum"),
        ("action_sr_best", best_value, "Action SR best-in-column value"),
        ("action_sr_zero_count", float(zero_count), "count of models scoring 0.00%"),
        ("medagentbench_model_count", float(model_count), "evaluated-model count"),
    ]
    for concept, computed, label in checks:
        if concept not in consensus:
            report.add(section, f"manuscript's {label} claim", "paper/main.md", str(computed),
                        "no claim of this figure found in manuscript", INFO)
            continue
        claimed = consensus[concept]
        verdict = PASS if abs(claimed - computed) < 1e-9 else FAIL
        report.add(section, f"manuscript's {label} claim", str(EXTERNAL_VERIFICATION_MD),
                    str(computed), f"manuscript claims {claimed:g}", verdict)

    # best-model name check (string, not numeric, but load-bearing for the same claim)
    if "Gemini-1.5 Pro" not in best_model and "Gemini-1.5" not in best_model:
        report.add(section, "manuscript's 'best is Gemini-1.5 Pro' claim",
                    str(EXTERNAL_VERIFICATION_MD), f"best model = {best_model}",
                    "manuscript claims Gemini-1.5 Pro", FAIL)
    else:
        report.add(section, "manuscript's 'best is Gemini-1.5 Pro' claim",
                    str(EXTERNAL_VERIFICATION_MD), f"best model = {best_model}",
                    "manuscript claims Gemini-1.5 Pro", PASS)

    # overall SR 69.67% -- quoted verbatim in EXTERNAL-VERIFICATION.md rather than tabulated
    if "overall_sr_claude" in consensus:
        claimed = consensus["overall_sr_claude"]
        found_quote = "69.67%" in text
        verdict = PASS if (found_quote and abs(claimed - 69.67) < 1e-9) else FAIL
        report.add(section, "manuscript's '69.67% overall SR' claim",
                    str(EXTERNAL_VERIFICATION_MD),
                    "69.67% quoted in EXTERNAL-VERIFICATION.md" if found_quote else
                    "69.67% NOT found in EXTERNAL-VERIFICATION.md",
                    f"manuscript claims {claimed:g}%", verdict)

    # NEJM AI volume/issue
    if {"nejm_ai_volume", "nejm_ai_issue"} <= consensus.keys():
        m2 = re.search(r"NEJM AI\*{0,2},?\s*Vol\.?\s*(\d+),?\s*Issue\s*(\d+)", text)
        if m2:
            computed_vol, computed_iss = float(m2.group(1)), float(m2.group(2))
            verdict = PASS if (consensus["nejm_ai_volume"] == computed_vol and
                                consensus["nejm_ai_issue"] == computed_iss) else FAIL
            report.add(section, "manuscript's 'NEJM AI (vol. 2, iss. 9)' claim",
                        str(EXTERNAL_VERIFICATION_MD),
                        f"vol {computed_vol:g}, iss {computed_iss:g}",
                        f"manuscript claims vol {consensus['nejm_ai_volume']:g}, iss "
                        f"{consensus['nejm_ai_issue']:g}", verdict)
        else:
            report.add(section, "manuscript's 'NEJM AI (vol. 2, iss. 9)' claim",
                        str(EXTERNAL_VERIFICATION_MD), "NEJM AI Vol./Issue statement",
                        "not found", UNVERIFIABLE)

    # "exactly one commit in its history (January 2025)" -- cross-check the ISO date
    if "medagentbench_source_file_commit_count" in consensus:
        m3 = re.search(
            r"touched by \*\*exactly one commit in its entire history\*\*:\s*`([0-9a-f]+)`,\s*"
            r"(\d{4})-(\d{2})-(\d{2})", text)
        if m3:
            year, month = m3.group(2), m3.group(3)
            months = ["", "January", "February", "March", "April", "May", "June", "July",
                      "August", "September", "October", "November", "December"]
            month_name = months[int(month)]
            manuscript_text = read_text(DEFAULT_MANUSCRIPT) if DEFAULT_MANUSCRIPT.exists() else ""
            expected_phrase = f"({month_name} {year})"
            found_phrase = expected_phrase in manuscript_text
            report.add(section, "manuscript's '(January 2025)' single-commit date claim",
                        str(EXTERNAL_VERIFICATION_MD),
                        f"commit dated {month_name} {year}",
                        f"manuscript contains '{expected_phrase}'" if found_phrase else
                        f"manuscript does NOT contain '{expected_phrase}'",
                        PASS if found_phrase else FAIL)
        else:
            report.add(section, "manuscript's '(January 2025)' single-commit date claim",
                        str(EXTERNAL_VERIFICATION_MD), "single-commit-history statement",
                        "not found", UNVERIFIABLE)


def check_disclosure_lead_time(consensus: dict[str, float], report: Report) -> None:
    section = "4-external-figures"
    if "disclosure_lead_days" not in consensus:
        report.add(section, "manuscript's '17 days before submission' disclosure claim",
                    "paper/main.md", "n/a", "no disclosure-lead-time claim found", INFO)
        return
    manuscript_text = read_text(DEFAULT_MANUSCRIPT) if DEFAULT_MANUSCRIPT.exists() else ""
    disc_m = re.search(r"maintainer teams on (\d{4}-\d{2}-\d{2})", manuscript_text)
    if not disc_m or not CLAUDE_MD.exists():
        report.add(section, "manuscript's '17 days before submission' disclosure claim",
                    "paper/main.md", "disclosure date and deadline both stated",
                    "disclosure date or CLAUDE.md deadline not found", UNVERIFIABLE)
        return
    claude_text = read_text(CLAUDE_MD)
    deadline_m = re.search(r"Deadline (\d{4}-\d{2}-\d{2})", claude_text)
    if not deadline_m:
        report.add(section, "manuscript's '17 days before submission' disclosure claim",
                    str(CLAUDE_MD), "a 'Deadline YYYY-MM-DD' line", "not found", UNVERIFIABLE)
        return
    disc_date = date.fromisoformat(disc_m.group(1))
    deadline = date.fromisoformat(deadline_m.group(1))
    computed_days = (deadline - disc_date).days
    claimed_days = consensus["disclosure_lead_days"]
    verdict = PASS if claimed_days == computed_days else FAIL
    report.add(section, "manuscript's '17 days before submission' disclosure claim",
                f"{CLAUDE_MD} deadline + manuscript disclosure date", str(computed_days),
                f"manuscript claims {claimed_days:g}", verdict,
                detail=f"disclosure {disc_date.isoformat()} -> deadline {deadline.isoformat()}")


# ---------------------------------------------------------------------------
# Check 5: the lexical rule on score-at-risk sentences
# ---------------------------------------------------------------------------

BASIS_TAGS = ("whole_state_hash", "collection_only", "exact_field")


def split_paragraphs(text: str) -> list[tuple[int, str]]:
    out = []
    for m in re.finditer(r"[^\n]+(?:\n[^\n]+)*", text):
        out.append((line_of(text, m.start()), m.group(0)))
    return out


def split_sentences(paragraph: str) -> list[str]:
    # Adequate for formal academic prose: split after sentence-final punctuation followed by
    # whitespace and a capital letter (or an opening quote/bracket/backtick), which is how this
    # manuscript is written throughout.
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9`\[(\"‘“])", paragraph)
    return [p.strip() for p in parts if p.strip()]


def check_lexical_rule(text: str, report: Report) -> None:
    section = "5-lexical-rule"
    has_percent_or_fraction = re.compile(r"\d+(?:\.\d+)?%|\b\d+\s*/\s*\d+\b")
    checked_any = False
    for para_line, para in split_paragraphs(text):
        for sent in split_sentences(para):
            lower = sent.lower()
            carries_number = bool(has_percent_or_fraction.search(sent))
            mentions_at_risk = "at risk" in lower or "at-risk" in lower
            mentions_basis_tag = any(tag in sent for tag in BASIS_TAGS)
            is_score_at_risk_sentence = carries_number and (mentions_at_risk or
                                                              mentions_basis_tag)
            if not is_score_at_risk_sentence:
                continue
            checked_any = True
            has_required_word = ("at risk" in lower or "at-risk" in lower or
                                  "depend" in lower)
            has_forbidden_word = bool(re.search(r"\bmisgraded\b|\bwrong\b", lower))
            has_basis_tag = mentions_basis_tag
            excerpt = sent if len(sent) <= 160 else sent[:157] + "..."
            if not has_required_word:
                report.add(section, "score-at-risk sentence must say 'at risk' or 'depend'",
                            f"paper/main.md (near line {para_line})", "'at risk' or 'depend' "
                            "present", f"missing in: {excerpt!r}", FAIL)
            if has_forbidden_word:
                report.add(section, "score-at-risk sentence must not say 'misgraded'/'wrong'",
                            f"paper/main.md (near line {para_line})", "neither word present",
                            f"forbidden word present in: {excerpt!r}", FAIL)
            if not has_basis_tag:
                report.add(section, "at-risk figure must carry a basis tag",
                            f"paper/main.md (near line {para_line})",
                            f"one of {BASIS_TAGS} present", f"no basis tag in: {excerpt!r}",
                            FAIL)
            if has_required_word and not has_forbidden_word and has_basis_tag:
                report.add(section, "score-at-risk sentence satisfies the lexical rule",
                            f"paper/main.md (near line {para_line})", "required word present, "
                            "forbidden words absent, basis tag present", excerpt, PASS)
    if not checked_any:
        report.add(section, "score-at-risk sentences found in current draft", "paper/main.md",
                    "n/a", "0 sentences currently carry both a number and an at-risk/basis-tag "
                    "marker (§IV is a stub) -- rule is wired and will fire once §IV is drafted",
                    INFO)


# ---------------------------------------------------------------------------
# Check 6: placeholder discipline
# ---------------------------------------------------------------------------

_PATH_TOKEN_RE = re.compile(
    r"[A-Za-z0-9_./-]+\.(?:py|md|json|jsonl|ya?ml|txt|csv)\b")

# Directories excluded from the basename-fallback search below: vendored/cloned sources, venvs
# and caches. A placeholder pointing at a bare filename (e.g. "findings.jsonl" instead of
# "report/findings.jsonl") should still resolve if the file lives one level down in this repo's
# own tree -- but should not silently "find" an unrelated same-named file inside a cloned
# benchmark under repos/.
_SEARCH_EXCLUDE_DIRS = {
    "repos", ".git", "__pycache__", "node_modules", ".tau2-src-c3398666",
}
_SEARCH_EXCLUDE_PREFIXES = (".venv",)


def resolve_repo_path(token: str) -> Path:
    return (PROJECT_ROOT / token) if not Path(token).is_absolute() else Path(token)


def find_by_basename(basename: str) -> list[Path]:
    matches = []
    for p in PROJECT_ROOT.rglob(basename):
        rel_parts = p.relative_to(PROJECT_ROOT).parts
        if any(part in _SEARCH_EXCLUDE_DIRS or part.startswith(_SEARCH_EXCLUDE_PREFIXES)
               for part in rel_parts[:-1]):
            continue
        matches.append(p)
    return matches


def check_placeholder_discipline(text: str, report: Report) -> None:
    section = "6-placeholder-discipline"
    placeholders = extract_placeholders(text)
    seen: set[tuple[str, str]] = set()
    for p in placeholders:
        dedup_key = (p.key, p.body)
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        tokens = _PATH_TOKEN_RE.findall(p.body)
        if not tokens:
            report.add(section, f"[{p.key}: ...] names a real artifact path",
                        f"paper/main.md:{p.line}", "a script/artifact path token (e.g. "
                        "'analysis/foo.py')", f"no path-like token found in {p.body!r}", FAIL)
            continue
        for tok in tokens:
            resolved = resolve_repo_path(tok)
            if resolved.exists():
                report.add(section, f"[{p.key}: {tok}] path exists", f"paper/main.md:{p.line}",
                            "path exists in repo", str(resolved), PASS)
                continue
            # fallback: the token may be a bare filename (e.g. "findings.jsonl" instead of
            # "report/findings.jsonl") -- search the repo tree before declaring it missing.
            fallback_matches = find_by_basename(Path(tok).name)
            if len(fallback_matches) == 1:
                report.add(section, f"[{p.key}: {tok}] path exists", f"paper/main.md:{p.line}",
                            "path exists in repo", str(fallback_matches[0]), PASS,
                            detail=f"literal token {tok!r} not found at that exact path; "
                            f"resolved uniquely by basename search instead")
            elif len(fallback_matches) > 1:
                report.add(section, f"[{p.key}: {tok}] path exists", f"paper/main.md:{p.line}",
                            "path exists in repo, unambiguously", "AMBIGUOUS", UNVERIFIABLE,
                            detail=f"basename {Path(tok).name!r} matches multiple files: "
                            f"{[str(m) for m in fallback_matches]}")
            else:
                report.add(section, f"[{p.key}: {tok}] path exists", f"paper/main.md:{p.line}",
                            "path exists in repo", f"MISSING: {resolved}", FAIL)
        # if the placeholder cites a section marker (e.g. "ARCHITECTURE-FINAL.md §9 risk 3"),
        # spot-check that a numbered heading matching that section exists in the target file
        sec_m = re.search(r"§(\d+)", p.body)
        if sec_m and tokens:
            target = resolve_repo_path(tokens[0])
            if target.exists() and target.suffix == ".md":
                heading_present = bool(re.search(
                    rf"^#+\s*{sec_m.group(1)}\.", read_text(target), re.MULTILINE))
                report.add(section, f"[{p.key}: ...] section §{sec_m.group(1)} exists in "
                            f"{tokens[0]}", f"paper/main.md:{p.line}",
                            f"heading matching '## {sec_m.group(1)}.' in {tokens[0]}",
                            "found" if heading_present else "NOT found",
                            PASS if heading_present else FAIL)

    # citation markers [Ck -> `File.md`] get the same treatment, informationally: they are not
    # the [Nk: ...] evidence-placeholder convention CLAUDE.md's rule targets, but a citation
    # pointing at a nonexistent file is the same failure mode.
    for c in extract_citation_markers(text):
        tokens = re.findall(r"[A-Za-z0-9_./-]+\.(?:py|md|json|jsonl|ya?ml)\b",
                             c.body.replace("`", ""))
        if not tokens:
            continue
        for tok in tokens:
            resolved = resolve_repo_path(tok)
            verdict = PASS if resolved.exists() else FAIL
            report.add(section, f"[{c.key} -> {tok}] citation target exists",
                        f"paper/main.md:{c.line}", "path exists in repo",
                        str(resolved) if resolved.exists() else f"MISSING: {resolved}", verdict)


# ---------------------------------------------------------------------------
# Commit-hash consistency (supplementary; folded into check 2's spirit -- the
# same commit should be cited the same way everywhere it appears)
# ---------------------------------------------------------------------------

def check_commit_hash_consistency(text: str, report: Report) -> None:
    section = "2-internal-consistency"
    _resolves_in_our_git.cache_clear() if hasattr(_resolves_in_our_git, "cache_clear") else None
    full_hashes: set[str] = set()
    for path in (FINDINGS_VERIFIED_MD, EXTERNAL_VERIFICATION_MD):
        if path.exists():
            full_hashes.update(re.findall(r"\b([0-9a-f]{40})\b", read_text(path)))
    if not full_hashes:
        report.add(section, "commit short-hashes are prefixes of a known full hash",
                    "FINDINGS-VERIFIED.md / EXTERNAL-VERIFICATION.md", "n/a",
                    "no 40-char commit hashes found in either file", UNVERIFIABLE)
        return
    short_hashes = {h for _, h in extract_commit_hashes(text) if 6 <= len(h) < 40}
    for h in sorted(short_hashes):
        match = any(fh.startswith(h) for fh in full_hashes) or _resolves_in_our_git(h)
        report.add(section, f"commit short-hash `{h}` is a prefix of a known full hash",
                    "paper/main.md", "prefix of some 40-char hash in FINDINGS-VERIFIED.md / "
                    "EXTERNAL-VERIFICATION.md", "matched" if match else "NO MATCH FOUND",
                    PASS if match else FAIL)


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------

SECTION_TITLES = {
    "1-extraction": "1. Extraction census (every numeric claim found)",
    "2-internal-consistency": "2. Internal consistency (same quantity, two values?)",
    "3-artifact-crosscheck": "3. Cross-check against generated artifacts",
    "4-external-figures": "4. External figures vs EXTERNAL-VERIFICATION.md",
    "5-lexical-rule": "5. Lexical rule on score-at-risk sentences",
    "6-placeholder-discipline": "6. Placeholder discipline ([Nk: ...] paths)",
}
SECTION_ORDER = list(SECTION_TITLES)


def render_report(report: Report) -> str:
    lines = []
    by_section = report.by_section()
    counts = {PASS: 0, FAIL: 0, UNVERIFIABLE: 0, INFO: 0}
    for f in report.findings:
        counts[f.verdict] += 1

    lines.append("=" * 78)
    lines.append("NUMBERS AUDIT -- paper/main.md")
    lines.append("=" * 78)
    lines.append(f"PASS={counts[PASS]}  FAIL={counts[FAIL]}  "
                  f"UNVERIFIABLE={counts[UNVERIFIABLE]}  INFO={counts[INFO]}")
    lines.append("")

    for key in SECTION_ORDER:
        findings = by_section.get(key, [])
        if not findings:
            continue
        lines.append("-" * 78)
        lines.append(SECTION_TITLES[key])
        lines.append("-" * 78)
        for f in findings:
            lines.append(f"[{f.verdict}] {f.claim}")
            lines.append(f"    location: {f.location}")
            lines.append(f"    expected: {f.expected}")
            lines.append(f"    found:    {f.found}")
            if f.detail:
                lines.append(f"    detail:   {f.detail}")
        lines.append("")

    if counts[FAIL]:
        lines.append("=" * 78)
        lines.append(f"{counts[FAIL]} FAILING CHECK(S) -- see [FAIL] rows above")
        lines.append("=" * 78)
    else:
        lines.append("No FAIL verdicts. (UNVERIFIABLE/INFO rows may still need human attention "
                      "-- see PAPER-OUTLINE.md's evidence map.)")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_audit(manuscript_path: Path, tex_manuscript_path: Path = DEFAULT_TEX_MANUSCRIPT) -> Report:
    text = read_text(manuscript_path)
    report = Report()

    run_extraction_census(text, report)

    matches = extract_concept_matches(text)
    consensus = check_internal_consistency(matches, report)
    check_commit_hash_consistency(text, report)
    check_manuscript_tex_numeric_equivalence(text, tex_manuscript_path, report)

    check_findings_jsonl_headline_cells(consensus, report)
    check_findings_verified_instance_count(consensus, report)
    check_findings_verified_cell_count(consensus, report)
    check_contracts_and_adapters(consensus, report)
    check_validator_checks_count(consensus, report)
    check_gate_md_category_mapping(consensus, report)
    check_score_at_risk_and_mutation_artifacts(text, report)

    check_external_verification(consensus, report)
    check_disclosure_lead_time(consensus, report)

    check_lexical_rule(text, report)
    check_placeholder_discipline(text, report)

    return report


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--manuscript", type=Path, default=DEFAULT_MANUSCRIPT,
                         help="path to the manuscript markdown file (default: paper/main.md)")
    parser.add_argument("--tex-manuscript", type=Path, default=DEFAULT_TEX_MANUSCRIPT,
                         help="path to the submitted LaTeX manuscript, cross-checked against "
                         "--manuscript for numeric-token equivalence (default: "
                         "paper/latex/main.tex)")
    args = parser.parse_args(argv)

    if not args.manuscript.exists():
        print(f"ERROR: manuscript not found: {args.manuscript}", file=sys.stderr)
        return 2

    report = run_audit(args.manuscript, args.tex_manuscript)
    print(render_report(report))
    return 1 if report.failed() else 0


if __name__ == "__main__":
    sys.exit(main())
