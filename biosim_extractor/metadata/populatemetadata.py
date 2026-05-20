#!/usr/bin/env python3
"""
Extract and populate metadata from a single MD engine log file, validated against the biosim-schema.
Preserves canonical casing from schema mappings.
"""

import argparse
import json
from typing import Any, Dict

from biosim_extractor.amber.amberlog import AmberLogParser
from biosim_extractor.gromacs.gromacslog import GromacsLogParser
from biosim_extractor.mdanalysis.toptraj import TopTrajParser
from biosim_extractor.metadata.validatemetadata import validate_metadata
from biosim_extractor.units.unitconversion import UnitConverter

# -----------------------------
# Utility functions
# -----------------------------


def flatten_dict(d: Dict) -> Dict:
    """Recursively flatten a nested dict, keeping the first occurrence of duplicate keys.

    Args:
        d: Nested dictionary to flatten.

    Returns:
        Single-level dictionary with all leaf key-value pairs.
    """
    items = {}

    for k, v in d.items():
        if isinstance(v, dict):
            items.update(flatten_dict(v))
        else:
            if k not in items:
                items[k] = v

    return items


def get_by_path(d: Dict, path: str):
    """Retrieve a value from a nested dict using a dot-separated path.

    Args:
        d: Dictionary to traverse.
        path: Dot-separated key path, e.g. ``"SimulationMetadata.timestep"``.

    Returns:
        Value at the path, or ``None`` if any key is missing.
    """
    keys = path.split(".")
    for key in keys:
        if not isinstance(d, dict):
            return None
        if key not in d:
            return None
        d = d[key]
    return d


def assign_by_path(d: Dict, path: str, value: Any):
    """Set a value in a nested dict at a dot-separated path, creating intermediate dicts as needed.

    Args:
        d: Dictionary to modify in place.
        path: Dot-separated key path.
        value: Value to assign at the final key.
    """
    keys = path.split(".")

    for key in keys[:-1]:
        if key not in d or not isinstance(d[key], dict):
            d[key] = {}
        d = d[key]

    d[keys[-1]] = value


def add_to_path(d: Dict, path: str, value: Any):
    """Append a value to a list in a nested dict at a dot-separated path.

    Args:
        d: Dictionary to modify in place.
        path: Dot-separated key path pointing to an existing list.
        value: Value to append.
    """
    keys = path.split(".")

    for key in keys[:-1]:
        if key not in d or not isinstance(d[key], dict):
            d[key] = {}
        d = d[key]

    d[keys[-1]].append(value)


def is_numeric(value):
    """Check whether a value can be interpreted as a float.

    Args:
        value: Value to test.

    Returns:
        ``True`` if ``float(value)`` succeeds, ``False`` otherwise.
    """
    try:
        float(value)
        return True
    except (ValueError, TypeError):
        return False


def remove_null_parents(d):
    """Recursively remove any dict that contains a ``None`` value.

    Args:
        d: Dictionary to clean.

    Returns:
        Cleaned dictionary with ``None``-containing dicts removed, or ``None`` if
        the top-level dict itself contains a ``None`` value.
    """
    if not isinstance(d, dict):
        return d
    if any(v is None for v in d.values()):
        return None
    cleaned = {}
    for k, v in d.items():
        result = remove_null_parents(v)
        if result is not None:
            cleaned[k] = result
    return cleaned


# -----------------------------
# VALUE NORMALISATION
# -----------------------------


def normalize_key(value: Any) -> str:
    """Normalise a value to lowercase stripped string for case-insensitive matching.

    Args:
        value: Value to normalise.

    Returns:
        Lowercased, stripped string representation.
    """
    return str(value).strip().lower()


def transform_value(value: Any, rules: Dict):
    """Map a raw engine value to its canonical schema equivalent using a rules dict.

    Args:
        value: Raw value from the engine data.
        rules: Mapping of raw keys to canonical values (empty dict skips mapping).

    Returns:
        Canonical mapped value, or ``None`` if the value has no matching rule.
    """
    if not rules:
        return value

    # case-insensitive matching
    norm_value = normalize_key(value)

    normalised_keys = []
    for key, mapped in rules.items():
        normalised_keys.append(normalize_key(key))
        if normalize_key(key) == norm_value:
            if isinstance(mapped, list) and mapped:
                # return canonical casing exactly as defined
                return mapped[0]
            return mapped
    if norm_value not in normalised_keys:
        return None
    return value  # fallback (unchanged, but not lowercased)


# -----------------------------
# Main class
# -----------------------------


