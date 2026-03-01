# ruff: noqa: PLR0913, PLR0917, FBT001
from typing import NamedTuple

import numba
import numpy as np

# Power System Model (NO_H2 variant)
# Handles renewable/net supply with medium storage, interconnects, gas CCS, and DAC/E-DAC from gas

# Floating point precision tolerance for residual energy calculations
FLOATING_POINT_TOLERANCE = 1e-10


class SimulationParameters(NamedTuple):
    """Parameters for the NO_H2 power system simulation."""

    # Storage
    initial_medium_storage_level: float
    medium_storage_capacity: float
    medium_storage_max_daily_energy: float
    medium_storage_efficiency: float
    # DAC
    dac_max_daily_energy: float
    # Gas CCS
    gas_ccs_max_daily_energy: float
    # Interconnect
    interconnect_imports: np.ndarray  # Daily available import capacity (TWh)
    # Gas DAC / E-DAC coefficients
    gas_dac_electricity_per_t: float  # MWh per tonne CO2
    gas_co2_intensity: float  # tCO2 per MWh gross electricity
    gas_dac_heat_per_t: float  # MWh heat per tonne CO2
    gas_electrical_efficiency: float  # fraction
    gas_waste_heat_fraction: float  # fraction
    gas_low_temperature_fraction: float  # fraction
    gas_tech_is_edac: bool


@numba.njit(cache=True)
def handle_deficit_no_h2(
    net_supply: float,
    prev_medium_storage: float,
    medium_storage_max_daily_energy: float,
    medium_storage_efficiency: float,
    gas_ccs_max_daily_energy: float,  # kept for signature consistency; unused in NO_H2 dispatch cap
    interconnect_import: float,
    gas_dac_electricity_per_t: float,
    gas_co2_intensity: float,
    gas_dac_heat_per_t: float,
    gas_electrical_efficiency: float,
    gas_waste_heat_fraction: float,
    gas_low_temperature_fraction: float,
    gas_tech_is_edac: bool,
) -> tuple[float, float, float, float, float, bool]:
    """Handle deficit without hydrogen: interconnect -> medium storage -> gas CCS (+ DAC/E-DAC)."""
    remaining_deficit = -net_supply
    medium_storage_level = prev_medium_storage
    gas_ccs_energy = 0.0
    interconnect_energy = 0.0
    gas_dac_electricity_twh = 0.0
    gas_dac_capture_mt = 0.0

    if remaining_deficit > 0 and interconnect_import > 0:
        interconnect_energy = min(remaining_deficit, interconnect_import)
        remaining_deficit -= interconnect_energy

    if remaining_deficit > 0 and prev_medium_storage > 0:
        available_from_medium = min(prev_medium_storage * medium_storage_efficiency, medium_storage_max_daily_energy)
        energy_from_medium = min(remaining_deficit, available_from_medium)
        energy_drawn_from_medium = energy_from_medium / medium_storage_efficiency
        medium_storage_level = prev_medium_storage - energy_drawn_from_medium
        if medium_storage_level < 0 and medium_storage_level > -FLOATING_POINT_TOLERANCE:
            medium_storage_level = 0.0
        remaining_deficit -= energy_from_medium

    if remaining_deficit > 0:
        # In NO_H2 mode, allow gas CCS to cover all remaining deficit (no daily cap)
        gas_ccs_energy = remaining_deficit
        remaining_deficit = 0.0

    if remaining_deficit > 0:
        return 0.0, 0.0, 0.0, 0.0, 0.0, True

    # DAC/E-DAC calculation based on gas CCS energy (gross electricity produced)
    if gas_ccs_energy > 0:
        gas_output_mwh = gas_ccs_energy * 1e6  # TWh -> MWh

        if gas_tech_is_edac:
            # Uncapped: allow net-negative capture, limited only by available electricity.
            capture_t = gas_output_mwh / gas_dac_electricity_per_t
        else:
            fuel_input_mwh = gas_output_mwh / gas_electrical_efficiency
            waste_heat_mwh = fuel_input_mwh * gas_waste_heat_fraction
            usable_heat_mwh = waste_heat_mwh * gas_low_temperature_fraction
            capture_t = usable_heat_mwh / gas_dac_heat_per_t

        gas_dac_electricity_twh = (capture_t * gas_dac_electricity_per_t) / 1e6
        gas_dac_capture_mt = capture_t / 1e6
        # Include DAC electricity in total gas CCS energy to reflect gross generation.
        gas_ccs_energy += gas_dac_electricity_twh

    return medium_storage_level, gas_ccs_energy, interconnect_energy, gas_dac_electricity_twh, gas_dac_capture_mt, False


