Hi — three separate observations from reading through the `v1` default suites, bundled into one
issue since they're all instances of the same shape: an argument or return value the interface
documents, that the body doesn't fully honor.

1. `update_scheduled_transaction`'s `recurring` (and several siblings) can be set to a truthy
   value but never explicitly to a falsy one.

`src/agentdojo/default_suites/v1/tools/banking_client.py`, lines 115-151 at commit
`089ed468cf3ed0322acc66b0211f26d9d90dbf60`. The docstring documents `recurring: bool | None`
as an optional, settable field. The body guards on truthiness rather than on `is not None`:

    if recurring:
        transaction.recurring = recurring

Since `recurring`'s only meaningful values are `True`/`False`, `if recurring:` can't
distinguish "caller passed False" from "caller passed nothing." A call like
`update_scheduled_transaction(id=1, recurring=False)` silently does nothing to that field.
`amount` has the same issue at `0`, and `date`/`subject`/`recipient` at `""`. The function then
returns unconditionally:

    return {"message": f"Transaction with ID {id} updated."}

so the caller is told the update happened either way. Swapping each `if field:` for
`if field is not None:` (and the string fields for an explicit sentinel-vs-empty-string check,
since `""` is presumably a valid value for some of them) would close all of these at once; we
noticed the identical pattern in `update_user_info` (`user_account.py:46-75`) on four more
fields, so a single shared fix likely covers both call sites.

Reproduce:

    git clone https://github.com/ethz-spylab/agentdojo
    git -C agentdojo checkout 089ed468cf3ed0322acc66b0211f26d9d90dbf60
    sed -n '115,151p' agentdojo/src/agentdojo/default_suites/v1/tools/banking_client.py

2. `reserve_car_rental`'s `end_time` argument is accepted, echoed back, and then not the value
   actually stored.

`src/agentdojo/default_suites/v1/tools/travel_booking_client.py`, lines 382-400. `end_time` is
in both the signature and the docstring, but the body writes `start_time` into both fields:

    reservation.start_time = datetime.datetime.fromisoformat(start_time)
    reservation.end_time = datetime.datetime.fromisoformat(start_time)

and then quotes the (unused) `end_time` argument back in the success message:

    return f"Reservation for a car at {company} from {start_time} to {end_time} has been made
        successfully."

so the message a caller sees actually asserts a duration that was never stored — the rental is
recorded as zero-length regardless of what `end_time` was. `reserve_restaurant` a few lines
above (L378-379) builds the same kind of message from `reservation.end_time` (i.e., from the
stored state), so the fix pattern already exists in the same file — this looks like a copy/paste
slip in `reserve_car_rental` rather than a design choice. We checked the shipped v1 task set and
didn't find one that exercises this tool's `end_time` through its ground truth, so as far as we
can tell this isn't currently affecting any published task score — we're only flagging the
interface/implementation gap itself.

Reproduce:

    sed -n '382,400p' agentdojo/src/agentdojo/default_suites/v1/tools/travel_booking_client.py

3. `invite_user_to_slack`'s required `user_email` argument is never used.

`src/agentdojo/default_suites/v1/tools/slack.py`, lines 93-103:

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

`user_email` has no default, so every caller must supply one, and the docstring states a
specific purpose ("where invite should be sent"), but the body never reads it — no message goes
to `slack.user_inbox` or anywhere else. Since the simulated environment already models an inbox
(`slack.user_inbox`), sending something there when a user is invited looks mechanically easy to
add if that was the intent; alternatively, if `user_email` was meant only for a hypothetical
real-Slack integration and isn't meant to do anything in this simulated environment, saying so
in the docstring (or dropping the parameter) would resolve it just as completely as adding the
send.

Reproduce:

    sed -n '93,103p' agentdojo/src/agentdojo/default_suites/v1/tools/slack.py

We're preparing a paper describing this kind of interface/implementation gap across several
agent benchmarks, targeting submission around 2026-09-27. Anything you send back before then, we
report with its substance; silence gets recorded neutrally, no inference drawn; anything you
think we've gotten wrong, tell us and we'll mark it contested with your reasoning rather than
ours.

Thanks for AgentDojo — it's a large, actively used suite, and all three of the above turned up
just from reading the tool bodies against their own docstrings, nothing more elaborate.
