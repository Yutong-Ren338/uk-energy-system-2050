from enum import StrEnum

import numpy as np
import pandas as pd

from src import assumptions as A
from src.data import cb7, historical_demand
from src.data.historical_demand import HistoricalDemandSource


class DemandMode(StrEnum):
    NAIVE = "naive"
    SEASONAL = "seasonal"
    CB7 = "cb7"
    HDD = "hdd"


def seasonality_index(df: pd.DataFrame, column: str, *, average_year: bool = False) -> pd.Series:
    """Calculate the seasonality index for a given column in the DataFrame.

    Args:
        df: DataFrame containing the historical demand data.
        column: The column name for which to calculate the seasonality index.
        average_year: If True, averages the values over different years.

    Returns:
        Series containing the seasonality index.
    """
    if average_year:
        df["day_of_year"] = df.index.dayofyear  # type: ignore[unresolved-attribute]
        xs = df.groupby("day_of_year")[column].mean()
        return xs / xs.mean()

    df["year"] = df.index.year  # type: ignore[unresolved-attribute]
    yearly_means = df.groupby("year")[column].mean()
    df["yearly_means"] = df["year"].map(yearly_means)
    return df[column] / df["yearly_means"]


def average_2050_demands() -> tuple[float, float]:
    """Get the average 2050 demands for heating and non-heating.

    Returns:
        Tuple containing the average heating demand and non-heating demand in TWh.
    """
    total_2050_heat_demand = A.CB7EnergyDemand2050Buildings * A.CB7FractionSpaceHeatDemandBuildings
    daily_2050_heat_demand = total_2050_heat_demand / 365
    daily_2050_non_heating_demand = (A.EnergyDemand2050 - total_2050_heat_demand) / 365

    return daily_2050_heat_demand, daily_2050_non_heating_demand


def map_years(historical_df: pd.DataFrame, predicted_df: pd.DataFrame) -> pd.DataFrame:
    """Randomly map years from the historical DataFrame to the predicted DataFrame.

    Used for CB7 demand data, where we have predicted 2050 demands for 3 weather years.
    Mapping them randomly to historical years is better than taking an average and using that every year.

    Args:
        historical_df: DataFrame containing historical demand data with a datetime index.
        predicted_df: DataFrame containing predicted demand data with a datetime index.

    Returns:
        DataFrame with the historical demand data mapped to the predicted years.
    """
    historical_df = historical_df.copy()
    historical_years = historical_df.index.year.unique()  # type: ignore[unresolved-attribute]
    available_years = predicted_df.index.year.unique()  # type: ignore[unresolved-attribute]

    # map each historical year to a random choice from available years
    mapping = np.random.default_rng(seed=42).choice(available_years, len(historical_years))
    historical_df["year"] = historical_df.index.year  # type: ignore[unresolved-attribute]
    historical_df["year"] = historical_df["year"].map(dict(zip(historical_years, mapping, strict=False)))

    historical_df["day_of_year"] = historical_df.index.day_of_year  # type: ignore[unresolved-attribute]
    predicted_df["year"] = predicted_df.index.year  # type: ignore[unresolved-attribute]
    predicted_df["day_of_year"] = predicted_df.index.day_of_year  # type: ignore[unresolved-attribute]

    # merge on year and day
    merged_df = (
        historical_df.reset_index()
        .merge(
            predicted_df,
            on=["year", "day_of_year"],
            suffixes=("", "_predicted"),
        )
        .set_index("date")
    )
    merged_df = merged_df[["demand_predicted"]]
    return merged_df.rename(columns={"demand_predicted": "demand"})


def naive_demand_scaling(df: pd.DataFrame) -> pd.DataFrame:
    """Get naive scaled demand data for analysis.

    This doesn't take into account increased seasonality from electrification of space heating and hot water.

    Args:
        df: DataFrame containing the historical electricity demand data.

    Returns:
        DataFrame with daily demand values scaled to 2050 levels.
    """
    # convert from GW to TWh
    df["demand"] *= A.HoursPerDay

    # Calculate yearly totals and scale each year independently
    df["year"] = df.index.year  # type: ignore[unresolved-attribute]
    yearly_totals = df.groupby("year")["demand"].sum()
    df["yearly_total"] = df["year"].map(yearly_totals)
    scaling_factor = A.EnergyDemand2050 / df["yearly_total"]
    df["demand"] = (df["demand"] * scaling_factor).astype("pint[terawatt_hour]")

    return df[["demand"]]


