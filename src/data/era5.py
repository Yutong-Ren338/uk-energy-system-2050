import functools
from pathlib import Path

import pandas as pd
import xarray as xr

DATA_DIR = Path(__file__).parents[2] / "data"

COUNTRY_MAP = {
    "France": "FR",
    "Ireland": "IE",
    "Netherlands": "NL",
    "Germany": "DE",
    "Belgium": "BE",
    "Denmark": "DK",
    "Norway": "NO",
}


@functools.cache
def get_2024_data(generation_type: str = "solar", country: str = "UK", resample: str | None = None) -> pd.DataFrame:
    """ERA5 data from https://doi.org/10.5281/zenodo.12634069.

    Args:
        generation_type: "solar", "onshore_wind", or "offshore_wind"
        country: ISO 3166-1 alpha-2 country code, e.g. "GB", "DE", "FR" (UK is converted to GB)
        resample: resample frequency, e.g. "D" for daily, "ME" for monthly, "YE" for yearly. If None, no resampling is done.

    Returns:
        DataFrame with datetime index and "capacity_factor" column.

    Raises:
        ValueError: if generation_type is not one of the expected values.
    """
    if country == "UK":
        country = "GB"

    if country in COUNTRY_MAP:
        country = COUNTRY_MAP[country]

    base = DATA_DIR / "ERA5_2024"
    if generation_type == "solar":
        path = base / "solar_capacity_factor" / f"{country}__ERA5__solar__capacity_factor_time_series.nc"
    elif generation_type == "onshore_wind":
        path = base / "wind_capacity_factor" / f"{country}__ERA5__wind__capacity_factor_time_series__onshore.nc"
    elif generation_type == "offshore_wind":
        path = base / "wind_capacity_factor" / f"{country}__ERA5__wind__capacity_factor_time_series__offshore.nc"
    else:
        raise ValueError(f"Unknown generation type: {generation_type}")

    ds = xr.open_dataset(path)
    df = ds.to_dataframe()
    df.columns = ["capacity_factor"]

    if resample is not None:
        df = df.resample(resample).mean()

    return df


@functools.cache
def get_2021_data(generation_type: str = "solar", country: str = "UK", resample: str | None = None) -> pd.DataFrame:
    """ERA5 data from https://doi.org/10.17864/1947.000321.

    Args:
        generation_type: "solar", "onshore_wind", or "offshore_wind"
        country: NUTS0 country code, e.g. "UK", "DE", "FR"
        resample: resample frequency, e.g. "D" for daily, "ME" for monthly, "YE" for yearly. If None, no resampling is done.

    Returns:
        DataFrame with datetime index and "capacity_factor" column.

    Raises:
        ValueError: if generation_type is not one of the expected values.
    """
    if country in COUNTRY_MAP:
        country = COUNTRY_MAP[country]

    base = DATA_DIR / "ERA5_2021"
    if generation_type == "solar":
        path = base / "solar_power_capacity_factor" / "NUTS_0_sp_historical.nc"
    elif generation_type == "onshore_wind":
        path = base / "wp_onshore" / "NUTS_0_wp_ons_sim_0_historical_loc_weighted.nc"
    elif generation_type == "offshore_wind":
        path = base / "wp_offshore" / "NUTS_0_wp_ofs_sim_0_historical_loc_weighted.nc"
    else:
        raise ValueError(f"Unknown generation type: {generation_type}")

    # open the dataset
    ds = xr.open_dataset(path)

    # Select the data for country of interest
    ds = ds.sel(NUTS=ds.NUTS[ds.NUTS_keys == country])

    # convert the time_in_hours_from_first_jan_1950 data array to a datetime index
    ds["time"] = xr.date_range(start="1950-01-01", periods=ds.sizes["time"], freq="h", use_cftime=True)
    ds = ds.set_index(time="time")

    # drop all columns except timeseries_data
    ds = ds.drop_vars(["NUTS_keys", "time_in_hours_from_first_jan_1950"])

    # drop the NUTS dimension
    ds = ds.squeeze(dim="NUTS")

    # convert to pandas dataframe
    df = ds.to_dataframe()

    # convert CFTimeIndex to pandas DateTimeIndex
    df.index = pd.to_datetime(df.index.to_datetimeindex(time_unit="ns"))  # type: ignore[possibly-missing-attribute]

    df.columns = ["capacity_factor"]

    if resample is not None:
        df = df.resample(resample).mean()

    return df
