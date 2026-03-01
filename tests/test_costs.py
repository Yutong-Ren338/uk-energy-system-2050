from config import check

from src import assumptions as A
from src.costs import energy_cost, total_storage_cost, total_system_cost, yearly_cost
from src.units import Units as U


def test_nuclear_cost_contribution() -> None:
    nuclear_cost = yearly_cost(capacity=A.Nuclear.Capacity, capacity_factor=A.Nuclear.CapacityFactor, lcoe=A.Nuclear.AverageLCOE)
    cost_constribution = nuclear_cost / A.EnergyDemand2050.to(U.MWh)
    expected = 10.67 * U.GBP / U.MWh
    check(cost_constribution, expected)


def test_recover_old_costs() -> None:
    energy_demand = 575 * U.TWh

    nuclear_cost = yearly_cost(capacity=A.Nuclear.Capacity, capacity_factor=A.Nuclear.CapacityFactor, lcoe=A.Nuclear.AverageLCOE)
    nuclear_cost = energy_cost(nuclear_cost, energy_demand)
    check(nuclear_cost.magnitude, 12.84)

    renewable_cost = yearly_cost(capacity=220 * U.GW, capacity_factor=0.3063, lcoe=37.6 * U.GBP / U.MWh)
    renewable_cost = energy_cost(renewable_cost, energy_demand)
    check(renewable_cost.magnitude, 38.6)

    storage_capacity = 165 * U.TWh
    electrolyser_power = 80 * U.GW
    generation_capacity = 100 * U.GW
    storage_cost = total_storage_cost(storage_capacity, electrolyser_power, generation_capacity)
    storage_cost = energy_cost(storage_cost, energy_demand)
    check(storage_cost.magnitude, 17.28)  # slightly discrepancy here between 17.784 from Rei

    additional_costs = A.AdditionalCosts * energy_demand
    additional_costs = energy_cost(additional_costs, energy_demand)
    check(additional_costs.magnitude, 4.0)

    total_cost = total_system_cost(
        energy_demand=energy_demand,
        renewable_capacity=220 * U.GW,
        renewable_capacity_factor=0.3063,
        renewable_lcoe=37.6 * U.GBP / U.MWh,
        nuclear_capacity=A.Nuclear.Capacity,
        nuclear_capacity_factor=A.Nuclear.CapacityFactor,
        nuclear_lcoe=A.Nuclear.AverageLCOE,
        storage_capacity=165 * U.TWh,
        electrolyser_power=80 * U.GW,
        generation_capacity=100 * U.GW,
    )
    total_cost = energy_cost(total_cost, energy_demand)
    print(nuclear_cost + renewable_cost + storage_cost + additional_costs)
    check(total_cost.magnitude, 72.75)  # 73.22 slightly different from Rei again due to hydrogen storage

    storage_cost_fraction = storage_cost / total_cost
    check(storage_cost_fraction.magnitude, 0.238)
