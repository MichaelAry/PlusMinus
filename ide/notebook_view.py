"""Notebook editor using Jupyter v4 files and isolated PlusMinus execution.

No persistent state is shared between code cells. Each run spawns the
existing native interpreter in a background thread, never the Qt UI thread.
"""
from __future__ import annotations

import copy
import os
import tempfile
import threading
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel, QMessageBox, QPlainTextEdit,
    QPushButton, QScrollArea, QTextBrowser, QVBoxLayout, QWidget,
)

from engine import execute, find_runner
from highlighting import PlusMinusHighlighter
from notebook_format import (
    error_output, load_notebook, make_cell, new_notebook, serialize, source_text,
    stream_output,
)


class CellEditor(QPlainTextEdit):
    """Run current cell with Shift+Enter or Ctrl+Enter, as in Jupyter."""
    executeRequested = Signal()

    def keyPressEvent(self, event):
        if (event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and
                event.modifiers() & (
                    Qt.KeyboardModifier.ShiftModifier |
                    Qt.KeyboardModifier.ControlModifier)):
            self.executeRequested.emit()
            return
        super().keyPressEvent(event)


class CellJob(QThread):
    completed = Signal(dict)

    def __init__(self, runner, source, cancel, parent=None):
        super().__init__(parent)
        self.runner, self.source, self.cancel = runner, source, cancel

    def run(self):
        try:
            result = execute(self.runner, self.source, "run", 25.0, self.cancel)
        except Exception as exc:
            result = {"ok": False, "error": str(exc), "output": ""}
        self.completed.emit(result)


