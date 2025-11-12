import flyte
import asyncio
from flyte.io import File

env = flyte.TaskEnvironment(
    name="download_test", resources=flyte.Resources(memory="5Gi")
)


@env.task
async def download_flytefile(input_file: File) -> str:
    import time
    import os

    start = time.time()
    local_path = await input_file.download()
    download_time = round(time.time() - start, 2)
    actual_size = os.path.getsize(local_path) / 1024**2

    return f"{int(actual_size)}MB -> {download_time} seconds"


@env.task
async def main(
    inputs: list[File] = [
        File(
            path="s3://union-internal-aws-prod-use2/test_download_speed/dataset_50MB.csv"
        ),
        File(
            path="s3://union-internal-aws-prod-use2/test_download_speed/dataset_200MB.csv"
        ),
        File(
            path="s3://union-internal-aws-prod-use2/test_download_speed/dataset_500MB.csv"
        ),
        File(
            path="s3://union-internal-aws-prod-use2/test_download_speed/dataset_2GB.csv"
        ),
        File(
            path="s3://union-internal-aws-prod-use2/test_download_speed/dataset_5GB.csv"
        ),
    ],
) -> list[str]:
    results = []
    for i in inputs:
        results.append(download_flytefile(input_file=i))
    result = await asyncio.gather(*results)
    return result


if __name__ == "__main__":
    flyte.init_from_config()
    run = flyte.run(main)

    # print various attributes of the run.
    print(run.name)
    print(run.url)

    run.wait(run)  # stream the logs from the root action to the terminal.
