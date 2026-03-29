"""Tests for the power system model simulation."""

import time
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from pint import Quantity

import src.assumptions as A
from src import demand_model, supply_model
from src.demand_model import DemandMode
from src.power_system import PowerSystem
from src.units import Units as U
from tests.config import OUTPUT_DIR, check

OUTPUT_PATH = OUTPUT_DIR / "power_system"
OUTPUT_PATH.mkdir(parents=True, exist_ok=True)

SIMULATION_KWARGS = {
    "renewable_capacity": 250 * U.GW,  # Default renewable capacity for the simulation
    "hydrogen_storage_capacity": 71 * U.TWh,  # Maximum hydrogen storage capacity
    "electrolyser_power": 50 * U.GW,  # Electrolyser power capacity
    # To maintain backward compatibility for this regression test, set a very high generation power
    # to simulate the old behavior of no power limit on drawing from hydrogen storage.
    "hydrogen_generation_power": 9999 * U.GW,
    "dac_capacity": A.DAC.Capacity,  # DAC capacity
    "medium_storage_capacity": 0 * U.TWh,  # Disable medium storage for backward compatibility
    "medium_storage_power": 0 * U.GW,  # Disable medium storage power for backward compatibility
    "gas_ccs_capacity": 0 * U.GW,  # Disable gas CCS for backward compatibility
}


@pytest.fixture
def sample_data_rei() -> pd.DataFrame:
    test_data_path = Path(__file__).parent / "rei_net_supply_df_12gw_nuclear.csv"
    return pd.read_csv(test_data_path)


@pytest.fixture
def sample_data() -> pd.DataFrame:
    # Generate demand and supply data
    demand_df = demand_model.predicted_demand(mode=DemandMode.CB7, average_year=False)
    return supply_model.get_net_supply(demand_df).reset_index()


@pytest.fixture
def power_system_model() -> PowerSystem:
    return PowerSystem(**SIMULATION_KWARGS)  # type: ignore[missing-argument]


def test_run_simulation_with_expected_outputs(power_system_model: PowerSystem, sample_data_rei: pd.DataFrame) -> None:
    # Run the simulation
    sim_df = power_system_model.run_simulation(sample_data_rei)
    assert sim_df is not None

    # Analyze results
    results = power_system_model.analyze_simulation_results(sim_df)
    assert results is not None

    # Check that the expected outputs match the documented values
    # (with some tolerance for floating point precision)
    expected_values = {
        "minimum_medium_storage": 0.0 * U.TWh,  # Medium storage disabled for backward compatibility
        "minimum_hydrogen_storage": 20.16927245757229 * U.TWh,
        "annual_dac_energy": 1.825 * U.TWh,
        "dac_capacity_factor": 0.19,  # 19.0%
        "curtailed_energy": 112.7148 * U.TWh,
        "annual_gas_ccs_energy": 0.0 * U.TWh,  # Gas CCS disabled for backward compatibility
        "gas_ccs_capacity_factor": 0.0,  # Gas CCS disabled
        "annual_gas_dac_electricity": 0.0 * U.TWh,
        "annual_gas_dac_capture": 0.0 * U.Mt,
    }
    check(results["minimum_medium_storage"], expected_values["minimum_medium_storage"])
    check(results["minimum_hydrogen_storage"], expected_values["minimum_hydrogen_storage"])
    check(results["annual_dac_energy"], expected_values["annual_dac_energy"])
    check(results["dac_capacity_factor"], expected_values["dac_capacity_factor"])
    check(results["curtailed_energy"], expected_values["curtailed_energy"])
    check(results["annual_gas_ccs_energy"], expected_values["annual_gas_ccs_energy"])
    check(results["gas_ccs_capacity_factor"], expected_values["gas_ccs_capacity_factor"])
    check(results["annual_gas_dac_electricity"], expected_values["annual_gas_dac_electricity"])
    check(results["annual_gas_dac_capture"], expected_values["annual_gas_dac_capture"])


