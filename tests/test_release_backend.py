import importlib.util
import json
import sqlite3
from urllib.request import urlopen
import zipfile
from pathlib import Path

import pytest

from backend.server import CPSHTTPRequestHandler
from backend.runtime import LocalBackend
from cps import config
from cps import storage
from cps.patcher import apply_patch


def _load_packager():
    path = Path(__file__).parents[1] / "scripts" / "package_release.py"
    spec = importlib.util.spec_from_file_location("cps_package_release", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _load_script(name):
    path = Path(__file__).parents[1] / "scripts" / name
    spec = importlib.util.spec_from_file_location(f"cps_{name.replace('.', '_')}", path)
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


def test_extension_store_validator_enforces_narrow_manifest_and_root_layout(tmp_path):
    packager = _load_packager()
    extension = packager.build_extension_archive(tmp_path / "store.zip")
    packager.validate_extension_tree(Path(__file__).parents[1] / "extension")
    packager.validate_store_package(extension, "1.0.0")

    with zipfile.ZipFile(extension) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert "<all_urls>" not in {
            match
            for script in manifest["content_scripts"]
            for match in script["matches"]
        }
        assert "scripting" in manifest["permissions"]
        background = archive.read("background.js").decode("utf-8")
        assert "body.apiKey" not in background
        assert "backend-stopped" in background
        assert "python -m backend.server" in background


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


def test_installed_data_defaults_to_windows_local_appdata(monkeypatch, tmp_path):
    monkeypatch.delenv("CPS_DATA_DIR", raising=False)
    monkeypatch.delenv("VULNQUEST_DATA_DIR", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "LocalAppData"))
    monkeypatch.setattr(config.sys, "platform", "win32")

    assert config.default_data_dir() == tmp_path / "LocalAppData" / "CPS"


def test_local_backend_is_loopback_only_and_has_lifecycle():
    with pytest.raises(ValueError, match="loopback"):
        LocalBackend("0.0.0.0", 0)

    backend = LocalBackend("127.0.0.1", 0).start()
    try:
        assert backend.running
        assert backend.address is not None
        assert backend.address[0] == "127.0.0.1"
        assert backend.address[1] > 0
        with urlopen(f"http://127.0.0.1:{backend.address[1]}/api/health", timeout=2) as response:
            assert json.loads(response.read())['status'] == "ok"
    finally:
        backend.stop()
    assert not backend.running


def test_local_backend_reuses_an_existing_cps_listener():
    owner = LocalBackend("127.0.0.1", 0).start()
    port = owner.address[1]
    attached = LocalBackend("127.0.0.1", port).start()
    try:
        assert attached.running
        attached.stop()
        assert owner.running
    finally:
        owner.stop()


def test_release_metadata_and_installer_are_synchronized():
    root = Path(__file__).parents[1]
    with (root / "pyproject.toml").open("rb") as fh:
        import tomllib
        project_version = tomllib.load(fh)["project"]["version"]
    package_version = importlib.import_module("cps").__version__
    manifest_version = json.loads((root / "extension" / "manifest.json").read_text())[
        "version"
    ]
    installer = (root / "installer" / "CPS.iss").read_text(encoding="utf-8")
    spec = (root / "packaging" / "cps.spec").read_text(encoding="utf-8")

    assert project_version == package_version == manifest_version
    assert "GetFileVersion(\"..\\dist\\CPS\\CPS.exe\")" in installer
    assert "from cps import __product__, __version__" in spec


def test_windows_release_inputs_do_not_ship_local_state():
    root = Path(__file__).parents[1]
    installer = (root / "installer" / "CPS.iss").read_text(encoding="utf-8")
    assert "dist\\CPS\\*" in installer
    assert "history.db" not in installer
    assert ".env" not in installer


def test_desktop_archive_is_deterministic_and_contains_executable(tmp_path):
    packager = _load_script("package_desktop.py")
    source = tmp_path / "CPS"
    source.mkdir()
    (source / "CPS.exe").write_bytes(b"test executable")
    (source / "Qt6Core.dll").write_bytes(b"test dll")
    (source / "history.db").write_bytes(b"must not be bundled")

    first = packager.build_desktop_archive(source, tmp_path / "first.zip")
    second = packager.build_desktop_archive(source, tmp_path / "second.zip")
    assert first.read_bytes() == second.read_bytes()
    with zipfile.ZipFile(first) as archive:
        assert "CPS.exe" in archive.namelist()
        assert "Qt6Core.dll" in archive.namelist()
        assert "history.db" not in archive.namelist()


def test_checksum_writer_rejects_missing_artifacts(tmp_path, monkeypatch):
    checksums = _load_script("write_checksums.py")
    import sys
    monkeypatch.setattr(sys, "argv", ["write_checksums.py", str(tmp_path / "missing.zip")])
    with pytest.raises(SystemExit, match="Missing release artifact"):
        checksums.main()
