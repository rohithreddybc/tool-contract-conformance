"""tau2-bench adapter -- Gate 1a/1b. Implements adapters.base.Adapter for tau2-bench
(repos/tau2 @ c3398666), domains airline, retail, telecom.

WHY THIS FILE TALKS TO A SUBPROCESS INSTEAD OF IMPORTING `tau2` DIRECTLY
--------------------------------------------------------------------------
tau2-bench's pyproject.toml pins `requires-python = ">=3.12,<3.14"`. This project's ambient
interpreter -- the one `python -m unittest discover tests` runs under, per the build
instructions -- is 3.11.7. Those cannot share a process. ARCHITECTURE-FINAL.md sec 2
("Adapter process model") anticipated exactly this class of mismatch for a different pair of
benchmarks (tau2 vs MedAgentBench's 3.9) and mandated a subprocess boundary over JSON on stdio
rather than a shared interpreter; MedAgentBench was later demoted to a static-only case study
and never gets this adapter, but the mismatch shows up again here, between tau2 and the harness
itself, so the same boundary is what makes this adapter importable and runnable at all under the
project's own test command. `Tau2Adapter` below is the harness-side client: pure stdlib, safe to
import under any interpreter. `adapters/_tau2_worker.py` is the tau2-side counterpart, launched
as a child process under a project-local `.venv-tau2` (Python 3.12.13, provisioned with
`uv venv --python 3.12` + `uv pip install -e <tau2 checkout>` -- see this project's build log /
final report for the exact commands and the dependency list that came down transitively).

One worker process is started lazily on first use and kept alive for the adapter's lifetime
(tau2's own import graph pulls in litellm, which alone costs several seconds -- paying that once
per `Tau2Adapter` instance, not once per call, is the whole point of keeping a live worker
rather than re-launching per request). Use `Tau2Adapter` as a context manager, or call
`close()` explicitly, to make sure the worker is not leaked.

SCOPE NOTE -- scenario_id. `fresh_env(scenario_id)` currently accepts only a bare in-scope
domain name ("airline", "retail", "telecom") and loads that domain's on-disk default database.
Per-task initialization (tau2's `InitializationData`, applied via `Environment.set_state`) is
not wired up in this milestone; Gate 1a/1b probe tools directly against the default database
rather than against a specific task's initial state. Extending `scenario_id` to
"domain:task_id" is the natural next step and is left for the dynamic-harness work
(ARCHITECTURE-FINAL.md sec 6, Tier 1 trajectory replay) which needs task-scoped environments
regardless.

SCOPE NOTE -- assistant tools only. `list_tools()`/`invoke()` cover the tools tau2 exposes to
the AGENT (`Environment.tools`), matching what the one shipped contract
(spec/contracts/tau2/cancel_reservation.yaml) and the new one authored alongside this adapter
(spec/contracts/tau2/refuel_data.yaml) both describe. telecom's separate user-facing toolkit
(`Environment.user_tools`) is a distinct mutating surface -- see adapters/NOTES.md, which
answers the "can the user simulator mutate state" question this adapter's existence was
partly commissioned to resolve -- but calling a user-side tool through this adapter is not
exposed yet; `snapshot()` still captures user-side state (see its docstring) so that omission is
visible in a diff even though it can't be triggered through `invoke()` today.
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
from pathlib import Path
from typing import Optional

from adapters.base import Adapter, EnvHandle, SourceRef, ToolRef, ToolResult

__all__ = ["Tau2Adapter", "Tau2AdapterError"]

PROJECT_ROOT = Path(__file__).resolve().parent.parent
_VENV_DIR = PROJECT_ROOT / ".venv-tau2"
_WORKER_SCRIPT = Path(__file__).resolve().parent / "_tau2_worker.py"

IN_SCOPE_DOMAINS = ("airline", "retail", "telecom")


def _default_venv_python() -> Path:
    if os.name == "nt":
        return _VENV_DIR / "Scripts" / "python.exe"
    return _VENV_DIR / "bin" / "python"


class Tau2AdapterError(RuntimeError):
    """Raised for a worker-side failure (bad request, tool not found, ...) or a protocol-level
    problem (worker died, sent unparseable output). Wraps enough of the worker's error message
    to be useful without leaking the JSON wire format into caller code."""


class Tau2Adapter(Adapter):
    """Adapter for tau2-bench, domains airline/retail/telecom. See module docstring for the
    subprocess boundary this class owns.

    Args:
        venv_python: path to the tau2 environment's python executable. Defaults to
            `<project_root>/.venv-tau2/Scripts/python.exe` (`.../bin/python` off Windows).
        repo_check: if True (default), verify at construction time that the worker's tau2
            package is importable and reports the expected pinned commit is at least present
            as a plausible checkout (best-effort; see `_verify_worker` -- this is a fast-fail
            for "the venv was never provisioned", not a substitute for pinning by commit, which
            is the caller's responsibility when choosing `venv_python`).
    """

    def __init__(self, venv_python: Optional[Path] = None, *, repo_check: bool = True):
        self._venv_python = Path(venv_python) if venv_python else _default_venv_python()
        self._proc: Optional[subprocess.Popen] = None
        self._next_id = 0
        self._lock = threading.Lock()
        self._tool_index: Optional[dict[str, list[ToolRef]]] = None  # name -> [ToolRef, ...]
        if repo_check and not self._venv_python.exists():
            raise Tau2AdapterError(
                f"tau2 venv python not found at {self._venv_python}. Provision it with:\n"
                f"  uv venv --python 3.12 {_VENV_DIR.relative_to(PROJECT_ROOT)}\n"
                f"  uv pip install --python {self._venv_python} -e <path to tau2 checkout @ pinned commit>"
            )

    # -- process lifecycle ---------------------------------------------------

    def _ensure_started(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            return
        env = dict(os.environ)
        # PYTHONUTF8: tau2's policy-document loader opens files with the platform default text
        # encoding. On Windows that's the ANSI codepage (cp1252 here), which raises
        # UnicodeDecodeError on the telecom tech-support policy docs (they contain non-ASCII
        # punctuation). Forcing UTF-8 mode is the fix; found by running the worker's own domain
        # constructors standalone against this checkout before wiring up the subprocess.
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        self._proc = subprocess.Popen(
            [str(self._venv_python), "-u", str(_WORKER_SCRIPT)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=None,  # inherit, deliberately NOT a pipe -- see _tau2_worker.py's module
            # docstring: tau2 logs verbosely via loguru, and an undrained stderr PIPE risks
            # deadlocking the child once the OS pipe buffer fills.
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
        # subprocess.Popen with stdin/stdout=PIPE opens file objects that are only closed by
        # communicate()/wait() as a side effect on some platforms, not guaranteed on Windows --
        # close them explicitly rather than relying on GC (which raised ResourceWarning here).
        for stream in (proc.stdin, proc.stdout):
            try:
                if stream is not None:
                    stream.close()
            except Exception:
                pass
        self._proc = None

    def __enter__(self) -> "Tau2Adapter":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    # -- wire protocol --------------------------------------------------------

    def _send(self, req: dict) -> dict:
        """Send one request, block for its response. One request in flight at a time (the
        worker is strictly synchronous) -- the lock protects concurrent callers, not pipelining."""
        with self._lock:
            self._ensure_started()
            assert self._proc is not None and self._proc.stdin is not None and self._proc.stdout is not None
            self._next_id += 1
            req = {**req, "id": self._next_id}
            try:
                self._proc.stdin.write(json.dumps(req) + "\n")
                self._proc.stdin.flush()
            except (BrokenPipeError, OSError) as e:
                raise Tau2AdapterError(
                    f"tau2 worker process is not accepting input (exit code {self._proc.poll()}): {e}"
                ) from e

            # Skip any line that isn't a marked protocol reply (adapters/_tau2_worker.py's
            # _reply() prefixes every line it writes with _REPLY_MARKER). Needed in practice for
            # the record_trajectory path: on a failed live model call, litellm writes its own
            # multi-line "Give Feedback" / "LiteLLM.Info" banner straight to stdout -- not
            # through logging, so it isn't suppressed by the loguru level filter, and stdout is
            # the only piped stream this protocol reads line-by-line (stderr is inherited, not
            # piped -- see _ensure_started's docstring). Bounded so a truly wedged process still
            # raises instead of looping forever.
            _REPLY_MARKER = "\x01"
            skipped = 0
            while True:
                line = self._proc.stdout.readline()
                if line == "":
                    rc = self._proc.poll()
                    raise Tau2AdapterError(f"tau2 worker process closed its output unexpectedly (exit code {rc})")
                if line.startswith(_REPLY_MARKER):
                    line = line[len(_REPLY_MARKER):]
                    break
                skipped += 1
                if skipped > 10000:
                    raise Tau2AdapterError(
                        "tau2 worker: gave up after 10000 non-protocol lines on stdout without a reply"
                    )
            try:
                resp = json.loads(line)
            except json.JSONDecodeError as e:
                raise Tau2AdapterError(f"tau2 worker sent non-JSON output: {line!r} ({e})") from e

            if not resp.get("ok", False):
                raise Tau2AdapterError(f"tau2 worker reported an error for cmd {req.get('cmd')!r}: {resp.get('error')}")
            return resp.get("result", {})

    # -- Adapter interface ------------------------------------------------------

    def list_tools(self) -> list[ToolRef]:
        result = self._send({"cmd": "list_tools"})
        refs = [
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
        index: dict[str, list[ToolRef]] = {}
        for ref in refs:
            index.setdefault(ref.name, []).append(ref)
        self._tool_index = index
        return refs

    def fresh_env(self, scenario_id: str) -> EnvHandle:
        result = self._send({"cmd": "fresh_env", "args": {"scenario_id": scenario_id}})
        return EnvHandle(env_id=result["env_id"], domain=result["domain"], scenario_id=result["scenario_id"])

    def fresh_task_env(self, domain: str, task_id: str) -> EnvHandle:
        """Agent-impact-experiment extension (ARCHITECTURE-FINAL.md sec 6, experiments/ab_run.py):
        a live environment initialized from ONE task's own `initial_state`, not the domain's bare
        on-disk default -- see adapters/_tau2_worker.py's `_cmd_fresh_task_env` docstring. Unlike
        `fresh_env`, `scenario_id` here is split into (domain, task_id) rather than encoded as a
        single string, since task IDs can themselves contain ':' (see tasks.json)."""
        result = self._send({"cmd": "fresh_task_env", "args": {"domain": domain, "task_id": task_id}})
        return EnvHandle(env_id=result["env_id"], domain=result["domain"], scenario_id=result["scenario_id"])

    def snapshot(self, env: EnvHandle) -> dict:
        result = self._send({"cmd": "snapshot", "args": {"env_id": env.env_id}})
        return result["snapshot"]

    def invoke(self, env: EnvHandle, tool: str, args: dict, *, requestor: str = "assistant") -> ToolResult:
        result = self._send(
            {"cmd": "invoke", "args": {"env_id": env.env_id, "tool": tool, "args": args, "requestor": requestor}}
        )
        r = result["result"]
        return ToolResult(raw=r["raw"], success=r["success"], error=r["error"])

    def record_trajectory(
        self,
        domain: str,
        task_id: str,
        *,
        agent: Optional[str] = None,
        user: Optional[str] = None,
        llm_agent: Optional[str] = None,
        llm_user: Optional[str] = None,
        llm_args_agent: Optional[dict] = None,
        llm_args_user: Optional[dict] = None,
        seed: Optional[int] = None,
        max_steps: Optional[int] = None,
        max_errors: Optional[int] = None,
    ) -> dict:
        """Run tau2's own orchestrator (LLMAgent + UserSimulator, a REAL model call via litellm)
        once against task `task_id` in `domain`, and return the recorded trajectory. See
        adapters/_tau2_worker.py's `_cmd_record_trajectory` docstring: this is the one call in
        the whole adapter that is not deterministic and not free, and experiments/ab_run.py must
        call it AT MOST ONCE per task (experiments/analysis_plan.md sec 4, no re-rolls).

        Any argument left as None falls back to tau2's own config.py default (DEFAULT_LLM_AGENT,
        DEFAULT_SEED, temperature 0.0 for both agent and user, ...) -- passing nothing at all
        already satisfies "fixed model, fixed prompts, fixed seeds, temperature 0."

        Raises Tau2AdapterError (wrapping whatever the worker reported -- a missing API key, a
        provider error, ...) if the live model call fails. Does not retry and does not fabricate
        a fallback trajectory; the caller decides what "recording failed" means for its report.
        """
        args: dict = {"domain": domain, "task_id": task_id}
        for key, value in (
            ("agent", agent),
            ("user", user),
            ("llm_agent", llm_agent),
            ("llm_user", llm_user),
            ("llm_args_agent", llm_args_agent),
            ("llm_args_user", llm_args_user),
            ("seed", seed),
            ("max_steps", max_steps),
            ("max_errors", max_errors),
        ):
            if value is not None:
                args[key] = value
        return self._send({"cmd": "record_trajectory", "args": args})

    def replay_and_score(
        self,
        domain: str,
        task_id: str,
        messages: list,
        *,
        patch: Optional[dict] = None,
        strict_replay: bool = False,
    ) -> dict:
        """Tier-1 replay (ARCHITECTURE-FINAL.md sec 6): re-execute a recorded trajectory's tool
        calls against a fresh task-scoped environment and score the result with tau2's own
        evaluator (tau2.evaluator.evaluator_env.EnvironmentEvaluator, unmodified). No model in
        this call. `patch`, if given, is `{"tool": <name>, "source": <decorator-free function
        source>}` -- the same shape `patch_tool` accepts. Call this twice with the identical
        `messages` (once with patch=None, once with the finding's patch) and compare the two
        `reward_info["reward"]` values to read the flip -- see
        adapters/_tau2_worker.py's `_cmd_replay_and_score` docstring."""
        args: dict = {
            "domain": domain,
            "task_id": task_id,
            "messages": messages,
            "strict_replay": strict_replay,
        }
        if patch is not None:
            args["patch"] = patch
        return self._send({"cmd": "replay_and_score", "args": args})

    def reset(self, env: EnvHandle) -> None:
        self._send({"cmd": "reset", "args": {"env_id": env.env_id}})

    def source(self, tool: str) -> SourceRef:
        result = self._send({"cmd": "source", "args": {"tool": tool}})
        return SourceRef.from_dict(result["source"])

    def patch_tool(self, env: EnvHandle, tool: str, mutant_source: str) -> None:
        """Scoped to `env` alone -- see adapters/_tau2_worker.py's `_cmd_patch_tool` docstring
        and adapters/base.py's `Adapter.patch_tool`."""
        self._send({"cmd": "patch_tool", "args": {"env_id": env.env_id, "tool": tool, "source": mutant_source}})

    def unpatch_tool(self, tool: str) -> None:
        """No-op -- see `patch_tool`'s docstring."""
        return None
