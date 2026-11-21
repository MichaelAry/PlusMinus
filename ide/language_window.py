"""Separate editable C++ compiler/VM window opened from Ctrl+click in the IDE."""
from __future__ import annotations

import os
import re
import shutil
import tempfile
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat, QTextCursor, QShortcut, QKeySequence
from PySide6.QtWidgets import (QCheckBox, QComboBox, QHBoxLayout, QLabel, QMainWindow,
                               QMessageBox, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget)

from internals import SYMBOLS, SourceTarget, editable_checkout, locate_target, source_targets


class CppSyntax(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.rules = []
        for regex, color in [
            (r'\b(?:class|struct|enum|namespace|void|bool|double|int|auto|return|break|continue|if|else|while|for|switch|case|const|static|public|private|try|catch|throw|using|std|size_t|true|false|nullptr|template|typename)\b', '#b9c9e7'),
            (r'"(?:\\.|[^"\\])*"', '#a8cdb1'),
            (r'//[^\n]*', '#8995a5'),
            (r'#\s*(?:include|define|ifdef|ifndef|endif|pragma)\b', '#d8c28c'),
        ]:
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            self.rules.append((re.compile(regex), fmt))

    def highlightBlock(self, text):
        for regex, fmt in self.rules:
            for match in regex.finditer(text):
                self.setFormat(match.start(), match.end() - match.start(), fmt)


class LanguageSourceWindow(QMainWindow):
    """Edit only interpreter source files, preserving backups and external edits."""
    sourceSaved = Signal(str)
    rebuildRequested = Signal()
    CORE = (
        SourceTarget('include/plusminus/bytecode.hpp', 'enum class OpCode', 'VM value types and opcodes'),
        SourceTarget('ide/runner.cpp', 'int main(', 'Runner / JSON protocol'),
    )

    def __init__(self, root: Path, parent=None):
        super().__init__(parent)
        self.root = Path(root).resolve()
        self.current_path: Path | None = None
        self.loaded_text = ''
        self.loaded_bytes = b''
        self.keyword = 'if'
        self.targets = ()
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.setWindowTitle('PlusMinus Studio — Language Internals')
        self.resize(1130, 755)
        self.setMinimumSize(800, 530)
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(18, 14, 18, 14)

        row = QHBoxLayout()
        row.addWidget(QLabel('LANGUAGE INTERNALS  /  C++ SOURCES'))
        row.addStretch()
        row.addWidget(QLabel('Keyword'))
        self.symbol_selector = QComboBox()
        self.symbol_selector.addItems(sorted(SYMBOLS))
        self.symbol_selector.currentTextChanged.connect(self.navigate_symbol)
        row.addWidget(self.symbol_selector)
        self.target_selector = QComboBox()
        self.target_selector.currentIndexChanged.connect(self.navigate_target)
        row.addWidget(self.target_selector, 1)
        layout.addLayout(row)

        self.description = QLabel()
        self.description.setWordWrap(True)
        self.description.setStyleSheet('color: #adc0d6; font-size: 10pt; padding: 8px;')
        layout.addWidget(self.description)
        self.location_label = QLabel()
        layout.addWidget(self.location_label)
        self.editor = QPlainTextEdit()
        self.editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        font = QFont('Cascadia Code', 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.editor.setFont(font)
        self.syntax = CppSyntax(self.editor.document())
        self.editor.textChanged.connect(self.mark_dirty)
        layout.addWidget(self.editor, 1)

        self.info = QLabel('This editor changes the native C++ interpreter. Save and rebuild before running new code.')
        self.info.setWordWrap(True)
        self.info.setStyleSheet('color: #d8c28c; padding: 7px;')
        layout.addWidget(self.info)
        actions = QHBoxLayout()
        self.auto_build = QCheckBox('Rebuild + run built-in tests after Save')
        self.auto_build.setChecked(True)
        actions.addWidget(self.auto_build)
        actions.addStretch()
        save = QPushButton('Save C++  Ctrl+S')
        save.clicked.connect(self.save_source)
        actions.addWidget(save)
        rebuild = QPushButton('Rebuild & test')
        rebuild.clicked.connect(self.rebuildRequested.emit)
        actions.addWidget(rebuild)
        layout.addLayout(actions)
        self.save_shortcut = QShortcut(QKeySequence('Ctrl+S'), self)
        self.save_shortcut.activated.connect(self.save_source)
        if not editable_checkout(self.root):
            self.editor.setReadOnly(True)
            self.info.setText('This feature requires an editable PlusMinus source checkout, not a bundled binary.')
        self.select_symbol('if')

    def dirty(self):
        return self.current_path is not None and self.editor.toPlainText() != self.loaded_text

    def mark_dirty(self):
        self.setWindowTitle('PlusMinus Studio — Language Internals' + (' • Unsaved' if self.dirty() else ''))

    def confirm_leave(self):
        if not self.dirty():
            return True
        choice = QMessageBox.question(self, 'Unsaved C++ changes', 'Save edited interpreter source?',
                    QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard |
                    QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Save)
        if choice == QMessageBox.StandardButton.Cancel:
            return False
        return self.save_source() if choice == QMessageBox.StandardButton.Save else True

    def select_symbol(self, name):
        if name not in SYMBOLS:
            return
        if name == self.keyword and self.current_path is not None:
            return
        if not self.confirm_leave():
            self.symbol_selector.blockSignals(True)
            self.symbol_selector.setCurrentText(self.keyword)
            self.symbol_selector.blockSignals(False)
            return
        self.keyword = name
        self.description.setText(f'{name} — {SYMBOLS[name].description}')
        self.targets = source_targets(name) + self.CORE
        self.symbol_selector.blockSignals(True)
        self.symbol_selector.setCurrentText(name)
        self.symbol_selector.blockSignals(False)
        self.target_selector.blockSignals(True)
        self.target_selector.clear()
        for target in self.targets:
            self.target_selector.addItem(f'{target.label} · {target.file}')
        index = 1 if SYMBOLS[name].runtime and name in (
            'print','len','resize','sin','cos','pow','fact','multifact') else 0
        self.target_selector.setCurrentIndex(index)
        self.target_selector.blockSignals(False)
        self.navigate_target(index)

    def navigate_symbol(self, name):
        self.select_symbol(name)

    def navigate_target(self, index):
        if index < 0 or index >= len(self.targets):
            return
        target = self.targets[index]
        try:
            path, line = locate_target(self.root, target)
        except (OSError, ValueError) as exc:
            self.info.setText(str(exc))
            return
        if self.current_path != path:
            if not self.confirm_leave():
                self.target_selector.blockSignals(True)
                previous = next((i for i,t in enumerate(self.targets)
                    if (self.root/t.file).resolve() == self.current_path), 0)
                self.target_selector.setCurrentIndex(previous)
                self.target_selector.blockSignals(False)
                return
            try:
                raw = path.read_bytes()
                contents = raw.decode('utf-8-sig')
            except (OSError, UnicodeError) as exc:
                QMessageBox.warning(self, 'Read error', str(exc))
                return
            self.current_path = path
            self.loaded_text = contents
            self.loaded_bytes = raw
            self.editor.setPlainText(contents)
        offset = self.editor.toPlainText().find(target.anchor)
        if offset < 0:
            self.info.setText(f'C++ source anchor is not present in edited text: {target.anchor}')
            return
        cursor = self.editor.textCursor()
        cursor.setPosition(offset)
        cursor.select(QTextCursor.SelectionType.LineUnderCursor)
        self.editor.setTextCursor(cursor)
        self.editor.centerCursor()
        current_line = self.editor.toPlainText().count('\n', 0, offset)+1
        self.location_label.setText(f'{path.relative_to(self.root)} · line {current_line} · {target.label}')
        self.mark_dirty()

    def save_source(self):
        if not self.current_path or self.editor.isReadOnly():
            QMessageBox.information(self, 'Read only', 'An editable source checkout is required.')
            return False
        if not self.dirty():
            return True
        path = self.current_path
        try:
            if path.read_bytes() != self.loaded_bytes:
                QMessageBox.warning(self, 'External modification',
                  'This source file changed on disk. Save was blocked to protect external changes. '
                  'Close and reopen Language Internals to reload it.')
                return False
            backups = self.root/'.plusminus-backups'
            backups.mkdir(exist_ok=True)
            shutil.copy2(path, backups/(path.name+'.bak'))
            bom = b'\xef\xbb\xbf' if self.loaded_bytes.startswith(b'\xef\xbb\xbf') else b''
            new_bytes = bom+self.editor.toPlainText().encode('utf-8')
            mode = path.stat().st_mode
            handle, temporary = tempfile.mkstemp(prefix='.plusminus-',suffix='.tmp',dir=str(path.parent))
            try:
                with os.fdopen(handle,'wb') as stream:
                    stream.write(new_bytes)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.chmod(temporary,mode)
                os.replace(temporary,path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
            self.loaded_text = self.editor.toPlainText()
            self.loaded_bytes = new_bytes
            self.mark_dirty()
            self.info.setText(f'Saved {path.relative_to(self.root)}. Backup in .plusminus-backups/. '
                              'A successful C++ rebuild is required before the changes execute.')
            self.sourceSaved.emit(str(path))
            return True
        except (OSError, UnicodeError) as exc:
            QMessageBox.critical(self,'Save failed',str(exc))
            return False

    def closeEvent(self, event):
        if not self.confirm_leave():
            event.ignore()
            return
        event.accept()
