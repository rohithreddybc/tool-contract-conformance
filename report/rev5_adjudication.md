# REV-5 adjudication: `frame.other_users_unchanged` on AgentDojo `invite_user_to_slack`

Item under review: Annotator B's frame clause `frame.other_users_unchanged` in
`spec/contracts_annotator_b/agentdojo/invite_user_to_slack.yaml`, reported VIOLATES on 5/5 probes
in `report/agreement_summary.md`'s blind stratum, flagged there as unadjudicated:

> B's notes flag it as a debatable path-scoping choice -- an "unchanged" claim over a wildcard
> that includes a growing list. It is either a real unadvertised-side-effect signal or an
> over-broad frame path, and it is currently neither confirmed nor dismissed.

## Determination: **(b) — over-broad frame path, unsatisfiable by construction**

This is a grammar/authoring finding, not a candidate benchmark defect. The clause VIOLATES on
every successful call not because the tool mutates any *existing* user's entry, but because its
path resolves, under this checker's own documented pre/post-union matching rule, to include the
one new index the tool is advertised to create -- and that index can never be equal between `pre`
and `post` because it does not exist in `pre` at all. The clause is unsatisfiable by construction
whenever the call succeeds, independent of anything the tool actually does to `slack.users[0..k-1]`.

## Evidence

### 1. What the tool actually does

`repos/agentdojo/src/agentdojo/default_suites/v1/tools/slack.py`, pinned commit
`089ed468cf3ed0322acc66b0211f26d9d90dbf60`, lines 93-104 (verified against `git show
089ed468cf3ed0322acc66b0211f26d9d90dbf60:src/agentdojo/default_suites/v1/tools/slack.py`, byte
identical to the working tree copy):

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

The docstring advertises exactly one outcome: "Invites a user to the Slack workspace." The only
per-call state change to `slack.users` is `.append(user)` — a single new element at the end of the
list. No existing element of `slack.users` is read, indexed, or reassigned anywhere in the
function body. There is no mechanism by which this function could alter an existing user's entry.

### 2. B's clause

`spec/contracts_annotator_b/agentdojo/invite_user_to_slack.yaml`, lines 63-67:

```yaml
  - id: frame.other_users_unchanged
    path: slack.users.[]
    mode: unchanged
    text: "existing users' entries in the user list are not altered by inviting a new one"
    inferred: true
```

B's own notes (same file, lines 111-121) already identify the ambiguity and reason toward (a
mistaken) belief that the clause is nonetheless sound:

> frame.other_users_unchanged uses the "[]" wildcard over the whole users list rather than
> excluding the newly appended entry, because the frame-path grammar has no way to reference "all
> entries except the one this call is documented to add" ... Since users are represented as bare
> strings rather than keyed records, and this clause's predicate only needs to hold over the
> elements that existed pre-call, this one happens to still be sound: ... "unchanged" over the
> wildcard is checking that the existing string entries are not mutated in place, which is true
> regardless of the append.

B's reasoning is correct about intent (the *text* of the clause) but wrong about how the checker
actually resolves the wildcard against a pre/post pair whose matched collection changed length —
see 3-4 below.

### 3. How the frame grammar's wildcard is defined

`spec/PREDICATE-GRAMMAR.md` §3: `[]` matches "any single sequence index at this level."
`core/frame.py`'s `match_paths`/`_match` (lines 91-95) implement exactly that: given a list node,
`[]` yields one concrete path per **currently present** index of *whichever snapshot it is run
against*. Read in isolation, matching `slack.users.[]` against `pre` alone would indeed yield only
indices `0..k-1` (the pre-call membership), which is what B's reasoning assumes.

### 4. How the checker actually resolves the pattern against a (pre, post) pair — this is the deciding fact

`dynamic/harness.py` does not match the frame path against `pre` alone. Its helper
`_frame_concrete_paths` (immediately above `check_frame`, checker-freeze-v2, not modified by this
adjudication) unions the matches from both snapshots, by design:

```python
paths = set(match_paths(pattern, pre, require_match=False))
paths |= set(match_paths(pattern, post, require_match=False))
if not paths:
    raise FrameMatchError(f"frame path {pattern!r} matched nothing in pre or post")
return sorted(paths, key=lambda p: tuple(str(x) for x in p))
```

The module-level comment directly above `check_frame` (`dynamic/harness.py`, in the
`check_frame` section header) states the reason explicitly: matching only `pre` would "silently
miss" a key present in `post` but absent in `pre` — "itself exactly the kind of unadvertised
structural change frame checking exists to catch" — and matching only `post` "symmetrically
misses a key the call just DELETED." This union is a deliberate, documented design choice, not an
oversight, and it is exactly the reason B's assumption ("this clause's predicate only needs to
hold over the elements that existed pre-call") does not hold at runtime: the checker does not stop
at "elements that existed pre-call."

For `invite_user_to_slack`, `pre.slack.users` has some length `k` (indices `0..k-1`);
`eff.user_added_to_workspace` — the tool's own advertised, undisputed effect — guarantees
`post.slack.users` has length `k+1` on every successful call. The union of
`match_paths("slack.users.[]", pre)` and `match_paths("slack.users.[]", post)` is therefore
indices `0..k`, where index `k` exists **only** in `post`.

