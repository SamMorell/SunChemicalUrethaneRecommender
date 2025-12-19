"""Core (framework-agnostic) logic for the Sun Chemical urethane recommender.

Extracted from the original Streamlit app so the data + filtering + export
can be reused from:
- Streamlit UI
- Flask/FastAPI API
- CLI scripts
"""

from __future__ import annotations

from io import BytesIO
from typing import Dict, List, Tuple, Any

import pandas as pd


REQUIRED_COLS = [
    "Category", "End_Use", "Application", "Features",
    "SB_WB_HS_P", "Composition", "Component_A", "Component_B"
]
OPTIONAL_SORT_COLS = ["Category_Sort_Order", "End_Use_Sort_Order"]


def _make_row(Application, Features, SB_WB_HS_P, Composition, Component_A, Component_B=None):
    return {
        "Application": Application,
        "Features": Features,
        "SB_WB_HS_P": SB_WB_HS_P,
        "Composition": Composition,
        "Component_A": Component_A,
        "Component_B": Component_B,
    }


# Default dataset (kept identical to your Streamlit script)
SAMPLE_DATA: Dict[str, Dict[str, List[Dict[str, Any]]]] = {
    # ---------------------------------------------------------
    # PRODUCTS FOR WOOD Application (pages 44–49)
    # ---------------------------------------------------------
    "Products for wood Application": {
        # Page 44 – Barrier primers
        "Barrier Primers": [
            _make_row("Barrier Primers", "Deep Penetration", "SB", "1K",
                     "POLURENE MD 50 EA"),
            _make_row("Barrier Primers", "Deep Penetration", "SB", "2K",
                     "VINYLIC RESIN", "POLURENE MD 50 EA"),
            _make_row("Barrier Primers", "Long Pot Life", "SB", "2K",
                     "REXIN HSP 411", "POLURGREEN AD 75 EA"),
            _make_row("Barrier Primers", "Not Yellowing", "SB", "2K",
                     "REXIN HSP 411", "POLURGREEN MT 75 MX"),
        ],

        # Page 45 – Sealers
        "Sealers": [
            _make_row("Sealers", "Clear for MDF slabs", "SB", "1K",
                     "POLURENE MD 50 EA"),
            _make_row("Sealers", "Clear not yellowing", "SB", "1K",
                     "POLURGREEN MC 1180 M"),
            _make_row("Sealers", "Clear", "SB", "1K",
                     "UCOPOL OL 1850 X"),
            _make_row("Sealers", "Clear – hard flexible", "WB", "1K",
                     "BLUECRYL 012", "BLUEPUR 2937"),
            _make_row("Sealers", "Clear", "WB", "1K",
                     "BLUECRYL 092"),
            _make_row("Sealers", "Clear", "SB", "2K",
                     "REXIN 129 50 X / REXIN DP 343",
                     "POLURGREEN AD 75 EA"),
            _make_row("Sealers", "Clear", "SB", "2K",
                     "REXIN C760", "POLURGREEN 60T"),
            _make_row("Sealers", "Pigmented", "SB", "2K",
                     "REXIN C760", "POLURGREEN 60T"),
            _make_row("Sealers", "Pigmented - high solid", "SB", "2K",
                     "REXIN HSP 05100", "POLURGREEN 60T"),
            _make_row("Sealers", "Pigmented", "WB", "2K",
                     "BLUECRYL 233", "HYDRORENE AW 1"),
        ],

        # Page 46 – Gloss top coats
        "Top Coats - Gloss": [
            _make_row("Gloss Top Coat", "Clear", "SB", "1K",
                     "POLURGREEN MC 5860 MX"),
            _make_row("Gloss Top Coat", "Clear not yellowing", "SB", "1K",
                     "POLURGREEN MC 1180 M"),
            _make_row("Gloss Top Coat", "Clear", "SB", "1K",
                     "UCOPOL OL 1760 WD"),
            _make_row("Gloss Top Coat", "Clear", "WB", "1K",
                     "BLUECRYL 012", "BLUEPUR 2937"),
            _make_row("Gloss Top Coat", "Clear", "WB", "1K",
                     "BLUECRYL 092"),
            _make_row("Gloss Top Coat", "Clear", "SB", "2K",
                     "REXIN DP 127",
                     "POLURGREEN AD 75 EA / POLURGREEN IR 50 BA"),
            _make_row("Gloss Top Coat", "Clear", "SB", "2K",
                     "REXIN HG 60 X", "POLURGREEN 60T"),
            _make_row("Gloss Top Coat", "Clear - high solid", "SB", "2K",
                     "REXIN DS 214 80 BA", "POLURGREEN OK HD"),
            _make_row("Gloss Top Coat", "Pigmented", "SB", "2K",
                     "REXIN DP 127", "POLURGREEN OK HD"),
            _make_row("Gloss Top Coat", "Pigmented", "WB", "2K",
                     "BLUECRYL 242", "HYDRORENE AW 5"),
            _make_row("Gloss Top Coat", "Clear", "WB", "2K",
                     "BLUECRYL 233", "HYDRORENE AW 5"),
            _make_row("Gloss Top Coat", "Clear", "WB", "2K",
                     "WATERSOL AC 3080",
                     "BURNOCK PU 8985 or HYDRORENE AW 65"),
        ],

        # Page 47 – Matte top coats
        "Top Coats - Matte": [
            _make_row("Matte Top Coats", "Clear", "SB", "1K",
                     "UCOPOL OL 1850 X"),
            _make_row("Matte Top Coats", "Clear", "WB", "1K",
                     "BLUECRYL 012", "BLUEPUR 2937"),
            _make_row("Matte Top Coats", "Clear", "WB", "1K",
                     "BLUECRYL 092", "BLUEPUR 2937"),
            _make_row("Matte Top Coats", "Clear", "SB", "2K",
                     "REXIN 590 70 BA",
                     "POLURGREEN AD 75 EA / POLURGREEN IR 50 BA"),
            _make_row("Matte Top Coats", "Clear", "SB", "2K",
                     "REXIN C760", "POLURGREEN 60T"),
            _make_row("Matte Top Coats", "Clear", "SB", "2K",
                     "REXIN 129 50 X / REXIN DP 343",
                     "POLURGREEN OK"),
            _make_row("Matte Top Coats", "Pigmented", "SB", "2K",
                     "REXIN C760", "POLURGREEN OK"),
            _make_row("Matte Top Coats", "Pigmented", "SB", "2K",
                     "REXIN 590 70 BA", "POLURGREEN OK"),
            _make_row("Matte Top Coats", "Pigmented", "SB", "2K",
                     "REXIN 129 50 X / REXIN DP343",
                     "POLURGREEN OK"),
            _make_row("Matte Top Coats", "Clear, fast drying", "WB", "2K",
                     "WATERSOL AC 7000",
                     "BURNOCK PU 8985 or HYDRORENE AW 65"),
        ],

        # Page 48 – Wood flooring
        "Wood Flooring": [
            # Sealers
            _make_row("Sealers", "Fast curing", "SB", "1K",
                     "UCOPOL OL 1850 X"),
            _make_row("Sealers", "Fast sanding", "WB", "1K",
                     "BLUECRYL 012", "BLUEPUR 2937"),
            _make_row("Sealers", "Fast sanding", "SB", "2K",
                     "REXIN 129 50 X / REXIN DP 343",
                     "POLURGREEN AD 75 EA / POLURGREEN IR 50 BA"),
            # Gloss top coats
            _make_row("Gloss Top Coat",
                     "Fast curing – high performance", "SB", "1K",
                     "POLURGREEN MC 5860 MX"),
            _make_row("Gloss Top Coat",
                     "High performance - not yellowing", "SB", "1K",
                     "POLURGREEN MC 1180 M"),
            _make_row("Gloss Top Coat", "Easy to apply", "SB", "1K",
                     "UCOPOL OL 1760 WD"),
            _make_row("Gloss Top Coat",
                     "Fast drying – high performance", "WB", "1K",
                     "BLUEPUR 2937", "BLUECRYL 012"),
            _make_row("Gloss Top Coat", "High performance", "SB", "2K",
                     "REXIN DP 127",
                     "POLURGREEN AD 75 EA / POLURGREEN IR 50 BA"),
            _make_row("Gloss Top Coat", "High performance", "WB", "2K",
                     "BLUEPUR 2937 / BLUEPUR 3070",
                     "HYDRORENE AW 65"),
            # Matte top coats
            _make_row("Matte Top Coats", "Easy to apply", "SB", "1K",
                     "UCOPOL OL 18 50 X"),
            _make_row("Matte Top Coats",
                     "Fast drying - high performance", "WB", "1K",
                     "BLUEPUR 2937", "BLUECRYL 012"),
            _make_row("Matte Top Coats",
                     "High performance – also deep matte", "WB", "2K",
                     "BLUEPUR 2937 / BLUEPUR 3070",
                     "HYDRORENE AW 65"),
        ],

        # Page 49 – Outdoor
        "Outdoor": [
            # Sealers
            _make_row("Sealers", "Fast curing", "SB", "1K",
                     "UCOPOL OL 18 50 X"),
            _make_row("Sealers", "Deep penetration", "SB", "1K",
                     "UCOPOL OL 17 60 WD"),
            _make_row("Sealers", "High yellowing resistance", "SB", "1K",
                     "UCOPOL OL W 41 55 WD"),
            _make_row("Sealers",
                     "Fast drying – high vapour permeability",
                     "WB", "1K", "BLUECRYL 099"),
            # Top coats – gloss
            _make_row("Top Coats Gloss", "High covering", "SB", "1K",
                     "UCOPOL OL 17 60 WD"),
            _make_row("Top Coats Gloss", "High yellowing resistance", "SB", "1K",
                     "UCOPOL OL W 41 55 WD"),
            _make_row("Top Coats Gloss",
                     "Fast drying – high vapour permeability",
                     "WB", "1K", "BLUECRYL 099"),
            # Top coats – matte
            _make_row("Top Coats Matte",
                     "Fast drying – high vapour permeability",
                     "WB", "1K", "BLUECRYL 099"),
        ],
    },

    # ---------------------------------------------------------
    # PRODUCTS FOR BUILDING AND CONSTRUCTION (pages 50–54)
    # ---------------------------------------------------------
    "Products for building and construction": {
        # Pages 50–51 – Flooring
        "Flooring": [
            # Primers
            _make_row("Primers",
                     "Deep penetration waterproof barrier",
                     "SB", "1K",
                     "UCOPOL M 621 / POLURGREEN MC 5860 MX / POLURGREEN PRP 940"),
            _make_row("Primers",
                     "Powder fixative – cold climate", "HS", "1K",
                     "UCOPOL M 601"),
            _make_row("Primers",
                     "Powder fixative – hot climate", "HS", "1K",
                     "UCOPOL M 602"),
            # Self-levelling sealants
            _make_row("Self levelling sealants",
                     "For flexible joints", "HS", "2K",
                     "ETHACURE 300 / POLURGREEN PRP 450 / POLURGREEN PRP 5500"),
            _make_row("Self levelling sealants",
                     "For flexible joints", "HS", "2K",
                     "REXIN HSP 50", "POLURENE MD 1600"),
            # Self-levelling or spatulate top coats
            _make_row("Self levelling or spatulate top coats",
                     "Improves impact resistance", "HS", "2K",
                     "EPOXY", "POLURGREEN LP 100 LV / POLYAMINE ADDUCTS"),
            _make_row("Self levelling or spatulate top coats",
                     "Hard flexible", "HS", "2K",
                     "REXIN HSP 05100 / REXIN HSP 50",
                     "POLURENE MD 1500 / POLURENE MD 1600"),
            _make_row("Self levelling or spatulate top coats",
                     "Flexible, not yellowing", "HS", "2K",
                     "REXIN HSP 05100",
                     "POLURGREEN MT 100 / POLURGREEN MT 100 LLV"),
            _make_row("Self levelling or spatulate top coats",
                     "\"Not yellowing\"", "HS", "2K",
                     "FINEPLUS HY 6000",
                     "POLURGREEN MT 100 LV / POLURGREEN ML 2000"),
            # Top coats (page 51)
            _make_row("Top Coats",
                     "High resistance, fast curing, not yellowing",
                     "SB", "1K", "POLURGREEN MC 1180 M"),
            _make_row("Top Coats",
                     "High resistance, fast curing (indoor use)",
                     "SB", "1K", "POLURGREEN MC 5860 MX"),
            _make_row("Top Coats",
                     "High resistance, clear and pigmented",
                     "SB", "2K",
                     "REXIN DP 127",
                     "POLURGREEN MT 75 MX / POLURGREEN MT 100"),
            _make_row("Top Coats",
                     "Domestic area", "WB", "1K",
                     "BLUEPUR 2937", "BLUECRYL 012"),
            _make_row("Top Coats",
                     "Commercial area, clear and pigmented", "WB", "2K",
                     "BLUECRYL 233", "HYDRORENE AW 65"),
            _make_row("Top Coats",
                     "Commercial area, clear and pigmented", "WB", "2K",
                     "BLUECRYL 242", "HYDRORENE AW 1 / HYDRORENE AW 65"),
            # Stone carpets
            _make_row("Stone Carpets",
                     "5–7% suggested quantity amount", "SB", "1K",
                     "POLURGREEN MC 1180 M"),
            _make_row("Stone Carpets",
                     "5–7% suggested quantity amount", "HS", "2K",
                     "FINEPLUS HY 6000",
                     "POLURGREEN MT 100 LV / POLURGREEN ML 2000"),
            _make_row("Stone Carpets",
                     "5–7% suggested quantity amount", "HS", "2K",
                     "REXIN HSP 05100", "POLURGREEN MT 100 LV"),
            # Rubber crumbs
            _make_row("Rubber Crumbs",
                     "Flexible", "HS", "1K",
                     "POLURENE LPI 604"),
            _make_row("Rubber Crumbs",
                     "Modulable flexibility", "SB", "1K",
                     "POLURGREEN PRP 450 / POLURGREEN AD"),
            _make_row("Rubber Crumbs",
                     "Not yellowing, modulable flexibility", "SB", "1K",
                     "POLURGREEN MC 1180 M / POLURGREEN PRP 4041"),
        ],

        # Page 52 – Walls
        "Walls": [
            # Thixotropic sealers
            _make_row("Thixotropic sealers",
                     "Slow blowing", "HS", "1K",
                     "POLURGREEN PRP 450 / POLURGREEN PRP 350"),
            _make_row("Thixotropic sealers",
                     "Constant dimension", "HS", "2K",
                     "EPOXY",
                     "POLURGREEN LP 100 LV / POLYAMINES ADDUCTS"),
            # Antigraffiti
            _make_row("Antigraffiti",
                     "Clear systems", "SB", "1K",
                     "POLURGREEN MC 1180 M"),
            _make_row("Antigraffiti",
                     "Clear systems", "WB", "2K",
                     "BLUECRYL 233", "HYDRORENE AW1 / HYDRORENE AW 65"),
            _make_row("Antigraffiti",
                     "Pigmented systems", "WB", "2K",
                     "BLUECRYL 242", "HYDRORENE AW1 / HYDRORENE AW 65"),
            _make_row("Antigraffiti",
                     "Clear or pigmented", "WB", "2K",
                     "WATERSOL AC 3080",
                     "BURNOCK PU 8985 or HYDRORENE AW 65"),
        ],

        # Page 53 – Roofing
        "Roofing": [
            _make_row("Membranes",
                     "High flexibility, excellent waterproofing resistance",
                     "SB", "1K",
                     "POLURGREEN PRP 450 / POLURGREEN PRP 940"),
            _make_row("Membranes",
                     "High performance, easy to manufacture", "SB", "2K",
                     "FINEPLUS HY 6000",
                     "POLURGREEN PRP 450 / POLURGREEN PRP 5500"),
            _make_row("Membranes",
                     "High performance, easy to manufacture", "HS", "2K",
                     "ETHACURE 300", "POLURGREEN PRP 450"),
            _make_row("Membranes",
                     "Easy to manufacture", "WB", "1K",
                     "BLUEPUR XP 2561"),
            _make_row("Membranes",
                     "Price/performance ratio", "HS", "2K",
                     "ASPHALT", "POLURENE MD 1600"),
        ],

        # Page 54 – Adhesives and foams
        "Adhesives and foams": [
            # Adhesives
            _make_row("Adhesives", "Wood flooring", "HS", "1K",
                     "POLURGREEN PRP 450"),
            _make_row("Adhesives", "Wood flooring", "HS", "2K",
                     "REXIN HSP 05100 / REXIN HSP 50",
                     "POLURENE MD 1600"),
            _make_row("Adhesives", "Wood flooring", "HS", "2K",
                     "EPOXY",
                     "POLURGREEN LP 100 LV / POLYAMINES ADDUCT"),
            _make_row("Adhesives", "Linoleum", "HS", "2K",
                     "EPOXY",
                     "POLURGREEN LP 100 LV / POLYAMINES ADDUCT"),
            _make_row("Adhesives", "PVC", "HS", "2K",
                     "EPOXY",
                     "POLURGREEN LP 100 LV / POLYAMINES ADDUCT"),
            # Foams
            _make_row("Foams", "OCF", "HS", "1K",
                     "POLURGREEN PRP F 930"),
            _make_row("Foams", "Liquid at room temperature", "HS", "2K",
                     "REXIN HSP 50", "POLURENE MD 1600"),
        ],
    },

    # ---------------------------------------------------------
    # PRODUCTS FOR Application ON METAL (pages 55–58)
    # ---------------------------------------------------------
    "Products for Application on metal": {
        # Page 55 – Primers
        "Primers": [
            _make_row("Primers", "Zinc dust", "SB", "1K",
                     "UCOPOL M 621"),
            _make_row("Primers", "Hard flexible zinc dust", "SB", "1K",
                     "POLURGREEN PRP 450 / POLURGREEN AD 67 MX"),
            _make_row("Primers", "For DIY", "WB", "1K",
                     "BLUECRYL 099"),
            _make_row("Primers", "Pigmented", "WB", "1K",
                     "WATERSOL HY 3360"),
            _make_row("Primers", "Pigmented", "WB", "1K",
                     "WATERSOL EP 5501"),
            _make_row("Primers", "Zinc rich primer", "SB", "2K",
                     "BURNOCK EP 9547", "AMINO ADDUCT"),
            _make_row("Primers", "Pigmented", "SB", "2K",
                     "BURNOCK EP 9547", "POLURGREEN AD 67 MX"),
            _make_row("Primers", "Pigmented", "SB", "2K",
                     "REXIN DP 127 / BURNOCK PE 2101",
                     "POLURGREEN OK HD"),
        ],

        # Page 56 – DTM
        "DTM": [
            _make_row("DTM",
                     "Semi-duty, sagging resistance", "WB", "1K",
                     "WATERSOL HY 3360"),
            _make_row("DTM",
                     "Good resistance to yellowing", "SB", "1K",
                     "UCOPOL OL W 41 55 WD"),
            _make_row("DTM",
                     "Good resistance to yellowing", "SB", "2K",
                     "REXIN DP 127 / BURNOCK PE 2101",
                     "POLURGREEN MT 75 MX"),
            _make_row("DTM",
                     "Excellent resistance to yellowing", "SB", "2K",
                     "REXIN DP 127 / REXIN DP 500",
                     "POLURGREEN MT 75 MX"),
            _make_row("DTM",
                     "Solvent free", "HS", "2K",
                     "POLYASPARTICS", "POLURGREEN MT 100 LLV"),
            _make_row("DTM",
                     "High gloss, low VOC", "HS", "2K",
                     "BURNOCK AC 3723", "POLURGREEN MT 75 BA"),
            _make_row("DTM",
                     "High durability", "WB", "2K",
                     "WATERSOL AC 3080",
                     "BURNOCK PU 8985 or HYDRORENE AW 5"),
            _make_row("DTM",
                     "Acrylic powder coating", "P", "1K",
                     "FINEPLUS AC 2810", "LINEAR DIACID HARDENER"),
            _make_row("DTM",
                     "Polyester powder coating", "P", "1K",
                     "CARBOXYLIC POLYESTER RESINS",
                     "FINEPLUS AC 2660"),
            _make_row("DTM",
                     "Polyester powder coating, matte, superdurable",
                     "P", "1K",
                     "BI FUNCTIONAL POLYESTER RESINS",
                     "FINEPLUS AC 2660 / FINEPLUS AC 2490"),
            _make_row("DTM",
                     "Polyester powder coating, matte", "P", "1K",
                     "CARBOXYLIC POLYESTER RESINS",
                     "FINEPLUS AC 2790"),
        ],

        # Page 57 – Top coats
        "Top Coats": [
            _make_row("Top Coats",
                     "Clear, high performance", "SB", "2K",
                     "REXIN 2268 / BURNOCK AC 1612",
                     "POLURGREEN MT 75 MX"),
            _make_row("Top Coats",
                     "Clear, fast performing", "SB", "2K",
                     "REXIN 2268 / BURNOCK AC 8820",
                     "POLURGREEN MT 75 MX"),
            _make_row("Top Coats",
                     "Pigmented", "SB", "2K",
                     "REXIN DP 127 / BURNOCK PE 2101",
                     "POLURGREEN MT 75 MX"),
            _make_row("Top Coats",
                     "Pigmented", "SB", "2K",
                     "REXIN DP 127 / REXIN HSP 412",
                     "POLURGREEN MT 75 MX"),
            _make_row("Top Coats",
                     "Pigmented, fast curing", "SB", "2K",
                     "REXIN 2268 / BURNOCK AC 1835",
                     "POLURGREEN MT 75 MX"),
            _make_row("Top Coats",
                     "Automotive refinish", "SB", "2K",
                     "BURNOCK AC 1612", "POLURGREEN MT 100 LV"),
            _make_row("Top Coats",
                     "Automotive refinish, low VOC", "SB", "2K",
                     "BURNOCK AC 7208", "POLURGREEN MT 100 LV"),
            _make_row("Top Coats",
                     "Clear", "WB", "2K",
                     "BLUECRYL 233", "HYDRORENE AW 1"),
            _make_row("Top Coats",
                     "Clear, high performance", "WB", "2K",
                     "WATERSOL AC 3080", "HYDRORENE AW 5"),
            _make_row("Top Coats",
                     "Pigmented ACE", "WB", "2K",
                     "BLUECRYL 242", "HYDRORENE AW 1"),
        ],

        # Page 58 – Stoving
        "Stoving": [
            _make_row("Stoving", "Not yellowing", "SB", "1K",
                     "BURNOCK PE 2101", "POLURENE BK 1175"),
            _make_row("Stoving", "Not yellowing", "SB", "1K",
                     "REXIN HSP 417", "POLURENE BK 1175"),
            _make_row("Stoving", "High mechanical strength", "SB", "1K",
                     "REXIN HSP 411 / REXIN HSP 412",
                     "POLURENE BK 5250 ME"),
            _make_row("Stoving", "Topcoat, clear", "SB", "1K",
                     "BURNOCK PE 2133 / BURNOCK PE 6202",
                     "MELAMINE"),
            _make_row("Stoving", "Low curing temp.", "WB", "1K",
                     "WATERSOL AC 3080", "MELAMINE"),
            _make_row("Stoving", "High resistance to chemicals", "WB", "1K",
                     "BLUECRYL 233", "MELAMINE"),
            _make_row("Stoving", "Anticorrosion", "WB", "1K",
                     "WATERSOL EP 5501", "MELAMINE"),
            _make_row("Stoving", "High resistance to chemicals", "WB", "1K",
                     "BLUECRYL 242", "MELAMINE"),
        ],
    },
}


