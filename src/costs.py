from pint import Quantity

import src.assumptions as A
from src.units import Units as U
from src.utils import annualised_cost


def edac_equipment_costs(
    installed_power: Quantity,
    actual_annual_removals: Quantity,
    discount_rate: float = A.EDAC.CentralDiscountRate,
) -> dict[str, Quantity]:
    """Calculate E-DAC fixed annual costs and realised equipment LCOR.

    Installed electrical power is converted to nameplate annual capture
    capacity using the model's E-DAC electricity intensity. CAPEX and fixed
    OPEX are paid for that installed capacity, while realised LCOR uses actual
    removals from the simulation. Consequently, capacity factor affects LCOR
    through actual removals; it does not reduce fixed OPEX.

    This is equipment-only LCOR. Electricity, labour, sorbent, transport and
    CO2 storage costs are not added because no current assumptions for those
    variable costs have been supplied. The legacy GBP 56.84/MWh proxy is also
    intentionally excluded.

    Args:
        installed_power: Installed E-DAC electrical input capacity in GW.
        actual_annual_removals: CO2 removed in an average simulated year.
        discount_rate: Rate used to annualise equipment CAPEX.

    Returns:
        Nameplate removals, total CAPEX, annualised CAPEX, fixed OPEX, total
        annual equipment cost, and realised equipment LCOR.
    """
    assert installed_power.units == U.GW, "E-DAC installed power must be in GW"
    assert actual_annual_removals.check("[mass]"), "Annual removals must have mass units"

    # Full-load electricity consumption defines the nameplate capture capacity
    # corresponding to the model's installed E-DAC power capacity.
    nameplate_energy = (installed_power * A.HoursPerYear).to(U.TWh)
    nameplate_removals = (nameplate_energy / A.DAC.EnergyCost.MediumTWhPerMtCO2).to(U.t)

    # Both CAPEX and fixed non-labour OPEX scale with installed nameplate
    # capacity, not with actual annual operation.
    total_capex = (nameplate_removals * A.EDAC.LearnedCapexPerAnnualCaptureCapacity).to(U.GBP)
    annualised_capex = annualised_cost(total_capex, 0 * U.GBP, A.EDAC.Lifetime, discount_rate)
    fixed_opex = (nameplate_removals * A.EDAC.LearnedFixedOpexPerAnnualCaptureCapacity).to(U.GBP)
    annual_equipment_cost = annualised_capex + fixed_opex

    # Only the denominator uses simulated output. This is how a lower realised
    # capacity factor increases cost per tonne while fixed annual costs remain.
    if actual_annual_removals.to(U.t).magnitude > 0:
        lcor = (annual_equipment_cost / actual_annual_removals).to(U.GBP / U.t)
    else:
        lcor = float("inf") * U.GBP / U.t

    return {
        "nameplate_annual_removals": nameplate_removals,
        "total_capex": total_capex,
        "annualised_capex": annualised_capex,
        "fixed_opex": fixed_opex,
        "annual_equipment_cost": annual_equipment_cost,
        "lcor": lcor,
    }


def yearly_cost(capacity: Quantity, capacity_factor: float, lcoe: Quantity) -> Quantity:
    """Calculate the total yearly cost of an energy source.

    Calculates cost based on its installed capacity, capacity factor, and levelized cost of energy (LCOE).

    Args:
        capacity: Installed capacity in GW.
        capacity_factor: Capacity factor as a fraction (0.0 to 1.0).
        lcoe: Levelized Cost of Energy in GBP/MWh.

    Returns:
        Total yearly cost in GBP.
    """
    # Calculate the annual energy production in GWh
    annual_energy_production = capacity * capacity_factor * A.HoursPerYear

    # Return the total cost in GBP
    return (annual_energy_production * lcoe).to(U.GBP)


def total_storage_cost(
    storage_capacity: Quantity,
    electrolyser_power: Quantity,
    generation_capacity: Quantity,
) -> Quantity:
    """Calculate the total cost of energy storage.

    Includes electrolysis, storage, and generation costs.

    Args:
        storage_capacity: Storage capacity in kWh.
        electrolyser_power: Power of the electrolyser in kW.
        generation_capacity: Generation capacity in kW.

    Returns:
        Total cost of energy storage in GBP.
    """
    storage_cost = storage_capacity * A.HydrogenStorage.CavernStorage.AnnualisedCost
    electrolyser_cost = electrolyser_power * A.HydrogenStorage.Electrolysis.AnnualisedCost
    generation_cost = generation_capacity * A.HydrogenStorage.Generation.AnnualisedCost
    return (storage_cost + electrolyser_cost + generation_cost).to(U.GBP)


def total_system_cost(  # noqa: PLR0913
    *,
    energy_demand: Quantity,
    renewable_capacity: Quantity,
    renewable_capacity_factor: float,
    renewable_lcoe: Quantity,
    nuclear_capacity: Quantity,
    nuclear_capacity_factor: float,
    nuclear_lcoe: Quantity,
    storage_capacity: Quantity,
    electrolyser_power: Quantity,
    generation_capacity: Quantity,
) -> Quantity:
    """Calculate the total system cost.

    Includes renewable energy, storage, electrolysis, and generation costs.

    Args:
        energy_demand: Total energy demand in TWh.
        renewable_capacity: Renewable energy capacity in GW.
        renewable_capacity_factor: Renewable energy capacity factor (0 to 1).
        renewable_lcoe: Renewable energy levelized cost of energy (GBP/MWh).
        nuclear_capacity: Nuclear energy capacity in GW.
        nuclear_capacity_factor: Nuclear energy capacity factor (0 to 1).
        nuclear_lcoe: Nuclear energy levelized cost of energy (GBP/MWh).
        storage_capacity: Storage capacity in kWh.
        electrolyser_power: Power of the electrolyser in kW.
        generation_capacity: Generation capacity in kW.

    Returns:
        Total system cost in GBP.
    """
    renewable_cost = yearly_cost(
        capacity=renewable_capacity,
        capacity_factor=renewable_capacity_factor,
        lcoe=renewable_lcoe,
    )
    nuclear_cost = yearly_cost(
        capacity=nuclear_capacity,
        capacity_factor=nuclear_capacity_factor,
        lcoe=nuclear_lcoe,
    )
    storage_cost = total_storage_cost(storage_capacity, electrolyser_power, generation_capacity)
    additional_costs = A.AdditionalCosts * energy_demand
    return (renewable_cost + nuclear_cost + storage_cost + additional_costs).to(U.GBP)


def energy_cost(system_cost: Quantity, energy_demand: Quantity) -> Quantity:
    """Calculate the cost of energy per MWh.

    Calculates cost based on the total system cost and energy demand (the energy delivered by the system).

    Args:
        system_cost: Total system cost in GBP.
        energy_demand: Total energy demand in MWh.

    Returns:
        Cost of energy in GBP/MWh.
    """
    return (system_cost / energy_demand).to(U.GBP / U.MWh)
