"""AgentDojo adapter -- closes the rigour gap CLAUDE.md's build spec names: until this file
existed, `analysis/score_at_risk.py` seeded AgentDojo's step-1 field extraction directly from
citations in FINDINGS-VERIFIED.md rather than from a shipped contract, because no AgentDojo
contract existed. This is that adapter. Implements adapters.base.Adapter for AgentDojo
(repos/agentdojo @ 089ed468cf3ed0322acc66b0211f26d9d90dbf60), v1 suites banking/slack/travel/
workspace, per repos/AGENTDOJO-SPIKE.md's GO verdict.

WHY THIS FILE ALSO TALKS TO A SUBPROCESS, EVEN THOUGH THERE IS NO INTERPRETER-VERSION CONFLICT
--------------------------------------------------------------------------------------------
adapters/tau2.py's subprocess boundary exists because tau2 requires Python >=3.12 and this
project's ambient interpreter is 3.11.7 -- a hard, unavoidable mismatch. AgentDojo requires only
`>=3.10` (repos/AGENTDOJO-SPIKE.md sec "Clone command" preamble; pyproject.toml:31), which the
ambient 3.11.7 interpreter already satisfies. THIS IS THE ONE PLACE THIS BUILD DID NOT FIT THE
EXISTING ADAPTER PATTERN CLEANLY: adapters/base.py's docstring frames the subprocess boundary as
existing specifically for cross-interpreter-version cases, and AgentDojo is not one.

The subprocess boundary is used here anyway, for a DIFFERENT reason the base interface does not
name: AgentDojo's `[project.dependencies]` hard-require `openai`, `anthropic`, `cohere`,
`google-genai`, and `langchain` unconditionally (AGENTDOJO-SPIKE.md sec 2 -- importing any v1
suite module transitively imports `agentdojo.agent_pipeline`, which does `import anthropic`
unconditionally). None of these are called at tool-invocation time, but all of them must resolve
at import time, which means installing AgentDojo into this project's own ambient interpreter (the
one `python -m unittest discover tests` and every other adapter's test run under) would pin that
interpreter's site-packages to AgentDojo's transitive dependency closure -- a form of silent
cross-project contamination adapters/tau2.py's isolation already avoids for a different reason.
Routing through `.venv-agentdojo` (provisioned the same way as `.venv-tau2`: `uv venv --python
3.11 .venv-agentdojo` + `uv pip install --python .venv-agentdojo/Scripts/python.exe -e <path to
agentdojo checkout @ pinned commit>`) keeps that dependency closure out of the harness's own
interpreter entirely. Recorded here rather than left implicit, per the build instructions'
request to report "anything in the adapter interface that did not fit these two benchmarks."

`AgentDojoAdapter` is the harness-side client (pure stdlib, mirrors adapters/tau2.py's
Tau2Adapter class-for-class); `adapters/_agentdojo_worker.py` is the AgentDojo-side counterpart
and owns the mutating-tool enumeration rule (see its module docstring) and the wire protocol.

SCOPE NOTE -- suites. In scope: banking, slack, travel, workspace (the four v1 suites with a
`tools/` package). `default_suites/v1_1` through `v1_2_2` are task-level overlays on the same
tool classes via `TaskSuite.get_new_version()` and add no tools of their own (confirmed in the
spike by directory listing); this adapter does not expose them as separate scenario_ids, since
doing so would double-count the same 25 tool implementations under six more scenario names.

SCOPE NOTE -- scenario_id. `fresh_env(scenario_id)` accepts a bare in-scope suite name and loads
that suite's default environment via `load_and_inject_default_environment({})` -- the same
"probe against the default fixture, not a specific task's initial state" scoping tau2.py's
`fresh_env` uses, for the same reason (Gate-equivalent probes need a live environment, not a
specific task's injected placeholders).
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
from pathlib import Path
from typing import Optional

from adapters.base import Adapter, EnvHandle, SourceRef, ToolRef, ToolResult

__all__ = ["AgentDojoAdapter", "AgentDojoAdapterError"]

PROJECT_ROOT = Path(__file__).resolve().parent.parent
_VENV_DIR = PROJECT_ROOT / ".venv-agentdojo"
_WORKER_SCRIPT = Path(__file__).resolve().parent / "_agentdojo_worker.py"

IN_SCOPE_SUITES = ("banking", "slack", "travel", "workspace")


def _default_venv_python() -> Path:
    if os.name == "nt":
        return _VENV_DIR / "Scripts" / "python.exe"
    return _VENV_DIR / "bin" / "python"


class AgentDojoAdapterError(RuntimeError):
    """Mirrors adapters.tau2.Tau2AdapterError's role: a worker-side failure or a protocol-level
    problem, never leaking the JSON wire format into caller code."""


class AgentDojoAdapter(Adapter):
    """Adapter for AgentDojo, v1 suites banking/slack/travel/workspace. See module docstring for
    why this uses a subprocess boundary despite no interpreter-version conflict.

    Args:
        venv_python: path to the AgentDojo environment's python executable. Defaults to
            `<project_root>/.venv-agentdojo/Scripts/python.exe` (`.../bin/python` off Windows).
        repo_check: if True (default), fail fast if the venv python does not exist, mirroring
            adapters.tau2.Tau2Adapter's constructor-time check.
    """

    def __init__(self, venv_python: Optional[Path] = None, *, repo_check: bool = True):
        self._venv_python = Path(venv_python) if venv_python else _default_venv_python()
        self._proc: Optional[subprocess.Popen] = None
        self._next_id = 0
        self._lock = threading.Lock()
        if repo_check and not self._venv_python.exists():
            raise AgentDojoAdapterError(
                f"agentdojo venv python not found at {self._venv_python}. Provision it with:\n"
                f"  uv venv --python 3.11 {_VENV_DIR.relative_to(PROJECT_ROOT)}\n"
                f"  uv pip install --python {self._venv_python} -e <path to agentdojo checkout @ pinned commit>"
            )

    # -- process lifecycle (identical shape to adapters.tau2.Tau2Adapter) -------------------

    def _ensure_started(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            return
        env = dict(os.environ)
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        self._proc = subprocess.Popen(
            [str(self._venv_python), "-u", str(_WORKER_SCRIPT)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=None,  # inherit -- see adapters/_tau2_worker.py's docstring for why a piped,
            # undrained stderr risks a deadlock; the same reasoning applies here even though
            # AgentDojo is far quieter than tau2's loguru output.
            cwd=str(PROJECT_ROOT),
            env=env,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )

    def close(self) -> None:
        if self._proc is None:
            return
        proc = self._proc
        if proc.poll() is None:
            try:
                self._send({"cmd": "shutdown"})
            except Exception:
                pass
            try:
                proc.wait(timeout=5)
            except Exception:
                proc.kill()
        for stream in (proc.stdin, proc.stdout):
            try:
                if stream is not None:
                    stream.close()
            except Exception:
                pass
        self._proc = None

    def __enter__(self) -> "AgentDojoAdapter":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    # -- wire protocol (identical shape to adapters.tau2.Tau2Adapter._send) -----------------

    def _send(self, req: dict) -> dict:
        with self._lock:
            self._ensure_started()
            assert self._proc is not None and self._proc.stdin is not None and self._proc.stdout is not None
            self._next_id += 1
            req = {**req, "id": self._next_id}
            try:
                self._proc.stdin.write(json.dumps(req) + "\n")
                self._proc.stdin.flush()
            except (BrokenPipeError, OSError) as e:
                raise AgentDojoAdapterError(
                    f"agentdojo worker process is not accepting input (exit code {self._proc.poll()}): {e}"
                ) from e

            line = self._proc.stdout.readline()
            if line == "":
                rc = self._proc.poll()
                raise AgentDojoAdapterError(f"agentdojo worker process closed its output unexpectedly (exit code {rc})")
            try:
                resp = json.loads(line)
            except json.JSONDecodeError as e:
                raise AgentDojoAdapterError(f"agentdojo worker sent non-JSON output: {line!r} ({e})") from e

            if not resp.get("ok", False):
                raise AgentDojoAdapterError(f"agentdojo worker reported an error for cmd {req.get('cmd')!r}: {resp.get('error')}")
            return resp.get("result", {})

    # -- Adapter interface --------------------------------------------------------------------

    def list_tools(self) -> list[ToolRef]:
        result = self._send({"cmd": "list_tools"})
        return [
            ToolRef(
                name=t["name"],
                domain=t["domain"],
                source=SourceRef.from_dict(t["source"]),
                docstring=t["docstring"],
                signature=t["signature"],
                mutates_state=t["mutates_state"],
                tool_type=t["tool_type"],
            )
            for t in result["tools"]
        ]

    def fresh_env(self, scenario_id: str) -> EnvHandle:
        result = self._send({"cmd": "fresh_env", "args": {"scenario_id": scenario_id}})
        return EnvHandle(env_id=result["env_id"], domain=result["domain"], scenario_id=result["scenario_id"])

    def snapshot(self, env: EnvHandle) -> dict:
        result = self._send({"cmd": "snapshot", "args": {"env_id": env.env_id}})
        return result["snapshot"]

    def invoke(self, env: EnvHandle, tool: str, args: dict) -> ToolResult:
        result = self._send({"cmd": "invoke", "args": {"env_id": env.env_id, "tool": tool, "args": args}})
        r = result["result"]
        return ToolResult(raw=r["raw"], success=r["success"], error=r["error"])

    def reset(self, env: EnvHandle) -> None:
        self._send({"cmd": "reset", "args": {"env_id": env.env_id}})

    def source(self, tool: str) -> SourceRef:
        result = self._send({"cmd": "source", "args": {"tool": tool}})
        return SourceRef.from_dict(result["source"])
