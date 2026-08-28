"""Defect-exercise-rate machinery -- experiments/analysis_plan.md sec 2: "For each confirmed
finding, a mechanical trigger predicate over the recorded trajectory, evaluated with no model in
the loop. A trajectory exercises the defect iff at least one recorded call satisfies it."

Two predicates, one per tau2 finding this A/B covers (F5-F8's predicates from the plan's own
table are AgentDojo/MM-ToolSandbox and out of scope for this build -- CLAUDE.md's patch list
names only telecom refuel_data and airline cancel_reservation):

    F2 -- telecom refuel_data, Unenforced Precondition: "a refuel_data call whose line_id
          resolves to a line whose status is not Active at call time." Dynamic (needs the DB
          state at the moment of the call, not just the call's own arguments), so
          `exercised_f2` replays the trajectory's calls one at a time against a fresh
          TASK-scoped, UNPATCHED environment (adapters.tau2.Tau2Adapter.fresh_task_env),
          snapshotting immediately before each call.

    F3 -- airline cancel_reservation, Partial Effect: "a cancel_reservation call on a
          reservation whose flights had available_seats decremented earlier in the SAME
          trajectory." Purely mechanical over the recorded call/result sequence -- no replay
          needed, since "decremented earlier in this trajectory" is answered by whether a prior
          book_reservation call in the same sequence returned that reservation_id.

Both take a `calls` list already normalized to `{"name": str, "arguments": dict, "requestor":
str}` dicts, in trajectory order -- see `extract_calls_with_results` for turning a raw recorded
`messages` list (adapters.tau2.Tau2Adapter.record_trajectory's "messages" field, tau2's own wire
JSON for SimulationRun.messages) into that shape plus the paired tool-call result.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

__all__ = [
    "RecordedCall",
    "extract_calls_with_results",
    "exercised_f2",
    "exercised_f3",
]


@dataclass(frozen=True)
class RecordedCall:
    id: str
    name: str
    arguments: dict
    requestor: str
    result_raw: Any
    result_error: bool


def extract_calls_with_results(messages: list) -> list:
    """Pair each ToolCall in a recorded `messages` list with its ToolMessage result, in
    trajectory order. Mirrors tau2's own environment/environment.py `set_state ->
    get_actions_from_messages` pairing (a tool-call-bearing AssistantMessage/UserMessage is
    always immediately followed by one ToolMessage per call, matched by id) closely enough for
    this project's purposes, but tolerates a message list that is JUST the calls (no
    surrounding user-simulator chat turns) since that is all `record_trajectory`/hand-built test
    trajectories need to carry."""
    calls: list = []
    pending_by_id: dict = {}
    for msg in messages:
        role = msg.get("role")
        if role in ("assistant", "user") and msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                pending_by_id[tc["id"]] = {
                    "id": tc["id"],
                    "name": tc["name"],
                    "arguments": tc.get("arguments") or {},
                    "requestor": tc.get("requestor") or role,
                }
        elif role == "tool":
            tc_id = msg.get("id")
            entry = pending_by_id.pop(tc_id, None)
            if entry is None:
                continue  # a tool result with no matching recorded call -- ignore rather than error
            calls.append(
                RecordedCall(
                    id=entry["id"],
                    name=entry["name"],
                    arguments=entry["arguments"],
                    requestor=entry["requestor"],
                    result_raw=msg.get("content"),
                    result_error=bool(msg.get("error", False)),
                )
            )
    return calls


def exercised_f2(adapter, domain: str, task_id: str, calls: list) -> tuple:
    """Replay `calls` against a fresh, UNPATCHED, task-scoped environment, checking before each
    `refuel_data` call whether the target line is non-Active at that moment. Returns
    (exercised: bool, evidence: list[dict]) -- evidence entries carry the call and the line
    status observed immediately before it, for exactly the tasks/calls that tripped the
    predicate, so a reviewer can audit "at least one recorded call satisfies it" without rerunning
    anything.

    Deliberately invokes every call (not just refuel_data) in order, exactly as recorded, so a
    later call's pre-state reflects every earlier call's effects -- an unenforced precondition
    a few calls into a trajectory only shows up if the state that makes it unenforced (a line
    suspended by an earlier call in the SAME trajectory, say) is actually present."""
    env = adapter.fresh_task_env(domain, task_id)
    evidence: list = []
    for call in calls:
        pre = adapter.snapshot(env)
        if call.name == "refuel_data":
            line_id = call.arguments.get("line_id")
            line = next((l for l in (pre.get("lines") or []) if l.get("line_id") == line_id), None)
            if line is not None and line.get("status") != "Active":
                evidence.append(
                    {
                        "call_id": call.id,
                        "tool": call.name,
                        "arguments": call.arguments,
                        "line_status_at_call": line.get("status"),
                    }
                )
        adapter.invoke(env, call.name, call.arguments, requestor=call.requestor)
    return (len(evidence) > 0, evidence)


def exercised_f3(calls: list) -> tuple:
    """Purely mechanical, no adapter/replay needed: a cancel_reservation call exercises F3 iff
    an EARLIER call in the same trajectory was a successful book_reservation that produced the
    same reservation_id (i.e. the decrement this trajectory itself is responsible for, not one
    already present in the task's initial DB state). Returns (exercised, evidence)."""
    booked_reservation_ids: set = set()
    evidence: list = []
    for call in calls:
        if call.name == "book_reservation" and not call.result_error:
            raw = call.result_raw
            rid = None
            if isinstance(raw, dict):
                rid = raw.get("reservation_id")
            elif isinstance(raw, str):
                import json as _json

                try:
                    parsed = _json.loads(raw)
                    if isinstance(parsed, dict):
                        rid = parsed.get("reservation_id")
                except ValueError:
                    rid = None
            if rid:
                booked_reservation_ids.add(rid)
        elif call.name == "cancel_reservation":
            rid = call.arguments.get("reservation_id")
            if rid in booked_reservation_ids:
                evidence.append({"call_id": call.id, "tool": call.name, "reservation_id": rid})
    return (len(evidence) > 0, evidence)
