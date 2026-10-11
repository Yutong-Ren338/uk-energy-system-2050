from pathlib import Path

import pytest

from src.data import cb7, historical_demand, renewable_capacity_factors


@pytest.fixture(autouse=True)
def use_compact_test_data(monkeypatch: pytest.MonkeyPatch) -> None:
    """Run tests against compact, versioned fixtures instead of full datasets."""
    fixture_data_dir = Path(__file__).parent / "fixtures" / "data"
    monkeypatch.setattr(cb7, "DATA_DIR", fixture_data_dir)
    monkeypatch.setattr(historical_demand, "DATA_DIR", fixture_data_dir)
    monkeypatch.setattr(renewable_capacity_factors, "DATA_DIR", fixture_data_dir)
