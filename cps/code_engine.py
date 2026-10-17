"""
C.P.S. Code Generation & Analysis Engine
========================================
Centralized multi-language code generation, explanation, debugging, optimization,
test generation, complexity analysis, and security review.
Supports 28+ programming languages with capability registries and language profiles.
"""
import json
import re
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
from .ai_provider import BaseProvider, MockProvider, AIError

LANGUAGE_PROFILES = {
    "python": {
        "name": "Python",
        "extension": ".py",
        "comment": "#",
        "block_comment": ('"""', '"""'),
        "entry": 'if __name__ == "__main__":',
        "typing": True,
        "compiled": False,
        "paradigm": "Multi-paradigm (OOP, Functional, Imperative)",
        "standard_version": "3.11+",
    },
    "javascript": {
        "name": "JavaScript",
        "extension": ".js",
        "comment": "//",
        "block_comment": ("/*", "*/"),
        "entry": 'function main() { ... } main();',
        "typing": False,
        "compiled": False,
        "paradigm": "Multi-paradigm (Event-driven, Functional, Prototype-based)",
        "standard_version": "ES2023 / Node 20+",
    },
    "typescript": {
        "name": "TypeScript",
        "extension": ".ts",
        "comment": "//",
        "block_comment": ("/*", "*/"),
        "entry": 'function main(): void { ... } main();',
        "typing": True,
        "compiled": True,
        "paradigm": "Typed Superscript of JavaScript",
        "standard_version": "5.0+",
    },
    "java": {
        "name": "Java",
        "extension": ".java",
        "comment": "//",
        "block_comment": ("/*", "*/"),
        "entry": "public static void main(String[] args)",
        "typing": True,
        "compiled": True,
        "paradigm": "Class-based Object-Oriented",
        "standard_version": "Java 17 / 21 LTS",
    },
    "c": {
        "name": "C",
        "extension": ".c",
        "comment": "//",
        "block_comment": ("/*", "*/"),
        "entry": "int main(int argc, char *argv[])",
        "typing": True,
        "compiled": True,
        "paradigm": "Imperative, Procedural",
        "standard_version": "C11 / C17",
    },
    "cpp": {
        "name": "C++",
        "extension": ".cpp",
        "comment": "//",
        "block_comment": ("/*", "*/"),
        "entry": "int main(int argc, char* argv[])",
        "typing": True,
        "compiled": True,
        "paradigm": "Multi-paradigm (OOP, Generic, Procedural)",
        "standard_version": "C++17 / C++20",
    },
    "csharp": {
        "name": "C#",
        "extension": ".cs",
        "comment": "//",
        "block_comment": ("/*", "*/"),
        "entry": "static void Main(string[] args)",
        "typing": True,
        "compiled": True,
        "paradigm": "Object-Oriented, Component-Oriented",
        "standard_version": ".NET 8.0 / C# 12",
    },
    "go": {
        "name": "Go",
        "extension": ".go",
        "comment": "//",
        "block_comment": ("/*", "*/"),
        "entry": "func main()",
        "typing": True,
        "compiled": True,
        "paradigm": "Concurrent, Imperative",
        "standard_version": "Go 1.22+",
    },
    "rust": {
        "name": "Rust",
        "extension": ".rs",
        "comment": "//",
        "block_comment": ("/*", "*/"),
        "entry": "fn main()",
        "typing": True,
        "compiled": True,
        "paradigm": "Multi-paradigm (Functional, Concurrent, Systems)",
        "standard_version": "Rust 2021 Edition",
    },
    "php": {
        "name": "PHP",
        "extension": ".php",
        "comment": "//",
        "block_comment": ("/*", "*/"),
        "entry": "<?php",
        "typing": True,
        "compiled": False,
        "paradigm": "Server-side scripting",
        "standard_version": "PHP 8.2+",
    },
    "ruby": {
        "name": "Ruby",
        "extension": ".rb",
        "comment": "#",
        "block_comment": ("=begin", "=end"),
        "entry": 'if __FILE__ == $0',
        "typing": False,
        "compiled": False,
        "paradigm": "Pure Object-Oriented",
        "standard_version": "Ruby 3.2+",
    },
    "kotlin": {
        "name": "Kotlin",
        "extension": ".kt",
        "comment": "//",
        "block_comment": ("/*", "*/"),
        "entry": "fun main(args: Array<String>)",
        "typing": True,
        "compiled": True,
        "paradigm": "Concise Multi-platform OOP / Functional",
        "standard_version": "Kotlin 1.9+",
    },
    "swift": {
        "name": "Swift",
        "extension": ".swift",
        "comment": "//",
        "block_comment": ("/*", "*/"),
        "entry": "@main or top-level code",
        "typing": True,
        "compiled": True,
        "paradigm": "Protocol-oriented, Functional, OOP",
        "standard_version": "Swift 5.9+",
    },
    "dart": {
        "name": "Dart",
        "extension": ".dart",
        "comment": "//",
        "block_comment": ("/*", "*/"),
        "entry": "void main()",
        "typing": True,
        "compiled": True,
        "paradigm": "Client-optimized OOP",
        "standard_version": "Dart 3.0+",
    },
    "r": {
        "name": "R",
        "extension": ".r",
        "comment": "#",
        "block_comment": None,
        "entry": "top-level script execution",
        "typing": False,
        "compiled": False,
        "paradigm": "Statistical computing, Functional",
        "standard_version": "R 4.3+",
    },
    "sql": {
        "name": "SQL",
        "extension": ".sql",
        "comment": "--",
        "block_comment": ("/*", "*/"),
        "entry": "SELECT, INSERT, UPDATE, DDL scripts",
        "typing": True,
        "compiled": False,
        "paradigm": "Declarative Relational",
        "standard_version": "ANSI SQL:2016",
    },
    "bash": {
        "name": "Bash",
        "extension": ".sh",
        "comment": "#",
        "block_comment": (": '", "'"),
        "entry": "#!/usr/bin/env bash",
        "typing": False,
        "compiled": False,
        "paradigm": "Command interpreter, Shell scripting",
        "standard_version": "Bash 5+",
    },
    "powershell": {
        "name": "PowerShell",
        "extension": ".ps1",
        "comment": "#",
        "block_comment": ("<#", "#>"),
        "entry": "Param(...) execution block",
        "typing": True,
        "compiled": False,
        "paradigm": "Object-based Command Shell",
        "standard_version": "PowerShell 7+",
    },
    "html": {
        "name": "HTML5",
        "extension": ".html",
        "comment": "<!--",
        "block_comment": ("<!--", "-->"),
        "entry": "<!DOCTYPE html>",
        "typing": False,
        "compiled": False,
        "paradigm": "Hypertext Markup",
        "standard_version": "HTML5",
    },
    "css": {
        "name": "CSS3",
        "extension": ".css",
        "comment": "/*",
        "block_comment": ("/*", "*/"),
        "entry": ":root { ... }",
        "typing": False,
        "compiled": False,
        "paradigm": "Cascading Style Sheets",
        "standard_version": "CSS3 / Modern CSS",
    },
    "scala": {
        "name": "Scala",
        "extension": ".scala",
        "comment": "//",
        "block_comment": ("/*", "*/"),
        "entry": "@main def run()",
        "typing": True,
        "compiled": True,
        "paradigm": "Functional meets Object-Oriented",
        "standard_version": "Scala 3.3+",
    },
    "perl": {
        "name": "Perl",
        "extension": ".pl",
        "comment": "#",
        "block_comment": ("=pod", "=cut"),
        "entry": "#!/usr/bin/env perl",
        "typing": False,
        "compiled": False,
        "paradigm": "Text-processing, Imperative",
        "standard_version": "Perl 5.38+",
    },
    "lua": {
        "name": "Lua",
        "extension": ".lua",
        "comment": "--",
        "block_comment": ("--[[", "]]"),
        "entry": "top-level script execution",
        "typing": False,
        "compiled": False,
        "paradigm": "Lightweight, Embedded Multi-paradigm",
        "standard_version": "Lua 5.4+",
    },
    "julia": {
        "name": "Julia",
        "extension": ".jl",
        "comment": "#",
        "block_comment": ("#=", "=#"),
        "entry": "function main() ... end",
        "typing": True,
        "compiled": True,
        "paradigm": "High-performance Scientific Computing",
        "standard_version": "Julia 1.10+",
    },
    "matlab": {
        "name": "MATLAB",
        "extension": ".m",
        "comment": "%",
        "block_comment": ("%{", "%}"),
        "entry": "function main()",
        "typing": False,
        "compiled": False,
        "paradigm": "Matrix Laboratory, Numerical",
        "standard_version": "R2023b+",
    },
    "haskell": {
        "name": "Haskell",
        "extension": ".hs",
        "comment": "--",
        "block_comment": ("{-", "-}"),
        "entry": "main :: IO ()",
        "typing": True,
        "compiled": True,
        "paradigm": "Purely Functional, Lazy evaluation",
        "standard_version": "GHC 9.6+",
    },
    "solidity": {
        "name": "Solidity",
        "extension": ".sol",
        "comment": "//",
        "block_comment": ("/*", "*/"),
        "entry": "contract ...",
        "typing": True,
        "compiled": True,
        "paradigm": "Contract-oriented Smart Contracts",
        "standard_version": "^0.8.20",
    },
}