def test_run_simulation_more_aggressive_dac(sample_data_rei: pd.DataFrame) -> None:
    """Test simulation with more aggressive DAC capacity."""
    model = PowerSystem(
        renewable_capacity=300 * U.GW,
        hydrogen_storage_capacity=71 * U.TWh,
        electrolyser_power=50 * U.GW,
        hydrogen_generation_power=A.HydrogenStorage.Generation.Power,
        dac_capacity=100 * U.GW,
        medium_storage_capacity=0 * U.TWh,  # Disable medium storage for backward compatibility
        medium_storage_power=0 * U.GW,  # Disable medium storage power for backward compatibility
        gas_ccs_capacity=0 * U.GW,  # Disable gas CCS for backward compatibility
        only_dac_if_hydrogen_storage_full=False,  # Allow DAC operation when electrolyser capacity is exceeded
    )
    sim_df = model.run_simulation(sample_data_rei)
    results = model.analyze_simulation_results(sim_df)
    assert results is not None

    # Check that results are reasonable with increased DAC capacity
    assert results["annual_dac_energy"] > 38.47911516786211 * U.TWh, "DAC energy should increase with more capacity"


def test_simulation_creates_expected_columns(power_system_model: PowerSystem, sample_data_rei: pd.DataFrame) -> None:
    sim_df = power_system_model.run_simulation(sample_data_rei)
    assert sim_df is not None

    # Check that expected columns exist for 250GW renewable capacity
    expected_columns = [
        "medium_storage_level (TWh),RC=250GW",
        "hydrogen_storage_level (TWh),RC=250GW",
        "dac_energy (TWh),RC=250GW",
        "curtailed_energy (TWh),RC=250GW",
        "energy_into_medium_storage (TWh),RC=250GW",
        "energy_into_hydrogen_storage (TWh),RC=250GW",
        "gas_ccs_energy (TWh),RC=250GW",
        "gas_dac_electricity (TWh),RC=250GW",
        "gas_dac_capture (MtCO2),RC=250GW",
    ]

    for col in expected_columns:
        assert col in sim_df.columns, f"Expected column {col} not found"


def test_simulation_physical_constraints(power_system_model: PowerSystem, sample_data_rei: pd.DataFrame) -> None:
    sim_df = power_system_model.run_simulation(sample_data_rei)
    assert sim_df is not None

    # Check hydrogen storage level constraints
    hydrogen_storage_col = "hydrogen_storage_level (TWh),RC=250GW"
    assert (sim_df[hydrogen_storage_col] >= 0).all(), "Hydrogen storage levels cannot be negative"
    assert (sim_df[hydrogen_storage_col] <= power_system_model.hydrogen_storage_capacity * U.TWh).all(), (
        "Hydrogen storage levels cannot exceed maximum capacity"
    )

    # Check medium storage level constraints (should be 0 since disabled)
    medium_storage_col = "medium_storage_level (TWh),RC=250GW"
    assert (sim_df[medium_storage_col] >= 0).all(), "Medium storage levels cannot be negative"
    assert (sim_df[medium_storage_col] <= power_system_model.medium_storage_capacity * U.TWh).all(), (
        "Medium storage levels cannot exceed maximum capacity"
    )

    # Check that energies are non-negative
    dac_col = "dac_energy (TWh),RC=250GW"
    unused_col = "curtailed_energy (TWh),RC=250GW"
    gas_dac_elec_col = "gas_dac_electricity (TWh),RC=250GW"
    gas_dac_capture_col = "gas_dac_capture (MtCO2),RC=250GW"

    assert (sim_df[dac_col] >= 0).all(), "DAC energy cannot be negative"
    assert (sim_df[unused_col] >= 0).all(), "Unused energy cannot be negative"
    assert (sim_df[gas_dac_elec_col] >= 0).all(), "Gas DAC electricity cannot be negative"
    assert (sim_df[gas_dac_capture_col] >= 0).all(), "Gas DAC capture cannot be negative"

    # Check DAC capacity constraint
    assert (sim_df[dac_col] <= power_system_model.dac_max_daily_energy * U.TWh).all(), "DAC energy cannot exceed daily capacity"


