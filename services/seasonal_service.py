from __future__ import annotations

import json
from typing import Optional

import numpy as np
import pandas as pd
import plotly
import plotly.graph_objs as go
from plotly.subplots import make_subplots
from statsmodels.tsa.seasonal import STL

from data_loader import DataRepository, SeriesRequest

# Injected by app.py at startup
repo: Optional[DataRepository] = None

CATEGORY_TO_FEATURE = {
    "Water Level":            "Water_Level",
    "Discharge":              "Discharge",
    "Total Suspended Solids": "Total_Suspended_Solids",
    "Rainfall":               "Rainfall",
}

FEATURE_UNITS = {
    "Water Level": "m",
    "Discharge":   "m³/s",
    "Total Suspended Solids": "mg/l",
    "Rainfall":    "mm",
}


def _load_series(station: str, category: str, start_date: str, end_date: str) -> pd.Series:
    feature = CATEGORY_TO_FEATURE.get(category)
    if not feature:
        raise ValueError(f"Unknown category: {category}")
    if repo is None:
        raise RuntimeError("seasonal_service.repo not initialised — check app.py startup")

    sk = station.replace(" ", "_")
    request = SeriesRequest(
        station=sk, feature=feature,
        start_date=start_date, end_date=end_date,
    )
    df = repo.get_feature_series(request)
    df = df.set_index("Timestamp").sort_index()
    return df["Value"].dropna()


