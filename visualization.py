from __future__ import annotations

import json
from typing import Optional

import pandas as pd
import plotly
import plotly.express as px
import plotly.graph_objs as go
from plotly.subplots import make_subplots

from data_loader import DataRepository, SeriesRequest
import numpy as np
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.statespace.sarimax import SARIMAX
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import LinearRegression
from sklearn.svm import SVR
from sklearn.preprocessing import StandardScaler

# Set by app.py at startup
repo: Optional[DataRepository] = None

# Maps display category name (used by frontend) → schema feature key
CATEGORY_TO_FEATURE = {
    "Water Level": "Water_Level",
    "Discharge": "Discharge",
    "Total Suspended Solids": "Total_Suspended_Solids",
    "Rainfall": "Rainfall",
}

FEATURE_DISPLAY_UNITS = {
    "Water Level": "Water Level (m)",
    "Discharge": "Discharge (m³/s)",
    "Total Suspended Solids": "Total Suspended Solids (mg/l)",
    "Rainfall": "Rainfall (mm)",
}


def get_category_units(category_name: str) -> str:
    return FEATURE_DISPLAY_UNITS.get(category_name, "Value")


def station_key(station_name: str) -> str:
    """Convert display name (spaces) to repo key (underscores)."""
    return station_name.replace(" ", "_")


def station_display(station_key_str: str) -> str:
    """Convert repo key (underscores) to display name (spaces)."""
    return station_key_str.replace("_", " ")


def get_feature_series_df(category_name: str, station_name: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
    """Return a filtered DataFrame with Timestamp+Value columns, or None on any error.
    Accepts dates in DD-MM-YYYY or YYYY-MM-DD format. Station name may use spaces or underscores."""
    feature = CATEGORY_TO_FEATURE.get(category_name)
    if not feature or repo is None:
        return None
    try:
        start_iso = pd.to_datetime(start_date, dayfirst=True).strftime('%Y-%m-%d')
        end_iso = pd.to_datetime(end_date, dayfirst=True).strftime('%Y-%m-%d')
        request = SeriesRequest(station=station_key(station_name), feature=feature, start_date=start_iso, end_date=end_iso)
        return repo.get_feature_series(request)
    except Exception:
        return None


# ------------------------------
# LAYOUT / SHARED HELPERS
# ------------------------------

def normalize_series(series: pd.Series) -> pd.Series:
    series = pd.to_numeric(series, errors="coerce")
    min_val, max_val = series.min(), series.max()
    if pd.isna(min_val) or pd.isna(max_val) or min_val == max_val:
        return pd.Series([0.5] * len(series), index=series.index)
    return (series - min_val) / (max_val - min_val)


def apply_clean_layout(fig, title: str, yaxis_title: str = "Value", xaxis_title: str = "Date"):
    fig.update_layout(
        title={"text": title, "x": 0.5, "xanchor": "center", "font": dict(size=20, color="#1f2d3d")},
        template="plotly_white",
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin=dict(l=50, r=30, t=80, b=50),
        font=dict(family="Segoe UI, Arial, sans-serif", size=12, color="#223142"),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(title=xaxis_title, showline=True, linecolor="#9fb3c8", showgrid=True, gridcolor="#e7edf3", tickformat="%Y"),
        yaxis=dict(title=yaxis_title, showline=True, linecolor="#9fb3c8", showgrid=True, gridcolor="#e7edf3"),
    )
    return fig


def create_no_data_chart(title: str, message: str = "No data available for the selected range.") -> str:
    fig = go.Figure()
    fig.add_annotation(text=message, x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False, font=dict(size=16, color="#5f7082"))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    fig = apply_clean_layout(fig, title, "", "")
    return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)


def fig_to_json(fig) -> str:
    return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)


# ------------------------------
# CHART 1: Single Category, Single Station Timeline
# ------------------------------

def plot_single_category_single_station_chart(df_filtered, station_name, category_name):
    chart_title = f"{category_name} Trend at {station_name}"
    fig = px.area(df_filtered, x="Timestamp", y="Value", title=chart_title, labels={"Value": get_category_units(category_name)})
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
        chart_title = f"{category_name} Trend at {station_name}"
        df = get_feature_series_df(category_name, station_name, data["start_date"], data["end_date"])
        if df is None or df.empty:
            charts.append(create_no_data_chart(chart_title, "No data available for the selected range."))
            continue
        charts.append(plot_single_category_single_station_chart(df, station_name, category_name))
    return charts


# ------------------------------
# CHART 2: Multiple Categories, Single Station Timeline
# ------------------------------

