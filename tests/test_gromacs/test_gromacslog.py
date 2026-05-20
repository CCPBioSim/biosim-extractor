import json
import os

import pytest

from biosim_extractor.gromacs.gromacslog import GromacsLogParser, main


@pytest.fixture(scope="module")
def log_path():
    return os.path.join(
        os.path.dirname(__file__), "example_files", "1AKI_production.log"
    )


@pytest.fixture(scope="module")
def parsed_data(log_path):
    parser = GromacsLogParser(log_path)
    return parser.parse()


def test_missing_input_parameters(monkeypatch, tmp_path):
    # Log with no Input Parameters or qm-opts
    log = "GROMACS version: 2022.1\n"
    log_path = tmp_path / "no_input_params.log"
    log_path.write_text(log)
    parser = GromacsLogParser(str(log_path))
    data = parser.parse()
    # Should not raise, and data should be a dict
    assert isinstance(data, dict)
    # Should not contain Input Parameters
    assert "Input Parameters" not in data


def test_partial_indented_block(tmp_path):
    # Log with incomplete indented block
    log = "Input Parameters:\n  integrator: md\n  nsteps:\n"
    log_path = tmp_path / "partial_block.log"
    log_path.write_text(log)
    parser = GromacsLogParser(str(log_path))
    data = parser.parse()
    assert "Input Parameters" in data
    assert "integrator" in data["Input Parameters"]
    # nsteps should be present but None or empty string
    assert "nsteps" in data["Input Parameters"]


def test_summary_only(tmp_path):
    # Log with only summary section
    log = "Performance:  123.4  0.56\nTime:\n  111.1  222.2\n"
    log_path = tmp_path / "summary_only.log"
    log_path.write_text(log)
    parser = GromacsLogParser(str(log_path))
    data = parser.parse()
    assert "Summary" in data
    assert data["Summary"]["Performance"]["(ns/day)"] == 123.4
    assert data["Summary"]["Time"]["Core t (s)"] == 111.1


def test_averages_only(tmp_path):
    # Log with only averages block
    log = (
        "A V E R A G E S\n"
        "Statistics over 10 steps, 5 frames\n"
        "Box-X Box-Y Box-Z\n"
        "  1.0  2.0  3.0\n"
    )
    log_path = tmp_path / "averages_only.log"
    log_path.write_text(log)
    parser = GromacsLogParser(str(log_path))
    data = parser.parse()
    av = data.get("Averages", {})
    assert av["total-steps"] == 10
    assert av["Box-X"] == 1.0


def test_cli_entrypoint(tmp_path, log_path, monkeypatch):
    # Test the CLI main() function
    output_file = tmp_path / "out.json"
    monkeypatch.setattr(
        "sys.argv", ["gromacslog.py", log_path, "--output", str(output_file)]
    )
    main()
    assert output_file.exists()
    with open(output_file) as f:
        data = json.load(f)
    assert "Summary" in data


def test_parse_twice(log_path):
    # Ensure repeated parsing is consistent
    parser = GromacsLogParser(log_path)
    data1 = parser.parse()
    data2 = parser.parse()
    assert data1 == data2


def test_parse_with_nonexistent_file(tmp_path):
    # Should raise FileNotFoundError
    fake_path = tmp_path / "does_not_exist.log"
    with pytest.raises(FileNotFoundError):
        GromacsLogParser(str(fake_path)).parse()
