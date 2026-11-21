#!/usr/bin/env python3
"""PlusMinus Studio 2.0: Qt desktop IDE, testing and runtime observability.

The C++ interpreter is always executed out-of-process. Qt is confined to the
main thread; background jobs emit immutable results through Qt signals.
"""
from __future__ import annotations

import csv
import json
import os
import re
import subprocess
import statistics
import sys
import threading
from collections import Counter
from pathlib import Path

from PySide6.QtCore import Qt, QThread, QTimer, QSettings, Signal, QPointF, QRectF
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QSyntaxHighlighter, QTextCharFormat, QTextCursor, QAction
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QPlainTextEdit, QSplitter, QTableWidget, QTableWidgetItem,
    QHeaderView, QStackedWidget, QListWidget, QListWidgetItem, QTabWidget,
    QFileDialog, QMessageBox, QSpinBox, QProgressBar, QInputDialog, QComboBox,
    QTextEdit, QAbstractItemView, QCheckBox,
)

from analytics import (BUILTIN_TESTS, HistoryStore, analyze_bytecode, analyze_source,
                       judge_test, summarize_benchmark)
from engine import execute, find_runner
from internals import keyword_at, editable_checkout
from language_window import LanguageSourceWindow
from workspace import WorkspaceTabs
from documents import DocumentTabs
from native_test_view import NativeTestPanel
from highlighting import CppHighlighter
from source_diagnostics import analyze_diagnostics
from native_tests import NativeHistory, find_native_runner, discover_native_tests, run_native_case
from highlighting import PlusMinusHighlighter

try:
    import psutil
except ImportError:
    psutil = None

ROOT = Path(__file__).resolve().parents[1]
PREFS = Path.home() / '.plusminus'
EXAMPLE = '''// PlusMinus / computation sample
x = 0;
while (x < 5) {
    print(x * x);
    x = x + 1;
}
'''
COLORS = dict(bg='#0e1118', surface='#171c26', panel='#1d2430', stroke='#303949',
              text='#e3e9f4', sub='#909bac', muted='#637083', accent='#b9c9e7',
              good='#8fd2b4', bad='#ec9d9d', gold='#d8c28c')

STYLE = '''
QWidget { background: #0e1118; color: #e3e9f4; font: 10pt "Segoe UI"; }
QMainWindow { background: #0e1118; }
QFrame#panel { background: #171c26; border: 1px solid #303949; border-radius: 11px; }
QFrame#rail { background: #121721; border-right: 1px solid #303949; }
QLabel#section { font-size: 16pt; font-weight: 700; color: #e3e9f4; }
QLabel#muted { color: #909bac; }
QLabel#metric { font-size: 21pt; font-weight: 700; color: #e3e9f4; }
QPushButton { background: #242e3d; border: 1px solid #39465a; border-radius: 7px;
              padding: 8px 13px; font-weight: 600; }
QPushButton:hover { background: #303e53; border-color: #667a99; }
QPushButton:disabled { color: #6d7889; background: #1b212b; }
QPushButton#primary { background: #b9c9e7; color: #101722; border-color: #b9c9e7; }
QPushButton#primary:hover { background: #d4e0f4; }
QPlainTextEdit, QTextEdit, QTableWidget, QComboBox, QSpinBox {
  background: #121821; color: #e3e9f4; border: 1px solid #303949;
  border-radius: 6px; selection-background-color: #394b65; }
QPlainTextEdit { padding: 10px; font-family: "Cascadia Code", "Consolas", monospace; font-size: 10pt; }
QTableWidget { gridline-color: #283241; alternate-background-color: #19202b; }
QHeaderView::section { background: #202937; color: #a9b9ce; padding: 7px;
                       border: 0; border-bottom: 1px solid #303949; }
QListWidget { background: transparent; border: none; outline: none; }
QListWidget::item { padding: 13px 14px; margin: 2px 6px; border-radius: 7px; color: #99a8bb; }
QListWidget::item:selected { color: #e7efff; background: #303d50; }
QListWidget::item:hover { background: #232d3b; }
QTabWidget::pane { border: 1px solid #303949; background: #171c26; }
QTabBar::tab { padding: 8px 15px; background: #1a222d; color: #98a6b9; }
QTabBar::tab:selected { color: #e3e9f4; background: #303949; }
QProgressBar { background: #202938; border: 0; border-radius: 5px; height: 10px; }
QProgressBar::chunk { background: #8fd2b4; border-radius: 5px; }
QStatusBar { background: #161d27; color: #98a6b9; border-top: 1px solid #303949; }
QSplitter::handle { background: #303949; }
QCheckBox { spacing: 7px; }
'''


def label(text='', *, style=None):
    obj = QLabel(str(text))
    if style:
        obj.setObjectName(style)
    obj.setWordWrap(True)
    return obj


def button(text, callback=None, *, primary=False):
    obj = QPushButton(text)
    if primary:
        obj.setObjectName('primary')
    if callback:
        obj.clicked.connect(callback)
    return obj


def panel(layout='vertical'):
    frame = QFrame()
    frame.setObjectName('panel')
    content = QHBoxLayout(frame) if layout == 'horizontal' else QVBoxLayout(frame)
    content.setContentsMargins(15, 13, 15, 13)
    content.setSpacing(10)
    return frame, content


def page(title, subtitle):
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(21, 18, 21, 18)
    layout.setSpacing(14)
    layout.addWidget(label(title, style='section'))
    layout.addWidget(label(subtitle, style='muted'))
    return widget, layout


def table(columns):
    result = QTableWidget(0, len(columns))
    result.setHorizontalHeaderLabels(columns)
    result.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    result.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    result.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    result.setAlternatingRowColors(True)
    result.setSortingEnabled(False)
    result.verticalHeader().hide()
    result.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    return result


def fill_table(widget, rows):
    widget.setRowCount(len(rows))
    for row_index, row in enumerate(rows):
        for col_index, value in enumerate(row):
            cell = QTableWidgetItem(str(value))
            if value in ('PASS', 'OK'):
                cell.setForeground(QColor(COLORS['good']))
            elif value in ('FAIL', 'ERROR'):
                cell.setForeground(QColor(COLORS['bad']))
            widget.setItem(row_index, col_index, cell)


