# Data Dictionary

Fields of the Workload object returned by `GET /api/v1/workloads`, taken from the
[NVIDIA Run:ai API docs, version 2.25](https://run-ai-docs.nvidia.com/api/2.25/workloads/workloads).
**No row has been checked against a real response yet.** Once a field has been seen in real data,
change its Status to `Verified (YYYY-MM-DD)` and correct the type and meaning if needed.

Most fields have no description in the API schema. Meanings marked *(inferred)* are our reading
of the field name, not documented behavior.

**Public-safe?** asks whether the field (or a value derived from it) may appear on the public display.
- `yes`: fine to show in aggregate (counts, totals, distributions). Not per-workload rows.
- `no`: never shown publicly. It may still be used internally for counting (e.g. unique submitters).
- `unsure`: needs a decision from Noyce leadership or infrastructure staff before any public use.

Even `yes` fields can identify someone when combined at fine granularity (e.g. one 8-GPU job
created at 2:14 am in a small department). Public views should aggregate over time and group size.

## Workload fields

### Used by `src/summarize_workloads.py`

| Field | Type | Meaning | Public-safe? | Status | Notes |
|-------|------|---------|--------------|--------|-------|
| `phase` | string (enum) | Current lifecycle state. Values: Creating, Initializing, Resuming, Pending, Deleting, Running, Updating, Stopped, Stopping, Degraded, Failed, Completed, Terminating, Unknown | yes | Unverified, from docs | Main source for "running vs. pending" counts |
| `type` | string | Workload type *(inferred: e.g. workspace, training, inference)* | yes | Unverified, from docs | Allowed values not listed in docs |
| `submittedBy` | string | User who submitted the workload *(inferred)* | **no** | Unverified, from docs | Likely a username or email. Count unique values only; never display, log, or commit |
| `workloadRequestedResources.gpu.request` | number (double), nullable | GPUs requested for the workload | yes | Unverified, from docs | Meaning depends on `gpuRequestType`; may be a fraction (e.g. 0.5) |
| `allocatedResources.gpu` | number (double), nullable | "States the number of GPUs allocated for the created workload." Present "if and only if `gpuRequestType` is portion" | yes | Unverified, from docs | Missing for memory-based GPU requests, so totals may undercount |

### Time

| Field | Type | Meaning | Public-safe? | Status | Notes |
|-------|------|---------|--------------|--------|-------|
| `createdAt` | string (date-time) | When the workload was created/submitted *(inferred)* | yes | Unverified, from docs | Use for "workloads per day/week"; round to day or hour publicly |
| `phaseUpdatedAt` | string (date-time) | Time of the most recent phase change | yes | Unverified, from docs | For a Running workload this may approximate start time, but resets on any phase change |
| `completedAt` | string (date-time), nullable | When the workload completed *(inferred)* | yes | Unverified, from docs | Null while still active |
| `updatedAt` | string (date-time) | Last time the record changed *(inferred)* | yes | Unverified, from docs | Probably not useful for display |
| `deletedAt` | string (date-time), nullable | When the workload was deleted | unsure | Unverified, from docs | Default list returns active workloads only; deleted ones need `?deleted=true` |
| `totalRunningTimeSeconds` | integer, nullable | "The total cumulative time, in seconds, that the workload has spent in the Running phase since submission." | yes | Unverified, from docs | Best source for duration and GPU-hours (× allocated GPUs) |
| `totalPendingTimeSeconds` | integer, nullable | "The total cumulative time, in seconds, that the workload has spent in the Pending phase since submission." | yes | Unverified, from docs | Queue wait time; a useful demand signal |

**Start time:** the docs list no `startedAt`/`runningAt` field. Options:
- `phaseUpdatedAt` when `phase` is `Running` (approximate).
- `createdAt + totalPendingTimeSeconds` (approximate; assumes one pending period).
- The workload events/history endpoints (not yet explored).

### Ownership and organization

| Field | Type | Meaning | Public-safe? | Status | Notes |
|-------|------|---------|--------------|--------|-------|
| `projectName` | string | Run:ai project the workload belongs to | unsure | Unverified, from docs | Projects may be named after people, courses, or unpublished research |
| `projectId` | string | Project identifier | no | Unverified, from docs | Internal ID; use only for grouping |
| `departmentName` | string | Run:ai department that owns the project | unsure | Unverified, from docs | Likely fine after approval; small departments may identify people |
| `departmentId` | string | Department identifier | no | Unverified, from docs | Internal ID |
| `namespace` | string | Kubernetes namespace | no | Unverified, from docs | Often embeds project or user names |
| `clusterId` | string (uuid) | "The id of the cluster." | no | Unverified, from docs | Internal ID |
| `id` | string (uuid) | Workload identifier | no | Unverified, from docs | Use for de-duplication only |
| `name` | string | User-chosen workload name | no | Unverified, from docs | Free text; may contain names or project details |

### Workload characteristics

| Field | Type | Meaning | Public-safe? | Status | Notes |
|-------|------|---------|--------------|--------|-------|
| `category` | string | Workload category *(inferred: e.g. Build, Train, Deploy)* | yes | Unverified, from docs | Docs description is a placeholder |
| `images` | array of string | Container image(s) the workload runs | no | Unverified, from docs | May reveal internal registry hostnames. A derived label (e.g. "PyTorch", "Jupyter") could be public |
| `distributedFramework` | string | Distributed training framework *(inferred: e.g. PyTorch, MPI)* | yes | Unverified, from docs | |
| `priority` | integer (int32), nullable | Scheduling priority | unsure | Unverified, from docs | Internal policy detail |
| `preemptible` | boolean, nullable | Whether the scheduler may preempt the workload | unsure | Unverified, from docs | |
| `requestedNodePools` / `currentNodePools` | array of string | Node pools requested / currently used | unsure | Unverified, from docs | Pool names may reveal hardware layout |

### Requested and allocated resources

| Field | Type | Meaning | Public-safe? | Status | Notes |
|-------|------|---------|--------------|--------|-------|
| `workloadRequestedResources.gpuRequestType` | string (enum: `portion`, `memory`), nullable | "Sets the unit type for GPU resources requests. Stated in terms of portion or memory." | yes | Unverified, from docs | Determines how to read the GPU request fields |
| `workloadRequestedResources.gpu.limit` | number (double), nullable | GPU limit for the workload | yes | Unverified, from docs | |
| `workloadRequestedResources.gpuMemory.request` | string, nullable | GPU memory requested (e.g. `"20Gi"`) *(inferred format)* | yes | Unverified, from docs | Used when `gpuRequestType` is `memory` |
| `workloadRequestedResources.cpu.request` | number (double), nullable | CPU cores requested | yes | Unverified, from docs | |
| `workloadRequestedResources.cpuMemory.request` | string, nullable | CPU memory requested *(inferred format: e.g. `"64Gi"`)* | yes | Unverified, from docs | |
| `podsRequestedResources.gpu.request` | number (double), nullable | GPUs requested, per pod *(inferred)* | yes | Unverified, from docs | Not used by the summarizer. If it's per pod, totals need × pod count |
| `allocatedResources.gpuMemory` | string, nullable | GPU memory allocated | yes | Unverified, from docs | |
| `allocatedResources.cpu` | number (double), nullable | "States the amount of CPU cores used by the workload running." | yes | Unverified, from docs | |
| `allocatedResources.cpuMemory` | string, nullable | CPU memory allocated | yes | Unverified, from docs | |
| `requestedPods.number` | integer | Number of pods requested | yes | Unverified, from docs | Also has `min`, `max`, `parallelism`, `completions` |
| `runningPods` | integer (int32) | Pods currently running | yes | Unverified, from docs | |
| `idleAllocatedGpus` | number, nullable | "sum of idle allocated gpus in the workload" | unsure | Unverified, from docs | Fine aggregated; per-workload values could single out users |

## Allocated vs. utilized GPUs

**Allocated** GPUs (`allocatedResources.gpu`) are what the scheduler has *reserved* for a
workload. They can't be given to anyone else while the workload holds them, whether or not
any computation is happening. A Jupyter notebook that holds 1 GPU overnight with no code running
counts as 1 allocated GPU.

**Utilized** GPUs describe how busy those GPUs actually are (compute and memory activity),
usually as a percentage over time.

They answer different questions:
- **Allocated:** "How much of the Factory is reserved?" This is a demand and capacity-planning
  signal, and it is what users actually wait on.
- **Utilized:** "How much useful work is happening?" This is an efficiency signal.

High allocation with low utilization usually means idle reservations, not a busy cluster.
`idleAllocatedGpus` is a partial hint (allocated but idle), but it is a point-in-time value
without a documented definition of "idle."

**Utilization likely needs a separate metrics source.** The workloads list does not include
utilization. The docs describe `GET /api/v1/workloads/{workloadId}/metrics` ("Retrieves workloads
data metrics from the metrics database"), with metric types including `GPU_UTILIZATION` and
`GPU_MEMORY_USAGE_BYTES` and required `start`/`end` times. That means one request per workload
per time window, which is too many for a frequently refreshed dashboard. Alternatives to discuss
with infrastructure staff:
- cluster- or node-pool-level metrics endpoints in Run:ai
- direct access to the underlying Prometheus/DCGM GPU telemetry, which fits the "GPU telemetry"
  future data source in `architecture.md`

Until one of these is approved, the dashboard should label GPU figures as **allocated**, never as
"usage" or "utilization."

## Candidate metrics

- Running and pending workloads (`phase`)
- Workload type (`type`, `category`)
- Requested vs. allocated GPUs (`workloadRequestedResources.gpu.request`, `allocatedResources.gpu`)
- Workload duration and GPU-hours (`totalRunningTimeSeconds` × `allocatedResources.gpu`)
- Queue wait time (`totalPendingTimeSeconds`)
- Workloads submitted per day/week (`createdAt`)
- Unique active users over an approved period (count of `submittedBy`, never names)
- Department- or project-level activity, if approved (`departmentName`, `projectName`)
