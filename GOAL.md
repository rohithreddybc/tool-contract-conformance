# Standing goal

Get this paper submitted in the strongest honest form it can take, to the venue
that gives it the best chance, without claiming anything the evidence does not
support.

## What that means in practice

**Every claim traceable.** No sentence about another system, another paper, or our
own results survives unless it can be checked against a primary source at a pinned
commit. When a claim fails that test, correct it in print rather than hedging it.

**Weak results stated, not hidden or dressed up.** Recall is low, the open-world arm
has no usable real-benchmark number, no verdict flips. These are the true results.
Report them once, in the results section, with their causes. Do not repeat them under
a Threats heading where a reviewer will mine them, and do not soften them.

**Reads like something worth reading.** Venue register, but a person wrote it. No
verdict-label openings, no formulaic transitions, no bolded full sentences, no em
dashes. Interesting wherever it reports a finding; short wherever it explains
procedure.

**Fits the venue it is actually going to.** Conventions derived from what the venue
publishes, not assumed. Keywords in the venue's own vocabulary.

**Co-authors' input answered, not absorbed.** Zichong Wang's five comments stay in the
source verbatim with a reply beside each. Where a reply would overstate what changed,
say the smaller true thing. Where a co-author asks for something the venue sample
contradicts, raise it rather than silently picking one.

## Hard constraints

- Exactly 10 pages. Template spacing is never altered to gain room. Anything added
  names what it displaces.
- `numbers_audit.py` exits 0 before any commit touching `paper/`.
- Zero em dashes in `main.tex`.
- The ten limitations, eight findings rows, disposal rows and taxonomy table stay.
- Findings confirmed by hand before entering the paper. A false claim about someone
  else's code is worse than a weak paper.

## Open, needing the author

| Item | By |
|---|---|
| Venue: IDM special session (Sep 27) or SE4AgenticAI (Oct 10). Notifications do not overlap, so this is a choice, not a fallback | before Sep 27 |
| Wenbin Zhang's agreement if the venue changes, since the data-mining shape was his request | before switching |
| Zichong Wang's affiliation, currently a placeholder in the author block | before submission |
| The two back-matter placeholders: AI-use statement, coordinated disclosure | disclosure needs the responses |
| Eleven Scopus venue confirmations for the bibliography | before submission |
| One email to Paulo Alencar: is SE4AgenticAI single or double blind, and did last year's papers reach Xplore | only if switching |

## Settled, not to be relitigated

- No verdict flip is demonstrable. No shipped task composes a suspended line with a
  refuel, and choosing tasks that would flip means choosing after seeing which flip.
- The recorded-calls corpus will not improve recall. It feeds the open-world arm, the
  miss diagnostic and the agreement study; the checker's prober is separate.
- No third refreeze cycle, no fifth benchmark.
- MedAgentBench's no-write design is documented in its own paper. The defect rests on
  the agent-visible success string, not the missing write.
