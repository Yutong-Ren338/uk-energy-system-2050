"""Optimise a zero E-DAC power system without modifying the core model."""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import src.assumptions as A
from src.costs import total_system_cost
from src.data import renewable_capacity_factors
from src.demand_model import DemandMode, predicted_demand
from src.lcoe import renewables_2050_lcoe
from src.power_system import PowerSystem
from src.supply_model import get_available_imports
from src.units import Units as U

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure
    from pint import Quantity

    from src.data.renewable_capacity_factors import CapacityFactorSource


DEFAULT_OUTPUT_DIR = Path("output/zero_dac_optimisation")
_DAYS_PER_MODEL_YEAR = 365.0
_HOURS_PER_DAY = 24.0
_TWH_PER_GW_DAY = 0.024
_FLOAT_TOLERANCE = 1e-9
_IMPORT_ALLOCATION_TOLERANCE_TWH = 1e-7
_MINIMUM_CYCLE_ITERATIONS = 2

_TECHNOLOGIES: dict[str, tuple[str, float]] = {
    "Large Scale Solar PV": ("solar", A.Renewables.CapacityRatios.Solar),
    "Fixed Offshore Wind": ("offshore", A.Renewables.CapacityRatios.OffshoreWind),
    "Onshore Wind": ("onshore", A.Renewables.CapacityRatios.OnshoreWind),
}


@dataclass(frozen=True)
class OptimisationConfig:
    """Configuration for a zero E-DAC capacity optimisation."""

    demand_mode: DemandMode = DemandMode.SEASONAL
    capacity_factors_source: CapacityFactorSource = "era5_2024"
    enable_nuclear: bool = True
    enable_gas_ccs: bool = False
    enable_medium_storage: bool = False
    enable_imports: bool = False
    reserve_twh: float = 20.0
    renewable_min_gw: float = 220.0
    renewable_max_gw: float = 500.0
    coarse_renewable_step_gw: float = 10.0
    electrolyser_min_gw: float = 20.0
    electrolyser_max_gw: float = 160.0
    coarse_electrolyser_step_gw: float = 5.0
    fine_renewable_span_gw: float = 10.0
    fine_electrolyser_span_gw: float = 10.0
    fine_renewable_step_gw: float = 1.0
    fine_electrolyser_step_gw: float = 1.0
    storage_max_twh: float = 500.0
    storage_tolerance_twh: float = 0.1
    cycle_tolerance_twh: float = 0.01
    max_cycle_iterations: int = 20
    hydrogen_generation_resolution_gw: float = 0.1
    verbose: bool = True

    def validate(self) -> None:
        """Raise a useful error when search settings are inconsistent.

        Raises:
            ValueError: If any search setting is internally inconsistent.
        """
        positive_values = {
            "reserve_twh": self.reserve_twh,
            "coarse_renewable_step_gw": self.coarse_renewable_step_gw,
            "coarse_electrolyser_step_gw": self.coarse_electrolyser_step_gw,
            "fine_renewable_step_gw": self.fine_renewable_step_gw,
            "fine_electrolyser_step_gw": self.fine_electrolyser_step_gw,
            "storage_max_twh": self.storage_max_twh,
            "storage_tolerance_twh": self.storage_tolerance_twh,
            "cycle_tolerance_twh": self.cycle_tolerance_twh,
            "hydrogen_generation_resolution_gw": self.hydrogen_generation_resolution_gw,
        }
        invalid = [name for name, value in positive_values.items() if value <= 0]
        if invalid:
            msg = f"Configuration values must be positive: {', '.join(invalid)}"
            raise ValueError(msg)
        if self.renewable_min_gw >= self.renewable_max_gw:
            raise ValueError("renewable_min_gw must be below renewable_max_gw")
        if self.electrolyser_min_gw >= self.electrolyser_max_gw:
            raise ValueError("electrolyser_min_gw must be below electrolyser_max_gw")
        if self.storage_max_twh <= self.reserve_twh:
            raise ValueError("storage_max_twh must exceed reserve_twh")
        if self.max_cycle_iterations < _MINIMUM_CYCLE_ITERATIONS:
            raise ValueError("max_cycle_iterations must be at least 2")


@dataclass
class OptimisationResult:
    """All tabular and time-series outputs from an optimisation."""

    config: OptimisationConfig
    summary: dict[str, Any]
    coarse_candidates: pd.DataFrame
    fine_candidates: pd.DataFrame
    optimal_daily_storage: pd.DataFrame


@dataclass
class _PreparedInputs:
    demand: pd.DataFrame
    capacity_factors: pd.DataFrame
    dates: pd.DatetimeIndex
    imports: pd.DataFrame | None
    potential_capacity_factors: dict[str, float]
    net_supply_cache: dict[float, pd.DataFrame]


@dataclass
class _CyclicRun:
    status: str
    reason: str
    system: PowerSystem | None = None
    simulation: pd.DataFrame | None = None
    initial_hydrogen_twh: float = math.nan
    final_hydrogen_twh: float = math.nan
    minimum_hydrogen_twh: float = math.nan
    initial_medium_twh: float = math.nan
    final_medium_twh: float = math.nan
    minimum_medium_twh: float = math.nan
    cycle_error_twh: float = math.nan
    cycle_iterations: int = 0


def _float_grid(start: float, stop: float, step: float) -> list[float]:
    count = math.floor((stop - start) / step + _FLOAT_TOLERANCE)
    return [round(start + index * step, 10) for index in range(count + 1)]


def _quantity_series_magnitude(series: pd.Series, unit: Quantity) -> np.ndarray:
    return series.pint.to(unit).pint.magnitude.to_numpy(dtype=float)


