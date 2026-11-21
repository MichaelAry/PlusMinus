"""Native C++ Test Inspector with searchable tree and per-method history.

The structure summary is lexical, not a Clang AST or source coverage proof.
Actual test outcomes always come from the portable native test runner.
"""
from __future__ import annotations

import re
from pathlib import Path
from PySide6.QtCore import Qt, Signal, QSortFilterProxyModel
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QTreeView, QPlainTextEdit, QTabWidget, QSplitter, QTableWidget,
    QTableWidgetItem, QHeaderView,
)
from highlighting import CppHighlighter


def extract_method(source, identifier):
    """Return a bounded C++ method preview and approximate structural metrics."""
    method = identifier.rsplit(".", 1)[-1]
    klass = identifier.split(".", 1)[0]
    matches = list(re.finditer(r"\bTEST_METHOD\s*\(\s*" + re.escape(method) + r"\s*\)", source))
    match = next(
        (m for m in matches if
         (re.findall(r"\bTEST_CLASS\s*\(\s*(\w+)\s*\)", source[:m.start()])
          or [""])[-1] == klass), None)
    if match is None:
        return "", {"assertions": 0, "api_calls": [], "operations": []}
    open_brace = source.find("{", match.end())
    if open_brace < 0:
        return "", {"assertions": 0, "api_calls": [], "operations": []}
    # Scan balanced braces while ignoring strings and comments.
    depth = 0
    end = len(source)
    state = "code"
    i = open_brace
    while i < len(source):
        ch = source[i]
        nxt = source[i+1] if i+1 < len(source) else ""
        if state == "line":
            if ch == "\n":
                state = "code"
        elif state == "block":
            if ch == "*" and nxt == "/":
                state = "code"
                i += 1
        elif state in ('"', "'"):
            if ch == "\\":
                i += 1
            elif ch == state:
                state = "code"
        elif ch in ('"', "'"):
            state = ch
        elif ch == "/" and nxt == "/":
            state = "line"
            i += 1
        elif ch == "/" and nxt == "*":
            state = "block"
            i += 1
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
        i += 1
    fragment = source[match.start():end]
    assertions = re.findall(r"\bAssert::(\w+)\s*\(", fragment)
    api = sorted({name for name in ("evaluate", "compileToCommands",
                   "getOutput", "runAndGetVars", "getArrayVar")
                  if re.search(r"\b" + name + r"\s*\(", fragment)})
    operations = sorted({op for op in ("go", "sync", "lock", "unlock", "while",
                       "if", "print", "pow", "resize", "len")
                         if re.search(r"\b" + op + r"\b", fragment)})
    return fragment, {"assertions": len(assertions),
                      "assert_types": sorted(set(assertions)),
                      "api_calls": api, "operations": operations}


