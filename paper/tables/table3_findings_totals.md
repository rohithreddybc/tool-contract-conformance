| Benchmark | Tools audited | Mutating | Independent impl. | Classes reported (headline) | Source |
|---|---:|---:|---:|---:|---|
| MedAgentBench | 3 | 3 | 1 | 2 (1) | FINDINGS-VERIFIED.md Findings 1 and 4; ARCHITECTURE-FINAL.md “Realistic tool counts” (static case study; no adapter, no contract, zero findings.jsonl rows) |
| tau2-bench | 19 | 19 | 3 | 3 (1) | report/findings.jsonl (180 rows, 4 VIOLATES) |
| AgentDojo | 7 | 7 | 3 | 2 (1) | report/findings.jsonl (60 rows, 5 VIOLATES) |
| MM-ToolSandbox | 5 | 5 | 1 | 1 (1) | report/findings.jsonl (27 rows, 3 VIOLATES) |
| **Total** | **34** | **34** | **8** | **8 (4)** | |

Excluded (reported, not headline): MedAgentBench Ungrounded Oracle (evaluator-layer, not tool-layer); tau2-bench Ignored Argument (unadjudicated candidate); tau2-bench Partial Effect (maintainer-annotated); AgentDojo Phantom Effect (fixture never trips biconditional).
