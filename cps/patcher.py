import difflib
import hashlib
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

MAX_PATCH_BYTES = 500_000
BACKUP_DIR = ".cps_backup"
MANIFEST_FILE = "manifest.json"

def safe_rel(path: str) -> str:
    """Validates and normalizes relative path, preventing traversal and symlink escapes."""
    if not path or not isinstance(path, str):
        raise ValueError(f"invalid path: {path!r}")
    p = path.replace("\\", "/").strip()
    parts = p.split("/")
    if not p or p.startswith("/") or "\x00" in p:
        raise ValueError(f"unsafe path: {path!r}")
    if ".." in parts or any(part == ".." for part in parts):
        raise ValueError(f"path traversal detected: {path!r}")
    if ":" in parts[0]:
        raise ValueError(f"drive letter or stream detected: {path!r}")
    return p

def _inside(root: Path | str, rel: str) -> Path:
    """Ensures target path stays strictly inside root directory and is not a symlink escaping root."""
    root_path = Path(root).resolve()
    rel_clean = safe_rel(rel)
    target = (root_path / rel_clean).resolve()
    if root_path != target and root_path not in target.parents:
        raise ValueError(f"path escapes workspace: {rel!r}")
    # Prevent symlink escapes
    if (root_path / rel_clean).is_symlink():
        target_dest = (root_path / rel_clean).resolve()
        if root_path != target_dest and root_path not in target_dest.parents:
            raise ValueError(f"symlink escapes workspace: {rel!r}")
    return target

def detect_line_ending(text: str) -> str:
    """Detects primary line ending used in text."""
    if "\r\n" in text:
        return "\r\n"
    return "\n"

def compute_hash(text: str) -> str:
    """Returns SHA-256 hex digest of the string encoded in UTF-8."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def align_indentation(orig_line: str, replacement: str) -> str:
    """Aligns indentation of replacement lines to match the target line being replaced."""
    orig_indent = orig_line[:len(orig_line) - len(orig_line.lstrip())]
    rep_lines = replacement.splitlines(keepends=True)
    non_empty = [l for l in rep_lines if l.strip()]
    if not non_empty:
        return replacement
    first_indent = non_empty[0][:len(non_empty[0]) - len(non_empty[0].lstrip())]
    if first_indent == orig_indent:
        return replacement

    aligned = []
    for line in rep_lines:
        if line.strip():
            if line.startswith(first_indent):
                aligned.append(orig_indent + line[len(first_indent):])
            else:
                aligned.append(orig_indent + line.lstrip())
        else:
            aligned.append(line)
    return "".join(aligned)

def build_patched(src: str, start: int, end: int, replacement: str, expected_sha256: str = None) -> str:
    """
    Replaces lines from `start` to `end` (1-indexed inclusive) with `replacement`.
    Optionally validates that `src` matches `expected_sha256` to prevent stale patches.
    """
    if expected_sha256:
        actual_hash = compute_hash(src)
        if actual_hash != expected_sha256:
            raise ValueError("source file has been modified since patch generation (hash mismatch)")

    if "\x00" in replacement or len(replacement.encode("utf-8")) > MAX_PATCH_BYTES:
        raise ValueError("replacement rejected (binary or oversized)")

    le = detect_line_ending(src)
    lines = src.splitlines(keepends=True)
    total_lines = len(lines)

    if total_lines == 0 and start == 1 and end == 1:
        # Empty file patching
        rep = replacement if replacement.endswith("\n") else replacement + le
        return rep

    if not (1 <= start <= end <= max(1, total_lines)):
        raise ValueError(f"invalid line range: {start}-{end} (file has {total_lines} lines)")

    target_line = lines[start - 1]
    if not target_line.startswith((" ", "\t")) and replacement.startswith((" ", "\t")):
        replacement = align_indentation(target_line, replacement)

    # Ensure replacement ends with matching line ending if not empty
    if replacement and not replacement.endswith(("\n", "\r")):
        replacement += le

    # Reconstruct source with preserved line endings
    patched = "".join(lines[:start - 1]) + replacement + "".join(lines[end:])
    return patched

def unified_diff(old: str, new: str, path: str) -> str:
    """Generates standard unified diff format."""
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    diff = difflib.unified_diff(
        old_lines, new_lines,
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
        lineterm="\n"
    )
    return "".join(diff)


def _atomic_write_text(path: Path, text: str) -> None:
    """Write text beside *path* and atomically replace it.

    ``newline=''`` is intentional: Python's default newline translation on
    Windows would silently turn LF patches into CRLF files and invalidate the
    preview hash.  The temporary file lives in the destination directory so
    ``os.replace`` remains atomic on every supported platform.
    """
    fd, temp_path = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.cps-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


def _read_text_preserve(path: Path) -> str:
    """Read source without platform newline conversion."""
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        return handle.read()

def create_workcopy(files: dict, dest: Path | str) -> Path:
    """Copies file blobs into an isolated working copy directory."""
    dest_path = Path(dest).resolve()
    for rel, data in files.items():
        target = _inside(dest_path, rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, str):
            _atomic_write_text(target, data)
        else:
            target.write_bytes(data)
    return dest_path

def apply_patch(workdir: Path | str, rel: str, new_source: str, approved: bool = False, original_sha256: str = None) -> dict:
    """
    Safely applies patch to a file in working directory with backup preservation and hash verification.
    Requires explicit human approval (approved=True).
    Never overwrites the pristine backup with a newer patched version.
    """
    if not approved:
        raise PermissionError("explicit human approval required before applying patch")

    target = _inside(workdir, rel)
    if not target.exists():
        raise FileNotFoundError(f"target file does not exist: {rel}")

    current_source = _read_text_preserve(target)
    current_hash = compute_hash(current_source)

    if original_sha256 and current_hash != original_sha256:
        raise ValueError("target file was modified after patch preview was created; apply cancelled")

    # Prepare backup directory
    backup_base = Path(workdir).resolve() / BACKUP_DIR
    backup_file = backup_base / safe_rel(rel)

    # CRITICAL: Preserve the pristine original backup; do NOT overwrite earlier backup with a newer version
    if not backup_file.exists():
        backup_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(target, backup_file)

        # Update backup manifest
        manifest_path = backup_base / MANIFEST_FILE
        manifest = {}
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception:
                manifest = {}
        manifest[rel] = {
            "backup_path": str(backup_file.relative_to(backup_base)),
            "original_sha256": current_hash,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        _atomic_write_text(manifest_path, json.dumps(manifest, indent=2) + "\n")

    # Write patched source atomically using a same-directory temp file.
    _atomic_write_text(target, new_source)

    new_hash = compute_hash(new_source)

    return {
        "file": rel,
        "before_sha256": current_hash,
        "sha256": new_hash,
        "applied_at": datetime.now(timezone.utc).isoformat()
    }

def rollback(workdir: Path | str, rel: str) -> bool:
    """Restores the pristine original file from backup and verifies restoration."""
    target = _inside(workdir, rel)
    backup_base = Path(workdir).resolve() / BACKUP_DIR
    backup_file = backup_base / safe_rel(rel)

    if not backup_file.exists():
        raise FileNotFoundError(f"no backup found for file: {rel}")

    # Rollback is a write too; use the same atomic replacement guarantees as
    # forward patching so a crash cannot leave a truncated source file.
    _atomic_write_text(target, _read_text_preserve(backup_file))
    return True
