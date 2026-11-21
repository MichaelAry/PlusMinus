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
assert window.stack.count() == 7
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
print('Qt startup, seven analytics views and language source navigation: OK')
