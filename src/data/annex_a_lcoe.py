"""Loaders for the DESNZ Electricity Generation Costs 2025 (Annex A/B) data.

``data/annex_a/annex_a_technical_assumptions.json`` holds the raw per-technology,
per-commissioning-year cost and technical inputs (Annex A). ``annex_a_lcoe_results.json``
holds DESNZ's own computed LCOE results, used only to validate a re-implementation
of the Annex B calculator logic (see ``src/lcoe.py``).
"""

from __future__ import annotations

import json

from src import DATA_DIR

_ANNEX_A_DIR = DATA_DIR / "annex_a"
_TECHNICAL_ASSUMPTIONS_FILE = _ANNEX_A_DIR / "annex_a_technical_assumptions.json"
_LCOE_RESULTS_FILE = _ANNEX_A_DIR / "annex_a_lcoe_results.json"

# The technical assumptions and results files use slightly different names
# for the same technology (e.g. Annex A calls it "Large Scale Solar PV",
# while the results table calls it "Large Scale Solar"). This maps
# technical-assumptions names to results names.
RESULTS_TECHNOLOGY_ALIASES: dict[str, str] = {
    "Large Scale Solar PV": "Large Scale Solar",
}


def load_technical_assumptions() -> dict:
    """Load Annex A raw technical/cost assumptions, keyed by technology then commissioning year.

    Returns:
        Nested dict: ``{technology: {commissioning_year: {parameter_name: value}}}``.
    """
    with _TECHNICAL_ASSUMPTIONS_FILE.open(encoding="utf-8") as f:
        return json.load(f)


def load_lcoe_results() -> dict:
    """Load DESNZ's own computed LCOE results, keyed by technology then commissioning year.

    Intended for validating a re-implementation of the LCOE calculation, not for
    production use.

    Returns:
        Nested dict: ``{technology: {commissioning_year: {cost_category: value}}}``.
    """
    with _LCOE_RESULTS_FILE.open(encoding="utf-8") as f:
        return json.load(f)
