import numpy as np
import pandas as pd

import src.assumptions as A
from src.data import renewable_capacity_factors
from src.data.renewable_capacity_factors import CapacityFactorSource
from src.units import Units as U


def daily_renewables_capacity(renewable_capacity: float, capacity_factors: pd.DataFrame) -> pd.DataFrame:
    """Calculate the daily renewable generation capacity.

    Calculates capacity based on the given renewable capacity and capacity factors.

    Args:
        renewable_capacity: Total renewable capacity.
        capacity_factors: DataFrame containing daily capacity factors for solar, offshore wind, and onshore wind.

    Returns:
        A DataFrame with daily renewable generation capacity.
    """
    solar = renewable_capacity * A.Renewables.CapacityRatios.Solar * capacity_factors["solar"]
    offshore_wind = renewable_capacity * A.Renewables.CapacityRatios.OffshoreWind * capacity_factors["offshore"]
    onshore_wind = renewable_capacity * A.Renewables.CapacityRatios.OnshoreWind * capacity_factors["onshore"]
    total_power = solar + offshore_wind + onshore_wind + A.Nuclear.Capacity * A.Nuclear.CapacityFactor
    return (total_power * A.HoursPerDay).astype("pint[TWh]")


def get_net_supply(demand_df: pd.DataFrame, capacity_factors_source: CapacityFactorSource = "renewable_ninja") -> pd.DataFrame:
    """Get net supply dataframe (supply minus demand) for analysis.

    Args:
        demand_df: DataFrame containing the projected 2050 demand data.
        capacity_factors_source: Source of the renewable capacity factors. Options are "renewable_ninja", "era5_2021", "era5_2024", or "ninja_2025".

    Returns:
        DataFrame with renewable capacity as columns and daily net demand (supply - demand) as values.
        Negative values indicate demand exceeds supply.
    """
    # get output for a range of renewable capacities
    daily_capacity_factors = renewable_capacity_factors.get_renewable_capacity_factors(source=capacity_factors_source, resample="D")
    renewable_capacities = [x * U.GW for x in range(100, 500, 10)]
    supply_df = pd.DataFrame({capacity.magnitude: daily_renewables_capacity(capacity, daily_capacity_factors) for capacity in renewable_capacities})

    # apply losses to supply
    supply_df *= 1 - A.PowerSystem.TotalLosses

    # reindex for subtraction
    common_idx = supply_df.index.intersection(demand_df.index)
    assert len(common_idx) > 0, "No common dates between supply and demand dataframes."
    supply_df = supply_df.reindex(common_idx)
    demand_df = demand_df.reindex(common_idx)

    # subtract the demand from the renewable generation to get the net demand
    return supply_df.sub(demand_df["demand"], axis=0)


def fraction_days_without_excess(net_supply_df: pd.DataFrame, *, return_mean: bool = True) -> pd.Series:
    """Calculate the fraction of days without excess renewable generation.

    Calculates for a range of renewable capacities.

    Args:
        net_supply_df: DataFrame with renewable capacity as columns and daily net supply (supply - demand) as values.
        return_mean: If True, return the mean fraction of days without excess generation.

    Returns:
        A series with renewable capacity as index and the number of days without excess generation as values.
    """
    # count the number of days without excess generation (where net supply is negative)
    days_without_excess = (net_supply_df < 0).mean(axis=0) if return_mean else (net_supply_df < 0).sum(axis=0)
    days_without_excess.index.name = "renewable_capacity_GW"
    days_without_excess.name = "days_without_excess_generation"

    return days_without_excess


def total_unmet_demand(net_supply_df: pd.DataFrame) -> pd.Series:
    """Calculate the total unmet demand.

    Args:
        net_supply_df: DataFrame with renewable capacity as columns and daily net supply (supply - demand) as values.

    Returns:
        A series with renewable capacity as index and the total unmet demand as values.
    """
    unmet_demand = net_supply_df[net_supply_df < 0].sum(axis=0).abs()
    unmet_demand.index.name = "renewable_capacity_GW"
    unmet_demand.name = "total_unmet_demand"

    return unmet_demand


def get_surplus_days_for_country(source: CapacityFactorSource, country: str, percentile: int) -> pd.DataFrame:
    """Get days where combined renewable capacity factor is above the specified percentile for a given country.

    Note: the current approach of summing CF only makes sense for the current daily resampling, otherwise will never choose times at night.

    Args:
        source: Source of capacity factor data, e.g. "era5_2021" or "era5_2024"
        country: Country name, e.g. "France"
        percentile: Percentile threshold for surplus days

    Returns:
        DataFrame with 1s on days with available imports and 0s otherwise.

    Raises:
        ValueError: if country is not in country_map
    """
    if country not in A.Interconnectors.Config:
        raise ValueError(f"Country {country} not configured in assumptions.Interconnectors.Config")

    # get combined renewable capacity factor for country
    combined_cf = renewable_capacity_factors.get_renewable_capacity_factors(source=source, country=country).astype(float).sum(axis=1)

    # get specified percentile of combined_cf
    x = np.percentile(combined_cf, percentile)

    out = pd.DataFrame(index=combined_cf.index, columns=[country])
    out.loc[combined_cf > x, country] = 1
    out.loc[combined_cf <= x, country] = 0
    return out


def get_available_imports(source: CapacityFactorSource) -> pd.DataFrame:
    """Get available imports from interconnectors based on surplus renewable generation in each country.

    Args:
        source: Source of capacity factor data, e.g. "era5_2021" or "era5_2024"

    Returns:
        pd.DataFrame: DataFrame with available imports from each country in GW.
    """
    import_df = None
    for country, config in A.Interconnectors.Config.items():
        days = get_surplus_days_for_country(source=source, country=country, percentile=50)
        capacity = config["Capacity"]
        unit = capacity.units
        this_import = days * capacity.magnitude
        import_df = this_import if import_df is None else import_df.join(this_import, how="inner")
    assert import_df is not None
    import_df["total"] = import_df.sum(axis=1)
    return import_df.astype(f"pint[{unit}]")

