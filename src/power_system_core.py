# ruff: noqa: PLR0913, PLR0917, FBT001
from typing import NamedTuple

import numba
import numpy as np

# Power System Model
# Models renewable energy generation, storage systems, demand response, and excess energy allocation
# Includes energy storage, Direct Air Capture (DAC), and curtailment strategies

# Floating point precision tolerance for residual energy calculations
FLOATING_POINT_TOLERANCE = 1e-10


class SimulationParameters(NamedTuple):
    """Parameters for the core power system simulation."""

    initial_hydrogen_storage_level: float
    hydrogen_storage_capacity: float
    electrolyser_max_daily_energy: float
    hydrogen_generation_max_daily_energy: float
    dac_max_daily_energy: float
    hydrogen_e_in: float
    hydrogen_e_out: float
    only_dac_if_hydrogen_storage_full: bool
    # Medium term storage parameters
    initial_medium_storage_level: float
    medium_storage_capacity: float
    medium_storage_max_daily_energy: float
    medium_storage_efficiency: float
    # Gas CCS parameters
    gas_ccs_max_daily_energy: float
    # Interconnect parameters
    interconnect_imports: np.ndarray  # Daily available import capacity


@numba.njit(cache=True)
def handle_deficit(
    net_supply: float,
    prev_medium_storage: float,
    prev_hydrogen_storage: float,
    medium_storage_max_daily_energy: float,
    medium_storage_efficiency: float,
    hydrogen_e_out: float,
    hydrogen_generation_max_daily_energy: float,
    gas_ccs_max_daily_energy: float,
    interconnect_import: float,
) -> tuple[float, float, float, float, bool]:
    """Handle energy deficit scenario by drawing from storage.

    Priority order: Medium-term storage first, then interconnect imports, then gas CCS, then hydrogen storage.

    Args:
        net_supply: Negative supply-demand value (deficit)
        prev_medium_storage: Previous medium-term storage level
        prev_hydrogen_storage: Previous hydrogen storage level
        medium_storage_max_daily_energy: Maximum daily energy capacity for medium storage (power * 24h)
        medium_storage_efficiency: Medium-term storage round-trip efficiency
        hydrogen_e_out: Hydrogen storage output efficiency
        hydrogen_generation_max_daily_energy: Maximum daily energy that can be generated from hydrogen.
        gas_ccs_max_daily_energy: Maximum daily energy capacity for gas CCS
        interconnect_import: Available import capacity for this day in TWh

    Returns:
        Tuple of (new_medium_storage_level, new_hydrogen_storage_level, gas_ccs_energy, interconnect_energy, simulation_failed)
    """
    remaining_deficit = -net_supply
    medium_storage_level = prev_medium_storage
    hydrogen_storage_level = prev_hydrogen_storage
    gas_ccs_energy = 0.0
    interconnect_energy = 0.0

    # Try to meet remaining deficit from interconnect imports
    if remaining_deficit > 0 and interconnect_import > 0:
        interconnect_energy = min(remaining_deficit, interconnect_import)
        remaining_deficit -= interconnect_energy

    # Try to meet deficit from medium-term storage
    if remaining_deficit > 0 and prev_medium_storage > 0:
        # Available energy from medium storage (considering efficiency and power constraints)
        available_from_medium = min(prev_medium_storage * medium_storage_efficiency, medium_storage_max_daily_energy)
        energy_from_medium = min(remaining_deficit, available_from_medium)

        # Update medium storage level (accounting for efficiency)
        energy_drawn_from_medium = energy_from_medium / medium_storage_efficiency
        medium_storage_level = prev_medium_storage - energy_drawn_from_medium

        # Fix small negative values due to floating point precision errors
        if medium_storage_level < 0 and medium_storage_level > -FLOATING_POINT_TOLERANCE:
            medium_storage_level = 0.0

        remaining_deficit -= energy_from_medium

    # Try to meet remaining deficit from gas CCS
    if remaining_deficit > 0:
        gas_ccs_energy = min(remaining_deficit, gas_ccs_max_daily_energy)
        remaining_deficit -= gas_ccs_energy

    # If deficit still remains, use hydrogen storage
    if remaining_deficit > 0 and prev_hydrogen_storage > 0:
        # Available energy from hydrogen (considering efficiency and power constraints)
        available_from_hydrogen = min(prev_hydrogen_storage * hydrogen_e_out, hydrogen_generation_max_daily_energy)
        energy_from_hydrogen = min(remaining_deficit, available_from_hydrogen)

        # Draw from hydrogen storage
        energy_drawn_from_hydrogen = energy_from_hydrogen / hydrogen_e_out
        hydrogen_storage_level = prev_hydrogen_storage - energy_drawn_from_hydrogen
        if hydrogen_storage_level < 0 and hydrogen_storage_level > -FLOATING_POINT_TOLERANCE:
            hydrogen_storage_level = 0.0

        remaining_deficit -= energy_from_hydrogen

    # Check if deficit was fully met
    if remaining_deficit > 0:
        # Not enough storage to meet demand - simulation failed
        return 0.0, 0.0, 0.0, 0.0, True

    return medium_storage_level, hydrogen_storage_level, gas_ccs_energy, interconnect_energy, False


