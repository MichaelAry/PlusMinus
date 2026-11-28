"""Studio plot editor and QPainter canvas."""
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
import math
from pathlib import Path
from threading import Event

from PySide6.QtCore import QPointF, QRectF, Qt, Signal, Slot, QTimer, QSignalBlocker
from PySide6.QtGui import QBrush, QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication, QColorDialog, QDoubleSpinBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMessageBox, QPushButton, QSlider, QSplitter, QStackedWidget, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from plot_expression import ExpressionError, MAX_EXPRESSION, PARAMETERS, parse, sample
from plot_model import (
    MAX_POINTS, MAX_SERIES, Formula, PlotDocument, Points, Viewport,
    fit, load_plot, save_plot, zoom,
)


class PlotCanvas(QWidget):
    painted = Signal(int)
    resized = Signal()
    viewportChanged = Signal(object)

    def __init__(self):
        super().__init__()
        self.document = PlotDocument()
        self.curves = {}
        self.revision = -1
        self.drag = None
        self.setMinimumSize(250, 190)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

    def data_rect(self):
        return (52, 12, max(1, self.width() - 67), max(1, self.height() - 42))

    def resizeEvent(self, event):
        self.resized.emit()
        super().resizeEvent(event)

    def wheelEvent(self, event):
        pos = event.position()
        if not QRectF(*self.data_rect()).contains(pos) or not event.angleDelta().y():
            event.ignore()
            return
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        view = self.document.viewport
        exponent = max(-10, min(10, -event.angleDelta().y() / 120))
        try:
            new_view = zoom(view, view.data(pos.x(), pos.y(), self.data_rect()), 1.2 ** exponent)
        except ValueError:
            pass
        else:
            self.viewportChanged.emit(new_view)
        event.accept()

    def mousePressEvent(self, event):
        if (event.button() == Qt.MouseButton.LeftButton and
                QRectF(*self.data_rect()).contains(event.position())):
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            self.drag = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.drag is None:
            super().mouseMoveEvent(event)
            return
        delta = event.position() - self.drag
        self.drag = event.position()
        _, _, width, height = self.data_rect()
        view = self.document.viewport
        dx = -delta.x() / width * (view.xmax - view.xmin)
        dy = delta.y() / height * (view.ymax - view.ymin)
        try:
            new_view = Viewport(view.xmin + dx, view.xmax + dx, view.ymin + dy, view.ymax + dy)
        except ValueError:
            return
        self.viewportChanged.emit(new_view)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag = None
            self.unsetCursor()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = self.palette()
        painter.fillRect(self.rect(), palette.base())
        painter.setPen(palette.text().color())
        bounds = self.data_rect()
        rect = QRectF(*bounds)
        painter.drawRect(rect)
        view = self.document.viewport
        for i in range(5):
            fraction = i / 4
            x = rect.left() + fraction * rect.width()
            y = rect.bottom() - fraction * rect.height()
            painter.drawText(QPointF(x - 12, rect.bottom() + 17),
                             f'{view.xmin + fraction * (view.xmax - view.xmin):.3g}')
            painter.drawText(QPointF(2, y + 4),
                             f'{view.ymin + fraction * (view.ymax - view.ymin):.3g}')
        painter.setClipRect(rect)
        painter.setPen(palette.mid().color())
        x, y = view.screen(0, 0, bounds)
        if rect.left() <= x <= rect.right():
            painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
        if rect.top() <= y <= rect.bottom():
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
        for series in self.document.series:
            if not series.visible:
                continue
            painter.setPen(QPen(QColor(series.color), 2))
            if isinstance(series, Points):
                painter.setBrush(QColor(series.color))
                for x, y in series.points:
                    px, py = view.screen(x, y, bounds)
                    if rect.adjusted(-4, -4, 4, 4).contains(QPointF(px, py)):
                        painter.drawEllipse(QPointF(px, py), 3, 3)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                continue
            for segment in self.curves.get(series.id, ()):
                path = QPainterPath()
                started = False
                for x, y in segment:
                    px, py = view.screen(x, y, bounds)
                    if math.isfinite(px) and math.isfinite(py):
                        (path.lineTo if started else path.moveTo)(px, py)
                        started = True
                    else:
                        started = False
                painter.drawPath(path)
        painter.end()
        self.painted.emit(self.revision)


@lru_cache(maxsize=128)
def compile_formula(text):
    try:
        return parse(text), ''
    except ExpressionError as error:
        return None, str(error)


