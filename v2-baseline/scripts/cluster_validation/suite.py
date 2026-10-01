"""In-cluster capability suite: one `flyte run` that exercises the data plane end to end.

Complements the platform's own smoke tests (a fan-out run, a trigger registration,
dataproxy inputs/outputs/logs/upload) with the capabilities those don't touch. Each
check runs as its own group of child actions, all in parallel, and the parent writes a
PASS / WARN / FAIL / SKIP table to its Report tab.

    uv run flyte run scripts/cluster_validation/suite.py validate

    # optional capabilities, each skipped when its flag is empty:
    uv run flyte run scripts/cluster_validation/suite.py validate \
        --gpu T4:1 --queue moderation-api --secret_key HF_TOKEN

For registries that need credentials, export IMAGE_PULL_SECRET=<image_pull secret name>
before `flyte run`; every image and pod then requests it.

Pass `--strict false` to always finish green and just read the report. With strict on
(the default) the run fails when any check FAILs, so it can gate a CI step.

Things that need `flyte.deploy` / `flyte.serve` from a client (apps, trigger firing,
OnArtifact) live in deploy_checks.py next to this file.
"""

import asyncio
import html
import json
import os
import socket
import time
import uuid
from datetime import timedelta

import flyte
import flyte.artifacts as artifacts
import flyte.errors
import flyte.report
from flyte.io import File
from flyte.remote import Artifact

# Artifact deletion isn't implemented server-side yet, so each run leaves one version
# (named after the run) under each of these two fixed names.
PROBE_ARTIFACT = "cluster-validation-probe"
DECLARED_ARTIFACT = "cluster-validation-declared"

PASS, WARN, FAIL, SKIP, INFO = "PASS", "WARN", "FAIL", "SKIP", "INFO"

# ── Environments ──────────────────────────────────────────────────────────────────────
# `probe` runs the small single-purpose tasks; the others each test one image/pod-shape
# property, so they get their own env.

# Name of an `image_pull` secret (flyte create secret --type image_pull ...) for
# deployments whose registry needs credentials. It goes on every image (so the builder
# can push/pull) and every env (so pods can pull at runtime). The env var is also passed
# to the pods, so re-importing this module in a pod builds identical environments.
PULL_SECRET = os.environ.get("IMAGE_PULL_SECRET", "")


def _image(name: str) -> flyte.Image:
    # A name is required: from_debian_base drops registry_secret unless name or registry is set.
    return flyte.Image.from_debian_base(name=name, registry_secret=PULL_SECRET or None)


def _env(name: str, image: flyte.Image | None = None, **kwargs) -> flyte.TaskEnvironment:
    if PULL_SECRET:
        kwargs["secrets"] = [PULL_SECRET]
        kwargs["env_vars"] = {"IMAGE_PULL_SECRET": PULL_SECRET}
    return flyte.TaskEnvironment(name=name, image=image or _image("cv-base"), **kwargs)


probe = _env(
    "cv_probe",
    resources=flyte.Resources(cpu="500m", memory="512Mi"),
)

# Exact limits the `resources` check reads back from the pod's cgroup.
sized = _env(
    "cv_sized",
    resources=flyte.Resources(cpu="2", memory="2Gi"),
)

# Deliberately small, so the `oom` check can blow through it.
tiny = _env(
    "cv_tiny",
    resources=flyte.Resources(cpu="250m", memory="256Mi"),
)

# Exercises the image builder: a package not in the default image.
custom_image = _env(
    "cv_custom_image",
    image=_image("cv-custom-image").with_pip_packages("pyfiglet==1.0.2"),
    resources=flyte.Resources(cpu="500m", memory="512Mi"),
)

# `unionai-reuse` must be in the image, not just on the laptop. One replica, so every
# call lands on the same warm pod and the check can assert that deterministically.
warm_pool = _env(
    "cv_warm_pool",
    image=_image("cv-reuse").with_pip_packages("unionai-reuse>=0.1.15"),
    resources=flyte.Resources(cpu="500m", memory="512Mi"),
    reusable=flyte.ReusePolicy(replicas=1, idle_ttl=timedelta(minutes=2), scaledown_ttl=timedelta(minutes=2)),
)

driver = _env(
    "cv_driver",
    resources=flyte.Resources(cpu="1", memory="1Gi"),
    depends_on=[probe, sized, tiny, custom_image, warm_pool],
)


# ── Child tasks ───────────────────────────────────────────────────────────────────────

@probe.task(cache=flyte.Cache(behavior="auto"))
async def cached_nonce(key: str) -> str:
    """Returns a fresh uuid on execution; a cache hit returns the first call's uuid."""
    return uuid.uuid4().hex


