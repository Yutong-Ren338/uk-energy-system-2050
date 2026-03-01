import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pytest

import src.assumptions as A
from src import (
    demand_model,
    matplotlib_style,  # noqa: F401
    supply_model,
)
from src.data import renewable_capacity_factors
from src.demand_model import DemandMode
from src.units import Units as U
from tests.config import IN_CI, OUTPUT_DIR

OUTPUT_PATH = OUTPUT_DIR / "supply_model"
OUTPUT_PATH.mkdir(parents=True, exist_ok=True)


def test_fraction_days_without_excess() -> None:
    demand_era5 = demand_model.predicted_demand(mode=DemandMode.SEASONAL, historical="era5", average_year=False)
    demand_espeni = demand_model.predicted_demand(mode=DemandMode.SEASONAL, historical="espeni", average_year=False)

    A.Nuclear.Capacity = 12 * U.GW
    era5_nuclear = supply_model.fraction_days_without_excess(supply_model.get_net_supply(demand_era5), return_mean=True)
    espeni_nuclear = supply_model.fraction_days_without_excess(supply_model.get_net_supply(demand_espeni), return_mean=True)
    A.Nuclear.Capacity = 0 * U.GW
    era5_no_nuclear = supply_model.fraction_days_without_excess(supply_model.get_net_supply(demand_era5), return_mean=True)
    espeni_no_nuclear = supply_model.fraction_days_without_excess(supply_model.get_net_supply(demand_espeni), return_mean=True)

    plt.figure()
    plt.plot(era5_nuclear.index.values, era5_nuclear, label="ERA5 12 GW Nuclear")
    plt.plot(era5_no_nuclear.index.values, era5_no_nuclear, label="ERA5 0 GW Nuclear")
    plt.plot(espeni_nuclear.index.values, espeni_nuclear, ls="--", label="ESPENI 12 GW Nuclear", color="blue")
    plt.plot(espeni_no_nuclear.index.values, espeni_no_nuclear, ls="--", label="ESPENI 0 GW Nuclear", color="orange")
    plt.xlabel("Renewable Capacity (GW)")
    plt.ylabel("Days without Excess Generation")
    plt.legend()
    plt.savefig(OUTPUT_PATH / "fraction_days_without_excess.png")
    plt.close()


def test_fraction_days_without_excess_naive_demand() -> None:
    # now a version comparing naive and new demand scaling
    demand_naive = demand_model.predicted_demand(mode=DemandMode.NAIVE, historical="era5", average_year=False)
    demand_seasonal = demand_model.predicted_demand(mode=DemandMode.SEASONAL, historical="era5", average_year=False)
    demand_cb7 = demand_model.predicted_demand(mode=DemandMode.CB7, historical="era5", average_year=False)

    A.Nuclear.Capacity = 12 * U.GW
    naive_nuclear = supply_model.fraction_days_without_excess(supply_model.get_net_supply(demand_naive), return_mean=True)
    seasonal_nuclear = supply_model.fraction_days_without_excess(supply_model.get_net_supply(demand_seasonal), return_mean=True)
    cb7_nuclear = supply_model.fraction_days_without_excess(supply_model.get_net_supply(demand_cb7), return_mean=True)
    A.Nuclear.Capacity = 0 * U.GW
    naive_no_nuclear = supply_model.fraction_days_without_excess(supply_model.get_net_supply(demand_naive), return_mean=True)
    seasonal_no_nuclear = supply_model.fraction_days_without_excess(supply_model.get_net_supply(demand_seasonal), return_mean=True)
    cb7_no_nuclear = supply_model.fraction_days_without_excess(supply_model.get_net_supply(demand_cb7), return_mean=True)

    plt.figure()
    plt.plot(naive_nuclear.index.values, naive_nuclear, label="Naive 12 GW Nuclear")
    plt.plot(naive_no_nuclear.index.values, naive_no_nuclear, label="Naive 0 GW Nuclear")
    plt.plot(seasonal_nuclear.index.values, seasonal_nuclear, ls="--", label="Seasonal 12 GW Nuclear", color="blue")
    plt.plot(seasonal_no_nuclear.index.values, seasonal_no_nuclear, ls="--", label="Seasonal 0 GW Nuclear", color="orange")
    plt.plot(cb7_nuclear.index.values, cb7_nuclear, label="CB7 12 GW Nuclear", color="green", ls="dotted")
    plt.plot(cb7_no_nuclear.index.values, cb7_no_nuclear, label="CB7 0 GW Nuclear", color="lightgreen", ls="dotted")
    plt.xlabel("Renewable Capacity (GW)")
    plt.ylabel("Days without Excess Generation")
    plt.legend()
    plt.savefig(OUTPUT_PATH / "fraction_days_without_excess_naive_demand.png")
    plt.close()


