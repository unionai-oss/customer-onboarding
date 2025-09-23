"""
Simple Hyperparameter Optimization Example using Union SDK v1 with Weights & Biases

This HPO workflow demonstrates grid search optimization with actual model training
and W&B tracking integration using Pydantic models.
"""
import union
from typing import List, Tuple
from union import workflow, task, dynamic, Resources, Secret, ImageSpec
from pydantic import BaseModel
from orchestration.container_images import hpo_image
from flytekitplugins.wandb import wandb_init
import wandb


# W&B Configuration
WANDB_PROJECT = "union-demos"
WANDB_ENTITY = "espejo-david-union-ai"

# W&B Secret Configuration
wandb_secret = union.Secret(key="wandb-api-key")


class SimpleHyperparameters(BaseModel):
    """Hyperparameters for logistic regression model using Pydantic"""
    learning_rate: float = 0.01
    max_iter: int = 1000
    C: float = 1.0  # Regularization strength
    solver: str = "lbfgs"
    
    class Config:
        # Allow the model to be serialized
        arbitrary_types_allowed = True


class TrainingResult(BaseModel):
    """Result of a training run with hyperparameters"""
    accuracy: float
    hyperparams: SimpleHyperparameters
    
    class Config:
        arbitrary_types_allowed = True


@task(
    container_image=hpo_image,
    secret_requests=[union.Secret(key="wandb-api-key")] if wandb_init else []
)
@wandb_init(project=WANDB_PROJECT, entity=WANDB_ENTITY, secret=wandb_secret)
def train_simple_model(hyperparams: SimpleHyperparameters) -> TrainingResult:
    """
    Train a logistic regression model with the given hyperparameters.
    Uses iris dataset for classification with W&B tracking.
    """
    from sklearn.datasets import load_iris
    from sklearn.model_selection import train_test_split
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import accuracy_score
    import wandb
    
    # Load and split data
    X, y = load_iris(return_X_y=True)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # Train model with hyperparameters
    model = LogisticRegression(
        C=hyperparams.C,
        max_iter=hyperparams.max_iter,
        solver=hyperparams.solver,
        random_state=42
    )
    
    model.fit(X_train, y_train)
    
    # Make predictions and calculate accuracy
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    
    # Log metrics to W&B
    wandb.log({
        "accuracy": accuracy,
        "C": hyperparams.C,
        "max_iter": hyperparams.max_iter,
        "solver": hyperparams.solver,
        "n_train_samples": len(X_train),
        "n_test_samples": len(X_test)
    })
    
    # Log hyperparameters as summary
    wandb.run.summary["final_accuracy"] = accuracy
    wandb.run.summary["hyperparams"] = hyperparams.model_dump()
    
    wandb.finish()
    
    print(f"Trained with {hyperparams} -> Accuracy: {accuracy:.4f}")
    
    return TrainingResult(accuracy=accuracy, hyperparams=hyperparams)


@task(container_image=hpo_image,
    secret_requests=[union.Secret(key="wandb-api-key")] if wandb_init else [])
def generate_hyperparameter_grid() -> List[SimpleHyperparameters]:
    """Generate a grid of hyperparameters for logistic regression"""
    C_values = [0.1, 1.0, 10.0]  # Regularization strength
    max_iter_values = [500, 1000, 2000]  # Maximum iterations
    solvers = ["lbfgs", "liblinear"]  # Solvers
    
    combinations = []
    for C in C_values:
        for max_iter in max_iter_values:
            for solver in solvers:
                combinations.append(SimpleHyperparameters(
                    C=C,
                    max_iter=max_iter,
                    solver=solver
                ))
    
    return combinations


@dynamic(container_image=hpo_image)
def run_hyperparameter_sweep(
    hyperparameter_list: List[SimpleHyperparameters]
) -> List[TrainingResult]:
    """
    Run training with multiple hyperparameter combinations in parallel.
    This demonstrates Union's dynamic workflow capabilities.
    """
    results = []
    
    # Each of these tasks will run in parallel
    for hyperparams in hyperparameter_list:
        result = train_simple_model(hyperparams=hyperparams)
        results.append(result)
    
    return results


@task(
    container_image=hpo_image,
    secret_requests=[union.Secret(key="wandb-api-key")] if wandb_init else []
)
@wandb_init(project=WANDB_PROJECT, entity=WANDB_ENTITY, secret=wandb_secret)

def find_best_hyperparameters(
    results: List[TrainingResult]
) -> TrainingResult:
    """
    Find the hyperparameters that achieved the best accuracy.
    Creates W&B summary with comparison table.
    """
    import wandb
    
    best_result = None
    
    # Find best hyperparameters
    for i, result in enumerate(results):
        if best_result is None or result.accuracy > best_result.accuracy:
            best_result = result
        
        # Log each trial to W&B
        wandb.log({
            f"trial_{i}_accuracy": result.accuracy,
            f"trial_{i}_C": result.hyperparams.C,
            f"trial_{i}_max_iter": result.hyperparams.max_iter,
            f"trial_{i}_solver": result.hyperparams.solver,
            "trial_number": i
        })
    
    # Log best results to W&B
    wandb.run.summary.update({
        "best_accuracy": best_result.accuracy,
        "best_C": best_result.hyperparams.C,
        "best_max_iter": best_result.hyperparams.max_iter,
        "best_solver": best_result.hyperparams.solver,
        "total_trials": len(results)
    })
    
    # Create a comparison table
    trial_data = []
    for i, result in enumerate(results):
        trial_data.append([
            i, 
            result.hyperparams.C, 
            result.hyperparams.max_iter, 
            result.hyperparams.solver, 
            result.accuracy
        ])
    
    table = wandb.Table(
        data=trial_data,
        columns=["Trial", "C", "Max Iter", "Solver", "Accuracy"]
    )
    wandb.log({"hpo_results": table})
    
    wandb.finish()
    
    print(f"Best result: {best_result.accuracy:.4f} with {best_result.hyperparams}")
    return best_result


@workflow
def simple_hpo_workflow() -> TrainingResult:
    """
    Simple HPO workflow that demonstrates:
    1. Generating hyperparameter combinations
    2. Running parallel training trials
    3. Selecting the best performing hyperparameters
    All with W&B tracking enabled.
    """
    # Generate hyperparameter combinations
    hyperparameter_combinations = generate_hyperparameter_grid()
    
    # Run hyperparameter sweep in parallel
    all_results = run_hyperparameter_sweep(hyperparameter_combinations)
    
    # Find the best performing hyperparameters
    best_result = find_best_hyperparameters(all_results)
    
    return best_result
