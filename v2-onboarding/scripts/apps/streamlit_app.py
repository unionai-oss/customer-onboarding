"""Streamlit dashboard app for 07-apps-and-inference.

Deploy from the notebook / shell:

    python scripts/apps/streamlit_app.py

Streamlit apps use the generic AppEnvironment: the container runs
`streamlit run <this file>` and this script doubles as the app code
(the `--server` sentinel distinguishes the two roles).
"""

import pathlib
import sys

import flyte
import flyte.app


def main() -> None:
    import pandas as pd
    import streamlit as st

    st.set_page_config(page_title="Workshop run dashboard", page_icon="📊")
    st.title("Workshop scoring dashboard")

    text = st.text_input("Text to score", "hello union")
    st.metric("Score", float(len(text)) * 2.0)

    st.subheader("Recent scores")
    st.dataframe(pd.DataFrame({"text": [text], "score": [float(len(text)) * 2.0]}))


file_name = pathlib.Path(__file__).name

app_env = flyte.app.AppEnvironment(
    name="workshop-dashboard",
    image=flyte.Image.from_debian_base(python_version=(3, 12)).with_pip_packages(
        "streamlit==1.41.1", "pandas==2.2.3"
    ),
    args=["streamlit", "run", file_name, "--server.port", "8080", "--", "--server"],
    port=8080,
    resources=flyte.Resources(cpu="1", memory="1Gi"),
    requires_auth=False,
)


if __name__ == "__main__":
    if "--server" in sys.argv:
        main()                      # running inside the app container
    else:
        flyte.init_from_config()    # running on your laptop: deploy it
        deployment = flyte.serve(app_env)
        print(f"Deployed: {deployment.url}")
