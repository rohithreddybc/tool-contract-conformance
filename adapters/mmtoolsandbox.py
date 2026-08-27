"""MM-ToolSandbox adapter -- the harness-side client half of the boundary described in
adapters/base.py and adapters/tau2.py's module docstrings. Implements adapters.base.Adapter for
MM-ToolSandbox (repos/mmtoolsandbox @ 1e8e9324abcb741cc6a9718f9e7c1b80e85a1363), per
repos/MMTOOLSANDBOX-SPIKE.md's "GO, scoped" verdict. Mirrors adapters/agentdojo.py class-for-class
(same subprocess wire protocol, same lifecycle) -- see that module's docstring for why the
subprocess boundary is used even though `adapters/_mmtoolsandbox_worker.py` runs under Python
3.11, the same major version as this project's own ambient interpreter: MM-ToolSandbox's package
import graph (`common/safety_guard.py:22`'s unconditional `import resource`, POSIX-only stdlib)
fails outright on native Windows without the shim `adapters/_mmtoolsandbox_worker.py` installs
before importing the package (see that module's docstring), and routing through a dedicated
`.venv-mmtoolsandbox` keeps that shim, and MM-ToolSandbox's own dependency closure, out of this
project's own interpreter -- the same isolation argument adapters/agentdojo.py makes for a
different reason (AgentDojo's unconditional `anthropic`/`openai`/... imports).

SCOPE BOUNDARY -- read this before adding a scenario_id. CLAUDE.md's build instructions are
explicit: "Do not attempt the AppWorld tier -- that package cannot be cloned (LFS quota exceeded,
recorded in FINDINGS-VERIFIED.md), so its 296 tools are static-reading only." This adapter
exposes exactly the two scenarios `adapters/_mmtoolsandbox_worker.py` implements, and nothing
from the raw `tools/appworld/*.py` layer beyond the one hand-written seam MM-ToolSandbox's own
code controls:

  "tool_sandbox"    -- the self-contained, in-process, offline calendar/reminder/setting domain.
                       Fully dynamic: fresh_env/snapshot/invoke/reset all execute real
                       MM-ToolSandbox code end to end, no stub anywhere in the call path.

  "venmo_boundary"  -- the `tools/mini/venmo.py` dispatch facade (`venmo_social`,
                       `venmo_transact`), executed for real up to the one line that would hand
                       off to a live `AppWorldBridge` (`_get(name)(...)`), which this worker
                       intercepts with a recording stub -- repos/MMTOOLSANDBOX-SPIKE.md's own
                       verification method, reused rather than reinvented. `snapshot()` for this
                       scenario returns the boundary-call log (`{"boundary_calls": [...]}`):
                       every {tool name, forwarded kwargs} MM-ToolSandbox's own code decided to
                       send onward. This is real, agent-adjacent, observable state -- exactly
                       what would cross the wire to AppWorld -- not a synthetic test fixture, and
                       contracts against this scenario assert only over that log
                       (`post.boundary_calls`), never over anything inside AppWorld itself.

Any claim about the other 295 appworld-tier mutating tools, or the compact/consolidated dispatch
tiers, remains the static-reading-only claim repos/MMTOOLSANDBOX-SPIKE.md already made -- this
adapter does not extend it.
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
from pathlib import Path
from typing import Optional

from adapters.base import Adapter, EnvHandle, SourceRef, ToolRef, ToolResult

__all__ = ["MMToolSandboxAdapter", "MMToolSandboxAdapterError"]

PROJECT_ROOT = Path(__file__).resolve().parent.parent
_VENV_DIR = PROJECT_ROOT / ".venv-mmtoolsandbox"
_WORKER_SCRIPT = Path(__file__).resolve().parent / "_mmtoolsandbox_worker.py"

# Matches adapters/_mmtoolsandbox_worker.py's IN_SCOPE_SCENARIOS exactly -- see module docstring
# for what each one is and is not.
IN_SCOPE_SCENARIOS = ("tool_sandbox", "venmo_boundary")


def _default_venv_python() -> Path:
    if os.name == "nt":
        return _VENV_DIR / "Scripts" / "python.exe"
    return _VENV_DIR / "bin" / "python"


class MMToolSandboxAdapterError(RuntimeError):
    """Mirrors adapters.tau2.Tau2AdapterError / adapters.agentdojo.AgentDojoAdapterError's role:
    a worker-side failure or a protocol-level problem, never leaking the JSON wire format into
    caller code."""


class MMToolSandboxAdapter(Adapter):
    """Adapter for MM-ToolSandbox, scenarios "tool_sandbox" and "venmo_boundary". See module
    docstring for the scope boundary and why a subprocess is used.

    Args:
        venv_python: path to the MM-ToolSandbox environment's python executable. Defaults to
            `<project_root>/.venv-mmtoolsandbox/Scripts/python.exe` (`.../bin/python` off
            Windows).
        repo_check: if True (default), fail fast if the venv python does not exist, mirroring
            adapters.tau2.Tau2Adapter / adapters.agentdojo.AgentDojoAdapter's constructor-time
            check.
    """

    def __init__(self, venv_python: Optional[Path] = None, *, repo_check: bool = True):
        self._venv_python = Path(venv_python) if venv_python else _default_venv_python()
        self._proc: Optional[subprocess.Popen] = None
        self._next_id = 0
        self._lock = threading.Lock()
        if repo_check and not self._venv_python.exists():
            raise MMToolSandboxAdapterError(
                f"mmtoolsandbox venv python not found at {self._venv_python}. Provision it with:\n"
                f"  uv venv --python 3.11 {_VENV_DIR.relative_to(PROJECT_ROOT)}\n"
                f"  uv pip install --python {self._venv_python} -e <path to mmtoolsandbox checkout @ pinned commit>"
            )

    # -- process lifecycle (identical shape to adapters.tau2.Tau2Adapter / adapters.agentdojo.AgentDojoAdapter) --

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
            # undrained stderr risks a deadlock; the same reasoning applies here.
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

    def __enter__(self) -> "MMToolSandboxAdapter":
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
                raise MMToolSandboxAdapterError(
                    f"mmtoolsandbox worker process is not accepting input (exit code {self._proc.poll()}): {e}"
                ) from e

            line = self._proc.stdout.readline()
            if line == "":
                rc = self._proc.poll()
                raise MMToolSandboxAdapterError(f"mmtoolsandbox worker process closed its output unexpectedly (exit code {rc})")
            try:
                resp = json.loads(line)
            except json.JSONDecodeError as e:
                raise MMToolSandboxAdapterError(f"mmtoolsandbox worker sent non-JSON output: {line!r} ({e})") from e

            if not resp.get("ok", False):
                raise MMToolSandboxAdapterError(f"mmtoolsandbox worker reported an error for cmd {req.get('cmd')!r}: {resp.get('error')}")
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

    def patch_tool(self, env: EnvHandle, tool: str, mutant_source: str) -> None:
        """Process-wide, not scoped to `env` -- see adapters/_mmtoolsandbox_worker.py's
        `_cmd_patch_tool` docstring. Callers must call `unpatch_tool` when done with this
        mutant."""
        self._send({"cmd": "patch_tool", "args": {"env_id": env.env_id, "tool": tool, "source": mutant_source}})

    def unpatch_tool(self, tool: str) -> None:
        self._send({"cmd": "unpatch_tool", "args": {"tool": tool}})
