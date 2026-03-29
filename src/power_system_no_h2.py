from typing import NamedTuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import gridspec
from pint import Quantity

import src.assumptions as A
from src.costs import energy_cost, total_system_cost
from src.data.renewable_capacity_factors import CapacityFactorSource
from src.power_system_core_no_h2 import SimulationParameters, simulate_power_system_core_no_h2
from src.supply_model import get_available_imports
from src.units import Units as U


class SimulationColumnsNoH2(NamedTuple):
    """Column names for NO_H2 simulation outputs."""

    medium_storage_level: str
    dac_energy: str
    curtailed_energy: str
    energy_into_medium_storage: str
    gas_ccs_energy: str
    interconnect_energy: str
    gas_dac_electricity: str
    gas_dac_capture: str


class PowerSystemNoH2:
    """Power system variant without hydrogen storage; uses medium storage + gas CCS + DAC/E-DAC."""

    def __init__(  # noqa: PLR0913
        self,
        *,
        renewable_capacity: Quantity,
        medium_storage_capacity: Quantity | None = None,
        medium_storage_power: Quantity | None = None,
        dac_capacity: Quantity,
        gas_ccs_capacity: Quantity | None = None,
        enable_imports: bool = False,
        capacity_factors_source: CapacityFactorSource = "era5_2024",
    ) -> None:
        assert renewable_capacity.units == U.GW, "Renewable capacity must be in GW"
        assert dac_capacity.units == U.GW, "DAC capacity must be in GW"

        if medium_storage_capacity is None:
            medium_storage_capacity = A.MediumTermStorage.Capacity
        if medium_storage_power is None:
            medium_storage_power = A.MediumTermStorage.Power
        if gas_ccs_capacity is None:
            gas_ccs_capacity = A.DispatchableGasCCS.Capacity

        assert medium_storage_capacity.units == U.TWh, "Medium storage capacity must be in TWh"
        assert medium_storage_power.units == U.GW, "Medium storage power must be in GW"
        assert gas_ccs_capacity.units == U.GW, "Gas CCS capacity must be in GW"

        if medium_storage_capacity == 0:
            assert medium_storage_power == 0, "If medium storage capacity is zero, power must also be zero"

        self.renewable_capacity = renewable_capacity.magnitude

        # Medium-term storage parameters (magnitudes)
        self.medium_storage_capacity = medium_storage_capacity.magnitude
        self.medium_storage_power = medium_storage_power.magnitude
        self.medium_storage_max_daily_energy = (medium_storage_power * A.HoursPerDay).to(U.TWh).magnitude
        self.medium_storage_efficiency = np.sqrt(A.MediumTermStorage.RoundTripEfficiency)
        self.initial_medium_storage_level = self.medium_storage_capacity

        # DAC parameters
        self.dac_capacity = dac_capacity.magnitude
        self.dac_max_daily_energy = (dac_capacity * A.HoursPerDay).to(U.TWh).magnitude

        # Gas CCS parameters
        self.gas_ccs_capacity = gas_ccs_capacity.magnitude
        self.gas_ccs_max_daily_energy = (gas_ccs_capacity * A.HoursPerDay).to(U.TWh).magnitude

        # Interconnect
        self.enable_imports = enable_imports
        self.interconnect_imports_df = None
        if enable_imports:
            self.interconnect_imports_df = get_available_imports(source=capacity_factors_source)

        # Gas DAC coefficients (default to CCGT with LTDAC from assumptions)
        gas_cfg = A.GasTechDACParameters.TechnologyParameters["CCGT (normal combined cycle)"]
        self.gas_dac_electricity_per_t = gas_cfg["DACElectricityPerTonCO2"].to(U.MWh / U.t).magnitude
        self.gas_co2_intensity = A.GasTechDACParameters.GasCO2Intensity.to(U.t / U.MWh).magnitude
        self.gas_dac_heat_per_t = A.GasTechDACParameters.HeatPerTonCO2.to(U.MWh / U.t).magnitude
        self.gas_electrical_efficiency = gas_cfg["ElectricalEfficiency"]
        self.gas_waste_heat_fraction = gas_cfg["WasteHeatFraction"]
        self.gas_low_temperature_fraction = gas_cfg["LowTemperatureFraction"]
        self.gas_tech_is_edac = False

    def run_simulation(self, net_supply_df: pd.DataFrame) -> pd.DataFrame | None:
        """Run NO_H2 simulation for this renewable capacity scenario."""
        supply_demand_col = self.renewable_capacity
        if supply_demand_col not in net_supply_df.columns:
            supply_demand_col = f"S-D(TWh),Ren={self.renewable_capacity}GW"

        columns = SimulationColumnsNoH2(
            medium_storage_level=f"medium_storage_level (TWh),RC={self.renewable_capacity}GW",
            dac_energy=f"dac_energy (TWh),RC={self.renewable_capacity}GW",
            curtailed_energy=f"curtailed_energy (TWh),RC={self.renewable_capacity}GW",
            energy_into_medium_storage=f"energy_into_medium_storage (TWh),RC={self.renewable_capacity}GW",
            gas_ccs_energy=f"gas_ccs_energy (TWh),RC={self.renewable_capacity}GW",
            interconnect_energy=f"interconnect_energy (TWh),RC={self.renewable_capacity}GW",
            gas_dac_electricity=f"gas_dac_electricity (TWh),RC={self.renewable_capacity}GW",
            gas_dac_capture=f"gas_dac_capture (MtCO2),RC={self.renewable_capacity}GW",
        )

        supply_demand_values = net_supply_df[supply_demand_col].astype(float).to_numpy()

        if self.interconnect_imports_df is not None:
            supply_demand_aligned = net_supply_df
            common_idx = supply_demand_aligned.index.intersection(self.interconnect_imports_df.index)
            interconnect_imports_aligned = self.interconnect_imports_df.reindex(common_idx)
            supply_demand_aligned = supply_demand_aligned.reindex(common_idx)
            interconnect_imports_array = (interconnect_imports_aligned["total"] * A.HoursPerDay).pint.to(U.TWh).astype(float).to_numpy()
            supply_demand_values = supply_demand_aligned[supply_demand_col].astype(float).to_numpy()
        else:
            interconnect_imports_array = np.zeros(len(supply_demand_values))

        params = SimulationParameters(
            initial_medium_storage_level=self.initial_medium_storage_level,
            medium_storage_capacity=self.medium_storage_capacity,
            medium_storage_max_daily_energy=self.medium_storage_max_daily_energy,
            medium_storage_efficiency=self.medium_storage_efficiency,
            dac_max_daily_energy=self.dac_max_daily_energy,
            gas_ccs_max_daily_energy=self.gas_ccs_max_daily_energy,
            interconnect_imports=interconnect_imports_array,
            gas_dac_electricity_per_t=self.gas_dac_electricity_per_t,
            gas_co2_intensity=self.gas_co2_intensity,
            gas_dac_heat_per_t=self.gas_dac_heat_per_t,
            gas_electrical_efficiency=self.gas_electrical_efficiency,
            gas_waste_heat_fraction=self.gas_waste_heat_fraction,
            gas_low_temperature_fraction=self.gas_low_temperature_fraction,
            gas_tech_is_edac=self.gas_tech_is_edac,
        )

        results = simulate_power_system_core_no_h2(supply_demand_values, params)
        if np.isnan(results).any():
            return None

        results_df = pd.DataFrame({
            columns.medium_storage_level: pd.Series(results[:, 0], dtype="pint[TWh]"),
            columns.dac_energy: pd.Series(results[:, 1], dtype="pint[TWh]"),
            columns.curtailed_energy: pd.Series(results[:, 2], dtype="pint[TWh]"),
            columns.energy_into_medium_storage: pd.Series(results[:, 3], dtype="pint[TWh]"),
            columns.gas_ccs_energy: pd.Series(results[:, 4], dtype="pint[TWh]"),
            columns.interconnect_energy: pd.Series(results[:, 5], dtype="pint[TWh]"),
            columns.gas_dac_electricity: pd.Series(results[:, 6], dtype="pint[TWh]"),
            columns.gas_dac_capture: pd.Series(results[:, 7], dtype="pint[Mt]"),
        })

        self._validate_simulation_results(results_df, columns)
        return results_df

    def _validate_simulation_results(self, df: pd.DataFrame, columns: SimulationColumnsNoH2) -> None:
        assert (df[columns.curtailed_energy] >= 0).all(), "Curtailed energy cannot be negative"
        assert (df[columns.medium_storage_level] <= self.medium_storage_capacity * U.TWh).all(), "Medium storage cannot exceed maximum capacity"
        assert (df[columns.medium_storage_level] >= 0).all(), "Medium storage cannot be negative"
        assert (df[columns.dac_energy] <= self.dac_max_daily_energy * U.TWh).all(), "DAC energy cannot exceed its maximum daily capacity"
        assert (df[columns.gas_ccs_energy] >= 0).all(), "Gas CCS energy cannot be negative"
        assert (df[columns.interconnect_energy] >= 0).all(), "Interconnect energy cannot be negative"
        assert (df[columns.gas_dac_electricity] >= 0).all(), "Gas DAC electricity cannot be negative"
        assert (df[columns.gas_dac_capture] >= 0).all(), "Gas DAC capture cannot be negative"

    def analyze_simulation_results(self, sim_df: pd.DataFrame | None) -> dict | None:
        if sim_df is None:
            return None
        medium_storage_column = f"medium_storage_level (TWh),RC={int(self.renewable_capacity)}GW"
        dac_column = f"dac_energy (TWh),RC={int(self.renewable_capacity)}GW"
        curtailed_column = f"curtailed_energy (TWh),RC={int(self.renewable_capacity)}GW"
        gas_ccs_column = f"gas_ccs_energy (TWh),RC={int(self.renewable_capacity)}GW"
        interconnect_column = f"interconnect_energy (TWh),RC={int(self.renewable_capacity)}GW"
        gas_dac_elec_column = f"gas_dac_electricity (TWh),RC={int(self.renewable_capacity)}GW"
        gas_dac_capture_column = f"gas_dac_capture (MtCO2),RC={int(self.renewable_capacity)}GW"

        minimum_medium_storage = sim_df[medium_storage_column].min()
        annual_dac_energy = sim_df[dac_column].mean() * 365
        annual_co2_removals = annual_dac_energy / A.DAC.EnergyCost.MediumTWhPerMtCO2
        dac_capacity_factor = (sim_df[dac_column] > 0).mean()
        curtailed_energy = sim_df[curtailed_column].mean() * 365
        annual_gas_ccs_energy = sim_df[gas_ccs_column].mean() * 365
        gas_ccs_capacity_factor = (sim_df[gas_ccs_column] > 0).mean()
        annual_interconnect_energy = sim_df[interconnect_column].mean() * 365
        annual_gas_dac_electricity = sim_df[gas_dac_elec_column].mean() * 365
        annual_gas_dac_capture = sim_df[gas_dac_capture_column].mean() * 365
        gas_emissions_intensity = A.GasTechDACParameters.GasCO2Intensity
        annual_gas_emissions = (annual_gas_ccs_energy.to(U.MWh) * gas_emissions_intensity).to(U.Mt)
        annual_net_capture = annual_co2_removals + annual_gas_dac_capture - annual_gas_emissions
        annual_edac_cost = annual_dac_energy * A.EDAC.LCOE
        annual_ltdac_cost = annual_gas_dac_capture.to(U.t) * A.LTDAC.LCOR
        annual_dac_total_cost = annual_edac_cost + annual_ltdac_cost
        dac_cost_per_mwh = (annual_dac_total_cost / A.EnergyDemand2050).to(U.GBP / U.MWh)

        return {
            "minimum_medium_storage": minimum_medium_storage,
            "annual_dac_energy": annual_dac_energy,
            "annual_co2_removals": annual_co2_removals,
            "dac_capacity_factor": dac_capacity_factor,
            "curtailed_energy": curtailed_energy,
            "annual_gas_ccs_energy": annual_gas_ccs_energy,
            "gas_ccs_capacity_factor": gas_ccs_capacity_factor,
            "annual_interconnect_energy": annual_interconnect_energy,
            "annual_gas_dac_electricity": annual_gas_dac_electricity,
            "annual_gas_dac_capture": annual_gas_dac_capture,
            "annual_gas_emissions": annual_gas_emissions,
            "annual_net_capture": annual_net_capture,
            "annual_dac_total_cost": annual_dac_total_cost,
            "dac_cost_per_mwh": dac_cost_per_mwh,
        }

    def calculate_power_system_cost(self, sim_df: pd.DataFrame | None = None) -> Quantity:
        base_cost = total_system_cost(
            energy_demand=A.EnergyDemand2050,
            renewable_capacity=self.renewable_capacity * U.GW,
            renewable_capacity_factor=A.Renewables.AverageCapacityFactor,
            renewable_lcoe=A.Renewables.AverageLCOE,
            nuclear_capacity=A.Nuclear.Capacity,
            nuclear_capacity_factor=A.Nuclear.CapacityFactor,
            nuclear_lcoe=A.Nuclear.AverageLCOE,
            storage_capacity=self.medium_storage_capacity * U.TWh,
            electrolyser_power=0 * U.GW,
            generation_capacity=0 * U.GW,
        )
        if sim_df is None:
            return base_cost

        additional_costs = 0 * U.GBP
        gas_ccs_column = f"gas_ccs_energy (TWh),RC={int(self.renewable_capacity)}GW"
        annual_gas_ccs_energy = sim_df[gas_ccs_column].mean() * 365
        gas_ccs_cost = annual_gas_ccs_energy * A.DispatchableGasCCS.LCOE
        additional_costs += gas_ccs_cost

        medium_storage_column = f"energy_into_medium_storage (TWh),RC={int(self.renewable_capacity)}GW"
        annual_medium_storage_energy = sim_df[medium_storage_column].mean() * 365
        medium_storage_cost = annual_medium_storage_energy * A.MediumTermStorage.LCOE
        additional_costs += medium_storage_cost

        return base_cost + additional_costs

    def calculate_energy_cost(self, sim_df: pd.DataFrame | None = None) -> Quantity:
        return energy_cost(self.calculate_power_system_cost(sim_df), A.EnergyDemand2050)

    @staticmethod
    def format_simulation_results(results: dict) -> str:
        return (
            f"- Minimum medium storage: {results['minimum_medium_storage']:~0.1f}\n"
            f"- DAC energy: {results['annual_dac_energy']:~0.1f}\n"
            f"- DAC CO2 removals: {results['annual_co2_removals']:~0.1f}\n"
            f"- DAC Capacity Factor: {results['dac_capacity_factor']:.1%}\n"
            f"- Gas energy: {results['annual_gas_ccs_energy']:~0.1f}\n"
            f"- Gas Capacity Factor: {results['gas_ccs_capacity_factor']:.1%}\n"
            f"- Gas DAC electricity: {results['annual_gas_dac_electricity']:~0.1f}\n"
            f"- Gas DAC capture: {results['annual_gas_dac_capture']:~0.1f}\n"
            f"- Gas CO2 emissions: {results['annual_gas_emissions']:~0.1f}\n"
            f"- Net CO2 capture: {results['annual_net_capture']:~0.1f}\n"
            f"- Curtailed energy: {results['curtailed_energy']:~0.1f}\n"
            f"- Interconnect energy: {results['annual_interconnect_energy']:~0.1f}\n"
        )

    def plot_simulation_results(self, sim_df: pd.DataFrame | None, results: dict | None, demand_mode: str, fname: str | None = None) -> None:
        if sim_df is None or results is None:
            print(f"Cannot plot results: simulation failed for {demand_mode} demand scenario")
            return

        with plt.rc_context({"figure.constrained_layout.use": False}):
            fig = plt.figure(figsize=(18, 8))

        gs = gridspec.GridSpec(2, 4, figure=fig, hspace=0.0, wspace=0.1, width_ratios=[1, 1, 1, 1.6])

        ax1 = fig.add_subplot(gs[0, :3])
        medium_storage_pct = (
            (sim_df[f"medium_storage_level (TWh),RC={self.renewable_capacity}GW"] / self.medium_storage_capacity * 100)
            if self.medium_storage_capacity > 0
            else pd.Series([0] * len(sim_df))
        )
        ax1.plot(medium_storage_pct, color="orange", linewidth=0.8, label="Medium-term Storage")
        ax1.set_ylim(0, 110)
        ax1.set_ylabel("Storage Level (%)")
        ax1.legend(loc="upper right", fontsize=10, facecolor="white", edgecolor="gray", frameon=True, framealpha=0.9)

        ax2 = fig.add_subplot(gs[1, :3])
        ax2.plot(sim_df[f"curtailed_energy (TWh),RC={self.renewable_capacity}GW"], color="black", linewidth=0.5, label="Curtailed Energy")
        ax2.plot(sim_df[f"interconnect_energy (TWh),RC={self.renewable_capacity}GW"], color="blue", linewidth=0.5, label="Interconnect Imports")
        ax2.plot(sim_df[f"gas_ccs_energy (TWh),RC={self.renewable_capacity}GW"], color="purple", linewidth=0.5, label="Gas CCS")
        ax2.plot(sim_df[f"energy_into_medium_storage (TWh),RC={self.renewable_capacity}GW"], color="orange", linewidth=0.5, label="Medium Storage")
        ax2.plot(sim_df[f"dac_energy (TWh),RC={self.renewable_capacity}GW"], color="red", linewidth=0.5, label="DAC Energy")
        ax2.set_xlabel("Day in 40 Years")
        ax2.set_ylabel("Energy (TWh)")
        ax2.legend(loc="upper right", fontsize=10, facecolor="white", edgecolor="gray", frameon=True, framealpha=0.9)

        ax3 = fig.add_subplot(gs[:, 3])
        ax3.axis("off")
        gas_ccs_col = f"gas_ccs_energy (TWh),RC={self.renewable_capacity}GW"
        peak_gas_twh = sim_df[gas_ccs_col].max()
        if hasattr(peak_gas_twh, "units"):
            implied_min_gas_capacity = (peak_gas_twh / A.HoursPerDay).to(U.GW)
        else:
            implied_min_gas_capacity = (peak_gas_twh * U.TWh / A.HoursPerDay).to(U.GW)
        text = (
            f"Parameters:\n"
            f"- Demand Mode: {demand_mode}\n"
            f"- Renewables: {self.renewable_capacity:.0f} GW\n"
            f"- Medium Storage: {self.medium_storage_capacity:.1f} TWh, {self.medium_storage_power:.0f} GW\n"
            f"- Implied min gas capacity: {implied_min_gas_capacity:~0.1f}\n"
            f"- DAC: {self.dac_capacity:.1f} GW\n"
            f"- Energy cost: {self.calculate_energy_cost(sim_df):~0.1f}  DAC cost: {results['dac_cost_per_mwh']:~0.1f}\n"
            f"\nResults:\n"
            f"{self.format_simulation_results(results)}"
        )
        ax3.text(0, 0.5, text, fontsize=16, verticalalignment="center", fontfamily="monospace")

        if fname:
            fig.savefig(fname, bbox_inches="tight", dpi=300)
