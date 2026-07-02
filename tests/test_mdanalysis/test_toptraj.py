from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import biosim_extractor.mdanalysis.toptraj as toptraj


def test_get_protein_sequence_returns_none_on_exception():
    fragment = MagicMock()
    fragment.select_atoms.side_effect = RuntimeError("boom")
    assert toptraj.get_protein_sequence(fragment) is None


def test_get_nucleic_sequence_returns_none_on_exception():
    fragment = MagicMock()
    fragment.select_atoms.side_effect = RuntimeError("boom")
    assert toptraj.get_nucleic_sequence(fragment) is None


def test_classify_box_hexagonal_angle_branch():
    # Covers the 90,90,120 branch
    assert toptraj.classify_box([10, 20, 30, 90, 90, 120]) == "orthorhombic"


@patch("biosim_extractor.mdanalysis.toptraj.Universe")
def test_parse_handles_non_callable_toptraj_extract(mock_universe, monkeypatch):
    u = MagicMock()
    u.atoms.fragments = []
    mock_universe.return_value = u
    monkeypatch.setattr(toptraj, "TOPTRAJ_AUTO_EXTRACT", {"constant_field": 123})

    parser = toptraj.TopTrajParser("top", "traj")
    out = parser.parse()
    assert out["constant_field"] == 123


def test_find_molecule_ids_atom_formula_fallback(monkeypatch):
    parser = object.__new__(toptraj.TopTrajParser)
    parser.data = {}
    atom = SimpleNamespace(name="C12")  # no .element -> fallback strips digits
    frag = MagicMock()
    frag.atoms = MagicMock()
    frag.atoms.__getitem__.return_value = atom

    parser.molecule_types = {(("X",), ("C12",)): {"count": 1, "fragment": frag}}

    monkeypatch.setattr(toptraj, "MOLID_AUTO_EXTRACT", {})
    parser._find_molecule_IDs()
    assert parser.data["molecule_ids"][0]["molecular_formula"] == "C"


def test_find_molecule_ids_rdkit_failure_continue(monkeypatch):
    parser = object.__new__(toptraj.TopTrajParser)
    parser.data = {}
    frag = MagicMock()
    frag.convert_to.side_effect = ValueError("rdkit fail")

    parser.molecule_types = {(("ALA",), ("N", "CA")): {"count": 1, "fragment": frag}}

    monkeypatch.setattr(toptraj, "MOLID_AUTO_EXTRACT", {})
    parser._find_molecule_IDs()
    assert "InChIKey" not in parser.data["molecule_ids"][0]


def test_find_molecule_ids_non_callable_molid_and_sequence(monkeypatch):
    parser = object.__new__(toptraj.TopTrajParser)
    parser.data = {}
    frag = MagicMock()

    parser.molecule_types = {
        (("ALA", "GLY"), ("N", "CA")): {"count": 1, "fragment": frag}
    }

    monkeypatch.setattr(toptraj, "MOLID_AUTO_EXTRACT", {"kind": "peptide"})
    monkeypatch.setattr(toptraj, "SEQUENCE_AUTO_EXTRACT", {"source": "fallback"})
    parser._find_molecule_IDs()

    m = parser.data["molecule_ids"][0]
    assert m["kind"] == "peptide"
    assert m["source"] == "fallback"


def test_main_writes_output_file(monkeypatch, tmp_path):
    out = tmp_path / "result.json"
    args = SimpleNamespace(topology="top", trajectory=["traj"], output=str(out))

    monkeypatch.setattr(toptraj, "parse_args", lambda: args)

    fake_parser = MagicMock()
    fake_parser.parse.return_value = {"foo": "bar"}
    monkeypatch.setattr(toptraj, "TopTrajParser", lambda *_: fake_parser)

    toptraj.main()
    assert out.exists()
    assert '"foo": "bar"' in out.read_text()


def make_mock_atoms(length, names=None):
    atoms = MagicMock()
    atom_mocks = [MagicMock() for _ in range(length)]
    atoms.__len__.return_value = length
    atoms.__getitem__.side_effect = lambda idx: atom_mocks[idx]
    atoms.__iter__.return_value = iter(atom_mocks)
    if names:
        atoms.names = names
    return atoms


