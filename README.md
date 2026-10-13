# Cal Poly AI Factory Dashboard

An internal data-visualization project for Cal Poly's AI Factory. The dashboard will translate AI Factory workload activity into clear, useful information for students, faculty, visitors, and Noyce School leadership.

## Project goals

The AI Factory includes NVIDIA DGX B200 GPU systems, high-speed storage, networking, and workload-management software. This project focuses first on answering human questions about how the Factory is being used:

- What kinds of workloads are running?
- How active is the AI Factory right now?
- How many people and projects are using it over time?
- Which resources have the highest demand?
- How can students and faculty learn to use the AI Factory?

The long-term platform may also incorporate lower-level storage, GPU, and power telemetry. The first version will use high-level workload data from NVIDIA Run:ai.

## Audiences

### Public display

For students, faculty, visitors, donors, and prospective collaborators. It should explain what an AI Factory enables and show approved, aggregated activity in an approachable format.

### Internal reporting

For Noyce School leadership and technical infrastructure staff. It may support capacity planning, resource governance, and future investment decisions.

## Initial scope

Version 0 will explore NVIDIA Run:ai's read-only REST API and validate a simple pipeline:

1. Authenticate with a personal Run:ai access key.
2. Retrieve approved workload or summary data.
3. Document the fields, meaning, and availability of the data.
4. Produce a small prototype visualization using aggregated, non-sensitive metrics.

Initial metrics to investigate:

- Running and pending workloads
- Workload type or category, such as Jupyter, training, or inference
- Requested and allocated GPU resources
- Workload duration
- Unique active users over an approved period
- Project-level activity, when appropriate for the audience

## Architecture

```text
Run:ai control plane
        |
        | Read-only REST API
        v
Python data-access layer
        |
        | Validated, aggregated metrics
        v
Dashboard / public display
```

Additional data sources, such as VAST storage, GPU metrics, and power-distribution units, can be added after the Run:ai data flow is understood.

## Tech stack

- Python for API access, data transformation, and analysis
- NVIDIA Run:ai REST API for initial workload data
- Grafana or a custom web dashboard for visualization, to be decided after data exploration
- GitHub for source control, documentation, and project history

## Local setup

### Prerequisites

- Python 3.11+
- Access to the Cal Poly network or VPN when required
- A read-only NVIDIA Run:ai account and personal access key

### Environment variables

Create a local `.env` file. Never commit it.

```text
RUNAI_BASE_URL=https://<your-runai-instance>
RUNAI_CLIENT_ID=<your-client-id>
RUNAI_CLIENT_SECRET=<your-client-secret>
RUNAI_VERIFY_TLS=true
```

`RUNAI_VERIFY_TLS` should remain `true` once the Run:ai certificate is trusted. Do not put real credentials, bearer tokens, internal IP addresses, or sensitive screenshots in this repository.

## Project documentation

- [Software Requirements Document](docs/SRD.md) - project requirements, audiences, and open decisions
- [Data Dictionary](docs/data-dictionary.md) - definitions for retrieved metrics and fields
- [Architecture Notes](docs/architecture.md) - data sources, API access, and deployment decisions

## Status

Early exploration. The immediate objective is to authenticate successfully with the Run:ai API and retrieve one approved, read-only data response.