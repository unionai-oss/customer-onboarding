"""Trigger deployment examples: Review Radar's nightly ingest (schedule) and
model revalidation (artifact).

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
from flyte.io import File

env = flyte.TaskEnvironment(
    name="scheduled",
    resources=flyte.Resources(cpu="1", memory="512Mi"),
)

# Must match the artifact name published in 06-model-artifacts §2.
MODEL_NAME = "review-radar-sentiment"


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


# ── Artifact trigger (06 §5): fire whenever a new model version is published. ────
# `OnArtifact(name=...)` fires on ANY new version of that artifact; pass version="v3"
# to fire only on that exact one. `flyte.TriggeredArtifact` binds the artifact that
# fired the trigger to a task input, the way flyte.TriggerTime binds the scheduled
# time above. The artifact name is scoped to this task's project and domain.
@env.task(
    triggers=flyte.Trigger(
        "revalidate_on_new_model",
        flyte.OnArtifact(name=MODEL_NAME),
        inputs={"model": flyte.TriggeredArtifact, "min_accuracy": 0.85},
        auto_activate=True,
    )
)
async def revalidate_model(model: File, min_accuracy: float) -> str:
    """Runs automatically whenever a new version of MODEL_NAME is published.

    The real version scores the new model on a holdout set and, if it clears
    min_accuracy, republishes it with attrs={"stage": "prod"} to promote it.
    """
    local = await model.download()
    return f"revalidated {local} against min_accuracy={min_accuracy}"


if __name__ == "__main__":
    flyte.init_from_config()
    deployment = flyte.deploy(env)
    print(deployment)
