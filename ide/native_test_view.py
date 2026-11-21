"""Native C++ test explorer, status display and baseline comparisons."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
                               QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
                               QWidget, QHeaderView, QAbstractItemView)


class NativeTestPanel(QWidget):
    runRequested = Signal(str)
    baselineRequested = Signal()
    compareRequested = Signal()
    refreshRequested = Signal()
    openSourceRequested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cases = []
        self.last_results = {}
        layout = QVBoxLayout(self)
        controls = QHBoxLayout()
        self.summary = QLabel('Discovering C++ tests...')
        controls.addWidget(self.summary, 1)
        for title, action in (
            ('Refresh', self.refreshRequested.emit),
            ('Run selected', lambda: self.runRequested.emit('selected')),
            ('Run quick', lambda: self.runRequested.emit('quick')),
            ('Run all 225', lambda: self.runRequested.emit('full')),
            ('Set baseline', self.baselineRequested.emit),
            ('Compare', self.compareRequested.emit),
        ):
            b = QPushButton(title)
            b.clicked.connect(action)
            controls.addWidget(b)
        layout.addLayout(controls)
        filters = QHBoxLayout()
        self.group_filter = QComboBox()
        self.group_filter.addItem('All groups')
        self.group_filter.currentTextChanged.connect(self.populate)
        filters.addWidget(self.group_filter)
        self.search = QLineEdit()
        self.search.setPlaceholderText('Filter tests by class, name or source...')
        self.search.textChanged.connect(self.populate)
        filters.addWidget(self.search, 1)
        layout.addLayout(filters)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(['Test method', 'Group', 'Status', 'Wall ms', 'Source'])
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.doubleClicked.connect(self.open_selected)
        layout.addWidget(self.table, 1)
        self.report = QPlainTextEdit()
        self.report.setReadOnly(True)
        self.report.setMaximumHeight(155)
        self.report.setPlaceholderText('Test failures and baseline comparisons appear here.')
        layout.addWidget(self.report)

    def set_cases(self, cases):
        self.cases = list(cases)
        self.group_filter.blockSignals(True)
        self.group_filter.clear()
        self.group_filter.addItem('All groups')
        self.group_filter.addItems(sorted(set(c['group'] for c in self.cases)))
        self.group_filter.blockSignals(False)
        self.summary.setText(f'{len(self.cases)} C++ test methods discovered · not run')
        self.populate()

    def selected(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        identifier = item.data(Qt.ItemDataRole.UserRole) if item else None
        return next((c for c in self.cases if c['id'] == identifier), None)

    def set_result(self, result):
        self.last_results[result['id']] = result
        self.populate()
        total = len(self.last_results)
        passed = sum(r['status'] == 'PASS' for r in self.last_results.values())
        self.summary.setText(f'{passed} / {total} checked · {total - passed} not passed')

    def populate(self, *_):
        group = self.group_filter.currentText()
        needle = self.search.text().lower()
        shown = [c for c in self.cases if
                 (group == 'All groups' or c['group'] == group) and
                 needle in (c['id']+' '+c['source']).lower()]
        selected = self.selected()
        previous = selected['id'] if selected else None
        self.table.setRowCount(len(shown))
        for row, case in enumerate(shown):
            report = self.last_results.get(case['id'], {})
            values = [case['id'], case['group'],
                      report.get('status', 'NOT RUN'),
                      f"{report['elapsed_ms']:.2f}" if 'elapsed_ms' in report else '—',
                      case['source']]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if col == 0:
                    item.setData(Qt.ItemDataRole.UserRole, case['id'])
                self.table.setItem(row, col, item)
            if case['id'] == previous:
                self.table.selectRow(row)

    def open_selected(self, *_):
        case = self.selected()
        if case:
            self.openSourceRequested.emit(case['id'])
