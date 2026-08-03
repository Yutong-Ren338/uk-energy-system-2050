from dataclasses import replace

from teaching_site.service import SCENARIO_PRESETS, run_teaching_scenario


def test_teaching_site_baseline_scenario_runs() -> None:
    result = run_teaching_scenario(SCENARIO_PRESETS["Baseline"])

    assert result.succeeded
    assert result.analysis is not None
    assert result.sim_df is not None
    assert "minimum_gas_capacity" in result.analysis
    assert result.metrics


def test_teaching_site_no_hydrogen_scenario_runs() -> None:
    scenario = replace(SCENARIO_PRESETS["Baseline"], model_variant="No hydrogen")
    result = run_teaching_scenario(scenario)

    assert result.succeeded
    assert result.analysis is not None
    assert result.sim_df is not None
    assert "minimum_medium_storage" in result.analysis
    assert "minimum_hydrogen_storage" not in result.analysis
    assert "minimum_gas_capacity" in result.analysis
    assert result.metrics
