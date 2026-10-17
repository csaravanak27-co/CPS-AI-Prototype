"""Create a deterministic portable Windows desktop ZIP from PyInstaller output."""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from cps import __version__  # noqa: E402

TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def _include(path: Path) -> bool:
    if path.name in {".env", "history.db", "backend_settings.json"}:
        return False
    if path.suffix.lower() in {".db", ".sqlite", ".sqlite3", ".pyc", ".pyo", ".log", ".tmp"}:
        return False
    return True


def build_desktop_archive(source: Path | None = None, destination: Path | None = None) -> Path:
    source = (source or ROOT / "dist" / "CPS").resolve()
    destination = destination or ROOT / "dist" / f"cps-desktop-v{__version__}-windows-x64.zip"
    executable = source / "CPS.exe"
    if not executable.is_file():
        raise FileNotFoundError(f"PyInstaller executable is missing: {executable}")

    files = sorted(
        (path for path in source.rglob("*") if path.is_file() and _include(path)),
        key=lambda p: p.relative_to(source).as_posix(),
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            info = zipfile.ZipInfo(path.relative_to(source).as_posix(), date_time=TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    return destination


if __name__ == "__main__":
    artifact = build_desktop_archive()
    print(f"Created {artifact} ({artifact.stat().st_size} bytes)")
