"""Deterministic AST + pattern rules. Rules marked heuristic may be false positives."""
import ast
import re
from dataclasses import dataclass, asdict
from .security import redact, KEY_PAT

SECRET_NAME = re.compile(r"(?i)(pass(word|wd)?|secret|api_?key|token|credential|auth|privkey)")
AUTH_CHECK_NAME = re.compile(r"(?i)(auth|admin|role|permission|allow|user|pass|token)")

RULES = {
    "VQ001": ("SQL injection (string-built query)", "High", "Medium", "Injection",
              "A query built by concatenation/formatting reaches execute(); attacker input can change its meaning.",
              "Use parameterized queries: cursor.execute(sql, (value,)).", True),
    "VQ002": ("Command injection / shell execution", "High", "High", "Injection",
              "Shell execution (os.system, os.popen, shell=True) can run attacker-controlled commands.",
              "Use subprocess.run([...]) with an argument list and shell=False.", False),
    "VQ003": ("Hard-coded credential", "High", "Medium", "Secrets",
              "A credential-like literal is embedded in source and leaks with the code.",
              "Load secrets from environment variables or a secret manager; rotate the exposed value.", True),
    "VQ004": ("Unsafe YAML deserialization", "High", "High", "Deserialization",
              "yaml.load without a safe loader can construct arbitrary objects.",
              "Use yaml.safe_load().", False),
    "VQ005": ("Dangerous eval()/exec()", "High", "High", "Code execution",
              "eval/exec on non-constant input executes arbitrary code.",
              "Use ast.literal_eval or an explicit parser/dispatch table.", False),
    "VQ006": ("Unsafe pickle deserialization", "High", "High", "Deserialization",
              "Unpickling untrusted data can execute arbitrary code.",
              "Use JSON or another data-only format.", False),
    "VQ007": ("Possible path traversal", "Medium", "Low", "File access",
              "open() receives a dynamically built path; '../' may escape the intended directory.",
              "Resolve the path and verify it stays inside an allowed base directory.", True),
    "VQ008": ("Insecure temporary file (mktemp)", "Medium", "High", "File access",
              "tempfile.mktemp is racy and predictable.",
              "Use tempfile.NamedTemporaryFile or mkstemp.", False),
    "VQ009": ("Weak hash algorithm (MD5/SHA-1)", "Medium", "High", "Cryptography",
              "MD5/SHA-1 are broken for security purposes.",
              "Use SHA-256 or stronger (bcrypt/argon2 for passwords).", False),
    "VQ010": ("TLS certificate verification disabled", "High", "High", "Cryptography",
              "verify=False / unverified context permits man-in-the-middle attacks.",
              "Remove verify=False; configure a CA bundle if needed.", False),
    "VQ011": ("Insecure randomness for secret-like value", "Medium", "Medium", "Cryptography",
              "The random module is not cryptographically secure.",
              "Use the secrets module.", True),
    "VQ012": ("Unsafe subprocess invocation", "Medium", "Medium", "Injection",
              "A subprocess command is built as a dynamic string.",
              "Pass a list of arguments; avoid string-built commands.", True),
    "VQ013": ("Insecure debug mode enabled", "High", "High", "Configuration",
              "Running Flask/Django with debug=True in production exposes interactive debuggers and secrets.",
              "Set debug=False or load configuration from environment variables.", False),
    "VQ014": ("Insecure network interface bind (0.0.0.0)", "Medium", "Medium", "Configuration",
              "Binding server to '0.0.0.0' exposes service to all network interfaces including public ones.",
              "Bind to '127.0.0.1' or localhost unless public network access is intended.", True),
    "VQ015": ("Insecure XML parsing (possible XXE)", "Medium", "Medium", "XML entity injection",
              "Standard xml.etree / minidom parsing untrusted XML may be vulnerable to entity expansion attacks.",
              "Use the defusedxml package to parse untrusted XML.", True),
    "VQ016": ("Assert statement used for security check", "Medium", "High", "Validation",
              "assert statements are removed when Python runs with optimization (-O flag).",
              "Use standard if-statements and raise exceptions instead of assert for security checks.", False),
}

@dataclass
class Finding:
    rule_id: str
    title: str
    severity: str
    confidence: str
    file: str
    line: int
    snippet: str
    explanation: str
    fix: str
    category: str
    status: str = "open"
    heuristic: bool = False
    source: str = "vulnquest"
    diff_status: str = "Scanned"
    is_new_in_diff: bool = False

    def to_dict(self):
        return asdict(self)

def dotted(n):
    parts = []
    while isinstance(n, ast.Attribute):
        parts.append(n.attr)
        n = n.value
    if isinstance(n, ast.Name):
        parts.append(n.id)
        return ".".join(reversed(parts))
    return ""

def dynamic(n):
    if isinstance(n, ast.JoinedStr):
        return any(isinstance(v, ast.FormattedValue) for v in n.values)
    if isinstance(n, ast.BinOp):
        return not (isinstance(n.left, ast.Constant) and isinstance(n.right, ast.Constant))
    return isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "format"

def kw(call, name):
    return next((k.value for k in call.keywords if k.arg == name), None)

