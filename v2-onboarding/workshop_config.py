"""Client-side configuration loader for the workshop notebooks.

================================  WARNING  ================================
CLIENT-SIDE ONLY. This module exists on your laptop, not in task images.

Never reference `workshop_config` (or any local module) from *inside* a task
body. Notebook-defined tasks are shipped to the cluster as pickled code, and
pickle stores local-module functions by reference — the import would fail
remotely with ModuleNotFoundError. Pass values from here into tasks as plain
task inputs instead.
===========================================================================

Usage in a notebook cell:

    from workshop_config import WS
    print(WS.project, WS.domain, WS.registry)
"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()  # reads .env sitting next to the notebooks


@dataclass(frozen=True)
class WorkshopSettings:
    project: str
    domain: str
    registry: str
    gcs_bucket: str
    bq_project: str
    bq_dataset: str
    hf_model_id: str


WS = WorkshopSettings(
    project=os.getenv("WORKSHOP_PROJECT", "onboarding"),
    domain=os.getenv("WORKSHOP_DOMAIN", "development"),
    registry=os.getenv("GAR_REGISTRY", ""),
    gcs_bucket=os.getenv("GCS_BUCKET", ""),
    bq_project=os.getenv("BQ_PROJECT", ""),
    bq_dataset=os.getenv("BQ_DATASET", ""),
    hf_model_id=os.getenv("HF_MODEL_ID", "Qwen/Qwen2.5-0.5B-Instruct"),
)


def preflight() -> "WorkshopSettings":
    """Print the resolved settings and flag anything missing. Returns WS."""
    missing = [f for f in ("registry", "gcs_bucket") if not getattr(WS, f)]
    print(f"project={WS.project} domain={WS.domain}")
    print(f"registry={WS.registry or '<unset>'} gcs_bucket={WS.gcs_bucket or '<unset>'}")
    if missing:
        print(f"NOTE: unset in .env: {', '.join(missing)} — some cells will need them.")
    return WS