CODE_SYSTEM_PROMPT = (
    "You are C.P.S. (Code Processing System), an elite AI coding companion, software architect, "
    "and algorithmic problem solver. You produce complete, executable, clean, production-grade solutions. "
    "Do not provide incomplete placeholders or omissions. "
    "Always structure your output with exact code, clear step-by-step logic, complexity breakdown, and edge test cases."
)


@dataclass
class CodeRequest:
    action: str = "generate"  # generate, explain, debug, optimize, convert, tests, complexity, security, summarize
    source_code: str = ""
    language: str = "python"
    target_language: str = ""
    problem_statement: str = ""
    error_message: str = ""
    constraints: str = ""
    context: str = ""
    additional_instructions: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CodeResponse:
    code: str = ""
    explanation: str = ""
    language: str = "python"
    complexity_analysis: str = ""
    test_cases: List[str] = field(default_factory=list)
    alternatives: List[str] = field(default_factory=list)
    assumptions: str = ""
    model_used: str = ""
    warnings: List[str] = field(default_factory=list)
    raw_response: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def get_supported_languages() -> List[Dict[str, Any]]:
    """Returns registry of supported programming languages and their capabilities."""
    out = []
    for lang_id, prof in sorted(LANGUAGE_PROFILES.items()):
        out.append({
            "id": lang_id,
            "name": prof["name"],
            "extension": prof["extension"],
            "typing": prof["typing"],
            "compiled": prof["compiled"],
            "standard": prof["standard_version"],
            "paradigm": prof["paradigm"]
        })
    return out


