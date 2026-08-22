"""ToyAdapter -- implements adapters.base.Adapter for toy/bank.py. Purely in-process: unlike
adapters/tau2.py, the toy domain has no cross-interpreter version conflict to route around (it is
pure stdlib Python, importable under the project's own 3.11.7), so this adapter is a direct,
synchronous wrapper rather than a subprocess client. It exists to let the SAME harness code that
will eventually drive a real benchmark adapter also drive the toy domain -- "make it
adapter-compatible so the existing harness drives it" (CLAUDE.md build spec) -- and, right now, to
give mutation/*.py something real to import and run against in this milestone's tests.

Source-location note (`source()`): line ranges are read off toy/bank.py directly (not computed
by inspecting the live object with `inspect.getsource`, though that would also work) so they stay
exact even if a future refactor reorders methods without updating this table -- a stale entry
here would fail loudly the next time tests/test_toy_adapter.py's line-range assertions run against
the file, which is the point.
"""
from __future__ import annotations

import uuid

from adapters.base import Adapter, EnvHandle, SourceRef, ToolRef, ToolResult
from toy.bank import MUTATING_TOOLS, ToyBank, ToyError

__all__ = ["ToyAdapter", "ToyAdapterError", "TOOL_SOURCE_RANGES"]

DOMAIN = "toy"
BANK_FILE = "toy/bank.py"

# tool name -> (start_line, end_line) in toy/bank.py, `def` line through the tool's last
# statement. Kept as a literal table rather than derived via ast/inspect so this file has zero
# import-time dependency on toy/bank.py's exact formatting -- see module docstring.
TOOL_SOURCE_RANGES: dict[str, tuple[int, int]] = {
    "deposit": (85, 97),
    "withdraw": (99, 113),
    "transfer": (115, 142),
    "freeze_account": (144, 153),
    "unfreeze_account": (155, 164),
    "reserve_item": (166, 187),
    "release_item": (189, 202),
    "acquire_lock": (204, 215),
    "release_lock": (217, 236),
    "resize_inventory": (238, 264),
    "tag_item": (266, 278),
}

_SIGNATURES: dict[str, str] = {
    "deposit": "deposit(account_id: str, amount: float) -> dict",
    "withdraw": "withdraw(account_id: str, amount: float) -> dict",
    "transfer": "transfer(from_account: str, to_account: str, amount: float) -> dict",
    "freeze_account": "freeze_account(account_id: str) -> dict",
    "unfreeze_account": "unfreeze_account(account_id: str) -> dict",
    "reserve_item": "reserve_item(item_id: str, qty: int, account_id: str) -> dict",
    "release_item": "release_item(item_id: str, qty: int) -> dict",
    "acquire_lock": "acquire_lock(lock_id: str, holder: str) -> dict",
    "release_lock": "release_lock(lock_id: str, holder: str) -> dict",
    "resize_inventory": "resize_inventory(item_id: str, delta: int, mode: str) -> dict",
    "tag_item": "tag_item(item_id: str, tag: str) -> dict",
}


class ToyAdapterError(RuntimeError):
    """Raised for an unknown env_id/tool name, mirroring adapters.tau2.Tau2AdapterError's role
    for the real adapter (a caller-facing error that never leaks an internal exception type)."""


class ToyAdapter(Adapter):
    """In-process Adapter for the toy domain. One ToyBank instance per `fresh_env()` call, keyed
    by an opaque env_id (adapters.base.EnvHandle's contract: callers must never construct one by
    hand)."""

    def __init__(self) -> None:
        self._envs: dict[str, ToyBank] = {}

    def list_tools(self) -> list[ToolRef]:
        import toy.bank as bank_module

        refs: list[ToolRef] = []
        for name in MUTATING_TOOLS:
            fn = getattr(bank_module.ToyBank, name)
            start, end = TOOL_SOURCE_RANGES[name]
            refs.append(
                ToolRef(
                    name=name,
                    domain=DOMAIN,
                    source=SourceRef(file=BANK_FILE, start_line=start, end_line=end),
                    docstring=(fn.__doc__ or "").strip(),
                    signature=_SIGNATURES[name],
                    mutates_state=True,
                    tool_type="WRITE",
                )
            )
        return refs

    def fresh_env(self, scenario_id: str) -> EnvHandle:
        # The toy domain has exactly one scenario -- make_initial_state() is deterministic, so
        # any scenario_id maps to the same initial snapshot. scenario_id is still threaded
        # through and echoed in the handle, matching adapters.tau2.Tau2Adapter's shape, so
        # harness code written against the Adapter interface doesn't need a toy-domain special
        # case here either.
        env_id = uuid.uuid4().hex
        self._envs[env_id] = ToyBank()
        return EnvHandle(env_id=env_id, domain=DOMAIN, scenario_id=scenario_id)

    def _get(self, env: EnvHandle) -> ToyBank:
        bank = self._envs.get(env.env_id)
        if bank is None:
            raise ToyAdapterError(f"unknown env_id: {env.env_id}")
        return bank

    def snapshot(self, env: EnvHandle) -> dict:
        import copy

        return copy.deepcopy(self._get(env).state)

    def invoke(self, env: EnvHandle, tool: str, args: dict) -> ToolResult:
        bank = self._get(env)
        if tool not in MUTATING_TOOLS:
            raise ToyAdapterError(f"unknown tool: {tool}")
        fn = getattr(bank, tool)
        try:
            raw = fn(**args)
        except ToyError as e:
            return ToolResult(raw=None, success=False, error=str(e))
        return ToolResult(raw=raw, success=True, error=None)

    def reset(self, env: EnvHandle) -> None:
        self._get(env).reset()

    def source(self, tool: str) -> SourceRef:
        if tool not in TOOL_SOURCE_RANGES:
            raise ToyAdapterError(f"unknown tool: {tool}")
        start, end = TOOL_SOURCE_RANGES[tool]
        return SourceRef(file=BANK_FILE, start_line=start, end_line=end)
