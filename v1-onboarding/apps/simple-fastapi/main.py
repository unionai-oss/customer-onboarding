"""Set up the FastAPI app."""

from contextlib import asynccontextmanager
import os
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
import tensorflow as tf
from io import BytesIO
import numpy as np

ml_models = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    model_file = os.getenv("KERAS_MODEL")
    ml_models["model"] = tf.keras.models.load_model(model_file)
    yield


app = FastAPI(lifespan=lifespan)


@app.post("/predict")
async def predict(file: UploadFile = File(...)) -> JSONResponse:
    if file.content_type != "image/jpeg":
        return JSONResponse(
            status_code=400, content={"error": "Only JPEG files are supported."}
        )

    # Read and preprocess image
    image_bytes = await file.read()
    img = tf.keras.utils.load_img(BytesIO(image_bytes), target_size=(150, 150))
    img_array = tf.keras.utils.img_to_array(img)
    img_array = np.expand_dims(img_array, axis=0)

    # Predict
    model = ml_models["model"]
    logits = model.predict(img_array)
    probabilities = tf.nn.softmax(logits).numpy()
    class_index = np.argmax(probabilities, axis=1)[0]
    return JSONResponse(
        status_code=200,
        content={"message": "You dit it 🚀", "class_index": int(class_index)},
    )
