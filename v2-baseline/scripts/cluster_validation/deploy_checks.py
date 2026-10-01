"""Client-side capability checks: the ones that need flyte.deploy / flyte.serve.

suite.py covers everything that fits in a single `flyte run`. This script covers what
doesn't. For each capability it deploys, confirms it works from outside the cluster,
and cleans up:

  app           serve a throwaway HTTP app, wait for it to activate, GET its endpoint
  schedule      deploy a minutely trigger and wait for it to actually launch a run
                (the platform's own smoke test only checks that the trigger registers)
  on-artifact   deploy a flyte.OnArtifact trigger, publish a new artifact version,
                and wait for the triggered run

    uv run python scripts/cluster_validation/deploy_checks.py                 # all
    uv run python scripts/cluster_validation/deploy_checks.py app schedule    # a subset

Uses the project/domain from your flyte config. For registries that need credentials,
export IMAGE_PULL_SECRET=<image_pull secret name> first, the same as for suite.py. The app is deployed with
requires_auth=False so the check can reach it without a token. It is a static file
server with nothing behind it, and it is deleted when the check finishes.
"""

import os
import sys
import tempfile
import time
import uuid
from datetime import datetime
from pathlib import Path

import flyte
import flyte.app
import flyte.remote as remote
from flyte.io import File

APP_NAME = "cv-http-probe"
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


app_env = flyte.app.AppEnvironment(
    name=APP_NAME,
    command=["python", "-m", "http.server", "8080"],
    port=8080,
    image=IMAGE,
    resources=flyte.Resources(cpu="250m", memory="256Mi"),
    scaling=flyte.app.Scaling(replicas=(1, 1)),
    requires_auth=False,
    **PULL,
)


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


def check_app() -> str:
    import httpx

    try:
        flyte.serve(app_env)
        app = remote.App.get(name=APP_NAME).watch(wait_for="activated")
        endpoint = app.endpoint
        deadline = time.monotonic() + 300
        last = ""
        while time.monotonic() < deadline:
            try:
                resp = httpx.get(endpoint, timeout=10, follow_redirects=True)
                if resp.status_code == 200:
                    return f"activated and served HTTP 200 at {endpoint}"
                last = f"HTTP {resp.status_code}"
            except httpx.HTTPError as e:
                last = f"{type(e).__name__}: {e}"
            time.sleep(10)
        raise RuntimeError(f"app activated but {endpoint} never returned 200 (last: {last})")
    finally:
        remote.App.delete(name=APP_NAME)


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
        art = remote.Artifact.create(File.from_local_sync(str(tmp)), name=ARTIFACT_NAME, version=version)
        run = _wait_for_new_run(task_name, seen, timeout_s=300)
        run.wait(quiet=True)
        if run.phase != "succeeded":
            raise RuntimeError(f"triggered run {run.name} ended {run.phase}")
        output = run.outputs()[0]
        if version not in output:
            raise RuntimeError(f"run {run.name} received a different artifact: {output!r}")
        art.delete()
        return f"publishing {ARTIFACT_NAME}@{version} fired run {run.name}, which read it back"
    finally:
        _delete_trigger("cv_on_artifact", task_name)


CHECKS = {"app": check_app, "schedule": check_schedule, "on-artifact": check_on_artifact}


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
        print(f"{status:5} {name:12} {detail}  [{time.monotonic() - started:.0f}s]", flush=True)
    sys.exit(1 if failed else 0)
