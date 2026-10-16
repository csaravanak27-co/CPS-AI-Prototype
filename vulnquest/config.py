import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# AI Model Configuration Defaults
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"
DEFAULT_OPENROUTER_MODEL = "meta-llama/llama-3.3-70b-instruct:free"
DEFAULT_OLLAMA_MODEL = os.getenv("VULNQUEST_GEMMA_MODEL", "gemma4:e2b-it-q4_K_M")
DEFAULT_OLLAMA_HOST = "http://localhost:11434"

MODEL = os.getenv("VULNQUEST_MODEL", DEFAULT_OLLAMA_MODEL)
DEFAULT_PROVIDER = os.getenv("VULNQUEST_PROVIDER", "ollama")
DATA_DIR = Path(os.getenv("VULNQUEST_DATA_DIR", "vulnquest_data"))
MAX_FILE_BYTES = int(os.getenv("VULNQUEST_MAX_FILE_BYTES", 1_000_000))

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
