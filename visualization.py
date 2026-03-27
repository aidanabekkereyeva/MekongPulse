import glob
import json
import re

import pandas as pd
import plotly
import plotly.express as px
import plotly.graph_objs as go
from plotly.subplots import make_subplots


CATEGORY_PATHS = {
    "Water Level": "./data/Mekong_database/Water.Level/*.csv",
    "Water Discharge Daily": "./data/Mekong_database/Discharge.Daily/*.csv",
    "Sediment Concentration": "./data/Mekong_database/Sediment.Concentration/*.csv",
    "Sediment Concentration (DSMP)": "./data/Mekong_database/Sediment.Concentration (DSMP)/*.csv",
    "Total Suspended Solids": "./data/Mekong_database/Total.Suspended.Solids/*.csv",
    "Rainfall Manual": "./data/Mekong_database/Rainfall.Manual/*.csv",
}


def extract_station_name(filename):
    match = re.search(r"\[(.*?)\]", filename)
    if match:
        return match.group(1)
    return None


def get_category_units(category_name):
    units = {
        "Water Level": "Water Level (m)",
        "Water Discharge Daily": "Discharge (m³/s)",
        "Sediment Concentration": "Sediment Concentration (mg/l)",
        "Sediment Concentration (DSMP)": "Sediment Concentration (mg/l)",
        "Total Suspended Solids": "Total Suspended Solids (mg/l)",
        "Rainfall Manual": "Rainfall (mm)",
    }
    return units.get(category_name, "Value")


def normalize_series(series):
    series = pd.to_numeric(series, errors="coerce")
    min_val = series.min()
    max_val = series.max()

    if pd.isna(min_val) or pd.isna(max_val) or min_val == max_val:
        return pd.Series([0.5] * len(series), index=series.index)

    return (series - min_val) / (max_val - min_val)


def apply_clean_layout(fig, title, yaxis_title="Value", xaxis_title="Date"):
    fig.update_layout(
        title={
            "text": title,
            "x": 0.5,
            "xanchor": "center",
            "font": dict(size=20, color="#1f2d3d"),
        },
        template="plotly_white",
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin=dict(l=50, r=30, t=80, b=50),
        font=dict(
            family="Segoe UI, Arial, sans-serif",
            size=12,
            color="#223142",
        ),
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
        xaxis=dict(
            title=xaxis_title,
            showline=True,
            linecolor="#9fb3c8",
            showgrid=True,
            gridcolor="#e7edf3",
            tickformat="%Y",
        ),
        yaxis=dict(
            title=yaxis_title,
            showline=True,
            linecolor="#9fb3c8",
            showgrid=True,
            gridcolor="#e7edf3",
        ),
    )
    return fig


def create_no_data_chart(title, message="No data available for the selected range."):
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        font=dict(size=16, color="#5f7082"),
    )
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    fig = apply_clean_layout(fig, title, "", "")
    return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)


def dataframe_from_file(file_path):
    df = pd.read_csv(file_path)
    df["Timestamp"] = pd.to_datetime(df["Timestamp (UTC+07:00)"], utc=True)
    df["Value"] = pd.to_numeric(df["Value"], errors="coerce")
    df = df.dropna(subset=["Value"])
    return df


def filter_df_by_dates(df, start_date, end_date):
    start = pd.to_datetime(start_date, dayfirst=True).tz_localize("UTC")
    end = pd.to_datetime(end_date, dayfirst=True).tz_localize("UTC")
    return df[(df["Timestamp"] >= start) & (df["Timestamp"] <= end)].copy()


def get_matching_file(category_name, station_name):
    if category_name not in CATEGORY_PATHS:
        return None

    csv_files = glob.glob(CATEGORY_PATHS[category_name])
    for file in csv_files:
        current_station_name = extract_station_name(file)
        if current_station_name == station_name:
            return file
    return None


def fig_to_json(fig):
    return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)


def plot_single_category_single_station_chart(df, station_name, category_name, start_date, end_date):
    df_filtered = filter_df_by_dates(df, start_date, end_date)
    chart_title = f"{category_name} Trend at {station_name}"

    if df_filtered.empty:
        return create_no_data_chart(chart_title)

    fig = px.area(
        df_filtered,
        x="Timestamp",
        y="Value",
        title=chart_title,
        labels={"Value": get_category_units(category_name)},
    )

    fig.update_traces(
        mode="lines",
        line=dict(width=2, color="#2f6da3"),
        fill="tozeroy",
        hovertemplate="Date: %{x|%d-%b-%Y}<br>Value: %{y:.2f}<extra></extra>",
    )

    fig = apply_clean_layout(fig, chart_title, get_category_units(category_name))
    return fig_to_json(fig)


