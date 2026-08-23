"""MM-ToolSandbox adapter worker -- the subprocess-side half of the boundary described in
adapters/base.py and adapters/tau2.py's module docstrings; adapters/mmtoolsandbox.py's module
docstring explains why a subprocess is used here even though (like AgentDojo, unlike tau2) there
is no hard interpreter-version conflict.

Runs ONLY under `.venv-mmtoolsandbox`, MM-ToolSandbox's own dependency closure (repos/mmtoolsandbox
@ 1e8e9324abcb741cc6a9718f9e7c1b80e85a1363, `requires-python = ">=3.11,<3.13"`).

SCOPE BOUNDARY -- read this before adding a tool. Per repos/MMTOOLSANDBOX-SPIKE.md and CLAUDE.md's
build instructions ("Do not attempt the AppWorld tier -- that package cannot be cloned"), this
adapter covers exactly two things, and nothing from the raw `tools/appworld/*.py` layer (467
auto-generated wrapper functions, 296 of them mutating by the spike's method-literal rule) is
executed by this file:

  1. `tools/tool_sandbox/` -- a self-contained, in-process, offline domain (calendar/reminder/
     setting). Fully dynamic: fresh_env/snapshot/invoke/reset all execute real MM-ToolSandbox
     code end to end. scenario_id "tool_sandbox".

  2. The `tools/mini/venmo.py` DISPATCH FACADE -- hand-written, in-repo code that itself calls
     `_get(name)` to resolve and invoke an `appworld`-tier function (`bridge.call_api(...)`,
     which needs a live `AppWorldBridge` this project cannot construct -- LFS quota exceeded,
     FINDINGS-VERIFIED.md). This worker patches `mini.venmo._get` to a recording stub, exactly
     reproducing repos/MMTOOLSANDBOX-SPIKE.md's own verification method ("intercepting that call
     with a stub -- the same idea as AgentDojo's `runtime.run_function`, just moved one layer
     earlier because the next layer is unavailable"): every line of `venmo_social`/
     `venmo_transact` MM-ToolSandbox itself owns still executes for real; only the hand-off past
     the seam is replaced. scenario_id "venmo_boundary". "snapshot" for this scenario is the
     boundary-call log -- {tool name, forwarded kwargs} per call -- which is exactly the state
     MM-ToolSandbox's own code produces and is therefore agent-adjacent, observable state, not a
     synthetic test fixture: it is what would be sent across the wire to AppWorld if AppWorld
     were reachable. Contracts against this scenario assert over that log (`post.boundary_calls`),
     never over anything inside AppWorld.

Both scenarios are dynamically exercised, real execution -- neither is a static-reading claim.
The other 295 appworld-tier mutating tools, and the `compact`/`consolidated` dispatch tiers, are
NOT covered by this adapter; any claim about them remains the static-only claim
repos/MMTOOLSANDBOX-SPIKE.md already made, unchanged by this file.

Protocol: identical wire format to adapters/_tau2_worker.py and adapters/_agentdojo_worker.py.

MUTATING-TOOL ENUMERATION RULE (tool_sandbox tier only; see repos/MMTOOLSANDBOX-SPIKE.md sec 1a)
--------------------------------------------------------------------------------------------
MM-ToolSandbox's tool_sandbox tier funnels every write through exactly three named
`ExecutionContext` methods: `add_to_database`, `update_database`, `remove_from_database`. Unlike
AgentDojo (no shared write API; every tool mutates its own `Depends`-injected pydantic object
directly), this means the enumeration rule does not need to trace a per-tool dependency name --
it needs only to ask, per `@register_as_tool(..., visible_to=(RoleType.AGENT,))`-decorated
function in the three tool_sandbox modules (calendar, reminder, setting -- `user_tools` is
`visible_to=(RoleType.USER,)` only, confirmed by runtime introspection, not agent-callable):

  1. PHASE 1 (direct): does the tool's own body call `<anything>.add_to_database(...)`,
     `.update_database(...)`, or `.remove_from_database(...)`? (The receiver is always a local
     bound to `get_current_context()`, so matching on method NAME alone -- not tracing which
     name it is bound to -- is sufficient and does not need AgentDojo's chain-root tracking.)
  2. PHASE 2 (one-hop plain-function delegate): `set_wifi_status` does not call a `*_database`
     method itself -- it calls `set_boolean_settings(...)`, a plain module-level helper (not a
     registered tool) defined in the same file, which does the actual `update_database` call.
     For every bare-name call in the tool's body, this worker looks up that name as a
     module-level function in the SAME source module and re-runs phase 1 on its body. One hop,
     matching adapters/_agentdojo_worker.py's phase-2 delegate rule in spirit (documented there
     in more detail since AgentDojo's version also needs chain-root taint tracking; this one
     does not).

`inspect.getsource` on a `@register_as_tool`-decorated function resolves to the `decorator`
package's internal template, not the real source, whenever `@typechecked` (from `typeguard`) is
also applied -- confirmed empirically. Both decorators preserve `__wrapped__`, so this worker
always unwraps via `__wrapped__` before any AST/source operation, and always calls through the
ORIGINAL (fully decorated) callable for actual invocation.
"""
from __future__ import annotations

