import math
from typing import ClassVar

from src.lcoe import renewables_2050_lcoe
from src.units import Units as U
from src.units import ureg
from src.utils import annualised_cost, convert_energy_cost

# UK Energy Modelling Assumptions
# This module contains key assumptions and parameters used throughout the energy modelling analysis

# ============================================================================
# PHYSICAL CONSTANTS
# ============================================================================
MolecularWeightCO2 = 44.01 * U.g / U.mol  # g/mol
HoursPerDay = 24 * U.h
HoursPerYear = HoursPerDay * 365.25  # Including leap years

# ============================================================================
# PROJECTED DEMAND AND EMISSIONS TARGETS
# ============================================================================

CB7EnergyDemand2050 = 692 * U.TWh  # Seventh Carbon Budget energy demand target for 2050
EnergyDemand2050 = CB7EnergyDemand2050
CB7EnergyDemand2050Buildings = 355.44 * U.TWh  # Seventh Carbon Budget energy demand for buildings in 2050
CB7FractionHeatDemandBuildings = 0.597  # Fraction of energy demand from buildings that is for heating in 2050

FractionHeatDemandSpaceHeating = 0.65  # Fraction of building heating demand that is for space heating - This is an unmotivated assumption for now
CB7FractionSpaceHeatDemandBuildings = CB7FractionHeatDemandBuildings * FractionHeatDemandSpaceHeating  # only space heating

# CO2 emissions targets and constraints
CO2Emissions2050 = 59  # Mt CO2 - Maximum emissions allowed in 2050
TotalCO2EmissionsCap19902100 = 29636  # Mt CO2 - Total carbon budget 1990-2100
TotalCO2EmissionsCap19902050 = 26626  # Mt CO2 - Total carbon budget 1990-2050
NetNegativeRemovals = 592.720  # Mt CO2 - Yearly removals required to achieve net negative

# ============================================================================
# ECONOMIC PARAMETERS
# ============================================================================

DiscountRate = 0.05
GBPToUSD = 1.35  # 2024 Average Closing USD/GBP exchange rate
GBPToEuro = 1.18  # Just use the number from the RS report


# ============================================================================
# POWER SYSTEM
# ============================================================================
class PowerSystem:
    # Transmission and distribution losses in the energy system
    # This is taken by taking the ratio of the CB7 hourly demand data (which is supply side),
    # to the demand in the main CB7 workbook (which is end use demand).
    # Other sources:
    # - FES 2025 states that transmission losses are around 2% today but increasing to 3% by 2050
    # - DUKES 2024 says that 2023 total losses are around 9%
    TotalLosses = 0.113


class DispatchableGasCCS:
    Capacity = 18 * U.GW  # CB7 (Table 7.5.1): 38 GW total capacity (shared with generation from hydrogen). FES 2025 (Table 32) has 48.3 GW.
    Efficiency = 0.55  # Electrical efficiency of CCGT with CCS
    LCOE = (
        114 * U.GBP / U.MWh
    )  # from CB7 (Table 7.5.1): 165-194 £/MWh. Price includes generation from hydrogen so this is not accurate. will be 376.7 from emergency deployment paper.


class GasTechnologies:
    """Performance characteristics for common gas-based generation technologies."""

    class CCGT:
        ElectricalEfficiency = 0.55  # Fraction, 55%
        WasteHeatFraction = 0.45  # Fraction of input energy available as waste heat
        StackTemperatureRange = (
            ureg.Quantity(80, U.degC),
            ureg.Quantity(150, U.degC),
        )
        CondenserTemperatureRange = (
            ureg.Quantity(25, U.degC),
            ureg.Quantity(40, U.degC),
        )

    class GasTurbineSimpleCycle:
        ElectricalEfficiencyRange = (0.30, 0.35)  # Fraction, 30-35%
        WasteHeatFractionRange = (0.65, 0.70)  # Fraction of input energy available as waste heat
        ExhaustTemperatureRange = (
            ureg.Quantity(450, U.degC),
            ureg.Quantity(600, U.degC),
        )

    class CCGTWithoutSteamCycle:
        ElectricalEfficiency = 0.35  # Fraction, 35%
        WasteHeatFraction = 0.65  # Fraction of input energy available as waste heat
        ExhaustTemperatureRange = (
            ureg.Quantity(450, U.degC),
            ureg.Quantity(600, U.degC),
        )
        UsableTemperatureAfterHeatExchangerRange = (
            ureg.Quantity(80, U.degC),
            ureg.Quantity(120, U.degC),
        )