def generate_single_category_single_station_visualizations(selected_data):
    charts = []

    for data in selected_data:
        category_name = data["category_name"]
        station_name = data["station_name"]
        start_date = data["start_date"]
        end_date = data["end_date"]

        file_path = get_matching_file(category_name, station_name)
        if not file_path:
            charts.append(create_no_data_chart(f"{category_name} Trend at {station_name}", "Matching station file was not found."))
            continue

        df = dataframe_from_file(file_path)
        charts.append(
            plot_single_category_single_station_chart(
                df, station_name, category_name, start_date, end_date
            )
        )

    return charts


def plot_multiple_categories_single_station_chart(categories_data, station_name):
    colors = px.colors.qualitative.Plotly
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    any_data = False
    overall_start = None
    overall_end = None

    for i, data in enumerate(categories_data):
        category_name = data["category_name"]
        start_date = pd.to_datetime(data["start_date"], dayfirst=True).tz_localize("UTC")
        end_date = pd.to_datetime(data["end_date"], dayfirst=True).tz_localize("UTC")

        if overall_start is None or start_date < overall_start:
            overall_start = start_date
        if overall_end is None or end_date > overall_end:
            overall_end = end_date

        file_path = get_matching_file(category_name, station_name)
        if not file_path:
            continue

        df = dataframe_from_file(file_path)
        df_filtered = filter_df_by_dates(df, data["start_date"], data["end_date"])

        if df_filtered.empty:
            continue

        df_filtered["Normalized Value"] = normalize_series(df_filtered["Value"])
        any_data = True

        fig.add_trace(
            go.Scatter(
                x=df_filtered["Timestamp"],
                y=df_filtered["Normalized Value"],
                mode="lines",
                name=f"{category_name}",
                line=dict(color=colors[i % len(colors)], width=2),
                hovertemplate="Date: %{x|%d-%b-%Y}<br>Normalized value: %{y:.2f}<extra></extra>",
            ),
            secondary_y=(i % 2 != 0),
        )

    chart_title = f"Multi-Category Timeline for {station_name}"

    if not any_data:
        return create_no_data_chart(chart_title)

    fig = apply_clean_layout(fig, chart_title, "Normalized Value")
    fig.update_xaxes(range=[overall_start, overall_end])
    return fig_to_json(fig)


def generate_multiple_categories_single_station_visualizations(selected_data):
    charts = []
    grouped_data = {}

    for data in selected_data:
        station_name = data["station_name"]
        grouped_data.setdefault(station_name, []).append(data)

    for station_name, categories_data in grouped_data.items():
        charts.append(plot_multiple_categories_single_station_chart(categories_data, station_name))

    return charts


def plot_single_category_multiple_stations_chart(category_name, stations_data):
    colors = px.colors.qualitative.Plotly
    fig = go.Figure()
    any_data = False

    start_dates = [pd.to_datetime(data["start_date"], dayfirst=True).tz_localize("UTC") for data in stations_data]
    end_dates = [pd.to_datetime(data["end_date"], dayfirst=True).tz_localize("UTC") for data in stations_data]
    overall_start = min(start_dates) if start_dates else None
    overall_end = max(end_dates) if end_dates else None

    for i, data in enumerate(stations_data):
        station_name = data["station_name"]
        file_path = get_matching_file(category_name, station_name)
        if not file_path:
            continue

        df = dataframe_from_file(file_path)
        df_filtered = filter_df_by_dates(df, data["start_date"], data["end_date"])

        if df_filtered.empty:
            continue

        any_data = True
        fig.add_trace(
            go.Scatter(
                x=df_filtered["Timestamp"],
                y=df_filtered["Value"],
                mode="lines",
                name=station_name,
                line=dict(color=colors[i % len(colors)], width=2),
                hovertemplate="Date: %{x|%d-%b-%Y}<br>Value: %{y:.2f}<extra></extra>",
            )
        )

    chart_title = f"{category_name} Comparison Across Stations"

    if not any_data:
        return create_no_data_chart(chart_title)

    fig = apply_clean_layout(fig, chart_title, get_category_units(category_name))
    fig.update_xaxes(range=[overall_start, overall_end])
    return fig_to_json(fig)


def generate_single_category_multiple_stations_visualizations(selected_data):
    charts = []
    grouped_data = {}

    for data in selected_data:
        category_name = data["category_name"]
        grouped_data.setdefault(category_name, []).append(data)

    for category_name, stations_data in grouped_data.items():
        charts.append(plot_single_category_multiple_stations_chart(category_name, stations_data))

    return charts


