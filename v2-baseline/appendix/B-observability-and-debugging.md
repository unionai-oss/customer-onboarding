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
| `OOMError` / exit code 137 with OOM event | **User code (sizing)** | UI shows OOM | Raise `memory`, or the catch-and-override pattern (05 §2); in reusable pods, lower `concurrency` |
| Run `PENDING`, nothing scheduled | **Platform (capacity)** | Queue wait growing | Capacity/quota (platform side); set `Timeout(max_queued_time=...)` to fail fast (05 §1) |
| Slow container start on scale-out | **Platform (registry)** | `describe pod` events show pull backoff | Registry permissions or throttling; reusable containers reduce pull storms (03 §2, §4) |
| Task ran, node disappeared mid-run | **Platform (spot/preemption)** | Node event; `interruptible` retries are *not* charged to user retries | Expected on spot; pair with retries, `flyte.Checkpoint` and traces (05) |
| Exit code 137 **without** OOM event | Ambiguous | Could be eviction or SIGKILL on abort | Check node events before blaming memory |
| Webhook timeouts, slow aborts at high parallelism | **Platform (control plane)** | Many pods churning at once | Micro-batching + reuse (03 §2, §4) shrinks pod churn; escalate with run URL |
| Image build fails pushing | **Platform (registry IAM)** | `denied` in build logs | Builder needs write access to the registry (appendix A) |

**Escalation packet for Union support:** run URL · action name · task logs (or note if
missing) · `kubectl describe pod` + namespace events · what changed
(SDK version, image, chart version). That set resolves the majority of tickets in one pass.
## Salvaging a failed run: rerun, recover, fork

The three run-level operations are introduced in [05 §6](../05-resilience-and-recovery.ipynb).
This is the detail you need when one of them behaves unexpectedly.

### Which one, in one table

| | Code that runs | Succeeded actions | Requires |
|---|---|---|---|
| `flyte.rerun(run)` | the source run's | all re-execute | flyte 2.x |
| `flyte.rerun(run, recover=True)` | the source run's | reused (`RECOVERED`) | flyte ≥ 2.6, and backend support |
| `fork(run, task_template=…)` | your local working tree | reused (`RECOVERED`) | `flyteplugins-union` ≥ 0.8.1, flyte ≥ 2.6.5 |

All three are remote-only. `--action-name` cannot be combined with `--recover`.

### Why an action re-executed when you expected reuse

An action is reused only if its **name** is unchanged. The name hashes the task's identity
(task name, interface, and the decorated function's own source), plus its parent action,
inputs, and call order. So:

| Changing this | Renames the action? |
|---|---|
| Comments, formatting, whitespace inside the task | no |
| `flyte.Resources` (cpu, memory) | no — deliberately, so you can fork an OOM fix |
| The image, or packages added to it | no — same reason |
| A module-level constant the task reads | **no** |
| A helper function the task calls | **no** |
| The task function's body | yes |
| The task signature, docstring, or function name | yes |
| The `TaskEnvironment` name | yes |
| Anything at all, when tasks come from a **notebook** | yes — every action, always |

The last row is why fork demos live in `scripts/`: notebook tasks ship as pickled bundles
that version on the bundle, so nothing is ever reused.

### Why your fix had no effect

The two **no** rows in bold are the trap. Identity covers only the decorated function's own
source, so editing a constant or helper that a *succeeded* task reads leaves the action name
untouched — the old result is reused and your change is silently skipped. Same shape for
inputs: a recovered action keeps the output it produced under the **original** inputs, so
`rerun(run, recover=True, threshold=0.9)` does not recompute what already succeeded.

The fix in both cases is `force_rerun_actions=["a3", "a7"]` (`--force-rerun-action a3`),
which re-executes named actions despite their prior success.

### Other failure modes

| Symptom | Cause | Fix |
|---|---|---|
| `NotImplementedError: recover is not yet supported by this backend` | The deployment's `flyteidl2` build has no `RunSpec.relation` | Backend upgrade; check with the platform team |
| Recovery fails on missing outputs | The source run's outputs were garbage-collected | `allow_missing_source_outputs=True` (`--allow-missing-outputs`) |
| A task input named `recover`, `run_name`, `action_name`, `force_rerun_actions`, or `allow_missing_source_outputs` is unreachable | Those share the keyword namespace with `rerun()`'s own arguments | Rename the task input |
| `flyte.rerun(run, recover=True)` silently passes `recover` as a task input | The SDK predates 2.6 — the parameter does not exist there | Upgrade; `pyproject.toml` pins `flyte>=2.6.9,<2.7` |

Recovery is **not** caching: caching is content-addressed on inputs plus task version and
applies globally, while recovery is scoped to one source run and matched by action name.
They compose — a recovery run still takes normal cache hits, and recovery covers tasks that
are not cacheable at all.