def default_data_to_df() -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for category, end_use_dict in SAMPLE_DATA.items():
        for end_use, items in end_use_dict.items():
            for item in items:
                rows.append(
                    {
                        "Category": category,
                        "End_Use": end_use,
                        "Application": item["Application"],
                        "Features": item["Features"],
                        "SB_WB_HS_P": item["SB_WB_HS_P"],
                        "Composition": item["Composition"],
                        "Component_A": item["Component_A"],
                        "Component_B": item.get("Component_B"),
                    }
                )

    df = pd.DataFrame(rows)
    df["Component_B"] = df["Component_B"].where(df["Component_B"].notna(), None)
    for c in OPTIONAL_SORT_COLS:
        if c not in df.columns:
            df[c] = pd.NA
    return df


def validate_schema(df: pd.DataFrame) -> Tuple[bool, List[str]]:
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    return (len(missing) == 0), missing


def load_data_file(fileobj_or_path) -> pd.DataFrame:
    name = getattr(fileobj_or_path, "name", "")
    if isinstance(fileobj_or_path, str):
        name = fileobj_or_path.lower()
    else:
        name = str(name).lower()

    if name.endswith(".csv"):
        df = pd.read_csv(fileobj_or_path)
    elif name.endswith((".xlsx", ".xls")):
        df = pd.read_excel(fileobj_or_path)
    else:
        raise ValueError("Unsupported file type. Please provide a CSV or Excel (.xlsx/.xls) file.")

    ok, missing = validate_schema(df)
    if not ok:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")

    df["Component_B"] = df["Component_B"].where(df["Component_B"].notna(), None)
    for c in OPTIONAL_SORT_COLS:
        if c not in df.columns:
            df[c] = pd.NA
    return df