class Interconnectors:
    Config: ClassVar[dict] = {
        "France": {"Capacity": 10 * U.GW, "LCOE": 10 * U.GBP / U.MWh},
        "Ireland": {"Capacity": 2 * U.GW, "LCOE": 15 * U.GBP / U.MWh},
        "Netherlands": {"Capacity": 3 * U.GW, "LCOE": 20 * U.GBP / U.MWh},
        "Germany": {"Capacity": 3 * U.GW, "LCOE": 25 * U.GBP / U.MWh},
        "Belgium": {"Capacity": 3 * U.GW, "LCOE": 30 * U.GBP / U.MWh},
        "Denmark": {"Capacity": 2 * U.GW, "LCOE": 35 * U.GBP / U.MWh},
        "Norway": {"Capacity": 2 * U.GW, "LCOE": 40 * U.GBP / U.MWh},
    }


# ============================================================================
# RENEWABLE ENERGY
# ============================================================================


class Renewables:
    """Parameters for renewable energy technologies including solar, offshore wind, and onshore wind."""

    class CapacityRatios:
        """Mix ratios for different renewable technologies in the energy portfolio.

        Source: CB7 Table 7.5.1
        """

        Solar = 0.4
        OffshoreWind = 0.45
        OnshoreWind = 0.15

    class CapacityFactors:
        """Average capacity factors (fraction of nominal capacity achieved).

        Note that these numbers are not used by the core simulation, they are obtained
        as a time series from renewables.ninja instead.
        """

        Solar = 0.108
        OffshoreWind = 0.383  # 61% according to Department for Net Zero
        OnshoreWind = 0.293  # 45% according to Department for Net Zero

    class LCOE:
        """Levelized Cost of Energy.

        Source: DESNZ Electricity Generation Costs 2025 (Annex A/B methodology),
        computed via src.lcoe for 2050 commissioning, Medium hurdle-rate scenario.
        """

        Solar = renewables_2050_lcoe("Large Scale Solar PV")["total"]
        OffshoreWind = renewables_2050_lcoe("Fixed Offshore Wind")["total"]
        OnshoreWind = renewables_2050_lcoe("Onshore Wind")["total"]

    # LCOE recomputed using this model's own capacity factors (CapacityFactors,
    # derived from renewables.ninja hourly data) instead of DESNZ Annex A's
    # reference-plant load factor. LCOE.* stays on the DESNZ Annex A load
    # factor so it remains checkable against DESNZ's own published figures
    # (see tests/test_lcoe.py); ModelImpliedLCOE.* shows what the £/MWh cost
    # looks like if the plant instead achieves this model's simulated average
    # utilisation, which differs from the Annex A assumption (e.g. offshore
    # wind: 0.5 in Annex A vs CapacityFactors.OffshoreWind here). Built via
    # type() rather than a nested `class` statement because a nested class
    # body can't see names (like CapacityFactors) from its enclosing class body.
    ModelImpliedLCOE = type(
        "ModelImpliedLCOE",
        (),
        {
            "Solar": renewables_2050_lcoe("Large Scale Solar PV", load_factor=CapacityFactors.Solar)["total"],
            "OffshoreWind": renewables_2050_lcoe("Fixed Offshore Wind", load_factor=CapacityFactors.OffshoreWind)["total"],
            "OnshoreWind": renewables_2050_lcoe("Onshore Wind", load_factor=CapacityFactors.OnshoreWind)["total"],
        },
    )

    # Calculated weighted average capacity factor across all renewable technologies
    AverageCapacityFactor = (
        CapacityFactors.Solar * CapacityRatios.Solar
        + CapacityFactors.OffshoreWind * CapacityRatios.OffshoreWind
        + CapacityFactors.OnshoreWind * CapacityRatios.OnshoreWind
    )

    AverageLCOE = LCOE.Solar * CapacityRatios.Solar + LCOE.OffshoreWind * CapacityRatios.OffshoreWind + LCOE.OnshoreWind * CapacityRatios.OnshoreWind

    AverageModelImpliedLCOE = (
        ModelImpliedLCOE.Solar * CapacityRatios.Solar
        + ModelImpliedLCOE.OffshoreWind * CapacityRatios.OffshoreWind
        + ModelImpliedLCOE.OnshoreWind * CapacityRatios.OnshoreWind
    )