def seasonal_demand_scaling(df: pd.DataFrame, *, filter_ldz: bool = True) -> pd.DataFrame:
    """Scale the electricity demand data.

    Takes into account increased seasonality from electrification of space heating and hot water.
    Use the raw historical electricity demand data, but average the gas data over different years.

    Args:
        df: DataFrame containing the historical electricity demand data.
        filter_ldz: If True, filters the gas data for "NTS Energy Offtaken, LDZ Offtake Total".
                           This should always be true (just for testing).

    Returns:
        DataFrame with daily demand values scaled to 2050 levels.
    """
    df_gas = historical_demand.historical_gas_demand(filter_ldz=filter_ldz)
    gas_seasonality = seasonality_index(df_gas, "demand", average_year=False)
    ele_seasonality = seasonality_index(df, "demand", average_year=False)
    gas_seasonality = pd.DataFrame(data={"demand": gas_seasonality})
    ele_seasonality = pd.DataFrame(data={"demand": ele_seasonality})

    year_counts = gas_seasonality.index.year.value_counts()  # type: ignore[unresolved-attribute]
    valid_years = year_counts[year_counts >= 365].index  # noqa: PLR2004
    gas_seasonality = gas_seasonality[gas_seasonality.index.year.isin(valid_years)]  # type: ignore[unresolved-attribute]
    gas_seasonality = map_years(ele_seasonality, gas_seasonality)

    # get the daily heating demand
    daily_2050_heat_demand, daily_2050_non_heating_demand = average_2050_demands()
    daily_heating_demand = daily_2050_heat_demand * gas_seasonality
    daily_non_heating_demand = daily_2050_non_heating_demand * ele_seasonality

    merged = daily_non_heating_demand.join(daily_heating_demand, how="inner", validate="one_to_many", lsuffix="_non_heating", rsuffix="_heating")
    merged["demand"] = merged["demand_heating"] + merged["demand_non_heating"]

    return merged[["demand"]]


def hdd_demand_scaling(df: pd.DataFrame) -> pd.DataFrame:
    """Scale the electricity demand data based on heating degree days (HDD).

    Args:
        df: DataFrame containing the historical electricity demand data.

    Returns:
        DataFrame with daily demand values scaled to 2050 levels.
    """
    # get the electricity seasonality (non heating demand seasonality)
    ele_seasonality = seasonality_index(df, "demand", average_year=False)
    ele_seasonality = pd.DataFrame(data={"demand": ele_seasonality})

    # get the heating demand seasonality
    hdd = historical_demand.hdd_era5()
    hdd_seasonality = seasonality_index(hdd, "hdd", average_year=False)
    hdd_seasonality = pd.DataFrame(data={"demand": hdd_seasonality})

    # compute the final seasonal demand time eries
    daily_2050_heat_demand, daily_2050_non_heating_demand = average_2050_demands()
    daily_2050_heat_demand *= hdd_seasonality
    daily_2050_non_heating_demand *= ele_seasonality

    merged = daily_2050_non_heating_demand.join(
        daily_2050_heat_demand, how="inner", validate="one_to_one", lsuffix="_non_heating", rsuffix="_heating"
    )
    merged["demand"] = merged["demand_heating"] + merged["demand_non_heating"]

    return merged[["demand"]]


def predicted_demand(
    mode: DemandMode = DemandMode.NAIVE,
    historical: HistoricalDemandSource = "era5",
    *,
    filter_ldz: bool = True,
    average_year: bool = False,
) -> pd.DataFrame:
    """Get the predicted demand for 2050 based on the specified mode.

    Args:
        mode: The mode of demand prediction.
        historical: The source of historical demand data, either "era5" or "espeni".
        filter_ldz: If True, filters the gas data for "NTS Energy Offtaken, LDZ Offtake Total".
        average_year: If True, returns the average over different years.

    Returns:
        DataFrame with predicted daily demand values.

    Raises:
        ValueError: If the mode is not a valid DemandMode.
    """
    df = historical_demand.historical_electricity_demand(source=historical)
    if mode == DemandMode.NAIVE:
        out = naive_demand_scaling(df)
    elif mode == DemandMode.SEASONAL:
        out = seasonal_demand_scaling(df, filter_ldz=filter_ldz)
    elif mode == DemandMode.CB7:
        out = cb7.cb7_demand(A.EnergyDemand2050)[["demand"]]
        # randomly match cb7 demand years to historical years
        if not average_year:
            out = map_years(historical_df=df, predicted_df=out)
    elif mode == DemandMode.HDD:
        out = hdd_demand_scaling(df)
    else:
        raise ValueError(f"Invalid mode. Choose from {[e.value for e in DemandMode]}.")

    if average_year:
        out = out.groupby(out.index.dayofyear).mean()  # type: ignore[unresolved-attribute]

    return out
