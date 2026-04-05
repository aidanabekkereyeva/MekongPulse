from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly
import plotly.graph_objects as go

from data_loader import DataRepository, SeriesRequest

# Injected by app.py at startup (same pattern as visualization.repo)
repo: Optional[DataRepository] = None

DATA_DIR = Path('data/prediction_results')

# Maps display category → schema feature key (used by DataRepository)
_CATEGORY_TO_FEATURE = {
    'Water Level':           'Water_Level',
    'Discharge':             'Discharge',
    'Total Suspended Solids':'Total_Suspended_Solids',
    'Rainfall':              'Rainfall',
}

# Maps display category → folder name inside prediction_results/
_CATEGORY_TO_FOLDER = {
    'Water Level':           'Water_Level',
    'Discharge':             'Water_Discharge',   # note: different from feature key
    'Total Suspended Solids':'Total_Suspended_Solids',
    'Rainfall':              'Rainfall',
}

_UNIT_MAP = {
    'Water Level':           'm',
    'Discharge':             'm³/s',
    'Total Suspended Solids':'mg/l',
    'Rainfall':              'mm',
}

# Five primary comparison models
ML_MODELS: List[str] = ['LSTM', 'GRU', 'PatchTST', 'DLinear', 'iTransformer']

_MODEL_COLORS = {
    'LSTM':         '#34d399',
    'GRU':          '#a78bfa',
    'PatchTST':     '#f59e0b',
    'DLinear':      '#f87171',
    'iTransformer': '#60a5fa',
}
_MODEL_SYMBOLS = {
    'LSTM':         'square',
    'GRU':          'triangle-down',
    'PatchTST':     'diamond',
    'DLinear':      'triangle-up',
    'iTransformer': 'circle',
}


# ── station availability map ─────────────────────────────────────────────────

def build_ml_station_map() -> dict:
    """
    Scan station_predictions_future to find which stations/categories have
    pre-trained ML data. Returns {display_station_name: [display_category, ...]}.
    """
    folder_to_cat = {v: k for k, v in _CATEGORY_TO_FOLDER.items()}  # reverse map
    result: dict = {}
    future_dir = DATA_DIR / 'station_predictions_future'

    for folder, cat in folder_to_cat.items():
        folder_path = future_dir / folder
        if not folder_path.exists():
            continue
        for model in ML_MODELS:
            model_path = folder_path / model
            if not model_path.exists():
                continue
            for csv_file in model_path.glob('*.csv'):
                display_name = csv_file.stem.replace('_', ' ')
                result.setdefault(display_name, set()).add(cat)

    return {name: sorted(cats) for name, cats in sorted(result.items())}


# ── internal helpers ──────────────────────────────────────────────────────────

def _sk(station_name: str) -> str:
    """Display name → underscore station key used in repo and CSV filenames."""
    return station_name.replace(' ', '_')


def _load_actual(category_name: str, station_name: str) -> Optional[pd.DataFrame]:
    """Load the full historical daily series from DataRepository."""
    if repo is None:
        return None
    sk = _sk(station_name)
    feature_key = _CATEGORY_TO_FEATURE.get(category_name)
    if not feature_key:
        return None
    try:
        fd = repo.station_index[sk]['feature_details'][feature_key]
        req = SeriesRequest(
            station=sk, feature=feature_key,
            start_date=fd['start_date'], end_date=fd['end_date'],
        )
        df = repo.get_feature_series(req)
        df['Timestamp'] = pd.to_datetime(df['Timestamp'])
        return df[['Timestamp', 'Value']].dropna().sort_values('Timestamp').reset_index(drop=True)
    except Exception:
        return None


def _future_path(station_name: str, category_name: str, model: str) -> Path:
    return (DATA_DIR / 'station_predictions_future'
            / _CATEGORY_TO_FOLDER[category_name] / model / f'{_sk(station_name)}.csv')


def _hist_path(station_name: str, category_name: str, model: str) -> Path:
    return (DATA_DIR / 'station_predictions'
            / _CATEGORY_TO_FOLDER[category_name] / model / f'{_sk(station_name)}.csv')


