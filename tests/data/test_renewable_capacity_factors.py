import matplotlib.pyplot as plt
import pandas as pd
import pytest

from src.data.renewable_capacity_factors import get_renewable_capacity_factors
from tests.config import IN_CI, OUTPUT_DIR

OUTPUT_PATH = OUTPUT_DIR / "data" / "renewable_capacity_factors"
OUTPUT_PATH.mkdir(parents=True, exist_ok=True)


def test_get_renewable_capacity_factors() -> None:
    """Test that the function loads and combines PV and wind data correctly."""
    result = get_renewable_capacity_factors(resample=None)

    # Check that data was loaded correctly
    assert "solar" in result.columns
    assert "wind" in result.columns
    assert len(result) > 0

    # Check that all values are between 0 and 1 (valid capacity factors)
    assert (result["solar"] >= 0).all()
    assert (result["solar"] <= 1).all()
    assert (result["wind"] >= 0).all()
    assert (result["wind"] <= 1).all()

    # Check that units are applied
    assert str(result.dtypes["solar"]).startswith("pint")
    assert str(result.dtypes["wind"]).startswith("pint")

    # Check that index is datetime
    assert isinstance(result.index, pd.DatetimeIndex)


def test_get_renewable_capacity_factors_resampling() -> None:
    """Test that the function applies resampling when rule is provided."""
    # Get original hourly data
    hourly_result = get_renewable_capacity_factors(resample=None)

    # Get daily resampled data
    daily_result = get_renewable_capacity_factors(resample="D")

    # Daily data should have fewer rows than hourly
    assert len(daily_result) < len(hourly_result)

    # Check that resampled data still has valid capacity factors
    assert (daily_result["solar"] >= 0).all()
    assert (daily_result["solar"] <= 1).all()
    assert (daily_result["wind"] >= 0).all()
    assert (daily_result["wind"] <= 1).all()

    # Check that units are preserved
    assert str(daily_result.dtypes["solar"]).startswith("pint")
    assert str(daily_result.dtypes["wind"]).startswith("pint")

    # Check that index frequency matches resampling rule
    assert daily_result.index.freq == pd.Timedelta(days=1)  # type: ignore[possibly-unbound-attribute]


@pytest.mark.skipif(IN_CI, reason="Skip in CI")
@pytest.mark.parametrize("generation_type", ["solar", "onshore", "offshore"])
def test_plot_all_three(generation_type: str) -> None:
    plt.figure()
    for source in ["era5_2021", "era5_2024", "renewable_ninja"]:
        df = get_renewable_capacity_factors(source=source, resample="ME")[[generation_type]]
        plt.plot(df[generation_type], label=source)
        plt.ylabel("Capacity Factor")
        plt.ylim(0, 1)
        plt.xlabel("Date")
        plt.legend()
    plt.savefig(OUTPUT_PATH / f"capacity_factors_{generation_type}.png")
    plt.close()
