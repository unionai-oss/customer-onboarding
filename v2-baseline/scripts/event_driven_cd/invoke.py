"""Event-driven CD: the caller (your Lambda).

The v1 equivalent of what this replaces:

    lp = remote.fetch_active_launchplan(project, domain, "my_lp")   # no version
    remote.execute(lp, inputs={...})

The caller names a *release*, never a version, and its code never changes across a
release or a rollback. Task inputs are passed as `--<param-name>`, the same shape
`flyte run` uses. Run from the v2-baseline root:

    python scripts/event_driven_cd/invoke.py --object-key s3://bucket/obj
    python scripts/event_driven_cd/invoke.py --object-key s3://bucket/obj --mode pointer

`label` (default)
    The release name is a version label. Operators move it by re-deploying code
    under that label. Requires pipeline.py.

`pointer`
    The release name is a trigger, which stores the version it designates.
    Operators move it with repoint.py, without redeploying. Requires
    pointer_pipeline.py.

Both print the resolved version and code bundle before launching, so you can see
exactly which code the release currently serves.
"""

import argparse
import asyncio
from datetime import datetime, timezone

import flyte
import flyte.remote as remote

LABEL_TASK = "event_driven.ingest"
POINTER_TASK = "event_driven_pointer.ingest"
RELEASE = "prod"


def code_bundle(task: remote.TaskDetails) -> str:
    """The content-hashed code bundle a version serves.

    This is the platform's own record of *which code* sits behind a name, so
    nothing has to be duplicated into the source to keep track of releases.
    Compare it across tags to see what a label currently points at.
    """
    args = list(task.pb2.spec.task_template.container.args)
    if "--tgz" not in args:
        return "<baked into image>"
    return args[args.index("--tgz") + 1].rsplit("/", 1)[-1]


async def resolve(mode: str) -> tuple[str, remote.TaskDetails]:
    """Turn the release name into a concrete version. The caller never sees this."""
    if mode == "label":
        return RELEASE, await remote.Task.get(LABEL_TASK, version=RELEASE).fetch.aio()

    trigger = await remote.Trigger.get.aio(name=RELEASE, task_name=POINTER_TASK)
    version = trigger.pb2.spec.task_version
    return version, await remote.Task.get(POINTER_TASK, version=version).fetch.aio()


async def main() -> None:
    p = argparse.ArgumentParser(description="Fire the pipeline by release name.")
    p.add_argument("--object-key", required=True, help="task input: the object that triggered the event")
    p.add_argument("--mode", choices=("label", "pointer"), default="label")
    args = p.parse_args()

    # In Lambda: flyte.init(endpoint=..., api_key=..., project=..., domain=...)
    flyte.init_from_config()

    version, task = await resolve(args.mode)
    print(f"release {RELEASE!r} -> version {version!r}, bundle {code_bundle(task)}")

    run = await flyte.run.aio(
        task, object_key=args.object_key, event_time=datetime.now(timezone.utc)
    )
    print(f"run: {run.name}  {run.url}")


if __name__ == "__main__":
    asyncio.run(main())
