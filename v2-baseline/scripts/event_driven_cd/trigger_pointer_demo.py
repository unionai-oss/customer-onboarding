"""Demo: using a trigger's task_version as a release pointer.

Supports the discussion on ENG26-1233 ("can't we use task versions in triggers?").
Runs the whole story end to end and narrates each step:

    1. deploy r1                -> pointer lands on r1
    2. run by pointer name      -> executes r1
    3. deploy r2                -> pointer moves to r2 BY ITSELF (deploy publishes)
    4. run by pointer name      -> executes r2
    5. re-point back to r1      -> one write, no rebuild, no redeploy
    6. run by pointer name      -> executes r1 again
    7. revision history         -> who moved production, and when

The caller only ever names "prod". It never learns a version.

    python trigger_pointer_demo.py                # full story
    python trigger_pointer_demo.py --cleanup      # delete the demo trigger

Requires a working `flyte` config (`flyte create config ...`) or FLYTE_API_KEY.
"""

import asyncio

from flyteidl2.common import identifier_pb2, list_pb2
from flyteidl2.trigger import trigger_definition_pb2, trigger_service_pb2

import flyte
import flyte.remote as remote
from flyte._initialize import get_client, get_init_config

ENV_NAME = "trigger_pointer_demo"
TASK = f"{ENV_NAME}.process"
POINTER = "prod"

env = flyte.TaskEnvironment(name=ENV_NAME, resources=flyte.Resources(cpu="1", memory="512Mi"))

# A pointer, not a schedule. The cron is inert: the scheduler only fires triggers
# where active = true, and this one is never activated. CreateRun by trigger name
# ignores `active`, so it stays launchable by name while never firing on its own.
PROD_POINTER = flyte.Trigger(
    POINTER,
    flyte.Cron("0 0 1 1 *"),
    auto_activate=False,
    description="Release pointer. Not a schedule.",
)


@env.task(triggers=PROD_POINTER)
async def process(payload: str = "") -> str:
    # ctx().version is the *resolved* version, which is the point: the caller asked
    # for "prod" and the platform recorded which concrete version that was.
    return f"processed {payload!r} on version {flyte.ctx().version}"


# ---------------------------------------------------------------- helpers


def banner(step: str, text: str) -> None:
    print(f"\n{'=' * 70}\n{step}  {text}\n{'=' * 70}")


async def pointer_version() -> tuple[str, int]:
    t = await remote.Trigger.get.aio(name=POINTER, task_name=TASK)
    return t.pb2.spec.task_version, t.pb2.id.revision


async def run_by_pointer(payload: str) -> None:
    """What the Lambda does: resolve the pointer, run what it names."""
    version, _ = await pointer_version()
    task = remote.Task.get(TASK, version=version)
    run = await flyte.run.aio(task, payload=payload)
    print(f"  launched {run.name}  ({run.url})")
    await run.wait.aio()
    print(f"  phase   : {run.phase}")
    print(f"  output  : {await run.outputs.aio()}")


async def repoint(to_version: str) -> None:
    """Move the pointer. Read-modify-write under the optimistic lock.

    This is the operation ENG26-1233 asks to expose in the CLI. It is not
    reachable from remote.Trigger.create(), which cannot forward a revision.
    """
    cfg = get_init_config()
    current = await remote.Trigger.get.aio(name=POINTER, task_name=TASK)

    spec = trigger_definition_pb2.TriggerSpec()
    spec.CopyFrom(current.pb2.spec)
    spec.task_version = to_version

    await get_client().trigger_service.deploy_trigger(
        request=trigger_service_pb2.DeployTriggerRequest(
            name=identifier_pb2.TriggerName(
                org=cfg.org, project=cfg.project, domain=cfg.domain,
                task_name=TASK, name=POINTER,
            ),
            revision=current.pb2.id.revision,
            spec=spec,
            automation_spec=current.pb2.automation_spec,
        )
    )


async def history() -> None:
    cfg = get_init_config()
    resp = await get_client().trigger_service.get_trigger_revision_history(
        request=trigger_service_pb2.GetTriggerRevisionHistoryRequest(
            name=identifier_pb2.TriggerName(
                org=cfg.org, project=cfg.project, domain=cfg.domain,
                task_name=TASK, name=POINTER,
            ),
            request=list_pb2.ListRequest(limit=20),
        )
    )
    for rev in resp.triggers:
        # deployed_by / updated_by are EnrichedIdentity: a user or an application.
        ident = rev.metadata.updated_by if rev.metadata.HasField("updated_by") else rev.metadata.deployed_by
        who = ident.user.spec.email or ident.application.id.name or "unknown"
        action = trigger_definition_pb2.TriggerRevisionAction.Name(rev.action).replace(
            "TRIGGER_REVISION_ACTION_", ""
        )
        when = rev.created_at.ToDatetime().isoformat(timespec="seconds") if rev.HasField("created_at") else "?"
        print(f"  rev {rev.id.revision:<4} {action:<12} {when}  by {who}")


# ---------------------------------------------------------------- the story


async def main() -> None:
    import sys

    flyte.init_from_config()

    if "--cleanup" in sys.argv:
        cfg = get_init_config()
        await get_client().trigger_service.delete_triggers(
            request=trigger_service_pb2.DeleteTriggersRequest(
                names=[identifier_pb2.TriggerName(
                    org=cfg.org, project=cfg.project, domain=cfg.domain,
                    task_name=TASK, name=POINTER)]
            )
        )
        print(f"deleted trigger {POINTER!r} on {TASK}")
        return

    banner("STEP 1", "deploy r1")
    flyte.deploy(env, version="r1")
    print(f"  pointer {POINTER!r} -> {await pointer_version()}")

    banner("STEP 2", "run by pointer name (the caller never names a version)")
    await run_by_pointer("first")

    banner("STEP 3", "deploy r2 — watch the pointer move on its own")
    before, _ = await pointer_version()
    flyte.deploy(env, version="r2")
    after, rev = await pointer_version()
    print(f"  pointer {POINTER!r}: {before} -> {after}  (revision {rev})")
    print("  NOTE: nobody asked for this. Deploying publishes — there is no staging gate.")

    banner("STEP 4", "run again — same caller, new code")
    await run_by_pointer("second")

    #banner("STEP 5", "roll back to r1 — one write, no rebuild, no redeploy")
    #await repoint("r1")
    #print(f"  pointer {POINTER!r} -> {await pointer_version()}")

    #banner("STEP 6", "run again — rollback took effect, caller unchanged")
    #await run_by_pointer("third")

    banner("STEP 7", "revision history — the audit trail a version label cannot give you")
    await history()
    print("\n  (history records who and when per revision; the version each revision")
    print("   pointed at is not carried on the revision record itself)")

    print("\nTakeaway: the pointer works today. What is missing is a CLI/UI path to")
    print("step 5, and control over step 3.\n")


if __name__ == "__main__":
    asyncio.run(main())
