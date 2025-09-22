import pandas as pd


def training_metrics_to_markdown_table(history):
    df = pd.DataFrame(history.history)
    df.insert(0, "epoch", range(1, len(df) + 1))
    df = df.round(4)
    markdown_table = df.to_markdown(index=False)
    return markdown_table


def generate_md_contents(history: dict) -> str:
    contents = "# Unions's Super Model 🚀 🚀 🚀\n\n"
    contents = (
        contents
        + "![Unions](https://avatars.githubusercontent.com/u/94206482?s=280&v=4)"
        + "\n\n"
    )
    contents = contents + training_metrics_to_markdown_table(history=history)

    return contents
