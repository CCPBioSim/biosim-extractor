from pathlib import Path

from biosim_extractor.metadata.filemetadata import (
    file_metadata,
    files_metadata,
    group_files,
)


def test_group_files_creates_dict_when_none():
    out = group_files(["a.log"], saved_files=None, role="log")
    assert out == {"log": ["a.log"]}


def test_group_files_appends_to_existing_role():
    out = group_files(["b.log"], saved_files={"log": ["a.log"]}, role="log")
    assert out == {"log": ["a.log", "b.log"]}


def test_single_file(tmp_path):
    path = tmp_path / "test.bin"
    path.write_bytes(b"\x00\x01\x02")  # Known small content

    meta = file_metadata(str(path), role="other", hash_algorithm="sha256")

    assert meta["file_name"] == "test.bin"
    assert meta["file_role"] == "other"
    assert len(meta["file_hash"]) == 64  # SHA-256 hex length
    assert "value_unit" in meta["file_size"]


def test_multiple_files(tmp_path):
    p1 = tmp_path / "a.bin"
    p2 = tmp_path / "b.bin"
    p1.write_bytes(b"A")
    p2.write_bytes(b"B")

    inputs: dict[str, list[Path]] = {
        "group_1": [p1],
        "group_2": [p2],
    }

    metas = files_metadata(inputs)

    assert len(metas) == 2


def test_default_algorithm(tmp_path):
    p = tmp_path / "d.bin"
    p.write_bytes(b"D")

    # Ensure MD5 is default (no arg provided in call if desired,
    # but explicit check ensures correct hash length for MD5=32)
    meta = file_metadata(str(p))

    assert len(meta["file_hash"]) == 32  # MD5 hex length
