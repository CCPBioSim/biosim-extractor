#!/usr/bin/env python3
"""
Convert units from various MD engine outputs to a consistent standard unit system.

This module provides the UnitConverter class for converting scientific values
between different units, standardizing to a chosen system (default: SI-like).
"""

from typing import Any, Dict, List, Optional, Tuple, Union


class UnitConverter:
    """
    Simple unit conversion class for scientific calculations.
    Converts values to a chosen standard unit system.
    """

    def __init__(self, standard_units: Optional[Dict[str, str]] = None) -> None:
        """
        Initialize the UnitConverter.

        Args:
            standard_units (dict, optional): Mapping of unit types to standard units.
        """
        self.standards: Dict[str, str] = standard_units or {
            "length": "nm",  # nanometers
            "volume": "nm³",  # nanometers cubed
            "time": "ps",  # picoseconds
            "energy": "kJ/mol",  # kilojoules per mole
            "temperature": "K",  # Kelvin
            "pressure": "bar",  # bar
            "compressibility": "1/bar",  # inverse bar
            "force": "kJ/mol/nm",  # kilojoules per mole per nanometer
            "velocity": "nm/ps",  # nanometers per picosecond
            "frequency": "1/ps",  # inverse picoseconds
            "friction": "a/ps",  # atomic mass units per picosecond
            "angle": "degree",  # degree
            "charge": "e",  # atomic charge units
            "molecular_weight": "g/mol",  # grams per mol
        }

        # Conversion factors to standard units
        self.factors: Dict[str, Dict[str, Any]] = {
            "length": {
                "Å": 0.1,
                "A": 0.1,
                "Ang": 0.1,
                "angstrom": 0.1,
                "nm": 1.0,
                "pm": 0.001,
                "m": 1e9,
            },
            "volume": {
                "nm³": 1,
                "nm^3": 1,
                "A^3": 1000,
                "Å^3": 1000,
                "Ang^3": 1000,
                "Å³": 1000,
            },
            "time": {
                "fs": 0.001,
                "ps": 1.0,
                "ns": 1000.0,
                "s": 1e12,
            },
            "energy": {
                "kcal/mol": 4.184,
                "kJ/mol": 1.0,
                "eV": 96.485,
                "J": 6.022e20,
                "hartree": 2625.5,
            },
            "force": {
                "kcal/mol/Å": 41.84,
                "kJ/mol/nm": 1.0,
            },
            "temperature": {
                "K": 1.0,
                "C": lambda x: x + 273.15,
                "°C": lambda x: x + 273.15,
                "F": lambda x: (x - 32) * 5 / 9 + 273.15,
                "°F": lambda x: (x - 32) * 5 / 9 + 273.15,
            },
            "pressure": {
                "bar": 1.0,
                "atm": 1.01325,
                "Pa": 1e-5,
                "kPa": 0.01,
                "MPa": 10.0,
            },
            "compressibility": {
                "1/bar": 1.0,
                "bar^-1": 1.0,
                "1e10-6 bar^-1": 1e-6,
                "1e10-6 1/bar": 1e-6,
            },
            "frequency": {
                "ps^-1": 1.0,
                "1/ps": 1.0,
                "fs^-1": 1000.0,
                "1/fs": 1000.0,
                "GHz": 1e-3,
                "THz": 1e-6,
                "Hz": 1e-12,
            },
            "friction": {
                "a/ps": 1.0,
                "amu/ps": 1.0,
            },
            "angle": {
                "degree": 1.0,
            },
            "charge": {
                "e": 1.0,
                "acu": 1.0,
            },
            "molecular_weight": {
                "g/mol": 1.0,
                "amu": 1.0,
                "Da": 1.0,
            },
        }

        # Create reverse lookup: unit -> unit_type
        self.unit_to_type: Dict[str, str] = {}
        for unit_type, units in self.factors.items():
            for unit in units.keys():
                self.unit_to_type[unit] = unit_type

    def convert(
        self,
        value: Union[float, List[float]],
        from_unit: str,
        unit_type: Optional[str] = None,
        decimals: Optional[int] = None,
    ) -> Union[float, List[float]]:
        """
        Convert a value from one unit to the standard unit.

        Args:
            value (float or list): Value(s) to convert.
            from_unit (str): The original unit.
            unit_type (str, optional): The unit type (auto-detected if None).

        Returns:
            float or list: Converted value(s) in standard unit.

        Raises:
            ValueError: If unit or unit type is unknown.
        """
        # Auto-detect unit type if not provided
        if unit_type is None:
            unit_type = self.get_unit_type(from_unit)
            if unit_type is None:
                raise ValueError(f"Unknown unit: {from_unit}")

        target_unit = self.standards[unit_type]
        # Skip conversion if already in standard unit
        if from_unit == target_unit:
            result = value

        if unit_type not in self.factors:
            raise ValueError(f"Unknown unit type: {unit_type}")

        factor = self.factors[unit_type].get(from_unit)
        if factor is None:
            raise ValueError(f"Unknown {unit_type} unit: {from_unit}")

        # Handle temperature conversions (functions instead of factors)
        if callable(factor):
            if isinstance(value, list):
                result = [factor(x) for x in value]
            else:
                result = factor(value)
        else:
            if isinstance(value, list):
                result = [x * factor for x in value]
            else:
                result = value * factor

        # Apply rounding if requested
        if decimals is not None:
            if isinstance(result, list):
                result = [round(float(x), decimals) for x in result]
            else:
                result = round(float(result), decimals)
        return result

    def convert_with_unit(
        self,
        value: Union[float, List[float]],
        from_unit: str,
        unit_type: Optional[str] = None,
    ) -> Tuple[Union[float, List[float]], str]:
        """
        Convert a value and return both the value and the target unit.

        Args:
            value (float or list): Value(s) to convert.
            from_unit (str): The original unit.
            unit_type (str, optional): The unit type (auto-detected if None).

        Returns:
            tuple: (converted value(s), target unit)

        Raises:
            ValueError: If unit or unit type is unknown.
        """
        if unit_type is None:
            unit_type = self.get_unit_type(from_unit)
            if unit_type is None:
                raise ValueError(f"Unknown unit: {from_unit}")

        target_unit = self.standards[unit_type]
        converted_value = self.convert(value, from_unit, unit_type)

        return converted_value, target_unit

    def get_target_unit(self, from_unit: str) -> str:
        """
        Get the standard unit for a given unit.

        Args:
            from_unit (str): The original unit.

        Returns:
            str: The standard unit.

        Raises:
            ValueError: If unit is unknown.
        """
        unit_type = self.get_unit_type(from_unit)
        if unit_type is None:
            raise ValueError(f"Unknown unit: {from_unit}")
        return self.standards[unit_type]

    def __call__(
        self,
        value: Union[float, List[float]],
        from_unit: str,
        unit_type: Optional[str] = None,
    ) -> Union[float, List[float]]:
        """
        Convert a value using the instance as a callable.

        Args:
            value (float or list): Value(s) to convert.
            from_unit (str): The original unit.
            unit_type (str, optional): The unit type (auto-detected if None).

        Returns:
            float or list: Converted value(s) in standard unit.
        """
        return self.convert(value, from_unit, unit_type)

    def get_unit_type(self, unit: str) -> Optional[str]:
        """
        Get the unit type for a given unit string.

        Args:
            unit (str): The unit string.

        Returns:
            str or None: The unit type, or None if unknown.
        """
        return self.unit_to_type.get(unit)

    def is_standard_unit(self, unit: str) -> bool:
        """
        Check if a unit is the standard for its type.

        Args:
            unit (str): The unit string.

        Returns:
            bool: True if unit is standard, False otherwise.
        """
        unit_type = self.get_unit_type(unit)
        if unit_type is None:
            return False
        return unit == self.standards[unit_type]

    def needs_conversion(self, from_unit: str) -> bool:
        """
        Determine if a unit needs conversion to standard.

        Args:
            from_unit (str): The unit string.

        Returns:
            bool: True if conversion is needed, False if already standard.
        """
        return not self.is_standard_unit(from_unit)
