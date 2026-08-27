"""The checker's OWN probe generator -- ARCHITECTURE-FINAL.md sec 1/7 ("dynamic/probes.py"),
built to drive dynamic/harness.py's snapshot -> invoke -> snapshot -> evaluate loop against a
live adapter. For each precondition clause: an args-dict that satisfies it and one that violates
it. For each effect clause: one args-dict ("the happy path") under which every declared
precondition holds, so the effect is actually observable rather than pre-empted by a raise. For
each `effective: true` argument: a varied set of args-dicts differing only in that argument's
value, for the checker's own Ignored Argument test (dynamic/harness.py's
`check_ignored_argument` -- see that module for the M-IGNARG definition this drives).

SEPARATION FROM mutation/probes.py -- READ THIS BEFORE REUSING ANYTHING HERE.
detector_analysis_plan.md sec 4.3 depends on this module and mutation/probes.py's equivalence
probe corpus being genuinely disjoint code paths: "if the same probes both screened equivalence
and drove the checker, probe gaps would be invisible by construction." mutation/probes.py's own
module docstring pinned a tripwire test for the day this file was created; that test is now
updated (tests/test_mutation_probes.py, TestSeparationFromCheckerProbes) to assert the ongoing
separation instead of the file's prior absence -- see it and tests/test_dynamic_probes.py's
mirror-image assertion.

This module does NOT import mutation.probes, does NOT import adapters.contract_check (it is a
probe generator, not a checker -- dynamic/harness.py is what calls the checker), and its value-
generation mechanism is deliberately different from mutation/probes.py's, not just differently
named:

  mutation/probes.py (the sec 2 EQUIVALENCE corpus)   generates per-parameter boundary values
      from a fixed, type-keyed valid/domain_invalid/zero_empty triad (_VALID_BY_TYPE etc.),
      varying one parameter at a time while holding every other parameter at one static base
      value. Purpose: screen a mutant against the ORIGINAL tool over a broad, cheap, generic
      input sweep.

  dynamic/probes.py (this module, the CHECKER's own probes)   harvests candidate values FROM THE
      LIVE SNAPSHOT itself -- every dict key and every scalar leaf the environment is actually
      holding, plus "membership links" (an id-like field paired with a same-record list-of-
      scalars field, e.g. a Customer's own `customer_id` alongside its `line_ids`) -- and samples
      JOINT argument assignments over that harvested pool, because several of the six defect
      classes (Unenforced Precondition and Partial Effect above all) are only observable when
      the call actually reaches the tool's effect code, which for a real benchmark tool usually
      requires several arguments to be jointly, relationally valid (refuel_data's
      pre.customer_owns_line is exactly this: the checker needs a (customer_id, line_id) pair
      that is TRUE in the live database, not independently-boundary-valid values for each).
      Purpose: get a real call to actually happen, in either direction (precondition satisfied or
      violated), against the real tool.

Two probers grounded in different mechanisms are far less likely to share the same blind spot --
which is the entire point of keeping them apart. If you find yourself wanting to import one from
the other, or to factor "shared" value-generation logic into a common helper, that is the exact
failure detector_analysis_plan.md sec 4.3 exists to catch. Report it; do not do it.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Optional

from core.model import ArgSpec, Contract
from core.predicates import PathError, PredicateTypeError, compile_predicate, evaluate

__all__ = [
    "Probe",
    "DynamicProbePlan",
    "harvest_snapshot_pool",
    "generate_precondition_probes",
    "generate_effect_probe",
    "generate_ignored_argument_probes",
    "joint_falsy_argument_names",
    "generate_joint_falsy_probe",
    "build_dynamic_probe_plan",
]

# Deterministic default search budgets. Kept small and named (not buried as inline literals) so a
# caller can widen them for a sparser snapshot without editing this module -- see the `k=`/
# `n_values=` keyword arguments below. `_DEFAULT_POOL_SIZE` is deliberately larger than
# `_DEFAULT_N_VALUES`: the JOINT SEARCH (satisfy/violate/happy-path) needs a wide per-argument
# pool so a rare value (the one frozen account among three, say) is actually reachable, while the
# Ignored Argument variant SET reported in findings.jsonl stays small and readable on purpose.
_DEFAULT_K = 48
_DEFAULT_POOL_SIZE = 16
_DEFAULT_N_VALUES = 3


@dataclass(frozen=True)
class Probe:
    """One probe call: `tool` with `args`, tagged with `origin` for provenance/reporting.
    `origin` is one of "precondition_satisfy:<clause_id>", "precondition_violate:<clause_id>",
    "effect_happy_path", or "ignored_argument:<arg_name>:<i>"."""

    tool: str
    args: dict
    origin: str


@dataclass(frozen=True)
class DynamicProbePlan:
    """The full sec-1-build-spec probe set for one contract, bundled for dynamic/harness.py's
    convenience: precondition satisfy/violate probes, the effect happy-path probe (None if the
    search found no joint assignment satisfying every precondition -- the harness reports that as
    UNTESTABLE rather than guessing), per-effective-argument Ignored Argument variant sets
    (an argument is absent from this dict if fewer than two distinct-valued variants could be
    built for it), and the joint-falsy probe (None if the contract has fewer than two falsy-
    eligible `effective: true` arguments -- not applicable, not a gap -- or if no joint
    assignment with every such argument set falsy at once could be found satisfying every
    precondition; see `generate_joint_falsy_probe`)."""

    precondition_probes: tuple = ()
    effect_probe: Optional[Probe] = None
    ignored_argument_probes: dict = field(default_factory=dict)
    joint_falsy_probe: Optional[Probe] = None


# ---------------------------------------------------------------------------------------------
# Snapshot-grounded value harvesting -- the mechanism this module uses instead of
# mutation/probes.py's fixed per-type boundary triad. See module docstring.
# ---------------------------------------------------------------------------------------------


def _type_name(value: Any) -> Optional[str]:
    # bool before int -- bool is an int subclass in Python and must never be bucketed as one
    # (mirrors core/canonical.py's _is_number's same precaution, for the same reason: a flag
    # flip must never be silently treated as a number).
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    return None


def _id_like_fields(record: dict) -> dict:
    """Scalar fields of `record` whose key looks like an identifier ('id', or ending '_id') --
    the generic, shape-only signal `_harvest_membership_links` uses to find an "owner" field
    alongside a same-record list-of-scalars field. No benchmark or domain vocabulary."""
    out = {}
    for k, v in record.items():
        if (k == "id" or k.endswith("_id")) and _type_name(v) in ("str", "int"):
            out[k] = v
    return out


def _is_homogeneous_collection(d: dict) -> bool:
    """True iff every value in `d` shares a common shape signature -- all dicts with the same
    key-set, all lists, or all the same scalar type. The generic signal this module uses to tell
    an ID-KEYED COLLECTION (e.g. `state.accounts: {"acc_alice": {...}, "acc_bob": {...}}`, whose
    KEYS are entity ids worth harvesting as candidate argument values) apart from a fixed-schema
    RECORD/struct (e.g. one account's own `{"owner": ..., "balance": ..., "frozen": ...}`, whose
    keys are field NAMES -- harvesting those would pollute the pool with strings like 'balance'
    that are never a valid argument value for anything). An empty dict is neither."""
    if not d:
        return False
    values = list(d.values())
    if all(isinstance(v, dict) for v in values):
        return len({frozenset(v.keys()) for v in values}) == 1
    if all(isinstance(v, list) for v in values):
        return True
    types = {_type_name(v) for v in values}
    return len(types) == 1 and None not in types


_ROLE_PREFIXES = ("from_", "to_", "src_", "dst_", "source_", "target_", "primary_", "secondary_")


def _concept_root(arg_name: str) -> str:
    """Strip a common role prefix (`from_account` -> `account`) and/or a trailing `_id`
    (`account_id` -> `account`) off an argument name, leaving the bare concept it names. Purely
    string-shape-driven, no benchmark vocabulary -- used only to MATCH an argument against a
    harvested collection's own field name (`_collection_pool_for`), never to interpret meaning."""
    root = arg_name
    for p in _ROLE_PREFIXES:
        if root.startswith(p):
            root = root[len(p):]
            break
    if root.endswith("_id") and len(root) > len("_id"):
        root = root[: -len("_id")]
    return root


