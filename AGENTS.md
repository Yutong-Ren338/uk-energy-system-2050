# UK Energy Modelling - AI Coding Agent Instructions

## Project Overview
This is a 2050 UK energy system model with CO2 removal capabilities. The system models renewable energy generation, storage, demand patterns, and Direct Air Capture (DAC) using hourly/daily time series data.

## Architecture & Core Components

### 1. Units System (Critical)
- **Always use `pint` units** - the codebase has strict unit checking via assertions
- Import units as `from src.units import Units as U`
- Example: `250 * U.GW`, `5.2 * U.TWh`, quantities have `.magnitude` and `.units`
- Functions expect specific units (e.g., renewable capacity in GW, storage in TWh)

### 2. Core Models Structure
- **`PowerSystemModel`**: Main simulation engine (`src/power_system_model.py`)
  - Takes renewable capacity, storage capacity, electrolyser power, DAC capacity
  - Runs timestep-by-timestep energy balance simulations
  - Returns storage levels, DAC energy, curtailed energy
- **`demand_model.py`**: Three demand scaling modes: "naive", "seasonal", "cb7"
  - `seasonal_demand_scaling()` accounts for heat pump electrification using gas seasonality
- **`supply_model.py`**: Renewable generation from capacity factors (solar/wind split)
- **`assumptions.py`**: Central parameter store - **reference this heavily**

### 3. Data Flow Pattern
```
Historical data (data/new/) → Demand/Supply models → PowerSystemModel → Analysis/Plotting
```

### 4. Key Import Patterns
- **Units**: `from src.units import Units as U`
- **Assumptions**: `import src.assumptions as A`
- **Models**: Import individual classes (e.g., `from src.power_system_model import PowerSystemModel`)
- **Plotting**: `import src.matplotlib_style` for consistent styling

## Development Workflow

### Dependencies & Testing
Project uses `uv` package manager. Key commands:

```bash
# Setup
uv install

# Run tests (critical - model has regression tests)
uv run pytest

# Linting
uv run ruff check --fix . && uv run ruff format .
```

Instead of manually fixing linting and formatting errors yourself, just run `ruff`.

### Key Testing Pattern
- Tests use `tests/config.py::check()` for floating-point comparisons
- Regression tests compare against documented expected values
- Run `uv run pytest` after changes

## Data Sources & Structure
- `data/new/`: CSV files with processed time series (ERA5 weather, CCC demand projections)
- `src/data/`: Data loading modules (e.g., `renewable_capacity_factors.py`, `historical_demand.py`)
- ERA5 weather data, CCC carbon budget scenarios, Renewables.ninja capacity factors
- Data preprocessing in `src/data/` modules handles unit conversions and resampling

## Key Conventions

### Parameter Management
- **Central assumptions**: All parameters live in `src/assumptions.py` with units
- Example: `A.HydrogenStorage.Electrolysis.Efficiency`, `A.EnergyDemand2050`
- Use nested classes for organization (e.g., `A.Renewables.CapacityRatios.Solar`)

### Simulation Results Analysis
- `PowerSystemModel.analyze_simulation_results()` returns standardized metrics
- Key outputs: minimum_storage, annual_dac_energy, dac_capacity_factor, curtailed_energy

### Time Series Handling
- Daily resolution is standard (converted from hourly via `resample("D")`)
- Index alignment critical: use `common_idx = df1.index.intersection(df2.index)`
- Energy calculations: power × 24h → daily energy (TWh)

## Common Pitfalls
- **Unit mismatches**: Always check `.units` before calculations
- **Index misalignment**: Time series operations require common indices  
- **Parameter updates**: Update `assumptions.py` rather than hardcoding values
- **Test regression**: Changes to model logic should update expected test values

## When Making Changes
1. Update parameters in `assumptions.py` with proper units
2. Run regression tests and update expected values if intentional
3. Check notebooks still execute without errors
4. Ensure plots/outputs are regenerated if analysis changes
5. Follow the coding style guidelines below

## Code Style
- Follow [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings) for docstrings
- Type hints in function signatures, not docstrings
- Trivial functions don't require docstrings
