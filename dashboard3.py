import streamlit as st
import pandas as pd
import plotly.express as px

# =========================
# Flexible score mappings
# =========================
SCORE_MAPPINGS = {
    "VIBRATION": {"acceptable": 3, "excellent": 3, "ok": 3,
                  "requires evaluation": 2, "unacceptable": 1, "not applicable": None},
    "OIL ANALYSIS": {"no action required": 3, "ok": 3,
                     "monitor compartment": 2, "need action": 2,
                     "urgent action required": 1, "not applicable": None},
    "TEMPERATURE": {"good": 3, "warning": 2, "unacceptable": 1, "not applicable": None},
    "OTHER INSPECTION": {"good": 3, "alert": 2, "need action": 1, "not applicable": None}
}

# =========================
# Helper functions
# =========================
def map_score(value, category):
    if pd.isna(value):
        return None
    return SCORE_MAPPINGS[category].get(str(value).strip().lower(), None)

def aggregate_score(row):
    subs = [row["VIBRATION_SCORE"], row["OIL_SCORE"], row["TEMP_SCORE"], row["OTHER_SCORE"]]
    subs = [s for s in subs if s is not None]
    return min(subs) if subs else None

def color_score(val):
    if val == 1:
        return "background-color: red; color: white;"
    elif val == 2:
        return "background-color: yellow; color: black;"
    elif val == 3:
        return "background-color: green; color: white;"
    return ""

