"""Streamlit teaching prototype for the UK 2050 energy model."""

from __future__ import annotations

import importlib
from dataclasses import replace

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import teaching_site.service as teaching_service
from src.demand_model import DemandMode

if "model_variant" not in teaching_service.TeachingScenario.__dataclass_fields__:
    teaching_service = importlib.reload(teaching_service)

SCENARIO_PRESETS = teaching_service.SCENARIO_PRESETS
TeachingRun = teaching_service.TeachingRun
TeachingScenario = teaching_service.TeachingScenario
run_teaching_scenario = teaching_service.run_teaching_scenario
simulation_columns = teaching_service.simulation_columns

st.set_page_config(
    page_title="UK 2050 Energy System Simulator",
    page_icon="⚡",
    layout="wide",
)


def main() -> None:
    st.title("UK 2050 Energy System Simulator")
    st.caption("Teaching prototype built on the existing power-system model.")

    scenario = _sidebar_controls()

    with st.spinner("Running simulation..."):
        run = run_teaching_scenario(scenario)

    _render_metrics(run)

    if not run.succeeded:
        st.error("The model could not meet demand with this combination of capacities. Increase storage, generation, or backup capacity.")
        return

    assert run.sim_df is not None
    cols = simulation_columns(run.scenario.renewable_capacity_gw)
    tab_balance, tab_storage, tab_flows, tab_data = st.tabs(
        ["Supply balance", "Storage", "Energy flows", "Data"],
    )

    with tab_balance:
        st.plotly_chart(_supply_balance_chart(run.sim_df, run.scenario), use_container_width=True)

    with tab_storage:
        st.plotly_chart(_storage_chart(run.sim_df, cols), use_container_width=True)

    with tab_flows:
        st.plotly_chart(_flows_chart(run.sim_df, cols), use_container_width=True)

    with tab_data:
        st.dataframe(_preview_dataframe(run.sim_df, cols), use_container_width=True)


def _sidebar_controls() -> TeachingScenario:
    st.sidebar.header("Scenario")
    preset_name = st.sidebar.selectbox(
        "Preset",
        options=list(SCENARIO_PRESETS.keys()),
        index=0,
    )
    base = SCENARIO_PRESETS[preset_name]
    base_model_variant = getattr(base, "model_variant", "Hydrogen")
    model_variant = st.sidebar.selectbox(
        "Model",
        options=["Hydrogen", "No hydrogen"],
        index=["Hydrogen", "No hydrogen"].index(base_model_variant),
    )

    st.sidebar.header("Capacities")
    renewable_capacity_gw = st.sidebar.slider("Renewables (GW)", 100, 490, base.renewable_capacity_gw, step=10)
    if model_variant == "Hydrogen":
        hydrogen_storage_twh = st.sidebar.slider("Hydrogen storage (TWh)", 0.0, 100.0, float(base.hydrogen_storage_twh), step=1.0)
        electrolyser_power_gw = st.sidebar.slider("Electrolyser power (GW)", 0, 120, base.electrolyser_power_gw, step=5)
        hydrogen_generation_power_gw = st.sidebar.slider("Hydrogen generation power (GW)", 0, 150, base.hydrogen_generation_power_gw, step=5)
    else:
        hydrogen_storage_twh = 0.0
        electrolyser_power_gw = 0
        hydrogen_generation_power_gw = 0
    medium_storage_twh = st.sidebar.slider("Medium-term storage (TWh)", 0.0, 10.0, float(base.medium_storage_twh), step=0.1)
    medium_storage_power_gw = st.sidebar.slider("Medium-term storage power (GW)", 0, 80, base.medium_storage_power_gw, step=1)
    dac_capacity_gw = st.sidebar.slider("DAC capacity (GW)", 0.0, 100.0, float(base.dac_capacity_gw), step=0.5)

    st.sidebar.header("Model options")
    demand_mode = DemandMode(
        st.sidebar.selectbox(
            "Demand mode",
            options=[mode.value for mode in DemandMode],
            index=list(DemandMode).index(base.demand_mode),
        ),
    )
    enable_imports = st.sidebar.toggle("Interconnector imports", value=base.enable_imports)
    enable_gas_ltdac = st.sidebar.toggle("Gas waste-heat DAC", value=base.enable_gas_ltdac) if model_variant == "Hydrogen" else False

    return replace(
        base,
        model_variant=model_variant,
        renewable_capacity_gw=renewable_capacity_gw,
        hydrogen_storage_twh=hydrogen_storage_twh,
        electrolyser_power_gw=electrolyser_power_gw,
        hydrogen_generation_power_gw=hydrogen_generation_power_gw,
        medium_storage_twh=medium_storage_twh,
        medium_storage_power_gw=medium_storage_power_gw,
        dac_capacity_gw=dac_capacity_gw,
        demand_mode=demand_mode,
        enable_imports=enable_imports,
        enable_gas_ltdac=enable_gas_ltdac,
    )


