# Architecture Notes

> Stub. Record decisions here as they are made.

## Data flow (v0)

```text
Run:ai control plane
        |  read-only REST API (client-credentials token)
        v
src/runai_client.py  ->  src/explore_runai.py
        |  validated, aggregated metrics
        v
Dashboard / public display (TBD)
```

## Data sources

| Source | Status | Access |
|--------|--------|--------|
| NVIDIA Run:ai | Exploring | REST API, `/api/v1/token` then `/api/v1/workloads` |
| VAST storage | Future | TBD |
| GPU telemetry | Future | TBD |
| Power distribution units | Future | TBD |

## Repository layout

- `src/` — Python data-access and exploration code
- `docs/` — requirements, data dictionary, architecture notes
- `samples/` — local raw API responses (git-ignored, never committed)

## Deployment

- TBD
