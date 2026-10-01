"""Client-side capability checks: the ones that need flyte.deploy / flyte.serve.

suite.py covers everything that fits in a single `flyte run`. This script covers what
doesn't. For each capability it deploys, confirms it works from outside the cluster,
and cleans up:

  app                 serve a FastAPI app with a file parameter; GET /health and
                      confirm the app read the file the platform downloaded for it
  app-auth            serve an app with requires_auth=True; an unauthenticated
                      request must be rejected
  app-scale-to-zero   serve an app with replicas=(0, 1); wait for it to reach zero
                      replicas, then time the cold start from a request
  schedule            deploy a minutely trigger and wait for it to actually launch a
                      run (the platform's own smoke test only checks registration)
  on-artifact         deploy a flyte.OnArtifact trigger, publish a new artifact
                      version, and wait for the triggered run

    uv run python scripts/cluster_validation/deploy_checks.py                     # all
    uv run python scripts/cluster_validation/deploy_checks.py app app-auth        # a subset

Uses the project/domain from your flyte config. For registries that need credentials,
export IMAGE_PULL_SECRET=<image_pull secret name> first, the same as for suite.py.

The `app` and `app-scale-to-zero` apps are deployed with requires_auth=False so the
checks can reach them without a token. They expose only /health and /probe-file
(the throwaway file this script uploads), and every app is deleted when its check
finishes.
"""

import os
import socket
import sys
import tempfile
import time
import uuid
from datetime import datetime
from pathlib import Path

import flyte
import flyte.app
import flyte.remote as remote
from fastapi import FastAPI
from flyte.app import Parameter
from flyte.app.extras import FastAPIAppEnvironment
from flyte.io import File

ARTIFACT_NAME = "cluster-validation-trigger-probe"

# Name of an `image_pull` secret for registries that need credentials; see suite.py.
PULL_SECRET = os.environ.get("IMAGE_PULL_SECRET", "")
# A name is required: from_debian_base drops registry_secret unless name or registry is set.
IMAGE = flyte.Image.from_debian_base(name="cv-base", registry_secret=PULL_SECRET or None)
PULL = {"secrets": [PULL_SECRET], "env_vars": {"IMAGE_PULL_SECRET": PULL_SECRET}} if PULL_SECRET else {}

# One env per trigger: deploying an env (re)activates every trigger in it.
schedule_env = flyte.TaskEnvironment(
    name="cv_schedule",
    image=IMAGE,
    resources=flyte.Resources(cpu="250m", memory="256Mi"),
    **PULL,
)
artifact_env = flyte.TaskEnvironment(
    name="cv_on_artifact",
    image=IMAGE,
    resources=flyte.Resources(cpu="250m", memory="256Mi"),
    **PULL,
)


@schedule_env.task(triggers=flyte.Trigger.minutely(name="cv_minutely", trigger_time_input_key="fired_at"))
async def on_schedule(fired_at: datetime) -> str:
    return f"fired at {fired_at.isoformat()}"


@artifact_env.task(
    triggers=flyte.Trigger(
        "cv_on_artifact",
        flyte.OnArtifact(name=ARTIFACT_NAME),
        inputs={"artifact": flyte.TriggeredArtifact},
        auto_activate=True,
    )
)
async def on_artifact(artifact: File) -> str:
    local = await artifact.download()
    return Path(local).read_text()


# ── Apps ──────────────────────────────────────────────────────────────────────────────
# One FastAPI object, served by three app environments that differ only in auth and
# scaling. Each container re-imports this module and serves its env's `app`.

PROBE_FILE_ENV = "CV_PROBE_FILE"
api = FastAPI(title="cluster-validation probe")


@api.get("/health")
async def health() -> dict:
    return {"status": "ok", "pod": socket.gethostname()}


@api.get("/probe-file")
async def probe_file() -> dict:
    # With download=True the platform fetches the file parameter before start-up and
    # puts its local path in this env var.
    path = os.environ.get(PROBE_FILE_ENV, "")
    return {"content": Path(path).read_text() if path and os.path.isfile(path) else None}


