"""The same pipeline as v1_pipeline.py, re-authored for Flyte v2.

Run remotely:  python scripts/migration/v2_pipeline.py
The construct-by-construct mapping lives in 08-v1-to-v2-migration.ipynb.
"""

from datetime import timedelta
from functools import lru_cache, partial
from typing import List

import flyte
from flyte import Cache
from flyte.io import File

# ---- image (was: ImageSpec) --------------------------------------------------
image = flyte.Image.from_debian_base(python_version=(3, 12)).with_pip_packages(
    "numpy", "scikit-learn", "unionai-reuse>=0.1.15"
)

# ---- warm workers: ReusePolicy (was: ActorEnvironment) -----------------------
predict_env = flyte.TaskEnvironment(
    name="predict_pool",
    image=image,
    resources=flyte.Resources(cpu="1", memory="1Gi"),
    reusable=flyte.ReusePolicy(replicas=(1, 4), concurrency=1,
                               scaledown_ttl=timedelta(minutes=5)),
)

# ---- everything else (was: the default @task env + @workflow) ----------------
env = flyte.TaskEnvironment(
    name="migration",
    image=image,
    resources=flyte.Resources(cpu="2", memory="4Gi"),
    depends_on=[predict_env],
)


@env.task(cache=Cache(behavior="override", version_override="v1"))
async def train_model(examples: int, epochs: int) -> File:
    import numpy as np
    np.save("model.npy", np.random.default_rng(0).normal(size=(epochs,)))
    return await File.from_local("model.npy")


@lru_cache(maxsize=1)                      # load once per warm pod (was: @actor_cache)
def load_model(path: str):
    import numpy as np
    return np.load(path)


@predict_env.task
async def predict(item: int, model: File) -> float:
    path = await model.download("/tmp/model.npy")   # load_model caches the parse per pod
    return float(item * load_model(path).sum())


# ---- composition: plain async Python (was: @workflow + map) ------------------
@env.task
async def pipeline(examples: int = 1000, epochs: int = 5) -> List[float]:
    model = await train_model(examples=examples, epochs=epochs)
    fn = partial(predict, model=model)     # v1: map(predict, bound_inputs={"model": model})
    return [r async for r in flyte.map.aio(fn, list(range(10)))]


if __name__ == "__main__":
    flyte.init_from_config()
    flyte.run(pipeline, examples=1000, epochs=5).wait()
