"""Independent source documents, per-tab dirty tracking and persistence."""
from dataclasses import dataclass
from pathlib import Path
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QTabWidget, QFileDialog, QMessageBox

@dataclass
class SourceDocument:
    editor: object
    path: Path | None
    saved: str
    line_ending: str = '\n'
    bom: bool = False

    @property
    def modified(self):
        return self.editor.toPlainText() != self.saved

class DocumentTabs(QTabWidget):
    activated = Signal(object)
    savedFile = Signal(str)
    documentsChanged = Signal()

    def __init__(self, factory, parent=None):
        super().__init__(parent)
        self.factory = factory
        self._documents = {}
        self.setTabsClosable(True)
        self.setMovable(True)
        self.setDocumentMode(True)
        self.currentChanged.connect(self._activated)
        self.tabCloseRequested.connect(self.close_tab)

    def current_document(self):
        return self._documents.get(self.currentWidget())

    def all_documents(self):
        return list(self._documents.values())

    def new_document(self, content='', path=None, bom=False):
        editor = self.factory()
        newline = '\r\n' if '\r\n' in content else ('\r' if '\r' in content else '\n')
        content = content.replace('\r\n','\n').replace('\r','\n')
        doc = SourceDocument(editor, Path(path).resolve() if path else None,
                             content, newline, bom)
        self._documents[editor] = doc
        index = self.addTab(editor, '')
        editor.setPlainText(content)
        editor.textChanged.connect(lambda e=editor: self._update_caption(e))
        self._update_caption(editor)
        self.setCurrentIndex(index)
        self.activated.emit(doc)
        self.documentsChanged.emit()
        return doc

    def open_path(self, path):
        path = Path(path).resolve()
        for doc in self._documents.values():
            if doc.path == path:
                self.setCurrentWidget(doc.editor)
                return doc
        raw = path.read_bytes()
        return self.new_document(raw.decode('utf-8-sig'), path,
                                 raw.startswith(b'\xef\xbb\xbf'))

    def _update_caption(self, editor):
        doc = self._documents.get(editor)
        if doc is None:
            return
        index = self.indexOf(editor)
        if index >= 0:
            title = doc.path.name if doc.path else f'untitled-{index+1}.pm'
            self.setTabText(index, ('● ' if doc.modified else '') + title)
            self.setTabToolTip(index, str(doc.path) if doc.path else 'Unsaved source')

    def _activated(self, index):
        if index >= 0 and self.current_document() is not None:
            self.activated.emit(self.current_document())

    def save_current(self):
        doc = self.current_document()
        if doc is None:
            return False
        if doc.path is None:
            filename, _ = QFileDialog.getSaveFileName(
                self, 'Save source', 'main.pm', 'PlusMinus (*.pm);;All files (*)')
            if not filename:
                return False
            dest = Path(filename).resolve()
            if any(other is not doc and other.path == dest for other in self._documents.values()):
                QMessageBox.warning(self, 'Already open', 'This file is already open in another tab.')
                return False
            doc.path = dest
        try:
            content = doc.editor.toPlainText().replace('\n', doc.line_ending)
            payload = (b'\xef\xbb\xbf' if doc.bom else b'') + content.encode('utf-8')
            doc.path.write_bytes(payload)
        except OSError as exc:
            QMessageBox.critical(self, 'Save failed', str(exc))
            return False
        doc.saved = doc.editor.toPlainText()
        self._update_caption(doc.editor)
        self.savedFile.emit(str(doc.path))
        self.activated.emit(doc)
        self.documentsChanged.emit()
        return True

    def maybe_save(self, doc):
        if doc is None or not doc.modified:
            return True
        answer = QMessageBox.question(
            self, 'Unsaved changes', f"Save {doc.path.name if doc.path else 'untitled'}?",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard |
            QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Save)
        if answer == QMessageBox.StandardButton.Cancel:
            return False
        if answer == QMessageBox.StandardButton.Save:
            self.setCurrentWidget(doc.editor)
            return self.save_current()
        return True

    def close_tab(self, index):
        editor = self.widget(index)
        if not self.maybe_save(self._documents.get(editor)):
            return False
        self.removeTab(index)
        self._documents.pop(editor, None)
        self.documentsChanged.emit()
        editor.deleteLater()
        if self.count() == 0:
            self.new_document()
        return True

    def confirm_all(self):
        return all(self.maybe_save(doc) for doc in self.all_documents())

    def open_paths(self):
        return [str(doc.path) for doc in self.all_documents() if doc.path]
