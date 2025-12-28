"""Sun Chemical Urethane Recommender (Streamlit) — organized."""

from __future__ import annotations
import os
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import re
import base64


# ---------------- Brochure search + highlight (optional) ----------------
# Requires: pip install pymupdf
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except Exception:
    fitz = None
    PYMUPDF_AVAILABLE = False

BROCHURE_FILENAME = "Advanced Materials - Polymers and Additives.pdf"

@st.cache_resource
def _brochure_page_text_index(pdf_path: str):
    """Cache lowercase page text for fast candidate-page filtering."""
    doc = fitz.open(pdf_path)
    texts = [doc[i].get_text("text").lower() for i in range(doc.page_count)]
    doc.close()
    return texts

@st.cache_data
def _highlighted_brochure_bytes(pdf_path: str, term: str, pdf_mtime: float):
    """Return (highlighted_pdf_bytes, hit_pages). Cached by term + brochure mtime."""
    doc = fitz.open(pdf_path)
    term_lc = term.lower()

    # Phase A: fast candidate pages using cached page text
    page_text = _brochure_page_text_index(pdf_path)
    candidate_pages = [i for i, t in enumerate(page_text) if term_lc in t]

    if not candidate_pages:
        doc.close()
        return None, []

    hit_pages = []
    for i in candidate_pages:
        page = doc[i]
        # Note: modern PyMuPDF search_for is case-insensitive by default; TEXT_IGNORECASE may not exist.
        rects = page.search_for(term, flags=getattr(fitz, "TEXT_DEHYPHENATE", 0))
        if rects:
            hit_pages.append(i + 1)
            for r in rects:
                page.add_highlight_annot(r)

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes, hit_pages

def brochure_find_and_highlight(brochure_path: Path, term: str):
    """Convenience wrapper using brochure mtime as part of cache key."""
    mtime = os.path.getmtime(str(brochure_path))
    return _highlighted_brochure_bytes(str(brochure_path), term, mtime)

# ----------------------------------------------------------------------
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union
from datetime import datetime
from urethane.core.urethane_core import (
    load_application_product,
    load_uploaded_dataset,
    get_dropdown_options,
    filter_recommendations,
    export_recommendations_excel,
)


# --- ChatGPT
import pandas as pd
import re

def filter_recommendations(
    df: pd.DataFrame,
    category=None,
    end_use=None,
    application=None,
    selected_features=None,   # list or None
    sb_wb_hs_p=None,
    composition=None,
):
    out = df.copy()

    # Normalize None/""/"(All)"
    def norm(v):
        if v is None:
            return None
        v = str(v).strip()
        return None if v in ("", "(All)") else v

    category = norm(category)
    end_use = norm(end_use)
    application = norm(application)
    sb_wb_hs_p = norm(sb_wb_hs_p)
    composition = norm(composition)

    # Basic equality filters
    if category is not None:
        out = out[out["category"].astype(str).str.strip().eq(category)]
    if end_use is not None:
        out = out[out["end_use"].astype(str).str.strip().eq(end_use)]
    if application is not None:
        out = out[out["application"].astype(str).str.strip().eq(application)]
    if sb_wb_hs_p is not None:
        out = out[out["sb_wb_hs_p"].astype(str).str.strip().eq(sb_wb_hs_p)]
    if composition is not None:
        out = out[out["composition"].astype(str).str.strip().eq(composition)]

    # Features: treat as "contains" (safe for multi-value cells)
    if selected_features:
        s = out["features"].fillna("").astype(str)
        for feat in selected_features:
            feat = norm(feat)
            if feat is None:
                continue
            out = out[s.str.contains(re.escape(feat), na=False)]

    return out

# -------------------------------------------------------------------


# =====================
# App code starts here
# =====================

