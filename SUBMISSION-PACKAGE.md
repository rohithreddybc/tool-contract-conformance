# Submission Package — paste-and-click drafts

Prepared 2026-09-11. Nothing here has been filed, posted, or edited into `paper/latex/main.tex`
or `paper/main.md`. These are drafts for a human to review and send.

## Flag before you paste anything

**`report/disclosure_log.md` currently states, as fact, that all four findings were "sent to the
four maintainer teams on 2026-09-10."** Your task brief for this package says the opposite —
"Nothing has been filed" — and `paper/latex/main.tex`'s own Conclusion paragraph agrees with the
brief: it describes disclosure in the future tense ("All findings go to the four maintainer teams
before submission"), not the past tense the log uses. So the log is ahead of reality: it reads
like a record of a completed action that has not happened yet. Two things follow:

1. Don't treat the "pending" response status in that table as evidence anything is in flight —
   no issue exists yet for any of the four repos, as far as I can verify from this repository.
2. Once you actually post the four issues below, `report/disclosure_log.md`'s "sent... on
   2026-09-10" line needs correcting to the real filing date, or a reviewer who checks GitHub
   against the log will find a discrepancy in the artifact itself. That edit is yours to make (it
   is not `paper/latex/main.tex` or `paper/main.md`, so it is outside this task's do-not-edit
   list) — I have not touched it.

Everything below assumes you are filing these for the first time.

---

# PART 1 — Four disclosure issues, ready to paste

Each is written as one engineer telling another something they noticed, not as an audit verdict.
None of the paper's taxonomy names (Ignored Argument, Phantom Effect, Partial Effect, Unenforced
Precondition, etc.) or headline counts appear below — a maintainer has no reason to care what we
call the category, only what the code does and what the interface promises. Each issue also states
the disclosure/response commitment from `report/disclosure_log.md` in plain language, and each
says explicitly that a documentation fix would resolve the finding as completely as a code change
would — that is our own project's stated position, not a courtesy line.

## Issue 1 of 4 — `github.com/stanfordmlgroup/MedAgentBench`

**Title:** POST tool response and the write-task grader both key off transcript text, not FHIR
server state

**Body:**

```
Hi — we've been running a study on how agent-benchmark tool interfaces communicate outcomes to
the agent, and MedAgentBench turned up something specific we wanted to bring to you directly
rather than let it surface first in a paper.

First, the part that isn't news to you: Sections 2.4 and 2.4.3 of the MedAgentBench paper
already explain that POST requests aren't forwarded to the FHIR server — you note the ~90s
environment reinitialization cost and instead run a JSON-loadable sanity check and report
success. That's a reasonable, documented engineering trade-off, and it isn't what this issue is
about.

What we noticed is narrower and sits one layer down, in what the agent itself is told.
`src/server/tasks/medagentbench/__init__.py`, lines 85-91 at commit `9926011`:

    elif r.startswith('POST'):
        try:
            payload = json.loads('\n'.join(r.split('\n')[1:]))
        except Exception as e:
            session.inject({"role": "user", "content": "Invalid POST request"})
        else:
            session.inject({"role": "user", "content": "POST request accepted and executed
                successfully. Please call FINISH if you have got answers for all the questions
                and finished all the requested tasks"})

`payload` is parsed and then never read again (it appears nowhere else in the file except inside
a prompt-template string). The string the agent actually receives — "accepted and executed
successfully" — is more definite than your paper's own paraphrase ("indicate success of
execution"), and nothing on the agent's side (the Appendix A.2 prompt template, the tool schema)
qualifies it. An agent has no way to tell this response apart from a genuine FHIR
acknowledgment.

Second, and we think this is the part worth your attention regardless of what happens to the
first: we obtained `refsol.py` (per the Box link in README.md) and read the write-task grading
path. `extract_posts` reconstructs "what was written" from the conversation transcript itself,
gated on the literal string "POST request accepted" — the same string above:

    def extract_posts(results):
        posts = []
        for idx, i in enumerate(results.history):
            if (i.role == 'agent') and ('POST' in i.content):
                if (idx<len(results.history)) and ("POST request accepted" in results.history[idx+1].content):
                    ...
                    posts.append((url, payload))

`task3` and `task8` then grade entirely off that reconstructed payload — no FHIR read occurs
anywhere in either function. `task5`, `task9`, and `task10` read FHIR state, but only to decide
*whether* a write is expected, then grade the write itself the same transcript-text way. So for
at least `task3` and `task8` (60 of 300 cases), the recorded score reflects whether the agent
emitted a well-formed POST string, not whether any clinical record changed — and it's
mechanically consistent for it to stay that way even if the underlying write behavior changes,
since nothing downstream ever looks at the FHIR server.

We'd flag that a documentation change resolves this just as completely as a code change would —
whichever is cheaper on your end:

  - Return a string that doesn't claim execution, e.g. "payload validated (not forwarded to
    FHIR)" — this alone removes the ambiguity for the agent.
  - Or, if the response string stays as-is, a one-line note in the README or the paper that
    task3/task8 scores measure request well-formedness rather than a verified write, since
    `refsol.py`'s `extract_posts` is keyed on that exact string.

Reproduce:

    git clone https://github.com/stanfordmlgroup/MedAgentBench.git && cd MedAgentBench
    git show 9926011:src/server/tasks/medagentbench/__init__.py | sed -n '85,91p'
    git grep send_post_request 9926011 ; echo "exit=$? (1 = no matches)"
    # refsol.py is obtained separately per README.md's Box link:
    sed -n '4,16p;62,83p' refsol.py

We're preparing a paper describing tool-interface/grader interactions like this one across
several agent benchmarks, and expect to submit it around 2026-09-27. If you're able to respond
before then, we'll report your response's substance alongside this finding; if we don't hear
back, we'll record that neutrally, with no inference drawn from silence either way. If you think
we've mischaracterized anything above, please say so — we'll mark it contested and include your
reasoning rather than our own.

Thanks for MedAgentBench — happy to share more detail on any of the above if useful.
```

