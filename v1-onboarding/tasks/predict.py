from union import FlyteFile, actor_cache
from orchestration.actor_env import actor
import tensorflow as tf
import numpy as np


@actor_cache
def load_model(model_path: str) -> tf.keras.Model:
    return tf.keras.models.load_model(model_path)


@actor.task
def predict(image: FlyteFile, model: FlyteFile) -> np.ndarray:
    image_path = image.download()
    img = tf.keras.utils.load_img(image_path, target_size=(150, 150))
    # Convert to array
    img_array = tf.keras.utils.img_to_array(img)
    img_array = np.expand_dims(img_array, axis=0)

    model = load_model(model)
    logits = model.predict(img_array)
    probabilities = tf.nn.softmax(logits).numpy()
    return probabilities
