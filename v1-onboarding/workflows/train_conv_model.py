from union import workflow, FlyteFile
from tasks.train import train_conv_model
from tasks.load import load_training_data


@workflow
def wf(epochs: int = 5) -> FlyteFile:
    training_data = load_training_data()
    return train_conv_model(dataset=training_data, epochs=epochs)
