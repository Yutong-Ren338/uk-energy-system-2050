import numpy as np
from config import ABSOLUTE_TOLERANCE, RELATIVE_TOLERANCE

import src.assumptions as A
from src.energy_costs import yearly_dac_energy_cost, yearly_dac_energy_cost_cumulative


def test_renewables_weighted_average_capacity_factor() -> None:
    """Test the weighted average capacity factor from assumptions."""
    expected_value = 0.2595
    actual_value = A.Renewables.AverageCapacityFactor
    assert np.isclose(actual_value, expected_value, rtol=RELATIVE_TOLERANCE, atol=ABSOLUTE_TOLERANCE)


def test_yearly_dac_energy_cost_low() -> None:
    """Test yearly DAC energy cost with low energy cost."""
    expected_value = 21.94
    actual_value = yearly_dac_energy_cost(A.CO2Emissions2050, A.DAC.EnergyCost.Low, 5.928)
    assert np.isclose(actual_value, expected_value, rtol=RELATIVE_TOLERANCE, atol=ABSOLUTE_TOLERANCE)


def test_yearly_dac_energy_cost_medium() -> None:
    """Test yearly DAC energy cost with medium energy cost."""
    expected_value = 43.53
    actual_value = yearly_dac_energy_cost(A.CO2Emissions2050, A.DAC.EnergyCost.Medium, 5.928)
    assert np.isclose(actual_value, expected_value, rtol=RELATIVE_TOLERANCE, atol=ABSOLUTE_TOLERANCE)


def test_yearly_dac_energy_cost_cumulative() -> None:
    """Test cumulative yearly DAC energy cost."""
    expected_value = 220.1
    actual_value = yearly_dac_energy_cost_cumulative(A.TotalCO2EmissionsCap19902100, A.DAC.EnergyCost.Low, 2964, 50)
    assert np.isclose(actual_value, expected_value, rtol=RELATIVE_TOLERANCE, atol=ABSOLUTE_TOLERANCE)