def make_mock_residues(length, resnames=None):
    residues = MagicMock()
    residues.__len__.return_value = length
    if resnames:
        residues.resnames = resnames
    return residues


@pytest.mark.parametrize(
    "dims, expected",
    [
        ([10, 10, 10, 90, 90, 90], "cubic"),
        ([10, 10, 20, 90, 90, 90], "tetragonal"),
        ([10, 20, 30, 90, 90, 90], "orthorhombic"),
        ([10, 10, 10, 90, 120, 120], "truncated octahedron"),
        ([10, 10, 10, 80, 100, 110], "triclinic"),
    ],
)
def test_classify_box_variants(dims, expected):
    assert toptraj.classify_box(dims) == expected


def test_safe_extract_numpy_scalar():
    class Dummy:
        def __call__(self):
            class N:
                def item(self):
                    return 42.0

            return N()

    assert toptraj.safe_extract(Dummy()) == 42.0


def test_safe_extract_numpy_array():
    class Dummy:
        def __call__(self):
            class N:
                def tolist(self):
                    return [1.0, 2.0]

            return N()

    assert toptraj.safe_extract(Dummy()) == [1.0, 2.0]


def test_safe_extract_list_of_numpy():
    class Dummy:
        def __call__(self):
            class N:
                def item(self):
                    return 1.0

                def __float__(self):
                    return 1.0

            return [N(), N()]

    assert toptraj.safe_extract(Dummy()) == [1.0, 1.0]


def test_safe_extract_handles_non_numpy():
    class Dummy:
        def __call__(self):
            return 123

    assert toptraj.safe_extract(Dummy()) == 123


def test_get_protein_sequence_handles_no_protein():
    fragment = MagicMock()
    fragment.select_atoms.return_value = []
    assert toptraj.get_protein_sequence(fragment) is None


def test_get_nucleic_sequence_handles_no_nucleic():
    fragment = MagicMock()
    fragment.select_atoms.return_value = []
    assert toptraj.get_nucleic_sequence(fragment) is None


def test_get_protein_sequence_with_alternative_names():
    fragment = MagicMock()
    protein_atoms = MagicMock()
    residues_mock = MagicMock()
    residues_mock.__iter__.return_value = [
        MagicMock(resname="ALAD"),
        MagicMock(resname="ASH"),
    ]
    residues_mock.sequence.return_value.seq = "AA"
    protein_atoms.residues = residues_mock
    fragment.select_atoms.return_value = protein_atoms
    protein_atoms.__len__.return_value = 2
    assert toptraj.get_protein_sequence(fragment) == "AA"


def test_get_nucleic_sequence_with_dna():
    fragment = MagicMock()
    dna_atoms = MagicMock()
    dna_atoms.residues = MagicMock()
    dna_atoms.residues.resnames = ["DA", "DT", "DG"]
    fragment.select_atoms.return_value = dna_atoms
    dna_atoms.__len__.return_value = 3
    assert toptraj.get_nucleic_sequence(fragment) == "ATG"


@patch("biosim_extractor.mdanalysis.toptraj.Chem")
def test_rdkit_auto_extract_and_sequence_auto_extract(mock_chem):
    rdkit_mol = MagicMock()
    mock_chem.MolToInchiKey.return_value = "INCHIKEY"
    mock_chem.MolToSmiles.return_value = "SMILES"
    mock_chem.MolToInchi.return_value = "INCHI"
    mock_chem.rdMolDescriptors.CalcMolFormula.return_value = "H2O"
    mock_chem.rdMolDescriptors.CalcExactMolWt.return_value = 18.0

    assert toptraj.RDKIT_AUTO_EXTRACT["InChIKey"](rdkit_mol) == "INCHIKEY"
    assert toptraj.RDKIT_AUTO_EXTRACT["SMILES"](rdkit_mol) == "SMILES"
    assert toptraj.RDKIT_AUTO_EXTRACT["InChI"](rdkit_mol) == "INCHI"
    assert toptraj.RDKIT_AUTO_EXTRACT["molecular_formula"](rdkit_mol) == "H2O"
    assert toptraj.RDKIT_AUTO_EXTRACT["molecular_weight"](rdkit_mol) == 18.0

    fragment = MagicMock()
    with patch(
        "biosim_extractor.mdanalysis.toptraj.get_protein_sequence", return_value="ABC"
    ):
        assert toptraj.SEQUENCE_AUTO_EXTRACT["protein_sequence"](fragment) == "ABC"
    with patch(
        "biosim_extractor.mdanalysis.toptraj.get_nucleic_sequence", return_value="ATG"
    ):
        assert toptraj.SEQUENCE_AUTO_EXTRACT["nucleic_sequence"](fragment) == "ATG"