def plot_multiple_categories_single_station_chart(categories_data, station_name):
    colors = px.colors.qualitative.Plotly
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    any_data = False
    overall_start = None
    overall_end = None

    for i, data in enumerate(categories_data):
        category_name = data["category_name"]
        start_dt = pd.to_datetime(data["start_date"], dayfirst=True)
        end_dt = pd.to_datetime(data["end_date"], dayfirst=True)
        overall_start = start_dt if overall_start is None else min(overall_start, start_dt)
        overall_end = end_dt if overall_end is None else max(overall_end, end_dt)

        df = get_feature_series_df(category_name, station_name, data["start_date"], data["end_date"])
        if df is None or df.empty:
            continue

        df["Normalized Value"] = normalize_series(df["Value"])
        any_data = True
        fig.add_trace(
            go.Scatter(
                x=df["Timestamp"], y=df["Normalized Value"], mode="lines",
                name=category_name, line=dict(color=colors[i % len(colors)], width=2),
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
    grouped = {}
    for data in selected_data:
        grouped.setdefault(data["station_name"], []).append(data)
    for station_name, categories_data in grouped.items():
        charts.append(plot_multiple_categories_single_station_chart(categories_data, station_name))
    return charts


# ------------------------------
# CHART 3: Single Category Across Multiple Stations
# ------------------------------

def plot_single_category_multiple_stations_chart(category_name, stations_data):
    colors = px.colors.qualitative.Plotly
    fig = go.Figure()
    any_data = False
    start_dts = [pd.to_datetime(d["start_date"], dayfirst=True) for d in stations_data]
    end_dts = [pd.to_datetime(d["end_date"], dayfirst=True) for d in stations_data]
    overall_start = min(start_dts) if start_dts else None
    overall_end = max(end_dts) if end_dts else None

    for i, data in enumerate(stations_data):
        station_name = data["station_name"]
        df = get_feature_series_df(category_name, station_name, data["start_date"], data["end_date"])
        if df is None or df.empty:
            continue
        any_data = True
        fig.add_trace(go.Scatter(
            x=df["Timestamp"], y=df["Value"], mode="lines", name=station_name,
            line=dict(color=colors[i % len(colors)], width=2),
            hovertemplate="Date: %{x|%d-%b-%Y}<br>Value: %{y:.2f}<extra></extra>",
        ))

    chart_title = f"{category_name} Comparison Across Stations"
    if not any_data:
        return create_no_data_chart(chart_title)

    fig = apply_clean_layout(fig, chart_title, get_category_units(category_name))
    fig.update_xaxes(range=[overall_start, overall_end])
    return fig_to_json(fig)


def generate_single_category_multiple_stations_visualizations(selected_data):
    charts = []
    grouped = {}
    for data in selected_data:
        grouped.setdefault(data["category_name"], []).append(data)
    for category_name, stations_data in grouped.items():
        charts.append(plot_single_category_multiple_stations_chart(category_name, stations_data))
    return charts


# ------------------------------
# CHART 4: Multiple Categories Across Multiple Stations
# ------------------------------

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
            start_dt = pd.to_datetime(data["start_date"], dayfirst=True)
            end_dt = pd.to_datetime(data["end_date"], dayfirst=True)
            overall_start = start_dt if overall_start is None else min(overall_start, start_dt)
            overall_end = end_dt if overall_end is None else max(overall_end, end_dt)

            df = get_feature_series_df(category_name, station_name, data["start_date"], data["end_date"])
            if df is None or df.empty:
                continue

            df["Normalized Value"] = normalize_series(df["Value"])
            any_data = True
            fig.add_trace(
                go.Scatter(
                    x=df["Timestamp"], y=df["Normalized Value"], mode="lines",
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
    group_data = {}
    for data in selected_data:
        group_data.setdefault(data["station_name"], []).append(data)
    return [plot_multiple_categories_multiple_stations_chart(group_data)]


# ------------------------------
# CHART 5: Year-over-Year Comparison
# ------------------------------

def plot_year_over_year_comparison_chart(station_name, category_name, start_date, end_date):
    chart_title = f"Year-over-Year {category_name} Comparison at {station_name}"
    df = get_feature_series_df(category_name, station_name, start_date, end_date)
    if df is None or df.empty:
        return create_no_data_chart(chart_title)

    df = df.copy()
    df["Year"] = df["Timestamp"].dt.year
    df["Month"] = df["Timestamp"].dt.month
    monthly_data = df.groupby(["Year", "Month"])["Value"].mean().reset_index()

    fig = go.Figure()
    colors = px.colors.qualitative.Plotly
    for i, year in enumerate(sorted(monthly_data["Year"].unique())):
        year_data = monthly_data[monthly_data["Year"] == year]
        fig.add_trace(go.Scatter(
            x=year_data["Month"], y=year_data["Value"], mode="lines+markers", name=str(year),
            line=dict(color=colors[i % len(colors)], width=2),
            hovertemplate="Month: %{x}<br>Value: %{y:.2f}<extra></extra>",
        ))

    fig = apply_clean_layout(fig, chart_title, get_category_units(category_name), "Month")
    fig.update_xaxes(tickmode="array", tickvals=list(range(1, 13)),
                     ticktext=["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])
    return fig_to_json(fig)


def generate_year_over_year_comparison_visualizations(selected_data):
    return [
        plot_year_over_year_comparison_chart(d["station_name"], d["category_name"], d["start_date"], d["end_date"])
        for d in selected_data
    ]


# ------------------------------
# CHART 6: Annual Monthly Totals Overview
# ------------------------------

def plot_annual_monthly_totals_chart(station_name, category_name, start_date, end_date):
    chart_title = f"Monthly Total Analysis for {category_name} at {station_name}"
    df = get_feature_series_df(category_name, station_name, start_date, end_date)
    if df is None or df.empty:
        return create_no_data_chart(chart_title)

    df = df.copy()
    df["Month"] = df["Timestamp"].dt.month
    monthly_totals = round(df.groupby("Month")["Value"].sum().reindex(range(1, 13), fill_value=0), 2)

    month_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    fig = go.Figure(data=[go.Bar(
        x=month_labels, y=monthly_totals.values, text=monthly_totals.values, textposition="auto",
        marker=dict(color="#7aa6d1"),
        hovertemplate="Month: %{x}<br>Total: %{y:.2f}<extra></extra>",
    )])
    fig = apply_clean_layout(fig, chart_title, get_category_units(category_name), "Month")
    return fig_to_json(fig)


def generate_annual_monthly_totals_visualizations(selected_data):
    return [
        plot_annual_monthly_totals_chart(d["station_name"], d["category_name"], d["start_date"], d["end_date"])
        for d in selected_data
    ]


# ------------------------------
# CHART 7: Flow Duration Curve
# ------------------------------

def plot_flow_duration_curve(station_name, category_name, start_date, end_date):
    chart_title = f"Flow Duration Curve — {category_name} at {station_name}"
    df = get_feature_series_df(category_name, station_name, start_date, end_date)
    if df is None or df.empty:
        return create_no_data_chart(chart_title)

    sorted_values = df["Value"].sort_values(ascending=False).reset_index(drop=True)
    exceedance = (sorted_values.index + 1) / len(sorted_values) * 100

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=exceedance, y=sorted_values, mode="lines",
        line=dict(color="#2f6da3", width=2),
        fill="tozeroy", fillcolor="rgba(47, 109, 163, 0.1)",
        hovertemplate="Exceedance: %{x:.1f}%<br>Value: %{y:.2f}<extra></extra>",
    ))
    fig = apply_clean_layout(fig, chart_title, get_category_units(category_name), "Exceedance Probability (%)")
    fig.update_xaxes(tickformat=".0f", range=[0, 100], ticksuffix="%")
    return fig_to_json(fig)


def generate_flow_duration_curve_visualizations(selected_data):
    return [
        plot_flow_duration_curve(d["station_name"], d["category_name"], d["start_date"], d["end_date"])
        for d in selected_data
    ]


# ------------------------------
# CHART 8: Monthly Distribution Box Plot
# ------------------------------

def plot_monthly_distribution_boxplot(station_name, category_name, start_date, end_date):
    chart_title = f"Monthly Distribution — {category_name} at {station_name}"
    df = get_feature_series_df(category_name, station_name, start_date, end_date)
    if df is None or df.empty:
        return create_no_data_chart(chart_title)

    df = df.copy()
    df["Month"] = df["Timestamp"].dt.month
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    fig = go.Figure()
    for month_num in range(1, 13):
        month_data = df[df["Month"] == month_num]["Value"]
        fig.add_trace(go.Box(
            y=month_data, name=month_names[month_num - 1],
            marker_color="#2f6da3", line_color="#1e4f7a", boxmean=True,
            hovertemplate=f"Month: {month_names[month_num - 1]}<br>Value: %{{y:.2f}}<extra></extra>",
        ))

    fig = apply_clean_layout(fig, chart_title, get_category_units(category_name), "Month")
    fig.update_layout(showlegend=False, hovermode="closest")
    return fig_to_json(fig)


def generate_monthly_distribution_boxplot_visualizations(selected_data):
    return [
        plot_monthly_distribution_boxplot(d["station_name"], d["category_name"], d["start_date"], d["end_date"])
        for d in selected_data
    ]


# ------------------------------
# CHART 9: Multi-Station Temporal Heatmap
# ------------------------------

def plot_multi_station_temporal_heatmap(category_name, stations_data):
    chart_title = f"{category_name} — Multi-Station Temporal Heatmap"
    station_names = []
    year_values: dict = {}

    for data in stations_data:
        station_name = data["station_name"]
        df = get_feature_series_df(category_name, station_name, data["start_date"], data["end_date"])
        if df is None or df.empty:
            continue

        df = df.copy()
        df["Year"] = df["Timestamp"].dt.year
        yearly_avg = df.groupby("Year")["Value"].mean()
        station_names.append(station_name)
        for year, val in yearly_avg.items():
            year_values.setdefault(year, {})[station_name] = round(val, 2)

    if not station_names:
        return create_no_data_chart(chart_title)

    years = sorted(year_values.keys())
    z_matrix = [[year_values.get(year, {}).get(station, None) for year in years] for station in station_names]

    fig = go.Figure(data=go.Heatmap(
        z=z_matrix, x=[str(y) for y in years], y=station_names,
        colorscale="Blues", colorbar=dict(title=get_category_units(category_name)),
        hovertemplate="Year: %{x}<br>Station: %{y}<br>Avg Value: %{z:.2f}<extra></extra>",
    ))
    fig = apply_clean_layout(fig, chart_title, "", "Year")
    fig.update_layout(yaxis_title="Station", hovermode="closest")
    return fig_to_json(fig)


def generate_multi_station_heatmap_visualizations(selected_data):
    charts = []
    grouped = {}
    for data in selected_data:
        grouped.setdefault(data["category_name"], []).append(data)
    for category_name, stations_data in grouped.items():
        charts.append(plot_multi_station_temporal_heatmap(category_name, stations_data))
    return charts


# ------------------------------
# CHART 10: Correlation Scatter Plot
# ------------------------------

def plot_correlation_scatter(station_name, categories_data):
    if len(categories_data) < 2:
        return create_no_data_chart("Correlation Scatter Plot", "Two categories are required for this chart.")

    data_a, data_b = categories_data[0], categories_data[1]
    cat_a, cat_b = data_a["category_name"], data_b["category_name"]
    chart_title = f"Correlation: {cat_a} vs {cat_b} at {station_name}"

    df_a = get_feature_series_df(cat_a, station_name, data_a["start_date"], data_a["end_date"])
    df_b = get_feature_series_df(cat_b, station_name, data_b["start_date"], data_b["end_date"])

    if df_a is None or df_b is None or df_a.empty or df_b.empty:
        return create_no_data_chart(chart_title)

    series_a = df_a.set_index(df_a["Timestamp"].dt.date)["Value"].rename(cat_a)
    series_b = df_b.set_index(df_b["Timestamp"].dt.date)["Value"].rename(cat_b)
    merged = pd.concat([series_a, series_b], axis=1).dropna()

    if merged.empty:
        return create_no_data_chart(chart_title, "No overlapping dates found between the two categories.")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=merged[cat_a], y=merged[cat_b], mode="markers",
        marker=dict(color="#2f6da3", size=5, opacity=0.65),
        hovertemplate=f"{cat_a}: %{{x:.2f}}<br>{cat_b}: %{{y:.2f}}<extra></extra>",
    ))
    fig = apply_clean_layout(fig, chart_title, get_category_units(cat_b), get_category_units(cat_a))
    fig.update_layout(hovermode="closest")
    return fig_to_json(fig)


def generate_correlation_scatter_visualizations(selected_data):
    charts = []
    grouped = {}
    for data in selected_data:
        grouped.setdefault(data["station_name"], []).append(data)
    for station_name, categories_data in grouped.items():
        charts.append(plot_correlation_scatter(station_name, categories_data))
    return charts


# ------------------------------
# CHART 11: Anomaly Detection Chart
# ------------------------------

def plot_anomaly_detection_chart(station_name, category_name, start_date, end_date):
    chart_title = f"Anomaly Detection — {category_name} at {station_name}"
    df = get_feature_series_df(category_name, station_name, start_date, end_date)
    if df is None or df.empty:
        return create_no_data_chart(chart_title)

    df = df.copy()
    mean_val = df["Value"].mean()
    std_val = df["Value"].std()
    df["ZScore"] = (df["Value"] - mean_val) / std_val if std_val > 0 else 0.0
    df["IsAnomaly"] = df["ZScore"].abs() > 2.5

    normal = df[~df["IsAnomaly"]]
    anomalies = df[df["IsAnomaly"]]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=normal["Timestamp"], y=normal["Value"], mode="lines", name="Normal",
        line=dict(color="#2f6da3", width=1.5),
        hovertemplate="Date: %{x|%d-%b-%Y}<br>Value: %{y:.2f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=anomalies["Timestamp"], y=anomalies["Value"], mode="markers",
        name=f"Anomaly ({len(anomalies)})",
        marker=dict(color="#c0392b", size=7, symbol="circle-open", line=dict(width=2)),
        hovertemplate="Date: %{x|%d-%b-%Y}<br>Value: %{y:.2f} (anomaly)<extra></extra>",
    ))
    fig = apply_clean_layout(fig, chart_title, get_category_units(category_name))
    return fig_to_json(fig)


