# example-union-workflows

This repository contains examples of end-to-end ML workflows built with **[Union](https://union.ai/)**, showcasing Union-specific features for training, inference, and serving.

## Highlights

### 1. **Train a Keras Model**
- Build container images using `ImageSpec` with Union's **remote image builder**:  
  → [`./orchestration/container_images.py`](./orchestration/container_images.py)  
- Define the model artifact with Union’s native artifact abstraction:  
  → [`./orchestration/artifacts.py`](./orchestration/artifacts.py)
- Train a simple Keras model and generate a **Union Artifact**:  
  → [`./tasks/train.py`](./tasks/train.py)  
- Run Hyperparameter Optimization for a simple Linear Regression model and track experiments in Weights & Biases:
 → [`./workflows/simple_hpo.py`](./workflows/simple_hpo.py)  

### 2. **Run Batch Inference at Scale**

- **Massively accelerate batch inference** with Union **Actors**:  
  → [`./orchestration/actor_env.py`](./orchestration/actor_env.py)  
- Perform scalable and parallel inference using Union’s **`map`** construct:  
  → [`./workflows/predict_conv_model.py`](./workflows/predict_conv_model.py)  

  - Union Actors eliminate container startup/teardown time  
  - Cache and reuse model loading logic:  
    → [`./tasks/predict.py`](./tasks/predict.py)

### 3. **Serve the Keras Model via a FastAPI App**
- Deploy a FastAPI app that pulls the **Union Model Artifact** and serves it with Union:  
  → [`./apps/simple-fastapi/app.py`](./apps/simple-fastapi/app.py)

---

## 🚀 Get Started

1. Create and activate a Python environment of your choice   
2. [Follow the docs](https://www.union.ai/docs/v1/byoc/user-guide/getting-started/local-setup/) to configure your environment and connect to your Union tenant.
3. Install dependencies:  
   ```bash
   pip install -r requirements.txt
   ```


  

---

## 🛠️ Run Training and Prediction Workflows

```bash
# Run training workflow
union run  --remote workflows/train_conv_model.py wf
```

> Wait for the training execution to complete and the Model Artifact to be generated.

```bash
# Run prediction workflow using the trained model
union run -p <your-project> --remote workflows/predict_conv_model.py wf
```

---

## 📅 Setup Launchplans

Register and activate launchplans for training and prediction, including:
- Fixed-rate scheduling
- Notifications
- Artifact triggers

```bash
union register -p <your-project> ./launchplans --activate-launchplans
```

---

## 🌐 Serve the Keras Model with FastAPI

Deploy the FastAPI app using Union:

```bash
union deploy apps -p <your-project> apps/simple-fastapi/app.py simple-fastapi
```

Then open your deployed app at:

```
<your-deployed-endpoint>/docs
```

To apply changes after modifying the app code, re-run the deploy command above.