class TestAnalysisPanel(QWidget):
    testRequested = Signal(str)
    openSourceRequested = Signal(str)
    compareRequested = Signal()

    def __init__(self, root, history, parent=None):
        super().__init__(parent)
        self.root = Path(root)
        self.history = history
        self.cases = []
        self.outcomes = {}
        self.items = {}
        layout = QVBoxLayout(self)
        heading = QHBoxLayout()
        title = QLabel("NATIVE C++  /  TEST ANALYSIS")
        title.setObjectName("researchEyebrow")
        heading.addWidget(title, 1)
        for label, action in (
            ("Run method", self.run_selected),
            ("Open C++", self.open_selected),
            ("Compare baseline", self.compareRequested.emit),
        ):
            btn = QPushButton(label)
            btn.clicked.connect(action)
            heading.addWidget(btn)
        layout.addLayout(heading)
        split = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget()
        lc = QVBoxLayout(left)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter by class, method or group…")
        lc.addWidget(self.search)
        self.model = QStandardItemModel(self)
        self.model.setHorizontalHeaderLabels(["Native tests", "Status", "Group"])
        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setRecursiveFilteringEnabled(True)
        self.proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.proxy.setFilterKeyColumn(0)
        self.search.textChanged.connect(self.proxy.setFilterFixedString)
        self.tree = QTreeView()
        self.tree.setModel(self.proxy)
        self.tree.setRootIsDecorated(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.setUniformRowHeights(True)
        self.tree.selectionModel().currentChanged.connect(self.show_selected)
        lc.addWidget(self.tree, 1)
        self.counts = QLabel("No native methods discovered")
        lc.addWidget(self.counts)
        split.addWidget(left)

        inspect = QTabWidget()
        source_page = QWidget()
        source_layout = QVBoxLayout(source_page)
        self.metadata = QLabel("Choose a method to inspect its source.")
        self.metadata.setWordWrap(True)
        source_layout.addWidget(self.metadata)
        self.source = QPlainTextEdit()
        self.source.setReadOnly(True)
        self._cpp_syntax = CppHighlighter(self.source.document())
        source_layout.addWidget(self.source, 1)
        inspect.addTab(source_page, "Source / Assertions")
        self.history_table = QTableWidget(0, 5)
        self.history_table.setHorizontalHeaderLabels(
            ["Session", "Git SHA", "Status", "C++ ms", "Wall ms"])
        self.history_table.verticalHeader().hide()
        self.history_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        inspect.addTab(self.history_table, "History")
        self.failure_details = QPlainTextEdit()
        self.failure_details.setReadOnly(True)
        inspect.addTab(self.failure_details, "Last failure")
        self.coverage = QLabel(
            "Source coverage is not available in this build.\n\n"
            "Exact C++ line/branch coverage requires instrumented native binaries "
            "and LLVM/gcov report ingestion. Static mentions are not coverage.")
        self.coverage.setWordWrap(True)
        self.coverage.setAlignment(Qt.AlignmentFlag.AlignTop)
        inspect.addTab(self.coverage, "Coverage")
        split.addWidget(inspect)
        split.setSizes([330, 850])
        layout.addWidget(split, 1)
        self.inspector_tabs = inspect

    def set_cases(self, cases):
        self.cases = list(cases)
        self.items.clear()
        self.model.removeRows(0, self.model.rowCount())
        buckets = {}
        for case in sorted(self.cases, key=lambda c: (c.get("group", ""), c["id"])):
            group = case.get("group", "other")
            if group not in buckets:
                parent = QStandardItem(group.upper())
                parent.setEditable(False)
                buckets[group] = parent
                self.model.appendRow([parent, QStandardItem(""), QStandardItem("")])
            test = QStandardItem(case["id"].split(".", 1)[-1])
            test.setData(case["id"], Qt.ItemDataRole.UserRole)
            test.setEditable(False)
            status = QStandardItem(self.outcomes.get(case["id"], {}).get("status", "NOT RUN"))
            status.setEditable(False)
            category = QStandardItem(group)
            category.setEditable(False)
            buckets[group].appendRow([test, status, category])
            self.items[case["id"]] = status
        self.tree.expandAll()
        self.counts.setText(f"{len(self.cases)} registered C++ methods · lexical inspection")
        self.tree.resizeColumnToContents(0)

    def set_result(self, result):
        self.outcomes[result["id"]] = result
        item = self.items.get(result["id"])
        if item is not None:
            item.setText(result["status"])
        if self.selected_id() == result["id"]:
            self.show_selected()

    def selected_id(self):
        index = self.tree.currentIndex()
        if not index.isValid():
            return None
        item = self.model.itemFromIndex(self.proxy.mapToSource(index.siblingAtColumn(0)))
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def run_selected(self):
        identifier = self.selected_id()
        if identifier:
            self.testRequested.emit(identifier)

    def open_selected(self):
        identifier = self.selected_id()
        if identifier:
            self.openSourceRequested.emit(identifier)

    def show_selected(self, *_):
        identifier = self.selected_id()
        if not identifier:
            return
        case = next((value for value in self.cases if value["id"] == identifier), None)
        if case is None:
            return
        path = self.root / case.get("source", "")
        if path.is_file():
            try:
                fragment, meta = extract_method(
                    path.read_text(encoding="utf-8-sig"), identifier)
            except (OSError, UnicodeError):
                fragment, meta = "", {"assertions": 0, "api_calls": [], "operations": []}
            self.source.setPlainText(fragment or "The selected method was not found.")
            self.metadata.setText(
                f"{identifier}\n{case.get('source', '')}\n"
                f"Assert calls: {meta['assertions']} · Interpreter API: "
                f"{', '.join(meta['api_calls']) or 'not detected'}\n"
                f"Operations mentioned: {', '.join(meta['operations']) or 'none'}\n"
                "Lexical summary, not Clang AST analysis.")
        else:
            self.source.setPlainText("C++ source files are not included in this build.")
            self.metadata.setText(identifier)
        result = self.outcomes.get(identifier)
        self.failure_details.setPlainText(
            (f"{result.get('status', '')}\n\n{result.get('error', '')}"
             if result is not None else
             "No result for this method in the current session."))
        self.history_table.setRowCount(0)
        try:
            sessions = self.history.recent(40)
            rows = []
            for session in sessions:
                outcome = self.history.results(session["id"]).get(identifier)
                if outcome:
                    rows.append([
                        session["id"], str(session.get("git_sha", ""))[:9],
                        outcome["status"], (
                            f"{outcome['test_ms']:.3f}" if outcome.get("test_ms") is not None else "—"),
                        f"{outcome['elapsed_ms']:.3f}"])
            self.history_table.setRowCount(len(rows))
            for row, values in enumerate(rows):
                for col, value in enumerate(values):
                    self.history_table.setItem(row, col, QTableWidgetItem(str(value)))
        except (OSError, ValueError) as exc:
            self.failure_details.setPlainText(f"History unavailable: {exc}")
