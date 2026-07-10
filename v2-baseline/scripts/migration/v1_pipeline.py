"""REFERENCE ONLY — Flyte/Union **v1** pipeline (requires `union` v1, not in
this workshop's requirements). A trimmed version of the patterns in
../../../v1-onboarding: @workflow, @task, ActorEnvironment, @actor_cache,
map with bound_inputs, ImageSpec.

Read side-by-side with v2_pipeline.py in 08-v1-to-v2-migration.ipynb.
"""

from typing import List

import numpy as np
from union import (
    ActorEnvironment,
    FlyteFile,
    ImageSpec,
    Resources,
    actor_cache,
    map,
    task,
    workflow,
)

# ---- image: ImageSpec, built by the Union remote builder --------------------
container_image = ImageSpec(
    builder="union",
    packages=["numpy", "scikit-learn"],
)

# ---- warm workers: ActorEnvironment (v1's reusable containers) --------------
actor = ActorEnvironment(
    name="predict-actor",
    replica_count=4,                 # fixed replica count (no autoscaling)
    ttl_seconds=300,                 # idle timeout, max 900s
    requests=Resources(cpu="1", mem="1Gi"),
    container_image=container_image,
)


# ---- tasks -------------------------------------------------------------------
@task(container_image=container_image, requests=Resources(cpu="2", mem="4Gi"),
      cache=True, cache_version="v1")
def train_model(examples: int, epochs: int) -> FlyteFile:
    rng = np.random.default_rng(0)
    weights = rng.normal(size=(epochs,))
    np.save("model.npy", weights)
    return FlyteFile("model.npy")


@actor_cache                          # load once per warm actor replica
def load_model(model_path: str) -> np.ndarray:
    return np.load(model_path)


@actor.task
def predict(item: int, model: FlyteFile) -> float:
    weights = load_model(model.download())
    return float(item * weights.sum())


# ---- composition: compile-time DSL -------------------------------------------
@workflow
def wf(examples: int = 1000, epochs: int = 5) -> List[float]:
    model = train_model(examples=examples, epochs=epochs)
    # v1 map task with a constant input bound across all items
    return map(predict, bound_inputs={"model": model})(item=list(range(10)))
