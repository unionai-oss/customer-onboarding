"""Deploys a small named task so notebooks can demonstrate cross-team
composition via flyte.remote.Task.get (05-gcp-data-and-integrations).

Deploy with:

    python scripts/remote_task_deploy.py
"""

import flyte

env = flyte.TaskEnvironment(
    name="shared_utils",
    resources=flyte.Resources(cpu="1", memory="512Mi"),
)


@env.task
async def tokenize(text: str) -> list[str]:
    """A 'platform team' task other teams call without importing this code."""
    return text.lower().split()


if __name__ == "__main__":
    flyte.init_from_config()
    deployment = flyte.deploy(env)
    print(deployment)
