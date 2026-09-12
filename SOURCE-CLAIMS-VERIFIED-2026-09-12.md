# Every claim about another system, re-verified at its pinned commit

Checked on 2026-09-12 by reading the upstream source directly, not by trusting
`FINDINGS-VERIFIED.md` or any earlier pass. One claim failed and was corrected; the rest hold
exactly as the paper states them.

## Failed, and repaired

**`airline/tools.py:689` was described as agent-visible.** The paper said tau2-bench's maintainers
"advertise a deferred flight-database update where the agent can see it, so the checker does not
flag it", contrasted against line 367. At `c3398666`, line 689 is a Python comment:

```python
# Do not make flight database update here, assume it takes time to be updated  # TODO: ...
```

The docstring of `update_reservation_flights` documents parameters, the returned reservation and
five `ValueError` cases, and never mentions the deferral. Line 689 is maintainer-annotated exactly
like line 367, so the contrast did not exist, and a knock-on sentence calling 689 "a true negative
because the agent sees it" inherited the error. `FINDINGS-VERIFIED.md` had it right all along,
calling it "the maintainer TODO at line 689" and using it as evidence for Finding 3. Both
sentences are repaired: the passage now says the grounding tier decides rather than the intent.

## Verified, holding as written

| Claim | Source read | Result |
|---|---|---|
| F1 POST branch discards payload, reports success | `medagentbench @ 9926011`, `__init__.py:85-91` | Holds. Payload parsed into a local, never read again; injects "POST request accepted and executed successfully" |
| F2 Active-line precondition commented out under a docstring that advertises it | `tau2 @ c3398666`, `telecom/tools.py:625-633` | Holds. Docstring at 625 advertises `ValueError` "if checks fail"; check commented at 629-630; `gb_amount` check survives |
| F3 Seats never released on cancellation | `tau2 @ c3398666`, `airline/tools.py:366-367` | Holds. `logger.warning("Seats release not implemented for cancellation!!!")` |
| F5 `recurring` guarded on truthiness | `agentdojo @ 089ed46`, `banking_client.py:115-123, 144` | Holds. Declared optional in the signature; `if recurring:` at 144, so it cannot be set false |
| F6 `end_time` dropped from state, kept in the success string | `agentdojo @ 089ed46`, `travel_booking_client.py:382-400` | Holds, and is sharper than stated: `reservation.end_time = datetime.datetime.fromisoformat(start_time)` assigns from the wrong parameter, while the return string interpolates `{end_time}` |
| F7 `sort_by` declared, documented, never forwarded | `mmtoolsandbox @ 1e8e932`, `mini/venmo.py:464-470` | Holds. The list branch forwards `page_index` and `page_limit` and never `sort_by` |
| F8 `user_email` advertised as an action, never read | `agentdojo @ 089ed46`, `slack.py:93-103` | Holds. Docstring says "The user email where invite should be sent"; body appends the user and initialises inbox and channels without touching it |
| Airline graded by whole-database hash | `tau2 @ c3398666`, `environment/toolkit.py:242-244` | Holds. `get_db_hash` returns `get_dict_hash(self.db.model_dump())` |
| `mutates_state` authoritative over the `ToolType.WRITE` tag | `tau2 @ c3398666`, `environment/toolkit.py:66-88` | Holds. Documented at 72 and 80; line 83 shows the tag is only the fallback default |
| All four findings still live upstream | current default branches, via the GitHub API | Holds. None fixed since the pinned commits |

## Why this pass existed

Earlier passes checked that the paper agreed with `FINDINGS-VERIFIED.md`. That is a different
question from whether both agree with the code. The one claim that failed had been consistent with
our own records for weeks and was wrong about tau2-bench's file the whole time.
