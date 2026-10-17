import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _env(cps_key: str, vulnquest_key: str, default: str = "") -> str:
    """Read env var with CPS_ prefix, falling back to VULNQUEST_ for migration."""
    return os.getenv(cps_key, os.getenv(vulnquest_key, default))


def _env_bool(cps_key: str, vulnquest_key: str, default: bool = False) -> bool:
    value = _env(cps_key, vulnquest_key, "1" if default else "0").strip().lower()
    return value in {"1", "true", "yes", "on"}


def default_data_dir() -> Path:
    """Return a writable per-user data directory for the installed desktop app.

    A relative directory is useful for source checkouts but is not safe for an
    installed application (the install directory may be read-only).  Keep an
    explicit environment override for portable/developer deployments, then use
    the platform's normal per-user data location.
    """
    configured = os.getenv("CPS_DATA_DIR") or os.getenv("VULNQUEST_DATA_DIR")
    if configured:
        return Path(configured).expanduser()

    if sys.platform == "win32":
        base = os.getenv("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")
        return Path(base) / "CPS"

    base = os.getenv("XDG_DATA_HOME")
    return (Path(base) if base else Path.home() / ".local" / "share") / "cps"


# AI Model Configuration Defaults
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"
DEFAULT_OPENROUTER_MODEL = "meta-llama/llama-3.3-70b-instruct:free"
DEFAULT_OLLAMA_MODEL = _env("CPS_GEMMA_MODEL", "VULNQUEST_GEMMA_MODEL", "gemma4:e2b-it-q4_K_M")
DEFAULT_OLLAMA_HOST = "http://localhost:11434"

MODEL = _env("CPS_MODEL", "VULNQUEST_MODEL", DEFAULT_OLLAMA_MODEL)
DEFAULT_PROVIDER = _env("CPS_PROVIDER", "VULNQUEST_PROVIDER", "ollama")
DATA_DIR = default_data_dir()
MAX_FILE_BYTES = int(_env("CPS_MAX_FILE_BYTES", "VULNQUEST_MAX_FILE_BYTES", "1000000"))

# The desktop-managed backend is opt-in.  It is always constrained to loopback
# by backend.runtime, so enabling it cannot publish the API on a LAN interface.
BACKEND_ENABLED = _env_bool("CPS_BACKEND_ENABLED", "VULNQUEST_BACKEND_ENABLED", False)
BACKEND_HOST = _env("CPS_BACKEND_HOST", "VULNQUEST_BACKEND_HOST", "127.0.0.1")
BACKEND_PORT = int(_env("CPS_PORT", "VULNQUEST_PORT", "8899"))


def groq_api_key() -> str:
    return os.getenv("GROQ_API_KEY", "").strip()


def gemini_api_key() -> str:
    return os.getenv("GEMINI_API_KEY", "").strip()


def openrouter_api_key() -> str:
    return os.getenv("OPENROUTER_API_KEY", "").strip()


def ollama_host() -> str:
    return os.getenv("OLLAMA_HOST", DEFAULT_OLLAMA_HOST).strip().rstrip("/")


def api_key() -> str:
    """Legacy alias for default Groq provider key."""
    return groq_api_key()