class Plot(QWidget):
    """Dependency-free, antialiased Qt line chart; data comes from measured samples."""
    def __init__(self, title='Timeline', parent=None):
        super().__init__(parent)
        self.title = title
        self.series = []
        self.setMinimumHeight(165)

    def set_series(self, series):
        # Array of (name, numeric values, color)
        self.series = [(str(name), [float(x) for x in samples if x is not None], str(color))
                       for name, samples, color in series]
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(COLORS['surface']))
        painter.setPen(QColor(COLORS['sub']))
        painter.drawText(12, 20, self.title)
        area = QRectF(28, 35, max(20, self.width()-47), max(40, self.height()-62))
        painter.setPen(QPen(QColor(COLORS['stroke']), 1))
        for i in range(5):
            y = area.top() + area.height() * i / 4
            painter.drawLine(QPointF(area.left(), y), QPointF(area.right(), y))
        observed = [v for _, data, _ in self.series for v in data]
        if not observed:
            painter.setPen(QColor(COLORS['muted']))
            painter.drawText(area.toRect(), Qt.AlignmentFlag.AlignCenter, 'No measurements yet')
            return
        minimum, maximum = min(observed), max(observed)
        if maximum == minimum:
            maximum += max(1., abs(maximum)*.1)
            minimum -= max(1., abs(minimum)*.1)
        for name, values, color in self.series:
            if not values:
                continue
            painter.setPen(QPen(QColor(color), 2.2))
            path = QPainterPath()
            for i, value in enumerate(values):
                x = area.left() + area.width() * i / max(len(values)-1, 1)
                y = area.bottom() - (value-minimum)/(maximum-minimum)*area.height()
                if i == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)
            painter.drawPath(path)
        painter.setPen(QColor(COLORS['sub']))
        painter.drawText(8, self.height()-8,
                         '   |   '.join(f'{name}: {values[-1]:.2f}'
                                      for name, values, _ in self.series if values)[:100])




class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        from PySide6.QtCore import QSize
        return QSize(self.editor.gutter_width(), 0)

    def paintEvent(self, event):
        self.editor.paint_gutter(event)


