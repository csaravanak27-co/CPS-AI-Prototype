import ast
import os
import re
from pathlib import Path
from .rules import Finding, run_rules
from .config import MAX_FILE_BYTES

SKIP_DIRS = {
    ".git", ".venv", "venv", "env", "ENV", "node_modules",
    "__pycache__", ".pytest_cache", ".idea", ".vscode", "dist", "build", ".vulnquest_backup", ".cps_backup"
}

# Broad source-file coverage. Python gets AST rules; other languages get
# conservative, language-agnostic lexical checks until a language parser exists.
SOURCE_EXTENSIONS = {
    ".py", ".pyw", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx",
    ".java", ".kt", ".kts", ".go", ".rs", ".c", ".h", ".cc", ".cpp",
    ".hpp", ".cs", ".php", ".rb", ".swift", ".scala", ".sh", ".bash",
    ".ps1", ".psm1", ".sql", ".html", ".htm", ".vue", ".svelte",
    ".yaml", ".yml", ".json", ".xml", ".toml", ".tf",
}

def _supported_source(path: str) -> bool:
    name = Path(path).name.lower()
    return Path(name).suffix.lower() in SOURCE_EXTENSIONS or name in {
        "dockerfile", "makefile", ".env", ".env.example", ".npmrc", ".pypirc"
    }

_GENERIC_RULES = [
    ("VQ003", "Hard-coded credential", "High", "Medium", "Secrets",
     re.compile(r"(?i)\b(api[_-]?key|secret|password|passwd|token|private[_-]?key)\b\s*[:=]\s*['\"][^'\"]{6,}['\"]"),
     "Move this credential to an environment variable or secret manager and rotate it."),
    ("VQ005", "Dynamic code execution", "High", "Low", "Code execution",
     re.compile(r"(?i)\b(eval|exec)\s*\("),
     "Avoid evaluating source strings; use a constrained parser or explicit dispatch."),
    ("VQ002", "Shell execution", "High", "Low", "Injection",
     re.compile(r"(?i)(shell\s*[:=]\s*true|child_process\.(exec|execSync)\s*\(|Runtime\.getRuntime\(\)\.exec\s*\(|\bos\.system\s*\()"),
     "Avoid shell command strings. Pass arguments separately and validate untrusted input."),
    ("VQ010", "TLS certificate verification disabled", "High", "Medium", "Cryptography",
     re.compile(r"(?i)(verify\s*[:=]\s*false|rejectUnauthorized\s*[:=]\s*false|InsecureSkipVerify\s*:\s*true|CERT_NONE)"),
     "Enable certificate verification and configure a trusted CA when needed."),
    ("VQ009", "Weak hash algorithm", "Medium", "Low", "Cryptography",
     re.compile(r"(?i)(md5|sha1)\s*\("),
     "Use SHA-256 or stronger for integrity; use Argon2/bcrypt/scrypt for passwords."),
    ("VQ004", "Unsafe deserialization candidate", "High", "Low", "Deserialization",
     re.compile(r"(?i)(yaml\.load\s*\(|pickle\.loads?\s*\(|unserialize\s*\()"),
     "Use safe, data-only formats or safe loader APIs for untrusted input."),
]

def _scan_generic(text: str, path: str):
    findings = []
    for line_no, line in enumerate(text.splitlines(), 1):
        for rid, title, severity, confidence, category, pattern, fix in _GENERIC_RULES:
            if pattern.search(line):
                snippet = line.strip()[:200]
                if rid == "VQ003":
                    from .security import redact
                    snippet = redact(snippet)
                findings.append(Finding(
                    rid, title, severity, confidence, path, line_no, snippet,
                    "Cross-language lexical match; confirm the call is reachable and handles untrusted data.",
                    fix, category, heuristic=True, source="cps-generic",
                ))
    return findings

def scan_source(text: str, path: str = "<memory>"):
    """
    Static analysis only: source is parsed into an AST and never executed.
    Returns (findings, error).
    """
    if not text:
        return [], None
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError) as e:
        return [], f"syntax error: {e}"
    except Exception as e:
        return [], f"parse error: {type(e).__name__}: {e}"
    return run_rules(tree, text, path), None

def scan_files(files: dict, max_bytes: int = MAX_FILE_BYTES, use_bandit: bool = False):
    """
    Scans a dictionary of { relative_path: byte_data } safely.
    Handles invalid encodings, oversized files, and binary files gracefully.
    """
    res = {"findings": [], "scanned": 0, "skipped": [], "errors": [], "notes": [], "languages": {}}
    ok_files = {}

    for path, data in sorted(files.items()):
        ext = Path(path).suffix.lower()
        if not _supported_source(path):
            res["skipped"].append((path, "unsupported file type"))
            continue
        if len(data) > max_bytes:
            res["skipped"].append((path, f"oversized (> {max_bytes // 1000} KB)"))
            continue
        if b"\x00" in data:
            res["skipped"].append((path, "binary content detected"))
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = data.decode("latin-1")
            except Exception:
                res["skipped"].append((path, "unsupported encoding"))
                continue

        if ext in {".py", ".pyw"}:
            findings, err = scan_source(text, path)
        else:
            findings, err = _scan_generic(text, path), None
        res["scanned"] += 1
        label = ext.lstrip(".") or Path(path).name
        res["languages"][label] = res["languages"].get(label, 0) + 1
        ok_files[path] = data
        if err:
            res["errors"].append((path, err))
        res["findings"] += findings

    if use_bandit:
        try:
            from .bandit_runner import run_bandit
            bf, note = run_bandit(ok_files)
            res["findings"] += bf
            if note:
                res["notes"].append(note)
        except Exception as e:
            res["notes"].append(f"Bandit integration error: {e}")

    return res

def read_folder(folder: Path | str, max_files: int = 1000, max_bytes: int = MAX_FILE_BYTES):
    """
    Read supported source/config files from a local directory (read-only).
    Safely validates paths to prevent directory traversal escapes.
    """
    root = Path(folder).expanduser().resolve()
    if not root.is_dir():
        return {}, [(str(folder), "not a directory")]

    files, skipped = {}, []
    for dp, dn, fn in os.walk(root, followlinks=False):
        # Prune ignored directories in-place
        dn[:] = [d for d in dn if d not in SKIP_DIRS and not d.startswith(".")]

        for f in fn:
            p = Path(dp) / f
            try:
                rel = p.relative_to(root).as_posix()
            except ValueError:
                skipped.append((str(p), "path resolution error"))
                continue

            if p.is_symlink():
                skipped.append((rel, "symlink skipped"))
                continue

            if not _supported_source(f):
                continue

            if len(files) >= max_files:
                skipped.append((rel, "file count limit reached"))
                continue

            try:
                size = p.stat().st_size
                if size > max_bytes:
                    skipped.append((rel, f"oversized (> {max_bytes // 1000} KB)"))
                    continue
                files[rel] = p.read_bytes()
            except (OSError, PermissionError) as e:
                skipped.append((rel, f"unreadable: {type(e).__name__}"))

    return files, skipped