def _singularize(name: str) -> str:
    return name[:-1] if name.endswith("s") and not name.endswith("ss") else name


def harvest_snapshot_pool(snapshot: Any) -> tuple:
    """Walk a JSON-shaped snapshot once and return `(pools, links, collections)`:

    `pools`: dict[type_name, list[value]] -- every dict KEY belonging to a dict
    `_is_homogeneous_collection` judges to be an id-keyed collection (JSON keys are always
    strings, so these feed the "str" pool -- this is what lets a probe satisfy something shaped
    like `args.reservation_id in pre.reservations`, a dict-key existence check) and every scalar
    leaf VALUE the snapshot holds, deduplicated, first-seen order preserved.

    `links`: list[(owner_key, owner_value, member_field, member_value)] -- for every dict record
    that carries both an id-like scalar field (`_id_like_fields`) and a same-record
    list-of-scalars field elsewhere, one tuple per (owner field, that record's own value for it,
    the NAME of the list field the member came from, each list element). This is the
    relational-shape signal `_joint_combinations` uses to keep two dependent arguments (an owner
    id and a member id it lists) consistent when sampling -- e.g. a tau2 telecom Customer's
    `customer_id` alongside its `line_ids`. `member_field` is carried through (not just the
    value) because a record can carry MORE THAN ONE same-owner list-of-scalars field -- a tau2
    telecom Customer has both `line_ids` and `bill_ids` -- and conflating them by owner alone
    would let a probe pair an argument like `line_id` with a value harvested from the sibling
    `bill_ids` field just because both are plain strings; `_linked_owner_and_member` uses
    `member_field` to disambiguate by name, not merely by type.

    `collections`: dict[enclosing_key_name, list[value]] -- the SAME id-keyed-collection keys as
    `pools["str"]`, but kept separate per the dict key they were found under (e.g. `"accounts"`
    for `state.accounts`'s own keys) instead of merged into one flat pool. `_argument_pool` uses
    this to prefer, for an argument like `from_account` or `item_id`, values sourced from the ONE
    collection whose own name matches the argument's concept root (`_concept_root` /
    `_singularize`) over the generic flattened pool -- which otherwise mixes real entity ids from
    every collection together and can make two same-typed, differently-sourced arguments (e.g.
    `from_account` and `to_account`, both plain `str`) very unlikely to land on two valid,
    DISTINCT entities of the right kind by independent chance alone."""
    pools: dict = {"str": [], "int": [], "float": [], "bool": []}
    seen: dict = {"str": set(), "int": set(), "float": set(), "bool": set()}
    links: list = []
    collections: dict = {}

    def _add(value: Any) -> None:
        t = _type_name(value)
        if t is None:
            return
        if value in seen[t]:
            return
        seen[t].add(value)
        pools[t].append(value)

    def _walk(node: Any, enclosing_key: Optional[str]) -> None:
        if isinstance(node, dict):
            id_fields = _id_like_fields(node)
            collection = _is_homogeneous_collection(node)
            if collection and enclosing_key is not None:
                bucket = collections.setdefault(enclosing_key, [])
                for k in node:
                    if k not in bucket:
                        bucket.append(k)
            for k, v in node.items():
                if collection:
                    _add(k)  # id-keyed collection -- see docstring
                if isinstance(v, list) and v and all(_type_name(e) is not None for e in v):
                    for owner_key, owner_value in id_fields.items():
                        for member_value in v:
                            links.append((owner_key, owner_value, k, member_value))
                _walk(v, k)
            return
        if isinstance(node, list):
            for v in node:
                _walk(v, enclosing_key)
            return
        _add(node)

    _walk(snapshot, None)
    return pools, links, collections


