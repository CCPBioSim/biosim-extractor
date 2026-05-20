#!/usr/bin/env python3
"""
Validation utilities for extracted MD simulation metadata against the biosim LinkML schema.
"""

import os
import warnings

from linkml.validator import validate


def validate_metadata(result, biosimschema_path=None, strict=False):
    """Validate a populated metadata dict, optionally against a biosim schema.

    Args:
        result: Populated metadata dictionary to validate.
        biosimschema_path: Path or URL to the biosim schema YAML. If ``None``, validation is skipped.
        strict: If ``True``, raises ``ValueError`` on validation errors; otherwise emits a warning.

    Raises:
        ValueError: If ``strict=True`` and validation errors are found.
    """
    if biosimschema_path:
        errors = validate_extracted(result, biosimschema_path)
        if errors:
            if strict:
                raise ValueError("Schema validation failed:\n" + "\n".join(errors))
            else:
                warnings.warn("Schema validation warnings:\n" + "\n".join(errors))


def validate_extracted(instance, schema_path):
    """Validate extracted MD simulation metadata against the biosim LinkML schema.

    Uses a two-pass strategy to work around LinkML's JSON-Schema compiler not
    supporting nested array (matrix) constraints:

    1. Custom pass: checks every ``vector_value`` field for correct numeric types and (for matrices) consistent row lengths.
    2. LinkML pass: matrix ``vector_value`` fields are stripped and the remainder is validated with linkml.validator.validate, which enforces types, enums, required fields, and cardinality on flat vectors.

    The working directory is temporarily changed to the directory containing
    schema_path so that relative $import paths inside the schema resolve correctly.

    Args:
        instance: Extracted metadata dict conforming to the SimulationMetadata class.
        schema_path: Path to the top-level biosim_schema.yaml file, or a raw GitHub URL (https://raw.githubusercontent.com/...).

    Returns:
        list: Validation error messages. An empty list means the instance is valid.
    """
    errors = []

    errors.extend(_validate_all_vector_values(instance))

    stripped = _strip_all_matrix_vector_values(instance)

    if schema_path.startswith("http"):
        # SchemaView resolves relative imports from the base URL — no chdir needed
        report = validate(stripped, schema_path, "SimulationMetadata")
    else:
        orig_dir = os.getcwd()
        os.chdir(os.path.dirname(os.path.abspath(schema_path)))
        try:
            report = validate(stripped, schema_path, "SimulationMetadata")
        finally:
            os.chdir(orig_dir)

    errors.extend(r.message for r in report.results)
    return errors


def _validate_all_vector_values(instance, path=""):
    """Recursively walk *instance* and validate every ``vector_value`` field found.

    Delegates to _validate_vector_value for each field encountered.

    Args:
        instance: The (possibly nested) metadata dict to inspect.
        path: Dot-separated path accumulated during recursion, used in error messages.

    Returns:
        list: Validation error messages; empty if all ``vector_value`` fields are valid.
    """
    errors = []
    if not isinstance(instance, dict):
        return errors

    if "vector_value" in instance:
        vv = instance["vector_value"]
        field_path = f"{path}.vector_value" if path else "vector_value"
        err = _validate_vector_value(vv, field_path)
        if err:
            errors.append(err)

    for key, value in instance.items():
        child_path = f"{path}.{key}" if path else key
        if isinstance(value, dict):
            errors.extend(_validate_all_vector_values(value, child_path))
        elif isinstance(value, list):
            for i, item in enumerate(value):
                errors.extend(_validate_all_vector_values(item, f"{child_path}[{i}]"))

    return errors


def _validate_vector_value(vv, path):
    """Validate a single ``vector_value`` field.

    Accepts two shapes: a flat vector (list of numbers) or a matrix
    (list of equal-length lists of numbers).

    Args:
        vv: The value of the ``vector_value`` field.
        path: Dot-separated path to this field, used in error messages.

    Returns:
        str or None: An error message string if validation fails, otherwise None.
    """
    if not isinstance(vv, list) or len(vv) == 0:
        return None

    if isinstance(vv[0], list):
        # Matrix: all rows must be lists of numbers of equal length
        row_len = len(vv[0])
        for i, row in enumerate(vv):
            if not isinstance(row, list):
                return f"{path}: row {i} is not a list"
            if len(row) != row_len:
                return f"{path}: row {i} has length {len(row)}, expected {row_len}"
            if not all(isinstance(x, (int, float)) for x in row):
                return f"{path}: row {i} contains non-numeric values"
    else:
        # Flat vector: all elements must be numbers
        if not all(isinstance(x, (int, float)) for x in vv):
            return f"{path}: contains non-numeric values"

    return None


def _strip_all_matrix_vector_values(instance):
    """Recursively remove ``vector_value`` fields whose value is a nested list (matrix).

    The LinkML JSON-Schema validator cannot validate nested arrays — matrix classes
    compile ``vector_value`` to an unconstrained string array, causing false-positive
    type errors. Matrices are validated separately by _validate_all_vector_values.

    Args:
        instance: The metadata dict to strip.

    Returns:
        dict: A shallow-copied dict with matrix ``vector_value`` fields removed.
    """
    if not isinstance(instance, dict):
        return instance
    result = {}
    for key, value in instance.items():
        if (
            key == "vector_value"
            and isinstance(value, list)
            and value
            and isinstance(value[0], list)
        ):
            continue  # drop nested array
        elif isinstance(value, dict):
            result[key] = _strip_all_matrix_vector_values(value)
        elif isinstance(value, list):
            result[key] = [_strip_all_matrix_vector_values(i) for i in value]
        else:
            result[key] = value
    return result
