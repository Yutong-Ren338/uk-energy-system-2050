import pandas as pd
from pint import Quantity

from src.units import Units as U


def convert_energy_cost(energy_cost_per_mol: Quantity, molecular_weight: Quantity) -> Quantity:
    """Convert energy cost from kJ/mol to TWh/Mt.

    Uses the molecular weight of CO2.

    Args:
        energy_cost_per_mol: Energy cost in kJ/mol.
        molecular_weight: Molecular weight in g/mol.

    Returns:
        Energy cost in TWh/Mt.
    """
    assert energy_cost_per_mol.units == U.kJ / U.mol, "Input must be in kJ/mol"
    return (energy_cost_per_mol / molecular_weight).to(U.TWh / U.Mt)


def rolling_mean_circular(df: pd.DataFrame, column: str, window_size: int) -> pd.Series:
    """Apply a rolling mean with circular padding to a DataFrame column.

    This function applies circular padding by concatenating the end of the data
    to the beginning and the beginning to the end, then applies a centered
    rolling mean to smooth the data while maintaining the original length.

    Args:
        df: DataFrame containing the data.
        column: Column name to apply the rolling mean on.
        window_size: Size of the rolling window. Should be an odd number for proper centering.

    Returns:
        Series with the smoothed values, same length as the original data.
    """
    half_window = window_size // 2

    # Check if the column has pint units and store them
    units = None
    data = df[column]

    if "pint" in str(df[column].dtype):
        units = df[column].pint.units
        data = df[column].pint.magnitude

    # Apply rolling mean with circular padding
    data_padded = pd.concat([data.tail(half_window), data, data.head(half_window)]).reset_index(drop=True)
    result = data_padded.rolling(window=window_size, center=True).mean().iloc[half_window:-half_window]
    result.index = df.index

    # Convert back to pint quantity if original had units
    if units is not None:
        result = result.astype(f"pint[{units}]")

    return result


def annualised_cost(capex: float, opex: float, lifetime: int, discount_rate: float, efficiency: float = 1.0) -> float:
    """Calculate the annualised cost of a project.

    Calculates cost given its capital expenditure (capex), operational expenditure (opex),
    lifetime in years, and discount rate.

    Args:
        capex: Capital expenditure.
        opex: Annual operational expenditure.
        lifetime: Lifetime of the project in years.
        discount_rate: Discount rate as a decimal.
        efficiency: Efficiency factor for the project.

    Returns:
        Annualised cost.
    """
    assert 0 <= discount_rate < 1, "Discount rate must be between 0 and 1"
    assert lifetime > 0, "Lifetime must be greater than 0"
    assert 0 < efficiency <= 1, "Efficiency must be between 0 and 1"

    if discount_rate == 0:
        return capex / lifetime + opex

    annuity_factor = (1 - (1 + discount_rate) ** -lifetime) / discount_rate
    annualised_capex = capex / annuity_factor
    annualised_cost = annualised_capex + opex
    return annualised_cost / efficiency
