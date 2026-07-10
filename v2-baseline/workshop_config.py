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


def _get(*names: str, default: str = "") -> str:
    """First set env var among `names` (legacy names kept for older .env files)."""
    for n in names:
        v = os.getenv(n)
        if v:
            return v
    return default


@dataclass(frozen=True)
class WorkshopSettings:
    project: str
    domain: str
    registry: str
    object_store: str
    warehouse_project: str
    warehouse_dataset: str
    hf_model_id: str


WS = WorkshopSettings(
    project=_get("WORKSHOP_PROJECT", default="onboarding"),
    domain=_get("WORKSHOP_DOMAIN", default="development"),
    registry=_get("IMAGE_REGISTRY", "GAR_REGISTRY"),
    object_store=_get("OBJECT_STORE_URI", "GCS_BUCKET"),
    warehouse_project=_get("WAREHOUSE_PROJECT", "BQ_PROJECT"),
    warehouse_dataset=_get("WAREHOUSE_DATASET", "BQ_DATASET"),
    hf_model_id=_get("HF_MODEL_ID", default="Qwen/Qwen2.5-0.5B-Instruct"),
)


def preflight() -> "WorkshopSettings":
    """Print the resolved settings and flag anything missing. Returns WS."""
    print(f"project={WS.project} domain={WS.domain}")
    print(f"registry={WS.registry or '<managed/unset>'} object_store={WS.object_store or '<unset>'}")
    if not WS.object_store:
        print("NOTE: OBJECT_STORE_URI unset — the from_existing_remote cells in 02 need it.")
    return WS