# ============================================================================
# NUCLEAR POWER
# ============================================================================


class Nuclear:
    """Parameters for nuclear power generation technologies."""

    Capacity = 12 * U.GW  # was 12 GW in CB7 (Table 7.5.1), FES 2025 (Table 32) has 24.1 GW.
    CapacityFactor = 0.9  # Based on Hinkley Point C performance

    class CapacityRatios:
        """Mix ratios for different nuclear technologies in the nuclear portfolio."""

        Existing = 0.2  # Including Hinkley Point C
        LargeReactors = 0.2
        SmallReactors = 0.6  # Small modular reactors (SMRs)

    class LCOE:
        """Levelized Cost of Energy for nuclear technologies."""

        Existing = 130.0 * U.GBP / U.MWh
        LargeReactors = 80.0 * U.GBP / U.MWh
        SmallReactors = 60.0 * U.GBP / U.MWh  # Small modular reactors

    # Calculated weighted average LCOE across all nuclear technologies
    AverageLCOE = (
        LCOE.Existing * CapacityRatios.Existing
        + LCOE.LargeReactors * CapacityRatios.LargeReactors
        + LCOE.SmallReactors * CapacityRatios.SmallReactors
    )


# ============================================================================
# MEDIUM-TERM ENERGY STORAGE
# ============================================================================
class MediumTermStorage:
    # from CB7 (Table 7.5.1)
    Power = 39.3 * U.GW  # FES 2025 (Table 28) has 39.3 GW
    Capacity = 0.433 * U.TWh  # Energy capacity of the medium-term storage system
    RoundTripEfficiency = 0.70  # Round-trip efficiency for medium-term storage
    LCOE = (
        100 * U.GBP / U.MWh
    )  # Levelized Cost of Energy for medium-term storage (this is a placeholder, the actual cost will depend on the specific technology used)


# ============================================================================
# HYDROGEN STORAGE
# ============================================================================
class HydrogenStorage:
    """Parameters for hydrogen energy storage system including electrolysis, cavern storage, and generation."""

    class Electrolysis:
        """Parameters for hydrogen generation via electrolysis."""

        # Source: IEA via RS report

        Power = 40 * U.GW  # Electrolyser power capacity #40
        Efficiency = 0.74  # Converting electrical energy to hydrogen
        Capex = 450 / GBPToUSD * U.GBP / U.kW
        Opex = Capex * 0.015
        Lifetime = 30  # years

        AnnualisedCost = annualised_cost(Capex, Opex, Lifetime, DiscountRate)

    class CavernStorage:
        """Parameters for large-scale hydrogen storage in underground caverns."""

        # For Capex, H21 NOE assumes £325M for 1.22 TWh. CS Smith et al (2023)
        # take the midpoint of 1-2x this number, which is £399.59M per TWh.

        Capacity = 50.0 * U.TWh  # CB7 has 5-9 TWh, FES 2025 (Table 38) has 12 TWh. #50
        Efficiency = 0.407  # Round-trip efficiency (electrolysis * generation efficiencies
        Capex = 400 * U.GBP / U.MWh
        Opex = Capex * 0.015
        Lifetime = 30  # years

        AnnualisedCost = annualised_cost(Capex, Opex, Lifetime, DiscountRate)

    class Generation:
        """Parameters for electricity generation from stored hydrogen."""

        Power = 100 * U.GW  # FES 2025 (Table 29) has 16.5 GW (+ constraints on combined capacity with gas+CCS, see above)
        Efficiency = 0.55  # Converting stored hydrogen back to electricity
        Capex = 425 / GBPToUSD * U.GBP / U.kW
        Opex = Capex * 0.015
        Lifetime = 30  # years

        AnnualisedCost = annualised_cost(Capex, Opex, Lifetime, DiscountRate)


