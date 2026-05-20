import pytest
from biosim_extractor.units.unitconversion import UnitConverter

def test_length_conversion():
    uc = UnitConverter()
    assert uc.convert(10, 'nm') == 10
    assert uc.convert(10, 'Å') == 1
    assert uc.convert([10, 20], 'Å') == [1, 2]
    assert uc.convert(1, 'm') == 1e9

def test_energy_conversion():
    uc = UnitConverter()
    assert uc.convert(1, 'kcal/mol', 'energy') == pytest.approx(4.184)
    assert uc.convert(1, 'kJ/mol', 'energy') == 1

def test_temperature_conversion():
    uc = UnitConverter()
    assert uc.convert(0, 'C', 'temperature') == 273.15
    assert uc.convert(32, 'F', 'temperature') == pytest.approx(273.15)
    assert uc.convert(300, 'K', 'temperature') == 300

def test_is_standard_unit_and_needs_conversion():
    uc = UnitConverter()
    assert uc.is_standard_unit('nm')
    assert not uc.is_standard_unit('Å')
    assert not uc.needs_conversion('nm')
    assert uc.needs_conversion('Å')

def test_get_unit_type():
    uc = UnitConverter()
    assert uc.get_unit_type('nm') == 'length'
    assert uc.get_unit_type('kJ/mol') == 'energy'
    assert uc.get_unit_type('foobar') is None

def test_get_target_unit():
    uc = UnitConverter()
    assert uc.get_target_unit('Å') == 'nm'
    with pytest.raises(ValueError):
        uc.get_target_unit('foobar')

def test_convert_with_unit():
    uc = UnitConverter()
    val, unit = uc.convert_with_unit(10, 'Å')
    assert val == 1
    assert unit == 'nm'

def test_call_equivalent_to_convert():
    uc = UnitConverter()
    assert uc(10, 'Å') == 1
    assert uc([10, 20], 'Å') == [1, 2]

def test_unknown_unit_type_raises():
    uc = UnitConverter()
    with pytest.raises(ValueError):
        uc.convert(1, 'foobar')

def test_unknown_unit_raises():
    uc = UnitConverter()
    with pytest.raises(ValueError):
        uc.convert(1, 'nm', 'energy')  # nm is not an energy unit

def test_unknown_unit_in_convert_with_unit():
    uc = UnitConverter()
    with pytest.raises(ValueError):
        uc.convert_with_unit(1, 'foobar')