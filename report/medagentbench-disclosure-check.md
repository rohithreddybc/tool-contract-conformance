# MedAgentBench disclosure check — does the co-author's objection survive?

**Question posed:** does the MedAgentBench paper (arXiv 2501.14654) disclose that POST/write
requests are not executed against the FHIR server, such that the paper's flagship finding
(Finding 1, Phantom Effect on every POST) is not a defect under our own benign-simplification
criterion?

**Verdict: (b) — disclosed to the reader, not to the agent.** The co-author is right about what
the MedAgentBench paper says. He is wrong about the conclusion he draws from it. The paper
discloses the no-write design to a human reader in three places. Nothing on the agent-visible
surface — the prompt template the agent conditions on, or the tool's own runtime return string —
discloses anything of the kind; the return string affirmatively asserts execution. Under this
project's own stated criterion ("a simplification is benign exactly when it is advertised... the
undisclosed divergence between what the interface tells the agent and what the implementation
does"), disclosure to the paper's readership does not satisfy "advertised," because the object of
that criterion is the agent, not the reader. The finding survives, but its current framing in the
manuscript is thinner than it should be and is exposed to exactly this objection because it does
not quote or engage with the paper's strongest disclosure language.

---

## 1. What the MedAgentBench paper itself says

Source: `https://arxiv.org/html/2501.14654v2` (HTML full text, arXiv v2, 2025-02-12), fetched and
parsed directly (tags stripped, verified against the raw downloaded HTML rather than taken from a
summarized fetch). Three passages are dispositive, all in §2.4 ("Evaluation setup") and its
subsections.

**§2.4, evaluation setup, stating the design choice and its rationale:**

> "Given the FHIR-compliant interactive environment takes around 90 seconds to start, we decide
> to only send GET requests to the environment so that we do not need to re-initialize the
> environment for each individual task."

**§2.4.3, "Agent orchestrator," describing the mechanism exactly:**

> "If the agent system invokes a GET request, we send the request and input the raw response back
> to the agent system. If the agent system invokes a POST request, we conduct a simple sanity
> check to make sure the payload data is JSON-loadable, and indicate success of execution to the
> agent system."

**§2.4.1, "Metrics," the passage our manuscript already cites:**

> "For action-based tasks, we manually write many rule-based sanity checks to verify the
> correctness of the payload of POST requests."

Answering the report's specific sub-questions directly:

- **Does the paper state that POST/write requests are not actually executed against the FHIR
  server?** Yes, and squarely: "we decide to only send GET requests to the environment." No POST
  reaches the server; the paper says so in its own evaluation-design rationale, not as an aside.
- **Does it state that success responses are returned without the corresponding write?** Yes,
  verbatim: "we conduct a simple sanity check... and indicate success of execution to the agent
  system," in the same sentence that withholds the GET treatment (an actual forwarded request)
  from POST (a payload check only).
- **Does it describe checking POST payloads rather than resulting state?** Yes: "rule-based
  sanity checks to verify the correctness of the payload of POST requests" (§2.4.1) is the grading
  side of the same design; nowhere does §2.4 or §2.4.1 describe reading FHIR state back to verify
  a write.
- The paper is not silent on any of these three points. All three are stated plainly, in the
  evaluation-methodology section, as a considered design choice with a stated engineering reason
  (avoiding a 90-second re-initialization per task).

I also checked Appendix A.2 ("Prompts for the agent system"), which reproduces the full prompt
text given to the agent, since that is the one place a disclosure to the paper's readers could
also double as a disclosure to the agent. It does not:

> "You are an expert in using FHIR functions to assist medical professionals... 1. If you decide
> to invoke a GET function, you MUST put it in the format of GET url?param_name1=param_value1...
> 2. If you decide to invoke a POST function, you MUST put it in the format of POST url [your
> payload data in JSON format]... 3. If you have answered all the questions... finish(...)"

This is pure call-syntax instruction. It says nothing about what happens after a POST is issued,
disclosed or otherwise.

## 2. What the agent actually sees (from `FINDINGS-VERIFIED.md`, Findings 1 and 4)

`FINDINGS-VERIFIED.md` records the code at pinned commit `9926011`
(`src/server/tasks/medagentbench/__init__.py`, lines 85–91):

```
85    elif r.startswith('POST'):
86        try:
87            payload = json.loads('\n'.join(r.split('\n')[1:]))
88        except Exception as e:
89            session.inject({"role": "user", "content": "Invalid POST request"})
90        else:
91            session.inject({"role": "user", "content": "POST request accepted and executed
                successfully. Please call FINISH if you have got answers for all the questions
                and finished all the requested tasks"})
```

This is the entire agent-visible surface for a POST call: the payload is parsed (line 87) and
never read again, and the string injected into the agent's own conversation at line 91 is what
the agent receives as its tool result. Contrast this with the paper's own description of the same
mechanism — "indicate success of execution" (§2.4.3) — which is a cautious paraphrase written for
a human reader. What the agent is actually told is stronger and more specific: "accepted **and
executed successfully**." Nothing in the docstring, the tool's JSON schema (`FINDINGS-VERIFIED.md`
notes the functions "are defined as JSON schemas... manually translated based on FHIR API
documentation," i.e. modeled on the real, executing FHIR API), or the Appendix A.2 prompt tells
the agent that this string is fabricated or that no server-side write occurred.