@patch("biosim_extractor.mdanalysis.toptraj.Universe")
def test_toptrajparser_parse_and_extract_molecules(mock_universe):
    import numpy as np

    mock_u = MagicMock()
    mock_u.atoms.n_atoms = 100
    mock_u.atoms.charges = [1.0] * 100
    mock_u.atoms.fragments = [MagicMock(), MagicMock()]
    mock_trajectory = MagicMock()
    mock_trajectory.__len__.return_value = 1
    mock_trajectory.__getitem__.return_value = MagicMock(
        dimensions=np.array([10, 10, 10, 90, 90, 90])
    )
    mock_u.trajectory = mock_trajectory
    mock_u.select_atoms.return_value = [1, 2, 3]
    mock_universe.return_value = mock_u

    parser = toptraj.TopTrajParser("top", "traj")
    result = parser.parse()
    assert isinstance(result, dict)
    assert "total_atom_count" in result
    assert "molecule_ids" in result


def test_molid_auto_extract():
    fragment = MagicMock()
    fragment.atoms = make_mock_atoms(5)
    fragment.residues = [1, 2]
    fragment.atoms.charges = [1.0, -1.0, 0.0, 0.0, 0.0]
    fragment.masses = [12.0, 1.0, 1.0, 16.0, 14.0]
    assert toptraj.MOLID_AUTO_EXTRACT["atom_count"](fragment) == 5
    assert toptraj.MOLID_AUTO_EXTRACT["monomer_count"](fragment) == 2
    assert toptraj.MOLID_AUTO_EXTRACT["molecule_charge"](fragment) == 0.0
    assert toptraj.MOLID_AUTO_EXTRACT["molecular_weight"](fragment) == pytest.approx(
        44.0
    )


@patch("biosim_extractor.mdanalysis.toptraj.Universe")
def test_toptrajparser_find_molecule_ids_peptide_and_atom(mock_universe):
    import numpy as np

    mock_u = MagicMock()
    mock_u.atoms.n_atoms = 2
    mock_u.atoms.charges = [1.0, -1.0]
    # Atom fragment
    atom_fragment = MagicMock()
    atom_fragment.atoms = make_mock_atoms(1)
    atom_fragment.residues = make_mock_residues(1)
    atom_fragment.atoms[0].element = "H"
    atom_fragment.atoms[0].name = "H1"
    # Peptide fragment
    peptide_fragment = MagicMock()
    peptide_fragment.atoms = make_mock_atoms(2, names=["N", "CA"])
    peptide_fragment.residues = make_mock_residues(2, resnames=["ALA", "GLY"])
    peptide_fragment.convert_to.return_value = MagicMock()
    mock_u.atoms.fragments = [atom_fragment, peptide_fragment]
    mock_trajectory = MagicMock()
    mock_trajectory.__len__.return_value = 1
    mock_trajectory.__getitem__.return_value = MagicMock(
        dimensions=np.array([10, 10, 10, 90, 90, 90])
    )
    mock_u.trajectory = mock_trajectory
    mock_u.select_atoms.return_value = [1, 2]
    mock_universe.return_value = mock_u

    parser = toptraj.TopTrajParser("top", "traj")
    result = parser.parse()
    assert "molecule_ids" in result
    assert result["unique_molecule_count"] == 2


def test_cli_entry_point(monkeypatch):
    import sys

    args = ["prog", "top", "traj"]
    monkeypatch.setattr(sys, "argv", args)
    with patch("biosim_extractor.mdanalysis.toptraj.TopTrajParser") as mock_parser:
        instance = mock_parser.return_value
        instance.parse.return_value = {"foo": "bar"}
        with patch("builtins.print") as mock_print:
            toptraj.main()
            mock_print.assert_called_with('{\n  "foo": "bar"\n}')