def run_rules(tree, src, path):
    lines, out, seen = src.splitlines(), [], set()

    def add(rid, node):
        ln = getattr(node, "lineno", 1)
        if (rid, ln) in seen:
            return
        seen.add((rid, ln))
        t, sev, conf, cat, ex, fix, h = RULES[rid]
        snip = lines[ln - 1].strip()[:200] if ln <= len(lines) else ""
        if rid == "VQ003":
            snip = redact(snip)
        if h:
            ex += " (Heuristic - may be a false positive.)"
        out.append(Finding(rid, t, sev, conf, path, ln, snip, ex, fix, cat, heuristic=h))

    insecure_xml_aliases = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                if a.name.startswith(("xml.etree", "xml.dom", "xml.sax")):
                    insecure_xml_aliases.add(a.asname or a.name)
                    insecure_xml_aliases.add((a.asname or a.name).split(".")[-1])
        elif isinstance(n, ast.ImportFrom):
            if n.module and n.module.startswith(("xml.etree", "xml.dom", "xml.sax")):
                for a in n.names:
                    insecure_xml_aliases.add(a.asname or a.name)

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = dotted(node.func)
            base = name.split(".")[-1]
            a0 = node.args[0] if node.args else None

            # VQ001: SQL Injection
            if isinstance(node.func, ast.Attribute) and node.func.attr in ("execute", "executemany") and a0 is not None and dynamic(a0):
                add("VQ001", node)

            # VQ002: Command injection
            if name in ("os.system", "os.popen"):
                add("VQ002", node)
            sp = name.startswith("subprocess.") and base in ("run", "call", "Popen", "check_output", "check_call")
            sh = kw(node, "shell")
            if sp and isinstance(sh, ast.Constant) and sh.value is True:
                add("VQ002", node)

            # VQ012: Unsafe subprocess command formatting
            if sp and a0 is not None and dynamic(a0):
                add("VQ012", node)

            # VQ004: Unsafe YAML
            if name == "yaml.load":
                ld = kw(node, "Loader")
                if not (ld is not None and dotted(ld).split(".")[-1] in ("SafeLoader", "CSafeLoader")):
                    add("VQ004", node)

            # VQ005: Dangerous eval/exec
            if name in ("eval", "exec") and a0 is not None and not isinstance(a0, ast.Constant):
                add("VQ005", node)

            # VQ006: Unsafe pickle
            if name in ("pickle.load", "pickle.loads", "cPickle.load", "cPickle.loads", "dill.load", "dill.loads", "_pickle.loads", "shelve.open"):
                add("VQ006", node)

            # VQ007: Path traversal
            if name == "open" and a0 is not None and dynamic(a0):
                add("VQ007", node)

            # VQ008: Insecure temporary file
            if name == "tempfile.mktemp":
                add("VQ008", node)

            # VQ009: Weak hash algorithms
            if name in ("hashlib.md5", "hashlib.sha1"):
                add("VQ009", node)

            # VQ010: TLS verification disabled
            v = kw(node, "verify")
            if (isinstance(v, ast.Constant) and v.value is False) or name == "ssl._create_unverified_context":
                add("VQ010", node)

            # VQ013: Flask debug mode
            dbg = kw(node, "debug")
            if base == "run" and isinstance(dbg, ast.Constant) and dbg.value is True:
                add("VQ013", node)

            # VQ014: 0.0.0.0 binding
            host = kw(node, "host")
            if isinstance(host, ast.Constant) and host.value == "0.0.0.0":
                add("VQ014", node)
            if base == "bind" and node.args and isinstance(node.args[0], ast.Tuple):
                tup = node.args[0].elts
                if tup and isinstance(tup[0], ast.Constant) and tup[0].value == "0.0.0.0":
                    add("VQ014", node)

            # VQ015: Insecure XML
            if base in ("parse", "fromstring", "parseString"):
                caller = name.split(".")[0]
                if name.startswith(("xml.etree", "xml.dom", "xml.sax")) or caller in insecure_xml_aliases:
                    add("VQ015", node)

        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            val = node.value
            for t in targets:
                tn = t.id if isinstance(t, ast.Name) else getattr(t, "attr", "")
                if not tn:
                    continue

                # VQ013: Django DEBUG = True
                if tn == "DEBUG" and isinstance(val, ast.Constant) and val.value is True:
                    add("VQ013", node)

                if SECRET_NAME.search(tn) and val is not None:
                    # VQ003: Hardcoded credentials
                    if isinstance(val, ast.Constant) and isinstance(val.value, str) and len(val.value) >= 6:
                        add("VQ003", node)
                    # VQ011: Insecure randomness
                    if isinstance(val, ast.Call) and dotted(val.func).startswith("random."):
                        add("VQ011", node)

        elif isinstance(node, ast.Assert):
            # VQ016: Assert used for security validation
            test_repr = ast.unparse(node.test) if hasattr(ast, "unparse") else ""
            if AUTH_CHECK_NAME.search(test_repr):
                add("VQ016", node)

    # Regex scan for high-entropy tokens and private keys
    for i, l in enumerate(lines, 1):
        if KEY_PAT.search(l):
            n = ast.Pass()
            n.lineno = i
            add("VQ003", n)

    return sorted(out, key=lambda f: (f.line, f.rule_id))