def generate_anomaly_detection_visualizations(selected_data):
    return [
        plot_anomaly_detection_chart(d["station_name"], d["category_name"], d["start_date"], d["end_date"])
        for d in selected_data
    ]


# ------------------------------
# CHART 12: Rolling Average Trend
# ------------------------------

def plot_rolling_average_trend(station_name, category_name, start_date, end_date):
    chart_title = f"Rolling Average Trend — {category_name} at {station_name}"
    df = get_feature_series_df(category_name, station_name, start_date, end_date)
    if df is None or df.empty:
        return create_no_data_chart(chart_title)

    df = df.copy().sort_values("Timestamp")
    df["Roll3"]  = df["Value"].rolling(window=3,  min_periods=1).mean()
    df["Roll12"] = df["Value"].rolling(window=12, min_periods=1).mean()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["Timestamp"], y=df["Value"], mode="lines", name="Raw data",
        line=dict(color="rgba(180,200,220,0.55)", width=1),
        hovertemplate="Date: %{x|%d-%b-%Y}<br>Value: %{y:.2f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=df["Timestamp"], y=df["Roll3"], mode="lines", name="3-month rolling avg",
        line=dict(color="#d4863a", width=2),
        hovertemplate="Date: %{x|%d-%b-%Y}<br>3-month avg: %{y:.2f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=df["Timestamp"], y=df["Roll12"], mode="lines", name="12-month rolling avg",
        line=dict(color="#1c2340", width=2.5),
        hovertemplate="Date: %{x|%d-%b-%Y}<br>12-month avg: %{y:.2f}<extra></extra>",
    ))
    fig = apply_clean_layout(fig, chart_title, get_category_units(category_name))
    return fig_to_json(fig)


