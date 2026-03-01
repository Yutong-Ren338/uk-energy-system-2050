"""Plotting helpers for Renewables.ninja 2025 wind data.

Functions load and plot onshore/offshore wind time series for chosen NUTS2
regions from the Renewables.ninja 2025 dataset.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import TypeAlias

import matplotlib.pyplot as plt
import pandas as pd
from pint import Quantity

import src.matplotlib_style  # applies project-wide plotting defaults
from src.data.ninja_2025_capacity_factors import (
    WindType,
    get_ninja_2025_capacity_factors,
    list_available_wind_regions,
)
from src.units import Units as U

RegionSelector: TypeAlias = str | Sequence[str]
TimeLike: TypeAlias = str | pd.Timestamp | None

DEFAULT_REGION = "NATIONAL"
_DEFAULT_CAPACITY_DATASET = Path(
    r"C:\Users\Yutong Ren\AppData\Local\Temp\Rar$DIa72688.31523.rartemp\Dataset_SE.dta"
)


def available_ninja_2025_regions(wind_type: WindType) -> list[str]:
    """Return available NUTS2 region codes for the given wind dataset."""
    return list_available_wind_regions(wind_type)


def load_ninja_2025_wind_series(
    wind_type: WindType,
    region_code: RegionSelector = DEFAULT_REGION,
    *,
    start: TimeLike = None,
    end: TimeLike = None,
    resample: str | None = "D",
    capacity_gw: Quantity | float | int | None = None,
    dataset_path: str | Path | None = None,
    dataset_year: int | None = None,
    include_all_regions: bool = False,
) -> pd.Series | pd.DataFrame:
    """Return pint-aware wind time series for the requested regions and period.

    Args:
        wind_type: Either ``"onshore"`` or ``"offshore"``.
        region_code: Single NUTS2 code or a list of codes to plot separately.
        start: Optional start datetime (inclusive).
        end: Optional end datetime (inclusive).
        resample: Resampling rule such as ``"D"`` for daily averages or ``None``
            for raw hourly values.
        capacity_gw: Installed capacity (GW) to convert capacity factors into power.
            Used when the dataset does not contain a capacity for the region.
        dataset_path: Optional path to ``Dataset_SE.dta`` containing historical
            capacities. If omitted, tries the known local default path.
        dataset_year: Optional year to pick from the dataset. Defaults to the
            latest available year for each region.
        include_all_regions: When True, ignore ``region_code`` and load all
            available UK regions for the selected wind type.

    Returns:
        Series (single region) or DataFrame (multiple regions) indexed by
        datetime containing capacity factor or power (GW).
    """
    if include_all_regions:
        region_list = available_ninja_2025_regions(wind_type)
    else:
        region_list = [region_code] if isinstance(region_code, str) else list(region_code)
    series_map: dict[str, pd.Series] = {}

    for code in region_list:
        cf_df = get_ninja_2025_capacity_factors(
            resample=resample,
            onshore_region_code=code if wind_type == "onshore" else DEFAULT_REGION,
            offshore_region_code=code if wind_type == "offshore" else DEFAULT_REGION,
        )
        region_series = cf_df[wind_type]
        region_series = _slice_period(region_series, start=start, end=end)
        capacity_qty = _lookup_capacity(
            code,
            wind_type=wind_type,
            dataset_path=dataset_path,
            dataset_year=dataset_year,
            fallback_capacity=capacity_gw,
        )
        if capacity_qty is not None:
            region_series = (region_series * capacity_qty).pint.to(U.GW)
        series_map[_region_label(code)] = region_series

    if len(series_map) == 1:
        return next(iter(series_map.values()))

    return pd.DataFrame(series_map)


def plot_ninja_2025_wind_power(
    *,
    wind_type: WindType,
    region_code: RegionSelector = DEFAULT_REGION,
    start: TimeLike = None,
    end: TimeLike = None,
    resample: str | None = "D",
    capacity_gw: Quantity | float | int | None = None,
    ax: plt.Axes | None = None,
    figsize: tuple[float, float] | None = (12, 6),
    dataset_path: str | Path | None = None,
    dataset_year: int | None = None,
    include_all_regions: bool = False,
) -> tuple[plt.Figure, plt.Axes, pd.Series]:
    """Plot wind power or capacity factors for a selected NUTS2 region.

    Args:
        wind_type: Either ``"onshore"`` or ``"offshore"``.
        region_code: Region selector matching the ninja_2025 CSVs.
        start: Optional start datetime (inclusive).
        end: Optional end datetime (inclusive).
        resample: Resampling rule such as ``"D"`` for daily averages or ``None``
            for raw hourly values.
        capacity_gw: Installed capacity to convert capacity factors into power.
            If omitted, capacity factors are plotted instead.
        ax: Optional matplotlib axes to draw on. Creates a new figure if None.
        figsize: Figure size passed to ``plt.subplots`` when ``ax`` is None.
        dataset_path: Optional path to ``Dataset_SE.dta`` for per-region
            capacities. If missing, falls back to user-specified capacity.
        dataset_year: Year to pick from the dataset (latest if None).
        include_all_regions: When True, ignore ``region_code`` and plot all
            available UK regions for the selected wind type.

    Returns:
        A tuple of (figure, axes, plotted_series).
    """
    series = load_ninja_2025_wind_series(
        wind_type=wind_type,
        region_code=region_code,
        start=start,
        end=end,
        resample=resample,
        capacity_gw=capacity_gw,
        dataset_path=dataset_path,
        dataset_year=dataset_year,
        include_all_regions=include_all_regions,
    )

    fig, plot_ax = (
        (ax.figure, ax) if ax is not None else plt.subplots(figsize=figsize)
    )
    ylabel = "Wind power"

    series_to_plot = series if isinstance(series, pd.DataFrame) else series.to_frame()
    for col in series_to_plot.columns:
        col_series = series_to_plot[col]
        if hasattr(col_series, "pint"):
            unit = col_series.pint.units
            y_values = col_series.pint.magnitude
            if unit == U.dimensionless:
                ylabel = "Capacity factor"
                unit_label = ""
            else:
                unit_label = f" [{unit:~P}]"
        else:
            y_values = col_series
            unit_label = ""

        plot_ax.plot(col_series.index, y_values, label=f"{wind_type} {col}")

    plot_ax.set_xlabel("Date")
    plot_ax.set_ylabel(f"{ylabel}{unit_label}")
    plot_ax.set_title("Ninja 2025 wind")
    plot_ax.legend()

    return fig, plot_ax, series


def _lookup_capacity(
    region_code: str,
    *,
    wind_type: WindType,
    dataset_path: str | Path | None,
    dataset_year: int | None,
    fallback_capacity: Quantity | float | int | None,
) -> Quantity | None:
    """Return capacity from dataset if present; otherwise fallback."""
    dataset_capacity = _read_capacity_from_dataset(
        region_code=region_code,
        wind_type=wind_type,
        dataset_path=dataset_path,
        dataset_year=dataset_year,
    )
    if dataset_capacity is not None:
        return dataset_capacity
    if fallback_capacity is None:
        return None
    return _coerce_capacity(fallback_capacity)


def _coerce_capacity(capacity: Quantity | float | int) -> Quantity:
    quantity = capacity if isinstance(capacity, Quantity) else float(capacity) * U.GW
    return quantity.to(U.GW)


def _slice_period(series: pd.Series, *, start: TimeLike, end: TimeLike) -> pd.Series:
    if start is None and end is None:
        return series

    start_ts = pd.to_datetime(start) if start is not None else series.index.min()
    end_ts = pd.to_datetime(end) if end is not None else series.index.max()

    if start_ts > end_ts:
        raise ValueError("start must be earlier than or equal to end")

    return series.loc[start_ts:end_ts]


def _region_label(region_code: RegionSelector) -> str:
    if isinstance(region_code, str):
        return (region_code or DEFAULT_REGION).upper()

    parts = [str(code).upper() for code in region_code]
    return ", ".join(parts)


def _read_capacity_from_dataset(
    *,
    region_code: str,
    wind_type: WindType,  # Included for future differentiation if needed
    dataset_path: str | Path | None,
    dataset_year: int | None,
) -> Quantity | None:
    """Try to read installed capacity from the Stata dataset."""
    path = Path(dataset_path) if dataset_path is not None else _DEFAULT_CAPACITY_DATASET
    if not path.exists():
        return None

    try:
        df = pd.read_stata(path, columns=["NUTS_ID", "year", "wind"])
    except (OSError, ValueError, FileNotFoundError):
        return None

    region_df = df[df["NUTS_ID"].str.upper() == region_code.upper()]
    if region_df.empty:
        return None

    if dataset_year is not None:
        region_df = region_df[region_df["year"] == dataset_year]
        if region_df.empty:
            return None
    else:
        region_df = region_df.sort_values("year")

    value = region_df.iloc[-1]["wind"]
    if pd.isna(value):
        return None

    try:
        capacity_mw = float(value)
    except (TypeError, ValueError):
        return None

    capacity_quantity = (capacity_mw * U.MW).to(U.GW)
    return capacity_quantity
