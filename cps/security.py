import io
import os
import re
import zipfile
from pathlib import Path

# Common credential patterns in assignments (variable = "secret")
SECRET_ASSIGN = re.compile(
    r'(?i)(\b\w*(?:pass(?:word|wd)?|secret|api_?key|token|auth|credential|privkey)\w*\s*[=:]\s*)(["\'])[^"\']{3,}\2'
)

# Known high-entropy API key & token signatures
KEY_PAT = re.compile(
    r'\b(?:'
    r'gsk_[A-Za-z0-9_\-]{12,}|'                   # Groq API key
    r'sk-[A-Za-z0-9_\-]{16,}|'                    # OpenAI / generic secret key
    r'AKIA[0-9A-Z]{16}|'                          # AWS Access Key ID
    r'ghp_[A-Za-z0-9_]{36}|'                      # GitHub Personal Access Token
    r'gho_[A-Za-z0-9_]{36}|'                      # GitHub OAuth Token
    r'github_pat_[A-Za-z0-9_]{82}|'               # GitHub Fine-Grained Token
    r'xox[baprs]-[A-Za-z0-9_\-]{10,}|'            # Slack API Token
    r'AIza[0-9A-Za-z\-_]{35}|'                    # Google API Key
    r'eyJ[A-Za-z0-9_\-]{20,}\.eyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{20,}'  # JWT token
    r')\b'
)

# Private key headers
PRIVATE_KEY_PAT = re.compile(r'-----BEGIN (?:[A-Z ]+)?PRIVATE KEY-----[\s\S]*?-----END (?:[A-Z ]+)?PRIVATE KEY-----')

def redact(text: str) -> str:
    """Redacts potential passwords, tokens, API keys, and private keys from text snippets."""
    if not text:
        return ""
    text = PRIVATE_KEY_PAT.sub("-----BEGIN PRIVATE KEY-----\n***REDACTED PRIVATE KEY***\n-----END PRIVATE KEY-----", text)
    text = SECRET_ASSIGN.sub(r'\1\2***REDACTED***\2', text)
    text = KEY_PAT.sub("***REDACTED***", text)
    return text

def safe_member(name: str) -> bool:
    """Validate archive member path to prevent Zip Slip / path traversal attacks."""
    n = name.replace("\\", "/")
    parts = n.split("/")
    if not n or "\x00" in n:
        return False
    if n.startswith("/") or n.startswith("\\"):
        return False
    if ".." in parts or "." in parts and parts[0] == ".":
        return False
    if re.match(r"^[A-Za-z]:", n):
        return False
    return True

def is_safe_subpath(base: Path, target: Path) -> bool:
    """Verifies that target is strictly inside base and does not escape via symlink or relative navigation."""
    try:
        base_res = base.resolve()
        target_res = target.resolve()
        return base_res == target_res or base_res in target_res.parents
    except (ValueError, RuntimeError, OSError):
        return False

def extract_zip(data: bytes, max_files: int = 200, max_file_bytes: int = 1_000_000, max_total: int = 20_000_000):
    """Safely extracts ZIP members into memory (in-memory only, nothing is written to disk or executed)."""
    files, skipped = {}, []
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except (zipfile.BadZipFile, OSError):
        return {}, [("<zip>", "not a valid ZIP")]

    total = 0
    for info in zf.infolist():
        if info.is_dir():
            continue
        n = info.filename
        if not safe_member(n):
            skipped.append((n, "unsafe path"))
            continue
        # Check for UNIX symlink attribute
        if (info.external_attr >> 16) & 0o170000 == 0o120000:
            skipped.append((n, "symlink"))
            continue
        if len(files) >= max_files:
            skipped.append((n, "too many files"))
            continue
        if info.file_size > max_file_bytes:
            skipped.append((n, "oversized"))
            continue
        try:
            with zf.open(info) as fh:
                blob = fh.read(max_file_bytes + 1)
        except Exception as e:
            skipped.append((n, f"read error: {type(e).__name__}"))
            continue
        if len(blob) > max_file_bytes:
            skipped.append((n, "oversized"))
            continue
        total += len(blob)
        if total > max_total:
            skipped.append((n, "archive too large"))
            break
        files[n.replace("\\", "/")] = blob

    return files, skipped