# Small, out-of-pool values so an argument's candidate list never collapses to a single entry
# even when the live snapshot happens to hold only one distinct value of that type. Deliberately
# distinct literals from mutation/probes.py's _DOMAIN_INVALID_BY_TYPE/_ZERO_EMPTY_BY_TYPE -- not
# a "the same idea, renamed" duplication, a different, smaller safety net for a different
# purpose (this module wants *diversity* for a joint search, not a boundary taxonomy).
_SYNTH_EXTRA = {
    "str": ("__dynamic_probe_absent__",),
    "int": (-1, 1_000_003),
    "float": (-1.0, 1_000_003.5),
    "bool": (True, False),
}


def _argument_pool(name: str, spec: ArgSpec, pools: dict, collections: dict, n: int) -> list:
    """Up to `n` distinct candidate values for one argument, in preference order:

    1. contract-declared `probe_values` (authoritative -- schema.json argSpec)
    2. values from the ONE harvested collection whose own field name matches this argument's
       concept root (`_concept_root`/`_singularize` -- e.g. `from_account`/`item_id` against a
       harvested `accounts`/`items` collection), if such a match is unambiguous
    3. the generic flattened snapshot pool for the argument's declared type
    4. a couple of synthesized out-of-pool values as a floor

    Never empty. Step 2 is what keeps two same-typed arguments (e.g. `from_account` and
    `to_account`) from having to find each other by pure chance in the generic pool -- see
    `harvest_snapshot_pool`'s docstring."""
    values: list = list(spec.probe_values)
    root = _singularize(_concept_root(name))
    matching_collections = [vs for key, vs in collections.items() if _singularize(key) == root]
    if len(matching_collections) == 1:
        for v in matching_collections[0]:
            if len(values) >= n:
                break
            if v not in values:
                values.append(v)
    for v in pools.get(spec.type, []):
        if len(values) >= n:
            break
        if v not in values:
            values.append(v)
    for v in _SYNTH_EXTRA.get(spec.type, ()):
        if len(values) >= n:
            break
        if v not in values:
            values.append(v)
    if not values:
        values = [None]
    return values