class NotebookCell(QFrame):
    changed = Signal()
    runRequested = Signal(object)
    moveRequested = Signal(object, int)
    deleteRequested = Signal(object)

    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.setObjectName("notebookCell")
        self.data = copy.deepcopy(data)
        self.kind = self.data["cell_type"]
        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        self.title = QLabel()
        self.title.setObjectName("notebookCellTitle")
        header.addWidget(self.title, 1)
        self.run_button = QPushButton("Run ▶" if self.kind == "code" else "Preview")
        self.run_button.clicked.connect(self._clicked)
        header.addWidget(self.run_button)
        for name, direction in (("↑", -1), ("↓", 1)):
            control = QPushButton(name)
            control.setToolTip("Move cell")
            control.clicked.connect(lambda _=False, n=direction: self.moveRequested.emit(self, n))
            header.addWidget(control)
        remove = QPushButton("×")
        remove.setToolTip("Delete cell")
        remove.clicked.connect(lambda: self.deleteRequested.emit(self))
        header.addWidget(remove)
        layout.addLayout(header)
        self.editor = CellEditor()
        self.editor.executeRequested.connect(self._clicked)
        self.editor.setPlaceholderText(
            "PlusMinus code" if self.kind == "code" else "Markdown text")
        self.editor.setPlainText(source_text(self.data.get("source", "")))
        self.editor.setMinimumHeight(110)
        self.editor.setMaximumHeight(280)
        if self.kind == "code":
            self._highlighter = PlusMinusHighlighter(self.editor.document())
        layout.addWidget(self.editor)
        self.preview = QTextBrowser()
        self.preview.setOpenExternalLinks(False)
        self.preview.setVisible(False)
        layout.addWidget(self.preview)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setMaximumHeight(145)
        layout.addWidget(self.output)
        self.stats = QLabel()
        self.stats.setObjectName("muted")
        self.stats.setWordWrap(True)
        layout.addWidget(self.stats)
        self.editor.textChanged.connect(self._edited)
        self.show_saved_output()
        self.update_title()

    def update_title(self):
        if self.kind == "code":
            count = self.data.get("execution_count")
            self.title.setText("CODE  /  In [" + (str(count) if count is not None else " ") + "]")
        else:
            self.title.setText("MARKDOWN")

    def _edited(self):
        if self.kind == "code" and self.data.get("execution_count") is not None:
            self.stats.setText("Code changed — previous output and timings may be stale.")
        self.changed.emit()

    def _clicked(self):
        if self.kind == "code":
            self.runRequested.emit(self)
        else:
            visible = not self.preview.isVisible()
            if visible:
                self.preview.setMarkdown(self.editor.toPlainText())
            self.preview.setVisible(visible)
            self.run_button.setText("Edit" if visible else "Preview")

    def snapshot(self):
        data = copy.deepcopy(self.data)
        data["source"] = self.editor.toPlainText()
        return data

    def show_saved_output(self):
        outputs = self.data.get("outputs", []) if self.kind == "code" else []
        lines = []
        for output in outputs:
            if not isinstance(output, dict):
                continue
            kind = output.get("output_type")
            if kind == "stream":
                lines.append(source_text(output.get("text", "")))
            elif kind == "error":
                lines.append(str(output.get("evalue", "Execution error")))
            elif kind in ("execute_result", "display_data"):
                lines.append(source_text(output.get("data", {}).get("text/plain", "")))
        text = "\n".join(lines).strip()
        if self.kind == "code" and self.data.get("execution_count") is not None and not text:
            text = "(Completed without stdout or a return value.)"
        self.output.setPlainText(text)
        self.output.setVisible(bool(text))
        record = self.data.get("metadata", {}).get("plusminus_run", {})
        if record:
            from execution_report import _measured
            metrics = record.get("metrics") or {}
            self.stats.setText(
                f"{'PASS' if record.get('ok') else 'FAIL'} · "
                f"Wall {_measured(record.get('wall_ms'), 'ms')} · "
                f"Compile {_measured(metrics.get('compile_ms'), 'ms')} · "
                f"VM {_measured(metrics.get('execute_ms'), 'ms')} · "
                f"Sampled RSS {_measured(metrics.get('peak_rss_mb'), 'MB')}")
        else:
            self.stats.clear()

    def set_report(self, report, counter):
        self.data["execution_count"] = counter
        outputs = []
        if report.get("output"):
            outputs.append(stream_output(report["output"]))
        if not report.get("ok"):
            outputs.append(error_output(report.get("error") or "Execution failed"))
        result = report.get("result")
        if report.get("ok") and result is not None and result != "":
            outputs.append({
                "output_type": "execute_result",
                "execution_count": counter,
                "data": {"text/plain": str(result)}, "metadata": {},
            })
        self.data["outputs"] = outputs
        metrics = report.get("metrics") or {}
        self.data.setdefault("metadata", {})["plusminus_run"] = {
            "ok": bool(report.get("ok")), "wall_ms": report.get("ms"),
            "metrics": {key: value for key, value in metrics.items()
                        if key in ("compile_ms", "execute_ms", "cpu_ms",
                                   "peak_rss_mb", "peak_threads")},
        }
        self.show_saved_output()
        self.update_title()


