"""Scenario helpers for the power system model.

This module provides convenience functions to run common scenarios such as
"with vs without gas CCS" and "reduced or zero hydrogen storage".

All functions use pint units and existing model components.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd
from pint import Quantity

import src.assumptions as A
from src.demand_model import DemandMode, predicted_demand
from src.power_system import PowerSystem
from src.supply_model import CapacityFactorSource, get_net_supply
from src.units import Units as U


@dataclass
class ScenarioResult:
    """Container for scenario outputs for convenient use in notebooks."""

    system: PowerSystem
    sim_df: pd.DataFrame | None
    analysis: dict | None
    energy_cost: Quantity
    lt_dac_result: "LTDACResult | None" = None


@dataclass
class LTDACResult:
    """Results for low-temperature DAC fed by CCGT waste heat."""

    heat_available: pd.Series
    heat_used: pd.Series
    co2_captured: pd.Series
    electricity_consumption: pd.Series
    net_gas_ccs_energy: pd.Series
    annual_heat_used: Quantity
    annual_co2_captured: Quantity
    annual_electricity: Quantity


def run_power_system_scenario(  # noqa: PLR0913
    *,
    renewable_capacity: Quantity,
    demand_mode: DemandMode = DemandMode.SEASONAL,
    capacity_factors_source: CapacityFactorSource = "era5_2024",
    enable_imports: bool = False,
    hydrogen_storage_capacity: Quantity | None = None,
    electrolyser_power: Quantity | None = None,
    hydrogen_generation_power: Quantity | None = None,
    medium_storage_capacity: Quantity | None = None,
    medium_storage_power: Quantity | None = None,
    gas_ccs_capacity: Quantity | None = None,
    dac_capacity: Quantity | None = None,
    enable_gas_ltdac: bool = False,
) -> ScenarioResult:
    """Run a single power system scenario and return results.

    Args:
        renewable_capacity: Total renewable capacity in GW.
        demand_mode: Demand scaling mode for 2050 demand.
        capacity_factors_source: Source for renewable capacity factors (e.g., "era5_2024" or "ninja_2025").
        enable_imports: Whether to include interconnector imports.
        hydrogen_storage_capacity: Hydrogen storage capacity in TWh.
        electrolyser_power: Electrolyser power in GW.
        hydrogen_generation_power: Hydrogen generation power in GW.
        medium_storage_capacity: Medium-term storage capacity in TWh.
        medium_storage_power: Medium-term storage power in GW.
        gas_ccs_capacity: Dispatchable gas with CCS capacity in GW.
        dac_capacity: DAC capacity in GW.
        enable_gas_ltdac: Whether to enable low-temperature DAC on gas CCS (waste heat based).

    Returns:
        ScenarioResult containing the configured system, simulation dataframe,
        analysis dict, and energy cost quantity.
    """
    # Defaults from assumptions when not specified
    if hydrogen_storage_capacity is None:
        hydrogen_storage_capacity = A.HydrogenStorage.CavernStorage.Capacity
    if electrolyser_power is None:
        electrolyser_power = A.HydrogenStorage.Electrolysis.Power
    if hydrogen_generation_power is None:
        hydrogen_generation_power = A.HydrogenStorage.Generation.Power
    if medium_storage_capacity is None:
        medium_storage_capacity = A.MediumTermStorage.Capacity
    if medium_storage_power is None:
        medium_storage_power = A.MediumTermStorage.Power
    if gas_ccs_capacity is None:
        gas_ccs_capacity = A.DispatchableGasCCS.Capacity
    if dac_capacity is None:
        dac_capacity = A.DAC.Capacity

    # Demand and net supply
    demand_df = predicted_demand(mode=demand_mode)
    net_supply_df = get_net_supply(demand_df=demand_df, capacity_factors_source=capacity_factors_source)

    # Instantiate and run the power system
    system = PowerSystem(
        renewable_capacity=renewable_capacity,
        hydrogen_storage_capacity=hydrogen_storage_capacity,
        electrolyser_power=electrolyser_power,
        dac_capacity=dac_capacity,
        hydrogen_generation_power=hydrogen_generation_power,
        medium_storage_capacity=medium_storage_capacity,
        medium_storage_power=medium_storage_power,
        gas_ccs_capacity=gas_ccs_capacity,
        only_dac_if_hydrogen_storage_full=True,
        enable_gas_ltdac=enable_gas_ltdac,
        enable_imports=enable_imports,
        capacity_factors_source=capacity_factors_source,
    )

    sim_df = system.run_simulation(net_supply_df=net_supply_df)
    analysis = system.analyze_simulation_results(sim_df)
    energy_cost = system.calculate_energy_cost(sim_df)

    return ScenarioResult(system=system, sim_df=sim_df, analysis=analysis, energy_cost=energy_cost)


def compare_ccs_vs_no_ccs(
    *,
    renewable_capacity: Quantity,
    demand_mode: DemandMode = DemandMode.SEASONAL,
    capacity_factors_source: CapacityFactorSource = "era5_2024",
    enable_imports: bool = False,
    hydrogen_storage_capacity: Quantity | None = None,
    electrolyser_power: Quantity | None = None,
    hydrogen_generation_power: Quantity | None = None,
) -> dict[Literal["with_ccs", "no_ccs"], ScenarioResult]:
    """Run a pair of scenarios to review gas with CCS vs without CCS.

    "Without CCS" is modeled by setting dispatchable gas CCS capacity to zero.
    """
    with_ccs = run_power_system_scenario(
        renewable_capacity=renewable_capacity,
        demand_mode=demand_mode,
        capacity_factors_source=capacity_factors_source,
        enable_imports=enable_imports,
        hydrogen_storage_capacity=hydrogen_storage_capacity,
        electrolyser_power=electrolyser_power,
        hydrogen_generation_power=hydrogen_generation_power,
        gas_ccs_capacity=A.DispatchableGasCCS.Capacity,
    )

    no_ccs = run_power_system_scenario(
        renewable_capacity=renewable_capacity,
        demand_mode=demand_mode,
        capacity_factors_source=capacity_factors_source,
        enable_imports=enable_imports,
        hydrogen_storage_capacity=hydrogen_storage_capacity,
        electrolyser_power=electrolyser_power,
        hydrogen_generation_power=hydrogen_generation_power,
        gas_ccs_capacity=0 * U.GW,
    )

    return {"with_ccs": with_ccs, "no_ccs": no_ccs}


def low_or_zero_hydrogen_storage(
    *,
    renewable_capacity: Quantity,
    mode: Literal["reduced", "zero"] = "reduced",
    demand_mode: DemandMode = DemandMode.SEASONAL,
    capacity_factors_source: CapacityFactorSource = "era5_2024",
    enable_imports: bool = False,
    reduced_storage_capacity: Quantity = 1.0 * U.TWh,
    reduced_electrolyser_power: Quantity = 5.0 * U.GW,
    reduced_hydrogen_generation_power: Quantity = 5.0 * U.GW,
    gas_ccs_capacity: Quantity | None = None,
    fill_with_natural_gas: bool = True,
) -> ScenarioResult:
    """Run the model with much less hydrogen storage (or zero).

    By default any deficit created by the reduced hydrogen system is met with
    dispatchable natural-gas generation (modeled via the `gas_ccs_capacity`
    parameter). Set ``fill_with_natural_gas=False`` to disable gas backup.

    For "zero", electrolyser and hydrogen generation power are also set to zero
    to avoid unusable conversion pathways.
    """
    if mode == "zero":
        h2_storage = 0 * U.TWh
        el_power = 0 * U.GW
        h2_gen_power = 0 * U.GW
    else:
        h2_storage = reduced_storage_capacity
        el_power = reduced_electrolyser_power
        h2_gen_power = reduced_hydrogen_generation_power

    if fill_with_natural_gas:
        backup_capacity = A.DispatchableGasCCS.Capacity if gas_ccs_capacity is None else gas_ccs_capacity
    else:
        backup_capacity = 0 * U.GW

    return run_power_system_scenario(
        renewable_capacity=renewable_capacity,
        demand_mode=demand_mode,
        capacity_factors_source=capacity_factors_source,
        enable_imports=enable_imports,
        hydrogen_storage_capacity=h2_storage,
        electrolyser_power=el_power,
        hydrogen_generation_power=h2_gen_power,
        gas_ccs_capacity=backup_capacity,
    )


def _estimate_gas_emissions(
    annual_gas_energy: Quantity, *, intensity: Quantity | None = None
) -> Quantity:
    """Estimate residual CO2 from annual gas generation.https://ourworldindata.org/grapher/carbon-dioxide-emissions-factor?tab=table"""
    emissions_intensity = (
        (201.96 * U.t_mt / U.GWh).to(U.Mt_mt / U.TWh) if intensity is None else intensity
    )
    assert annual_gas_energy.units == U.TWh, "Gas energy must be in TWh"
    return (annual_gas_energy * emissions_intensity).to(U.Mt_mt)