def _drop_internal_sort_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Remove internal sort-order columns from display/export outputs."""
    cols_to_drop = [c for c in ["category_sort_order", "end_use_sort_order"] if c in df.columns]
    return df.drop(columns=cols_to_drop, errors="ignore")


def _prettify_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Make dataframe column labels more user-friendly.
    - Replace _ with space
    - Title Case
    - Special-case a few columns
    """
    out = df.copy()
    mapping = {c: c.replace("_", " ").title() for c in out.columns}
    # Special cases / branding
    mapping.update(
        {
            "sb_wb_hs_p": "SB / WB / HS / P",
            "sb_wb_hs": "SB / WB / HS / P",
            "component_a": "Component A",
            "component_b": "Component B",
            "end_use": "End Use",
        }
    )
    out.rename(columns=mapping, inplace=True)
    return out


def _results_column_widths(cols):
    """Column widths tuned for a wide, readable layout."""
    widths = {}
    for c in cols:
        if c in {"Component A", "Component B"}:
            widths[c] = "medium"
        elif c in {"Application", "Features"}:
            widths[c] = "medium"
        elif c in {"Category", "End Use"}:
            widths[c] = "small"
        else:
            widths[c] = "small"
    return widths


def _render_pdf_view_button(label: str, pdf_bytes: bytes, key: str) -> None:
    """Render a button that opens the PDF in a NEW browser tab.
    Uses a data: URL inside the new tab to avoid the Chrome 'about:blank until reload' behavior.
    """
    b64 = base64.b64encode(pdf_bytes).decode("utf-8")

    html = f"""
    <div style="margin: 0.25rem 0;">
      <button
        id="{key}"
        style="padding:0.45rem 0.7rem; border:1px solid #d1d5db; border-radius:0.5rem; background:white; cursor:pointer;"
      >
        📄 View PDS: {label}
      </button>
    </div>
    <script>
      (function() {{
        const btn = document.getElementById("{key}");
        if (!btn) return;

        btn.addEventListener("click", function() {{
          const pdfUrl = "data:application/pdf;base64,{b64}";

          const w = window.open("", "_blank");
          if (!w) return;

          w.document.open();
          w.document.write(`
            <!doctype html>
            <html>
              <head><title>{label} (PDS)</title></head>
              <body style="margin:0;">
                <iframe src="${{pdfUrl}}" style="border:0; width:100vw; height:100vh;"></iframe>
              </body>
            </html>
          `);
          w.document.close();
          w.focus();
        }});
      }})();
    </script>
    """

    components.html(html, height=70)


def _find_repo_root(start_path: Path) -> Path:
    """
    Walk upward from start_path until a directory containing 'data' is found.
    Assumes project layout:
        repo_root/
            data/
            src/
    """
    current = start_path
    for parent in [current, *current.parents]:
        if (parent / "data").exists():
            return parent
    raise RuntimeError("Could not locate repository root (folder containing 'data').")


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

