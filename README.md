# UK Energy Modelling with CO2 Removal

A simple Python-based energy system model for simulating the UK's 2050 net-zero energy landscape.

## Overview

This model simulates the UK's future energy system using hourly/daily time series data with the following key capabilities:

- **Renewable generation** from wind and solar with realistic ERA5-based capacity factors
- **Multiple demand scenarios**: naive scaling, seasonal scenarios, and CCC CB7 projections
- **Energy storage systems** with configurable capacity, power and efficiency
- **Direct Air Capture (DAC)** integration for CO2 removal using excess capacity
- **Scenario costing**: system cost and energy cost calculations for modeled pathways

## Getting Started

Install dependencies using `uv`:

```bash
uv install
```

Run tests to ensure everything works:

```bash
uv run pytest
```

Check code style:

```bash
uv run ruff check .
uv run ruff format .
```

An example simulation run can be found below:

<img width="4534" height="1834" alt="image" src="https://github.com/user-attachments/assets/8e508380-4123-4db9-aacf-f4b38843b2ad" />

## Development Status

### Current Capabilities
- Core daily-resolution power system simulation over multi-decade weather and demand traces
- Multiple demand modelling approaches, including CCC CB7 and seasonal scaling
- Renewable supply modelling from ERA5 and Renewables.ninja capacity factors
- Hydrogen storage pathway with electrolyser charging and hydrogen generation limits
- Medium-term storage modelling alongside hydrogen storage
- Dispatchable low-carbon generation with gas + CCS
- Optional interconnector import modelling
- DAC integration, including electricity-driven DAC metrics and gas-linked DAC accounting
- Transmission and distribution losses (11.3% total)
- System cost and energy cost calculations for simulated scenarios
- Separate `PowerSystemNoH2` pathway for comparing non-hydrogen system designs
- Regression tests for the main power system and no-hydrogen variant

### Planned Enhancements
- Configurable initial storage levels for sensitivity testing
- Alternative operating modes for DAC and gas + CCS beyond surplus-only dispatch
- Hourly time resolution
- Interconnector cost integration and improved cost assumptions
- Automated cost optimisation
- Expanded emissions and removals coverage, including ERW and BECCS

See `todo.md` for detailed development roadmap.

## Data Sources

Historical weather data from ERA5, renewable capacity factors from Renewables.ninja, and demand projections from the CCC Seventh Carbon Budget. See [src/data/README.md](src/data/README.md) for complete data source documentation.

## Related Work

| Title | Author | Date | Type |
|:------|:--------|:-----|:-----|
| [Large-scale electricity storage](https://royalsociety.org/news-resources/projects/low-carbon-energy-programme/large-scale-electricity-storage/) | Royal Society | 2023 | Report |
| [UK-Energy-Modelling](https://github.com/samvanstroud/UK-Energy-Modelling) | Dr Sam Vanstroud | 2025 | Repository |
| [Exploration of Great Britain's Optimal Energy Supply Mixture and Energy Storage Scenarios Upon a Transition to Net-Zero](https://github.com/majmis1/Energy-Transition-Modelling) | Maj Mis | 2024 | Master's thesis |
| [Modelling the UK's 2050 Energy System with Carbon Dioxide Removal](https://github.com/RSuz1/UK-Energy-Model-with-CO2-Removal) | Rei Suzuki | 2025 | Master's thesis |
| [The Seventh Carbon Budget](https://www.theccc.org.uk/publication/the-seventh-carbon-budget/) | CCC | 2025 | Report |
| [Future Energy Scenarios (FES)](https://www.neso.energy/publications/future-energy-scenarios-fes) | NESO | 2025 | Report |
| [Net Zero Power and Hydrogen: Capacity Requirements for Flexibility (AFRY BID3)](https://www.theccc.org.uk/publication/net-zero-power-and-hydrogen-capacity-requirements-for-flexibility-afry/) | CCC | 2023 | Report |
| [Delivering a reliable decarbonised power system](https://www.theccc.org.uk/publication/delivering-a-reliable-decarbonised-power-system/) | CCC | 2023 | Report |
