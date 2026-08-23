"""Utility to extract binary file metadata (size, hash)."""

import hashlib
from pathlib import Path

import xxhash


def file_metadata(path, role="other", hash_algorithm="md5"):
    """Extract name, size (MB), and hash of a single file.

    Args:
        path: Input file path (str or :class:`pathlib.Path`).
        role: Optional category label for the file. Defaults to "other".
        hash_algorithm: Hash function identifier ('md5', 'sha256', 'xxh3_64').
        Default is 'md5'.

    Returns:
        Dictionary containing 'file_name', 'file_size' (dict), 'file_hash',
        'file_hash_algorithm', and 'file_role'.
    """
    path = Path(path)
    size_mb = path.stat().st_size / 1_000_000

    if hash_algorithm == "xxh3_64":
        hasher = xxhash.xxh3_64()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
                hasher.update(chunk)
        file_hash = hasher.hexdigest()
    else:
        with path.open("rb") as handle:
            digest = hashlib.file_digest(handle, hash_algorithm)
            file_hash = digest.hexdigest()

    return {
        "file_name": path.name,
        "file_size": {"value": round(size_mb, 6), "value_unit": "MB"},
        "file_hash": file_hash,
        "file_hash_algorithm": hash_algorithm,
        "file_role": role,
    }


def files_metadata(saved_files):
    """Compile metadata for multiple files grouped by role.

    Args:
        saved_files: Dictionary mapping roles to lists of file paths
            (:data:`str` or :class:`pathlib.Path`).

    Returns:
        Flat list of ``file_metadata`` dictionaries for all provided paths.
    """
    return [
        file_metadata(path, role)
        for role, paths in saved_files.items()
        for path in paths
    ]


def group_files(filepaths, saved_files=None, role="other"):
    """Add file paths to a role-based dictionary.

    Args:
        filepaths: Iterable of file paths to add.
        saved_files: Dictionary mapping roles to lists of file paths.
        role: Role name under which to store the file paths.

    Returns:
        Updated dictionary of file paths grouped by role.
    """
    if saved_files is None:
        saved_files = {}
    for filepath in filepaths:
        saved_files.setdefault(role, []).append(filepath)
    return saved_files
