"""Build deterministic C.P.S. distribution archives.

The extension archive has the extension files at its root, as required by
Chrome and Edge.  The application archive contains source and documentation,
but never local databases, backups, secrets, caches, build products, or the
``dist`` directory itself.
"""
from __future__ import annotations

import os
import sys
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
try:
    # Keep archive names synchronized with the application package metadata.
    sys.path.insert(0, str(ROOT))
    from cps import __version__ as VERSION
except (ImportError, AttributeError):
    VERSION = "1.0.0"
_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)

# Directory names are checked at every level so generated local data cannot
# leak into a release even when nested below another directory.
EXCLUDE_DIRS = frozenset({
    ".git",
    ".venv",
    "venv",
    ".cps_backup",
    ".vulnquest_backup",
    "__pycache__",
    ".pytest_cache",
    "cps_data",
    "vulnquest_data",
    "build",
    "dist",
})
EXCLUDE_SUFFIXES = (".egg-info",)
EXCLUDE_FILES = frozenset({".env", "history.db", "backend_settings.json"})
EXCLUDE_EXTENSIONS = frozenset({".pyc", ".pyo", ".log", ".tmp", ".sqlite", ".sqlite3", ".db"})

STORE_PERMISSIONS = frozenset({"activeTab", "storage", "sidePanel", "contextMenus", "scripting"})
STORE_HOST_PERMISSIONS = frozenset({"http://localhost:8899/*", "http://127.0.0.1:8899/*"})
STORE_OPTIONAL_HOST_PERMISSIONS = frozenset({
    "https://api.groq.com/*",
    "https://generativelanguage.googleapis.com/*",
    "https://openrouter.ai/*",
})
STORE_REQUIRED_FILES = frozenset({
    "manifest.json",
    "background.js",
    "content.js",
    "shared/browser-api.js",
    "site_adapters/adapters.js",
    "popup/popup.html",
    "popup/popup.js",
    "sidebar/sidebar.html",
    "sidebar/sidebar.js",
    "icons/16.png",
    "icons/32.png",
    "icons/48.png",
    "icons/128.png",
})


def _is_excluded_file(path: Path) -> bool:
    if path.name in EXCLUDE_FILES:
        return True
    if path.suffix.lower() in EXCLUDE_EXTENSIONS:
        return True
    return path.name.startswith(".") and path.name != ".env.example" and path.name != ".gitignore"


def _iter_files(base: Path, *, extension_only: bool = False):
    """Yield archive candidates in stable, POSIX-relative order."""
    candidates = []
    for current, dirs, files in os.walk(base):
        current_path = Path(current)
        dirs[:] = sorted(
            d for d in dirs
            if d not in EXCLUDE_DIRS and not any(d.endswith(s) for s in EXCLUDE_SUFFIXES)
        )
        for filename in files:
            path = current_path / filename
            if extension_only and path.is_file() and not _is_excluded_file(path):
                candidates.append(path)
            elif not extension_only and path.is_file() and not _is_excluded_file(path):
                candidates.append(path)
    return sorted(candidates, key=lambda p: p.relative_to(base).as_posix())


def _write_zip(destination: Path, files: list[tuple[Path, str]]) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        destination,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for source, arcname in files:
            info = zipfile.ZipInfo(arcname, date_time=_ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            # Stable Unix regular-file mode and no host-specific attributes.
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, source.read_bytes())


def _store_validation_errors(names: set[str], manifest: dict) -> list[str]:
    errors = []
    missing = sorted(STORE_REQUIRED_FILES - names)
    if missing:
        errors.append(f"missing required files: {', '.join(missing)}")
    if manifest.get("manifest_version") != 3:
        errors.append("manifest_version must be 3")
    if not isinstance(manifest.get("version"), str) or not manifest["version"]:
        errors.append("manifest version must be a non-empty string")
    permissions = frozenset(manifest.get("permissions", []))
    if permissions != STORE_PERMISSIONS:
        errors.append(f"permissions must be exactly {sorted(STORE_PERMISSIONS)}")
    if frozenset(manifest.get("host_permissions", [])) != STORE_HOST_PERMISSIONS:
        errors.append("host_permissions must contain only the local backend origins")
    if frozenset(manifest.get("optional_host_permissions", [])) != STORE_OPTIONAL_HOST_PERMISSIONS:
        errors.append("optional_host_permissions do not match the supported direct providers")
    matches = [match for script in manifest.get("content_scripts", []) for match in script.get("matches", [])]
    if any(match == "<all_urls>" or "*://*/*" in match for match in matches):
        errors.append("content scripts must not use broad all-site matches")
    for name in names:
        if name.startswith("/") or "\\" in name or name.startswith((".env", ".git", "__pycache__/")):
            errors.append(f"unsafe store archive path: {name}")
    return errors


def validate_extension_tree(extension_root: Path | None = None) -> None:
    """Validate the unpacked extension before it is offered as a store package."""
    extension_root = extension_root or ROOT / "extension"
    manifest_path = extension_root / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError("extension manifest.json is missing")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"extension manifest.json is not valid JSON: {exc}") from exc
    names = {path.relative_to(extension_root).as_posix() for path in _iter_files(extension_root, extension_only=True)}
    errors = _store_validation_errors(names, manifest)
    if errors:
        raise ValueError("invalid store package: " + "; ".join(errors))


def validate_store_package(package_path: Path, expected_version: str | None = None) -> None:
    """Validate a built ZIP has a store-safe root and deterministic metadata."""
    with zipfile.ZipFile(package_path) as archive:
        infos = archive.infolist()
        names = {info.filename for info in infos}
        if len(names) != len(infos):
            raise ValueError("store package contains duplicate paths")
        if any(info.date_time != _ZIP_TIMESTAMP for info in infos):
            raise ValueError("store package contains non-deterministic timestamps")
        if any(name.startswith("extension/") for name in names):
            raise ValueError("manifest.json must be at the ZIP root")
        try:
            manifest = json.loads(archive.read("manifest.json"))
        except (KeyError, json.JSONDecodeError) as exc:
            raise ValueError(f"store package manifest is invalid: {exc}") from exc
        if expected_version and manifest.get("version") != expected_version:
            raise ValueError("store package version does not match the requested version")
        errors = _store_validation_errors(names, manifest)
        if errors:
            raise ValueError("invalid store package: " + "; ".join(errors))


def build_extension_archive(destination: Path | None = None) -> Path:
    destination = destination or DIST / f"cps-extension-v{VERSION}.zip"
    extension_root = ROOT / "extension"
    validate_extension_tree(extension_root)
    files = [
        (path, path.relative_to(extension_root).as_posix())
        for path in _iter_files(extension_root, extension_only=True)
    ]
    _write_zip(destination, files)
    validate_store_package(destination, VERSION)
    return destination


def build_release_archive(destination: Path | None = None) -> Path:
    destination = destination or DIST / f"cps-v{VERSION}-release.zip"
    files = [
        (path, path.relative_to(ROOT).as_posix())
        for path in _iter_files(ROOT)
    ]
    _write_zip(destination, files)
    return destination


def main() -> int:
    extension_zip = build_extension_archive()
    release_zip = build_release_archive()
    print(f"Created {extension_zip} ({extension_zip.stat().st_size} bytes)")
    print(f"Created {release_zip} ({release_zip.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
