"""Optional vLLM LLM-serving add-on for 07-serving.

Requires a GPU schedulable in the deployment (an L4/L40s/T4-class device is
plenty for the default 0.5B model — adjust `gpu=` to what the deployment
exposes; see appendix A). Deploy from the notebook / shell:

    python scripts/apps/vllm_app.py

The served endpoint is OpenAI-compatible (/v1/chat/completions). Chapter 08's
agent can use it as a self-hosted LLM.
"""

import os

import flyte
import flyte.app
from flyteplugins.vllm import VLLMAppEnvironment

MODEL_HF_PATH = os.getenv("HF_MODEL_ID", "Qwen/Qwen2.5-0.5B-Instruct")

vllm_app = VLLMAppEnvironment(
    name="review-radar-llm",
    model_hf_path=MODEL_HF_PATH,
    model_id="review-radar-llm",
    resources=flyte.Resources(
        cpu="4",
        memory="16Gi",
        gpu="L4:1",              # adjust to a GPU type this deployment offers
        disk="30Gi",             # model weights cache
    ),
    scaling=flyte.app.Scaling(
        replicas=(0, 1),         # scale to zero — GPU is only used while active
        scaledown_after=300,
    ),
    requires_auth=False,
)


if __name__ == "__main__":
    flyte.init_from_config()
    deployment = flyte.serve(vllm_app)
    import flyte.remote
    endpoint = flyte.remote.App.get(name=vllm_app.name).endpoint
    print(f"Deployed {vllm_app.name}. Console: {deployment.url}")
    print(f"Chat completions endpoint: {endpoint}/v1/chat/completions")