---

## Issue 2 of 4 — `github.com/sierra-research/tau2-bench`

**Title:** Two telecom/airline tool bodies don't enforce what their docstrings promise, plus a
question about `suspend_line`'s `reason` argument

**Body:**

```
Hi — flagging three things we noticed while reading through the telecom and airline tool
implementations, in decreasing order of confidence. All three are read-only observations from
the source; nothing here required running the environment.

1. `refuel_data` doesn't enforce the precondition its own docstring states.

`src/tau2/domains/telecom/tools.py`, lines 607-647 at commit `c3398666`:

    @is_tool(ToolType.WRITE)
    def refuel_data(
        self, customer_id: str, line_id: str, gb_amount: float
    ) -> Dict[str, Any]:
        """
        Refuels data for a specific line, adding to the customer's bill.
        Checks: Line status must be Active, Customer owns the line.
        ...
        """
        target_line = self._get_target_line(customer_id, line_id)

        # if target_line.status != LineStatus.ACTIVE:
        #     raise ValueError("Line must be active to refuel data")

        if gb_amount <= 0:
            raise ValueError("Refuel amount must be positive")
        ...
        charge_amount = gb_amount * plan.data_refueling_price_per_gb
        target_line.data_refueling_gb += gb_amount
        self._apply_one_time_charge(customer_id, charge_amount, ...)

The docstring's "Checks:" line and its "Raises:" section both describe an Active-line check.
The `gb_amount > 0` check right below it is live, so this looks like one specific check that
got commented out rather than validation being absent generally — possibly during a refactor.
A suspended or closed line can currently be refuelled and billed.

Reproduce:

    git clone https://github.com/sierra-research/tau2-bench.git && cd tau2-bench
    git show c3398666:src/tau2/domains/telecom/tools.py | sed -n '607,657p'

A one-line uncomment restores the check; alternatively, if the Active-line requirement is no
longer intended, updating the docstring's "Checks:" and "Raises:" lines resolves it just as
completely on our end — either way the interface and the body would agree again.

2. Cancelling a reservation doesn't release the seats booking reserved — and you already know
   it, in two places.

`src/tau2/domains/airline/tools.py`. Booking decrements inventory (line 315):

    flight_date_data.available_seats[cabin] -= len(passengers)

Cancellation refunds and marks the reservation cancelled, but logs the gap itself
(lines 363-368):

    reservation.payment_history.extend(refunds)
    reservation.status = "cancelled"
    ...
    # Release seats
    logger.warning("Seats release not implemented for cancellation!!!")
    return reservation

and the flight-change path has a maintainer TODO connecting the same gap back to cancellation
(line 689):

    # Do not make flight database update here, assume it takes time to be updated
    # TODO: So this means that we don't update the seats here. What about in cancel_reservation?

So this isn't news to whoever wrote that `logger.warning` — we're mostly surfacing that it's
still open and that we traced its blast radius: `available_seats` only drifts within a single
simulation episode, since `runner/build.py` reloads `FlightDB` from disk per simulation
(`build_environment` -> `FlightDB.load(AIRLINE_DB_PATH)`), so this doesn't compound across
episodes. Book-then-cancel within one episode still leaves seat counts lower than they should
be, which matters for any task in that episode that reasons about remaining capacity.

Reproduce:

    git show c3398666:src/tau2/domains/airline/tools.py | sed -n '313,318p;363,368p;685,690p'

Implementing the release at the point already flagged (line 367) closes this; short of that,
the existing `logger.warning` already documents it for a human reader, and moving that same
sentence into the docstring's own text would make it visible on the surface the agent
(indirectly, via any tooling built on the docstring) and future contributors both read.

3. A question, not a finding: `suspend_line`'s `reason: str` parameter (telecom/tools.py,
   lines 261-295) is required, documented as "Reason for suspension," and used only in a log
   line (`logger.info(f"Line {line_id} suspended. Reason: {reason}")`) — it's never persisted
   on the `Line` object or returned. We genuinely don't know whether "for the audit log" was
   always the intended full scope of this parameter, in which case there's nothing to fix, or
   whether it was meant to end up somewhere queryable. We'd appreciate knowing which, and we'll
   report whichever answer you give rather than guess.

We're preparing a paper describing patterns like these across several agent benchmarks, aiming
to submit around 2026-09-27. Any response you send before then, we'll report with its substance;
no response gets recorded neutrally with no inference drawn; anything you think we got wrong
we'll mark contested with your reasoning attached rather than ours.

Really enjoyed working with tau2-bench's codebase — it's some of the more readable environment
code we've gone through, which is exactly how we noticed the commented-out line in (1) as an
outlier rather than a pattern.
```