def _prepare_inputs(config: OptimisationConfig) -> _PreparedInputs:
    demand = predicted_demand(
        mode=config.demand_mode,
        historical="era5",
        filter_ldz=True,
        average_year=False,
    )
    capacity_factors = renewable_capacity_factors.get_renewable_capacity_factors(
        source=config.capacity_factors_source,
        resample="D",
    )
    dates = demand.index.intersection(capacity_factors.index)

    imports = None
    if config.enable_imports:
        imports = get_available_imports(source=config.capacity_factors_source)
        dates = dates.intersection(imports.index)
        imports = imports.reindex(dates)

    if dates.empty:
        raise ValueError("Demand, capacity-factor, and optional import data have no common dates")

    demand = demand.reindex(dates)
    capacity_factors = capacity_factors.reindex(dates)
    potential_capacity_factors = {
        technology: float(capacity_factors[column].astype(float).mean()) for technology, (column, _) in _TECHNOLOGIES.items()
    }
    return _PreparedInputs(
        demand=demand,
        capacity_factors=capacity_factors,
        dates=pd.DatetimeIndex(dates),
        imports=imports,
        potential_capacity_factors=potential_capacity_factors,
        net_supply_cache={},
    )


def _build_net_supply(
    renewable_capacity_gw: float,
    config: OptimisationConfig,
    prepared: _PreparedInputs,
) -> pd.DataFrame:
    cache_key = round(renewable_capacity_gw, 10)
    if cache_key in prepared.net_supply_cache:
        return prepared.net_supply_cache[cache_key]

    renewable_power = (
        renewable_capacity_gw
        * U.GW
        * sum(
            (ratio * prepared.capacity_factors[column] for column, ratio in _TECHNOLOGIES.values()),
            0,
        )
    )
    nuclear_power = A.Nuclear.Capacity * A.Nuclear.CapacityFactor if config.enable_nuclear else 0 * U.GW
    daily_supply = ((renewable_power + nuclear_power) * A.HoursPerDay * (1 - A.PowerSystem.TotalLosses)).pint.to(U.TWh)
    net_supply = (daily_supply - prepared.demand["demand"]).pint.to(U.TWh)
    frame = net_supply.to_frame(name=renewable_capacity_gw).reset_index()
    frame = frame.rename(columns={frame.columns[0]: "index"})
    prepared.net_supply_cache[cache_key] = frame
    return frame


def _make_system(  # noqa: PLR0913
    *,
    renewable_capacity_gw: float,
    electrolyser_power_gw: float,
    storage_capacity_twh: float,
    hydrogen_generation_power_gw: float,
    config: OptimisationConfig,
    prepared: _PreparedInputs,
) -> PowerSystem:
    medium_capacity = A.MediumTermStorage.Capacity if config.enable_medium_storage else 0 * U.TWh
    medium_power = A.MediumTermStorage.Power if config.enable_medium_storage else 0 * U.GW
    gas_capacity = A.DispatchableGasCCS.Capacity if config.enable_gas_ccs else 0 * U.GW
    system = PowerSystem(
        renewable_capacity=renewable_capacity_gw * U.GW,
        hydrogen_storage_capacity=storage_capacity_twh * U.TWh,
        electrolyser_power=electrolyser_power_gw * U.GW,
        dac_capacity=0 * U.GW,
        hydrogen_generation_power=hydrogen_generation_power_gw * U.GW,
        medium_storage_capacity=medium_capacity,
        medium_storage_power=medium_power,
        gas_ccs_capacity=gas_capacity,
        only_dac_if_hydrogen_storage_full=True,
        enable_gas_ltdac=False,
        enable_imports=False,
        capacity_factors_source=config.capacity_factors_source,
    )
    if config.enable_imports:
        system.enable_imports = True
        system.interconnect_imports_df = prepared.imports
    return system


def _column(system: PowerSystem, stem: str) -> str:
    return f"{stem},RC={system.renewable_capacity}GW"


def _run_cyclic(  # noqa: PLR0913
    *,
    renewable_capacity_gw: float,
    electrolyser_power_gw: float,
    storage_capacity_twh: float,
    hydrogen_generation_power_gw: float,
    config: OptimisationConfig,
    prepared: _PreparedInputs,
) -> _CyclicRun:
    net_supply = _build_net_supply(renewable_capacity_gw, config, prepared)
    system = _make_system(
        renewable_capacity_gw=renewable_capacity_gw,
        electrolyser_power_gw=electrolyser_power_gw,
        storage_capacity_twh=storage_capacity_twh,
        hydrogen_generation_power_gw=hydrogen_generation_power_gw,
        config=config,
        prepared=prepared,
    )
    initial_hydrogen = storage_capacity_twh
    initial_medium = system.medium_storage_capacity

    for iteration in range(1, config.max_cycle_iterations + 1):
        system.initial_hydrogen_storage_level = initial_hydrogen
        system.initial_medium_storage_level = initial_medium
        simulation = system.run_simulation(net_supply.copy())
        if simulation is None:
            return _CyclicRun(
                status="infeasible",
                reason="unmet_demand",
                cycle_iterations=iteration,
            )

        hydrogen_col = _column(system, "hydrogen_storage_level (TWh)")
        medium_col = _column(system, "medium_storage_level (TWh)")
        hydrogen_values = _quantity_series_magnitude(simulation[hydrogen_col], U.TWh)
        medium_values = _quantity_series_magnitude(simulation[medium_col], U.TWh)
        final_hydrogen = float(hydrogen_values[-1])
        final_medium = float(medium_values[-1])
        cycle_error = max(
            abs(final_hydrogen - initial_hydrogen),
            abs(final_medium - initial_medium),
        )

        if cycle_error <= config.cycle_tolerance_twh:
            minimum_hydrogen = float(hydrogen_values.min())
            minimum_medium = float(medium_values.min())
            if minimum_hydrogen + _FLOAT_TOLERANCE < config.reserve_twh:
                return _CyclicRun(
                    status="infeasible",
                    reason="reserve_shortfall",
                    system=system,
                    simulation=simulation,
                    initial_hydrogen_twh=initial_hydrogen,
                    final_hydrogen_twh=final_hydrogen,
                    minimum_hydrogen_twh=minimum_hydrogen,
                    initial_medium_twh=initial_medium,
                    final_medium_twh=final_medium,
                    minimum_medium_twh=minimum_medium,
                    cycle_error_twh=cycle_error,
                    cycle_iterations=iteration,
                )
            return _CyclicRun(
                status="feasible",
                reason="ok",
                system=system,
                simulation=simulation,
                initial_hydrogen_twh=initial_hydrogen,
                final_hydrogen_twh=final_hydrogen,
                minimum_hydrogen_twh=minimum_hydrogen,
                initial_medium_twh=initial_medium,
                final_medium_twh=final_medium,
                minimum_medium_twh=minimum_medium,
                cycle_error_twh=cycle_error,
                cycle_iterations=iteration,
            )

        initial_hydrogen = final_hydrogen
        initial_medium = final_medium

    return _CyclicRun(
        status="infeasible",
        reason="cycle_not_converged",
        system=system,
        simulation=simulation,
        initial_hydrogen_twh=initial_hydrogen,
        final_hydrogen_twh=final_hydrogen,
        minimum_hydrogen_twh=float(hydrogen_values.min()),
        initial_medium_twh=initial_medium,
        final_medium_twh=final_medium,
        minimum_medium_twh=float(medium_values.min()),
        cycle_error_twh=cycle_error,
        cycle_iterations=config.max_cycle_iterations,
    )