def generate_rolling_average_trend_visualizations(selected_data):
    return [
        plot_rolling_average_trend(d["station_name"], d["category_name"], d["start_date"], d["end_date"])
        for d in selected_data
    ]


# ------------------------------
# CHART 13: Cumulative Departure
# ------------------------------

def plot_cumulative_departure(station_name, category_name, start_date, end_date):
    chart_title = f"Cumulative Departure from Mean — {category_name} at {station_name}"
    df = get_feature_series_df(category_name, station_name, start_date, end_date)
    if df is None or df.empty:
        return create_no_data_chart(chart_title)

    df = df.copy().sort_values("Timestamp")
    long_mean = df["Value"].mean()
    df["Departure"]   = df["Value"] - long_mean
    df["Cumulative"]  = df["Departure"].cumsum()

    colors = np.where(df["Cumulative"] >= 0, "#2e8b6e", "#c0392b")

    fig = go.Figure()
    fig.add_hline(y=0, line=dict(color="#aaaaaa", width=1, dash="dash"))
    fig.add_trace(go.Bar(
        x=df["Timestamp"], y=df["Cumulative"],
        name="Cumulative departure",
        marker_color=colors.tolist(),
        hovertemplate="Date: %{x|%d-%b-%Y}<br>Cumulative departure: %{y:.2f}<extra></extra>",
    ))
    fig = apply_clean_layout(fig, chart_title, f"Cumulative departure ({get_category_units(category_name)})")
    fig.add_annotation(
        x=0.01, y=0.97, xref="paper", yref="paper",
        text=f"Long-term mean: {long_mean:.2f}",
        showarrow=False, font=dict(size=11, color="#666"), xanchor="left",
    )
    return fig_to_json(fig)


def generate_cumulative_departure_visualizations(selected_data):
    return [
        plot_cumulative_departure(d["station_name"], d["category_name"], d["start_date"], d["end_date"])
        for d in selected_data
    ]


# ------------------------------
# CHART 14: Monthly Climatology
# ------------------------------

def plot_monthly_climatology(station_name, category_name, start_date, end_date):
    chart_title = f"Monthly Climatology — {category_name} at {station_name}"
    df = get_feature_series_df(category_name, station_name, start_date, end_date)
    if df is None or df.empty:
        return create_no_data_chart(chart_title)

    df = df.copy()
    df["Month"] = df["Timestamp"].dt.month
    clim = df.groupby("Month")["Value"].agg(["mean", "std"]).reindex(range(1, 13)).fillna(0)
    month_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=month_labels, y=clim["mean"],
        error_y=dict(type="data", array=clim["std"].tolist(), visible=True, color="#888", thickness=1.5),
        name="Monthly mean",
        marker=dict(
            color=clim["mean"].tolist(),
            colorscale=[[0, "#d4e9f7"], [0.5, "#2e8b6e"], [1, "#1c2340"]],
            showscale=False,
        ),
        hovertemplate="Month: %{x}<br>Mean: %{y:.2f}<br>Std Dev: %{error_y.array:.2f}<extra></extra>",
    ))
    years = int(df["Timestamp"].dt.year.max()) - int(df["Timestamp"].dt.year.min()) + 1
    fig = apply_clean_layout(fig, chart_title, get_category_units(category_name), "Month")
    fig.add_annotation(
        x=0.01, y=0.97, xref="paper", yref="paper",
        text=f"Based on {years} years of data — error bars show ±1 std dev",
        showarrow=False, font=dict(size=11, color="#666"), xanchor="left",
    )
    fig.update_layout(showlegend=False)
    return fig_to_json(fig)


def generate_monthly_climatology_visualizations(selected_data):
    return [
        plot_monthly_climatology(d["station_name"], d["category_name"], d["start_date"], d["end_date"])
        for d in selected_data
    ]


# ------------------------------
# CHART 15: Decade Comparison
# ------------------------------

def plot_decade_comparison(station_name, category_name, start_date, end_date):
    chart_title = f"Decade-by-Decade Comparison — {category_name} at {station_name}"
    df = get_feature_series_df(category_name, station_name, start_date, end_date)
    if df is None or df.empty:
        return create_no_data_chart(chart_title)

    df = df.copy()
    df["Decade"] = (df["Timestamp"].dt.year // 10 * 10).astype(str) + "s"
    decades = sorted(df["Decade"].unique())

    if len(decades) < 2:
        return create_no_data_chart(chart_title, "Not enough data — at least two decades required.")

    colors = px.colors.qualitative.Plotly
    fig = go.Figure()
    for i, decade in enumerate(decades):
        decade_data = df[df["Decade"] == decade]["Value"]
        fig.add_trace(go.Box(
            y=decade_data, name=decade,
            marker_color=colors[i % len(colors)],
            boxmean="sd",
            hovertemplate=f"Decade: {decade}<br>Value: %{{y:.2f}}<extra></extra>",
        ))

    fig = apply_clean_layout(fig, chart_title, get_category_units(category_name), "Decade")
    fig.update_layout(showlegend=False, hovermode="closest")
    return fig_to_json(fig)


def generate_decade_comparison_visualizations(selected_data):
    return [
        plot_decade_comparison(d["station_name"], d["category_name"], d["start_date"], d["end_date"])
        for d in selected_data
    ]


# ------------------------------
# CHART 16: Station Ranking Bar Chart
# ------------------------------

def plot_station_ranking_bar(category_name, stations_data):
    chart_title = f"Station Ranking by Average {category_name}"
    rows = []
    for data in stations_data:
        df = get_feature_series_df(category_name, data["station_name"], data["start_date"], data["end_date"])
        if df is None or df.empty:
            continue
        rows.append({
            "station": data["station_name"],
            "mean":    round(float(df["Value"].mean()), 2),
            "max":     round(float(df["Value"].max()), 2),
            "min":     round(float(df["Value"].min()), 2),
        })

    if not rows:
        return create_no_data_chart(chart_title)

    rows.sort(key=lambda r: r["mean"])
    stations = [r["station"] for r in rows]
    means    = [r["mean"]   for r in rows]

    norm = np.array(means)
    norm = (norm - norm.min()) / (norm.max() - norm.min() + 1e-9)
    bar_colors = [f"rgba(28,35,64,{0.4 + 0.6 * float(v):.2f})" for v in norm]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=stations, x=means, orientation="h",
        name="Average value",
        marker_color=bar_colors,
        text=[f"{v:.2f}" for v in means], textposition="outside",
        hovertemplate="Station: %{y}<br>Average: %{x:.2f}<extra></extra>",
    ))
    fig = apply_clean_layout(fig, chart_title, "", get_category_units(category_name))
    # Override the date tickformat that apply_clean_layout sets — x-axis is numeric here
    fig.update_xaxes(tickformat="", title=get_category_units(category_name))
    fig.update_layout(
        yaxis_title="",
        hovermode="closest",
        margin=dict(l=160, r=60, t=80, b=50),
    )
    return fig_to_json(fig)