class MetadataPopulator:
    """Orchestrates extraction of MD engine metadata and population of metadata validated against the biosim schema.

    Supports log-file-based engines (Amber, GROMACS) and topology/trajectory parsing via MDAnalysis.
    """

    def __init__(
        self,
        schema_path=None,
        log_file=None,
        engine=None,
        top_file=None,
        traj_file=None,
    ):
        """
        Args:
            schema_path: Path to the extraction schema JSON file.
            log_file: Path to the MD engine log file.
            engine: MD engine name (``"amber"``, ``"gromacs"``).
            top_file: Path to the topology file.
            traj_file: Path to the trajectory file (or list of paths).
        """
        self.schema_path = schema_path
        self.log_file = log_file
        self.top_file = top_file
        self.traj_file = traj_file
        self.engine = engine
        if engine:
            self.engine = engine.lower()
        self.converter = UnitConverter()
        self.schema = {}
        self.engine_data = {}
        self.data = {}

    def populate(self):
        """Run the full extraction and mapping pipeline.

        Returns:
            Populated ``SimulationMetadata`` dictionary with ``None``-containing
            entries removed.
        """
        self.load_schema()

        if self.engine:
            self.engine_data = self.parse_log()

            if self.engine not in self.schema.get("reverse", {}):
                raise ValueError(f"No reversemapping found for engine: {self.engine}")

            if self.engine not in self.schema.get("forward", {}):
                raise ValueError(f"No forwardmapping found forengine: {self.engine}")

            self.data = self.apply_mapping()

        if self.top_file and self.traj_file:
            self.data = self.populate_toptraj()

        # self.data["SimulationMetadata"]["@type"] = "SimulationMetadata"
        result = self.data["SimulationMetadata"]

        # Remove any dict that contains a None field
        result = remove_null_parents(result) or {}

        return result

    def validate(self, result, biosimschema_path=None, strict=False):
        """Validate populated metadata against the biosim schema.

        Args:
            result: Populated metadata dictionary to validate.
            biosimschema_path: Optional path to the biosim schema YAML.
            strict: If ``True``, raise on warnings in addition to errors.
        """
        validate_metadata(result, biosimschema_path, strict)

    def load_schema(self):
        """Load and parse the extraction schema JSON from ``self.schema_path``."""
        with open(self.schema_path) as f:
            self.schema = json.load(f)

    def parse_log(self):
        """Parse the MD engine log file and return a flattened parameter dictionary.

        Returns:
            Flat dictionary of parameter names to raw values.

        Raises:
            ValueError: If ``self.engine`` is not a supported engine.
        """
        if self.engine == "amber":
            parser = AmberLogParser(self.log_file)
            # raw = parser.parse()["SimulationSettings"]
        elif self.engine == "gromacs":
            parser = GromacsLogParser(self.log_file)
            # raw = parser.parse()["Input Parameters"]
        else:
            raise ValueError(f"Unsupported engine: {self.engine}")

        raw = parser.parse()
        # print(json.dumps(raw, indent=2))
        # print("----------")
        # print(json.dumps(flatten_dict(raw), indent=2))

        return flatten_dict(raw)

    def populate_toptraj(self):
        """Parse topology and trajectory files and apply schema mapping.

        Returns:
            Schema-mapped result dictionary, or ``None`` if topology/trajectory
            files are not set.
        """
        if self.top_file and self.traj_file:
            parser = TopTrajParser(self.top_file, self.traj_file)
            self.engine_data = parser.parse()
            self.engine = "toptrajparser"
            return self.apply_mapping()

    # -----------------------------
    # Mapping logic
    # -----------------------------

    def apply_mapping(self) -> Dict:
        """
        Apply mapping rules to engine data to produce schema-compliant output.

        Returns:
            Result dictionary with mapped schema values applied.
        """
        engine_data = self.engine_data
        reverse_mapping = self.schema["reverse"][self.engine]
        forward_mapping = self.schema["forward"][self.engine]

        result = self.data

        for param, config in reverse_mapping.items():
            if param not in engine_data:
                continue

            raw_value = engine_data[param]
            for path, rules in config.get("by_path", {}).items():
                mapped_value = transform_value(raw_value, rules)

                if len(rules) == 0:  # check for unit conversion
                    for term in forward_mapping[path]:
                        if "unit" in term and term["key"] == param:
                            # Check if this is a vector value based on path or value type
                            is_vector = (
                                "box_dimensions" in path
                                or "box_angles" in path
                                or "vector" in path.lower()
                                or (
                                    isinstance(mapped_value, list)
                                    and len(mapped_value) > 1
                                )
                            )
                            # Handle both single values and lists uniformly
                            mapped_value = self.convert_values(
                                mapped_value, term, is_vector
                            )

                existing = get_by_path(result, path)

                if existing is None:
                    assign_by_path(result, path, mapped_value)
                elif (
                    isinstance(existing, dict)
                    and "value" in existing
                    and isinstance(mapped_value, dict)
                    and "value" in mapped_value
                ):
                    # Second key hit same path — promote scalar to vector
                    assign_by_path(
                        result,
                        path,
                        {
                            "vector_value": [existing["value"], mapped_value["value"]],
                            "value_unit": existing["value_unit"],
                        },
                    )
                elif (
                    isinstance(existing, dict)
                    and "vector_value" in existing
                    and isinstance(mapped_value, dict)
                    and "value" in mapped_value
                ):
                    # Third+ key — append to existing vector
                    existing["vector_value"].append(mapped_value["value"])
                else:
                    try:
                        add_to_path(result, path, mapped_value)
                    except (KeyError, AttributeError):
                        continue

        # Special handling for molecule_ids with full transformation pipeline
        if "molecule_ids" in engine_data:
            molecules_list = []

            for _mol_index, mol_data in engine_data["molecule_ids"].items():
                transformed_molecule = {}

                # Process each property of the molecule through the transformation pipeline
                for prop_name, prop_value in mol_data.items():
                    # Check if this molecule property has mapping rules
                    if prop_name in reverse_mapping:
                        config = reverse_mapping[prop_name]
                        for path, rules in config.get("by_path", {}).items():
                            mapped_value = transform_value(prop_value, rules)

                            # Check for unit conversion
                            if len(rules) == 0:
                                for term in forward_mapping[path]:
                                    if "unit" in term and term["key"] == prop_name:
                                        mapped_value = self.convert_values(
                                            mapped_value, term
                                        )

                            # Use the final path segment as the key
                            final_key = path.split(".")[-1]
                            transformed_molecule[final_key] = mapped_value
                    else:
                        # No mapping found in schema, skip
                        continue

                molecules_list.append(transformed_molecule)

            # Assign the transformed molecules list to the schema path
            assign_by_path(
                result, "SimulationMetadata.composition.molecule_ID", molecules_list
            )

        return result

    def convert_values(self, value, term, is_vector=False):
        """
        Convert a raw value (or list) to a unit-annotated schema dictionary.

        Args:
            value: Numeric value or list of values to convert.
            term: Forward-mapping entry containing ``"unit"`` and ``"key"``.
            is_vector: If ``True``, stores the result under ``"vector_value"`` instead of ``"value"``.

        Returns:
            Dictionary with ``"value"`` (or ``"vector_value"``) and ``"value_unit"`` keys.
        """
        unit = (
            self.converter.get_target_unit(term["unit"])
            if self.converter.needs_conversion(term["unit"])
            else term["unit"]
        )

        if isinstance(value, list):
            # Handle list of values (vectors)
            converted_values = (
                [self.converter.convert(v, term["unit"]) for v in value]
                if self.converter.needs_conversion(term["unit"])
                else value
            )

            if is_vector:
                return {"vector_value": converted_values, "value_unit": unit}
            else:
                return {"value": converted_values, "value_unit": unit}
        else:
            # Handle single value
            if is_numeric(value):
                converted_value = (
                    self.converter.convert(value, term["unit"])
                    if self.converter.needs_conversion(term["unit"])
                    else value
                )
                return {"value": converted_value, "value_unit": unit}
            else:
                return {"value": value, "value_unit": unit}


