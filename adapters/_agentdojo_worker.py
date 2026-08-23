"""AgentDojo adapter worker -- the subprocess-side half of the boundary described in
adapters/base.py and adapters/tau2.py's module docstrings, reused here for a different reason.

Runs ONLY under AgentDojo's own interpreter (repos/AGENTDOJO-SPIKE.md: `requires-python = ">=
3.10"`, satisfied by this project's ambient 3.11.7 -- there is NO version conflict here, unlike
tau2). This worker exists anyway, in its own venv (`.venv-agentdojo`), for a different reason
than tau2's: AgentDojo's `pyproject.toml` hard-requires `openai`, `anthropic`, `cohere`,
`google-genai` and `langchain` as unconditional `[project.dependencies]` (AGENTDOJO-SPIKE.md
sec 2) -- none of them are called at tool-invocation time, but all of them must be importable,
because `agentdojo.agent_pipeline` (pulled in transitively by `agentdojo.task_suite.load_suites`)
does `import anthropic` unconditionally at module load. Installing that dependency set into the
project's own ambient interpreter (the one `python -m unittest discover tests` runs under) would
make every future `pip install` in this project resolve against AgentDojo's pinned transitive
closure, which is exactly the kind of silent cross-contamination the subprocess boundary in
adapters/base.py exists to prevent -- see adapters/agentdojo.py's module docstring for the note
this is meant to be, per the build spec, on where the two-file adapter/worker split did not need
to fit for a version reason but was kept anyway for an isolation reason.

Protocol: identical wire format to adapters/_tau2_worker.py -- one JSON object per line in, one
out, synchronous, {"id", "cmd", "args"} -> {"id", "ok", "result"} | {"id", "ok": false, "error"}.

MUTATING-TOOL ENUMERATION RULE (stated once here, applied uniformly; see repos/AGENTDOJO-SPIKE.md
sec 1, "Enumeration rule used")
--------------------------------------------------------------------------------------------
AgentDojo has no `mutates_state`-style tag anywhere (confirmed by grep in the spike). This
worker derives it from source, by static analysis of each registered tool's own body, applied
uniformly across all four in-scope v1 suites (banking, slack, travel, workspace) rather than
hand-curated per tool:

  1. A tool's `Depends`-injected parameters are read off the *runtime* Function object
     (`f.dependencies`, populated by `agentdojo.functions_runtime._get_dependencies` from the
     function's own type hints) -- not re-derived by parsing `Annotated[...]` text, since the
     runtime already resolves this exactly and re-parsing it would be a second, potentially
     divergent implementation of the same rule.
  2. PHASE 1 (direct): the tool's own body is AST-walked for a write rooted at one of those
     parameter names -- `Assign`/`AugAssign`/`Delete` whose target's attribute/subscript chain
     resolves back to the parameter, or a call `<chain>.method(...)` where `method` is one of a
     small, fixed set of known-mutating container methods (append/extend/insert/pop/remove/
     clear/update/popitem/sort/reverse/setdefault) and `<chain>` resolves back to the parameter.
     Matches the spike's stated rule exactly: "attribute assignment, .append/.extend/.pop/del,
     or dict-key assignment on the environment sub-model."
  3. WITHIN PHASE 1, straight-line TAINT TRACKING: `share_file` writes through a local variable
     -- `file = cloud_drive.get_file_by_id(file_id); file.shared_with[email] = permission`
     (cloud_drive_client.py) -- not through `cloud_drive` itself. A rule that only looked for
     writes rooted directly at a `Depends` name would miss this, and it is not an edge case: it
     is the dominant pattern for any tool that first looks an entity up by id and then mutates
     the entity, which is most of them. So the AST walk is sequential and taint-propagating, one
     function body at a time: a local name is added to the tainted set when it is assigned (a)
     directly from a tainted root (`x = cloud_drive`), (b) from a subscript/attribute access
     into a tainted root (`x = self.events[event_id]`), (c) from a `.values()`/`.items()`/
     `.keys()` call on a tainted root inside a comprehension's first `for` clause (the
     `get_unread_emails` -> `Inbox.get_unread` pattern below), or (d) from ANY method call whose
     receiver chain is rooted in a tainted name (`x = cloud_drive.get_file_by_id(...)`) --
     deliberately over-inclusive (a getter's return value is conservatively treated as a
     possible alias into the same mutable state), but this cannot by itself produce a false
     "mutating": a tainted variable only trips the rule if it is later itself the target of a
     write. `for y in <tainted-expr>:` taints the loop variable `y` the same way. Python has no
     block scoping, so one tainted-name set threaded through the whole function body (extended,
     never narrowed, as statements are visited in order) is a faithful, auditable model of this
     -- not a full dataflow analysis, but enough for the patterns that occur in this codebase.
  4. PHASE 2 (one-hop delegate): some tools do not write directly at all -- `create_file` returns
     `cloud_drive.create_file(...)`, a *method* on the same `Depends`-injected object, defined
     on its pydantic class in the same module (`CloudDrive.create_file`, cloud_drive_client.py).
     For every method-shaped call `<chain>.<name>(...)` on a `Depends` parameter that is not
     itself a phase-1 container-mutator call, this worker looks up `<name>` as a method defined
     on any class in the SAME source module and re-runs the phase-1 (taint-tracking) check on
     that method's body with `self` as the sole seed root. One hop only, no further recursion --
     sufficient for every case in this codebase (`create_file`, `delete_file`, `append_to_file`,
     `get_unread_emails`, `reschedule_calendar_event`, `add_calendar_event_participants` all
     resolve this way; checked by running this rule and comparing its output against the spike's
     hand count -- see adapters/agentdojo.py's module docstring for the comparison and the one
     documented, accepted discrepancy). This is the same "index the module's own direct
     children, follow one hop of calls" idiom analysis/score_at_risk.py already uses
     (`transitive_read_profile`), applied here to writes instead of reads.

Return-value construction alone (building and returning a brand-new object with no read of the
dependency at all) never counts, matching the spike's stated rule -- nothing is tainted unless it
traces back to a seed root.
"""
from __future__ import annotations

