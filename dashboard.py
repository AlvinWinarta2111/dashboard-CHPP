import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="Equipment Condition Dashboard", layout="wide")
st.title("📊 Equipment Condition Dashboard")

REQUIRED_COLS = {
    "AREA",
    "SYSTEM",
    "EQUIPMENT DESCRIPTION",
    "DATE",
    "CONDITION MONITORING SCORE",
    "VIBRATION",
    "OIL ANALYSIS",
    "TEMPERATURE",
    "OTHER INSPECTION",
}

# ---------- Helpers ----------

def load_scorecard(xlsx_file) -> pd.DataFrame:
    """Read the 'Scorecard' sheet and auto-detect header row.
    Tries header rows [1, 0, 2, 3, 4] and returns the first that contains REQUIRED_COLS.
    """
    tried = []
    for hdr in [1, 0, 2, 3, 4]:  # Row 2 in Excel is header=1
        try:
            df = pd.read_excel(xlsx_file, sheet_name="Scorecard", header=hdr)
            df.columns = df.columns.str.strip().str.upper()
            if REQUIRED_COLS.issubset(set(df.columns)):
                return df
            tried.append((hdr, df.columns.tolist()))
        except Exception as e:
            tried.append((hdr, f"error: {e}"))
    st.error(
        "Could not find all required columns in 'Scorecard'.\n"
        + "Required: " + ", ".join(sorted(REQUIRED_COLS))
    )
    with st.expander("Debug: header attempts"):
        for hdr, cols in tried:
            st.write(f"header={hdr}", cols)
    st.stop()


def coerce_score(val):
    """Map various inputs to a 1–3 score. Returns int 1..3 or None.
    - Numeric -> clamped to 1..3
    - Text -> map common labels (good/normal/ok=3, fair/alert=2, bad/poor/fail=1)
    """
    if pd.isna(val):
        return None
    # numeric path
    try:
        v = float(str(val).strip())
        v = int(round(v))
        return max(1, min(3, v))
    except Exception:
        pass
    # text path
    s = str(val).strip().lower()
    map3 = {
        "3", "good", "normal", "ok", "green", "pass", "low risk", "baik",
    }
    map2 = {
        "2", "fair", "medium", "moderate", "yellow", "alert", "cukup",
    }
    map1 = {
        "1", "bad", "poor", "fail", "red", "critical", "buruk", "need action", "action",
    }
    if s in map3:
        return 3
    if s in map2:
        return 2
    if s in map1:
        return 1
    # fallback: try parse last-resort digits in text
    for ch in ("1", "2", "3"):
        if ch == s:
            return int(ch)
    return None


def score_to_status(score: float) -> str:
    if pd.isna(score):
        return "UNKNOWN"
    score = int(score)
    return {1: "RED", 2: "AMBER", 3: "GREEN"}.get(score, "UNKNOWN")


def color_status(val: str):
    colors = {
        "RED": "#ff4d4f",
        "AMBER": "#faad14",
        "GREEN": "#52c41a",
        "UNKNOWN": "#8c8c8c",
    }
    return f"background-color: {colors.get(val, '#8c8c8c')}; color: white;"