def _field_concept(field_name: str) -> str:
    """Concept root of a harvested list-FIELD name (e.g. 'line_ids' -> 'line'), via the same
    singularize/strip-role-prefix/strip-trailing-_id pipeline `_concept_root`/`_singularize`
    apply to ARGUMENT names -- so a field and an argument naming the same concept resolve to the
    same root and can be matched by name, not merely by shared scalar type."""
    return _concept_root(_singularize(field_name))


def _linked_owner_and_member(contract: Contract, links: list) -> tuple:
    """If exactly one argument's name exactly matches some link's owner_key, find the ONE
    sibling list-field of that owner (there can be several, e.g. a Customer's `line_ids` AND
    `bill_ids`) whose name-concept unambiguously matches exactly one OTHER argument, and return
    (owner_arg_name, member_arg_name, member_field_name) so `_joint_combinations` can sample the
    pair jointly, drawing only from links sourced from THAT field. Otherwise (no owner match, no
    field-name match, or an ambiguous match) return (None, None, None) -- a wrong guess is worse
    than no linkage, so this only ever commits to an unambiguous pairing.

    Matching by field NAME first (not just by scalar type, which the first version of this
    function used) matters because two sibling list fields of the same owner are very often the
    same scalar type (two lists of strings) -- type alone cannot tell a `line_ids` value from a
    `bill_ids` value, and picking the wrong one silently manufactures a joint sample that looks
    valid (a real owner, a real list member) but pairs an argument with a value from the wrong
    relation entirely (probing `refuel_data`'s `line_id` with a harvested `bill_id`, for tau2
    telecom's Customer -- found empirically: it made the search for a genuinely-owned, non-Active
    line effectively unreachable, since the "violating" combo it settled on failed for the wrong
    reason -- `line_id` not found at all -- rather than the declared reason -- an inactive line)."""
    if not links:
        return None, None, None
    owner_keys = {k for k, _, _, _ in links}
    arg_names = list(contract.signature.args)
    owner_candidates = [a for a in arg_names if a in owner_keys]
    if len(owner_candidates) != 1:
        return None, None, None
    owner_arg = owner_candidates[0]

    fields_for_owner = {field for (k, _, field, _) in links if k == owner_arg}
    by_field_name_match: dict = {}
    for field in fields_for_owner:
        concept = _field_concept(field)
        matches = [a for a in arg_names if a != owner_arg and _singularize(_concept_root(a)) == concept]
        if len(matches) == 1:
            by_field_name_match[field] = matches[0]

    if len(by_field_name_match) == 1:
        (field, member_arg), = by_field_name_match.items()
        return owner_arg, member_arg, field

    # No unambiguous name match (zero fields matched, or more than one field each claimed a
    # distinct argument -- e.g. both `line_ids`->`line_id` and some other field matched some
    # other argument, in which case each pair is already handled by its own iteration and
    # committing to the type-only rule below would be a guess). Fall back to the old,
    # type-only rule ONLY when there is a single list field for this owner in the first
    # place -- so there is nothing left to disambiguate and the fallback cannot silently pick
    # the wrong sibling field.
    if len(fields_for_owner) == 1 and not by_field_name_match:
        field = next(iter(fields_for_owner))
        member_examples = [mv for (k, _, f, mv) in links if k == owner_arg and f == field]
        member_type = _type_name(member_examples[0])
        member_candidates = [
            a for a in arg_names if a != owner_arg and contract.signature.args[a].type == member_type
        ]
        if len(member_candidates) == 1:
            return owner_arg, member_candidates[0], field

    return None, None, None