def electricity_to_capture_co2(
    residual_co2: Quantity, *, electricity_per_t_co2: Quantity | None = None
) -> Quantity:
    """Calculate auxiliary electricity needed to capture a given mass of CO2 via LT DAC."""
    electricity_per_t_co2 = (
        A.LTDAC.ElectricityPerTonCO2 if electricity_per_t_co2 is None else electricity_per_t_co2
    )
    assert electricity_per_t_co2.units == U.MWh / U.t_mt, "Electricity intensity must be in MWh/tCO2"
    co2_tonnes = residual_co2.to(U.t_mt)
    return (co2_tonnes * electricity_per_t_co2).to(U.TWh)


def capital_cost_to_capture_co2(
    residual_co2: Quantity, *, cost_per_t_co2: Quantity | None = None
) -> Quantity:
    """Calculate capital cost to capture a given mass of CO2 at $2170/t by default."""
    default_cost = (2170 / A.GBPToUSD) * U.GBP / U.t_mt
    cost_per_t_co2 = default_cost if cost_per_t_co2 is None else cost_per_t_co2
    assert cost_per_t_co2.units == U.GBP / U.t_mt, "Cost must be in currency per tCO2"
    co2_tonnes = residual_co2.to(U.t_mt)
    return (co2_tonnes * cost_per_t_co2).to(U.GBP)