def generate_station_ranking_bar_visualizations(selected_data):
    charts = []
    grouped = {}
    for data in selected_data:
        grouped.setdefault(data["category_name"], []).append(data)
    for category_name, stations_data in grouped.items():
        charts.append(plot_station_ranking_bar(category_name, stations_data))
    return charts


# ------------------------------
# SUMMARY & RANKING
# ------------------------------

def build_summary_for_selection(selected_data):
    if not selected_data:
        return {
            "station": "--", "category": "--", "date_range": "--",
            "mean": "--", "min": "--", "max": "--",
            "first_year": "--", "last_year": "--", "record_count": "--",
            "coverage_note": "Awaiting visualization selection",
        }

    first = selected_data[0]
    station_name = first["station_name"]
    category_name = first["category_name"]
    start_date = first["start_date"]
    end_date = first["end_date"]

    df = get_feature_series_df(category_name, station_name, start_date, end_date)
    if df is None or df.empty:
        return {
            "station": station_display(station_name), "category": category_name,
            "date_range": f"{start_date} -> {end_date}",
            "mean": "--", "min": "--", "max": "--",
            "first_year": "--", "last_year": "--", "record_count": 0,
            "coverage_note": "No data available for selected range",
        }

    std_dev = round(float(df["Value"].std()), 2) if len(df) > 1 else 0.0

    mid = len(df) // 2
    first_half_mean = float(df["Value"].iloc[:mid].mean()) if mid > 0 else 0.0
    second_half_mean = float(df["Value"].iloc[mid:].mean()) if mid > 0 else 0.0
    if first_half_mean != 0:
        trend_pct = round((second_half_mean - first_half_mean) / abs(first_half_mean) * 100, 1)
    else:
        trend_pct = 0.0
    trend_direction = "up" if trend_pct > 1 else ("down" if trend_pct < -1 else "stable")

    date_span_months = max((df["Timestamp"].max() - df["Timestamp"].min()).days / 30.44, 1)
    coverage_pct = round(min(len(df) / date_span_months * 100, 100), 1)

    return {
        "station": station_display(station_name),
        "category": category_name,
        "date_range": f"{start_date} -> {end_date}",
        "mean": round(df["Value"].mean(), 2),
        "min": round(df["Value"].min(), 2),
        "max": round(df["Value"].max(), 2),
        "std_dev": std_dev,
        "trend_pct": abs(trend_pct),
        "trend_direction": trend_direction,
        "coverage_pct": coverage_pct,
        "first_year": int(df["Timestamp"].dt.year.min()),
        "last_year": int(df["Timestamp"].dt.year.max()),
        "record_count": int(len(df)),
        "coverage_note": "Based on current visualization selection",
    }


def build_station_ranking_for_category(category_name: str, top_n: int = 5):
    feature = CATEGORY_TO_FEATURE.get(category_name)
    if not feature or repo is None:
        return []

    ranking_rows = []
    for station_name, station_meta in repo.station_index.items():
        if feature not in station_meta.get("features", []):
            continue
        try:
            df = repo.get_station_dataframe(station_name)
            if feature not in df.columns:
                continue
            series = pd.to_numeric(df[feature], errors="coerce").dropna()
            if series.empty:
                continue
            ranking_rows.append({
                "station": station_display(station_name),
                "average_value": round(float(series.mean()), 2),
                "maximum_value": round(float(series.max()), 2),
                "record_count": int(len(series)),
            })
        except Exception:
            continue

    ranking_rows.sort(key=lambda r: r["average_value"], reverse=True)
    return ranking_rows[:top_n]


# ------------------------------
# MAIN ENTRY POINT
# ------------------------------

GRAPH_DISPATCH = {
    "Single Category, Single Station Timeline": generate_single_category_single_station_visualizations,
    "Multiple Categories, Single Station Timeline": generate_multiple_categories_single_station_visualizations,
    "Single Category Across Multiple Stations Comparison": generate_single_category_multiple_stations_visualizations,
    "Multiple Categories Across Multiple Stations Comparison": generate_multiple_categories_multiple_stations_visualizations,
    "Year-over-Year Comparison": generate_year_over_year_comparison_visualizations,
    "Annual Monthly Totals Overview": generate_annual_monthly_totals_visualizations,
    "Flow Duration Curve": generate_flow_duration_curve_visualizations,
    "Monthly Distribution Box Plot": generate_monthly_distribution_boxplot_visualizations,
    "Multi-Station Temporal Heatmap": generate_multi_station_heatmap_visualizations,
    "Correlation Scatter Plot": generate_correlation_scatter_visualizations,
    "Anomaly Detection Chart": generate_anomaly_detection_visualizations,
    "Rolling Average Trend": generate_rolling_average_trend_visualizations,
    "Cumulative Departure from Mean": generate_cumulative_departure_visualizations,
    "Monthly Climatology": generate_monthly_climatology_visualizations,
    "Decade Comparison": generate_decade_comparison_visualizations,
    "Station Ranking Bar Chart": generate_station_ranking_bar_visualizations,
}


def generate_visualizations_with_summary(graph_type: str, selected_data: list) -> dict:
    generator = GRAPH_DISPATCH.get(graph_type)
    charts = generator(selected_data) if generator else []

    summary = build_summary_for_selection(selected_data)
    ranking = build_station_ranking_for_category(summary["category"]) if summary["category"] != "--" else []

    return {"charts": charts, "summary": summary, "ranking": ranking}


# ------------------------------
# HOLT-WINTERS PREDICTION
# ------------------------------

