from __future__ import annotations

import argparse
import json
import os
import shutil
import tarfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SchemaBundle:
    version: str
    root: Path
    mapping_json: Path
    schema_yaml: Path


def _latest_release_tag(owner: str, repo: str) -> str:
    url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    with urllib.request.urlopen(url, timeout=30) as r:
        payload = json.load(r)
    return payload["tag_name"]


def _download_release_tarball(owner: str, repo: str, tag: str, out_path: Path) -> None:
    url = f"https://github.com/{owner}/{repo}/archive/refs/tags/{tag}.tar.gz"
    with urllib.request.urlopen(url, timeout=60) as r, out_path.open("wb") as w:
        w.write(r.read())


def _extract_needed(tar_path: Path, target_dir: Path) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tar_path, "r:gz") as tf:
        tf.extractall(target_dir)
    roots = [p for p in target_dir.iterdir() if p.is_dir()]
    if not roots:
        raise RuntimeError("Release archive extraction failed")
    return roots[0]


def get_schema(
    version: str = "latest",
    cache_dir: str | None = None,
    owner: str = "CCPBioSim",
    repo: str = "biosim-schema",
    force: bool = False,
) -> SchemaBundle:
    tag = (
        _latest_release_tag(owner, repo)
        if version == "latest"
        else (version if version.startswith("v") else f"v{version}")
    )

    base = Path(
        cache_dir or os.getenv("BIOSIM_SCHEMA_CACHE_DIR", "/tmp/biosim-schema-cache")
    )
    bundle_dir = base / tag

    if force and bundle_dir.exists():
        shutil.rmtree(bundle_dir)

    if not bundle_dir.exists():
        bundle_dir.mkdir(parents=True, exist_ok=True)
        tar_path = bundle_dir / f"{tag}.tar.gz"
        _download_release_tarball(owner, repo, tag, tar_path)
        release_root = _extract_needed(tar_path, bundle_dir / "src")
        tar_path.unlink(missing_ok=True)
    else:
        src = bundle_dir / "src"
        roots = [p for p in src.iterdir() if p.is_dir()]
        if not roots:
            raise RuntimeError(f"Cached schema bundle is incomplete: {bundle_dir}")
        release_root = roots[0]

    mapping_json = release_root / "project" / "schema_enginemappings.json"
    schema_yaml = release_root / "biosim_schema" / "schema" / "biosim_schema.yaml"

    if not mapping_json.exists():
        raise FileNotFoundError(f"Missing mapping json: {mapping_json}")
    if not schema_yaml.exists():
        raise FileNotFoundError(f"Missing schema yaml: {schema_yaml}")

    return SchemaBundle(
        version=tag,
        root=release_root,
        mapping_json=mapping_json,
        schema_yaml=schema_yaml,
    )


def update_schema(
    version: str = "latest",
    cache_dir: str | None = None,
    owner: str = "CCPBioSim",
    repo: str = "biosim-schema",
) -> SchemaBundle:
    return get_schema(
        version=version,
        cache_dir=cache_dir,
        owner=owner,
        repo=repo,
        force=True,
    )


def parse_args():
    parser = argparse.ArgumentParser(
        description="Fetch biosim-schema mapping and validation schema files."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common(subparser):
        subparser.add_argument(
            "--version", default="latest", help="Schema version/tag, or latest"
        )
        subparser.add_argument("--cache-dir", default=None, help="Cache directory")
        subparser.add_argument("--owner", default="CCPBioSim", help="GitHub owner")
        subparser.add_argument("--repo", default="biosim-schema", help="GitHub repo")
        subparser.add_argument(
            "--json", action="store_true", help="Print result as JSON"
        )

    get_parser = subparsers.add_parser("get", help="Use cached schema if available")
    add_common(get_parser)

    update_parser = subparsers.add_parser(
        "update", help="Force refresh schema in cache"
    )
    add_common(update_parser)

    return parser.parse_args()


def _bundle_payload(bundle: SchemaBundle) -> dict:
    return {
        "version": bundle.version,
        "root": str(bundle.root),
        "mapping_json": str(bundle.mapping_json),
        "schema_yaml": str(bundle.schema_yaml),
    }


def main():
    args = parse_args()

    func = update_schema if args.command == "update" else get_schema
    bundle = func(
        version=args.version,
        cache_dir=args.cache_dir,
        owner=args.owner,
        repo=args.repo,
    )

    payload = _bundle_payload(bundle)
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print("version:", payload["version"])
        print("root:", payload["root"])
        print("mapping_json:", payload["mapping_json"])
        print("schema_yaml:", payload["schema_yaml"])


if __name__ == "__main__":
    main()
