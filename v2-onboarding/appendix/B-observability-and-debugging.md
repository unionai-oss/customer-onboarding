# Appendix B · Observability and debugging

A field guide for operating Union workloads on your self-managed GCP deployment:
where signals live, how to attribute failures, and the debugging workflow we use in
support engagements.

## Where the signals live

| Signal | Where | Notes |
|---|---|---|
| Run/action status, timelines, inputs/outputs | Union UI (run URL printed by every notebook cell) | Per-item visibility for `flyte.map` fan-outs |
| Task logs (live) | UI log tab · `flyte get logs <run>` | Streamed from the pod |
| Task logs (after pod deletion) | Persisted logs: FluentBit ships every container log to `persisted-logs/` in the dataplane GCS bucket | On by default; see appendix A → *Persistent task logs* |
| Task metrics (CPU/mem/GPU per action), cost | Built-in dataplane Prometheus (no setup) | Powers the UI's resource views |
| Cluster health (nodes, CoreDNS, API server) | Optional `kube-prometheus-stack` (`monitoring.enabled`) + **customer-hosted Grafana** | Union provides dashboard templates |
| Kubernetes ground truth | `kubectl -n <project>-<domain> get pods` / `describe pod` / `get events` | The namespace per project-domain pair |
| Ray dashboards | Log/dashboard links configured with the plugin (appendix A → *Ray*) | Per-ephemeral-cluster |

## Platform errors vs user-code errors

The distinction that keeps operational reviews sane. First-pass classification:

| Symptom | Class | Evidence | First move |
|---|---|---|---|
| Python traceback in task logs | **User code** | Exception originates in your function | Fix/patch the task; `retries` only helps if transient |
| `OOMError` / pod `OOMKilled` (exit code 137) | **User code (sizing)** | UI shows OOM; `kubectl describe pod` shows `OOMKilled` | Raise `memory`, or the catch-and-override pattern (02 §4); in reusable pods, lower `concurrency` |
| Run `PENDING`, no pod scheduled | **Platform (capacity)** | `kubectl get events` shows `FailedScheduling`; queue wait growing | Node-pool capacity/quota (platform team); set `Timeout(max_queued_time=...)` to fail fast (02 §3) |
| Pod stuck `ContainerCreating` / `ImagePullBackOff` | **Platform (registry)** | `describe pod` events | GAR permissions or throttling; reusable containers reduce pull storms (04 §4) |
| Task ran, node disappeared mid-run | **Platform (spot/preemption)** | Node event; retry consumed *not* charged for `interruptible` tasks | Expected on spot — pair with retries + traces (03 §4) |
| Exit code 137 **without** OOM event | Ambiguous | Could be eviction or SIGKILL on abort | Check node events before blaming memory |
| Webhook timeouts, slow aborts at high parallelism | **Platform (control plane)** | Many pods churning at once | Micro-batching + reuse (04) shrinks pod churn; escalate with run URL |
| `flyte deploy`/image build fails pushing | **Platform (IAM)** | `denied` in build logs | `artifactregistry.writer` for the builder (appendix A) |

**Escalation packet for Union support:** run URL · action name · task logs (or note if
missing → persisted-logs gap) · `kubectl describe pod` + namespace events · what changed
(SDK version, image, chart version). That set resolves the majority of tickets in one pass.

## Exit codes worth memorizing

| Code | Meaning | Typical cause |
|---|---|---|
| 137 | SIGKILL | OOMKilled (check for the OOM event) or forced eviction |
| 143 | SIGTERM | Graceful shutdown — abort, spot reclaim, scale-down |
| 1 | App error | Unhandled Python exception (read the traceback) |
| 126/127 | Command not found / not executable | Broken image entrypoint — usually a custom base image |

## Debugging workflow (support-engagement default)

1. **Open the run URL.** Failed action → read the error + logs there. 80% of cases end here.
2. **Classify** with the table above (user code vs platform).
3. **Reproduce small.** Same task, tiny input, `flyte.run` from a notebook — is it data-dependent?
4. **Inspect Kubernetes** if the platform is suspect: pod events, node events, quota.
5. **Check the deltas.** New image? New chart? New SDK pin? The notebooks pin everything
   for exactly this reason.
6. **Escalate** with the packet above.

## Notes on customer-operated pieces

- **Log routing to your destinations** (Cloud Logging, BigQuery sinks, SIEM): the FluentBit
  DaemonSet writes to GCS by default; routing beyond that is your logging stack — Union
  provides routing guidance and the Union-side config.
- **Grafana**: customer-hosted. Ask Union for the current dashboard templates (task
  queueing, resource utilization, cost) rather than rebuilding from scratch.
- **Alerting**: alert on queue-wait times, OOM rates per project, and image-pull error
  rates first — those three catch most operational drift before users notice.
