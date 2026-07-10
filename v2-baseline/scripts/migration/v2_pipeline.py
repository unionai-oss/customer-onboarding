"""The same pipeline as v1_pipeline.py, re-authored for Flyte **v2**.

Run remotely:

    python scripts/migration/v2_pipeline.py

Every construct maps to a v1 counterpart — the mapping table and the
walkthrough live in 08-v1-to-v2-migration.ipynb.
"""

from datetime import timedelta
from functools import partial
from typing import List

import flyte
from flyte import Cache
from flyte.io import File

# ---- image: flyte.Image fluent builder (was: ImageSpec) ----------------------
image = (
    flyte.Image.from_debian_base(name="migration-demo", python_version=(3, 12))
    .with_pip_packages("numpy", "scikit-learn", "unionai-reuse>=0.1.15")
)

# ---- warm workers: ReusePolicy (was: ActorEnvironment) -----------------------
predict_env = flyte.TaskEnvironment(
    name="predict_pool",
    image=image,
    resources=flyte.Resources(cpu="1", memory="1Gi"),
    reusable=flyte.ReusePolicy(
        replicas=(1, 4),                     # autoscaling (v1: fixed replica_count)
        concurrency=1,                       # CPU-bound prediction
        scaledown_ttl=timedelta(minutes=5),
        idle_ttl=timedelta(minutes=10),
    ),
)

train_env = flyte.TaskEnvironment(
    name="train",
    image=image,
    resources=flyte.Resources(cpu="2", memory="4Gi"),
)

main_env = flyte.TaskEnvironment(
    name="pipeline",
    image=image,
    resources=flyte.Resources(cpu="1", memory="1Gi"),
    depends_on=[train_env, predict_env],
)


# ---- tasks --------------------------------------------------------------------
@train_env.task(cache=Cache(behavior="override", version_override="v1"))
async def train_model(examples: int, epochs: int) -> File:
    # (was: @task(cache=True, cache_version="v1") returning FlyteFile)
    import numpy as np

    rng = np.random.default_rng(0)
    weights = rng.normal(size=(epochs,))
    np.save("model.npy", weights)
    return await File.from_local("model.npy")


from functools import lru_cache


@lru_cache(maxsize=1)
def load_model(path: str):
    """Load once per warm pod (was: @actor_cache). Survives across executions
    because the ReusePolicy keeps the Python process alive."""
    import numpy as np

    return np.load(path)


@predict_env.task
async def predict(item: int, model: File) -> float:
    import pathlib

    local = pathlib.Path("/tmp/model.npy")
    if not local.exists():                    # first execution on this pod downloads
        await model.download(local)
    weights = load_model(str(local))
    return float(item * weights.sum())


# ---- composition: plain async Python (was: @workflow + map) --------------------
@main_env.task
async def pipeline(examples: int = 1000, epochs: int = 5) -> List[float]:
    model = await train_model(examples=examples, epochs=epochs)

    # v1: map(predict, bound_inputs={"model": model})(item=[...])
    fn = partial(predict, model=model)
    results: List[float] = []
    async for r in flyte.map.aio(fn, list(range(10)), return_exceptions=True):
        if isinstance(r, Exception):
            raise r
        results.append(r)
    return results


if __name__ == "__main__":
    flyte.init_from_config()
    run = flyte.run(pipeline, examples=1000, epochs=5)
    print(run.url)
    run.wait()