def test_total_unmet_demand() -> None:
    # now a version comparing naive and new demand scaling
    demand_naive = demand_model.predicted_demand(mode=DemandMode.NAIVE, historical="era5", average_year=False)
    demand_seasonal = demand_model.predicted_demand(mode=DemandMode.SEASONAL, historical="era5", average_year=False)
    demand_cb7 = demand_model.predicted_demand(mode=DemandMode.CB7, historical="era5", average_year=False)

    original_capacity = A.Nuclear.Capacity
    A.Nuclear.Capacity = 12 * U.GW
    naive_nuclear = supply_model.total_unmet_demand(supply_model.get_net_supply(demand_naive))
    seasonal_nuclear = supply_model.total_unmet_demand(supply_model.get_net_supply(demand_seasonal))
    cb7_nuclear = supply_model.total_unmet_demand(supply_model.get_net_supply(demand_cb7))
    A.Nuclear.Capacity = 0 * U.GW
    naive_no_nuclear = supply_model.total_unmet_demand(supply_model.get_net_supply(demand_naive))
    seasonal_no_nuclear = supply_model.total_unmet_demand(supply_model.get_net_supply(demand_seasonal))
    cb7_no_nuclear = supply_model.total_unmet_demand(supply_model.get_net_supply(demand_cb7))
    A.Nuclear.Capacity = original_capacity

    plt.figure()
    plt.plot(naive_nuclear.index.values, naive_nuclear, label="Naive 12 GW Nuclear")
    plt.plot(naive_no_nuclear.index.values, naive_no_nuclear, label="Naive 0 GW Nuclear")
    plt.plot(seasonal_nuclear.index.values, seasonal_nuclear, ls="--", label="Seasonal 12 GW Nuclear", color="blue")
    plt.plot(seasonal_no_nuclear.index.values, seasonal_no_nuclear, ls="--", label="Seasonal 0 GW Nuclear", color="orange")
    plt.plot(cb7_nuclear.index.values, cb7_nuclear, label="CB7 12 GW Nuclear", color="green", ls="dotted")
    plt.plot(cb7_no_nuclear.index.values, cb7_no_nuclear, label="CB7 0 GW Nuclear", color="lightgreen", ls="dotted")
    plt.xlabel("Renewable Capacity (GW)")
    plt.ylabel("Total Unmet Demand (TWh)")
    plt.legend()
    plt.savefig(OUTPUT_PATH / "total_unmet_demand.png")
    plt.close()


def test_compare_supply_demand() -> None:
    # supply
    daily_capacity_factors = renewable_capacity_factors.get_renewable_capacity_factors(resample="D")
    supply_df = supply_model.daily_renewables_capacity(300 * U.GW, daily_capacity_factors).to_frame()
    supply_df["day_of_year"] = supply_df.index.dayofyear
    mean = supply_df.groupby("day_of_year").mean().astype(float)
    plt.figure(figsize=(10, 5))
    plt.plot(mean.index, mean, label="Supply")

    # naive demand
    naive_df = demand_model.predicted_demand(mode=DemandMode.NAIVE, average_year=True)
    plt.plot(naive_df.index, naive_df["demand"], label="Naive Demand")

    # seasonal demand
    seasonal_df = demand_model.predicted_demand(mode=DemandMode.SEASONAL, average_year=True)
    plt.plot(seasonal_df.index, seasonal_df["demand"], label="Seasonal Demand")

    plt.xlabel("Day of Year")
    plt.ylabel("Energy (TWh)")
    plt.legend()
    plt.savefig(OUTPUT_PATH / "compare_supply_demand.png")
    plt.close()


