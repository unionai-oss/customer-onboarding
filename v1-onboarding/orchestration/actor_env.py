from union import ActorEnvironment, Resources
from orchestration.container_images import container_image

actor = ActorEnvironment(
    name="example-workflow-actor",
    replica_count=10,
    ttl_seconds=30,
    requests=Resources(cpu="1", mem="1Gi"),
    limits=Resources(cpu="2", mem="5Gi"),
    container_image=container_image,
)
