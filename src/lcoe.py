"""LCOE calculation following the DESNZ Electricity Generation Costs 2025 methodology.

Re-implements the discounted-cash-flow LCOE calculation described in Annex B
(Example LCOE Calculator) using the raw per-technology inputs from Annex A.
See ``data/annex_a/lcoe_calculation_spec.json`` for the machine-readable
specification this module implements, and ``tests/test_lcoe.py`` for
validation against DESNZ's own published results.

Do not import ``src.assumptions`` here: ``assumptions.py`` imports this
module to populate ``Renewables.LCOE``, so the reverse import would create a
circular dependency.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.data.annex_a_lcoe import load_technical_assumptions
from src.units import Units as U

if TYPE_CHECKING:
    from pint import Quantity

HoursPerYear = 8760

# Annex A phasing rows have 6 buckets: explicit Year 1..5 percentages, then a
# "Year 6+" percentage covering any remaining years of a longer period.
_EXPLICIT_PHASING_YEARS = 5

# Annex A "2050" parameter rows for the three renewable technologies used by
# Renewables.LCOE in src/assumptions.py, copied verbatim from
# data/annex_a/annex_a_technical_assumptions.json so that importing
# src.assumptions doesn't require reading that file from disk. Kept in sync
# with the JSON by tests/test_lcoe.py's anti-drift test — update both if
# DESNZ publishes revised figures.
RENEWABLES_2050_PARAMS: dict[str, dict] = {
    "Large Scale Solar PV": {
        "Reference plant size": 52,
        "Average load factor (net load factor)": 0.12,  # leaved as it is for validation, but this is not used in the LCOE calculation for solar PV
        "Average fuel efficiency": 0,
        "Operating lifetime": 38,
        "Pre-development Cost (Low)": 10,
        "Pre-development Cost (Medium)": 30,
        "Pre-development Cost (High)": 60,
        "Pre-development period (Low)": 1,
        "Pre-development period (Medium)": 3,
        "Pre-development period (High)": 4,
        "Pre-development phasing (Year 1)": 0.37,
        "(% spent in each year) (Year 2)": 0.37,
        "(% spent in each year) (Year 3)": 0.26,
        "(% spent in each year) (Year 4)": 0,
        "(% spent in each year) (Year 5)": 0,
        "(% spent in each year) (Year 6+)": 0,
        "Construction Cost (Low)": 300,
        "Construction Cost (Medium)": 400,
        "Construction Cost (High)": 400,
        "Construction period (Low)": 1,
        "Construction period (Medium)": 1,
        "Construction period (High)": 2,
        "Construction phasing (Year 1)": 0.8,
        "Construction phasing (Year 2)": 0.2,
        "Construction phasing (Year 3)": 0,
        "Construction phasing (Year 4)": 0,
        "Construction phasing (Year 5)": 0,
        "Construction phasing (Year 6+)": 0,
        "Infrastructure (Low)": 4900,
        "Infrastructure (Medium)": 6100,
        "Infrastructure (High)": 7000,
        "Fixed O&M": 5100,
        "Variable O&M": 0,
        "Insurance": 1600,
        "Connection and use of system charges": 1600,
        "Hurdle Rate (Low)": 0.065,
        "Hurdle Rate (Medium)": 0.076,
        "Hurdle Rate (High)": 0.089,
        "CO2 capture and storage": 0,
        "Decommissioning Cost (Low)": 4500,
        "Decommissioning Cost (Medium)": 16100,
        "Decommissioning Cost (High)": 26500,
    },
    "Onshore Wind": {
        "Reference plant size": 51.6,
        "Average load factor (net load factor)": 0.37,
        "Average fuel efficiency": 0,
        "Operating lifetime": 35,
        "Pre-development Cost (Low)": 40,
        "Pre-development Cost (Medium)": 80,
        "Pre-development Cost (High)": 200,
        "Pre-development period (Low)": 5,
        "Pre-development period (Medium)": 8,
        "Pre-development period (High)": 13,
        "Pre-development phasing (Year 1)": 0.13,
        "(% spent in each year) (Year 2)": 0.13,
        "(% spent in each year) (Year 3)": 0.13,
        "(% spent in each year) (Year 4)": 0.13,
        "(% spent in each year) (Year 5)": 0.13,
        "(% spent in each year) (Year 6+)": 0.33,
        "Construction Cost (Low)": 900,
        "Construction Cost (Medium)": 1100,
        "Construction Cost (High)": 1500,
        "Construction period (Low)": 1,
        "Construction period (Medium)": 2,
        "Construction period (High)": 3,
        "Construction phasing (Year 1)": 0.57,
        "Construction phasing (Year 2)": 0.43,
        "Construction phasing (Year 3)": 0,
        "Construction phasing (Year 4)": 0,
        "Construction phasing (Year 5)": 0,
        "Construction phasing (Year 6+)": 0,
        "Infrastructure (Low)": 13000,
        "Infrastructure (Medium)": 16300,
        "Infrastructure (High)": 21600,
        "Fixed O&M": 14800,
        "Variable O&M": 0,
        "Insurance": 3800,
        "Connection and use of system charges": 17700,
        "Hurdle Rate (Low)": 0.065,
        "Hurdle Rate (Medium)": 0.076,
        "Hurdle Rate (High)": 0.089,
        "CO2 capture and storage": 0,
        "Decommissioning Cost (Low)": 15500,
        "Decommissioning Cost (Medium)": 31900,
        "Decommissioning Cost (High)": 64500,
    },
    "Fixed Offshore Wind": {
        "Reference plant size": 1296.6666666666667,
        "Average load factor (net load factor)": 0.5,
        "Average fuel efficiency": 0,
        "Operating lifetime": 30,
        "Pre-development Cost (Low)": 90,
        "Pre-development Cost (Medium)": 140,
        "Pre-development Cost (High)": 200,
        "Pre-development period (Low)": 7,
        "Pre-development period (Medium)": 7,
        "Pre-development period (High)": 15,
        "Pre-development phasing (Year 1)": 0.1,
        "(% spent in each year) (Year 2)": 0.1,
        "(% spent in each year) (Year 3)": 0.15,
        "(% spent in each year) (Year 4)": 0.15,
        "(% spent in each year) (Year 5)": 0.2,
        "(% spent in each year) (Year 6+)": 0.3,
        "Construction Cost (Low)": 1900,
        "Construction Cost (Medium)": 2200,
        "Construction Cost (High)": 2600,
        "Construction period (Low)": 2,
        "Construction period (Medium)": 3,
        "Construction period (High)": 5,
        "Construction phasing (Year 1)": 0.35,
        "Construction phasing (Year 2)": 0.3,
        "Construction phasing (Year 3)": 0.35,
        "Construction phasing (Year 4)": 0,
        "Construction phasing (Year 5)": 0,
        "Construction phasing (Year 6+)": 0,
        "Infrastructure (Low)": None,
        "Infrastructure (Medium)": None,
        "Infrastructure (High)": None,
        "Fixed O&M": 38700,
        "Variable O&M": 0,
        "Insurance": 8900,
        "Connection and use of system charges": 86700,
        "Hurdle Rate (Low)": 0.073,
        "Hurdle Rate (Medium)": 0.089,
        "Hurdle Rate (High)": 0.106,
        "CO2 capture and storage": 0,
        "Decommissioning Cost (Low)": 114400,
        "Decommissioning Cost (Medium)": 265200,
        "Decommissioning Cost (High)": 527300,
    },
}


def _discount_factors(n_years: int, hurdle_rate: float) -> list[float]:
    """Discount factors for years 1..n_years (1-indexed; index 0 is unused).

    Returns:
        List of length ``n_years + 1`` where index ``t`` holds the discount
        factor for year ``t`` (index 0 is unused padding).
    """
    df = [0.0] * (n_years + 1)
    df[1] = 1.0
    for t in range(2, n_years + 1):
        df[t] = df[t - 1] / (1 + hurdle_rate)
    return df


def _phase_spend(period_years: int, phasing_pcts: list[float]) -> list[float]:
    """Spread a total spend across ``period_years`` using Annex A's phasing percentages.

    ``phasing_pcts`` has 6 entries: explicit Year 1-5 percentages, then a
    "Year 6+" percentage for any remaining years.

    Two data-shape quirks in Annex A are handled here (see plan/spec notes):
    - If ``period_years > 5``, the Year 6+ percentage is spread evenly across
      the years from 6 to ``period_years``.
    - If ``period_years <= 5``, the phasing row sometimes has more nonzero
      buckets than the period is long (it was seemingly authored for a
      different Low/Medium/High scenario's period). In that case the first
      ``period_years`` buckets are truncated and renormalized to sum to 1, so
      100% of the spend is always allocated within the actual period.

    Returns:
        List of length ``period_years`` giving the fraction of total spend
        allocated to each year of the period, in order.
    """
    if period_years <= _EXPLICIT_PHASING_YEARS:
        truncated = list(phasing_pcts[:period_years])
        total = sum(truncated)
        if total <= 0:
            return truncated
        return [pct / total for pct in truncated]

    explicit = list(phasing_pcts[:_EXPLICIT_PHASING_YEARS])
    remaining_years = period_years - _EXPLICIT_PHASING_YEARS
    each_remaining = phasing_pcts[_EXPLICIT_PHASING_YEARS] / remaining_years
    return [*explicit, *([each_remaining] * remaining_years)]


def calculate_lcoe(params: dict, hurdle_rate_scenario: str = "Medium", load_factor: float | None = None) -> dict[str, Quantity]:
    """Calculate LCOE for a single technology/commissioning-year using Annex A parameters.

    Args:
        params: Annex A parameter dict for one technology and commissioning year
            (i.e. ``annex_a_technical_assumptions.json[technology][year]``).
        hurdle_rate_scenario: One of "Low", "Medium", "High".
        load_factor: If given, overrides ``params["Average load factor (net
            load factor)"]``. Useful for recomputing LCOE against a
            model-derived capacity factor (e.g. from renewables.ninja hourly
            data) instead of DESNZ's reference-plant assumption, to check how
            sensitive the £/MWh figure is to actual dispatch.

    Returns:
        Dict of GBP/MWh Quantities: pre_development, construction, fixed_om,
        variable_om, fuel, and total (the sum of the preceding five;
        decommissioning is deliberately excluded, matching Annex B's master
        total formula).
    """
    net_power_output_mw = params["Reference plant size"]
    gross_load_factor = params["Average load factor (net load factor)"] if load_factor is None else load_factor
    net_fuel_efficiency = params["Average fuel efficiency"]
    operating_lifetime = int(params["Operating lifetime"])
    hurdle_rate = params[f"Hurdle Rate ({hurdle_rate_scenario})"]

    pre_dev_cost_per_kw = params[f"Pre-development Cost ({hurdle_rate_scenario})"]
    pre_dev_period = int(params[f"Pre-development period ({hurdle_rate_scenario})"])
    pre_dev_phasing = [
        params["Pre-development phasing (Year 1)"],
        params["(% spent in each year) (Year 2)"],
        params["(% spent in each year) (Year 3)"],
        params["(% spent in each year) (Year 4)"],
        params["(% spent in each year) (Year 5)"],
        params["(% spent in each year) (Year 6+)"],
    ]

    capital_cost_per_kw = params[f"Construction Cost ({hurdle_rate_scenario})"]
    construction_period = int(params[f"Construction period ({hurdle_rate_scenario})"])
    construction_phasing = [
        params["Construction phasing (Year 1)"],
        params["Construction phasing (Year 2)"],
        params["Construction phasing (Year 3)"],
        params["Construction phasing (Year 4)"],
        params["Construction phasing (Year 5)"],
        params["Construction phasing (Year 6+)"],
    ]
    infrastructure_cost_thousand = params.get(f"Infrastructure ({hurdle_rate_scenario})") or 0

    fixed_om_per_mw = params["Fixed O&M"]
    insurance_per_mw = params["Insurance"]
    connection_per_mw = params["Connection and use of system charges"] or 0
    variable_om_per_mwh = params["Variable O&M"]

    total_years = pre_dev_period + construction_period + operating_lifetime
    discount_factor = _discount_factors(total_years, hurdle_rate)

    operation_start = pre_dev_period + construction_period + 1
    operation_end = pre_dev_period + construction_period + operating_lifetime

    generation_mwh = net_power_output_mw * gross_load_factor * HoursPerYear

    total_discounted_generation = sum(generation_mwh * discount_factor[t] for t in range(operation_start, operation_end + 1))

    # Pre-development costs (£m)
    total_pre_dev_spend = pre_dev_cost_per_kw * net_power_output_mw * 1000 * 1e-6
    pre_dev_yearly_pct = _phase_spend(pre_dev_period, pre_dev_phasing)
    discounted_pre_dev = sum(total_pre_dev_spend * pct * discount_factor[t] for t, pct in enumerate(pre_dev_yearly_pct, start=1))

    # Construction costs (£m), including infrastructure spend where present
    total_capital_spend = capital_cost_per_kw * net_power_output_mw * 1000 * 1e-6
    infrastructure_spend = infrastructure_cost_thousand / 1000
    construction_yearly_pct = _phase_spend(construction_period, construction_phasing)
    discounted_construction = sum(
        (total_capital_spend + infrastructure_spend) * pct * discount_factor[pre_dev_period + i]
        for i, pct in enumerate(construction_yearly_pct, start=1)
    )

    # Fixed O&M, insurance and connection charges (£m/year), operation years only
    total_fixed_om_per_year = (fixed_om_per_mw + insurance_per_mw + connection_per_mw) * net_power_output_mw * 1e-6
    discounted_fixed_om = sum(total_fixed_om_per_year * discount_factor[t] for t in range(operation_start, operation_end + 1))

    # Variable O&M (£m/year), operation years only
    discounted_variable_om = sum(variable_om_per_mwh * generation_mwh * 1e-6 * discount_factor[t] for t in range(operation_start, operation_end + 1))

    # Fuel cost: 0 for wind/solar (net_fuel_efficiency == 0, no fuel consumed)
    discounted_fuel = 0.0
    if net_fuel_efficiency:
        fuel_price_per_mwh = params.get("Fuel price", 0)
        fuel_consumption_mwh = generation_mwh / net_fuel_efficiency
        discounted_fuel = sum(
            fuel_price_per_mwh * fuel_consumption_mwh * 1e-6 * discount_factor[t] for t in range(operation_start, operation_end + 1)
        )

    def per_mwh(discounted_cost_gbp_m: float) -> Quantity:
        return (discounted_cost_gbp_m * 1e6 / total_discounted_generation) * U.GBP / U.MWh

    breakdown = {
        "pre_development": per_mwh(discounted_pre_dev),
        "construction": per_mwh(discounted_construction),
        "fixed_om": per_mwh(discounted_fixed_om),
        "variable_om": per_mwh(discounted_variable_om),
        "fuel": per_mwh(discounted_fuel),
    }
    breakdown["total"] = sum(breakdown.values())
    return breakdown


def technology_lcoe(technology: str, year: str, hurdle_rate_scenario: str = "Medium") -> dict[str, Quantity]:
    """Calculate LCOE for a named technology and commissioning year from Annex A.

    Args:
        technology: Technology name as it appears in
            ``annex_a_technical_assumptions.json`` (e.g. "Fixed Offshore Wind").
        year: Commissioning year as a string (e.g. "2050").
        hurdle_rate_scenario: One of "Low", "Medium", "High".

    Returns:
        See ``calculate_lcoe``.
    """
    assumptions = load_technical_assumptions()
    params = assumptions[technology][year]
    return calculate_lcoe(params, hurdle_rate_scenario)


def renewables_2050_lcoe(technology: str, hurdle_rate_scenario: str = "Medium", load_factor: float | None = None) -> dict[str, Quantity]:
    """Calculate 2050-commissioning LCOE for a renewable technology without reading from disk.

    Uses ``RENEWABLES_2050_PARAMS`` instead of ``load_technical_assumptions()``,
    so this is safe to call from ``src.assumptions`` at import time. Only
    covers the technologies in ``RENEWABLES_2050_PARAMS``; use
    ``technology_lcoe`` for other technologies or commissioning years.

    Args:
        technology: One of "Large Scale Solar PV", "Onshore Wind", "Fixed Offshore Wind".
        hurdle_rate_scenario: One of "Low", "Medium", "High".
        load_factor: See ``calculate_lcoe``.

    Returns:
        See ``calculate_lcoe``.
    """
    return calculate_lcoe(RENEWABLES_2050_PARAMS[technology], hurdle_rate_scenario, load_factor=load_factor)
