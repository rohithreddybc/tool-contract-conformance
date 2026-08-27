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

## `arg.<name>` clause ids can never land above INFERRED tier under the shipped AgentDojo/
## MM-ToolSandbox contracts, even when the argument is genuinely docstring-documented

**RESOLVED 2026-08-26** for all 12 AgentDojo/MM-ToolSandbox contracts. See amendment at the
bottom of this entry. The gap as originally found is left below unedited, since it is still the
correct description of why the gap existed and what would have been wrong about fixing it
alongside the headline_tier wiring itself.

Found while wiring `core.model.headline_tier()` through `dynamic/harness.py` (the two adapters'
contracts, plus the check-8 threading). Not a schema or grammar limitation -- `ArgSpec` already
carries an optional `provenance` field (schema.json argSpec $defs, `core/model.py`'s `ArgSpec`
dataclass) -- but none of the 12 AgentDojo/MM-ToolSandbox contracts' `signature.args.<name>`
entries populate it, for any argument, anywhere. `dynamic/harness.py`'s `check_ignored_argument`
reports its verdict against a synthetic `arg.<name>` clause id (there is no Clause object for an
argument in `Contract.all_clauses()` at all -- see `dynamic/harness.py`'s `_ArgAsClause` shim),
and `headline_tier()`'s own rule is unconditional: `provenance is None` -> `INFERRED`, regardless
of how well-documented the argument actually is in the tool's docstring.

Concretely: `invite_user_to_slack.yaml`'s `user_email` (FINDINGS-VERIFIED.md Finding 8) IS
documented ("The user email where invite should be sent", per that contract's own header
comment) but carries no `signature.args.user_email.provenance` block, so its `arg.user_email`
VIOLATES verdict is permanently `INFERRED` tier -- and, because this finding has NO state path an
effect clause could assert over (the contract's own notes explain why: the Slack model has no
email-tracking field at all), `arg.user_email` is the ONLY clause this finding can ever be
reported against. Finding 8 is therefore structurally unable to reach headline-eligibility under
the current contracts, regardless of how the check-8/repo-root wiring is done -- not because the
evidence is weak, but because no `signature.args` entry in the shipped batch was ever given a
provenance quote to grade.

`reserve_car_rental.yaml`'s `end_time` (Finding 6) and `venmo_social.yaml`'s `sort_by` (Finding 7)
do not hit this same wall only because each ALSO has a same-named effect clause
(`eff.end_time_applied`, `eff.sort_by_forwarded`) carrying its own docstring provenance -- so
those two findings are headline-eligible via the effect-clause route even though their own
`arg.*` verdict is `INFERRED` for the identical reason `user_email`'s is.

This was not fixed by adding `signature.args.<name>.provenance` retroactively to the 12 shipped
contracts: those contracts are described as already authored and validating with zero skips, and
backfilling provenance on them now, in the same change that wires up headline_tier, would be
indistinguishable from tuning a contract to hit a tier -- exactly what CLAUDE.md's "do not weaken
a clause to make a finding appear" guards against, even though provenance is additive rather than
a weakening. Recorded here instead, as a real result about this contract batch's completeness:
`Contract.signature.args[...].provenance` needs to be populated as a matter of course whenever an
argument's own documentation is the ONLY grounds for a future finding that has no effect-clause
counterpart, or that finding cannot be headline-eligible no matter how faithfully check 8 is run.

### Amendment 2026-08-26 -- backfilled, in a change separate from the headline_tier wiring

The objection above was specifically to backfilling provenance "in the same change that wires up
headline_tier" -- doing it there would have been indistinguishable from tuning a contract to hit
a tier chosen in advance. That change has long since landed and shipped; this is a later, separate
change, made for its own stated reason (closing a probe gap named in
`detector_analysis_plan.md` sec 4.3, and this structural cap on Finding 8 named here), not to move
any one finding's tier.

Every `signature.args.<name>` entry across all 12 AgentDojo/MM-ToolSandbox contracts was checked
against the tool's own docstring at its pinned commit. The result is unqualified in this batch:
**every single argument in all 12 contracts turned out to have a genuine, verbatim, per-argument
docstring line** (AgentDojo's `:param name: ...` convention and MM-ToolSandbox's `Args:`-block
convention both document parameters individually, with no undocumented argument found anywhere in
this batch). Each entry now carries `provenance: {surface: docstring, file, line, quote}` citing
that exact line, verified the same way check4_provenance verifies it (the quote is a substring of
the cited source line at the pinned commit) -- `python spec/validate.py` was re-run per benchmark
with `--repo-root` and the matching `tests/fixtures/*_state.json` `--state-schema`, and all 12
files pass all 8 checks with zero skips, unchanged from before this amendment.

No argument was left without provenance in this batch, so the "leave it absent, do not invent a
surface" rule this file otherwise emphasizes had no case to apply to here -- it remains the rule
for the NEXT contract that has a genuinely undocumented argument, and nothing above should be read
as license to invent a quote where none exists.

**Consequence for Finding 8.** `arg.user_email` now resolves `AGENT_VISIBLE` (docstring surface,
`check8_passed` true by default for a surface check 8 does not test) instead of `INFERRED`.
Finding 8 is therefore now headline-eligible on its own clause -- the structural cap this entry
originally described no longer applies to it. `arg.end_time` (Finding 6) and `arg.sort_by`
(Finding 7) also now resolve `AGENT_VISIBLE` directly at the `arg.*` clause, which changes nothing
about their headline-eligibility (both already reached it via their same-named effect clause) but
removes the asymmetry this entry noted between them and `user_email`.

**What remains.** This amendment is scoped to the 12 shipped AgentDojo/MM-ToolSandbox contracts
only, per the change that produced it. tau2 and toy contracts were not touched and were not
audited for the same gap here; if any of their `signature.args` entries are similarly
under-provenanced, that is a separate, unverified question this amendment does not answer.
