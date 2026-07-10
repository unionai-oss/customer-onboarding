"""Review Radar dashboard (Streamlit) for 07-serving.

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

    st.set_page_config(page_title="Review Radar", page_icon="📊")
    st.title("Review Radar — corpus dashboard")

    text = st.text_input("Try a review", "solid air fryer, works as advertised")
    pos = sum(w in text.lower() for w in ("love", "solid", "exceeded"))
    neg = sum(w in text.lower() for w in ("terrible", "disappointed", "broken"))
    st.metric("Sentiment hint", round(0.5 + 0.15 * (pos - neg), 2))

    st.subheader("Corpus snapshot (demo data)")
    st.dataframe(pd.DataFrame({
        "product": ["espresso machine", "trail shoes", "headphones", "air fryer"],
        "avg_stars": [4.1, 2.9, 3.8, 4.4],
        "reviews": [1240, 830, 2210, 990],
    }))


file_name = pathlib.Path(__file__).name

app_env = flyte.app.AppEnvironment(
    name="review-radar-dashboard",
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
