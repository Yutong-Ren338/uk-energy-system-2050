import pandas as pd

import src.assumptions as A
from src.costs import total_system_cost, yearly_cost
from src.power_system_no_h2 import PowerSystemNoH2
from src.units import Units as U


def test_no_h2_gas_cost_uses_capacity_factor_based_yearly_cost() -> None:
    """Gas cost should use installed capacity times capacity factor times yearly hours."""
    system = PowerSystemNoH2(
        renewable_capacity=200 * U.GW,
        dac_capacity=2 * U.GW,
        gas_ccs_capacity=99 * U.GW,
    )

    sim_df = pd.DataFrame({
        "gas_ccs_energy (TWh),RC=200GW": pd.Series([2.0, 0.0, 0.5], dtype="pint[TWh]"),
        "energy_into_medium_storage (TWh),RC=200GW": pd.Series([0.0, 0.0, 0.0], dtype="pint[TWh]"),
    })

    actual_cost = system.calculate_power_system_cost(sim_df)

    base_cost = total_system_cost(
        energy_demand=A.EnergyDemand2050,
        renewable_capacity=200 * U.GW,
        renewable_capacity_factor=A.Renewables.AverageCapacityFactor,
        renewable_lcoe=A.Renewables.AverageLCOE,
        nuclear_capacity=A.Nuclear.Capacity,
        nuclear_capacity_factor=A.Nuclear.CapacityFactor,
        nuclear_lcoe=A.Nuclear.AverageLCOE,
        storage_capacity=A.MediumTermStorage.Capacity,
        electrolyser_power=0 * U.GW,
        generation_capacity=0 * U.GW,
    )
    expected_gas_cost = yearly_cost(
        capacity=99 * U.GW,
        capacity_factor=2 / 3,
        lcoe=A.DispatchableGasCCS.LCOE,
    )

    assert actual_cost == base_cost + expected_gas_cost
