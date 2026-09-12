# The four review passes, and what each one found

Run 2026-09-12 over `paper/latex/main.tex`. Every finding below was checked in the file or against
upstream source, not accepted from a report.

## Zichong's comments: five, verbatim, each with a reply beside it

Verified mechanically by brace-matching the macros rather than by eye. `main.tex` holds five
`\zichong{}` calls, each followed immediately by a `\response{}`, and each comment's text matches
`ZICHONG-COMMENTS.md` word for word. The sixth match a naive grep reports is the macro definition
at line 87.

| # | His comment, in one line | Where it stands |
|---|---|---|
| C1 | Two evaluation designs conflated | Fixed. The class covers reading state or reading the returned result, so the example sits inside it |
| C2 | MedAgentBench's no-write design is documented in their paper | Conceded in print. The finding relocated onto the agent-visible success string and the grader keyed to it |
| C3 | Certainty exceeds the measure | Fixed. Presence and consequence separated; score-at-risk bounds exposure and says so |
| C4 | Prior-work claims too categorical | Fixed. Every claim scoped to the audits cited; the unsupported five-audits claim deleted |
| C5 | Centre of gravity moves to defence | Fixed. Defensive paragraph cut to one sentence, "what we did not invent" moved to related work |

C2 is a concession rather than a repair, and the reply says the smaller true thing rather than
claiming more changed than did.

## Pass 1, claim support: the pass that mattered

- **A false claim about tau2-bench's code**, in the passage defining the paper's own criterion. The
  paper said line 689 advertises a deferred update "where the agent can see it". It is a Python
  comment; the docstring never mentions the deferral. A knock-on sentence inherited the error.
  Both repaired. Detail in `SOURCE-CLAIMS-VERIFIED-2026-09-12.md`.
- Abstract overclaimed by saying the defect travels into every reuse; score-at-risk bounds
  exposure, not realised loss. Now matches the introduction's calibrated wording.
- "No prior tool-contract checker exists for these benchmarks" was an unbacked existence claim.
  Scoped to the work surveyed.
- The conclusion closed on "the layer nobody has been checking", an unbounded universal negative.
  Scoped.
- Nine claims about other systems re-read at their pinned commits. Eight hold; one was the failure
  above; one is sharper than stated.

## Pass 2, contribution salience

- The headline count of 34 mutating tools had no stated rule behind it. The rule is now in the
  scope paragraph, verified at the pinned commit.
- "Every in-scope tool is audited and none sampled" read as a census when the scope is three of
  tau2-bench's five registered domains. Now says which.
- The abstract ended on the sharpest finding without saying what follows. It now closes on the two
  repairs.
- Implementation detail about the Python interpreter and subprocess boundary cut from the setup,
  since nothing pointed back at it.

## Pass 3, venue fit and structure

Eighteen conventions checked against the exemplar and the session's call; all satisfied. Full
table and the honest residual in `VENUE-FIT-PASS-2026-09-12.md`.

- The two weakest numbers were stated twice, once in results and again under Threats where a
  reviewer mines them. The second copy is gone; the limitations and their pointers stay.

## Pass 4, internal coherence

- The metrics section stated a rule the abstract breaks, that toy-domain numbers never enter a
  headline, while the abstract reports pooled precision. The rule now names the quantity it
  governs.
- Related work opened on a prevalence claim the paper's own limitations forbid. Scoped.
- The findings ledger was discussed for a paragraph while being called "the table", its only
  reference two subsections away. Now referenced where it is discussed.
- A correction that had not propagated: Agent-Diff was fixed to a non-archival poster in one
  sentence and still called a preprint two paragraphs later.
- A clause shipped twice, found by reading the compiled page rather than the source.
- A sentence opened on four bare citation numbers; a run-in label had grown to seventeen words.
- 229 live mutants against a decomposition summing to 225, with the four detected never stated.
- "iCLR" lowercase in two references; four references printing as title plus bare year.
- FHIR used unexpanded at first occurrence before a data-mining audience.

## What is deliberately not fixed

- The experiments section opens straight onto a subsection with no orienting sentence. Prose after
  that heading moves a float and costs the page, tried at two lengths.
- Eighteen sentences remain over forty words, down from twenty-one. The rest are enumerations
  where the length is the list rather than the syntax.
