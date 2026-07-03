"""FastAPI inference app for 07-apps-and-inference.

Lives in a .py file (not a notebook cell) because app deployment is not
supported from interactive sessions. Deploy it from the notebook with:

    !python scripts/apps/fastapi_app.py

or from a shell:

    python scripts/apps/fastapi_app.py
"""

import time

import flyte
import flyte.app
from fastapi import FastAPI
from flyte.app.extras import FastAPIAppEnvironment
from pydantic import BaseModel

app = FastAPI(
    title="Workshop scoring API",
    description="Minimal real-time inference endpoint deployed as a Union app",
    version="1.0.0",
)


class ScoreRequest(BaseModel):
    text: str


class ScoreResponse(BaseModel):
    score: float
    latency_ms: float


@app.get("/health")
async def health() -> dict:
    return {"status": "healthy"}


@app.post("/score", response_model=ScoreResponse)
async def score(req: ScoreRequest) -> ScoreResponse:
    started = time.perf_counter()
    # Stand-in for real model inference. With a real model, load it once at
    # startup (FastAPI lifespan) — never per request.
    value = float(len(req.text)) * 2.0
    return ScoreResponse(score=value, latency_ms=(time.perf_counter() - started) * 1000)


app_env = FastAPIAppEnvironment(
    name="workshop-scoring-api",
    app=app,
    image=flyte.Image.from_debian_base(python_version=(3, 12)).with_pip_packages(
        "fastapi", "uvicorn", "pydantic"
    ),
    resources=flyte.Resources(cpu="1", memory="1Gi"),
    scaling=flyte.app.Scaling(
        replicas=(0, 2),        # scale to zero when idle
        scaledown_after=300,    # after 5 minutes without traffic
    ),
    requires_auth=False,        # workshop only — real deployments keep auth on
)


if __name__ == "__main__":
    flyte.init_from_config()
    deployment = flyte.serve(app_env)
    print(f"Deployed: {deployment.url}")
    print(f"Swagger:  {deployment.url}/docs")
