"""Real-corpus target enumeration for the mutation-validation experiment
(experiments/detector_analysis_plan.md, ARCHITECTURE-FINAL.md sec 5).

This module answers exactly one question per benchmark: "which contracted tools are eligible for
the mutation corpus, and how do I get a live Adapter + a scenario_id + this tool's own module
source text for one?" It does not itself enumerate mutation sites or apply operators -- that is
still mutation/sites.py's and mutation/operators.py's job, untouched. This module is new plumbing
the pre-registered plan anticipated needing (sec 3: "sites are enumerated ... across all
conformant tools", "the tools carrying confirmed findings are excluded") without specifying the
mechanism, because the plan is a statistics/scoring contract, not an implementation one.

**Anchor exclusion (sec 3) is read from report/findings.jsonl, not hand-copied.** Any
(benchmark, tool) pair with at least one VIOLATES row is an anchor case and is excluded --
mutating it would let the checker rediscover a defect it already found for a different reason.
This keeps the exclusion list grounded in the actual artifact of record (FINDINGS-VERIFIED.md
says the same thing in prose; this reads the machine-readable copy) and automatically stays
correct if findings.jsonl is regenerated.

Repo-root mapping is a literal table (three entries) because there are exactly three real
benchmarks with a subprocess adapter, matching dynamic/harness.py's own REPO_ROOT_BY_BENCHMARK
table for the same reason (no generic rule to derive one from the other without guessing).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from core.model import Contract

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONTRACTS_ROOT = PROJECT_ROOT / "spec" / "contracts"
FINDINGS_PATH = PROJECT_ROOT / "report" / "findings.jsonl"

REPO_ROOT_BY_BENCHMARK = {
    "tau2-bench": PROJECT_ROOT / "repos" / "tau2",
    "agentdojo": PROJECT_ROOT / "repos" / "agentdojo",
    "mm-toolsandbox": PROJECT_ROOT / "repos" / "mmtoolsandbox",
    "toy": PROJECT_ROOT,  # toy/bank.py's path in the contract is already project-root-relative
}

CONTRACT_DIR_BY_BENCHMARK = {
    "tau2-bench": "tau2",
    "agentdojo": "agentdojo",
    "mm-toolsandbox": "mmtoolsandbox",
    "toy": "toy",
}

__all__ = [
    "RealTarget",
    "anchor_exclusions",
    "load_contracts",
    "resolve_domain",
    "read_module_source",
    "enumerate_eligible_targets",
]


@dataclass(frozen=True)
class RealTarget:
    """Everything mutation/real_corpus.py needs about one eligible tool: which contract, which
    live scenario_id (domain/suite) to build an Adapter env against, and the absolute path to its
    own module source file (read-only; never written)."""

    benchmark: str
    tool: str
    contract: Contract
    scenario_id: str
    source_path: Path
    is_toy: bool


def anchor_exclusions(findings_path: Path = FINDINGS_PATH) -> "dict[str, set[str]]":
    """(benchmark -> {tool, ...}) for every tool with at least one VIOLATES row in
    report/findings.jsonl -- sec 3's "tools carrying confirmed findings are excluded"."""
    out: dict[str, set[str]] = {}
    if not findings_path.exists():
        return out
    with open(findings_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("verdict") == "VIOLATES":
                out.setdefault(row["benchmark"], set()).add(row["tool"])
    return out


def load_contracts(benchmark: str) -> "list[Contract]":
    contracts_dir = CONTRACTS_ROOT / CONTRACT_DIR_BY_BENCHMARK[benchmark]
    return [Contract.from_yaml(p) for p in sorted(contracts_dir.glob("*.yaml"))]


_DOMAIN_FROM_PATH_RE = re.compile(r"domains/([^/]+)/")


def resolve_domain(benchmark: str, contract: Contract, domain_by_tool: "Optional[dict[str, str]]" = None) -> Optional[str]:
    """The scenario_id `Adapter.fresh_env()` expects for `contract.tool`.

    tau2-bench: several tool names recur across domains (adapters/tau2.py's `source()` docstring)
    but a single CONTRACT is authored against one specific domain's tools.py, and that domain
    name is baked into `contract.source.file` (".../domains/<domain>/tools.py") -- read off the
    path directly rather than hand-maintaining a second tool->domain table that could drift from
    what the contract was actually authored against (dynamic/harness.py's TAU2_DOMAIN_BY_TOOL
    does the latter, but only for the 2 tools its milestone shipped; this generalises to all 19
    without introducing a second hand-maintained mapping to keep in sync).

    AgentDojo / MM-ToolSandbox: neither has cross-domain name reuse among its contracted tools
    (dynamic/harness.py's `_iter_contracts_by_live_domain` docstring), so the live adapter's own
    `list_tools()` domain field is authoritative -- pass it in as `domain_by_tool`.

    toy: exactly one scenario, "default", regardless of tool.
    """
    if benchmark == "toy":
        return "default"
    if benchmark == "tau2-bench":
        m = _DOMAIN_FROM_PATH_RE.search(contract.source.file)
        return m.group(1) if m else None
    return (domain_by_tool or {}).get(contract.tool)


def read_module_source(benchmark: str, contract: Contract) -> str:
    repo_root = REPO_ROOT_BY_BENCHMARK[benchmark]
    path = repo_root / contract.source.file
    return path.read_text(encoding="utf-8")


def enumerate_eligible_targets(domain_by_tool: "dict[str, dict[str, str]]") -> "list[RealTarget]":
    """Every contracted tool across all four benchmarks, minus anchor exclusions (sec 3).

    `domain_by_tool` is `{"agentdojo": {tool: domain, ...}, "mm-toolsandbox": {...}}` -- built by
    the caller from each live adapter's `list_tools()` (see `resolve_domain`'s docstring for why
    tau2/toy don't need an entry). Callers that only need enumeration without spinning up the
    agentdojo/mm-toolsandbox subprocesses can pass `{}` and accept that those two benchmarks'
    targets will be skipped (reported, not silently dropped -- see mutation/real_corpus.py).
    """
    exclusions = anchor_exclusions()
    targets: list[RealTarget] = []
    skipped: list[tuple] = []
    for benchmark in ("toy", "tau2-bench", "agentdojo", "mm-toolsandbox"):
        is_toy = benchmark == "toy"
        for contract in load_contracts(benchmark):
            if contract.tool in exclusions.get(benchmark, set()):
                continue
            domain = resolve_domain(benchmark, contract, domain_by_tool.get(benchmark))
            if domain is None:
                skipped.append((benchmark, contract.tool, "no domain resolved"))
                continue
            try:
                source_path = REPO_ROOT_BY_BENCHMARK[benchmark] / contract.source.file
                if not source_path.exists():
                    skipped.append((benchmark, contract.tool, f"source file not found: {source_path}"))
                    continue
            except Exception as e:  # noqa: BLE001
                skipped.append((benchmark, contract.tool, str(e)))
                continue
            targets.append(
                RealTarget(
                    benchmark=benchmark, tool=contract.tool, contract=contract,
                    scenario_id=domain, source_path=source_path, is_toy=is_toy,
                )
            )
    enumerate_eligible_targets.last_skipped = skipped  # exposed for the caller's build log
    return targets
