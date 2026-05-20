#!/usr/bin/env python
"""
Extract gmx log file metadata into a dictionary.
"""
import re
import json
import argparse
from biosim_extractor.helpers.log_utils import parse_value


class GromacsLogParser:
    """Parser for GROMACS ``.log`` files, extracting header, input parameters, summary, and averages."""
    def __init__(self, filepath):
        """
        Args:
            filepath: Path to the GROMACS log file.
        """
        self.filepath = filepath
        self.lines = []
        self.data = {}
        self.energy_timeseries = []

    # =========================
    # MAIN ENTRY
    # =========================
    def parse(self):
        """Parse the log file and return all extracted data.

        Returns:
            Dictionary containing header fields, input parameters, summary,
            and averages.
        """
        with open(self.filepath) as f:
            self.lines = f.readlines()

        self._parse_header()
        self._parse_indented_blocks()
        self._parse_summary()
        # self._parse_energy_timeseries()
        self._parse_averages()  # new averages parser

        # self.data["Energy Time Series"] = self.energy_timeseries
        # print(json.dumps(self.data, indent=2))
        return self.data

    # =========================
    # HEADER
    # =========================
    def _parse_header(self):
        """Extract top-level key-value fields from the file header (e.g. GROMACS version, compiler)."""
        keys = [
            "Executable", "Data prefix", "Working dir", "Process ID",
            "Command line", "GROMACS version", "Precision", "Memory model",
            "MPI library", "OpenMP support", "GPU support",
            "SIMD instructions", "CPU FFT library", "GPU FFT library",
            "RDTSCP usage", "TNG support", "Hwloc support",
            "Tracing support", "C compiler", "C compiler flags",
            "C++ compiler", "C++ compiler flags",
        ]
        for line in self.lines:
            for key in keys:
                if line.startswith(key):
                    _, val = line.split(":", 1)
                    self.data[key] = val.strip()

    # =========================
    # INDENTED BLOCKS
    # =========================
    def _parse_indented_blocks(self):
        """Parse indented ``key: value`` and ``key = value`` blocks into nested dicts.

        Also collapses ``(3x3)`` matrix entries into lists of rows.
        """
        stack = [(-1, self.data)]
        for line in self.lines:
            if not line.strip():
                continue
            indent = len(line) - len(line.lstrip(" "))
            stripped = line.strip()
            while stack and stack[-1][0] >= indent:
                stack.pop()
            parent = stack[-1][1]

            if ":" in stripped and not stripped.endswith(":"):
                key, val = map(str.strip, stripped.split(":", 1))
                parent[key] = parse_value(val)
                continue
            if "=" in stripped:
                key, val = map(str.strip, stripped.split("=", 1))
                parent[key] = parse_value(val)
                continue
            if stripped.endswith(":"):
                key = stripped[:-1].strip()
                new_dict = {}
                parent[key] = new_dict
                stack.append((indent, new_dict))

        # deal with 3x3 arrays here
        for key in ["Input Parameters", "qm-opts"]:
            sub_dict = self.data.get(key)
            if not sub_dict:
                continue
            for k, v in list(sub_dict.items()):
                if "(3x3)" in k:
                    new_k = k.split(" (")[0]
                    array = [arr for arr in v.values()]
                    sub_dict.pop(k)
                    sub_dict[new_k] = array
                


    # =========================
    # SUMMARY (PERFORMANCE, TIME)
    # =========================
    def _parse_summary(self):
        """Extract performance and wall-time summary from the end of the log file."""
        summary = {}
        lines = self.lines
        n = len(lines)
        i = 0
        while i < n:
            line = lines[i]
            if "Performance:" in line:
                parts = line.split()
                summary["Performance"] = {
                    "(ns/day)": parse_value(parts[-2]),
                    "(hour/ns)": parse_value(parts[-1]),
                }
            elif line.strip().startswith("Time:"):
                vals = lines[i + 1].split()
                summary["Time"] = {
                    "Core t (s)": parse_value(vals[0]),
                    "Wall t (s)": parse_value(vals[1]),
                }
            i += 1
        self.data["Summary"] = summary

    # =========================
    # ENERGY TIME SERIES
    # =========================
    # unused — retained for future use
    def _parse_energy_timeseries(self):
        """Extract per-step energy blocks into ``self.energy_timeseries``."""
        lines = self.lines
        n = len(lines)
        i = 0

        while i < n:
            line = lines[i]
            if re.match(r"\s*Step\s+Time", line):
                step_line = lines[i + 1].split()
                entry = {"Step": parse_value(step_line[0]), "Time": parse_value(step_line[1])}

                # locate "Energies" block
                j = i + 2
                while j < n and "Energies (kJ/mol)" not in lines[j]:
                    j += 1
                if j >= n:
                    break

                # parse 4 energy blocks
                for block in range(4):
                    headers = lines[j + 1 + block * 2].split()
                    values = lines[j + 2 + block * 2].split()
                    for h, v in zip(headers, values):
                        entry[h] = parse_value(v)

                # parse last line with Pres., DC, bar
                k = j + 9
                if k < n:
                    extra_line = lines[k].split()
                    if len(extra_line) >= 3:
                        entry["Pres."] = parse_value(extra_line[0])
                        entry["DC"] = parse_value(extra_line[1])
                        entry["(bar)"] = parse_value(extra_line[2])

                self.energy_timeseries.append(entry)
                i = j + 10
            else:
                i += 1

    # =========================
    # AVERAGES
    # =========================
    def _parse_averages(self):
        """Extract the ``A V E R A G E S`` block, including energies, box dimensions, and tensors."""
        lines = self.lines
        n = len(lines)
        i = 0
        averages = {}
        capture = False

        while i < n:
            line = lines[i]

            # detect start of averages block
            if "A V E R A G E S" in line:
                capture = True
                i += 1
                continue

            if capture:
                # Statistics header
                if "Statistics over" in line:
                    parts = line.split()
                    averages["total-steps"] = parse_value(parts[2])
                    averages["total-frames"] = parse_value(parts[-2])

                # Energies block (same as timeseries)
                elif "Energies (kJ/mol)" in line:
                    for block in range(4):
                        headers = lines[i + 1 + block * 2]
                        values = lines[i + 2 + block * 2].split()
                        headers_split = [(headers[i:i+15].split()) for i in range(0, len(headers), 15)]
                        for h, v in zip(headers_split[:-1], values):
                            h = (" ".join(h))
                            averages[h] = parse_value(v)
                    i += 8
                    continue

                # Box dimensions
                elif line.strip().startswith("Box-"):
                    headers = line.split()
                    values = lines[i + 1].split()
                    for h, v in zip(headers, values):
                        averages[h] = parse_value(v)
                    i += 2
                    continue

                # Protein temperatures
                elif line.strip().startswith("T-Protein"):
                    headers = line.split()
                    values = lines[i + 1].split()
                    for h, v in zip(headers, values):
                        averages[h] = parse_value(v)
                    i += 2
                    continue

                # Total Virial and Pressure tensors
                elif "Total Virial" in line or "Pressure (bar)" in line:
                    key = line.strip()
                    matrix = []
                    for j in range(1, 4):
                        row = [parse_value(x) for x in lines[i + j].split()]
                        matrix.append(row)
                    averages[key + " tensor"] = matrix
                    i += 4
                    continue

            i += 1

        self.data["Averages"] = averages

# =========================
# ENTRY POINT
# =========================

def parse_args():
    """Parse command-line arguments.

    Returns:
        Parsed ``argparse.Namespace`` object.
    """
    parser = argparse.ArgumentParser(description="Extract GROMACS log file metadata to JSON")
    parser.add_argument("logfile", help="Path to GROMACS log file")
    parser.add_argument("--output", "-o", help="Output file path (default: stdout)")
    return parser.parse_args()


def main():
    """Entry point: parse args, run extraction, and write output."""
    args = parse_args()

    parser = GromacsLogParser(args.logfile)
    result = parser.parse()

    if args.output:
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2)
    else:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
