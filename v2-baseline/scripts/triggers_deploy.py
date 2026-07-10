"""Scheduled-task deployment example: Review Radar's nightly ingest.

Triggers require a *deployment* (a versioned task registered on the control
plane), and deployment is not supported from interactive notebook sessions —
which is why this lives here. Deploy with:

    python scripts/triggers_deploy.py

Then manage the trigger:

    flyte get trigger
    flyte update trigger nightly_ingest scheduled.nightly_ingest --deactivate
"""

from datetime import datetime

import flyte

env = flyte.TaskEnvironment(
    name="scheduled",
    resources=flyte.Resources(cpu="1", memory="512Mi"),
)


@env.task(
    triggers=flyte.Trigger(
        "nightly_ingest",
        flyte.Cron("0 6 * * *", timezone="UTC"),
        inputs={"batch_date": flyte.TriggerTime},
        auto_activate=True,
    )
)
async def nightly_ingest(batch_date: datetime) -> str:
    # In the real pipeline this calls the chapter-02 ingest for yesterday's reviews.
    return f"ingested review batch for {batch_date.date()}"


if __name__ == "__main__":
    flyte.init_from_config()
    deployment = flyte.deploy(env)
    print(deployment)
