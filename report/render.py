"""Render Table III (per-benchmark audit totals) -- CLAUDE.md's reporting-granularity rule:
"Per benchmark, report: tools audited, mutating tools, independent implementations, unique
defect classes. Not a raw bug count -- eight bugs in one copied helper is one bug."

PAPER-OUTLINE.md N1 names this script's inputs exactly: `report/render.py` <- `findings.jsonl`.
`paper/main.md` sec IX cites the same placeholder. What that citation elides, and what this
module states explicitly instead, is that findings.jsonl alone cannot produce the row for one
of the four audited benchmarks:

  * tau2-bench, AgentDojo, MM-ToolSandbox all have adapters, contracts, and dynamic probe runs,
    so their rows are computed mechanically from report/findings.jsonl -- distinct `tool` names
    give the audited/mutating counts, `verdict == VIOLATES` rows give the defect classes, and
    `headline_tier == agent_visible` is the sole headline-eligibility rule (CLAUDE.md
    "Grounding tiers": "A clause is headline-eligible only if its provenance surface is
    agent-visible ... Maintainer annotations ... are their own tier and never enter headline
    counts.").
  * MedAgentBench has ZERO rows in findings.jsonl. It has no contract and no adapter --
    FINDINGS-VERIFIED.md's "framing error to stop repeating" section is explicit that this is
    a static case study by design, not a coverage gap. Its row is therefore hand-sourced from
    FINDINGS-VERIFIED.md Findings 1 and 4, and from ARCHITECTURE-FINAL.md's "Realistic tool
    counts" line (three POST tool definitions sharing one code path -- the MedAgentBench
    instantiation of the very principle this table exists to enforce). Every number in
    MEDAGENTBENCH_STATIC below carries a citation in its own value; nothing here is invented.

Both are rendered from the SAME row objects (BenchmarkRow), each carrying an explicit `source`
string, so paper/main.md sec VI's "every table is rendered from the ledger" claim is visibly
false for exactly one row and that falsity is machine-readable rather than something a reader
has to reconstruct. (Sec VI's own wording is being corrected elsewhere; this script does not
touch prose.)

Reported vs. headline-eligible, shown rather than left for a reader to subtract (the same
instruction R2 gave the sec IX arithmetic): a defect class enters `classes_reported` whenever
it has direct evidence (a ledger VIOLATES row OR a specific FINDINGS-VERIFIED.md citation for a
class the harness cannot emit), and enters `classes_headline` only when at least one of its
instances is `agent_visible`. Three classes are reported and excluded by name:

  * tau2-bench Partial Effect -- every instance is `maintainer_annotated` (grounded in a
    `logger.warning` the agent never sees), never `agent_visible`.
  * MedAgentBench Ungrounded Oracle -- an evaluator-layer property, not one of the six
    tool-layer classes (FINDINGS-VERIFIED.md Finding 4; main.md sec III/IV).
  * AgentDojo Phantom Effect -- the contract is correct (`success_signal.biconditional: true`)
    but the shipped banking fixture never trips both effect halves in the same call, so the
    checker's re-tag never fires and no VIOLATES row for this class exists anywhere in
    findings.jsonl. Reported here from the narrative record only (FINDINGS-VERIFIED.md "Why
    the fifth cell went"), specifically so a reader is told it exists rather than left to
    notice its absence.

A fourth exclusion is a ledger fact, not a narrative one, and is surfaced here rather than
suppressed: findings.jsonl carries a VIOLATES row for tau2-bench's `suspend_line` (clause
`arg.reason`, defect_class `ignored_argument`, headline_tier `inferred`). FINDINGS-VERIFIED.md
"Candidates, not yet confirmed" documents this clause's *behavior* as confirmed by direct
source read but its *classification* as contested and un-adjudicated, and explicitly states it
"does not raise the headline count." Excluding it from the headline is therefore correct and
uncontroversial; what is a live inconsistency is that FINDINGS-VERIFIED.md's own frozen
seven-cell table (dated 2026-08-21) predates this row (surfaced 2026-08-27) and so does not
list it at all, while report/findings.jsonl -- "the artifact of record" per that same file's
2026-08-26 revision -- does. This module reads findings.jsonl mechanically and therefore
reports the row; it does not silently drop a ledger entry to match an older hand count. See
this project's RESUME-STATE.md item R8 and R2, which track the reconciliation; this script
does not attempt it and does not edit either document.

Two output formats, one set of rows, matching CLAUDE.md's "paper/tables/ is generated only":
a LaTeX booktabs fragment (paper/tables/table3_findings_totals.tex, sized for a single IEEE
column, dropped in place of the tab:table3 placeholder in paper/latex/main.tex) and a Markdown
table (paper/tables/table3_findings_totals.md, dropped in place of the Table III stub in
paper/main.md sec IX). Neither this script nor its tests edit either manuscript file.

`--verify` matches analysis/score_at_risk.py's convention: re-derive both files from
report/findings.jsonl and the static MedAgentBench/AgentDojo-Phantom-Effect constants below,
diff against what is on disk, exit non-zero on any mismatch.

Usage:
    python report/render.py               # write paper/tables/table3_findings_totals.{tex,md}
    python report/render.py --verify       # re-derive and diff; exit 0 iff clean
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FINDINGS_JSONL = PROJECT_ROOT / "report" / "findings.jsonl"
OUT_TEX = PROJECT_ROOT / "paper" / "tables" / "table3_findings_totals.tex"
OUT_MD = PROJECT_ROOT / "paper" / "tables" / "table3_findings_totals.md"

# CLAUDE.md "Grounding tiers": headline-eligible iff the provenance surface is agent-visible.
# maintainer_annotated and inferred are their own tiers and never enter the headline count.
HEADLINE_TIER = "agent_visible"

# "toy" is the synthetic regression domain used to debug the detector independently of
# benchmark quirks, not one of the four audited benchmarks (FINDINGS-VERIFIED.md "A framing
# error to stop repeating": "31 contracts across three audited benchmarks, plus 11 toy
# contracts"). It is deliberately excluded from Table III.
LEDGER_BENCHMARKS = ["medagentbench", "tau2-bench", "agentdojo", "mm-toolsandbox"]

DISPLAY_NAME = {
    "medagentbench": "MedAgentBench",
    "tau2-bench": "tau2-bench",
    "agentdojo": "AgentDojo",
    "mm-toolsandbox": "MM-ToolSandbox",
}

DEFECT_CLASS_DISPLAY = {
    "unenforced_precondition": "Unenforced Precondition",
    "partial_effect": "Partial Effect",
    "ignored_argument": "Ignored Argument",
    "phantom_effect": "Phantom Effect",
    "invariant_break": "Invariant Break",
    "reset_leak": "Reset Leak",
}

# Why a class is reported but excluded from the headline, keyed by the ledger's own
# headline_tier value. Only used for classes that HAVE a ledger row; classes with no ledger
# row at all (AgentDojo Phantom Effect, MedAgentBench's two static classes) carry their own
# reason string directly, below.
TIER_EXCLUSION_REASON = {
    "maintainer_annotated": "maintainer-annotated (grounded in a logger line the agent "
                            "never sees, not agent-visible)",
    "inferred": "inferred; unadjudicated candidate (annotation-protocol adjudication "
                "pending -- FINDINGS-VERIFIED.md “Candidates, not yet confirmed”)",
}

# Compact one-word/one-phrase version of the same exclusion, for the table's single-line note.
SHORT_TIER_EXCLUSION_REASON = {
    "maintainer_annotated": "maintainer-annotated",
    "inferred": "unadjudicated candidate",
}


@dataclass(frozen=True)
class ClassEntry:
    """One defect class reported against one benchmark."""
    name: str            # display name, e.g. "Phantom Effect"
    headline: bool       # True iff at least one instance is agent_visible
    tools: tuple         # tool names implicated (for cross-checking independent_implementations)
    reason: str          # full grounding tier / exclusion reason, or "agent_visible" if headline
    source: str          # where this class entry comes from
    short_reason: str = ""  # compact exclusion label for the table's one-line note; only
                             # meaningful when headline is False. Falls back to `reason` if unset.


@dataclass(frozen=True)
class BenchmarkRow:
    benchmark: str                 # internal key, e.g. "tau2-bench"
    tools_audited: int
    mutating_tools: int
    independent_implementations: int
    classes: tuple                 # tuple[ClassEntry, ...], stable order
    source: str

    @property
    def display_name(self) -> str:
        return DISPLAY_NAME[self.benchmark]

    @property
    def classes_reported(self) -> int:
        return len(self.classes)

    @property
    def classes_headline(self) -> int:
        return sum(1 for c in self.classes if c.headline)

    def to_dict(self) -> dict:
        return {
            "benchmark": self.benchmark,
            "tools_audited": self.tools_audited,
            "mutating_tools": self.mutating_tools,
            "independent_implementations": self.independent_implementations,
            "classes_reported": self.classes_reported,
            "classes_headline": self.classes_headline,
            "classes": [
                {
                    "name": c.name,
                    "headline": c.headline,
                    "tools": list(c.tools),
                    "reason": c.reason,
                    "short_reason": c.short_reason,
                    "source": c.source,
                }
                for c in self.classes
            ],
            "source": self.source,
        }


# ---------------------------------------------------------------------------------------------
# MedAgentBench -- static, no adapter, zero findings.jsonl rows. Every number below is cited.
# ---------------------------------------------------------------------------------------------

# ARCHITECTURE-FINAL.md "Realistic tool counts": "MedAgentBench: 3 tool definitions but ONE
# unique code path -- all three POST tools route through the same branch. The honest number
# for MedAgentBench is one mutating behavior." PAPER-OUTLINE.md C13 (VERIFIED) and
# paper/main.md's own findings table both cite the same fact ("three tool definitions, one
# code path", __init__.py:85-91). This is the MedAgentBench instantiation of the reporting
# rule this whole table exists to enforce: three advertised tools, one implementation.
MEDAGENTBENCH_TOOLS_AUDITED = 3
MEDAGENTBENCH_MUTATING_TOOLS = 3
MEDAGENTBENCH_INDEPENDENT_IMPLEMENTATIONS = 1
MEDAGENTBENCH_SOURCE = (
    "FINDINGS-VERIFIED.md Findings 1 and 4; ARCHITECTURE-FINAL.md “Realistic tool "
    "counts” (static case study; no adapter, no contract, zero findings.jsonl rows)"
)
MEDAGENTBENCH_CLASSES = (
    ClassEntry(
        name="Phantom Effect",
        headline=True,
        tools=("post_dispatch",),
        reason="agent_visible (prompt_template, tool_return)",
        source="FINDINGS-VERIFIED.md Finding 1 (__init__.py:85-91)",
    ),
    ClassEntry(
        name="Ungrounded Oracle",
        headline=False,
        tools=("post_dispatch",),
        reason="evaluator-layer property, not one of the six tool-layer classes",
        source="FINDINGS-VERIFIED.md Finding 4 (refsol.py, SHA-256-pinned)",
        short_reason="evaluator-layer, not tool-layer",
    ),
)

# AgentDojo's Phantom Effect cell never fires under the shipped fixture: the contract is
# correct (success_signal.biconditional: true) but transaction id 7 already carries
# recurring: False, so the two effect halves are demonstrated in separate probe calls and the
# biconditional re-tag needs them simultaneous. No VIOLATES row for this class exists anywhere
# in findings.jsonl. Reported here from the narrative record only, so a reader is told it was
# looked for and did not fire, rather than left to notice its absence from the ledger.
AGENTDOJO_SUPPLEMENTAL_CLASSES = (
    ClassEntry(
        name="Phantom Effect",
        headline=False,
        tools=("update_scheduled_transaction",),
        reason="contract correct (success_signal.biconditional); re-tag never fires -- the "
               "banking fixture never trips both effect halves in one call",
        source="FINDINGS-VERIFIED.md “Why the fifth cell went” (no ledger row)",
        short_reason="fixture never trips biconditional",
    ),
)

SUPPLEMENTAL_CLASSES = {
    "agentdojo": AGENTDOJO_SUPPLEMENTAL_CLASSES,
}


# ---------------------------------------------------------------------------------------------
# Ledger-derived rows
# ---------------------------------------------------------------------------------------------

def load_findings(path: Path = FINDINGS_JSONL) -> list:
    rows = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def build_ledger_row(benchmark: str, all_rows: list) -> BenchmarkRow:
    bench_rows = [r for r in all_rows if r["benchmark"] == benchmark]
    tools = sorted({r["tool"] for r in bench_rows})
    violates = [r for r in bench_rows if r["verdict"] == "VIOLATES"]
    impl_tools = sorted({r["tool"] for r in violates})

    # class name -> (headline, tools seen, reason, short_reason) for the winning instance
    by_class: dict = {}
    for r in violates:
        cname = DEFECT_CLASS_DISPLAY.get(r["defect_class"], r["defect_class"] or "unclassified")
        tier = r["headline_tier"]
        is_headline = tier == HEADLINE_TIER
        prior = by_class.get(cname)
        tool_set = set(prior[1]) if prior else set()
        tool_set.add(r["tool"])
        was_headline = prior[0] if prior else False
        # a class is headline the moment ANY instance is agent_visible; keep that reason once won
        if is_headline or was_headline:
            reason = "agent_visible"
            short_reason = ""
            headline = True
        else:
            reason = TIER_EXCLUSION_REASON.get(tier, f"headline_tier={tier}")
            short_reason = SHORT_TIER_EXCLUSION_REASON.get(tier, tier)
            headline = False
        by_class[cname] = (headline, tool_set, reason, short_reason)

    classes = [
        ClassEntry(
            name=cname,
            headline=headline,
            tools=tuple(sorted(tool_set)),
            reason=reason,
            source="report/findings.jsonl",
            short_reason=short_reason,
        )
        for cname, (headline, tool_set, reason, short_reason) in by_class.items()
    ]

    for supp in SUPPLEMENTAL_CLASSES.get(benchmark, ()):
        if supp.name not in by_class:
            classes.append(supp)

    classes.sort(key=lambda c: c.name)

    n_total = len(bench_rows)
    n_violates = len(violates)
    return BenchmarkRow(
        benchmark=benchmark,
        tools_audited=len(tools),
        mutating_tools=len(tools),
        independent_implementations=len(impl_tools),
        classes=tuple(classes),
        source=f"report/findings.jsonl ({n_total} rows, {n_violates} VIOLATES)",
    )


def build_medagentbench_row() -> BenchmarkRow:
    return BenchmarkRow(
        benchmark="medagentbench",
        tools_audited=MEDAGENTBENCH_TOOLS_AUDITED,
        mutating_tools=MEDAGENTBENCH_MUTATING_TOOLS,
        independent_implementations=MEDAGENTBENCH_INDEPENDENT_IMPLEMENTATIONS,
        classes=MEDAGENTBENCH_CLASSES,
        source=MEDAGENTBENCH_SOURCE,
    )


def build_rows() -> list:
    findings = load_findings()
    rows = []
    for benchmark in LEDGER_BENCHMARKS:
        if benchmark == "medagentbench":
            rows.append(build_medagentbench_row())
        else:
            rows.append(build_ledger_row(benchmark, findings))
    return rows


# ---------------------------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------------------------

def _excluded_note(rows: list) -> str:
    """One compact sentence naming every reported-but-excluded class, so a reader is told
    rather than left to subtract classes_reported - classes_headline (RESUME-STATE.md R2)."""
    parts = []
    for row in rows:
        for c in row.classes:
            if not c.headline:
                label = c.short_reason or c.reason
                parts.append(f"{row.display_name} {c.name} ({label})")
    return "Excluded (reported, not headline): " + "; ".join(parts) + "."


def render_markdown(rows: list) -> str:
    lines = []
    lines.append("| Benchmark | Tools audited | Mutating | Independent impl. | Classes reported (headline) | Source |")
    lines.append("|---|---:|---:|---:|---:|---|")
    tot_tools = tot_mut = tot_impl = tot_reported = tot_headline = 0
    for row in rows:
        lines.append(
            f"| {row.display_name} | {row.tools_audited} | {row.mutating_tools} | "
            f"{row.independent_implementations} | {row.classes_reported} ({row.classes_headline}) | "
            f"{row.source} |"
        )
        tot_tools += row.tools_audited
        tot_mut += row.mutating_tools
        tot_impl += row.independent_implementations
        tot_reported += row.classes_reported
        tot_headline += row.classes_headline
    lines.append(
        f"| **Total** | **{tot_tools}** | **{tot_mut}** | **{tot_impl}** | "
        f"**{tot_reported} ({tot_headline})** | |"
    )
    lines.append("")
    lines.append(_excluded_note(rows))
    return "\n".join(lines) + "\n"


def _tex_escape(s: str) -> str:
    return s.replace("_", r"\_").replace("&", r"\&")


def render_latex(rows: list) -> str:
    tot_tools = sum(r.tools_audited for r in rows)
    tot_mut = sum(r.mutating_tools for r in rows)
    tot_impl = sum(r.independent_implementations for r in rows)
    tot_reported = sum(r.classes_reported for r in rows)
    tot_headline = sum(r.classes_headline for r in rows)

    body_lines = []
    for row in rows:
        body_lines.append(
            f"{_tex_escape(row.display_name)} & {row.tools_audited} & {row.mutating_tools} & "
            f"{row.independent_implementations} & {row.classes_reported} ({row.classes_headline}) \\\\"
        )

    note = _excluded_note(rows)
    note = _tex_escape(note)

    lines = [
        "% Generated by report/render.py -- DO NOT HAND-EDIT (CLAUDE.md: paper/tables/ is",
        "% generated only). Re-run: python report/render.py",
        "\\begin{table}[t]",
        "\\caption{Per-benchmark audit totals. \emph{Classes} counts distinct defect classes observed per benchmark, including one unadjudicated candidate (tau2-bench \texttt{suspend\_line}); the parenthetical is the headline-eligible subset.}",
        "\\label{tab:table3}",
        "\\centering",
        "\\small",
        "\\begin{tabular}{@{}lrrrr@{}}",
        "\\toprule",
        "Benchmark & Tools & Mut. & Impl. & Classes (HL) \\\\",
        "\\midrule",
    ]
    lines.extend(body_lines)
    lines.append("\\midrule")
    lines.append(
        f"\\textbf{{Total}} & \\textbf{{{tot_tools}}} & \\textbf{{{tot_mut}}} & "
        f"\\textbf{{{tot_impl}}} & \\textbf{{{tot_reported} ({tot_headline})}} \\\\"
    )
    lines.append("\\bottomrule")
    lines.append("\\end{tabular}")
    lines.append("")
    lines.append(f"\\footnotesize {note}")
    lines.append("\\end{table}")
    return "\n".join(lines) + "\n"


def write_outputs(rows: list, out_tex: Path = OUT_TEX, out_md: Path = OUT_MD) -> None:
    out_tex.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_tex.write_text(render_latex(rows), encoding="utf-8")
    out_md.write_text(render_markdown(rows), encoding="utf-8")


# ---------------------------------------------------------------------------------------------
# CLI / verify
# ---------------------------------------------------------------------------------------------

def verify(out_tex: Path = OUT_TEX, out_md: Path = OUT_MD) -> int:
    """Re-derive both files from report/findings.jsonl (plus the static constants above) and
    diff against what is on disk. Exits non-zero on any mismatch, matching
    analysis/score_at_risk.py's --verify convention."""
    if not out_tex.exists() or not out_md.exists():
        missing = [str(p) for p in (out_tex, out_md) if not p.exists()]
        print(f"VERIFY FAILED: missing {missing}", file=sys.stderr)
        return 1

    rows = build_rows()
    fresh_tex = render_latex(rows)
    fresh_md = render_markdown(rows)
    on_disk_tex = out_tex.read_text(encoding="utf-8")
    on_disk_md = out_md.read_text(encoding="utf-8")

    ok = True
    if fresh_tex != on_disk_tex:
        print(f"VERIFY FAILED: {out_tex} does not match a fresh render", file=sys.stderr)
        ok = False
    if fresh_md != on_disk_md:
        print(f"VERIFY FAILED: {out_md} does not match a fresh render", file=sys.stderr)
        ok = False

    if ok:
        print(f"VERIFY OK: {len(rows)} benchmark rows match {out_tex.name} and {out_md.name}")
        return 0
    return 1


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--out-tex", type=Path, default=OUT_TEX, help="output LaTeX path")
    parser.add_argument("--out-md", type=Path, default=OUT_MD, help="output Markdown path")
    parser.add_argument(
        "--verify", action="store_true",
        help="re-derive and diff against --out-tex/--out-md instead of writing",
    )
    args = parser.parse_args(argv)

    if args.verify:
        return verify(args.out_tex, args.out_md)

    rows = build_rows()
    write_outputs(rows, args.out_tex, args.out_md)
    print(f"wrote {len(rows)} benchmark rows to {args.out_tex} and {args.out_md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
