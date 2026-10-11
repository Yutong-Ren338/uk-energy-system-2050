"""Curtailment-penalty-adjusted LCOE for renewables (average curtailment).

Implements the Average-Curtailment-adjusted LCOE (LACoE) from David Newbery
(2025), "Implications of renewable electricity curtailment for delivered
costs", Energy Economics 145: 108472:

    ACF_j = PCF_j - ac_j
    LACoE_j = F_j / (8760 * ACF_j) + v_j

where PCF is the technology's potential (pre-curtailment) capacity factor and
ac is the average curtailment rate, both expressed in capacity-factor units.

This model's simulation (see ``src.power_system_core``) only tracks
curtailment on the combined renewable supply, not per technology, so the
curtailment rate here is applied uniformly to every technology (a pro-rata
attribution) -- this matches Newbery's own pro-rata-curtailment case.

Kept separate from ``src.lcoe`` (which must not import ``src.assumptions``,
to avoid a circular import -- see ``src/lcoe.py``'s module docstring) and
from ``src.assumptions`` (whose ``Renewables.LCOE``/``ModelImpliedLCOE`` are
fixed constants computed once at import time, whereas curtailment inherently
depends on a scenario's installed ``renewable_capacity``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import src.assumptions as A
from src.data.renewable_capacity_factors import get_renewable_capacity_factors
from src.lcoe import renewables_2050_lcoe
from src.units import Units as U

if TYPE_CHECKING:
    from pint import Quantity

    from src.data.renewable_capacity_factors import CapacityFactorSource

# Maps RENEWABLES_2050_PARAMS technology names to their CapacityRatios weight
# and their column in get_renewable_capacity_factors' output.
_TECHNOLOGY_CAPACITY_RATIOS: dict[str, float] = {
    "Large Scale Solar PV": A.Renewables.CapacityRatios.Solar,
    "Fixed Offshore Wind": A.Renewables.CapacityRatios.OffshoreWind,
    "Onshore Wind": A.Renewables.CapacityRatios.OnshoreWind,
}

_TECHNOLOGY_CF_COLUMNS: dict[str, str] = {
    "Large Scale Solar PV": "solar",
    "Fixed Offshore Wind": "offshore",
    "Onshore Wind": "onshore",
}


def _live_potential_capacity_factors(capacity_factors_source: CapacityFactorSource) -> dict[str, float]:
    """Mean per-technology capacity factor from the same weather data a simulation used.

    Used as the potential capacity factor (PCF): the pre-curtailment capacity
    factor. Deliberately sourced from the live weather time series rather
    than ``assumptions.Renewables.CapacityFactors`` (a fixed historical
    average that may come from a different source and silently diverge from
    the one a given ``PowerSystem`` simulation actually used).
    """
    cf_df = get_renewable_capacity_factors(source=capacity_factors_source, resample="D").astype(float)
    return {technology: float(cf_df[column].mean()) for technology, column in _TECHNOLOGY_CF_COLUMNS.items()}


def average_curtailment_adjusted_lcoe(
    renewable_capacity: Quantity,
    curtailed_energy: Quantity,
    *,
    capacity_factors_source: CapacityFactorSource = "era5_2024",
    hurdle_rate_scenario: str = "Medium",
) -> dict:
    """Compute renewable LCOE adjusted for average curtailment (Newbery 2025's LACoE).

    Args:
        renewable_capacity: Total installed renewable capacity in GW -- the
            same value used to construct the ``PowerSystem`` that produced
            ``curtailed_energy``.
        curtailed_energy: Annual curtailed energy in TWh, e.g.
            ``PowerSystem.analyze_simulation_results()["curtailed_energy"]``.
        capacity_factors_source: Source of the capacity factor time series;
            must match the source used by the simulation that produced
            ``curtailed_energy``.
        hurdle_rate_scenario: Passed through to ``renewables_2050_lcoe``.

    Returns:
        Dict with ``curtailment_fraction`` (float, clipped to [0, 1]),
        ``potential_capacity_factor`` and ``average_capacity_factor``
        (per-technology dicts of floats), ``lacoe_by_technology`` (per-technology
        dict of GBP/MWh Quantities, ``inf`` where curtailment fully consumes the
        potential capacity factor), ``portfolio_weight`` (per-technology dict of
        floats, each technology's share of potential generation), and
        ``portfolio_lacoe`` (generation-weighted GBP/MWh Quantity).
    """
    assert renewable_capacity.units == U.GW, "renewable_capacity must be in GW"
    assert curtailed_energy.units == U.TWh, "curtailed_energy must be in TWh"

    potential_capacity_factor = _live_potential_capacity_factors(capacity_factors_source)

    potential_generation = {
        technology: (renewable_capacity * ratio * potential_capacity_factor[technology] * A.HoursPerYear).to(U.TWh)
        for technology, ratio in _TECHNOLOGY_CAPACITY_RATIOS.items()
    }
    potential_generation_total = sum(potential_generation.values(), 0 * U.TWh)

    if potential_generation_total.magnitude > 0:
        raw_fraction = (curtailed_energy / potential_generation_total).to_base_units().magnitude
        curtailment_fraction = min(max(raw_fraction, 0.0), 1.0)
    else:
        curtailment_fraction = 0.0

    average_capacity_factor = {technology: pcf * (1 - curtailment_fraction) for technology, pcf in potential_capacity_factor.items()}

    lacoe_by_technology = {}
    for technology, acf in average_capacity_factor.items():
        if acf > 0:
            lacoe_by_technology[technology] = renewables_2050_lcoe(technology, hurdle_rate_scenario, load_factor=acf)["total"]
        else:
            lacoe_by_technology[technology] = float("inf") * U.GBP / U.MWh

    # Portfolio LCOE must be weighted by each technology's share of generation,
    # not by its installed-capacity share: a technology with a higher capacity
    # factor delivers proportionally more energy per GW installed. Since the
    # curtailment fraction is applied uniformly (pro-rata) across all three
    # technologies, it cancels out of the *relative* weights, so weighting by
    # potential generation share (already computed above) is equivalent to
    # weighting by delivered generation share.
    if potential_generation_total.magnitude > 0:
        portfolio_weight = {
            technology: (generation / potential_generation_total).to_base_units().magnitude for technology, generation in potential_generation.items()
        }
    else:
        portfolio_weight = dict(_TECHNOLOGY_CAPACITY_RATIOS)

    portfolio_lacoe = sum(
        (lacoe_by_technology[technology] * weight for technology, weight in portfolio_weight.items()),
        0 * U.GBP / U.MWh,
    )

    # Capacity-weighted (not generation-weighted) average of the post-curtailment
    # capacity factors, matching how A.Renewables.AverageCapacityFactor is built
    # from CapacityRatios. Pairing this with portfolio_lacoe in yearly_cost's
    # capacity * capacity_factor * lcoe formula reproduces the true portfolio
    # cost sum(generation_j * LACoE_j): see src/power_system.py's
    # calculate_power_system_cost for the derivation.
    portfolio_average_capacity_factor = sum(average_capacity_factor[technology] * ratio for technology, ratio in _TECHNOLOGY_CAPACITY_RATIOS.items())

    return {
        "curtailment_fraction": curtailment_fraction,
        "potential_capacity_factor": potential_capacity_factor,
        "average_capacity_factor": average_capacity_factor,
        "lacoe_by_technology": lacoe_by_technology,
        "portfolio_weight": portfolio_weight,
        "portfolio_lacoe": portfolio_lacoe,
        "portfolio_average_capacity_factor": portfolio_average_capacity_factor,
    }