@probe.task(retries=2)
async def fail_first_attempt() -> int:
    attempt = flyte.ctx().attempt_number
    if attempt == 0:
        raise RuntimeError("intentional failure on attempt 0")
    return attempt


@probe.task
async def raise_user_error(message: str) -> str:
    raise ValueError(message)


@probe.task(timeout=timedelta(seconds=20))
async def sleep_past_timeout() -> str:
    await asyncio.sleep(300)
    return "should have timed out"


@tiny.task
async def allocate_past_limit() -> int:
    chunks = []
    for _ in range(64):                 # 64 x 32 MiB = 2 GiB against a 256Mi limit
        chunks.append(bytearray(32 * 1024 * 1024))
    return len(chunks)


@sized.task
async def read_cgroup_limits() -> dict[str, str]:
    """cgroup v2 first, v1 fallback. Values are the raw kernel strings."""
    def read(*paths: str) -> str:
        for p in paths:
            try:
                with open(p) as f:
                    return f.read().strip()
            except OSError:
                continue
        return ""

    return {
        "memory": read("/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory/memory.limit_in_bytes"),
        "cpu": read("/sys/fs/cgroup/cpu.max", "/sys/fs/cgroup/cpu/cpu.cfs_quota_us"),
        "cpu_period": read("/sys/fs/cgroup/cpu/cpu.cfs_period_us"),
    }


@custom_image.task
async def use_custom_package() -> str:
    import pyfiglet
    return pyfiglet.__version__


@warm_pool.task
async def warm_identity() -> str:
    # Module globals survive between calls only when the process is reused.
    global _WARM_CALLS
    _WARM_CALLS = globals().get("_WARM_CALLS", 0) + 1
    return f"{socket.gethostname()}:{os.getpid()}:{_WARM_CALLS}"


@probe.task
async def gpu_probe() -> dict[str, str]:
    import shutil
    import subprocess

    out = {
        "NVIDIA_VISIBLE_DEVICES": os.environ.get("NVIDIA_VISIBLE_DEVICES", ""),
        "dev_nvidia0": str(os.path.exists("/dev/nvidia0")),
        "nvidia_smi": "",
    }
    if shutil.which("nvidia-smi"):
        out["nvidia_smi"] = subprocess.run(["nvidia-smi", "-L"], capture_output=True, text=True).stdout.strip()
    return out


@probe.task
async def where_am_i() -> str:
    return socket.gethostname()


@probe.task
async def secret_length(env_var: str) -> int:
    # Never return the value itself; outputs are visible in the console.
    return len(os.environ.get(env_var, ""))


@probe.task
async def burn_cpu(seconds: int) -> int:
    """Long and busy enough for the Metrics tab to have datapoints (>30s, >1 scrape)."""
    deadline = time.monotonic() + seconds
    ballast = bytearray(256 * 1024 * 1024)   # visible memory usage, too; held until return
    n = 0
    while time.monotonic() < deadline:
        n += sum(i * i for i in range(10_000)) % 7
    return n + len(ballast) // len(ballast)


@probe.task(produces_artifacts=True)
async def declare_artifact(version: str) -> File:
    """Declaration path: the backend, not the SDK, registers the artifact from the output."""
    path = "/tmp/declared.txt"
    with open(path, "w") as f:
        f.write(f"declared {version}\n")
    return artifacts.new(
        await File.from_local(path),
        artifacts.Metadata(name=DECLARED_ARTIFACT, version=version, kind="generic",
                           attrs={"source": "cluster-validation"}),
    )


# ── Checks (run inside the driver task) ───────────────────────────────────────────────

def _err(e: BaseException) -> str:
    return f"{type(e).__name__}: {str(e)[:300]}"


async def check_cache(run_name: str) -> tuple[str, str]:
    first = await cached_nonce(key=run_name)
    second = await cached_nonce(key=run_name)
    if first == second:
        return PASS, "second call with identical inputs returned the cached output"
    return FAIL, f"second call re-executed (got {second[:8]}, expected {first[:8]})"


async def check_retries() -> tuple[str, str]:
    attempt = await fail_first_attempt()
    return PASS, f"attempt 0 failed, succeeded on attempt {attempt}"


async def check_user_error() -> tuple[str, str]:
    marker = f"cv-marker-{uuid.uuid4().hex[:6]}"
    try:
        await raise_user_error(message=marker)
    except flyte.errors.RuntimeUserError as e:
        if marker in str(e):
            return PASS, f"child ValueError surfaced in parent as {type(e).__name__} with its message"
        return WARN, f"surfaced as {type(e).__name__} but the original message was lost: {_err(e)}"
    return FAIL, "child raised but parent saw success"