def calculate(snapshot, cancel):
    revision, formulas, view, width, height = snapshot
    curves, errors = {}, {}
    for identifier, text, parameters in formulas:
        if cancel.is_set():
            break
        expression, error = compile_formula(text)
        if error:
            errors[identifier] = error
        else:
            curves[identifier] = sample(expression, parameters, view, width, height, cancel.is_set)
    return revision, curves, errors


class PlotEditor(QWidget):
    completed = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_studio = parent
        self.canvas = PlotCanvas()
        self.document = self.canvas.document
        self.dirty = False
        self.path = None
        self.drafts = {}
        self.series_list = QListWidget()
        self.series_list.setMaximumHeight(125)
        self.expression = QLineEdit()
        self.expression.setMaxLength(MAX_EXPRESSION)
        self.expression.setToolTip('Decimal numbers start with a digit. Use x, a, b, c, '
                                   '+, -, *, /, ^, sin, cos and pow. Angles are in radians. '
                                   'Parameters default to 1 and range from -10 to 10 in steps of 0.01.')
        self.diagnostic = QLabel()
        self.diagnostic.setWordWrap(True)
        self.parameter_controls = {}
        formula = QWidget()
        formula_layout = QVBoxLayout(formula)
        formula_layout.addWidget(QLabel('y ='))
        formula_layout.addWidget(self.expression)
        formula_layout.addWidget(self.diagnostic)
        for key in PARAMETERS:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.addWidget(QLabel(key))
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(-1000, 1000)
            number = QDoubleSpinBox()
            number.setRange(-10, 10)
            number.setSingleStep(.01)
            number.setKeyboardTracking(False)
            row_layout.addWidget(slider)
            row_layout.addWidget(number)
            formula_layout.addWidget(row)
            self.parameter_controls[key] = (row, slider, number)
            slider.valueChanged.connect(lambda v, k=key: self.edit_parameter(k, v / 100))
            number.valueChanged.connect(lambda v, k=key: self.edit_parameter(k, v))
        formula_layout.addStretch()

        points = QWidget()
        points_layout = QVBoxLayout(points)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(['X', 'Y'])
        points_layout.addWidget(self.table)
        points_layout.addLayout(self.buttons(
            ('Add row', self.add_row), ('Remove row', self.remove_row)))
        self.pages = QStackedWidget()
        self.pages.addWidget(QWidget())
        self.pages.addWidget(formula)
        self.pages.addWidget(points)
        side = QWidget()
        side_layout = QVBoxLayout(side)
        side_layout.addLayout(self.buttons(
            ('Add formula', lambda: self.add_series(Formula)),
            ('Add points', lambda: self.add_series(Points))))
        side_layout.addWidget(self.series_list)
        side_layout.addLayout(self.buttons(('Color', self.choose_color), ('Remove', self.remove_series)))
        side_layout.addWidget(self.pages, 1)
        self.splitter = QSplitter()
        self.splitter.addWidget(side)
        self.splitter.addWidget(self.canvas)
        self.splitter.setStretchFactor(1, 1)
        layout = QVBoxLayout(self)
        layout.addLayout(self.buttons(
            ('New', self.new_document), ('Open', self.open_dialog),
            ('Save', self.save_document), ('Save As', lambda: self.save_document(save_as=True)),
            ('Fit', self.fit_view)))
        layout.addWidget(self.splitter)
        self.revision = 0
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='plot')
        self.cancel = None
        self.pending = None
        self.stopped = False
        self.errors = {}
        self.timer = QTimer(self, singleShot=True)
        self.timer.timeout.connect(self.queue_preview)
        self.completed.connect(self.apply_preview, Qt.ConnectionType.QueuedConnection)
        self.canvas.resized.connect(self.schedule)
        self.canvas.viewportChanged.connect(self.set_viewport)
        self.expression.textChanged.connect(self.edit_expression)
        self.series_list.currentRowChanged.connect(self.select_series)
        self.series_list.itemChanged.connect(self.edit_series)
        self.table.cellChanged.connect(self.edit_points)
        self.refresh_series(0)
        self.schedule()

    @staticmethod
    def buttons(*commands):
        layout = QHBoxLayout()
        for label, callback in commands:
            button = QPushButton(label)
            button.clicked.connect(callback)
            layout.addWidget(button)
        return layout

    def selected(self):
        index = self.series_list.currentRow()
        return self.document.series[index] if 0 <= index < len(self.document.series) else None

    def focus_editor(self):
        targets = (self.series_list, self.expression, self.table)
        targets[self.pages.currentIndex()].setFocus()

    def refresh_series(self, selected):
        with QSignalBlocker(self.series_list):
            self.series_list.clear()
            for series in self.document.series:
                item = QListWidgetItem(series.label)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
                item.setCheckState(Qt.CheckState.Checked if series.visible else Qt.CheckState.Unchecked)
                self.swatch(item, series.color)
                self.series_list.addItem(item)
            self.series_list.setCurrentRow(selected)
        self.select_series(selected)

    @staticmethod
    def swatch(item, color):
        square = QPixmap(12, 12)
        square.fill(QColor(color))
        item.setIcon(QIcon(square))

    def select_series(self, index):
        series = self.selected()
        if isinstance(series, Formula):
            self.pages.setCurrentIndex(1)
            with QSignalBlocker(self.expression):
                self.expression.setText(series.expression)
            self.update_formula_controls(series)
            self.update_diagnostic()
        elif isinstance(series, Points):
            self.pages.setCurrentIndex(2)
            rows = self.drafts.get(series.id, [[str(x), str(y)] for x, y in series.points])
            with QSignalBlocker(self.table):
                self.table.setRowCount(len(rows))
                for row, values in enumerate(rows):
                    for column, value in enumerate(values):
                        self.table.setItem(row, column, QTableWidgetItem(value))
                self.read_table()
        else:
            self.pages.setCurrentIndex(0)

    def add_series(self, kind):
        if len(self.document.series) >= MAX_SERIES:
            return
        color = '#5AB0FF' if kind is Formula else '#F2AF57'
        self.document.series.append(kind(kind.__name__, color))
        self.refresh_series(len(self.document.series) - 1)
        self.changed()

    def remove_series(self):
        index = self.series_list.currentRow()
        if self.selected() is not None:
            series = self.document.series.pop(index)
            self.drafts.pop(series.id, None)
            self.canvas.curves.pop(series.id, None)
            self.refresh_series(min(index, len(self.document.series) - 1))
            self.changed()

    def edit_series(self, item):
        series = self.document.series[self.series_list.row(item)]
        visible = item.checkState() == Qt.CheckState.Checked
        needs_preview = visible and not series.visible
        series.label, series.visible = item.text(), visible
        self.changed(preview=needs_preview)

    def choose_color(self):
        series = self.selected()
        if series is None:
            return
        color = QColorDialog.getColor(QColor(series.color), self, 'Series color')
        if color.isValid() and color.name() != series.color:
            series.color = color.name()
            with QSignalBlocker(self.series_list):
                self.swatch(self.series_list.currentItem(), series.color)
            self.changed(preview=False)

    def edit_expression(self, text):
        series = self.selected()
        series.expression = text
        self.update_formula_controls(series)
        self.changed(60, repaint=False)

    def update_formula_controls(self, series):
        expression, _ = compile_formula(series.expression)
        for key, (row, slider, number) in self.parameter_controls.items():
            row.setVisible(expression is not None and key in expression.parameters)
            value = series.parameters.get(key, 1.)
            with QSignalBlocker(slider), QSignalBlocker(number):
                slider.setValue(round(value * 100))
                number.setValue(value)

    def update_diagnostic(self):
        series = self.selected()
        self.diagnostic.setText(self.errors.get(series.id, '') if isinstance(series, Formula) else '')

    def edit_parameter(self, key, value):
        series = self.selected()
        series.parameters[key] = value
        _, slider, number = self.parameter_controls[key]
        with QSignalBlocker(slider), QSignalBlocker(number):
            slider.setValue(round(value * 100))
            number.setValue(value)
        self.changed(repaint=False)

    def add_row(self):
        count = sum(len(self.drafts.get(s.id, s.points)) for s in self.document.series
                    if isinstance(s, Points))
        if count >= MAX_POINTS:
            return
        row = self.table.rowCount()
        with QSignalBlocker(self.table):
            self.table.insertRow(row)
            for column in range(2):
                self.table.setItem(row, column, QTableWidgetItem(''))
        self.edit_points()
        self.table.setCurrentCell(row, 0)
        self.table.editItem(self.table.item(row, 0))

    def remove_row(self):
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)
            self.edit_points()

    def read_table(self):
        rows, points = [], []
        for row in range(self.table.rowCount()):
            texts, numbers = [], []
            for column in range(2):
                item = self.table.item(row, column)
                texts.append(item.text())
                try:
                    value = float(item.text())
                    if not math.isfinite(value):
                        raise ValueError
                except ValueError:
                    item.setBackground(QColor('#8b2934'))
                else:
                    item.setBackground(QBrush())
                    numbers.append(value)
            rows.append(texts)
            if len(numbers) == 2:
                points.append(tuple(numbers))
        return rows, points

    def edit_points(self, *_):
        with QSignalBlocker(self.table):
            rows, points = self.read_table()
        series = self.selected()
        self.drafts[series.id] = rows
        series.points = points
        self.changed(preview=False)

    def changed(self, delay=16, preview=True, repaint=True):
        self.dirty = True
        if preview:
            self.schedule(delay)
        if repaint:
            self.canvas.update()

    def commit_table_editor(self):
        focused = QApplication.focusWidget()
        if focused is not None and focused is not self.table and self.table.isAncestorOf(focused):
            self.table.setFocus()

    def confirm_replace(self):
        self.commit_table_editor()
        if not self.dirty:
            return True
        buttons = QMessageBox.StandardButton
        answer = QMessageBox.question(self, 'Plot Editor', 'Save changes to the current plot?',
                                      buttons.Save | buttons.Discard | buttons.Cancel, buttons.Save)
        if answer == buttons.Save:
            return self.save_document()
        return answer == buttons.Discard

    def replace_document(self, document, path):
        self.document = self.canvas.document = document
        self.path = path
        self.dirty = False
        self.drafts.clear()
        self.errors.clear()
        self.canvas.curves.clear()
        self.canvas.revision = -1
        self.refresh_series(0 if document.series else -1)
        self.schedule()
        self.canvas.update()

    def new_document(self):
        if self.confirm_replace():
            self.replace_document(PlotDocument(), None)

    def open_dialog(self):
        filename, _ = QFileDialog.getOpenFileName(self, 'Open plot', '', 'Plot files (*.pmplot)')
        if filename:
            self.open_document(Path(filename))

    def open_document(self, path, restoring=False):
        try:
            document = load_plot(path)
        except (OSError, ValueError) as error:
            message = f'Cannot open {path.name}: {error}'
            if restoring:
                QTimer.singleShot(0, lambda: self.parent_studio.statusBar().showMessage(message, 12000))
            else:
                QMessageBox.warning(self, 'Plot Editor', message)
            return False
        if not restoring and not self.confirm_replace():
            return False
        self.replace_document(document, path)
        if not restoring:
            self.parent_studio.show_plot_editor()
        return True

    def save_document(self, checked=False, *, save_as=False):
        self.commit_table_editor()
        for series in self.document.series:
            if isinstance(series, Points) and len(self.drafts.get(series.id, series.points)) != len(series.points):
                QMessageBox.warning(self, 'Plot Editor',
                                    f'Correct or remove incomplete rows in {series.label} before saving.')
                return False
        path = self.path
        if path is None or save_as:
            filename, _ = QFileDialog.getSaveFileName(
                self, 'Save plot', str(path or 'untitled.pmplot'), 'Plot files (*.pmplot)')
            if not filename:
                return False
            path = Path(filename)
            if path.suffix.lower() != '.pmplot':
                path = path.with_name(path.name + '.pmplot')
        try:
            save_plot(path, self.document)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, 'Plot Editor', f'Cannot save {path.name}: {error}')
            return False
        self.path = path
        self.dirty = False
        self.parent_studio.statusBar().showMessage(f'Saved: {path}', 4000)
        return True

    def set_viewport(self, view):
        if view != self.document.viewport:
            self.document.viewport = view
            self.changed()

    def fit_view(self):
        try:
            view = fit(self.document)
        except ValueError as error:
            if self.parent_studio is not None:
                self.parent_studio.statusBar().showMessage(str(error), 5000)
            return
        self.set_viewport(view)

    def schedule(self, delay=16):
        if self.stopped:
            return
        self.revision += 1
        self.pending = None
        if self.cancel:
            self.cancel.set()
        if delay == 60 or not self.timer.isActive():
            self.timer.start(delay)

    def queue_preview(self):
        _, _, width, height = self.canvas.data_rect()
        formulas = [(s.id, s.expression, dict(s.parameters)) for s in self.document.series
                    if isinstance(s, Formula) and s.visible]
        self.pending = (self.revision, formulas, self.document.viewport, width, height)
        self.start_pending()

    def start_pending(self):
        if self.cancel is not None or self.pending is None or self.stopped:
            return
        self.cancel = Event()
        snapshot, self.pending = self.pending, None
        future = self.executor.submit(calculate, snapshot, self.cancel)
        emit = self.completed.emit
        future.add_done_callback(lambda result: emit(result.result()))

    @Slot(object)
    def apply_preview(self, result):
        self.cancel = None
        revision, curves, errors = result
        if not self.stopped and revision == self.revision:
            self.errors = errors
            self.canvas.curves = curves
            self.update_diagnostic()
            self.canvas.revision = revision
            self.canvas.update()
        self.start_pending()

    def shutdown(self):
        self.stopped = True
        self.timer.stop()
        self.pending = None
        if self.cancel:
            self.cancel.set()
        self.executor.shutdown(wait=True)
