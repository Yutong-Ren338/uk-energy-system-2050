"""Capacity factor loaders for the 2025 Renewables.ninja datasets.

This module mirrors the public API of ``renewable_capacity_factors.py`` but
operates on the higher resolution CSV exports stored in ``data/ninja_2025``.
The datasets provide national and NUTS2 regional capacity factors for future
onshore and offshore fleets, enabling region-specific scaling (e.g. ``UKG1``).
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import pandas as pd

from src import DATA_DIR
from src.units import Units as U

from collections.abc import Mapping, Sequence

WindType = Literal["onshore", "offshore"]

_NINJA_2025_DIR = DATA_DIR / "ninja_2025"
_PV_FILE = _NINJA_2025_DIR / "ninja-pv-country-GB-national-merra2.csv"
_WIND_FILES: dict[WindType, Path] = {
    "onshore": _NINJA_2025_DIR / "ninja-wind-country-GB-future_onshore-merra2.csv",
    "offshore": _NINJA_2025_DIR / "ninja-wind-country-GB-future_offshore-merra2.csv",
}
_DEFAULT_REGION = "NATIONAL"


def get_ninja_2025_capacity_factors(
    resample: str | None = "D",
    *,
    onshore_region_code: str | list[str] | dict[str, float] = _DEFAULT_REGION,
    offshore_region_code: str | list[str] | dict[str, float] = _DEFAULT_REGION,
) -> pd.DataFrame:
    """Return solar, onshore, and offshore capacity factors from ninja_2025.

    Args:
        resample: Resampling rule (e.g. ``"D"`` for daily means). ``None`` keeps
            the original hourly data.
        onshore_region_code: Region code to use for the onshore wind series
            (e.g. ``"UKG1"``). Defaults to the national profile.
        offshore_region_code: Region code for the offshore wind series.

    Returns:
        DataFrame with pint quantities, indexed by datetime and containing the
        columns ``["solar", "onshore", "offshore"]``.

    Raises:
        ValueError: If a requested region code is absent from the dataset.
    """
    wind_on_df = _load_wind_dataframe("onshore", resample=resample)
    wind_off_df = _load_wind_dataframe("offshore", resample=resample)
    solar = _load_pv_capacity_factor(resample=resample).rename("solar")
    onshore = _combine_regions(wind_on_df, onshore_region_code).rename("onshore")
    offshore = _combine_regions(wind_off_df, offshore_region_code).rename("offshore")

    df = pd.concat([solar, onshore, offshore], axis=1)
    return df.astype(f"pint[{U.dimensionless}]")


def list_available_wind_regions(wind_type: WindType) -> list[str]:
    """Return the list of available region codes for a wind dataset."""
    df = _load_wind_dataframe(wind_type, resample=None)
    return sorted(df.columns.tolist())


def _combine_regions(
    df: pd.DataFrame, region_code: str | list[str] | dict[str, float]
) -> pd.Series:
    """Combine regions by averaging (list) or weighted average (dict)."""
    if isinstance(region_code, str):
        column_key = (region_code or _DEFAULT_REGION).upper()
        if column_key not in df.columns:
            available = ", ".join(df.columns)
            raise ValueError(
                f"Region '{region_code}' not found. Available regions: {available}"
            )
        return df[column_key]
    elif isinstance(region_code, list):
        columns = [(code or _DEFAULT_REGION).upper() for code in region_code]
        missing = [c for c in columns if c not in df.columns]
        if missing:
            available = ", ".join(df.columns)
            raise ValueError(
                f"Regions {missing} not found. Available regions: {available}"
            )
        return df[columns].mean(axis=1)
    elif isinstance(region_code, dict):
        columns = [(code or _DEFAULT_REGION).upper() for code in region_code.keys()]
        missing = [c for c in columns if c not in df.columns]
        if missing:
            available = ", ".join(df.columns)
            raise ValueError(
                f"Regions {missing} not found. Available regions: {available}"
            )
        weights = list(region_code.values())
        return (df[columns] * weights).sum(axis=1) / sum(weights)
    else:
        raise TypeError(f"Unsupported region_code type: {type(region_code)}")


def _load_pv_capacity_factor(resample: str | None) -> pd.Series:
    df = _load_capacity_factor_csv(_PV_FILE, resample=resample)
    try:
        series = df[_DEFAULT_REGION]
    except KeyError as exc:  # pragma: no cover - indicates missing file columns
        raise ValueError("PV CSV does not contain the NATIONAL column.") from exc
    return series


def _load_wind_capacity_factor(
    wind_type: WindType, region_code: str, resample: str | None
) -> pd.Series:
    df = _load_wind_dataframe(wind_type, resample=resample)
    column_key = (region_code or _DEFAULT_REGION).upper()
    if column_key not in df.columns:
        available = ", ".join(df.columns)
        raise ValueError(
            f"Region '{region_code}' not found for {wind_type} wind. "
            f"Available regions: {available}"
        )
    return df[column_key]


def _load_wind_dataframe(wind_type: WindType, resample: str | None) -> pd.DataFrame:
    file_path = _WIND_FILES[wind_type]
    return _load_capacity_factor_csv(file_path, resample=resample)


def _load_capacity_factor_csv(file_path: Path, resample: str | None) -> pd.DataFrame:
    df = pd.read_csv(
        file_path,
        skiprows=3,
        index_col=0,
        parse_dates=True,
        na_values=[""],
    )
    df.index.name = "date"
    if isinstance(df.index, pd.DatetimeIndex) and df.index.tz is not None:
        # Convert to naive timestamps to match demand data (which has tz info stripped).
        df.index = df.index.tz_convert("UTC").tz_localize(None)
    df = df.dropna(axis=1, how="all").sort_index()

    if resample is not None:
        df = df.resample(resample).mean()
    return df