def sorted_categories(df: pd.DataFrame) -> List[str]:
    if "Category_Sort_Order" not in df.columns:
        return sorted(df["Category"].dropna().unique().tolist())

    tmp = df[["Category", "Category_Sort_Order"]].drop_duplicates()
    tmp["Category_Sort_Order"] = pd.to_numeric(tmp["Category_Sort_Order"], errors="coerce")
    tmp = tmp.sort_values(["Category_Sort_Order", "Category"], na_position="last")
    return tmp["Category"].tolist()


def sorted_end_uses(df: pd.DataFrame, category: str) -> List[str]:
    subset = df[df["Category"] == category]
    if subset.empty:
        return []

    if "End_Use_Sort_Order" not in subset.columns:
        return sorted(subset["End_Use"].dropna().unique().tolist())

    tmp = subset[["End_Use", "End_Use_Sort_Order"]].drop_duplicates()
    tmp["End_Use_Sort_Order"] = pd.to_numeric(tmp["End_Use_Sort_Order"], errors="coerce")
    tmp = tmp.sort_values(["End_Use_Sort_Order", "End_Use"], na_position="last")
    return tmp["End_Use"].tolist()


def unique_sorted(df: pd.DataFrame, col: str) -> List[str]:
    return sorted(df[col].dropna().unique().tolist())