---

## Issue 3 of 4 — `github.com/ethz-spylab/agentdojo`

**Title:** Three tool interfaces (banking, car rental, Slack invite) promise more than their
bodies currently deliver

**Body:**

```
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
```

---

## Issue 4 of 4 — MM-ToolSandbox

> **This one cannot be filed as a GitHub issue.** Checked 2026-09-12: `apple/ml-tool-sandbox`
> is a 404. The real repository is `apple/ml-mmtoolsandbox`, which redirects to
> `apple-aiml-research/ml-mmtoolsandbox`, and that repository has issues and discussions
> both disabled. Forking is allowed, so a pull request against `main` is the remaining
> in-repo channel; otherwise reach the authors through arXiv 2607.11818. The body below
> works as a pull-request description or an email with no change beyond the greeting.

**Title:** `venmo_social`'s `sort_by` parameter is documented twice but never forwarded to the
comment-list call

**Body:**

```
Hi — small, specific one from `venmo_social`'s comment/list branch.

`mmtoolsandbox/tools/mini/venmo.py`, commit `1e8e9324abcb741cc6a9718f9e7c1b80e85a1363`.
`sort_by` is declared in the signature (L370: `sort_by: str | None | NotGiven = NOT_GIVEN`) and
documented twice in the function's own docstring — once in the parameter summary (L388,
"Optional: page_index, page_limit, sort_by.") and once with its intended semantics (L405,
"sort_by: Sort attribute with +/- prefix (for comment list)."). The `list` branch that docstring
is describing, though, never forwards it:

    elif action == "list":
        kwargs = {"transaction_id": transaction_id}
        if page_index is not NOT_GIVEN:
            kwargs["page_index"] = page_index
        if page_limit is not NOT_GIVEN:
            kwargs["page_limit"] = page_limit
        return _get("venmo_show_transaction_comments")(**kwargs)

`page_index` and `page_limit` — the two parameters `sort_by` is listed alongside in the
docstring — are both forwarded correctly; `sort_by` just isn't added to `kwargs` anywhere in
this branch. A caller that passes `sort_by` to order a comment listing gets back an unordered
list with no signal that the argument was dropped.

The fix looks mechanical and there's already a working example of it 250 lines up, in
`venmo_transact` (L216-217):

    if sort_by is not NOT_GIVEN:
        kwargs["sort_by"] = sort_by

Adding the same three lines to the `list` branch would bring it in line with both its own
docstring and the pattern already used elsewhere in the file.

Reproduce:

    git clone https://github.com/apple/ml-mmtoolsandbox
    git -C ml-mmtoolsandbox checkout 1e8e9324abcb741cc6a9718f9e7c1b80e85a1363
    sed -n '464,470p' ml-mmtoolsandbox/mmtoolsandbox/tools/mini/venmo.py
    grep -n "sort_by" ml-mmtoolsandbox/mmtoolsandbox/tools/mini/venmo.py

One scope note, in the interest of not overclaiming: we understand the downstream AppWorld
integration wraps some of these tools, and we were not able to check whether `sort_by` survives
that far, since we hit an LFS quota error cloning AppWorld at the time we looked. Everything
above is scoped to this repository's own code, which is where the gap between the docstring and
the forwarded kwargs already exists regardless of what happens downstream. If a documentation
correction (dropping `sort_by` from the docstring, if forwarding it isn't planned) is easier than
wiring it through, that resolves this from our side just as completely as the three-line fix
above would.

We're preparing a paper describing gaps like this one across several agent-tool benchmarks and
expect to submit around 2026-09-27. A response before then gets reported with its substance; no
response gets recorded neutrally, with nothing inferred from silence; anything you dispute we'll
mark contested and include your reasoning.

Thanks for open-sourcing ml-mmtoolsandbox — happy to send over the small script we used to walk
the docstring-vs-forwarded-kwargs pattern across the other `mini/` tools if it's useful to you.
```