def test_unmet_demand_by_month() -> None:
    # now a version comparing naive and new demand scaling
    demand_naive = demand_model.predicted_demand(mode=DemandMode.NAIVE, historical="era5", average_year=False)
    demand_seasonal = demand_model.predicted_demand(mode=DemandMode.SEASONAL, historical="era5", average_year=False)
    demand_cb7 = demand_model.predicted_demand(mode=DemandMode.CB7, historical="era5", average_year=False)

    net_supply_naive = supply_model.get_net_supply(demand_naive)
    net_supply_seasonal = supply_model.get_net_supply(demand_seasonal)
    net_supply_cb7 = supply_model.get_net_supply(demand_cb7)

    unmet_demand_naive = net_supply_naive[net_supply_naive < 0].abs()
    unmet_demand_seasonal = net_supply_seasonal[net_supply_seasonal < 0].abs()
    unmet_demand_cb7 = net_supply_cb7[net_supply_cb7 < 0].abs()

    monthly_unmet_demand_naive = unmet_demand_naive.groupby(unmet_demand_naive.index.month).mean()
    monthly_unmet_demand_seasonal = unmet_demand_seasonal.groupby(unmet_demand_seasonal.index.month).mean()
    monthly_unmet_demand_cb7 = unmet_demand_cb7.groupby(unmet_demand_cb7.index.month).mean()

    plt.figure()
    plt.plot(monthly_unmet_demand_naive.index, monthly_unmet_demand_naive.mean(axis=1), label="Naive")
    plt.plot(monthly_unmet_demand_seasonal.index, monthly_unmet_demand_seasonal.mean(axis=1), label="Seasonal")
    plt.plot(monthly_unmet_demand_cb7.index, monthly_unmet_demand_cb7.mean(axis=1), label="CB7")

    plt.xlabel("Month")
    plt.ylabel("Average Daily Unmet Demand (TWh)")
    plt.legend()
    plt.savefig(OUTPUT_PATH / "unmet_demand_by_month.png")
    plt.close()


@pytest.mark.skipif(IN_CI, reason="Skip in CI - requires full data")
def test_get_surplus_days_for_country() -> None:
    """Test get_surplus_days_for_country function."""
    # Test with a known country
    surplus_days = supply_model.get_surplus_days_for_country(source="era5_2021", country="France", percentile=90)

    # Check that we get a non-empty DataFrame
    assert not surplus_days.empty, "Surplus days DataFrame should not be empty"

    # Check that it has the correct country column
    assert "France" in surplus_days.columns, "DataFrame should have France column"

    # Check that values are 0 or 1 (binary)
    assert surplus_days["France"].isin([0, 1]).all(), "Values should be binary (0 or 1)"

    # Check that we have some surplus days (not all zeros)
    assert surplus_days["France"].sum() > 0, "Should have some surplus days"

    # Test with invalid country - should raise ValueError
    with pytest.raises(ValueError, match="Country InvalidCountry not configured"):
        supply_model.get_surplus_days_for_country(source="era5_2021", country="InvalidCountry", percentile=90)


@pytest.mark.skipif(IN_CI, reason="Skip in CI - requires full data")
def test_get_available_imports() -> None:
    """Test get_available_imports function."""
    imports = supply_model.get_available_imports(source="era5_2021")

    # Check that we get a non-empty DataFrame
    assert not imports.empty, "Imports DataFrame should not be empty"

    # Check that it has the total column
    assert "total" in imports.columns, "DataFrame should have total column"

    # Check that all values have the correct units (should be GW)
    for col in imports.columns:
        assert str(imports[col].dtype).startswith("pint["), f"Column {col} should have pint units"
        # Extract the unit from the dtype string
        unit_str = str(imports[col].dtype).split("[")[1].rstrip("]")
        assert "gigawatt" in unit_str.lower() or "gw" in unit_str.lower(), f"Column {col} should have GW units, got {unit_str}"

    # Check that total is sum of individual countries
    country_columns = [col for col in imports.columns if col != "total"]
    if country_columns:  # Only check if we have country columns
        calculated_total = imports[country_columns].sum(axis=1)
        assert (imports["total"] == calculated_total).all(), "Total should equal sum of individual countries"