def test_analyze_simulation_results_structure(power_system_model: PowerSystem, sample_data_rei: pd.DataFrame) -> None:
    sim_df = power_system_model.run_simulation(sample_data_rei)
    assert sim_df is not None
    results = power_system_model.analyze_simulation_results(sim_df)
    assert results is not None

    # Check that all expected keys are present
    expected_keys = {
        "minimum_medium_storage",
        "minimum_hydrogen_storage",
        "annual_dac_energy",
        "annual_co2_removals",
        "dac_capacity_factor",
        "curtailed_energy",
        "annual_gas_ccs_energy",
        "gas_ccs_capacity_factor",
        "annual_interconnect_energy",
        "annual_gas_dac_electricity",
        "annual_gas_dac_capture",
        "annual_gas_emissions",
        "annual_net_capture",
        "annual_dac_total_cost",
        "dac_cost_per_mwh",
    }

    assert set(results.keys()) == expected_keys, "Results dictionary missing expected keys"

    # Check value types and ranges
    assert isinstance(results["minimum_medium_storage"], Quantity)
    assert isinstance(results["minimum_hydrogen_storage"], Quantity)
    assert isinstance(results["annual_dac_energy"], Quantity)
    assert isinstance(results["annual_co2_removals"], Quantity)
    assert isinstance(results["dac_capacity_factor"], float)
    assert isinstance(results["curtailed_energy"], Quantity)
    assert isinstance(results["annual_gas_ccs_energy"], Quantity)
    assert isinstance(results["gas_ccs_capacity_factor"], float)
    assert isinstance(results["annual_gas_dac_electricity"], Quantity)
    assert isinstance(results["annual_gas_dac_capture"], Quantity)
    assert isinstance(results["annual_gas_emissions"], Quantity)
    assert isinstance(results["annual_net_capture"], Quantity)
    assert isinstance(results["annual_dac_total_cost"], Quantity)
    assert isinstance(results["dac_cost_per_mwh"], Quantity)

    # Check capacity factor is a valid percentage
    assert 0 <= results["dac_capacity_factor"] <= 1, "DAC capacity factor should be between 0 and 1"
    assert 0 <= results["gas_ccs_capacity_factor"] <= 1, "Gas CCS capacity factor should be between 0 and 1"


def test_simulation_with_custom_renewable_capacity(sample_data: pd.DataFrame) -> None:
    # Test with different renewable capacities
    custom_model = PowerSystem(
        renewable_capacity=450 * U.GW,
        hydrogen_storage_capacity=A.HydrogenStorage.CavernStorage.Capacity,
        electrolyser_power=A.HydrogenStorage.Electrolysis.Power,
        hydrogen_generation_power=A.HydrogenStorage.Generation.Power,
        dac_capacity=A.DAC.Capacity,
        medium_storage_capacity=A.MediumTermStorage.Capacity,
        medium_storage_power=A.MediumTermStorage.Power,
    )
    sim_df = custom_model.run_simulation(sample_data)
    assert sim_df is not None
    results = custom_model.analyze_simulation_results(sim_df)

    assert results is not None
    assert isinstance(results, dict)

    # Test that the simulation creates the correct columns for custom capacity
    expected_columns = [
        "medium_storage_level (TWh),RC=450GW",
        "hydrogen_storage_level (TWh),RC=450GW",
        "dac_energy (TWh),RC=450GW",
        "curtailed_energy (TWh),RC=450GW",
        "energy_into_medium_storage (TWh),RC=450GW",
        "energy_into_hydrogen_storage (TWh),RC=450GW",
    ]
    for col in expected_columns:
        assert col in sim_df.columns, f"Expected column {col} not found"


