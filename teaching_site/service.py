"""Reusable service layer for the teaching website prototype."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    import pandas as pd

import src.assumptions as A
from src.demand_model import DemandMode, predicted_demand
from src.power_system import PowerSystem
from src.power_system_no_h2 import PowerSystemNoH2
from src.supply_model import CapacityFactorSource, get_net_supply
from src.units import Units as U

ScenarioName = Literal["Baseline", "High wind and solar", "High storage", "High DAC"]
ModelVariant = Literal["Hydrogen", "No hydrogen"]


@dataclass(frozen=True)
class TeachingScenario:
    """Parameters exposed by the first teaching-site prototype."""

    model_variant: ModelVariant
    renewable_capacity_gw: int
    hydrogen_storage_twh: float
    electrolyser_power_gw: int
    hydrogen_generation_power_gw: int
    medium_storage_twh: float
    medium_storage_power_gw: int
    dac_capacity_gw: float
    gas_ccs_capacity_gw: int
    demand_mode: DemandMode = DemandMode.SEASONAL
    capacity_factors_source: CapacityFactorSource = "era5_2024"
    enable_imports: bool = False
    enable_gas_ltdac: bool = False


@dataclass(frozen=True)
class Metric:
    """Display-ready simulation metric."""

    label: str
    value: str
    help_text: str


@dataclass(frozen=True)
class TeachingRun:
    """Outputs needed by the Streamlit teaching interface."""

    scenario: TeachingScenario
    sim_df: pd.DataFrame | None
    analysis: dict | None
    metrics: tuple[Metric, ...]

    @property
    def succeeded(self) -> bool:
        return self.sim_df is not None and self.analysis is not None


SCENARIO_PRESETS: dict[ScenarioName, TeachingScenario] = {
    "Baseline": TeachingScenario(
        model_variant="Hydrogen",
        renewable_capacity_gw=400,
        hydrogen_storage_twh=A.HydrogenStorage.CavernStorage.Capacity.to(U.TWh).magnitude,
        electrolyser_power_gw=int(A.HydrogenStorage.Electrolysis.Power.to(U.GW).magnitude),
        hydrogen_generation_power_gw=int(A.HydrogenStorage.Generation.Power.to(U.GW).magnitude),
        medium_storage_twh=A.MediumTermStorage.Capacity.to(U.TWh).magnitude,
        medium_storage_power_gw=int(A.MediumTermStorage.Power.to(U.GW).magnitude),
        dac_capacity_gw=A.DAC.Capacity.to(U.GW).magnitude,
        gas_ccs_capacity_gw=int(A.DispatchableGasCCS.Capacity.to(U.GW).magnitude),
    ),
    "High wind and solar": TeachingScenario(
        model_variant="Hydrogen",
        renewable_capacity_gw=460,
        hydrogen_storage_twh=A.HydrogenStorage.CavernStorage.Capacity.to(U.TWh).magnitude,
        electrolyser_power_gw=int(A.HydrogenStorage.Electrolysis.Power.to(U.GW).magnitude),
        hydrogen_generation_power_gw=int(A.HydrogenStorage.Generation.Power.to(U.GW).magnitude),
        medium_storage_twh=A.MediumTermStorage.Capacity.to(U.TWh).magnitude,
        medium_storage_power_gw=int(A.MediumTermStorage.Power.to(U.GW).magnitude),
        dac_capacity_gw=A.DAC.Capacity.to(U.GW).magnitude,
        gas_ccs_capacity_gw=int(A.DispatchableGasCCS.Capacity.to(U.GW).magnitude),
    ),
    "High storage": TeachingScenario(
        model_variant="Hydrogen",
        renewable_capacity_gw=400,
        hydrogen_storage_twh=80.0,
        electrolyser_power_gw=60,
        hydrogen_generation_power_gw=int(A.HydrogenStorage.Generation.Power.to(U.GW).magnitude),
        medium_storage_twh=2.0,
        medium_storage_power_gw=20,
        dac_capacity_gw=A.DAC.Capacity.to(U.GW).magnitude,
        gas_ccs_capacity_gw=int(A.DispatchableGasCCS.Capacity.to(U.GW).magnitude),
    ),
    "High DAC": TeachingScenario(
        model_variant="Hydrogen",
        renewable_capacity_gw=450,
        hydrogen_storage_twh=A.HydrogenStorage.CavernStorage.Capacity.to(U.TWh).magnitude,
        electrolyser_power_gw=int(A.HydrogenStorage.Electrolysis.Power.to(U.GW).magnitude),
        hydrogen_generation_power_gw=int(A.HydrogenStorage.Generation.Power.to(U.GW).magnitude),
        medium_storage_twh=A.MediumTermStorage.Capacity.to(U.TWh).magnitude,
        medium_storage_power_gw=int(A.MediumTermStorage.Power.to(U.GW).magnitude),
        dac_capacity_gw=20.0,
        gas_ccs_capacity_gw=int(A.DispatchableGasCCS.Capacity.to(U.GW).magnitude),
    ),
}


@cache
def load_net_supply(
    demand_mode: DemandMode = DemandMode.SEASONAL,
    capacity_factors_source: CapacityFactorSource = "era5_2024",
) -> pd.DataFrame:
    """Load demand and renewable net-supply traces once per app process.

    Returns:
        Net supply dataframe with one column per renewable-capacity scenario.
    """
    demand_df = predicted_demand(mode=demand_mode, average_year=False)
    return get_net_supply(
        demand_df=demand_df,
        capacity_factors_source=capacity_factors_source,
    ).reset_index()


def run_teaching_scenario(scenario: TeachingScenario) -> TeachingRun:
    """Run a configured teaching scenario through the existing model.

    Returns:
        Display-ready simulation outputs for the teaching interface.
    """
    net_supply_df = load_net_supply(
        demand_mode=scenario.demand_mode,
        capacity_factors_source=scenario.capacity_factors_source,
    )

    if scenario.model_variant == "No hydrogen":
        system = PowerSystemNoH2(
            renewable_capacity=scenario.renewable_capacity_gw * U.GW,
            dac_capacity=scenario.dac_capacity_gw * U.GW,
            medium_storage_capacity=scenario.medium_storage_twh * U.TWh,
            medium_storage_power=scenario.medium_storage_power_gw * U.GW,
            gas_ccs_capacity=scenario.gas_ccs_capacity_gw * U.GW,
            enable_imports=scenario.enable_imports,
            capacity_factors_source=scenario.capacity_factors_source,
        )
    else:
        system = PowerSystem(
            renewable_capacity=scenario.renewable_capacity_gw * U.GW,
            hydrogen_storage_capacity=scenario.hydrogen_storage_twh * U.TWh,
            electrolyser_power=scenario.electrolyser_power_gw * U.GW,
            hydrogen_generation_power=scenario.hydrogen_generation_power_gw * U.GW,
            dac_capacity=scenario.dac_capacity_gw * U.GW,
            medium_storage_capacity=scenario.medium_storage_twh * U.TWh,
            medium_storage_power=scenario.medium_storage_power_gw * U.GW,
            gas_ccs_capacity=scenario.gas_ccs_capacity_gw * U.GW,
            enable_imports=scenario.enable_imports,
            enable_gas_ltdac=scenario.enable_gas_ltdac,
            capacity_factors_source=scenario.capacity_factors_source,
        )
    sim_df = system.run_simulation(net_supply_df=net_supply_df)
    if sim_df is not None:
        sim_df = sim_df.copy()
        sim_df[scenario.renewable_capacity_gw] = net_supply_df[scenario.renewable_capacity_gw].reset_index(drop=True)
    analysis = system.analyze_simulation_results(sim_df)
    if analysis is not None and sim_df is not None:
        analysis = dict(analysis)
        analysis["minimum_gas_capacity"] = _minimum_gas_capacity(sim_df, scenario.renewable_capacity_gw)

    return TeachingRun(
        scenario=scenario,
        sim_df=sim_df,
        analysis=analysis,
        metrics=format_metrics(analysis),
    )


def simulation_columns(renewable_capacity_gw: int) -> dict[str, str]:
    """Return the model's capacity-specific output columns."""
    return {
        "medium_storage": f"medium_storage_level (TWh),RC={renewable_capacity_gw}GW",
        "hydrogen_storage": f"hydrogen_storage_level (TWh),RC={renewable_capacity_gw}GW",
        "dac_energy": f"dac_energy (TWh),RC={renewable_capacity_gw}GW",
        "curtailed_energy": f"curtailed_energy (TWh),RC={renewable_capacity_gw}GW",
        "energy_into_hydrogen": f"energy_into_hydrogen_storage (TWh),RC={renewable_capacity_gw}GW",
        "energy_into_medium": f"energy_into_medium_storage (TWh),RC={renewable_capacity_gw}GW",
        "gas_ccs_energy": f"gas_ccs_energy (TWh),RC={renewable_capacity_gw}GW",
        "interconnect_energy": f"interconnect_energy (TWh),RC={renewable_capacity_gw}GW",
        "gas_dac_electricity": f"gas_dac_electricity (TWh),RC={renewable_capacity_gw}GW",
        "gas_dac_capture": f"gas_dac_capture (MtCO2),RC={renewable_capacity_gw}GW",
    }


