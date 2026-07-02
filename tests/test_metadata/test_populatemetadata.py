from types import SimpleNamespace

import pytest

from biosim_extractor.metadata import populatemetadata
from biosim_extractor.metadata import populatemetadata as pop


class _NoConvert:
    def get_target_unit(self, u):
        return u

    def needs_conversion(self, u):
        return False

    def convert(self, v, u):
        return v


def test_parse_log_unsupported_engine_raises():
    p = pop.MetadataPopulator(engine="unknown")
    with pytest.raises(ValueError, match="Unsupported engine"):
        p.parse_log()


def test_populate_includes_file_metadata(monkeypatch):
    p = pop.MetadataPopulator(
        schema_path="ignored.json",
        log_file="dummy.log",
        engine="amber",
        store_file_metadata=True,
    )

    monkeypatch.setattr(
        p,
        "load_schema",
        lambda: setattr(
            p, "schema", {"reverse": {"amber": {}}, "forward": {"amber": {}}}
        ),
    )
    monkeypatch.setattr(p, "parse_log", lambda: {})
    monkeypatch.setattr(p, "apply_mapping", lambda: {"SimulationMetadata": {}})
    monkeypatch.setattr(
        pop, "group_files", lambda files, saved, role="other": {"log": files}
    )
    monkeypatch.setattr(
        pop, "files_metadata", lambda saved: [{"file_name": saved["log"][0]}]
    )

    result = p.populate()
    assert result["files"][0]["file_name"] == "dummy.log"


def test_populate_uses_toptraj_branch(monkeypatch):
    p = pop.MetadataPopulator(
        schema_path="ignored.json",
        top_file="a.top",
        traj_file=["a.xtc"],
        store_file_metadata=False,
    )
    monkeypatch.setattr(p, "load_schema", lambda: None)
    monkeypatch.setattr(
        p, "populate_toptraj", lambda: {"SimulationMetadata": {"ok": 1}}
    )

    assert p.populate()["ok"] == 1


def test_apply_mapping_promotes_scalar_to_vector_and_appends():
    p = pop.MetadataPopulator(engine="amber")
    p.converter = _NoConvert()
    p.schema = {
        "reverse": {
            "amber": {
                "x": {"by_path": {"SimulationMetadata.v": {}}},
                "y": {"by_path": {"SimulationMetadata.v": {}}},
                "z": {"by_path": {"SimulationMetadata.v": {}}},
            }
        },
        "forward": {
            "amber": {
                "SimulationMetadata.v": [
                    {"key": "x", "unit": "nm"},
                    {"key": "y", "unit": "nm"},
                    {"key": "z", "unit": "nm"},
                ]
            }
        },
    }
    p.engine_data = {"x": 1.0, "y": 2.0, "z": 3.0}
    p.data = {"SimulationMetadata": {}}

    out = p.apply_mapping()
    assert out["SimulationMetadata"]["v"]["vector_value"] == [1.0, 2.0, 3.0]


def test_apply_mapping_handles_molecule_ids():
    p = pop.MetadataPopulator(engine="amber")
    p.converter = _NoConvert()
    p.schema = {
        "reverse": {
            "amber": {"charge": {"by_path": {"SimulationMetadata.any.charge": {}}}}
        },
        "forward": {
            "amber": {"SimulationMetadata.any.charge": [{"key": "charge", "unit": "e"}]}
        },
    }
    p.engine_data = {"molecule_ids": {"1": {"charge": 1.0, "ignore_me": "x"}}}
    p.data = {"SimulationMetadata": {}}

    out = p.apply_mapping()
    mol = out["SimulationMetadata"]["composition"]["molecule_ID"][0]
    assert mol["charge"]["value"] == 1.0


def test_parse_args_no_file_metadata(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        [
            "prog",
            "m.json",
            "--no-file-metadata",
            "--engine",
            "amber",
            "--logfile",
            "a.log",
        ],
    )
    args = pop.parse_args()
    assert args.store_file_metadata is False


