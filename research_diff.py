#!/usr/bin/env python3
"""research_diff.py - Compare decision registers across parallel trial runners.

Usage:
    python3 research_diff.py TRIAL_DIR_1 TRIAL_DIR_2 [TRIAL_DIR_3 ...]
    python3 research_diff.py run_a run_b run_c

Outputs a clean markdown comparison showing where models agreed and where choices split.
"""

import argparse
import csv
import sys
from pathlib import Path

REQUIRED_STAGES = ["question", "scope", "data", "digest", "draft", "mint"]


def load_decisions(trial_path):
    p = Path(trial_path) / "decisions.csv"
    if not p.exists():
        sys.exit(f"Error: {p} does not exist")
    with p.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = {r["decision_id"].strip().upper(): r for r in reader if r.get("decision_id")}
    return rows


def main():
    parser = argparse.ArgumentParser(description="Compare decisions across trial directories.")
    parser.add_argument("trials", nargs="+", help="Paths to trial directories to compare")
    parser.add_argument("--markdown", action="store_true", default=True, help="Output in markdown format")
    args = parser.parse_args()

    if len(args.trials) < 2:
        sys.exit("Error: Specify at least two trial directories to diff.")

    trial_dirs = [Path(t) for t in args.trials]
    trial_data = {t.name: load_decisions(t) for t in trial_dirs}

    all_dids = []
    for d in trial_data.values():
        for did in d.keys():
            if did not in all_dids and did:
                all_dids.append(did)

    names = [t.name for t in trial_dirs]
    print(f"# Cross-Runner Decision Diff")
    print(f"Comparing {len(names)} runners: {', '.join(names)}\n")

    for did in all_dids:
        rows = [trial_data[name].get(did, {}) for name in names]
        question_text = next((r.get("question") for r in rows if r.get("question")), did)
        stage = next((r.get("stage") for r in rows if r.get("stage")), "")

        chosen_vals = [r.get("chosen", "").strip() for r in rows]
        has_content = any(chosen_vals)
        if not has_content:
            continue

        all_identical = len(set(chosen_vals)) == 1

        print(f"## {did} ({stage}: {question_text})")
        status = "CONSENSUS" if all_identical else "DIVERGENCE"
        print(f"**Status:** {status}\n")

        for name, r in zip(names, rows):
            by = r.get("decided_by", "unspecified")
            chosen = r.get("chosen", "[empty]")
            alts = r.get("alternatives", "")
            rationale = r.get("rationale", "")
            print(f"- **{name}** (`{by}`):")
            print(f"  - *Chosen:* {chosen}")
            if alts:
                print(f"  - *Alternatives:* {alts}")
            if rationale:
                print(f"  - *Rationale:* {rationale}")
        print("\n---\n")


if __name__ == "__main__":
    main()