---

# PART 2 — arXiv submission package

## Venue facts, read off the conference site on 2026-09-12

Verified against the pages themselves rather than recalled. The main call and the special
session do not share a deadline, which is the fact most likely to cause a bad surprise.

| Item | Value | Source |
|---|---|---|
| Full paper deadline | **Sept 27, 2026, 11:59 pm PST** | IDM special session page |
| Main-track deadline (does not apply to us) | Aug 21, 2026, already passed | main call for papers |
| Notification | Nov 1, 2026 | IDM special session page |
| Camera-ready and pre-registration | Nov 14, 2026, 11:59 pm PST | IDM special session page |
| Conference | Dec 14-17, 2026, Phoenix AZ | IDM special session page |
| Page limit | "Papers must not exceed 10 pages, including references." No appendices. | main call for papers |
| Format | IEEE Computer Society Proceedings Manuscript Formatting Guidelines, two-column | main call for papers |
| Review policy | **Single-blind.** Author names and affiliations stay in the PDF. | main call for papers |
| Submission portal | `https://wi-lab.com/cyberchair/2026/bigdata26/index.php` | main call for papers |
| Session organizer | Asst. Prof. Dr. Uraz Yavanoglu, Gazi University | IDM special session page |

Pages: <https://bigdataieee.org/BigData2026/calls/special-data-mining/> and
<https://bigdataieee.org/BigData2026/calls/papers/>.

**Required statements: none.** The call names no ethics, data-availability, AI-use or funding
statement as mandatory. Our AI-use paragraph and coordinated-disclosure paragraph are therefore
voluntary, and keeping them is a choice rather than a compliance step. This resolves the comment
in `paper/latex/main.tex` asking whoever submits to recheck the portal's required fields.

**Single-blind matters for one open item.** Author names ship in the PDF, so the placeholder
affiliation in the author block is a blocker rather than a cosmetic gap.

**On topic fit, stated plainly.** The session's topic list runs from graph mining and clustering
through LLMs, autonomous systems and knowledge discovery. It names nothing about benchmark
quality, evaluation methodology or reproducibility, and it does not name data quality either.
The paper's anchors into that list are LLMs and autonomous systems. This is the same gap
`REVIEW-RESPONSE.md` recorded when the data-quality framing was added, and it is the structural
reason two reviewers on the September panel flagged venue fit.

## Title

```
Do Agent Benchmarks Do What They Say? An Executable-Contract Audit of Tool-Using Agent Environments
```

Exactly as in `paper/latex/main.tex`'s `\title{...\\\large ...}` (the two lines are the title and
its subtitle; arXiv has one title field, so join them with a colon or leave the `?`-then-subtitle
run-on as above — either reads fine as a single field).

## Authors and affiliations

