#!/usr/bin/env python
"""
Extract AMBER log file metadata into a structured dictionary.

This script parses AMBER log files and outputs structured metadata as JSON.
It can be used as a standalone CLI tool or imported as a module.
"""

import re
import json
import argparse
from biosim_extractor.helpers.log_utils import parse_value, add_value, normalize_name


# -------------------------
# PARSER
# -------------------------
class AmberLogParser:
    """
    Parser for AMBER log files.
    """
    def __init__(self, filepath):
        """
        Args:
            filepath (str): Path to the AMBER log file.
        """
        self.filepath = filepath
        self.lines = []
        self.data = {
            # "Header": {},
            "SimulationSettings": {},
            "Results": {
                "TimeSeries": [],
                "Averages": {},
                "RMSFluctuations": {},
                "Timings": {},
            },
        }

    # -------------------------
    # PUBLIC API
    # -------------------------
    def parse(self):
        """
        Parse the AMBER log file.

        Returns:
            dict: Parsed metadata.
        """
        with open(self.filepath) as f:
            self.lines = f.readlines()

        # self._parse_header()
        self._parse_simulation_settings()
        self._parse_results()
        # print(json.dumps(self.data, indent=2))
        return self.data

    # # -------------------------
    # # HEADER
    # # -------------------------
    # def _parse_header(self):
    #     for line in self.lines[:200]:
    #         if "=" in line:
    #             parts = line.split(",")[0].split("=")
    #             if len(parts) == 2:
    #                 key, val = parts
    #                 add_value(self.data["Header"], key.strip(), parse_value(val))

    # -------------------------
    # SIMULATION SETTINGS
    # -------------------------
    def _parse_simulation_settings(self):
        """
        Parse simulation settings from the log file.
        """
        settings = self.data["SimulationSettings"]
        current_section = None
        capture_cntrl = False

        for line in self.lines:
            stripped = line.strip()

            # Stop at time series
            if "NSTEP" in line and "TIME" in line:
                break

            # -------------------------
            # &cntrl block
            # -------------------------
            if "&cntrl" in stripped:
                capture_cntrl = True
                current_section = "cntrl"
                settings[current_section] = {}
                continue

            if capture_cntrl:
                if "/" in stripped:
                    capture_cntrl = False
                    current_section = None
                    continue

                for part in stripped.split(","):
                    if "=" in part:
                        k, v = part.split("=")
                        add_value(settings["cntrl"], k.strip(), parse_value(v))
                continue

            # -------------------------
            # Colon sections
            # -------------------------
            if stripped.endswith(":") and "=" not in stripped:
                section_name = normalize_name(stripped[:-1])
                current_section = section_name
                settings[current_section] = {}
                continue

            # -------------------------
            # Key-value pairs
            # -------------------------
            if "=" in line:
                matches = re.findall(r"([A-Za-z0-9_\-\s]+?)\s*=\s*([-\d\.E+]+)", line)

                for k, v in matches:
                    key = normalize_name(k)
                    val = parse_value(v)

                    if current_section:
                        add_value(settings[current_section], key, val)
                    else:
                        add_value(settings, key, val)

            # Reset section on blank line
            if not stripped:
                current_section = None

        self._parse_file_assignments(settings)

    # -------------------------
    # SETTINGS: FILE ASSIGNMENTS
    # -------------------------
    def _parse_file_assignments(self, settings):
        """
        Parse file assignments from the log file.

        Args:
            settings (dict): Simulation settings dictionary to update.
        """
        capture = False
        files = {}

        pattern = r"\|\s*([A-Z0-9_]+):\s*(.+)"

        for line in self.lines:
            stripped = line.strip()

            # Start block
            if "File Assignments:" in line:
                capture = True
                continue

            if capture:
                # Stop if block ends
                if not stripped or not stripped.startswith("|"):
                    break

                match = re.search(pattern, line)
                if match:
                    key = match.group(1).strip()
                    val = match.group(2).strip()

                    files[key] = val

        if files:
            settings["File_Assignments"] = files

    # -------------------------
    # RESULTS (ALL OUTPUT DATA)
    # -------------------------
    def _parse_results(self):
        """
        Parse results blocks from the log file.
        """
        # self._parse_time_series()
        self._parse_block("A V E R A G E S", "R M S  F L U C T U A T I O N S", "Averages")
        # self._parse_block("R M S  F L U C T U A T I O N S", "TIMINGS", "RMSFluctuations")
        self._parse_timings()

    # -------------------------
    # TIME SERIES
    # -------------------------
    def _parse_time_series(self):
        """
        Parse time series data from the log file.
        """
        steps = []
        current = {}
        in_series = False

        for line in self.lines:
            if "NSTEP" in line and "TIME" in line:
                in_series = True
                if current:
                    steps.append(current)
                    current = {}

                matches = re.findall(r"([A-Za-z\(\)\-]+)\s*=\s*([-\d\.E+]+)", line)
                for k, v in matches:
                    current[k] = parse_value(v)
                continue

            if in_series and "=" in line:
                matches = re.findall(r"([A-Za-z\(\)\-]+)\s*=\s*([-\d\.E+]+)", line)
                for k, v in matches:
                    current[k] = parse_value(v)

            if "A V E R A G E S" in line:
                break

        if current:
            steps.append(current)

        self.data["Results"]["TimeSeries"] = steps

    # -------------------------
    # GENERIC BLOCK PARSER
    # -------------------------
    def _parse_block(self, start_marker, end_marker, target_key):
        """
        Parse a generic results block.

        Args:
            start_marker (str): Line indicating the start of the block.
            end_marker (str): Line indicating the end of the block.
            target_key (str): Key in the results dictionary to populate.
        """
        capture = False
        target = self.data["Results"][target_key]

        for line in self.lines:
            if start_marker in line:
                capture = True
                continue

            if capture and "=" in line:
                matches = re.findall(r"([A-Za-z\(\)\-]+)\s*=\s*([-\d\.E+]+)", line)
                for k, v in matches:
                    add_value(target, k, parse_value(v))

            if end_marker in line:
                break

    # -------------------------
    # TIMINGS
    # -------------------------
    def _parse_timings(self):
        """
        Parse timing information from the log file.
        """
        timings = self.data["Results"]["Timings"]
        pattern = r"\|\s*(.*?)\s*:\s*([-\d\.E+]+)\s*seconds"

        for line in self.lines:
            if "CPU time" in line or "wall time" in line:
                match = re.search(pattern, line)
                if match:
                    key = normalize_name(match.group(1))
                    val = parse_value(match.group(2))
                    add_value(timings, key, val)

# =========================
# ENTRY POINT
# =========================

def parse_args():
    """Parse command-line arguments.

    Returns:
        Parsed ``argparse.Namespace`` object.
    """
    parser = argparse.ArgumentParser(description="Extract Amber log file metadata to JSON")
    parser.add_argument("logfile", help="Path to Amber log file")
    parser.add_argument("--output", "-o", help="Output file path (default: stdout)")
    return parser.parse_args()


def main():
    """Entry point: parse args, run extraction, and write output."""
    args = parse_args()

    parser = AmberLogParser(args.logfile)
    result = parser.parse()

    if args.output:
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2)
    else:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