def _generous_hydrogen_generation_power_gw(net_supply: pd.DataFrame) -> float:
    net_column = next(column for column in net_supply.columns if column != "index")
    net_values = _quantity_series_magnitude(net_supply[net_column], U.TWh)
    peak_deficit_twh = max(0.0, -float(net_values.min()))
    return peak_deficit_twh / _TWH_PER_GW_DAY + 0.1


def _find_minimum_storage(
    *,
    renewable_capacity_gw: float,
    electrolyser_power_gw: float,
    hydrogen_generation_power_gw: float,
    config: OptimisationConfig,
    prepared: _PreparedInputs,
) -> tuple[float | None, _CyclicRun]:
    cache: dict[float, _CyclicRun] = {}

    def evaluate(storage_twh: float) -> _CyclicRun:
        key = round(storage_twh, 10)
        if key not in cache:
            cache[key] = _run_cyclic(
                renewable_capacity_gw=renewable_capacity_gw,
                electrolyser_power_gw=electrolyser_power_gw,
                storage_capacity_twh=storage_twh,
                hydrogen_generation_power_gw=hydrogen_generation_power_gw,
                config=config,
                prepared=prepared,
            )
        return cache[key]

    lower = config.reserve_twh
    upper = min(config.storage_max_twh, max(50.0, config.reserve_twh * 2))
    upper_run = evaluate(upper)
    while upper_run.status != "feasible" and upper < config.storage_max_twh:
        upper = min(config.storage_max_twh, upper * 2)
        upper_run = evaluate(upper)

    if upper_run.status != "feasible":
        return None, upper_run

    lower_run = evaluate(lower)
    if lower_run.status == "feasible":
        return lower, lower_run

    while upper - lower > config.storage_tolerance_twh:
        midpoint = (lower + upper) / 2
        midpoint_run = evaluate(midpoint)
        if midpoint_run.status == "feasible":
            upper = midpoint
            upper_run = midpoint_run
        else:
            lower = midpoint

    return upper, upper_run


def _minimum_generation_power_gw(
    run: _CyclicRun,
    config: OptimisationConfig,
) -> float:
    if run.system is None or run.simulation is None:
        raise ValueError("A feasible cyclic simulation is required")
    hydrogen_col = _column(run.system, "hydrogen_storage_level (TWh)")
    levels = _quantity_series_magnitude(run.simulation[hydrogen_col], U.TWh)
    previous_levels = np.concatenate(([run.initial_hydrogen_twh], levels[:-1]))
    hydrogen_draw_twh = np.maximum(previous_levels - levels, 0.0)
    delivered_twh = hydrogen_draw_twh * A.HydrogenStorage.Generation.Efficiency
    raw_power_gw = float(delivered_twh.max(initial=0.0)) / _TWH_PER_GW_DAY
    resolution = config.hydrogen_generation_resolution_gw
    return math.ceil((raw_power_gw - _FLOAT_TOLERANCE) / resolution) * resolution


def _curtailment_adjusted_renewable_terms(
    renewable_capacity_gw: float,
    annual_curtailed_twh: float,
    prepared: _PreparedInputs,
) -> tuple[float, Quantity, float]:
    potential_generation: dict[str, Quantity] = {}
    for technology, (_, ratio) in _TECHNOLOGIES.items():
        potential_generation[technology] = (
            renewable_capacity_gw * U.GW * ratio * prepared.potential_capacity_factors[technology] * A.HoursPerYear
        ).to(U.TWh)
    total_potential = sum(potential_generation.values(), 0 * U.TWh)
    raw_fraction = annual_curtailed_twh / total_potential.to(U.TWh).magnitude
    curtailment_fraction = min(max(raw_fraction, 0.0), 1.0)

    portfolio_lcoe = 0 * U.GBP / U.MWh
    portfolio_capacity_factor = 0.0
    for technology, (_, ratio) in _TECHNOLOGIES.items():
        adjusted_capacity_factor = prepared.potential_capacity_factors[technology] * (1 - curtailment_fraction)
        if adjusted_capacity_factor <= 0:
            return 0.0, float("inf") * U.GBP / U.MWh, curtailment_fraction
        lcoe = renewables_2050_lcoe(
            technology,
            "Medium",
            load_factor=adjusted_capacity_factor,
        )["total"]
        generation_weight = (potential_generation[technology] / total_potential).to_base_units().magnitude
        portfolio_lcoe += lcoe * generation_weight
        portfolio_capacity_factor += adjusted_capacity_factor * ratio
    return portfolio_capacity_factor, portfolio_lcoe, curtailment_fraction