@numba.njit(cache=True)
def handle_dac(
    remaining_energy: float,
    hydrogen_storage_level: float,
    max_hydrogen_storage: float,
    max_dac: float,
    only_dac_if_storage_full: bool,
) -> tuple[float, float]:
    """Handle DAC energy allocation and curtailment calculations.

    Args:
        remaining_energy: Energy remaining after storage allocation
        hydrogen_storage_level: Current hydrogen storage level
        max_hydrogen_storage: Maximum hydrogen storage capacity
        max_dac: Maximum DAC daily energy capacity
        only_dac_if_storage_full: Energy allocation policy for DAC

    Returns:
        Tuple of (dac_energy, curtailed_energy)
    """
    # Check if DAC is allowed based on storage policy
    if only_dac_if_storage_full and hydrogen_storage_level < max_hydrogen_storage:
        # DAC not allowed - all remaining energy is curtailed
        return 0.0, remaining_energy

    # DAC is allowed - allocate up to DAC capacity
    dac_energy = min(remaining_energy, max_dac)
    curtailed_energy = remaining_energy - dac_energy

    return dac_energy, curtailed_energy


@numba.njit(cache=True)
def handle_surplus(
    net_supply: float,
    prev_medium_storage: float,
    prev_hydrogen_storage: float,
    max_medium_storage: float,
    max_hydrogen_storage: float,
    medium_storage_max_daily_energy: float,
    medium_storage_efficiency: float,
    max_electrolyser: float,
    hydrogen_e_in: float,
) -> tuple[float, float, float, float, float]:
    """Handle energy surplus allocation between storages and DAC.

    Energy allocation priority system:
    1. Medium-term storage (up to power and capacity limits)
    2. Hydrogen storage via electrolyser (up to electrolyser and capacity limits)
    3. Remaining energy passed to DAC handling

    Args:
        net_supply: Positive supply-demand value (surplus energy available)
        prev_medium_storage: Previous medium-term storage level
        prev_hydrogen_storage: Previous hydrogen storage level
        max_medium_storage: Maximum medium-term storage capacity
        max_hydrogen_storage: Maximum hydrogen storage capacity
        medium_storage_max_daily_energy: Maximum daily energy for medium storage (power * 24h)
        medium_storage_efficiency: Medium-term storage round-trip efficiency
        max_electrolyser: Maximum electrolyser daily energy capacity
        hydrogen_e_in: Hydrogen storage input efficiency

    Returns:
        Tuple of (medium_storage_level, hydrogen_storage_level,
                 energy_into_medium_storage, energy_into_hydrogen_storage,
                 remaining_energy)
    """
    remaining_energy = net_supply
    medium_storage_level = prev_medium_storage
    hydrogen_storage_level = prev_hydrogen_storage
    energy_into_medium_storage = 0.0
    energy_into_hydrogen_storage = 0.0

    # First priority: fill medium-term storage
    if remaining_energy > 0 and prev_medium_storage < max_medium_storage:
        available_medium_capacity = max_medium_storage - prev_medium_storage

        # Consider both power constraint and capacity constraint
        energy_into_medium_storage = min(remaining_energy, medium_storage_max_daily_energy, available_medium_capacity / medium_storage_efficiency)

        if energy_into_medium_storage > 0:
            # Account for storage efficiency
            actual_stored_medium = energy_into_medium_storage * medium_storage_efficiency
            medium_storage_level = prev_medium_storage + actual_stored_medium
            remaining_energy -= energy_into_medium_storage

    # Second priority: hydrogen storage via electrolyser
    if remaining_energy > 0 and prev_hydrogen_storage < max_hydrogen_storage:
        available_hydrogen_capacity = max_hydrogen_storage - prev_hydrogen_storage

        # Consider both electrolyser power constraint and storage capacity constraint
        energy_into_hydrogen_storage = min(remaining_energy, max_electrolyser, available_hydrogen_capacity / hydrogen_e_in)

        if energy_into_hydrogen_storage > 0:
            # Account for storage efficiency
            actual_stored_hydrogen = energy_into_hydrogen_storage * hydrogen_e_in
            hydrogen_storage_level = prev_hydrogen_storage + actual_stored_hydrogen
            remaining_energy -= energy_into_hydrogen_storage

    return (
        medium_storage_level,
        hydrogen_storage_level,
        energy_into_medium_storage,
        energy_into_hydrogen_storage,
        remaining_energy,
    )


