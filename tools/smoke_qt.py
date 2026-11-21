"""Headless integration check for Qt GUI, including the language editor."""
import os
import sys
import time
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'ide'))
from PySide6.QtWidgets import QApplication
from studio_qt import Studio

# Test only the visual/navigation contract here. The real interpreter startup
# suite is covered separately by studio_qt.py --self-test. Avoid racing a
# background auto-suite with window shutdown on slower Windows CI machines.
Studio.auto_tests = lambda self: None
Studio.discover_native = lambda self: None

app = QApplication([])
window = Studio()
window.show()
app.processEvents()
assert len(window.workspace.pages) == 9
window.nav.setCurrentRow(2)
window.nav.setCurrentRow(1)
assert window.workspace.count() >= 3, 'Sidebar must retain multiple open pages'
assert window.editor.toPlainText()
from pathlib import Path
import tempfile
with tempfile.TemporaryDirectory() as folder:
    example = Path(folder) / 'windows.pm'
    example.write_bytes(b'\xef\xbb\xbfprint(1);\r\nprint(2);\r\n')
    loaded = window.documents.open_path(example)
    assert not loaded.modified, 'Windows BOM+CRLF file must not be marked dirty'
    assert window.documents.save_current()
    assert example.read_bytes().startswith(b'\xef\xbb\xbfprint(1);\r\n')

# Native Test Laboratory status filters and failure-only reruns.
panel = window.native_panel
panel.set_cases([
    {'id':'Math.pass','group':'arithmetic','source':'math.cpp'},
    {'id':'Math.fail','group':'arithmetic','source':'math.cpp'},
    {'id':'Loop.other','group':'control_flow','source':'loop.cpp'},
])
panel.set_result({'id':'Math.pass','status':'PASS','elapsed_ms':2.0})
panel.set_result({'id':'Math.fail','status':'FAIL','elapsed_ms':3.0,'error':'expected mismatch'})
assert [c['id'] for c in panel.nonpassing_cases()] == ['Math.fail']
panel.status_filter.setCurrentText('FAIL')
assert [c['id'] for c in panel.filtered_cases()] == ['Math.fail']
panel.status_filter.setCurrentText('NOT RUN')
assert [c['id'] for c in panel.filtered_cases()] == ['Loop.other']
panel.status_filter.setCurrentText('All statuses')
assert window.research_controller.explorer is not None
assert window.research_controller.inspector is not None
assert window.research_controller.console is not None
explorer = window.research_controller.explorer
assert explorer.isVisible(), 'Persistent left navigation must always be visible'
assert not explorer.toggleViewAction().isEnabled(), 'Left navigation must not be closable'
explorer.hide()  # Simulate an older stored layout that hid the Activity Bar.
window.research_controller.restore_layout()
app.processEvents()
assert explorer.isVisible(), 'Restoring layout must reopen the Activity Bar'
assert window.test_suites.count() == 3, 'Native C++ inspector tab must be present'
window.research_controller.activate('Notebooks')
assert window.nav.currentRow() == 8
assert len(window.notebooks.cells) >= 1
assert window.notebooks.snapshot()['nbformat'] == 4
with tempfile.TemporaryDirectory() as folder:
    document = Path(folder) / 'experiment.ipynb'
    window.notebooks.path = document
    window.notebooks.add_cell('markdown', '# Experiment')
    assert window.notebooks.save_file()
    assert document.is_file()
    from notebook_format import load_notebook
    assert len(load_notebook(document)['cells']) == 2
    assert window.save_active(), 'Save in Notebook mode must save .ipynb'
    first = window.notebooks.cells[0]
    assert first.kind == 'code'
    window.notebooks.run_cell(first)
    deadline = time.monotonic() + 15
    while window.notebooks.worker is not None and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.02)
    app.processEvents()
    assert window.notebooks.worker is None, 'Notebook C++ execution timed out'
    assert '4' in first.output.toPlainText(), 'Notebook must show actual runner output'
    assert 'Wall' in first.stats.text(), 'Notebook must show runtime metrics'
    assert len(window.notebooks.cells) == 3, 'Running final code cell must append a blank cell'
    assert window.notebooks.cells[-1].editor.toPlainText() == ''
    window.notebooks.run_cell(first)
    deadline = time.monotonic() + 15
    while window.notebooks.worker is not None and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.02)
    app.processEvents()
    assert len(window.notebooks.cells) == 3, 'Rerun must not create duplicate blank cells'
    assert window.notebooks.save_file()
    reloaded = load_notebook(document)
    assert len(reloaded['cells']) == 3
    assert reloaded['cells'][0]['metadata']['plusminus_run']['ok']
window.nav.setCurrentRow(1)
# A real output view and detailed native metrics must be visible together.
window.record = lambda *args: None
window.refresh_history = lambda: None
window.research_controller.console.hide()
report = dict(ok=True, output='hello\\n', result=0,
              variables='x = 0', bytecode='', error='', diagnostics=[],
              trace=[], trace_truncated=False, ms=32.5,
              metrics={'compile_ms': 1.7, 'execute_ms': 2.1,
                       'peak_rss_mb': 13.0, 'samples': [[0, 13.0, 1, 1.1]]})
window.show_report(report, 'print(1);', 'Run')
app.processEvents()
assert window.research_controller.console.isVisible(), 'Execution must reopen output dock'
assert window.result_tabs.currentWidget() is window.run_report_widget
assert 'hello' in window.output.toPlainText()
assert 'Return value: 0' in window.output.toPlainText()
assert '32.50 ms' in window.run_details.toPlainText()
assert '13.00 MB' in window.run_details.toPlainText()
window.research_controller.console.hide()
failed = dict(report, ok=False, output='', result='', error='synthetic compile error')
window.show_report(failed, 'invalid;', 'Run')
app.processEvents()
assert window.research_controller.console.isVisible(), 'Failed execution must reopen dock'
assert 'synthetic compile error' in window.run_details.toPlainText()
assert 'Execution failed' in window.output.toPlainText()

window.toggle_split_editor()
assert window.split_pane.isVisible(), 'Split view must open'
assert window.secondary_editor.document() is window.editor.document(), 'Split must share the live source document'
window.toggle_split_editor()
window.new_file()
assert window.documents.count() >= 2
window.documents.setCurrentIndex(0)
assert window.editor.toPlainText()
# Ctrl+click symbol navigation must open the actual C++ source in an editor tab.
window.open_language_internals('int')
app.processEvents()
assert window.documents.current_document().path.name == 'statements.cpp'
assert 'if (checkKeyword("int"))' in window.editor.toPlainText()
# Explicit Language Internals action must still open the independent native editor.
window.open_language_internals()
app.processEvents()
assert window.language_window is not None
window.language_window.select_symbol('print')
assert not window.language_window.dirty(), 'Loading a C++ source must not mark it as edited'
assert 'if (c.name == "print")' in window.language_window.editor.toPlainText()
assert not window.language_window.editor.isReadOnly()
window.language_window.close()
window.saved = window.editor.toPlainText()  # No unsaved-edit dialog in a headless test.
window.close()
app.processEvents()
print('Qt startup, eight analytics views, source split and language navigation: OK')