# ============================================================================
# DIRECT AIR CAPTURE (DAC)
# ============================================================================


class DAC:
    """Parameters for Direct Air Capture technology."""

    # System capacity parameters
    Capacity = 1.1 * U.GW

    CarbonStorage = 7.5  # GBP/tonne CO2

    LCOR = 106.8 * U.GBP / U.t  # Levelized Cost of Removal (LCOR) for DAC, including carbon storage costs

    class EnergyCost:
        """Energy requirements for DAC processes."""

        Low = 43 * U.kJ / U.mol
        Medium = 101 * U.kJ / U.mol
        High = 162 * U.kJ / U.mol

        # Energy cost per unit CO2 removed (TWh/Mt)
        LowTWhPerMtCO2 = convert_energy_cost(Low, MolecularWeightCO2)
        MediumTWhPerMtCO2 = convert_energy_cost(Medium, MolecularWeightCO2)
        HighTWhPerMtCO2 = convert_energy_cost(High, MolecularWeightCO2)


class LTDAC:
    """Parameters for low-temperature DAC driven by CCGT waste heat."""

    GasInputPerTonCO2 = 1.1389 * U.MWh / U.t_mt  # Gas input per tonne of CO2 captured
    HeatPerTonCO2 = 4 * U.GJ / U.t_mt  # Heat input required per tonne of CO2 captured (Deprecated)
    ElectricityPerTonCO2 = 0.331122 * U.MWh / U.t_mt  # Auxiliary electricity per tonne of CO2
    RegenerationEfficiency = 0.9  # Process efficiency factor for LT DAC
    LCOE = 193 * U.GBP / U.t  # Cost per tonne of CO2 captured (THIS IS INCORRECT, just a placeholder for now)
    LCOR = 119 * U.GBP / U.t  # Levelized Cost of Removal (LCOR) for low-temperature DAC, including carbon storage costs


