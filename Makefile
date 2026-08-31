# Offline reproduction. No network, no API keys, no model calls: every target
# below runs against files committed in this repository.
#
# Windows without make: run `python reproduce.py` instead. Same steps, same order.

PY ?= python
export PYTHONPATH := .
CONTRACTS := $(wildcard spec/contracts/*/*.yaml) $(wildcard spec/contracts_annotator_b/*/*.yaml)

.PHONY: reproduce-results validate validate-full tables audit test help

help:
	@echo "reproduce-results  full offline reproduction: validate, tables, audit, tests"
	@echo "validate           grammar and schema checks on all contracts (offline)"
	@echo "validate-full      all 8 checks, including provenance; needs repos/ (see README)"
	@echo "tables             re-derive paper/tables/ and report/ and diff against committed"
	@echo "audit              check every numeric claim in the manuscript"
	@echo "test               run the test suite"

reproduce-results: validate tables audit test
	@echo ""
	@echo "reproduce-results: OK"

# Checks 1-3, 6, 7 and the JSON schema run from this repository alone. Checks 4,
# 5 and 8 read the audited benchmark source and are reported as SKIPPED here;
# `validate-full` runs them. The skip count is expected, not a failure.
validate:
	@echo "== contract validation (offline subset) =="
	$(PY) spec/validate.py $(CONTRACTS)

# Provenance and agent-visibility checks. Requires the audited benchmarks cloned
# under repos/ at the commits pinned in FINDINGS-VERIFIED.md; they are not
# redistributed here.
validate-full:
	@echo "== contract validation (all 8 checks) =="
	$(PY) spec/validate.py $(CONTRACTS) --repo-root repos --state-schema spec/schema.json

# Generated outputs are a pure function of the committed evidence. --verify
# re-derives and diffs, so a stale table fails here rather than reaching the paper.
tables:
	@echo "== generated tables =="
	$(PY) report/render.py --verify
	$(PY) analysis/score_at_risk.py --verify

# Every numeric claim in paper/main.md and paper/latex/main.tex, checked against
# the generated artifacts, with the two files diffed for divergence.
audit:
	@echo "== numbers audit =="
	$(PY) experiments/numbers_audit.py

test:
	@echo "== test suite =="
	$(PY) -m pytest tests -q