def _render_metrics(run: TeachingRun) -> None:
    columns = st.columns(len(run.metrics))
    for column, metric in zip(columns, run.metrics, strict=True):
        column.metric(metric.label, metric.value, help=metric.help_text)


def _supply_balance_chart(sim_df: pd.DataFrame, scenario: TeachingScenario) -> go.Figure:
    net_supply_col = scenario.renewable_capacity_gw
    net_supply = _as_float(sim_df[net_supply_col]) if net_supply_col in sim_df else pd.Series(dtype=float)
    rolling = net_supply.rolling(30, min_periods=1).mean()

    fig = go.Figure()
    fig.add_trace(go.Scatter(y=net_supply, mode="lines", name="Daily net supply", line={"width": 0.8, "color": "#4a7c59"}))
    fig.add_trace(go.Scatter(y=rolling, mode="lines", name="30-day average", line={"width": 2.0, "color": "#1f2937"}))
    fig.add_hline(y=0, line_dash="dash", line_color="#9ca3af")
    fig.update_layout(
        title="Renewable and nuclear supply minus demand",
        xaxis_title="Simulated day",
        yaxis_title="TWh/day",
        hovermode="x unified",
        margin={"l": 20, "r": 20, "t": 60, "b": 40},
    )
    return fig


def _storage_chart(sim_df: pd.DataFrame, cols: dict[str, str]) -> go.Figure:
    fig = go.Figure()
    storage_series = {
        "Hydrogen storage": (cols["hydrogen_storage"], "#2f6f73"),
        "Medium-term storage": (cols["medium_storage"], "#b7791f"),
    }
    for label, (column, color) in storage_series.items():
        if column in sim_df:
            fig.add_trace(go.Scatter(y=_as_float(sim_df[column]), mode="lines", name=label, line={"color": color}))
    fig.update_layout(
        title="Storage levels",
        xaxis_title="Simulated day",
        yaxis_title="TWh",
        hovermode="x unified",
        margin={"l": 20, "r": 20, "t": 60, "b": 40},
    )
    return fig


def _flows_chart(sim_df: pd.DataFrame, cols: dict[str, str]) -> go.Figure:
    fig = go.Figure()
    flows = {
        "DAC electricity": (cols["dac_energy"], "#c2410c"),
        "Curtailed energy": (cols["curtailed_energy"], "#525252"),
        "Hydrogen charging": (cols["energy_into_hydrogen"], "#15803d"),
        "Medium storage charging": (cols["energy_into_medium"], "#ca8a04"),
        "Gas energy": (cols["gas_ccs_energy"], "#7e22ce"),
        "Gas DAC electricity": (cols["gas_dac_electricity"], "#a855f7"),
        "Interconnector imports": (cols["interconnect_energy"], "#2563eb"),
    }
    for label, (column, color) in flows.items():
        if column in sim_df:
            fig.add_trace(go.Scatter(y=_as_float(sim_df[column]), mode="lines", name=label, line={"width": 0.9, "color": color}))
    fig.update_layout(
        title="Daily energy flows",
        xaxis_title="Simulated day",
        yaxis_title="TWh/day",
        hovermode="x unified",
        margin={"l": 20, "r": 20, "t": 60, "b": 40},
    )
    return fig


def _preview_dataframe(sim_df: pd.DataFrame, cols: dict[str, str]) -> pd.DataFrame:
    preview_cols = [column for column in cols.values() if column in sim_df.columns]
    preview = pd.DataFrame(index=sim_df.index)
    for column in preview_cols:
        preview[column] = _as_float(sim_df[column])
    return preview.head(365)


def _as_float(series: pd.Series) -> pd.Series:
    if hasattr(series, "pint"):
        return series.pint.magnitude.astype(float)
    return series.astype(float)


if __name__ == "__main__":
    main()
