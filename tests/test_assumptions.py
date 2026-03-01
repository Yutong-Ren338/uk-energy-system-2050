from config import check

import src.assumptions as A
from src.units import Units as U


def test_renewable_weighted_average_capacity_factor() -> None:
    expected_value = 0.2595
    check(A.Renewables.AverageCapacityFactor, expected_value)


def test_electrolyser_annualised_cost() -> None:
    # CL Smith et al (2023). Table 6
    expected = 26.7 * U.GBP / U.kW
    check(A.HydrogenStorage.Electrolysis.AnnualisedCost, expected)


def test_storage_annualised_cost() -> None:
    # CL Smith et al (2023). Table 6
    # !! note they actually have 32.1
    expected = 32.0 * U.GBP / U.MWh
    check(A.HydrogenStorage.CavernStorage.AnnualisedCost, expected)


def test_generation_annualised_cost() -> None:
    # CL Smith et al (2023). Table 6
    expected = 25.2 * U.GBP / U.kW
    check(A.HydrogenStorage.Generation.AnnualisedCost, expected)
