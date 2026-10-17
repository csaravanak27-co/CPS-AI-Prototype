"""
C.P.S. — AI Coding Companion
============================
Native Windows Desktop Application (Windows 10/11, PySide6).
Provides:
  - Multi-language AI Code Studio (Generation, Explanation, Debugging, Optimization, Conversion, Tests, Complexity)
  - Interactive AI Coding Chat
  - Security Scanner & AST Analysis
  - Findings Explorer with Evidence Inspection
  - Safe Patch Lab with Human Approval, Backups & Rollback
  - Independent Patch Verification Center
  - Git Diff Scanner for Staged and Working Changes
  - Isolated Code Execution Sandbox
  - Redacted Audit Reports (JSON, CSV, HTML, Markdown)
  - Local Scan & Conversation History
  - Model Manager (Ollama / Gemma 4 / Groq / Gemini / OpenRouter)
  - Privacy Controls & Diagnostics
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Optional

try:
    from PySide6.QtCore import QThread, Signal, Qt
    from PySide6.QtWidgets import (
        QApplication, QComboBox, QFileDialog, QGroupBox, QHBoxLayout,
        QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox,
        QPushButton, QScrollArea, QSplitter, QStackedWidget,
        QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
    )
except ImportError as exc:
    if "--self-check" in sys.argv:
        print(f"C.P.S. self-check unavailable: {type(exc).__name__}: {exc}")
        raise SystemExit(2)
    raise

from cps import __version__, __product__, config, storage
from cps.ai_provider import (
    get_provider, BaseProvider, MockProvider, OllamaProvider,
    GroqProvider, GeminiProvider, OpenRouterProvider
)
from cps.code_engine import CodeEngine, CodeRequest, CodeResponse, LANGUAGE_PROFILES
from cps.executor import CodeExecutor
from cps.git_diff import is_git_repo, scan_git_diff
from cps.patcher import apply_patch, build_patched, rollback, unified_diff
from cps.reports import build_report, to_csv, to_html, to_json, to_markdown
from cps.scanner import read_folder, scan_files, scan_source
from cps.verification import verify


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


class CodeGenWorker(QThread):
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, provider_name: str, request: CodeRequest):
        super().__init__()
        self.provider_name = provider_name
        self.request = request

    def run(self):
        try:
            prov = get_provider(self.provider_name)
            engine = CodeEngine(provider=prov)
            res = engine.process(self.request)
            self.completed.emit(res)
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class ModelCheckWorker(QThread):
    completed = Signal(bool, str)

    def __init__(self, provider_name: str = "ollama"):
        super().__init__()
        self.provider_name = provider_name

    def run(self):
        try:
            prov = get_provider(self.provider_name)
            ok, msg = prov.test_connection()
            self.completed.emit(ok, msg)
        except Exception as exc:
            self.completed.emit(False, f"{type(exc).__name__}: {exc}")


class ExecWorker(QThread):
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, code: str, language: str, stdin: str = "", timeout: int = 10):
        super().__init__()
        self.code = code
        self.language = language
        self.stdin = stdin
        self.timeout = timeout

    def run(self):
        try:
            executor = CodeExecutor(default_timeout=self.timeout)
            res = executor.execute(self.code, language=self.language, stdin=self.stdin, timeout=self.timeout)
            self.completed.emit(res)
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class GitDiffWorker(QThread):
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, folder: Path, staged: bool = False):
        super().__init__()
        self.folder = folder
        self.staged = staged

    def run(self):
        try:
            res = scan_git_diff(self.folder, staged=self.staged)
            self.completed.emit(res)
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class CPSMainWindow(QMainWindow):
    PAGES = [
        "Dashboard",
        "Code Studio",
        "AI Chat",
        "Project Scanner",
        "Findings Explorer",
        "Patch Lab",
        "Verification Center",
        "Git Diff Scanner",
        "Execution Sandbox",
        "Reports",
        "Scan History",
        "Model Manager",
        "Settings & Privacy",
    ]

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{__product__} — AI Coding Companion (v{__version__})")
        self.resize(1380, 880)
        self.setMinimumSize(1080, 720)

        self.project: Path | None = None
        self.findings: list[dict] = []
        self.last_scan: dict | None = None
        self.selected_finding: dict | None = None
        self.last_proposed_patch: dict | None = None
        self.chat_history: list[dict] = []
        self._workers: list[QThread] = []

        root = QWidget()
        main_layout = QHBoxLayout(root)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Left Navigation Sidebar
        nav_widget = QWidget()
        nav_widget.setObjectName("NavSidebar")
        nav_widget.setFixedWidth(240)
        self.nav = QVBoxLayout(nav_widget)
        self.nav.setContentsMargins(14, 20, 14, 20)
        self.nav.setSpacing(4)
        self.nav.setAlignment(Qt.AlignmentFlag.AlignTop)

        brand_layout = QVBoxLayout()
        brand_layout.setSpacing(2)
        self.nav_title = QLabel("C.P.S.")
        self.nav_title.setObjectName("Brand")
        self.nav_subtitle = QLabel("AI CODING COMPANION")
        self.nav_subtitle.setObjectName("BrandSub")
        brand_layout.addWidget(self.nav_title)
        brand_layout.addWidget(self.nav_subtitle)
        self.nav.addLayout(brand_layout)
        self.nav.addSpacing(16)

        self.stack = QStackedWidget()
        main_layout.addWidget(nav_widget)
        main_layout.addWidget(self.stack, 1)
        self.setCentralWidget(root)

        # Build pages
        for name in self.PAGES:
            button = QPushButton(name)
            button.setObjectName("NavButton")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, n=name: self.show_page(n))
            self.nav.addWidget(button)
            self.stack.addWidget(self.make_page(name))

        self.nav.addStretch(1)

        # Footer status in nav
        self.nav_status = QLabel("🟢 System Ready")
        self.nav_status.setStyleSheet("color: #4adeb5; font-size: 8pt; padding: 6px;")
        self.nav.addWidget(self.nav_status)

        self.show_page("Dashboard")
        self.apply_theme()

    def _start_worker(self, worker: QThread) -> None:
        """Keep background workers alive until they finish."""
        self._workers.append(worker)
        worker.finished.connect(
            lambda w=worker: self._workers.remove(w) if w in self._workers else None
        )
        worker.start()

    def closeEvent(self, event):
        """Stop/finish background work before Qt destroys worker objects."""
        for worker in tuple(self._workers):
            if worker.isRunning():
                worker.requestInterruption()
        for worker in tuple(self._workers):
            if worker.isRunning():
                worker.wait(5000)
        event.accept()

    def apply_theme(self):
        self.setStyleSheet("""
            QWidget { background: #0b1220; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; font-size: 10pt; }
            QMainWindow { background: #0b1220; }
            QWidget#NavSidebar { background: #070d17; border-right: 1px solid #1a273b; }
            QLabel#Brand { color: #4adeb5; font-size: 22pt; font-weight: 900; letter-spacing: 2px; }
            QLabel#BrandSub { color: #38bdf8; font-size: 7.5pt; font-weight: 700; letter-spacing: 1px; }
            QLabel { color: #dbe5f1; }
            QStackedWidget { background: #0b1220; }
            QPushButton { background: #132035; color: #dce8f5; border: 1px solid #24354d; border-radius: 6px; padding: 8px 14px; }
            QPushButton:hover { background: #1b3048; border-color: #38bdf8; color: #ffffff; }
            QPushButton#PrimaryButton { background: #0f766e; color: #ffffff; border: 1px solid #14b8a6; font-weight: 700; padding: 10px 16px; border-radius: 6px; }
            QPushButton#PrimaryButton:hover { background: #14b8a6; }
            QPushButton#DangerButton { background: #7f1d1d; color: #fecaca; border: 1px solid #dc2626; font-weight: 700; }
            QPushButton#DangerButton:hover { background: #b91c1c; color: #ffffff; }
            QPushButton#NavButton { background: transparent; border: 0; color: #94a3b8; padding: 9px 12px; text-align: left; font-size: 9.5pt; font-weight: 500; border-radius: 6px; }
            QPushButton#NavButton:hover { background: #132238; color: #e2e8f0; }
            QPushButton#NavButton:checked { background: #13263d; color: #4adeb5; font-weight: 700; border-left: 3px solid #4adeb5; }
            QLineEdit, QTextEdit, QTableWidget, QComboBox { background: #101b2b; border: 1px solid #26364a; border-radius: 6px; padding: 8px; color: #f1f5f9; }
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus { border: 1px solid #38bdf8; }
            QComboBox::drop-down { border: 0; }
            QHeaderView::section { background: #162438; color: #94a3b8; padding: 8px; border: 0; font-weight: 600; }
            QTableWidget { gridline-color: #1e2e42; selection-background-color: #0e7490; }
            QScrollBar:vertical { background: #0b1220; width: 8px; }
            QScrollBar::handle:vertical { background: #334155; border-radius: 4px; }
        """)

    def make_page(self, name: str) -> QWidget:
        page = QWidget()
        box = QVBoxLayout(page)
        box.setContentsMargins(28, 24, 28, 24)
        box.setSpacing(14)

        header = QLabel(name)
        header.setStyleSheet("font-size: 20pt; font-weight: 800; color: #f8fafc;")
        box.addWidget(header)

        if name == "Dashboard":
            self.setup_dashboard(box)
        elif name == "Code Studio":
            self.setup_code_studio(box)
        elif name == "AI Chat":
            self.setup_ai_chat(box)
        elif name == "Project Scanner":
            self.setup_scanner(box)
        elif name == "Findings Explorer":
            self.setup_findings(box)
        elif name == "Patch Lab":
            self.setup_patch_lab(box)
        elif name == "Verification Center":
            self.setup_verification(box)
        elif name == "Git Diff Scanner":
            self.setup_git_diff(box)
        elif name == "Execution Sandbox":
            self.setup_executor(box)
        elif name == "Reports":
            self.setup_reports(box)
        elif name == "Scan History":
            self.setup_history(box)
        elif name == "Model Manager":
            self.setup_model_manager(box)
        elif name == "Settings & Privacy":
            self.setup_settings(box)

        return page

    # ------------------------------------------------------------------------
    # 1. Dashboard
    # ------------------------------------------------------------------------
    def setup_dashboard(self, box: QVBoxLayout):
        desc = QLabel(
            "Welcome to C.P.S. — your unified AI coding companion, browser extension partner, "
            "and local code security engine."
        )
        desc.setStyleSheet("color: #94a3b8; font-size: 11pt;")
        box.addWidget(desc)

        # Quick stats cards
        cards_layout = QHBoxLayout()
        self.dash_card1 = self.create_card("Supported Languages", "28+ Languages", "Python, Java, C++, JS, Rust, Go...")
        self.dash_card2 = self.create_card("Local AI Provider", "Gemma 4 via Ollama", "100% Private local inference ready")
        self.dash_card3 = self.create_card("Security Scanner", "16 AST/Lexical Rules", "Deterministic zero-leakage analysis")
        self.dash_card4 = self.create_card("Browser Extension", "Manifest V3 Ready", "Companion active on port 8899")
        cards_layout.addWidget(self.dash_card1)
        cards_layout.addWidget(self.dash_card2)
        cards_layout.addWidget(self.dash_card3)
        cards_layout.addWidget(self.dash_card4)
        box.addLayout(cards_layout)

        # Quick action buttons
        actions_label = QLabel("Quick Actions")
        actions_label.setStyleSheet("font-size: 13pt; font-weight: 700; color: #e2e8f0; margin-top: 10px;")
        box.addWidget(actions_label)

        action_row = QHBoxLayout()
        btn_studio = QPushButton("⚡ Open Code Studio")
        btn_studio.clicked.connect(lambda: self.show_page("Code Studio"))
        btn_scan = QPushButton("🛡️ Scan Project Folder")
        btn_scan.clicked.connect(lambda: self.show_page("Project Scanner"))
        btn_chat = QPushButton("💬 Open AI Chat")
        btn_chat.clicked.connect(lambda: self.show_page("AI Chat"))
        btn_exec = QPushButton("▶️ Test in Sandbox")
        btn_exec.clicked.connect(lambda: self.show_page("Execution Sandbox"))

        action_row.addWidget(btn_studio)
        action_row.addWidget(btn_scan)
        action_row.addWidget(btn_chat)
        action_row.addWidget(btn_exec)
        box.addLayout(action_row)

        self.dash_summary = QTextEdit()
        self.dash_summary.setReadOnly(True)
        self.dash_summary.setPlaceholderText("Recent scan and activity details will appear here...")
        box.addWidget(self.dash_summary)

    def create_card(self, title: str, main_text: str, sub_text: str) -> QWidget:
        card = QWidget()
        card.setStyleSheet("background: #111e31; border: 1px solid #1e324c; border-radius: 8px; padding: 12px;")
        l = QVBoxLayout(card)
        t = QLabel(title)
        t.setStyleSheet("color: #94a3b8; font-size: 8.5pt; font-weight: 600; text-transform: uppercase;")
        m = QLabel(main_text)
        m.setStyleSheet("color: #4adeb5; font-size: 14pt; font-weight: 800; margin: 4px 0;")
        s = QLabel(sub_text)
        s.setStyleSheet("color: #64748b; font-size: 8.5pt;")
        s.setWordWrap(True)
        l.addWidget(t)
        l.addWidget(m)
        l.addWidget(s)
        return card

    # ------------------------------------------------------------------------
    # 2. Code Studio
    # ------------------------------------------------------------------------
    def setup_code_studio(self, box: QVBoxLayout):
        top_bar = QHBoxLayout()

        top_bar.addWidget(QLabel("Target Language:"))
        self.studio_lang = QComboBox()
        for lang_id, prof in sorted(LANGUAGE_PROFILES.items()):
            self.studio_lang.addItem(prof["name"], lang_id)
        top_bar.addWidget(self.studio_lang)

        top_bar.addWidget(QLabel("Provider:"))
        self.studio_prov = QComboBox()
        self.studio_prov.addItems(["Mock / Offline", "Ollama (Local)", "Groq", "Google Gemini", "OpenRouter"])
        top_bar.addWidget(self.studio_prov)

        top_bar.addStretch(1)
        box.addLayout(top_bar)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left pane: Input
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        left_layout.addWidget(QLabel("Problem Statement / Prompt:"))
        self.studio_prompt = QTextEdit()
        self.studio_prompt.setPlaceholderText("Describe the problem or algorithm (e.g. 'Two Sum optimal hash map solution')...")
        self.studio_prompt.setMaximumHeight(130)
        left_layout.addWidget(self.studio_prompt)

        left_layout.addWidget(QLabel("Source Code (Optional for explain/debug/optimize):"))
        self.studio_code_in = QTextEdit()
        self.studio_code_in.setPlaceholderText("Paste source code here...")
        left_layout.addWidget(self.studio_code_in)

        # Actions buttons grid
        btn_layout = QHBoxLayout()
        for action, label in [
            ("generate", "⚡ Generate"),
            ("explain", "💡 Explain"),
            ("debug", "🐛 Debug"),
            ("optimize", "🚀 Optimize"),
            ("tests", "🧪 Tests"),
            ("complexity", "📊 Complexity"),
        ]:
            b = QPushButton(label)
            if action == "generate":
                b.setObjectName("PrimaryButton")
            b.clicked.connect(lambda checked=False, a=action: self.run_studio_action(a))
            btn_layout.addWidget(b)
        left_layout.addLayout(btn_layout)

        # Right pane: Output
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        right_header = QHBoxLayout()
        right_header.addWidget(QLabel("Solution & Explanation:"))
        self.studio_copy_btn = QPushButton("📋 Copy Code")
        self.studio_copy_btn.clicked.connect(self.copy_studio_code)
        right_header.addWidget(self.studio_copy_btn)
        right_layout.addLayout(right_header)

        self.studio_code_out = QTextEdit()
        self.studio_code_out.setReadOnly(True)
        self.studio_code_out.setPlaceholderText("Generated code and explanation will appear here...")
        right_layout.addWidget(self.studio_code_out)

        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([550, 750])
        box.addWidget(splitter)

    def run_studio_action(self, action: str):
        lang = self.studio_lang.currentData()
        prov_map = {
            "Mock / Offline": "mock",
            "Ollama (Local)": "ollama",
            "Groq": "groq",
            "Google Gemini": "gemini",
            "OpenRouter": "openrouter",
        }
        prov_key = prov_map.get(self.studio_prov.currentText(), "mock")

        req = CodeRequest(
            action=action,
            source_code=self.studio_code_in.toPlainText().strip(),
            language=lang,
            problem_statement=self.studio_prompt.toPlainText().strip(),
        )

        self.studio_code_out.setPlainText("Processing request with C.P.S. engine...")
        self.studio_worker = CodeGenWorker(prov_key, req)
        self.studio_worker.completed.connect(self.studio_action_done)
        self.studio_worker.failed.connect(lambda err: self.studio_code_out.setPlainText(f"Error: {err}"))
        self._start_worker(self.studio_worker)

    def studio_action_done(self, res: CodeResponse):
        out = []
        if res.code:
            out.append(f"```{res.language}\n{res.code}\n```\n")
        if res.explanation:
            out.append(f"### Explanation\n{res.explanation}\n")
        if res.complexity_analysis:
            out.append(f"### Complexity\n{res.complexity_analysis}\n")
        if res.test_cases:
            out.append(f"### Test Cases\n" + "\n".join(f"- {t}" for t in res.test_cases))
        if not out:
            out.append(res.raw_response or "Analysis completed.")
        self.studio_code_out.setPlainText("\n".join(out))

    def copy_studio_code(self):
        txt = self.studio_code_out.toPlainText()
        if txt:
            QApplication.clipboard().setText(txt)
            QMessageBox.information(self, "Copied", "Content copied to clipboard!")

    # ------------------------------------------------------------------------
    # 3. AI Coding Chat
    # ------------------------------------------------------------------------
    def setup_ai_chat(self, box: QVBoxLayout):
        chat_top = QHBoxLayout()
        chat_top.addWidget(QLabel("AI Provider:"))
        self.chat_prov = QComboBox()
        self.chat_prov.addItems(["Mock / Offline", "Ollama (Local Gemma 4)", "Groq", "Google Gemini", "OpenRouter"])
        chat_top.addWidget(self.chat_prov)
        chat_top.addStretch(1)
        clear_chat_btn = QPushButton("Clear Thread")
        clear_chat_btn.clicked.connect(self.clear_chat)
        chat_top.addWidget(clear_chat_btn)
        box.addLayout(chat_top)

        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setPlaceholderText("Ask C.P.S. any coding question, architecture design, or algorithm explanation...")
        box.addWidget(self.chat_display, 1)

        input_layout = QHBoxLayout()
        self.chat_input = QTextEdit()
        self.chat_input.setFixedHeight(70)
        self.chat_input.setPlaceholderText("Type your coding question here (Ctrl+Enter to send)...")
        send_btn = QPushButton("Send")
        send_btn.setObjectName("PrimaryButton")
        send_btn.setFixedWidth(100)
        send_btn.clicked.connect(self.send_chat_message)

        input_layout.addWidget(self.chat_input, 1)
        input_layout.addWidget(send_btn)
        box.addLayout(input_layout)

        # Load persisted history from SQLite
        self.load_persisted_chat()

    def load_persisted_chat(self):
        try:
            saved = storage.list_chat_history(limit=50)
            for msg in saved:
                role = msg.get("role", "User")
                content = msg.get("content", "")
                self.chat_history.append({"sender": role, "text": content})
                color = "#4adeb5" if role == "C.P.S." else "#38bdf8"
                self.chat_display.append(f"<b style='color: {color};'>[{role}]</b><br>{content.replace(chr(10), '<br>')}<br>")
        except Exception:
            pass

    def send_chat_message(self):
        msg = self.chat_input.toPlainText().strip()
        if not msg:
            return

        self.chat_input.clear()
        self.append_chat("User", msg)

        prov_map = {
            "Mock / Offline": "mock",
            "Ollama (Local Gemma 4)": "ollama",
            "Groq": "groq",
            "Google Gemini": "gemini",
            "OpenRouter": "openrouter",
        }
        prov_key = prov_map.get(self.chat_prov.currentText(), "mock")

        req = CodeRequest(action="generate", problem_statement=msg, language="python")
        self.chat_worker = CodeGenWorker(prov_key, req)
        self.chat_worker.completed.connect(lambda res: self.append_chat("C.P.S.", res.raw_response or res.explanation or res.code))
        self.chat_worker.failed.connect(lambda err: self.append_chat("C.P.S. [Error]", err))
        self._start_worker(self.chat_worker)

    def append_chat(self, sender: str, text: str, persist: bool = True):
        self.chat_history.append({"sender": sender, "text": text})
        color = "#4adeb5" if sender == "C.P.S." else "#38bdf8"
        self.chat_display.append(f"<b style='color: {color};'>[{sender}]</b><br>{text.replace(chr(10), '<br>')}<br>")
        if persist and not sender.endswith("[Error]"):
            try:
                storage.save_chat_message(role=sender, content=text, action="chat")
            except Exception:
                pass

    def clear_chat(self):
        conf = QMessageBox.question(self, "Clear Thread", "Permanently clear chat thread and saved messages?")
        if conf == QMessageBox.StandardButton.Yes:
            self.chat_history.clear()
            self.chat_display.clear()
            try:
                storage.clear_chat_history()
            except Exception:
                pass

    # ------------------------------------------------------------------------
    # 4. Project Scanner
    # ------------------------------------------------------------------------
    def setup_scanner(self, box: QVBoxLayout):
        top_row = QHBoxLayout()
        self.project_label = QLabel("No project folder selected")
        self.project_label.setStyleSheet("color: #94a3b8; font-style: italic;")
        choose_btn = QPushButton("📁 Choose Project Folder")
        choose_btn.clicked.connect(self.choose_project)
        scan_btn = QPushButton("🛡️ Run Static Security Scan")
        scan_btn.setObjectName("PrimaryButton")
        scan_btn.clicked.connect(self.start_scan)

        top_row.addWidget(choose_btn)
        top_row.addWidget(self.project_label, 1)
        top_row.addWidget(scan_btn)
        box.addLayout(top_row)

        self.scan_status_label = QLabel("Ready to scan project files. Source code is never executed.")
        box.addWidget(self.scan_status_label)

        self.scan_console = QTextEdit()
        self.scan_console.setReadOnly(True)
        self.scan_console.setPlaceholderText("Scan diagnostics and summary will appear here...")
        box.addWidget(self.scan_console)

    def choose_project(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Project Folder")
        if folder:
            self.project = Path(folder)
            self.project_label.setText(str(self.project))
            self.scan_status_label.setText(f"Selected: {self.project}")

    def start_scan(self):
        if not self.project:
            QMessageBox.information(self, "No Project", "Please choose a project folder first.")
            return

        self.scan_status_label.setText("Scanning project files...")
        self.scan_console.append(f"Starting scan on: {self.project}")

        self.scan_worker = ScanWorker(self.project)
        self.scan_worker.completed.connect(self.scan_done)
        self.scan_worker.failed.connect(lambda err: self.scan_status_label.setText(f"Scan failed: {err}"))
        self._start_worker(self.scan_worker)

    def scan_done(self, result: dict):
        self.last_scan = result
        self.findings = [f.to_dict() if hasattr(f, "to_dict") else dict(f) for f in result.get("findings", [])]
        counts = Counter(f.get("severity", "Unknown") for f in self.findings)
        storage.save_scan(result.get("scanned", 0), len(self.findings), dict(counts))

        summary_msg = (
            f"✅ Scan Complete!\n"
            f"- Scanned Files: {result.get('scanned', 0)}\n"
            f"- Total Findings: {len(self.findings)}\n"
            f"- Severity Breakdown: {dict(counts)}\n"
            f"- Skipped: {len(result.get('skipped', []))} files\n"
        )
        self.scan_status_label.setText(f"Complete: {result.get('scanned', 0)} files, {len(self.findings)} findings.")
        self.scan_console.setPlainText(summary_msg)
        self.populate_findings_table()

    # ------------------------------------------------------------------------
    # 5. Findings Explorer
    # ------------------------------------------------------------------------
    def setup_findings(self, box: QVBoxLayout):
        self.findings_table = QTableWidget(0, 6)
        self.findings_table.setHorizontalHeaderLabels(["Severity", "Rule ID", "Location", "Category", "Title", "Confidence"])
        self.findings_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.findings_table.horizontalHeader().setStretchLastSection(True)
        self.findings_table.cellClicked.connect(self.finding_selected)
        box.addWidget(self.findings_table, 1)

        detail_box = QGroupBox("Finding Details & Remediation Guidance")
        detail_layout = QVBoxLayout(detail_box)
        self.finding_detail = QTextEdit()
        self.finding_detail.setReadOnly(True)
        self.finding_detail.setPlaceholderText("Select a finding row above to view full explanation, evidence snippet, and fix guidance...")
        detail_layout.addWidget(self.finding_detail)

        send_to_patch_btn = QPushButton("Send Finding to Patch Lab 🛠️")
        send_to_patch_btn.setObjectName("PrimaryButton")
        send_to_patch_btn.clicked.connect(self.send_selected_to_patch_lab)
        detail_layout.addWidget(send_to_patch_btn)

        box.addWidget(detail_box)

    def populate_findings_table(self):
        self.findings_table.setRowCount(len(self.findings))
        for row, f in enumerate(self.findings):
            self.findings_table.setItem(row, 0, QTableWidgetItem(f.get("severity", "")))
            self.findings_table.setItem(row, 1, QTableWidgetItem(f.get("rule_id", "")))
            self.findings_table.setItem(row, 2, QTableWidgetItem(f"{f.get('file', '')}:{f.get('line', '')}"))
            self.findings_table.setItem(row, 3, QTableWidgetItem(f.get("category", "")))
            self.findings_table.setItem(row, 4, QTableWidgetItem(f.get("title", "")))
            self.findings_table.setItem(row, 5, QTableWidgetItem(f.get("confidence", "")))

    def finding_selected(self, row: int, col: int):
        if 0 <= row < len(self.findings):
            f = self.findings[row]
            self.selected_finding = f
            txt = (
                f"[{f.get('rule_id')}] {f.get('title')}\n"
                f"File: {f.get('file')} | Line: {f.get('line')} | Severity: {f.get('severity')}\n\n"
                f"Explanation:\n{f.get('explanation')}\n\n"
                f"Remediation Guidance:\n{f.get('fix')}\n\n"
                f"Evidence Snippet:\n{f.get('snippet')}"
            )
            self.finding_detail.setPlainText(txt)

    def send_selected_to_patch_lab(self):
        if not self.selected_finding:
            QMessageBox.information(self, "No Finding Selected", "Select a finding first.")
            return
        self.show_page("Patch Lab")
        self.patch_finding_lbl.setText(f"Target: [{self.selected_finding.get('rule_id')}] {self.selected_finding.get('title')} ({self.selected_finding.get('file')}:{self.selected_finding.get('line')})")

    # ------------------------------------------------------------------------
    # 6. Patch Lab
    # ------------------------------------------------------------------------
    def setup_patch_lab(self, box: QVBoxLayout):
        self.patch_finding_lbl = QLabel("No finding selected. Select a finding in Findings Explorer first.")
        self.patch_finding_lbl.setStyleSheet("font-weight: 700; color: #38bdf8;")
        box.addWidget(self.patch_finding_lbl)

        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("Remediation AI Provider:"))
        self.patch_prov = QComboBox()
        self.patch_prov.addItems(["Mock / Offline", "Ollama (Local Gemma 4)", "Groq", "Google Gemini", "OpenRouter"])
        top_row.addWidget(self.patch_prov)
        top_row.addStretch(1)
        box.addLayout(top_row)

        btn_row = QHBoxLayout()
        propose_btn = QPushButton("🤖 Generate AI Patch Proposal")
        propose_btn.setObjectName("PrimaryButton")
        propose_btn.clicked.connect(self.generate_ai_patch)
        btn_row.addWidget(propose_btn)

        apply_btn = QPushButton("✅ Approve & Apply Patch (With Backup)")
        apply_btn.setStyleSheet("background: #065f46; color: #a7f3d0; font-weight: 700;")
        apply_btn.clicked.connect(self.apply_approved_patch)
        btn_row.addWidget(apply_btn)

        rollback_btn = QPushButton("↩️ Rollback File to Backup")
        rollback_btn.setObjectName("DangerButton")
        rollback_btn.clicked.connect(self.rollback_patch)
        btn_row.addWidget(rollback_btn)
        box.addLayout(btn_row)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget()
        l_layout = QVBoxLayout(left)
        l_layout.setContentsMargins(0, 0, 0, 0)
        l_layout.addWidget(QLabel("Unified Diff Preview:"))
        self.patch_diff_view = QTextEdit()
        self.patch_diff_view.setReadOnly(True)
        self.patch_diff_view.setPlaceholderText("Unified diff preview will appear here...")
        l_layout.addWidget(self.patch_diff_view)

        right = QWidget()
        r_layout = QVBoxLayout(right)
        r_layout.setContentsMargins(0, 0, 0, 0)
        r_layout.addWidget(QLabel("Proposed Remediated Code:"))
        self.patch_code_view = QTextEdit()
        self.patch_code_view.setPlaceholderText("Proposed replacement code lines...")
        r_layout.addWidget(self.patch_code_view)

        splitter.addWidget(left)
        splitter.addWidget(right)
        box.addWidget(splitter, 1)

    def generate_ai_patch(self):
        if not self.selected_finding:
            QMessageBox.information(self, "Notice", "Select a finding in Findings Explorer first.")
            return

        prov_map = {
            "Mock / Offline": "mock",
            "Ollama (Local Gemma 4)": "ollama",
            "Groq": "groq",
            "Google Gemini": "gemini",
            "OpenRouter": "openrouter",
        }
        prov_key = prov_map.get(self.patch_prov.currentText(), "mock")
        prov = get_provider(prov_key)
        rel_path = self.selected_finding.get("file", "")
        line_no = self.selected_finding.get("line", 1)

        target_file = Path(self.project) / rel_path if self.project else Path(rel_path)
        if not target_file.exists():
            QMessageBox.warning(self, "File Not Found", f"Cannot find source file: {target_file}")
            return

        orig_src = target_file.read_text(encoding="utf-8", errors="replace")
        lines = orig_src.splitlines()
        start = max(1, line_no - 1)
        end = min(len(lines), line_no + 1)
        context = "\n".join(lines[start - 1:end])

        proposal = prov.propose_fix(self.selected_finding, context, start, end)
        replacement = proposal.get("replacement", "")

        try:
            patched_src = build_patched(orig_src, start, end, replacement)
            diff_text = unified_diff(orig_src, patched_src, rel_path)
            self.patch_diff_view.setPlainText(diff_text)
            self.patch_code_view.setPlainText(replacement)
            self.last_proposed_patch = {
                "file": rel_path,
                "orig": orig_src,
                "patched": patched_src,
                "start": start,
                "end": end,
            }
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to build patch: {e}")

    def apply_approved_patch(self):
        if not self.last_proposed_patch or not self.project:
            QMessageBox.information(self, "Notice", "Generate a patch proposal first.")
            return

        confirm = QMessageBox.question(
            self,
            "Confirm Patch Approval",
            f"Apply patch to '{self.last_proposed_patch['file']}'?\nA pristine backup will be created automatically in .cps_backup/",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm == QMessageBox.StandardButton.Yes:
            try:
                res = apply_patch(
                    self.project,
                    self.last_proposed_patch["file"],
                    self.last_proposed_patch["patched"],
                    approved=True
                )
                QMessageBox.information(self, "Applied", f"Patch applied successfully!\nSHA256: {res['sha256'][:16]}...")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not apply patch: {e}")

    def rollback_patch(self):
        if not self.last_proposed_patch or not self.project:
            QMessageBox.information(self, "Notice", "Select a patched file to rollback.")
            return
        try:
            rollback(self.project, self.last_proposed_patch["file"])
            QMessageBox.information(self, "Restored", "File successfully restored from pristine backup!")
        except Exception as e:
            QMessageBox.critical(self, "Rollback Error", f"Rollback failed: {e}")

    # ------------------------------------------------------------------------
    # 7. Verification Center
    # ------------------------------------------------------------------------
    def setup_verification(self, box: QVBoxLayout):
        lbl = QLabel("Independent Patch Verification: Syntax validation, finding resolution, and API regression testing.")
        lbl.setStyleSheet("color: #94a3b8;")
        box.addWidget(lbl)

        run_ver_btn = QPushButton("🔬 Run Verification Checks on Last Proposed Patch")
        run_ver_btn.setObjectName("PrimaryButton")
        run_ver_btn.clicked.connect(self.run_verification)
        box.addWidget(run_ver_btn)

        self.ver_results_view = QTextEdit()
        self.ver_results_view.setReadOnly(True)
        self.ver_results_view.setPlaceholderText("Verification results will appear here...")
        box.addWidget(self.ver_results_view)

    def run_verification(self):
        if not self.last_proposed_patch:
            QMessageBox.information(self, "Notice", "No patch available to verify. Generate a patch in Patch Lab first.")
            return

        v = verify(
            self.last_proposed_patch["file"],
            self.last_proposed_patch["orig"],
            self.last_proposed_patch["patched"],
            target_rule=self.selected_finding.get("rule_id") if self.selected_finding else None,
        )

        lines = [
            f"=== C.P.S. Independent Verification Report ===",
            f"File: {v['file']}",
            f"Overall Result: {v['overall_result']}",
            f"Syntax Check: {v['syntax_status']}",
            f"Target Finding Resolution: {v['target_status']}",
            f"New Findings Introduced: {v['new_findings_status']}",
            f"API Regression Check: {v['regression_status']}",
            "",
            "Detailed Checks:"
        ]
        for c in v.get("checks", []):
            lines.append(f"  - [{c['status'].upper()}] {c['name']}: {c['detail']}")

        self.ver_results_view.setPlainText("\n".join(lines))

    # ------------------------------------------------------------------------
    # 8. Git Diff Scanner
    # ------------------------------------------------------------------------
    def setup_git_diff(self, box: QVBoxLayout):
        lbl = QLabel("Scan uncommitted git diffs and modified branches for newly introduced security findings.")
        lbl.setStyleSheet("color: #94a3b8;")
        box.addWidget(lbl)

        btn_row = QHBoxLayout()
        diff_btn = QPushButton("🔍 Scan Working Tree Git Diff")
        diff_btn.setObjectName("PrimaryButton")
        diff_btn.clicked.connect(lambda: self.run_git_diff(staged=False))
        btn_row.addWidget(diff_btn)

        staged_btn = QPushButton("🔍 Scan Staged Diff (--cached)")
        staged_btn.clicked.connect(lambda: self.run_git_diff(staged=True))
        btn_row.addWidget(staged_btn)
        box.addLayout(btn_row)

        self.git_diff_view = QTextEdit()
        self.git_diff_view.setReadOnly(True)
        self.git_diff_view.setPlaceholderText("Git diff findings will appear here...")
        box.addWidget(self.git_diff_view)

    def run_git_diff(self, staged: bool = False):
        folder = self.project or Path(".")
        is_repo, msg = is_git_repo(folder)
        if not is_repo:
            QMessageBox.warning(self, "Not a Git Repo", f"{folder} is not a Git repository: {msg}")
            return

        self.git_diff_view.setPlainText(f"Scanning git diff ({'staged' if staged else 'working tree'})...")
        self.diff_worker = GitDiffWorker(folder, staged=staged)
        self.diff_worker.completed.connect(self.git_diff_done)
        self.diff_worker.failed.connect(lambda err: self.git_diff_view.setPlainText(f"Git Diff Error: {err}"))
        self._start_worker(self.diff_worker)

    def git_diff_done(self, res: dict):
        if res.get("error"):
            self.git_diff_view.setPlainText(f"Git Diff Error: {res['error']}")
            return

        lines = [
            f"=== C.P.S. Git Diff Scan Report ===",
            f"Repo: {res['repo']}",
            f"Changed Files Count: {res['files_changed_count']}",
            f"Total Findings on Changed Files: {res['summary']['total']}",
            f"Newly Introduced in Diff: {res['summary']['new_in_diff']}",
            f"Pre-existing in File: {res['summary']['preexisting']}",
            "",
            "Newly Introduced Findings:"
        ]
        for f in res.get("new_in_diff", []):
            lines.append(f"  🚨 [{f.get('rule_id')}] {f.get('title')} at {f.get('file')}:{f.get('line')}")

        self.git_diff_view.setPlainText("\n".join(lines))

    # ------------------------------------------------------------------------
    # 9. Execution Sandbox
    # ------------------------------------------------------------------------
    def setup_executor(self, box: QVBoxLayout):
        top = QHBoxLayout()
        top.addWidget(QLabel("Execution Language:"))
        self.exec_lang = QComboBox()
        self.exec_lang.addItems(["Python", "JavaScript", "C", "C++", "Go", "Rust", "Java"])
        top.addWidget(self.exec_lang)

        top.addStretch(1)
        run_btn = QPushButton("▶️ Run in Isolated Sandbox")
        run_btn.setObjectName("PrimaryButton")
        run_btn.clicked.connect(self.run_sandbox_code)
        top.addWidget(run_btn)
        box.addLayout(top)

        splitter = QSplitter(Qt.Orientation.Vertical)

        in_widget = QWidget()
        in_l = QVBoxLayout(in_widget)
        in_l.setContentsMargins(0, 0, 0, 0)
        in_l.addWidget(QLabel("Source Code to Execute:"))
        self.exec_code_in = QTextEdit()
        self.exec_code_in.setPlainText('print("Hello from C.P.S. Isolated Sandbox!")\nfor i in range(5):\n    print(f"Count: {i}")')
        in_l.addWidget(self.exec_code_in)

        out_widget = QWidget()
        out_l = QVBoxLayout(out_widget)
        out_l.setContentsMargins(0, 0, 0, 0)
        out_l.addWidget(QLabel("Execution Output & Diagnostics:"))
        self.exec_console = QTextEdit()
        self.exec_console.setReadOnly(True)
        self.exec_console.setPlaceholderText("Standard Output and Standard Error will appear here separately...")
        out_l.addWidget(self.exec_console)

        splitter.addWidget(in_widget)
        splitter.addWidget(out_widget)
        box.addWidget(splitter, 1)

    def run_sandbox_code(self):
        code = self.exec_code_in.toPlainText()
        lang = self.exec_lang.currentText().lower()
        self.exec_console.setPlainText("Executing code in isolated sandbox (background worker)...")

        self.exec_worker = ExecWorker(code=code, language=lang, timeout=10)
        self.exec_worker.completed.connect(self.sandbox_code_done)
        self.exec_worker.failed.connect(lambda err: self.exec_console.setPlainText(f"Execution Error: {err}"))
        self._start_worker(self.exec_worker)

    def sandbox_code_done(self, res):
        out_lines = [
            f"=== Execution Completed ({res.duration_ms} ms, Exit Code: {res.exit_code}) ===",
        ]
        if res.stdout:
            out_lines.append(f"--- Standard Output ---\n{res.stdout}")
        if res.stderr:
            out_lines.append(f"--- Standard Error / Diagnostics ---\n{res.stderr}")
        if not res.stdout and not res.stderr:
            out_lines.append("(No output produced)")

        self.exec_console.setPlainText("\n\n".join(out_lines))

    # ------------------------------------------------------------------------
    # 10. Reports
    # ------------------------------------------------------------------------
    def setup_reports(self, box: QVBoxLayout):
        desc = QLabel("Export comprehensive security audit reports with automated secret redaction.")
        desc.setStyleSheet("color: #94a3b8;")
        box.addWidget(desc)

        btn_row = QHBoxLayout()
        for fmt in ("JSON", "CSV", "HTML", "Markdown"):
            b = QPushButton(f"Export {fmt}")
            b.clicked.connect(lambda checked=False, f=fmt.lower(): self.export_report(f))
            btn_row.addWidget(b)
        box.addLayout(btn_row)

        self.report_preview = QTextEdit()
        self.report_preview.setReadOnly(True)
        self.report_preview.setPlaceholderText("Report preview will appear here...")
        box.addWidget(self.report_preview, 1)

    def export_report(self, fmt: str):
        if not self.findings:
            QMessageBox.information(self, "No Scan", "Run a project scan before exporting a report.")
            return

        rep = build_report(self.findings, meta={"project": str(self.project) if self.project else ""})
        ext_map = {"json": "json", "csv": "csv", "html": "html", "markdown": "md", "md": "md"}
        render_map = {"json": to_json, "csv": to_csv, "html": to_html, "markdown": to_markdown, "md": to_markdown}

        rendered = render_map[fmt](rep)
        self.report_preview.setPlainText(rendered[:3000] + ("..." if len(rendered) > 3000 else ""))

        save_path, _ = QFileDialog.getSaveFileName(self, "Save Security Report", f"cps-audit-report.{ext_map[fmt]}")
        if save_path:
            Path(save_path).write_text(rendered, encoding="utf-8")
            QMessageBox.information(self, "Exported", f"Report saved to:\n{save_path}")

    # ------------------------------------------------------------------------
    # 11. Scan History
    # ------------------------------------------------------------------------
    def setup_history(self, box: QVBoxLayout):
        btn_row = QHBoxLayout()
        refresh_btn = QPushButton("🔄 Refresh History")
        refresh_btn.clicked.connect(self.refresh_history)
        clear_btn = QPushButton("🗑️ Clear All Scan History")
        clear_btn.setObjectName("DangerButton")
        clear_btn.clicked.connect(self.clear_history)

        btn_row.addWidget(refresh_btn)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch(1)
        box.addLayout(btn_row)

        self.history_list = QTextEdit()
        self.history_list.setReadOnly(True)
        box.addWidget(self.history_list, 1)
        self.refresh_history()

    def refresh_history(self):
        rows = storage.list_scans()
        if not rows:
            self.history_list.setPlainText("No scan records stored in local SQLite database.")
            return
        lines = ["Date & Time (UTC) | Files Scanned | Total Findings | Severity Breakdown", "-" * 80]
        for r in rows:
            lines.append(f"{r[0]} | {r[1]} files | {r[2]} findings | {r[3]}")
        self.history_list.setPlainText("\n".join(lines))

    def clear_history(self):
        conf = QMessageBox.question(self, "Confirm", "Permanently clear all scan history records?")
        if conf == QMessageBox.StandardButton.Yes:
            storage.clear_history()
            self.refresh_history()

    # ------------------------------------------------------------------------
    # 12. Model Manager
    # ------------------------------------------------------------------------
    def setup_model_manager(self, box: QVBoxLayout):
        desc = QLabel(
            "C.P.S. supports both 100% private local models and optional hosted providers.\n"
            "Configure endpoints, verify connectivity, and inspect model health."
        )
        desc.setStyleSheet("color: #94a3b8;")
        box.addWidget(desc)

        # Local Ollama section
        ollama_group = QGroupBox("Local Inference (Gemma 4 via Ollama)")
        o_l = QVBoxLayout(ollama_group)
        self.model_status_lbl = QLabel("Connection not tested yet.")
        o_l.addWidget(self.model_status_lbl)

        test_ollama_btn = QPushButton("🔍 Check Local Ollama & Gemma 4")
        test_ollama_btn.clicked.connect(self.check_local_model)
        o_l.addWidget(test_ollama_btn)
        box.addWidget(ollama_group)

        # Hosted providers test
        hosted_group = QGroupBox("Hosted Providers (Groq / Gemini / OpenRouter)")
        h_l = QVBoxLayout(hosted_group)
        test_groq_btn = QPushButton("Test Groq Connection")
        test_groq_btn.clicked.connect(lambda: self.test_prov("groq"))
        test_gemini_btn = QPushButton("Test Google Gemini Connection")
        test_gemini_btn.clicked.connect(lambda: self.test_prov("gemini"))
        test_openrouter_btn = QPushButton("Test OpenRouter Connection")
        test_openrouter_btn.clicked.connect(lambda: self.test_prov("openrouter"))

        h_l.addWidget(test_groq_btn)
        h_l.addWidget(test_gemini_btn)
        h_l.addWidget(test_openrouter_btn)
        box.addWidget(hosted_group)

        self.model_diagnostics = QTextEdit()
        self.model_diagnostics.setReadOnly(True)
        box.addWidget(self.model_diagnostics, 1)

    def check_local_model(self):
        self.model_status_lbl.setText("Checking local Ollama instance at http://localhost:11434...")
        self.model_worker = ModelCheckWorker("ollama")
        self.model_worker.completed.connect(self.local_model_done)
        self._start_worker(self.model_worker)

    def local_model_done(self, ok: bool, msg: str):
        status = "Ready: " if ok else "Notice: "
        self.model_status_lbl.setText(status + msg)
        self.model_diagnostics.append(f"[{'SUCCESS' if ok else 'CHECK'}] Ollama: {msg}")

    def test_prov(self, prov_name: str):
        self.model_diagnostics.append(f"Checking {prov_name} in background...")
        self.provider_worker = ModelCheckWorker(prov_name)
        self.provider_worker.completed.connect(
            lambda ok, msg, name=prov_name: self.provider_test_done(name, ok, msg)
        )
        self._start_worker(self.provider_worker)

    def provider_test_done(self, provider_name: str, ok: bool, msg: str):
        self.model_diagnostics.append(f"[{'OK' if ok else 'FAILED'}] {provider_name}: {msg}")

    # ------------------------------------------------------------------------
    # 13. Settings & Privacy
    # ------------------------------------------------------------------------
    def setup_settings(self, box: QVBoxLayout):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        c_layout = QVBoxLayout(container)

        info = (
            f"<b>Product:</b> {__product__} — AI Coding Companion<br>"
            f"<b>Version:</b> {__version__}<br>"
            f"<b>Local Data Directory:</b> {config.DATA_DIR.resolve()}<br><br>"
            f"<b>Privacy Principles:</b><br>"
            f"• Scanned source code is analyzed statically and NEVER transmitted without user action.<br>"
            f"• Source code is NEVER executed automatically.<br>"
            f"• Credentials, API keys, and passwords are redacted by default.<br>"
            f"• Local Ollama keeps all prompt context strictly on this computer."
        )
        l = QLabel(info)
        l.setStyleSheet("background: #111e31; border: 1px solid #1e324c; border-radius: 8px; padding: 14px; font-size: 10pt; line-height: 1.5;")
        c_layout.addWidget(l)

        # AI Configuration Group
        cfg_group = QGroupBox("Active AI Provider & Endpoints")
        g_l = QVBoxLayout(cfg_group)

        row_prov = QHBoxLayout()
        row_prov.addWidget(QLabel("Primary Provider:"))
        self.set_prov = QComboBox()
        self.set_prov.addItems(["Mock / Offline", "Ollama (Local Gemma 4)", "Groq", "Google Gemini", "OpenRouter"])
        saved_prov = storage.get_setting("provider", config.DEFAULT_PROVIDER)
        for idx in range(self.set_prov.count()):
            if saved_prov in self.set_prov.itemText(idx).lower():
                self.set_prov.setCurrentIndex(idx)
                break
        row_prov.addWidget(self.set_prov, 1)
        g_l.addLayout(row_prov)

        row_host = QHBoxLayout()
        row_host.addWidget(QLabel("Ollama Host URL:"))
        self.set_host = QLineEdit()
        self.set_host.setText(storage.get_setting("ollama_host", config.DEFAULT_OLLAMA_HOST))
        row_host.addWidget(self.set_host, 1)
        g_l.addLayout(row_host)

        row_groq = QHBoxLayout()
        row_groq.addWidget(QLabel("Groq API Key:"))
        self.set_groq_key = QLineEdit()
        self.set_groq_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.set_groq_key.setText(storage.get_setting("groq_key", config.groq_api_key()))
        row_groq.addWidget(self.set_groq_key, 1)
        g_l.addLayout(row_groq)

        row_gemini = QHBoxLayout()
        row_gemini.addWidget(QLabel("Gemini API Key:"))
        self.set_gemini_key = QLineEdit()
        self.set_gemini_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.set_gemini_key.setText(storage.get_setting("gemini_key", config.gemini_api_key()))
        row_gemini.addWidget(self.set_gemini_key, 1)
        g_l.addLayout(row_gemini)

        row_or = QHBoxLayout()
        row_or.addWidget(QLabel("OpenRouter Key:"))
        self.set_openrouter_key = QLineEdit()
        self.set_openrouter_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.set_openrouter_key.setText(storage.get_setting("openrouter_key", config.openrouter_api_key()))
        row_or.addWidget(self.set_openrouter_key, 1)
        g_l.addLayout(row_or)

        save_settings_btn = QPushButton("💾 Save AI Settings")
        save_settings_btn.setObjectName("PrimaryButton")
        save_settings_btn.clicked.connect(self.save_user_settings)
        g_l.addWidget(save_settings_btn)

        c_layout.addWidget(cfg_group)

        # Data Management Group
        data_group = QGroupBox("Local Data & Privacy Management")
        d_l = QVBoxLayout(data_group)
        d_lbl = QLabel("Permanently purge all scan history records, chat conversations, and stored local settings.")
        d_lbl.setStyleSheet("color: #94a3b8;")
        d_l.addWidget(d_lbl)

        clear_all_btn = QPushButton("🗑️ Clear All User Data & Reset Settings")
        clear_all_btn.setObjectName("DangerButton")
        clear_all_btn.clicked.connect(self.clear_all_app_data)
        d_l.addWidget(clear_all_btn)

        c_layout.addWidget(data_group)
        c_layout.addStretch(1)

        scroll.setWidget(container)
        box.addWidget(scroll, 1)

    def save_user_settings(self):
        prov_map = {
            "Mock / Offline": "mock",
            "Ollama (Local Gemma 4)": "ollama",
            "Groq": "groq",
            "Google Gemini": "gemini",
            "OpenRouter": "openrouter",
        }
        p_name = prov_map.get(self.set_prov.currentText(), "mock")
        host = self.set_host.text().strip()
        groq_k = self.set_groq_key.text().strip()
        gemini_k = self.set_gemini_key.text().strip()
        or_k = self.set_openrouter_key.text().strip()

        storage.save_setting("provider", p_name)
        storage.save_setting("ollama_host", host)
        if groq_k:
            storage.save_setting("groq_key", groq_k)
            import os
            os.environ["GROQ_API_KEY"] = groq_k
        if gemini_k:
            storage.save_setting("gemini_key", gemini_k)
            import os
            os.environ["GEMINI_API_KEY"] = gemini_k
        if or_k:
            storage.save_setting("openrouter_key", or_k)
            import os
            os.environ["OPENROUTER_API_KEY"] = or_k

        # Also write to backend settings json
        from backend.server import save_settings
        save_settings({
            "provider": p_name,
            "ollama_host": host,
            "apiKey": groq_k or gemini_k or or_k or ""
        })

        QMessageBox.information(self, "Settings Saved", "AI configuration and provider endpoints saved successfully.")

    def clear_all_app_data(self):
        conf = QMessageBox.question(
            self,
            "Confirm Data Purge",
            "Permanently erase all scan records, chat history, and stored settings?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if conf == QMessageBox.StandardButton.Yes:
            storage.clear_all_data()
            self.refresh_history()
            self.clear_chat()
            QMessageBox.information(self, "Data Purged", "All local application data has been safely cleared.")

    def show_page(self, name: str):
        if name in self.PAGES:
            self.stack.setCurrentIndex(self.PAGES.index(name))
            for btn in self.findChildren(QPushButton, "NavButton"):
                btn.setChecked(btn.text() == name)


def main() -> int:
    self_check = "--self-check" in sys.argv
    try:
        app = QApplication(sys.argv)
        app.setStyle("Fusion")
        win = CPSMainWindow()
    except Exception as exc:
        if self_check:
            print(f"C.P.S. self-check failed: {type(exc).__name__}: {exc}")
            return 2
        raise

    if self_check:
        valid = win.stack.count() == len(win.PAGES)
        win.close()
        print("C.P.S. self-check passed" if valid else "C.P.S. self-check failed")
        return 0 if valid else 2

    win.show()
    return app.exec()


# Backward compatibility alias
VulnQuestWindow = CPSMainWindow


if __name__ == "__main__":
    raise SystemExit(main())
