"""Run offline checks required before submitting the browser extension package."""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from package_release import build_extension_archive, validate_extension_tree, validate_store_package


ROOT = Path(__file__).resolve().parent.parent
EXTENSION = ROOT / "extension"


def check_javascript_syntax() -> None:
    """Use the local Node runtime; no network or package install is needed."""
    node = "node.exe" if __import__("os").name == "nt" else "node"
    files = sorted(EXTENSION.rglob("*.js"))
    for path in files:
        subprocess.run([node, "--check", str(path)], check=True, capture_output=True, text=True)


def main() -> int:
    validate_extension_tree(EXTENSION)
    check_javascript_syntax()
    with tempfile.TemporaryDirectory(prefix="cps-extension-check-") as temp_dir:
        package = build_extension_archive(Path(temp_dir) / "cps-extension-store.zip")
        validate_store_package(package)
    print(f"Validated {len(list(EXTENSION.rglob('*.js')))} JavaScript files and the deterministic store package.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
