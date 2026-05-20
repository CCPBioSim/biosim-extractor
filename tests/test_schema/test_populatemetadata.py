import pytest
from biosim_extractor.metadata import populatemetadata

def test_flatten_dict():
    nested = {'a': 1, 'b': {'c': 2, 'd': {'e': 3}}}
    flat = populatemetadata.flatten_dict(nested)
    assert flat == {'a': 1, 'c': 2, 'e': 3}

def test_get_by_path_and_assign_by_path():
    d = {}
    populatemetadata.assign_by_path(d, "foo.bar.baz", 42)
    assert populatemetadata.get_by_path(d, "foo.bar.baz") == 42
    assert populatemetadata.get_by_path(d, "foo.bar.missing") is None

def test_add_to_path():
    d = {'foo': {'bar': []}}
    populatemetadata.add_to_path(d, "foo.bar", 99)
    assert d['foo']['bar'] == [99]

def test_is_numeric():
    assert populatemetadata.is_numeric("3.14")
    assert populatemetadata.is_numeric(2)
    assert not populatemetadata.is_numeric("abc")

def test_remove_null_parents():
    d = {'a': 1, 'b': {'c': None, 'd': 2}}
    cleaned = populatemetadata.remove_null_parents(d)
    assert cleaned == {'a': 1}

def test_normalize_key():
    assert populatemetadata.normalize_key("  Foo  ") == "foo"
    assert populatemetadata.normalize_key("BAR") == "bar"

def test_transform_value():
    rules = {"A": "alpha", "B": ["Beta"]}
    assert populatemetadata.transform_value("A", rules) == "alpha"
    assert populatemetadata.transform_value("b", rules) == "Beta"
    assert populatemetadata.transform_value("C", rules) is None
    assert populatemetadata.transform_value("A", {}) == "A"

def test_metadata_populator(monkeypatch, tmp_path):
    # Mock schema and engine data
    schema = {
        "reverse": {"amber": {"foo": {"by_path": {"SimulationMetadata.bar": {}}}}},
        "forward": {"amber": {"SimulationMetadata.bar": [{"key": "foo", "unit": "nm"}]}}
    }
    engine_data = {"foo": 1.0}
    # Write schema to file
    schema_path = tmp_path / "schema.json"
    schema_path.write_text('{"reverse": {"amber": {"foo": {"by_path": {"SimulationMetadata.bar": {}}}}}, "forward": {"amber": {"SimulationMetadata.bar": [{"key": "foo", "unit": "nm"}]}}}')

    # Patch AmberLogParser to return engine_data
    class DummyParser:
        def __init__(self, *a, **kw): pass
        def parse(self): return engine_data

    monkeypatch.setattr(populatemetadata, "AmberLogParser", DummyParser)
    monkeypatch.setattr(populatemetadata, "GromacsLogParser", DummyParser)
    monkeypatch.setattr(populatemetadata, "TopTrajParser", DummyParser)
    monkeypatch.setattr(populatemetadata, "validate_metadata", lambda *a, **kw: None)

    pop = populatemetadata.MetadataPopulator(
        schema_path=str(schema_path),
        log_file="dummy.log",
        engine="amber"
    )
    pop.load_schema()
    assert pop.schema["reverse"]["amber"]
    parsed = pop.parse_log()
    assert parsed == engine_data
    pop.engine_data = engine_data
    pop.data = {"SimulationMetadata": {}}
    result = pop.apply_mapping()
    assert "SimulationMetadata" in result or "SimulationMetadata" in pop.data

    # Test populate (integration)
    pop = populatemetadata.MetadataPopulator(
        schema_path=str(schema_path),
        log_file="dummy.log",
        engine="amber"
    )
    pop.data = {"SimulationMetadata": {}}
    monkeypatch.setattr(pop, "parse_log", lambda: engine_data)
    monkeypatch.setattr(pop, "load_schema", lambda: setattr(pop, "schema", schema))
    result = pop.populate()
    assert isinstance(result, dict)

def test_convert_values(monkeypatch):
    pop = populatemetadata.MetadataPopulator()
    pop.converter = type("DummyConverter", (), {
        "get_target_unit": lambda self, u: "nm",
        "needs_conversion": lambda self, u: True,
        "convert": lambda self, v, u: v
    })()
    # Single value
    out = pop.convert_values(1.0, {"unit": "nm", "key": "foo"})
    assert out["value"] == 1.0
    # List value, is_vector True
    out = pop.convert_values([1.0, 2.0], {"unit": "nm", "key": "foo"}, is_vector=True)
    assert out["vector_value"] == [1.0, 2.0]
    # Non-numeric
    out = pop.convert_values("abc", {"unit": "nm", "key": "foo"})
    assert out["value"] == "abc"