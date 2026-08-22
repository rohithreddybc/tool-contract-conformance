"""Score-at-risk analysis -- the paper's headline contribution.

ARCHITECTURE-FINAL.md sec 1 ("score-at-risk analysis... must be section 3 of the paper, not a
script in an appendix") and sec 4 ("Score-at-risk analysis (analysis/score_at_risk.py)").
REVIEW-RESPONSE.md W2 (oracle-grounding classification, never print zero for a transcript-
grounded oracle) and W6 (two different "affected task" definitions; state the bound's
direction). FINDINGS-VERIFIED.md carries the seven confirmed findings this module traces.

Three static steps, no model in the loop, no agent runs (ARCHITECTURE-FINAL.md sec 4 and sec 10
"Zero LLM" bucket, which explicitly lists "score-at-risk analysis" and "probes" together):

  1. Defect -> field.   From a contract's VIOLATES effect/precondition clauses, extract the
     state paths the tool should have written but did not, or wrote unconditionally when a
     precondition should have blocked the write. Extracted from the predicate's own AST via
     core/predicates.py's compile_predicate() -- never by pattern-matching the predicate string.
  2. Field -> evaluator. Parse the benchmark's own evaluation code (its grader functions, task
     assertion functions, or DB-hash mechanism) for the state fields it reads, via Python's
     `ast` module against the pinned grader/tool source -- never by regexing it. This step also
     produces the per-task oracle-grounding classification W2 requires: state_grounded,
     transcript_grounded, or mixed.
  3. Evaluator -> tasks. Enumerate tasks whose verdict depends on any field in the Step
     1 / Step 2 intersection, from the benchmark's own pinned task-definition files.

Everything here reads only pinned, offline files: contract YAMLs (spec/contracts/tau2/), the
tau2 source snapshot (.tau2-src-c3398666/), the tau2 task JSON files inside it, the pinned
MedAgentBench grader (repro/env/refsol.py, sha256-pinned) and its task file
(repos/medagentbench/), and the AgentDojo v1 user-task suites (repos/agentdojo/). No network
call, no subprocess, no tau2 venv, no model. `--verify` re-derives every row from these same
files and diffs against what is on disk, for the project's numbers audit.

WHERE THIS MODULE DEVIATES FROM A NAIVE READING OF ARCHITECTURE-FINAL.md SEC 4, AND WHY
--------------------------------------------------------------------------------------------
Sec 4 says "Field -> evaluator: parse the benchmark's own evaluation code for the state fields
it reads." Read literally and mechanically, this only works for tau2, where the evaluator's own
predicates and the contract's own predicates are drawn from the same well-typed pydantic DB and
a single canonical AST-walkable representation covers both. Two things about the *real* graders
did not survive contact with the code as cleanly as a one-line spec sentence implies:

  * MedAgentBench's write graders (FINDINGS-VERIFIED.md Finding 4) read a reconstructed
    transcript, not the FHIR server -- REVIEW-RESPONSE.md W2's whole point. For those tasks,
    "the field the evaluator reads" and "the field the tool should have written" are the *same*
    set (the grader literally checks the payload the agent claims it POSTed), so a naive
    field-intersection would report near-100% "at risk" -- exactly the misleading opposite of
    the true 0%-state-grounded reading this module now prints instead. Field intersection alone
    cannot distinguish "the evaluator reads this field from live state" from "the evaluator reads
    this field from the agent's own claim about what it did"; that is a provenance question
    about the read site, not a set-membership question about field names, so this module adds a
    read-site provenance classification (state_grounded / transcript_grounded / mixed) as a
    first-class output alongside the field intersection, per task, per grader function.
  * AgentDojo (repos/AGENTDOJO-SPIKE.md) has no Contract YAML in this milestone (contract
    authoring for benchmarks 3+ is future work) and no `mutates_state` tag on its tools, so Step
    1 cannot start from a shipped contract clause the way it does for tau2. This module derives
    AgentDojo's defect fields directly from FINDINGS-VERIFIED.md Finding 5 / Finding 6's own
    source citations instead (KNOWN_AGENTDOJO_DEFECTS below) and is explicit that this is a
    narrower, manually-seeded substitute for Step 1's contract-driven derivation -- not a claim
    that AgentDojo has been contract-audited to the same standard as tau2.
  * tau2's own evaluator (evaluator/evaluator_env.py) is not one mechanism but two, and they
    have very different read granularity: DB-hash compares `self.db.model_dump()` end to end
    (toolkit.py:242-244) -- i.e. it reads *everything*, so any field a defective tool writes is
    trivially "read" by it -- while `env_assertions` call one named, statically-readable Python
    function per task that reads specific fields. This module reports both mechanisms
    separately, tags the whole-DB-hash match "whole_state_hash" (the weakest, most
    over-approximate confidence tier), and tags an env_assertion match "exact_field" or
    "collection_only" depending on whether the matched name is the specific written attribute or
    only its containing collection. None of this is a claim that every at-risk task is actually
    misgraded (ARCHITECTURE-FINAL.md sec 4, REVIEW-RESPONSE.md W6): it is an over-approximation
    of misgrading via the state-dependency mechanism only, and only for state-grounded oracles.

W6's two "affected task" populations are both emitted: `at_risk` (this module's field-dependency
population) and `in_experiment_frame` (the agent experiment's stricter rule -- gold solution
invokes a tool with a confirmed VIOLATES clause, ARCHITECTURE-FINAL.md sec 4). Every summary row
also reports `experiment_frame_subset_of_at_risk`, a mechanical containment check, not an
inference -- see verify().
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

from core.model import Clause, Contract, HeadlineTier, headline_tier
from core.predicates import compile_predicate
from core.verdict import DefectClass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPORT_PATH = PROJECT_ROOT / "report" / "score_at_risk.jsonl"

TAU2_SRC = PROJECT_ROOT / ".tau2-src-c3398666"
TAU2_DATA = TAU2_SRC / "data" / "tau2" / "domains"
TAU2_TOOLS_SRC = TAU2_SRC / "src" / "tau2" / "domains"
TAU2_CONTRACTS = PROJECT_ROOT / "spec" / "contracts" / "tau2"
TAU2_DOMAIN_TASK_FILE = {
    # tau2/domains/{airline,telecom}/utils.py: both AIRLINE_TASK_SET_PATH and
    # TELECOM_TASK_SET_PATH point at plain "tasks.json" -- tasks_small.json/tasks_full.json are
    # commented "Not used anymore" in telecom/utils.py. This is the file the harness actually
    # loads by default; verified by reading both utils.py modules at c3398666, not assumed.
    "airline": TAU2_DATA / "airline" / "tasks.json",
    "telecom": TAU2_DATA / "telecom" / "tasks.json",
}
TAU2_DOMAIN_TOOLKIT = {
    "airline": (TAU2_TOOLS_SRC / "airline" / "tools.py", "AirlineTools"),
    "telecom": (TAU2_TOOLS_SRC / "telecom" / "tools.py", "TelecomTools"),
}

MEDAGENTBENCH_ROOT = PROJECT_ROOT / "repos" / "medagentbench"
MEDAGENTBENCH_REFSOL = PROJECT_ROOT / "repro" / "env" / "refsol.py"
MEDAGENTBENCH_TASKS = MEDAGENTBENCH_ROOT / "data" / "medagentbench" / "test_data_v2.json"
MEDAGENTBENCH_EVAL = MEDAGENTBENCH_ROOT / "src" / "server" / "tasks" / "medagentbench" / "eval.py"

AGENTDOJO_ROOT = PROJECT_ROOT / "repos" / "agentdojo" / "src" / "agentdojo" / "default_suites" / "v1"
AGENTDOJO_TASKS_FILE = {
    "banking": AGENTDOJO_ROOT / "banking" / "user_tasks.py",
    "travel": AGENTDOJO_ROOT / "travel" / "user_tasks.py",
}


# =============================================================================================
# Generic AST utilities, shared across all three benchmarks below. None of this is benchmark-
# specific; the benchmark sections only supply file paths, class/root names, and known defects.
# =============================================================================================


def _literal_key(node: ast.AST) -> Optional[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _unwind_subscript_chain(node: ast.AST) -> tuple[Optional[str], tuple]:
    """(root_name, path_segments) for a plain Subscript/Name chain -- no comprehension-binding
    awareness (see extract_state_paths below for that). '*' stands in for a non-constant key.
    Suitable for source that indexes directly, e.g. `payload['resourceType']`."""
    if isinstance(node, ast.Name):
        return node.id, ()
    if isinstance(node, ast.Subscript):
        root, path = _unwind_subscript_chain(node.value)
        if root is None:
            return None, ()
        key = _literal_key(node.slice)
        return root, path + (key if key is not None else "*",)
    return None, ()


def extract_state_paths(predicate_src: str, roots: frozenset) -> set[tuple]:
    """Walk a contract predicate's compiled, attribute-rewritten AST (core/predicates.py's
    compile_predicate() already turns every `.attr` into a constant-key Subscript, so dotted
    access and bracket indexing look identical here) and collect every concrete path rooted at
    one of `roots` as a tuple (root, seg1, seg2, ...), '*' standing in for a subscript key that
    is not a literal constant.

    Comprehension-binding aware: `for l2 in post.lines` followed by `l2.data_refueling_gb`
    resolves to `('post', 'lines', '*', 'data_refueling_gb')`, not a bare, disconnected
    `('post', 'lines')` plus an untraceable `l2.data_refueling_gb` -- refuel_data.yaml's effect
    clauses depend on exactly this pattern (a comprehension variable bound to a `post.<field>`
    element, then attribute-accessed), and a version of this walker that only followed literal
    `pre.`/`post.`-rooted chains at the top level would silently miss `data_refueling_gb` and
    `total_due` entirely, reporting only the containing collections. Verified during development
    against both shipped contracts (see tests/test_score_at_risk.py) before being trusted here.

    Recurses into non-constant subscript keys too, since a key can itself be a rooted expression
    (e.g. `available_seats[pre.reservations[args.reservation_id].cabin]` in
    cancel_reservation.yaml) -- that nested path is collected as its own, separate entry.
    """
    compiled = compile_predicate(predicate_src)
    found: set[tuple] = set()

    def resolve(node: ast.AST, bindings: dict) -> tuple[Optional[str], tuple]:
        if isinstance(node, ast.Name):
            if node.id in bindings:
                return bindings[node.id]
            return node.id, ()
        if isinstance(node, ast.Subscript):
            root, path = resolve(node.value, bindings)
            if root is None:
                return None, ()
            key = _literal_key(node.slice)
            return root, path + (key if key is not None else "*",)
        return None, ()

    def walk(node: ast.AST, bindings: dict) -> None:
        if isinstance(node, ast.Subscript):
            root, path = resolve(node, bindings)
            if root in roots and path:
                found.add((root,) + path)
            walk(node.value, bindings)
            walk(node.slice, bindings)
            return
        if isinstance(node, (ast.GeneratorExp, ast.ListComp, ast.SetComp, ast.DictComp)):
            local = dict(bindings)
            for gen in node.generators:
                walk(gen.iter, local)
                iter_root, iter_path = resolve(gen.iter, local)
                if isinstance(gen.target, ast.Name) and iter_root is not None:
                    local[gen.target.id] = (iter_root, iter_path + ("*",))
                for cond in gen.ifs:
                    walk(cond, local)
            if isinstance(node, ast.DictComp):
                walk(node.key, local)
                walk(node.value, local)
            else:
                walk(node.elt, local)
            return
        for child in ast.iter_child_nodes(node):
            walk(child, bindings)

    walk(compiled.tree, {})
    return found


def _maximal_paths(paths: set[tuple]) -> list[tuple]:
    """Drop any path that is a strict prefix of another path in the set -- display
    de-duplication only; extract_state_paths finds every prefix too because resolve() unwinds
    the whole chain on the way back out of each Subscript."""
    result = [p for p in paths if not any(len(q) > len(p) and q[: len(p)] == p for q in paths)]
    return sorted(result)


def leaf_field_names(paths: set[tuple], root: str) -> frozenset:
    """Every literal (non-'*') segment in a path rooted at `root` -- the matching granularity
    used against evaluator read sites, since the evaluator side is parsed from arbitrary Python
    (not the predicate DSL), so a full static path can't always be recovered there."""
    names: set = set()
    for p in paths:
        if p and p[0] == root:
            names.update(seg for seg in p[1:] if seg != "*")
    return frozenset(names)


