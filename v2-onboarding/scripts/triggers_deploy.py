"""Scheduled-task deployment example.

Triggers require a *deployment* (a versioned task registered on the control
plane), and deployment is not supported from interactive notebook sessions —
which is why this lives here. Deploy with:

    python scripts/triggers_deploy.py

Then manage the trigger:

    flyte get trigger
    flyte update trigger daily_report scheduled.daily_report --deactivate
"""

from datetime import datetime

import flyte

env = flyte.TaskEnvironment(
    name="scheduled",
    resources=flyte.Resources(cpu="1", memory="512Mi"),
)


@env.task(
    triggers=flyte.Trigger(
        "daily_report",
        flyte.Cron("0 6 * * *", timezone="America/New_York"),
        inputs={"report_date": flyte.TriggerTime},
        auto_activate=True,
    )
)
async def daily_report(report_date: datetime) -> str:
    return f"report generated for {report_date.date()}"


if __name__ == "__main__":
    flyte.init_from_config()
    deployment = flyte.deploy(env)
    print(deployment)
