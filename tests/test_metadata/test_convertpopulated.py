from biosim_extractor.metadata.convertpopulated import convert_populated_metadata_units


def test_scalar_conversion():
    data = {"length": {"value": 10, "value_unit": "Å"}}
    result = convert_populated_metadata_units(data)
    assert result["length"]["value"] == 1.0
    assert result["length"]["value_unit"] == "nm"


def test_vector_conversion():
    data = {"box": {"vector_value": [10, 20], "value_unit": "Å"}}
    result = convert_populated_metadata_units(data)
    assert result["box"]["vector_value"] == [1.0, 2.0]
    assert result["box"]["value_unit"] == "nm"


def test_nested_conversion():
    data = {"outer": {"inner": {"energy": {"value": 1, "value_unit": "kcal/mol"}}}}
    result = convert_populated_metadata_units(data)
    assert result["outer"]["inner"]["energy"]["value"] == 4.184
    assert result["outer"]["inner"]["energy"]["value_unit"] == "kJ/mol"


def test_no_conversion_needed():
    data = {"temperature": {"value": 300, "value_unit": "K"}}
    result = convert_populated_metadata_units(data)
    assert result["temperature"]["value"] == 300
    assert result["temperature"]["value_unit"] == "K"


def test_error_on_unknown_unit():
    data = {"foo": {"value": 1, "value_unit": "unknown_unit"}}
    try:
        convert_populated_metadata_units(data)
        assert False, "Should have raised ValueError"
    except ValueError:
        pass
