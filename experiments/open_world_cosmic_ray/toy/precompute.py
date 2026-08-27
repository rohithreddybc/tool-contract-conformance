"""Run ONCE, before cosmic-ray touches bank.py, against the pristine copy. Caches, per tool: the
probe corpus (mutation/probes.py's sec-2 equivalence corpus) and each probe's ORIGINAL
canonicalized (post_state, result) pair. test_command.py diffs against this cache instead of
re-importing an unmutated reference copy in-process (see that file's docstring for why)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scoring_lib as sl  # noqa: E402

OUT = Path(__file__).resolve().parent / "original_cache.json"


def main():
    cache = {}
    bank_module = sl.load_bank_module()
    pre_state = bank_module.ToyBank().state
    for tool in sl.load_toy_tool_names():
        probes = sl.build_probe_corpus_for_tool(tool)
        records = sl.run_probes_against_current_bank(tool, probes, bank_module=bank_module)
        cache[tool] = {"probes": probes, "records": records, "pre_state": pre_state}
    OUT.write_text(json.dumps(cache), encoding="utf-8")
    print(f"wrote {OUT} ({sum(len(v['probes']) for v in cache.values())} probes across {len(cache)} tools)")


if __name__ == "__main__":
    main()