import ast
import inspect
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Callable

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.getcwd()) != _THIS_DIR]

from pydantic import BaseModel  # noqa: E402

import agentdojo  # noqa: E402,F401 -- side effect: resolves AGENTDOJO_ROOT below
from agentdojo.functions_runtime import FunctionsRuntime  # noqa: E402
from agentdojo.task_suite.load_suites import get_suite  # noqa: E402

AGENTDOJO_ROOT = Path(agentdojo.__file__).resolve().parent.parent.parent

IN_SCOPE_SUITES = ("banking", "slack", "travel", "workspace")

MUTATOR_METHODS = frozenset(
    {"append", "extend", "insert", "pop", "remove", "clear", "update", "popitem", "sort", "reverse", "setdefault"}
)

_INTROSPECT_SUITES: dict[str, Any] = {}
_LIVE_ENVS: dict[str, dict[str, Any]] = {}
_MODULE_AST_CACHE: dict[str, ast.Module] = {}


def _suite(name: str):
    if name not in IN_SCOPE_SUITES:
        raise ValueError(f"unknown suite {name!r}; in-scope suites are {IN_SCOPE_SUITES}")
    if name not in _INTROSPECT_SUITES:
        _INTROSPECT_SUITES[name] = get_suite("v1", name)
    return _INTROSPECT_SUITES[name]


# ---------------------------------------------------------------------------
# Mutating-tool enumeration -- see module docstring.
# ---------------------------------------------------------------------------


def _chain_root(node: ast.AST) -> "str | None":
    """Unwind an Attribute/Subscript chain (e.g. `slack.user_channels[user]`) back to its
    root Name id, or None if the chain does not bottom out in a bare name."""
    while isinstance(node, (ast.Attribute, ast.Subscript)):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


# Small, closed, auditable set of builtins that pass taint through from an argument to their
# result when that argument is itself tainted -- mirrors `next((t for t in account.
# scheduled_transactions if t.id == id), None)` in `update_scheduled_transaction`
# (banking_client.py), the standard "find one matching element" idiom this codebase uses instead
# of a dict lookup. Kept as a short literal list, the same idiom core/predicates.py's
# ALLOWED_BUILTINS uses for the same auditability reason.
_TAINT_PASSTHROUGH_BUILTINS = frozenset({"next", "list", "sorted", "filter", "iter", "sum"})