APP_VERSION = "1.0.7"
#RUNNING_LABEL = "RUNNING: urethane_streamlit_1_0_5 (via shim)"
GIF_FILENAME = "sammorell.com_animated_header_no_loop.gif"


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
            #color: #6b7280; /* gray-ish */
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 0.95rem;
            margin-top: 0.1em;
            margin-bottom: 1em;
        }
        .ucr-section {
            color: #FFA500;
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 1.6rem;
            font-weight: 600;
            margin-top: 1.0em;
            margin-bottom: 0.5em;
            #border-top: 6px solid #e5e7eb;
            border-top: 2px solid rgb(255, 165, 0);
            padding-bottom: 0.2em;
        }

        .ucr-subsection {
            color: #000000;
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 1.2rem;
            font-weight: 600;
            margin-top: .5em;
            margin-bottom: 0.5em;
            # border-top: 2px solid #e5e7eb;
            padding-bottom: 0.2em;
        }

        /* --- DataFrame/table readability tweaks --- */
        div[data-testid="stDataFrame"] * {
            font-size: 16px !important;
        }
        div[data-testid="stDataFrame"] thead th {
            justify-content: flex-start !important; /* left align headers */
        }
        div[data-testid="stDataFrame"] td, div[data-testid="stDataFrame"] th {
            padding-top: 6px !important;
            padding-bottom: 6px !important;
        }

        
        /* --- Dataframe readability tweaks --- */
        div[data-testid="stDataFrame"] * {
            font-size: 16px !important;
        }
        div[data-testid="stDataFrame"] div[role="gridcell"] {
            padding-top: 0.35rem !important;
            padding-bottom: 0.35rem !important;
        }
        div[data-testid="stDataFrame"] div[role="columnheader"] {
            justify-content: flex-start !important; /* left align headers */
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

    
def section(title: str) -> None:
    st.markdown(f'<div class="ucr-section">{title}</div>', unsafe_allow_html=True)

def subsection(title: str) -> None:
    st.markdown(f'<div class="ucr-subsection">{title}</div>', unsafe_allow_html=True)


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

def render_product_type_guide(repo_root: Path) -> None:
    # ---- Product Type Guide ----

    # ---- Product Type Guide (from data/defaults/product_type.xlsx) ----
    # This section is intentionally self-contained so it doesn't affect the
    # Application/Product Guide logic above.

    product_type_path = repo_root / "data" / "defaults" / "product_type.xlsx"
    if not product_type_path.exists():
        st.info(f"Product Type Guide file not found: {product_type_path}")
        return

    try:
        pt_df = pd.read_excel(product_type_path)
    except Exception as e:
        st.error(f"Failed to load Product Type Guide dataset: {e}")
        return

    required_cols = {"Product Type", "Product Type Order"}
    if not required_cols.issubset(set(pt_df.columns)):
        st.error(
            "Product Type Guide dataset must include columns: "
            + ", ".join(sorted(required_cols))
        )
        return

    
    # Build dropdowns in the same style as the first guide:
    # cascade filters left-to-right based on the columns in the spreadsheet.
    # 'Product Type' is ordered by 'Product Type Order' (numeric ascending).

    section("Product Type Guide")
    
    pt_filter_cols = [c for c in pt_df.columns if c != "Product Type Order"]




    def _pt_unique(col, df):
        """Return UNIQUE dropdown values for a column.

        Goals:
        - Text columns (e.g., Product, Product Type, NCO Type/Form, Solvents) sort alphabetically.
        - Numeric columns (e.g., % Solids, NCO %, Viscosity, Equivalent Weight, Max. Free Monomer %) sort numerically.
        - Mixed label+number columns used for color/scale (e.g., 'HAZEN 40', 'GARDNER 2') use natural sort.
        - Always UNIQUE values.
        """
        series = df[col].dropna()

        s = series.astype(str).str.strip()
        s = s[s != ""]
        if s.empty:
            return []

        uniq_vals = pd.Series(s.unique()).tolist()

        col_lc = str(col).strip().casefold()

        alpha_cols = {"product", "product type", "nco type", "nco form", "solvents"}
        if col_lc in alpha_cols:
            return sorted(uniq_vals, key=lambda v: str(v).casefold())

        s_clean = pd.Series(uniq_vals).astype(str).str.replace(",", "", regex=False).str.strip()
        nums = pd.to_numeric(s_clean, errors="coerce")

        if nums.notna().all():
            uniq_nums = pd.Series(nums.unique()).sort_values(kind="mergesort")

            def _fmt(x):
                xf = float(x)
                return str(int(xf)) if xf.is_integer() else str(xf)

            return [_fmt(x) for x in uniq_nums.tolist()]

        num_re = re.compile(r"([-+]?(?:\d+\.?\d*|\d*\.?\d+))")

        def sort_key(v):
            v_str = str(v).strip()
            matches = num_re.findall(v_str.replace(",", ""))
            if matches:
                try:
                    num = float(matches[-1])
                except Exception:
                    num = float("inf")
                prefix = v_str[: v_str.rfind(matches[-1])].strip().casefold()
                return (0, prefix, num, v_str.casefold())
            return (1, "", float("inf"), v_str.casefold())

        return sorted(uniq_vals, key=sort_key)

    def _apply_filters(frame: pd.DataFrame, selections: dict, exclude_col: str | None = None) -> pd.DataFrame:
        out = frame
        for c, v in selections.items():
            if c == exclude_col:
                continue
            if v and v != "(All)":
                out = out[out[c].astype(str).str.strip() == str(v)]
        return out

    # Current selections (from session_state)
    selections = {col: st.session_state.get(f"pt_{col}", "(All)") for col in pt_filter_cols}

    # Render each selectbox with options limited by OTHER selections
    for col in pt_filter_cols:
        # Filter by all selections except this column
        frame_for_opts = _apply_filters(pt_df, selections, exclude_col=col)
        # Build options from the reduced frame
        opts = _pt_unique(col, frame_for_opts)

        # Safety: ensure numeric/natural ordering even if the column has mixed formats
        def _pt_sort_list(values, col_name: str):
            """Final safety sort for dropdown options.
            - For key text columns (Product, Product Type, NCO Type/Form, Solvents): pure alphabetical sort.
            - Otherwise: numeric sort if all numeric, else natural sort by embedded number.
            """
            if not values:
                return []
            vv = [str(v).strip() for v in values if str(v).strip() != ""]
            if not vv:
                return []

            col_lc = str(col_name).strip().casefold()
            alpha_cols = {"product", "product type", "nco type", "nco form", "solvents"}
            if col_lc in alpha_cols:
                return sorted(pd.Series(vv).unique().tolist(), key=lambda x: str(x).casefold())

            vclean = [v.replace(",", "").strip() for v in vv]
            nums = pd.to_numeric(pd.Series(vclean), errors="coerce")
            if nums.notna().all():
                uniq_nums = pd.Series(nums.unique()).sort_values(kind="mergesort")
                out = []
                for x in uniq_nums.tolist():
                    xf = float(x)
                    out.append(str(int(xf)) if xf.is_integer() else str(xf))
                return out

            num_re = re.compile(r"([-+]?(?:\d+\.?\d*|\d*\.?\d+))")
            uniq_vals = pd.Series(vv).unique().tolist()

            def sk(v):
                ms = num_re.findall(v.replace(",", ""))
                if ms:
                    try:
                        num = float(ms[-1])
                    except Exception:
                        num = float("inf")
                    prefix = v[: v.rfind(ms[-1])].strip().casefold()
                    return (0, prefix, num, v.casefold())
                return (1, "", float("inf"), v.casefold())

            return sorted(uniq_vals, key=sk)

        opts = _pt_sort_list(opts, col)
        opts = ["(All)"] + opts

        # If current selection is no longer valid, reset it
        current = selections[col]
        if current not in opts:
            current = "(All)"
            st.session_state[f"pt_{col}"] = "(All)"
            selections[col] = "(All)"

        # Render selectbox (index ensures stable selection)
        st.selectbox(
            col,
            opts,
            index=opts.index(current),
            key=f"pt_{col}",
        )

    # The fully-filtered result uses ALL selections
    filtered = _apply_filters(pt_df, {c: st.session_state[f"pt_{c}"] for c in pt_filter_cols})

    st.markdown("")  # spacer

#--------------------------------------------------------------------------------------------------





    if st.button("Get Product Type Recommendations", key="btn_product_types"):
        out = filtered.copy()
        # sort by spreadsheet order then drop the sort column from display/export
        out = out.sort_values(by=["Product Type Order", "Product Type"], kind="mergesort")
        out = out.drop(columns=["Product Type Order"], errors="ignore")

        out_pretty = _prettify_columns(out)

        if out_pretty.empty:
            st.warning("No matches for the selected Product Type filters.")
        else:
            st.dataframe(out_pretty, use_container_width=True)

            try:
                xlsx_bytes = export_recommendations_excel(out_pretty)
                st.download_button(
                    "Download Recommendations (Excel)",
                    data=xlsx_bytes,
                    file_name="Product Type Recommendations.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="dl_product_type_excel",
                )
            except Exception as e:
                st.error(f"Export failed: {e}")


def main() -> None:
    st.set_page_config(page_title="Sun Chemical Urethane Recommender", layout="wide")

    render_header()

    # Repo root (used for locating data/ and pds/ folders)
    repo_root = _find_repo_root(Path(__file__).resolve())

    section("Application/Product Guide")

    # ---- Data source ----
    with st.expander("Data source", expanded=False):
        st.write("application_product dataset is loaded.")
        uploaded = st.file_uploader("Upload Excel dataset of your choice.", type=["xlsx", "xls"])

    try:
        if uploaded is not None:
            df = load_uploaded_dataset(uploaded)
        else:
            df = load_application_product()
    except Exception as e:
        st.error(f"Failed to load dataset: {e}")
        return

    if not isinstance(df, pd.DataFrame):
        st.error("Failed to load dataset: loader did not return a DataFrame.")
        return


    # ---- Normalize columns for core filtering ----
    # The recommendation engine (urethane_core.filter_recommendations) expects snake_case
    # column names. Some Excel files (or older versions of this app) use Title Case.
    # Normalize here so UI + filtering operate on the same schema.
    _col_map = {
        "Category": "category",
        "End Use": "end_use",
        "EndUse": "end_use",
        "Application": "application",
        "Features": "features",
        "SB / WB / HS / P": "sb_wb_hs_p",
        "SB/WB/HS/P": "sb_wb_hs_p",
        "Composition": "composition",
    }
    df = df.rename(columns={k: v for k, v in _col_map.items() if k in df.columns}).copy()

    # Clean whitespace for key filter columns (string-safe)
    for _c in ["category", "end_use", "application", "features", "sb_wb_hs_p", "composition"]:
        if _c in df.columns:
            df[_c] = df[_c].astype(str).str.strip()

    # ---- Application/Product Guide ----

    import re as _re  # local alias (safe inside Streamlit reruns)

    def _ap_norm(v: str):
        """Normalize UI values for the core recommender.
        Returns None to mean 'no filter' (this avoids empty-string/empty-list edge cases).
        """
        if v is None:
            return None
        v = str(v).strip()
        return None if v in ("", "(All)") else v

    def _ap_find_col(frame: pd.DataFrame, candidates: list[str]) -> str:
        cols_lower = {c.strip().lower(): c for c in frame.columns}
        for cand in candidates:
            key = cand.strip().lower()
            if key in cols_lower:
                return cols_lower[key]
        raise KeyError(f"None of these columns found in dataset: {candidates}")

    # Prefer snake_case (what the core recommender typically uses), but fall back to Title Case
    AP_COLS = {
        "category": _ap_find_col(df, ["category"]),
        "end_use": _ap_find_col(df, ["end_use"]),
        "application": _ap_find_col(df, ["application"]),
        "features": _ap_find_col(df, ["features"]),
        "sb_wb_hs_p": _ap_find_col(df, ["sb_wb_hs_p"]),
        "composition": _ap_find_col(df, ["composition"]),
    }

    AP_KEYS_IN_UI_ORDER = ["category", "end_use", "application", "features", "sb_wb_hs_p", "composition"]

    # Init session state
    for k in AP_KEYS_IN_UI_ORDER:
        st.session_state.setdefault(f"ap_{k}", "(All)")

    def _apply_ap_filters(frame: pd.DataFrame, selections: dict[str, str], exclude_key: str | None = None) -> pd.DataFrame:
        out = frame
        for k, v in selections.items():
            if k == exclude_key:
                continue
            v = _ap_norm(v)
            if not v:
                continue

            col = AP_COLS[k]

            # Features is often multi-valued per cell; treat selection as a token/substring match
            if k == "features":
                out = out[out[col].fillna("").astype(str).str.contains(_re.escape(v), na=False)]
            else:
                out = out[out[col].astype(str).str.strip() == v]
        return out

    def _ap_unique_sorted(frame: pd.DataFrame, key: str) -> list[str]:
        col = AP_COLS[key]
        series = frame[col].dropna().astype(str).str.strip()

        # Numeric-aware sort when a column is truly numeric
        numeric_vals = pd.to_numeric(series, errors="coerce")
        if numeric_vals.notna().all():
            return numeric_vals.sort_values().astype(str).tolist()

        return sorted(series.unique().tolist())

    # Current selections
    ap_sel = {k: st.session_state.get(f"ap_{k}", "(All)") for k in AP_KEYS_IN_UI_ORDER}

    # Faceted dropdowns: options for each dropdown are filtered by *all other* selections
    for k in AP_KEYS_IN_UI_ORDER:
        frame_for_opts = _apply_ap_filters(df, ap_sel, exclude_key=k)
        opts = ["(All)"] + _ap_unique_sorted(frame_for_opts, k)

        current = ap_sel[k]
        if current not in opts:
            current = "(All)"
            st.session_state[f"ap_{k}"] = "(All)"
            ap_sel[k] = "(All)"

        label = {
            "category": "Category",
            "end_use": "End Use",
            "application": "Application",
            "features": "Features",
            "sb_wb_hs_p": "SB / WB / HS / P",
            "composition": "Composition",
        }[k]

        st.selectbox(label, opts, index=opts.index(current), key=f"ap_{k}")

    # Normalize values for the core recommender (it treats '' as "no filter")
    category = _ap_norm(st.session_state["ap_category"])
    end_use = _ap_norm(st.session_state["ap_end_use"])
    application = _ap_norm(st.session_state["ap_application"])
    features = _ap_norm(st.session_state["ap_features"])
    selected_features = [features] if features is not None else None
    sb_wb_hs_p = _ap_norm(st.session_state["ap_sb_wb_hs_p"])
    composition = _ap_norm(st.session_state["ap_composition"])

    # Optional: quick sanity check count (comment out if you don't want it)
    # st.caption(f"Matching rows in dataset (faceted): {len(_apply_ap_filters(df, ap_sel))}")
#-------------------------------------------------------------------------------------------



    # ---- Results ----
    
    if st.button("Get Application/Product Recommendations"):
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
            #if composition and "Composition" in results_df.columns:
                #results_df = results_df[results_df["Composition"].astype(str).eq(str(composition))].copy()

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

        results_display = _prettify_columns(results_out)
        col_widths = _results_column_widths(list(results_display.columns))
        column_config = {c: st.column_config.TextColumn(width=col_widths.get(c, "medium")) for c in results_display.columns}
        st.dataframe(results_display, use_container_width=True, hide_index=True, column_config=column_config)

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

                # Also offer a highlighted brochure download if the product appears in the brochure
                brochure_path = repo_root / "data" / "brochures" / BROCHURE_FILENAME
                if PYMUPDF_AVAILABLE and brochure_path.exists():
                    # Cached: fast after first run per product and brochure version
                    with st.spinner(f'Searching brochure for "{product}"...'):
                        b_bytes, pages = brochure_find_and_highlight(brochure_path, product)
                    if b_bytes:
                        any_found = True
                        st.success(
                            f'Found {product} in brochure: "{BROCHURE_FILENAME}" (highlighted)'
                            + (f" — pages: {pages}" if pages else "")
                        )
                        st.download_button(
                            label=f"Download brochure (highlighted): {product}",
                            data=b_bytes,
                            file_name=f"{product}_brochure_highlighted.pdf",
                            mime="application/pdf",
                            key=f"bro_dl_{i}",
                        )
                        st.divider()

            if not products_for_pds:
                st.info("No products found in the results to look up PDS files.")
            elif not any_found:
                st.info("No matching PDS PDFs were found in data/pds.")

        # Export

        try:
            xlsx_bytes = export_recommendations_excel(_prettify_columns(results_out))
            st.download_button(
                "Download Recommendations (Excel)",
                data=xlsx_bytes,
                file_name="Application Product Recommendations.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        except Exception as e:
            st.error(f"Export failed: {e}")
            return
        
    render_product_type_guide(repo_root)
