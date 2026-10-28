from biosim_extractor.helpers.metadata_utils import round_floats
from biosim_extractor.units.unitconversion import UnitConverter


class UnitConversionError(ValueError):
    """Raised when one or more quantities cannot be converted; holds all messages."""

    def __init__(self, errors, heading="Unit conversion failed:"):
        self.errors = list(errors)
        self.heading = heading
        super().__init__(heading + "\n" + "\n".join(self.errors))


def _to_numbers(value):
    """Convert a scalar or arbitrarily nested list of scalars to floats."""
    if isinstance(value, list):
        return [_to_numbers(item) for item in value]
    return float(value)


def convert_populated_metadata_units(metadata: dict) -> dict:
    """
    Recursively convert all value/value_unit and vector_value/value_unit pairs in a
    metadata dict to standard units.

    Args:
        metadata (dict): The metadata dictionary to process. This should contain
                         nested dictionaries where physical quantities are
                         represented as {'value': ..., 'value_unit': ...}
                         or {'vector_value': ..., 'value_unit': ...}.

    Returns:
        dict: A new metadata dictionary with all values converted to standard units
              as defined by UnitConverter. The structure of the input is preserved.

    Raises:
        ValueError: If a unit is unknown or conversion fails.
    """
    uc = UnitConverter()
    errors = []

    def convert_entry(entry, path=""):
        if isinstance(entry, dict):
            for key in ("value", "vector_value"):
                if key in entry and "value_unit" in entry:
                    return convert_quantity(entry, key, path or "<root>")
            return {
                k: convert_entry(v, f"{path}.{k}" if path else k)
                for k, v in entry.items()
            }
        if isinstance(entry, list):
            return [convert_entry(v, f"{path}[{i}]") for i, v in enumerate(entry)]
        return entry

    def convert_quantity(entry, key, path):
        unit = entry["value_unit"]
        unit_type = uc.get_unit_type(unit)
        if unit_type is None:
            errors.append(f"{path}: unknown unit {unit!r}")
            return entry  # leave unchanged
        raw = entry[key]
        try:
            raw = _to_numbers(raw) if key == "vector_value" else float(raw)
            converted = uc.convert(raw, unit, unit_type)
        except (TypeError, ValueError) as exc:
            errors.append(f"{path}: cannot convert {raw!r} from {unit!r} ({exc})")
            return entry
        return {
            key: round_floats(converted, decimals=3),
            "value_unit": uc.get_target_unit(unit),
        }

    result = convert_entry(metadata)
    if errors:
        raise UnitConversionError(errors)
    return result
