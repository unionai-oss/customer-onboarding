"""Move a trigger to a different deployed task version.

Rollback for the trigger-based release flow (pointer_pipeline.py): points `prod`
at an already-deployed version without rebuilding or redeploying anything.

Deploying always points a task's triggers at the version being deployed, so this
is only needed to go *backwards*. Arguments mirror `flyte update trigger`.

    python scripts/event_driven_cd/repoint.py prod event_driven_pointer.ingest --show
    python scripts/event_driven_cd/repoint.py prod event_driven_pointer.ingest --to r1

There is no `flyte` subcommand for this yet, which is why it is a script.
"""

import argparse
import asyncio

from flyteidl2.common import identifier_pb2
from flyteidl2.trigger import trigger_definition_pb2, trigger_service_pb2

import flyte
import flyte.remote as remote
from flyte._initialize import get_client, get_init_config




async def show(name: str, task_name: str) -> str:
    """Print which version the pointer currently designates."""
    trig = await remote.Trigger.get.aio(name=name, task_name=task_name)
    version = trig.pb2.spec.task_version
    print(f"pointer {name!r} -> task {task_name} version {version!r}")
    print(f"  revision: {trig.pb2.id.revision}")
    print(f"  active (schedule enabled): {trig.pb2.spec.active}")
    return version


async def repoint(name: str, task_name: str, to_version: str) -> None:
    """Re-point the trigger at `to_version`."""
    cfg = get_init_config()

    # Read the current revision, change only the version, write it back.
    current = await remote.Trigger.get.aio(name=name, task_name=task_name)
    if current.pb2.spec.task_version == to_version:
        print(f"pointer {name!r} already at {to_version!r}; nothing to do")
        return

    # Fail loudly if the target was never deployed, rather than pointing at a
    # version that cannot be launched.
    await remote.Task.get(task_name, version=to_version).fetch.aio()

    spec = trigger_definition_pb2.TriggerSpec()
    spec.CopyFrom(current.pb2.spec)
    spec.task_version = to_version

    await get_client().trigger_service.deploy_trigger(
        request=trigger_service_pb2.DeployTriggerRequest(
            name=identifier_pb2.TriggerName(
                org=cfg.org,
                project=cfg.project,
                domain=cfg.domain,
                task_name=task_name,
                name=name,
            ),
            revision=current.pb2.id.revision,
            spec=spec,
            automation_spec=current.pb2.automation_spec,
        )
    )
    print(f"pointer {name!r}: {current.pb2.spec.task_version!r} -> {to_version!r}")


async def main() -> None:
    # Argument shape mirrors `flyte update trigger NAME TASK_NAME [OPTIONS]`.
    p = argparse.ArgumentParser(
        description="Re-point a trigger at an already-deployed task version.",
        epilog="mirrors: flyte update trigger NAME TASK_NAME --activate|--deactivate",
    )
    p.add_argument("name", help="trigger name, e.g. prod")
    p.add_argument("task_name", help="task name, e.g. event_driven_pointer.ingest")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--show", action="store_true", help="print the current target")
    g.add_argument("--to", metavar="VERSION", help="re-point at this deployed version")
    args = p.parse_args()

    flyte.init_from_config()
    if args.show:
        await show(args.name, args.task_name)
    else:
        await repoint(args.name, args.task_name, args.to)


if __name__ == "__main__":
    asyncio.run(main())