def _load_future(station_name: str, category_name: str, model: str,
                 horizon: int) -> Optional[np.ndarray]:
    """Load horizon days of future forecast (1 row CSV, columns horizon_1..horizon_30)."""
    path = _future_path(station_name, category_name, model)
    if not path.exists():
        return None
    try:
        df = pd.read_csv(path, nrows=1)
        return df.iloc[0, :horizon].values.astype(float)
    except Exception:
        return None


def _load_historical_fit(
    station_name: str, category_name: str, model: str,
    horizon: int, actual_df: pd.DataFrame,
) -> Tuple[Optional[pd.DataFrame], float, float]:
    """
    Load rolling predictions and compute RMSE/MAPE.
    Returns (fit_df, rmse, mape).  fit_df has columns [Timestamp, ModelFit].
    """
    path = _hist_path(station_name, category_name, model)
    if not path.exists():
        return None, float('nan'), float('nan')
    try:
        pred_df = pd.read_csv(path)
        n_windows, n_horizons = len(pred_df), len(pred_df.columns)
        actual_h = min(horizon, n_horizons)
        col_idx = actual_h - 1

        last_date = actual_df['Timestamp'].max()
        eval_start = last_date - pd.Timedelta(days=n_windows + n_horizons - 2)
        dates = pd.date_range(
            start=eval_start + pd.Timedelta(days=actual_h - 1),
            periods=n_windows, freq='D',
        )
        values = pred_df.iloc[:, col_idx].values.astype(float)
        fit_df = pd.DataFrame({'Timestamp': dates, 'ModelFit': values})

        actual_indexed = actual_df.set_index('Timestamp')['Value']
        fit_df = fit_df[fit_df['Timestamp'].isin(actual_indexed.index)].reset_index(drop=True)
        if fit_df.empty:
            return None, float('nan'), float('nan')

        actuals = actual_indexed.reindex(fit_df['Timestamp']).values
        preds = fit_df['ModelFit'].values
        residuals = actuals - preds
        rmse = float(np.sqrt(np.nanmean(residuals ** 2)))

        act_mean = float(np.nanmean(np.abs(actuals)))
        threshold = max(act_mean * 0.01, 1e-6)
        valid = np.abs(actuals) > threshold
        mape = (float(np.nanmean(np.abs(residuals[valid] / actuals[valid])) * 100)
                if valid.sum() > 0 else float('nan'))

        return fit_df, rmse, mape
    except Exception:
        return None, float('nan'), float('nan')


def _base_layout(title: str) -> dict:
    return dict(
        title=dict(text=title, x=0.5, xanchor='center', font=dict(size=15, color='#1f2d3d')),
        template='plotly_white',
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(248,250,252,0.6)',
        font=dict(family='Inter, Arial, sans-serif', size=12, color='#334155'),
        margin=dict(l=50, r=28, t=64, b=48),
        hovermode='x unified',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='left', x=0,
                    font=dict(size=11), bgcolor='rgba(0,0,0,0)'),
    )


def _axis_style() -> dict:
    return dict(showgrid=True, gridcolor='rgba(148,163,184,0.18)',
                tickfont=dict(size=11, color='#64748b'))


def _add_divider(fig: go.Figure, last_date: pd.Timestamp) -> None:
    fig.add_shape(type='line', x0=last_date, x1=last_date, y0=0, y1=1, yref='paper',
                  line=dict(color='rgba(245,158,11,0.6)', width=1.5, dash='dot'))
    fig.add_annotation(x=last_date, y=1, yref='paper', text='Forecast start',
                       showarrow=False, font=dict(size=10, color='#f59e0b'),
                       xanchor='left', xshift=5)


# ── public API ────────────────────────────────────────────────────────────────

