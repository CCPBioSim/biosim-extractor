#!/usr/bin/env python
"""
Extract topology and trajectory metadata using MDAnalysis.
"""

import argparse
import json
from collections import Counter

import numpy as np
from MDAnalysis import Universe
from rdkit import Chem

alternative_residue_names = {
    "ALAD": "ALA",
    "ASH": "ASP",
    "ASPH": "ASP",
    "GLH": "GLU",
    "GLUH": "GLU",
    "ARGN": "ARG",
    "HIP": "HIS",
    "HIE": "HIS",
    "HID": "HIS",
    "CYM": "CYS",
    "CYX": "CYS",
    "LYN": "LYS",
}


def get_protein_sequence(fragment):
    """
    Extract the protein sequence from a molecule fragment.

    Args:
        fragment (MDAnalysis.AtomGroup): Molecule fragment to analyze.

    Returns:
        str or None: Protein sequence as a string, or None if not found.
    """

    # Check if fragment contains protein residues
    try:
        protein_atoms = fragment.select_atoms(
            "protein and not (resname ACE or resname NME)"
        )
        if len(protein_atoms) > 0:
            protein_residues = protein_atoms.residues
            # Handle alternative residue names
            for old_name, new_name in alternative_residue_names.items():
                for residue in protein_residues:
                    if residue.resname == old_name:
                        residue.resname = new_name

            sequence = protein_residues.sequence(id="sequence1", name="protein1")
            return str(sequence.seq)
    except Exception:
        return None


def get_nucleic_sequence(fragment):
    """
    Extract the nucleic acid sequence from a molecule fragment.

    Args:
        fragment (MDAnalysis.AtomGroup): Molecule fragment to analyze.

    Returns:
        str or None: Nucleic acid sequence as a string, or None if not found.
    """
    # Check if fragment contains nucleic acid residues
    try:
        dna_atoms = fragment.select_atoms("nucleic")
        if len(dna_atoms) > 0:
            dna_residues = dna_atoms.residues
            sequence = []
            for res in dna_residues.resnames:
                sequence.append(res[-1] if len(res) == 2 else res)
            return "".join(sequence)
    except Exception:
        return None


def classify_box(dim, tolerance=1e-3):
    """
    Classify the simulation box type based on dimensions and angles.

    Args:
        dim (list or tuple): Box dimensions [lx, ly, lz, a, b, g].
        tolerance (float): Tolerance for angle/length comparison.

    Returns:
        str: Box type (e.g., "cubic", "tetragonal", "orthorhombic", etc.).
    """
    lx, ly, lz, a, b, g = dim

    def close(x, y):
        return abs(x - y) < tolerance

    if all(close(x, 90) for x in (a, b, g)):
        if close(lx, ly) and close(ly, lz):
            return "cubic"
        elif close(lx, ly) or close(ly, lz) or close(lx, lz):
            return "tetragonal"
        else:
            return "orthorhombic"

    if close(a, 90) and close(b, 90) and close(g, 120):
        return "orthorhombic"

    if close(a, 90) and close(b, 120) and close(g, 120):
        return "truncated octahedron"

    return "triclinic"


def safe_extract(func):
    """
    Safely extract and convert values from a function, handling numpy types.

    Args:
        func (callable): Function to call.

    Returns:
        Any: Extracted and converted value.
    """
    value = func()
    # Convert numpy types to Python types
    if isinstance(value, list):
        value = [float(x) if hasattr(x, "item") else x for x in value]
    elif hasattr(value, "tolist"):  # numpy array
        value = value.tolist()
    elif hasattr(value, "item"):  # single numpy value
        value = value.item()
    return value


TOPTRAJ_AUTO_EXTRACT = {
    "total_atom_count": lambda u: safe_extract(lambda: u.atoms.n_atoms),
    "total_molecule_count": lambda u: safe_extract(lambda: len(u.atoms.fragments)),
    "frame_count": lambda u: safe_extract(lambda: len(u.trajectory)),
    "system_charge": lambda u: safe_extract(lambda: sum(list(u.atoms.charges))),
    "box_dimensions": lambda u: safe_extract(
        lambda: np.mean([f.dimensions[:3] for f in u.trajectory], axis=0)
    ),
    "box_angles": lambda u: safe_extract(
        lambda: list(u.trajectory[0].dimensions[3:].flatten())
    ),
    "box_type": lambda u: safe_extract(
        lambda: classify_box(u.trajectory[0].dimensions)
    ),
    "water": lambda u: safe_extract(lambda: len(u.select_atoms("water")) > 0),
    "positions": lambda u: safe_extract(
        lambda: getattr(u.trajectory.ts, "positions", None) is not None
    ),
    "forces": lambda u: safe_extract(
        lambda: getattr(u.trajectory.ts, "forces", None) is not None
    ),
    "velocities": lambda u: safe_extract(
        lambda: getattr(u.trajectory.ts, "velocities", None) is not None
    ),
    "masses": lambda u: safe_extract(
        lambda: getattr(u.atoms, "masses", None) is not None
    ),
    "bonds": lambda u: safe_extract(lambda: getattr(u, "bonds", None) is not None),
    "dihedrals": lambda u: safe_extract(
        lambda: getattr(u, "dihedrals", None) is not None
    ),
    "fixed_charges": lambda u: safe_extract(
        lambda: getattr(u.atoms, "charges", None) is not None
    ),
}


