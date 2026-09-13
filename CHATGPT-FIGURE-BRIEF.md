# Brief to paste into ChatGPT for figure ideas

Paste everything below the line. Attach the two rendered figure images if you can; the text
stands on its own if you cannot.

---

I am submitting a 10-page IEEE conference paper and want ideas for its figures. I need concrete,
implementable concepts, not general advice. Please push back if a figure is doing the wrong job.

## The paper in one paragraph

Agent benchmarks score a language model by executing its tool calls against a simulated
environment and grading what those calls report having done. That grade assumes each tool did
what its interface advertised. We treat each tool's advertised surfaces (docstring, JSON schema,
prompt template, return string) as an executable contract, check the implementation and its state
transitions against that contract, and then trace which task verdicts could have been computed on
state a defective tool should have written. Across 34 mutating tools in four shipped benchmarks we
confirm eight defect instances at pinned commits.

The flagship example: a clinical benchmark's write path parses the request payload into a local
variable, never reads it again, performs no database write, and returns to the agent the string
"POST request accepted and executed successfully". Its grader then reconstructs what was written
from the conversation transcript, gated on that same string. So its published "action success
rate" records whether a request was well formed, not whether any clinical record changed.

Honest weak results we report and do not hide: checker recall is 0.000 to 0.359; the
real-benchmark escape rate has a zero denominator; the replay experiment flips zero verdicts.

## Venue and hard constraints

- IEEE two-column conference format, exactly 10 pages including references, no appendix.
- Figures must be vector (we author in TikZ/PGF). No raster images, no photographs, no clipart.
- A figure spans one column (about 88mm) unless it earns `figure*` across both.
- The paper is at exactly 10 pages with zero slack. Any new figure must name what it displaces.
- Single-blind review, data-mining audience rather than software-testing specialists.
- Print may be greyscale, so colour cannot be the only channel carrying meaning.

## Figure 1 as it stands (page 1)

A left-to-right flow. "Agent issues a write" splits into two boxes: an upper blue box "WHAT THE
AGENT IS TOLD" containing the success string, and a lower grey box "WHAT THE RECORD DOES" reading
"payload parsed into a local, never read; no write occurs". The upper box feeds a blue "GRADER
reads the message" box, which feeds a green "SCORE counts a success" box. A dashed red arrow runs
from the grey box to the score, crossed out, labelled "the grader never reads the state". A note
above says the audits we survey read the blue boxes.

Caption: one write seen three ways at once; the agent is told it executed, no record changes, and
the grader scores the message rather than the state.

## Figure 2 as it stands (page 4)

Three boxes across the top: A. CONTRACT (authored from the tool's own advertised surfaces), B.
CHECKER (static scan proposes sites; dynamic run snapshots state around each call), C.
SCORE-AT-RISK (defect to field, field to evaluator, evaluator to the tasks it scores). A green
VALIDATION box below B, joined by a dashed arrow, reading "injected defects give precision and
recall; replay gives verdict impact".

## What I want from you

1. Is Figure 1 the right page-one figure for this paper, or is there a stronger concept? It has to
   make a reader who is deciding whether to keep reading understand the defect in about five
   seconds.
2. Figure 2 is a generic three-box pipeline. Most method overviews look like this and most are
   skipped. What would make it worth its space, or should it be cut for something else?
3. Is there a third figure this paper is missing that would carry an argument prose cannot? Bear
   in mind we have tables already for: per-benchmark totals, the six defect classes, the eight
   confirmed findings with quoted evidence, score-at-risk per defect, and recall per mutation
   operator.
4. For each idea: say what it shows, why a reader cares, roughly how to lay it out, and what it
   would displace. Tell me if an idea cannot work in one column or in greyscale.

Do not suggest photographs, icons, mascots, or anything decorative. Every mark should carry
information.
