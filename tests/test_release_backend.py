import importlib.util
import json
import sqlite3
import zipfile
from pathlib import Path

import pytest

from backend.server import CPSHTTPRequestHandler
from cps import storage
from cps.patcher import apply_patch


def _load_packager():
    path = Path(__file__).parents[1] / "scripts" / "package_release.py"
    spec = importlib.util.spec_from_file_location("cps_package_release", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_locked_database_is_not_treated_as_corruption(tmp_path, monkeypatch):
    monkeypatch.setattr(storage.config, "DATA_DIR", tmp_path)

    def locked(_path):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(storage, "_connect", locked)
    with pytest.raises(sqlite3.OperationalError, match="database is locked"):
        storage.list_scans()
    assert not list(tmp_path.glob("history.db.corrupt.*"))


def test_patch_preserves_lf_bytes_and_removes_temp_file(tmp_path):
    target = tmp_path / "sample.py"
    target.write_bytes(b"one\ntwo\n")
    apply_patch(tmp_path, "sample.py", "one\nchanged\n", approved=True)
    assert target.read_bytes() == b"one\nchanged\n"
    assert not list(tmp_path.glob(".*.cps-*"))


def test_release_archives_are_deterministic_and_clean(tmp_path):
    packager = _load_packager()
    extension_a = packager.build_extension_archive(tmp_path / "extension-a.zip")
    release_a = packager.build_release_archive(tmp_path / "release-a.zip")
    extension_b = packager.build_extension_archive(tmp_path / "extension-b.zip")
    release_b = packager.build_release_archive(tmp_path / "release-b.zip")

    assert extension_a.read_bytes() == extension_b.read_bytes()
    assert release_a.read_bytes() == release_b.read_bytes()

    with zipfile.ZipFile(extension_a) as archive:
        assert "manifest.json" in archive.namelist()
        assert all(not name.startswith("extension/") for name in archive.namelist())
        assert json.loads(archive.read("manifest.json"))["version"] == "1.0.0"

    with zipfile.ZipFile(release_a) as archive:
        names = set(archive.namelist())
        assert "README.md" in names
        assert not any(
            name.startswith(("dist/", "cps_data/", "vulnquest_data/"))
            or name.endswith((".db", ".pyc"))
            or name == ".env"
            for name in names
        )


def test_handler_dispatch_converts_unexpected_failures_to_json_error():
    handler = object.__new__(CPSHTTPRequestHandler)

    def fail(*_args, **_kwargs):
        raise RuntimeError("boom")

    # This exercises the fallback's protective boundary without opening a port.
    import backend.server as server
    original = server.handle_api_request
    server.handle_api_request = fail
    try:
        status, body = handler._dispatch("GET", "/api/health")
    finally:
        server.handle_api_request = original
    assert status == 500
    assert body["error"] == "internal server error"
