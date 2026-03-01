"""This module needs to be updated to use pint units."""

from pint import Quantity

import src.assumptions as A


def yearly_dac_energy_cost(mt_co2: float, energy_cost: Quantity, storage_energy_cost: float) -> float:
    """Calculate the total energy cost for Direct Air Capture (DAC).

    Calculates cost based on the amount of CO2 in Mt and the energy cost.

    Args:
        mt_co2: Amount of CO2 in megatons.
        energy_cost: Energy cost in kJ/mol CO2.
        storage_energy_cost: Additional storage energy cost in TWh.

    Returns:
        Total energy cost in TWh.
    """
    # Convert Mt CO2 to grams
    grams_co2 = mt_co2 * 1e6 * 1e6  # Mt -> t -> g

    # Convert grams to moles
    mol_co2 = grams_co2 / A.MolecularWeightCO2.magnitude

    # Calculate total energy in kJ
    total_energy_kj = mol_co2 * energy_cost.magnitude

    # Convert kJ to TWh (1 TWh = 3.6e12 kJ)
    total_energy_twh = total_energy_kj / 3.6e12

    return total_energy_twh + storage_energy_cost


def yearly_dac_energy_cost_cumulative(cum_mt_co2: float, energy_cost: Quantity, storage_energy_cost: float, num_years: int) -> float:
    """Calculate the cumulative energy cost for Direct Air Capture (DAC) over a number of years.

    Args:
        cum_mt_co2: Cumulative amount of CO2 in megatons.
        energy_cost: Energy cost in kJ/mol CO2.
        storage_energy_cost: Additional storage energy cost in TWh.
        num_years: Number of years over which the cost is calculated.

    Returns:
        Cumulative energy cost in TWh.
    """
    return yearly_dac_energy_cost(cum_mt_co2, energy_cost, storage_energy_cost) / num_years
