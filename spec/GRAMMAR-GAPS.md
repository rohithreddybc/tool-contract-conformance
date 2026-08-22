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
