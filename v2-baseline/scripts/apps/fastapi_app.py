"""Review Radar serving app for 07-serving.

Serves the sentiment model trained by `training.train_model` (chapter 06). At
deploy time, Flyte resolves the latest run of that task, downloads the model
artifact, and exposes its path via the MODEL_PATH env var. If no training run
exists yet, the app falls back to a keyword heuristic so the workshop can run
chapters out of order.

Lives in a .py file (not a notebook cell) because app deployment is not
supported from interactive sessions. Deploy from the notebook with:

    !python scripts/apps/fastapi_app.py
"""

import os
import time
from contextlib import asynccontextmanager

import flyte
import flyte.app
from fastapi import FastAPI
from flyte.app import Parameter, RunOutput
from flyte.app.extras import FastAPIAppEnvironment
from pydantic import BaseModel

MODEL_PATH_ENV = "MODEL_PATH"


def load_model():
    """Load the trained pipeline if present, else a keyword-heuristic fallback."""
    path = os.environ.get(MODEL_PATH_ENV, "")
    if path and os.path.exists(path):
        import joblib
        return joblib.load(path), "trained"

    class Heuristic:
        def predict_proba(self, texts):
            out = []
            for t in texts:
                pos = sum(w in t.lower() for w in ("love", "solid", "exceeded"))
                neg = sum(w in t.lower() for w in ("terrible", "disappointed", "broken"))
                p = 0.5 + 0.15 * (pos - neg)
                p = min(max(p, 0.01), 0.99)
                out.append([1 - p, p])
            return out

    return Heuristic(), "heuristic-fallback"


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.model, app.state.model_kind = load_model()   # load ONCE at startup
    yield


app = FastAPI(title="Review Radar API", lifespan=lifespan, version="1.0.0")


class ScoreRequest(BaseModel):
    text: str


class ScoreResponse(BaseModel):
    positive_probability: float
    model_kind: str
    latency_ms: float


@app.get("/health")
async def health() -> dict:
    return {"status": "healthy", "model": app.state.model_kind}


@app.post("/score", response_model=ScoreResponse)
async def score(req: ScoreRequest) -> ScoreResponse:
    started = time.perf_counter()
    proba = app.state.model.predict_proba([req.text])[0][1]
    return ScoreResponse(
        positive_probability=round(float(proba), 4),
        model_kind=app.state.model_kind,
        latency_ms=(time.perf_counter() - started) * 1000,
    )


app_env = FastAPIAppEnvironment(
    name="review-radar-api",
    app=app,
    parameters=[
        # Resolve the model from the latest run of the chapter-06 training task
        # and expose its downloaded path to the app via MODEL_PATH.
        Parameter(
            name="model",
            value=RunOutput(
                type="file",
                task_name="training.train_model",
                task_auto_version="latest",
            ),
            download=True,
            env_var=MODEL_PATH_ENV,
        ),
    ],
    image=flyte.Image.from_debian_base(python_version=(3, 12)).with_pip_packages(
        "fastapi", "uvicorn", "pydantic",
        "scikit-learn==1.5.2", "joblib==1.4.2",
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
    if os.environ.get("SKIP_MODEL_PARAM"):     # deploy before any training run exists
        app_env.parameters = []
    deployment = flyte.serve(app_env)
    print(f"Deployed: {deployment.url}")
    print(f"Swagger:  {deployment.url}/docs")
