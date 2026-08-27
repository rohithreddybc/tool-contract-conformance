"""tau2-bench adapter worker -- the subprocess-side half of the boundary described in
adapters/base.py and adapters/tau2.py's module docstrings.

Runs ONLY under tau2-bench's own interpreter (>=3.12,<3.14; this project's `.venv-tau2`, per
ARCHITECTURE-FINAL.md sec 2). Never imported by the harness process directly -- adapters/tau2.py
launches it with `<venv>/Scripts/python.exe adapters/_tau2_worker.py` and speaks newline-
delimited JSON over its stdin/stdout. Deliberately has NO dependency on this project's `core/`
or `adapters/base.py` dataclasses: it emits plain JSON-shaped dicts on the wire, and
adapters/tau2.py (running under the harness's own interpreter) is what reconstructs typed
objects from them. That keeps this file's only import surface the `tau2` package itself, so it
never has to reconcile two interpreters' view of one dataclass module.

Protocol: one JSON object per line in, one JSON object per line out, synchronous (this process
never has more than one request in flight). Request: {"id": int, "cmd": str, "args": {...}}.
Response: {"id": int, "ok": true, "result": {...}} or {"id": int, "ok": false, "error": str}.
"cmd": "shutdown" ends the loop after replying.

Domains in scope (ARCHITECTURE-FINAL.md sec 2): airline, retail, telecom. telecom has two
registered constructors -- get_environment_manual_policy / get_environment_workflow_policy
(registry.py:40-45) -- differing only in which tech-support policy document is loaded; the
underlying TelecomTools/TelecomDB/TelecomUserTools/TelecomUserDB objects and every tool's
behavior are identical either way (domains/telecom/environment.py: both are
`functools.partial(get_environment, policy_type=...)` over the same function). This worker
picks MANUAL, for two reasons: it is what commit c3398666's registry binds to the plain
"telecom" domain name (registry.py registers `telecom_domain_get_environment_manual_policy`
under "telecom" and reserves "telecom-workflow" for the other), and CLAUDE.md's refuel_data
finding is stated against the "telecom" domain without a workflow qualifier.
"""
from __future__ import annotations

import inspect
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Callable

# `python adapters/_tau2_worker.py` puts this file's own directory -- adapters/ -- at the front
# of sys.path (standard `python script.py` behavior). adapters/ also contains tau2.py (this
# project's adapter *client* module, adapters/tau2.py), so an unguarded `import tau2` below
# would shadow the real, installed tau2-bench package with that unrelated same-named file and
# fail deep inside it. Strip our own directory before importing anything tau2-side.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.getcwd()) != _THIS_DIR]

# Quiet loguru: tau2 logs at DEBUG by default (a full registry dump, full reservation JSON
# dumps on every mutating call, ...). Left at DEBUG it is both noisy and a latent deadlock risk
# if a caller ever pipes this process's stderr instead of inheriting it. adapters/tau2.py
# inherits stderr (does not pipe it) for exactly this reason; this cuts the volume further.
from loguru import logger as _loguru_logger  # noqa: E402

_loguru_logger.remove()
_loguru_logger.add(sys.stderr, level="WARNING")

from pydantic import BaseModel  # noqa: E402

import tau2  # noqa: E402,F401  -- import for its side effect of resolving TAU2_ROOT below
from tau2.domains.airline.environment import get_environment as _get_airline_env  # noqa: E402
from tau2.domains.retail.environment import get_environment as _get_retail_env  # noqa: E402
from tau2.domains.telecom.environment import (  # noqa: E402
    get_environment_manual_policy as _get_telecom_env,
)

# Repo root of the tau2 checkout this worker is running against (parent of "src") -- used to
# turn inspect's absolute source paths into the repo-relative paths contracts cite
# (spec/schema.json $defs.sourceRef: "src/tau2/domains/<domain>/tools.py, not domains/...").
TAU2_ROOT = Path(tau2.__file__).resolve().parent.parent.parent

DOMAIN_CONSTRUCTORS: dict[str, Callable[[], Any]] = {
    "airline": _get_airline_env,
    "retail": _get_retail_env,
    "telecom": _get_telecom_env,
}
DOMAINS = tuple(DOMAIN_CONSTRUCTORS.keys())

# One shared, never-invoked "introspection" environment per domain (list_tools/source only --
# safe to share since nothing here ever calls a tool on it). Live, mutable per-EnvHandle
# environments are tracked separately in _LIVE_ENVS, one fresh instance per fresh_env() call.
_INTROSPECT_ENVS: dict[str, Any] = {}
_LIVE_ENVS: dict[str, dict[str, Any]] = {}