MOLID_AUTO_EXTRACT = {
    "atom_count": lambda fragment: len(fragment.atoms),
    "monomer_count": lambda fragment: len(fragment.residues),
    "molecule_charge": lambda fragment: safe_extract(
        lambda: sum(list(fragment.atoms.charges))
    ),
    "molecular_weight": lambda fragment: float(sum(fragment.masses))
    if hasattr(fragment, "masses")
    else None,
}


RDKIT_AUTO_EXTRACT = {
    "InChIKey": lambda rdkit_mol: Chem.MolToInchiKey(rdkit_mol),
    "SMILES": lambda rdkit_mol: Chem.MolToSmiles(rdkit_mol),
    "InChI": lambda rdkit_mol: Chem.MolToInchi(rdkit_mol),
    "molecular_formula": lambda rdkit_mol: Chem.rdMolDescriptors.CalcMolFormula(
        rdkit_mol
    ),
    "molecular_weight": lambda rdkit_mol: Chem.rdMolDescriptors.CalcExactMolWt(
        rdkit_mol
    ),
}


SEQUENCE_AUTO_EXTRACT = {
    "protein_sequence": lambda fragment: get_protein_sequence(fragment),
    "nucleic_sequence": lambda fragment: get_nucleic_sequence(fragment),
}


class TopTrajParser:
    """
    Parse topology and trajectory files to extract system and molecule metadata.
    """

    def __init__(self, toppath, trajpath):
        """
        Initialize the parser with topology and trajectory file paths.

        Args:
            toppath (str): Path to topology file.
            trajpath (str): Path to trajectory file.
        """
        self.u = Universe(toppath, trajpath)
        self.lines = []
        self.data = {}
        self.molecule_types = {}

    # =========================
    # MAIN ENTRY
    # =========================
    def parse(self):
        """
        Extract system-level metadata and molecule information.

        Returns:
            dict: Extracted metadata.
        """
        for field, func in TOPTRAJ_AUTO_EXTRACT.items():
            key = field
            if callable(func):
                self.data[key] = func(self.u)
            else:
                self.data[key] = func

        self._extract_molecules()

        # print(json.dumps(self.data, indent=2))
        # print()

        return self.data

    def _extract_molecules(self):
        """
        Identify unique molecule types and their representative fragments.

        Returns:
            None
        """

        # Group by molecule signature
        molecule_types = Counter(
            (tuple(fragment.resnames), tuple(fragment.atoms.names))
            for fragment in self.u.atoms.fragments
        )

        # Get first representative fragment of each type
        representatives = {}
        for fragment in self.u.atoms.fragments:
            signature = (tuple(fragment.resnames), tuple(fragment.atoms.names))
            if signature not in representatives:
                representatives[signature] = {
                    "count": molecule_types[signature],
                    "fragment": fragment,  # Store the actual AtomGroup
                }
        self.data["unique_molecule_count"] = len(representatives)
        self.molecule_types = representatives
        self._find_molecule_IDs()

    def _find_molecule_IDs(self):
        """
        Assign external IDs and extract properties for each unique molecule.

        Returns:
            dict: Updated data with molecule IDs.
        """

        molecule_ids = {}
        for i, (signature, info) in enumerate(self.molecule_types.items()):
            mol_residues, mol_atoms = signature[0], signature[1]
            fragment = info["fragment"]
            fragment_count = info["count"]
            molecule_ids[i] = {"molecule_count": fragment_count}

            for field, func in MOLID_AUTO_EXTRACT.items():
                key = field
                if callable(func):
                    result = func(fragment)
                    if result is not None:
                        molecule_ids[i][key] = result
                else:
                    molecule_ids[i][key] = func

            if len(mol_atoms) == 1:
                atom = fragment.atoms[0]
                molecule_ids[i]["molecular_formula"] = getattr(
                    atom, "element", atom.name.strip("0123456789")
                )
            elif len(set(mol_residues)) == 1 and len(mol_atoms) > 1:
                try:
                    # Attempt RDKit conversion first
                    rdkit_mol = fragment.convert_to("RDKIT")
                    for field, func in RDKIT_AUTO_EXTRACT.items():
                        key = field
                        if callable(func):
                            result = func(rdkit_mol)
                            if result is not None:
                                molecule_ids[i][key] = result
                        else:
                            molecule_ids[i][key] = func

                except Exception:
                    continue
            else:
                for field, func in SEQUENCE_AUTO_EXTRACT.items():
                    key = field
                    if callable(func):
                        result = func(fragment)
                        if result is not None:
                            molecule_ids[i][key] = result
                    else:
                        molecule_ids[i][key] = func

        self.data["molecule_ids"] = molecule_ids
        return self.data


# # =========================
# # USAGE
# # =========================
# if __name__ == "__main__":
#     topology = sys.argv[1]
#     trajectory = sys.argv[2]
#     parser = TopTrajParser(topology, trajectory)
#     result = parser.parse()

#     print(json.dumps(result, indent=2))


# =========================
# ENTRY POINT
# =========================


def parse_args():
    """Parse command-line arguments.

    Returns:
        Parsed ``argparse.Namespace`` object.
    """
    parser = argparse.ArgumentParser(
        description="Extract topology and trajectory files metadata to JSON"
    )
    parser.add_argument("topology", help="Path to topology file")
    parser.add_argument("trajectory", nargs="+", help="Path to trajectory file/s")
    parser.add_argument("--output", "-o", help="Output file path (default: stdout)")
    return parser.parse_args()


def main():
    """Entry point: parse args, run extraction, and write output."""
    args = parse_args()

    parser = TopTrajParser(args.topology, args.trajectory)
    result = parser.parse()

    if args.output:
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2)
    else:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