| Author | Affiliation |
|---|---|
| Rohith Reddy | Florida International University, Miami, FL, USA |
| Zichong Wang | Florida International University, Miami, FL, USA |
| Wenbin Zhang | Florida International University, Miami, FL, USA |

**Note on Zichong Wang's affiliation:** `main.tex` already lists FIU (an earlier working note,
`CHECKPOINT-2026-09-10.md`, still shows `AFFILIATION TO CONFIRM` as an open item — that note is
now stale against the committed source). Independently of the source file, Zichong Wang's FIU
affiliation is corroborated by the FairGEM paper at NeurIPS 2025, which lists the same
affiliation for the same name — so this is confirmed from a second, external source, not just
carried over from our own draft. Worth a last look at the FairGEM paper's exact department/lab
line in case arXiv's affiliation field wants more granularity than "Florida International
University."

## Abstract (plain text, LaTeX stripped, for arXiv's abstract box)

1522 characters, against arXiv's 1,920-character limit. Regenerated from
paper/latex/main.tex; re-run the generator if the abstract changes again.

```
Tool-using agents are entering settings where a wrong action carries real cost, and the
benchmarks certifying them execute each call in simulation and grade what the call reports,
assuming the tool did what its interface advertises. The audits we survey inspect tasks, gold
solutions, and graders, never that assumption. A benchmark score is a published data product,
and a defect beneath it is present on every rerun, so the exposure it creates travels with the
number into every reuse. We treat each tool's advertised surfaces as an executable contract,
check the implementation against it, and trace which task verdicts read state a defective tool
should have written. Across 34 mutating tools in four benchmarks we confirm eight defect
instances at pinned commits, one headline-eligible class in each, meaning one visible to the
agent. Against injected defects the checker raised no false positive in 25 flags pooled from toy
and real sites; its recall is low, and 29 of 33 misses trace to the probe corpus that drives the
tools, not the taxonomy. The clearest case is a clinical benchmark whose interface tells the
agent each write executed, under a no-write design its paper documents and its interface does
not. Its grader takes that message as evidence, so its action success rate records whether a
request was well formed, not whether any record changed. Two repairs follow: disclose a
simplification on the surface the agent reads, and ground a write grader in state rather than in
the tool's own success string.
```

## Categories

**Primary: `cs.SE` (Software Engineering).** The technical core is a contract specification
(preconditions, arguments, success signals, side effects) authored against advertised interface
surfaces, checked with a static and dynamic conformance checker, and traced through dependency
analysis — that is interface-conformance testing, a core SE topic, applied to a new artifact
class (agent-benchmark tool implementations) rather than to ordinary APIs. `cs.SE` readers are
also the audience most likely to reuse the checker methodology directly.

**Recommend cross-listing `cs.AI`.** The audited artifacts are LLM agent benchmarks (tau2-bench,
AgentDojo, MedAgentBench, MM-ToolSandbox), and the finding — that benchmark scores can rest on a
tool that silently doesn't do what it claims — is squarely relevant to the cs.AI agent-evaluation
community that consumes and cites these benchmarks' leaderboard numbers. This is the cross-list
most likely to reach the readers who'd want to know before citing a score from one of these four.

**Recommend cross-listing `cs.LG`.** The paper's own framing treats benchmark scores as "a
published data product the field mines and reuses in leaderboards and model-selection
decisions" — a measurement-validity claim about ML benchmarking practice, which is `cs.LG`'s
territory as much as `cs.AI`'s. Cross-listing both costs nothing and covers readers who watch one
list but not the other.

**Recommend against `cs.CL`.** Nothing in the contribution is a language-modeling or NLP-methods
result — the tools happen to be called by LLM agents, but the audit is of the tool's own
implementation, not of any model or language-processing technique. `cs.CL` cross-listing would
mostly add noise for that list's readers; skip it unless arXiv's moderators specifically ask for
it (some agent-benchmark papers do get routed there, but it's not this paper's center of mass).

## Comments field

```
10 pages. Submitted to IEEE BigData 2026, Intelligent Data Mining special session.
```

(Confirmed 10 pages from `paper/latex/main-submission.pdf`'s own page count; update this line if
a later revision changes the page count before you post.)

## License recommendation

