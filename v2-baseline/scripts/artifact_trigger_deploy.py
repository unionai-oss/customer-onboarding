"""Artifact trigger for 06-model-artifacts §5: revalidate on every new model version.

Triggers need a *deployed* task, and deployment is not supported from interactive
notebook sessions — which is why this lives here. Deploy with:

    python scripts/artifact_trigger_deploy.py

Then publish a new version of the artifact (06 §5) and this task runs on its own.
Inspect or disable it with:

    flyte get trigger
    flyte update trigger revalidate_on_new_model model_ops.revalidate_model --deactivate
"""

import flyte
from flyte.io import File

env = flyte.TaskEnvironment(
    name="model_ops",
    resources=flyte.Resources(cpu="1", memory="512Mi"),
)

# Must match the artifact name published in 06-model-artifacts §2.
MODEL_NAME = "review-radar-sentiment"


# `OnArtifact(name=...)` fires on ANY new version of that artifact; pass version="v3"
# to fire only on that exact one. `flyte.TriggeredArtifact` binds the artifact that
# fired the trigger to a task input, the way `flyte.TriggerTime` binds the scheduled
# time for a Cron trigger. The artifact name is scoped to this task's project and
# domain.
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
    print(flyte.deploy(env))
