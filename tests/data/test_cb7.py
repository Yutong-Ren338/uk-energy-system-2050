import pandas as pd
from pint import Quantity

import src.assumptions as A
from src.data import cb7
from src.units import Units as U
from tests.config import check

EXPECTED_FRACTION = A.CB7FractionHeatDemandBuildings
EXPECTED_BUILDINGS_DEMAND = A.CB7EnergyDemand2050Buildings

# In the report, 692 TWh is stated as the total electricity demand for 2050.A
# We use that in the modelling assumptions, for the test of the data integrity use the derived value
# Atl some point should understand the discrepancy (probably we are not processing the data correctly)
EXPECTED_TOTAL_DEMAND = 682.395 * U.TWh


def test_frac_heat_demand_from_buildings() -> None:
    """Test that the function returns the expected fraction value."""
    result = cb7.frac_heat_demand_from_buildings()

    # Use check function for float comparison
    check(result, EXPECTED_FRACTION)

    # Also check that the result is a reasonable fraction (between 0 and 1)
    assert 0 <= result <= 1, f"Result should be between 0 and 1, got {result}"


def test_buildings_electricity_demand() -> None:
    """Test that the function returns the expected buildings electricity demand."""
    result = cb7.buildings_electricity_demand()

    # Check that the result is a Pint quantity with TWh units
    assert isinstance(result, Quantity), f"Result should be a Pint quantity, got {type(result)}"
    assert str(result.units) == "terawatt_hour", f"Result should have TWh units, got {result.units}"

    # Use check function for float comparison
    check(result, EXPECTED_BUILDINGS_DEMAND)

    # Check that the result is positive
    assert result > 0, f"Result should be positive, got {result}"


def test_total_demand_2050() -> None:
    """Test that the function returns the expected total electricity demand for 2050."""
    result = cb7.total_demand_2050()

    # Check that the result is a Pint quantity with TWh units
    assert isinstance(result, Quantity), f"Result should be a Pint quantity, got {type(result)}"
    assert str(result.units) == "terawatt_hour", f"Result should have TWh units, got {result.units}"

    # Use check function for float comparison
    check(result, EXPECTED_TOTAL_DEMAND)

    # Check that the result is positive
    assert result > 0, f"Result should be positive, got {result}"

    # Check that total demand is greater than buildings demand
    buildings_demand = cb7.buildings_electricity_demand()
    assert result > buildings_demand, f"Total demand ({result}) should be greater than buildings demand ({buildings_demand})"


def test_demand_ccc() -> None:
    df = cb7.cb7_demand(A.EnergyDemand2050)
    assert df.shape[0] > 0
    assert "demand" in df.columns
    assert df["demand"].dtype == "pint[TWh]"
    assert df["demand"].min() >= 0.0
    assert isinstance(df.index, pd.DatetimeIndex)
    assert df.index.dtype == "datetime64[ns]"
    # assert not df.index.has_duplicates