def _annual_import_cost(
    run: _CyclicRun,
    prepared: _PreparedInputs,
) -> Quantity:
    if run.system is None or run.simulation is None or prepared.imports is None:
        return 0 * U.GBP
    import_col = _column(run.system, "interconnect_energy (TWh)")
    used_twh = _quantity_series_magnitude(run.simulation[import_col], U.TWh)
    daily_costs = np.zeros(len(used_twh), dtype=float)
    remaining = used_twh.copy()
    countries = sorted(
        A.Interconnectors.Config,
        key=lambda country: A.Interconnectors.Config[country]["LCOE"].to(U.GBP / U.MWh).magnitude,
    )
    for country in countries:
        available_twh = (prepared.imports[country] * A.HoursPerDay).pint.to(U.TWh).pint.magnitude.to_numpy(dtype=float)
        allocated_twh = np.minimum(remaining, available_twh)
        lcoe = A.Interconnectors.Config[country]["LCOE"].to(U.GBP / U.MWh).magnitude
        daily_costs += allocated_twh * 1e6 * lcoe
        remaining -= allocated_twh
    if np.any(remaining > _IMPORT_ALLOCATION_TOLERANCE_TWH):
        raise ValueError("Unable to allocate all simulated interconnector energy")
    return float(daily_costs.mean() * _DAYS_PER_MODEL_YEAR) * U.GBP


def _calculate_metrics(
    run: _CyclicRun,
    config: OptimisationConfig,
    prepared: _PreparedInputs,
) -> dict[str, float]:
    if run.system is None or run.simulation is None:
        raise ValueError("A feasible cyclic simulation is required")
    system = run.system
    simulation = run.simulation
    curtailed_col = _column(system, "curtailed_energy (TWh)")
    gas_col = _column(system, "gas_ccs_energy (TWh)")
    import_col = _column(system, "interconnect_energy (TWh)")
    medium_input_col = _column(system, "energy_into_medium_storage (TWh)")
    dac_col = _column(system, "dac_energy (TWh)")

    annual_curtailed = float(_quantity_series_magnitude(simulation[curtailed_col], U.TWh).mean() * _DAYS_PER_MODEL_YEAR)
    annual_gas = float(_quantity_series_magnitude(simulation[gas_col], U.TWh).mean() * _DAYS_PER_MODEL_YEAR)
    annual_imports = float(_quantity_series_magnitude(simulation[import_col], U.TWh).mean() * _DAYS_PER_MODEL_YEAR)
    annual_medium_input = float(_quantity_series_magnitude(simulation[medium_input_col], U.TWh).mean() * _DAYS_PER_MODEL_YEAR)
    annual_dac = float(_quantity_series_magnitude(simulation[dac_col], U.TWh).mean() * _DAYS_PER_MODEL_YEAR)
    if not math.isclose(annual_dac, 0.0, abs_tol=1e-10):
        raise AssertionError("Zero-DAC optimisation produced non-zero DAC energy")

    capacity_factor, renewable_lcoe, curtailment_fraction = _curtailment_adjusted_renewable_terms(
        system.renewable_capacity,
        annual_curtailed,
        prepared,
    )
    nuclear_capacity = A.Nuclear.Capacity if config.enable_nuclear else 0 * U.GW
    annual_cost = total_system_cost(
        energy_demand=A.EnergyDemand2050,
        renewable_capacity=system.renewable_capacity * U.GW,
        renewable_capacity_factor=capacity_factor,
        renewable_lcoe=renewable_lcoe,
        nuclear_capacity=nuclear_capacity,
        nuclear_capacity_factor=A.Nuclear.CapacityFactor,
        nuclear_lcoe=A.Nuclear.AverageLCOE,
        storage_capacity=system.hydrogen_storage_capacity * U.TWh,
        electrolyser_power=system.electrolyser_power * U.GW,
        generation_capacity=system.hydrogen_generation_power * U.GW,
    )
    annual_cost += annual_gas * U.TWh * A.DispatchableGasCCS.LCOE
    annual_cost += annual_medium_input * U.TWh * A.MediumTermStorage.LCOE
    annual_cost += _annual_import_cost(run, prepared)
    annual_cost = annual_cost.to(U.GBP)
    energy_cost = (annual_cost / A.EnergyDemand2050).to(U.GBP / U.MWh)

    return {
        "annual_system_cost_gbp": float(annual_cost.magnitude),
        "energy_cost_gbp_per_mwh": float(energy_cost.magnitude),
        "annual_curtailed_energy_twh": annual_curtailed,
        "curtailment_fraction": float(curtailment_fraction),
        "annual_gas_ccs_energy_twh": annual_gas,
        "annual_interconnect_energy_twh": annual_imports,
        "annual_medium_storage_input_twh": annual_medium_input,
        "annual_dac_energy_twh": annual_dac,
    }


def _infeasible_record(
    *,
    stage: str,
    renewable_capacity_gw: float,
    electrolyser_power_gw: float,
    run: _CyclicRun,
) -> dict[str, Any]:
    return {
        "stage": stage,
        "status": "infeasible",
        "failure_reason": run.reason,
        "reliable": False,
        "renewable_capacity_gw": renewable_capacity_gw,
        "electrolyser_power_gw": electrolyser_power_gw,
        "hydrogen_storage_capacity_twh": math.nan,
        "hydrogen_generation_power_gw": math.nan,
        "dac_capacity_gw": 0.0,
        "minimum_hydrogen_storage_twh": run.minimum_hydrogen_twh,
        "initial_hydrogen_storage_twh": run.initial_hydrogen_twh,
        "final_hydrogen_storage_twh": run.final_hydrogen_twh,
        "cycle_error_twh": run.cycle_error_twh,
        "cycle_iterations": run.cycle_iterations,
        "annual_system_cost_gbp": math.nan,
        "energy_cost_gbp_per_mwh": math.nan,
        "annual_curtailed_energy_twh": math.nan,
        "curtailment_fraction": math.nan,
        "annual_gas_ccs_energy_twh": math.nan,
        "annual_interconnect_energy_twh": math.nan,
        "annual_medium_storage_input_twh": math.nan,
        "annual_dac_energy_twh": 0.0,
    }