def calculate_lt_dac_from_gas_waste_heat(
    scenario: ScenarioResult,
    *,
    gas_input_per_t_co2: Quantity | None = None,
    gas_ccs_efficiency: float | None = None,
    electricity_per_t_co2: Quantity | None = None,
    regeneration_efficiency: float | None = None,
    attach_to_scenario: bool = True,
) -> LTDACResult:
    """Estimate LT DAC capture powered by waste heat from gas+CCS generation.

    Args:
        scenario: Completed power system scenario.
        gas_input_per_t_co2: Gas energy required per tonne of CO2 captured (default ``A.LTDAC.GasInputPerTonCO2``).
        gas_ccs_efficiency: Electrical efficiency of the CCGT with CCS (default ``A.DispatchableGasCCS.Efficiency``).
        electricity_per_t_co2: Auxiliary electricity per tonne of CO2 (default ``A.LTDAC.ElectricityPerTonCO2``).
        regeneration_efficiency: Process efficiency factor (default ``A.LTDAC.RegenerationEfficiency``).
        attach_to_scenario: Whether to store the result on the ScenarioResult for convenience.

    Returns:
        LTDACResult with daily series and annual totals for LT DAC heat use, CO2 captured, and electricity draw.
    """
    if scenario.sim_df is None:
        raise ValueError("LT DAC calculation requires a successful simulation (sim_df cannot be None).")

    gas_input_per_t_co2 = A.LTDAC.GasInputPerTonCO2 if gas_input_per_t_co2 is None else gas_input_per_t_co2
    gas_ccs_efficiency = A.DispatchableGasCCS.Efficiency if gas_ccs_efficiency is None else gas_ccs_efficiency
    electricity_per_t_co2 = A.LTDAC.ElectricityPerTonCO2 if electricity_per_t_co2 is None else electricity_per_t_co2
    regeneration_efficiency = A.LTDAC.RegenerationEfficiency if regeneration_efficiency is None else regeneration_efficiency

    gas_ccs_column = f"gas_ccs_energy (TWh),RC={int(scenario.system.renewable_capacity)}GW"
    if gas_ccs_column not in scenario.sim_df:
        raise KeyError(f"Gas CCS column '{gas_ccs_column}' not found in simulation results.")

    gas_energy = scenario.sim_df[gas_ccs_column].astype("pint[TWh]")

    thermal_energy = gas_energy / gas_ccs_efficiency
    available_heat = thermal_energy

    co2_captured = (available_heat.pint.to(U.GJ) / gas_input_per_t_co2 * regeneration_efficiency).pint.to(U.Mt)
    heat_used = available_heat
    electricity_consumption = (co2_captured.pint.to(U.t) * electricity_per_t_co2).pint.to(U.TWh)
    net_gas_ccs_energy = (gas_energy - electricity_consumption).clip(lower=0 * U.TWh)

    result = LTDACResult(
        heat_available=available_heat,
        heat_used=heat_used,
        co2_captured=co2_captured,
        electricity_consumption=electricity_consumption,
        net_gas_ccs_energy=net_gas_ccs_energy,
        annual_heat_used=heat_used.sum().to(U.TWh),
        annual_co2_captured=co2_captured.sum().to(U.Mt),
        annual_electricity=electricity_consumption.sum().to(U.TWh),
    )

    if attach_to_scenario:
        scenario.lt_dac_result = result

    return result


def find_gas_only_capacity_no_hydrogen(
    *,
    renewable_capacity: Quantity,
    demand_mode: DemandMode = DemandMode.SEASONAL,
    capacity_factors_source: CapacityFactorSource = "era5_2024",
    enable_imports: bool = False,
    start_capacity: Quantity = 1 * U.GW,
    step: Quantity = 1 * U.GW,
    max_capacity: Quantity = 80 * U.GW,
) -> tuple[ScenarioResult, Quantity, Quantity]:
    """Run with zero hydrogen and ramp gas+CCS capacity until the simulation succeeds.

    Returns:
        A tuple of (scenario_result, gas_capacity_used, estimated_residual_co2)
    """
    gas_capacity = start_capacity

    while gas_capacity <= max_capacity:
        scenario = run_power_system_scenario(
            renewable_capacity=renewable_capacity,
            demand_mode=demand_mode,
            capacity_factors_source=capacity_factors_source,
            enable_imports=enable_imports,
            hydrogen_storage_capacity=0 * U.TWh,
            electrolyser_power=0 * U.GW,
            hydrogen_generation_power=0 * U.GW,
            gas_ccs_capacity=gas_capacity,
        )

        if scenario.analysis is not None:
            gas_energy = scenario.analysis["annual_gas_ccs_energy"]
            residual_co2 = _estimate_gas_emissions(gas_energy)
            return scenario, gas_capacity, residual_co2

        gas_capacity += step

    raise RuntimeError(
        f"Simulation failed to meet demand up to {max_capacity:~0.1f} gas CCS capacity"
    )
