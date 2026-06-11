from pathlib import Path
from types import SimpleNamespace

import biosim_extractor.metadata.fetchschema as fs
import biosim_extractor.metadata.populatemetadata as pop


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