def to_csv_download(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")

# ---------- UI: File upload ----------

uploaded = st.file_uploader("Upload Excel file (Scorecard sheet)", type=["xlsx", "xlsm"]) 

if not uploaded:
    st.info("👆 Please upload your Excel file to begin. The sheet must be named 'Scorecard'.")
    st.stop()

# ---------- Load & clean ----------

df = load_scorecard(uploaded)

# Drop completely empty rows
if "EQUIPMENT DESCRIPTION" in df.columns:
    df = df[df["EQUIPMENT DESCRIPTION"].notna()]

# Date handling (dd/mm/yyyy expected)
df["DATE"] = pd.to_datetime(df["DATE"], dayfirst=True, errors="coerce")

# ---------- Sidebar: Filters ----------

st.sidebar.header("🔍 Filters")

# Date range picker
if df["DATE"].notna().any():
    mind = pd.to_datetime(df["DATE"].min())
    maxd = pd.to_datetime(df["DATE"].max())
    start_date, end_date = st.sidebar.date_input(
        "Date range",
        [mind.date(), maxd.date()],
        min_value=mind.date(),
        max_value=maxd.date(),
    )
    mask_date = (df["DATE"] >= pd.Timestamp(start_date)) & (df["DATE"] <= pd.Timestamp(end_date))
    df = df.loc[mask_date]
else:
    st.sidebar.caption("No valid dates detected; skipping date filter.")

# Area/System/Equipment filters
areas = sorted([x for x in df["AREA"].dropna().unique()])
systems = sorted([x for x in df["SYSTEM"].dropna().unique()])
equipments = sorted([x for x in df["EQUIPMENT DESCRIPTION"].dropna().unique()])

sel_areas = st.sidebar.multiselect("AREA", areas, default=areas)
sel_systems = st.sidebar.multiselect("SYSTEM", systems, default=systems)
sel_equips = st.sidebar.multiselect("EQUIPMENT DESCRIPTION", equipments, default=equipments)

mask_filters = (
    df["AREA"].isin(sel_areas)
    & df["SYSTEM"].isin(sel_systems)
    & df["EQUIPMENT DESCRIPTION"].isin(sel_equips)
)
df = df.loc[mask_filters].copy()

# ---------- Scoring Logic ----------

# Element scores
for col in ["VIBRATION", "OIL ANALYSIS", "TEMPERATURE", "OTHER INSPECTION"]:
    df[f"{col} _SCORE"] = df[col].apply(coerce_score)
    # Fix accidental space before _SCORE
    df.rename(columns={f"{col} _SCORE": f"{col}_SCORE"}, inplace=True)

# Existing CMS as numeric (if present)
df["CMS_INPUT"] = df["CONDITION MONITORING SCORE"].apply(coerce_score)

# Equipment score = min of element scores; fallback to CMS if all elements are NaN
element_score_cols = ["VIBRATION_SCORE", "OIL ANALYSIS_SCORE", "TEMPERATURE_SCORE", "OTHER INSPECTION_SCORE"]

# Ensure all exist even if missing in data
for c in element_score_cols:
    if c not in df.columns:
        df[c] = None

row_min = df[element_score_cols].min(axis=1, skipna=True)
df["EQUIP_SCORE"] = row_min.where(row_min.notna(), df["CMS_INPUT"])  # fallback

df["EQUIP_STATUS"] = df["EQUIP_SCORE"].apply(score_to_status)

# System score/status = min(EQUIP_SCORE) within system
sys_scores = (
    df.groupby(["AREA", "SYSTEM"], dropna=True)["EQUIP_SCORE"].min().reset_index()
)
sys_scores["SYSTEM_STATUS"] = sys_scores["EQUIP_SCORE"].apply(score_to_status)

# Area score/status = min(system EQUIP_SCORE) within area
area_scores = sys_scores.groupby("AREA")["EQUIP_SCORE"].min().reset_index()
area_scores["AREA_STATUS"] = area_scores["EQUIP_SCORE"].apply(score_to_status)

# ---------- KPIs ----------

col1, col2, col3, col4 = st.columns(4)
col1.metric("Equipments (filtered)", len(df))
col2.metric("Systems (filtered)", sys_scores[["AREA", "SYSTEM"]].drop_duplicates().shape[0])
col3.metric("Areas (filtered)", area_scores["AREA"].nunique())
col4.metric(
    "Equip RED | AMBER | GREEN",
    f"{(df['EQUIP_STATUS']=='RED').sum()} | {(df['EQUIP_STATUS']=='AMBER').sum()} | {(df['EQUIP_STATUS']=='GREEN').sum()}",
)

st.divider()

# ---------- Hierarchy Tables ----------

st.subheader("Area Status")
area_view = area_scores[["AREA", "EQUIP_SCORE", "AREA_STATUS"]].sort_values(["AREA"]) 
st.dataframe(
    area_view.style.applymap(color_status, subset=["AREA_STATUS"]),
    use_container_width=True,
)

st.subheader("System Status")
sys_view = sys_scores[["AREA", "SYSTEM", "EQUIP_SCORE", "SYSTEM_STATUS"]].sort_values(["AREA", "SYSTEM"]) 
st.dataframe(
    sys_view.style.applymap(color_status, subset=["SYSTEM_STATUS"]),
    use_container_width=True,
)

st.subheader("Equipment Details")
cols_show = [
    "AREA",
    "SYSTEM",
    "EQUIPMENT DESCRIPTION",
    "DATE",
    "CONDITION MONITORING SCORE",
    "VIBRATION",
    "OIL ANALYSIS",
    "TEMPERATURE",
    "OTHER INSPECTION",
    "VIBRATION_SCORE",
    "OIL ANALYSIS_SCORE",
    "TEMPERATURE_SCORE",
    "OTHER INSPECTION_SCORE",
    "EQUIP_SCORE",
    "EQUIP_STATUS",
]
existing_cols = [c for c in cols_show if c in df.columns]

equip_view = df[existing_cols].sort_values(["AREA", "SYSTEM", "EQUIPMENT DESCRIPTION", "DATE"], na_position="last")
st.dataframe(
    equip_view.style.applymap(color_status, subset=["EQUIP_STATUS"]),
    use_container_width=True,
)

# ---------- Charts ----------

st.subheader("Status distribution by AREA")
status_counts = (
    df.pivot_table(index="AREA", columns="EQUIP_STATUS", values="EQUIPMENT DESCRIPTION", aggfunc="count", fill_value=0)
    .sort_index()
)
st.bar_chart(status_counts)

st.subheader("Average TEMPERATURE by SYSTEM (filtered)")
if df["TEMPERATURE"].apply(lambda x: pd.to_numeric(x, errors="coerce")).notna().any():
    tmp = df.copy()
    tmp["TEMPERATURE_NUM"] = pd.to_numeric(tmp["TEMPERATURE"], errors="coerce")
    tmp2 = tmp.groupby("SYSTEM")["TEMPERATURE_NUM"].mean().sort_values()
    st.bar_chart(tmp2)
else:
    st.caption("Temperature values are non-numeric or empty; skipping average temperature chart.")

# ---------- Download ----------

st.download_button(
    label="⬇️ Download filtered equipment table (CSV)",
    data=to_csv_download(equip_view),
    file_name="filtered_equipment.csv",
    mime="text/csv",
)

st.caption(
    "Scoring rule: Equipment score = min(VIBRATION, OIL ANALYSIS, TEMPERATURE, OTHER INSPECTION) after mapping to 1–3. "
    "If all four are missing, falls back to CONDITION MONITORING SCORE. System/Area status = worst (min) within the group."
)