# E-DAC (electricity-driven DAC)
class EDAC:
    """Economic parameters for electricity-driven DAC (E-DAC).

    The reference plant costs USD 31 million for 45.6 ktCO2/year of
    nameplate capture capacity. Costs are converted to GBP using the common
    project exchange-rate assumption above. A tonne in the capacity
    denominator means one tonne/year of installed capture capability; it is
    not an assumption that the plant actually captures that amount.
    """

    # Reference equipment CAPEX and nameplate capture capacity. Total CAPEX
    # scales linearly with installed nameplate capacity unless a separate
    # scale relationship is introduced in future.
    ReferenceCapex = 31e6 / GBPToUSD * U.GBP
    ReferenceAnnualCaptureCapacity = 45.6e3 * U.t
    CapexPerAnnualCaptureCapacity = ReferenceCapex / ReferenceAnnualCaptureCapacity

    # Fixed, non-labour OPEX is incurred on installed equipment regardless of
    # how often it runs. It must not be multiplied by the simulated capacity
    # factor; low utilisation instead raises LCOR by reducing its denominator.
    FixedOpexFraction = 0.025

    # CAPEX is annualised with a 20-year economic life. The central model uses
    # 5%; 10% is retained as an explicit sensitivity case.
    Lifetime = 20
    CentralDiscountRate = 0.05
    SensitivityDiscountRate = 0.10

    # Learning rates are cost reductions for each doubling of cumulative
    # E-DAC deployment, applied separately to CAPEX and fixed OPEX.
    CapexLearningRate = 0.14
    OpexLearningRate = 0.025

    # Technology learning depends on industry-wide cumulative deployment, not
    # the size of the single UK system being simulated.
    ReferenceCumulativeDeployment = ReferenceAnnualCaptureCapacity

    # Assumed global cumulative E-DAC/BPMED deployment by 2050. Source: team
    # assumption, TBC (see Q_2050 note in project discussion).
    CumulativeDeployment = 9.0e6 * U.t
    CapexLearningExponent = math.log2(1 - CapexLearningRate)
    OpexLearningExponent = math.log2(1 - OpexLearningRate)
    DeploymentRatio = (CumulativeDeployment / ReferenceCumulativeDeployment).to(U.dimensionless).magnitude
    LearnedCapexPerAnnualCaptureCapacity = CapexPerAnnualCaptureCapacity * DeploymentRatio**CapexLearningExponent
    LearnedFixedOpexPerAnnualCaptureCapacity = CapexPerAnnualCaptureCapacity * FixedOpexFraction * DeploymentRatio**OpexLearningExponent

    # Historical whole-cost proxy retained only for reproducing/comparing the
    # old model. It is deliberately excluded from the new CAPEX + OPEX LCOR.
    LegacyElectricityCost = 56.84 * U.GBP / U.MWh


# https://www.sciencedirect.com/science/article/pii/S2542435118302253?fr=RR-2&ref=pdf_download&rr=9a6c2b6339f763d5


class GasTechDACParameters:
    """Parameters from nbs/Gas_techs_update.ipynb for gas generation with DAC."""

    # Heat needed for each tonne of CO2 captured via low-temperature DAC
    HeatPerTonCO2 = 1.1389 * U.MWh / U.t
    # Gross emission intensity of gas-fired generation
    GasCO2Intensity = 0.34 * U.t / U.MWh
    # Capture cost used for quick scaling of DAC spending
    CaptureCostPerTon = 600 * U.GBP / U.t

    TechnologyParameters: ClassVar[dict] = {
        "CCGT (normal combined cycle)": {
            "ElectricalEfficiency": 0.55,
            "WasteHeatFraction": 0.45,
            "LowTemperatureFraction": 1.00,
            "WasteHeatTemperature": ureg.Quantity(171, U.degC),
            "DACElectricityPerTonCO2": LTDAC.ElectricityPerTonCO2.to(U.MWh / U.t),
        },
        "Gas Turbine (simple cycle)": {
            "ElectricalEfficiency": 0.325,
            "WasteHeatFraction": 0.675,
            "LowTemperatureFraction": 0.15,
            "WasteHeatTemperature": ureg.Quantity(538, U.degC),
            "DACElectricityPerTonCO2": LTDAC.ElectricityPerTonCO2.to(U.MWh / U.t),
        },
        "CCGT with E-DAC": {
            "ElectricalEfficiency": 0.35,
            "WasteHeatFraction": 0.65,
            "LowTemperatureFraction": 0.20,
            "WasteHeatTemperature": ureg.Quantity(538, U.degC),
            "DACElectricityPerTonCO2": 1.25 * U.MWh / U.t,
        },
    }

    # Example scenario used in the notebook to illustrate outputs
    ExampleGenerationTWh: ClassVar[dict[str, float]] = {
        "CCGT (normal combined cycle)": 150,
        "Gas Turbine (simple cycle)": 20,
        "CCGT with E-DAC": 10,
    }


# ============================================================================
# MISCELLANEOUS
# ============================================================================
AdditionalCosts = 4 * U.GBP / U.MWh  # Transport Rapid Response Costs
