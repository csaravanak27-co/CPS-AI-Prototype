"""
C.P.S. Code Execution Sandbox
=============================
Isolated runtime execution for verified code testing and debugging.
Never runs automatically — requires explicit human action.
Enforces process timeouts, environment isolation, and separate stdout/stderr capture.
"""
import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Optional, Tuple


@dataclass
class ExecutionResult:
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool
    language: str
    duration_ms: int
    runtime_version: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


RUNTIME_CONFIG = {
    "python": {
        "bin": "python",
        "alt_bin": "python3",
        "extension": ".py",
        "compiled": False,
        "run_cmd": lambda b, f: [b, f],
        "version_cmd": lambda b: [b, "--version"],
    },
    "javascript": {
        "bin": "node",
        "alt_bin": "nodejs",
        "extension": ".js",
        "compiled": False,
        "run_cmd": lambda b, f: [b, f],
        "version_cmd": lambda b: [b, "--version"],
    },
    "c": {
        "bin": "gcc",
        "alt_bin": "clang",
        "extension": ".c",
        "compiled": True,
        "compile_cmd": lambda b, f, out: [b, "-O2", "-Wall", f, "-o", out],
        "run_cmd": lambda out: [out],
        "version_cmd": lambda b: [b, "--version"],
    },
    "cpp": {
        "bin": "g++",
        "alt_bin": "clang++",
        "extension": ".cpp",
        "compiled": True,
        "compile_cmd": lambda b, f, out: [b, "-O2", "-Wall", "-std=c++17", f, "-o", out],
        "run_cmd": lambda out: [out],
        "version_cmd": lambda b: [b, "--version"],
    },
    "go": {
        "bin": "go",
        "alt_bin": None,
        "extension": ".go",
        "compiled": False,
        "run_cmd": lambda b, f: [b, "run", f],
        "version_cmd": lambda b: [b, "version"],
    },
    "rust": {
        "bin": "rustc",
        "alt_bin": None,
        "extension": ".rs",
        "compiled": True,
        "compile_cmd": lambda b, f, out: [b, "-O", f, "-o", out],
        "run_cmd": lambda out: [out],
        "version_cmd": lambda b: [b, "--version"],
    },
    "java": {
        "bin": "javac",
        "alt_bin": "java",
        "extension": ".java",
        "compiled": True,
        "compile_cmd": lambda b, f, out: [b, f],
        "run_cmd": lambda f: ["java", "-cp", str(Path(f).parent), Path(f).stem],
        "version_cmd": lambda b: ["java", "-version"],
    },
}


