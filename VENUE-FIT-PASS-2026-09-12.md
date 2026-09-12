# Venue-fit pass against IEEE BigData 2026, Intelligent Data Mining

Run 2026-09-12 against the conventions measured from the exemplar Wang supplied (Wang,
Narasimhan, Yao, Zhang, IEEE ICDM 2023) and against the session's own call for papers, read on
the conference site the same day.

## Structural conventions: every item satisfied

| Convention | State |
|---|---|
| Six-section shape: Introduction, Related Work, Notations and Preliminaries, Method, Experiments, Conclusion | Exactly this, in this order |
| Abstract opens on impact, not method | "Tool-using agents are entering settings where a wrong action carries real cost" |
| Abstract carries no numbered procedure, no "must" | Neither present |
| Index Terms present, session vocabulary first | "large language models, autonomous agents, ..." |
| Introduction mirrors the abstract, four to six paragraphs | Six |
| Challenges named, three, bolded run-in labels, plain prose after each | Three, each tied to this work's angle rather than the field's |
| Contributions bulleted, three to five, ordered by importance | Three, findings first |
| Roadmap paragraph closing the introduction | Present, after the sentence naming what the paper establishes |
| Related work: two or three lettered subsections, three to five works each | Three, carrying 7, 16 and 25 citations |
| Background folded into Notations rather than standing alone | Folded |
| Method carries an overview figure | Fig. 2, stages matching the subsection order |
| Experiments: setup, baselines, metrics, implementation, results | All present; data availability inside the section, as the convention wants |
| Ablation or equivalent | The injected-defect validation arm, which is the documented analogue for an audit paper |
| Conclusion one paragraph | One |
| Page limit including references, no appendix | 10 pages, no appendix, confirmed against the call |
| No bolded full sentences | No bold span runs past a run-in label |
| Completeness claims scoped | Every one scoped to the works surveyed |
| Em dashes | Zero |

## The residual, stated plainly

The session's topic list runs from graph mining and clustering through LLMs, autonomous systems,
knowledge discovery and about thirty more. It names nothing about benchmark quality, evaluation
methodology, reproducibility, or data quality. The paper's genuine anchors into that list are
**LLMs** and **autonomous systems**, and its bridge to the session's centre is the data-product
reading of a benchmark score, carried by Wang and Strong, Buneman et al., and Simmhan et al.

That bridge appears in the abstract, in a dedicated introduction paragraph, and twice in the
conclusion. It does not appear in Related Work, and that is deliberate. Two independent reviews
reached the same conclusion: bolting a provenance literature onto Related Work that the paper has
not actually engaged invites the reviewer who knows that literature, and costs more than the
fit it buys. The disposals table is the novelty argument, and it survived four review passes.

So structural fit is complete and topical fit is bounded by what the work is. The honest summary
is that this is a tool-layer audit whose results are a statement about the provenance of published
benchmark scores, submitted to a session that does not list evaluation methodology as a topic. The
framing makes that legible without pretending the paper is something else.

## One convention deliberately not followed

The measured exemplar ends its abstract on the experimental setting and headline result. This
abstract ends on the two repairs the findings argue for. That is the opposite convention, taken
deliberately: a scanning reader should leave knowing what to do differently, not what we ran. The
artefact sentence sits earlier instead.