def collection_names(paths: list[tuple], root: str) -> frozenset:
    """The first segment after `root` for each maximal path -- the top-level DB/state collection
    a defect's write paths live under (e.g. 'lines', 'bills'), used to distinguish a strong
    'exact_field' evaluator match from a weaker 'collection_only' one."""
    return frozenset(p[1] for p in paths if len(p) > 1 and p[0] == root)


_DOTTED_PATH_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)+$")


@dataclass(frozen=True)
class ReadProfile:
    """What one evaluator function statically appears to read: every `.attr` name it accesses
    (directly, or indirectly via a dotted-path *string* like AgentDojo's DeepDiff keys
    "root.reservation.end_time" -- both count as the function 'mentioning' that field name, so
    both feed the same set here), every function/method name it calls (for helper resolution),
    and every bare Name it references (used for the state-vs-transcript grounding check: does
    this function's body actually use its `pre_environment`/`post_environment`/`model_output`
    parameters, or only declare them?)."""

    attribute_names: frozenset
    called_names: frozenset
    referenced_names: frozenset


def _profile_function(fn: ast.AST) -> ReadProfile:
    attrs, calls, names = set(), set(), set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Attribute):
            attrs.add(node.attr)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                calls.add(node.func.attr)
        elif isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if _DOTTED_PATH_RE.match(node.value):
                attrs.update(node.value.split("."))
    return ReadProfile(frozenset(attrs), frozenset(calls), frozenset(names))