def parse_code_response(text: str, default_language: str = "python") -> CodeResponse:
    """Robust parser for LLM responses, extracting code blocks, JSON, and explanations."""
    if not text or not text.strip():
        return CodeResponse(explanation="Empty response from AI provider.", language=default_language)

    cleaned = text.strip()

    # 1. Try parsing JSON structure if the model produced structured output
    if (cleaned.startswith("{") and cleaned.endswith("}")) or re.search(r"^\s*\{[\s\S]*\}\s*$", cleaned):
        try:
            m = re.search(r"(\{[\s\S]*\})", cleaned)
            data = json.loads(m.group(1)) if m else json.loads(cleaned)
            if isinstance(data, dict):
                return CodeResponse(
                    code=str(data.get("code") or data.get("solution") or data.get("replacement") or ""),
                    explanation=str(data.get("explanation") or data.get("summary") or ""),
                    language=str(data.get("language") or default_language),
                    complexity_analysis=str(data.get("complexity") or data.get("complexity_analysis") or ""),
                    test_cases=[str(t) for t in data.get("test_cases", []) if t],
                    alternatives=[str(a) for a in data.get("alternatives", []) if a],
                    assumptions=str(data.get("assumptions") or ""),
                    warnings=[str(w) for w in data.get("warnings", []) if w],
                    raw_response=text,
                )
        except Exception:
            pass

    # 2. Extract code blocks from Markdown
    code_pattern = re.compile(r"```([a-zA-Z0-9_\+#\.\-]*)\n([\s\S]*?)```")
    blocks = code_pattern.findall(cleaned)

    extracted_code = ""
    lang = default_language
    if blocks:
        # Use the longest or first significant code block
        longest_block = max(blocks, key=lambda b: len(b[1]))
        if longest_block[0]:
            lang_cand = longest_block[0].strip().lower()
            if lang_cand in LANGUAGE_PROFILES:
                lang = lang_cand
            elif lang_cand == "py":
                lang = "python"
            elif lang_cand == "js":
                lang = "javascript"
            elif lang_cand == "ts":
                lang = "typescript"
        extracted_code = longest_block[1].strip()

    # Extract complexity section if present
    complexity = ""
    c_match = re.search(r"(?:Complexity|Time & Space Complexity|Complexity Analysis)[:\s]+([\s\S]*?)(?=\n##|\n\*\*|\Z)", cleaned, re.IGNORECASE)
    if c_match:
        complexity = c_match.group(1).strip()

    # Strip code blocks from explanation text
    explanation_text = code_pattern.sub("[Code block provided above]", cleaned).strip()

    return CodeResponse(
        code=extracted_code,
        explanation=explanation_text,
        language=lang,
        complexity_analysis=complexity,
        raw_response=text,
    )


