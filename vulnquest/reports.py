import csv
import html
import io
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional
from . import __version__
from .security import redact

LIMITS = [
    "Static, AST- and regex-based analysis only; heuristic rules may produce false positives and miss complex issues.",
    "Uploaded source code is never executed on the host machine; dynamic runtime sandboxing is not performed.",
    "A finding disappearing from static analysis does not mathematically prove complete vulnerability remediation.",
    "AI interpretations and proposed fixes are advisory; human diff review and independent verification are mandatory."
]

def build_report(
    findings: List[dict],
    meta: Optional[dict] = None,
    remediations: Optional[List[dict]] = None,
    verifications: Optional[List[dict]] = None,
    redact_snippets: bool = True,
    provider_info: Optional[str] = None
) -> dict:
    """Builds a structured security audit report with full secret redaction and metadata."""
    safe_findings = []
    severity_summary = {}
    rule_summary = {}

    for f in findings:
        f_clean = dict(f)
        if redact_snippets:
            f_clean["snippet"] = redact(f_clean.get("snippet", ""))
        else:
            f_clean["snippet"] = redact(f_clean.get("snippet", ""))  # Always redact secrets

        sev = f_clean.get("severity", "Unknown")
        rid = f_clean.get("rule_id", "Unknown")
        severity_summary[sev] = severity_summary.get(sev, 0) + 1
        rule_summary[rid] = rule_summary.get(rid, 0) + 1
        safe_findings.append(f_clean)

    safe_meta = dict(meta or {})
    if provider_info:
        safe_meta["ai_provider"] = provider_info

    # Clean remediations (exclude raw file blobs)
    safe_rem = []
    for r in (remediations or []):
        r_clean = {k: v for k, v in r.items() if k not in ("original", "patched")}
        safe_rem.append(r_clean)

    return {
        "tool": "VulnQuest AI",
        "version": __version__,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_findings": len(safe_findings),
            "by_severity": severity_summary,
            "by_rule": rule_summary
        },
        "meta": safe_meta,
        "findings": safe_findings,
        "remediations": safe_rem,
        "verifications": verifications or [],
        "limitations": LIMITS
    }

def to_json(report: dict) -> str:
    """Exports audit report as formatted JSON."""
    return json.dumps(report, indent=2, default=str)

def to_csv(report: dict) -> str:
    """Exports findings as CSV with location, severity, and remediation guidance."""
    cols = ["rule_id", "title", "severity", "confidence", "category", "file", "line", "status", "fix", "snippet"]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, cols, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(report.get("findings", []))
    return buf.getvalue()

def to_markdown(report: dict) -> str:
    """Exports human-readable Markdown security audit report."""
    md = []
    md.append(f"# 🛡️ VulnQuest AI Security Audit Report")
    md.append(f"**Generated:** {report.get('generated_at')} (UTC) | **Version:** {report.get('version', __version__)}")
    if report.get("meta", {}).get("ai_provider"):
        md.append(f"**AI Engine:** {report['meta']['ai_provider']}")
    md.append("")

    # Summary
    summary = report.get("summary", {})
    md.append(f"## Executive Summary")
    md.append(f"- **Total Findings:** {summary.get('total_findings', 0)}")
    sev_str = ", ".join(f"{k}: {v}" for k, v in summary.get("by_severity", {}).items())
    md.append(f"- **Severity Breakdown:** {sev_str or 'None'}")
    md.append("")

    # Findings Table
    md.append("## Vulnerability Findings")
    if not report.get("findings"):
        md.append("No security findings reported.")
    else:
        md.append("| Rule | Severity | Location | Title | Status |")
        md.append("|---|---|---|---|---|")
        for f in report["findings"]:
            md.append(f"| `{f.get('rule_id')}` | **{f.get('severity')}** | `{f.get('file')}:{f.get('line')}` | {f.get('title')} | {f.get('status', 'open')} |")
        md.append("")

        md.append("### Detailed Findings & Remediation")
        for f in report["findings"]:
            md.append(f"#### [{f.get('rule_id')}] {f.get('title')}")
            md.append(f"- **File & Line:** `{f.get('file')}:{f.get('line')}`")
            md.append(f"- **Severity / Confidence:** {f.get('severity')} / {f.get('confidence')}")
            md.append(f"- **Explanation:** {f.get('explanation')}")
            md.append(f"- **Remediation:** {f.get('fix')}")
            md.append(f"```python\n{f.get('snippet', '')}\n```")
            md.append("")

    # Verification Section
    if report.get("verifications"):
        md.append("## Verification Results")
        for v in report["verifications"]:
            md.append(f"### {v.get('file')}: {v.get('overall_result', v.get('status'))}")
            for c in v.get("checks", []):
                md.append(f"- [{c.get('status', '').upper()}] **{c.get('name')}:** {c.get('detail')}")
        md.append("")

    # Limitations
    md.append("## Limitations & Responsible Use")
    for lim in report.get("limitations", []):
        md.append(f"- {lim}")

    return "\n".join(md)

