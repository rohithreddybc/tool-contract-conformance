# Grammar gaps found while authoring spec/contracts/tau2/cancel_reservation.yaml

Do not fix these by reshaping spec/schema.json or spec/PREDICATE-GRAMMAR.md (per CLAUDE.md /
the build instructions). Recorded here instead.

## Frame-path grammar has no key-exclusion, so "no OTHER X" is inexpressible

PREDICATE-GRAMMAR.md sec 5's worked example carried:

```yaml
frame:
  - id: frame.other_reservations
    path: state.reservations.*
    mode: unchanged
    text: "no other reservation is modified"
```

`state.reservations.*` matches every key under `reservations`, including
`args.reservation_id` itself -- the one reservation `cancel_reservation` is *advertised* to
change (`eff.status_cancelled` asserts `post.reservations[args.reservation_id].status ==
'cancelled'`). A frame clause with `mode: unchanged` over that path would therefore fail on
every conforming call, because the tool's own advertised effect collides with the frame
assertion on the same matched subtree.

The frame-path grammar (sec 3) has four segment kinds -- identifier, `*`, `[]`, `**` -- and
none of them can be parameterized by `args` to exclude one key from a wildcard match. There is
no "all keys except this one" segment, and no way to reference `args.reservation_id` from
inside a `frame` clause's `path` string at all (frame paths are pure literal-plus-wildcard
strings, unlike predicates, which do see `args`).

Two ways to state the intent, both currently unavailable:
- `state.reservations.* except args.reservation_id` (an exclusion segment), or
- letting frame `path` interpolate `args.<name>` the way predicates reference bindings.

Neither exists today. Consequence: any tool whose only wildcard-shaped invariant is "every
sibling of the one record I legitimately touch is untouched" cannot get that specific clause
checked by the frame mechanism. The workaround used in `cancel_reservation.yaml` is
`frame.users_unchanged` (`state.users`, `mode: unchanged`) -- true, inferred, and fully
expressible, but it is a weaker claim than "no other reservation is modified": it says nothing
about whether cancelling reservation A silently perturbs reservation B's payment history or
flight list, which is exactly the kind of unadvertised side effect the frame mechanism exists
to catch. That coverage gap is real and should be named as a limitation in the paper, not
quietly patched over by weakening the example.

If this needs fixing later, the two options above are the shape of the fix; a v2 schema bump
would be needed since it changes the frame-path grammar's expressive power, not just this
document.

## check 5's synthetic-argument table has no case for list/object-typed arguments

Found while authoring the 17-contract batch of remaining tau2 mutating tools (airline
book_reservation / send_certificate / update_reservation_baggages / update_reservation_flights
/ update_reservation_passengers; retail cancel_pending_order / exchange_delivered_order_items /
modify_pending_order_address / modify_pending_order_items / modify_pending_order_payment /
modify_user_address / return_delivered_order_items; telecom suspend_line / resume_line /
send_payment_request / enable_roaming / disable_roaming).

`spec/validate.py`'s check 5 (synthetic-snapshot evaluation) builds the predicate `args` binding
purely from each argument's declared `signature.args.<name>.type` string:

```python
_SYNTH_BY_TYPE = {"str": "x", "int": 1, "float": 1.0, "bool": True}
args = {name: _SYNTH_BY_TYPE.get(a.get("type")) for name, a in doc.get("signature", {}).get("args", {}).items()}
```

Any declared type outside that four-entry table -- `List[FlightInfo]`, `List[Passenger]`,
`List[str]`, or any other collection/object-shaped argument -- resolves to `None`. A predicate
that iterates such an argument (`for f in args.flights`) or takes its length
(`len(args.passengers)`) then raises `TypeError`/`AttributeError` inside `evaluate()`, which
check 5 reports as a clause failure, not a skip. This is not a predicate-grammar limitation
(the grammar in PREDICATE-GRAMMAR.md sec 2 has no trouble parsing or, given a real list,
evaluating such a comprehension) -- it is a gap in the validator's own synthetic-fixture
harness, one level below the grammar this file otherwise tracks.

Half of tau2's mutating-tool interface is built around list-shaped arguments (a batch of flight
segments, a batch of passengers, a batch of item ids to exchange or return), and several of the
most substantive advertised preconditions are stated over exactly those arguments -- most
notably `book_reservation`'s per-flight seat-availability check ("Not enough seats on flight",
airline/tools.py:261), which needs `args.flights` and `args.passengers` together and cannot be
restated over `pre`/`post`/`result` alone (unlike, say, update_reservation_passengers' passenger
COUNT invariant, which check 5 can express because pre/post are both real, controlled
snapshots). `spec/contracts/tau2/book_reservation.yaml`'s notes record this specific instance
and the clause it prevented from being written; the workaround adopted across all 17 contracts
in the batch is to reason about list-shaped inputs via the pre/post snapshot or the tool's
result instead of iterating an args list directly, which the fixtures under
`tests/fixtures/tau2_{airline,retail,telecom}_state.json` fully control.

Two ways to close this, both currently unavailable:
- extend `_SYNTH_BY_TYPE`'s synthesis (or the `--state-schema` file format) to accept a literal
  synthetic value per named argument, not just per Python-ish type string, so a contract could
  supply `args.flights = [{"flight_number": "x", "date": "x"}]` directly; or
- accept that check 5 is a smoke test for the four scalar builtin types only, and document that
  predicates over list/object-typed arguments are validated solely by check 2 (AST whitelist +
  free-name binding) plus live evaluation against a real adapter, never by check 5's synthetic
  pass.

Neither exists today. This is a validate.py/tooling gap, not a spec/schema.json or
PREDICATE-GRAMMAR.md one, so it does not need a contract-version bump to fix -- but per
CLAUDE.md, spec/validate.py itself is not to be modified as part of this batch, so the fix is
left for a follow-up rather than applied here.
