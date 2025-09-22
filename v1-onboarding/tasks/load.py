import union
from union import task, FlyteDirectory, FlyteFile
from orchestration.container_images import container_image
from orchestration.actor_env import actor
from core.training_prep import split_and_copy
import kagglehub
import os


@task(cache=True, cache_version="0.1", container_image=container_image, secret_requests=[union.Secret(key=" ghcr-pull-creds-02")])
def load_training_data(split_ratio: float = 0.8) -> FlyteDirectory:
    path = kagglehub.dataset_download("imsparsh/flowers-dataset")

    dest_dir = "./dataset"
    split_and_copy(
        dest_dir=dest_dir, source_dir=f"{path}/train", split_ratio=split_ratio
    )

    return FlyteDirectory(path=dest_dir)


@actor.task(cache=True, cache_version="0.1")
def load_test_data() -> list[FlyteFile]:
    path = kagglehub.dataset_download("imsparsh/flowers-dataset")
    directory = f"{path}/test"
    test_data = [
        FlyteFile(path=os.path.join(directory, f))
        for f in os.listdir(directory)
        if os.path.isfile(os.path.join(directory, f))
    ]
    return test_data