def plot_multiple_categories_multiple_stations_chart(group_data):
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    colors = px.colors.qualitative.Plotly
    any_data = False
    overall_start = None
    overall_end = None
    trace_index = 0

    for station_name, categories_data in group_data.items():
        for data in categories_data:
            category_name = data["category_name"]
            start_date = pd.to_datetime(data["start_date"], dayfirst=True).tz_localize("UTC")
            end_date = pd.to_datetime(data["end_date"], dayfirst=True).tz_localize("UTC")

            if overall_start is None or start_date < overall_start:
                overall_start = start_date
            if overall_end is None or end_date > overall_end:
                overall_end = end_date

            file_path = get_matching_file(category_name, station_name)
            if not file_path:
                continue

            df = dataframe_from_file(file_path)
            df_filtered = filter_df_by_dates(df, data["start_date"], data["end_date"])

            if df_filtered.empty:
                continue

            df_filtered["Normalized Value"] = normalize_series(df_filtered["Value"])
            any_data = True

            fig.add_trace(
                go.Scatter(
                    x=df_filtered["Timestamp"],
                    y=df_filtered["Normalized Value"],
                    mode="lines",
                    name=f"{station_name} - {category_name}",
                    line=dict(color=colors[trace_index % len(colors)], width=2),
                    hovertemplate="Date: %{x|%d-%b-%Y}<br>Normalized value: %{y:.2f}<extra></extra>",
                ),
                secondary_y=(trace_index % 2 != 0),
            )
            trace_index += 1

    chart_title = "Multi-Category and Multi-Station Comparison"

    if not any_data:
        return create_no_data_chart(chart_title)

    fig = apply_clean_layout(fig, chart_title, "Normalized Value")
    fig.update_xaxes(range=[overall_start, overall_end])
    return fig_to_json(fig)


def generate_multiple_categories_multiple_stations_visualizations(selected_data):
    charts = []
    group_data = {}

    for data in selected_data:
        station_name = data["station_name"]
        group_data.setdefault(station_name, []).append(data)

    charts.append(plot_multiple_categories_multiple_stations_chart(group_data))
    return charts


