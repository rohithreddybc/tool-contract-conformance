# Adapter notes: can the tau2 user simulator mutate environment state?

Open question from the methodology review (ARCHITECTURE-FINAL.md sec 9 risk list is the closest
written trace of the concern; the question itself was raised verbally and is answered here for
the first time). Answer matters because if user-side tools write to the DB, trajectory replay
(ARCHITECTURE-FINAL.md sec 6, Tier 1) must record and replay THOSE calls too, not just the
agent's — a replay that only re-executes the agent's tool calls would silently diverge from the
live run's final state whenever the user simulator's own actions mutated anything.

Method: read every domain's `environment.py` and toolkit module in `repos/tau2` at commit
`c3398666`, cross-checked against `tau2.registry` (which domains actually get a `user_tools`
argument) and confirmed empirically against a live environment via the `.venv-tau2` interpreter
(commands and output below). Not inferred from documentation — every claim here was executed.

## Per-domain answer

| Domain | `Environment.user_tools` | User-side WRITE tools | Can the user simulator mutate state? |
|---|---|---|---|
| airline | `None` | n/a | **No.** `domains/airline/environment.py get_environment()` constructs `Environment(domain_name="airline", policy=policy, tools=tools)` — no `user_tools` argument at all. `Environment.use_user_tool()` / `get_user_tools()` raise `ValueError("User tools not available")` if called. The airline user simulator is purely conversational; it cannot call anything with a DB effect. |
| retail | `None` | n/a | **No.** Same shape as airline — `domains/retail/environment.py get_environment()` passes no `user_tools`. |
| telecom | `TelecomUserTools` (a real, separate toolkit) | **Yes — 15 WRITE tools** (`set_network_mode_preference`, `toggle_airplane_mode`, `reseat_sim_card`, `toggle_data`, `toggle_roaming`, `toggle_data_saver_mode`, `set_apn_settings`, `reset_apn_settings`, `toggle_wifi`, `toggle_wifi_calling`, `connect_vpn`, `disconnect_vpn`, `grant_app_permission`, `reboot_device`, `make_payment` — enumerated via `env.user_tools.tools` filtered on `__mutates_state__`, mirroring `adapters/_tau2_worker.py`'s `_cmd_list_tools`) | **Yes, and it is more consequential than "yes."** See below. |

Grep confirming no `mutates_state=` override anywhere in these three domains (so every
WRITE-tagged tool above really does default to `mutates_state=True`, and nothing hides a
mutation behind a non-WRITE tag either):

```
$ grep -rn "mutates_state=" repos/tau2/src/tau2/domains/{airline,retail,telecom}
(no output)
```

## The telecom answer is not a simple "yes" — there are two separate databases, bridged

telecom is the one domain with a real user-facing toolkit, and it is built on a **second,
separately-mutable database**: `TelecomUserTools.db` is a `TelecomUserDB`
(`domains/telecom/user_data_model.py`), not the `TelecomDB` the agent's tools operate on
(`domains/telecom/data_model.py`). A user-side WRITE tool call, by itself, only ever mutates
`TelecomUserDB` — none of the 15 tools listed above touch `self.db` on the agent-facing
`TelecomTools` instance directly.

But `TelecomEnvironment` overrides `sync_tools()` (`domains/telecom/environment.py:44-93`), and
`Environment.get_response()` — the single call site the orchestrator uses to execute ANY tool
call, agent's or user's (`orchestrator/orchestrator.py:312-327`, `_execute_tool_calls`, generic
over both requestors) — calls `self.sync_tools()` unconditionally after every call
(`environment/environment.py`, `get_response`). `TelecomEnvironment.sync_tools()` reads several
fields off `user_tools.db.surroundings` and, when a payment has been marked paid on the *user*
side, calls `self.tools._set_bill_to_paid(...)` — a write to the **agent-facing** `TelecomDB`:

```python
# domains/telecom/environment.py, inside TelecomEnvironment.sync_tools()
current_payment_request = self.user_tools.db.surroundings.payment_request
if current_payment_request is not None:
    if current_payment_request.paid:
        self.tools._set_bill_to_paid(current_payment_request.bill_id)
        self.user_tools.db.surroundings.payment_request = None
```

`make_payment` (`domains/telecom/user_tools.py:1072-1090`, a user-side WRITE tool) is what sets
`payment_request.paid = True`. So the actual causal chain for one concrete finding is:

1. User simulator calls `make_payment()` — mutates `TelecomUserDB.surroundings.payment_request.paid` only. `TelecomDB` (agent-facing) is untouched at this point.
2. The orchestrator's post-call `sync_tools()` runs (it runs after literally every tool call, by either party).
3. `sync_tools()` sees `payment_request.paid == True` and calls `self.tools._set_bill_to_paid(bill_id)`, which sets `Bill.status = BillStatus.PAID` on the **agent-facing** `TelecomDB` — a database the user-side tool never referenced.

### Empirically verified

```
$ PYTHONUTF8=1 .venv-tau2/Scripts/python.exe -c "..."   # full script below
before: bill B1001 status Awaiting Payment
make_payment -> Payment of 160.5 USD has been made for bill B1001.
main db bill status BEFORE sync_tools(): Awaiting Payment
main db bill status AFTER  sync_tools(): Paid
payment_request cleared: None
```

Reproduction script (run against `.tau2-src-c3398666/`, the durable extracted copy of commit
`c3398666` this adapter is installed from -- see the project's final report for how it was
produced and why an editable install needs a durable, non-ephemeral source directory):

```python
from tau2.domains.telecom.environment import get_environment_manual_policy as ge
from tau2.domains.telecom.user_data_model import PaymentRequest
from tau2.domains.telecom.data_model import BillStatus

env = ge()
db, udb = env.tools.db, env.user_tools.db
cust = db.customers[0]
line = next(l for l in db.lines if l.line_id in cust.line_ids)
bill_id = cust.bill_ids[0]
bill = env.tools._get_bill_by_id(bill_id)
bill.status = BillStatus.AWAITING_PAYMENT  # force a non-terminal status for the demo
print("before:", bill.status.value)

udb.surroundings.phone_number = line.phone_number       # sync_tools() no-ops without this
udb.surroundings.payment_request = PaymentRequest(bill_id=bill_id, amount_due=bill.total_due)

env.use_user_tool("make_payment")                        # USER-side WRITE tool call
print("BEFORE sync_tools():", env.tools._get_bill_by_id(bill_id).status.value)  # still Awaiting Payment
env.sync_tools()                                          # what the orchestrator calls after EVERY tool call
print("AFTER  sync_tools():", env.tools._get_bill_by_id(bill_id).status.value)  # now Paid
```

The first version of this check (setting `payment_request` without also setting
`surroundings.phone_number`) showed no effect — worth recording because it is a real trap:
`sync_tools()`'s very first line is `if self.user_tools.db.surroundings.phone_number is None:
return`, so the bridge is silently inert until the user's phone number has been established in
the conversation. A replay harness that does not also replay whatever established
`surroundings.phone_number` would reproduce the "no effect" case even when the live run had one.

## Consequence for the project

1. **Trajectory replay (ARCHITECTURE-FINAL.md sec 6, Tier 1) must record and replay user-side
   tool calls for telecom**, not only the agent's action sequence. `make_payment` is a confirmed,
   field-observed case where omitting the user's calls would make replay diverge from the live
   run's final `TelecomDB` state — exactly the failure mode the open question was worried about.
   airline and retail need no such handling: their user simulators cannot call anything with a
   DB effect, so replaying only the agent's tool calls is already complete for those two domains.

2. **`adapters/tau2.py`'s `snapshot()` captures `TelecomUserDB` state alongside the agent-facing
   `TelecomDB`** (as a `user_db` key) specifically because of this finding — see
   `adapters/_tau2_worker.py`'s `_cmd_snapshot` docstring. `invoke()` does not yet expose calling
   a user-side tool (Gate 1a/1b only needed agent-facing tools: `cancel_reservation`,
   `refuel_data`); extending it to accept a `requestor` is the natural next step and should
   happen before any telecom trajectory-replay work starts, given #1.

3. **Contract authoring for telecom tools should be aware that `sync_tools()` is a THIRD source
   of writes to `TelecomDB`**, distinct from both "this tool's own body" and "an unrelated
   concurrent call" — a frame clause asserting some region of `TelecomDB` is unchanged by an
   agent-facing WRITE tool could be violated by a user-side action that happened earlier in the
   same turn and only landed via `sync_tools()`, not by the tool under test at all. None of the
   two Gate 1b contracts (`cancel_reservation`, `refuel_data`) are affected — `cancel_reservation`
   is airline (no bridge exists), and `refuel_data`'s effects (`data_refueling_gb`, bill
   `total_due`) are not among the fields `sync_tools()` writes — but a future telecom contract
   whose frame clauses cover `bills.*.status` or `lines.*.status` should account for this path
   explicitly rather than treat every observed change as attributable to the tool being tested.

4. **Only `make_payment` was traced end-to-end here.** The other 14 user-side WRITE tools listed
   above mutate only `TelecomUserDB` fields that `TelecomEnvironment.sync_tools()` does not read
   back into `TelecomDB` (device/network/SIM/APN/VPN/app-permission state) — confirmed by reading
   `sync_tools()`'s full body (`domains/telecom/environment.py:44-93`), which touches exactly
   four `TelecomUserDB.surroundings` fields (`line_active`, `roaming_allowed`,
   `mobile_data_usage_exceeded`, `payment_request`) and writes to `TelecomDB` only via the
   `payment_request` branch. So `make_payment` is not one example among many — as of c3398666, it
   is the *only* user-side tool with any agent-facing-DB consequence at all. That is a claim about
   this one pinned commit, not a structural guarantee; re-check `sync_tools()`'s body if the
   commit pin ever moves.
