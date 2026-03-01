from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import requests


def scrape_uk_gas_data(date_from: str, date_to: str, output_filename: str) -> None:
    """Scrape UK gas demand data from National Gas API.

    Args:
        date_from: Start date in 'YYYY-MM-DD' format
        date_to: End date in 'YYYY-MM-DD' format
        output_filename: Full path to the output CSV file

    Raises:
        RuntimeError: If the API request fails or returns an error status.
    """
    # Construct API URL
    url = f"https://data.nationalgas.com/api/find-gas-data-download?applicableFor=Y&dateFrom={date_from}&dateTo={date_to}&dateType=GASDAY&latestFlag=Y&ids=PUBOBJ1026,PUBOBJ1025,PUBOBJ1023&type=CSV"

    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.RequestException as e:
        msg = f"Failed to fetch data from API: {e}"
        raise RuntimeError(msg) from e

    # Create output directory
    Path(output_filename).parent.mkdir(parents=True, exist_ok=True)

    # Write data to file
    Path(output_filename).write_bytes(response.content)

    print(f"Data successfully scraped and saved to {output_filename}")


def preprocess_gas_data(input_filename: str, output_filename: str) -> None:
    """Preprocess the scraped gas demand CSV data.

    Keeps only 'Applicable For', 'Data Item', and 'Value' columns,
    and converts values from kWh to TWh by dividing by 10^9.
    If output file exists, appends new data and removes duplicates,
    keeping newer data for overlapping dates.

    Args:
        input_filename: Path to the input CSV file
        output_filename: Path to save the processed CSV file
    """
    # Read the CSV file
    df = pd.read_csv(input_filename)

    # Keep only the required columns
    columns_to_keep = ["Applicable For", "Data Item", "Value"]
    df_processed = df[columns_to_keep].copy()

    # Rename columns
    df_processed = df_processed.rename(columns={"Applicable For": "date", "Data Item": "use", "Value": "demand (TWh)"})

    # Convert demand from kWh to TWh
    df_processed["demand (TWh)"] /= 1e9

    # Covert 'date' to datetime
    df_processed["date"] = pd.to_datetime(df_processed["date"], dayfirst=True)

    # Prepend if output file already exists
    output_path = Path(output_filename)
    if output_path.exists():
        existing_df = pd.read_csv(output_filename)
        existing_df["date"] = pd.to_datetime(existing_df["date"])
        combined_df = pd.concat([df_processed, existing_df], ignore_index=True)
        df_processed = combined_df.drop_duplicates(subset=["date", "use"], keep="last")

    # Create output directory
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Save the processed data
    df_processed.to_csv(output_filename, index=False)

    print(f"Processed data saved to {output_filename}")


if __name__ == "__main__":
    # Set sensible default values
    current_file = Path(__file__).resolve()
    project_root = current_file.parents[2]
    date_from = "2020-01-01"
    date_to = datetime.now(tz=UTC).strftime("%Y-%m-%d")
    output_filename = project_root / "data" / "UK_gas_demand.csv"
    processed_filename = project_root / "data" / "UK_gas_demand_processed.csv"

    scrape_uk_gas_data(date_from, date_to, output_filename)
    preprocess_gas_data(output_filename, processed_filename)
