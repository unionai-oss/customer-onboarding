# Appendix B · Observability and debugging

A field guide for operating Union workloads: where signals live, how to attribute
failures, and the debugging workflow we use in support engagements. 

## Where the signals live

| Signal | Where | Notes |
|---|---|---|
| Run/action status, timelines, inputs/outputs | Union UI (run URL printed by every notebook cell) | Per-item visibility for `flyte.map` fan-outs |
| Task logs (live) | UI log tab · `flyte get logs <run>` | Streamed from the container |
| Task logs (after pod deletion) | Persisted logs shipped to the deployment's object store | On by default on Union data planes |
| Task metrics (CPU/mem/GPU per action), cost | Built-in platform metrics | Powers the UI's resource views |
| Cluster health | customer monitoring stack (optional kube-prometheus + Grafana; Union provides dashboard templates) | |
| Kubernetes ground truth | `kubectl -n <project>-<domain> get pods` / `describe pod` / `get events` | One namespace per project-domain pair |
| Ray dashboards | Links configured with the Ray plugin | Per-ephemeral-cluster |

## Platform errors vs user-code errors

The distinction that keeps operational reviews sane. First-pass classification:

| Symptom | Class | Evidence | First move |
|---|---|---|---|
| Python traceback in task logs | **User code** | Exception originates in your function | Fix/patch the task; `retries` only helps if transient |
| `OOMError` / exit code 137 with OOM event | **User code (sizing)** | UI shows OOM | Raise `memory`, or the catch-and-override pattern (03 §4); in reusable pods, lower `concurrency` |
| Run `PENDING`, nothing scheduled | **Platform (capacity)** | Queue wait growing | Capacity/quota (platform side); set `Timeout(max_queued_time=...)` to fail fast (03 §3) |
| Slow container start on scale-out | **Platform (registry)** | `describe pod` events show pull backoff | Registry permissions or throttling; reusable containers reduce pull storms (05 §4) |
| Task ran, node disappeared mid-run | **Platform (spot/preemption)** | Node event; `interruptible` retries are *not* charged to user retries | Expected on spot; pair with retries + traces (04 §4) |
| Exit code 137 **without** OOM event | Ambiguous | Could be eviction or SIGKILL on abort | Check node events before blaming memory |
| Webhook timeouts, slow aborts at high parallelism | **Platform (control plane)** | Many pods churning at once | Micro-batching + reuse (05) shrinks pod churn; escalate with run URL |
| Image build fails pushing | **Platform (registry IAM)** | `denied` in build logs | Builder needs write access to the registry (appendix A) |

**Escalation packet for Union support:** run URL · action name · task logs (or note if
missing) · `kubectl describe pod` + namespace events · what changed
(SDK version, image, chart version). That set resolves the majority of tickets in one pass.

## Exit codes worth memorizing

| Code | Meaning | Typical cause |
|---|---|---|
| 137 | SIGKILL | OOMKilled (check for the OOM event) or forced eviction |
| 143 | SIGTERM | Graceful shutdown: abort, spot reclaim, scale-down |
| 1 | App error | Unhandled Python exception (read the traceback) |
| 126/127 | Command not found / not executable | Broken image entrypoint, usually a custom base image |

