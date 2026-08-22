# Predicate and Frame-Path Grammar

Normative specification for the two small languages a contract uses. Referenced from `spec/schema.json`.

This is a DSL. The paper says so rather than claiming otherwise — a reviewer who knows IcePICK will recognize the shape immediately, and pretending it is "just Python" invites the objection that we re-solved a solved problem badly. What we claim is narrow: the language is small enough to review by eye, executes without a parser we have to defend, and is expressive enough for the six defect classes.

---

## 1. Bindings

Every predicate is evaluated against exactly four names. Nothing else is in scope.

| Name | Type | Meaning |
|---|---|---|
| `pre` | canonical snapshot | environment state immediately before `invoke` |
| `post` | canonical snapshot | environment state immediately after `invoke` |
| `args` | mapping | the arguments passed to this call |
| `result` | mapping | the tool's return value, canonicalized; `result.error` is present iff the call raised |

A snapshot is JSON-shaped: nested mappings, sequences, strings, numbers, booleans, nulls. There are no objects and no methods. `pre.customers` is a mapping lookup, not attribute access — the evaluator rewrites dotted access into subscripting before execution, so a missing key is a contract error with a located message, not an `AttributeError`.

## 2. Expression whitelist

Permitted AST nodes:

- literals: `Constant`, `List`, `Tuple`, `Dict`, `Set`
- names: `Name` (only the four bindings and comprehension binders), `Attribute` (rewritten to subscript), `Subscript`, `Slice`
- operators: `BoolOp`, `UnaryOp`, `BinOp` restricted to `+ - * / // % **`, `Compare` including `in` and `not in`
- conditionals: `IfExp`
- comprehensions: `GeneratorExp`, `ListComp`, `SetComp`, `DictComp` — **with an explicit binder**, see §2.1
- calls: `Call` where the callee is one of the allowed builtins below and every argument is itself permitted

Permitted builtins, and nothing else:

```
len  sum  min  max  abs  round  sorted  any  all  set  int  float  str  bool
```

Explicitly rejected: `import`, `Lambda`, `Await`, `Yield`, walrus (`NamedExpr`), f-strings (`JoinedStr`), attribute access on anything that is not a snapshot path, dunder names, and any call whose callee is not a bare allowed builtin. A rejected node is a validator error at contract-authoring time, never a runtime surprise.

### 2.1 Binders are mandatory in comprehensions

The v1 draft contained this clause:

```
post.flights[f].available_seats == pre.flights[f].available_seats + booked_seats
```

`f` and `booked_seats` are unbound. It does not evaluate, and it would have shipped. Every free name must be bound by a comprehension over a snapshot or argument path:

```
all(
  post.flights[f].available_seats == pre.flights[f].available_seats + args.n_seats
  for f in args.reservation.flights
)
```

The validator enforces: every `Name` is either one of the four bindings or introduced by an enclosing `for` target in the same expression. A free name is an error naming the identifier and the clause id.

### 2.2 Quantification idioms

| Intent | Form |
|---|---|
| all matching elements satisfy P | `all(P for x in <path>)` |
| at least one satisfies P | `any(P for x in <path>)` |
| exactly one satisfies P | `sum(1 for x in <path> if P) == 1` |
| counting | `len([x for x in <path> if P])` |

`for x in <path>` iterates a sequence's elements or a mapping's **keys**, following Python. Contracts that mean values must say `<path>[k]`.

### 2.3 Missing paths

A path that does not resolve is not `False`. It raises a located contract error and the clause resolves to UNTESTABLE with reason `no_observable_state`. This matters: silently treating an absent field as falsy would let a shallow contract report CONFORMS on an environment it cannot actually see, which is precisely the failure the contract-coverage metric exists to expose.

To assert presence deliberately, write `'k' in pre.customers`.

---

## 3. Frame-path grammar

Frame clauses name regions of state that must not change. A frame path is segments joined by `.`:

| Segment | Matches |
|---|---|
| `identifier` | that literal key |
| `*` | any single mapping key at this level |
| `[]` | any single sequence index at this level |
| `**` | any depth, including zero levels |