def test_multiple_renewable_capacities(sample_data: pd.DataFrame) -> None:
    capacities = [380, 390, 400]
    all_results = {}

    for capacity in capacities:
        model = PowerSystem(
            renewable_capacity=capacity * U.GW,
            hydrogen_storage_capacity=A.HydrogenStorage.CavernStorage.Capacity,
            electrolyser_power=A.HydrogenStorage.Electrolysis.Power,
            hydrogen_generation_power=A.HydrogenStorage.Generation.Power,
            dac_capacity=A.DAC.Capacity,
            medium_storage_capacity=0 * U.TWh,  # Disable medium storage for backward compatibility
            medium_storage_power=0 * U.GW,  # Disable medium storage power for backward compatibility
        )
        sim_df = model.run_simulation(sample_data)
        if sim_df is None:
            continue
        results = model.analyze_simulation_results(sim_df)
        assert results is not None
        all_results[capacity] = results

        # Verify that each capacity produces valid results
        assert results["minimum_medium_storage"] >= 0 * U.TWh
        assert results["minimum_hydrogen_storage"] >= 0 * U.TWh
        assert results["annual_dac_energy"] >= 0 * U.TWh
        assert 0 <= results["dac_capacity_factor"] <= 1
        assert results["curtailed_energy"] >= 0 * U.TWh

    # Verify that different capacities produce different results
    assert len({r["minimum_hydrogen_storage"] for r in all_results.values()}) > 1, "Different capacities should produce different results"


@pytest.mark.parametrize("demand_mode", list(DemandMode))
def test_plot_simulation_results(demand_mode: DemandMode) -> None:
    """Test plotting simulation results for different demand modes."""
    # Setup test parameters
    renewable_capacity = 450

    # Generate demand and supply data
    demand_df = demand_model.predicted_demand(mode=demand_mode, average_year=False)
    df = supply_model.get_net_supply(demand_df).reset_index()

    # Create power system model
    storage = PowerSystem(
        renewable_capacity=renewable_capacity * U.GW,
        hydrogen_storage_capacity=A.HydrogenStorage.CavernStorage.Capacity,
        electrolyser_power=A.HydrogenStorage.Electrolysis.Power,
        hydrogen_generation_power=A.HydrogenStorage.Generation.Power,
        dac_capacity=A.DAC.Capacity,
        medium_storage_capacity=A.MediumTermStorage.Capacity,
        medium_storage_power=A.MediumTermStorage.Power,
    )

    # Run simulation
    sim_df = storage.run_simulation(df)
    results = storage.analyze_simulation_results(sim_df)
    assert results is not None

    # Create output directory for simulation runs
    simulation_outdir = OUTPUT_PATH / "simulation_runs"
    simulation_outdir.mkdir(exist_ok=True)

    # Generate plot filename
    plot_filename = simulation_outdir / f"simulation_results_{demand_mode}_{renewable_capacity}GW.png"

    # Generate plot
    storage.plot_simulation_results(sim_df, results, demand_mode, fname=str(plot_filename))

    # Verify plot was created
    assert plot_filename.exists(), f"Plot file {plot_filename} was not created"

    # Verify results are reasonable
    assert results["minimum_medium_storage"] >= 0 * U.TWh
    assert results["minimum_hydrogen_storage"] >= 0 * U.TWh
    assert results["annual_dac_energy"] >= 0 * U.TWh
    assert 0 <= results["dac_capacity_factor"] <= 1
    assert results["curtailed_energy"] >= 0 * U.TWh


