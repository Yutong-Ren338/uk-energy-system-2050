import tempfile
from pathlib import Path

import pandas as pd
import pytest

from src.data.scrape_gas_demand import preprocess_gas_data, scrape_uk_gas_data


class TestGasDataScraping:
    """Test suite for gas data scraping and preprocessing functions."""

    @pytest.fixture(autouse=True)
    def setup_temp_dir(self) -> None:
        """Set up test fixtures with temporary directories."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

    def test_scrape_uk_gas_data_actual_api(self) -> None:
        """Test scraping gas data from actual API with a small date range."""
        # Use a small date range to minimize API load
        date_from = "2024-01-01"
        date_to = "2024-01-02"
        output_file = self.temp_path / "test_gas_data.csv"

        # Call the scraping function
        scrape_uk_gas_data(date_from, date_to, str(output_file))

        # Verify file was created
        assert output_file.exists()

        # Verify file has content
        assert output_file.stat().st_size > 0

        # Verify it's a valid CSV by reading it
        df = pd.read_csv(output_file)
        assert len(df) > 0

        # Check expected columns exist in the raw data
        expected_columns = ["Applicable For", "Data Item", "Value"]
        for col in expected_columns:
            assert col in df.columns

    def test_preprocess_gas_data(self) -> None:
        """Test preprocessing of gas data after scraping."""
        # First scrape some data
        date_from = "2024-01-01"
        date_to = "2024-01-02"
        raw_file = self.temp_path / "raw_gas_data.csv"
        processed_file = self.temp_path / "processed_gas_data.csv"

        # Scrape data
        scrape_uk_gas_data(date_from, date_to, str(raw_file))

        # Preprocess data
        preprocess_gas_data(str(raw_file), str(processed_file))

        # Verify processed file was created
        assert processed_file.exists()

        # Read and verify processed data
        df_processed = pd.read_csv(processed_file)

        # Check columns were renamed correctly
        expected_columns = ["date", "use", "demand (TWh)"]
        for col in expected_columns:
            assert col in df_processed.columns

        # Verify data types
        # Parse date column to verify it can be converted to datetime
        df_processed["date"] = pd.to_datetime(df_processed["date"])
        assert pd.api.types.is_datetime64_any_dtype(df_processed["date"])
        assert pd.api.types.is_numeric_dtype(df_processed["demand (TWh)"])

        # Verify demand values are reasonable (converted from kWh to TWh)
        # Should be small positive numbers after conversion
        max_expected_demand = 1000  # TWh - sanity check
        assert (df_processed["demand (TWh)"] >= 0).all()
        assert (df_processed["demand (TWh)"] < max_expected_demand).all()

    def test_full_pipeline(self) -> None:
        """Test the complete pipeline from scraping to preprocessing."""
        date_from = "2024-01-01"
        date_to = "2024-01-01"  # Single day to minimize API load
        raw_file = self.temp_path / "pipeline_raw.csv"
        processed_file = self.temp_path / "pipeline_processed.csv"

        # Run full pipeline
        scrape_uk_gas_data(date_from, date_to, str(raw_file))
        preprocess_gas_data(str(raw_file), str(processed_file))

        # Verify both files exist
        assert raw_file.exists()
        assert processed_file.exists()

        # Compare raw and processed data
        df_raw = pd.read_csv(raw_file)
        df_processed = pd.read_csv(processed_file)

        # Should have same number of rows
        assert len(df_raw) == len(df_processed)

        # Processed data should have converted units (much smaller values)
        raw_values = df_raw["Value"].mean()
        processed_values = df_processed["demand (TWh)"].mean()
        assert processed_values < raw_values / 1e6  # Should be much smaller after conversion

    def test_api_error_handling(self) -> None:
        """Test error handling for invalid API requests."""
        # Use invalid date format to trigger error
        invalid_date_from = "invalid-date"
        invalid_date_to = "2024-01-01"
        output_file = self.temp_path / "error_test.csv"

        # Should raise RuntimeError
        with pytest.raises(RuntimeError):
            scrape_uk_gas_data(invalid_date_from, invalid_date_to, str(output_file))