def _introspect_env(domain: str) -> Any:
    if domain not in DOMAIN_CONSTRUCTORS:
        raise ValueError(f"unknown domain {domain!r}; in-scope domains are {DOMAINS}")
    if domain not in _INTROSPECT_ENVS:
        _INTROSPECT_ENVS[domain] = DOMAIN_CONSTRUCTORS[domain]()
    return _INTROSPECT_ENVS[domain]


def _to_jsonable(value: Any) -> Any:
    """Recursively coerce a tau2 return value into JSON-shaped data. Mirrors what
    `Environment.to_json_str` does internally, but returns a Python structure (for us to
    json.dumps ourselves) rather than a pre-serialized string."""
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {k: _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    # datetime.date/datetime, Enum members, etc. -- str() is what json.dumps(default=str) would
    # have done anyway; doing it here keeps the wire payload plain JSON with no custom decoder.
    return str(value)


def _source_ref(func: Any) -> dict:
    lines, start = inspect.getsourcelines(func)
    end = start + len(lines) - 1
    file = os.path.relpath(inspect.getsourcefile(func), TAU2_ROOT).replace(os.sep, "/")
    return {"file": file, "start_line": start, "end_line": end, "note": None}


def _tool_ref(domain: str, name: str, method: Any) -> dict:
    tool_type = getattr(method, "__tool_type__", None)
    return {
        "name": name,
        "domain": domain,
        "source": _source_ref(method),
        "docstring": inspect.getdoc(method) or "",
        "signature": str(inspect.signature(method)),
        "mutates_state": bool(getattr(method, "__mutates_state__", True)),
        "tool_type": tool_type.value if hasattr(tool_type, "value") else str(tool_type),
    }


# ---------------------------------------------------------------------------
# Command handlers -- each takes the request's "args" dict, returns the "result" dict.
# ---------------------------------------------------------------------------


def _cmd_ping(args: dict) -> dict:
    return {"pong": True}


def _cmd_list_tools(args: dict) -> dict:
    tools = []
    for domain in DOMAINS:
        env = _introspect_env(domain)
        for name, method in env.tools.tools.items():
            tools.append(_tool_ref(domain, name, method))
    return {"tools": tools}


def _cmd_fresh_env(args: dict) -> dict:
    scenario_id = args["scenario_id"]
    if scenario_id not in DOMAIN_CONSTRUCTORS:
        raise ValueError(
            f"unknown scenario_id {scenario_id!r}; Gate 1a/1b scope supports only a bare "
            f"domain name as scenario_id: {DOMAINS}. Per-task initialization is not wired up "
            "in this milestone -- see adapters/tau2.py module docstring."
        )
    env = DOMAIN_CONSTRUCTORS[scenario_id]()
    env_id = uuid.uuid4().hex
    _LIVE_ENVS[env_id] = {"domain": scenario_id, "scenario_id": scenario_id, "env": env}
    return {"env_id": env_id, "domain": scenario_id, "scenario_id": scenario_id}


def _live_env(env_id: str) -> Any:
    if env_id not in _LIVE_ENVS:
        raise KeyError(f"no live environment for env_id {env_id!r} (was it reset by another process, or never created?)")
    return _LIVE_ENVS[env_id]["env"]


def _cmd_snapshot(args: dict) -> dict:
    env = _live_env(args["env_id"])
    snap = env.tools.db.model_dump(mode="json")
    # Full mutable state (not just the agent-facing DB): telecom carries a second, separately
    # mutable database for user-side tools (TelecomUserDB). See adapters/NOTES.md for why this
    # matters -- user-side tool calls write here, and TelecomEnvironment.sync_tools() can bridge
    # a subset of that state into the agent-facing DB (`tools.db`) after ANY tool call, so a
    # snapshot that omitted it would silently under-report what "full mutable state" means for
    # this domain.
    user_tools = getattr(env, "user_tools", None)
    if user_tools is not None:
        snap["user_db"] = user_tools.db.model_dump(mode="json")
    return {"snapshot": snap}


def _cmd_invoke(args: dict) -> dict:
    env = _live_env(args["env_id"])
    tool = args["tool"]
    tool_args = args.get("args") or {}
    try:
        raw = env.make_tool_call(tool, requestor="assistant", **tool_args)
        env.sync_tools()  # matches Environment.get_response()'s post-call sync (env.py docstring
        # on make_tool_call: "This does not call sync_tools" -- get_response does it for us
        # normally; we replicate that here since we call make_tool_call directly).
        return {"result": {"raw": _to_jsonable(raw), "success": True, "error": None}}
    except Exception as e:  # noqa: BLE001 -- a tool's precondition failure is a normal outcome
        # here, not a worker fault; it is reported to the caller as ToolResult(error=...), never
        # propagated as a wire-protocol failure.
        return {"result": {"raw": None, "success": False, "error": f"{type(e).__name__}: {e}"}}


def _cmd_reset(args: dict) -> dict:
    """The benchmark's OWN reset path -- which, per FINDINGS-VERIFIED.md's resolved reset-scope
    question, is not a method tau2 exposes on Environment/DB at all. tau2 achieves "reset" by
    building an entirely fresh environment per simulation (runner/batch.py:409 ->
    runner/build.py:393 -> the domain's get_environment(), which reloads the DB from disk). This
    handler replicates exactly that: reconstruct via the same DOMAIN_CONSTRUCTORS entry used by
    fresh_env(), and replace the live environment in place so the caller's EnvHandle (env_id)
    keeps referring to the same slot."""
    entry = _LIVE_ENVS.get(args["env_id"])
    if entry is None:
        raise KeyError(f"no live environment for env_id {args['env_id']!r}")
    entry["env"] = DOMAIN_CONSTRUCTORS[entry["domain"]]()
    return {}


def _cmd_source(args: dict) -> dict:
    tool = args["tool"]
    if ":" in tool:
        domain, name = tool.split(":", 1)
        env = _introspect_env(domain)
        if name not in env.tools.tools:
            raise KeyError(f"tool {name!r} not found in domain {domain!r}")
        return {"source": _source_ref(env.tools.tools[name])}

    matches = []
    for domain in DOMAINS:
        env = _introspect_env(domain)
        if tool in env.tools.tools:
            matches.append((domain, env.tools.tools[tool]))
    if not matches:
        raise KeyError(f"tool {tool!r} not found in any in-scope domain {DOMAINS}")
    if len(matches) > 1:
        domains = ", ".join(d for d, _ in matches)
        raise ValueError(
            f"tool name {tool!r} is ambiguous across domains ({domains}); "
            f"disambiguate with 'domain:{tool}'"
        )
    return {"source": _source_ref(matches[0][1])}


def _cmd_patch_tool(args: dict) -> dict:
    """Mutation-experiment-only (adapters/base.py's `patch_tool`; see its docstring): install a
    mutated implementation of `tool` on ONE live environment's `env.tools` instance.
    `env.tools.tools` (toolkit.py's `ToolKitBase.tools` property) is recomputed on every access
    via `getattr(self, name)`, never stored, so an ordinary instance attribute set here
    (`setattr(env.tools, tool, bound_mutant)`) shadows the class method for `getattr` lookups on
    THIS instance only -- Python attribute resolution checks the instance `__dict__` before a
    non-data-descriptor (a plain method) defined on the class. Every other live environment
    (including a fresh one from another `fresh_env()` call) is unaffected, so `_cmd_unpatch_tool`
    has nothing process-wide to undo.

    `mutant_source` is exec'd against the ORIGINAL bound method's own `__globals__` (its
    defining module's real globals, e.g. `tau2.domains.airline.tools`'s namespace) so every name
    the mutant body still reads (`ValueError`, a sibling helper, an imported class, ...) resolves
    exactly as it did before mutation -- see adapters/base.py's `patch_tool` docstring for why
    `mutant_source` is decorator-free (there is nothing here to reapply: `is_tool`'s marker
    attributes are copied onto the new function object directly, not re-run as a decorator)."""
    env = _live_env(args["env_id"])
    tool = args["tool"]
    original = getattr(env.tools, tool)
    original_func = getattr(original, "__func__", original)
    globals_ns = original_func.__globals__
    ns: dict = {}
    exec(compile(args["source"], f"<mutant:{tool}>", "exec"), globals_ns, ns)
    new_func = ns[tool]
    for attr in ("__tool__", "__tool_type__", "__mutates_state__", "__discoverable__"):
        if hasattr(original_func, attr):
            setattr(new_func, attr, getattr(original_func, attr))
    bound = new_func.__get__(env.tools, type(env.tools))
    setattr(env.tools, tool, bound)
    return {}


def _cmd_unpatch_tool(args: dict) -> dict:
    """No-op: see _cmd_patch_tool's docstring -- the patch it installs is scoped to one
    already-live env.tools instance, never to the class or module, so there is nothing
    process-wide to restore. Present so the harness-side `unpatch_tool` call (uniform across
    every adapter, per adapters/base.py) always has a handler to reach."""
    return {}


_HANDLERS: dict[str, Callable[[dict], dict]] = {
    "ping": _cmd_ping,
    "list_tools": _cmd_list_tools,
    "fresh_env": _cmd_fresh_env,
    "snapshot": _cmd_snapshot,
    "invoke": _cmd_invoke,
    "reset": _cmd_reset,
    "source": _cmd_source,
    "patch_tool": _cmd_patch_tool,
    "unpatch_tool": _cmd_unpatch_tool,
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