def _is_tainted_expr(node: ast.AST, tainted: set) -> bool:
    """Does evaluating `node` potentially yield a reference into state reachable from a name in
    `tainted`? See module docstring point 3 for the four cases (a)-(d)."""
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id in _TAINT_PASSTHROUGH_BUILTINS:
            return any(_is_tainted_expr(a, tainted) for a in node.args)
        if isinstance(node.func, ast.Attribute):
            if node.func.attr in {"values", "items", "keys"} and _chain_root(node.func.value) in tainted:
                return True  # (c)
            if _chain_root(node.func.value) in tainted:
                return True  # (d) -- any method call on a tainted receiver
        return False
    if isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)) and node.generators:
        return _is_tainted_expr(node.generators[0].iter, tainted)
    if isinstance(node, (ast.Attribute, ast.Subscript)):
        return _chain_root(node) in tainted  # (a)/(b) -- chain rooted directly at a tainted name
    if isinstance(node, ast.Name):
        return node.id in tainted
    return False


def _scan_expr_for_mutator_calls(node: ast.AST, tainted: set) -> bool:
    for n in ast.walk(node):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
            if n.func.attr in MUTATOR_METHODS and _chain_root(n.func.value) in tainted:
                return True
    return False


def _scan_stmts(stmts: list, tainted: set) -> bool:
    mutated = False
    for stmt in stmts:
        if _scan_stmt(stmt, tainted):
            mutated = True
    return mutated


def _scan_stmt(stmt: ast.AST, tainted: set) -> bool:
    """Sequential, taint-propagating statement scan -- see module docstring point 3. `tainted`
    is mutated in place (extended, never narrowed) as the function body is visited in order;
    Python's lack of block scoping makes this a faithful model of the real name bindings."""
    if isinstance(stmt, ast.Assign):
        mutated = any(
            isinstance(t, (ast.Attribute, ast.Subscript)) and _chain_root(t) in tainted for t in stmt.targets
        )
        mutated = _scan_expr_for_mutator_calls(stmt.value, tainted) or mutated  # e.g. `x =
        # self.files.pop(k)` -- the mutation happens evaluating the RHS, not at the target.
        if _is_tainted_expr(stmt.value, tainted):
            for t in stmt.targets:
                if isinstance(t, ast.Name):
                    tainted.add(t.id)
        return mutated
    if isinstance(stmt, ast.AugAssign):
        mutated = isinstance(stmt.target, (ast.Attribute, ast.Subscript)) and _chain_root(stmt.target) in tainted
        return _scan_expr_for_mutator_calls(stmt.value, tainted) or mutated
    if isinstance(stmt, ast.Delete):
        return any(isinstance(t, (ast.Attribute, ast.Subscript)) and _chain_root(t) in tainted for t in stmt.targets)
    if isinstance(stmt, ast.Return):
        return stmt.value is not None and _scan_expr_for_mutator_calls(stmt.value, tainted)
    if isinstance(stmt, ast.For):
        if _is_tainted_expr(stmt.iter, tainted) and isinstance(stmt.target, ast.Name):
            tainted.add(stmt.target.id)
        mutated = _scan_expr_for_mutator_calls(stmt.iter, tainted)
        mutated = _scan_stmts(stmt.body, tainted) or mutated
        mutated = _scan_stmts(stmt.orelse, tainted) or mutated
        return mutated
    if isinstance(stmt, (ast.If, ast.While)):
        mutated = _scan_expr_for_mutator_calls(stmt.test, tainted)
        mutated = _scan_stmts(stmt.body, tainted) or mutated
        mutated = _scan_stmts(stmt.orelse, tainted) or mutated
        return mutated
    if isinstance(stmt, ast.Try):
        mutated = _scan_stmts(stmt.body, tainted)
        for h in stmt.handlers:
            mutated = _scan_stmts(h.body, tainted) or mutated
        mutated = _scan_stmts(stmt.orelse, tainted) or mutated
        mutated = _scan_stmts(stmt.finalbody, tainted) or mutated
        return mutated
    if isinstance(stmt, ast.With):
        return _scan_stmts(stmt.body, tainted)
    if isinstance(stmt, ast.Expr):
        return _scan_expr_for_mutator_calls(stmt.value, tainted)
    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return False  # a nested def/class is its own scope -- do not descend into it
    return False


def _direct_writes(node: ast.AST, roots: frozenset) -> bool:
    """Phase-1 check (see module docstring points 2-3): does `node`'s body contain a write
    reachable from one of `roots`, by direct chain or by the taint-propagation rules above?
    `node` is either a tool's own FunctionDef or a delegate method's FunctionDef; `roots` is the
    seed name set ('Depends' parameter names for a tool, or {'self'} for a delegate method)."""
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return False
    return _scan_stmts(node.body, set(roots))


