import pytest
from biosim_extractor.helpers import log_utils

def test_parse_value_bool():
    assert log_utils.parse_value("true") is True
    assert log_utils.parse_value("false") is False

def test_parse_value_inf():
    assert log_utils.parse_value("inf") == float("inf")

def test_parse_value_brace_array():
    assert log_utils.parse_value("{1.0, 2.0, 3.0}") == [1.0, 2.0, 3.0]

def test_parse_value_space_list():
    assert log_utils.parse_value("1 2 3") == [1, 2, 3]

def test_parse_value_float():
    assert log_utils.parse_value("3.14") == 3.14
    assert log_utils.parse_value("1e-3") == 0.001

def test_parse_value_int():
    assert log_utils.parse_value("42") == 42

def test_parse_value_fallback():
    assert log_utils.parse_value("not_a_number") == "not_a_number"

def test_add_value_new_key():
    d = {}
    log_utils.add_value(d, "a", 1)
    assert d["a"] == 1

def test_add_value_promote_to_list():
    d = {"a": 1}
    log_utils.add_value(d, "a", 2)
    assert d["a"] == [1, 2]

def test_add_value_append_to_list():
    d = {"a": [1]}
    log_utils.add_value(d, "a", 2)
    assert d["a"] == [1, 2]

def test_normalize_name():
    assert log_utils.normalize_name("foo bar") == "foo_bar"
    assert log_utils.normalize_name("foo-bar!") == "foo_bar"
    assert log_utils.normalize_name("  foo  ") == "foo"

def test_get_array_valid():
    assert log_utils.get_array("{1.0, 2.0, 3.0}") == [1.0, 2.0, 3.0]

def test_get_array_invalid():
    assert log_utils.get_array("no_braces") == "no_braces"