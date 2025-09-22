from union import LaunchPlan
from union.artifacts import OnArtifact
from orchestration.artifacts import example_union_model
from flytekit import Slack, WorkflowExecutionPhase
from workflows.predict_conv_model import wf

predict_conv_model_lp = LaunchPlan.create(
    name="predict_conv_model_lp",
    workflow=wf,
    trigger=OnArtifact(trigger_on=example_union_model),
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
