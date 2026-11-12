"""Workload retrieval built on RunaiClient.

Pagination follows the NVIDIA Run:ai REST API docs, version 2.25:
  https://run-ai-docs.nvidia.com/api/2.25/workloads/workloads
  https://run-ai-docs.nvidia.com/api/2.25/getting-started/using-the-rest-api/pagination

  GET /api/v1/workloads?offset=<int>&limit=<1..500, default 50>
  200 response: {"workloads": [...], "next": <int, optional>}
  "If next is not returned (or is empty), you've reached the end of the collection."

The docs do not say whether `next` is an item offset or a page index, so this
module only treats `next` as a "more pages exist" signal and advances the
offset itself by the number of items received.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from runai_client import RunaiClient

WORKLOADS_PATH = "/api/v1/workloads"
MAX_PAGE_SIZE = 500  # documented upper bound for `limit`
DEFAULT_PAGE_SIZE = 100
DEFAULT_MAX_PAGES = 100


@dataclass
class WorkloadsResult:
    workloads: list[dict] = field(default_factory=list)
    pages_fetched: int = 0
    truncated: bool = False  # True if max_pages was hit before the last page


def fetch_all_workloads(
    client: RunaiClient,
    page_size: int = DEFAULT_PAGE_SIZE,
    max_pages: int = DEFAULT_MAX_PAGES,
) -> WorkloadsResult:
    """Fetch every page of /api/v1/workloads, up to max_pages."""
    if not 1 <= page_size <= MAX_PAGE_SIZE:
        raise ValueError(f"page_size must be between 1 and {MAX_PAGE_SIZE}")
    if max_pages < 1:
        raise ValueError("max_pages must be at least 1")

    result = WorkloadsResult()
    seen_ids: set[str] = set()
    offset = 0

    while True:
        if result.pages_fetched >= max_pages:
            result.truncated = True
            break

        data = client.get(
            WORKLOADS_PATH,
            # Stable ordering so items don't shift between pages as workloads change.
            params={"offset": offset, "limit": page_size, "sortBy": "createdAt", "sortOrder": "asc"},
        )
        page = data.get("workloads") or []
        result.pages_fetched += 1

        for workload in page:
            workload_id = workload.get("id")
            if workload_id is not None:
                if workload_id in seen_ids:
                    continue
                seen_ids.add(workload_id)
            result.workloads.append(workload)

        if data.get("next") in (None, "") or not page:
            break
        offset += len(page)

    return result
