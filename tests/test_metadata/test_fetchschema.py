import io
import json
import sys
import tarfile
from pathlib import Path
from types import SimpleNamespace

import pytest

import biosim_extractor.metadata.fetchschema as fs
import biosim_extractor.metadata.populatemetadata as pop


class _Ctx:
    def __init__(self, obj):
        self.obj = obj

    def __enter__(self):
        return self.obj

    def __exit__(self, exc_type, exc, tb):
        return False


def test_latest_release_tag_reads_tag_name(monkeypatch):
    stream = io.StringIO('{"tag_name": "v9.9.9"}')

    def _fake_urlopen(url, timeout):
        assert url.endswith("/releases/latest")
        assert timeout == 30
        stream.seek(0)
        return _Ctx(stream)

    monkeypatch.setattr(fs.urllib.request, "urlopen", _fake_urlopen)

    assert fs._latest_release_tag("CCPBioSim", "biosim-schema") == "v9.9.9"


def test_download_release_tarball_writes_content(monkeypatch, tmp_path):
    out = tmp_path / "release.tar.gz"

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b"tar-bytes"

    def _fake_urlopen(url, timeout):
        assert url.endswith("/v1.2.3.tar.gz")
        assert timeout == 60
        return _Resp()

    monkeypatch.setattr(fs.urllib.request, "urlopen", _fake_urlopen)

    fs._download_release_tarball("CCPBioSim", "biosim-schema", "v1.2.3", out)

    assert out.read_bytes() == b"tar-bytes"


def test_extract_needed_extracts_and_returns_root(tmp_path):
    source_root = tmp_path / "biosim-schema-1.0.0"
    source_root.mkdir()
    (source_root / "dummy.txt").write_text("x", encoding="utf-8")

    tar_path = tmp_path / "bundle.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tf:
        tf.add(source_root, arcname=source_root.name)

    target = tmp_path / "extract"

    root = fs._extract_needed(tar_path, target)

    assert root.exists()
    assert root.name == "biosim-schema-1.0.0"


def test_extract_needed_raises_when_archive_has_no_root_dirs(tmp_path):
    tar_path = tmp_path / "empty.tar.gz"
    with tarfile.open(tar_path, "w:gz"):
        pass

    with pytest.raises(RuntimeError, match="Release archive extraction failed"):
        fs._extract_needed(tar_path, tmp_path / "extract")


def test_get_schema_force_removes_existing_bundle(monkeypatch, tmp_path):
    base = tmp_path / "cache"
    tag = "v1.2.3"
    bundle_dir = base / tag
    bundle_dir.mkdir(parents=True, exist_ok=True)
    stale = bundle_dir / "stale.txt"
    stale.write_text("old", encoding="utf-8")

    release_root = tmp_path / "release" / "biosim-schema-1.2.3"
    _write_bundle(release_root)

    def _fake_download(_owner, _repo, _tag, out_path):
        # stale marker should be gone after force cleanup
        assert not stale.exists()
        out_path.write_bytes(b"x")

    monkeypatch.setattr(fs, "_download_release_tarball", _fake_download)
    monkeypatch.setattr(fs, "_extract_needed", lambda *_a, **_k: release_root)

    bundle = fs.get_schema(version="1.2.3", cache_dir=str(base), force=True)

    assert bundle.version == tag
    assert bundle.root == release_root


def test_get_schema_raises_for_incomplete_cached_bundle(tmp_path):
    base = tmp_path / "cache"
    tag = "v0.1.0"
    (base / tag / "src").mkdir(parents=True, exist_ok=True)

    with pytest.raises(RuntimeError, match="Cached schema bundle is incomplete"):
        fs.get_schema(version="0.1.0", cache_dir=str(base))


def test_get_schema_raises_when_mapping_missing(tmp_path):
    base = tmp_path / "cache"
    tag = "v0.0.2"
    release_root = base / tag / "src" / "biosim-schema-0.0.2"
    _write_bundle(release_root)
    (release_root / "project" / "schema_enginemappings.json").unlink()

    with pytest.raises(FileNotFoundError, match="Missing mapping json"):
        fs.get_schema(version="0.0.2", cache_dir=str(base))


def test_get_schema_raises_when_schema_yaml_missing(tmp_path):
    base = tmp_path / "cache"
    tag = "v0.0.2"
    release_root = base / tag / "src" / "biosim-schema-0.0.2"
    _write_bundle(release_root)
    (release_root / "biosim_schema" / "schema" / "biosim_schema.yaml").unlink()

    with pytest.raises(FileNotFoundError, match="Missing schema yaml"):
        fs.get_schema(version="0.0.2", cache_dir=str(base))


