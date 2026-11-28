"""Plot editor checks run by the Qt smoke suite."""
from pathlib import Path
import statistics
from threading import Event, Timer
import time
from unittest.mock import patch

from PySide6.QtCore import QPoint, QPointF, QSettings, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox, QPushButton

import plot_editor
from plot_model import Formula, PlotDocument, Points, Viewport, load_plot


def wait_for(check, timeout=4):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        QApplication.processEvents()
        if check():
            return
        time.sleep(.001)
    raise AssertionError('Timed out waiting for plot editor')


def wait_preview(plot):
    wait_for(lambda: plot.canvas.revision == plot.revision)


def run(studio, folder, benchmark=False):
    root = Path(folder)
    window = studio()
    window.show()
    wait_for(window.isVisible)
    plot = window.plot_editor
    try:
        assert window.plot_dock.isHidden()
        menu = window.menuBar().actions()[0].menu()
        assert menu.title() == 'View'
        menu.actions()[0].trigger()
        wait_preview(plot)
        assert plot.canvas.curves and not plot.dirty
        plot.expression.setText('x^2')
        window.plot_dock.setFloating(True)
        window.plot_dock.close()
        window.show_plot_editor()
        assert plot.expression.text() == 'x^2'
        wait_preview(plot)

        entered, release = Event(), Event()
        calculate = plot_editor.calculate
        old_revision = plot.revision + 1

        def delayed(snapshot, cancel):
            if snapshot[0] == old_revision:
                entered.set()
                release.wait(2)
                return calculate(snapshot, Event())
            return calculate(snapshot, cancel)

        painted_revisions = []
        plot.canvas.painted.connect(painted_revisions.append)
        with patch.object(plot_editor, 'calculate', delayed):
            plot.expression.setText('cos(x)')
            wait_for(entered.is_set)
            plot.expression.setText('a*sin(x)')
            wait_for(lambda: plot.pending is not None)
            assert plot.pending[0] == plot.revision
            old_painted = plot.canvas.revision
            release.set()
            wait_preview(plot)
            assert old_painted < old_revision < plot.canvas.revision
            assert old_revision not in painted_revisions

        plot.parameter_controls['a'][1].setFocus()
        QTest.keyClick(plot.parameter_controls['a'][1], Qt.Key.Key_Right)
        assert plot.selected().parameters['a'] == 1.01
        plot.add_series(Formula)
        plot.expression.setText('cos(x)')
        plot.add_series(Points)
        for row, pair in enumerate([('0', '0'), ('1', '0.84'), ('2', '0.91')]):
            plot.add_row()
            QTest.keyClick(QApplication.focusWidget(), Qt.Key.Key_Escape)
            for col, value in enumerate(pair):
                plot.table.item(row, col).setText(value)
        assert plot.selected().points == [(0, 0), (1, .84), (2, .91)]
        item = plot.table.item(1, 1)
        item.setText('invalid')
        assert plot.selected().points == [(0, 0), (2, .91)]
        with patch.object(QMessageBox, 'warning') as warning:
            assert not plot.save_document()
            assert warning.called
        assert item.text() == 'invalid'
        item.setText('0.84')
        wait_preview(plot)
        assert len(plot.canvas.curves) == 2
        first = plot.series_list.item(0)
        first.setCheckState(Qt.CheckState.Unchecked)
        assert not plot.document.series[0].visible
        first.setCheckState(Qt.CheckState.Checked)
        plot.series_list.setCurrentRow(0)
        plot.expression.setFocus()
        plot.expression.setCursorPosition(2)
        wait_preview(plot)
        assert plot.expression.cursorPosition() == 2

        rect = plot.canvas.data_rect()
        view = plot.document.viewport
        pos = QPointF(*view.screen(1, .84, rect))
        event = QWheelEvent(pos, QPointF(plot.canvas.mapToGlobal(pos.toPoint())),
                            QPoint(), QPoint(0, 120), Qt.MouseButton.NoButton,
                            Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
        QApplication.sendEvent(plot.canvas, event)
        new_view = plot.document.viewport
        assert new_view.xmax - new_view.xmin < view.xmax - view.xmin
        assert all(abs(a - b) < 1 for a, b in zip(new_view.screen(1, .84, rect), (pos.x(), pos.y())))
        start = pos.toPoint()
        QTest.mousePress(plot.canvas, Qt.MouseButton.LeftButton, pos=start)
        QTest.mouseMove(plot.canvas, start + QPoint(20, 15))
        QTest.mouseRelease(plot.canvas, Qt.MouseButton.LeftButton, pos=start + QPoint(20, 15))
        assert plot.document.viewport != new_view

        window.plot_dock.resize(1390, 650)
        wait_preview(plot)
        path = root / 'experiment.pmplot'
        with patch.object(QFileDialog, 'getSaveFileName', return_value=(str(path), '')):
            window.show_plot_editor()
            wait_for(lambda: QApplication.focusWidget() is plot.expression)
            QTest.keyClick(plot.expression, Qt.Key.Key_S, Qt.KeyboardModifier.ControlModifier)
            wait_for(path.exists)
        saved = load_plot(path)
        assert saved == plot.document and not plot.dirty

        plot.expression.setText('sin(')
        wait_preview(plot)
        assert 'column' in plot.diagnostic.text()
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Cancel):
            assert not plot.open_document(path)
            assert not window.close()
        assert plot.expression.text() == 'sin(' and plot.path == path and plot.dirty
        bad = root / 'invalid.pmplot'
        bad.write_text('{', encoding='utf-8')
        with patch.object(QMessageBox, 'warning'):
            assert not plot.open_document(bad)
        assert plot.expression.text() == 'sin(' and plot.dirty

        with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Discard):
            with patch.object(QFileDialog, 'getOpenFileName', return_value=(str(path), '')):
                window.open_file()
        assert plot.document == saved and not plot.dirty
        tree = window.research_controller.explorer_tree
        index = tree.model().index(str(path))
        assert index.isValid()
        tree.doubleClicked.emit(index)
        assert plot.document == saved and plot.path == path
        window.plot_dock.setFloating(False)
        window.show_plot_editor()
        plot.expression.setText('2*a*sin(x)')
        header_save = next(button for button in window.centralWidget().findChildren(QPushButton)
                           if button.text() == 'Save')
        QTest.mouseClick(header_save, Qt.MouseButton.LeftButton)
        saved = load_plot(path)
        plot.expression.setText('a')
        with patch.object(QFileDialog, 'getSaveFileName', return_value=(str(root / 'missing' / path.name), '')):
            with patch.object(QMessageBox, 'warning'):
                assert not plot.save_document(save_as=True)
        assert plot.path == path and plot.dirty and load_plot(path) == saved
        plot.replace_document(saved, path)
        assert saved.series[0].expression == '2*a*sin(x)'

        source = root / 'test.pm'
        source.write_text('print(1);', encoding='utf-8')
        window.read_file(source)
        window.editor.setPlainText('print(2);')
        window.editor.setFocus()
        wait_for(lambda: not window.plot_is_active)
        assert window.save_active()
        assert 'print(2);' in source.read_text(encoding='utf-8')
        window.research_controller.activate('Notebooks')
        window.notebooks.path = root / 'test.ipynb'
        assert window.save_active() and window.notebooks.path.is_file()
        if benchmark:
            window.show_plot_editor()
            measure(window)
            plot.replace_document(saved, path)

        assert window.close()
        window.settings.sync()
        reopened = studio()
        try:
            assert reopened.plot_editor.path == path
            assert reopened.plot_editor.document == saved
            assert not reopened.plot_editor.dirty
        finally:
            assert reopened.close()
    finally:
        plot.shutdown()

    # Use an empty session so notebook restoration is outside this worker test.
    settings = QSettings('PlusMinus', 'Studio4')
    settings.clear()
    settings.sync()
    window = studio()
    plot = window.plot_editor
    entered.clear()
    release.clear()
    old_revision = plot.revision
    with patch.object(plot_editor, 'calculate', delayed):
        wait_for(entered.is_set)
        Timer(.05, release.set).start()
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Discard):
            assert window.close()
    print('Plot Editor round trip, save routing, stale result and shutdown: OK')


def measure(window):
    plot = window.plot_editor
    window.plot_dock.setFloating(True)
    window.plot_dock.resize(1400, 650)
    document = PlotDocument(Viewport(), [Formula(text, '#5AB0FF', expression=text)
                                        for text in ('sin(x)', 'cos(x)', 'a*sin(x)')])
    plot.replace_document(document, None)
    plot.splitter.setSizes([320, 1067])
    plot.series_list.setCurrentRow(2)
    painted = {}
    plot.canvas.painted.connect(lambda revision: painted.setdefault(revision, time.perf_counter()))
    wait_for(lambda: plot.revision in painted)
    for kind in ('slider', 'formula'):
        samples = []
        for i in range(35):
            painted.clear()
            start = time.perf_counter()
            if kind == 'slider':
                plot.parameter_controls['a'][1].setValue(130 + i)
            else:
                plot.expression.setText(f'a*sin(x)+0.{i:02d}')
            wait_for(lambda: plot.revision in painted)
            samples.append((painted[plot.revision] - start) * 1000)
        result = sorted(samples[5:])
        print(f'{kind} at {plot.canvas.data_rect()[2]} px: median '
              f'{statistics.median(result):.2f} ms, P95 {result[28]:.2f} ms')
