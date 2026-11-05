"""Exploration script: authenticate with Run:ai and summarize one workloads response.

Usage (from the repo root, with .venv active and .env filled in):
    python src/explore_runai.py            # print a field/summary overview
    python src/explore_runai.py --save     # also save raw JSON to samples/ (git-ignored)
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from runai_client import RunaiClient, RunaiConfig

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"


def summarize(workloads: list[dict]) -> None:
    print(f"Workloads returned: {len(workloads)}")
    if not workloads:
        return

    fields = Counter(key for w in workloads for key in w)
    print("\nTop-level fields (count of workloads containing each):")
    for key, count in sorted(fields.items()):
        print(f"  {key}: {count}")

    for field in ("phase", "type"):
        values = Counter(str(w.get(field)) for w in workloads)
        print(f"\nBy {field}:")
        for value, count in values.most_common():
            print(f"  {value}: {count}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--save", action="store_true", help="save raw JSON to samples/")
    args = parser.parse_args()

    client = RunaiClient(RunaiConfig.from_env())
    client.authenticate()
    print("Authenticated with Run:ai.")

    data = client.list_workloads(limit=args.limit)
    summarize(data.get("workloads", []))

    if args.save:
        SAMPLES_DIR.mkdir(exist_ok=True)
        out = SAMPLES_DIR / f"workloads_{datetime.now():%Y%m%d_%H%M%S}.json"
        out.write_text(json.dumps(data, indent=2))
        print(f"\nSaved raw response to {out} (git-ignored; do not share).")


if __name__ == "__main__":
    main()