def test_main_prints_json_when_no_output(monkeypatch):
    args = SimpleNamespace(
        mappingschema="m.json",
        biosimschema="b.yaml",
        schema_version="latest",
        schema_cache_dir=None,
        update_schema=False,
        engine="amber",
        logfile="a.log",
        top=None,
        traj=None,
        config=None,
        store_file_metadata=False,
        output=None,
    )

    class DummyPopulator:
        def __init__(self, **kwargs):
            pass

        def populate(self):
            return {"k": 1}

        def validate(self, result, biosimschema_path=None):
            assert biosimschema_path == "b.yaml"

    printed = []
    monkeypatch.setattr(pop, "parse_args", lambda: args)
    monkeypatch.setattr(
        pop, "resolve_schema_inputs", lambda _args: ("m.json", "b.yaml")
    )
    monkeypatch.setattr(pop, "MetadataPopulator", DummyPopulator)
    monkeypatch.setattr("builtins.print", lambda s: printed.append(s))

    pop.main()
    assert printed and '"k": 1' in printed[0]


def test_flatten_dict():
    nested = {"a": 1, "b": {"c": 2, "d": {"e": 3}}}
    flat = populatemetadata.flatten_dict(nested)
    assert flat == {"a": 1, "c": 2, "e": 3}


def test_get_by_path_and_assign_by_path():
    d = {}
    populatemetadata.assign_by_path(d, "foo.bar.baz", 42)
    assert populatemetadata.get_by_path(d, "foo.bar.baz") == 42
    assert populatemetadata.get_by_path(d, "foo.bar.missing") is None


def test_add_to_path():
    d = {"foo": {"bar": []}}
    populatemetadata.add_to_path(d, "foo.bar", 99)
    assert d["foo"]["bar"] == [99]


def test_is_numeric():
    assert populatemetadata.is_numeric("3.14")
    assert populatemetadata.is_numeric(2)
    assert not populatemetadata.is_numeric("abc")


def test_remove_null_parents():
    d = {"a": 1, "b": {"c": None, "d": 2}}
    cleaned = populatemetadata.remove_null_parents(d)
    assert cleaned == {"a": 1}


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
        "forward": {
            "amber": {"SimulationMetadata.bar": [{"key": "foo", "unit": "nm"}]}
        },
    }
    engine_data = {"foo": 1.0}
    # Write schema to file
    schema_path = tmp_path / "schema.json"
    schema_path.write_text(
        '{"reverse": {"amber": {"foo": {"by_path": {"SimulationMetadata.bar": {}}}}}, "forward": {"amber": {"SimulationMetadata.bar": [{"key": "foo", "unit": "nm"}]}}}'
    )

    # Patch AmberLogParser to return engine_data
    class DummyParser:
        def __init__(self, *a, **kw):
            pass

        def parse(self):
            return engine_data

    monkeypatch.setattr(populatemetadata, "AmberLogParser", DummyParser)
    monkeypatch.setattr(populatemetadata, "GromacsLogParser", DummyParser)
    monkeypatch.setattr(populatemetadata, "TopTrajParser", DummyParser)
    monkeypatch.setattr(populatemetadata, "validate_metadata", lambda *a, **kw: None)

    pop = populatemetadata.MetadataPopulator(
        schema_path=str(schema_path),
        log_file="dummy.log",
        engine="amber",
        store_file_metadata=False,
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
        engine="amber",
        store_file_metadata=False,
    )
    pop.data = {"SimulationMetadata": {}}
    monkeypatch.setattr(pop, "parse_log", lambda: engine_data)
    monkeypatch.setattr(pop, "load_schema", lambda: setattr(pop, "schema", schema))
    result = pop.populate()
    assert isinstance(result, dict)


def test_convert_values(monkeypatch):
    pop = populatemetadata.MetadataPopulator()
    pop.converter = type(
        "DummyConverter",
        (),
        {
            "get_target_unit": lambda self, u: "nm",
            "needs_conversion": lambda self, u: True,
            "convert": lambda self, v, u: v,
        },
    )()
    # Single value
    out = pop.convert_values(1.0, {"unit": "nm", "key": "foo"})
    assert out["value"] == 1.0
    # List value, is_vector True
    out = pop.convert_values([1.0, 2.0], {"unit": "nm", "key": "foo"}, is_vector=True)
    assert out["vector_value"] == [1.0, 2.0]
    # Non-numeric
    out = pop.convert_values("abc", {"unit": "nm", "key": "foo"})
    assert out["value"] == "abc"
