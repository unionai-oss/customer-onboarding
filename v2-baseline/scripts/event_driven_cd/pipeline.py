"""Event-driven CD: the task an external caller fires.

An external caller (Lambda, EventBridge, webhook) fires this pipeline and must not
know a version, while you keep control over which version it actually runs.

The mechanism is a **version label**. Task versions are mutable, so re-deploying an
existing version swaps its code in place. Deploy each release twice: once under an
immutable tag that is a permanent record, once under a label the caller pins.

    version "r1"    <- immutable; never overwritten
    version "r2"    <- immutable; never overwritten
    version "prod"  <- overwritten each release; the caller pins this

Run from the v2-baseline root:

    # release r1
    flyte deploy --version r1   scripts/event_driven_cd/pipeline.py env
    flyte deploy --version prod scripts/event_driven_cd/pipeline.py env

    # release r2 — production follows, the caller is untouched
    flyte deploy --version r2   scripts/event_driven_cd/pipeline.py env
    flyte deploy --version prod scripts/event_driven_cd/pipeline.py env

    # roll back — check out the older commit, re-publish under the label
    flyte deploy --version prod scripts/event_driven_cd/pipeline.py env

The label deploy re-uploads an identical code bundle. If your images have code baked
in, add `--copy-style none` to it and it becomes a metadata-only write. Do not use
`--copy-style none` with the images defined here: with no bundle to ship, the
labelled version would have no code to run.

See pointer_pipeline.py for the trigger-based alternative.
"""

from datetime import datetime, timezone

import flyte

env = flyte.TaskEnvironment(
    name="event_driven",
    resources=flyte.Resources(cpu="1", memory="512Mi"),
)

EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


@env.task
async def ingest(object_key: str = "", event_time: datetime = EPOCH) -> str:
    """Stand-in for the real event-driven pipeline body."""
    return f"processed {object_key} (event at {event_time.isoformat()}) as version {flyte.ctx().version}"