def generate_holt_winters_prediction(
    category_name: str,
    station_name: str,
    start_date: str,
    end_date: str,
    forecast_months: int = 12,
) -> dict:
    """Fit a Holt-Winters model on monthly-resampled historical data and forecast ahead."""
    df = get_feature_series_df(category_name, station_name, start_date, end_date)
    if df is None or df.empty:
        raise ValueError(f"No data found for {station_name} / {category_name}")

    unit_label = get_category_units(category_name)

    series = (
        df.set_index("Timestamp")["Value"]
        .resample("MS")
        .mean()
        .interpolate(method="linear")
        .dropna()
    )

    if len(series) < 12:
        raise ValueError("At least 12 months of data are required for forecasting.")

    use_seasonal = len(series) >= 24

    model = ExponentialSmoothing(
        series,
        trend="add",
        seasonal="add" if use_seasonal else None,
        seasonal_periods=12 if use_seasonal else None,
        initialization_method="estimated",
    )
    fitted = model.fit(optimized=True, remove_bias=True)

    forecast = fitted.forecast(forecast_months)
    residuals = series - fitted.fittedvalues
    sigma = float(residuals.std())
    ci_offset = pd.Series(
        [1.96 * sigma * float(np.sqrt(h)) for h in range(1, forecast_months + 1)],
        index=forecast.index,
    )
    ci_upper = forecast + ci_offset
    ci_lower = (forecast - ci_offset).clip(lower=0.0)

    # Bridge point: last historical observation used to connect all traces
    bridge_date  = series.index[-1]
    bridge_value = float(series.values[-1])

    # Extend CI band to start at the last historical point (zero width there)
    ci_upper_bridged = pd.concat([pd.Series([bridge_value], index=[bridge_date]), ci_upper])
    ci_lower_bridged = pd.concat([pd.Series([bridge_value], index=[bridge_date]), ci_lower])

    # Extend forecast trace to start at the last historical point
    forecast_x = [bridge_date] + list(forecast.index)
    forecast_y = [bridge_value] + list(forecast.values)

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=list(ci_upper_bridged.index) + list(ci_lower_bridged.index[::-1]),
        y=list(ci_upper_bridged.values) + list(ci_lower_bridged.values[::-1]),
        fill="toself",
        fillcolor="rgba(231,107,64,0.15)",
        line=dict(color="rgba(0,0,0,0)"),
        name="95% Confidence Interval",
        hoverinfo="skip",
    ))

    fig.add_trace(go.Scatter(
        x=series.index, y=series.values,
        mode="lines", name="Historical (monthly avg)",
        line=dict(color="#2874a6", width=2),
    ))

    fig.add_trace(go.Scatter(
        x=fitted.fittedvalues.index, y=fitted.fittedvalues.values,
        mode="lines", name="Model fit",
        line=dict(color="#27ae60", width=1.5, dash="dot"),
    ))

    fig.add_trace(go.Scatter(
        x=forecast_x, y=forecast_y,
        mode="lines+markers",
        name=f"Forecast ({forecast_months} months)",
        line=dict(color="#e74c3c", width=2.5),
        marker=dict(size=5),
    ))

    split_x = series.index[-1]
    fig.add_shape(
        type="line",
        x0=split_x, x1=split_x,
        y0=0, y1=1,
        yref="paper",
        line=dict(color="#888888", width=1.5, dash="dash"),
    )
    fig.add_annotation(
        x=split_x, y=1, yref="paper",
        text="Forecast start",
        showarrow=False,
        xanchor="left",
        font=dict(size=11, color="#888888"),
    )

    apply_clean_layout(
        fig,
        title=f"Holt-Winters Forecast — {station_display(station_name)} · {category_name}",
        yaxis_title=unit_label,
        xaxis_title="Date",
    )

    params = fitted.params if isinstance(fitted.params, dict) else dict(fitted.params)
    rmse = float(np.sqrt(float(np.mean(residuals ** 2))))

    def _p(key):
        v = params.get(key)
        try:
            return round(float(v), 4) if v is not None else 0.0
        except (TypeError, ValueError):
            return 0.0

    model_info = {
        "station": station_display(station_name),
        "category": category_name,
        "historical_months": int(len(series)),
        "model_type": "Holt-Winters (additive trend + seasonal)" if use_seasonal else "Holt-Winters (additive trend only)",
        "forecast_months": int(forecast_months),
        "alpha": _p("smoothing_level"),
        "beta": _p("smoothing_trend"),
        "gamma": _p("smoothing_seasonal") if use_seasonal else None,
        "aic": round(float(fitted.aic), 2),
        "rmse": round(rmse, 4),
        "last_historical": series.index[-1].strftime("%Y-%m"),
        "forecast_end": forecast.index[-1].strftime("%Y-%m"),
    }

    return {
        "chart": json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder),
        "model_info": model_info,
    }


# ------------------------------
# SHARED ML HELPERS
# ------------------------------

def _prepare_ml_series(category_name, station_name, start_date, end_date):
    """Load and resample to monthly. Returns pd.Series indexed by DatetimeIndex."""
    df = get_feature_series_df(category_name, station_name, start_date, end_date)
    if df is None or df.empty:
        raise ValueError(f"No data found for {station_name} / {category_name}")
    series = (
        df.set_index("Timestamp")["Value"]
        .resample("MS").mean()
        .interpolate(method="linear")
        .dropna()
    )
    if len(series) < 12:
        raise ValueError("At least 12 months of data are required for forecasting.")
    return series


def _make_forecast_chart(series, fitted_vals, forecast_vals, forecast_index, ci_upper, ci_lower,
                          model_label, station_name, category_name, accent_color="#e74c3c"):
    """Build a standard Plotly figure for any forecast model."""
    unit_label = get_category_units(category_name)
    bridge_date = series.index[-1]
    bridge_value = float(series.values[-1])

    ci_upper_bridged = [bridge_value] + list(ci_upper)
    ci_lower_bridged = [bridge_value] + list(ci_lower)
    ci_x = [bridge_date] + list(forecast_index)

    forecast_x = [bridge_date] + list(forecast_index)
    forecast_y = [bridge_value] + list(forecast_vals)

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=ci_x + ci_x[::-1],
        y=ci_upper_bridged + ci_lower_bridged[::-1],
        fill="toself",
        fillcolor="rgba(231,107,64,0.13)",
        line=dict(color="rgba(0,0,0,0)"),
        name="95% Confidence Interval",
        hoverinfo="skip",
    ))

    fig.add_trace(go.Scatter(
        x=series.index, y=series.values,
        mode="lines", name="Historical (monthly avg)",
        line=dict(color="#2874a6", width=2),
    ))

    if fitted_vals is not None:
        fig.add_trace(go.Scatter(
            x=series.index, y=fitted_vals,
            mode="lines", name="Model fit",
            line=dict(color="#27ae60", width=1.5, dash="dot"),
        ))

    fig.add_trace(go.Scatter(
        x=forecast_x, y=forecast_y,
        mode="lines+markers",
        name=f"Forecast ({len(forecast_vals)} months)",
        line=dict(color=accent_color, width=2.5),
        marker=dict(size=5),
    ))

    split_x = series.index[-1]
    fig.add_shape(type="line", x0=split_x, x1=split_x, y0=0, y1=1, yref="paper",
                  line=dict(color="#888888", width=1.5, dash="dash"))
    fig.add_annotation(x=split_x, y=1, yref="paper", text="Forecast start",
                       showarrow=False, xanchor="left", font=dict(size=11, color="#888888"))

    apply_clean_layout(
        fig,
        title=f"{model_label} — {station_display(station_name)} · {category_name}",
        yaxis_title=unit_label,
        xaxis_title="Date",
    )
    return fig