def test_simulation_timing() -> None:
    """Time the power system simulation to measure performance across different parameter combinations."""
    demand_mode = DemandMode.SEASONAL  # Use seasonal mode for timing test

    # Generate demand and supply data once
    demand_df = demand_model.predicted_demand(mode=demand_mode, average_year=False)
    df = supply_model.get_net_supply(demand_df).reset_index()

    # Use the realistic parameter ranges as specified
    renewable_capacities = range(200, 410, 10)
    electrolyser_powers = range(20, 110, 10)
    max_storage = range(10, 60, 10)

    timing_results = []
    total_combinations = len(renewable_capacities) * len(electrolyser_powers) * len(max_storage)
    print(f"\nTesting {total_combinations} parameter combinations...")

    for renewable_capacity in renewable_capacities:
        for electrolyser_power in electrolyser_powers:
            for storage in max_storage:
                model = PowerSystem(
                    renewable_capacity=renewable_capacity * U.GW,
                    hydrogen_storage_capacity=storage * U.TWh,
                    electrolyser_power=electrolyser_power * U.GW,
                    hydrogen_generation_power=A.HydrogenStorage.Generation.Power,
                    dac_capacity=A.DAC.Capacity,
                    medium_storage_capacity=0 * U.TWh,  # Disable medium storage for backward compatibility
                    medium_storage_power=0 * U.GW,  # Disable medium storage power for backward compatibility
                )

                start_time = time.time()
                model.run_simulation(df.copy())
                end_time = time.time()
                timing_results.append(end_time - start_time)

    # Calculate timing statistics
    mean_time = np.mean(timing_results)
    std_time = np.std(timing_results)
    total_time = np.sum(timing_results)

    print(f"\nPower System Simulation Timing Results ({len(timing_results)} combinations):")
    print(f"Total execution time: {total_time:.2f} seconds")
    print(f"Mean execution time: {mean_time:.4f} seconds")
    print(f"Standard deviation: {std_time:.4f} seconds")
    print(f"Min time: {np.min(timing_results):.4f} seconds")
    print(f"Max time: {np.max(timing_results):.4f} seconds")

    # Basic sanity checks
    max_reasonable_time = 1  # seconds per simulation
    max_total_test_time = 30  # seconds for entire test

    assert mean_time < max_reasonable_time, f"Simulation taking too long: {mean_time:.2f} seconds on average"
    assert total_time < max_total_test_time, f"Total test time too long: {total_time:.2f} seconds"


@pytest.mark.parametrize("only_dac_if_storage_full", [True, False])
def test_medium_term_storage_functionality(sample_data: pd.DataFrame, *, only_dac_if_storage_full: bool) -> None:
    """Test that medium-term storage works correctly when enabled."""
    # Test with medium-term storage enabled
    model_with_medium = PowerSystem(
        renewable_capacity=400 * U.GW,
        hydrogen_storage_capacity=A.HydrogenStorage.CavernStorage.Capacity,
        electrolyser_power=A.HydrogenStorage.Electrolysis.Power,
        hydrogen_generation_power=A.HydrogenStorage.Generation.Power,
        dac_capacity=A.DAC.Capacity,
        only_dac_if_hydrogen_storage_full=only_dac_if_storage_full,
        medium_storage_capacity=A.MediumTermStorage.Capacity,  # Enable medium storage
        medium_storage_power=A.MediumTermStorage.Power,  # Enable medium storage power
    )

    # Test with medium-term storage disabled (baseline)
    model_without_medium = PowerSystem(
        renewable_capacity=400 * U.GW,
        hydrogen_storage_capacity=A.HydrogenStorage.CavernStorage.Capacity,
        electrolyser_power=A.HydrogenStorage.Electrolysis.Power,
        hydrogen_generation_power=A.HydrogenStorage.Generation.Power,
        dac_capacity=A.DAC.Capacity,
        only_dac_if_hydrogen_storage_full=only_dac_if_storage_full,
        medium_storage_capacity=0 * U.TWh,  # Disable medium storage
        medium_storage_power=0 * U.GW,  # Disable medium storage power
    )

    # Run simulations
    results_with_medium = model_with_medium.run_simulation(sample_data)
    results_without_medium = model_without_medium.run_simulation(sample_data)

    # Both simulations should succeed
    assert results_with_medium is not None, "Simulation with medium storage should not fail"
    assert results_without_medium is not None, "Simulation without medium storage should not fail"

    # Medium storage should be used when enabled
    medium_storage_col = "medium_storage_level (TWh),RC=400GW"
    assert (results_with_medium[medium_storage_col] >= 0).all(), "Medium storage levels should be non-negative"

    # Medium storage should remain at 0 when disabled
    assert (results_without_medium[medium_storage_col] == 0).all(), "Medium storage should be 0 when disabled"

    # Analyze results
    analysis_with_medium = model_with_medium.analyze_simulation_results(results_with_medium)
    analysis_without_medium = model_without_medium.analyze_simulation_results(results_without_medium)
    assert analysis_with_medium is not None
    assert analysis_without_medium is not None

    # With medium storage, hydrogen minimum should be higher (medium storage takes priority)
    assert analysis_with_medium["minimum_hydrogen_storage"] >= analysis_without_medium["minimum_hydrogen_storage"], (
        "Hydrogen storage minimum should be higher when medium storage is available"
    )

    # Medium storage minimum should be 0 when disabled, and potentially positive when enabled
    assert analysis_without_medium["minimum_medium_storage"] == 0 * U.TWh, "Medium storage minimum should be 0 when disabled"
    assert analysis_with_medium["minimum_medium_storage"] >= 0 * U.TWh, "Medium storage minimum should be non-negative when enabled"


