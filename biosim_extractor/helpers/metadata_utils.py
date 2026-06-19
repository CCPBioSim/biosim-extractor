#!/usr/bin/env python3


def round_floats(obj, decimals=3, preserve_below=1e-3):
    """
    Recursively round floats in nested dicts, lists, and tuples.

    Very small non-zero floats are rounded in scientific notation so they are
    not rounded to zero. They remain numbers.

    Args:
        obj: Object to process.
        decimals: Decimal places to keep.
        preserve_below: Lower absolute-value threshold for preserving floats.

    Returns:
        Object with floats rounded while preserving numeric types.
    """
    if isinstance(obj, float):
        if obj != 0 and abs(obj) < preserve_below:
            return float(f"{obj:.{decimals}e}")
        return round(obj, decimals)

    elif isinstance(obj, list):
        return [round_floats(item, decimals, preserve_below) for item in obj]

    elif isinstance(obj, tuple):
        return tuple(round_floats(item, decimals, preserve_below) for item in obj)

    elif isinstance(obj, dict):
        return {k: round_floats(v, decimals, preserve_below) for k, v in obj.items()}

    return obj