**CC BY 4.0** for the arXiv posting itself. This is consistent with, and not the same decision
as, the artifact's own licensing: the code/checker repository is MIT (already stated in the
paper's Data Availability sentence, `main.tex` line ~432: "development history at
github.com/rohithreddybc/tool-contract-conformance (MIT license)"), and the Zenodo deposit uses
CC-BY. Posting the paper text itself under CC BY 4.0 on arXiv keeps all three artifacts
(paper, data/tables deposit, code) under maximally reusable, attribution-only terms, rather than
defaulting to arXiv's more restrictive standard non-exclusive license — worth the one extra
click in the submission form.

## Checklist — what to upload, and how

**Upload TeX source, not a PDF-only submission.** arXiv strongly prefers source for a paper like
this (full-text indexing, cross-referencing, and it lets arXiv typeset consistently); there is no
reason here to hide the source, and IEEE has no policy against posting the accepted LaTeX source
as a preprint.

Files to include in the source upload:

- `paper/latex/main.tex` — **but first regenerate it with `\reviewfalse`, which is already the
  setting checked into the repo, so no toggle change needed.** However, six `\zichong{...}` /
  `\response{...}` macro calls still carry their real text as raw source (invisible only at
  *render* time, not in the uploaded `.tex` file itself) — anyone who downloads the arXiv source
  package can open `main.tex` and read Zichong's inline review comments and your replies to them
  verbatim, since `\reviewfalse` only suppresses them in the compiled PDF. Decide deliberately
  whether that is fine (he is a co-author, and the comments are already his own words) or whether
  to strip those six macro calls into a clean copy before uploading — recommend stripping, since
  they read as an internal review thread and add nothing for an arXiv reader.
- `paper/latex/main.bbl` — the pre-generated bibliography. Uploading this (rather than
  `references.bib` alone) means arXiv's compile doesn't need to run BibTeX, which is the more
  reliable path. `references.bib` (539 lines) can be included alongside it for transparency, but
  is not required for the PDF to build correctly.
- No separate image files: both figures are native TikZ (`\begin{tikzpicture}`, 2 occurrences),
  so they compile from the `.tex` source directly — nothing to export or attach.
- No custom `.cls`/`.sty` files are used beyond standard packages already on arXiv's TeX Live
  (`IEEEtran`, `graphicx`, `amsmath`, `amssymb`, `booktabs`, `makecell`, `listings`, `xcolor`,
  `balance`, `url`, `tikz`, `hyperref`) — nothing extra to bundle.

**Do not upload** `paper/latex/main-review.pdf` (the reviewer-comments copy) or the two loose
`main-review.pdf` / `main-submission.pdf` files sitting untracked in `paper/latex/` right now —
confirm which one is the actual submission-quality build before this goes anywhere.

## What would be wrong to post now, and the timing recommendation

**Post-arXiv timing is a disclosure-ordering question, not just a paper-readiness one.** The
paper names four real repositories and quotes their source verbatim as evidence of a gap between
what each tool advertises and what it does. If the arXiv preprint goes up before the four GitHub
issues in Part 1 are actually filed, or before the maintainers have had any real window to see
them, the first these teams would hear about being named in a public preprint is the preprint
itself — which is the opposite of the coordinated-disclosure commitment `report/disclosure_log.md`
states and that this paper's own Conclusion paragraph promises the reader. Per the flag at the
top of this document, no issue currently appears to be filed despite the log's wording, so as of
today posting to arXiv would run ahead of disclosure entirely.

**Recommendation: file the four issues first, then post arXiv the same week as the IEEE BigData
submission (2026-09-27), not before.** This matches the schedule already recorded in
`ARCHITECTURE-FINAL.md` ("Sep 27: Submit, and in the same week post the arXiv preprint and the
Zenodo artifact, and link both from the disclosure issues opened on Sep 10") — the only
correction needed to that plan is the date the issues actually go up, given the Part-1 flag
above. Posting arXiv and the Zenodo deposit in the same week as submission, after disclosure, also
means the preprint can link the live GitHub issues (showing "disclosed, here's the thread") rather
than promising disclosure it hasn't done yet.

**Also worth resolving before posting, independent of timing:** `CHECKPOINT-2026-09-10.md` lists
several open items that would ideally be closed before a public, citable preprint goes up —
confirming `10.5281/zenodo.22182792` is the concept DOI (the record page currently shows the
release as `...793`, one below what's cited), and the eleven outstanding Scopus venue
confirmations for the bibliography. Neither blocks *this* package, but both are worth finishing
before the preprint is the version of record someone might cite.
