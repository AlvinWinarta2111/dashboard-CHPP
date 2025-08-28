import streamlit as st
import pandas as pd
import plotly.express as px

# =========================
# Helper functions (for styling and status mapping)
# =========================

def map_status(score):
    """Converts a numeric score (1, 2, 3) to a text status."""
    if score == 1:
        return "Need Action"
    elif score == 2:
        return "Caution"
    elif score == 3:
        return "Okay"
    return "UNKNOWN"

def color_score(val):
    """Applies background color to a cell based on its numeric score."""
    if val == 1:
        return "background-color: red; color: white;"
    elif val == 2:
        return "background-color: yellow; color: white;"
    elif val == 3:
        return "background-color: green; color: white;"
    return ""

def color_status(val):
    """Applies background color to a cell based on its text status."""
    if val == "Need Action":
        return "background-color: red; color: white;"
    elif val == "Caution":
        return "background-color: yellow; color: white;"
    elif val == "Okay":
        return "background-color: green; color: white;"
    return ""

# =========================
# Main Streamlit App
# =========================
def main():
    st.set_page_config(layout="wide")
    st.title("📊 Condition Monitoring Dashboard")

    uploaded_file = st.file_uploader("Upload your Excel file", type=["xlsx"])
    if not uploaded_file:
        st.info("Please upload a file to continue.")
        return

    # Load data from the "Scorecard" sheet
    try:
        df = pd.read_excel(uploaded_file, sheet_name="Scorecard", header=1)
    except Exception as e:
        st.error(f"Error reading the 'Scorecard' sheet in the file: {e}")
        return

    # Clean up column names
    df.columns = [col.strip().upper() for col in df.columns]

    # --- DIRECTLY USE THE SCORE FROM EXCEL ---
    # Rename the score column for easier use and ensure it's a numeric type
    if "CONDITION MONITORING SCORE" not in df.columns:
        st.error("Error: A column named 'CONDITION MONITORING SCORE' was not found in your file.")
        return
        
    df = df.rename(columns={"CONDITION MONITORING SCORE": "SCORE"})
    
    # Convert score to a number, coercing errors to 'Not a Number' (NaN)
    df["SCORE"] = pd.to_numeric(df["SCORE"], errors='coerce')

    # Parse date and drop rows with invalid dates or scores
    df["DATE"] = pd.to_datetime(df["DATE"], errors='coerce')
    df.dropna(subset=['AREA', 'SYSTEM', 'EQUIPMENT DESCRIPTION', 'DATE', 'SCORE'], inplace=True)
    
    # Convert score to integer
    df["SCORE"] = df["SCORE"].astype(int)

    # Create the text-based status column for the pie charts
    df["EQUIP_STATUS"] = df["SCORE"].apply(map_status)

    # --- FILTERS ---
    min_date, max_date = df["DATE"].min().date(), df["DATE"].max().date()
    date_range = st.date_input("Select Date Range", [min_date, max_date])
    if len(date_range) == 2:
        df = df[(df["DATE"].dt.date >= date_range[0]) & (df["DATE"].dt.date <= date_range[1])]

    if df.empty:
        st.warning("No data available for the selected date range.")
        return

    # --- HIERARCHICAL AGGREGATION (using the score from Excel) ---
    system_scores = df.groupby(["AREA", "SYSTEM"])["SCORE"].min().reset_index()
    area_scores = system_scores.groupby("AREA")["SCORE"].min().reset_index()

    # ======================
    # 📊 BAR CHARTS
    # ======================
    st.subheader("AREA Score Distribution")
    fig_area = px.bar(
        area_scores, x="AREA", y="SCORE",
        color=area_scores["SCORE"].astype(str),
        text="SCORE",
        color_discrete_map={"3": "green", "2": "yellow", "1": "red"},
        title="Lowest Score per AREA"
    )
    fig_area.update_layout(yaxis=dict(title="Score", range=[0, 3.5], dtick=1))
    st.plotly_chart(fig_area, use_container_width=True)

    st.subheader("SYSTEM Score Distribution")
    fig_system = px.bar(
        system_scores, x="SYSTEM", y="SCORE",
        color=system_scores["SCORE"].astype(str),
        text="SCORE",
        color_discrete_map={"3": "green", "2": "yellow", "1": "red"},
        title="Lowest Score per SYSTEM"
    )
    fig_system.update_layout(yaxis=dict(title="Score", range=[0, 3.5], dtick=1), xaxis=dict(tickangle=-45))
    st.plotly_chart(fig_system, use_container_width=True)

    # ======================
    # 🥧 PIE CHARTS
    # ======================
    st.subheader("Equipment Status Distribution per AREA")
    area_dist = df.groupby(["AREA", "EQUIP_STATUS"])["EQUIPMENT DESCRIPTION"].count().reset_index(name="COUNT")
    areas = sorted(area_dist["AREA"].unique())

    cols_per_row = 3
    for i in range(0, len(areas), cols_per_row):
        cols = st.columns(cols_per_row)
        for j, area in enumerate(areas[i:i+cols_per_row]):
            if j < len(cols):
                with cols[j]:
                    st.markdown(f"**{area}**")
                    area_data = area_dist[area_dist["AREA"] == area]
                    fig = px.pie(
                        area_data, names="EQUIP_STATUS", values="COUNT",
                        color="EQUIP_STATUS",
                        color_discrete_map={"Need Action": "red", "Caution": "yellow", "Okay": "green"},
                        hole=0.4
                    )
                    fig.update_layout(showlegend=False, margin=dict(t=20, b=20, l=20, r=20))
                    st.plotly_chart(fig, use_container_width=True)
    
    # ======================
    # 📍 TABLES
    # ======================
    st.subheader("Area Status (Lowest Score)")
    st.dataframe(area_scores.style.applymap(color_score, subset=["SCORE"]), use_container_width=True)

    st.subheader("System Status (Lowest Score)")
    system_scores["STATUS"] = system_scores["SCORE"].apply(map_status)
    st.dataframe(system_scores.style.applymap(color_status, subset=["STATUS"]), use_container_width=True)
    
    # ======================
    # 🔎 INTERACTIVE EXPLORER
    # ======================
    st.subheader("Explore Equipment by System")
    selected_system = st.selectbox("Select a System:", sorted(df["SYSTEM"].unique()))
    if selected_system:
        filtered_df = df[df["SYSTEM"] == selected_system]
        
        display_cols = [
            "AREA", "SYSTEM", "EQUIPMENT DESCRIPTION", "DATE", "SCORE",
            "VIBRATION", "OIL ANALYSIS", "TEMPERATURE", "OTHER INSPECTION",
            "FINDING", "ACTION PLAN"
        ]
        # Ensure only existing columns are displayed
        display_cols = [col for col in display_cols if col in filtered_df.columns]
        
        st.dataframe(
            filtered_df[display_cols].style.applymap(color_score, subset=["SCORE"]),
            use_container_width=True
        )

    # ======================
    # 📈 PERFORMANCE TREND
    # ======================
    st.subheader("System Performance Trend Over Time")
    trend_df = df.groupby(['DATE', 'SYSTEM'])['SCORE'].min().reset_index()
    
    trend_systems = sorted(df["SYSTEM"].unique())
    if trend_systems:
        selected_system_trend = st.selectbox("Select System for Trend Line:", trend_systems)
        trend_df_filtered = trend_df[trend_df["SYSTEM"] == selected_system_trend]

        fig_trend = px.line(
            trend_df_filtered, x="DATE", y="SCORE", markers=True,
            title=f"Performance Trend for {selected_system_trend}"
        )
        fig_trend.update_layout(yaxis=dict(title="Score", range=[0.5, 3.5], dtick=1))
        st.plotly_chart(fig_trend, use_container_width=True)


if __name__ == "__main__":
    main()