def _evaluate_candidate(
    *,
    stage: str,
    renewable_capacity_gw: float,
    electrolyser_power_gw: float,
    config: OptimisationConfig,
    prepared: _PreparedInputs,
) -> tuple[dict[str, Any], _CyclicRun | None]:
    net_supply = _build_net_supply(renewable_capacity_gw, config, prepared)
    generation_upper = _generous_hydrogen_generation_power_gw(net_supply)
    storage_capacity, run = _find_minimum_storage(
        renewable_capacity_gw=renewable_capacity_gw,
        electrolyser_power_gw=electrolyser_power_gw,
        hydrogen_generation_power_gw=generation_upper,
        config=config,
        prepared=prepared,
    )
    if storage_capacity is None:
        return (
            _infeasible_record(
                stage=stage,
                renewable_capacity_gw=renewable_capacity_gw,
                electrolyser_power_gw=electrolyser_power_gw,
                run=run,
            ),
            None,
        )

    generation_power = _minimum_generation_power_gw(run, config)
    verified_run = _run_cyclic(
        renewable_capacity_gw=renewable_capacity_gw,
        electrolyser_power_gw=electrolyser_power_gw,
        storage_capacity_twh=storage_capacity,
        hydrogen_generation_power_gw=generation_power,
        config=config,
        prepared=prepared,
    )
    while verified_run.status != "feasible" and generation_power < generation_upper:
        generation_power = round(
            generation_power + config.hydrogen_generation_resolution_gw,
            10,
        )
        verified_run = _run_cyclic(
            renewable_capacity_gw=renewable_capacity_gw,
            electrolyser_power_gw=electrolyser_power_gw,
            storage_capacity_twh=storage_capacity,
            hydrogen_generation_power_gw=generation_power,
            config=config,
            prepared=prepared,
        )
    if verified_run.status != "feasible":
        return (
            _infeasible_record(
                stage=stage,
                renewable_capacity_gw=renewable_capacity_gw,
                electrolyser_power_gw=electrolyser_power_gw,
                run=verified_run,
            ),
            None,
        )

    metrics = _calculate_metrics(verified_run, config, prepared)
    record: dict[str, Any] = {
        "stage": stage,
        "status": "feasible",
        "failure_reason": "",
        "reliable": True,
        "renewable_capacity_gw": renewable_capacity_gw,
        "electrolyser_power_gw": electrolyser_power_gw,
        "hydrogen_storage_capacity_twh": storage_capacity,
        "hydrogen_generation_power_gw": generation_power,
        "dac_capacity_gw": 0.0,
        "minimum_hydrogen_storage_twh": verified_run.minimum_hydrogen_twh,
        "initial_hydrogen_storage_twh": verified_run.initial_hydrogen_twh,
        "final_hydrogen_storage_twh": verified_run.final_hydrogen_twh,
        "cycle_error_twh": verified_run.cycle_error_twh,
        "cycle_iterations": verified_run.cycle_iterations,
        **metrics,
    }
    return record, verified_run


def _search_grid(
    *,
    stage: str,
    renewable_values: list[float],
    electrolyser_values: list[float],
    config: OptimisationConfig,
    prepared: _PreparedInputs,
) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for renewable_index, renewable_capacity_gw in enumerate(renewable_values, start=1):
        if config.verbose:
            print(f"{stage}: renewable {renewable_capacity_gw:g} GW ({renewable_index}/{len(renewable_values)})")
        for electrolyser_power_gw in electrolyser_values:
            record, _ = _evaluate_candidate(
                stage=stage,
                renewable_capacity_gw=renewable_capacity_gw,
                electrolyser_power_gw=electrolyser_power_gw,
                config=config,
                prepared=prepared,
            )
            records.append(record)
    return pd.DataFrame.from_records(records)


def _best_candidate(candidates: pd.DataFrame, stage: str) -> pd.Series:
    feasible = candidates[candidates["status"] == "feasible"]
    if feasible.empty:
        reasons = candidates["failure_reason"].value_counts().to_dict()
        msg = f"No feasible {stage} candidates. Failure reasons: {reasons}"
        raise RuntimeError(msg)
    return feasible.sort_values([
        "annual_system_cost_gbp",
        "renewable_capacity_gw",
        "electrolyser_power_gw",
    ]).iloc[0]


def _check_boundary(
    best: pd.Series,
    renewable_values: list[float],
    electrolyser_values: list[float],
    stage: str,
) -> None:
    renewable = float(best["renewable_capacity_gw"])
    electrolyser = float(best["electrolyser_power_gw"])
    boundaries: list[str] = []
    if math.isclose(renewable, renewable_values[0]) or math.isclose(renewable, renewable_values[-1]):
        boundaries.append("renewable capacity")
    if math.isclose(electrolyser, electrolyser_values[0]) or math.isclose(electrolyser, electrolyser_values[-1]):
        boundaries.append("electrolyser power")
    if boundaries:
        msg = f"The {stage} optimum lies on the search boundary for {', '.join(boundaries)}; widen the corresponding range."
        raise RuntimeError(msg)