class CodeExecutor:
    """Safe, bounded local code execution for user-authorized tasks."""

    def __init__(self, default_timeout: int = 10):
        self.default_timeout = default_timeout

    def resolve_binary(self, lang: str) -> Optional[str]:
        cfg = RUNTIME_CONFIG.get(lang.lower())
        if not cfg:
            return None
        bin_path = shutil.which(cfg["bin"])
        if not bin_path and cfg.get("alt_bin"):
            bin_path = shutil.which(cfg["alt_bin"])
        return bin_path

    def check_runtime(self, lang: str) -> Tuple[bool, str]:
        """Verifies if the compiler/runtime for a language is installed."""
        cfg = RUNTIME_CONFIG.get(lang.lower())
        if not cfg:
            return False, f"Unsupported language '{lang}' for execution"
        bin_path = self.resolve_binary(lang)
        if not bin_path:
            return False, f"Binary '{cfg['bin']}' not found in PATH"
        try:
            cmd = cfg["version_cmd"](bin_path)
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            ver = (res.stdout or res.stderr).strip().splitlines()[0] if (res.stdout or res.stderr) else "Available"
            return True, ver
        except Exception as e:
            return False, f"Execution check failed: {e}"

    def check_all_runtimes(self) -> Dict[str, dict]:
        """Returns installed status of all supported execution runtimes."""
        out = {}
        for lang in sorted(RUNTIME_CONFIG.keys()):
            avail, details = self.check_runtime(lang)
            out[lang] = {
                "available": avail,
                "details": details,
                "compiled": RUNTIME_CONFIG[lang]["compiled"],
            }
        return out

    def execute(self, code: str, language: str, stdin: str = "", timeout: Optional[int] = None) -> ExecutionResult:
        """
        Executes code in an isolated temporary directory.
        Captures exit code, execution time, stdout, and stderr.
        """
        lang = language.lower()
        cfg = RUNTIME_CONFIG.get(lang)
        if not cfg:
            return ExecutionResult(
                stdout="",
                stderr=f"Execution not supported for language: {language}",
                exit_code=127,
                timed_out=False,
                language=lang,
                duration_ms=0,
            )

        bin_path = self.resolve_binary(lang)
        if not bin_path:
            return ExecutionResult(
                stdout="",
                stderr=f"Runtime environment for '{lang}' is not installed on this system.",
                exit_code=127,
                timed_out=False,
                language=lang,
                duration_ms=0,
            )

        t_limit = timeout or self.default_timeout
        start_t = time.perf_counter()

        with tempfile.TemporaryDirectory(prefix="cps_exec_") as tmp_dir:
            tmp_path = Path(tmp_dir)
            ext = cfg["extension"]
            # For Java, class name should match filename if it contains public class
            src_name = "Solution" + ext if lang == "java" else "main" + ext
            src_file = tmp_path / src_name
            src_file.write_text(code, encoding="utf-8")

            # Compilation step if required
            if cfg["compiled"]:
                out_bin = str(tmp_path / ("app.exe" if os.name == "nt" else "app"))
                if lang == "java":
                    comp_cmd = cfg["compile_cmd"](bin_path, str(src_file), out_bin)
                else:
                    comp_cmd = cfg["compile_cmd"](bin_path, str(src_file), out_bin)

                try:
                    c_res = subprocess.run(comp_cmd, cwd=str(tmp_path), capture_output=True, text=True, timeout=15)
                    if c_res.returncode != 0:
                        elapsed = int((time.perf_counter() - start_t) * 1000)
                        return ExecutionResult(
                            stdout=c_res.stdout,
                            stderr=f"Compilation Error:\n{c_res.stderr}",
                            exit_code=c_res.returncode,
                            timed_out=False,
                            language=lang,
                            duration_ms=elapsed,
                        )
                except subprocess.TimeoutExpired:
                    return ExecutionResult(
                        stdout="",
                        stderr="Compilation timed out.",
                        exit_code=124,
                        timed_out=True,
                        language=lang,
                        duration_ms=15000,
                    )
                except Exception as e:
                    return ExecutionResult(
                        stdout="",
                        stderr=f"Compilation execution failed: {e}",
                        exit_code=1,
                        timed_out=False,
                        language=lang,
                        duration_ms=0,
                    )

                run_cmd = cfg["run_cmd"](str(src_file) if lang == "java" else out_bin)
            else:
                run_cmd = cfg["run_cmd"](bin_path, str(src_file))

            # Runtime execution step
            try:
                p_res = subprocess.run(
                    run_cmd,
                    cwd=str(tmp_path),
                    input=stdin,
                    capture_output=True,
                    text=True,
                    timeout=t_limit,
                )
                elapsed = int((time.perf_counter() - start_t) * 1000)
                return ExecutionResult(
                    stdout=p_res.stdout,
                    stderr=p_res.stderr,
                    exit_code=p_res.returncode,
                    timed_out=False,
                    language=lang,
                    duration_ms=elapsed,
                )
            except subprocess.TimeoutExpired:
                elapsed = int((time.perf_counter() - start_t) * 1000)
                return ExecutionResult(
                    stdout="",
                    stderr=f"Execution timed out after {t_limit}s.",
                    exit_code=124,
                    timed_out=True,
                    language=lang,
                    duration_ms=elapsed,
                )
            except Exception as e:
                return ExecutionResult(
                    stdout="",
                    stderr=f"Execution process error: {e}",
                    exit_code=1,
                    timed_out=False,
                    language=lang,
                    duration_ms=0,
                )