Examples:

```
state.customers.*.payment_methods        every customer's payment methods, one level of wildcard
state.reservations.*.flights.[].cabin    cabin of every flight of every reservation
state.**.audit_log                       any audit_log at any depth
```

Matching yields a set of concrete paths. `mode: unchanged` (the default) asserts every matched subtree is equal pre and post after canonicalization; `mode: changed` asserts at least one differs. A frame path matching nothing is an error, not a vacuous pass — an unmatched frame clause almost always means a typo or a snapshot-shape change, and passing vacuously would hide it.

`state.` is the conventional root prefix and is stripped before matching against the snapshot; it exists so frame paths read the way the docstrings do.

---

## 4. Canonicalization

Both snapshots pass through the same canonicalizer before any comparison. Without this, false positives from irrelevant churn would dominate the Partial Effect and frame detectors — and the paper reports the rules, because "we diffed the state" is not a method description.

1. Mappings are serialized with sorted keys. Insertion order is never semantic.
2. Volatile fields are replaced by a sentinel, per adapter, from an explicit list. Timestamps, autogenerated identifiers, and monotonic counters go here. The list is part of the adapter's declared configuration and is printed in the artifact — a volatile field is a place where the checker is deliberately blind, so it must be auditable.
3. Floats are compared at a declared tolerance, default exact. A tool that computes a charge must state its tolerance in the contract if exactness is wrong.
4. Sequences are order-sensitive by default. An adapter may declare specific paths as order-insensitive sets; that declaration is likewise printed.

Rules 2 and 4 are the two places where a defect could hide. Both are explicit, both are in the artifact, and the count of paths affected by each is reported alongside the findings.

---

## 5. Worked example

`cancel_reservation`, tau2-bench airline, commit `c3398666`. This is the contract that must catch Finding 3.

```yaml
contract_version: "1.0"
tool: cancel_reservation
benchmark: tau2-bench
commit: c3398666
source:
  file: src/tau2/domains/airline/tools.py
  start_line: 340
  end_line: 368

signature:
  args:
    reservation_id: { type: str, effective: true }

preconditions:
  - id: pre.reservation_exists
    text: "the reservation must exist"
    predicate: "args.reservation_id in pre.reservations"
    provenance:
      surface: docstring
      file: src/tau2/domains/airline/tools.py
      line: 345
      quote: "reservation_id: The reservation ID"

effects:
  - id: eff.status_cancelled
    text: "the reservation is marked cancelled"
    predicate: "post.reservations[args.reservation_id].status == 'cancelled'"
    provenance:
      surface: docstring
      file: src/tau2/domains/airline/tools.py
      line: 342
      quote: "Cancel the whole reservation"

  - id: eff.seats_released
    text: "cancelling releases the seats the booking reserved"
    predicate: >
      all(
        post.flights[f.flight_number][f.date].available_seats[pre.reservations[args.reservation_id].cabin]
        == pre.flights[f.flight_number][f.date].available_seats[pre.reservations[args.reservation_id].cabin]
           + len(pre.reservations[args.reservation_id].passengers)
        for f in pre.reservations[args.reservation_id].flights
      )
    provenance:
      surface: tool_return
      file: src/tau2/domains/airline/tools.py
      line: 367
      quote: "Seats release not implemented for cancellation!!!"

frame:
  - id: frame.other_reservations
    path: state.reservations.*
    text: "no other reservation is modified"
    mode: unchanged
    inferred: true

success_signal:
  predicate: "'error' not in result"
  biconditional: true
  justification: >
    The tool returns the mutated reservation object on the success path and raises on every
    declared failure, so a returned reservation is the interface's only signal that the whole
    cancellation was applied. No effect on this tool is advertised as deferred.
  provenance:
    surface: docstring
    file: src/tau2/domains/airline/tools.py
    line: 342
    quote: "Cancel the whole reservation"

invariants:
  - id: inv.seat_conservation
    text: "booked seats plus available seats equals capacity"
    predicate: >
      all(
        post.flights[fn][d].available_seats[c] >= 0
        for fn in post.flights for d in post.flights[fn] for c in post.flights[fn][d].available_seats
      )
    inferred: true

reset:
  predicate: "post == pre"
  scope: unknown
```

