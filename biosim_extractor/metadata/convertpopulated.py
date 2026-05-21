from biosim_extractor.helpers.metadata_utils import round_floats
from biosim_extractor.units.unitconversion import UnitConverter


def convert_populated_metadata_units(metadata: dict) -> dict:
    """
    Recursively convert all value/value_unit and vector_value/value_unit pairs in a metadata dict to standard units.

    Args:
        metadata (dict): The metadata dictionary to process. This should contain nested dictionaries
                         where physical quantities are represented as {'value': ..., 'value_unit': ...}
                         or {'vector_value': ..., 'value_unit': ...}.

    Returns:
        dict: A new metadata dictionary with all values converted to standard units as defined by UnitConverter.
              The structure of the input is preserved.

    Raises:
        ValueError: If a unit is unknown or conversion fails.
    """
    uc = UnitConverter()

    def convert_entry(entry):
        if isinstance(entry, dict):
            # If both 'value' and 'value_unit' keys exist, try to convert
            if "value" in entry and "value_unit" in entry:
                unit_type = uc.get_unit_type(entry["value_unit"])
                if unit_type is None:
                    raise ValueError(f"Unknown unit: {entry['value_unit']}")
                std_value = uc.convert(entry["value"], entry["value_unit"], unit_type)
                std_value = round_floats(std_value, decimals=3)
                std_unit = uc.get_target_unit(entry["value_unit"])
                return {"value": std_value, "value_unit": std_unit}
            # If both 'vector_value' and 'value_unit' keys exist, convert the vector
            if "vector_value" in entry and "value_unit" in entry:
                unit_type = uc.get_unit_type(entry["value_unit"])
                if unit_type is None:
                    raise ValueError(f"Unknown unit: {entry['value_unit']}")
                std_vector = uc.convert(
                    entry["vector_value"], entry["value_unit"], unit_type
                )
                std_vector = round_floats(std_vector, decimals=3)
                std_unit = uc.get_target_unit(entry["value_unit"])
                return {"vector_value": std_vector, "value_unit": std_unit}
            # Otherwise, recurse into dict
            return {k: convert_entry(v) for k, v in entry.items()}
        elif isinstance(entry, list):
            return [convert_entry(i) for i in entry]
        else:
            return entry

    return convert_entry(metadata)
