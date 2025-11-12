from union import workflow, task, dynamic, ImageSpec, FlyteFile, Resources


container_image = ImageSpec(packages=["union"], builder="union")


@task(container_image=container_image, requests=Resources(mem="5Gi"))
def download_flyte_file(input_file: FlyteFile) -> str:
    import time
    import os

    start = time.time()
    input_file.download()
    download_time = round(time.time() - start, 2)
    actual_size = os.path.getsize(input_file) / 1024**2

    return f"{int(actual_size)}MB -> {download_time} seconds"


@dynamic(container_image=container_image)
def wf_wrapper(inputs: list[FlyteFile]) -> list[str]:
    results = []
    for i in inputs:
        results.append(download_flyte_file(input_file=i))
    return results


@workflow
def wf(
    inputs: list[FlyteFile] = [
        FlyteFile(
            "s3://union-internal-aws-prod-use2/test_download_speed/dataset_50MB.csv"
        ),
        FlyteFile(
            "s3://union-internal-aws-prod-use2/test_download_speed/dataset_200MB.csv"
        ),
        FlyteFile(
            "s3://union-internal-aws-prod-use2/test_download_speed/dataset_500MB.csv"
        ),
        FlyteFile(
            "s3://union-internal-aws-prod-use2/test_download_speed/dataset_2GB.csv"
        ),
        FlyteFile(
            "s3://union-internal-aws-prod-use2/test_download_speed/dataset_5GB.csv"
        ),
    ],
) -> list[str]:
    return wf_wrapper(inputs=inputs)
