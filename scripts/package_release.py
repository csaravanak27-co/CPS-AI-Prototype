"""Build deterministic C.P.S. distribution archives.

The extension archive has the extension files at its root, as required by
Chrome and Edge.  The application archive contains source and documentation,
but never local databases, backups, secrets, caches, build products, or the
``dist`` directory itself.
"""
from __future__ import annotations

import os
import sys
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


def build_extension_archive(destination: Path | None = None) -> Path:
    destination = destination or DIST / f"cps-extension-v{VERSION}.zip"
    extension_root = ROOT / "extension"
    files = [
        (path, path.relative_to(extension_root).as_posix())
        for path in _iter_files(extension_root, extension_only=True)
    ]
    _write_zip(destination, files)
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