def to_html(report: dict) -> str:
    """Exports stylized, standalone HTML security report with clean cyber styling."""
    e = lambda x: html.escape(str(x))
    rows = "".join(
        f"<tr><td><code>{e(f.get('rule_id'))}</code></td>"
        f"<td><span class='badge-{e(f.get('severity','').lower()[:3])}'>{e(f.get('severity'))}</span></td>"
        f"<td><code>{e(f.get('file'))}:{e(f.get('line'))}</code></td>"
        f"<td>{e(f.get('title'))}</td>"
        f"<td><code>{e(f.get('snippet', ''))}</code></td>"
        f"<td>{e(f.get('fix', ''))}</td></tr>"
        for f in report.get("findings", [])
    )
    ver_items = "".join(
        f"<li><strong>{e(v.get('file'))}</strong>: {e(v.get('overall_result', v.get('status')))}</li>"
        for v in report.get("verifications", [])
    )
    lim_items = "".join(f"<li>{e(x)}</li>" for x in report.get("limitations", []))

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>VulnQuest AI Security Report</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #0e1117; color: #e0e0e0; margin: 2rem; }}
h1, h2, h3 {{ color: #2ee6a6; }}
table {{ border-collapse: collapse; width: 100%; margin-top: 1rem; background: #161b22; }}
th, td {{ border: 1px solid #30363d; padding: 10px; text-align: left; font-size: 0.9rem; }}
th {{ background: #21262d; color: #2ee6a6; }}
code {{ font-family: monospace; background: #21262d; padding: 2px 4px; border-radius: 4px; color: #79c0ff; }}
.badge-hig, .badge-cri {{ background: #ff4b4b33; color: #ff6b6b; padding: 2px 8px; border-radius: 4px; font-weight: bold; }}
.badge-med {{ background: #ffa50033; color: #ffb74d; padding: 2px 8px; border-radius: 4px; font-weight: bold; }}
.badge-low {{ background: #00c0f233; color: #4fc3f7; padding: 2px 8px; border-radius: 4px; font-weight: bold; }}
.summary-box {{ background: #161b22; border: 1px solid #30363d; padding: 1rem; border-radius: 6px; margin-bottom: 2rem; }}
</style>
</head>
<body>
<h1>🛡️ VulnQuest AI Security Audit Report</h1>
<div class="summary-box">
<p><strong>Generated At:</strong> {e(report.get('generated_at'))} (UTC)</p>
<p><strong>Scanner Version:</strong> {e(report.get('version'))}</p>
<p><strong>Total Findings:</strong> {len(report.get('findings', []))}</p>
</div>
<h2>Vulnerability Findings</h2>
<table>
<thead><tr><th>Rule</th><th>Severity</th><th>Location</th><th>Title</th><th>Evidence Snippet</th><th>Remediation Guidance</th></tr></thead>
<tbody>{rows or '<tr><td colspan="6">No findings reported.</td></tr>'}</tbody>
</table>
<h2>Verification Results</h2>
<ul>{ver_items or '<li>No verifications performed.</li>'}</ul>
<h2>Limitations & Scope</h2>
<ul>{lim_items}</ul>
</body>
</html>"""