def _daily_output(
    run: _CyclicRun,
    config: OptimisationConfig,
    prepared: _PreparedInputs,
) -> pd.DataFrame:
    if run.system is None or run.simulation is None:
        raise ValueError("A feasible optimal simulation is required")
    system = run.system
    simulation = run.simulation
    if len(simulation) != len(prepared.dates):
        raise ValueError("Simulation length does not match the aligned date index")
    net_supply = _build_net_supply(system.renewable_capacity, config, prepared)
    net_column = next(column for column in net_supply.columns if column != "index")
    hydrogen_col = _column(system, "hydrogen_storage_level (TWh)")
    medium_col = _column(system, "medium_storage_level (TWh)")
    charge_col = _column(system, "energy_into_hydrogen_storage (TWh)")
    curtailed_col = _column(system, "curtailed_energy (TWh)")
    gas_col = _column(system, "gas_ccs_energy (TWh)")
    import_col = _column(system, "interconnect_energy (TWh)")
    dac_col = _column(system, "dac_energy (TWh)")

    hydrogen_levels = _quantity_series_magnitude(
        simulation[hydrogen_col],
        U.TWh,
    )
    previous_levels = np.concatenate(([run.initial_hydrogen_twh], hydrogen_levels[:-1]))
    hydrogen_generation = np.maximum(previous_levels - hydrogen_levels, 0.0) * A.HydrogenStorage.Generation.Efficiency
    return pd.DataFrame({
        "date": prepared.dates,
        "net_supply_twh": _quantity_series_magnitude(
            net_supply[net_column],
            U.TWh,
        ),
        "hydrogen_storage_twh": hydrogen_levels,
        "hydrogen_charge_input_twh": _quantity_series_magnitude(
            simulation[charge_col],
            U.TWh,
        ),
        "hydrogen_generation_twh": hydrogen_generation,
        "medium_storage_twh": _quantity_series_magnitude(
            simulation[medium_col],
            U.TWh,
        ),
        "gas_ccs_energy_twh": _quantity_series_magnitude(
            simulation[gas_col],
            U.TWh,
        ),
        "interconnect_energy_twh": _quantity_series_magnitude(
            simulation[import_col],
            U.TWh,
        ),
        "curtailed_energy_twh": _quantity_series_magnitude(
            simulation[curtailed_col],
            U.TWh,
        ),
        "dac_energy_twh": _quantity_series_magnitude(
            simulation[dac_col],
            U.TWh,
        ),
    })


def _serialisable_config(config: OptimisationConfig) -> dict[str, Any]:
    values = asdict(config)
    values["demand_mode"] = str(config.demand_mode)
    return values


def optimise_zero_dac(config: OptimisationConfig) -> OptimisationResult:
    """Run the coarse and fine zero E-DAC capacity optimisation.

    Returns:
        Optimisation result containing the summary, candidate tables, and daily data.

    Raises:
        AssertionError: If the final result fails deterministic or physical checks.
    """
    config.validate()
    prepared = _prepare_inputs(config)
    coarse_renewables = _float_grid(
        config.renewable_min_gw,
        config.renewable_max_gw,
        config.coarse_renewable_step_gw,
    )
    coarse_electrolysers = _float_grid(
        config.electrolyser_min_gw,
        config.electrolyser_max_gw,
        config.coarse_electrolyser_step_gw,
    )
    coarse_candidates = _search_grid(
        stage="coarse",
        renewable_values=coarse_renewables,
        electrolyser_values=coarse_electrolysers,
        config=config,
        prepared=prepared,
    )
    coarse_best = _best_candidate(coarse_candidates, "coarse")
    _check_boundary(
        coarse_best,
        coarse_renewables,
        coarse_electrolysers,
        "coarse",
    )

    fine_renewable_min = max(
        config.renewable_min_gw,
        float(coarse_best["renewable_capacity_gw"]) - config.fine_renewable_span_gw,
    )
    fine_renewable_max = min(
        config.renewable_max_gw,
        float(coarse_best["renewable_capacity_gw"]) + config.fine_renewable_span_gw,
    )
    fine_electrolyser_min = max(
        config.electrolyser_min_gw,
        float(coarse_best["electrolyser_power_gw"]) - config.fine_electrolyser_span_gw,
    )
    fine_electrolyser_max = min(
        config.electrolyser_max_gw,
        float(coarse_best["electrolyser_power_gw"]) + config.fine_electrolyser_span_gw,
    )
    fine_renewables = _float_grid(
        fine_renewable_min,
        fine_renewable_max,
        config.fine_renewable_step_gw,
    )
    fine_electrolysers = _float_grid(
        fine_electrolyser_min,
        fine_electrolyser_max,
        config.fine_electrolyser_step_gw,
    )
    fine_candidates = _search_grid(
        stage="fine",
        renewable_values=fine_renewables,
        electrolyser_values=fine_electrolysers,
        config=config,
        prepared=prepared,
    )
    fine_best = _best_candidate(fine_candidates, "fine")
    _check_boundary(fine_best, fine_renewables, fine_electrolysers, "fine")
    if float(fine_best["annual_system_cost_gbp"]) > float(coarse_best["annual_system_cost_gbp"]) + 1e-3:
        raise AssertionError("Fine search is more expensive than the coarse optimum")

    best_record, optimal_run = _evaluate_candidate(
        stage="verification",
        renewable_capacity_gw=float(fine_best["renewable_capacity_gw"]),
        electrolyser_power_gw=float(fine_best["electrolyser_power_gw"]),
        config=config,
        prepared=prepared,
    )
    if optimal_run is None or best_record["status"] != "feasible":
        raise AssertionError("The final optimal candidate failed deterministic verification")
    if not math.isclose(
        float(best_record["annual_system_cost_gbp"]),
        float(fine_best["annual_system_cost_gbp"]),
        rel_tol=1e-10,
        abs_tol=1e-3,
    ):
        raise AssertionError("The final optimal candidate is not deterministic")

    daily = _daily_output(optimal_run, config, prepared)
    if not np.allclose(daily["dac_energy_twh"], 0.0, atol=1e-10):
        raise AssertionError("Daily E-DAC energy must be zero")
    if not config.enable_gas_ccs and not np.allclose(
        daily["gas_ccs_energy_twh"],
        0.0,
        atol=1e-10,
    ):
        raise AssertionError("Gas CCS ran while disabled")
    if not config.enable_imports and not np.allclose(
        daily["interconnect_energy_twh"],
        0.0,
        atol=1e-10,
    ):
        raise AssertionError("Interconnectors ran while disabled")
    if not config.enable_medium_storage and not np.allclose(
        daily["medium_storage_twh"],
        0.0,
        atol=1e-10,
    ):
        raise AssertionError("Medium-duration storage ran while disabled")

    summary = {
        "scenario": "zero_e_dac_optimised_power_system",
        "configuration": _serialisable_config(config),
        "system_switches": {
            "e_dac": False,
            "nuclear": config.enable_nuclear,
            "gas_ccs": config.enable_gas_ccs,
            "medium_storage": config.enable_medium_storage,
            "imports": config.enable_imports,
        },
        "data": {
            "start_date": prepared.dates.min().date().isoformat(),
            "end_date": prepared.dates.max().date().isoformat(),
            "number_of_days": len(prepared.dates),
            "equivalent_years": len(prepared.dates) / 365.25,
            "demand_mode": str(config.demand_mode),
            "capacity_factors_source": config.capacity_factors_source,
        },
        "optimal_system": {
            key: (
                bool(value)
                if isinstance(value, (bool, np.bool_))
                else int(value)
                if isinstance(value, (int, np.integer))
                else float(value)
                if isinstance(value, (float, np.floating))
                else value
            )
            for key, value in best_record.items()
            if key not in {"stage", "status", "failure_reason"}
        },
        "reliability": {
            "status": "feasible",
            "zero_unmet_demand": True,
            "minimum_required_hydrogen_storage_twh": config.reserve_twh,
            "minimum_simulated_hydrogen_storage_twh": float(best_record["minimum_hydrogen_storage_twh"]),
            "cycle_error_twh": float(best_record["cycle_error_twh"]),
            "cycle_iterations": int(best_record["cycle_iterations"]),
            "annual_dac_energy_twh": 0.0,
        },
        "search": {
            "coarse_candidate_count": len(coarse_candidates),
            "coarse_feasible_count": int((coarse_candidates["status"] == "feasible").sum()),
            "fine_candidate_count": len(fine_candidates),
            "fine_feasible_count": int((fine_candidates["status"] == "feasible").sum()),
            "coarse_best_cost_gbp_per_mwh": float(coarse_best["energy_cost_gbp_per_mwh"]),
            "fine_best_cost_gbp_per_mwh": float(fine_best["energy_cost_gbp_per_mwh"]),
        },
    }
    return OptimisationResult(
        config=config,
        summary=summary,
        coarse_candidates=coarse_candidates,
        fine_candidates=fine_candidates,
        optimal_daily_storage=daily,
    )


