import pandas as pd
from pint import Quantity

from src import DATA_DIR
from src.units import Units as U

TARGET_YEAR = 2050


def frac_heat_demand_from_buildings() -> float:
    """Calculate the fraction of energy demand from residential buildings that is for heating.

    Analyzes the Seventh Carbon Budget dataset to determine what proportion of residential
    building energy demand (excluding other home energy use) comes from heating in 2050
    under the Balanced Pathway scenario.

    Returns:
        Fraction of energy demand that is for heating (expected ~0.597)
    """
    data_path = DATA_DIR / "The-Seventh-Carbon-Budget-full-dataset.xlsx"

    df = pd.read_excel(data_path, sheet_name="Subsector-level data")

    # Filter for residential buildings in 2050 under Balanced Pathway scenario
    mask = (
        (df["scenario"] == "Balanced Pathway")
        & (df["year"] == TARGET_YEAR)
        & (df["sector"] == "Residential buildings")
        & (df["variable"] == "Energy: gross demand electricity")
    )
    df_filtered = df[mask]

    # Calculate fraction excluding "Other home energy use"
    # Keeping only "Heat in existing homes" and "Heat in new homes"
    heating_demand = df_filtered[df_filtered["subsector"].isin(["Heat in existing homes", "Heat in new homes"])]["value"].sum()
    total_demand = df_filtered["value"].sum()

    return heating_demand / total_demand


def buildings_electricity_demand(*, include_non_residential: bool = True) -> float:
    """Calculate the total electricity demand for UK buildings in 2050 in TWh.

    Combines demand for residential and non-residential buildings.

    Args:
        include_non_residential: If True, includes non-residential buildings in the calculation.

    Returns:
        Total electricity demand for buildings in 2050 in TWh.
    """
    data_path = DATA_DIR / "The-Seventh-Carbon-Budget-full-dataset.xlsx"
    df = pd.read_excel(data_path, sheet_name="Sector-level data")
    df = df[df["scenario"] == "Balanced Pathway"]
    df = df[df["country"] == "United Kingdom"]
    df = df[df["year"] == TARGET_YEAR]
    sectors = ["Residential buildings"]
    if include_non_residential:
        sectors = ["Residential buildings", "Non-residential buildings"]
    df = df[df["sector"].isin(sectors)]
    df = df[df["variable"] == "Energy: final demand electricity"]
    return df["value"].sum() * U.TWh


def total_demand_2050() -> float:
    """Calculate the total electricity demand for the UK in 2050 in TWh.

    Returns:
        Total energy demand for buildings in 2050 in TWh.
    """
    data_path = DATA_DIR / "The-Seventh-Carbon-Budget-full-dataset.xlsx"
    df = pd.read_excel(data_path, sheet_name="Economy-wide data")
    df = df[df["scenario"] == "Balanced Pathway"]
    df = df[df["country"] == "United Kingdom"]
    df = df[df["year"] == TARGET_YEAR]
    df = df[df["variable"] == "Energy: final demand electricity"]
    return df["value"].sum() * U.TWh


def extract_daily_2050_demand() -> None:
    """Extract the daily electricity demand for 2050 from the Seventh Carbon Budget dataset.

    The dataset contains hourly demand data for different weather years, save it as daily for convenience.
    Note: the demands here are "generation level", rather than "end use" leve, which means they are around 11% large,
    taking into account transmission and distribution losses.

    """
    demand_year = 2050
    df = pd.read_excel(
        DATA_DIR / "The-Seventh-Carbon-Budget-methodology-accompanying-data-electricity-supply-hourly-results.xlsx",
        sheet_name="Data",
        skiprows=4,
    )
    df = df.loc[df["Year"] == demand_year]

    # remove column
    df = df.drop(columns=["Unnamed: 20"])

    # convert Year and Hour columns to date
    df["date"] = pd.to_datetime(df["Weather year"], format="%Y") + pd.to_timedelta(df["Hour"] - 1, unit="h")

    # convert to TWh
    df["Electricity demand without electrolysis"] /= 1e3

    # resample each weather year to daily sums and combine
    dfs = {}
    for weather_year in df["Weather year"].unique():
        df_ = df[df["Weather year"] == weather_year].copy()
        df_ = df_.resample("D", on="date")["Electricity demand without electrolysis"].sum().reset_index()
        df_ = df_.rename(columns={"Electricity demand without electrolysis": "demand (TWh)"})
        df_["weather year"] = weather_year
        dfs[weather_year] = df_
    df_combined = pd.concat(dfs.values(), ignore_index=True)

    # save as csv
    df_combined.to_csv(DATA_DIR / f"ccc_daily_demand_{demand_year}.csv", index=False)


def cb7_demand(total_yearly_demand: Quantity) -> pd.DataFrame:
    """Load and return the CCC 2050 demand data for the UK.

    Loads the data from the preprocessed CSV file created by `extract_daily_2050_demand`.

    Args:
        total_yearly_demand: The total yearly demand in TWh, used to scale the daily demand.

    Returns:
        DataFrame containing the demand data in GW.
    """
    df = pd.read_csv(DATA_DIR / "ccc_daily_demand_2050.csv", index_col=0, parse_dates=True)
    df = df.rename(columns={"demand (TWh)": "demand"})
    df.index.name = "date"
    df["demand"] = (df["demand"]).astype("pint[TWh]")
    df["demand"] *= total_yearly_demand * 3 / df["demand"].sum()
    return df