import ast
import inspect
import json
import os
import sys
import types
import uuid
from pathlib import Path
from typing import Any, Callable

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.getcwd()) != _THIS_DIR]

# --- Windows `resource`-module shim -----------------------------------------------------------
# common/safety_guard.py:22 does an unconditional `import resource` (POSIX-only stdlib module);
# execution_context.py imports safety_guard, and virtually every package module transitively
# imports execution_context, so the whole `mmtoolsandbox` package fails to import on native
# Windows without this. Same finding, same fix, as repos/MMTOOLSANDBOX-SPIKE.md sec 2a's
# scratch-directory shim -- installed here, inside adapters/, so it ships with the adapter
# instead of living in a throwaway spike script. The actual resource.setrlimit-gated
# memory-limiting feature (sandboxed code-execution role only, never tool invocation) is inert
# under the shim, exactly as the spike found.
if os.name == "nt" and "resource" not in sys.modules:
    _resource_shim = types.ModuleType("resource")
    _resource_shim.RLIMIT_AS = 9
    _resource_shim.RLIM_INFINITY = -1
    _resource_shim.getrlimit = lambda who: (_resource_shim.RLIM_INFINITY, _resource_shim.RLIM_INFINITY)
    _resource_shim.setrlimit = lambda who, limits: None
    sys.modules["resource"] = _resource_shim

from pydantic import BaseModel  # noqa: E402

import mmtoolsandbox  # noqa: E402,F401 -- side effect: resolves MMTS_ROOT below
from mmtoolsandbox.common.execution_context import (  # noqa: E402
    DatabaseNamespace,
    ExecutionContext,
    RoleType,
    get_current_context,
    set_current_context,
)
from mmtoolsandbox.common.utils import NotGiven  # noqa: E402
from mmtoolsandbox.tools.tool_sandbox import calendar as _ts_calendar  # noqa: E402
from mmtoolsandbox.tools.tool_sandbox import reminder as _ts_reminder  # noqa: E402
from mmtoolsandbox.tools.tool_sandbox import setting as _ts_setting  # noqa: E402
import mmtoolsandbox.tools.mini.venmo as _mini_venmo  # noqa: E402

MMTS_ROOT = Path(mmtoolsandbox.__file__).resolve().parent.parent

TOOL_SANDBOX_MODULES = (_ts_calendar, _ts_reminder, _ts_setting)
DB_WRITE_METHODS = frozenset({"add_to_database", "update_database", "remove_from_database"})

IN_SCOPE_SCENARIOS = ("tool_sandbox", "venmo_boundary")

# Boundary-tier tools this adapter knows how to invoke through the `_get`-stub seam -- see
# module docstring. Deliberately a short, explicit allowlist, NOT an exhaustive enumeration of
# the 296 appworld-tier tools (that enumeration is repos/MMTOOLSANDBOX-SPIKE.md sec 1b's static,
# method-literal sweep, out of this adapter's dynamic scope by the build instructions).
VENMO_BOUNDARY_TOOLS = frozenset({"venmo_social", "venmo_transact"})

_LIVE_ENVS: dict[str, dict[str, Any]] = {}
_MODULE_AST_CACHE: dict[str, ast.Module] = {}
_MODULE_FUNC_INDEX_CACHE: dict[str, dict] = {}


def _unwrap(fn: Callable) -> Callable:
    seen = set()
    while hasattr(fn, "__wrapped__") and id(fn) not in seen:
        seen.add(id(fn))
        fn = fn.__wrapped__
    return fn


def _agent_visible_tools(module) -> list:
    return [
        obj
        for _, obj in inspect.getmembers(module)
        if getattr(obj, "is_tool", False) and RoleType.AGENT in getattr(obj, "visible_to", ())
    ]


# ---------------------------------------------------------------------------
# Mutating-tool enumeration -- see module docstring.
# ---------------------------------------------------------------------------