class NotebookView(QWidget):
    statusChanged = Signal(str)

    def __init__(self, root, parent=None):
        super().__init__(parent)
        self.root = Path(root)
        self.path = None
        self.notebook = new_notebook()
        self.cells = []
        self.dirty = False
        self.execution_count = 0
        self.worker = None
        self.cancel = threading.Event()
        self.run_queue = []
        self.active_cell = None

        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        self.document_name = QLabel("UNTITLED NOTEBOOK")
        self.document_name.setObjectName("researchEyebrow")
        toolbar.addWidget(self.document_name, 1)
        for name, callback in (
            ("New", self.new_file), ("Open", self.open_file),
            ("Save", self.save_file),
            ("+ Code", lambda: self.add_cell("code")),
            ("+ Markdown", lambda: self.add_cell("markdown")),
            ("Run all", self.run_all), ("Interrupt", self.interrupt),
        ):
            b = QPushButton(name)
            if name == "Run all":
                b.setObjectName("primary")
            b.clicked.connect(callback)
            toolbar.addWidget(b)
        layout.addLayout(toolbar)
        warning = QLabel(
            "ISOLATED EXECUTION  ·  Every code cell starts a new PlusMinus process. "
            "Variables and functions are not shared between cells.")
        warning.setObjectName("kernelWarning")
        warning.setWordWrap(True)
        layout.addWidget(warning)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.container = QWidget()
        self.cell_layout = QVBoxLayout(self.container)
        self.cell_layout.setContentsMargins(16, 16, 16, 16)
        self.cell_layout.setSpacing(12)
        self.cell_layout.addStretch(1)
        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll, 1)
        self.status = QLabel("Kernel: isolated · idle")
        layout.addWidget(self.status)
        self.add_cell("code", "print(2 + 2);", mark_dirty=False)

    def _rename(self):
        self.document_name.setText(
            (self.path.name if self.path else "UNTITLED NOTEBOOK")
            + ("  ●" if self.dirty else ""))

    def _changed(self):
        self.dirty = True
        self._rename()

    def add_cell(self, kind, source="", mark_dirty=True, data=None):
        cell = NotebookCell(data or make_cell(kind, source), self.container)
        cell.changed.connect(self._changed)
        cell.runRequested.connect(self.run_cell)
        cell.moveRequested.connect(self.move_cell)
        cell.deleteRequested.connect(self.delete_cell)
        self.cells.append(cell)
        self.cell_layout.insertWidget(len(self.cells) - 1, cell)
        if mark_dirty:
            self._changed()
        return cell

    def delete_cell(self, cell):
        if self.worker and self.worker.isRunning():
            self.status.setText("Wait for execution to finish before deleting cells.")
            return
        self.cells.remove(cell)
        self.cell_layout.removeWidget(cell)
        cell.deleteLater()
        self._changed()

    def move_cell(self, cell, direction):
        if self.worker and self.worker.isRunning():
            return
        index = self.cells.index(cell)
        target = index + direction
        if target < 0 or target >= len(self.cells):
            return
        self.cells[index], self.cells[target] = self.cells[target], self.cells[index]
        self.cell_layout.removeWidget(cell)
        self.cell_layout.insertWidget(target, cell)
        self._changed()

    def snapshot(self):
        result = copy.deepcopy(self.notebook)
        result["cells"] = [cell.snapshot() for cell in self.cells]
        return result

    def maybe_close(self):
        # Do not interrupt an execution if the user declines closing.
        if self.dirty:
            answer = QMessageBox.question(
                self, "Notebook changes", "Save notebook changes?",
                QMessageBox.StandardButton.Save |
                QMessageBox.StandardButton.Discard |
                QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save)
            if answer == QMessageBox.StandardButton.Cancel:
                return False
            if answer == QMessageBox.StandardButton.Save and not self.save_file():
                return False
        self.interrupt()
        if self.worker and self.worker.isRunning():
            if not self.worker.wait(6500):
                QMessageBox.warning(self, "Notebook is executing",
                                    "The native kernel is still shutting down.")
                return False
        return True

    def new_file(self):
        if not self.maybe_close():
            return
        self._load(new_notebook(), None)
        self.add_cell("code", mark_dirty=False)

    def _load(self, data, path):
        for cell in self.cells:
            self.cell_layout.removeWidget(cell)
            cell.deleteLater()
        self.cells.clear()
        self.notebook = data
        self.path = path
        self.execution_count = max(
            (cell.get("execution_count") or 0 for cell in data["cells"]
             if cell["cell_type"] == "code"), default=0)
        for entry in data["cells"]:
            self.add_cell(entry["cell_type"], data=entry, mark_dirty=False)
        if not self.cells:
            self.add_cell("code", mark_dirty=False)
        self.dirty = False
        self._rename()

    def open_file(self, path=None):
        if not self.maybe_close():
            return
        if not isinstance(path, (str, Path)):
            filename, _ = QFileDialog.getOpenFileName(
                self, "Open Jupyter notebook", str(self.root),
                "Jupyter Notebooks (*.ipynb)")
            if not filename:
                return
            path = filename
        try:
            path = Path(path).resolve()
            data = load_notebook(path)
            self._load(data, path)
        except (OSError, ValueError, UnicodeError) as exc:
            QMessageBox.warning(self, "Cannot open notebook", str(exc))

    def save_file(self):
        path = self.path
        if path is None:
            filename, _ = QFileDialog.getSaveFileName(
                self, "Save Jupyter notebook",
                str(self.root / "experiment.ipynb"), "Jupyter Notebooks (*.ipynb)")
            if not filename:
                return False
            path = Path(filename)
            if path.suffix.lower() != ".ipynb":
                path = path.with_suffix(".ipynb")
        tmp = None
        try:
            content = serialize(self.snapshot())
            with tempfile.NamedTemporaryFile("w", encoding="utf-8",
                                             dir=str(path.parent), suffix=".tmp",
                                             delete=False) as fp:
                tmp = Path(fp.name)
                fp.write(content)
            os.replace(tmp, path)
            self.path = path
            self.dirty = False
            self._rename()
            self.statusChanged.emit(f"Saved notebook: {path.name}")
            return True
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Cannot save notebook", str(exc))
            return False
        finally:
            if tmp is not None:
                tmp.unlink(missing_ok=True)

    def run_all(self):
        if self.worker and self.worker.isRunning():
            return
        self.run_queue = [cell for cell in self.cells
                          if cell.kind == "code" and cell.editor.toPlainText().strip()]
        self._next()

    def run_focused_cell(self):
        """F5 targets the current code editor, never a hidden source document."""
        focus = QApplication.focusWidget()
        cell = next((item for item in self.cells
                     if item.editor is focus), None)
        if cell is None or cell.kind != "code":
            cell = next((item for item in reversed(self.cells)
                         if item.kind == "code" and item.editor.toPlainText().strip()), None)
        if cell:
            self.run_cell(cell)
        else:
            self.status.setText("Enter PlusMinus code in a cell before running.")

    def run_cell(self, cell):
        if self.worker and self.worker.isRunning():
            self.status.setText("An execution is already running.")
            return
        if cell.kind != "code" or not cell.editor.toPlainText().strip():
            self.status.setText("Empty code cell — enter PlusMinus source first.")
            return
        self.run_queue = [cell]
        self._next()

    def _next(self):
        if not self.run_queue:
            self.status.setText("Kernel: isolated · idle")
            return
        runner = find_runner()
        if runner is None:
            self.run_queue.clear()
            self.status.setText("C++ runner unavailable: rebuild the project first.")
            return
        self.active_cell = self.run_queue.pop(0)
        self.cancel.clear()
        self.status.setText("Kernel: isolated · executing a code cell…")
        self.active_cell.run_button.setEnabled(False)
        self.executed_source = self.active_cell.editor.toPlainText()
        self.worker = CellJob(runner, self.executed_source,
                              self.cancel, self)
        self.worker.completed.connect(self._result)
        self.worker.finished.connect(self._finished)
        self.worker.start()

    def _result(self, report):
        cell = self.active_cell
        if cell is None:
            return
        self.execution_count += 1
        cell.set_report(report, self.execution_count)
        if cell.editor.toPlainText() != self.executed_source:
            cell.stats.setText(
                "Code changed during execution — results belong to the earlier source.")
        cell.run_button.setEnabled(True)
        # Each completed final code cell gets exactly one following blank cell.
        # Re-running a cell must not keep generating empty cells.
        if (not self.cancel.is_set() and cell in self.cells and
                not any(next_cell.kind == "code"
                        for next_cell in self.cells[self.cells.index(cell) + 1:])):
            new_cell = self.add_cell("code", mark_dirty=False)
            new_cell.editor.setFocus()
            self.scroll.ensureWidgetVisible(new_cell, 0, 24)
        self._changed()
        ok = bool(report.get("ok"))
        self.statusChanged.emit("Notebook cell passed" if ok else
                                "Notebook cell failed: " + str(report.get("error", ""))[:160])
        if not ok:
            self.run_queue.clear()

    def _finished(self):
        job = self.worker
        self.worker = None
        self.active_cell = None
        if job is not None:
            job.deleteLater()
        if not self.cancel.is_set():
            self._next()
        else:
            self.status.setText("Kernel: isolated · interrupted")

    def interrupt(self):
        self.cancel.set()
        self.run_queue.clear()
        if self.worker and self.worker.isRunning():
            self.status.setText("Interrupt requested…")
