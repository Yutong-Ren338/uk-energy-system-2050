import math

import pytest

from src.curtailment_lcoe import _TECHNOLOGY_CAPACITY_RATIOS, average_curtailment_adjusted_lcoe
from src.lcoe import renewables_2050_lcoe
from src.units import Units as U

# Plausible range for curtailment-adjusted portfolio LCOE (GBP/MWh). Wider than
# tests/test_lcoe.py's PLAUSIBLE_LCOE_UPPER_BOUND since curtailment is expected
# to inflate cost above the uncurtailed range.
PLAUSIBLE_LACOE_LOWER_BOUND = 20
PLAUSIBLE_LACOE_UPPER_BOUND = 500


def test_zero_curtailment_matches_potential_capacity_factor_lcoe() -> None:
    """With no curtailment, ACF must equal PCF and LACoE must equal the PCF-based LCOE."""
    result = average_curtailment_adjusted_lcoe(renewable_capacity=300 * U.GW, curtailed_energy=0 * U.TWh)

    assert result["curtailment_fraction"] == 0

    for technology, pcf in result["potential_capacity_factor"].items():
        assert result["average_capacity_factor"][technology] == pytest.approx(pcf)
        expected = renewables_2050_lcoe(technology, load_factor=pcf)["total"]
        assert result["lacoe_by_technology"][technology] == expected


def test_moderate_curtailment_increases_lcoe() -> None:
    """Positive curtailment must strictly raise LACoE above the zero-curtailment baseline."""
    baseline = average_curtailment_adjusted_lcoe(renewable_capacity=500 * U.GW, curtailed_energy=0 * U.TWh)
    # 500 GW at a plausible weighted-average CF (~0.25-0.35) yields roughly
    # 1,000-1,500 TWh/yr of potential generation, so 50 TWh is comfortably
    # inside (0, potential_generation_total) without needing to compute it.
    curtailed = average_curtailment_adjusted_lcoe(renewable_capacity=500 * U.GW, curtailed_energy=50 * U.TWh)

    assert 0 < curtailed["curtailment_fraction"] < 1

    for technology in _TECHNOLOGY_CAPACITY_RATIOS:
        assert curtailed["lacoe_by_technology"][technology] > baseline["lacoe_by_technology"][technology] > 0 * U.GBP / U.MWh

    assert curtailed["portfolio_lacoe"] > baseline["portfolio_lacoe"] > 0 * U.GBP / U.MWh


def test_curtailment_exceeding_potential_generation_clips_and_gives_infinite_lcoe() -> None:
    """Curtailment beyond total potential generation clips to a fraction of 1, giving ACF=0 and LACoE=inf."""
    result = average_curtailment_adjusted_lcoe(renewable_capacity=1 * U.GW, curtailed_energy=1000 * U.TWh)

    assert result["curtailment_fraction"] == 1.0

    for technology in _TECHNOLOGY_CAPACITY_RATIOS:
        assert result["average_capacity_factor"][technology] == 0
        assert math.isinf(result["lacoe_by_technology"][technology].magnitude)

    assert math.isinf(result["portfolio_lacoe"].magnitude)


def test_portfolio_weight_reflects_generation_share_not_capacity_share() -> None:
    """Portfolio weights must track potential-generation share (CapacityRatio * PCF), not CapacityRatio alone."""
    result = average_curtailment_adjusted_lcoe(renewable_capacity=300 * U.GW, curtailed_energy=0 * U.TWh)

    weight = result["portfolio_weight"]
    assert sum(weight.values()) == pytest.approx(1.0)

    unnormalised = {
        technology: _TECHNOLOGY_CAPACITY_RATIOS[technology] * result["potential_capacity_factor"][technology]
        for technology in _TECHNOLOGY_CAPACITY_RATIOS
    }
    total = sum(unnormalised.values())
    for technology in _TECHNOLOGY_CAPACITY_RATIOS:
        assert weight[technology] == pytest.approx(unnormalised[technology] / total)
        # Capacity-share weighting would be wrong: PCF differs enough across
        # technologies (offshore wind >> solar) that the two must diverge.
        assert weight[technology] != pytest.approx(_TECHNOLOGY_CAPACITY_RATIOS[technology], rel=1e-2)


def test_portfolio_lacoe_is_plausible() -> None:
    """Regression guard: portfolio LACoE stays in GBP/MWh and within a sane range under moderate curtailment."""
    result = average_curtailment_adjusted_lcoe(renewable_capacity=400 * U.GW, curtailed_energy=30 * U.TWh)

    assert result["portfolio_lacoe"].units == U.GBP / U.MWh
    magnitude = result["portfolio_lacoe"].to(U.GBP / U.MWh).magnitude
    assert PLAUSIBLE_LACOE_LOWER_BOUND < magnitude < PLAUSIBLE_LACOE_UPPER_BOUND