def generate_ml_prediction(
    category_name: str,
    station_name: str,
    model: str,
    horizon: int = 14,
) -> Dict[str, Any]:
    """
    Single-model forecast using pre-trained CSV predictions.
    Returns {"chart": json_str, "model_info": {...}} — same shape as statistical models.
    """
    actual_df = _load_actual(category_name, station_name)
    if actual_df is None or len(actual_df) < 30:
        raise ValueError(f"Insufficient historical data for {station_name} / {category_name}.")

    horizon = max(1, min(horizon, 30))
    unit = _UNIT_MAP.get(category_name, '')
    color = _MODEL_COLORS.get(model, '#60a5fa')
    symbol = _MODEL_SYMBOLS.get(model, 'circle')

    display_days = 365
    plot_actual = actual_df.iloc[-display_days:] if len(actual_df) > display_days else actual_df
    last_date = actual_df['Timestamp'].max()
    last_value = float(actual_df.loc[actual_df['Timestamp'] == last_date, 'Value'].iloc[0])

    future_vals = _load_future(station_name, category_name, model, horizon)
    fit_df, rmse, mape = _load_historical_fit(station_name, category_name, model, horizon, actual_df)

    if future_vals is None and fit_df is None:
        raise ValueError(
            f"No pre-trained model data found for {station_name} / {category_name} / {model}. "
            f"Only stations with pre-computed prediction CSVs are supported."
        )

    future_dates = pd.date_range(start=last_date + pd.Timedelta(days=1), periods=horizon, freq='D')
    connected_dates = [last_date] + list(future_dates)
    non_negative = float(actual_df['Value'].dropna().min()) >= 0
    if future_vals is not None and non_negative:
        future_vals = np.clip(future_vals, 0, None)

    fig = go.Figure()

    # Actual history (last 365 days)
    fig.add_trace(go.Scatter(
        x=plot_actual['Timestamp'].tolist(), y=plot_actual['Value'].tolist(),
        mode='lines', name='Actual',
        line=dict(color='#38bdf8', width=1.8),
        fill='tozeroy', fillcolor='rgba(56,189,248,0.07)',
        hovertemplate=f'%{{x|%Y-%m-%d}}: %{{y:.3f}} {unit}<extra></extra>',
    ))

    # Historical fit overlay (faint)
    if fit_df is not None and not fit_df.empty:
        fit_display = fit_df[fit_df['Timestamp'] >= plot_actual['Timestamp'].min()]
        if not fit_display.empty:
            fig.add_trace(go.Scatter(
                x=fit_display['Timestamp'].tolist(), y=fit_display['ModelFit'].tolist(),
                mode='lines', name=f'{model} historical fit',
                line=dict(color=color, width=1), opacity=0.4,
                hovertemplate=f'{model} fit %{{x|%Y-%m-%d}}: %{{y:.3f}} {unit}<extra></extra>',
            ))

    # Future forecast connected to last historical value
    if future_vals is not None:
        fig.add_trace(go.Scatter(
            x=connected_dates, y=[last_value] + future_vals.tolist(),
            mode='lines+markers', name=f'{model} Forecast',
            line=dict(color=color, width=2, dash='dash'),
            marker=dict(size=5, color=color, symbol=symbol),
            hovertemplate=f'{model} %{{x|%Y-%m-%d}}: %{{y:.3f}} {unit}<extra></extra>',
        ))

    _add_divider(fig, last_date)

    layout = _base_layout(f'{model} Forecast — {category_name} · {station_name}')
    layout['hovermode'] = 'x unified'
    fig.update_layout(**layout)
    fig.update_xaxes(**_axis_style())
    fig.update_yaxes(**_axis_style(),
                     title=f'{category_name} ({unit})' if unit else category_name)

    rmse_str = f'{rmse:.3f}' if not np.isnan(rmse) else 'n/a'
    mape_str = f'{mape:.1f}%' if (not np.isnan(mape) and mape <= 500) else 'n/a'

    return {
        'chart': json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder),
        'model_info': {
            'model': model,
            'horizon_days': horizon,
            'rmse': rmse_str,
            'mape': mape_str,
            'last_historical': last_date.strftime('%Y-%m-%d'),
            'forecast_end': future_dates[-1].strftime('%Y-%m-%d') if future_vals is not None else 'n/a',
            'source_type': 'trained_model',
        },
    }


