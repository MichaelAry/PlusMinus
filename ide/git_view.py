"""Read-only Git panel for PlusMinus Studio."""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton
from git_service import repository_summary


class GitPanel(QWidget):
    def __init__(self, root, parent=None):
        super().__init__(parent)
        self.root = root
        layout=QVBoxLayout(self)
        bar=QHBoxLayout()
        self.status=QLabel('Git status not loaded')
        bar.addWidget(self.status,1)
        refresh=QPushButton('Refresh')
        refresh.clicked.connect(self.refresh)
        bar.addWidget(refresh)
        layout.addLayout(bar)
        self.details=QPlainTextEdit()
        self.details.setReadOnly(True)
        layout.addWidget(self.details,1)
        self.refresh()

    def refresh(self):
        state=repository_summary(self.root)
        if not state['available']:
            self.status.setText('No local Git checkout available')
            self.details.setPlainText(state['error'])
            return
        self.status.setText(f"{state['branch']} · {state['sha']} · "
                            + ('modified' if state['dirty'] else 'clean'))
        self.details.setPlainText(
            'CHANGED FILES\n'+state['changes']+'\n\nDIFF SUMMARY\n'+state['diff']
            +'\n\nRECENT COMMITS\n'+state['commits'])