def test_parse_args_get_defaults(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["fetchschema.py", "get"])
    args = fs.parse_args()

    assert args.command == "get"
    assert args.version == "latest"
    assert args.cache_dir is None
    assert args.owner == "CCPBioSim"
    assert args.repo == "biosim-schema"
    assert args.json is False


def test_parse_args_update_with_options(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "fetchschema.py",
            "update",
            "--version",
            "0.0.2",
            "--cache-dir",
            "/tmp/cache",
            "--owner",
            "X",
            "--repo",
            "Y",
            "--json",
        ],
    )
    args = fs.parse_args()

    assert args.command == "update"
    assert args.version == "0.0.2"
    assert args.cache_dir == "/tmp/cache"
    assert args.owner == "X"
    assert args.repo == "Y"
    assert args.json is True


def test_bundle_payload_serializes_paths(tmp_path):
    bundle = fs.SchemaBundle(
        version="v1",
        root=tmp_path / "root",
        mapping_json=tmp_path / "root" / "project" / "schema_enginemappings.json",
        schema_yaml=tmp_path
        / "root"
        / "biosim_schema"
        / "schema"
        / "biosim_schema.yaml",
    )

    payload = fs._bundle_payload(bundle)

    assert payload["version"] == "v1"
    assert isinstance(payload["root"], str)
    assert isinstance(payload["mapping_json"], str)
    assert isinstance(payload["schema_yaml"], str)


def test_main_prints_json_for_get(monkeypatch, tmp_path):
    args = SimpleNamespace(
        command="get",
        version="latest",
        cache_dir=None,
        owner="CCPBioSim",
        repo="biosim-schema",
        json=True,
    )
    bundle = fs.SchemaBundle(
        version="v1",
        root=tmp_path / "r",
        mapping_json=tmp_path / "r" / "project" / "schema_enginemappings.json",
        schema_yaml=tmp_path / "r" / "biosim_schema" / "schema" / "biosim_schema.yaml",
    )

    monkeypatch.setattr(fs, "parse_args", lambda: args)
    monkeypatch.setattr(fs, "get_schema", lambda **_k: bundle)

    printed = []
    monkeypatch.setattr(
        "builtins.print", lambda *a, **k: printed.append(" ".join(map(str, a)))
    )

    fs.main()

    assert len(printed) == 1
    payload = json.loads(printed[0])
    assert payload["version"] == "v1"


def test_main_prints_text_for_update(monkeypatch, tmp_path):
    args = SimpleNamespace(
        command="update",
        version="0.0.2",
        cache_dir="/tmp/cache",
        owner="CCPBioSim",
        repo="biosim-schema",
        json=False,
    )
    bundle = fs.SchemaBundle(
        version="v0.0.2",
        root=tmp_path / "r",
        mapping_json=tmp_path / "r" / "project" / "schema_enginemappings.json",
        schema_yaml=tmp_path / "r" / "biosim_schema" / "schema" / "biosim_schema.yaml",
    )

    monkeypatch.setattr(fs, "parse_args", lambda: args)
    monkeypatch.setattr(fs, "update_schema", lambda **_k: bundle)

    printed = []
    monkeypatch.setattr(
        "builtins.print", lambda *a, **k: printed.append(" ".join(map(str, a)))
    )

    fs.main()

    assert len(printed) == 4
    assert printed[0].startswith("version:")
    assert printed[1].startswith("root:")
    assert printed[2].startswith("mapping_json:")
    assert printed[3].startswith("schema_yaml:")


