import src.assumptions as A
from src import utils
from src.units import Units as U
from tests.config import check


def test_convert_energy_cost() -> None:
    result = utils.convert_energy_cost(400 * U.kJ / U.mol, A.MolecularWeightCO2)
    expected = 2.52468 * U.TWh / U.Mt
    check(result, expected)