def _joint_combinations(contract: Contract, pre: Any, *, seed: int, k: int) -> list:
    """`k` joint argument-value assignments (dicts covering every declared argument), the first
    always the "base" (first pool value per argument, and the first harvested link if one was
    found -- deterministic, not random). The remaining draws are a seeded pseudo-random JOINT
    sample: every argument independently drawn from its own harvested pool, EXCEPT that if
    `_linked_owner_and_member` found an unambiguous relational pair, that pair is drawn together
    from the harvested links so the two stay relationally consistent (contrast
    mutation/probes.py's per-parameter sweep, which never couples two parameters). Exact
    duplicate assignments are collapsed, order preserved."""
    pools, links, collections = harvest_snapshot_pool(pre)
    arg_names = list(contract.signature.args)
    arg_pools = {
        name: _argument_pool(name, spec, pools, collections, n=_DEFAULT_POOL_SIZE)
        for name, spec in contract.signature.args.items()
    }
    owner_arg, member_arg, member_field = _linked_owner_and_member(contract, links)
    pair_pool = (
        [(ov, mv) for (k_, ov, f, mv) in links if k_ == owner_arg and f == member_field] if owner_arg else []
    )

    rng = random.Random(seed)

    def _draw() -> dict:
        assignment = {name: rng.choice(arg_pools[name]) for name in arg_names}
        if pair_pool:
            ov, mv = rng.choice(pair_pool)
            assignment[owner_arg] = ov
            assignment[member_arg] = mv
        return assignment

    base = {name: arg_pools[name][0] for name in arg_names}
    if pair_pool:
        ov, mv = pair_pool[0]
        base[owner_arg] = ov
        base[member_arg] = mv

    combos = [base]
    for _ in range(max(k - 1, 0)):
        combos.append(_draw())

    seen_keys: set = set()
    deduped: list = []
    for combo in combos:
        key = tuple(sorted(combo.items()))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append(combo)
    return deduped


# ---------------------------------------------------------------------------------------------
# 1. Precondition satisfy/violate probes.
# ---------------------------------------------------------------------------------------------


def generate_precondition_probes(
    contract: Contract, pre: Any, *, seed: int = 0, k: int = _DEFAULT_K
) -> list:
    """For each declared precondition clause, search a joint-sampled combination pool (see
    `_joint_combinations`) for one args-dict that makes the clause's predicate evaluate True
    against `pre`, and one that makes it False. A clause with no satisfying or no violating
    combination in the sampled set contributes only what it found -- never invented outright,
    matching detector_analysis_plan.md sec 2's "probes are never added to justify a result" in
    spirit (that rule is written about the equivalence corpus; the same discipline applies here:
    a probe this module could not actually derive is a probe gap, not something to paper over)."""
    combos = _joint_combinations(contract, pre, seed=seed, k=k)
    probes: list = []
    for pc in contract.preconditions:
        compiled = compile_predicate(pc.predicate)
        satisfying: Optional[dict] = None
        violating: Optional[dict] = None
        for combo in combos:
            try:
                held = evaluate(compiled, pre, pre, combo, {})
            except (PathError, PredicateTypeError):
                continue
            if held and satisfying is None:
                satisfying = combo
            if not held and violating is None:
                violating = combo
            if satisfying is not None and violating is not None:
                break
        if satisfying is not None:
            probes.append(Probe(tool=contract.tool, args=dict(satisfying), origin=f"precondition_satisfy:{pc.id}"))
        if violating is not None:
            probes.append(Probe(tool=contract.tool, args=dict(violating), origin=f"precondition_violate:{pc.id}"))
    return probes