`check_frame` then computes, per matched path, `canonical_equal_at(pre, post, path, cfg)`
(`dynamic/harness.py`, `check_frame`, line 613: `changed_paths = [p for p in paths if not
canonical_equal_at(pre, post, p, cfg)]`). `core/canonical.py`'s `canonical_equal_at` (lines
145-160) descends into each canonicalized
snapshot with `_descend` (lines 129-142), which returns the sentinel `_MISSING = object()` — never
raises — "the instant a step does not resolve" (i.e., an index past the end of the list). For path
`(slack, users, k)`: `_descend(cpre, path)` returns `_MISSING` (index `k` does not exist in the
`k`-element pre list); `_descend(cpost, path)` returns the newly invited user's name string.
`_struct_equal(_MISSING, <username>, tol)` falls through to `_values_equal`, which is false for a
sentinel object compared to a string. So `canonical_equal_at` is `False` at index `k`, `k` lands in
`changed_paths`, `any_changed` is `True`, and the `mode: unchanged` clause is graded VIOLATES —
**on every successful call, unconditionally, regardless of what happens to indices `0..k-1`.**

### 5. This is a mechanical certainty, not a probabilistic observation

Because `eff.user_added_to_workspace` guarantees exactly one append on every successful
`invite_user_to_slack` call, index `k` is guaranteed to exist only in `post` on every successful
probe. `report/agreement_summary.md`'s own count for this clause — `CONFORMS=0, VIOLATES=5,
UNTESTABLE=0` over 5/5 probes — is exactly the expected result of the mechanism above, not evidence
of a probabilistically-observed side effect. There is no probe configuration under which this
clause could grade CONFORMS while the tool behaves as advertised (short of the tool never
succeeding at all, in which case the clause is checked against a case where nothing was invited).

### 6. Corroborating contrast: B's other two frame clauses on the same tool behave correctly

B's `frame.channels_unchanged` (`slack.channels`) and `frame.channel_inbox_unchanged`
(`slack.channel_inbox`) both grade `CONFORMS=5, VIOLATES=0` (`report/agreement_summary.md`,
"Segmentation differences" under `agentdojo:invite_user_to_slack`). Neither of those paths names a
collection the tool is advertised to grow, and neither collides with the pre/post-union matching
rule. This confirms the checker mechanism is working correctly in general, and that the VIOLATES
result is isolated specifically to the one frame path whose matched collection the tool's own
advertised effect necessarily extends — the signature of an unsatisfiable-by-construction path,
not a real signal.

### 7. Same gap as the one already on record

`spec/PREDICATE-GRAMMAR.md` §5 and `spec/GRAMMAR-GAPS.md`'s first entry record the identical shape
of gap for `state.reservations.*` in the `cancel_reservation` worked example: a frame path over a
collection the tool is advertised to change collides with the tool's own advertised effect on that
same collection, because "the frame-path grammar has no way to reference 'all entries except the
one this call is documented to add.'" `invite_user_to_slack`'s `slack.users.[]` differs only in
surface form (a list index appended to, rather than a dict key mutated in place) — mechanically it
is the same missing-exclusion-segment problem, on the append side rather than the update side.

## Disposition

- **Not added to `FINDINGS-VERIFIED.md`.** This is not a candidate finding about AgentDojo's
  implementation; it is a false-positive artifact of a frame path's scoping, produced by a checker
  mechanism (the pre/post union in `_frame_concrete_paths`) that is itself correct and documented.
- **Recorded in `spec/GRAMMAR-GAPS.md`** as the second instance of the frame-grammar exclusion gap
  (see diff below).
- **No headline count changes.** No clause here is or becomes a finding; AgentDojo's existing
  headline-eligible Ignored Argument cell (Finding 8, `arg.user_email`, `AGENT_VISIBLE` per
  `spec/GRAMMAR-GAPS.md`'s 2026-08-26 amendment) is unaffected, and this item was never eligible to
  add an AgentDojo cell in the first place since (b) is the determination.
- **`paper/main.md` not touched**, per the standing constraint (another pass is editing it) — this
  item does not require a paper change; if the exclusion-gap discussion in the paper cites only the
  `cancel_reservation` instance, the author may wish to note there are now two independently
  authored instances of the same gap, but that is an editorial call for the pass already in
  progress, not made here.

## Reproduction

```bash
cd "C:/Users/rohit/Documents/Research Papers/ResearchPaper20-ToolContractConformance"
python -c "
from core.frame import match_paths
pre  = {'slack': {'users': ['alice', 'bob'], 'channels': [], 'user_channels': {'alice': [], 'bob': []}, 'user_inbox': {'alice': [], 'bob': []}, 'channel_inbox': {}}}
post = {'slack': {'users': ['alice', 'bob', 'carol'], 'channels': [], 'user_channels': {'alice': [], 'bob': [], 'carol': []}, 'user_inbox': {'alice': [], 'bob': [], 'carol': []}, 'channel_inbox': {}}}
pre_paths  = set(match_paths('slack.users.[]', pre,  require_match=False))
post_paths = set(match_paths('slack.users.[]', post, require_match=False))
only_in_post = post_paths - pre_paths
print('pre paths:', sorted(pre_paths))
print('post paths:', sorted(post_paths))
print('paths present only in post (never resolve in pre -> _MISSING -> always \"changed\"):', sorted(only_in_post))
"
```

Expected output: `paths present only in post` contains exactly one path, `('slack', 'users', 2)` —
the index the append created — for any `pre`/`post` pair that differs by exactly one appended
user, confirming the mechanism is general and not dependent on the specific probe values used in
the dual-annotation run.