@numba.njit(cache=True)
def simulate_power_system_core(net_supply_values: np.ndarray, params: SimulationParameters) -> np.ndarray:
    """Core simulation function optimized for Numba JIT compilation.

    Uses smaller specialized functions for different scenarios to improve readability
    while maintaining JIT performance.

    Args:
        net_supply_values: Array of supply-demand values for each timestep
        params: Simulation parameters

    Returns:
        Array of shape (n_timesteps, 8) containing:
        [medium_storage_level, hydrogen_storage_level, dac_energy,
         curtailed_energy, energy_into_medium_storage, energy_into_hydrogen_storage, gas_ccs_energy, interconnect_energy]
        Returns array filled with NaN values if simulation fails (storage hits zero).
    """
    n_timesteps = len(net_supply_values)
    results = np.zeros((n_timesteps, 8))  # Expanded to include interconnect energy

    # Extract ALL parameters to local variables
    max_hydrogen_storage = params.hydrogen_storage_capacity
    max_electrolyser = params.electrolyser_max_daily_energy
    hydrogen_generation_max_daily_energy = params.hydrogen_generation_max_daily_energy
    max_dac = params.dac_max_daily_energy
    hydrogen_e_in = params.hydrogen_e_in
    hydrogen_e_out = params.hydrogen_e_out
    only_dac_if_storage_full = params.only_dac_if_hydrogen_storage_full

    # Medium-term storage parameters
    max_medium_storage = params.medium_storage_capacity
    medium_storage_max_daily_energy = params.medium_storage_max_daily_energy
    medium_storage_efficiency = params.medium_storage_efficiency

    # Gas CCS parameters
    gas_ccs_max_daily_energy = params.gas_ccs_max_daily_energy

    # Interconnect parameters
    interconnect_imports = params.interconnect_imports

    prev_medium_storage = params.initial_medium_storage_level
    prev_hydrogen_storage = params.initial_hydrogen_storage_level

    for i in range(n_timesteps):
        net_supply = net_supply_values[i]

        if net_supply <= 0:
            # Energy shortage - draw from storage
            medium_storage_level, hydrogen_storage_level, gas_ccs_energy, interconnect_energy, simulation_failed = handle_deficit(
                net_supply,
                prev_medium_storage,
                prev_hydrogen_storage,
                medium_storage_max_daily_energy,
                medium_storage_efficiency,
                hydrogen_e_out,
                hydrogen_generation_max_daily_energy,
                gas_ccs_max_daily_energy,
                interconnect_imports[i],
            )
            if simulation_failed:
                results[:] = np.nan
                return results

            # Deficit scenario - all other values are zero
            dac_energy = curtailed_energy = 0.0
            energy_into_medium_storage = energy_into_hydrogen_storage = 0.0

        else:
            # Energy surplus - allocate to storages and DAC
            (
                medium_storage_level,
                hydrogen_storage_level,
                energy_into_medium_storage,
                energy_into_hydrogen_storage,
                remaining_energy,
            ) = handle_surplus(
                net_supply,
                prev_medium_storage,
                prev_hydrogen_storage,
                max_medium_storage,
                max_hydrogen_storage,
                medium_storage_max_daily_energy,
                medium_storage_efficiency,
                max_electrolyser,
                hydrogen_e_in,
            )

            # Handle DAC allocation and curtailment
            dac_energy, curtailed_energy = handle_dac(
                remaining_energy,
                hydrogen_storage_level,
                max_hydrogen_storage,
                max_dac,
                only_dac_if_storage_full,
            )

            # Surplus scenario - gas CCS and interconnect energy are zero
            gas_ccs_energy = 0.0
            interconnect_energy = 0.0

        # Direct array assignment is faster than list creation
        results[i, 0] = medium_storage_level
        results[i, 1] = hydrogen_storage_level
        results[i, 2] = dac_energy
        results[i, 3] = curtailed_energy
        results[i, 4] = energy_into_medium_storage
        results[i, 5] = energy_into_hydrogen_storage
        results[i, 6] = gas_ccs_energy
        results[i, 7] = interconnect_energy

        prev_medium_storage = medium_storage_level
        prev_hydrogen_storage = hydrogen_storage_level

    return results
