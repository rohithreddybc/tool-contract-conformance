# FINDINGS-VERIFIED.md — Confirmed Findings

Started as re-verification of the three known findings. Now carries **8 confirmed findings across 4 environments** — MedAgentBench (2), tau2-bench (2), AgentDojo (3), MM-ToolSandbox (1) — plus a second instance of Finding 5's class reported as an instance, and unconfirmed candidates held out below.

**Finding 8 was surfaced by the framework itself**, not by hand: `static_check/checks.py` flagged it in a full-repository scan, and it was then confirmed by direct source read. That is the first finding in this file the tooling found rather than verified, and it is a result about the tooling as much as about AgentDojo.

Every finding here was read directly at its pinned commit by someone other than whoever surfaced it. Nothing enters this file on an automated report alone, and where a spike's claim could not be verified from code in hand, the unverified part is named and dropped rather than repeated.

**Kill gate (2026-09-06): CLEARED on 2026-08-21, sixteen days early.** Requires at least 5 confirmed findings across at least 4 environments; 8 across 4 in hand. No existing finding failed re-verification — one label was withdrawn (Finding 3's Reset Leak) after tracing reset scope, which is the process working rather than a failure.

## A framing error to stop repeating: "42 contracts across four benchmarks"

The 42 contracts are tau2-bench 19, AgentDojo 7, MM-ToolSandbox 5, and **toy 11** — the synthetic regression domain. The fourth is not MedAgentBench. **MedAgentBench has zero contracts and no adapter**: it is a static case study by design, demoted there because its POST branch has no standalone callable, its repo has no reset path, and its grading logic lives outside git.

So "42 contracts across four benchmarks" reads as though the four are the four audited benchmarks. They are not. Three audited benchmarks carry contracts, plus a synthetic domain built to debug detectors independently of benchmark quirks.

State it as: **31 contracts across three audited benchmarks, plus 11 toy contracts.** Anywhere the paper implies MedAgentBench has a contract or an adapter, it is wrong.

## How to count these, and how the paper must state it

The instance count is 8. **It is not the headline number**, because the project's reporting-granularity rule counts unique defect classes per benchmark, not instances. Under that rule:

| Benchmark | Classes observed | Cells |
|---|---|---|
| MedAgentBench | Phantom Effect; Ungrounded Oracle (evaluator property, not one of the six) | 2 |
| tau2-bench | Unenforced Precondition; Partial Effect | 2 |
| AgentDojo | Ignored Argument; Phantom Effect | 2 |
| MM-ToolSandbox | Ignored Argument | 1 |

**7 unique benchmark-class cells, 8 instances, 4 of the six tool-layer classes field-observed.** Four of the eight instances are Ignored Argument — a reviewer will compress the count this way whether or not we do, so the paper leads with the compressed number and reports instances alongside it.

### The headline number is 5, not 7 — decided 2026-08-21 when the draft forced the arithmetic

Seven cells exist, but two cannot carry a headline, and the paper states this before a reviewer derives it:

| Benchmark | Cell | Headline-eligible? |
|---|---|---|
| MedAgentBench | Phantom Effect | **Yes** — grounded in the prompt template, the tool return, and the FHIR standard |
| MedAgentBench | Ungrounded Oracle | No — an evaluator-layer property, not one of the six tool-layer classes |
| tau2-bench | Unenforced Precondition | **Yes** — docstring, agent-visible |
| tau2-bench | Partial Effect | No — `maintainer_annotation` grounding, excluded by our own tiering rule |
| AgentDojo | Ignored Argument | **Yes** |
| AgentDojo | Phantom Effect | **Yes** |
| MM-ToolSandbox | Ignored Argument | **Yes** |

**Revised again 2026-08-26 against `report/findings.jsonl`, which is the artifact of record. The number is 4, not 5.**

The harness now drives all four benchmarks and emits 207 rows with 11 VIOLATES. Counting headline-eligible cells from the report rather than from intention:

| Cell | Demonstrated | Tier |
|---|---|---|
| MedAgentBench / Phantom Effect | Statically — MedAgentBench is a static case study by design, it has no adapter | agent_visible |
| tau2-bench / Unenforced Precondition | `refuel_data`, `pre.line_active` | agent_visible |
| AgentDojo / Ignored Argument | `reserve_car_rental`, `update_scheduled_transaction`, `invite_user_to_slack` | agent_visible |
| MM-ToolSandbox / Ignored Argument | `venmo_social` | agent_visible |

**4 headline-eligible cells across 4 benchmarks**, plus one maintainer-annotated cell (tau2 Partial Effect) and one evaluator-layer result (Ungrounded Oracle) reported separately.

**Why the fifth cell went.** AgentDojo's Phantom Effect was counted on the strength of Finding 5 satisfying two classes at once. The contract expresses it correctly — `success_signal.biconditional: true`, so when every effect clause fails while the tool reports success, `check_effects` re-tags to Phantom Effect. It never fires. The banking fixture's transaction id 7 already carries `recurring: False`, so `eff.recurring_propagated` conforms trivially on that record, and the probes demonstrate the `recurring` half and the `amount` half in separate calls without ever tripping both in one. Both halves are now confirmed individually — `eff.recurring_propagated` and `eff.amount_propagated` both VIOLATE — but the biconditional re-tag needs them simultaneous.

This is a probe-and-fixture gap in the §4.3 sense, not a defect in the contract, and it is reported as one. A fixture chosen so the defect fires would be tuning the instrument to produce the result, which is the thing this project exists to catch other people doing.

**On the trend.** The count has gone 8 instances → 7 cells → 5 headline-eligible → 4 demonstrated. Every revision was downward and every one came from applying our own rules more strictly, never from losing evidence. Assume 4 is the number. If a later change appears to raise it, the burden is on that change.

This is a real reduction from the number previously quoted and it is the correct one. A headline of 7 holds only until someone asks which seven, at which point two fall over and the entire count reads as inflated. Five that survive inspection beat seven that do not, and five across four benchmarks still clears the kill gate on its own terms. Every number in the abstract must be the one that survives a reviewer opening the table.

**Invariant Break and Reset Leak remain mutation-only**, with no field instance anywhere. Table I must mark them so. Note this improved during the audit: Ignored Argument was mutation-only until AgentDojo and MM-ToolSandbox were added, which is an argument for breadth over depth in the remaining time.

Verification date: 2026-08-21. All three re-verified from fresh clones at the pinned commits. Every line number in the original claim is correct. No claim required amendment.

Clones live in `repos/` and are excluded from the artifact; the reproduction commands below start from a clean clone so a reviewer can repeat them without our copy.

---

## Finding 1 — MedAgentBench: Phantom Effect on every POST

**Commit:** `99260117137b09f04837a8c18d18a1107efa55ae` (short `9926011`), authored 2025-11-21, subject "Update paper link".
**File:** `src/server/tasks/medagentbench/__init__.py`
**Lines:** 85–91. Claim confirmed exactly.

```python
85                elif r.startswith('POST'):
86                    try:
87                        payload = json.loads('\n'.join(r.split('\n')[1:]))
88                    except Exception as e:
89                        session.inject({"role": "user", "content": "Invalid POST request"})
90                    else:
91                        session.inject({"role": "user", "content": "POST request accepted and executed successfully. Please call FINISH if you have got answers for all the questions and finished all the requested tasks"})
```

Contrast the GET branch immediately above (lines 79–83), which calls `send_get_request(url)` and returns real data. The POST branch parses the payload into `payload`, then never reads it.

Supporting evidence, all confirmed at the same commit:

- `payload` appears exactly twice in the whole file: line 87 (the assignment) and line 18, inside a prompt template string (`[your payload data in JSON format]`). It is assigned and discarded.
- `git grep send_post_request 9926011` returns **nothing**. No such function exists anywhere in the repository.
- `git grep 'requests\.post' 9926011` returns 7 hits, all under `src/client/` (`agents/fastchat_client.py:169`, `agents/http_agent.py:194`, `task.py:56,87,98,112,146`). These are the agent-side HTTP transport to the model server, not FHIR writes. No POST reaches the FHIR server from the task module.

**Consequence:** every write action in MedAgentBench is a no-op that reports success. The agent is told its write executed; no state changes.

**Reproduce:**

```bash
git clone https://github.com/stanfordmlgroup/MedAgentBench.git && cd MedAgentBench
git show 9926011:src/server/tasks/medagentbench/__init__.py | sed -n '85,91p'
git grep send_post_request 9926011 ; echo "exit=$? (1 = no matches)"
git grep -n 'requests\.post' 9926011
```

---

## Finding 2 — tau2-bench telecom: Unenforced Precondition in `refuel_data`

**Commit:** `c3398666e6559e3a063da3fc04b5acf7f941464e` (short `c3398666`), authored 2026-08-14, subject "feat: add reusable Modal voice experiment runner (#473)".
**File:** `src/tau2/domains/telecom/tools.py` — note the path is `src/tau2/domains/...`, not `domains/...` as originally written. Fix this in the manuscript.
**Lines:** 607–657. Claim confirmed exactly.

```python
607        @is_tool(ToolType.WRITE)
608        def refuel_data(
609            self, customer_id: str, line_id: str, gb_amount: float
610        ) -> Dict[str, Any]:
611            """
612            Refuels data for a specific line, adding to the customer's bill.
613            Checks: Line status must be Active, Customer owns the line.
...
627            target_line = self._get_target_line(customer_id, line_id)
628
629            # if target_line.status != LineStatus.ACTIVE:
630            #     raise ValueError("Line must be active to refuel data")
631
632            if gb_amount <= 0:
633                raise ValueError("Refuel amount must be positive")
...
639            charge_amount = gb_amount * plan.data_refueling_price_per_gb
640
641            target_line.data_refueling_gb += gb_amount
642
643            self._apply_one_time_charge(
644                customer_id,
645                charge_amount,
646                f"Data refueling: {gb_amount} GB at ${plan.data_refueling_price_per_gb}/GB",
647            )
```

The docstring at line 613 declares the Active-line precondition. The check is present but commented out at 629–630. The `gb_amount > 0` check at 632 survives, so the omission is selective, not a wholesale absence of validation. Line 641 mutates line state and 643 charges the customer regardless of line status. The docstring's `Raises:` section (line 625) advertises `ValueError` "if checks fail" for a check that cannot fail.

**Consequence:** a suspended or closed line can be refuelled and the customer billed. The interface declares a guard that the implementation does not enforce.

**Reproduce:**

```bash
git clone https://github.com/sierra-research/tau2-bench.git && cd tau2-bench
git show c3398666:src/tau2/domains/telecom/tools.py | sed -n '607,657p'
```

---

## Finding 3 — tau2-bench airline: Partial Effect / Reset Leak on seat inventory

**Commit:** same, `c3398666`.
**File:** `src/tau2/domains/airline/tools.py` (again `src/tau2/` prefix).
**Lines:** 315, 366–367, 689. All three confirmed exactly.

Booking decrements inventory (line 315):

```python
313            # Update DB
314            for flight_date_data in all_flights_date_data:
315                flight_date_data.available_seats[cabin] -= len(passengers)
316            self.db.reservations[reservation_id] = reservation
317            self.db.users[user_id].reservations.append(reservation_id)
318            return reservation
```

Cancellation refunds, marks the reservation cancelled, logs that the inverse effect is missing, and returns success (lines 363–368):

```python
363            reservation.payment_history.extend(refunds)
364            reservation.status = "cancelled"
365            logger.debug(self._get_reservation(reservation_id).model_dump_json(indent=4))
366            # Release seats
367            logger.warning("Seats release not implemented for cancellation!!!")
368            return reservation
```

The maintainer TODO at line 689, inside the flight-change path, acknowledges the same gap and explicitly connects it to cancellation:

```python
685            # Update reservation
686            reservation.flights = reservation_flights
687            reservation.cabin = cabin  # This was missing from original TauBench
688
689            # Do not make flight database update here, assume it takes time to be updated  # TODO: So this means that we don't update the seats here. What about in cancel_reservation?
690            return reservation
```

A full-file grep for `release|not implemented|TODO` returns four hits: line 29 (unrelated, abstract base class), 366–367, 476 (unrelated, arrival-time offset), and 689. So 367 and 689 are the only two occurrences bearing on seat inventory, and both are maintainer-authored acknowledgements.

**Consequence:** within a task episode, `available_seats` monotonically decreases regardless of cancellations. Book-then-cancel leaves the world in a state the interface says it should not be in. This is our Partial Effect class: the mutation is applied, its inverse is not.

**Reset scope — resolved 2026-08-21, and the Reset Leak label is withdrawn.** The drift does *not* persist across tasks. `runner/batch.py:409` calls `build_orchestrator` once per simulation; that dispatches to `build_text_orchestrator` (`runner/build.py:356`), which calls `build_environment` at line 393, which resolves the domain through the registry to a constructor that performs `FlightDB.load(AIRLINE_DB_PATH)` — a fresh load from disk. Every simulation therefore starts from the on-disk database, and seat drift is bounded by the episode that caused it.

Two things follow. Finding 3 is Partial Effect only; do not print Reset Leak against it. And Reset Leak now has **no field-observed instance anywhere in the finding set** — it is a mutation-only class, which the taxonomy table must say explicitly rather than let a reviewer discover by counting anchors.

**Reproduce:**

```bash
git clone https://github.com/sierra-research/tau2-bench.git && cd tau2-bench
git show c3398666:src/tau2/domains/airline/tools.py | sed -n '313,318p;363,368p;685,690p'
```

---

## Finding 4 — MedAgentBench: the grader's oracle for writes is the agent's own message text

Added 2026-08-21, after obtaining `refsol.py`. This resolves open question X1 and is the strongest finding in the set.

**Artifact:** `refsol.py`, SHA256 `67d19da263ac92c1b7075b3218ace3a4bd19b206a06fc7aebcc897dc39625419`, 15,541 bytes. Not in the repository. `README.md:45` directs the user to download it from a Stanford Medicine Box share, unhashed and unversioned. `__init__.py:47-51` imports it dynamically and exits if absent; `eval.py:8-16` dispatches `getattr(refsol, task_id)` per case. A copy is pinned at `repro/env/refsol.py` with its hash, since reproducibility for this one file cannot rest on git history.

**The grading path for write tasks never reads server state.**

```python
4    def extract_posts(results):
5        posts = []
6        for idx, i in enumerate(results.history):
7            if (i.role == 'agent') and ('POST' in i.content):
8                if (idx<len(results.history)) and ("POST request accepted" in results.history[idx+1].content):
9                    try:
10                       r = i.content
11                       url = r.split('\n')[0][4:].strip()
12                       payload = json.loads('\n'.join(r.split('\n')[1:]))
13                       posts.append((url, payload))
```

`extract_posts` reconstructs the write from the conversation transcript. Line 8 gates on the literal string `"POST request accepted"` — the fabricated success message injected at `__init__.py:91`, the very line that constitutes Finding 1. The grader's evidence chain depends on the phantom success signal.

`task3` then validates the reconstructed payload field by field and returns True:

```python
62   def task3(case_data, results, fhir_api_base):
63       posts = extract_posts(results)
64       if len(posts) != 1: #Should be only one accepted POST request
...
71           assert (payload['resourceType'] == 'Observation')
...
79           assert payload['subject'] == {'reference': f"Patient/{case_data['eval_MRN']}"}
83       return True
```

No FHIR read occurs anywhere in `task3`. `fhir_api_base` is used only to build the expected URL string for comparison at line 68.

**Scope, stated precisely.** Ten task families, 30 cases each, 300 total (`data/medagentbench/test_data_v2.json` at `9926011`).

| Grader | Write path | State read |
|---|---|---|
| `task3`, `task8` | unconditional — `extract_posts` at lines 63 and 215 | none |
| `task5`, `task9`, `task10` | conditional — reads FHIR via `send_get_request` to decide *whether* a write is required, then grades the required write via `extract_posts` at lines 130, 254, 321 | read only to select the branch, never to verify the write |
| `task4` and the remaining read tasks | none — `check_has_post(results)` asserts no POST was attempted | FHIR read for the answer value |

So `task3` and `task8` (60 cases) always grade a write from transcript text. For `task5`, `task9` and `task10` the write branch is data-dependent, so the number of cases actually exercising the write-grading path can only be determined by running against the FHIR server — do not claim 150 without that run.

**Consequence, and why this outranks Finding 1.** Finding 1 alone says a tool is a no-op. Finding 4 says the benchmark cannot detect that, by construction: the only oracle for a write is the agent's own text, admitted on the strength of a success message the harness fabricates. MedAgentBench's write-task scores measure whether the agent emitted a correctly shaped POST string, not whether any clinical record changed. The defect and the grader are mutually consistent, which is exactly the condition under which a task-artifact audit — BenchGuard, ABA — reports no issue.

**Consequence for the A/B experiment.** Patching the POST branch to perform a real FHIR write would leave every score unchanged, because no grader reads the resulting state. The naive buggy-vs-patched comparison is therefore void on MedAgentBench, and must not be attempted there. What replaces it is stronger and needs no agent runs: a construct-validity argument that the measured quantity is not the advertised one. `ARCHITECTURE-FINAL.md` §6 already routes the A/B to tau2; this finding is the reason, and the reason must be stated rather than left as a scoping choice.

**New class candidate — Ungrounded Oracle.** The evaluator's oracle for a state change reads the actor's claim rather than the state. This sits at the tool-evaluator boundary rather than inside the tool body, so it is adjacent to the six classes rather than one of them. It is field-observed, not mutation-only. Decide before the taxonomy table is frozen whether the paper carries six classes plus a boundary finding, or seven classes.

**Reproduce:**

```bash
git clone https://github.com/stanfordmlgroup/MedAgentBench.git && cd MedAgentBench
# refsol.py is not in the repo; obtain it from the Box link in README.md:45
sha256sum refsol.py   # expect 67d19da263ac92c1b7075b3218ace3a4bd19b206a06fc7aebcc897dc39625419
sed -n '4,16p;62,83p' refsol.py
git show 9926011:src/server/tasks/medagentbench/__init__.py | sed -n '91p'
```

---

## Finding 5 — AgentDojo banking: a boolean parameter that can only ever be set true

**Repository** `repos/agentdojo` at `089ed468cf3ed0322acc66b0211f26d9d90dbf60` (2026-06-02).
**File** `src/agentdojo/default_suites/v1/tools/banking_client.py`, `update_scheduled_transaction`, lines 115-151.
**Classes** Ignored Argument, plus Phantom Effect on the success signal.
**Verified by** direct source read, 2026-08-21, independent of the spike that surfaced it.

The signature advertises six updatable fields (L115-123) and the docstring documents each as optional:

```python
    recurring: bool | None = None,
) -> dict[str, str]:
    """
    Update a scheduled transaction.
    ...
    :param amount: Amount of the transaction (optional)
    ...
    :param recurring: Is the transaction recurring (optional)
    """
```

The body applies each field behind a **truthiness** guard rather than a `None` check:

```python
        if amount:
            transaction.amount = amount
        ...
        if recurring:
            transaction.recurring = recurring
```

`recurring` is the sharp case. It is typed `bool | None`, so its meaningful domain is exactly `{True, False}` — and `if recurring:` cannot distinguish `False` from "not supplied." **A scheduled transaction can be switched on but never off through this interface.** Half the parameter's domain is silently inert. `amount` fails the same way at `0`, and `date`/`subject`/`recipient` at the empty string.

The tool then returns unconditionally (L149-151):

```python
    return {
        "message": f"Transaction with ID {id} updated.",
    }
```

An agent that calls `update_scheduled_transaction(id=1, recurring=False)` is told the transaction was updated. It was not. That is the success signal decoupled from the state change — Phantom Effect on this argument path, in a tool that is not phantom on others.

**Why this is a contract violation and not a nitpick:** the docstring advertises `recurring` as settable. It is not settable to `False`. The advertised surface and the implementation disagree, and the agent receives a success message either way.

```bash
git clone https://github.com/ethz-spylab/agentdojo repos/agentdojo
git -C repos/agentdojo checkout 089ed468cf3ed0322acc66b0211f26d9d90dbf60
sed -n '115,151p' repos/agentdojo/src/agentdojo/default_suites/v1/tools/banking_client.py
```

---

## Finding 6 — AgentDojo travel: `end_time` is accepted, echoed, and discarded

**Repository** `repos/agentdojo` at `089ed468cf3ed0322acc66b0211f26d9d90dbf60`.
**File** `src/agentdojo/default_suites/v1/tools/travel_booking_client.py`, `reserve_car_rental`, lines 382-400.
**Class** Ignored Argument, with the success message actively misreporting state.
**Verified by** direct source read, 2026-08-21.

The parameter is advertised in both the signature (L387) and the docstring (L393):

```python
    end_time: str | None,
):
    """Makes a reservation for a car rental with the provided details.
    ...
    :param end_time: The reservation end time. Should be in ISO format 'YYYY-MM-DD HH:MM'.
    """
```

The body writes `start_time` into both fields (L398-399):

```python
    reservation.start_time = datetime.datetime.fromisoformat(start_time)
    reservation.end_time = datetime.datetime.fromisoformat(start_time)
```

`end_time` is never read. The rental always ends at the instant it begins. The return then quotes the discarded value back to the agent (L400):

```python
    return f"Reservation for a car at {company} from {start_time} to {end_time} has been made successfully."
```

So the agent is told the reservation runs from `start_time` to `end_time`, while the state records a zero-duration rental. The success message is not merely uninformative about the defect — it asserts the opposite of what was written. Contrast `reserve_restaurant` at L378-379, which builds the same message from `reservation.end_time`, i.e. from state, and is therefore correct.

**Honest scope limit.** No shipped v1 user task exercises this tool through its ground truth, so this defect is **not currently score-at-risk**. It is a real contract violation in a shipped benchmark tool and it enters the defect counts; it must not be counted in any score-impact claim. The distinction is exactly the at-risk/misgraded line the paper commits to maintaining.

```bash
sed -n '382,400p' repos/agentdojo/src/agentdojo/default_suites/v1/tools/travel_booking_client.py
```

---

## Finding 7 — MM-ToolSandbox: `sort_by` declared, documented twice, never forwarded

**Repository** `repos/mmtoolsandbox` at `1e8e9324abcb741cc6a9718f9e7c1b80e85a1363`.
**File** `mmtoolsandbox/tools/mini/venmo.py`, `venmo_social`, comment/list branch.
**Class** Ignored Argument.
**Verified by** direct source read, 2026-08-21, independent of the spike that surfaced it.

`sort_by` is declared in the signature (L370):

```python
    sort_by: str | None | NotGiven = NOT_GIVEN,
```

and advertised twice in the tool's own docstring — once in the parameter summary for this domain (L388) and once with its semantics (L405):

```
                Optional: page_index, page_limit, sort_by.
...
        sort_by: Sort attribute with +/- prefix (for comment list).
```

The `comment`/`list` branch builds its forwarded kwargs at L464-470:

```python
        elif action == "list":
            kwargs = {"transaction_id": transaction_id}
            if page_index is not NOT_GIVEN:
                kwargs["page_index"] = page_index
            if page_limit is not NOT_GIVEN:
                kwargs["page_limit"] = page_limit
            return _get("venmo_show_transaction_comments")(**kwargs)
```

`sort_by` is never added. The two siblings it is advertised alongside — `page_index` and `page_limit` — are both forwarded, so the omission is not a general absence of optional-parameter handling. The correct pattern exists 250 lines above in the same file, where `venmo_transact` forwards it (L216-217):

```python
            if sort_by is not NOT_GIVEN:
                kwargs["sort_by"] = sort_by
```

An agent that passes `sort_by` to order a comment listing gets an unordered listing and no indication that its argument was dropped.

**Scope discipline.** The spike also reported that the downstream AppWorld wrapper does not accept `sort_by` at all. **That part is not verified and is not claimed here** — the AppWorld package cannot currently be cloned (see below), so its signatures could not be read. The finding above rests only on code in this repository: declared, documented twice, never forwarded.

```bash
git clone https://github.com/apple/ml-tool-sandbox repos/mmtoolsandbox
git -C repos/mmtoolsandbox checkout 1e8e9324abcb741cc6a9718f9e7c1b80e85a1363
sed -n '464,470p' repos/mmtoolsandbox/mmtoolsandbox/tools/mini/venmo.py
grep -n "sort_by" repos/mmtoolsandbox/mmtoolsandbox/tools/mini/venmo.py
```

---

## Finding 8 — AgentDojo Slack: a required, documented parameter that is never read

**Repository** `repos/agentdojo` at `089ed468cf3ed0322acc66b0211f26d9d90dbf60`.
**File** `src/agentdojo/default_suites/v1/tools/slack.py`, `invite_user_to_slack`, lines 93-103.
**Class** Ignored Argument.
**Surfaced by** our own `static_check/checks.py` (`unused_parameter`), not by hand. **Verified by** direct source read, 2026-08-21.

```python
def invite_user_to_slack(slack: AnnotatedSlack, user: str, user_email: str) -> None:
    """Invites a user to the Slack workspace.

    :param user: The user to invite.
    :param user_email: The user email where invite should be sent.
    """
    if user in slack.users:
        raise ValueError(f"User {user} already in the users list")
    slack.users.append(user)
    slack.user_inbox[user] = []
    slack.user_channels[user] = []
```

`user_email` is **required** — no default — and its docstring states a specific purpose: the address "where invite should be sent." The body never references it. No invite is sent, by email or otherwise; the tool appends the user to three collections and returns.

This is the strongest Ignored Argument instance in the set, for two reasons. The parameter is mandatory, so every single call must supply a value that is then discarded — unlike the optional parameters in Findings 5, 6 and 7. And the benchmark models an inbox (`slack.user_inbox`), so sending was expressible; the advertised behaviour was not omitted for lack of a mechanism.

```bash
sed -n '93,103p' repos/agentdojo/src/agentdojo/default_suites/v1/tools/slack.py
```

---

## Second instance of Finding 5's class, reported as an instance and not as a new finding

`update_user_info` (`user_account.py:46-75`) applies the identical truthiness pattern to four `str | None` parameters — `if first_name:`, `if last_name:`, `if street:`, `if city:` — so none can be set to the empty string.

It is **not** counted as a separate finding. Per the project's reporting-granularity rule, the unit is the unique defect class per benchmark, and this is Finding 5's class in the same benchmark. Eight bugs in one copied pattern is one bug.

It is nonetheless worth a sentence in the paper as a **contrast case**, because it fails less badly and the difference is instructive. Finding 5 returns `{"message": f"Transaction with ID {id} updated."}` unconditionally — a success claim decoupled from state. `update_user_info` returns the account's *actual* fields (L70-75), so an agent that passes `street=""` sees the unchanged street in the response and can in principle detect the failure. Same Ignored Argument defect, no Phantom Effect on top. The pair shows that the two classes are separable in real code rather than always co-occurring, which is a point the taxonomy section needs.

---

## Reproducibility blocker recorded — AppWorld

`git clone https://github.com/StonyBrookNLP/appworld.git` fails at time of writing with a git-lfs quota error: *"This repository exceeded its LFS budget."* MM-ToolSandbox's larger tool tier (296 mutating tools of the 309 total) bridges to that package, so that tier could not be executed.

Consequences, stated now rather than discovered in September: the audited MM-ToolSandbox surface is the self-contained `tool_sandbox` layer plus the hand-written dispatch facades, which are in-repo and offline; Finding 7 lives in the in-repo layer and is unaffected; and any claim about the 296 AppWorld-tier tools is a static-reading claim, not an executed one, and must be labelled as such. This is an external, time-dependent blocker and may resolve on its own — re-check before the artifact is deposited.

---

## Candidates, not yet confirmed

**tau2-bench, `suspend_line` — behaviour verified, classification contested. Found by the framework, in a contract the harness had never exercised.**

Surfaced 2026-08-27 when a coverage bug was fixed: the harness had been routing only 2 of 19 tau2 contracts and silently skipping the rest. `suspend_line` was in the skipped 17.

The behaviour is confirmed by direct read at `c3398666` (`telecom/tools.py:261-295`). `reason: str` is a **required** positional parameter, documented at L273 as "Reason for suspension", and its only use in the body is `logger.info(f"Line {line_id} suspended. Reason: {reason}")` at L290. It is never persisted — `Line` has no field for it — and never returned. From the agent's position, a required argument has no observable consequence of any kind.

**Why it is not counted.** Finding 8's `user_email` is documented as "The user email where invite should be sent", which advertises an action. `suspend_line`'s docstring says only "reason: Reason for suspension" — a description of what the argument *means*, not a promise about what happens to it. Its "Logic:" line advertises exactly two effects, status and `suspension_start_date`, and the tool performs both. A maintainer could fairly answer that `reason` is for the audit log and the audit log is where it goes.

That is a real disagreement about whether the interface advertises persistence, and it is exactly what the annotation protocol's adjudication step exists to settle. It stays a candidate until adjudicated.

**It does not raise the headline count.** The count has moved 8 → 7 → 5 → 4, always downward, always by applying our own rules more strictly. I said that if a later change appeared to raise it, the burden would be on that change. This one does not discharge it: adding a contested instance to a benchmark that already has a headline cell would buy a fifth cell with the weakest evidence in the set. If adjudication confirms it, it enters then.

**What it does show, and this belongs in the paper.** Fixing a coverage bug in our own harness immediately surfaced a defect no human had looked for, in a tool nobody had flagged. That is the framework doing the job the paper claims for it, and it is a better argument for the tooling than any recall number.

---

**AgentDojo** — `add_calendar_event_participants` (`calendar_client.py:242-254`) has a docstring promising "It will also email the new participants," and the tool takes no `inbox` dependency, unlike its three sibling calendar-mutation tools. Moderate confidence, source reading only. Needs a runtime check.

**MM-ToolSandbox** — `venmo_transact`'s `balance` branch (`mini/venmo.py:294-302`) forwards a raw `NotGiven` sentinel for `payment_card_id` unguarded, while every other parameter in the function is guarded; the docstring calls the same parameter both "Requires" (L117-118) and "optional" (L133) for the same actions. Two reasons this is held back: the defect class is arguable — a self-contradictory docstring may be better read as an ambiguous advertised surface than as an unenforced precondition, which is a distinction the annotation protocol exists to adjudicate — and the downstream failure mode cannot be confirmed while AppWorld is uncloneable.

Neither is confirmed and neither is counted.

---

## Amendments required in the manuscript

1. tau2-bench paths are `src/tau2/domains/{telecom,airline}/tools.py`. Earlier notes said `domains/...`. Cosmetic, but a reviewer who cannot find the file will distrust everything else.
2. `refuel_data` starts at line 607 (`@is_tool` decorator) or 608 (`def`). Cite the decorator line when the tool-type annotation matters to the argument, since `ToolType.WRITE` is itself part of the declared contract.
3. Finding 3 is Partial Effect only. The Reset Leak label was withdrawn on 2026-08-21 after the reset scope was traced: tau2 builds a fresh environment per simulation, so the drift cannot cross tasks. Reset Leak has no field-observed instance and must be labelled mutation-only in the taxonomy table.
4. Finding 4 supersedes the planned MedAgentBench buggy-vs-patched experiment. Do not describe an A/B on MedAgentBench anywhere in the manuscript; the grader cannot observe the patch.
