"""Run ONCE, under .venv-tau2, PYTHONPATH pointed at the PRISTINE scratch copy (before cosmic-ray
mutates anything). Mirrors cr_toy/precompute.py -- see that file's docstring."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scoring_lib as sl  # noqa: E402

OUT = Path(__file__).resolve().parent / "original_cache.json"


def main():
    cache = {}
    adapter = sl.InlineTau2Adapter()
    pre_state = adapter.snapshot(adapter.fresh_env("telecom"))
    for tool in sl.TELECOM_TOOLS:
        probes = sl.build_probe_corpus_for_tool(tool)
        records = sl.run_probes_against_current_tau2(tool, probes)
        cache[tool] = {"probes": probes, "records": records, "pre_state": pre_state}
        print(f"{tool}: {len(probes)} probes")
    OUT.write_text(json.dumps(cache), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
