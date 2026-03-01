import matplotlib.pyplot as plt
import pandas as pd
import pytest
from config import check

from src import assumptions as A
from src import (
    demand_model,
    matplotlib_style,  # noqa: F401
)
from src.data import cb7, historical_demand
from src.demand_model import DemandMode
from src.units import Units as U
from tests.config import OUTPUT_DIR

OUTPUT_PATH = OUTPUT_DIR / "demand_model"
OUTPUT_PATH.mkdir(parents=True, exist_ok=True)

# Constants
DAYS_IN_LEAP_YEAR = 366
MAX_DAILY_CHANGE = 0.1  # Maximum allowed day-to-day change in seasonality index


def test_naive_demand_scaling() -> None:
    """Test the naive demand scaling method."""
    df = demand_model.naive_demand_scaling(historical_demand.historical_electricity_demand())
    assert df.shape[0] > 0
    assert df.columns.tolist() == ["demand"]
    assert df["demand"].dtype == "pint[TWh]"
    assert df["demand"].min() >= 0.0
    assert df.index.name == "date"
    assert isinstance(df.index, pd.DatetimeIndex)
    assert df.index.dtype == "datetime64[ns]"
    assert not df.index.has_duplicates


def test_seasonality_indices() -> None:
    df_electricity = historical_demand.historical_electricity_demand()
    df_gas = historical_demand.historical_gas_demand()
    df_hdd = historical_demand.hdd_era5()
    electricity_seasonality = demand_model.seasonality_index(df_electricity, "demand", average_year=False)
    gas_seasonality = demand_model.seasonality_index(df_gas, "demand", average_year=False)
    hdd_seasonality = demand_model.seasonality_index(df_hdd, "hdd", average_year=False)

    plt.figure()
    plt.plot(hdd_seasonality.index, hdd_seasonality, label="HDD Seasonality Index")
    plt.plot(gas_seasonality.index, gas_seasonality, label="Gas Seasonality Index")
    plt.plot(electricity_seasonality.index, electricity_seasonality, label="Electricity Seasonality Index")
    plt.xlabel("Day of Year")
    plt.ylabel("Seasonality Index")
    plt.title("Gas, Electricity, and HDD Seasonality Indices")
    plt.legend()
    plt.savefig(OUTPUT_PATH / "seasonality_indices_comparison.png")
    plt.close()


def test_seasonality_indices_average_year() -> None:
    df_electricity = historical_demand.historical_electricity_demand()
    df_gas = historical_demand.historical_gas_demand()
    df_hdd = historical_demand.hdd_era5()
    electricity_seasonality = demand_model.seasonality_index(df_electricity, "demand", average_year=True)
    gas_seasonality = demand_model.seasonality_index(df_gas, "demand", average_year=True)
    hdd_seasonality = demand_model.seasonality_index(df_hdd, "hdd", average_year=True)

    # Check that the indices are of the expected length
    assert len(electricity_seasonality) == DAYS_IN_LEAP_YEAR
    assert len(gas_seasonality) == DAYS_IN_LEAP_YEAR
    assert len(hdd_seasonality) == DAYS_IN_LEAP_YEAR

    # Check that the indices are positive
    assert (electricity_seasonality > 0).all()
    assert (gas_seasonality > 0).all()
    assert (hdd_seasonality > 0).all()

    # Check that the mean seasonality index is approximately 1
    check(electricity_seasonality.mean(), 1.0)
    check(gas_seasonality.mean(), 1.0)
    check(hdd_seasonality.mean(), 1.0)

    # Create the plot artifact
    plt.figure()
    plt.plot(gas_seasonality.index, gas_seasonality, label="Gas Seasonality Index")
    plt.plot(electricity_seasonality.index, electricity_seasonality, label="Electricity Seasonality Index")
    plt.plot(hdd_seasonality.index, hdd_seasonality, label="HDD Seasonality Index")
    plt.xlabel("Day of Year")
    plt.ylabel("Seasonality Index")
    plt.title("Gas, Electricity, and HDD Seasonality Indices")
    plt.legend()
    plt.savefig(OUTPUT_PATH / "seasonality_indices_comparison_average_year.png")
    plt.close()


def test_seasonal_demand_scaling_options() -> None:
    A.CB7EnergyDemand2050Buildings = cb7.buildings_electricity_demand(include_non_residential=True)
    df = historical_demand.historical_electricity_demand()
    df["day_of_year"] = df.index.dayofyear  # type: ignore[unresolved-attribute]
    average_year = (df.groupby("day_of_year")["demand"].mean() * A.HoursPerDay).astype("pint[terawatt_hour]")
    plt.plot(average_year.index, average_year.values, label="Average Historical Demand")

    df_naive = demand_model.predicted_demand(mode=DemandMode.NAIVE)
    plt.plot(df_naive.index, df_naive.values, label="Naive Demand Scaling")

    df_seasonal = demand_model.predicted_demand(mode=DemandMode.SEASONAL)
    plt.plot(df_seasonal.index, df_seasonal.values, label="Seasonal Demand Scaling")

    df_seasonal = demand_model.predicted_demand(mode=DemandMode.SEASONAL, filter_ldz=False)
    plt.plot(df_seasonal.index, df_seasonal.values, label="Seasonal Demand Scaling (No LDZ Filter)")

    A.CB7EnergyDemand2050Buildings = cb7.buildings_electricity_demand(include_non_residential=False)
    df_seasonal = demand_model.predicted_demand(mode=DemandMode.SEASONAL, filter_ldz=False)
    plt.plot(df_seasonal.index, df_seasonal.values, label="Seasonal Demand Scaling (+ No Non-Residential)")

    plt.xlabel("Day of Year")
    plt.ylabel("Electricity Demand (TWh/day)")
    plt.legend(fontsize=8)
    plt.savefig(OUTPUT_PATH / "demand_scaling_comparison.png")
    plt.close()


@pytest.mark.parametrize("average_year", [True, False])
def test_predicted_demand(*, average_year: bool) -> None:
    demands = {}
    for mode in DemandMode:
        df = demand_model.predicted_demand(mode=mode, average_year=average_year)
        assert isinstance(df, pd.DataFrame), f"Expected df for mode {mode}, got {type(df)}"
        assert not df.empty, f"Predicted demand for mode {mode} is empty"
        assert df.columns.tolist() == ["demand"], f"Predicted demand for mode {mode} has unexpected columns: {df.columns.tolist()}"
        assert df.index.name == "date", f"Predicted demand for mode {mode} has unexpected index name: {df.index.name}"
        assert df["demand"].notna().all(), f"Predicted demand for mode {mode} contains NaN values"
        assert (df["demand"] >= 0 * U.TWh).all(), f"Predicted demand for mode {mode} contains negative values"
        assert df["demand"].dtype == "pint[TWh]", f"Predicted demand for mode {mode} has incorrect dtype: {df['demand'].dtype}"
        demands[mode] = df

    for mode, df in demands.items():
        plt.plot(df.index, df["demand"], label=f"Predicted Demand ({mode})")
    plt.xlabel("Day of Year")
    plt.ylabel("Electricity Demand (TWh)")
    plt.legend()
    plt.savefig(OUTPUT_PATH / f"predicted_demand_comparison_average_year_{average_year}.png")
    plt.close()
