"""VulnQuest native desktop entry point (Windows 10/11, PySide6)."""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
    QPushButton, QStackedWidget, QTableWidget, QTableWidgetItem, QTextEdit,
    QVBoxLayout, QWidget,
)

from vulnquest import config, storage
from vulnquest.ai_provider import OllamaProvider
from vulnquest.reports import build_report, to_csv, to_html, to_json, to_markdown
from vulnquest.scanner import read_folder, scan_files


class ScanWorker(QThread):
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, folder: Path):
        super().__init__()
        self.folder = folder

    def run(self):
        try:
            files, skipped = read_folder(self.folder)
            result = scan_files(files)
            result["skipped"].extend(skipped)
            result["project"] = str(self.folder)
            self.completed.emit(result)
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class ModelCheckWorker(QThread):
    completed = Signal(bool, str)

    def run(self):
        try:
            self.completed.emit(*OllamaProvider().test_connection())
        except Exception as exc:
            self.completed.emit(False, f"{type(exc).__name__}: {exc}")


class VulnQuestWindow(QMainWindow):
    PAGES = ["Dashboard", "Project Manager", "Security Scanner", "Findings Explorer",
             "AI Security Assistant", "Patch Lab", "Verification Center", "Git Diff Scanner",
             "Reports", "Scan History", "Model Manager", "Settings", "Help & Diagnostics"]

    def __init__(self):
        super().__init__()
        self.setWindowTitle("VulnQuest AI — Local Security Workbench")
        self.resize(1360, 860)
        self.setMinimumSize(1050, 700)
        self.project: Path | None = None
        self.project_labels: list[QLabel] = []
        self.progress_labels: list[QLabel] = []
        self.findings: list[dict] = []
        self.last_scan: dict | None = None
        root = QWidget()
        layout = QHBoxLayout(root)
        self.nav = QVBoxLayout()
        self.nav.setContentsMargins(12, 18, 12, 16)
        self.nav.setSpacing(6)
        self.stack = QStackedWidget()
        self.nav.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.nav_title = QLabel("VULNQUEST")
        self.nav_title.setObjectName("Brand")
        self.nav_subtitle = QLabel("LOCAL SECURITY WORKBENCH")
        self.nav_subtitle.setObjectName("BrandSub")
        self.nav.addWidget(self.nav_title)
        self.nav.addWidget(self.nav_subtitle)
        self.nav.addSpacing(22)
        layout.addLayout(self.nav, 1)
        layout.addWidget(self.stack, 5)
        self.setCentralWidget(root)

        for name in self.PAGES:
            button = QPushButton(name)
            button.setObjectName("NavButton")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, n=name: self.show_page(n))
            self.nav.addWidget(button)
            self.stack.addWidget(self.make_page(name))
        self.nav.addStretch(1)
        self.show_page("Dashboard")
        self.refresh_dashboard()
        self.setStyleSheet("""
            QWidget { background: #0b1220; color: #e2e8f0; font-family: 'Segoe UI'; font-size: 10pt; }
            QMainWindow { background: #0b1220; }
            QLabel#Brand { color:#4adeb5; font-size:20pt; font-weight:800; letter-spacing:1px; }
            QLabel#BrandSub { color:#718096; font-size:8pt; font-weight:600; }
            QLabel { color:#dbe5f1; }
            QStackedWidget { background:#0b1220; }
            QPushButton { background:#142238; color:#dce8f5; border:1px solid #24354d; border-radius:8px; padding:10px 14px; text-align:left; }
            QPushButton:hover { background:#1b3048; border-color:#38bdf8; }
            QPushButton#PrimaryButton { background:#087f68; color:#f0fdfa; border:1px solid #14b8a6; font-weight:700; padding:12px 16px; }
            QPushButton#PrimaryButton:hover { background:#0f9f82; }
            QPushButton#NavButton { background:transparent; border:0; color:#9babc0; padding:11px 12px; }
            QPushButton#NavButton:hover, QPushButton#NavButton:checked { background:#14283a; color:#4adeb5; border-left:3px solid #4adeb5; }
            QLineEdit, QTextEdit, QTableWidget { background:#101b2b; border:1px solid #26364a; border-radius:8px; padding:8px; gridline-color:#223147; }
            QHeaderView::section { background:#17263a; color:#9fb2c8; padding:8px; border:0; }
            QTableWidget { selection-background-color:#164e63; }
            QScrollBar:vertical { background:#0b1220; width:10px; } QScrollBar::handle:vertical { background:#334155; border-radius:4px; }
        """)

    def make_page(self, name: str) -> QWidget:
        page = QWidget()
        box = QVBoxLayout(page)
        heading = QLabel(name)
        heading.setStyleSheet("font-size: 25px; font-weight: 700; color: #f1f5f9; padding: 12px 4px")
        box.addWidget(heading)
        if name in ("Dashboard", "Project Manager", "Security Scanner"):
            self.project_label = QLabel("No project selected")
            self.project_labels.append(self.project_label)
            box.addWidget(self.project_label)
            choose = QPushButton("Choose project folder")
            choose.clicked.connect(self.choose_project)
            box.addWidget(choose)
            scan = QPushButton("Scan project source")
            scan.setObjectName("PrimaryButton")
            scan.clicked.connect(self.start_scan)
            box.addWidget(scan)
            if name == "Dashboard":
                self.dashboard_summary = QLabel("No scan has been run in this session.\n\nSupported discovery: Python, JavaScript / TypeScript, Java, C / C++, C#, Go, Rust, PHP, Ruby, Swift, Kotlin, Scala, shell, SQL, HTML, YAML, JSON, TOML, Terraform and common project config files.")
                self.dashboard_summary.setWordWrap(True)
                self.dashboard_summary.setStyleSheet("background:#101b2b; border:1px solid #26364a; border-radius:12px; padding:20px; font-size:12pt")
                box.addWidget(self.dashboard_summary)
            if name == "Project Manager":
                box.addWidget(QLabel("Read-only source scanning. Python gets AST checks; other supported source/config files get cautious lexical checks. Project code is never executed."))
            if name == "Security Scanner":
                self.progress_label = QLabel("Ready to scan supported source files")
                self.progress_labels.append(self.progress_label)
                box.addWidget(self.progress_label)
            else:
                self.progress_label = QLabel("Ready to scan")
                self.progress_labels.append(self.progress_label)
                box.addWidget(self.progress_label)
        elif name == "Findings Explorer":
            self.findings_table = QTableWidget(0, 6)
            self.findings_table.setHorizontalHeaderLabels(["Severity", "Rule", "File", "Line", "Finding", "Confidence"])
            self.findings_table.horizontalHeader().setStretchLastSection(True)
            box.addWidget(self.findings_table)
        elif name == "Reports":
            box.addWidget(QLabel("Exports redact evidence snippets using the existing report module."))
            for fmt in ("json", "csv", "html", "md"):
                btn = QPushButton(f"Export {fmt.upper()}")
                btn.clicked.connect(lambda checked=False, f=fmt: self.export_report(f))
                box.addWidget(btn)
        elif name == "Scan History":
            self.history_text = QTextEdit()
            self.history_text.setReadOnly(True)
            box.addWidget(self.history_text)
            refresh = QPushButton("Refresh local history")
            refresh.clicked.connect(self.refresh_history)
            box.addWidget(refresh)
            clear = QPushButton("Clear local history")
            clear.clicked.connect(self.clear_history)
            box.addWidget(clear)
        elif name == "Model Manager":
            box.addWidget(QLabel("Primary model: Gemma 4 E2B instruction-tuned, Ollama quantization tag gemma4:e2b-it-q4_K_M. Ollama packages model weights; this is not a Google-issued Ollama tag."))
            self.model_status = QLabel("Connection not checked")
            box.addWidget(self.model_status)
            check = QPushButton("Check local Ollama and model")
            check.clicked.connect(self.check_model)
            box.addWidget(check)
            box.addWidget(QLabel("Setup: install Ollama, then run `ollama pull gemma4:e2b-it-q4_K_M`. Model download is several GB; available RAM and speed depend on quantization and hardware."))
        elif name == "Settings":
            box.addWidget(QLabel(f"Data directory: {config.DATA_DIR.resolve()}\nAI defaults to local Ollama. Hosted-provider transmissions are not configured in this desktop interface."))
        else:
            info = {
                "AI Security Assistant": "Real local Gemma 4 inference is available through Model Manager/provider code. Interactive finding chat is not yet implemented.",
                "Patch Lab": "Patch approval, atomic source-file application, backup management, and rollback are not yet integrated into this desktop interface. No source files are modified here.",
                "Verification Center": "The existing static verification module is present, but this desktop screen does not yet run or persist patch verification.",
                "Git Diff Scanner": "The existing Git diff scanner module is present, but this desktop screen does not yet expose it.",
                "Help & Diagnostics": "Static scanning works without API keys or a local model. Python and PySide6 are required. Scanned source code is not executed.",
            }
            box.addWidget(QLabel(info.get(name, "Not implemented.")))
        box.addStretch(1)
        return page

    def show_page(self, name: str):
        self.stack.setCurrentIndex(self.PAGES.index(name))
        for button in self.findChildren(QPushButton, "NavButton"):
            button.setChecked(button.text() == name)
        if name == "Scan History":
            self.refresh_history()

    def choose_project(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose project folder")
        if folder:
            self.project = Path(folder)
            for label in self.project_labels:
                label.setText(str(self.project))

    def start_scan(self):
        if not self.project:
            QMessageBox.information(self, "Choose a project", "Select a project folder first.")
            return
        self.set_scan_status("Scanning project source…")
        self.worker = ScanWorker(self.project)
        self.worker.completed.connect(self.scan_done)
        self.worker.failed.connect(lambda e: self.set_scan_status(f"Scan failed: {e}"))
        self.worker.start()

    def set_scan_status(self, message: str):
        for label in self.progress_labels:
            label.setText(message)

    def scan_done(self, result: dict):
        self.last_scan = result
        self.findings = [f.to_dict() if hasattr(f, "to_dict") else dict(f) for f in result["findings"]]
        counts = Counter(f.get("severity", "Unknown") for f in self.findings)
        storage.save_scan(result["scanned"], len(self.findings), dict(counts))
        self.set_scan_status(f"Complete · {result['scanned']} source files · {len(self.findings)} findings · {len(result['errors'])} errors")
        self.populate_findings()
        self.refresh_dashboard()

    def populate_findings(self):
        table = self.findings_table
        table.setRowCount(len(self.findings))
        for row, finding in enumerate(self.findings):
            values = [finding.get("severity"), finding.get("rule_id"), finding.get("file"), finding.get("line"), finding.get("title"), finding.get("confidence")]
            for col, value in enumerate(values):
                table.setItem(row, col, QTableWidgetItem(str(value or "")))
        table.resizeColumnsToContents()

    def refresh_dashboard(self):
        if hasattr(self, "dashboard_summary"):
            if self.last_scan:
                self.dashboard_summary.setText(f"Project: {self.last_scan['project']}\nSource files scanned: {self.last_scan['scanned']}\nFile types: {self.last_scan.get('languages', {})}\nFindings: {len(self.findings)}\nSeverity counts: {dict(Counter(f.get('severity', 'Unknown') for f in self.findings))}")

    def refresh_history(self):
        rows = storage.list_scans()
        self.history_text.setPlainText("\n".join(f"{ts} | {files} files | {findings} findings | {severity}" for ts, files, findings, severity in rows) or "No scans stored.")

    def clear_history(self):
        answer = QMessageBox.question(self, "Clear history", "Delete all locally stored scan history?")
        if answer == QMessageBox.StandardButton.Yes:
            storage.clear_history()
            self.refresh_history()

    def export_report(self, fmt: str):
        if self.last_scan is None:
            QMessageBox.information(self, "No scan", "Run a scan before exporting a report.")
            return
        report = build_report(self.findings, {"project": str(self.project) if self.project else ""})
        render = {"json": to_json, "csv": to_csv, "html": to_html, "md": to_markdown}[fmt]
        path, _ = QFileDialog.getSaveFileName(self, "Save report", f"vulnquest-report.{fmt}")
        if path:
            Path(path).write_text(render(report), encoding="utf-8")

    def check_model(self):
        self.model_status.setText("Checking local Ollama…")
        self.model_worker = ModelCheckWorker()
        self.model_worker.completed.connect(self.model_check_done)
        self.model_worker.start()

    def model_check_done(self, ok: bool, message: str):
        self.model_status.setText(("Ready: " if ok else "Unavailable: ") + message)


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = VulnQuestWindow()
    if "--self-check" in sys.argv[1:]:
        valid = window.stack.count() == len(window.PAGES)
        window.close()
        return 0 if valid else 2
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