class CodeEditor(QPlainTextEdit):
    """Source editor with Ctrl+click into the actual C++ interpreter code."""
    definitionRequested = Signal(str)
    def __init__(self):
        super().__init__()
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self.setToolTip('Ctrl + click a language keyword to edit the C++ implementation')
        self.gutter = LineNumberArea(self)
        self.blockCountChanged.connect(self.update_gutter_width)
        self.updateRequest.connect(self.update_gutter)
        self.update_gutter_width(0)
        self._diagnostic_lines = set()

    def set_diagnostics(self, issues):
        markers = []
        highlights = set()
        for issue in issues:
            number = int(issue.get('line') or 0)
            column = int(issue.get('column') or 1)
            block = self.document().findBlockByNumber(number-1)
            if not block.isValid():
                continue
            highlights.add(number)
            marker = QTextEdit.ExtraSelection()
            cursor = self.textCursor()
            cursor.setPosition(min(block.position()+max(0,column-1),
                                   block.position()+max(0,block.length()-1)))
            cursor.movePosition(QTextCursor.MoveOperation.NextCharacter,
                                QTextCursor.MoveMode.KeepAnchor)
            marker.cursor = cursor
            marker.format.setUnderlineColor(
                QColor('#F08A8A' if issue.get('severity')=='error' else '#D9B579'))
            marker.format.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SpellCheckUnderline)
            markers.append(marker)
        self._diagnostic_lines = highlights
        self.setExtraSelections(markers)
        self.gutter.update()

    def mousePressEvent(self, event):
        if (event.button() == Qt.MouseButton.LeftButton and
                event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            cursor = self.cursorForPosition(event.position().toPoint())
            keyword = keyword_at(self.toPlainText(), cursor.position())
            if keyword:
                self.definitionRequested.emit(keyword)
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        cursor = self.cursorForPosition(event.position().toPoint())
        active = (QApplication.keyboardModifiers() & Qt.KeyboardModifier.ControlModifier and
                  keyword_at(self.toPlainText(), cursor.position()))
        self.viewport().setCursor(Qt.CursorShape.PointingHandCursor if active
                                  else Qt.CursorShape.IBeamCursor)
        super().mouseMoveEvent(event)

    def gutter_width(self):
        digits = len(str(max(1,self.blockCount())))
        return 18 + self.fontMetrics().horizontalAdvance('9') * digits

    def update_gutter_width(self, _):
        self.setViewportMargins(self.gutter_width(),0,0,0)

    def update_gutter(self, rect, dy):
        if dy:
            self.gutter.scroll(0,dy)
        else:
            self.gutter.update(0,rect.y(),self.gutter.width(),rect.height())
        if rect.contains(self.viewport().rect()):
            self.update_gutter_width(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        rect = self.contentsRect()
        self.gutter.setGeometry(rect.left(),rect.top(),self.gutter_width(),rect.height())

    def paint_gutter(self, event):
        painter = QPainter(self.gutter)
        painter.fillRect(event.rect(),QColor('#1d2531'))
        block = self.firstVisibleBlock()
        number = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.setPen(QColor('#E58C8C' if number+1 in self._diagnostic_lines
                                      else '#91a0b6'))
                painter.drawText(0,top,self.gutter.width()-7,
                    self.fontMetrics().height(),Qt.AlignmentFlag.AlignRight,str(number+1))
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            number += 1

class Syntax(PlusMinusHighlighter):
    """Backward-compatible name for the PlusMinus syntax highlighter."""
    pass


class Job(QThread):
    complete = Signal(object)
    failed = Signal(str)

    def __init__(self, work):
        super().__init__()
        self.work = work

    def run(self):
        try:
            self.complete.emit(self.work())
        except Exception as exc:
            self.failed.emit(f'{type(exc).__name__}: {exc}')


class NativeTestJob(QThread):
    """One subprocess per test with live progress signals."""
    progress = Signal(object)
    completed = Signal(object)

    def __init__(self, executable, cases, cancel):
        super().__init__()
        self.executable = executable
        self.cases = list(cases)
        self.cancel = cancel

    def run(self):
        results = []
        for case in self.cases:
            if self.cancel.is_set():
                break
            result = run_native_case(
                self.executable, case, self.cancel,
                timeout=180 if case.get('slow') else 20)
            results.append(result)
            self.progress.emit(result)
        self.completed.emit(results)


class Studio(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings('PlusMinus', 'Studio2')
        self.history = HistoryStore()
        self.runner = find_runner()
        self.language_window = None
        self.native_building = False
        self.file = None
        self.saved = EXAMPLE
        self.last_report = None
        self.last_tests = []
        self.last_benchmark = {}
        self.user_tests = []
        self.native_runner = find_native_runner()
        self.native_cases = []
        self.native_history = NativeHistory()
        self.last_native_session = None
        self.jobs = []
        self.cancel = threading.Event()
        self.gui_samples = []
        self.gui_cpu_samples = []
        self.process = psutil.Process(os.getpid()) if psutil else None
        if self.process:
            self.process.cpu_percent(None)
        self.setWindowTitle('PlusMinus Studio 2.0 — Analytics IDE')
        self.resize(1440, 885)
        self.setMinimumSize(1010, 680)
        self.setStyleSheet(STYLE)
        self.make_shell()
        self.load_user_tests()
        self.restore_session()
        self.nav.setCurrentRow(0)
        self.update_analysis()
        self.refresh_history()
        self.statusBar().showMessage('Ready — startup regression suite scheduled')
        self.resource_timer = QTimer(self)
        self.resource_timer.timeout.connect(self.update_resources)
        self.resource_timer.start(900)
        self.analysis_timer = QTimer(self)
        self.analysis_timer.setSingleShot(True)
        self.analysis_timer.setInterval(300)
        self.analysis_timer.timeout.connect(self.update_analysis)
        self.diagnostic_timer = QTimer(self)
        self.diagnostic_timer.setSingleShot(True)
        self.diagnostic_timer.setInterval(650)
        self.diagnostic_timer.timeout.connect(self.request_compile_diagnostics)
        QTimer.singleShot(450, self.auto_tests)
        QTimer.singleShot(1200, self.discover_native)

    def make_shell(self):
        central = QWidget()
        self.setCentralWidget(central)
        outer = QHBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        rail = QFrame()
        rail.setObjectName('rail')
        rail.setFixedWidth(198)
        rail_layout = QVBoxLayout(rail)
        rail_layout.setContentsMargins(9, 24, 9, 14)
        rail_layout.setSpacing(13)
        title = label('＋／－  PLUSMINUS')
        title.setStyleSheet('font-size: 12pt; font-weight: 800; padding: 0 9px;')
        rail_layout.addWidget(title)
        sub = label('STUDIO 2.0  /  ANALYTICS', style='muted')
        sub.setStyleSheet('color: #7f8ca0; font-size: 8pt; padding-left: 9px;')
        rail_layout.addWidget(sub)
        self.nav = QListWidget()
        self.nav.addItems(['Overview', 'Code Editor', 'Test Center',
                           'Profiler', 'Resources', 'Benchmarks', 'History & Reports'])
        rail_layout.addWidget(self.nav, 1)
        self.engine_status = label('●  Checking runtime...', style='muted')
        rail_layout.addWidget(self.engine_status)
        outer.addWidget(rail)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(20, 12, 18, 12)
        toolbar_layout.addWidget(label('WORKSPACE   /   LOCAL'))
        toolbar_layout.addStretch(1)
        toolbar_layout.addWidget(button('Open', self.open_file))
        toolbar_layout.addWidget(button('Save', self.save_file))
        toolbar_layout.addWidget(button('Run  F5', lambda: self.launch('run'), primary=True))
        toolbar_layout.addWidget(button('Profile  F6', lambda: self.launch('run', profile=True)))
        toolbar_layout.addWidget(button('Run tests', self.start_tests))
        toolbar_layout.addWidget(button('Language C++', self.open_language_internals))
        toolbar_layout.addWidget(button('Stop', self.stop))
        right_layout.addWidget(toolbar)
        self.stack = WorkspaceTabs()
        self.workspace = self.stack
        for title, create in zip(
                ('Overview', 'Code Editor', 'Test Center', 'Profiler',
                 'Resources', 'Benchmarks', 'History & Reports'),
                (self.make_overview, self.make_editor, self.make_tests,
                 self.make_profiler, self.make_resources, self.make_benchmarks,
                 self.make_history)):
            self.workspace.register_page(title, create())
        right_layout.addWidget(self.workspace, 1)
        outer.addWidget(right, 1)
        self.nav.currentRowChanged.connect(self.workspace.open_page)
        self.workspace.pageActivated.connect(self.nav.setCurrentRow)
        self.nav.setCurrentRow(0)
        for shortcut, action in [('F5', lambda: self.launch('run')),
                                 ('F6', lambda: self.launch('run', profile=True)),
                                 ('Ctrl+S', self.save_file), ('Ctrl+O', self.open_file),
                                 ('Ctrl+N', self.new_file),
                                 ('Ctrl+Shift+I', self.open_language_internals)]:
            a = QAction(self)
            a.setShortcut(shortcut)
            a.triggered.connect(action)
            self.addAction(a)

    def make_overview(self):
        page_widget, layout = page('Workspace Overview', 'Execution intelligence · test health · system telemetry')
        summary = QHBoxLayout()
        self.cards = {}
        for key, title, placeholder in [('tests','TEST SUITE','— / —'),
                                        ('duration','LAST EXECUTION','— ms'),
                                        ('memory','PEAK VM MEMORY','— MB'),
                                        ('runs','RECORDED EVENTS','0')]:
            frame, col = panel()
            col.addWidget(label(title,style='muted'))
            main = label(placeholder,style='metric')
            col.addWidget(main)
            col.addStretch()
            summary.addWidget(frame,1)
            self.cards[key] = main
        layout.addLayout(summary)
        charts = QHBoxLayout()
        a, ac = panel()
        ac.addWidget(label('Execution time trend  /  milliseconds'))
        self.duration_chart = Plot('Recorded run duration')
        ac.addWidget(self.duration_chart)
        charts.addWidget(a, 2)
        b, bc = panel()
        bc.addWidget(label('Runtime activity'))
        self.dashboard_notes = label('Opening checks pending...')
        self.dashboard_notes.setAlignment(Qt.AlignmentFlag.AlignTop)
        bc.addWidget(self.dashboard_notes)
        bc.addStretch()
        charts.addWidget(b, 1)
        layout.addLayout(charts)
        frame, col = panel()
        col.addWidget(label('Recent activity'))
        self.dashboard_table = table(['Time (UTC)', 'Category', 'Activity', 'Result', 'ms'])
        col.addWidget(self.dashboard_table)
        layout.addWidget(frame, 1)
        return page_widget

    def make_editor(self):
        page_widget, layout = page('Code Workspace', 'Edit · compile · inspect · execute')
        toolbar = QHBoxLayout()
        self.file_label = label('untitled.pm',style='muted')
        toolbar.addWidget(self.file_label)
        toolbar.addStretch()
        toolbar.addWidget(button('New', self.new_file))
        toolbar.addWidget(button('Compile', lambda: self.launch('compile')))
        toolbar.addWidget(button('Run', lambda: self.launch('run'), primary=True))
        toolbar.addWidget(button('Language Internals  Ctrl+click', self.open_language_internals))
        layout.addLayout(toolbar)
        split = QSplitter(Qt.Orientation.Horizontal)
        edit = QWidget()
        edit_layout = QVBoxLayout(edit)
        edit_layout.setContentsMargins(0,0,0,0)
        self.documents = DocumentTabs(self.make_source_editor)
        self.documents.activated.connect(self.activate_document)
        self.documents.savedFile.connect(lambda path: self.settings.setValue('last_file', path))
        self.documents.new_document(EXAMPLE)
        edit_layout.addWidget(self.documents)
        self.cursor_label = label('Line 1  ·  Column 1',style='muted')
        edit_layout.addWidget(self.cursor_label)
        split.addWidget(edit)
        insight, ins = panel()
        ins.addWidget(label('CODE INSIGHTS'))
        self.code_stats = label('Pending analysis')
        ins.addWidget(self.code_stats)
        ins.addWidget(label('HEURISTIC DIAGNOSTICS',style='muted'))
        self.code_warnings = QPlainTextEdit()
        self.code_warnings.setReadOnly(True)
        ins.addWidget(self.code_warnings,1)
        split.addWidget(insight)
        split.setSizes([800,300])
        layout.addWidget(split, 3)
        results = QTabWidget()
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.diagnostics = QPlainTextEdit()
        self.diagnostics.setReadOnly(True)
        problems_widget = QWidget()
        problems_layout = QVBoxLayout(problems_widget)
        problems_layout.setContentsMargins(2,2,2,2)
        self.problems_table = table(['Severity', 'Code', 'Line', 'Column', 'Description'])
        self.problems_table.doubleClicked.connect(self.jump_to_problem)
        problems_layout.addWidget(self.problems_table, 2)
        problems_layout.addWidget(self.diagnostics, 1)
        self.bytecode = QPlainTextEdit()
        self.bytecode.setReadOnly(True)
        self.variables = QPlainTextEdit()
        self.variables.setReadOnly(True)
        for title, widget in [('Output',self.output),('Problems',problems_widget),
                              ('Bytecode',self.bytecode),('Variables',self.variables)]:
            results.addTab(widget,title)
        self.result_tabs = results
        layout.addWidget(results, 2)
        return page_widget

    def make_tests(self):
        page_widget, layout = page(
            'Test Laboratory', 'Portable C++ tests · PlusMinus checks · Git baselines')
        suites = QTabWidget()
        embedded = QWidget()
        built_layout = QVBoxLayout(embedded)
        controls = QHBoxLayout()
        self.test_summary = label('Waiting for built-in test suite', style='muted')
        controls.addWidget(self.test_summary,1)
        controls.addWidget(button('Add current source', self.add_test))
        controls.addWidget(button('Import JSON', self.import_tests))
        controls.addWidget(button('Export JSON', self.export_tests))
        controls.addWidget(button('Run selected', self.run_selected_test))
        controls.addWidget(button('Run all', self.start_tests, primary=True))
        built_layout.addLayout(controls)
        self.test_progress = QProgressBar()
        self.test_progress.setRange(0,100)
        built_layout.addWidget(self.test_progress)
        self.tests_table = table(['Name', 'Suite', 'Result', 'Execution', 'Details'])
        self.tests_table.doubleClicked.connect(self.open_test_source)
        built_layout.addWidget(self.tests_table,1)
        self.test_details = QPlainTextEdit()
        self.test_details.setReadOnly(True)
        self.test_details.setMaximumHeight(145)
        built_layout.addWidget(self.test_details)
        suites.addTab(embedded, 'PlusMinus & user tests')
        self.native_panel = NativeTestPanel()
        self.native_panel.runRequested.connect(self.start_native_tests)
        self.native_panel.baselineRequested.connect(self.set_native_baseline)
        self.native_panel.compareRequested.connect(self.compare_native_baseline)
        self.native_panel.refreshRequested.connect(self.discover_native)
        self.native_panel.openSourceRequested.connect(self.open_native_source)
        suites.addTab(self.native_panel, 'Native C++ test suite')
        layout.addWidget(suites,1)
        self.test_suites = suites
        self.refresh_test_table()
        return page_widget

    def make_profiler(self):
        page_widget, layout = page('Runtime Profiler',
            'Real process measurements and instrumented C++ VM timings (if available)')
        info, col = panel()
        self.profile_metrics = label('Run or profile a program to collect performance metrics.')
        col.addWidget(self.profile_metrics)
        layout.addWidget(info)
        chart, chart_col = panel()
        self.profile_chart = Plot('VM process RSS · sampled MB')
        chart_col.addWidget(self.profile_chart)
        layout.addWidget(chart, 1)
        bottom, bottom_col = panel()
        bottom_col.addWidget(label('Compiled bytecode  /  opcode frequency'))
        self.opcode_table = table(['Opcode', 'Static instructions', 'Share'])
        bottom_col.addWidget(self.opcode_table)
        layout.addWidget(bottom, 1)
        return page_widget

    def make_resources(self):
        page_widget, layout = page('Resource Monitor',
            'Studio process and executed VM are measured independently')
        self.resource_stats = label('Collecting GUI process metrics...')
        layout.addWidget(self.resource_stats)
        a, al = panel()
        self.gui_chart = Plot('PlusMinus Studio GUI  /  resident memory (MB)')
        al.addWidget(self.gui_chart)
        layout.addWidget(a,1)
        cpu_panel, cpu_layout = panel()
        self.gui_cpu_chart = Plot('PlusMinus Studio GUI  /  sampled CPU %')
        cpu_layout.addWidget(self.gui_cpu_chart)
        layout.addWidget(cpu_panel,1)
        b, bl = panel()
        self.vm_chart = Plot('Most recent VM run  /  sampled resident memory (MB)')
        bl.addWidget(self.vm_chart)
        layout.addWidget(b,1)
        layout.addWidget(label('VM memory samples are not guaranteed absolute peaks. '
                               'Very short processes can finish between samples.',style='muted'))
        return page_widget

    def make_benchmarks(self):
        page_widget, layout = page('Benchmark Laboratory',
            'Repeatable experiments · distributions · performance comparisons')
        controls = QHBoxLayout()
        controls.addWidget(label('Repetitions'))
        self.benchmark_runs = QSpinBox()
        self.benchmark_runs.setRange(2,100)
        self.benchmark_runs.setValue(10)
        controls.addWidget(self.benchmark_runs)
        self.benchmark_warm = QCheckBox('One warm-up run')
        self.benchmark_warm.setChecked(True)
        controls.addWidget(self.benchmark_warm)
        controls.addStretch()
        controls.addWidget(button('Benchmark editor source', self.start_benchmark, primary=True))
        layout.addLayout(controls)
        frame, col = panel()
        self.benchmark_summary = label('No benchmark results yet.')
        col.addWidget(self.benchmark_summary)
        self.benchmark_chart = Plot('Measured end-to-end execution time  /  ms')
        col.addWidget(self.benchmark_chart)
        layout.addWidget(frame,1)
        layout.addWidget(label('Results include process startup and IPC overhead. VM-internal '
                               'execution time is displayed separately in Profiler when available.',style='muted'))
        return page_widget

    def make_history(self):
        page_widget, layout = page('History & Reports',
            'Persistent execution data · comparisons · portable exports')
        actions = QHBoxLayout()
        self.history_status = label('Loading history...',style='muted')
        actions.addWidget(self.history_status,1)
        actions.addWidget(button('Refresh', self.refresh_history))
        actions.addWidget(button('Export CSV', lambda: self.export_history('csv')))
        actions.addWidget(button('Export JSON', lambda: self.export_history('json')))
        layout.addLayout(actions)
        frame, col = panel()
        self.history_table = table(['UTC timestamp', 'Category', 'Action', 'Result', 'Wall ms', 'SHA-256'])
        col.addWidget(self.history_table)
        layout.addWidget(frame,1)
        return page_widget

    def spawn(self, work, success, title):
        job = Job(work)
        self.jobs.append(job)
        job.complete.connect(success)
        job.failed.connect(lambda text: self.error(f'{title} failed: {text}'))
        job.finished.connect(lambda j=job: self.finished_job(j))
        self.statusBar().showMessage(f'{title} running in background...')
        job.start()

    def finished_job(self, job):
        if job in self.jobs:
            self.jobs.remove(job)
        job.deleteLater()

    def error(self, message):
        self.statusBar().showMessage(message, 13000)
        self.dashboard_notes.setText(message)

    def open_language_internals(self, keyword=None):
        if not editable_checkout(ROOT) or getattr(sys, 'frozen', False):
            QMessageBox.information(self, 'Language source unavailable',
                'Editing the native interpreter requires a full PlusMinus source checkout. '
                'Clone the repository and run Start-PlusMinus. Prebuilt applications '
                'do not include editable C++ sources and a development toolchain.')
            return
        if isinstance(keyword, bool) or not isinstance(keyword, str):
            keyword = 'if'
        if self.language_window is None:
            self.language_window = LanguageSourceWindow(ROOT, self)
            self.language_window.sourceSaved.connect(self.language_source_saved)
            self.language_window.rebuildRequested.connect(self.rebuild_language)
        self.language_window.select_symbol(keyword)
        self.language_window.show()
        self.language_window.raise_()
        self.language_window.activateWindow()

    def language_source_saved(self, path):
        # Do not accidentally execute a stale VM after modifying its C++ code.
        self.runner = None
        self.engine_status.setText('● Native source changed / rebuild required')
        self.statusBar().showMessage(f'Interpreter source saved: {path}', 9000)
        if self.language_window and self.language_window.auto_build.isChecked():
            self.rebuild_language()

    def rebuild_language(self):
        if getattr(sys, 'frozen', False) or not editable_checkout(ROOT):
            self.error('Rebuilding requires source files, CMake and a C++20 compiler.')
            return
        if self.native_building:
            self.error('The C++ runner is already rebuilding.')
            return
        if any(job.isRunning() for job in self.jobs):
            self.error('Wait for running tests/programs to finish, then click Rebuild & test.')
            return
        self.native_building = True
        self.runner = None
        self.engine_status.setText('● Rebuilding C++ interpreter...')
        def work():
            try:
                process = subprocess.run(
                    [sys.executable, str(ROOT/'launch.py'), '--no-install', '--build-only'],
                    cwd=str(ROOT), capture_output=True, text=True,
                    timeout=240, check=False)
                return process.returncode == 0, (process.stdout+'\n'+process.stderr)[-16000:]
            except (OSError, subprocess.TimeoutExpired) as exc:
                return False, str(exc)
        self.spawn(work, self.language_rebuilt, 'C++ rebuild')

    def language_rebuilt(self, result):
        self.native_building = False
        ok, build_log = result
        if not ok:
            self.runner = None
            self.engine_status.setText('● C++ rebuild failed')
            self.error('Native rebuild failed; inspect the compiler output.')
            QMessageBox.warning(self, 'C++ compilation failed',
                'Edited interpreter code did not compile. The old VM will not run.\n\n'+
                build_log[-8500:])
            return
        self.runner = find_runner()
        if self.runner is None:
            self.error('C++ build reported success but did not produce a runner.')
            return
        self.engine_status.setText('● Runtime rebuilt')
        self.statusBar().showMessage('C++ interpreter rebuilt. Rerunning built-in tests.',10000)
        self.start_tests(startup=True)
        self.discover_native()

    def make_source_editor(self):
        editor = CodeEditor()
        editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        font = QFont('Cascadia Code', 11)
        font.setStyleHint(QFont.StyleHint.Monospace)
        editor.setFont(font)
        editor._highlighter = Syntax(editor.document())
        editor._syntax_kind = 'pm'
        editor.cursorPositionChanged.connect(
            lambda e=editor: self.update_cursor() if getattr(self,'editor',None) is e else None)
        editor.definitionRequested.connect(self.open_language_internals)
        editor.textChanged.connect(
            lambda e=editor: self.analysis_timer.start()
            if hasattr(self,'analysis_timer') and getattr(self,'editor',None) is e else None)
        return editor

    def activate_document(self, doc):
        self.editor = doc.editor
        self.file = doc.path
        self.saved = doc.saved
        is_cpp = bool(doc.path and doc.path.suffix.lower() in ('.cpp','.h','.hpp'))
        current_kind = getattr(doc.editor, '_syntax_kind', 'pm')
        expected_kind = 'cpp' if is_cpp else 'pm'
        if current_kind != expected_kind:
            doc.editor._highlighter.setDocument(None)
            doc.editor._highlighter = CppHighlighter(doc.editor.document()) if is_cpp else Syntax(doc.editor.document())
            doc.editor._syntax_kind = expected_kind
        if hasattr(self,'code_stats'):
            self.update_analysis()
            self.update_cursor()

    def update_cursor(self):
        cursor = self.editor.textCursor()
        self.cursor_label.setText(f'Line {cursor.blockNumber()+1}  ·  Column {cursor.positionInBlock()+1}')

    def update_analysis(self):
        metrics = analyze_source(self.editor.toPlainText())
        self.code_stats.setText('\n'.join([
            f"Lines of code              {metrics['code_lines']}",
            f"Functions / procedures    {metrics['functions']} / {metrics['procedures']}",
            f"Variables (estimated)     {metrics['variables']}",
            f"Branches / loops          {metrics['branches']} / {metrics['loops']}",
            f"Cyclomatic estimate       {metrics['complexity_estimate']}",
            f"Max block nesting         {metrics['max_nesting']}",
            f"Concurrent calls          {metrics['go_calls']}",
        ]))
        self.code_warnings.setPlainText('\n'.join(metrics['warnings']) if metrics['warnings']
                                        else 'No lexical warnings. Static analysis is heuristic, not a proof of correctness.')
        doc = self.documents.current_document()
        self.file_label.setText((doc.path.name if doc and doc.path else 'untitled.pm') +
                                 ('  ● unsaved changes' if doc and doc.modified else ''))

    def maybe_save(self):
        return self.documents.maybe_save(self.documents.current_document())

    def new_file(self):
        self.documents.new_document('')
        self.nav.setCurrentRow(1)

    def open_file(self):
        filename, _ = QFileDialog.getOpenFileName(
            self,'Open PlusMinus file',str(ROOT),'PlusMinus (*.pm);;All files (*)')
        if filename:
            self.read_file(Path(filename))

    def read_file(self, path):
        try:
            self.documents.open_path(path)
        except (OSError, UnicodeError) as exc:
            self.error(f'Cannot open file: {exc}')
            return
        self.settings.setValue('last_file', str(path))
        self.update_analysis()
        self.nav.setCurrentRow(1)

    def save_file(self):
        if not self.documents.save_current():
            return False
        self.update_analysis()
        self.statusBar().showMessage(f'Saved: {self.file}', 4000)
        return True

    def restore_session(self):
        geometry = self.settings.value('geometry')
        if geometry:
            self.restoreGeometry(geometry)
        pages = self.settings.value('workspace_pages', [0,1])
        if isinstance(pages, (list,tuple)):
            self.workspace.restore_pages(pages)
        files = self.settings.value('open_files', [])
        if not isinstance(files, (list,tuple)):
            files = [files] if files else []
        for item in files:
            if item and Path(str(item)).is_file():
                self.read_file(Path(str(item)))
        if not files:
            filename = self.settings.value('last_file','')
            if filename and Path(str(filename)).is_file():
                self.read_file(Path(str(filename)))
        self.update_analysis()

    def record(self, category, label_text, source, report):
        metrics = report.get('metrics', {})
        details = {'error':report.get('error', ''),
                   'output':report.get('output','')[:3000],
                   'metrics':{k:v for k,v in metrics.items() if k != 'samples'}}
        try:
            self.history.add(category,label_text,source,report.get('ok',False),
                             report.get('ms',0), details)
        except OSError as exc:
            self.error(f'History database unavailable: {exc}')

    def launch(self, mode='run', profile=False):
        if not self.runner:
            self.error('C++ runner missing. Launch via Start-PlusMinus or run python launch.py.')
            return
        source = self.editor.toPlainText()
        self.cancel.clear()
        runner = self.runner
        self.spawn(lambda: execute(runner,source,mode,8.0,self.cancel),
                   lambda report: self.show_report(report,source,'Profile' if profile else 'Run'),
                   'Profile' if profile else 'Compile' if mode=='compile' else 'Run')

    def show_report(self, report, source, category='Run'):
        self.last_report = report
        self.output.setPlainText(report['output'] + (f"\nReturn: {report['result']}" if report['result'] else ''))
        self.diagnostics.setPlainText(report['error'] or 'Execution successful; no runtime diagnostics.')
        self.bytecode.setPlainText(report['bytecode'])
        self.variables.setPlainText(report['variables'])
        self.result_tabs.setCurrentIndex(1 if report['error'] else 0)
        self.record(category, self.file.name if self.file else 'Editor source', source, report)
        metrics = report.get('metrics', {})
        samples = metrics.get('samples', [])
        self.profile_chart.set_series([('RSS MB',[x[1] for x in samples],COLORS['accent'])])
        self.vm_chart.set_series([('RSS MB',[x[1] for x in samples],COLORS['good'])])
        details = [
            f"Execution status: {'OK' if report['ok'] else 'ERROR'}",
            f"End-to-end wall time: {report['ms']:.2f} ms",
            f"Measured VM CPU time: {metrics.get('cpu_ms') if metrics.get('cpu_ms') is not None else 'N/A'} ms",
            f"Sampled peak VM RSS: {metrics.get('peak_rss_mb') if metrics.get('peak_rss_mb') is not None else 'N/A'} MB",
            f"Sampled max VM threads: {metrics.get('peak_threads') if metrics.get('peak_threads') is not None else 'N/A'}",
            f"VM compile time: {metrics.get('compile_ms', 'N/A')} ms",
            f"VM execute time: {metrics.get('execute_ms', 'N/A')} ms",
            f"VM compiled instruction count: {metrics.get('program_instructions','N/A')}",
        ]
        self.profile_metrics.setText('\n'.join(details))
        bc = analyze_bytecode(report['bytecode'])
        total = max(1, bc['instructions'])
        fill_table(self.opcode_table,[(op, qty, f'{qty/total*100:.1f}%')
                                       for op,qty in bc['opcodes'].items()])
        self.statusBar().showMessage(f"{'PASS' if report['ok'] else 'ERROR'}  ·  {report['ms']:.2f} ms",6000)
        self.refresh_history()
        self.nav.setCurrentRow(3 if category == 'Profile' else 1)

    def stop(self):
        self.cancel.set()
        self.statusBar().showMessage('Stop requested. Active VM executions will be interrupted.',5000)

    def test_cases(self):
        return [(dict(case), 'Built-in') for case in BUILTIN_TESTS] + [(dict(case),'User') for case in self.user_tests]

    def load_user_tests(self):
        target = PREFS / 'user_tests.json'
        if target.is_file():
            try:
                data = json.loads(target.read_text(encoding='utf-8'))
                if isinstance(data,list):
                    self.user_tests = [x for x in data if isinstance(x,dict) and
                                       all(isinstance(x.get(k),str) for k in ('name','source','kind','expected'))]
            except (OSError, ValueError):
                self.error('Could not read user test definitions')
        self.refresh_test_table()

    def save_user_tests(self):
        PREFS.mkdir(parents=True,exist_ok=True)
        (PREFS/'user_tests.json').write_text(json.dumps(self.user_tests,indent=2,ensure_ascii=False),encoding='utf-8')

    def refresh_test_table(self):
        cases = self.test_cases()
        results = {name: (passed, duration, detail) for name, passed, duration, detail
                   in self.last_tests}
        rows = []
        for case, suite in cases:
            outcome = results.get(case['name'])
            rows.append((case['name'], suite, 'PASS' if outcome and outcome[0] else
                         'FAIL' if outcome else 'NOT RUN',
                         f'{outcome[1]:.1f} ms' if outcome else '—',
                         outcome[2][:180] if outcome else ''))
        fill_table(self.tests_table, rows)

    def auto_tests(self):
        self.engine_status.setText('●  Runtime ready' if self.runner else '●  Runner unavailable')
        if self.runner:
            self.start_tests(startup=True)
        else:
            self.test_summary.setText('Runner missing — open via a platform launcher to build it')

    def start_tests(self, checked=False, startup=False):
        if not self.runner:
            self.error('C++ runner not found; cannot execute tests')
            return
        cases = self.test_cases()
        self.run_test_batch(cases, 'Startup tests' if startup else 'Test suite')

    def run_selected_test(self):
        selected = self.tests_table.currentRow()
        cases = self.test_cases()
        if selected < 0 or selected >= len(cases):
            self.error('Select a test row first')
            return
        self.run_test_batch([cases[selected]], 'Selected test')

    def run_test_batch(self, cases, title):
        self.cancel.clear()
        self.test_progress.setValue(0)
        self.test_summary.setText(f'{title}: executing {len(cases)} cases...')
        runner = self.runner
        def work():
            results = []
            for case, suite in cases:
                if self.cancel.is_set():
                    break
                report = execute(runner,case['source'],case.get('mode','run'),
                                 float(case.get('timeout',5)),self.cancel)
                passed, detail = judge_test(case,report)
                results.append((case,suite,passed,detail,report))
            return results
        self.spawn(work, self.show_test_results, title)

    def show_test_results(self, results):
        entries = []
        failures = []
        for case, suite, passed, detail, report in results:
            entries.append((case['name'],passed,report['ms'],detail))
            if not passed:
                failures.append(f"[{case['name']}] {detail}\n{report.get('error','')}")
            try:
                self.history.add('Test',case['name'],case['source'],passed,report['ms'],
                                 {'suite':suite,'error':report.get('error',''),'details':detail})
            except (OSError,ValueError) as exc:
                self.error(f'Test history write failed: {exc}')
        existing = {r[0]:r for r in self.last_tests}
        existing.update({r[0]:r for r in entries})
        self.last_tests = list(existing.values())
        passed = sum(x[1] for x in entries)
        self.test_summary.setText(f'{passed} / {len(entries)} passed  ·  '
                                  f'{len(entries)-passed} failed  ·  last test batch')
        self.test_progress.setValue(int(100*len(entries)/max(1,len(entries))))
        self.test_details.setPlainText('\n\n'.join(failures) or 'All tests in this batch passed.')
        self.refresh_test_table()
        self.refresh_history()
        self.nav.setCurrentRow(2 if passed != len(entries) else self.nav.currentRow())
        self.dashboard_notes.setText(f'Built-in / user test results\n{passed} of {len(entries)} '
                                      f'passed in the last batch.\n\n'
                                      'Tests run on a separate VM process with a timeout.')

    def add_test(self):
        name, ok = QInputDialog.getText(self,'New test','Test name')
        if not ok or not name.strip():
            return
        expected, ok = QInputDialog.getMultiLineText(self,'Expected output',
                     'Enter exact output (including final newline if applicable)', '')
        if not ok:
            return
        self.user_tests.append(dict(name=name.strip(),source=self.editor.toPlainText(),
                                    kind='output',expected=expected,mode='run',expect_ok=True))
        self.save_user_tests()
        self.refresh_test_table()

    def import_tests(self):
        filename, _ = QFileDialog.getOpenFileName(self,'Import tests',str(ROOT),'JSON (*.json)')
        if not filename:
            return
        try:
            data = json.loads(Path(filename).read_text(encoding='utf-8'))
            if not isinstance(data,list) or not all(isinstance(c,dict) and
                 all(isinstance(c.get(k),str) for k in ('name','source','kind','expected'))
                 and c['kind'] in ('output','result','bytecode_contains','error_contains')
                 for c in data):
                raise ValueError('Expected an array of valid test cases')
            self.user_tests.extend(data)
            self.save_user_tests()
            self.refresh_test_table()
        except (OSError,ValueError) as exc:
            self.error(f'Invalid test file: {exc}')

    def export_tests(self):
        filename, _ = QFileDialog.getSaveFileName(self,'Export user tests',str(ROOT/'tests.json'),'JSON (*.json)')
        if filename:
            try:
                Path(filename).write_text(json.dumps(self.user_tests,indent=2,ensure_ascii=False),encoding='utf-8')
            except OSError as exc:
                self.error(f'Test export failed: {exc}')

    def open_test_source(self):
        selected = self.tests_table.currentRow()
        cases = self.test_cases()
        if 0 <= selected < len(cases):
            self.documents.new_document(cases[selected][0]['source'])
            self.nav.setCurrentRow(1)

    def discover_native(self):
        self.native_runner = find_native_runner()
        if self.native_runner is None:
            self.native_panel.summary.setText(
                'Native C++ runner missing — rebuild CMake project to enable all 225 tests')
            return
        self.spawn(
            lambda: discover_native_tests(self.native_runner),
            self.native_discovered, 'Native C++ test discovery')

    def native_discovered(self, cases):
        self.native_cases = cases
        self.native_panel.set_cases(cases)
        previous = self.native_history.recent(1)
        if previous:
            self.last_native_session = previous[0]['id']
            self.native_panel.summary.setText(
                f"{len(cases)} C++ tests available · previous session #{self.last_native_session}")
            for record in self.native_history.results(self.last_native_session).values():
                self.native_panel.last_results[record['id']] = record
            self.native_panel.populate()

    def start_native_tests(self, selection='quick'):
        if not self.native_runner or not self.native_cases:
            self.error('Native C++ tests unavailable. Build with CMake first.')
            return
        if any(job.isRunning() for job in self.jobs):
            self.error('Another background task is active. Finish or stop it first.')
            return
        if selection == 'selected':
            case = self.native_panel.selected()
            if case is None:
                self.error('Choose a C++ test in the table.')
                return
            cases = [case]
        elif selection == 'full':
            cases = list(self.native_cases)
        else:
            cases = [c for c in self.native_cases if not c.get('slow')]
        self.cancel.clear()
        self.native_panel.last_results = {}
        self.native_panel.populate()
        self.native_panel.summary.setText(f'Running {len(cases)} native C++ tests...')
        self.test_suites.setCurrentIndex(1)
        self.nav.setCurrentRow(2)
        job = NativeTestJob(self.native_runner, cases, self.cancel)
        self.jobs.append(job)
        job.progress.connect(self.native_panel.set_result)
        job.completed.connect(
            lambda results, requested=selection: self.native_completed(results, requested))
        job.finished.connect(lambda j=job: self.finished_job(j))
        job.start()

    def native_completed(self, results, selection):
        if not results:
            self.native_panel.report.setPlainText('No native tests completed.')
            return
        self.last_native_session = self.native_history.save(selection, results)
        total = len(results)
        passed = sum(item['status'] == 'PASS' for item in results)
        failures = [f"{r['id']}: {r['status']} — {r['error']}"
                    for r in results if r['status'] != 'PASS']
        self.native_panel.summary.setText(
            f'C++ session #{self.last_native_session}: {passed}/{total} PASS')
        self.native_panel.report.setPlainText(
            '\n'.join(failures[:35]) if failures else
            f'All {total} executed C++ tests passed. Session saved to SQLite.')
        self.refresh_history()

    def set_native_baseline(self):
        if self.last_native_session is None:
            self.error('Run native tests before selecting a baseline.')
            return
        self.native_history.set_baseline(self.last_native_session)
        self.native_panel.report.setPlainText(
            f'Session #{self.last_native_session} set as the regression baseline.')

    def compare_native_baseline(self):
        baseline = self.native_history.baseline()
        if baseline is None or self.last_native_session is None:
            self.error('Select a baseline and run native C++ tests first.')
            return
        diff = self.native_history.compare(baseline, self.last_native_session)
        lines = [f'Comparing baseline #{baseline} → session #{self.last_native_session}']
        for title, key in [('New failures','introduced'),('Fixed','fixed'),
                           ('Still failing','remaining_failures'),
                           ('New tests','added'),('Absent tests','missing')]:
            lines.append(f"{title}: {len(diff[key])}")
            lines.extend('    '+item for item in diff[key][:30])
        self.native_panel.report.setPlainText('\n'.join(lines))

    def open_native_source(self, identifier):
        case = next((c for c in self.native_cases if c['id'] == identifier), None)
        if case is None:
            return
        path = ROOT / case['source']
        if not path.is_file():
            self.error('C++ test sources are unavailable in packaged releases.')
            return
        self.read_file(path)
        target = identifier.rsplit('.',1)[-1]
        editor = self.editor
        location = editor.toPlainText().find(f'TEST_METHOD({target})')
        if location >= 0:
            cursor = editor.textCursor()
            cursor.setPosition(location)
            editor.setTextCursor(cursor)
            editor.centerCursor()

    def update_resources(self):
        if self.process is None:
            self.resource_stats.setText('Install psutil to enable operating-system process metrics.')
            return
        try:
            rss = self.process.memory_info().rss / 1048576
            cpu = self.process.cpu_percent(None)
            threads = self.process.num_threads()
            self.gui_samples.append(round(rss,2))
            self.gui_samples = self.gui_samples[-160:]
            self.gui_cpu_samples.append(round(cpu,2))
            self.gui_cpu_samples = self.gui_cpu_samples[-160:]
            self.gui_cpu_chart.set_series([('CPU %',self.gui_cpu_samples,COLORS['gold'])])
            self.gui_chart.set_series([('RSS MB',self.gui_samples,COLORS['accent'])])
            self.resource_stats.setText(f'Studio GUI     CPU: {cpu:.1f}%     '
                                        f'RSS: {rss:.1f} MB     Threads: {threads}     '
                                        f'Samples: {len(self.gui_samples)}')
        except (psutil.Error,OSError) as exc:
            self.resource_stats.setText(f'GUI process metrics unavailable: {exc}')

    def start_benchmark(self):
        if not self.runner:
            self.error('C++ runner unavailable for benchmark')
            return
        source = self.editor.toPlainText()
        n = self.benchmark_runs.value()
        warmup = self.benchmark_warm.isChecked()
        runner = self.runner
        self.cancel.clear()
        def work():
            if warmup:
                test = execute(runner,source,'run',10,self.cancel)
                if not test['ok']:
                    return {'error':f"Warm-up failed: {test['error']}"}
            times = []
            vm_times = []
            for _ in range(n):
                if self.cancel.is_set():
                    break
                result = execute(runner,source,'run',10,self.cancel)
                if not result['ok']:
                    return {'error':f"Benchmark iteration failed: {result['error']}"}
                times.append(float(result['ms']))
                internal = result['metrics'].get('execute_ms')
                if internal is not None:
                    vm_times.append(float(internal))
            return dict(summary=summarize_benchmark(times), vm=vm_times, source=source)
        self.spawn(work,self.show_benchmark,'Benchmark')

    def show_benchmark(self, result):
        if result.get('error'):
            self.error(result['error'])
            return
        summary = result['summary']
        if not summary:
            self.error('No benchmark measurements collected (interrupted).')
            return
        self.last_benchmark = summary
        self.benchmark_summary.setText(
            f"Runs {summary['runs']}  ·  Mean {summary['mean']:.2f} ms  ·  "
            f"Median {summary['median']:.2f} ms\n"
            f"Min {summary['minimum']:.2f}  /  Max {summary['maximum']:.2f}  /  "
            f"P95 {summary['p95']:.2f} ms  /  StdDev {summary['stdev']:.2f} ms\n"
            f"Internal VM time samples: {len(result['vm'])}")
        self.benchmark_chart.set_series([('Wall ms',summary['samples'],COLORS['accent'])])
        try:
            self.history.add('Benchmark',f"{summary['runs']} iterations",result['source'],True,
                             summary['mean'], {'summary':summary})
        except (OSError,ValueError) as exc:
            self.error(f'Benchmark history write failed: {exc}')
        self.refresh_history()
        self.nav.setCurrentRow(5)

    def refresh_history(self):
        try:
            history = self.history.recent()
            overview = self.history.overview()
        except (OSError,ValueError) as exc:
            self.error(f'Cannot read history: {exc}')
            return
        fill_table(self.history_table,[(r['created'][:19],r['category'],r['label'],
                        'PASS' if r['ok'] else 'FAIL',f"{r['elapsed_ms']:.2f}",r['source_hash'])
                         for r in history])
        fill_table(self.dashboard_table,[(r['created'][11:19],r['category'],r['label'],
                        'PASS' if r['ok'] else 'FAIL',f"{r['elapsed_ms']:.1f}")
                         for r in history[:10]])
        self.cards['runs'].setText(str(overview['runs']))
        self.cards['duration'].setText(f"{overview['last_ms']:.1f} ms" if overview['last_ms'] is not None else '— ms')
        self.cards['memory'].setText(
            f"{self.last_report['metrics'].get('peak_rss_mb'):.1f} MB"
            if self.last_report and self.last_report['metrics'].get('peak_rss_mb') is not None else 'N/A')
        passed = sum(1 for x in self.last_tests if x[1])
        self.cards['tests'].setText(f'{passed} / {len(self.last_tests)}' if self.last_tests else '— / —')
        self.history_status.setText(f'{len(history)} latest records · SQLite: {self.history.path}')
        times = [x['elapsed_ms'] for x in reversed(history) if x['category'] in ('Run','Profile')]
        self.duration_chart.set_series([('Wall ms',times[-100:],COLORS['accent'])])

    def export_history(self, fmt):
        filename, _ = QFileDialog.getSaveFileName(self,'Export execution history',
                                  str(ROOT/f'plusminus-history.{fmt}'),
                                  'CSV (*.csv)' if fmt=='csv' else 'JSON (*.json)')
        if not filename:
            return
        try:
            rows = self.history.recent(100000)
            if fmt == 'json':
                Path(filename).write_text(json.dumps(rows,indent=2,ensure_ascii=False),encoding='utf-8')
            else:
                with open(filename,'w',newline='',encoding='utf-8') as stream:
                    keys = ['id','created','category','label','ok','elapsed_ms','source_hash','details']
                    writer = csv.DictWriter(stream,fieldnames=keys)
                    writer.writeheader()
                    for row in rows:
                        writer.writerow({**row,'details':json.dumps(row['details'],ensure_ascii=False)})
            self.statusBar().showMessage(f'Exported {len(rows)} records',5000)
        except (OSError,ValueError) as exc:
            self.error(f'Export failed: {exc}')

    def closeEvent(self, event):
        if self.language_window and not self.language_window.confirm_leave():
            event.ignore()
            return
        if not self.documents.confirm_all():
            event.ignore()
            return
        self.cancel.set()
        for job in self.jobs:
            if job.isRunning():
                job.wait(11000)
                if job.isRunning():
                    self.error('An active task is still shutting down. Try closing again.')
                    event.ignore()
                    return
        self.settings.setValue('geometry',self.saveGeometry())
        self.settings.setValue('workspace_pages',self.workspace.open_page_ids())
        self.settings.setValue('open_files',self.documents.open_paths())
        event.accept()


def self_test():
    runner = find_runner()
    if runner is None:
        return 2
    for case in BUILTIN_TESTS[:4]:
        report = execute(runner,case['source'],case['mode'],float(case.get('timeout',5)))
        if not judge_test(case,report)[0]:
            return 3
    return 0


def main():
    if '--self-test' in sys.argv:
        return self_test()
    app = QApplication(sys.argv)
    app.setApplicationName('PlusMinus Studio')
    app.setOrganizationName('PlusMinus')
    window = Studio()
    window.show()
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
