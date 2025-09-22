from union import LaunchPlan
from flytekit import FixedRate, Slack, WorkflowExecutionPhase
from datetime import timedelta
from workflows.train_conv_model import wf

train_conv_model_lp = LaunchPlan.create(
    name="train_conv_model_lp",
    workflow=wf,
    default_inputs={"epochs": 10},
    schedule=FixedRate(duration=timedelta(hours=10)),
    notifications=[
        Slack(
            phases=[
                WorkflowExecutionPhase.SUCCEEDED,
                WorkflowExecutionPhase.ABORTED,
                WorkflowExecutionPhase.TIMED_OUT,
                WorkflowExecutionPhase.FAILED,
            ],
            recipients_email=[
                "jandummybudgetchannel-aaaaooeewruwpgnbvqrt2573wu@unionai.slack.com"
            ],
        ),
    ],
)
