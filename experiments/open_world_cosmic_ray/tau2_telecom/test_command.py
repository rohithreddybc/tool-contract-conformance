"""cosmic-ray test-command for the tau2 telecom open-world run. Fresh process per invocation
(cosmic_ray.testing.run_tests). Mirrors cr_toy/test_command.py -- see that file's docstring."""
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
import scoring_lib as sl  # noqa: E402

CACHE_PATH = _HERE / "original_cache.json"
RESULTS_PATH = _HERE / "results.jsonl"
COUNTER_PATH = _HERE / "_mutation_seq.txt"


def _next_seq() -> int:
    n = int(COUNTER_PATH.read_text()) + 1 if COUNTER_PATH.exists() else 0
    COUNTER_PATH.write_text(str(n))
    return n


def main() -> int:
    cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    seq = _next_seq()
    any_live = False
    with open(RESULTS_PATH, "a", encoding="utf-8") as out:
        for tool, entry in cache.items():
            try:
                mutant_records = sl.run_probes_against_current_tau2(tool, entry["probes"])
                live = sl.is_behaviorally_live(entry["records"], mutant_records)
            except Exception as e:  # noqa: BLE001 -- a mutant can break env construction itself
                live = True  # cannot prove equivalence -- treat as live per sec 4.1's spirit
                row = {"mutation_seq": seq, "tool": tool, "live": live, "detected": None,
                       "error": f"probe_run_failed: {type(e).__name__}: {e}"}
                any_live = True
                out.write(json.dumps(row) + "\n")
                continue
            row = {"mutation_seq": seq, "tool": tool, "live": live}
            if live:
                any_live = True
                row.update(sl.checker_detects(tool))
                if row.get("detected") is False:
                    witness = sl.first_differing_probe(entry["records"], mutant_records, entry["probes"])
                    if witness is not None:
                        try:
                            row["escape_cause"] = sl.classify_escape_for_tool(tool, witness, entry["pre_state"])
                        except Exception as e:  # noqa: BLE001
                            row["escape_cause"] = None
                            row["escape_cause_error"] = f"{type(e).__name__}: {e}"
            out.write(json.dumps(row) + "\n")
    return 1 if any_live else 0


if __name__ == "__main__":
    sys.exit(main())
