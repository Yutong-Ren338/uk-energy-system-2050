from typing import Literal

import pandas as pd

from src import DATA_DIR
from src.data.era5 import get_2021_data, get_2024_data
from src.data.ninja_2025_capacity_factors import (
    WindType as NinjaWindType,
    get_ninja_2025_capacity_factors as _get_ninja_2025_capacity_factors,
    list_available_wind_regions as _list_available_wind_regions,
)
from src.units import Units as U

CapacityFactorSource = Literal["renewable_ninja", "era5_2021", "era5_2024", "ninja_2025"]
WindType = NinjaWindType


def get_renewable_capacity_factors(source: CapacityFactorSource = "renewable_ninja", country: str = "UK", resample: str | None = "D") -> pd.DataFrame:
    """Get renewable capacity factors for solar, onshore wind, and offshore wind.

    Args:
        source: Source of the capacity factors. Options are "renewable_ninja", "era5_2021", "era5_2024", or "ninja_2025".
        country: Country for which to get the data. Renewable Ninja data is only available for the UK.
        resample: Resampling rule for the time series data (e.g., 'D' for daily, 'ME' for monthly). If None, no resampling is done.

    Returns:
        DataFrame with datetime index and columns "solar", "onshore", and "offshore".

    Raises:
        ValueError: if source is not one of the expected values.
    """
    if source == "renewable_ninja":
        if country != "UK":
            raise ValueError("Renewable Ninja data is only available for the UK.")
        return get_renewable_ninja(resample=resample)
    if source == "era5_2021":
        pv_df = get_2021_data(generation_type="solar", country=country, resample=resample)
        pv_df = pv_df.rename(columns={"capacity_factor": "solar"})
        onshore = get_2021_data(generation_type="onshore_wind", country=country, resample=resample)
        onshore = onshore.rename(columns={"capacity_factor": "onshore"})
        offshore = get_2021_data(generation_type="offshore_wind", country=country, resample=resample)
        offshore = offshore.rename(columns={"capacity_factor": "offshore"})
        df = pv_df.join(onshore).join(offshore)
        return df.astype(f"pint[{U.dimensionless}]")
    if source == "era5_2024":
        pv_df = get_2024_data(generation_type="solar", country=country, resample=resample)
        pv_df = pv_df.rename(columns={"capacity_factor": "solar"})
        onshore = get_2024_data(generation_type="onshore_wind", country=country, resample=resample)
        onshore = onshore.rename(columns={"capacity_factor": "onshore"})
        offshore = get_2024_data(generation_type="offshore_wind", country=country, resample=resample)
        offshore = offshore.rename(columns={"capacity_factor": "offshore"})
        df = pv_df.join(onshore).join(offshore)
        return df.astype(f"pint[{U.dimensionless}]")
    if source == "ninja_2025":
        if country != "UK":
            raise ValueError("Renewables.ninja 2025 data is only available for the UK.")
        return get_ninja_2025_capacity_factors(resample=resample)
    raise ValueError(f"Unknown source: {source}")


def get_renewable_ninja(resample: str | None = None) -> pd.DataFrame:
    """Load and return the renewable capacity factors for the UK.

    Args:
        resample: Resampling rule for the time series data (e.g., 'D' for daily, 'M' for monthly).

    Returns:
        DataFrame containing the capacity factors for PV and wind.
    """
    pv_fname = DATA_DIR / "ninja_pv_country_GB_merra-2_corrected.csv"
    wind_fname = DATA_DIR / "ninja_wind_country_GB_current-merra-2_corrected.csv"

    # load data
    pv_df = pd.read_csv(pv_fname, index_col=0, parse_dates=True, skiprows=2)
    pv_df = pv_df.rename(columns={"national": "solar"})
    pv_df.index.name = "date"
    wind_df = pd.read_csv(wind_fname, index_col=0, parse_dates=True, skiprows=2)
    wind_df = wind_df.rename(columns={"national": "wind"})
    wind_df.index.name = "date"

    # combine columns
    capacity_factors_df = pv_df.join(wind_df)

    # resample time series
    if resample is not None:
        capacity_factors_df = capacity_factors_df.resample(resample).mean()

    # convert to pint quantities
    return capacity_factors_df.astype(f"pint[{U.dimensionless}]")


def get_ninja_2025_capacity_factors(
    resample: str | None = "D",
    *,
    onshore_region_code: str = "NATIONAL",
    offshore_region_code: str = "NATIONAL",
) -> pd.DataFrame:
    """Return future renewable capacity factors with regional wind selection.

    Args:
        resample: Resampling rule such as ``\"D\"`` for daily (default) or ``None`` for
            raw hourly traces.
        onshore_region_code: Renewables.ninja region code to use for onshore wind
            (e.g. ``\"UKG1\"``).
        offshore_region_code: Region code for offshore wind.

    Returns:
        Pint-aware DataFrame with ``solar``, ``onshore``, ``offshore`` columns.
    """
    return _get_ninja_2025_capacity_factors(
        resample=resample,
        onshore_region_code=onshore_region_code,
        offshore_region_code=offshore_region_code,
    )


def list_ninja_2025_wind_regions(wind_type: WindType) -> list[str]:
    """List region codes available for the specified wind dataset."""
    return _list_available_wind_regions(wind_type)