def generate_stl_decomposition(
    station: str,
    category: str,
    start_date: str,
    end_date: str,
    period: int = 12,
) -> dict:
    """
    Run STL decomposition on monthly-resampled data.

    Returns
    -------
    dict with keys:
        'chart'   — Plotly figure JSON string
        'summary' — dict of computed statistics
    """
    raw = _load_series(station, category, start_date, end_date)

    # Resample to monthly means to get a regular time series
    series = raw.resample("MS").mean().dropna()

    min_obs = period * 2 + 1
    if len(series) < min_obs:
        raise ValueError(
            f"Not enough monthly observations for STL (period={period}). "
            f"Need at least {min_obs}, got {len(series)}. "
            f"Try a wider date range or a shorter period."
        )

    stl = STL(series, period=period, robust=True)
    result = stl.fit()

    observed = series
    trend    = result.trend
    seasonal = result.seasonal
    residual = result.resid
    dates    = observed.index

    unit    = FEATURE_UNITS.get(category, "")
    y_label = f"{category} ({unit})" if unit else category

    # ── 4-panel figure ─────────────────────────────────────────────────
    fig = make_subplots(
        rows=4, cols=1,
        shared_xaxes=True,
        subplot_titles=("Observed", "Trend", "Seasonal", "Residual"),
        vertical_spacing=0.06,
        row_heights=[0.30, 0.25, 0.25, 0.20],
    )

    # Row 1 — Observed
    fig.add_trace(go.Scatter(
        x=dates, y=observed.values, name="Observed",
        line=dict(color="#2563eb", width=1.4),
        hovertemplate="%{x|%b %Y}<br><b>%{y:.3f}</b> " + unit + "<extra>Observed</extra>",
    ), row=1, col=1)

    # Row 2 — Trend
    fig.add_trace(go.Scatter(
        x=dates, y=trend.values, name="Trend",
        line=dict(color="#d4863a", width=2.2),
        hovertemplate="%{x|%b %Y}<br><b>%{y:.3f}</b> " + unit + "<extra>Trend</extra>",
    ), row=2, col=1)

    # Row 3 — Seasonal
    fig.add_trace(go.Scatter(
        x=dates, y=seasonal.values, name="Seasonal",
        line=dict(color="#16a34a", width=1.6),
        fill="tozeroy", fillcolor="rgba(22,163,74,0.08)",
        hovertemplate="%{x|%b %Y}<br><b>%{y:.3f}</b> " + unit + "<extra>Seasonal</extra>",
    ), row=3, col=1)

    # Row 4 — Residual (bar so positive/negative are visually distinct)
    pos_mask = residual.values >= 0
    fig.add_trace(go.Bar(
        x=dates[pos_mask], y=residual.values[pos_mask], name="Residual (+)",
        marker_color="#16a34a", opacity=0.70,
        hovertemplate="%{x|%b %Y}<br><b>%{y:.3f}</b> " + unit + "<extra>Residual</extra>",
    ), row=4, col=1)
    fig.add_trace(go.Bar(
        x=dates[~pos_mask], y=residual.values[~pos_mask], name="Residual (−)",
        marker_color="#dc2626", opacity=0.70,
        hovertemplate="%{x|%b %Y}<br><b>%{y:.3f}</b> " + unit + "<extra>Residual</extra>",
    ), row=4, col=1)

    # Zero reference on residual panel
    fig.add_shape(
        type="line", x0=dates[0], x1=dates[-1], y0=0, y1=0,
        line=dict(color="rgba(0,0,0,0.3)", width=1, dash="dot"),
        row=4, col=1,
    )

    layout = dict(
        height=700,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", size=12, color="#1a1614"),
        showlegend=False,
        margin=dict(l=70, r=30, t=55, b=40),
        barmode="relative",
        title=dict(
            text=f"STL Seasonal Decomposition — {category} at {station}",
            font=dict(size=13, color="#1a1614"),
            x=0.01,
        ),
    )
    layout["hovermode"] = "x unified"
    fig.update_layout(**layout)

    fig.update_xaxes(showgrid=True, gridcolor="rgba(0,0,0,0.06)", zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor="rgba(0,0,0,0.06)", zeroline=False)

    for row_num in range(1, 5):
        fig.update_yaxes(title_text=y_label, title_font=dict(size=10), row=row_num, col=1)

    chart_json = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

    # ── Summary statistics ──────────────────────────────────────────────
    var_resid    = float(np.var(residual.values))
    var_tr_resid = float(np.var((trend + residual).values))
    var_se_resid = float(np.var((seasonal + residual).values))

    trend_strength    = max(0.0, 1.0 - var_resid / var_tr_resid) if var_tr_resid > 0 else 0.0
    seasonal_strength = max(0.0, 1.0 - var_resid / var_se_resid) if var_se_resid > 0 else 0.0

    # Average seasonal cycle by calendar month
    s_df      = pd.Series(seasonal.values, index=seasonal.index)
    month_avg = s_df.groupby(s_df.index.month).mean()
    peak_m    = int(month_avg.idxmax())
    trough_m  = int(month_avg.idxmin())
    MONTH_ABR = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

    seasonal_amplitude = round(float(month_avg.max() - month_avg.min()), 4)

    # Long-term trend direction
    valid_trend = trend.values[~np.isnan(trend.values)]
    if len(valid_trend) >= 2:
        slope = np.polyfit(np.arange(len(valid_trend)), valid_trend, 1)[0]
        rel   = abs(slope) / (np.mean(np.abs(valid_trend)) + 1e-10)
        if rel < 5e-4:
            trend_dir = "Stable"
        elif slope > 0:
            trend_dir = "Increasing"
        else:
            trend_dir = "Decreasing"
    else:
        trend_dir = "Indeterminate"

    # Residual anomalies (|residual| > 2σ)
    r_std         = float(np.std(residual.values))
    r_mean        = float(np.mean(residual.values))
    anomaly_count = int(np.sum(np.abs(residual.values - r_mean) > 2 * r_std))

    summary = {
        "station":            station,
        "category":           category,
        "start_date":         str(observed.index.min().date()),
        "end_date":           str(observed.index.max().date()),
        "n_obs":              int(len(observed)),
        "period":             period,
        "trend_strength":     round(trend_strength,    3),
        "seasonal_strength":  round(seasonal_strength, 3),
        "peak_month":         MONTH_ABR[peak_m   - 1],
        "trough_month":       MONTH_ABR[trough_m - 1],
        "trend_direction":    trend_dir,
        "anomaly_count":      anomaly_count,
        "seasonal_amplitude": seasonal_amplitude,
        "unit":               unit,
    }

    return {"chart": chart_json, "summary": summary}
