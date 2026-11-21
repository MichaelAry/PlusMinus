"""Headless integration check for Qt GUI, including the language editor."""
import os
import sys
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

app = QApplication([])
window = Studio()
window.show()
app.processEvents()
assert len(window.workspace.pages) == 8
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
window.toggle_split_editor()
assert window.split_pane.isVisible(), 'Split view must open'
assert window.secondary_editor.document() is window.editor.document(), 'Split must share the live source document'
window.toggle_split_editor()
window.new_file()
assert window.documents.count() >= 2
window.documents.setCurrentIndex(0)
assert window.editor.toPlainText()
window.open_language_internals('print')
app.processEvents()
assert window.language_window is not None
assert not window.language_window.dirty(), 'Loading a C++ source must not mark it as edited'
assert 'if (c.name == "print")' in window.language_window.editor.toPlainText()
assert not window.language_window.editor.isReadOnly()
window.language_window.close()
window.saved = window.editor.toPlainText()  # No unsaved-edit dialog in a headless test.
window.close()
app.processEvents()
print('Qt startup, eight analytics views, source split and language navigation: OK')
