import types
import warnings

import pytest

import biosim_extractor.metadata.validatemetadata as vs


def test_validate_metadata_no_schema(monkeypatch):
    # Should do nothing if biosimschema_path is None
    vs.validate_metadata({"foo": "bar"}, biosimschema_path=None)


def test_validate_metadata_strict(monkeypatch):
    # Patch validate_extracted to return errors
    monkeypatch.setattr(vs, "validate_extracted", lambda *a, **kw: ["err1", "err2"])
    with pytest.raises(ValueError):
        vs.validate_metadata(
            {"foo": "bar"}, biosimschema_path="dummy.yaml", strict=True
        )


def test_validate_metadata_warning(monkeypatch):
    monkeypatch.setattr(vs, "validate_extracted", lambda *a, **kw: ["err1"])
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        vs.validate_metadata(
            {"foo": "bar"}, biosimschema_path="dummy.yaml", strict=False
        )
        assert any("Schema validation warnings" in str(warn.message) for warn in w)


def test_validate_extracted_matrix_and_vector(monkeypatch):
    # Patch validate to return a dummy report
    class DummyReport:
        results = [
            types.SimpleNamespace(message="errA"),
            types.SimpleNamespace(message="errB"),
        ]

    monkeypatch.setattr(vs, "validate", lambda *a, **kw: DummyReport())
    # Matrix and vector_value
    instance = {
        "foo": {"vector_value": [[1, 2], [3, 4]], "bar": {"vector_value": [1, 2, 3]}}
    }
    errors = vs.validate_extracted(instance, schema_path="dummy.yaml")
    assert "errA" in errors and "errB" in errors


def test__validate_all_vector_values_flat_and_matrix():
    # Flat vector, all numeric
    flat = {"vector_value": [1, 2, 3]}
    assert vs._validate_all_vector_values(flat) == []
    # Flat vector, non-numeric
    flat_bad = {"vector_value": [1, "a", 3]}
    errs = vs._validate_all_vector_values(flat_bad)
    assert any("non-numeric" in e for e in errs)
    # Matrix, all numeric and consistent
    matrix = {"vector_value": [[1, 2], [3, 4]]}
    assert vs._validate_all_vector_values(matrix) == []
    # Matrix, inconsistent row length
    matrix_bad = {"vector_value": [[1, 2], [3]]}
    errs = vs._validate_all_vector_values(matrix_bad)
    assert any("length" in e for e in errs)
    # Matrix, non-numeric
    matrix_bad2 = {"vector_value": [[1, 2], ["a", 4]]}
    errs = vs._validate_all_vector_values(matrix_bad2)
    assert any("non-numeric" in e for e in errs)


def test__strip_all_matrix_vector_values():
    # Should remove matrix vector_value, keep flat
    d = {"foo": {"vector_value": [[1, 2], [3, 4]], "bar": {"vector_value": [1, 2, 3]}}}
    stripped = vs._strip_all_matrix_vector_values(d)
    assert "vector_value" not in stripped["foo"]
    assert "vector_value" in stripped["foo"]["bar"]
    assert stripped["foo"]["bar"]["vector_value"] == [1, 2, 3]
