"""
Core (framework-agnostic) logic for the Sun Chemical urethane recommender.

This version uses an Excel dataset on disk (default: data/defaults/application_product.xlsx)
instead of a built-in encoded dataset.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional

from io import BytesIO
from openpyxl.styles import Alignment

import pandas as pd


# --------- Defaults ---------
DEFAULT_DATASET_PATH = Path("data/defaults/application_product.xlsx")

# Expected canonical columns (after normalization)
REQUIRED_COLS = [
    "category",
    "end_use",
    "application",
    "features",
    "sb_wb_hs_p",
    "composition",
    "component_a",
    "component_b",
]


# --------- Helpers ---------
def _normalize_colname(c: str) -> str:
    c = str(c).strip()
    c = c.replace("\n", " ").replace("\r", " ")
    c = c.replace("-", "_").replace("/", "_")
    c = c.replace(" ", "_")
    c = c.lower()
    while "__" in c:
        c = c.replace("__", "_")
    return c


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [_normalize_colname(c) for c in df.columns]

    # Optional: handle a couple common variants
    rename_map = {
        "enduse": "end_use",
        "end_use_": "end_use",
        "sb_wb_hs_p_": "sb_wb_hs_p",
        "sb_wb_hs_p__": "sb_wb_hs_p",
        "componenta": "component_a",
        "componentb": "component_b",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    return df


def _validate(df: pd.DataFrame) -> None:
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(
            "Dataset is missing required columns:\n"
            f"{missing}\n\n"
            f"Found columns:\n{list(df.columns)}"
        )


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Standardize strings (avoid weird whitespace causing filtering failures)
    for c in REQUIRED_COLS:
        df[c] = df[c].astype(str).str.strip()

    # Treat empty strings as NA
    df = df.replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})

    # Drop rows missing core fields
    df = df.dropna(subset=["category", "end_use", "application"])
    return df


def _unique(series: pd.Series) -> List[str]:
    """Alphabetical unique list (fallback)."""
    vals = series.dropna().astype(str).str.strip()
    vals = vals[vals != ""]
    out = sorted(set(vals.tolist()))
    return out


def _unique_sorted_by_order(
    value_series: pd.Series,
    order_series: Optional[pd.Series] = None,
) -> List[str]:
    """Return unique values ordered by an accompanying numeric sort order column.

    - If order_series is missing/None OR all values are NaN, falls back to alphabetical.
    - If there are multiple rows per value, uses the minimum order number for that value.
    """
    vals = value_series.dropna().astype(str).str.strip()
    vals = vals[vals != ""]
    if vals.empty:
        return []

    if order_series is None:
        return sorted(set(vals.tolist()))

    orders = pd.to_numeric(order_series, errors="coerce")
    if orders.isna().all():
        return sorted(set(vals.tolist()))

    tmp = pd.DataFrame({"val": vals, "ord": orders})
    tmp = tmp.dropna(subset=["val"])
    grp = tmp.groupby("val", as_index=False)["ord"].min()
    grp = grp.sort_values(["ord", "val"], ascending=[True, True])
    return grp["val"].tolist()

def _resolve_path(path: Optional[str | Path]) -> Path:
    if path is None:
        path = DEFAULT_DATASET_PATH
    p = Path(path)

    # If called from inside src/urethane/core, Streamlit sometimes uses CWD at repo root.
    # This keeps it simple: assume repo root relative paths.
    return p


# --------- Public API used by Streamlit ---------
def load_application_product(path: Optional[str | Path] = None) -> pd.DataFrame:
    """
    Load the default Excel dataset.
    If path is None, uses data/defaults/application_product.xlsx
    """
    p = _resolve_path(path)

    if not p.exists():
        raise FileNotFoundError(
            f"Default dataset file not found: {p}\n"
            f"Expected at: {DEFAULT_DATASET_PATH}\n"
            "Make sure the file is in your repo and the relative path is correct."
        )

    df = pd.read_excel(p)
    df = _normalize_columns(df)
    _validate(df)
    df = _clean(df)
    return df


def load_uploaded_dataset(uploaded_file) -> pd.DataFrame:
    """
    Load an uploaded Excel/CSV file from Streamlit's uploader object.
    """
    if uploaded_file is None:
        raise ValueError("No uploaded file provided.")

    name = getattr(uploaded_file, "name", "").lower()

    if name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        # Excel (xlsx/xls)
        df = pd.read_excel(uploaded_file)

    df = _normalize_columns(df)
    _validate(df)
    df = _clean(df)
    return df


def get_dropdown_options(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Dropdown options with sort-order support.

    If the dataset includes:
      - category_sort_order
      - end_use_sort_order

    ...then Category and End Use dropdowns will be ordered by those numeric values
    (ascending), with alphabetical as a tiebreaker.

    Returns a dict where:
      - options["category"] is a list[str]
      - others are callables that return list[str] based on parent selections
    This matches how urethane_streamlit_1_0_2.py is written.
    """
    options: Dict[str, Any] = {}

    has_cat_order = "category_sort_order" in df.columns
    has_end_order = "end_use_sort_order" in df.columns

    # Category list (sorted by Category_Sort_Order if present)
    cat_orders = df["category_sort_order"] if has_cat_order else None
    options["category"] = _unique_sorted_by_order(df["category"], cat_orders)

    def end_use(category: str) -> List[str]:
        sub = df[df["category"] == category]
        end_orders = sub["end_use_sort_order"] if has_end_order else None
        return _unique_sorted_by_order(sub["end_use"], end_orders)

    def application(category: str, end_use: str) -> List[str]:
        sub = df[(df["category"] == category) & (df["end_use"] == end_use)]
        return _unique(sub["application"])

    def features(category: str, end_use: str, application: str) -> List[str]:
        sub = df[
            (df["category"] == category)
            & (df["end_use"] == end_use)
            & (df["application"] == application)
        ]
        return _unique(sub["features"])

    def sb_wb_hs_p(category: str, end_use: str, application: str, features) -> List[str]:
        sub = df[
            (df["category"] == category)
            & (df["end_use"] == end_use)
            & (df["application"] == application)
        ]

        # features may be a string OR a list (e.g., ["CHROME LOOK"])
        if isinstance(features, (list, tuple, set)):
            features_list = [str(x).strip() for x in features if str(x).strip()]
            if features_list:
                sub = sub[sub["features"].isin(features_list)]
        else:
            f = str(features).strip()
            if f:
                sub = sub[sub["features"] == f]

        return _unique(sub["sb_wb_hs_p"])

    def composition(category: str, end_use: str, application: str, features, sb: str) -> List[str]:
        sub = df[
            (df["category"] == category)
            & (df["end_use"] == end_use)
            & (df["application"] == application)
            & (df["sb_wb_hs_p"] == sb)
        ]

        if isinstance(features, (list, tuple, set)):
            features_list = [str(x).strip() for x in features if str(x).strip()]
            if features_list:
                sub = sub[sub["features"].isin(features_list)]
        else:
            f = str(features).strip()
            if f:
                sub = sub[sub["features"] == f]

        return _unique(sub["composition"])


    options["end_use"] = end_use
    options["application"] = application
    options["features"] = features
    options["sb_wb_hs_p"] = sb_wb_hs_p
    options["composition"] = composition

    return options

