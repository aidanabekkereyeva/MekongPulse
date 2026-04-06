from __future__ import annotations

import json
import re
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

# Maps display category name (used by frontend) â†’ schema feature key
CATEGORY_TO_FEATURE = {
    "Water Level": "Water_Level",
    "Discharge": "Discharge",
    "Total Suspended Solids": "Total_Suspended_Solids",
    "Rainfall": "Rainfall",
}

FEATURE_DISPLAY_UNITS = {
    "Water Level": "Water Level (m)",
    "Discharge": "Discharge (mÂ³/s)",
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
        def _to_iso(value: str) -> str:
            text = str(value or "").strip()
            if re.match(r"^\d{4}-\d{2}-\d{2}$", text):
                return pd.to_datetime(text).strftime('%Y-%m-%d')
            return pd.to_datetime(text, dayfirst=True).strftime('%Y-%m-%d')
        start_iso = _to_iso(start_date)
        end_iso = _to_iso(end_date)
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
    chart_title = f"Flow Duration Curve â€” {category_name} at {station_name}"
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
    chart_title = f"Monthly Distribution â€” {category_name} at {station_name}"
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
    chart_title = f"{category_name} â€” Multi-Station Temporal Heatmap"
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
    start_date = max(
        pd.to_datetime(data_a["start_date"], dayfirst=True),
        pd.to_datetime(data_b["start_date"], dayfirst=True),
    ).strftime("%d-%m-%Y")
    end_date = min(
        pd.to_datetime(data_a["end_date"], dayfirst=True),
        pd.to_datetime(data_b["end_date"], dayfirst=True),
    ).strftime("%d-%m-%Y")
    result = generate_correlation_explorer(
        station_name=station_name,
        category_a=data_a["category_name"],
        category_b=data_b["category_name"],
        start_date=start_date,
        end_date=end_date,
    )
    charts = result.get("charts", {})
    return charts.get("scatter") or create_no_data_chart(
        f"Correlation: {data_a['category_name']} vs {data_b['category_name']} at {station_name}"
    )


def generate_correlation_scatter_visualizations(selected_data):
    charts = []
    grouped = {}
    for data in selected_data:
        grouped.setdefault(data["station_name"], []).append(data)
    for station_name, categories_data in grouped.items():
        charts.append(plot_correlation_scatter(station_name, categories_data))
    return charts


def _get_feature_frequency(category_name: str) -> str:
    if repo is None:
        return "daily"
    feature_key = CATEGORY_TO_FEATURE.get(category_name)
    if not feature_key:
        return "daily"
    return str(repo.feature_frequency.get(feature_key, "daily")).lower()


def _corr_strength_label(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "Unavailable"
    abs_val = abs(float(value))
    if abs_val >= 0.85:
        return "Very strong"
    if abs_val >= 0.65:
        return "Strong"
    if abs_val >= 0.4:
        return "Moderate"
    if abs_val >= 0.2:
        return "Weak"
    return "Very weak"


def _corr_direction_label(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "undetermined"
    if value > 0.05:
        return "positive"
    if value < -0.05:
        return "negative"
    return "near-zero"


def _format_corr_value(value: float | None, digits: int = 3) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):.{digits}f}"


def _format_lag_label(lag: int, frequency: str) -> str:
    unit = "months" if frequency == "monthly" else "days"
    if lag == 0:
        return f"0 {unit}"
    return f"{lag:+d} {unit}"


def _format_frequency_label(frequency: str) -> str:
    return "Monthly aligned series" if frequency == "monthly" else "Daily aligned series"


def _prepare_correlation_dataset(
    station_name: str,
    category_a: str,
    category_b: str,
    start_date: str,
    end_date: str,
) -> dict:
    chart_title = f"Correlation Explorer - {category_a} vs {category_b} at {station_name}"
    df_a = get_feature_series_df(category_a, station_name, start_date, end_date)
    df_b = get_feature_series_df(category_b, station_name, start_date, end_date)

    if df_a is None or df_b is None or df_a.empty or df_b.empty:
        raise ValueError("Selected categories do not have enough data for the chosen station and date range.")

    freq_a = _get_feature_frequency(category_a)
    freq_b = _get_feature_frequency(category_b)
    align_frequency = "monthly" if "monthly" in (freq_a, freq_b) else "daily"

    ser_a = df_a.set_index("Timestamp")["Value"].sort_index()
    ser_b = df_b.set_index("Timestamp")["Value"].sort_index()

    if align_frequency == "monthly":
        ser_a = ser_a.resample("MS").mean()
        ser_b = ser_b.resample("MS").mean()
    else:
        ser_a = ser_a.resample("D").mean()
        ser_b = ser_b.resample("D").mean()

    merged = pd.concat([ser_a.rename(category_a), ser_b.rename(category_b)], axis=1).dropna()
    if len(merged) < 8:
        raise ValueError(
            f"Only {len(merged)} overlapping observations are available after alignment. "
            "Choose a wider date range or another variable pair."
        )

    merged["Month"] = merged.index.month
    merged["DateLabel"] = merged.index.strftime("%Y-%m-%d")
    return {
        "title": chart_title,
        "aligned": merged,
        "align_frequency": align_frequency,
        "freq_label": _format_frequency_label(align_frequency),
    }


def _compute_lag_correlation(aligned: pd.DataFrame, x_col: str, y_col: str, align_frequency: str) -> tuple[pd.DataFrame, dict]:
    max_lag = 12 if align_frequency == "monthly" else 30
    min_pairs = 6 if align_frequency == "monthly" else 10
    lag_rows = []

    for lag in range(-max_lag, max_lag + 1):
        compare = pd.concat(
            [
                aligned[x_col].rename("x"),
                aligned[y_col].shift(-lag).rename("y"),
            ],
            axis=1,
        ).dropna()
        corr = compare["x"].corr(compare["y"]) if len(compare) >= min_pairs else np.nan
        lag_rows.append({
            "lag": lag,
            "correlation": corr,
            "pair_count": int(len(compare)),
        })

    lag_df = pd.DataFrame(lag_rows)
    valid_lags = lag_df.dropna(subset=["correlation"])
    if valid_lags.empty:
        return lag_df, {
            "best_lag": 0,
            "best_corr": np.nan,
            "pair_count": 0,
            "lead_label": "Lag analysis unavailable",
        }

    best_row = valid_lags.iloc[valid_lags["correlation"].abs().argmax()]
    best_lag = int(best_row["lag"])
    if best_lag > 0:
        lead_label = f"{x_col} leads {y_col} by {abs(best_lag)} {'months' if align_frequency == 'monthly' else 'days'}"
    elif best_lag < 0:
        lead_label = f"{y_col} leads {x_col} by {abs(best_lag)} {'months' if align_frequency == 'monthly' else 'days'}"
    else:
        lead_label = "The strongest relationship is synchronous"

    return lag_df, {
        "best_lag": best_lag,
        "best_corr": float(best_row["correlation"]),
        "pair_count": int(best_row["pair_count"]),
        "lead_label": lead_label,
    }


def _build_correlation_charts(
    station_name: str,
    category_a: str,
    category_b: str,
    aligned: pd.DataFrame,
    align_frequency: str,
    lag_df: pd.DataFrame,
    stats: dict,
) -> dict:
    x_vals = aligned[category_a].astype(float)
    y_vals = aligned[category_b].astype(float)
    date_values = aligned.index
    month_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    slope = intercept = r_squared = np.nan
    if x_vals.nunique() > 1 and len(aligned) >= 3:
        slope, intercept = np.polyfit(x_vals.values, y_vals.values, 1)
        predicted = slope * x_vals.values + intercept
        ss_res = float(np.sum((y_vals.values - predicted) ** 2))
        ss_tot = float(np.sum((y_vals.values - y_vals.mean()) ** 2))
        r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else np.nan
    else:
        predicted = np.repeat(y_vals.mean(), len(y_vals))

    scatter_fig = go.Figure()
    scatter_fig.add_trace(go.Scatter(
        x=x_vals,
        y=y_vals,
        mode="markers",
        name="Aligned observations",
        marker=dict(
            size=8,
            color=np.arange(len(aligned)),
            colorscale="Turbo",
            showscale=True,
            colorbar=dict(title="Time order"),
            opacity=0.72,
            line=dict(color="rgba(255,255,255,0.55)", width=0.5),
        ),
        customdata=np.column_stack([date_values.strftime("%Y-%m-%d")]),
        hovertemplate=(
            f"Date: %{{customdata[0]}}<br>{category_a}: %{{x:.3f}}<br>{category_b}: %{{y:.3f}}<extra></extra>"
        ),
    ))
    scatter_fig.add_trace(go.Scatter(
        x=x_vals,
        y=predicted,
        mode="lines",
        name="Linear fit",
        line=dict(color="#c2410c", width=2.5, dash="dash"),
        hovertemplate="Trend line<extra></extra>",
    ))
    apply_clean_layout(
        scatter_fig,
        title=f"Correlation Structure - {category_a} vs {category_b}",
        yaxis_title=get_category_units(category_b),
        xaxis_title=get_category_units(category_a),
    )
    scatter_fig.update_layout(
        hovermode="closest",
        annotations=[
            dict(
                x=0.01,
                y=0.99,
                xref="paper",
                yref="paper",
                showarrow=False,
                align="left",
                bgcolor="rgba(255,255,255,0.84)",
                bordercolor="rgba(0,0,0,0.08)",
                borderwidth=1,
                text=(
                    f"Pearson r = {_format_corr_value(stats['pearson'])}<br>"
                    f"Spearman rho = {_format_corr_value(stats['spearman'])}<br>"
                    f"RÂ² = {_format_corr_value(r_squared)}"
                ),
            )
        ],
    )

    timeline_fig = make_subplots(specs=[[{"secondary_y": True}]])
    timeline_fig.add_trace(go.Scatter(
        x=date_values,
        y=x_vals,
        mode="lines",
        name=category_a,
        line=dict(color="#2563eb", width=2.1),
        hovertemplate=f"%{{x|%Y-%m-%d}}<br>{category_a}: %{{y:.3f}}<extra></extra>",
    ), secondary_y=False)
    timeline_fig.add_trace(go.Scatter(
        x=date_values,
        y=y_vals,
        mode="lines",
        name=category_b,
        line=dict(color="#d97706", width=2.1),
        hovertemplate=f"%{{x|%Y-%m-%d}}<br>{category_b}: %{{y:.3f}}<extra></extra>",
    ), secondary_y=True)
    apply_clean_layout(
        timeline_fig,
        title=f"Aligned Time Series Comparison - {station_name}",
        yaxis_title=get_category_units(category_a),
        xaxis_title="Date",
    )
    timeline_fig.update_layout(hovermode="x unified")
    timeline_fig.update_yaxes(title_text=get_category_units(category_b), secondary_y=True)

    monthly_profile = (
        aligned.groupby("Month")[[category_a, category_b]]
        .mean()
        .reindex(range(1, 13))
    )
    seasonal_fig = make_subplots(specs=[[{"secondary_y": True}]])
    seasonal_fig.add_trace(go.Bar(
        x=month_labels,
        y=monthly_profile[category_a],
        name=f"{category_a} monthly mean",
        marker_color="rgba(37,99,235,0.72)",
        hovertemplate=f"Month: %{{x}}<br>{category_a}: %{{y:.3f}}<extra></extra>",
    ), secondary_y=False)
    seasonal_fig.add_trace(go.Scatter(
        x=month_labels,
        y=monthly_profile[category_b],
        name=f"{category_b} monthly mean",
        mode="lines+markers",
        line=dict(color="#d97706", width=2.4),
        marker=dict(size=7),
        hovertemplate=f"Month: %{{x}}<br>{category_b}: %{{y:.3f}}<extra></extra>",
    ), secondary_y=True)
    apply_clean_layout(
        seasonal_fig,
        title="Seasonal Co-Movement by Calendar Month",
        yaxis_title=get_category_units(category_a),
        xaxis_title="Month",
    )
    seasonal_fig.update_yaxes(title_text=get_category_units(category_b), secondary_y=True)

    lag_fig = go.Figure()
    lag_fig.add_trace(go.Scatter(
        x=lag_df["lag"],
        y=lag_df["correlation"],
        mode="lines+markers",
        name="Lag correlation",
        line=dict(color="#7c3aed", width=2.2),
        marker=dict(size=7, color=lag_df["correlation"].fillna(0), colorscale="RdBu", cmin=-1, cmax=1),
        customdata=np.column_stack([lag_df["pair_count"]]),
        hovertemplate=(
            "Lag: %{x}<br>"
            "Correlation: %{y:.3f}<br>"
            "Overlapping pairs: %{customdata[0]}<extra></extra>"
        ),
    ))
    best_lag = stats["best_lag"]
    best_corr = stats["best_lag_corr"]
    lag_fig.add_vline(x=best_lag, line_width=1.5, line_dash="dash", line_color="#7c3aed")
    lag_fig.add_hline(y=0, line_width=1, line_dash="dot", line_color="rgba(0,0,0,0.3)")
    lag_fig.add_annotation(
        x=best_lag,
        y=best_corr if not pd.isna(best_corr) else 0,
        text=f"Peak at {_format_lag_label(best_lag, align_frequency)}",
        showarrow=True,
        arrowhead=2,
        ax=0,
        ay=-35,
        bgcolor="rgba(255,255,255,0.85)",
    )
    apply_clean_layout(
        lag_fig,
        title="Lead-Lag Correlation Scan",
        yaxis_title="Pearson correlation",
        xaxis_title="Lag (positive means first variable leads)",
    )
    lag_fig.update_yaxes(range=[-1.05, 1.05])

    rolling_window = 6 if align_frequency == "monthly" else 90
    rolling_fig = go.Figure()
    rolling_corr = aligned[category_a].rolling(rolling_window).corr(aligned[category_b]).dropna()
    if rolling_corr.empty:
        rolling_fig = go.Figure()
        rolling_fig.add_annotation(
            text="Not enough overlapping observations for rolling correlation.",
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            showarrow=False,
            font=dict(size=15, color="#5f7082"),
        )
        rolling_fig.update_xaxes(visible=False)
        rolling_fig.update_yaxes(visible=False)
        apply_clean_layout(rolling_fig, "Rolling Correlation Stability", "", "")
    else:
        rolling_fig.add_trace(go.Scatter(
            x=rolling_corr.index,
            y=rolling_corr.values,
            mode="lines",
            name="Rolling correlation",
            line=dict(color="#0f766e", width=2.3),
            fill="tozeroy",
            fillcolor="rgba(15,118,110,0.12)",
            hovertemplate="%{x|%Y-%m-%d}<br>Rolling r: %{y:.3f}<extra></extra>",
        ))
        rolling_fig.add_hline(y=0, line_width=1, line_dash="dot", line_color="rgba(0,0,0,0.3)")
        apply_clean_layout(
            rolling_fig,
            title=f"Rolling Correlation Stability ({rolling_window} {'months' if align_frequency == 'monthly' else 'days'})",
            yaxis_title="Rolling Pearson r",
            xaxis_title="Date",
        )
        rolling_fig.update_yaxes(range=[-1.05, 1.05])

    return {
        "scatter": fig_to_json(scatter_fig),
        "timeline": fig_to_json(timeline_fig),
        "seasonal": fig_to_json(seasonal_fig),
        "lag": fig_to_json(lag_fig),
        "rolling": fig_to_json(rolling_fig),
    }


def _build_correlation_findings(
    station_name: str,
    category_a: str,
    category_b: str,
    stats: dict,
) -> list[str]:
    findings = []
    findings.append(
        f"{category_a} and {category_b} at {station_name} show a {stats['strength_label'].lower()} "
        f"{stats['direction_label']} relationship overall (Pearson r = {stats['pearson_str']}, "
        f"Spearman rho = {stats['spearman_str']})."
    )
    findings.append(
        f"The explorer is based on {stats['n_obs']} overlapping {stats['freq_label'].lower()} observations "
        f"between {stats['start_date']} and {stats['end_date']}."
    )
    findings.append(
        f"The strongest lead-lag signal occurs at {_format_lag_label(stats['best_lag'], stats['align_frequency'])}, "
        f"where correlation reaches {stats['best_lag_corr_str']}. "
        f"{stats['lead_label']}."
    )
    findings.append(
        f"Rolling correlation ranges from {stats['rolling_min_str']} to {stats['rolling_max_str']}, "
        "which helps show whether the relationship is persistent or shifts across hydrological periods."
    )
    return findings


def generate_correlation_explorer(
    station_name: str,
    category_a: str,
    category_b: str,
    start_date: str,
    end_date: str,
) -> dict:
    prepared = _prepare_correlation_dataset(
        station_name=station_name,
        category_a=category_a,
        category_b=category_b,
        start_date=start_date,
        end_date=end_date,
    )
    aligned = prepared["aligned"]
    align_frequency = prepared["align_frequency"]

    pearson = float(aligned[category_a].corr(aligned[category_b]))
    spearman = float(aligned[category_a].rank().corr(aligned[category_b].rank()))

    lag_df, lag_meta = _compute_lag_correlation(aligned, category_a, category_b, align_frequency)

    rolling_window = 6 if align_frequency == "monthly" else 90
    rolling_corr = aligned[category_a].rolling(rolling_window).corr(aligned[category_b]).dropna()
    rolling_min = float(rolling_corr.min()) if not rolling_corr.empty else np.nan
    rolling_max = float(rolling_corr.max()) if not rolling_corr.empty else np.nan

    seasonal_profile = (
        aligned.groupby("Month")[[category_a, category_b]]
        .mean()
        .reindex(range(1, 13))
        .dropna()
    )
    seasonal_corr = (
        float(seasonal_profile[category_a].corr(seasonal_profile[category_b]))
        if len(seasonal_profile) >= 3 else np.nan
    )

    stats = {
        "station": station_name,
        "category_a": category_a,
        "category_b": category_b,
        "n_obs": int(len(aligned)),
        "start_date": aligned.index.min().strftime("%Y-%m-%d"),
        "end_date": aligned.index.max().strftime("%Y-%m-%d"),
        "align_frequency": align_frequency,
        "freq_label": prepared["freq_label"],
        "pearson": pearson,
        "spearman": spearman,
        "pearson_str": _format_corr_value(pearson),
        "spearman_str": _format_corr_value(spearman),
        "strength_label": _corr_strength_label(pearson),
        "direction_label": _corr_direction_label(pearson),
        "best_lag": lag_meta["best_lag"],
        "best_lag_corr": lag_meta["best_corr"],
        "best_lag_corr_str": _format_corr_value(lag_meta["best_corr"]),
        "lead_label": lag_meta["lead_label"],
        "seasonal_corr": seasonal_corr,
        "seasonal_corr_str": _format_corr_value(seasonal_corr),
        "rolling_min": rolling_min,
        "rolling_max": rolling_max,
        "rolling_min_str": _format_corr_value(rolling_min),
        "rolling_max_str": _format_corr_value(rolling_max),
    }

    charts = _build_correlation_charts(
        station_name=station_name,
        category_a=category_a,
        category_b=category_b,
        aligned=aligned,
        align_frequency=align_frequency,
        lag_df=lag_df,
        stats=stats,
    )

    return {
        "summary": stats,
        "charts": charts,
        "findings": _build_correlation_findings(station_name, category_a, category_b, stats),
    }


# ------------------------------
# CHART 11: Anomaly Detection Chart
# ------------------------------

def plot_anomaly_detection_chart(station_name, category_name, start_date, end_date):
    chart_title = f"Anomaly Detection â€” {category_name} at {station_name}"
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
    chart_title = f"Rolling Average Trend â€” {category_name} at {station_name}"
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
    chart_title = f"Cumulative Departure from Mean â€” {category_name} at {station_name}"
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
    chart_title = f"Monthly Climatology â€” {category_name} at {station_name}"
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
        text=f"Based on {years} years of data â€” error bars show Â±1 std dev",
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
    chart_title = f"Decade-by-Decade Comparison â€” {category_name} at {station_name}"
    df = get_feature_series_df(category_name, station_name, start_date, end_date)
    if df is None or df.empty:
        return create_no_data_chart(chart_title)

    df = df.copy()
    df["Decade"] = (df["Timestamp"].dt.year // 10 * 10).astype(str) + "s"
    decades = sorted(df["Decade"].unique())

    if len(decades) < 2:
        return create_no_data_chart(chart_title, "Not enough data â€” at least two decades required.")

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
    # Override the date tickformat that apply_clean_layout sets â€” x-axis is numeric here
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
# ADVANCED RESEARCH HELPERS
# ------------------------------

def _feature_key_for_category(category_name: str) -> Optional[str]:
    return CATEGORY_TO_FEATURE.get(category_name)


def _default_range_for_station_category(station_name: str, category_name: str):
    if repo is None:
        return None, None
    sk = station_key(station_name)
    feature = _feature_key_for_category(category_name)
    if sk not in repo.station_index or not feature:
        return None, None
    detail = repo.station_index[sk].get("feature_details", {}).get(feature, {})
    return detail.get("start_date"), detail.get("end_date")


def _resolve_station_category_range(station_name: str, category_name: str, start_date=None, end_date=None):
    default_start, default_end = _default_range_for_station_category(station_name, category_name)
    start = start_date or default_start
    end = end_date or default_end
    if not start or not end:
        raise ValueError("No valid date range available for the selected station and category.")
    return (
        pd.to_datetime(start, dayfirst=True).strftime('%Y-%m-%d'),
        pd.to_datetime(end, dayfirst=True).strftime('%Y-%m-%d'),
    )


def _series_from_df(df: pd.DataFrame) -> pd.Series:
    series = df.copy()
    series["Timestamp"] = pd.to_datetime(series["Timestamp"])
    return series.set_index("Timestamp")["Value"].sort_index()


def _quality_label(coverage_pct: float, imputed_pct: float) -> str:
    score = coverage_pct - (imputed_pct * 0.6)
    if score >= 85:
        return "High confidence"
    if score >= 60:
        return "Moderate confidence"
    return "Caution required"


def generate_data_quality_explorer(station_name: str, category_name: str, start_date=None, end_date=None) -> dict:
    if repo is None:
        raise RuntimeError("Repository not initialized.")

    start_iso, end_iso = _resolve_station_category_range(station_name, category_name, start_date, end_date)
    df = get_feature_series_df(category_name, station_name, start_iso, end_iso)
    if df is None or df.empty:
        raise ValueError("No data available for quality analysis.")

    sk = station_key(station_name)
    feature = _feature_key_for_category(category_name)
    detail = repo.station_index[sk]["feature_details"][feature]
    freq = detail.get("frequency", "daily")
    expected_freq = "MS" if freq == "monthly" else "D"

    observed = df.copy()
    observed["Timestamp"] = pd.to_datetime(observed["Timestamp"])
    observed["ObservedPeriod"] = observed["Timestamp"].dt.to_period("M").dt.to_timestamp() if expected_freq == "MS" else observed["Timestamp"].dt.normalize()
    observed["IsImputed"] = observed["Imputed"].astype(str).str.lower().eq("yes")

    expected_idx = pd.date_range(start_iso, end_iso, freq=expected_freq)
    observed_idx = pd.Index(sorted(observed["ObservedPeriod"].unique()))
    availability = pd.Series(expected_idx.isin(observed_idx), index=expected_idx)
    missing_count = int((~availability).sum())

    longest_gap = 0
    current_gap = 0
    for available in availability.tolist():
        if available:
            current_gap = 0
        else:
            current_gap += 1
            longest_gap = max(longest_gap, current_gap)

    monthly = pd.DataFrame({"ExpectedDate": expected_idx})
    monthly["Month"] = monthly["ExpectedDate"].dt.to_period("M").dt.to_timestamp()
    monthly_expected = monthly.groupby("Month").size().rename("expected_count")
    monthly_observed = observed.groupby(observed["ObservedPeriod"].dt.to_period("M").dt.to_timestamp()).size().rename("observed_count")
    monthly_imputed = observed.groupby(observed["ObservedPeriod"].dt.to_period("M").dt.to_timestamp())["IsImputed"].sum().rename("imputed_count")
    monthly_stats = pd.concat([monthly_expected, monthly_observed, monthly_imputed], axis=1).fillna(0).reset_index().rename(columns={"index": "Month"})
    monthly_stats["coverage_pct"] = np.where(
        monthly_stats["expected_count"] > 0,
        monthly_stats["observed_count"] / monthly_stats["expected_count"] * 100,
        0
    )

    coverage_pct = round(float(len(observed_idx) / max(len(expected_idx), 1) * 100), 1)
    imputed_count = int(observed["IsImputed"].sum())
    imputed_pct = round(float(imputed_count / max(len(observed), 1) * 100), 1)
    quality_label = _quality_label(coverage_pct, imputed_pct)

    fig_cov = go.Figure()
    fig_cov.add_trace(go.Bar(
        x=monthly_stats["Month"], y=monthly_stats["coverage_pct"],
        marker=dict(color=np.where(monthly_stats["coverage_pct"] >= 80, "#16a34a", np.where(monthly_stats["coverage_pct"] >= 50, "#f59e0b", "#dc2626"))),
        name="Coverage"
    ))
    fig_cov.add_trace(go.Scatter(
        x=monthly_stats["Month"], y=monthly_stats["imputed_count"],
        mode="lines+markers", yaxis="y2", name="Imputed points",
        line=dict(color="#2563eb", width=2)
    ))
    apply_clean_layout(fig_cov, f"Data Quality Coverage - {station_name} · {category_name}", "Coverage (%)", "Month")
    fig_cov.update_layout(yaxis=dict(range=[0, 105]), yaxis2=dict(title="Imputed points", overlaying="y", side="right", showgrid=False))

    avail_df = pd.DataFrame({"Timestamp": expected_idx, "Available": availability.values.astype(int)})
    avail_df["Status"] = np.where(avail_df["Available"] == 1, "Observed", "Missing")
    fig_av = px.scatter(
        avail_df, x="Timestamp", y="Available", color="Status",
        color_discrete_map={"Observed": "#0ea5e9", "Missing": "#ef4444"},
        title=f"Availability Timeline - {station_name} · {category_name}"
    )
    fig_av.update_traces(marker=dict(size=7, opacity=0.75))
    fig_av.update_yaxes(tickvals=[0, 1], ticktext=["Missing", "Observed"])
    apply_clean_layout(fig_av, f"Availability Timeline - {station_name} · {category_name}", "Availability", "Date")

    findings = [
        f"{category_name} at {station_name} covers {coverage_pct}% of the expected {freq} record in the selected window.",
        f"{imputed_count} observations are flagged as imputed ({imputed_pct}% of usable records).",
        f"The longest continuous gap spans {longest_gap} {'months' if expected_freq == 'MS' else 'days'}, which affects trend and forecast confidence."
    ]

    summary = {
        "station": station_name,
        "category": category_name,
        "coverage_pct": coverage_pct,
        "missing_count": missing_count,
        "imputed_count": imputed_count,
        "imputed_pct": imputed_pct,
        "longest_gap": longest_gap,
        "quality_label": quality_label,
        "frequency": freq,
        "start_date": start_iso,
        "end_date": end_iso,
    }
    return {
        "summary": summary,
        "findings": findings,
        "charts": {
            "coverage": fig_to_json(fig_cov),
            "availability": fig_to_json(fig_av),
        }
    }


def generate_station_linkage_explorer(station_a: str, station_b: str, category_name: str, start_date=None, end_date=None) -> dict:
    start_a, end_a = _resolve_station_category_range(station_a, category_name, start_date, end_date)
    start_b, end_b = _resolve_station_category_range(station_b, category_name, start_date, end_date)
    overlap_start = max(pd.to_datetime(start_a), pd.to_datetime(start_b))
    overlap_end = min(pd.to_datetime(end_a), pd.to_datetime(end_b))
    if overlap_end <= overlap_start:
        raise ValueError("The selected stations do not overlap for this category.")

    overlap_days = (overlap_end - overlap_start).days
    use_monthly = overlap_days > 720
    df_a = get_feature_series_df(category_name, station_a, overlap_start.strftime('%Y-%m-%d'), overlap_end.strftime('%Y-%m-%d'))
    df_b = get_feature_series_df(category_name, station_b, overlap_start.strftime('%Y-%m-%d'), overlap_end.strftime('%Y-%m-%d'))
    if df_a is None or df_b is None or df_a.empty or df_b.empty:
        raise ValueError("Insufficient data to compare these stations.")

    series_a = _series_from_df(df_a)
    series_b = _series_from_df(df_b)
    if use_monthly:
        series_a = series_a.resample("MS").mean().dropna()
        series_b = series_b.resample("MS").mean().dropna()

    aligned = pd.concat([series_a.rename(station_a), series_b.rename(station_b)], axis=1).dropna()
    if len(aligned) < 8:
        raise ValueError("Not enough aligned observations for station linkage analysis.")

    pearson = float(aligned[station_a].corr(aligned[station_b]))
    max_lag = 12 if use_monthly else 30
    lag_rows = []
    for lag in range(-max_lag, max_lag + 1):
        shifted = aligned[station_b].shift(lag)
        merged = pd.concat([aligned[station_a], shifted.rename("shifted")], axis=1).dropna()
        if len(merged) < 5:
            continue
        lag_rows.append((lag, float(merged[station_a].corr(merged["shifted"]))))
    lag_df = pd.DataFrame(lag_rows, columns=["lag", "corr"])
    best_lag_row = lag_df.iloc[lag_df["corr"].abs().idxmax()]

    norm = aligned.copy()
    norm[station_a] = normalize_series(norm[station_a])
    norm[station_b] = normalize_series(norm[station_b])
    fig_time = go.Figure()
    fig_time.add_trace(go.Scatter(x=norm.index, y=norm[station_a], mode="lines", name=station_a, line=dict(color="#2563eb", width=2)))
    fig_time.add_trace(go.Scatter(x=norm.index, y=norm[station_b], mode="lines", name=station_b, line=dict(color="#f59e0b", width=2)))
    apply_clean_layout(fig_time, f"Station Linkage Timeline - {category_name}", "Normalized value", "Date")

    fig_scatter = px.scatter(aligned.reset_index(), x=station_a, y=station_b, trendline="ols",
                             title=f"Station Linkage Scatter - {category_name}")
    apply_clean_layout(fig_scatter, f"Station Linkage Scatter - {category_name}", station_b, station_a)

    fig_lag = go.Figure()
    fig_lag.add_trace(go.Bar(x=lag_df["lag"], y=lag_df["corr"], marker_color=np.where(lag_df["corr"] >= 0, "#16a34a", "#dc2626")))
    apply_clean_layout(fig_lag, f"Lag Correlation Scan - {category_name}", "Correlation", "Lag")

    findings = [
        f"{station_a} and {station_b} have a Pearson correlation of {pearson:.3f} for {category_name}.",
        f"The strongest station-to-station linkage appears at lag {int(best_lag_row['lag'])} with correlation {best_lag_row['corr']:.3f}.",
        f"{'Monthly' if use_monthly else 'Daily'} alignment was used to emphasise comparable basin-scale timing."
    ]
    return {
        "summary": {
            "station_a": station_a,
            "station_b": station_b,
            "category": category_name,
            "pearson": round(pearson, 3),
            "best_lag": int(best_lag_row["lag"]),
            "best_lag_corr": round(float(best_lag_row["corr"]), 3),
            "alignment": "monthly" if use_monthly else "daily",
            "n_obs": int(len(aligned)),
        },
        "findings": findings,
        "charts": {
            "timeline": fig_to_json(fig_time),
            "scatter": fig_to_json(fig_scatter),
            "lag": fig_to_json(fig_lag),
        }
    }


def generate_extreme_event_explorer(station_name: str, category_name: str, start_date: str, end_date: str,
                                    threshold_mode: str = "percentile", threshold_value: float = 90,
                                    direction: str = "above") -> dict:
    df = get_feature_series_df(category_name, station_name, start_date, end_date)
    if df is None or df.empty:
        raise ValueError("No data available for extreme event analysis.")
    df = df.copy()
    df["Timestamp"] = pd.to_datetime(df["Timestamp"])
    values = df["Value"].astype(float)

    if threshold_mode == "absolute":
        threshold = float(threshold_value)
    else:
        threshold = float(np.nanpercentile(values, float(threshold_value)))

    if direction == "below":
        flag = values <= threshold
        label = "Low-extreme"
    else:
        flag = values >= threshold
        label = "High-extreme"

    df["Extreme"] = flag
    df["Year"] = df["Timestamp"].dt.year
    df["Month"] = df["Timestamp"].dt.month_name().str.slice(0, 3)
    exceedance_count = int(flag.sum())

    event_id = (flag.ne(flag.shift()) & flag).cumsum()
    event_durations = df.loc[flag].groupby(event_id).size().reset_index(name="duration")
    longest_event = int(event_durations["duration"].max()) if not event_durations.empty else 0

    annual_counts = df.groupby("Year")["Extreme"].sum().reset_index(name="count")
    month_counts = df.groupby("Month")["Extreme"].sum().reindex(["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]).fillna(0).reset_index()

    fig_time = go.Figure()
    fig_time.add_trace(go.Scatter(x=df["Timestamp"], y=df["Value"], mode="lines", name=category_name, line=dict(color="#2563eb", width=1.8)))
    fig_time.add_trace(go.Scatter(x=df.loc[flag, "Timestamp"], y=df.loc[flag, "Value"], mode="markers", name=label,
                                  marker=dict(color="#dc2626" if direction == "above" else "#0f766e", size=8)))
    fig_time.add_hline(y=threshold, line_dash="dash", line_color="#f59e0b", annotation_text=f"Threshold {threshold:.2f}")
    apply_clean_layout(fig_time, f"Extreme Event Timeline - {station_name} · {category_name}", get_category_units(category_name), "Date")

    fig_annual = px.bar(annual_counts, x="Year", y="count", title=f"Annual Extreme Event Counts - {station_name}")
    apply_clean_layout(fig_annual, f"Annual Extreme Event Counts - {station_name}", "Extreme observations", "Year")

    fig_month = px.bar(month_counts, x="Month", y="Extreme", title=f"Seasonality of Extremes - {station_name}")
    fig_month.update_traces(marker_color="#8b5cf6")
    apply_clean_layout(fig_month, f"Seasonality of Extremes - {station_name}", "Extreme observations", "Month")

    findings = [
        f"The {label.lower()} threshold is {threshold:.2f} based on {'an absolute value' if threshold_mode == 'absolute' else f'the {threshold_value}th percentile'}.",
        f"{exceedance_count} observations exceed the selected criterion across the chosen window.",
        f"The longest continuous extreme spell lasts {longest_event} observations."
    ]
    return {
        "summary": {
            "station": station_name,
            "category": category_name,
            "threshold": round(threshold, 4),
            "mode": threshold_mode,
            "direction": direction,
            "count": exceedance_count,
            "longest_event": longest_event,
        },
        "findings": findings,
        "charts": {
            "timeline": fig_to_json(fig_time),
            "annual": fig_to_json(fig_annual),
            "monthly": fig_to_json(fig_month),
        }
    }


def generate_scenario_compare(station_name: str, category_name: str,
                              start_a: str, end_a: str, start_b: str, end_b: str) -> dict:
    df_a = get_feature_series_df(category_name, station_name, start_a, end_a)
    df_b = get_feature_series_df(category_name, station_name, start_b, end_b)
    if df_a is None or df_b is None or df_a.empty or df_b.empty:
        raise ValueError("Both comparison windows need valid data.")

    df_a = df_a.copy(); df_b = df_b.copy()
    df_a["Timestamp"] = pd.to_datetime(df_a["Timestamp"]); df_b["Timestamp"] = pd.to_datetime(df_b["Timestamp"])
    df_a["Window"] = "Window A"; df_b["Window"] = "Window B"
    combo = pd.concat([df_a, df_b], ignore_index=True)

    summary_a = {
        "mean": float(df_a["Value"].mean()), "max": float(df_a["Value"].max()), "min": float(df_a["Value"].min()),
        "std": float(df_a["Value"].std() or 0), "records": int(len(df_a))
    }
    summary_b = {
        "mean": float(df_b["Value"].mean()), "max": float(df_b["Value"].max()), "min": float(df_b["Value"].min()),
        "std": float(df_b["Value"].std() or 0), "records": int(len(df_b))
    }
    mean_change_pct = ((summary_b["mean"] - summary_a["mean"]) / abs(summary_a["mean"]) * 100) if summary_a["mean"] else 0.0

    fig_box = px.box(combo, x="Window", y="Value", color="Window",
                     color_discrete_map={"Window A": "#2563eb", "Window B": "#d4863a"},
                     title=f"Scenario Distribution Compare - {station_name} · {category_name}")
    apply_clean_layout(fig_box, f"Scenario Distribution Compare - {station_name} · {category_name}", get_category_units(category_name), "Window")

    def _monthly_profile(df_local, label):
        s = df_local.set_index("Timestamp")["Value"].resample("MS").mean().dropna()
        m = s.groupby(s.index.month).mean().reindex(range(1, 13))
        return pd.DataFrame({"month": range(1, 13), "value": m.values, "window": label})

    profile = pd.concat([_monthly_profile(df_a, "Window A"), _monthly_profile(df_b, "Window B")], ignore_index=True)
    fig_profile = px.line(profile, x="month", y="value", color="window",
                          color_discrete_map={"Window A": "#2563eb", "Window B": "#d4863a"},
                          title=f"Monthly Regime Compare - {station_name} · {category_name}")
    fig_profile.update_xaxes(tickvals=list(range(1, 13)), ticktext=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"])
    apply_clean_layout(fig_profile, f"Monthly Regime Compare - {station_name} · {category_name}", get_category_units(category_name), "Month")

    findings = [
        f"Mean {category_name} changes by {mean_change_pct:.1f}% between Window A and Window B.",
        f"Window A contains {summary_a['records']} records, while Window B contains {summary_b['records']} records.",
        f"This comparison is useful for pre/post intervention analysis, decadal shifts, or wet-versus-dry period benchmarking."
    ]
    return {
        "summary": {
            "station": station_name,
            "category": category_name,
            "mean_a": round(summary_a["mean"], 3),
            "mean_b": round(summary_b["mean"], 3),
            "mean_change_pct": round(mean_change_pct, 1),
            "records_a": summary_a["records"],
            "records_b": summary_b["records"],
        },
        "findings": findings,
        "charts": {
            "distribution": fig_to_json(fig_box),
            "profile": fig_to_json(fig_profile),
        }
    }


def generate_forecast_diagnostics(category_name: str, station_name: str, start_date: str, end_date: str,
                                  model_key: str = "holt_winters", horizon: int = 12) -> dict:
    series = _prepare_ml_series(category_name, station_name, start_date, end_date)
    holdout = min(max(int(horizon), 6), max(6, min(12, len(series) // 3)))
    if len(series) <= holdout + 12:
        raise ValueError("Not enough historical data for forecast diagnostics. Use a wider range.")

    train = series.iloc[:-holdout]
    test = series.iloc[-holdout:]

    if model_key == "holt_winters":
        use_seasonal = len(train) >= 24
        model = ExponentialSmoothing(train, trend="add", seasonal="add" if use_seasonal else None,
                                     seasonal_periods=12 if use_seasonal else None,
                                     damped_trend=False).fit(optimized=True)
        preds = pd.Series(model.forecast(holdout), index=test.index)
    elif model_key == "sarima":
        fit = SARIMAX(train, order=(1, 1, 1), seasonal_order=(1, 1, 0, 12) if len(train) >= 24 else (0, 0, 0, 0),
                      enforce_stationarity=False, enforce_invertibility=False).fit(disp=False)
        preds = fit.get_forecast(steps=holdout).predicted_mean.reindex(test.index)
    elif model_key in ("random_forest", "gradient_boosting", "svr"):
        feat_df = _make_lag_features(train)
        feature_cols = sorted([c for c in feat_df.columns if c != "value"])
        X = feat_df[feature_cols].values
        y = feat_df["value"].values
        scaler = None
        if model_key == "random_forest":
            model = RandomForestRegressor(n_estimators=120, max_depth=8, min_samples_leaf=2, random_state=42, n_jobs=-1)
            model.fit(X, y)
        elif model_key == "gradient_boosting":
            model = GradientBoostingRegressor(n_estimators=180, max_depth=3, learning_rate=0.05, random_state=42)
            model.fit(X, y)
        else:
            scaler_X = StandardScaler()
            scaler_y = StandardScaler()
            X_sc = scaler_X.fit_transform(X)
            y_sc = scaler_y.fit_transform(y.reshape(-1, 1)).ravel()
            base = SVR(kernel="rbf", C=40, gamma="scale", epsilon=0.03)
            base.fit(X_sc, y_sc)
            class _DiagSVR:
                def predict(self_inner, X_new):
                    return scaler_y.inverse_transform(base.predict(scaler_X.transform(X_new)).reshape(-1, 1)).ravel()
            model = _DiagSVR()
        pred_vals, future_dates = _iterative_forecast(model, train, holdout)
        preds = pd.Series(pred_vals, index=future_dates).reindex(test.index)
    else:
        n = len(train)
        t = np.arange(n)
        def make_X(t_vals, month_vals):
            return np.column_stack([
                t_vals,
                t_vals ** 2,
                np.sin(2 * np.pi * month_vals / 12),
                np.cos(2 * np.pi * month_vals / 12),
                np.sin(4 * np.pi * month_vals / 12),
                np.cos(4 * np.pi * month_vals / 12),
            ])
        model = LinearRegression().fit(make_X(t, train.index.month), train.values)
        t_future = np.arange(n, n + holdout)
        preds = pd.Series(np.maximum(model.predict(make_X(t_future, test.index.month)), 0), index=test.index)

    metrics = _forecast_metrics(test.values, preds.values)
    diagnostics = pd.DataFrame({"actual": test.values, "pred": preds.values, "residual": test.values - preds.values}, index=test.index)
    diagnostics["abs_error"] = diagnostics["residual"].abs()
    monthly_error = diagnostics.groupby(diagnostics.index.month)["abs_error"].mean().reindex(range(1, 13))

    fig_backtest = go.Figure()
    fig_backtest.add_trace(go.Scatter(x=train.index, y=train.values, mode="lines", name="Training", line=dict(color="#94a3b8", width=1.5)))
    fig_backtest.add_trace(go.Scatter(x=test.index, y=test.values, mode="lines+markers", name="Observed holdout", line=dict(color="#2563eb", width=2.2)))
    fig_backtest.add_trace(go.Scatter(x=preds.index, y=preds.values, mode="lines+markers", name="Predicted holdout", line=dict(color="#d4863a", width=2.2)))
    apply_clean_layout(fig_backtest, f"Forecast Backtest - {station_name} · {category_name}", get_category_units(category_name), "Date")

    fig_res = px.bar(diagnostics.reset_index(), x="Timestamp", y="residual", title=f"Forecast Residuals - {station_name}")
    fig_res.update_traces(marker_color=np.where(diagnostics["residual"] >= 0, "#16a34a", "#dc2626"))
    apply_clean_layout(fig_res, f"Forecast Residuals - {station_name}", "Residual", "Date")

    fig_month = px.bar(x=list(range(1, 13)), y=monthly_error.fillna(0).values, title=f"Seasonal Absolute Error - {station_name}")
    fig_month.update_xaxes(tickvals=list(range(1, 13)), ticktext=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"])
    apply_clean_layout(fig_month, f"Seasonal Absolute Error - {station_name}", "Mean absolute error", "Month")

    findings = [
        f"{model_key.replace('_', ' ').title()} was backtested on the last {holdout} monthly observations.",
        f"Backtest RMSE is {metrics['rmse']} and MAPE is {metrics['mape']}%, which helps users judge forecast trust before projecting forward.",
        "The seasonal absolute error chart highlights whether wet-season or dry-season behaviour is harder for the model to capture."
    ]
    return {
        "summary": {
            "station": station_name,
            "category": category_name,
            "model": model_key,
            "holdout_months": holdout,
            "rmse": metrics["rmse"],
            "mape": metrics["mape"],
            "mae": metrics["mae"],
            "bias": metrics["bias"],
        },
        "findings": findings,
        "charts": {
            "backtest": fig_to_json(fig_backtest),
            "residuals": fig_to_json(fig_res),
            "seasonal_error": fig_to_json(fig_month),
        }
    }


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
    positive_only = bool((series > 0).all())

    candidates = [
        {"trend": "add", "seasonal": "add" if use_seasonal else None, "damped_trend": False},
        {"trend": "add", "seasonal": "add" if use_seasonal else None, "damped_trend": True},
    ]
    if use_seasonal and positive_only:
        candidates.append({"trend": "add", "seasonal": "mul", "damped_trend": False})

    fitted = None
    best_cfg = None
    best_aic = None
    for cfg in candidates:
        try:
            model = ExponentialSmoothing(
                series,
                trend=cfg["trend"],
                damped_trend=cfg["damped_trend"],
                seasonal=cfg["seasonal"],
                seasonal_periods=12 if cfg["seasonal"] else None,
                initialization_method="estimated",
            )
            candidate_fit = model.fit(optimized=True, remove_bias=True)
            candidate_aic = float(candidate_fit.aic)
            if best_aic is None or candidate_aic < best_aic:
                fitted = candidate_fit
                best_cfg = cfg
                best_aic = candidate_aic
        except Exception:
            continue

    if fitted is None:
        raise ValueError("Unable to fit a Holt-Winters model for the selected series.")

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
        title=f"Holt-Winters Forecast â€” {station_display(station_name)} Â· {category_name}",
        yaxis_title=unit_label,
        xaxis_title="Date",
    )

    params = fitted.params if isinstance(fitted.params, dict) else dict(fitted.params)
    metrics = _forecast_metrics(series.values, fitted.fittedvalues.values)

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
        "model_type": (
            f"Holt-Winters ({'damped ' if best_cfg.get('damped_trend') else ''}additive trend"
            + (f" + {'multiplicative' if best_cfg.get('seasonal') == 'mul' else 'additive'} seasonal)" if best_cfg.get("seasonal") else ")")
        ),
        "forecast_months": int(forecast_months),
        "alpha": _p("smoothing_level"),
        "beta": _p("smoothing_trend"),
        "gamma": _p("smoothing_seasonal") if best_cfg.get("seasonal") else None,
        "aic": round(float(fitted.aic), 2),
        "rmse": metrics["rmse"],
        "mae": metrics["mae"],
        "mape": metrics["mape"],
        "bias": metrics["bias"],
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
        title=f"{model_label} â€” {station_display(station_name)} Â· {category_name}",
        yaxis_title=unit_label,
        xaxis_title="Date",
    )
    return fig


def _make_lag_features(series: pd.Series, lags=(1, 2, 3, 6, 12)):
    """Build lag, rolling-history, and seasonal features for ML models."""
    df = pd.DataFrame({"value": series})
    for lag in lags:
        df[f"lag_{lag}"] = df["value"].shift(lag)
    df["roll_mean_3"] = df["value"].rolling(3).mean().shift(1)
    df["roll_mean_6"] = df["value"].rolling(6).mean().shift(1)
    df["roll_std_3"] = df["value"].rolling(3).std().shift(1)
    df["roll_std_6"] = df["value"].rolling(6).std().shift(1)
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
        recent3 = history[-3:] if len(history) >= 3 else history
        recent6 = history[-6:] if len(history) >= 6 else history
        row["roll_mean_3"] = float(np.mean(recent3))
        row["roll_mean_6"] = float(np.mean(recent6))
        row["roll_std_3"] = float(np.std(recent3))
        row["roll_std_6"] = float(np.std(recent6))
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


def _forecast_metrics(actual, fitted) -> dict:
    actual_arr = np.asarray(actual, dtype=float)
    fitted_arr = np.asarray(fitted, dtype=float)
    residuals = actual_arr - fitted_arr
    rmse = float(np.sqrt(np.mean(residuals ** 2)))
    mae = float(np.mean(np.abs(residuals)))
    denom = np.maximum(np.abs(actual_arr), max(float(np.nanmean(np.abs(actual_arr))) * 0.01, 1e-6))
    mape = float(np.mean(np.abs(residuals) / denom) * 100)
    bias = float(np.mean(residuals))
    return {
        "rmse": round(rmse, 4),
        "mae": round(mae, 4),
        "mape": round(mape, 2),
        "bias": round(bias, 4),
    }


# ------------------------------
# SARIMA
# ------------------------------

def generate_sarima_prediction(category_name, station_name, start_date, end_date, forecast_months=12):
    series = _prepare_ml_series(category_name, station_name, start_date, end_date)
    use_seasonal = len(series) >= 24

    candidates = [
        ((1, 1, 1), (1, 1, 0, 12) if use_seasonal else (0, 0, 0, 0)),
        ((2, 1, 1), (1, 1, 0, 12) if use_seasonal else (0, 0, 0, 0)),
        ((1, 1, 2), (0, 1, 1, 12) if use_seasonal else (0, 0, 0, 0)),
    ]

    fitted = None
    best_order = None
    best_seasonal_order = None
    best_aic = None
    for order, seasonal_order in candidates:
        try:
            model = SARIMAX(series, order=order, seasonal_order=seasonal_order,
                            enforce_stationarity=False, enforce_invertibility=False)
            candidate_fit = model.fit(disp=False)
            candidate_aic = float(candidate_fit.aic)
            if best_aic is None or candidate_aic < best_aic:
                fitted = candidate_fit
                best_order = order
                best_seasonal_order = seasonal_order
                best_aic = candidate_aic
        except Exception:
            continue

    if fitted is None:
        raise ValueError("Unable to fit a SARIMA model for the selected series.")

    forecast_result = fitted.get_forecast(steps=forecast_months)
    forecast_mean = forecast_result.predicted_mean
    ci = forecast_result.conf_int(alpha=0.05)
    ci_upper = list(ci.iloc[:, 1].clip(lower=0))
    ci_lower = list(ci.iloc[:, 0].clip(lower=0))

    aligned_fitted = fitted.fittedvalues.reindex(series.index).interpolate(method="linear").bfill().ffill()
    metrics = _forecast_metrics(series.values, aligned_fitted.values)

    fig = _make_forecast_chart(
        series, list(fitted.fittedvalues), list(forecast_mean.values),
        forecast_mean.index, ci_upper, ci_lower,
        "SARIMA Forecast", station_name, category_name, accent_color="#8e44ad"
    )

    model_info = {
        "station": station_display(station_name),
        "category": category_name,
        "historical_months": int(len(series)),
        "model_type": f"SARIMA{best_order}x{best_seasonal_order}" + (" (seasonal)" if use_seasonal else ""),
        "forecast_months": int(forecast_months),
        "aic": round(float(fitted.aic), 2),
        "rmse": metrics["rmse"],
        "mae": metrics["mae"],
        "mape": metrics["mape"],
        "bias": metrics["bias"],
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

    model = RandomForestRegressor(n_estimators=160, max_depth=10, min_samples_leaf=2, random_state=42, n_jobs=-1)
    model.fit(X, y)

    fitted_vals = model.predict(X)
    residuals = y - fitted_vals
    metrics = _forecast_metrics(y, fitted_vals)

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
        "model_type": "Random Forest (n=160 trees, max_depth=10, leaf>=2)",
        "forecast_months": int(forecast_months),
        "rmse": metrics["rmse"],
        "mae": metrics["mae"],
        "mape": metrics["mape"],
        "bias": metrics["bias"],
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

    model = GradientBoostingRegressor(n_estimators=240, max_depth=3, learning_rate=0.045, subsample=0.85, random_state=42)
    model.fit(X, y)

    fitted_vals = model.predict(X)
    residuals = y - fitted_vals
    metrics = _forecast_metrics(y, fitted_vals)

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

    importances = dict(zip(feature_cols, model.feature_importances_.round(3)))
    top_features = ", ".join(f"{k}={v}" for k, v in sorted(importances.items(), key=lambda x: -x[1])[:3])

    model_info = {
        "station": station_display(station_name),
        "category": category_name,
        "historical_months": int(len(series)),
        "model_type": "Gradient Boosting (n=240, lr=0.045, depth=3, subsample=0.85)",
        "forecast_months": int(forecast_months),
        "rmse": metrics["rmse"],
        "mae": metrics["mae"],
        "mape": metrics["mape"],
        "bias": metrics["bias"],
        "top_features": top_features,
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
            t_vals ** 2,
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
    metrics = _forecast_metrics(y_train, fitted_vals)
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

    coef_labels = ["Trend", "Trend^2", "sin(2pi/12)", "cos(2pi/12)", "sin(4pi/12)", "cos(4pi/12)"]
    coef_str = ", ".join(f"{l}={round(c,3)}" for l, c in zip(coef_labels, model.coef_))

    model_info = {
        "station": station_display(station_name),
        "category": category_name,
        "historical_months": int(n),
        "model_type": "Linear Regression with Polynomial Trend + Fourier Seasonal Terms",
        "forecast_months": int(forecast_months),
        "rmse": metrics["rmse"],
        "mae": metrics["mae"],
        "mape": metrics["mape"],
        "bias": metrics["bias"],
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

    model = SVR(kernel="rbf", C=60, gamma="scale", epsilon=0.03)
    model.fit(X, y_scaled)

    fitted_scaled = model.predict(X)
    fitted_vals = scaler_y.inverse_transform(fitted_scaled.reshape(-1, 1)).ravel()
    residuals = y - fitted_vals
    metrics = _forecast_metrics(y, fitted_vals)

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
        "model_type": "Support Vector Regression (RBF kernel, C=60, epsilon=0.03)",
        "forecast_months": int(forecast_months),
        "rmse": metrics["rmse"],
        "mae": metrics["mae"],
        "mape": metrics["mape"],
        "bias": metrics["bias"],
        "kernel": "RBF",
        "last_historical": series.index[-1].strftime("%Y-%m"),
        "forecast_end": future_dates[-1].strftime("%Y-%m"),
    }
    return {"chart": json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder), "model_info": model_info}
