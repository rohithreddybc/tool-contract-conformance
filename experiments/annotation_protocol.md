# Annotation Protocol

Committed before any clause is dual-annotated. Repairs W3 of the methodology review, which found the agreement study unspecified in every dimension that produced a prior low-kappa rejection.

The protocol's contents are the commitment, not its existence. Nothing below may be decided after seeing annotation results.

---

## 1. What is measured, and why not agreement-on-meaning

Judged semantic agreement between two predicate texts requires a rater to decide whether two expressions are logically equivalent — a judgment call about a judgment call. That is the mechanism behind the earlier low-kappa-plus-post-hoc-rule failure, and it would be self-inflicted here, because this project's predicates are *executable*.

**Primary measure: extensional agreement.** Both annotators' predicates are compiled and evaluated against a shared probe corpus. Agreement is reported at the verdict level, per clause. Two predicates that differ textually but return the same verdict on every probe agree; two that read alike but diverge on a probe do not.

**Headline robustness number:** does any VIOLATES finding change under the second annotator's contracts? The sentence the paper needs is *no reported finding depends on which annotator wrote the predicate* — or, if one does, exactly which and how.

Textual agreement is not reported as a primary result. Where the two annotators' predicates differ extensionally, the disagreement is adjudicated (§6) and the case is described qualitatively.

## 2. The annotation unit

A **clause** is one entry under `preconditions`, `effects`, `frame`, or `invariants` in a contract file. Segmentation is fixed by this rule, applied in order:

1. One clause per advertised-surface sentence that asserts a checkable property. A sentence asserting two independent properties ("checks the line is Active, and that the customer owns the line") yields two clauses.
2. A sentence that asserts a property over a collection yields one clause with a bounded comprehension, not one clause per element.
3. Prose that is not checkable — restatements of the argument list, "Returns: the updated reservation" — yields no clause and is recorded as uncovered in the coverage metric.

**Unit reconciliation.** `spec/coverage.py` reports the fraction of *advertised-surface sentences* operationalized. That denominator and this protocol's clause unit are related by rule 1: a sentence maps to zero, one, or several clauses. Both numbers are reported and the mapping is emitted per tool, so the two units cannot silently diverge.

## 3. Who annotates

Annotator A: the first author. Annotator B: to be named before annotation begins, and the paper states whether B is the co-author. If B is the co-author, the paper says "second annotator" and not "independent annotator" — the claim is agreement between two authors, which is what it will be.

The independent-contract arm described in `ARCHITECTURE-FINAL.md` §5 is a **different** exercise from this one and its tool source must be stated. If the independent person re-authors already-contracted tools, that is extensional dual annotation and merges into this protocol. If contracts come from the toy domain, the external-validity claim is weaker and is labelled as such. Whichever holds, it is written down before the work starts.

## 4. Blinding, and the contamination that cannot be removed

Both annotators know the four verified findings. Agreement on the tools carrying those findings is therefore contaminated upward and **is reported separately from agreement on the remaining tools**. No pooled agreement number is reported across the two strata.

Annotator B does not see Annotator A's contracts before writing their own. B works from the tool source and the advertised surfaces alone. This is enforceable and is enforced; it is the only blinding available.

## 5. Sampling frame

| Stratum | Coverage | Reason |
|---|---|---|
| Tools carrying a confirmed finding | **100%** of clauses | These clauses carry the paper's findings; a wide interval on them is useless |
| All other in-scope mutating tools | A stated fraction, minimum 30% of clauses, drawn by seeded random selection over the clause list | Gross-instability screen |

The seed and the selection script are committed with this protocol. The 20% figure in the earlier draft was withdrawn: at roughly 100-150 clauses it yields 20-30 items, and any agreement coefficient on that n carries an interval too wide to defend. For the sampled stratum the exact interval is reported and the number is described as a screen, not an estimate.

## 6. Probe corpus and adjudication

**Probe corpus.** The shared corpus is (i) every probe in the pre-committed mutation probe corpus (see `detector_analysis_plan.md` §2) plus (ii) every recorded real call to the tool captured during adapter smoke-testing. Committed before annotation.

**Verdict-level comparison.** For each clause and each probe, both compiled predicates are evaluated. Outcomes are CONFORMS / VIOLATES / UNTESTABLE, and UNTESTABLE-vs-anything counts as a disagreement, never as a skip.

**Adjudication.** Every extensional disagreement is resolved by returning to the advertised surface, not by discussion of the predicates. The adjudication record states, per disagreement: the clause, the probe that separated them, which reading the surface supports, and whether either predicate was wrong or the surface is genuinely ambiguous. Surface ambiguity is a reportable finding about the benchmark's interface, not a nuisance to be resolved away.

**Post-adjudication contracts** are what ship. The agreement numbers reported are pre-adjudication.

## 7. The annotator checklist

Applied by both annotators to every clause:

1. Does the provenance quote appear verbatim at the cited file and line?
2. Is the surface agent-visible, maintainer-annotated, or absent? A `logger.*` call, a comment, or a TODO is **maintainer-annotated**, never `tool_return`. Validator check 8 enforces this; the checklist exists so it is not discovered at CI time.
3. Does the predicate assert what the `text` claims, no more and no less? `inv.seat_conservation` in the worked example is the standing counterexample — its text describes a capacity equation and its predicate asserts only non-negativity.
4. Iteration semantics: `for x in <path>` binds mapping **keys**, following Python. If values are meant, write `<path>[x]`.
5. Are all names bound? Comprehensions require explicit binders.
6. Does any frame path match nothing, or match the very key an effect clause is advertised to change?
7. Is `biconditional: true` justified by a cited surface, and is any deferred effect annotated?

## 8. What is reported

- Extensional agreement per stratum, with exact intervals, never pooled across strata.
- The headline robustness sentence from §1.
- Count and nature of adjudicated disagreements, split into predicate error and surface ambiguity.
- Coverage metric alongside agreement, per `ARCHITECTURE-FINAL.md` §5 — high agreement on shallow contracts is not evidence of anything, and the two numbers must be read together.
- Whether B is the co-author.