class CodeEngine:
    """Centralized code generation, explanation, debugging and translation engine."""

    def __init__(self, provider: Optional[BaseProvider] = None):
        self.provider = provider or MockProvider()

    def _query(self, prompt: str, system_override: Optional[str] = None) -> str:
        """Invokes provider backend safely. Real providers are invoked and errors raised on failure."""
        sys_p = system_override or CODE_SYSTEM_PROMPT
        prov = self.provider

        if isinstance(prov, MockProvider):
            return self._mock_dispatch(prompt)

        # Call unified chat method on active provider
        if hasattr(prov, "chat"):
            try:
                return prov.chat(prompt, json_mode=False, system_prompt=sys_p)
            except Exception as e:
                raise AIError(f"{prov.name} inference failed: {e}")

        # Fallback to _chat if custom provider only implements _chat
        if hasattr(prov, "_chat"):
            try:
                messages = [
                    {"role": "system", "content": sys_p},
                    {"role": "user", "content": prompt}
                ]
                return prov._chat(messages)
            except Exception as e:
                raise AIError(f"{prov.name} inference failed: {e}")

        raise AIError(f"Provider '{prov.name}' does not implement chat() or _chat()")

    def _mock_dispatch(self, prompt: str) -> str:
        """Deterministic, rich responses for tests, offline mode, and demos."""
        p_lower = prompt.lower()
        if "generate" in p_lower or "solve" in p_lower:
            return (
                "```python\n"
                "def solve(nums: list[int], target: int) -> list[int]:\n"
                "    \"\"\"\n"
                "    Optimal Two-Sum using a single-pass hash map.\n"
                "    Time Complexity: O(n), Space Complexity: O(n)\n"
                "    \"\"\"\n"
                "    seen = {}\n"
                "    for idx, num in enumerate(nums):\n"
                "        complement = target - num\n"
                "        if complement in seen:\n"
                "            return [seen[complement], idx]\n"
                "        seen[num] = idx\n"
                "    return []\n\n"
                "if __name__ == '__main__':\n"
                "    print(solve([2, 7, 11, 15], 9))  # Output: [0, 1]\n"
                "```\n\n"
                "### Algorithm & Complexity Explanation\n"
                "1. We maintain a hash table of traversed elements.\n"
                "2. For each element `num`, we look up `target - num` in O(1) expected time.\n"
                "3. **Time Complexity:** O(n) where n is the number of elements.\n"
                "4. **Space Complexity:** O(n) for the dictionary."
            )
        elif "debug" in p_lower or "fix" in p_lower:
            return (
                "```python\n"
                "def binary_search(arr: list[int], target: int) -> int:\n"
                "    low, high = 0, len(arr) - 1\n"
                "    while low <= high:\n"
                "        mid = low + (high - low) // 2  # Prevents integer overflow\n"
                "        if arr[mid] == target:\n"
                "            return mid\n"
                "        elif arr[mid] < target:\n"
                "            low = mid + 1\n"
                "        else:\n"
                "            high = mid - 1\n"
                "    return -1\n"
                "```\n\n"
                "### Root Cause & Bug Fix\n"
                "- **Original Issue:** Integer boundary off-by-one error and missing loop exit condition.\n"
                "- **Solution:** Used `low <= high` and standard mid recalculation `low + (high - low) // 2`."
            )
        elif "explain" in p_lower or "complexity" in p_lower:
            return (
                "### Code Explanation & Algorithmic Analysis\n"
                "The selected snippet implements an efficient divide-and-conquer strategy.\n\n"
                "- **Base Case:** When subarray size <= 1, it is already sorted.\n"
                "- **Recursive Step:** Splits array into two halves, recursively sorts, and merges in O(n) time.\n\n"
                "### Complexity Breakdown\n"
                "- **Time Complexity:** O(n log n) in best, average, and worst cases.\n"
                "- **Space Complexity:** O(n) auxiliary space for merging buffers."
            )
        elif "convert" in p_lower or "translate" in p_lower:
            return (
                "```typescript\n"
                "export function quicksort(arr: number[]): number[] {\n"
                "    if (arr.length <= 1) return arr;\n"
                "    const pivot = arr[arr.length - 1];\n"
                "    const left = arr.filter((x, i) => x <= pivot && i < arr.length - 1);\n"
                "    const right = arr.filter(x => x > pivot);\n"
                "    return [...quicksort(left), pivot, ...quicksort(right)];\n"
                "}\n"
                "```\n\n"
                "Converted to strongly-typed TypeScript with ES6 array operations."
            )
        elif "test" in p_lower:
            return (
                "```python\n"
                "import unittest\n\n"
                "class TestSolution(unittest.TestCase):\n"
                "    def test_standard_case(self):\n"
                "        self.assertEqual(solve([2, 7, 11, 15], 9), [0, 1])\n\n"
                "    def test_negative_numbers(self):\n"
                "        self.assertEqual(solve([-3, 4, 3, 90], 0), [0, 2])\n\n"
                "    def test_no_solution(self):\n"
                "        self.assertEqual(solve([1, 2, 3], 7), [])\n\n"
                "if __name__ == '__main__':\n"
                "    unittest.main()\n"
                "```\n\n"
                "Comprehensive unit tests covering standard cases, negative integers, and empty matches."
            )
        elif "security" in p_lower:
            return (
                "### Security Review Findings\n"
                "- **Secret Handling:** No hardcoded tokens detected in selection.\n"
                "- **Input Validation:** Ensure user-supplied indices are bounded.\n"
                "- **Memory Safety:** Safe bounds checked."
            )
        else:
            return (
                "### C.P.S. Assistant\n"
                "Analyzed request successfully. Code is well-structured with clear semantics."
            )

    def process(self, req: CodeRequest) -> CodeResponse:
        """Central dispatch processing any CodeRequest."""
        action = (req.action or "generate").lower()
        lang = req.language or "python"

        prompt_parts = [f"Requested Action: {action.upper()}", f"Target Language: {lang}"]
        if req.target_language:
            prompt_parts.append(f"Destination Language: {req.target_language}")
        if req.problem_statement:
            prompt_parts.append(f"Problem Statement:\n{req.problem_statement}")
        if req.constraints:
            prompt_parts.append(f"Constraints:\n{req.constraints}")
        if req.source_code:
            prompt_parts.append(f"Source Code:\n```{lang}\n{req.source_code}\n```")
        if req.error_message:
            prompt_parts.append(f"Error / Diagnostics:\n{req.error_message}")
        if req.context:
            prompt_parts.append(f"Context / Contextual Notes:\n{req.context}")
        if req.additional_instructions:
            prompt_parts.append(f"Instructions:\n{req.additional_instructions}")

        full_prompt = "\n\n".join(prompt_parts)

        raw_resp = self._query(full_prompt)
        res = parse_code_response(raw_resp, default_language=lang)
        res.model_used = getattr(self.provider, "model", getattr(self.provider, "name", "C.P.S. Engine"))
        return res

    def generate(self, problem: str, language: str = "python", constraints: str = "", context: str = "") -> CodeResponse:
        req = CodeRequest(action="generate", problem_statement=problem, language=language, constraints=constraints, context=context)
        return self.process(req)

    def explain(self, code: str, language: str = "python") -> CodeResponse:
        req = CodeRequest(action="explain", source_code=code, language=language)
        return self.process(req)

    def debug(self, code: str, error: str = "", language: str = "python") -> CodeResponse:
        req = CodeRequest(action="debug", source_code=code, error_message=error, language=language)
        return self.process(req)

    def optimize(self, code: str, language: str = "python") -> CodeResponse:
        req = CodeRequest(action="optimize", source_code=code, language=language)
        return self.process(req)

    def convert(self, code: str, source_lang: str, target_lang: str) -> CodeResponse:
        req = CodeRequest(action="convert", source_code=code, language=source_lang, target_language=target_lang)
        return self.process(req)

    def generate_tests(self, code: str, language: str = "python") -> CodeResponse:
        req = CodeRequest(action="tests", source_code=code, language=language)
        return self.process(req)

    def analyze_complexity(self, code: str, language: str = "python") -> CodeResponse:
        req = CodeRequest(action="complexity", source_code=code, language=language)
        return self.process(req)

    def review_security(self, code: str, language: str = "python") -> CodeResponse:
        req = CodeRequest(action="security", source_code=code, language=language)
        return self.process(req)
