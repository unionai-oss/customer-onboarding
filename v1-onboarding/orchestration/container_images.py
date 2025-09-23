from union import ImageSpec

container_image = ImageSpec(
    name="example-image",
    builder="union",
    requirements="./requirements.txt",
#     builder_options={
#         "imagepull_secret_name":"ghcr-pull-creds-02",
#     }
 )

app_image = ImageSpec(
    name="union-serve-keras-fastapi",
    packages=["union-runtime>=0.1.10", "tensorflow", "fastapi[standard]", "pillow"],
    builder="union",
    # builder_options={
    #     "imagepull_secret_name":"ghcr-pull-creds-02",
    # } 
)

hpo_image = ImageSpec(
    name="example-hpo-image",
    builder="union",
    packages=["union==0.1.194", 
              "flytekitplugins-wandb", 
              "scikit-learn"],
    # builder_options={
    #     "imagepull_secret_name":"ghcr-pull-creds-02",
    # }
)