# -----------------------------
# Entry point
# -----------------------------


def parse_args():
    """Parse command-line arguments.

    Returns:
        Parsed ``argparse.Namespace`` object.
    """
    parser = argparse.ArgumentParser(
        description="Populate biosim-schema with MD engine data"
    )

    # Required arguments
    parser.add_argument("schema", help="Path to extraction schema JSON file")

    # Optional file arguments
    parser.add_argument("--biosimschema", help="Path to biosim schema yaml")
    parser.add_argument("--engine", help="MD engine (amber, gromacs, etc.)")
    parser.add_argument("--logfile", help="Path to MD log file")
    parser.add_argument("--top", help="Topology file path")
    parser.add_argument("--traj", nargs="+", help="Trajectory file path")
    parser.add_argument("--config", help="Configuration file path")
    parser.add_argument("--output", "-o", help="Output file path")

    return parser.parse_args()


def main():
    """Entry point: parse args, run population pipeline, validate, and write output."""
    args = parse_args()

    populator = MetadataPopulator(
        schema_path=args.schema,
        log_file=args.logfile,
        engine=args.engine,
        top_file=args.top,
        traj_file=args.traj,
    )

    result = populator.populate()
    populator.validate(result, biosimschema_path=args.biosimschema)

    if args.output:
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2)
    else:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