def _draw_cost_panel(
    *,
    figure: Figure,
    axis: Axes,
    candidates: pd.DataFrame,
    title: str,
) -> None:
    pivot = candidates.pivot_table(
        index="renewable_capacity_gw",
        columns="electrolyser_power_gw",
        values="energy_cost_gbp_per_mwh",
    )
    x_values = pivot.columns.to_numpy(dtype=float)
    y_values = pivot.index.to_numpy(dtype=float)
    z_values = np.ma.masked_invalid(pivot.to_numpy(dtype=float))

    if z_values.count() > 0 and len(x_values) > 1 and len(y_values) > 1:
        contour = axis.contourf(
            x_values,
            y_values,
            z_values,
            levels=20,
            cmap="viridis",
        )
        colour_bar = figure.colorbar(contour, ax=axis)
        colour_bar.set_label("System cost (GBP/MWh)")
    else:
        feasible = candidates[candidates["status"] == "feasible"]
        axis.scatter(
            feasible["electrolyser_power_gw"],
            feasible["renewable_capacity_gw"],
            c=feasible["energy_cost_gbp_per_mwh"],
            cmap="viridis",
        )
    axis.set_xlabel("Electrolyser power (GW)")
    axis.set_ylabel("Renewable capacity (GW)")
    axis.set_title(title)


def plot_cost_surface(result: OptimisationResult) -> Figure:
    """Plot the coarse and fine cost surfaces with their optima.

    Returns:
        Matplotlib figure containing the cost surfaces.
    """
    figure, axes = plt.subplots(1, 2, figsize=(14, 5.8))
    _draw_cost_panel(
        figure=figure,
        axis=axes[0],
        candidates=result.coarse_candidates,
        title="Global coarse search",
    )
    _draw_cost_panel(
        figure=figure,
        axis=axes[1],
        candidates=result.fine_candidates,
        title="Local fine search",
    )

    coarse_best = _best_candidate(result.coarse_candidates, "coarse")
    fine_best = _best_candidate(result.fine_candidates, "fine")
    axes[0].scatter(
        coarse_best["electrolyser_power_gw"],
        coarse_best["renewable_capacity_gw"],
        marker="o",
        s=90,
        facecolors="none",
        edgecolors="white",
        linewidths=2,
        label="Coarse optimum",
    )
    axes[0].scatter(
        fine_best["electrolyser_power_gw"],
        fine_best["renewable_capacity_gw"],
        marker="*",
        s=180,
        color="red",
        edgecolors="black",
        linewidths=0.7,
        label="Fine optimum",
    )
    axes[1].scatter(
        fine_best["electrolyser_power_gw"],
        fine_best["renewable_capacity_gw"],
        marker="*",
        s=180,
        color="red",
        edgecolors="black",
        linewidths=0.7,
        label="Fine optimum",
    )
    axes[0].legend()
    axes[1].legend()
    figure.suptitle("Zero E-DAC system cost surfaces")
    figure.tight_layout()
    return figure


