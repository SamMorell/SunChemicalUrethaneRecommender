import streamlit as st
import pandas as pd

from urethane.core.urethane_core import (
    load_default_dataset,
    load_uploaded_dataset,
    get_dropdown_options,
    filter_recommendations,
    export_recommendations_excel,
)

st.set_page_config(
    page_title="Sun Chemical Urethane Recommender",
    layout="wide"
)

st.title("Sun Chemical Urethane Recommender")
st.caption("Select requirements and receive recommended urethane systems.")

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
