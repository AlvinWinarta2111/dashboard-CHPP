import streamlit as st
import pandas as pd
import plotly.express as px
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode, GridUpdateMode
from streamlit_plotly_events import plotly_events
import requests
import io

# =========================
# Helper functions
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
    """Returns CSS style for SCORE cells (used in pandas Styler)."""
    if pd.isna(val):
        return ""
    try:
        v = int(val)
    except Exception:
        return ""
    if v == 1:
        return "background-color: red; color: white;"
    elif v == 2:
        return "background-color: yellow; color: black;"
    elif v == 3:
        return "background-color: green; color: white;"
    return ""

def color_status(val):
    """Returns CSS style for STATUS cells (used in pandas Styler)."""
    if val == "Need Action":
        return "background-color: red; color: white;"
    elif val == "Caution":
        return "background-color: yellow; color: black;"
    elif val =="Okay":
        return "background-color: green; color: white;"
    return ""

# =========================
# Main Streamlit App
# =========================
def main():
    st.set_page_config(layout="wide")
    st.title("📊 Condition Monitoring Dashboard")

    if 'clicked_point_index' not in st.session_state:
        st.session_state.clicked_point_index = None
    if 'selected_equipment_name' not in st.session_state:
        st.session_state.selected_equipment_name = None
    if 'clicked_trend_point' not in st.session_state:
        st.session_state.clicked_trend_point = None

    RAW_FILE_URL = "https://raw.githubusercontent.com/AlvinWinarta2111/equipment-monitoring-dashboard/main/data/CONDITION%20MONITORING%20SCORECARD.xlsx"

    @st.cache_data(ttl=300)
    def load_data():
        response = requests.get(RAW_FILE_URL)
        response.raise_for_status()
        return pd.read_excel(io.BytesIO(response.content), sheet_name="Scorecard", header=1)

    try:
        df = load_data()
    except Exception as e:
        st.error(f"Error reading data from GitHub file: {e}")
        return

    df.columns = [col.strip().upper() for col in df.columns]
    if "CONDITION MONITORING SCORE" not in df.columns:
        st.error("Error: 'CONDITION MONITORING SCORE' column not found.")
        return

    df = df.rename(columns={"CONDITION MONITORING SCORE": "SCORE"})
    df["SCORE"] = pd.to_numeric(df["SCORE"], errors="coerce")
    df["DATE"] = pd.to_datetime(df["DATE"], errors="coerce")

    # Clean categorical data to remove leading/trailing spaces
    for col in ['AREA', 'SYSTEM', 'EQUIPMENT DESCRIPTION']:
        if col in df.columns and df[col].dtype == 'object':
            df[col] = df[col].str.strip().str.upper()

    df.dropna(subset=['AREA', 'SYSTEM', 'EQUIPMENT DESCRIPTION', 'DATE', 'SCORE'], inplace=True)
    df["SCORE"] = df["SCORE"].astype(int)
    df["EQUIP_STATUS"] = df["SCORE"].apply(map_status)

    min_date, max_date = df["DATE"].min().date(), df["DATE"].max().date()
    date_range = st.date_input("Select Date Range", [min_date, max_date])
    if len(date_range) == 2:
        df_filtered_by_date = df[(df["DATE"].dt.date >= date_range[0]) & (df["DATE"].dt.date <= date_range[1])]
    else:
        df_filtered_by_date = df

    if df_filtered_by_date.empty:
        st.warning("No data available for the selected date range.")
        return

    # Aggregation
    system_scores = df_filtered_by_date.groupby(["AREA", "SYSTEM"])["SCORE"].min().reset_index()
    area_scores = system_scores.groupby("AREA")["SCORE"].min().reset_index()

    st.subheader("AREA Score Distribution")
    fig_area = px.bar(
        area_scores, x="AREA", y="SCORE", color=area_scores["SCORE"].astype(str), text="SCORE",
        color_discrete_map={"3": "green", "2": "yellow", "1": "red"}, title="Lowest Score per AREA",
        category_orders={"SCORE": ["3", "2", "1"]}
    )
    fig_area.update_layout(yaxis=dict(title="Score", range=[0, 3.5], dtick=1))
    st.plotly_chart(fig_area, use_container_width=True)

    st.subheader("Equipment Status Distribution per AREA")
    latest_for_pie = df_filtered_by_date.sort_values("DATE").groupby("EQUIPMENT DESCRIPTION", as_index=False).last()
    area_dist = latest_for_pie.groupby(["AREA", "EQUIP_STATUS"])["EQUIPMENT DESCRIPTION"].count().reset_index(name="COUNT")
    areas = sorted(area_dist["AREA"].unique())
    cols_per_row = 3
    for i in range(0, len(areas), cols_per_row):
        cols = st.columns(cols_per_row)
        for j, area in enumerate(areas[i:i + cols_per_row]):
            if j < len(cols):
                with cols[j]:
                    st.markdown(f"**{area}**")
                    area_data = area_dist[area_dist["AREA"] == area]
                    fig_pie = px.pie(
                        area_data, names="EQUIP_STATUS", values="COUNT", color="EQUIP_STATUS",
                        color_discrete_map={"Need Action": "red", "Caution": "yellow", "Okay": "green"}, hole=0.4,
                        category_orders={"EQUIP_STATUS": ["Okay", "Caution", "Need Action"]}
                    )
                    fig_pie.update_traces(textinfo='percent+value', textfont_size=16)
                    fig_pie.update_layout(showlegend=False, margin=dict(t=20, b=20, l=20, r=20))
                    st.plotly_chart(fig_pie, use_container_width=True)

    st.subheader("SYSTEM Score Distribution")
    fig_system = px.bar(
        system_scores, x="SYSTEM", y="SCORE", color=system_scores["SCORE"].astype(str), text="SCORE",
        color_discrete_map={"3": "green", "2": "yellow", "1": "red"}, title="Lowest Score per SYSTEM",
        category_orders={"SCORE": ["3", "2", "1"]}
    )
    fig_system.update_layout(yaxis=dict(title="Score", range=[0, 3.5], dtick=1), xaxis=dict(tickangle=-45))
    st.plotly_chart(fig_system, use_container_width=True)

    st.subheader("Area Status (Lowest Score)")
    st.dataframe(area_scores.style.map(color_score, subset=["SCORE"]).hide(axis="index"))

    st.subheader("System Status Explorer")
    system_summary = df_filtered_by_date.groupby("SYSTEM").agg({"SCORE": "min"}).reset_index()
    system_summary["STATUS"] = system_summary["SCORE"].apply(map_status)
    gb = GridOptionsBuilder.from_dataframe(system_summary[["SYSTEM", "STATUS", "SCORE"]])
    gb.configure_selection(selection_mode="single", use_checkbox=False)
    gb.configure_default_column(resizable=False, filter=True, sortable=True)
    cell_style_jscode = JsCode("""
        function(params) {
            if (params.value == 'Okay') return {'backgroundColor': 'green', 'color': 'white'};
            if (params.value == 'Caution') return {'backgroundColor': 'yellow', 'color': 'black'};
            if (params.value == 'Need Action') return {'backgroundColor': 'red', 'color': 'white'};
            return null;
        }""")
    gb.configure_column("STATUS", cellStyle=cell_style_jscode)
    gridOptions = gb.build()
    gridOptions['suppressMovableColumns'] = True
    grid_response = AgGrid(
        system_summary, gridOptions=gridOptions, enable_enterprise_modules=True,
        update_mode=GridUpdateMode.SELECTION_CHANGED, fit_columns_on_grid_load=True,
        height=300, theme="streamlit", allow_unsafe_jscode=True
    )

    selected_system_rows = grid_response.get("selected_rows", [])
    if isinstance(selected_system_rows, pd.DataFrame):
        selected_system_rows = selected_system_rows.to_dict("records")

    if selected_system_rows:
        selected_system = selected_system_rows[0].get("SYSTEM")
        st.markdown(f"### Equipment Details for **{selected_system}** (Latest Status in Range)")
        detail_df = df_filtered_by_date[df_filtered_by_date["SYSTEM"] == selected_system].copy()
        detail_df = detail_df.sort_values(by="DATE", ascending=False).drop_duplicates(subset=["EQUIPMENT DESCRIPTION"], keep="first")
        detail_df["STATUS"] = detail_df["SCORE"].apply(map_status)
        
        detail_display_cols = ["EQUIPMENT DESCRIPTION", "DATE", "SCORE", "STATUS", "VIBRATION", "OIL ANALYSIS", "TEMPERATURE", "OTHER INSPECTION"]
        gb_details = GridOptionsBuilder.from_dataframe(detail_df[detail_display_cols])
        gb_details.configure_selection(selection_mode="single", use_checkbox=False)
        gb_details.configure_default_column(resizable=False)
        gb_details.configure_column("STATUS", cellStyle=cell_style_jscode)
        gridOptions_details = gb_details.build()
        gridOptions_details['suppressMovableColumns'] = True
        detail_grid_response = AgGrid(
            detail_df[detail_display_cols], gridOptions=gridOptions_details, enable_enterprise_modules=True,
            update_mode=GridUpdateMode.SELECTION_CHANGED, fit_columns_on_grid_load=True,
            height=300, theme="streamlit", allow_unsafe_jscode=True
        )

        selected_equipment_rows = detail_grid_response.get("selected_rows", [])
        if isinstance(selected_equipment_rows, pd.DataFrame):
            selected_equipment_rows = selected_equipment_rows.to_dict("records")
        
        if selected_equipment_rows:
            selected_equip_name = selected_equipment_rows[0].get('EQUIPMENT DESCRIPTION')
            
            st.markdown(f"#### Details for: **{selected_equip_name}**")
            selected_equip_full_details = detail_df[detail_df['EQUIPMENT DESCRIPTION'] == selected_equip_name].iloc[0]
            action_data = [{"EQUIPMENT DESCRIPTION": selected_equip_full_details.get("EQUIPMENT DESCRIPTION"), "REPORTED BY": selected_equip_full_details.get("REPORTED BY"), "FINDING": selected_equip_full_details.get("FINDING"), "ACTION PLAN": selected_equip_full_details.get("ACTION PLAN"), "PART NEEDED": selected_equip_full_details.get("PART NEEDED")}]
            action_detail_df = pd.DataFrame(action_data)
            gb_action = GridOptionsBuilder.from_dataframe(action_detail_df)
            gb_action.configure_default_column(wrapText=True, autoHeight=True)
            gridOptions_action = gb_action.build()
            gridOptions_action['domLayout'] = 'autoHeight'
            AgGrid(action_detail_df, gridOptions=gridOptions_action, theme="streamlit", fit_columns_on_grid_load=True, allow_unsafe_jscode=True)

            st.subheader(f"Performance Trend for {selected_equip_name}")
            
            trend_df_filtered = df_filtered_by_date[df_filtered_by_date["EQUIPMENT DESCRIPTION"] == selected_equip_name].copy()
            trend_df_filtered.sort_values(by="DATE", inplace=True)
            
            if not trend_df_filtered.empty:
                fig_trend = px.line(trend_df_filtered, x="DATE", y="SCORE", markers=True)
                fig_trend.update_xaxes(tickformat="%d/%m/%y", fixedrange=True)
                # Invert the y-axis to make "Need Action" (1) appear at the top
                fig_trend.update_layout(yaxis=dict(title="Score", range=[3.5, 0.5], dtick=1, fixedrange=True))
                
                st.markdown("### Performance Trend (Click a point on the chart)")
                
                # Use plotly_events to capture the click
                selected_points = plotly_events(
                    fig_trend,
                    click_event=True,
                    key=f"trend_chart_{selected_equip_name}"
                )
                
                # Check for a clicked point and display details
                if selected_points:
                    clicked_date_str = selected_points[0]['x']
                    # Convert the string date from the event to a datetime object for comparison
                    clicked_date = pd.to_datetime(clicked_date_str).normalize()
                    selected_row = trend_df_filtered[trend_df_filtered['DATE'].dt.normalize() == clicked_date].iloc[0]
                    
                    st.subheader(f"Details for {selected_equip_name} on {selected_row['DATE'].strftime('%d-%m-%Y')}")
                    
                    st.markdown(f"**Score:** {selected_row['SCORE']}")
                    st.markdown(f"**Status:** {selected_row['EQUIP_STATUS']}")
                    st.markdown(f"**Finding:** {selected_row.get('FINDING', 'N/A')}")
                    st.markdown(f"**Action Plan:** {selected_row.get('ACTION PLAN', 'N/A')}")
                else:
                    st.info("Click a point on the trend chart to see details for that specific date.")

            else:
                st.warning(f"No trend data available for {selected_equip_name} in the selected date range.")
        else:
            st.info("Select a piece of equipment from the table above to see its performance trend.")

    else:
        st.info("Click a system above to see its latest equipment details.")


if __name__ == "__main__":
    main()