# ---------------------------------------------------------------------------------------------
# 2. Effect happy-path probe: one joint assignment satisfying every precondition at once.
# ---------------------------------------------------------------------------------------------


def generate_effect_probe(contract: Contract, pre: Any, *, seed: int = 1, k: int = _DEFAULT_K) -> Optional[Probe]:
    """One args-dict under which every declared precondition holds simultaneously, so a call
    built from it is expected to succeed and exercise the tool's effect code -- the only
    condition under which an effect clause is genuinely testable rather than pre-empted by a
    raise. A different, independent seed from `generate_precondition_probes` so this search's
    draw order is not coupled to that one's. Returns None (a probe gap, reported by the harness
    as UNTESTABLE) if no combination in the sampled set satisfies every precondition."""
    combos = _joint_combinations(contract, pre, seed=seed, k=k)
    compiled_preconditions = [compile_predicate(pc.predicate) for pc in contract.preconditions]
    for combo in combos:
        try:
            if all(evaluate(cp, pre, pre, combo, {}) for cp in compiled_preconditions):
                return Probe(tool=contract.tool, args=dict(combo), origin="effect_happy_path")
        except (PathError, PredicateTypeError):
            continue
    return None


# ---------------------------------------------------------------------------------------------
# 3. Ignored Argument variant sets: one per `effective: true` argument.
# ---------------------------------------------------------------------------------------------


def generate_ignored_argument_probes(
    contract: Contract,
    pre: Any,
    *,
    seed: int = 2,
    n_values: int = _DEFAULT_N_VALUES,
    k: int = _DEFAULT_K,
) -> dict:
    """For each `effective: true` argument, up to `n_values` full args-dicts differing ONLY in
    that argument's value, every other argument held at a shared base -- the effect happy-path
    probe's args when one was found (so the resulting calls are expected to succeed and a
    post-state comparison is meaningful; see dynamic/harness.py's `check_ignored_argument` for
    why a failed call must never be used as invariance evidence), else the joint search's own
    base combination. An argument is omitted from the returned dict if fewer than two DISTINCT
    values could be assembled for it -- there is nothing to compare."""
    happy = generate_effect_probe(contract, pre, seed=seed, k=k)
    if happy is not None:
        base = dict(happy.args)
    else:
        base = _joint_combinations(contract, pre, seed=seed, k=1)[0]

    pools, _links, collections = harvest_snapshot_pool(pre)
    result: dict = {}
    for name, spec in contract.signature.args.items():
        if not spec.effective:
            continue
        pool = _argument_pool(name, spec, pools, collections, n=max(n_values, 2))
        variants: list = []
        seen_values: list = []
        for i, v in enumerate(pool):
            if v in seen_values:
                continue
            seen_values.append(v)
            variant_args = dict(base)
            variant_args[name] = v
            variants.append(Probe(tool=contract.tool, args=variant_args, origin=f"ignored_argument:{name}:{i}"))
            if len(variants) >= n_values:
                break
        if len(variants) >= 2:
            result[name] = variants
    return result


# ---------------------------------------------------------------------------------------------
# 4. Joint-falsy probe: every falsy-eligible `effective: true` argument set falsy AT ONCE.
#
# Generic fix for the probe gap detector_analysis_plan.md sec 4.3 names: a clause the contract
# already covers, that the checker's own probes never drove the tool into the state to expose.
# `generate_ignored_argument_probes` above only ever varies ONE argument at a time (every OTHER
# argument held at a fixed, non-falsy base value) -- so a tool that truthiness-guards SEVERAL
# arguments (`if amount:` / `if recurring:`, Python truthiness rather than an `is not None`
# check -- the exact shape static_check's own `truthiness_guard` check looks for on the static
# side) only ever has ONE guarded argument at a time set to its falsy value in any single probed
# call. Every OTHER guarded argument's own effect clause still conforms in that call, because
# that argument's own base value is non-falsy and was in fact applied -- so the checker never
# observes the state where EVERY testable effect clause fails simultaneously, which is exactly
# the state `success_signal.biconditional` needs to re-tag a violation Phantom Effect rather than
# Ignored Argument/Partial Effect. This strategy is the generic fix: drive every falsy-eligible
# effective argument to its falsy value in the SAME call.
#
# Tool-agnostic by construction: `joint_falsy_argument_names` reads only `signature.args.<name>`
# (`effective` and `type`), never a tool name, a benchmark name, or a clause id. It fires for any
# contract with two or more such arguments; a single one is already exercised by the falsy value
# ordinarily present among `generate_ignored_argument_probes`'s own harvested/synthesized
# candidates for that one argument (`_SYNTH_EXTRA`'s bool entries include False, and 0/""/0.0
# are frequently present in a live snapshot's own pool) -- it takes at least two argument
# simultaneously falsy to reach a state the one-at-a-time strategy cannot reach at all.
# ---------------------------------------------------------------------------------------------