async def check_timeout() -> tuple[str, str]:
    try:
        await sleep_past_timeout()
    except flyte.errors.TaskTimeoutError as e:
        return PASS, f"20s timeout enforced ({type(e).__name__})"
    except flyte.errors.BaseRuntimeError as e:
        return WARN, f"stopped, but not classified as a timeout: {_err(e)}"
    return FAIL, "task ran past its 20s timeout to completion"


async def check_oom() -> tuple[str, str]:
    try:
        await allocate_past_limit()
    except flyte.errors.OOMError as e:
        return PASS, f"256Mi limit enforced and classified as {type(e).__name__}"
    except flyte.errors.BaseRuntimeError as e:
        return WARN, f"pod died but OOM wasn't detected as such: {_err(e)}"
    return FAIL, "allocated 2GiB under a 256Mi limit; memory limit not enforced"


async def check_resources() -> tuple[str, str]:
    limits = await read_cgroup_limits()
    want_mem = str(2 * 1024 ** 3)
    cpu = limits["cpu"].split()
    if len(cpu) == 2 and cpu[0] != "max":
        cpus = int(cpu[0]) / int(cpu[1])
    elif cpu and cpu[0].lstrip("-").isdigit() and limits["cpu_period"]:
        cpus = int(cpu[0]) / int(limits["cpu_period"]) if int(cpu[0]) > 0 else 0
    else:
        cpus = 0
    detail = f"cgroup memory={limits['memory']} cpu={limits['cpu']!r} (~{cpus:g} cores)"
    if limits["memory"] != want_mem:
        return FAIL, f"expected memory limit {want_mem} (2Gi); {detail}"
    if cpus and abs(cpus - 2) > 0.01:
        return WARN, f"memory OK, CPU limit isn't 2; {detail}"
    return PASS, detail


async def check_custom_image() -> tuple[str, str]:
    version = await use_custom_package()
    return PASS, f"image built and pulled; pyfiglet {version} importable"


async def check_reuse() -> tuple[str, str]:
    ids = [await warm_identity() for _ in range(4)]
    pods = {i.rsplit(":", 2)[0] for i in ids}
    max_calls = max(int(i.rsplit(":", 1)[1]) for i in ids)
    if len(pods) == 1 and max_calls >= 4:
        return PASS, f"4 calls served by one warm process on {pods.pop()}"
    if max_calls > 1:
        return WARN, f"some reuse ({max_calls} calls in one process) across {len(pods)} pod(s): {ids}"
    return FAIL, f"every call got a fresh process: {ids}"


async def check_gpu(gpu: str) -> tuple[str, str]:
    if not gpu:
        return SKIP, "pass --gpu (e.g. T4:1, A100:1, or 1) to test accelerator scheduling"
    info = await gpu_probe.override(resources=flyte.Resources(cpu="1", memory="2Gi", gpu=gpu))()
    if info["nvidia_smi"]:
        return PASS, info["nvidia_smi"]
    if info["dev_nvidia0"] == "True" or info["NVIDIA_VISIBLE_DEVICES"] not in ("", "void", "none"):
        return WARN, f"device present but nvidia-smi unavailable in image: {info}"
    return FAIL, f"scheduled with gpu={gpu} but no GPU visible in the pod: {info}"


async def check_queue(queue: str) -> tuple[str, str]:
    if not queue:
        return SKIP, "pass --queue <name> to test routing to a named queue / cluster pool"
    host = await where_am_i.override(queue=queue)()
    return PASS, f"action routed via queue {queue!r}, ran on {host}"


async def check_secret(secret_key: str) -> tuple[str, str]:
    if not secret_key:
        return SKIP, "pass --secret_key <name> of an existing secret (flyte create secret ...)"
    env_var = "CV_SECRET"
    # override(secrets=) replaces the env's list, so keep the pull secret in it.
    secrets = [flyte.Secret(key=secret_key, as_env_var=env_var)] + ([PULL_SECRET] if PULL_SECRET else [])
    n = await secret_length.override(secrets=secrets)(env_var=env_var)
    if n:
        return PASS, f"secret {secret_key!r} injected as ${env_var} ({n} chars)"
    return FAIL, f"secret {secret_key!r} requested but ${env_var} was empty"


async def check_metrics(seconds: int) -> tuple[str, str]:
    if seconds <= 0:
        return SKIP, "metrics workload disabled (--metrics_seconds 0)"
    await burn_cpu(seconds=seconds)
    return INFO, (f"burn_cpu ran {seconds}s at ~1 core / 256Mi; open that action's Metrics tab "
                  "and confirm CPU and memory curves render (no public SDK API to assert this)")


