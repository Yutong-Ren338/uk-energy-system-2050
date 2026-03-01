from pathlib import Path
from typing import Literal

import pandas as pd

from src import DATA_DIR

HistoricalDemandSource = Literal["era5", "espeni"]


def demand_era5(resample: str | None = None, *, weather_adjusted: bool = False) -> pd.DataFrame:
    """Load and return the ERA5 full electricity demand data for the UK.

    Args:
        resample: Resampling rule for the time series data (e.g., 'D' for daily, 'M' for monthly).
        weather_adjusted: If True, return weather-adjusted demand; otherwise, return raw demand.

    Returns:
        DataFrame containing the demand data in GW.
    """
    if weather_adjusted:
        data_file = DATA_DIR / "ERA5_weather_dependent_demand_UK_1979_2019_hourly.csv"
    else:
        data_file = DATA_DIR / "ERA5_full_demand_UK_1979_2019_hourly.csv"

    df = pd.read_csv(data_file, index_col=0, parse_dates=True)
    df.index.name = "date"
    df = df[df.columns[df.columns.str.contains("United_Kingdom")]]
    df.columns = ["demand"]
    if resample:
        df = df.resample(resample).mean()

    return df.astype("pint[GW]")


def demand_espeni(resample: str | None = None) -> pd.DataFrame:
    """Load and return the Espeni full electricity demand data for the UK.

    Args:
        resample: Resampling rule for the time series data (e.g., 'D' for daily, 'M' for monthly).

    Returns:
        DataFrame containing the demand data in GW.
    """
    # demand is in MW
    df = pd.read_csv(DATA_DIR / "espeni.csv")
    df = df[["ELEXM_utc", "POWER_ESPENI_MW"]]
    df = df.rename(columns={"ELEXM_utc": "date", "POWER_ESPENI_MW": "demand"})
    df["demand"] /= 1000.0  # convert to GW
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)  # type: ignore[unresolved-attribute]
    df = df.set_index("date")
    if resample:
        df = df.resample(resample).mean()

    return df.astype("pint[GW]")


def historical_electricity_demand(source: HistoricalDemandSource = "era5") -> pd.DataFrame:
    """Get raw demand data for analysis.

    Args:
        source: The source of demand data, either "era5" or "espeni".

    Returns:
        DataFrame with daily demand values.

    Raises:
        ValueError: If source is not "era5" or "espeni".
    """
    if source == "era5":
        return demand_era5("D")
    if source == "espeni":
        return demand_espeni("D")
    raise ValueError("Invalid source. Choose 'era5' or 'espeni'.")


def historical_gas_demand(*, filter_ldz: bool = True) -> pd.DataFrame:
    """Load and return the gas demand data for the UK.

    Args:
        filter_ldz: If True, filter the data for "NTS Energy Offtaken, LDZ Offtake Total".

    Returns:
        DataFrame containing the gas demand data.
    """
    data_dir = Path(__file__).parents[2] / "data"
    df = pd.read_csv(data_dir / "UK_gas_demand_processed.csv", parse_dates=["date"])
    if filter_ldz:
        df = df[df["use"] == "NTS Energy Offtaken, LDZ Offtake Total"]

    # set demand units and rename column
    df["demand (TWh)"] = df["demand (TWh)"].astype("pint[TWh]")
    df = df.rename(columns={"demand (TWh)": "demand"})

    return df.set_index("date")[["demand"]]


def hdd_era5(resample: str | None = None) -> pd.DataFrame:
    """Load and return the ERA5 heating degree days (HDD) data for the UK.

    Args:
        resample: The resampling frequency (e.g., 'M' for monthly). If None, no resampling is applied.

    Returns:
        pd.DataFrame: The HDD data for the UK
    """
    df = pd.read_csv(DATA_DIR / "ERA5_HDD_all_countries_1979_2019_inclusive.csv", index_col=0, parse_dates=True)
    uk_cols = df.columns[df.columns.str.contains("United_Kingdom")].tolist()
    assert len(uk_cols) == 1, f"Expected 1 column for United Kingdom, found {len(uk_cols)}"
    df = df[uk_cols]
    df = df.rename(columns={uk_cols[0]: "hdd"})
    if resample:
        df = df.resample(resample).mean()
    return df