# =========================
# Main Streamlit App
# =========================
def main():
    st.title("📊 Condition Monitoring Dashboard")

    uploaded_file = st.file_uploader("Upload your Excel file", type=["xlsx"])
    if not uploaded_file:
        st.info("Please upload a file to continue.")
        return

    # Load data
    try:
        df = pd.read_excel(uploaded_file, sheet_name="Scorecard", header=1)
    except Exception as e:
        st.error(f"Error reading file: {e}")
        return

    # Rename columns
    column_mapping = {
        "AREA": "AREA", "SYSTEM": "SYSTEM", "EQUIPMENT DESCRIPTION": "EQUIPMENT DESCRIPTION",
        "DATE": "DATE", "CONDITION MONITORING SCORE": "CONDITION MONITORING SCORE",
        "VIBRATION": "VIBRATION", "OIL ANALYSIS": "OIL ANALYSIS",
        "TEMPERATURE": "TEMPERATURE", "OTHER INSPECTION": "OTHER INSPECTION"
    }
    df = df.rename(columns=column_mapping)

    # Parse date
    df["DATE"] = pd.to_datetime(df["DATE"], dayfirst=True, errors="coerce")

    # Map scores
    df["VIBRATION_SCORE"] = df["VIBRATION"].apply(lambda x: map_score(x, "VIBRATION"))
    df["OIL_SCORE"] = df["OIL ANALYSIS"].apply(lambda x: map_score(x, "OIL ANALYSIS"))
    df["TEMP_SCORE"] = df["TEMPERATURE"].apply(lambda x: map_score(x, "TEMPERATURE"))
    df["OTHER_SCORE"] = df["OTHER INSPECTION"].apply(lambda x: map_score(x, "OTHER INSPECTION"))

    # Aggregate equipment score
    df["CALCULATED_SCORE"] = df.apply(aggregate_score, axis=1)

    # Date filter
    min_date, max_date = df["DATE"].min(), df["DATE"].max()
    date_range = st.date_input("Select Date Range", [min_date, max_date])
    if len(date_range) == 2:
        df = df[(df["DATE"] >= pd.to_datetime(date_range[0])) &
                (df["DATE"] <= pd.to_datetime(date_range[1]))]

    # Hierarchical aggregation for tables
    system_scores = df.groupby(["AREA", "SYSTEM"])["CALCULATED_SCORE"].min().reset_index()
    area_scores = system_scores.groupby("AREA")["CALCULATED_SCORE"].min().reset_index()

    # Replace NaN with 0
    area_scores["CALCULATED_SCORE"] = area_scores["CALCULATED_SCORE"].fillna(0).astype(int)
    system_scores["CALCULATED_SCORE"] = system_scores["CALCULATED_SCORE"].fillna(0).astype(int)

    # ======================
    # 📊 BAR CHARTS (Minimum Score)
    # ======================
    st.subheader("AREA Score Distribution")
    fig_area = px.bar(
        area_scores,
        x="AREA",
        y="CALCULATED_SCORE",
        color=area_scores["CALCULATED_SCORE"].astype(str),
        text="CALCULATED_SCORE",
        color_discrete_map={"3": "green", "2": "yellow", "1": "red"},
        title="Score per AREA",
        opacity=1
    )
    fig_area.update_traces(texttemplate="%{text}", textposition="outside")
    fig_area.update_layout(
        yaxis=dict(title="Score", range=[0, 3], dtick=1),
        xaxis=dict(title="Area", tickangle=-45),
        width=900,
        margin=dict(b=150)
    )
    st.plotly_chart(fig_area)

    st.subheader("SYSTEM Score Distribution")
    fig_system = px.bar(
        system_scores,
        x="SYSTEM",
        y="CALCULATED_SCORE",
        color=system_scores["CALCULATED_SCORE"].astype(str),
        text="CALCULATED_SCORE",
        color_discrete_map={"3": "green", "2": "yellow", "1": "red"},
        title="Score per SYSTEM",
        opacity=1
    )
    fig_system.update_traces(texttemplate="%{text}", textposition="outside")
    fig_system.update_layout(
        yaxis=dict(title="Score", range=[0, 3], dtick=1),
        xaxis=dict(title="System", tickangle=-45),
        width=1200,
        margin=dict(b=250)
    )
    st.plotly_chart(fig_system)

    # ======================
    # 📍 TABLES WITH COLORS
    # ======================
    st.subheader("Area Status")
    st.dataframe(area_scores.style.applymap(color_score, subset=["CALCULATED_SCORE"]))

    st.subheader("System Status")
    st.dataframe(system_scores.style.applymap(color_score, subset=["CALCULATED_SCORE"]))

    # ======================
    # 🔎 INTERACTIVE SYSTEM → EQUIPMENT
    # ======================
    st.subheader("Explore Equipment by System")
    selected_system = st.selectbox("Select a System:", sorted(df["SYSTEM"].unique()))
    filtered_df = df[df["SYSTEM"] == selected_system]

    # Remove decimals for display
    filtered_df_display = filtered_df.copy()
    filtered_df_display["CALCULATED_SCORE"] = filtered_df_display["CALCULATED_SCORE"].fillna(0).astype(int)

    st.dataframe(filtered_df_display[[
        "AREA", "SYSTEM", "EQUIPMENT DESCRIPTION", "DATE",
        "VIBRATION", "OIL ANALYSIS", "TEMPERATURE", "OTHER INSPECTION",
        "CALCULATED_SCORE"
    ]].style.applymap(color_score, subset=["CALCULATED_SCORE"]))

    # ======================
    # 🔎 INTERACTIVE EQUIPMENT → FINDING & ACTION PLAN
    # ======================
    st.subheader("Explore Finding & Action Plan by Equipment Score")
    selected_equipment = st.selectbox(
        "Select an Equipment:",
        sorted(filtered_df["EQUIPMENT DESCRIPTION"].unique())
    )
    equipment_details = filtered_df[filtered_df["EQUIPMENT DESCRIPTION"] == selected_equipment]

    # Text wrap for FINDING and ACTION PLAN
    styled_df = equipment_details[[
        "AREA", "SYSTEM", "EQUIPMENT DESCRIPTION",
        "FINDING", "ACTION PLAN"
    ]].style.set_properties(**{
        'white-space': 'normal',
        'text-align': 'left'
    })

    st.dataframe(styled_df)
    # ======================
    # 📈 PERFORMANCE TREND OVER TIME
    # ======================
    st.subheader("System Performance Trend Over Time")

    # Aggregate minimum CALCULATED_SCORE per system per date
    trend_df = df.groupby(['DATE', 'SYSTEM'])['CALCULATED_SCORE'].min().reset_index()

    # Optional: filter by system for clarity
    selected_system_trend = st.selectbox("Select System for Trend Line:", sorted(df["SYSTEM"].unique()))
    trend_df_filtered = trend_df[trend_df["SYSTEM"] == selected_system_trend]

    # Plot trend line
    fig_trend = px.line(
        trend_df_filtered,
        x="DATE",
        y="CALCULATED_SCORE",
        markers=True,
        title=f"Performance Trend for {selected_system_trend}",
        line_shape='linear'
    )
    fig_trend.update_layout(
        yaxis=dict(title="Score", range=[0, 3], dtick=1),
        xaxis=dict(title="Date"),
        width=1200,
        height=500
    )
    st.plotly_chart(fig_trend)

if __name__ == "__main__":
    main()