def _delegate_call_names(node: ast.AST, roots: frozenset) -> set:
    """Method-shaped calls `<chain>.<name>(...)` on `roots` that are NOT phase-1 container
    mutators -- candidates for the phase-2 one-hop delegate check."""
    names: set = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
            if n.func.attr not in MUTATOR_METHODS and _chain_root(n.func.value) in roots:
                names.add(n.func.attr)
    return names


def _module_ast(source_path: str) -> ast.Module:
    if source_path not in _MODULE_AST_CACHE:
        _MODULE_AST_CACHE[source_path] = ast.parse(Path(source_path).read_text(encoding="utf-8"))
    return _MODULE_AST_CACHE[source_path]


def _module_methods_named(source_path: str, name: str) -> list:
    """Every method (across every class) in `source_path` named `name` -- deliberately not
    type-resolved (no import-graph tracing of which class the Depends object actually
    instantiates); see module docstring, phase 2."""
    out = []
    tree = _module_ast(source_path)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == name:
                    out.append(child)
    return out


def _is_mutating(fn: Callable, dep_names: frozenset) -> bool:
    if not dep_names:
        return False  # nothing to mutate -- no Depends-injected state at all
    try:
        source_path = inspect.getsourcefile(fn)
        src = inspect.getsource(fn)
        fn_ast = ast.parse(src).body[0]
    except (OSError, TypeError, SyntaxError):
        return False
    if _direct_writes(fn_ast, dep_names):
        return True
    for name in _delegate_call_names(fn_ast, dep_names):
        for method_node in _module_methods_named(source_path, name):
            if _direct_writes(method_node, frozenset({"self"})):
                return True
    return False


