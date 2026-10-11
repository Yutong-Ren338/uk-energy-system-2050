import pytest

import src.assumptions as A
from src.data.annex_a_lcoe import RESULTS_TECHNOLOGY_ALIASES, load_lcoe_results, load_technical_assumptions
from src.lcoe import RENEWABLES_2050_PARAMS, calculate_lcoe, renewables_2050_lcoe, technology_lcoe
from src.units import Units as U

# DESNZ rounds each cost-category line item to the nearest £/MWh independently
# before summing, and the Annex A phasing rows have some scenario-alignment
# ambiguity for periods <=5 years (see src/lcoe.py's _phase_spend docstring).
# Observed deviation across all validation cases below tops out at ~7.4%.
TOTAL_RELATIVE_TOLERANCE = 0.10

VALIDATION_TECHNOLOGIES = ["Large Scale Solar PV", "Onshore Wind", "Fixed Offshore Wind"]
VALIDATION_YEARS = ["2030", "2035", "2040", "2045", "2050"]

# Plausible range for renewable LCOE (GBP/MWh) used as a regression guard.
PLAUSIBLE_LCOE_LOWER_BOUND = 20
PLAUSIBLE_LCOE_UPPER_BOUND = 150


def test_known_check_value_fixed_offshore_wind_2050() -> None:
    """Reproduce lcoe_calculation_spec.json's own validation_targets.known_check_value."""
    breakdown = technology_lcoe("Fixed Offshore Wind", "2050", "Medium")

    # DESNZ rounds each line item to the nearest £/MWh, so component-level
    # comparisons need headroom beyond simple rounding (abs=1.5), not the
    # tight tolerance used for exact analytical values elsewhere in the suite.
    assert breakdown["pre_development"].to(U.GBP / U.MWh).magnitude == pytest.approx(5, abs=1.5)
    assert breakdown["construction"].to(U.GBP / U.MWh).magnitude == pytest.approx(52, abs=1.5)
    assert breakdown["fixed_om"].to(U.GBP / U.MWh).magnitude == pytest.approx(31, abs=1.5)
    assert breakdown["variable_om"].to(U.GBP / U.MWh).magnitude == pytest.approx(0, abs=1.5)
    assert breakdown["total"].to(U.GBP / U.MWh).magnitude == pytest.approx(89, abs=1.5)


@pytest.mark.parametrize("technology", VALIDATION_TECHNOLOGIES)
@pytest.mark.parametrize("year", VALIDATION_YEARS)
def test_matches_desnz_published_results(technology: str, year: str) -> None:
    assumptions = load_technical_assumptions()
    results = load_lcoe_results()

    params = assumptions[technology][year]
    breakdown = calculate_lcoe(params, "Medium")
    computed_total = breakdown["total"].to(U.GBP / U.MWh).magnitude

    results_technology = RESULTS_TECHNOLOGY_ALIASES.get(technology, technology)
    expected_total = results[results_technology][year]["Total13"]

    assert computed_total == pytest.approx(expected_total, rel=TOTAL_RELATIVE_TOLERANCE)


@pytest.mark.parametrize("technology", RENEWABLES_2050_PARAMS.keys())
def test_renewables_2050_params_match_json(technology: str) -> None:
    """Guards against src.lcoe.RENEWABLES_2050_PARAMS drifting from the source JSON.

    RENEWABLES_2050_PARAMS is a hardcoded copy of each technology's "2050" row,
    kept so importing src.assumptions doesn't require reading a file from disk.
    If annex_a_technical_assumptions.json is ever updated (e.g. a newer DESNZ
    report), this test fails until RENEWABLES_2050_PARAMS is updated to match.
    """
    assumptions = load_technical_assumptions()
    assert RENEWABLES_2050_PARAMS[technology] == assumptions[technology]["2050"]


@pytest.mark.parametrize("technology", RENEWABLES_2050_PARAMS.keys())
def test_renewables_2050_lcoe_matches_technology_lcoe(technology: str) -> None:
    """renewables_2050_lcoe (no disk I/O) must agree with technology_lcoe (reads the JSON)."""
    assert renewables_2050_lcoe(technology)["total"] == technology_lcoe(technology, "2050")["total"]


def test_renewables_lcoe_constants_are_plausible() -> None:
    """Regression guard: catches an accidental revert to broken/zero LCOE values."""
    for lcoe in (A.Renewables.LCOE.Solar, A.Renewables.LCOE.OffshoreWind, A.Renewables.LCOE.OnshoreWind):
        assert lcoe.units == U.GBP / U.MWh
        assert PLAUSIBLE_LCOE_LOWER_BOUND < lcoe.magnitude < PLAUSIBLE_LCOE_UPPER_BOUND


@pytest.mark.parametrize("technology", RENEWABLES_2050_PARAMS.keys())
def test_load_factor_override_changes_generation_denominator(technology: str) -> None:
    """A lower load_factor spreads the same lifetime cost over less generation, raising £/MWh."""
    default_total = renewables_2050_lcoe(technology)["total"]
    default_load_factor = RENEWABLES_2050_PARAMS[technology]["Average load factor (net load factor)"]

    lower_total = renewables_2050_lcoe(technology, load_factor=default_load_factor / 2)["total"]

    assert lower_total > default_total


def test_renewables_2050_lcoe_no_override_matches_params_load_factor() -> None:
    """Passing load_factor equal to the Annex A value must reproduce the unmodified result."""
    for technology in RENEWABLES_2050_PARAMS:
        default_load_factor = RENEWABLES_2050_PARAMS[technology]["Average load factor (net load factor)"]
        assert renewables_2050_lcoe(technology, load_factor=default_load_factor)["total"] == renewables_2050_lcoe(technology)["total"]


def test_model_implied_lcoe_constants_are_plausible() -> None:
    """Regression guard for Renewables.ModelImpliedLCOE, and sanity check that it differs from LCOE.

    Confirms the model-derived capacity factors (Renewables.CapacityFactors) actually diverge from
    DESNZ Annex A's load factor assumption, so ModelImpliedLCOE != LCOE for all three technologies.
    """
    pairs = (
        (A.Renewables.ModelImpliedLCOE.Solar, A.Renewables.LCOE.Solar),
        (A.Renewables.ModelImpliedLCOE.OffshoreWind, A.Renewables.LCOE.OffshoreWind),
        (A.Renewables.ModelImpliedLCOE.OnshoreWind, A.Renewables.LCOE.OnshoreWind),
    )
    for model_implied, annex_a in pairs:
        assert model_implied.units == U.GBP / U.MWh
        assert PLAUSIBLE_LCOE_LOWER_BOUND < model_implied.magnitude < PLAUSIBLE_LCOE_UPPER_BOUND * 2
        assert model_implied != annex_a