**The authoritative copy of this contract is `spec/contracts/tau2/cancel_reservation.yaml`**, which validates against the schema and has been corrected against the real pydantic models. The block above is illustrative and was written before those models were read; where the two differ, the YAML is right. In particular the real flight lookup is `pre.flights[fn].dates[date]` — `Flight.dates` is a union and only the `available` arm carries `available_seats` — and `cabin` lives once on the `Reservation`, not per flight.

Three things to read off it.

**`eff.seats_released` is grounded in `maintainer_annotation`, not `tool_return`, and therefore never enters a headline count.** The first draft of this document grounded it in `tool_return`, quoting `logger.warning("Seats release not implemented for cancellation!!!")` at line 367. That was wrong, and wrong in the exact way this mechanism exists to prevent: the tool *returns* the reservation object at line 368, and the warning goes to the harness log. No agent is ever conditioned on it. The clause was re-tiered after a search of every agent-visible surface in tau2 airline — the `cancel_reservation` docstring and `data/tau2/domains/airline/policy.md`, the agent's system prompt — found no statement anywhere that cancellation returns seats to inventory. Finding 3 is a real Partial Effect violation, corroborated by two maintainer annotations, and it is not headline-eligible. The paper says so.

**`inv.seat_conservation` asserts less than its text claims.** Its `text` describes seat conservation; its predicate asserts only that `available_seats` is non-negative, which is strictly weaker. This is left visible on purpose: it is a live instance of the translation gap between an advertised sentence and an executable predicate, and it is the reason clause authoring is dual-annotated extensionally rather than trusted. Do not read a clause's `text` as a description of what the checker tests — read the predicate.

**`frame.other_reservations` could not be expressed.** `state.reservations.*` under `mode: unchanged` would match the cancelled reservation itself and contradict `eff.status_cancelled`, and the frame grammar has no exclusion syntax and no `args` interpolation. The shipped contract substitutes `frame.users_unchanged` over `state.users`, which is true and expressible but strictly weaker. Recorded in `spec/GRAMMAR-GAPS.md` rather than patched over.

---

## 6. What the validator checks

`spec/validate.py`, run in CI on every contract before Gate 1b:

1. The document validates against `spec/schema.json`.
2. Every predicate parses, contains only whitelisted nodes, and has no free names.
3. Every frame path parses under §3.
4. Every provenance quote with a `file` and `line` actually occurs at that location in the pinned commit. A drifted quote fails the build — this is what keeps the construct-validity claim honest as upstream repositories move.
5. Every predicate evaluates without error against a synthetic snapshot generated from the adapter's declared state schema. Evaluating to `False` is fine; raising is not.
6. `biconditional: true` carries a justification and provenance; `advertised_deferred: true` carries provenance whose quote mentions the deferral.
7. Clause ids are unique within the contract and match their kind prefix.
8. **Agent-visibility of the claimed surface.** A `tool_return` quote must occur inside a `return` expression or in the message of a raised exception — never inside a `logger.*` call, a bare comment, or a `print`. A `prompt_template` quote must occur in a file that reaches the agent's message stream. A quote that fails this test is not agent-visible and must be re-tiered to `maintainer_annotation` or marked `inferred`.

   Check 8 exists because check 4 cannot substitute for it. Check 4 verifies a quote occurs *at the cited location*, which a log line satisfies trivially — and the first draft of the worked contract in §5 grounded its decisive clause in exactly that way and would have passed. Without check 8 the same error recurs silently across every contract authored.

### Headline eligibility

Derived, never hand-set. A clause is headline-eligible iff it carries a provenance whose surface is in the agent-visible tier (§ schema `advertisedSurface`) and that provenance passes check 8. Clauses grounded in `maintainer_annotation`, and clauses marked `inferred: true`, are reported in their own rows and stay out of every headline count and every headline denominator. `report/render.py` computes this from the contract; no table hand-labels it.