def _source_ref(fn: Callable) -> dict:
    lines, start = inspect.getsourcelines(fn)
    end = start + len(lines) - 1
    file = os.path.relpath(inspect.getsourcefile(fn), AGENTDOJO_ROOT).replace(os.sep, "/")
    return {"file": file, "start_line": start, "end_line": end, "note": None}


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {k: _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _tool_ref(suite_name: str, f) -> dict:
    dep_names = frozenset(f.dependencies.keys())
    return {
        "name": f.name,
        "domain": suite_name,
        "source": _source_ref(f.run),
        "docstring": f.full_docstring or "",
        "signature": str(inspect.signature(f.run)),
        "mutates_state": _is_mutating(f.run, dep_names),
        "tool_type": "WRITE" if _is_mutating(f.run, dep_names) else "READ",
    }


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------


def _cmd_ping(args: dict) -> dict:
    return {"pong": True}


def _cmd_list_tools(args: dict) -> dict:
    # De-duplicated by name: send_email, create_calendar_event, and cancel_calendar_event are
    # shared between the travel and workspace suites (same function object, imported into both
    # TOOLS lists) -- see repos/AGENTDOJO-SPIKE.md sec 1. Reporting once per (name) rather than
    # once per suite registration matches CLAUDE.md's reporting-granularity rule ("eight bugs in
    # one copied helper is one bug"): a shared tool's ToolRef carries the domain it was FIRST
    # seen in, and every domain it is registered in besides that is listed in `also_in`, folded
    # into the docstring-adjacent `signature` field is not appropriate for a wire dict shaped
    # like adapters.base.ToolRef, so a second key is added on the wire result only.
    seen: dict[str, dict] = {}
    also_in: dict[str, set] = {}
    for suite_name in IN_SCOPE_SUITES:
        suite = _suite(suite_name)
        for f in suite.tools:
            if f.name in seen:
                also_in.setdefault(f.name, set()).add(suite_name)
                continue
            seen[f.name] = _tool_ref(suite_name, f)
            also_in[f.name] = set()
    tools = []
    for name, ref in seen.items():
        ref = dict(ref)
        ref["also_in"] = sorted(also_in[name])
        tools.append(ref)
    return {"tools": tools}


def _cmd_fresh_env(args: dict) -> dict:
    suite_name = args["scenario_id"]
    suite = _suite(suite_name)
    env = suite.load_and_inject_default_environment({})
    runtime = FunctionsRuntime(suite.tools)
    env_id = uuid.uuid4().hex
    _LIVE_ENVS[env_id] = {"suite": suite_name, "env": env, "runtime": runtime}
    return {"env_id": env_id, "domain": suite_name, "scenario_id": suite_name}


def _live(env_id: str) -> dict:
    if env_id not in _LIVE_ENVS:
        raise KeyError(f"no live environment for env_id {env_id!r}")
    return _LIVE_ENVS[env_id]


def _cmd_snapshot(args: dict) -> dict:
    entry = _live(args["env_id"])
    return {"snapshot": entry["env"].model_dump(mode="json")}


def _cmd_invoke(args: dict) -> dict:
    entry = _live(args["env_id"])
    tool = args["tool"]
    tool_args = args.get("args") or {}
    try:
        raw, error = entry["runtime"].run_function(entry["env"], tool, tool_args, raise_on_error=False)
        if error is not None:
            return {"result": {"raw": None, "success": False, "error": error}}
        return {"result": {"raw": _to_jsonable(raw), "success": True, "error": None}}
    except Exception as e:  # noqa: BLE001 -- report to caller, not a worker fault
        return {"result": {"raw": None, "success": False, "error": f"{type(e).__name__}: {e}"}}


def _cmd_reset(args: dict) -> dict:
    """AgentDojo's own reset path is "construct fresh" -- repos/AGENTDOJO-SPIKE.md sec 4: no
    in-place mutable singleton exists across runs; `load_and_inject_default_environment` is the
    harness's only construction path (`task_suite.py:365-367`, `run_task_with_pipeline`), called
    fresh per task. This handler replicates that: rebuild the env from the same suite loader and
    swap it into the live entry in place, exactly mirroring adapters/_tau2_worker.py's
    `_cmd_reset` for the structurally identical reason (tau2's own per-simulation rebuild)."""
    entry = _live(args["env_id"])
    entry["env"] = _suite(entry["suite"]).load_and_inject_default_environment({})
    return {}


def _cmd_source(args: dict) -> dict:
    tool = args["tool"]
    if ":" in tool:
        suite_name, name = tool.split(":", 1)
        suite = _suite(suite_name)
        for f in suite.tools:
            if f.name == name:
                return {"source": _source_ref(f.run)}
        raise KeyError(f"tool {name!r} not found in suite {suite_name!r}")

    matches = []
    for suite_name in IN_SCOPE_SUITES:
        for f in _suite(suite_name).tools:
            if f.name == tool:
                matches.append((suite_name, f))
    if not matches:
        raise KeyError(f"tool {tool!r} not found in any in-scope suite {IN_SCOPE_SUITES}")
    # Shared tools (send_email, create_calendar_event, cancel_calendar_event) are the SAME
    # function object registered under >1 suite -- not ambiguous the way tau2's
    # transfer_to_human_agents is (a distinct implementation per domain), so a bare name
    # resolves here as long as every match is the same underlying callable.
    first_fn = matches[0][1].run
    if all(f.run is first_fn for _, f in matches):
        return {"source": _source_ref(first_fn)}
    suites = ", ".join(s for s, _ in matches)
    raise ValueError(f"tool name {tool!r} is ambiguous across suites ({suites}) with DIFFERENT implementations")


_HANDLERS: dict[str, Callable[[dict], dict]] = {
    "ping": _cmd_ping,
    "list_tools": _cmd_list_tools,
    "fresh_env": _cmd_fresh_env,
    "snapshot": _cmd_snapshot,
    "invoke": _cmd_invoke,
    "reset": _cmd_reset,
    "source": _cmd_source,
}


def _reply(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def main() -> None:
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError as e:
            _reply({"id": None, "ok": False, "error": f"bad request json: {e}"})
            continue

        rid = req.get("id")
        cmd = req.get("cmd")

        if cmd == "shutdown":
            _reply({"id": rid, "ok": True, "result": {}})
            break

        handler = _HANDLERS.get(cmd)
        if handler is None:
            _reply({"id": rid, "ok": False, "error": f"unknown cmd {cmd!r}"})
            continue

        try:
            result = handler(req.get("args") or {})
            _reply({"id": rid, "ok": True, "result": result})
        except Exception as e:  # noqa: BLE001 -- report to caller, keep the worker alive
            _reply({"id": rid, "ok": False, "error": f"{type(e).__name__}: {e}"})


if __name__ == "__main__":
    main()
