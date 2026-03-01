### Data Sources

To scrape the latest gas data, run:

```shell
uv run src/data/scrape_gas_demand.py
```

| Source | Use | Link |
|:-------|:----|:-----|
| University of Birmingham | ESPENI: Electrical half hourly raw and cleaned datasets for Great Britain from 2009-11-05 | [Dataset](https://zenodo.org/records/4739408) |
| University of Reading | ERA5 derived time series of European country-aggregate electricity demand, wind power generation and solar power generation | [Dataset](https://researchdata.reading.ac.uk/272/) |
| Renewables.ninja | Renewable capacity factors. Includes breakdown by onshore and offshore wind which is not included in the ERA5 dataset | [Website](https://www.renewables.ninja/) |
| GitHub (benmcwilliams) | Daily gas demand data (this is being rescraped in this repo) | [Repository](https://github.com/benmcwilliams/gas-demand) |
| NTS | National Transmission System gas demand data | [Website](https://data.nationalgas.com/) |
| CCC CB7 | Various assumptions including 2050 demand | [Report](https://www.theccc.org.uk/publication/the-seventh-carbon-budget/) |
| CCC CB7 | Hourly electricity demand data | [Methodology Report](https://www.theccc.org.uk/publication/methodology-report-uk-northern-ireland-wales-and-scotland-carbon-budget-advice/) |
| ERA5 2021 | Meteorological data (1950-2020) | [Dataset](https://doi.org/10.17864/1947.000321) |
| ERA5 2024 | Meteorological data (1940-2023) | [Dataset](https://doi.org/10.5281/zenodo.12634069) |