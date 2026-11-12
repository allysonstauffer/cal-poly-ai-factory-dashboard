# Architecture Notes

> Record decisions here as they are made.

## Data flow (v0)

```text
Run:ai control plane
        |  read-only REST API (client-credentials token)
        v
src/runai_client.py      login, GET requests, safe error messages
        |
src/workloads.py         fetch_all_workloads(): paginated /api/v1/workloads
        |
src/explore_runai.py     prints a field overview; --save writes samples/*.json
        |
        v
samples/*.json           raw responses, local only (git-ignored)
        |
src/summarize_workloads.py   aggregated counts only
        |
        v
Dashboard / public display (TBD)
```

## Components

### `src/runai_client.py`

- **`RunaiConfig.from_env()`:** reads `RUNAI_BASE_URL`, `RUNAI_CLIENT_ID`, `RUNAI_CLIENT_SECRET`, `RUNAI_VERIFY_TLS`, and `RUNAI_CA_BUNDLE` from `.env`. Fails early if the CA bundle file is missing, or if it's set while `RUNAI_VERIFY_TLS=false`.
- **`RunaiClient`:**
  - Only sends GET requests, plus `POST /api/v1/token`; anything else is refused.
  - The access token is kept in memory only, never written to disk. On HTTP 401 the client fetches a new token and retries the request once.
  - All failures raise `RunaiError`, whose message and traceback have hostnames, IP addresses, and the token removed. The original exception is not chained, so tracebacks are safe to share.

### `src/workloads.py`

- **`fetch_all_workloads(client, page_size=100, max_pages=100)`** returns a `WorkloadsResult`: the workloads, the number of pages fetched, and whether it stopped early.
- **Pagination:** follows the Run:ai API docs v2.25. It sends `offset` and `limit` (1-500), sorted by `createdAt` ascending, and stops when `next` is absent or a page comes back empty.
  - The docs don't say whether `next` is an item offset or a page number, so the code only uses it as a "more pages" signal and moves `offset` forward itself.
  - Workloads are de-duplicated by `id` in case items shift between pages.
- **Safety limit:** `max_pages` caps the number of requests.

### `src/explore_runai.py`

Command-line exploration tool. Options:

- `--page-size`: workloads per request (default 100)
- `--max-pages`: request limit (default 100)
- `--save`: write raw workloads to `samples/`

### `src/summarize_workloads.py`

Reads a workloads JSON file: the file named on the command line, or the newest one in `samples/`. Prints counts only, never names.

- **Field mapping:** field paths are defined once in `FIELDS` at the top of the file, taken from the docs and not yet checked against real data.
- **Missing data:** missing fields are reported as "(missing)" or "field not found" instead of crashing.

## Data sources

| Source | Status | Access |
|--------|--------|--------|
| NVIDIA Run:ai | Exploring (blocked on TLS CA) | REST API, `/api/v1/token` then `/api/v1/workloads` |
| Run:ai workload metrics | Candidate for GPU utilization | `/api/v1/workloads/{id}/metrics` (one request per workload) |
| GPU telemetry (Prometheus/DCGM) | Future; candidate for utilization | TBD |
| VAST storage | Future | TBD |
| Power distribution units | Future | TBD |

See `docs/data-dictionary.md` for allocated vs. utilized GPUs.

## Repository layout

- `src/`: Python data-access, fetching, and summary code
- `tests/`: pytest tests; `tests/fixtures/` holds clearly fake data only
- `docs/`: requirements, data dictionary, architecture notes, `progress/` updates
- `samples/`: local raw API responses (git-ignored, never committed)

## Testing

Run `python -m pytest` from the repo root. `pytest.ini` puts `src/` on the import path. The tests replace the HTTP layer with a fake, so they make no network requests and don't read `.env`.

## Deployment

- TBD