def plot_hydrogen_storage(result: OptimisationResult) -> Figure:
    """Plot the optimal hydrogen-storage trajectory and reliability reserve.

    Returns:
        Matplotlib figure containing the daily storage trajectory.
    """
    daily = result.optimal_daily_storage.copy()
    dates = pd.DatetimeIndex(pd.to_datetime(daily["date"]))
    storage = daily["hydrogen_storage_twh"].to_numpy(dtype=float)
    minimum_index = int(np.argmin(storage))
    optimal = result.summary["optimal_system"]

    figure, axis = plt.subplots(figsize=(12, 5.5))
    axis.plot(dates, storage, color="tab:blue", linewidth=1.0, label="Hydrogen storage")
    axis.axhline(
        result.config.reserve_twh,
        color="tab:red",
        linestyle="--",
        linewidth=1.3,
        label=f"Reserve ({result.config.reserve_twh:g} TWh)",
    )
    axis.scatter(
        dates[minimum_index],
        storage[minimum_index],
        color="black",
        s=30,
        zorder=3,
        label=f"Minimum ({storage[minimum_index]:.2f} TWh)",
    )
    axis.set_xlabel("Date")
    axis.set_ylabel("Stored hydrogen energy (TWh)")
    axis.set_title("Optimal zero E-DAC hydrogen-storage trajectory")
    axis.grid(alpha=0.25)
    axis.legend(loc="best")
    caption = (
        f"Renewables {optimal['renewable_capacity_gw']:.1f} GW | "
        f"Electrolyser {optimal['electrolyser_power_gw']:.1f} GW | "
        f"Store {optimal['hydrogen_storage_capacity_twh']:.1f} TWh | "
        f"H2 generation {optimal['hydrogen_generation_power_gw']:.1f} GW | "
        f"cycle error {optimal['cycle_error_twh']:.4f} TWh"
    )
    figure.text(0.5, 0.01, caption, ha="center", fontsize=9)
    figure.tight_layout(rect=(0, 0.04, 1, 1))
    return figure


def save_results(
    result: OptimisationResult,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Path]:
    """Save all optimisation tables, metadata, and figures.

    Returns:
        Mapping from output name to its saved path.
    """
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    paths = {
        "summary": destination / "optimal_system_summary.json",
        "coarse_candidates": destination / "coarse_search_candidates.csv",
        "fine_candidates": destination / "fine_search_candidates.csv",
        "daily_storage": destination / "optimal_daily_storage.csv",
        "cost_surface": destination / "cost_surface.png",
        "storage_plot": destination / "optimal_hydrogen_storage.png",
    }
    paths["summary"].write_text(
        json.dumps(result.summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    result.coarse_candidates.to_csv(paths["coarse_candidates"], index=False)
    result.fine_candidates.to_csv(paths["fine_candidates"], index=False)
    result.optimal_daily_storage.to_csv(paths["daily_storage"], index=False)

    cost_figure = plot_cost_surface(result)
    cost_figure.savefig(paths["cost_surface"], dpi=180, bbox_inches="tight")
    plt.close(cost_figure)
    storage_figure = plot_hydrogen_storage(result)
    storage_figure.savefig(paths["storage_plot"], dpi=180, bbox_inches="tight")
    plt.close(storage_figure)
    return paths


def _quick_config(config: OptimisationConfig) -> OptimisationConfig:
    return replace(
        config,
        coarse_renewable_step_gw=40.0,
        coarse_electrolyser_step_gw=20.0,
        fine_renewable_span_gw=40.0,
        fine_electrolyser_span_gw=20.0,
        fine_renewable_step_gw=5.0,
        fine_electrolyser_step_gw=5.0,
        storage_tolerance_twh=1.0,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Optimise a zero E-DAC renewable and hydrogen power system.",
    )
    parser.add_argument("--nuclear", action="store_true", help="Enable the existing nuclear fleet")
    parser.add_argument("--gas-ccs", action="store_true", help="Enable dispatchable gas with CCS")
    parser.add_argument("--medium-storage", action="store_true", help="Enable medium-duration storage")
    parser.add_argument("--imports", action="store_true", help="Enable interconnector imports")
    parser.add_argument("--quick", action="store_true", help="Use a sparse grid for a smoke test")
    parser.add_argument("--quiet", action="store_true", help="Suppress per-row search progress")
    parser.add_argument("--reserve-twh", type=float, default=20.0)
    parser.add_argument("--renewable-min-gw", type=float, default=220.0)
    parser.add_argument("--renewable-max-gw", type=float, default=500.0)
    parser.add_argument("--electrolyser-min-gw", type=float, default=20.0)
    parser.add_argument("--electrolyser-max-gw", type=float, default=160.0)
    parser.add_argument("--storage-max-twh", type=float, default=500.0)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    """Run the command-line optimisation and save all outputs."""
    args = _parse_args()
    config = OptimisationConfig(
        enable_nuclear=args.nuclear,
        enable_gas_ccs=args.gas_ccs,
        enable_medium_storage=args.medium_storage,
        enable_imports=args.imports,
        reserve_twh=args.reserve_twh,
        renewable_min_gw=args.renewable_min_gw,
        renewable_max_gw=args.renewable_max_gw,
        electrolyser_min_gw=args.electrolyser_min_gw,
        electrolyser_max_gw=args.electrolyser_max_gw,
        storage_max_twh=args.storage_max_twh,
        verbose=not args.quiet,
    )
    if args.quick:
        config = _quick_config(config)
    result = optimise_zero_dac(config)
    paths = save_results(result, args.output_dir)
    print(json.dumps(result.summary, indent=2, ensure_ascii=False))
    print("\nSaved outputs:")
    for name, path in paths.items():
        print(f"- {name}: {path}")


if __name__ == "__main__":
    main()