APP_IMAGE = flyte.Image.from_debian_base(name="cv-app", registry_secret=PULL_SECRET or None).with_pip_packages(
    "fastapi", "uvicorn"
)


def _app_env(name: str, *, requires_auth: bool = False, replicas=(1, 1), scaledown_after=None, parameters=()):
    return FastAPIAppEnvironment(
        name=name,
        app=api,
        image=APP_IMAGE,
        resources=flyte.Resources(cpu="250m", memory="256Mi"),
        scaling=flyte.app.Scaling(replicas=replicas, scaledown_after=scaledown_after),
        requires_auth=requires_auth,
        parameters=list(parameters),
        **PULL,
    )


# Its value is a file uploaded at serve time (see check_app), so importing this module
# in the container doesn't upload anything.
app_env = _app_env("cv-app", parameters=[Parameter(name="probe", type="file", env_var=PROBE_FILE_ENV)])
auth_app_env = _app_env("cv-app-auth", requires_auth=True)
cold_app_env = _app_env("cv-app-coldstart", replicas=(0, 1), scaledown_after=60)


def _wait_for_new_run(task_name: str, seen: set[str], timeout_s: int) -> remote.Run:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        for run in remote.Run.listall(task_name=task_name, limit=20):
            if run.name not in seen:
                return run
        time.sleep(10)
    raise TimeoutError(f"no run of {task_name} appeared within {timeout_s}s")


def _existing_runs(task_name: str) -> set[str]:
    return {r.name for r in remote.Run.listall(task_name=task_name, limit=100)}


def _delete_trigger(name: str, task_name: str) -> None:
    try:
        remote.Trigger.delete(name=name, task_name=task_name)
    except Exception as e:
        print(f"      cleanup: could not delete trigger {name}: {e}", flush=True)


def _get_until(url: str, ok, timeout_s: int = 300, **kwargs):
    """GET url until ok(response) holds. Retries while ingress/the pod come up."""
    import httpx

    deadline = time.monotonic() + timeout_s
    last = ""
    while time.monotonic() < deadline:
        try:
            resp = httpx.get(url, timeout=30, **kwargs)
            if ok(resp):
                return resp
            last = f"HTTP {resp.status_code}"
        except httpx.HTTPError as e:
            last = f"{type(e).__name__}: {e}"
        time.sleep(10)
    raise RuntimeError(f"{url} never returned the expected response within {timeout_s}s (last: {last})")


def _delete_app(name: str) -> None:
    try:
        remote.App.delete(name=name)
    except Exception as e:
        print(f"      cleanup: could not delete app {name}: {e}", flush=True)


def _replicas(name: str) -> int:
    return remote.App.get(name=name).pb2.status.current_replicas


def check_app() -> str:
    token = f"cv-{uuid.uuid4().hex[:8]}"
    tmp = Path(tempfile.mkdtemp()) / "probe.txt"
    tmp.write_text(token)
    try:
        flyte.with_servecontext(
            parameter_values={app_env.name: {"probe": File.from_local_sync(str(tmp))}}
        ).serve(app_env)
        endpoint = remote.App.get(name=app_env.name).endpoint
        pod = _get_until(f"{endpoint}/health", lambda r: r.status_code == 200).json()["pod"]
        content = _get_until(f"{endpoint}/probe-file", lambda r: r.status_code == 200).json()["content"]
        if content != token:
            raise RuntimeError(f"app is up but the file parameter wasn't delivered (got {content!r})")
        return f"FastAPI app on {pod} served /health and read its file parameter at {endpoint}"
    finally:
        _delete_app(app_env.name)


def check_app_auth() -> str:
    try:
        flyte.serve(auth_app_env)
        endpoint = remote.App.get(name=auth_app_env.name).endpoint

        # Rejected = 401/403, or a redirect to the login flow. Anything else (404/502/503)
        # means the route isn't ready yet, so keep polling.
        def decided(r):
            return r.status_code in (200, 401, 403) or r.is_redirect

        resp = _get_until(f"{endpoint}/health", decided, follow_redirects=False)
        if resp.status_code == 200:
            raise RuntimeError(f"requires_auth=True but {endpoint}/health answered an anonymous request")
        where = f" -> {resp.headers.get('location', '')[:80]}" if resp.is_redirect else ""
        return f"anonymous request rejected with HTTP {resp.status_code}{where}"
    finally:
        _delete_app(auth_app_env.name)