def _make_lag_features(series: pd.Series, lags=(1, 2, 3, 6, 12)):
    """Build lag + month seasonality features for ML models."""
    df = pd.DataFrame({"value": series})
    for lag in lags:
        df[f"lag_{lag}"] = df["value"].shift(lag)
    df["month_sin"] = np.sin(2 * np.pi * df.index.month / 12)
    df["month_cos"] = np.cos(2 * np.pi * df.index.month / 12)
    df["month_sin2"] = np.sin(4 * np.pi * df.index.month / 12)
    df["month_cos2"] = np.cos(4 * np.pi * df.index.month / 12)
    return df.dropna()


def _iterative_forecast(model, last_known: pd.Series, forecast_months: int,
                        lags=(1, 2, 3, 6, 12), scaler=None):
    """Iteratively predict future values using previous predictions as lags."""
    history = list(last_known.values)
    future_dates = pd.date_range(last_known.index[-1] + pd.DateOffset(months=1),
                                 periods=forecast_months, freq="MS")
    predictions = []
    for date in future_dates:
        row = {}
        for lag in lags:
            row[f"lag_{lag}"] = history[-lag] if lag <= len(history) else history[0]
        row["month_sin"] = np.sin(2 * np.pi * date.month / 12)
        row["month_cos"] = np.cos(2 * np.pi * date.month / 12)
        row["month_sin2"] = np.sin(4 * np.pi * date.month / 12)
        row["month_cos2"] = np.cos(4 * np.pi * date.month / 12)
        X = np.array([[row[k] for k in sorted(row.keys())]])
        if scaler:
            X = scaler.transform(X)
        pred = float(model.predict(X)[0])
        pred = max(pred, 0.0)
        predictions.append(pred)
        history.append(pred)
    return predictions, future_dates


def _residual_ci(residuals, forecast_months):
    """Compute growing CI from in-sample residuals (1.96 * sigma * sqrt(h))."""
    sigma = float(np.std(residuals))
    return [1.96 * sigma * np.sqrt(h) for h in range(1, forecast_months + 1)]


# ------------------------------
# SARIMA
# ------------------------------

def generate_sarima_prediction(category_name, station_name, start_date, end_date, forecast_months=12):
    series = _prepare_ml_series(category_name, station_name, start_date, end_date)
    use_seasonal = len(series) >= 24

    order = (1, 1, 1)
    seasonal_order = (1, 1, 0, 12) if use_seasonal else (0, 0, 0, 0)

    model = SARIMAX(series, order=order, seasonal_order=seasonal_order,
                    enforce_stationarity=False, enforce_invertibility=False)
    fitted = model.fit(disp=False)

    forecast_result = fitted.get_forecast(steps=forecast_months)
    forecast_mean = forecast_result.predicted_mean
    ci = forecast_result.conf_int(alpha=0.05)
    ci_upper = list(ci.iloc[:, 1].clip(lower=0))
    ci_lower = list(ci.iloc[:, 0].clip(lower=0))

    residuals = series - fitted.fittedvalues
    rmse = float(np.sqrt(np.mean(residuals.dropna() ** 2)))

    fig = _make_forecast_chart(
        series, list(fitted.fittedvalues), list(forecast_mean.values),
        forecast_mean.index, ci_upper, ci_lower,
        "SARIMA Forecast", station_name, category_name, accent_color="#8e44ad"
    )

    model_info = {
        "station": station_display(station_name),
        "category": category_name,
        "historical_months": int(len(series)),
        "model_type": f"SARIMA{order}x{seasonal_order}" + (" (seasonal)" if use_seasonal else ""),
        "forecast_months": int(forecast_months),
        "aic": round(float(fitted.aic), 2),
        "rmse": round(rmse, 4),
        "last_historical": series.index[-1].strftime("%Y-%m"),
        "forecast_end": forecast_mean.index[-1].strftime("%Y-%m"),
    }
    return {"chart": json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder), "model_info": model_info}


# ------------------------------
# RANDOM FOREST
# ------------------------------

def generate_random_forest_prediction(category_name, station_name, start_date, end_date, forecast_months=12):
    series = _prepare_ml_series(category_name, station_name, start_date, end_date)
    feat_df = _make_lag_features(series)
    feature_cols = sorted([c for c in feat_df.columns if c != "value"])

    X = feat_df[feature_cols].values
    y = feat_df["value"].values

    model = RandomForestRegressor(n_estimators=200, max_depth=8, random_state=42, n_jobs=-1)
    model.fit(X, y)

    fitted_vals = model.predict(X)
    residuals = y - fitted_vals
    rmse = float(np.sqrt(np.mean(residuals ** 2)))

    forecast_vals, future_dates = _iterative_forecast(model, series, forecast_months)
    ci_offsets = _residual_ci(residuals, forecast_months)
    ci_upper = [max(v + o, 0) for v, o in zip(forecast_vals, ci_offsets)]
    ci_lower = [max(v - o, 0) for v, o in zip(forecast_vals, ci_offsets)]

    # Align fitted_vals back onto the series index (lag rows were dropped)
    fitted_series = pd.Series(fitted_vals, index=feat_df.index)

    fig = _make_forecast_chart(
        series, list(fitted_series), forecast_vals, future_dates,
        ci_upper, ci_lower,
        "Random Forest Forecast", station_name, category_name, accent_color="#d35400"
    )

    importances = dict(zip(feature_cols, model.feature_importances_.round(3)))
    top_features = ", ".join(f"{k}={v}" for k, v in sorted(importances.items(), key=lambda x: -x[1])[:3])

    model_info = {
        "station": station_display(station_name),
        "category": category_name,
        "historical_months": int(len(series)),
        "model_type": "Random Forest (n=200 trees, max_depth=8)",
        "forecast_months": int(forecast_months),
        "rmse": round(rmse, 4),
        "top_features": top_features,
        "last_historical": series.index[-1].strftime("%Y-%m"),
        "forecast_end": future_dates[-1].strftime("%Y-%m"),
    }
    return {"chart": json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder), "model_info": model_info}


# ------------------------------
# GRADIENT BOOSTING
# ------------------------------

