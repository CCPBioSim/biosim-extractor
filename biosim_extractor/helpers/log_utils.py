import re

def parse_value(val):
    """
    Attempt to cast a string value to bool, float, int, or list.

    Args:
        val (str): Input string.

    Returns:
        bool, float, int, list, or str: Converted value.
    """
    val = val.strip()
    try:
        # Handle boolean
        if val.lower() in ["true", "false"]:
            return val.lower() == "true"
        # Handle inf
        if val == "inf":
            return float("inf")
        # Handle arrays in braces: "{1.0, 2.0, 3.0}"
        if "{" in val and "}" in val:
            return get_array(val)
        # Handle space-separated lists
        vals = val.split()
        if len(vals) > 1:
            return [parse_value(v) for v in vals]
        # Handle float/scientific
        if "." in val or "e" in val.lower():
            return float(val)
        # Handle int
        return int(val)
    except Exception:
        return val

def add_value(d, key, value):
    """
    Add a value to a dictionary, promoting to a list if the key already exists.

    Args:
        d (dict): Target dictionary.
        key (str): Key to add.
        value: Value to add.
    """
    if key in d:
        if isinstance(d[key], list):
            d[key].append(value)
        else:
            d[key] = [d[key], value]
    else:
        d[key] = value

def normalize_name(name):
    """
    Normalize a string to a valid key by replacing non-word characters with underscores.

    Args:
        name (str): Input string.

    Returns:
        str: Normalized string.
    """
    return re.sub(r"\W+", "_", name.strip()).strip("_")

def get_array(val):
    """
    Convert a brace-enclosed string of comma-separated numbers to a list of floats.

    Args:
        val (str): String containing a ``{...}`` enclosed list.

    Returns:
        list: List of floats, or the original string if no braces are found.
    """
    start, end = val.find('{'), val.find('}')
    if start == -1 or end == -1:
        return val
    return [float(x.strip()) for x in val[start+1:end].split(',') if x.strip()]