def generate_model_comparison(
    category_name: str,
    station_name: str,
    horizon: int = 14,
) -> Dict[str, Any]:
    """
    Multi-model comparison: FlowNet, LSTM, PatchTST, DLinear on one chart.
    Returns {"chart": json_str, "model_info": {"metrics": [...], "best_model": ...}}.
    """
    actual_df = _load_actual(category_name, station_name)
    if actual_df is None or len(actual_df) < 30:
        raise ValueError(f"Insufficient historical data for {station_name} / {category_name}.")

    horizon = max(1, min(horizon, 30))
    unit = _UNIT_MAP.get(category_name, '')

    display_days = 365
    plot_actual = actual_df.iloc[-display_days:] if len(actual_df) > display_days else actual_df
    last_date = actual_df['Timestamp'].max()
    last_value = float(actual_df.loc[actual_df['Timestamp'] == last_date, 'Value'].iloc[0])
    future_dates = pd.date_range(start=last_date + pd.Timedelta(days=1), periods=horizon, freq='D')
    connected_dates = [last_date] + list(future_dates)
    non_negative = float(actual_df['Value'].dropna().min()) >= 0

    fig = go.Figure()

    # Actual (grey reference line)
    fig.add_trace(go.Scatter(
        x=plot_actual['Timestamp'].tolist(), y=plot_actual['Value'].tolist(),
        mode='lines', name='Actual',
        line=dict(color='rgba(148,163,184,0.85)', width=1.5),
        hovertemplate=f'%{{x|%Y-%m-%d}}: %{{y:.3f}} {unit}<extra></extra>',
    ))

    metrics: List[Dict] = []
    any_forecast = False

    for model in ML_MODELS:
        color = _MODEL_COLORS[model]
        symbol = _MODEL_SYMBOLS[model]
        fit_df, rmse, mape = _load_historical_fit(station_name, category_name, model, horizon, actual_df)
        future_vals = _load_future(station_name, category_name, model, horizon)

        if fit_df is None and future_vals is None:
            metrics.append({'Model': model, 'RMSE': 'n/a', 'MAPE': 'n/a'})
            continue

        if future_vals is not None:
            if non_negative:
                future_vals = np.clip(future_vals, 0, None)
            fig.add_trace(go.Scatter(
                x=connected_dates, y=[last_value] + future_vals.tolist(),
                mode='lines+markers', name=model,
                line=dict(color=color, width=1.5),
                marker=dict(size=4, color=color, symbol=symbol),
                hovertemplate=f'{model} %{{x|%Y-%m-%d}}: %{{y:.3f}} {unit}<extra></extra>',
            ))
            any_forecast = True

        rmse_str = f'{rmse:.3f}' if not np.isnan(rmse) else 'n/a'
        mape_str = f'{mape:.1f}%' if (not np.isnan(mape) and mape <= 500) else 'n/a'
        metrics.append({'Model': model, 'RMSE': rmse_str, 'MAPE': mape_str})

    if not any_forecast:
        raise ValueError(
            f"No pre-trained model forecasts found for {station_name} / {category_name}. "
            f"Only stations with pre-computed prediction CSVs are supported."
        )

    _add_divider(fig, last_date)
    layout = _base_layout(f'Multi-Model Forecast Comparison — {category_name} · {station_name}')
    layout['hovermode'] = 'closest'
    fig.update_layout(**layout)
    fig.update_xaxes(**_axis_style())
    fig.update_yaxes(**_axis_style(),
                     title=f'{category_name} ({unit})' if unit else category_name)

    valid_rmse = [(m['Model'], float(m['RMSE'])) for m in metrics if m['RMSE'] != 'n/a']
    best_model = min(valid_rmse, key=lambda x: x[1])[0] if valid_rmse else 'n/a'

    return {
        'chart': json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder),
        'model_info': {
            'metrics': metrics,
            'best_model': best_model,
            'horizon_days': horizon,
            'last_historical': last_date.strftime('%Y-%m-%d'),
            'forecast_end': future_dates[-1].strftime('%Y-%m-%d'),
        },
    }
