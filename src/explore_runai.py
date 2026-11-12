"""Exploration script: authenticate with Run:ai and summarize all workloads.

Usage (from the repo root, with .venv active and .env filled in):
    python src/explore_runai.py            # print a field/summary overview
    python src/explore_runai.py --save     # also save raw JSON to samples/ (git-ignored)
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from runai_client import RunaiClient, RunaiConfig, RunaiError
from workloads import DEFAULT_MAX_PAGES, DEFAULT_PAGE_SIZE, WorkloadsResult, fetch_all_workloads

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"


def summarize(result: WorkloadsResult) -> None:
    workloads = result.workloads
    print(
        f"Total workloads across all pages: {len(workloads)} "
        f"({result.pages_fetched} page(s) fetched)"
    )
    if result.truncated:
        print("WARNING: stopped at --max-pages; more workloads exist than shown.")
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
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE, help="items per request (1-500)")
    parser.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES, help="safety limit on requests")
    parser.add_argument("--save", action="store_true", help="save raw JSON to samples/")
    args = parser.parse_args()

    try:
        client = RunaiClient(RunaiConfig.from_env())
        client.authenticate()
        print("Authenticated with Run:ai.")
        result = fetch_all_workloads(client, page_size=args.page_size, max_pages=args.max_pages)
    except RunaiError as exc:
        sys.exit(f"Error: {exc}")

    summarize(result)

    if args.save:
        SAMPLES_DIR.mkdir(exist_ok=True)
        out = SAMPLES_DIR / f"workloads_{datetime.now():%Y%m%d_%H%M%S}.json"
        payload = {
            "pagesFetched": result.pages_fetched,
            "truncated": result.truncated,
            "workloads": result.workloads,
        }
        out.write_text(json.dumps(payload, indent=2))
        print(f"\nSaved raw response to {out} (git-ignored; do not share).")


if __name__ == "__main__":
    main()
