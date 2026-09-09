# Zichong Wang's comments on the Overleaf draft

Collected 2026-09-09 from the Overleaf project, where they are inline `\zichong{}`
macros. Reproduced verbatim. Overleaf itself was not modified.

Five comments. All are about the argument rather than the prose, and three of them
attack the same underlying problem: the paper claims more than its evidence licenses.

---

## C1. The opening describes two different evaluation designs as one

> The opening does not consistently describe what the targeted benchmarks measure. It
> initially states that a benchmark scores an agent by executing tool calls and reading
> the resulting state. However, the main example concerns an evaluator that examines the
> agent's transcript rather than the resulting persistent state. This shifts the argument
> between two different evaluation designs and makes the claim about an assumption
> underlying every leaderboard position too broad.

**Location.** Abstract and Introduction paragraph 1.

---

## C2. MedAgentBench's missing writes may be a documented choice, not a defect

> The MedAgentBench example creates a problem for the introduction's distinction between
> disclosed simplifications and implementation defects. The original MedAgentBench paper
> explicitly describes executing only GET requests, checking POST payloads, and returning
> success responses without performing the corresponding writes. Therefore, the absence of
> writes is a documented evaluation choice. Presenting this behavior as the central example
> of an overlooked tool defect leaves the reader uncertain whether the paper is investigating
> implementation errors, limitations of deliberate simulation choices, or inconsistencies
> between advertised capabilities and evaluation scope.

**Location.** Introduction, MedAgentBench paragraph; Section V central chain.

**Why this one is existential.** The paper's own benign-simplification principle states that
a simplification is benign exactly when it is advertised. If the MedAgentBench paper
advertises that writes do not occur, then by our own criterion this is not a defect, and the
flagship finding collapses to a scope inconsistency rather than an implementation error.

**Must be verified against the MedAgentBench paper directly before any rewrite.**

---

## C3. The certainty of the consequence claims exceeds what score-at-risk supports

> The introduction uses different levels of certainty when discussing consequences for
> benchmark scores. The first contribution concerns score-at-risk, which indicates potential
> exposure. Elsewhere, the text states that the loss is not hypothetical, that defects
> propagate into every downstream use, and that they replicate on every rerun. A persistent
> implementation defect does not necessarily affect every execution or change every dependent
> verdict. These formulations make the claimed consequence stronger than the more limited
> concept of score-at-risk introduced in the contribution list.

**Location.** Introduction, data-quality paragraph and the "not hypothetical" sentence.

---

## C4. The description of prior work is too categorical

> The description of prior work is too categorical. Statements such as all stop one layer
> above the tool body, None of them tests, and no single-layer audit sees a defect imply a
> general limitation across the cited methods.

**Location.** Introduction paragraph 2; Figure 1 caption.

**Note.** This is the same fault the co-author raised in the first review round, when he asked
for "most" rather than "all" unless every case had been checked. It was fixed in the abstract
and in several other places, and these three instances survived.

---

## C5. The central contribution is not stable across the introduction

> The central contribution becomes less clear as the introduction progresses. The motivation
> emphasizes overlooked tool implementation defects, the contribution list places dependency
> analysis first, and the final paragraph emphasizes confirmation of findings that were mostly
> discovered manually. These are related activities, but they imply different primary
> objectives. The closing statements about what the checker did not discover and which
> techniques the authors did not invent further shift attention away from the paper's positive
> scientific claim and toward anticipated objections.

**Location.** Introduction: motivation, contribution list, and closing paragraph.

**Note.** The closing paragraph he objects to was added deliberately, in response to an earlier
internal review that wanted the discovery-versus-confirmation distinction surfaced early. His
point is that honesty placed in the introduction reads as defensiveness and displaces the
positive claim. Both concerns are legitimate; the disclosure belongs where it does not compete
with the contribution.
