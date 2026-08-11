"""Event-driven CD, alternative: a trigger as a named pointer.

Use this instead of pipeline.py when you need either:

  - **rollback without rebuilding** — moving the pointer is one write, so it works
    even when the old code no longer builds, and it cannot overwrite the tag you
    are rolling back to
  - **a history of releases** — every move is a recorded revision with an author,
    rather than only "who deployed last"

Otherwise prefer pipeline.py: it uses only `flyte deploy` and needs no extra tools.

The trigger here is a pointer, not a schedule. It is deployed inactive so it never
fires on its own, but stays launchable by name. The cron expression is inert and
exists only because a trigger currently requires a schedule.

Task parameters have defaults because a trigger must supply a value for every
parameter without one. Prefer defaults over trigger `inputs=` when an external
caller provides the real payload, since a trigger that declares its own inputs
overrides what the caller passes.

This uses its own environment name so it does not collide with pipeline.py.
Deploying a task without its trigger declared removes the trigger, so the two
designs must not share a task name.

Run from the v2-baseline root. Deploying points the trigger at the new version:

    flyte deploy --version r1 scripts/event_driven_cd/pointer_pipeline.py env
    python scripts/event_driven_cd/repoint.py prod event_driven_pointer.ingest --show

To move the pointer without redeploying, see repoint.py.
"""

from datetime import datetime, timezone

import flyte

env = flyte.TaskEnvironment(
    name="event_driven_pointer",
    resources=flyte.Resources(cpu="1", memory="512Mi"),
)

EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)

PROD_POINTER = flyte.Trigger(
    "prod",
    flyte.Cron("0 0 1 1 *"),  # inert: never activated, never fires
    auto_activate=False,
    description="Production pointer for the event-driven ingest. Not a schedule.",
)


@env.task(triggers=PROD_POINTER)
async def ingest(object_key: str = "", event_time: datetime = EPOCH) -> str:
    """Same body as pipeline.py; only the release mechanism differs.

    Here `flyte.ctx().version` is meaningful — the trigger resolves to a real tag
    like "r1" — because the pointer stores the version rather than being one.
    """
    return f"processed {object_key} (event at {event_time.isoformat()}) as version {flyte.ctx().version}"
