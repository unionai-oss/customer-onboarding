from union.app import App, Input
from union import Resources
from orchestration.container_images import app_image
from orchestration.artifacts import example_union_model

fast_api_app = App(
    name="simple-fastapi",
    subdomain="simple-fastapi",
    inputs=[
        Input(
            value=example_union_model.query(),
            download=True,
            env_var="KERAS_MODEL",
        )
    ],
    container_image=app_image,
    limits=Resources(cpu="1", mem="1Gi"),
    port=8082,
    include=["./main.py"],
    args="fastapi dev --port 8082",
)