async def check_artifact_create(project: str, domain: str, version: str) -> tuple[str, str]:
    path = "/tmp/cv-artifact.txt"
    payload = f"cluster validation {version}\n"
    with open(path, "w") as f:
        f.write(payload)
    uploaded = await File.from_local(path)
    # external_ref: without it, in-task create() builds a task-action source the server
    # rejects on some backends (see appendix B).
    created = await Artifact.create.aio(
        uploaded, name=PROBE_ARTIFACT, version=version, kind="generic",
        attrs={"source": "cluster-validation"}, external_ref=uploaded.path,
        project=project, domain=domain,
    )
    fetched = await Artifact.get.aio(PROBE_ARTIFACT, version, project=project, domain=domain)
    if fetched.version != version:
        return FAIL, f"get() returned version {fetched.version}, expected {version}"
    listed = [a.version async for a in Artifact.listall.aio(name=PROBE_ARTIFACT, project=project, domain=domain)]
    if version not in listed:
        return FAIL, f"listall() missing {version}; got {listed[:5]}"
    roundtrip: File = await fetched.to_python()
    local = await roundtrip.download()
    with open(local) as f:
        if f.read() != payload:
            return FAIL, "to_python() content does not match what was published"
    return PASS, f"create -> get -> listall -> to_python round-tripped {created.tracker}"


async def check_artifact_declared(project: str, domain: str, version: str) -> tuple[str, str]:
    await declare_artifact(version=version)
    # Registration happens backend-side after the action completes; give it a moment.
    last = None
    for _ in range(12):
        try:
            art = await Artifact.get.aio(DECLARED_ARTIFACT, version, project=project, domain=domain)
        except Exception as e:
            last = e
            await asyncio.sleep(5)
            continue
        return PASS, f"artifacts.new() output registered by the backend as {art.tracker}"
    return FAIL, f"task with produces_artifacts=True succeeded but nothing registered after 60s: {_err(last)}"


# ── Driver ────────────────────────────────────────────────────────────────────────────

async def _run_check(name: str, coro) -> tuple[str, str, str]:
    started = time.monotonic()
    try:
        with flyte.group(name):
            status, detail = await coro
    except Exception as e:
        status, detail = FAIL, _err(e)
    return name, status, f"{detail}  [{time.monotonic() - started:.0f}s]"


def _render(rows: list[tuple[str, str, str]], header: str) -> str:
    colors = {PASS: "#1a7f37", WARN: "#9a6700", FAIL: "#cf222e", SKIP: "#6e7781", INFO: "#0969da"}
    body = "".join(
        f"<tr><td><b>{html.escape(n)}</b></td>"
        f"<td style='color:{colors[s]};font-weight:600'>{s}</td>"
        f"<td><code>{html.escape(d)}</code></td></tr>"
        for n, s, d in rows
    )
    return (f"<h2>Cluster validation</h2><p>{html.escape(header)}</p>"
            f"<table border='1' cellpadding='6' style='border-collapse:collapse'>"
            f"<tr><th>check</th><th>status</th><th>detail</th></tr>{body}</table>")


@driver.task(report=True)
async def validate(
    gpu: str = "",
    queue: str = "",
    secret_key: str = "",
    metrics_seconds: int = 90,
    strict: bool = True,
) -> str:
    """Run every capability check in parallel; return the results as JSON."""
    action = flyte.ctx().action
    project, domain, run_name = action.project, action.domain, action.run_name
    version = f"{run_name}-{uuid.uuid4().hex[:6]}"

    checks = {
        "cache": check_cache(run_name),
        "retries": check_retries(),
        "user-error": check_user_error(),
        "timeout": check_timeout(),
        "oom": check_oom(),
        "resources": check_resources(),
        "custom-image": check_custom_image(),
        "reusable-containers": check_reuse(),
        "gpu": check_gpu(gpu),
        "queue": check_queue(queue),
        "secret": check_secret(secret_key),
        "metrics-workload": check_metrics(metrics_seconds),
        "artifact-create": check_artifact_create(project, domain, version),
        "artifact-declared": check_artifact_declared(project, domain, version),
    }
    rows = list(await asyncio.gather(*(_run_check(n, c) for n, c in checks.items())))

    counts = {s: sum(1 for _, st, _ in rows if st == s) for s in (PASS, WARN, FAIL, SKIP, INFO)}
    header = f"{project}/{domain} run {run_name}: " + ", ".join(f"{v} {k}" for k, v in counts.items() if v)
    await flyte.report.replace.aio(_render(rows, header), do_flush=True)
    for n, s, d in rows:
        print(f"{s:5} {n:22} {d}")

    if strict and counts[FAIL]:
        failed = ", ".join(n for n, s, _ in rows if s == FAIL)
        raise RuntimeError(f"{counts[FAIL]} check(s) failed: {failed}. See the Report tab.")
    return json.dumps({n: {"status": s, "detail": d} for n, s, d in rows}, indent=2)