def recommend(
    df: pd.DataFrame,
    category: str,
    end_use: str,
    application: str,
    features: str,
    sb_wb_hs_p: str,
    composition: str,
) -> pd.DataFrame:
    out = df[
        (df["Category"] == category)
        & (df["End_Use"] == end_use)
        & (df["Application"] == application)
        & (df["Features"] == features)
        & (df["SB_WB_HS_P"] == sb_wb_hs_p)
        & (df["Composition"] == composition)
    ].copy()

    export_cols = [
        "Category", "End_Use", "Application", "Features",
        "SB_WB_HS_P", "Composition", "Component_A", "Component_B"
    ]
    export_cols = [c for c in export_cols if c in out.columns]
    return out[export_cols].reset_index(drop=True)


def to_excel_bytes(df: pd.DataFrame, sheet_name: str = "Sheet1") -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output) as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    output.seek(0)
    return output.getvalue()


# -----------------------------
# Adapter functions for UI layers (Streamlit/Flask/etc.)
# -----------------------------

def load_default_dataset() -> pd.DataFrame:
    """Return the built-in default dataset as a DataFrame."""
    return default_data_to_df()


def load_uploaded_dataset(fileobj_or_path) -> pd.DataFrame:
    """Load a user-provided CSV/XLSX (path or file-like) and validate schema."""
    return load_data_file(fileobj_or_path)