# A separate, purpose-built table from mutation/probes.py's `_ZERO_EMPTY_BY_TYPE` and this
# module's own `_SYNTH_EXTRA` -- see the module docstring's separation note. This one is not a
# boundary triad or a diversity floor; it names the one falsy value Python truthiness treats as
# indistinguishable from "argument not supplied" for each of the four scalar builtin types.
_FALSY_BY_TYPE = {
    "int": 0,
    "float": 0.0,
    "bool": False,
    "str": "",
}


def joint_falsy_argument_names(contract: Contract) -> list:
    """`effective: true` arguments of `contract` whose declared `type` is one `_FALSY_BY_TYPE`
    names -- pure signature inspection, no snapshot needed, so a caller can decide applicability
    (2 or more such names) before ever searching for a probe. Order follows
    `contract.signature.args`'s own declaration order."""
    return [
        name
        for name, spec in contract.signature.args.items()
        if spec.effective and spec.type in _FALSY_BY_TYPE
    ]


def generate_joint_falsy_probe(
    contract: Contract, pre: Any, *, seed: int = 3, k: int = _DEFAULT_K
) -> Optional[Probe]:
    """One args-dict, drawn from the same joint-sampled combination pool `generate_effect_probe`
    searches (`_joint_combinations`), with every name in `joint_falsy_argument_names(contract)`
    overridden to its `_FALSY_BY_TYPE` value in that SAME combo -- so the probe both targets the
    joint-falsy state and stays a call the tool is expected to actually accept (only a combo
    still satisfying every declared precondition AFTER the override is returned; a call rejected
    before the tool's effect code runs is not a probe of the effect layer at all). Returns None
    if fewer than two falsy-eligible `effective: true` arguments exist (not applicable to this
    contract -- not a gap) or if no combo in the sampled set satisfies every precondition once
    those arguments are forced falsy (a genuine probe gap, left for the harness to report as
    UNTESTABLE rather than guessed around, matching `generate_effect_probe`'s own discipline)."""
    falsy_names = joint_falsy_argument_names(contract)
    if len(falsy_names) < 2:
        return None
    combos = _joint_combinations(contract, pre, seed=seed, k=k)
    compiled_preconditions = [compile_predicate(pc.predicate) for pc in contract.preconditions]
    for combo in combos:
        candidate = dict(combo)
        for name in falsy_names:
            candidate[name] = _FALSY_BY_TYPE[contract.signature.args[name].type]
        try:
            if all(evaluate(cp, pre, pre, candidate, {}) for cp in compiled_preconditions):
                return Probe(tool=contract.tool, args=candidate, origin="joint_falsy_effect")
        except (PathError, PredicateTypeError):
            continue
    return None


# ---------------------------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------------------------


def build_dynamic_probe_plan(contract: Contract, pre: Any, *, seed: int = 0) -> DynamicProbePlan:
    """The full probe plan dynamic/harness.py needs for one contract against one live pre-
    snapshot: precondition satisfy/violate probes, the effect happy-path probe, per-
    effective-argument Ignored Argument variant sets, and the joint-falsy probe. `seed` is
    forwarded (offset by a fixed, documented amount per sub-generator, so the four searches
    never share a draw sequence) -- see the individual functions' own `seed` defaults."""
    return DynamicProbePlan(
        precondition_probes=tuple(generate_precondition_probes(contract, pre, seed=seed)),
        effect_probe=generate_effect_probe(contract, pre, seed=seed + 1),
        ignored_argument_probes=generate_ignored_argument_probes(contract, pre, seed=seed + 2),
        joint_falsy_probe=generate_joint_falsy_probe(contract, pre, seed=seed + 3),
    )
