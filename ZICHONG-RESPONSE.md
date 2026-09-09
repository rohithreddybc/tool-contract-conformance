# Response to Zichong's comments

Draft for sending. Written to be read by a co-author, not filed as a rebuttal.

---

Zichong,

Thank you for these. The MedAgentBench one was right and it changed the paper.

**On the MedAgentBench example.** I went back to their paper before touching anything. You are
correct: §2.4 says they decided to send only GET requests so the environment would not need
re-initialising for each task, and §2.4.3 says a POST gets a JSON-loadable sanity check after which
the harness indicates success of execution to the agent system. That is a documented design choice
with a stated engineering reason, and by our own benign-simplification criterion, which says a
simplification is benign exactly when it is advertised, the missing write is not a defect. We were
calling a disclosed decision an oversight.

The finding survives, but it is a different finding, and the paper now says so. What their paper
discloses, it discloses to someone reading their paper. Nothing the agent sees discloses it. The
tool returns "POST request accepted and executed successfully" with no qualification, which is
stronger than their own careful phrasing, and the write-task grader then admits evidence only when
it matches that same string. So the defect we report is the agent-visible claim that the write
happened, not the absence of the write. I think this is a better paper for it: a documented
simplification that the agent cannot see, whose grader then trusts the tool's own success message,
is a cleaner instance of our actual thesis than an ordinary bug would have been. The headline is
less quotable and the argument is harder to attack.

Chasing what else rested on that claim turned up two things I would not have found otherwise. Our
statement that five prior audits reported nothing about this benchmark was not supportable: our own
prior-work gate file does not mention MedAgentBench anywhere, so we never established that those
audits examined it. That sentence is gone, and what remains is the narrower claim we did check,
that none of those audit taxonomies has a category for a success signal decoupled from state. I
also found that no contract exists for MedAgentBench under `spec/contracts/`, so the validator's
agent-visibility check has never run on this finding. Since the reframe makes agent-visibility the
whole basis of the claim, the paper now says the grounding rests on direct source reading recorded
at a pinned commit rather than on the automated check.

**On the opening describing two evaluation designs as one.** Also right. The class is now defined
as benchmarks grading what a call reports having done, whether by reading the state it left behind
or by reading the results it returned, so the transcript-reading example belongs to the class
rather than sitting outside it.

**On the levels of certainty.** The paper now separates two things it had been running together.
Presence is deterministic: a defect of this kind is there on every rerun. Effect is not, and the
paper no longer implies it is. Score-at-risk bounds what the exposure could amount to, and the text
now says that without asserting any verdict changed.

**On the categorical description of prior work.** Cut. "All stop one layer above the tool body",
"none of them tests", and the "no single-layer audit sees a defect" line in the figure caption are
gone, replaced with claims scoped to what we actually checked.

**On the introduction's centre of gravity.** This one I want to flag rather than simply accept,
because there is a real tension. That closing paragraph was added after an earlier review asked us
to surface the discovery-versus-confirmation distinction early, so a reader would not credit the
checker with findings a person made by hand. Your objection is that placing it in the introduction
moves attention from the claim to the defence, and I think you are right that placement was the
error rather than the honesty. It is now one sentence, and the concession about what we did not
invent has moved to related work where it belongs.

Two things still open on my side: the affiliation line for you, and the disclosure to the four
maintainer teams. The disclosure will use the reframed language, since telling MedAgentBench's
maintainers we found a missing write would invite them to point at their own §2.4.

Rohith