def _args(**overrides):
    defaults = {
        "mappingschema": None,
        "biosimschema": None,
        "schema_version": "latest",
        "schema_cache_dir": None,
        "update_schema": False,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _write_bundle(root: Path) -> None:
    (root / "project").mkdir(parents=True, exist_ok=True)
    (root / "biosim_schema" / "schema").mkdir(parents=True, exist_ok=True)
    (root / "project" / "schema_enginemappings.json").write_text("{}", encoding="utf-8")
    (root / "biosim_schema" / "schema" / "biosim_schema.yaml").write_text(
        "id: test\nname: test\n",
        encoding="utf-8",
    )


# -----------------------------
# populatemetadata resolver tests
# -----------------------------


def test_resolve_schema_inputs_uses_explicit_paths_without_fetch(monkeypatch):
    args = _args(
        mappingschema="/custom/schema_enginemappings.json",
        biosimschema="/custom/biosim_schema.yaml",
    )

    def _fail(*_a, **_k):
        raise AssertionError("fetch should not be called when paths are explicit")

    monkeypatch.setattr(pop, "get_schema", _fail)
    monkeypatch.setattr(pop, "update_schema", _fail)

    mapping_path, biosim_path = pop.resolve_schema_inputs(args)

    assert mapping_path == "/custom/schema_enginemappings.json"
    assert biosim_path == "/custom/biosim_schema.yaml"


def test_resolve_schema_inputs_fetches_missing_paths(monkeypatch):
    args = _args(mappingschema=None, biosimschema=None, update_schema=False)

    bundle = SimpleNamespace(
        mapping_json=Path("/cache/v1/project/schema_enginemappings.json"),
        schema_yaml=Path("/cache/v1/biosim_schema/schema/biosim_schema.yaml"),
    )

    called = {}

    def _get_schema(version, cache_dir):
        called["version"] = version
        called["cache_dir"] = cache_dir
        return bundle

    monkeypatch.setattr(pop, "get_schema", _get_schema)
    monkeypatch.setattr(
        pop,
        "update_schema",
        lambda **_k: (_ for _ in ()).throw(AssertionError("should not be called")),
    )

    mapping_path, biosim_path = pop.resolve_schema_inputs(args)

    assert mapping_path == str(bundle.mapping_json)
    assert biosim_path == str(bundle.schema_yaml)
    assert called["version"] == "latest"
    assert called["cache_dir"] is None


def test_resolve_schema_inputs_uses_update_schema_when_requested(monkeypatch):
    args = _args(
        mappingschema=None,
        biosimschema=None,
        schema_version="0.0.2",
        schema_cache_dir="/tmp/schema-cache",
        update_schema=True,
    )

    bundle = SimpleNamespace(
        mapping_json=Path("/cache/v0.0.2/project/schema_enginemappings.json"),
        schema_yaml=Path("/cache/v0.0.2/biosim_schema/schema/biosim_schema.yaml"),
    )

    called = {}

    def _update_schema(version, cache_dir):
        called["version"] = version
        called["cache_dir"] = cache_dir
        return bundle

    monkeypatch.setattr(
        pop,
        "get_schema",
        lambda **_k: (_ for _ in ()).throw(AssertionError("should not be called")),
    )
    monkeypatch.setattr(pop, "update_schema", _update_schema)

    mapping_path, biosim_path = pop.resolve_schema_inputs(args)

    assert mapping_path == str(bundle.mapping_json)
    assert biosim_path == str(bundle.schema_yaml)
    assert called["version"] == "0.0.2"
    assert called["cache_dir"] == "/tmp/schema-cache"


# -----------------------------
# fetchschema utility tests
# -----------------------------


def test_get_schema_uses_cached_bundle_without_download(monkeypatch, tmp_path):
    base = tmp_path / "cache"
    tag = "v0.0.2"
    release_root = base / tag / "src" / "biosim-schema-0.0.2"
    _write_bundle(release_root)

    monkeypatch.setattr(
        fs,
        "_download_release_tarball",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("should not download")),
    )

    bundle = fs.get_schema(version="0.0.2", cache_dir=str(base))

    assert bundle.version == tag
    assert bundle.root == release_root
    assert bundle.mapping_json.exists()
    assert bundle.schema_yaml.exists()


def test_get_schema_downloads_and_extracts_when_missing(monkeypatch, tmp_path):
    base = tmp_path / "cache"
    tag = "v1.2.3"
    extracted_root = tmp_path / "extracted" / "biosim-schema-1.2.3"

    monkeypatch.setattr(fs, "_latest_release_tag", lambda *_a, **_k: tag)

    def _fake_download(_owner, _repo, _tag, out_path):
        out_path.write_bytes(b"fake-tarball")

    def _fake_extract(_tar_path, _target_dir):
        _write_bundle(extracted_root)
        return extracted_root

    monkeypatch.setattr(fs, "_download_release_tarball", _fake_download)
    monkeypatch.setattr(fs, "_extract_needed", _fake_extract)

    bundle = fs.get_schema(version="latest", cache_dir=str(base))

    assert bundle.version == tag
    assert bundle.root == extracted_root
    assert (
        bundle.mapping_json == extracted_root / "project" / "schema_enginemappings.json"
    )
    assert (
        bundle.schema_yaml
        == extracted_root / "biosim_schema" / "schema" / "biosim_schema.yaml"
    )


def test_update_schema_passes_force_true(monkeypatch):
    captured = {}

    def _fake_get_schema(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            version="v0.0.2",
            root=Path("/tmp/root"),
            mapping_json=Path("/tmp/root/project/schema_enginemappings.json"),
            schema_yaml=Path("/tmp/root/biosim_schema/schema/biosim_schema.yaml"),
        )

    monkeypatch.setattr(fs, "get_schema", _fake_get_schema)

    fs.update_schema(
        version="0.0.2", cache_dir="/tmp/cache", owner="CCPBioSim", repo="biosim-schema"
    )

    assert captured["version"] == "0.0.2"
    assert captured["cache_dir"] == "/tmp/cache"
    assert captured["owner"] == "CCPBioSim"
    assert captured["repo"] == "biosim-schema"
    assert captured["force"] is True