Finding 4 compounds this independently of the disclosure question: the write-task grader
(`refsol.py`, `extract_posts`) reconstructs "what was written" from the agent's own transcript,
gated on the literal string `"POST request accepted"` — the same fabricated string from line 91.
No FHIR read occurs anywhere in the write-grading path (`task3`, `task8` unconditionally; `task5`,
`task9`, `task10` conditionally). This point is orthogonal to whether the no-write design is
disclosed to a reader: it is a claim about the evaluator's oracle, not about the tool's write
behavior, and the co-author's objection does not reach it. Finding 4 stands regardless of the
verdict on Finding 1's framing.

## 3. Verdict, argued

**(a) Fully disclosed** is not correct. It would require the agent-visible surface to also carry
the disclosure, and it does not: the prompt template is silent, and the tool's own return string
overstates what the paper's own methodology section describes ("executed successfully," not the
paper's more guarded "indicate success of execution").

**(c) Not disclosed** is also not correct, and is the error our current framing risks making by
omission. The paper does disclose this, plainly, in its own words, in the section our manuscript
already cites (§2.4.1) and in two adjacent passages our manuscript does not currently quote (§2.4,
§2.4.3). Claiming or implying the paper is silent here would be a false claim about someone else's
paper — exactly the outcome the project's own standing rules treat as the worst available result.

**(b) is correct.** The paper discloses a deliberate simplification to its human readers, with a
stated engineering rationale, and the underlying benchmark maintainers are not concealing
anything from the research community that reads their paper. But our own criterion, stated in
§III of our manuscript, is scoped to the agent: "the undisclosed divergence between what the
**interface tells the agent** and what the implementation does." A paper section a language-model
agent never ingests is not part of that interface. The agent conditions on the prompt template,
the tool schema, and the tool's return value — and on that surface, the claim "POST request
accepted and executed successfully" is unqualified and false. That is the actual defect: not that
a write is missing (the paper says it is, and says why), but that the agent is told, on the one
surface that determines its subsequent behavior and the grader's subsequent verdict, that the
write happened.

This also reframes what "the defect" should be named going forward, per the report's instruction:
the paper's disclosed simplification is that POST payloads are checked, not executed; the
undisclosed divergence is that the agent is told execution succeeded, with no signal distinguishing
that message from a genuine FHIR-write acknowledgment, and the write-task grader treats that same
unqualified string as its evidence of record.

## 4. Where the manuscript currently stands, and what should change

The manuscript is not making a false claim, but it is thinner than the evidence supports and is
exposed to exactly the co-author's objection, for a specific, fixable reason: it never quotes or
engages with the paper's two strongest disclosure passages (§2.4's "we decide to only send GET
requests," §2.4.3's "conduct a simple sanity check... and indicate success of execution"). It
quotes only the softer §2.4.1 phrase ("rule-based sanity checks to verify the correctness of the
payload"), at `paper/main.md:127`, and frames the numbers there as "not wrong... they faithfully
measure whether the agent emitted a well-formed POST request" — which is already close to
correct — but the flagship worked example in the introduction (`paper/main.md:80`) states flatly
that "the payload is parsed into a local variable and never read again... every write action in
this clinical-agent benchmark is a no-op that reports success to the agent," with no
acknowledgment anywhere nearby that MedAgentBench's own paper describes this exact mechanism and
gives an engineering reason for it. A careful reader who knows the source paper's §2.4 could read
that paragraph as claiming, or as being unaware of, something the source paper actually says
outright. §III's benign-simplification principle (`paper/main.md:160-166`) and the agent-visible
grounding-tier framework (`paper/main.md:206`) already supply the correct resolution in the
abstract — they are just never explicitly applied back to this specific worked example with the
paper's own words in hand.

**Suggested replacement wording** (drop-in for the vicinity of `paper/main.md:127`, or a new
sentence pair in the §I worked example at `paper/main.md:80`; every clause below is traceable to a
quote in §1 or §2 above):

> MedAgentBench's own paper discloses this design choice to its readers: it states that it
> decided "to only send GET requests to the environment" and that a POST request instead receives
> "a simple sanity check to make sure the payload data is JSON-loadable, and indicate success of
> execution to the agent system" (§2.4, §2.4.3). Neither disclosure reaches the agent: the prompt
> template the agent conditions on (Appendix A.2) states only GET/POST/finish call syntax, and the
> string the tool actually returns is stronger than the paper's own paraphrase — "POST request
> accepted **and executed successfully**" (`__init__.py:91`) — with nothing on the interface
> distinguishing it from a genuine FHIR write. The defect this paper reports is accordingly not
> the missing write, which MedAgentBench's authors chose deliberately and documented, but this
> unqualified, agent-visible claim of execution, on which the benchmark's own write-task grader
> then relies as its sole evidence of record (§VIII, Finding 4).

This does three things the current text does not: names the paper's disclosure honestly and
specifically (defusing the objection rather than leaving it to be found by a reviewer who reads
the source paper), states precisely why it does not resolve the finding under this project's own
criterion (the agent-visible / reader-visible distinction, already established elsewhere in the
manuscript but not applied here), and keeps Finding 4 as the independent, undamaged second half of
the argument.

## Bottom line for the co-author

He is right that the paper discloses the no-write design, in its own words, with a stated reason.
He is not right that this makes the finding disappear under our own stated criterion, because that
criterion is explicitly scoped to what the agent's interface tells the agent, not to what the
benchmark's paper tells a human reader — a distinction our own manuscript draws elsewhere (the
tau2 `airline/tools.py:689` vs. `:367` contrast) but has not yet drawn for this, its central
example. The fix is a framing correction, not a retraction: quote the paper's actual disclosure,
concede it plainly, and relocate the defect claim onto the one string the agent and the grader
both actually depend on.
