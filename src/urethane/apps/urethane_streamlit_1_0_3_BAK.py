from __future__ import annotations

import streamlit as st
import pandas as pd
import re
import base64

def _drop_internal_sort_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Remove internal sort-order columns from display/export outputs."""
    cols_to_drop = [c for c in ["category_sort_order", "end_use_sort_order"] if c in df.columns]
    return df.drop(columns=cols_to_drop, errors="ignore")

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union
from datetime import datetime

from urethane.core.urethane_core import (
    load_default_dataset,
    load_uploaded_dataset,
    get_dropdown_options,
    filter_recommendations,
    export_recommendations_excel,
)


# ---------------- PDS helpers ----------------
def _normalize_product_name(product: str) -> str:
    """Convert 'POLURGREEN MT 100' -> 'Polurgreen_MT_100_(PDS).pdf' (best-effort)."""
    s = (product or "").strip()
    # Title-ish casing for nicer filenames, but keep acronyms/nums.
    # We'll just use original tokens and replace spaces with underscores.
    s = re.sub(r"\s+", "_", s)
    # Remove characters that are problematic in filenames/URLs
    s = re.sub(r"[^A-Za-z0-9_\-]", "", s)
    return f"{s}_(PDS).pdf"

def _split_product_choices(cell: str) -> list[str]:
    """Split strings like 'A or B' into ['A','B']"""
    if cell is None:
        return []
    s = str(cell).strip()
    if not s:
        return []
    parts = [p.strip() for p in s.split(" or ")]
    # If user uses OR uppercase, handle that too
    if len(parts) == 1 and " OR " in s:
        parts = [p.strip() for p in s.split(" OR ")]
    return [p for p in parts if p]

def _find_pds_file(product: str, pds_dir: Path) -> Path | None:
    if not pds_dir.exists():
        return None
    target = _normalize_product_name(product).lower()
    # direct
    direct = pds_dir / _normalize_product_name(product)
    if direct.exists():
        return direct
    # case-insensitive scan
    for f in pds_dir.glob("*.pdf"):
        if f.name.lower() == target:
            return f
    return None

def _pdf_data_url(pdf_path: Path) -> str:
    data = pdf_path.read_bytes()
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:application/pdf;base64,{b64}"

APP_VERSION = "1.0.3"
#RUNNING_LABEL = "RUNNING: urethane_streamlit_1_0_3 (via shim)"
GIF_FILENAME = "sammorell.com_animated_header.gif"




def _get_repo_root() -> Path:
    """Best-effort repo root finder.

    Works locally (full repo) and on Streamlit Cloud (repo cloned).
    """
    here = Path(__file__).resolve()
    for parent in [here] + list(here.parents):
        if (parent / "pyproject.toml").exists() or (parent / ".git").exists():
            return parent
    # Fallback for src/urethane/apps layout
    # .../src/urethane/apps/<this_file>.py -> parents[3] == repo root
    try:
        return here.parents[3]
    except IndexError:
        return here.parent

# ---------------------------
# Helpers: paths + UI styling
# ---------------------------
def _candidate_gif_locations(filename: str) -> List[Path]:
    """Common places the GIF might live (repo root, src, package, etc.)."""
    here = Path(__file__).resolve()
    pkg_dir = here.parent  # .../src/urethane/apps
    src_dir = pkg_dir.parents[2] if len(pkg_dir.parents) >= 3 else pkg_dir.parents[0]  # .../src
    repo_root = src_dir.parent if src_dir.name == "src" else src_dir

    return [
        repo_root / filename,
        repo_root / "assets" / filename,
        repo_root / "images" / filename,
        repo_root / "static" / filename,
        src_dir / filename,
        src_dir / "assets" / filename,
        src_dir / "images" / filename,
        src_dir / "static" / filename,
        pkg_dir / filename,
    ]


def _find_first_existing(paths: List[Path]) -> Optional[Path]:
    for p in paths:
        if p.exists() and p.is_file():
            return p
    return None

def get_script_timestamp() -> str:
    script_path = Path(__file__)
    ts = script_path.stat().st_mtime
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")

def render_header() -> None:
    # --- CSS ---
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

    # --- Animated GIF header ---
    gif_path = _find_first_existing(_candidate_gif_locations(GIF_FILENAME))
    if gif_path:
        st.image(str(gif_path), use_container_width=False, width=360)

    # --- Title + Version ---
    st.markdown(
        '<div class="ucr-title">Sun Chemical Urethane Recommender</div>',
        unsafe_allow_html=True,
    )

    st.caption(f"{APP_VERSION} ({get_script_timestamp()})")

    #st.caption(f"v{APP_VERSION}")
    #st.caption(f"{APP_VERSION}")

    #st.caption(f"{get_script_timestamp()}")
    #st.caption(f"Last updated: {get_script_timestamp()}")

    #st.caption(RUNNING_LABEL)

    #st.markdown(
        #'<div class="ucr-subtle">'
        #'Select requirements and receive recommended urethane systems.'
        #'</div>',
        #unsafe_allow_html=True,
    #)


def section(title: str) -> None:
    st.markdown(f'<div class="ucr-section">{title}</div>', unsafe_allow_html=True)


# ---------------------------
# Helpers: options compatibility
# ---------------------------
OptionValue = Union[List[str], Callable[..., List[str]]]


def _get_options(options: Dict[str, Any], key: str, *args) -> List[str]:
    """
    get_dropdown_options() has historically returned either:
      - lists (options["category"] -> ["A","B"])
      - callables (options["end_use"](category) -> [...])
    This helper supports BOTH shapes.
    """
    if key not in options:
        return []

    v = options[key]
    if callable(v):
        try:
            return list(v(*args))
        except TypeError:
            # If callable signature differs, fall back to calling with no args
            return list(v())
    if isinstance(v, (list, tuple, pd.Series)):
        return list(v)
    return []


# ---------------------------
# Main app
# ---------------------------
def main() -> None:
    st.set_page_config(page_title="Sun Chemical Urethane Recommender", layout="wide")

    render_header()

    # ---- Data source ----
    with st.expander("Data source", expanded=False):
        st.write("Default dataset is loaded unless you upload a replacement Excel file.")
        uploaded = st.file_uploader("Upload dataset (Excel)", type=["xlsx", "xls"])

    try:
        if uploaded is not None:
            df = load_uploaded_dataset(uploaded)
        else:
            df = load_default_dataset()
    except Exception as e:
        st.error(f"Failed to load dataset: {e}")
        return

    if not isinstance(df, pd.DataFrame):
        st.error("Failed to load dataset: loader did not return a DataFrame.")
        return

    # ---- Selections ----
    section("Selections")

    options = get_dropdown_options(df)

    category_list = _get_options(options, "category")
    if not category_list:
        st.error("No Category options found. Check the dataset column names / loader.")
        return
    category = st.selectbox("Category", category_list)

    end_use_list = _get_options(options, "end_use", category)
    end_use = st.selectbox("End Use", end_use_list) if end_use_list else ""

    application_list = _get_options(options, "application", category, end_use)
    application = st.selectbox("Application", application_list) if application_list else ""

    features_list = _get_options(options, "features", category, end_use, application)
    # If you truly want single-select, keep selectbox; if multi-select later, switch to st.multiselect.
    features = st.selectbox("Features", features_list) if features_list else ""
    selected_features = [features] if features else []

    sb_list = _get_options(options, "sb_wb_hs_p", category, end_use, application, selected_features)
    sb_wb_hs_p = st.selectbox("SB / WB / HS / P", sb_list) if sb_list else ""

    comp_list = _get_options(options, "composition", category, end_use, application, selected_features, sb_wb_hs_p)
    if comp_list:
        composition = st.selectbox("Composition", comp_list)
    else:
        st.selectbox("Composition", ["No options to select"], disabled=True)
        composition = ""

    # ---- Results ----
    section("Results")

    if st.button("Get Recommendations"):
        try:
            # IMPORTANT: core signature uses selected_features (NOT features=)
            results_df = filter_recommendations(
                df=df,
                category=category,
                end_use=end_use,
                application=application,
                selected_features=selected_features,
                sb_wb_hs_p=sb_wb_hs_p,
                            composition=composition,
            )

            # If your core supports composition filtering, do it here safely:
            if composition and "Composition" in results_df.columns:
                results_df = results_df[results_df["Composition"].astype(str).eq(str(composition))].copy()

        except TypeError as e:
            st.error(f"Filter call failed (signature mismatch): {e}")
            return
        except Exception as e:
            st.error(f"Filtering failed: {e}")
            return

        if results_df is None or not isinstance(results_df, pd.DataFrame) or results_df.empty:
            st.warning("No recommendations found for the selected criteria.")
            return

        results_out = _drop_internal_sort_columns(results_df)

        st.dataframe(results_out, use_container_width=True)

        # --- Product Data Sheets (PDS) ---
        repo_root = _get_repo_root()
        pds_dir = repo_root / "data" / "pds"
        products_for_pds: list[str] = []
        if "component_a" in results_out.columns:
            for v in results_out["component_a"].dropna().unique().tolist():
                products_for_pds.extend(_split_product_choices(str(v)))
        if "component_b" in results_out.columns:
            for v in results_out["component_b"].dropna().unique().tolist():
                products_for_pds.extend(_split_product_choices(str(v)))

        # Deduplicate while preserving order
        seen = set()
        products_for_pds = [p for p in products_for_pds if not (p.lower() in seen or seen.add(p.lower()))]

        with st.expander("Product Data Sheets", expanded=False):
            any_found = False
            for i, product in enumerate(products_for_pds):
                pdf_path = _find_pds_file(product, pds_dir)
                if pdf_path:
                    any_found = True
                    pdf_bytes = pdf_path.read_bytes()
                    data_url = _pdf_data_url(pdf_path)
                    # A true "open in new tab" link (works in browsers; Streamlit will still sandbox local file://)
                    st.markdown(
                        f'<a href="{data_url}" target="_blank" rel="noopener">📄 View PDS: {product}</a>',
                        unsafe_allow_html=True,
                    )
                    st.download_button(
                        label=f"Download PDS: {product}",
                        data=pdf_bytes,
                        file_name=pdf_path.name,
                        mime="application/pdf",
                        key=f"pds_dl_{i}",
                    )
                    st.divider()
                else:
                    st.warning(f"PDS not found for {product}")

            if not products_for_pds:
                st.info("No products found in the results to look up PDS files.")
            elif not any_found:
                st.info("No matching PDS PDFs were found in data/pds.")

        # Export

        try:
            xlsx_bytes = export_recommendations_excel(results_out)
            st.download_button(
                "Download Excel",
                data=xlsx_bytes,
                file_name="urethane_recommendations.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        except Exception as e:
            st.error(f"Export failed: {e}")
            return