# Executable Tool-Contract Conformance Testing for Agentic Benchmarks

Replication artifact for an audit of the tool layer in four agentic benchmarks: tau2-bench,
AgentDojo, MM-ToolSandbox, and MedAgentBench.

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22182792.svg)](https://doi.org/10.5281/zenodo.22182792)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## What this is about

An agentic benchmark scores a model by letting it call simulated tools and then grading the
state those calls leave behind. Every such benchmark therefore advertises an executable
contract: the docstring, the schema, and the returned string tell the agent what a tool
requires and what it will do. Nothing checks that the implementation keeps that promise.

This project builds the missing check. Tool contracts are written from each tool's own
advertised surfaces, then tested statically and dynamically against the shipped code. Across
the four benchmarks the audit confirms eight defect instances spanning six executable defect
classes, four of which are headline-eligible under a grounding rule that excludes anything no
agent ever sees.

The clearest case is MedAgentBench. Its write tool performs no write, and its grader
independently reconstructs success from the agent's own transcript, gated on the same
fabricated success string the tool emits. Tool and grader agree about a write that never
happened. Five prior audits did not report it.

## Repository layout

| Path | Contents |
|---|---|
| `spec/` | Contract specification language, JSON schema, predicate grammar, and the validator. 42 contracts across four domains, plus 6 blind second-annotator contracts |
| `core/`, `static_check/`, `dynamic/` | The conformance checker, frozen at `checker-freeze-v2` |
| `adapters/` | Per-benchmark adapters. Each audited benchmark runs behind a subprocess boundary because they require mutually incompatible Python versions |
| `mutation/` | Two-arm detector validation: a closed-world arm over six taxonomy-aligned operators and an open-world, taxonomy-blind arm |
| `experiments/` | Both pre-registered analysis plans, the annotation protocol, and the numbers audit |
| `report/` | Every generated result behind the paper |
| `paper/` | Manuscript source and the generated tables |
| `tests/` | 25 test modules |

Key documents: `FINDINGS-VERIFIED.md` records each finding with a pinned upstream commit, a
file and line, and a verbatim quote. `GATE.md` records the prior-work gate that ran before any
code was written. `PROVENANCE.md` states plainly which ordering claims this repository's
history can support and which it cannot.

## Reproducing the results

Everything runs offline. No network access, no API keys, and no model calls are required at
any point.

```bash
make reproduce-results
```

On platforms without `make`:

```bash
python reproduce.py
```

Either command validates all contracts against the schema, regenerates the paper's tables and
diffs them against the committed copies, runs the numbers audit over the manuscript, and runs
the test suite.

## What is deliberately not here

The audited benchmarks are not redistributed. They are pinned by upstream commit in
`FINDINGS-VERIFIED.md`, so every finding can be re-verified against the exact tree it was found
in. To run the adapter-backed checks you will need to clone those repositories yourself into
`repos/` at the pinned commits; `make validate-full` covers that path.

## Reading the results honestly

Several things in this artifact cut against its own framing, and they are reported rather than
buried.

Seven of the eight findings were surfaced by hand. The checker's demonstrated role here is
confirmation and score-tracing, not discovery. Its recall against injected mutants is weak and
likely underpowered, and the open-world arm escapes most live mutants on the toy domain and
produces no usable denominator at all on the one real benchmark it was run against.

The trajectory replay returns a null. Zero of ten replayed trajectories trip either tested
defect and no verdict flips. Those trajectories are the benchmarks' own gold reference
solutions rather than agent runs, because this project has no model credentials, so the null
says less about agent behavior than its size suggests.

Benchmark selection is anchor-driven. Two benchmarks entered because their defects were already
known. No claim about how common these defects are is supportable from a sample chosen this
way.

## Coordinated disclosure

All findings go to the four maintainer teams on 2026-09-10, with per-finding reproduction
commands and proposed repairs. Responses, non-responses, and any contested finding are recorded
in `report/disclosure_log.md` under a reporting rule fixed before any response was known.

## Citing this work

A citation will be added here once the preprint is posted. Please cite the paper rather than
this repository. The Zenodo deposit archives the artifact and is referenced from the paper's
data availability statement; it is not the citation for the work.

## License

MIT. See `LICENSE`.
