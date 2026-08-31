"""Offline reproduction driver. Equivalent to `make reproduce-results`, for
platforms without make.

Runs, in order: contract validation, table re-derivation, the numbers audit,
and the test suite. No network access, no API keys, and no model calls are
required or made. Exits non-zero on the first failing step.
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def contracts():
    paths = sorted(
        p for d in ("contracts", "contracts_annotator_b")
        for p in (ROOT / "spec" / d).rglob("*.yaml")
    )
    return [str(p) for p in paths]


STEPS = [
    ("contract validation (offline subset)",
     [sys.executable, "spec/validate.py", *contracts()]),
    ("generated tables",
     [sys.executable, "report/render.py", "--verify"]),
    ("score-at-risk ledger",
     [sys.executable, "analysis/score_at_risk.py", "--verify"]),
    ("numbers audit",
     [sys.executable, "experiments/numbers_audit.py"]),
    ("test suite",
     [sys.executable, "-m", "pytest", "tests", "-q"]),
]


def main():
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONUTF8="1")
    for name, cmd in STEPS:
        print(f"\n== {name} ==", flush=True)
        rc = subprocess.call(cmd, cwd=ROOT, env=env)
        if rc != 0:
            print(f"\nreproduce: FAILED at '{name}' (exit {rc})")
            return rc
    print("\nreproduce-results: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
