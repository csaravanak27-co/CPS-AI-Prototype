"""Write SHA-256 checksums for release artifacts."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifacts", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, default=Path("dist/SHA256SUMS.txt"))
    args = parser.parse_args()
    artifacts = [path for path in args.artifacts if path.is_file()]
    if len(artifacts) != len(args.artifacts):
        missing = [str(path) for path in args.artifacts if not path.is_file()]
        raise SystemExit(f"Missing release artifact(s): {', '.join(missing)}")
    cwd = Path.cwd().resolve()
    def display_path(path: Path) -> str:
        resolved = path.resolve()
        try:
            return resolved.relative_to(cwd).as_posix()
        except ValueError:
            return path.as_posix()

    lines = [
        f"{sha256(path)}  {display_path(path)}"
        for path in sorted(artifacts, key=lambda p: display_path(p))
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
