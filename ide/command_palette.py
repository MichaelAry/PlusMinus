"""Searchable command palette shared by the Research Workbench."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem)


class CommandPalette(QDialog):
    def __init__(self, parent, commands):
        super().__init__(parent)
        self.commands = list(commands)
        self.setWindowTitle("Run a command")
        self.setMinimumWidth(580)
        self.setModal(True)
        layout = QVBoxLayout(self)
        heading = QLabel("COMMAND PALETTE   /   Ctrl+Shift+P")
        heading.setObjectName("researchEyebrow")
        layout.addWidget(heading)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search actions, workspaces and tools…")
        layout.addWidget(self.search)
        self.list = QListWidget()
        layout.addWidget(self.list)
        self.search.textChanged.connect(self.refresh)
        self.search.returnPressed.connect(self.activate)
        self.list.itemDoubleClicked.connect(lambda *_: self.activate())
        self.refresh()
        self.search.setFocus()

    def refresh(self, *_):
        query = self.search.text().strip().casefold()
        self.list.clear()
        for label, handler in self.commands:
            if query and all(token not in label.casefold() for token in query.split()):
                continue
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, handler)
            self.list.addItem(item)
        if self.list.count():
            self.list.setCurrentRow(0)

    def activate(self):
        item = self.list.currentItem()
        if not item:
            return
        callback = item.data(Qt.ItemDataRole.UserRole)
        self.accept()
        if callable(callback):
            callback()
