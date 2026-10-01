# Cluster validation

Automates most of the [appendix A §3 capability checklist](../../appendix/A-deployment-adaptation.md):
run it during engagement prep, or after a platform upgrade, to learn which v2 capabilities
work on a deployment before a session depends on them.

It is a companion to Union's own post-deploy smoke test (`tests/flytev2` in the cloud repo).
That test covers a fan-out run, trigger *registration*, and dataproxy inputs/outputs/logs/upload.
Everything below is what it doesn't cover.

**Requires flyte ≥ 2.6** (`flyte.artifacts`, `produces_artifacts`, `OnArtifact`). The flyte 2.5.x pin on
`main` can't import either script.

**Private registries:** if pods need credentials to pull images, export the name of an
`image_pull` secret before running either script:

```bash
flyte create secret --type image_pull my-registry-secret --from-docker-config --registries <registry>
export IMAGE_PULL_SECRET=my-registry-secret
```

Every image then gets it as `registry_secret` (so the builder can push and pull), and every task
environment and the app get it in `secrets` (so pods can pull at runtime). Images are built into the
deployment's default image-builder registry.

## `suite.py`: one `flyte run`, in-cluster checks

```bash
uv run flyte run scripts/cluster_validation/suite.py validate
# optional capabilities are SKIPped unless you name them:
uv run flyte run scripts/cluster_validation/suite.py validate \
    --gpu T4:1 --queue moderation-api --secret_key HF_TOKEN
```

The checks run in parallel, one console group each, and the results appear in the parent
action's **Report** tab. With `--strict true` (the default) the run fails if any check FAILs.
Pass `--strict false` to get the report without failing the run.

| Check | What it proves | PASS when |
|---|---|---|
| `cache` | task cache on the data plane | 2nd call with identical inputs returns the 1st call's uuid |
| `retries` | user retries | attempt 0 raises, a later attempt succeeds |
| `user-error` | failure propagation | child `ValueError` reaches the parent as `RuntimeUserError`, message intact |
| `timeout` | `timeout=` enforcement | 20s timeout kills a 300s sleep with `TaskTimeoutError` |
| `oom` | memory limits + OOM classification | 2 GiB alloc under 256Mi surfaces as `OOMError` (WARN if it dies unclassified) |
| `resources` | requests/limits reach the pod | cgroup shows memory 2Gi / cpu 2 |
| `custom-image` | image builder + registry pull | a `with_pip_packages` image builds and its package imports |
| `reusable-containers` | `ReusePolicy` (needs `unionai-reuse`) | 4 calls served by one warm process |
| `gpu` | accelerator scheduling (`--gpu`) | `nvidia-smi -L` lists a device |
| `queue` | named queue / cluster-pool routing (`--queue`) | an action routed via `override(queue=)` completes |
| `secret` | secret injection (`--secret_key`) | the secret lands as an env var (only its length is returned) |
| `metrics-workload` | execution metrics (**manual**) | INFO only: a 90s CPU + 256Mi task; open its Metrics tab |
| `artifact-create` | artifact service, in-task `Artifact.create` | create → get → listall → `to_python` round-trips |
| `artifact-declared` | backend-registered `artifacts.new()` | output of a `produces_artifacts=True` task is registered |

## `deploy_checks.py`: client-side checks (deploy/serve)

These can't run inside a task, so they run on your machine. Apps and triggers are deleted afterwards. Artifact versions are kept, because the artifact service can't delete them yet:

```bash
uv run python scripts/cluster_validation/deploy_checks.py                  # all five
uv run python scripts/cluster_validation/deploy_checks.py app app-auth     # a subset
```

| Check | PASS when |
|---|---|
| `app` | a FastAPI app (image built with `fastapi`/`uvicorn`) activates, `/health` returns 200, and `/probe-file` returns the contents of a file passed as an app `Parameter`. That proves the platform downloaded it from the object store into the app pod |
| `app-auth` | with `requires_auth=True`, an anonymous request is rejected (401/403 or a redirect to login). FAIL if the app answers it |
| `app-scale-to-zero` | an app with `replicas=(0, 1)` and `scaledown_after=60` reaches 0 replicas (`status.current_replicas`), then serves a request again. The detail reports the cold-start time. If the backend doesn't report replicas, it waits 180s and says 0 replicas is unconfirmed |
| `schedule` | a minutely trigger *actually launches* a run that succeeds |
| `on-artifact` | publishing an artifact version fires a `flyte.OnArtifact` run that reads that exact version |

`app` and `app-scale-to-zero` deploy with `requires_auth=False` so the script can call them without a token. They only expose `/health` and the throwaway probe file.

## Reading results

- **WARN** means the capability works partly. Example: the pod was OOM-killed but the SDK
  didn't get `OOMError`, so users see a generic failure.
- **artifact-declared** FAIL while **artifact-create** PASSes: the backend doesn't register
  declarations. Chapter 06 still works because it uses `create()`.
- **queue** or **gpu** hanging in *Queued*: the queue has no healthy cluster, or no node pool
  can satisfy the GPU. That's a platform-side fix.