def _direct_function_index(container: ast.AST) -> dict:
    """Direct-child function defs of `container` (a Module or a ClassDef) -- deliberately NOT
    ast.walk, which would also descend into nested classes/functions and silently merge
    same-named methods across unrelated classes. AgentDojo's user_tasks.py defines a `utility`
    method on every task class; ast.walk would collapse them into one index entry keyed
    "utility". Building the index from one container's direct children keeps each task class's
    (or each module's) own functions in their own namespace."""
    return {
        n.name: n
        for n in ast.iter_child_nodes(container)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def transitive_read_profile(name: str, index: dict, *, depth: int = 3, _seen: Optional[set] = None) -> ReadProfile:
    """_profile_function() for `name`, merged with the same for every helper it calls (by bare
    name, or by `self.<name>(...)`/`obj.<name>(...)` attribute), up to `depth` hops, cycle-safe.

    Name-based resolution only -- no type inference, no call-graph disambiguation across
    classes. `index` is always built by _direct_function_index() from exactly one class's or one
    module's own direct children (see call sites below), so within any single call there is
    nothing unrelated for a bare name to collide with; this has been checked by inspection for
    every file this module actually parses (TelecomTools, AirlineTools, refsol.py's module
    scope, and each AgentDojo user_tasks.py's module scope)."""
    seen = _seen if _seen is not None else set()
    if name in seen or name not in index or depth < 0:
        return ReadProfile(frozenset(), frozenset(), frozenset())
    seen.add(name)
    prof = _profile_function(index[name])
    attrs, calls, names = set(prof.attribute_names), set(prof.called_names), set(prof.referenced_names)
    for called in prof.called_names:
        sub = transitive_read_profile(called, index, depth=depth - 1, _seen=seen)
        attrs |= sub.attribute_names
        calls |= sub.called_names
        names |= sub.referenced_names
    return ReadProfile(frozenset(attrs), frozenset(calls), frozenset(names))


@lru_cache(maxsize=None)
def _class_function_index(source_path: str, class_name: str) -> dict:
    tree = ast.parse(Path(source_path).read_text(encoding="utf-8"))
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return _direct_function_index(node)
    raise ValueError(f"class {class_name!r} not found in {source_path}")


@lru_cache(maxsize=None)
def _module_function_index(source_path: str) -> dict:
    tree = ast.parse(Path(source_path).read_text(encoding="utf-8"))
    return _direct_function_index(tree)


# =============================================================================================
# tau2-bench
# =============================================================================================


@dataclass(frozen=True)
class KnownTau2Defect:
    domain: str
    tool: str
    contract_file: str  # relative to TAU2_CONTRACTS
    clause_id: str
    defect_class: DefectClass
    finding_citation: str
    derive_fields_from: str  # "own_clause" (an effect clause) | "tool_effects" (a precondition
    # clause tied to Unenforced Precondition -- the at-risk fields are the writes that land
    # unconditionally, i.e. every effect clause of the same tool)


# Pinned against FINDINGS-VERIFIED.md, re-verified 2026-08-21. Not derived from a findings.jsonl
# (that file does not exist until Gate 3, ARCHITECTURE-FINAL.md sec 7) -- this small, cited,
# hand-checked table is this module's "pinned input" for which clauses are known VIOLATES, the
# same epistemic status as the manually-confirmed findings it cites. Extending it to a future
# findings.jsonl is a mechanical substitution, not a redesign.
KNOWN_TAU2_DEFECTS = (
    KnownTau2Defect(
        domain="airline",
        tool="cancel_reservation",
        contract_file="cancel_reservation.yaml",
        clause_id="eff.seats_released",
        defect_class=DefectClass.PARTIAL_EFFECT,
        finding_citation="FINDINGS-VERIFIED.md Finding 3",
        derive_fields_from="own_clause",
    ),
    KnownTau2Defect(
        domain="telecom",
        tool="refuel_data",
        contract_file="refuel_data.yaml",
        clause_id="pre.line_active",
        defect_class=DefectClass.UNENFORCED_PRECONDITION,
        finding_citation="FINDINGS-VERIFIED.md Finding 2",
        derive_fields_from="tool_effects",
    ),
)


def tau2_defect_write_fields(kd: KnownTau2Defect) -> tuple[frozenset, list[tuple], HeadlineTier]:
    contract = Contract.from_yaml(TAU2_CONTRACTS / kd.contract_file)
    assert contract.tool == kd.tool, f"{kd.contract_file}: tool field {contract.tool!r} != {kd.tool!r}"
    clause = next((c for c in contract.all_clauses() if c.id == kd.clause_id), None)
    if clause is None:
        raise ValueError(f"{kd.contract_file}: no clause {kd.clause_id!r}")

    # check8_passed=True is a documented no-op here, not a bypass: check 8
    # (spec/validate.py check8_agent_visibility) only tests tool_return/prompt_template
    # provenance surfaces. Both clauses this module currently uses are 'docstring'
    # (pre.line_active) or 'maintainer_annotation' (eff.seats_released) -- surfaces check 8
    # never inspects -- so its outcome is irrelevant to headline_tier()'s result for either
    # (see tests/test_model.py's own fixtures for the same equivalence).
    tier = headline_tier(clause, check8_passed=True)

    if kd.derive_fields_from == "own_clause":
        paths = extract_state_paths(clause.predicate, frozenset({"post"}))
    elif kd.derive_fields_from == "tool_effects":
        paths = set()
        for ec in contract.effects:
            paths |= extract_state_paths(ec.predicate, frozenset({"post"}))
    else:
        raise ValueError(kd.derive_fields_from)

    fields = leaf_field_names(paths, "post")
    return fields, _maximal_paths(paths), tier


def _tau2_class_index(domain: str) -> dict:
    source_path, class_name = TAU2_DOMAIN_TOOLKIT[domain]
    return _class_function_index(str(source_path), class_name)


_TAU2_READ_FIELD_CACHE: dict = {}


def tau2_assertion_read_fields(domain: str, func_name: str) -> frozenset:
    key = (domain, func_name)
    if key not in _TAU2_READ_FIELD_CACHE:
        index = _tau2_class_index(domain)
        prof = transitive_read_profile(func_name, index)
        _TAU2_READ_FIELD_CACHE[key] = prof.attribute_names
    return _TAU2_READ_FIELD_CACHE[key]


def _load_tau2_tasks(domain: str) -> list[dict]:
    with open(TAU2_DOMAIN_TASK_FILE[domain], "r", encoding="utf-8") as fh:
        return json.load(fh)


def build_tau2_rows() -> list[dict]:
    rows: list[dict] = []
    for kd in KNOWN_TAU2_DEFECTS:
        fields, max_paths, tier = tau2_defect_write_fields(kd)
        collections = collection_names(max_paths, "post")
        specific_fields = fields - collections  # the field-level names, excluding bare
        # collection names, so a match on e.g. 'bills' alone (an unrelated assertion that
        # merely iterates the same collection) is not conflated with a match on the actually-
        # written attribute (e.g. 'total_due').

        rows.append(
            {
                "kind": "defect",
                "benchmark": "tau2-bench",
                "domain": kd.domain,
                "tool": kd.tool,
                "clause_id": kd.clause_id,
                "defect_class": kd.defect_class.value,
                "headline_tier": tier.value,
                "finding_citation": kd.finding_citation,
                "write_paths": [".".join(str(s) for s in p) for p in max_paths],
                "field_names": sorted(fields),
            }
        )

        tasks = _load_tau2_tasks(kd.domain)
        at_risk_ids: list[str] = []
        experiment_frame_ids: list[str] = []
        for t in tasks:
            task_id = t["id"]
            ec = t.get("evaluation_criteria") or {}
            reward_basis = set(ec.get("reward_basis") or [])
            actions = ec.get("actions") or []
            in_experiment_frame = any(a.get("name") == kd.tool for a in actions)
            if in_experiment_frame:
                experiment_frame_ids.append(task_id)

            site = None
            if "DB" in reward_basis:
                # toolkit.py:242-244 -- get_db_hash() hashes self.db.model_dump(), the ENTIRE
                # domain DB. Any field a defective tool writes is, by construction, read by this
                # mechanism. This is the module's most over-approximate confidence tier,
                # deliberately: it is a bound on the *mechanism*, not a per-field claim.
                site = {"mechanism": "db_hash", "detail": "whole_domain_state", "confidence": "whole_state_hash"}
            if site is None and "ENV_ASSERTION" in reward_basis:
                for ea in ec.get("env_assertions") or []:
                    if ea.get("env_type") != "assistant":
                        continue  # a different DB entirely (telecom's user simulator has its
                        # own TelecomUserDB, ARCHITECTURE-FINAL.md sec 2) -- out of scope for a
                        # defect whose fields live in the agent-facing DB.
                    fn = ea["func_name"]
                    read_fields = tau2_assertion_read_fields(kd.domain, fn)
                    exact = read_fields & specific_fields
                    if exact:
                        site = {
                            "mechanism": "env_assertion",
                            "detail": fn,
                            "confidence": "exact_field",
                            "matched_fields": sorted(exact),
                        }
                        break
                    coll = read_fields & collections
                    if coll and site is None:
                        site = {
                            "mechanism": "env_assertion",
                            "detail": fn,
                            "confidence": "collection_only",
                            "matched_fields": sorted(coll),
                        }
                        # keep scanning this task's remaining assertions for a stronger match
            if site is not None:
                at_risk_ids.append(task_id)
                rows.append(
                    {
                        "kind": "task_verdict",
                        "benchmark": "tau2-bench",
                        "domain": kd.domain,
                        "tool": kd.tool,
                        "clause_id": kd.clause_id,
                        "defect_class": kd.defect_class.value,
                        "task_id": task_id,
                        "at_risk": True,
                        "oracle_grounding": "state_grounded",
                        "evaluator_read_site": site,
                        "in_experiment_frame": in_experiment_frame,
                        "score_at_risk_status": "computed",
                    }
                )

        containment_ok = set(experiment_frame_ids) <= set(at_risk_ids)
        rows.append(
            {
                "kind": "summary",
                "benchmark": "tau2-bench",
                "domain": kd.domain,
                "tool": kd.tool,
                "clause_id": kd.clause_id,
                "defect_class": kd.defect_class.value,
                "headline_tier": tier.value,
                "finding_citation": kd.finding_citation,
                "n_tasks_total": len(tasks),
                "n_at_risk": len(at_risk_ids),
                "n_experiment_frame": len(experiment_frame_ids),
                "experiment_frame_subset_of_at_risk": containment_ok,
                "oracle_grounding": "state_grounded",
                "score_at_risk_status": "computed",
                "bound_direction": (
                    "over-approximation of misgrading via the state-dependency mechanism only; "
                    "not a claim that every at-risk task is actually misgraded "
                    "(ARCHITECTURE-FINAL.md sec 4, REVIEW-RESPONSE.md W6)"
                ),
            }
        )
    return rows


# =============================================================================================
# MedAgentBench
# =============================================================================================


def _medagentbench_index() -> dict:
    return _module_function_index(str(MEDAGENTBENCH_REFSOL))


def medagentbench_oracle_profile(task_func: str, index: dict) -> dict:
    """FINDINGS-VERIFIED.md Finding 4's classification, re-derived from the AST rather than
    quoted -- reproduces Finding 4's own grader table exactly (task3/task8 unconditional
    transcript, task5/task9/task10 conditional/mixed, task4-and-the-remaining-read-tasks no
    write oracle at all).

    The classifying signal is extract_posts() alone: that is the call that reconstructs a
    *write's content* from the agent's transcript, gated on the fabricated "POST request
    accepted" success string (Finding 1) -- the actual construct-validity problem W2 exists to
    surface. check_has_post() is a different thing: several read/answer graders (task1, task2,
    task4, task6, task7) call it only as a negative gate ("the agent must not have attempted a
    POST at all"), which is not a claim about *what* was written and carries none of Finding 4's
    problem -- lumping it in with extract_posts would misclassify five pure read tasks as
    "transcript_grounded" and, worse, would make every send_get_request-using read task
    (task2/4/6/7) look "state_grounded" for a write oracle none of them have. So a grader with no
    extract_posts() call at all is no_write_oracle regardless of what else it calls; a grader
    with extract_posts() and no send_get_request() is transcript_grounded; both is mixed.
    state_grounded never occurs among the current 10 graders -- no grader verifies a write by
    reading it back from FHIR -- and that absence is itself the finding W2 is about, not an
    artifact of this rule.
    """
    prof = _profile_function(index[task_func])
    calls = prof.called_names
    calls_extract_posts = "extract_posts" in calls
    calls_send_get_request = "send_get_request" in calls
    if not calls_extract_posts:
        grounding = "no_write_oracle"
    elif calls_send_get_request:
        grounding = "mixed"
    else:
        grounding = "transcript_grounded"
    return {
        "grounding": grounding,
        "calls_extract_posts": calls_extract_posts,
        "calls_check_has_post": "check_has_post" in calls,
        "calls_send_get_request": calls_send_get_request,
    }


def medagentbench_defect_fields(task_func: str, index: dict) -> frozenset:
    """Literal `payload[...]` keys this grader asserts on -- the FHIR resource fields it treats
    as 'what the write should have produced'. Finding 1: the POST branch is a no-op, so every
    key here is a field the tool should have written and did not."""
    found: set = set()
    for node in ast.walk(index[task_func]):
        if isinstance(node, ast.Subscript):
            root, path = _unwind_subscript_chain(node)
            if root == "payload" and path:
                found.update(seg for seg in path if seg != "*")
    return frozenset(found)


def _verify_medagentbench_dispatch_rule() -> None:
    """FINDINGS-VERIFIED.md Finding 4: eval.py:8-16 dispatches `getattr(refsol, task_id)` where
    `task_id = case_data['id'].split('_')[0]` -- i.e. a task id like "task3_7" is graded by the
    function named "task3". This module relies on that rule to map test_data_v2.json's task ids
    onto refsol.py's function names. Cheap, mechanical drift check against the pinned dispatch
    file rather than an unchecked assumption."""
    src = MEDAGENTBENCH_EVAL.read_text(encoding="utf-8")
    if "case_data['id'].split('_')[0]" not in src or "getattr(refsol, task_id)" not in src:
        raise AssertionError(
            f"{MEDAGENTBENCH_EVAL} no longer matches the dispatch rule this module assumes "
            "(case_data['id'].split('_')[0] -> getattr(refsol, task_id)); re-derive before trusting output"
        )


def build_medagentbench_rows() -> list[dict]:
    _verify_medagentbench_dispatch_rule()
    rows: list[dict] = []
    index = _medagentbench_index()
    tasks = json.loads(MEDAGENTBENCH_TASKS.read_text(encoding="utf-8"))

    by_grader: dict[str, int] = {}
    for t in tasks:
        grader = t["id"].split("_")[0]
        by_grader[grader] = by_grader.get(grader, 0) + 1

    grounding_case_counts = {"state_grounded": 0, "transcript_grounded": 0, "mixed": 0, "no_write_oracle": 0}

    def _sort_key(g: str) -> int:
        return int(g.replace("task", ""))

    for grader in sorted(by_grader, key=_sort_key):
        if grader not in index:
            raise AssertionError(
                f"{MEDAGENTBENCH_TASKS} references task family {grader!r} with no matching "
                f"function in {MEDAGENTBENCH_REFSOL} -- pinned inputs have drifted"
            )
        profile = medagentbench_oracle_profile(grader, index)
        grounding = profile["grounding"]
        n_cases = by_grader[grader]
        grounding_case_counts[grounding] += n_cases

        write_fields = sorted(medagentbench_defect_fields(grader, index)) if grounding != "no_write_oracle" else []

        if grounding == "no_write_oracle":
            status = "not_applicable"
            note = f"{grader} has no write component (read/answer task only); no oracle-grounding claim to make."
        elif grounding == "transcript_grounded":
            status = "undefined_transcript_grounded"
            note = "oracle not state-grounded: score-at-risk undefined, construct-validity finding applies"
        elif grounding == "mixed":
            status = "indeterminate_without_live_state"
            note = (
                "a live FHIR read selects whether a write is required, but the write itself is "
                "graded from the reconstructed transcript, never a live FHIR read; the number of "
                "cases actually exercising the write-grading path is data-dependent and cannot be "
                "determined statically -- FINDINGS-VERIFIED.md Finding 4"
            )
        else:  # state_grounded -- does not occur among the current 10 graders, handled generically
            status = "computed"
            note = ""

        rows.append(
            {
                "kind": "task_verdict",
                "benchmark": "medagentbench",
                "domain": "",
                "tool": "post_write (single code path shared by every POST-tagged tool def, Finding 1)",
                "clause_id": f"eff.fhir_write[{grader}]",
                "defect_class": DefectClass.PHANTOM_EFFECT.value,
                "task_id": grader,
                "n_cases": n_cases,
                "at_risk": None,
                "oracle_grounding": grounding,
                "evaluator_read_site": {
                    "mechanism": f"refsol.{grader}",
                    "detail": (
                        "extract_posts (transcript)"
                        if profile["calls_extract_posts"]
                        else ("send_get_request (state)" if profile["calls_send_get_request"] else "none")
                    ),
                    "confidence": "n/a",
                },
                "in_experiment_frame": None,
                "score_at_risk_status": status,
                "write_field_names": write_fields,
                "note": note,
            }
        )

    n_transcript = grounding_case_counts["transcript_grounded"]
    rows.append(
        {
            "kind": "summary",
            "benchmark": "medagentbench",
            "domain": "",
            "tool": "post_write (single code path, Finding 1)",
            "clause_id": "eff.fhir_write",
            "defect_class": DefectClass.PHANTOM_EFFECT.value,
            "finding_citation": "FINDINGS-VERIFIED.md Finding 1, Finding 4",
            "n_tasks_total": sum(by_grader.values()),
            "oracle_grounding_breakdown": dict(grounding_case_counts),
            "score_at_risk_status": "undefined_transcript_grounded",
            # REVIEW-RESPONSE.md W2's exact mandated verdict shape -- never printed as zero.
            "verdict": (
                f"oracle not state-grounded: {n_transcript} tasks; score-at-risk undefined, "
                "construct-validity finding applies"
            ),
            "bound_direction": (
                "not computable as a state-dependency bound: MedAgentBench's write graders read "
                "the agent's own transcript, never server state (REVIEW-RESPONSE.md W2); reported "
                "as a distinct verdict per the mandated rule, never as zero"
            ),
        }
    )
    return rows


# =============================================================================================
# AgentDojo
# =============================================================================================


@dataclass(frozen=True)
class KnownAgentDojoDefect:
    suite: str
    tool: str
    field: str
    finding_citation: str


# No Contract YAML exists yet for AgentDojo in this milestone (repos/AGENTDOJO-SPIKE.md is a
# go/no-go spike, not contract authoring) -- see module docstring. These two rows are pinned
# directly from FINDINGS-VERIFIED.md's own source citations, the same epistemic status as
# KNOWN_TAU2_DEFECTS above.
KNOWN_AGENTDOJO_DEFECTS = (
    KnownAgentDojoDefect(
        suite="banking",
        tool="update_scheduled_transaction",
        field="recurring",
        finding_citation="FINDINGS-VERIFIED.md Finding 5",
    ),
    KnownAgentDojoDefect(
        suite="travel",
        tool="reserve_car_rental",
        field="end_time",
        finding_citation="FINDINGS-VERIFIED.md Finding 6",
    ),
)


def agentdojo_task_classes(suite: str) -> list[ast.ClassDef]:
    tree = ast.parse(AGENTDOJO_TASKS_FILE[suite].read_text(encoding="utf-8"))
    return [
        n
        for n in ast.iter_child_nodes(tree)
        if isinstance(n, ast.ClassDef)
        and any(isinstance(m, ast.FunctionDef) and m.name == "utility" for m in ast.iter_child_nodes(n))
    ]


def agentdojo_task_profile(cls: ast.ClassDef, helper_index: dict) -> dict:
    utility_fn = next(m for m in ast.iter_child_nodes(cls) if isinstance(m, ast.FunctionDef) and m.name == "utility")
    own = _profile_function(utility_fn)
    attrs, names = set(own.attribute_names), set(own.referenced_names)
    for called in own.called_names:
        if called in helper_index:
            sub = transitive_read_profile(called, helper_index)
            attrs |= sub.attribute_names
            names |= sub.referenced_names

    ground_truth_fn = next(
        (m for m in ast.iter_child_nodes(cls) if isinstance(m, ast.FunctionDef) and m.name == "ground_truth"),
        None,
    )
    gt_tool_calls: set = set()
    if ground_truth_fn is not None:
        for node in ast.walk(ground_truth_fn):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "FunctionCall":
                for kw in node.keywords:
                    if kw.arg == "function" and isinstance(kw.value, ast.Constant):
                        gt_tool_calls.add(kw.value.value)

    reads_state = bool({"pre_environment", "post_environment"} & names)
    reads_transcript = "model_output" in names
    if reads_state and reads_transcript:
        grounding = "mixed"
    elif reads_state:
        grounding = "state_grounded"
    elif reads_transcript:
        grounding = "transcript_grounded"
    else:
        grounding = "no_write_oracle"

    return {
        "class_name": cls.name,
        "attribute_names": frozenset(attrs),
        "grounding": grounding,
        "gold_tool_calls": frozenset(gt_tool_calls),
    }


def build_agentdojo_rows() -> list[dict]:
    rows: list[dict] = []
    for kd in KNOWN_AGENTDOJO_DEFECTS:
        classes = agentdojo_task_classes(kd.suite)
        helper_index = _module_function_index(str(AGENTDOJO_TASKS_FILE[kd.suite]))
        clause_id = f"eff.{kd.field}_propagated"

        rows.append(
            {
                "kind": "defect",
                "benchmark": "agentdojo",
                "domain": kd.suite,
                "tool": kd.tool,
                "clause_id": clause_id,
                "defect_class": DefectClass.IGNORED_ARGUMENT.value,
                "finding_citation": kd.finding_citation,
                "write_paths": [f"{kd.tool}.{kd.field}"],
                "field_names": [kd.field],
            }
        )

        at_risk_ids: list[str] = []
        experiment_frame_ids: list[str] = []
        groundings_seen: set = set()
        for cls in classes:
            profile = agentdojo_task_profile(cls, helper_index)
            groundings_seen.add(profile["grounding"])
            task_id = f"{kd.suite}:{profile['class_name']}"
            in_experiment_frame = kd.tool in profile["gold_tool_calls"]
            if in_experiment_frame:
                experiment_frame_ids.append(task_id)
            if kd.field in profile["attribute_names"]:
                at_risk_ids.append(task_id)
                rows.append(
                    {
                        "kind": "task_verdict",
                        "benchmark": "agentdojo",
                        "domain": kd.suite,
                        "tool": kd.tool,
                        "clause_id": clause_id,
                        "defect_class": DefectClass.IGNORED_ARGUMENT.value,
                        "task_id": task_id,
                        "at_risk": True,
                        "oracle_grounding": profile["grounding"],
                        "evaluator_read_site": {
                            "mechanism": "utility()",
                            "detail": profile["class_name"],
                            "confidence": "exact_field",
                        },
                        "in_experiment_frame": in_experiment_frame,
                        "score_at_risk_status": "computed",
                    }
                )

        containment_ok = set(experiment_frame_ids) <= set(at_risk_ids)
        rows.append(
            {
                "kind": "summary",
                "benchmark": "agentdojo",
                "domain": kd.suite,
                "tool": kd.tool,
                "clause_id": clause_id,
                "defect_class": DefectClass.IGNORED_ARGUMENT.value,
                "finding_citation": kd.finding_citation,
                "n_tasks_total": len(classes),
                "n_at_risk": len(at_risk_ids),
                "n_experiment_frame": len(experiment_frame_ids),
                "experiment_frame_subset_of_at_risk": containment_ok,
                "oracle_grounding": "state_grounded" if groundings_seen <= {"state_grounded"} else sorted(groundings_seen),
                "score_at_risk_status": "computed",
                "bound_direction": (
                    "over-approximation of misgrading via the state-dependency mechanism only; "
                    "field-name matching confirms a task's oracle reads the same environment "
                    "field the defective tool writes, not that this task's own gold trajectory "
                    "reaches it through the defective tool specifically "
                    "(ARCHITECTURE-FINAL.md sec 4, REVIEW-RESPONSE.md W6)"
                ),
            }
        )
    return rows


# =============================================================================================
# Orchestration / CLI
# =============================================================================================


def build_all_rows() -> list[dict]:
    rows: list[dict] = []
    rows.extend(build_tau2_rows())
    rows.extend(build_medagentbench_rows())
    rows.extend(build_agentdojo_rows())
    return rows


def write_rows(rows: list[dict], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def verify(out_path: Path) -> int:
    """Re-derive every row from the pinned inputs and diff against what is on disk. Exits
    non-zero on any mismatch, for the numbers-audit rule (CLAUDE.md)."""
    if not out_path.exists():
        print(f"VERIFY FAILED: {out_path} does not exist", file=sys.stderr)
        return 1
    with open(out_path, "r", encoding="utf-8") as fh:
        on_disk = [json.loads(line) for line in fh if line.strip()]
    recomputed = build_all_rows()

    on_disk_lines = [json.dumps(r, sort_keys=True) for r in on_disk]
    recomputed_lines = [json.dumps(r, sort_keys=True) for r in recomputed]

    if on_disk_lines == recomputed_lines:
        print(f"VERIFY OK: {len(recomputed_lines)} rows match {out_path}")
        return 0

    on_set, re_set = set(on_disk_lines), set(recomputed_lines)
    missing = re_set - on_set
    extra = on_set - re_set
    print(f"VERIFY FAILED: {out_path} does not match a fresh derivation", file=sys.stderr)
    print(f"  {len(missing)} row(s) recomputed but missing on disk", file=sys.stderr)
    print(f"  {len(extra)} row(s) on disk but not recomputed", file=sys.stderr)
    for line in list(missing)[:5]:
        print(f"    + {line}", file=sys.stderr)
    for line in list(extra)[:5]:
        print(f"    - {line}", file=sys.stderr)
    return 1


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=REPORT_PATH, help="output JSONL path")
    parser.add_argument("--verify", action="store_true", help="re-derive and diff against --out instead of writing")
    args = parser.parse_args(argv)

    if args.verify:
        return verify(args.out)

    rows = build_all_rows()
    write_rows(rows, args.out)
    print(f"wrote {len(rows)} rows to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
