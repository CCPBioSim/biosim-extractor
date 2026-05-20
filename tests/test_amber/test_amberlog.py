import tempfile
import os
import json
import pytest
from biosim_extractor.amber.amberlog import AmberLogParser

# Helper to write a temporary log file
def write_temp_log(content: str) -> str:
    fd, path = tempfile.mkstemp(suffix=".log")
    with os.fdopen(fd, "w") as f:
        f.write(content)
    return path

def test_parse_simulation_settings_and_file_assignments():
    log_content = """
 &cntrl
  nstlim=5000, temp0=300.0, ntb=2,
 /
 File Assignments:
 | INPF: input.in
 | OUTF: output.out
 | REST: restrt.rst
 NSTEP = 1 TIME = 0.0 TEMP = 300.0
"""
    path = write_temp_log(log_content)
    parser = AmberLogParser(path)
    data = parser.parse()
    os.remove(path)

    # Check cntrl block
    assert "cntrl" in data["SimulationSettings"]
    assert data["SimulationSettings"]["cntrl"]["nstlim"] == 5000
    assert data["SimulationSettings"]["cntrl"]["temp0"] == 300.0

    # Check file assignments
    fa = data["SimulationSettings"]["File_Assignments"]
    assert fa["INPF"] == "input.in"
    assert fa["OUTF"] == "output.out"
    assert fa["REST"] == "restrt.rst"

def test_parse_block_and_timings():
    log_content = """
A V E R A G E S
TEMP = 300.0 PRESS = 1.0
R M S  F L U C T U A T I O N S
| Total CPU time 12.34 seconds
| Total wall time: 15.67 seconds
"""
    path = write_temp_log(log_content)
    parser = AmberLogParser(path)
    parser.lines = log_content.splitlines(keepends=True)
    parser._parse_block("A V E R A G E S", "R M S  F L U C T U A T I O N S", "Averages")
    parser._parse_timings()
    os.remove(path)

    results = parser.data["Results"]
    assert results["Averages"]["TEMP"] == 300.0
    assert results["Averages"]["PRESS"] == 1.0
    assert "Total_wall_time" in results["Timings"]
    assert results["Timings"]["Total_wall_time"] == 15.67

def test_parse_time_series():
    log_content = """
NSTEP = 1 TIME = 0.0 TEMP = 300.0
NSTEP = 2 TIME = 2.0 TEMP = 301.0
A V E R A G E S
"""
    path = write_temp_log(log_content)
    parser = AmberLogParser(path)
    parser.lines = log_content.splitlines(keepends=True)
    parser._parse_time_series()
    os.remove(path)

    ts = parser.data["Results"]["TimeSeries"]
    assert len(ts) == 2
    assert ts[0]["NSTEP"] == 1
    assert ts[1]["TEMP"] == 301.0

def test_parse_full_log(monkeypatch):
    # Patch out helpers to avoid import errors if helpers are not present
    import builtins
    import types
    dummy_helpers = types.SimpleNamespace(
        parse_value=lambda x: float(x) if "." in x or "e" in x.lower() else int(x),
        add_value=lambda d, k, v: d.setdefault(k, v),
        normalize_name=lambda x: x.strip().replace(" ", "_")
    )
    monkeypatch.setitem(__import__("sys").modules, "biosim_extractor.helpers.log_utils", dummy_helpers)

    log_content = """
 &cntrl
  nstlim=1000, temp0=310.0,
 /
 File Assignments:
 | INPF: in.in
 | OUTF: out.out
NSTEP = 1 TIME = 0.0 TEMP = 310.0
A V E R A G E S
  TEMP = 310.0
R M S  F L U C T U A T I O N S
CPU time: Total : 10.0 seconds
"""
    path = write_temp_log(log_content)
    parser = AmberLogParser(path)
    data = parser.parse()
    os.remove(path)

    assert data["SimulationSettings"]["cntrl"]["nstlim"] == 1000
    assert data["SimulationSettings"]["File_Assignments"]["INPF"] == "in.in"
    assert "Averages" in data["Results"]
    assert "Timings" in data["Results"]
