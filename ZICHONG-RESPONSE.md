# Note to Zichong

Short covering note. The detailed replies sit next to his comments in the review
build of the paper, so they are not duplicated here.

---

Zichong,

Thanks for these. Your five comments are in the source now, with a reply beside each one.
Compile with `\reviewtrue` in the preamble to see them; the submission build hides both and
still comes to ten pages.

The MedAgentBench point changed the paper, so it is worth saying here rather than leaving it
in a margin note. You were right that their paper documents the no-write design. Section 2.4
says they send only GET requests so the environment does not need re-initialising for each
task, and 2.4.3 says a POST gets a JSON-loadable sanity check and is then reported to the
agent as successful. By our own criterion a documented simplification is not a defect, so we
were calling a design decision an oversight.

The finding held up once we moved it. What their paper discloses, it discloses to someone
reading their paper. Nothing the agent sees discloses it, the tool returns "POST request
accepted and executed successfully" with no qualification, and the write-task grader accepts
that string as its evidence. So the defect we report is the claim the agent is given, not the
absence of the write. I think the paper is better for it. A documented simplification the
agent cannot see, whose grader then trusts the tool's own message, is a cleaner example of
what this paper is about than an ordinary bug would be.

Working out what else depended on that claim turned up two things I would not have found
otherwise. Our line about five prior audits reporting nothing could not be supported, because
our own prior-work file never established that those audits looked at MedAgentBench at all.
And no contract exists for that benchmark under `spec/contracts/`, so the validator's
agent-visibility check has never run on this finding. Since your comment makes agent
visibility the whole basis of it, the paper now says the grounding is a hand reading recorded
at a pinned commit.

On the introduction, I made the change but want you to know why that paragraph was there. An
earlier review asked us to say up front that seven of the eight findings were made by hand, so
that nobody would credit the checker with them. You are right that putting it in the
introduction moved attention from the claim to the defence. It is one sentence now and the
introduction ends on what the paper establishes.

Two things still open on my side: your affiliation line, and the disclosure to the four
maintainer teams. The disclosure will use the reframed language, since telling MedAgentBench's
maintainers we found a missing write would invite them to point at their own Section 2.4.

Rohith
