#!/usr/bin/env python3


def round_floats(obj, decimals=3):
    """
    Recursively round all floats in a nested structure (dict, list, tuple) to the given decimals.

    Args:
        obj: The object to process (dict, list, tuple, float, etc.).
        decimals: Number of decimal places to round to.

    Returns:
        The processed object with all floats rounded.
    """
    if isinstance(obj, float):
        return round(obj, decimals)
    elif isinstance(obj, list):
        return [round_floats(item, decimals) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(round_floats(item, decimals) for item in obj)
    elif isinstance(obj, dict):
        return {k: round_floats(v, decimals) for k, v in obj.items()}
    else:
        return obj