def get_dropdown_options(df: pd.DataFrame):
    """Return dropdown option providers compatible with thin Streamlit wrappers."""
    def end_use_fn(category: str):
        return sorted_end_uses(df, category)

    def application_fn(category: str, end_use: str):
        sub = df[(df["Category"] == category) & (df["End_Use"] == end_use)]
        return unique_sorted(sub, "Application")

    def features_fn(category: str, end_use: str, application: str):
        sub = df[(df["Category"] == category) & (df["End_Use"] == end_use) & (df["Application"] == application)]
        return unique_sorted(sub, "Features")

    def sb_fn(category: str, end_use: str, application: str, features: str):
        sub = df[
            (df["Category"] == category) &
            (df["End_Use"] == end_use) &
            (df["Application"] == application) &
            (df["Features"] == features)
        ]
        return unique_sorted(sub, "SB_WB_HS_P")

    def comp_fn(category: str, end_use: str, application: str, features: str, sb_wb_hs: str):
        sub = df[
            (df["Category"] == category) &
            (df["End_Use"] == end_use) &
            (df["Application"] == application) &
            (df["Features"] == features) &
            (df["SB_WB_HS_P"] == sb_wb_hs)
        ]
        return unique_sorted(sub, "Composition")

    return {
        "category": sorted_categories(df),
        "end_use": end_use_fn,
        "application": application_fn,
        "features": features_fn,
        "sb_wb_hs": sb_fn,
        "composition": comp_fn,
    }


def filter_recommendations(
    df: pd.DataFrame,
    category: str,
    end_use: str,
    application: str,
    features: str,
    sb_wb_hs: str,
    composition: str,
) -> pd.DataFrame:
    """Filter the dataset and return recommendation rows."""
    return recommend(
        df=df,
        category=category,
        end_use=end_use,
        application=application,
        features=features,
        sb_wb_hs_p=sb_wb_hs,
        composition=composition,
    )


def export_recommendations_excel(df: pd.DataFrame, sheet_name: str = "Recommendations") -> bytes:
    """Export recommendations to XLSX bytes."""
    return to_excel_bytes(df, sheet_name=sheet_name)