def generate_gradient_boosting_prediction(category_name, station_name, start_date, end_date, forecast_months=12):
    series = _prepare_ml_series(category_name, station_name, start_date, end_date)
    feat_df = _make_lag_features(series)
    feature_cols = sorted([c for c in feat_df.columns if c != "value"])

    X = feat_df[feature_cols].values
    y = feat_df["value"].values

    model = GradientBoostingRegressor(n_estimators=200, max_depth=4, learning_rate=0.05, random_state=42)
    model.fit(X, y)

    fitted_vals = model.predict(X)
    residuals = y - fitted_vals
    rmse = float(np.sqrt(np.mean(residuals ** 2)))

    forecast_vals, future_dates = _iterative_forecast(model, series, forecast_months)
    ci_offsets = _residual_ci(residuals, forecast_months)
    ci_upper = [max(v + o, 0) for v, o in zip(forecast_vals, ci_offsets)]
    ci_lower = [max(v - o, 0) for v, o in zip(forecast_vals, ci_offsets)]

    fitted_series = pd.Series(fitted_vals, index=feat_df.index)

    fig = _make_forecast_chart(
        series, list(fitted_series), forecast_vals, future_dates,
        ci_upper, ci_lower,
        "Gradient Boosting Forecast", station_name, category_name, accent_color="#16a085"
    )

    model_info = {
        "station": station_display(station_name),
        "category": category_name,
        "historical_months": int(len(series)),
        "model_type": "Gradient Boosting (n=200, lr=0.05, depth=4)",
        "forecast_months": int(forecast_months),
        "rmse": round(rmse, 4),
        "last_historical": series.index[-1].strftime("%Y-%m"),
        "forecast_end": future_dates[-1].strftime("%Y-%m"),
    }
    return {"chart": json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder), "model_info": model_info}


# ------------------------------
# LINEAR TREND + SEASONALITY
# ------------------------------

def generate_linear_seasonal_prediction(category_name, station_name, start_date, end_date, forecast_months=12):
    series = _prepare_ml_series(category_name, station_name, start_date, end_date)

    n = len(series)
    t = np.arange(n)
    months = series.index.month

    def make_X(t_vals, month_vals):
        return np.column_stack([
            t_vals,
            np.sin(2 * np.pi * month_vals / 12),
            np.cos(2 * np.pi * month_vals / 12),
            np.sin(4 * np.pi * month_vals / 12),
            np.cos(4 * np.pi * month_vals / 12),
        ])

    X_train = make_X(t, months)
    y_train = series.values

    model = LinearRegression()
    model.fit(X_train, y_train)

    fitted_vals = model.predict(X_train)
    residuals = y_train - fitted_vals
    rmse = float(np.sqrt(np.mean(residuals ** 2)))
    sigma = float(np.std(residuals))

    future_dates = pd.date_range(series.index[-1] + pd.DateOffset(months=1),
                                 periods=forecast_months, freq="MS")
    t_future = np.arange(n, n + forecast_months)
    X_future = make_X(t_future, future_dates.month)
    forecast_vals = list(np.maximum(model.predict(X_future), 0))

    ci_offsets = [1.96 * sigma * np.sqrt(h) for h in range(1, forecast_months + 1)]
    ci_upper = [max(v + o, 0) for v, o in zip(forecast_vals, ci_offsets)]
    ci_lower = [max(v - o, 0) for v, o in zip(forecast_vals, ci_offsets)]

    fig = _make_forecast_chart(
        series, list(fitted_vals), forecast_vals, future_dates,
        ci_upper, ci_lower,
        "Linear Trend + Seasonality Forecast", station_name, category_name, accent_color="#2980b9"
    )

    coef_labels = ["Trend", "sin(2π/12)", "cos(2π/12)", "sin(4π/12)", "cos(4π/12)"]
    coef_str = ", ".join(f"{l}={round(c,3)}" for l, c in zip(coef_labels, model.coef_))

    model_info = {
        "station": station_display(station_name),
        "category": category_name,
        "historical_months": int(n),
        "model_type": "Linear Regression with Fourier Seasonal Terms",
        "forecast_months": int(forecast_months),
        "rmse": round(rmse, 4),
        "r2": round(float(model.score(X_train, y_train)), 4),
        "coefficients": coef_str,
        "last_historical": series.index[-1].strftime("%Y-%m"),
        "forecast_end": future_dates[-1].strftime("%Y-%m"),
    }
    return {"chart": json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder), "model_info": model_info}


# ------------------------------
# SVR (Support Vector Regression)
# ------------------------------

def generate_svr_prediction(category_name, station_name, start_date, end_date, forecast_months=12):
    series = _prepare_ml_series(category_name, station_name, start_date, end_date)
    feat_df = _make_lag_features(series)
    feature_cols = sorted([c for c in feat_df.columns if c != "value"])

    X_raw = feat_df[feature_cols].values
    y = feat_df["value"].values

    scaler_X = StandardScaler()
    scaler_y = StandardScaler()
    X = scaler_X.fit_transform(X_raw)
    y_scaled = scaler_y.fit_transform(y.reshape(-1, 1)).ravel()

    model = SVR(kernel="rbf", C=100, gamma="scale", epsilon=0.01)
    model.fit(X, y_scaled)

    fitted_scaled = model.predict(X)
    fitted_vals = scaler_y.inverse_transform(fitted_scaled.reshape(-1, 1)).ravel()
    residuals = y - fitted_vals
    rmse = float(np.sqrt(np.mean(residuals ** 2)))

    # Wrap model + scalers so _iterative_forecast works on original scale
    class _ScaledSVR:
        def predict(self_inner, X_new):
            X_sc = scaler_X.transform(X_new)
            y_sc = model.predict(X_sc)
            return scaler_y.inverse_transform(y_sc.reshape(-1, 1)).ravel()

    forecast_vals, future_dates = _iterative_forecast(_ScaledSVR(), series, forecast_months)
    forecast_vals = [max(v, 0) for v in forecast_vals]

    ci_offsets = _residual_ci(residuals, forecast_months)
    ci_upper = [max(v + o, 0) for v, o in zip(forecast_vals, ci_offsets)]
    ci_lower = [max(v - o, 0) for v, o in zip(forecast_vals, ci_offsets)]

    fitted_series = pd.Series(fitted_vals, index=feat_df.index)

    fig = _make_forecast_chart(
        series, list(fitted_series), forecast_vals, future_dates,
        ci_upper, ci_lower,
        "SVR Forecast", station_name, category_name, accent_color="#c0392b"
    )

    model_info = {
        "station": station_display(station_name),
        "category": category_name,
        "historical_months": int(len(series)),
        "model_type": "Support Vector Regression (RBF kernel, C=100)",
        "forecast_months": int(forecast_months),
        "rmse": round(rmse, 4),
        "last_historical": series.index[-1].strftime("%Y-%m"),
        "forecast_end": future_dates[-1].strftime("%Y-%m"),
    }
    return {"chart": json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder), "model_info": model_info}