def plot_year_over_year_comparison_chart(station_name, category_name, start_date, end_date):
    file_path = get_matching_file(category_name, station_name)
    chart_title = f"Year-over-Year {category_name} Comparison at {station_name}"

    if not file_path:
        return create_no_data_chart(chart_title, "Matching station file was not found.")

    df = dataframe_from_file(file_path)
    df_filtered = filter_df_by_dates(df, start_date, end_date)

    if df_filtered.empty:
        return create_no_data_chart(chart_title)

    df_filtered["Year"] = df_filtered["Timestamp"].dt.year
    df_filtered["Month"] = df_filtered["Timestamp"].dt.month

    monthly_data = df_filtered.groupby(["Year", "Month"])["Value"].mean().reset_index()

    fig = go.Figure()
    colors = px.colors.qualitative.Plotly

    for i, year in enumerate(sorted(monthly_data["Year"].unique())):
        year_data = monthly_data[monthly_data["Year"] == year]
        fig.add_trace(
            go.Scatter(
                x=year_data["Month"],
                y=year_data["Value"],
                mode="lines+markers",
                name=str(year),
                line=dict(color=colors[i % len(colors)], width=2),
                hovertemplate="Month: %{x}<br>Value: %{y:.2f}<extra></extra>",
            )
        )

    fig = apply_clean_layout(fig, chart_title, get_category_units(category_name), "Month")
    fig.update_xaxes(
        tickmode="array",
        tickvals=list(range(1, 13)),
        ticktext=["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    )
    return fig_to_json(fig)


def generate_year_over_year_comparison_visualizations(selected_data):
    charts = []

    for data in selected_data:
        station_name = data["station_name"]
        category_name = data["category_name"]
        start_date = data["start_date"]
        end_date = data["end_date"]

        charts.append(
            plot_year_over_year_comparison_chart(
                station_name, category_name, start_date, end_date
            )
        )

    return charts


def plot_annual_monthly_totals_chart(station_name, category_name, start_date, end_date):
    file_path = get_matching_file(category_name, station_name)
    chart_title = f"Monthly Total Analysis for {category_name} at {station_name}"

    if not file_path:
        return create_no_data_chart(chart_title, "Matching station file was not found.")

    df = dataframe_from_file(file_path)
    df_filtered = filter_df_by_dates(df, start_date, end_date)

    if df_filtered.empty:
        return create_no_data_chart(chart_title)

    df_filtered["Month"] = df_filtered["Timestamp"].dt.month
    monthly_totals = round(
        df_filtered.groupby("Month")["Value"].sum().reindex(range(1, 13), fill_value=0),
        2,
    )

    fig = go.Figure(
        data=[
            go.Bar(
                x=["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
                y=monthly_totals.values,
                text=monthly_totals.values,
                textposition="auto",
                marker=dict(color="#7aa6d1"),
                hovertemplate="Month: %{x}<br>Total: %{y:.2f}<extra></extra>",
            )
        ]
    )

    fig = apply_clean_layout(fig, chart_title, get_category_units(category_name), "Month")
    fig.update_xaxes(tickmode="array", tickvals=["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])
    return fig_to_json(fig)


def generate_annual_monthly_totals_visualizations(selected_data):
    charts = []

    for data in selected_data:
        station_name = data["station_name"]
        category_name = data["category_name"]
        start_date = data["start_date"]
        end_date = data["end_date"]

        charts.append(
            plot_annual_monthly_totals_chart(
                station_name, category_name, start_date, end_date
            )
        )

    return charts

def build_summary_for_selection(selected_data):
    if not selected_data:
        return {
            "station": "--",
            "category": "--",
            "date_range": "--",
            "mean": "--",
            "min": "--",
            "max": "--",
            "first_year": "--",
            "last_year": "--",
            "record_count": "--",
            "coverage_note": "Awaiting visualization selection",
        }

    first_item = selected_data[0]
    station_name = first_item["station_name"]
    category_name = first_item["category_name"]
    start_date = first_item["start_date"]
    end_date = first_item["end_date"]

    file_path = get_matching_file(category_name, station_name)
    if not file_path:
        return {
            "station": station_name,
            "category": category_name,
            "date_range": f"{start_date} -> {end_date}",
            "mean": "--",
            "min": "--",
            "max": "--",
            "first_year": "--",
            "last_year": "--",
            "record_count": 0,
            "coverage_note": "Matching station file was not found",
        }

    df = dataframe_from_file(file_path)
    df_filtered = filter_df_by_dates(df, start_date, end_date)

    if df_filtered.empty:
        return {
            "station": station_name,
            "category": category_name,
            "date_range": f"{start_date} -> {end_date}",
            "mean": "--",
            "min": "--",
            "max": "--",
            "first_year": "--",
            "last_year": "--",
            "record_count": 0,
            "coverage_note": "No data available for selected range",
        }

    mean_value = round(df_filtered["Value"].mean(), 2)
    min_value = round(df_filtered["Value"].min(), 2)
    max_value = round(df_filtered["Value"].max(), 2)
    first_year = int(df_filtered["Timestamp"].dt.year.min())
    last_year = int(df_filtered["Timestamp"].dt.year.max())
    record_count = int(len(df_filtered))

    return {
        "station": station_name,
        "category": category_name,
        "date_range": f"{start_date} -> {end_date}",
        "mean": mean_value,
        "min": min_value,
        "max": max_value,
        "first_year": first_year,
        "last_year": last_year,
        "record_count": record_count,
        "coverage_note": "Based on current visualization selection",
    }


def generate_visualizations_with_summary(graph_type, selected_data):
    if graph_type == "Single Category, Single Station Timeline":
        charts = generate_single_category_single_station_visualizations(selected_data)
    elif graph_type == "Multiple Categories, Single Station Timeline":
        charts = generate_multiple_categories_single_station_visualizations(selected_data)
    elif graph_type == "Single Category Across Multiple Stations Comparison":
        charts = generate_single_category_multiple_stations_visualizations(selected_data)
    elif graph_type == "Multiple Categories Across Multiple Stations Comparison":
        charts = generate_multiple_categories_multiple_stations_visualizations(selected_data)
    elif graph_type == "Year-over-Year Comparison":
        charts = generate_year_over_year_comparison_visualizations(selected_data)
    elif graph_type == "Annual Monthly Totals Overview":
        charts = generate_annual_monthly_totals_visualizations(selected_data)
    else:
        charts = []

    summary = build_summary_for_selection(selected_data)
    ranking = build_station_ranking_for_category(summary["category"]) if summary["category"] != "--" else []

    return {
        "charts": charts,
        "summary": summary,
        "ranking": ranking,
    }

def build_station_ranking_for_category(category_name, top_n=5):
    if not category_name or category_name not in CATEGORY_PATHS:
        return []

    ranking_rows = []
    csv_files = glob.glob(CATEGORY_PATHS[category_name])

    for file_path in csv_files:
        station_name = extract_station_name(file_path)
        if not station_name:
            continue

        try:
            df = dataframe_from_file(file_path)
            if df.empty:
                continue

            avg_value = round(df["Value"].mean(), 2)
            max_value = round(df["Value"].max(), 2)
            record_count = int(len(df))

            ranking_rows.append({
                "station": station_name,
                "average_value": avg_value,
                "maximum_value": max_value,
                "record_count": record_count,
            })
        except Exception:
            continue

    ranking_rows = sorted(
        ranking_rows,
        key=lambda row: row["average_value"],
        reverse=True
    )

    return ranking_rows[:top_n]