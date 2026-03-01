import matplotlib.pyplot as plt
import pandas as pd
import pytest

from src import matplotlib_style  # noqa: F401
from src.data.era5 import get_2021_data, get_2024_data
from tests.config import IN_CI, OUTPUT_DIR

OUTPUT_PATH = OUTPUT_DIR / "data" / "capacity_factors"
OUTPUT_PATH.mkdir(parents=True, exist_ok=True)


def _make_plot(df_a: pd.DataFrame, df_b: pd.DataFrame, title: str, ylabel: str, output_filename: str) -> None:
    # get the intersection of the two dataframes
    common_index = df_a.index.intersection(df_b.index)
    n = max(int(len(common_index) * 0.1), 100)
    df_a = df_a.loc[common_index].iloc[:n]
    df_b = df_b.loc[common_index].iloc[:n]

    plt.figure(figsize=(10, 5))
    plt.plot(df_a.index, df_a["capacity_factor"], label="2024", color="orange")
    plt.plot(df_b.index, df_b["capacity_factor"], label="2021", color="blue")
    plt.title(title)
    plt.xlabel("Time")
    plt.ylabel(ylabel)
    plt.legend()
    plt.savefig(OUTPUT_PATH / output_filename)
    plt.close()


@pytest.mark.skipif(IN_CI, reason="Skip in CI")
@pytest.mark.parametrize("generation_type", ["solar", "onshore_wind", "offshore_wind"])
def test_get_2024_data(generation_type: str) -> None:
    df = get_2024_data(generation_type=generation_type, country="UK")
    assert not df.empty
    assert "capacity_factor" in df.columns
    assert (df["capacity_factor"] >= 0).all()
    assert (df["capacity_factor"] <= 1).all()
    assert isinstance(df.index, pd.DatetimeIndex)
    assert df.index.dtype == "datetime64[ns]"
    assert not df.index.has_duplicates


@pytest.mark.skipif(IN_CI, reason="Skip in CI")
@pytest.mark.parametrize("generation_type", ["solar", "onshore_wind", "offshore_wind"])
def test_get_2021_data(generation_type: str) -> None:
    df = get_2021_data(generation_type=generation_type, country="UK")
    assert not df.empty
    assert "capacity_factor" in df.columns
    assert (df["capacity_factor"] >= 0).all()
    assert (df["capacity_factor"] <= 1).all()
    assert isinstance(df.index, pd.DatetimeIndex)
    assert df.index.dtype == "datetime64[ns]"
    assert not df.index.has_duplicates


@pytest.mark.skipif(IN_CI, reason="Skip in CI")
@pytest.mark.parametrize("resample", [None, "D", "ME", "YE"])
def test_compare_solar_capacity_factors(resample: str | None) -> None:
    df_a = get_2024_data(generation_type="solar", country="UK", resample=resample)
    df_b = get_2021_data(generation_type="solar", country="UK", resample=resample)

    _make_plot(df_a, df_b, "Solar Capacity Factor", "Capacity Factor", f"solar_capacity_factors_{resample}.png")


@pytest.mark.skipif(IN_CI, reason="Skip in CI")
@pytest.mark.parametrize("resample", [None, "D", "ME", "YE"])
def test_compare_onshore_wind_capacity_factors(resample: str | None) -> None:
    df_a = get_2024_data(generation_type="onshore_wind", country="UK", resample=resample)
    df_b = get_2021_data(generation_type="onshore_wind", country="UK", resample=resample)

    _make_plot(df_a, df_b, "Onshore Wind Capacity Factor", "Capacity Factor", f"onshore_wind_capacity_factors_{resample}.png")


@pytest.mark.skipif(IN_CI, reason="Skip in CI")
@pytest.mark.parametrize("resample", [None, "D", "ME", "YE"])
def test_compare_offshore_wind_capacity_factors(resample: str | None) -> None:
    df_a = get_2024_data(generation_type="offshore_wind", country="UK", resample=resample)
    df_b = get_2021_data(generation_type="offshore_wind", country="UK", resample=resample)

    _make_plot(df_a, df_b, "Offshore Wind Capacity Factor", "Capacity Factor", f"offshore_wind_capacity_factors_{resample}.png")