def check_app_scale_to_zero() -> str:
    name = cold_app_env.name
    try:
        flyte.serve(cold_app_env)
        endpoint = remote.App.get(name=name).endpoint
        _get_until(f"{endpoint}/health", lambda r: r.status_code == 200)

        # current_replicas reads 0 when a backend doesn't report it, so only trust a 0
        # after seeing it above 0.
        reported = False
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline and not reported:
            reported = _replicas(name) > 0
            time.sleep(5)

        if reported:
            deadline = time.monotonic() + 600
            while _replicas(name) > 0:
                if time.monotonic() > deadline:
                    raise RuntimeError("min replicas is 0 but the app was still running 10 min after its last request")
                time.sleep(15)
            idle = "scaled to 0 replicas"
        else:
            time.sleep(180)    # scaledown_after=60s plus scale-down grace
            idle = "waited 180s idle (status.current_replicas isn't reported, so 0 replicas is unconfirmed)"

        started = time.monotonic()
        _get_until(f"{endpoint}/health", lambda r: r.status_code == 200)
        return f"{idle}; cold start served /health in {time.monotonic() - started:.0f}s"
    finally:
        _delete_app(name)


def check_schedule() -> str:
    task_name = "cv_schedule.on_schedule"
    seen = _existing_runs(task_name)
    flyte.deploy(schedule_env)
    try:
        # Minutely fires at the top of the next minute; allow a couple of misses.
        run = _wait_for_new_run(task_name, seen, timeout_s=240)
        run.wait(quiet=True)
        if run.phase != "succeeded":
            raise RuntimeError(f"triggered run {run.name} ended {run.phase}")
        return f"schedule fired run {run.name}, which succeeded"
    finally:
        _delete_trigger("cv_minutely", task_name)


def check_on_artifact() -> str:
    task_name = "cv_on_artifact.on_artifact"
    seen = _existing_runs(task_name)
    flyte.deploy(artifact_env)
    version = f"cv-{uuid.uuid4().hex[:8]}"
    try:
        tmp = Path(tempfile.mkdtemp()) / "probe.txt"
        tmp.write_text(f"artifact {version}\n")
        # Not deleted afterwards: artifact deletion isn't implemented server-side yet.
        remote.Artifact.create(File.from_local_sync(str(tmp)), name=ARTIFACT_NAME, version=version)
        run = _wait_for_new_run(task_name, seen, timeout_s=300)
        run.wait(quiet=True)
        if run.phase != "succeeded":
            raise RuntimeError(f"triggered run {run.name} ended {run.phase}")
        output = run.outputs()[0]
        if version not in output:
            raise RuntimeError(f"run {run.name} received a different artifact: {output!r}")
        return f"publishing {ARTIFACT_NAME}@{version} fired run {run.name}, which read it back"
    finally:
        _delete_trigger("cv_on_artifact", task_name)


CHECKS = {
    "app": check_app,
    "app-auth": check_app_auth,
    "app-scale-to-zero": check_app_scale_to_zero,
    "schedule": check_schedule,
    "on-artifact": check_on_artifact,
}


if __name__ == "__main__":
    selected = sys.argv[1:] or list(CHECKS)
    unknown = set(selected) - set(CHECKS)
    if unknown:
        sys.exit(f"unknown check(s) {sorted(unknown)}; choose from {list(CHECKS)}")

    flyte.init_from_config()
    failed = 0
    for name in selected:
        started = time.monotonic()
        try:
            status, detail = "PASS", CHECKS[name]()
        except Exception as e:
            status, detail = "FAIL", f"{type(e).__name__}: {str(e)[:400]}"
            failed += 1
        print(f"{status:5} {name:18} {detail}  [{time.monotonic() - started:.0f}s]", flush=True)
    sys.exit(1 if failed else 0)
