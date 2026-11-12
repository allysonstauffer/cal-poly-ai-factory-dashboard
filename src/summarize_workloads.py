"""Print aggregated, non-identifying counts from a saved workloads JSON file.

Usage (from the repo root):
    python src/summarize_workloads.py                    # newest file in samples/
    python src/summarize_workloads.py path/to/file.json

Accepts either a Run:ai response / explore_runai.py --save file
({"workloads": [...], ...}) or a bare JSON list of workloads.
Only counts are printed: never user, project, or workload names.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

# =============================================================================
# FIELD MAPPING: edit these once real data has been inspected.
# Each entry is a tuple of candidate paths, tried in order; the first one present
# on a workload is used. Dots separate nested keys ("allocatedResources.gpu").
# Names below are from the Run:ai API docs v2.25 (not yet checked against real data).
# =============================================================================
FIELDS: dict[str, tuple[str, ...]] = {
    "phase": ("phase",),
    "type": ("type",),
    "submitter": ("submittedBy",),
    "requested_gpus": ("workloadRequestedResources.gpu.request",),
    "allocated_gpus": ("allocatedResources.gpu",),
}
# =============================================================================

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"
MISSING = "(missing)"
_ABSENT = object()


def lookup(workload: Any, field: str) -> Any:
    """Return the first candidate path for `field` present on `workload`, else _ABSENT."""
    for path in FIELDS[field]:
        value: Any = workload
        for key in path.split("."):
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                value = _ABSENT
                break
        if value is not _ABSENT:
            return value
    return _ABSENT


def _as_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _count_by(workloads: list, field: str) -> Counter:
    counts: Counter = Counter()
    for w in workloads:
        value = lookup(w, field)
        counts[MISSING if value is _ABSENT or value in (None, "") else str(value)] += 1
    return counts


def _gpu_total(workloads: list, field: str) -> dict:
    total, found = 0.0, 0
    for w in workloads:
        number = _as_number(lookup(w, field))
        if number is not None:
            total += number
            found += 1
    return {"total": total, "found_on": found}


def summarize(workloads: list) -> dict:
    submitters = set()
    for w in workloads:
        value = lookup(w, "submitter")
        if value is not _ABSENT and value not in (None, ""):
            submitters.add(str(value))
    return {
        "total": len(workloads),
        "by_phase": _count_by(workloads, "phase"),
        "by_type": _count_by(workloads, "type"),
        "unique_submitters": len(submitters),
        "submitter_field_found": any(lookup(w, "submitter") is not _ABSENT for w in workloads),
        "requested_gpus": _gpu_total(workloads, "requested_gpus"),
        "allocated_gpus": _gpu_total(workloads, "allocated_gpus"),
    }


def _fmt_number(x: float) -> str:
    return str(int(x)) if x == int(x) else f"{x:.2f}"


def format_summary(summary: dict) -> str:
    total = summary["total"]
    lines = [f"Total workloads: {total}"]

    for title, key in (("By phase/status", "by_phase"), ("By workload type", "by_type")):
        lines.append(f"\n{title}:")
        if not summary[key]:
            lines.append("  (none)")
        for value, count in sorted(summary[key].items(), key=lambda kv: (-kv[1], kv[0])):
            lines.append(f"  {value}: {count}")

    lines.append("")
    if summary["submitter_field_found"] or total == 0:
        lines.append(f"Unique submitters: {summary['unique_submitters']}")
    else:
        lines.append(f"Unique submitters: field not found (tried {', '.join(FIELDS['submitter'])})")

    for label, key in (("Requested GPUs", "requested_gpus"), ("Allocated GPUs", "allocated_gpus")):
        gpu = summary[key]
        if gpu["found_on"] == 0:
            lines.append(f"{label}: field not found (tried {', '.join(FIELDS[key])})")
        else:
            lines.append(
                f"{label} (total): {_fmt_number(gpu['total'])} "
                f"(field found on {gpu['found_on']}/{total} workloads)"
            )
    return "\n".join(lines)


def load_workloads(path: Path) -> list:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        workloads = data
    elif isinstance(data, dict) and isinstance(data.get("workloads"), list):
        workloads = data["workloads"]
    else:
        raise ValueError("expected a JSON list or an object with a 'workloads' list")
    return [w for w in workloads if isinstance(w, dict)]


def newest_sample(samples_dir: Path = SAMPLES_DIR) -> Path | None:
    files = [p for p in samples_dir.glob("*.json") if p.is_file()] if samples_dir.is_dir() else []
    return max(files, key=lambda p: p.stat().st_mtime) if files else None


def main(argv: list[str] | None = None, samples_dir: Path = SAMPLES_DIR) -> int:
    parser = argparse.ArgumentParser(description="Print aggregated counts from a workloads JSON file.")
    parser.add_argument("path", nargs="?", type=Path, help="workloads JSON (default: newest in samples/)")
    args = parser.parse_args(argv)

    path = args.path or newest_sample(samples_dir)
    if path is None:
        print(f"No JSON files found in {samples_dir.name}/. Pass a file path.", file=sys.stderr)
        return 1
    try:
        workloads = load_workloads(path)
    except (OSError, ValueError) as exc:
        # ValueError covers json.JSONDecodeError. Message names the file, not its contents.
        print(f"Could not read {path.name}: {type(exc).__name__}", file=sys.stderr)
        return 1

    print(f"Source: {path.name}\n")
    print(format_summary(summarize(workloads)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
