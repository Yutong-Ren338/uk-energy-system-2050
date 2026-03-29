### Data Sources

To scrape the latest gas data, run:

```shell
uv run src/data/scrape_gas_demand.py
```

### Local datasets in use

| Local path / dataset | Use in model | Upstream source | Link |
|:---------------------|:-------------|:----------------|:-----|
| `data/espeni.csv` | Historical GB electricity demand benchmark | University of Birmingham | [Dataset](https://zenodo.org/records/4739408) |
| `data/ERA5_full_demand_UK_1979_2019_hourly.csv` | Historical UK electricity demand | University of Reading | [Dataset](https://researchdata.reading.ac.uk/272/) |
| `data/ERA5_weather_dependent_demand_UK_1979_2019_hourly.csv` | Weather-adjusted historical UK electricity demand | University of Reading | [Dataset](https://researchdata.reading.ac.uk/272/) |
| `data/ERA5_HDD_all_countries_1979_2019_inclusive.csv` | Heating degree days used in seasonal demand scaling | University of Reading | [Dataset](https://researchdata.reading.ac.uk/272/) |
| `data/ccc_daily_demand_2050.csv` | Daily 2050 electricity demand target series | CCC CB7 | [Report](https://www.theccc.org.uk/publication/the-seventh-carbon-budget/) |
| `data/The-Seventh-Carbon-Budget-full-dataset.xlsx` | CB7 assumptions and demand inputs | CCC CB7 | [Report](https://www.theccc.org.uk/publication/the-seventh-carbon-budget/) |
| `data/The-Seventh-Carbon-Budget-methodology-accompanying-data.xlsx` | Hourly electricity demand inputs and methodology data | CCC CB7 | [Methodology Report](https://www.theccc.org.uk/publication/methodology-report-uk-northern-ireland-wales-and-scotland-carbon-budget-advice/) |
| `data/ninja_pv_country_GB_merra-2_corrected.csv` and `data/ninja_wind_country_GB_current-merra-2_corrected.csv` | Legacy GB Renewables.ninja capacity factors | Renewables.ninja | [Website](https://www.renewables.ninja/) |
| `data/ninja_2025/ninja-pv-country-GB-national-merra2.csv` | New future GB solar capacity factor series | Renewables.ninja | [Website](https://www.renewables.ninja/) |
| `data/ninja_2025/ninja-wind-country-GB-future_onshore-merra2.csv` | New future GB onshore wind capacity factors, including regional selections | Renewables.ninja | [Website](https://www.renewables.ninja/) |
| `data/ninja_2025/ninja-wind-country-GB-future_offshore-merra2.csv` | New future GB offshore wind capacity factors, including regional selections | Renewables.ninja | [Website](https://www.renewables.ninja/) |
| `data/ERA5_2021/` | Legacy ERA5 renewable/weather dataset for UK and peer-country comparisons | ERA5 2021 | [Dataset](https://doi.org/10.17864/1947.000321) |
| `data/ERA5_2024/solar_capacity_factor/` and `data/ERA5_2024/wind_capacity_factor/` | New ERA5-based country-level solar/onshore/offshore capacity factors used for UK runs and interconnector-country import availability | ERA5 2024 | [Dataset](https://doi.org/10.5281/zenodo.12634069) |
| `data/UK_gas_demand.csv` and `data/UK_gas_demand_processed.csv` | Raw and processed UK gas demand for heat seasonality work | NTS / repo scrape workflow | [Website](https://data.nationalgas.com/) |

### How to obtain the datasets

Most of the actual data files are not bundled in the GitHub repo. They are ignored by git because they are large, derived from third-party sources, or downloaded separately for local analysis.

Use the table above as the source-of-truth for what the code expects locally under `data/`.

- `espeni.csv`: download the ESPENI dataset from the University of Birmingham Zenodo page, then place the CSV in `data/`.
- `ERA5_full_demand_UK_1979_2019_hourly.csv`, `ERA5_weather_dependent_demand_UK_1979_2019_hourly.csv`, and `ERA5_HDD_all_countries_1979_2019_inclusive.csv`: obtain these from the University of Reading ERA5-derived demand dataset and place them in `data/`.
- `ccc_daily_demand_2050.csv`, `The-Seventh-Carbon-Budget-full-dataset.xlsx`, and the CB7 methodology workbook: extract or export these from the CCC Seventh Carbon Budget material, then place them in `data/`.
- Legacy Renewables.ninja files: download the GB solar and wind exports and save them as `data/ninja_pv_country_GB_merra-2_corrected.csv` and `data/ninja_wind_country_GB_current-merra-2_corrected.csv`.
- `data/ninja_2025/`: create this directory locally and place the newer Renewables.ninja files in it:
  `ninja-pv-country-GB-national-merra2.csv`, `ninja-wind-country-GB-future_onshore-merra2.csv`, and `ninja-wind-country-GB-future_offshore-merra2.csv`.
- `data/ERA5_2021/` and `data/ERA5_2024/`: download and unpack the cited ERA5 archives so the folder structure matches what the loaders expect.
- `UK_gas_demand.csv` / `UK_gas_demand_processed.csv`: either place existing local copies in `data/` or regenerate them via:

```shell
uv run src/data/scrape_gas_demand.py
```

If a loader raises a file-not-found error, check that the expected filename and directory structure exactly match the paths listed above.

### Original source references

| Source | Use | Link |
|:-------|:----|:-----|
| University of Birmingham | ESPENI: Electrical half hourly raw and cleaned datasets for Great Britain from 2009-11-05 | [Dataset](https://zenodo.org/records/4739408) |
| University of Reading | ERA5 derived time series of European country-aggregate electricity demand, wind power generation and solar power generation | [Dataset](https://researchdata.reading.ac.uk/272/) |
| Renewables.ninja | Renewable capacity factors, including legacy GB data and newer future/regional GB wind datasets | [Website](https://www.renewables.ninja/) |
| GitHub (benmcwilliams) | Daily gas demand data workflow that this repo rescrapes and processes | [Repository](https://github.com/benmcwilliams/gas-demand) |
| NTS | National Transmission System gas demand data | [Website](https://data.nationalgas.com/) |
| CCC CB7 | Various assumptions including 2050 demand | [Report](https://www.theccc.org.uk/publication/the-seventh-carbon-budget/) |
| CCC CB7 | Hourly electricity demand data | [Methodology Report](https://www.theccc.org.uk/publication/methodology-report-uk-northern-ireland-wales-and-scotland-carbon-budget-advice/) |
| ERA5 2021 | Meteorological data (1950-2020) | [Dataset](https://doi.org/10.17864/1947.000321) |
| ERA5 2024 | Meteorological data (1940-2023) | [Dataset](https://doi.org/10.5281/zenodo.12634069) |
