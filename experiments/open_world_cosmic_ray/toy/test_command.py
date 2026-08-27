"""cosmic-ray test-command, invoked once per mutation (fresh process each time -- see
cosmic_ray.testing.run_tests: shlex.split + subprocess.Popen). Loads whatever bank.py currently
contains on disk (mutated by cosmic-ray for the duration of this call, restored right after),
runs every toy tool's probe corpus against it, diffs against precompute.py's cached original
records, and appends one JSON line per BEHAVIOURALLY LIVE tool to results.jsonl (append mode --
cosmic-ray's local distributor runs test-command strictly sequentially, one mutation at a time,
so concurrent writes are not a concern). Exits 1 if any tool came back live (arbitrary, cosmetic:
cosmic-ray's own kill/survived label is not what this experiment scores by -- results.jsonl is)."""
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
    bank_module = sl.load_bank_module()
    any_live = False
    with open(RESULTS_PATH, "a", encoding="utf-8") as out:
        for tool, entry in cache.items():
            mutant_records = sl.run_probes_against_current_bank(tool, entry["probes"], bank_module=bank_module)
            live = sl.is_behaviorally_live(entry["records"], mutant_records)
            row = {"mutation_seq": seq, "tool": tool, "live": live}
            if live:
                any_live = True
                row.update(sl.checker_detects(tool, bank_module=bank_module))
                witness = sl.first_differing_probe(entry["records"], mutant_records, entry["probes"])
                if witness is not None and row.get("detected") is False:
                    # Only escapes (live + not flagged VIOLATES) need sec 4.3's decomposition --
                    # a live mutant the checker DID flag needs no cause classification.
                    try:
                        row["escape_cause"] = sl.classify_escape_for_tool(tool, witness, entry["pre_state"])
                    except Exception as e:  # noqa: BLE001
                        row["escape_cause"] = None
                        row["escape_cause_error"] = f"{type(e).__name__}: {e}"
            out.write(json.dumps(row) + "\n")
    return 1 if any_live else 0


if __name__ == "__main__":
    sys.exit(main())
