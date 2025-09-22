from union import workflow, map, FlyteFile
from orchestration.artifacts import example_union_model
from tasks.load import load_test_data
from tasks.predict import predict


@workflow
def wf(model: FlyteFile = example_union_model.query()):
    test_data = load_test_data()
    map(predict, bound_inputs={"model": model})(image=test_data)
