from union import task, Resources, FlyteDirectory, FlyteFile
from orchestration.container_images import container_image
from orchestration.artifacts import example_union_model
from core.plot import generate_md_contents
import logging
import tensorflow as tf
from tensorflow.keras.callbacks import History
from union.artifacts import ModelCard
from typing import Annotated


@task(
    container_image=container_image,
    requests=Resources(cpu="3"),
    limits=Resources(mem="10Gi"),
)
def train_conv_model(
    dataset: FlyteDirectory, epochs: int
) -> Annotated[FlyteFile, example_union_model]:
    dataset.download()

    TRAINING_DIR = f"{dataset}/train"
    TEST_DIR = f"{dataset}/test"

    logging.basicConfig(level=logging.INFO)

    # Instantiate data loaders
    train = tf.keras.utils.image_dataset_from_directory(
        TRAINING_DIR, image_size=(150, 150), color_mode="rgb"
    )
    test = tf.keras.utils.image_dataset_from_directory(
        TEST_DIR, image_size=(150, 150), color_mode="rgb"
    )
    logging.info("Data Generators built")

    # Define Model Architecture
    model = tf.keras.models.Sequential(
        [
            tf.keras.layers.Rescaling(1.0 / 255, input_shape=(150, 150, 3)),
            tf.keras.layers.Conv2D(filters=64, activation="relu", kernel_size=3),
            tf.keras.layers.MaxPool2D(pool_size=2, strides=2),
            tf.keras.layers.Conv2D(filters=32, activation="relu", kernel_size=3),
            tf.keras.layers.MaxPool2D(pool_size=2, strides=2),
            tf.keras.layers.Conv2D(filters=16, activation="relu", kernel_size=3),
            tf.keras.layers.MaxPool2D(pool_size=2, strides=2),
            tf.keras.layers.Conv2D(filters=128, activation="relu", kernel_size=3),
            tf.keras.layers.MaxPool2D(pool_size=2, strides=2),
            tf.keras.layers.Dropout(0.2),
            tf.keras.layers.Flatten(),
            tf.keras.layers.Dense(units=512, activation="relu"),
            tf.keras.layers.Dense(units=20, activation="softmax"),
        ]
    )

    model.compile(
        optimizer="adam",
        loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True),
        metrics=["accuracy"],
    )

    logging.info(model.summary())

    history = History()

    # Fit Model
    hist = model.fit(train, validation_data=test, epochs=epochs, callbacks=[history])

    logging.info(hist.history)

    model_path = "./model.keras"
    # Save model Binary
    tf.keras.models.save_model(
        model,
        model_path,
        overwrite=True,
        include_optimizer=True,
        save_format=None,
    )

    return example_union_model.create_from(
        FlyteFile(path=model_path),
        ModelCard(generate_md_contents(history=history)),
    )