def filter_recommendations(
    df: pd.DataFrame,
    category: str,
    end_use: str,
    application: str,
    selected_features: Optional[List[str]] = None,
    sb_wb_hs_p: Optional[str] = None,
    composition: Optional[str] = None,
    # Accept UI synonyms safely (prevents “unexpected keyword argument” errors)
    features: Optional[List[str]] = None,
    **kwargs,
) -> pd.DataFrame:
    """
    Filter dataset for recommendations.

    NOTE:
    - The core parameter name is selected_features.
    - We also accept `features=` as a synonym to avoid Streamlit/UI mismatch errors.
    """
    if selected_features is None and features is not None:
        selected_features = features
    selected_features = selected_features or []

    out = df.copy()

    # Required filters
    out = out[(out["category"] == category) & (out["end_use"] == end_use) & (out["application"] == application)]

    # Features:
    # - if the sheet stores a single feature per row, then selected_features is typically length 1.
    # - if multiple features are allowed, keep rows matching ANY selected feature.
    if selected_features:
        out = out[out["features"].isin(selected_features)]

    # Optional filters
    if sb_wb_hs_p:
        out = out[out["sb_wb_hs_p"] == sb_wb_hs_p]

    if composition:
        out = out[out["composition"] == composition]

    # Make results nicer
    out = out.reset_index(drop=True)
    return out


def export_recommendations_excel(df: pd.DataFrame) -> bytes:
    output = BytesIO()  # <-- THIS WAS MISSING

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Recommendations")

        ws = writer.sheets["Recommendations"]

        # Left-align header row
        for cell in ws[1]:
            cell.alignment = Alignment(horizontal="left")

    output.seek(0)
    return output.getvalue()

