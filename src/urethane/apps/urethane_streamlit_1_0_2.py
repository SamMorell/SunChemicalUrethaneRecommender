import streamlit as st
import pandas as pd
from pathlib import Path

from urethane.core.urethane_core import (
    load_default_dataset,
    load_uploaded_dataset,
    get_dropdown_options,
    filter_recommendations,
    export_recommendations_excel,
)

APP_VERSION = "1.0.2"
RUNNING_LABEL = "RUNNING: urethane_streamlit_1_0_2 (via shim)"
GIF_FILENAME = "sammorell.com_animated_header.gif"


# -----------------------------
# Helpers for header assets
# -----------------------------
def _candidate_gif_locations(filename: str) -> list[Path]:
    """Common places to put assets in a src-layout repo."""
    here = Path(__file__).resolve()
    repo_root = here.parents[3] if len(here.parents) >= 4 else here.parents[-1]

    return [
        # Same folder as this script
        here.parent / filename,
        # Typical asset folders (either next to app or at repo root)
        here.parent / "assets" / filename,
        here.parent / "static" / filename,
        repo_root / filename,
        repo_root / "assets" / filename,
        repo_root / "static" / filename,
        repo_root / "data" / "assets" / filename,
    ]


def _find_first_existing(paths: list[Path]) -> Path | None:
    for p in paths:
        if p.exists():
            return p
    return None


def render_header() -> None:
    # --- CSS (feel free to tweak) ---
    st.markdown(
        """
        <style>
        .ucr-title {
            color: #000000;
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 2.2rem;
            font-weight: 600;
            margin-bottom: 0.15em;
            line-height: 1.1;
        }
        .ucr-subtle {
            color: #6b7280; /* gray-ish */
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 0.95rem;
            margin-top: 0.1em;
            margin-bottom: 1.0em;
        }
        .ucr-section {
            color: #FFA500;
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 1.6rem;
            font-weight: 600;
            margin-top: 1.4em;
            margin-bottom: 0.5em;
            border-bottom: 2px solid #e5e7eb;
            padding-bottom: 0.2em;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # --- Animated GIF header (optional) ---
    gif_path = _find_first_existing(_candidate_gif_locations(GIF_FILENAME))
    if gif_path:
        st.image(str(gif_path), width=420)

    # --- Title + Version (like HSP app) ---
    st.markdown('<div class="ucr-title">Sun Chemical Urethane Recommender</div>', unsafe_allow_html=True)
    st.caption(f"v{APP_VERSION}")
    st.caption(RUNNING_LABEL)
    st.markdown('<div class="ucr-subtle">Select requirements and receive recommended urethane systems.</div>', unsafe_allow_html=True)


def main() -> None:
    st.set_page_config(page_title="Sun Chemical Urethane Recommender", layout="wide")

    render_header()

    # -----------------------------
    # Load data
    # -----------------------------
    st.sidebar.header("Data Source")

    uploaded_file = st.sidebar.file_uploader(
        "Upload Product Data (CSV or XLSX)",
        type=["csv", "xlsx"]
    )

    if uploaded_file:
        df = load_uploaded_dataset(uploaded_file)
        st.sidebar.success(f"Loaded {len(df)} rows from upload")
    else:
        df = load_default_dataset()
        st.sidebar.info(f"Using built-in dataset ({len(df)} rows)")

    # -----------------------------
    # Dropdowns
    # -----------------------------
    st.markdown('<div class="ucr-section">Selections</div>', unsafe_allow_html=True)

    options = get_dropdown_options(df)

    category = st.selectbox("Category", options["category"])
    end_use = st.selectbox("End Use", options["end_use"](category))
    application = st.selectbox("Application", options["application"](category, end_use))
    features = st.selectbox("Features", options["features"](category, end_use, application))
    sb_wb_hs = st.selectbox("SB / WB / HS / P", options["sb_wb_hs"](category, end_use, application, features))
    composition = st.selectbox("Composition", options["composition"](category, end_use, application, features, sb_wb_hs))

    # -----------------------------
    # Results
    # -----------------------------
    st.markdown('<div class="ucr-section">Results</div>', unsafe_allow_html=True)

    if st.button("Get Recommendations"):
        results_df = filter_recommendations(
            df,
            category=category,
            end_use=end_use,
            application=application,
            features=features,
            sb_wb_hs=sb_wb_hs,
            composition=composition,
        )

        if results_df.empty:
            st.warning("No matching recommendations found.")
        else:
            st.success(f"Found {len(results_df)} recommendation(s)")
            st.dataframe(results_df, use_container_width=True)

            excel_bytes = export_recommendations_excel(results_df)

            st.download_button(
                label="Download Recommendations (XLSX)",
                data=excel_bytes,
                file_name="urethane_recommendations.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )


if __name__ == "__main__":
    main()
