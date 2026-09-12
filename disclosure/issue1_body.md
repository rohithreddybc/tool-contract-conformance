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