def _calls_db_write(fn_node: ast.AST) -> bool:
    for n in ast.walk(fn_node):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in DB_WRITE_METHODS:
            return True
    return False


def _bare_call_names(fn_node: ast.AST) -> set:
    return {n.func.id for n in ast.walk(fn_node) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}


def _module_ast(source_path: str) -> ast.Module:
    if source_path not in _MODULE_AST_CACHE:
        _MODULE_AST_CACHE[source_path] = ast.parse(Path(source_path).read_text(encoding="utf-8"))
    return _MODULE_AST_CACHE[source_path]


def _module_func_index(source_path: str) -> dict:
    """Module-level (not method) function defs, by name -- for the phase-2 plain-function
    delegate hop. Deliberately module-level only (register_as_tool tools and their private
    helpers in this codebase are plain functions, not methods)."""
    if source_path not in _MODULE_FUNC_INDEX_CACHE:
        tree = _module_ast(source_path)
        _MODULE_FUNC_INDEX_CACHE[source_path] = {
            n.name: n for n in ast.iter_child_nodes(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
    return _MODULE_FUNC_INDEX_CACHE[source_path]


def _is_mutating(fn: Callable) -> bool:
    real = _unwrap(fn)
    try:
        source_path = inspect.getsourcefile(real)
        src = inspect.getsource(real)
        fn_ast = ast.parse(src).body[0]
    except (OSError, TypeError, SyntaxError):
        return False
    if _calls_db_write(fn_ast):
        return True
    index = _module_func_index(source_path)
    for name in _bare_call_names(fn_ast):
        target = index.get(name)
        if target is not None and _calls_db_write(target):
            return True
    return False


def _source_ref(fn: Callable) -> dict:
    real = _unwrap(fn)
    lines, start = inspect.getsourcelines(real)
    end = start + len(lines) - 1
    file = os.path.relpath(inspect.getsourcefile(real), MMTS_ROOT).replace(os.sep, "/")
    return {"file": file, "start_line": start, "end_line": end, "note": "start_line is the @register_as_tool decorator line."}


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, NotGiven):
        return "⟪ NOT_GIVEN ⟫"  # distinguishable sentinel string -- see module docstring
        # on why an unguarded NotGiven forward (repos/MMTOOLSANDBOX-SPIKE.md Candidate 2) must be
        # OBSERVABLE in a boundary-call snapshot, not silently coerced to null/None, which would
        # look identical to "the parameter was never forwarded at all".
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_to_jsonable(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _tool_ref(scenario_id: str, name: str, fn: Callable) -> dict:
    return {
        "name": name,
        "domain": scenario_id,
        "source": _source_ref(fn),
        "docstring": inspect.getdoc(_unwrap(fn)) or "",
        "signature": str(inspect.signature(_unwrap(fn))),
        "mutates_state": _is_mutating(fn),
        "tool_type": "WRITE" if _is_mutating(fn) else "READ",
    }


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------


def _cmd_ping(args: dict) -> dict:
    return {"pong": True}


def _cmd_list_tools(args: dict) -> dict:
    tools = []
    for module in TOOL_SANDBOX_MODULES:
        for fn in _agent_visible_tools(module):
            tools.append(_tool_ref("tool_sandbox", fn.__name__, fn))
    for name in sorted(VENMO_BOUNDARY_TOOLS):
        fn = getattr(_mini_venmo, name)
        ref = _tool_ref("venmo_boundary", name, fn)
        ref["mutates_state"] = True  # both are financial-domain dispatchers whose non-`show`/
        # `list` actions mutate AppWorld-side state past the boundary this adapter can observe;
        # see the per-contract effect clauses for what IS checkable (the forwarded-kwargs log).
        ref["tool_type"] = "WRITE"
        tools.append(ref)
    return {"tools": tools}


def _cmd_fresh_env(args: dict) -> dict:
    scenario_id = args["scenario_id"]
    if scenario_id not in IN_SCOPE_SCENARIOS:
        raise ValueError(f"unknown scenario_id {scenario_id!r}; in-scope scenarios are {IN_SCOPE_SCENARIOS}")
    env_id = uuid.uuid4().hex
    if scenario_id == "tool_sandbox":
        _LIVE_ENVS[env_id] = {"scenario": scenario_id, "ctx": ExecutionContext()}
    else:  # venmo_boundary
        _LIVE_ENVS[env_id] = {"scenario": scenario_id, "log": []}
    return {"env_id": env_id, "domain": scenario_id, "scenario_id": scenario_id}


def _live(env_id: str) -> dict:
    if env_id not in _LIVE_ENVS:
        raise KeyError(f"no live environment for env_id {env_id!r}")
    return _LIVE_ENVS[env_id]


# The stub is installed once, at import time, and reads which log to append to from
# `_ACTIVE_BOUNDARY_LOG` -- set immediately before each venmo_boundary invoke() below. This
# worker is strictly synchronous (one request in flight, per adapters/agentdojo.py's protocol
# note), so there is never ambiguity about which live env's log is "active" during a call.
_ACTIVE_BOUNDARY_LOG: list = []


def _boundary_stub(name: str):
    def _stub(**kwargs: Any) -> dict:
        _ACTIVE_BOUNDARY_LOG.append({"tool": name, "kwargs": _to_jsonable(kwargs)})
        return {"stub": True, "boundary_intercepted": True}

    return _stub


_mini_venmo._get = _boundary_stub  # patch the one seam MM-ToolSandbox's own mini-tier code
# controls before handing off to AppWorld -- see module docstring and
# repos/MMTOOLSANDBOX-SPIKE.md's identical technique.


def _cmd_snapshot(args: dict) -> dict:
    entry = _live(args["env_id"])
    if entry["scenario"] == "tool_sandbox":
        set_current_context(entry["ctx"])
        dbs = get_current_context().get_tool_state_registry if False else None  # unused; explicit no-op
        raw = get_current_context().to_dict(serialize_console=False)["_dbs"]
        return {"snapshot": {str(namespace): rows for namespace, rows in raw.items()}}
    return {"snapshot": {"boundary_calls": entry["log"]}}


def _cmd_invoke(args: dict) -> dict:
    global _ACTIVE_BOUNDARY_LOG
    entry = _live(args["env_id"])
    tool = args["tool"]
    tool_args = args.get("args") or {}
    try:
        if entry["scenario"] == "tool_sandbox":
            set_current_context(entry["ctx"])
            fn = None
            for module in TOOL_SANDBOX_MODULES:
                fn = getattr(module, tool, None)
                if fn is not None and getattr(fn, "is_tool", False):
                    break
            if fn is None:
                raise KeyError(f"tool {tool!r} not found in tool_sandbox scope")
            raw = fn(**tool_args)
        else:
            if tool not in VENMO_BOUNDARY_TOOLS:
                raise KeyError(f"tool {tool!r} not found in venmo_boundary scope (known: {sorted(VENMO_BOUNDARY_TOOLS)})")
            _ACTIVE_BOUNDARY_LOG = entry["log"]
            fn = getattr(_mini_venmo, tool)
            raw = fn(**tool_args)
        return {"result": {"raw": _to_jsonable(raw), "success": True, "error": None}}
    except Exception as e:  # noqa: BLE001 -- report to caller, not a worker fault
        return {"result": {"raw": None, "success": False, "error": f"{type(e).__name__}: {e}"}}


def _cmd_reset(args: dict) -> dict:
    """Both scenarios reset by construct-fresh, matching every other adapter in this project
    (tau2, AgentDojo) for the same underlying reason: neither MM-ToolSandbox's own
    `ExecutionContext` nor this adapter's boundary log is meant to survive across simulated
    episodes -- repos/MMTOOLSANDBOX-SPIKE.md sec 4 confirms a brand-new `ExecutionContext()`
    starts every database empty, by execution."""
    entry = _live(args["env_id"])
    if entry["scenario"] == "tool_sandbox":
        entry["ctx"] = ExecutionContext()
    else:
        entry["log"] = []
    return {}


def _cmd_source(args: dict) -> dict:
    tool = args["tool"]
    if ":" in tool:
        scenario, name = tool.split(":", 1)
    else:
        scenario, name = None, tool

    if scenario in (None, "tool_sandbox"):
        for module in TOOL_SANDBOX_MODULES:
            fn = getattr(module, name, None)
            if fn is not None and getattr(fn, "is_tool", False):
                if scenario is None:
                    # ambiguity check: also present in venmo_boundary's allowlist?
                    if name in VENMO_BOUNDARY_TOOLS:
                        raise ValueError(f"tool name {name!r} is ambiguous across scenarios; disambiguate with 'scenario:{name}'")
                return {"source": _source_ref(fn)}
    if scenario in (None, "venmo_boundary") and name in VENMO_BOUNDARY_TOOLS:
        return {"source": _source_ref(getattr(_mini_venmo, name))}
    raise KeyError(f"tool {tool!r} not found in any in-scope scenario {IN_SCOPE_SCENARIOS}")


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