def test_calculate_power_system_cost(power_system_model: PowerSystem) -> None:
    """Test that power system cost calculation returns reasonable results."""
    # Calculate the cost
    total_cost = power_system_model.calculate_power_system_cost()

    # Check that the result is a valid quantity with GBP units
    assert isinstance(total_cost, Quantity), "Cost should be a pint Quantity"
    assert total_cost.units == U.GBP, "Cost should be in GBP units"

    # Check that the cost is positive and reasonable (not zero, not absurdly large)
    max_reasonable_cost = 1e15  # 1 quadrillion GBP upper bound for sanity check
    assert total_cost.magnitude > 0, "System cost should be positive"
    assert total_cost.magnitude < max_reasonable_cost, "System cost should be reasonable"

    # Test with different renewable capacities to ensure cost scaling
    smaller_system = PowerSystem(
        renewable_capacity=100 * U.GW,
        hydrogen_storage_capacity=30 * U.TWh,
        electrolyser_power=25 * U.GW,
        dac_capacity=15 * U.GW,
    )

    larger_system = PowerSystem(
        renewable_capacity=500 * U.GW,
        hydrogen_storage_capacity=100 * U.TWh,
        electrolyser_power=75 * U.GW,
        dac_capacity=50 * U.GW,
    )

    smaller_cost = smaller_system.calculate_power_system_cost()
    larger_cost = larger_system.calculate_power_system_cost()

    # Larger system should generally cost more (though this is not strictly guaranteed due to efficiency effects)
    assert larger_cost.magnitude > smaller_cost.magnitude, "Larger system should generally cost more than smaller system"


def test_energy_cost(power_system_model: PowerSystem) -> None:
    """Test that power system cost calculation returns reasonable results."""
    # Calculate the cost
    total_cost = power_system_model.calculate_energy_cost()

    # Check that the result is a valid quantity with GBP units
    assert isinstance(total_cost, Quantity), "Cost should be a pint Quantity"
    assert total_cost.units == U.GBP / U.MWh, "Cost should be in GBP/MWh units"

    # Check that the cost is positive and reasonable (not zero, not absurdly large)
    max_reasonable_cost = 1e15  # 1 quadrillion GBP upper bound for sanity check
    assert total_cost.magnitude > 0, "System cost should be positive"
    assert total_cost.magnitude < max_reasonable_cost, "System cost should be reasonable"

    # Test with different renewable capacities to ensure cost scaling
    smaller_system = PowerSystem(
        renewable_capacity=100 * U.GW,
        hydrogen_storage_capacity=30 * U.TWh,
        electrolyser_power=25 * U.GW,
        dac_capacity=15 * U.GW,
    )

    larger_system = PowerSystem(
        renewable_capacity=500 * U.GW,
        hydrogen_storage_capacity=100 * U.TWh,
        electrolyser_power=75 * U.GW,
        dac_capacity=50 * U.GW,
    )

    smaller_cost = smaller_system.calculate_energy_cost()
    larger_cost = larger_system.calculate_energy_cost()

    # Larger system should generally cost more (though this is not strictly guaranteed due to efficiency effects)
    assert larger_cost.magnitude > smaller_cost.magnitude, "Larger system should generally cost more than smaller system"