@numba.njit(cache=True)
def handle_surplus_no_h2(
    net_supply: float,
    prev_medium_storage: float,
    max_medium_storage: float,
    medium_storage_max_daily_energy: float,
    medium_storage_efficiency: float,
) -> tuple[float, float, float]:
    """Handle surplus without hydrogen: medium storage then pass remainder to DAC/curtailment."""
    remaining_energy = net_supply
    medium_storage_level = prev_medium_storage
    energy_into_medium_storage = 0.0

    if remaining_energy > 0 and prev_medium_storage < max_medium_storage:
        available_medium_capacity = max_medium_storage - prev_medium_storage
        energy_into_medium_storage = min(remaining_energy, medium_storage_max_daily_energy, available_medium_capacity / medium_storage_efficiency)
        if energy_into_medium_storage > 0:
            actual_stored_medium = energy_into_medium_storage * medium_storage_efficiency
            medium_storage_level = prev_medium_storage + actual_stored_medium
            remaining_energy -= energy_into_medium_storage

    return medium_storage_level, energy_into_medium_storage, remaining_energy


@numba.njit(cache=True)
def handle_dac_simple(remaining_energy: float, max_dac: float) -> tuple[float, float]:
    """Allocate surplus to DAC up to capacity; remainder is curtailed."""
    dac_energy = remaining_energy if remaining_energy < max_dac else max_dac
    curtailed_energy = remaining_energy - dac_energy
    return dac_energy, curtailed_energy


@numba.njit(cache=True)
def simulate_power_system_core_no_h2(net_supply_values: np.ndarray, params: SimulationParameters) -> np.ndarray:
    """Core simulation for NO_H2 mode with DAC/E-DAC on gas CCS."""
    n_timesteps = len(net_supply_values)
    results = np.zeros((n_timesteps, 8))  # [medium, dac, curtailed, into_medium, gas_ccs, interconnect, gas_dac_ele, gas_dac_cap]

    max_medium_storage = params.medium_storage_capacity
    medium_storage_max_daily_energy = params.medium_storage_max_daily_energy
    medium_storage_efficiency = params.medium_storage_efficiency
    max_dac = params.dac_max_daily_energy
    gas_ccs_max_daily_energy = params.gas_ccs_max_daily_energy
    interconnect_imports = params.interconnect_imports

    gas_dac_electricity_per_t = params.gas_dac_electricity_per_t
    gas_co2_intensity = params.gas_co2_intensity
    gas_dac_heat_per_t = params.gas_dac_heat_per_t
    gas_electrical_efficiency = params.gas_electrical_efficiency
    gas_waste_heat_fraction = params.gas_waste_heat_fraction
    gas_low_temperature_fraction = params.gas_low_temperature_fraction
    gas_tech_is_edac = params.gas_tech_is_edac

    prev_medium_storage = params.initial_medium_storage_level

    for i in range(n_timesteps):
        net_supply = net_supply_values[i]
        gas_dac_electricity = 0.0
        gas_dac_capture = 0.0

        if net_supply <= 0:
            (
                medium_storage_level,
                gas_ccs_energy,
                interconnect_energy,
                gas_dac_electricity,
                gas_dac_capture,
                simulation_failed,
            ) = handle_deficit_no_h2(
                net_supply,
                prev_medium_storage,
                medium_storage_max_daily_energy,
                medium_storage_efficiency,
                gas_ccs_max_daily_energy,
                interconnect_imports[i],
                gas_dac_electricity_per_t,
                gas_co2_intensity,
                gas_dac_heat_per_t,
                gas_electrical_efficiency,
                gas_waste_heat_fraction,
                gas_low_temperature_fraction,
                gas_tech_is_edac,
            )
            if simulation_failed:
                results[:] = np.nan
                return results

            dac_energy = 0.0
            curtailed_energy = 0.0
            energy_into_medium_storage = 0.0

        else:
            medium_storage_level, energy_into_medium_storage, remaining_energy = handle_surplus_no_h2(
                net_supply,
                prev_medium_storage,
                max_medium_storage,
                medium_storage_max_daily_energy,
                medium_storage_efficiency,
            )

            dac_energy, curtailed_energy = handle_dac_simple(remaining_energy, max_dac)
            gas_ccs_energy = 0.0
            interconnect_energy = 0.0

        results[i, 0] = medium_storage_level
        results[i, 1] = dac_energy
        results[i, 2] = curtailed_energy
        results[i, 3] = energy_into_medium_storage
        results[i, 4] = gas_ccs_energy
        results[i, 5] = interconnect_energy
        results[i, 6] = gas_dac_electricity
        results[i, 7] = gas_dac_capture

        prev_medium_storage = medium_storage_level

    return results