def format_metrics(analysis: dict | None) -> tuple[Metric, ...]:
    """Convert model analysis values into compact UI metrics.

    Returns:
        Tuple of display labels, values, and explanatory help text.
    """
    if analysis is None:
        return (Metric("Simulation", "Failed", "The model could not meet demand with the selected capacities."),)

    storage_metric = (
        Metric(
            "Min hydrogen store",
            _format_quantity(analysis["minimum_hydrogen_storage"], "TWh"),
            "Lowest hydrogen storage level reached during the weather trace.",
        )
        if "minimum_hydrogen_storage" in analysis
        else Metric(
            "Min medium store",
            _format_quantity(analysis["minimum_medium_storage"], "TWh"),
            "Lowest medium-term storage level reached during the weather trace.",
        )
    )

    return (
        storage_metric,
        Metric(
            "DAC energy",
            _format_quantity(analysis["annual_dac_energy"], "TWh/yr"),
            "Annual electricity used by Direct Air Capture.",
        ),
        Metric(
            "CO2 removals",
            _format_quantity(analysis.get("annual_net_capture", analysis["annual_co2_removals"]), "MtCO2/yr"),
            "Annual net removals after gas emissions and gas-DAC capture where modelled.",
        ),
        Metric(
            "Curtailed energy",
            _format_quantity(analysis["curtailed_energy"], "TWh/yr"),
            "Annual renewable output that cannot be used, stored, imported, or sent to DAC.",
        ),
        Metric(
            "DAC run days",
            f"{analysis['dac_capacity_factor']:.0%}",
            "Share of simulated days when DAC consumes electricity.",
        ),
        Metric(
            "Gas energy",
            _format_quantity(analysis["annual_gas_ccs_energy"], "TWh/yr"),
            "Annual dispatchable gas generation used for reliability.",
        ),
        Metric(
            "Min gas capacity",
            _format_quantity(analysis["minimum_gas_capacity"], "GW"),
            "Minimum gas capacity implied by the peak daily gas dispatch in this simulation.",
        ),
    )


def _minimum_gas_capacity(sim_df: pd.DataFrame, renewable_capacity_gw: int) -> object:
    gas_ccs_column = f"gas_ccs_energy (TWh),RC={renewable_capacity_gw}GW"
    peak_daily_gas = sim_df[gas_ccs_column].max()
    if hasattr(peak_daily_gas, "units"):
        return (peak_daily_gas / A.HoursPerDay).to(U.GW)
    return (peak_daily_gas * U.TWh / A.HoursPerDay).to(U.GW)


def _format_quantity(value: object, suffix: str) -> str:
    magnitude = getattr(value, "magnitude", value)
    return f"{float(magnitude):,.1f} {suffix}"
