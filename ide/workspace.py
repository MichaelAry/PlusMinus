"""Workspace navigation with independent, closable and movable page tabs."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QTabWidget


class WorkspaceTabs(QTabWidget):
    pageActivated = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pages = []
        self.setTabsClosable(True)
        self.setMovable(True)
        self.setDocumentMode(True)
        self.tabCloseRequested.connect(self.close_tab)
        self.currentChanged.connect(self._changed)

    def register_page(self, title, widget):
        self.pages.append((title, widget))

    def open_page(self, number):
        if not 0 <= number < len(self.pages):
            return
        title, widget = self.pages[number]
        index = self.indexOf(widget)
        if index < 0:
            index = self.addTab(widget, title)
        self.setCurrentIndex(index)

    def close_tab(self, index):
        if 0 <= index < self.count() and self.count() > 1:
            self.removeTab(index)

    def _changed(self, index):
        if index >= 0:
            widget = self.widget(index)
            for index, (_, page) in enumerate(self.pages):
                if widget is page:
                    self.pageActivated.emit(index)
                    break

    def open_page_ids(self):
        return [i for i, (_, page) in enumerate(self.pages) if self.indexOf(page) >= 0]

    def restore_pages(self, values):
        for raw in values:
            try:
                self.open_page(int(raw))
            except (TypeError, ValueError):
                pass
