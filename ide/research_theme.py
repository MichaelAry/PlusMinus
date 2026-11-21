"""Graphite Research visual system for PlusMinus Studio 4.0.

Widgets use semantic object names rather than one-off inline styles.
"""
GRAPHITE_QSS = """
QWidget { background-color: #11151A; color: #E0E5EC;
          font-family: "Segoe UI", "Inter", sans-serif; font-size: 10pt; }
QMainWindow { background: #11151A; }
QFrame#activityRail { background: #141920; border-right: 1px solid #303841; }
QFrame#researchHeader { background: #181D24; border-bottom: 1px solid #303841; }
QFrame#panel { background: #1B2027; border: 1px solid #343D49; border-radius: 6px; }
QLabel#section { color: #E0E5EC; font-weight: 700; font-size: 17px; }
QLabel#muted { color: #9AA6B3; }
QLabel#metric { color: #F1F3F6; font-weight: 700; font-size: 24px; }
QLabel#researchBrand { color: #DFD6C6; font-weight: 800; font-size: 13px; }
QLabel#researchEyebrow { color: #8E9BAA; font-size: 10px; letter-spacing: 1px; }
QLabel#kernelWarning { color: #D8B477; background: #29271F;
                       padding: 7px; border: 1px solid #514735; border-radius: 5px; }
QPushButton, QToolButton {
    background: #252C35; color: #DDE3EB; border: 1px solid #37414B;
    border-radius: 5px; padding: 6px 10px; font-weight: 550;
}
QPushButton:hover, QToolButton:hover { background: #313A44; border-color: #546271; }
QPushButton:pressed, QToolButton:pressed { background: #394550; }
QPushButton:disabled, QToolButton:disabled {
    background: #1D2229; color: #717E8B; border-color: #303841;
}
QPushButton#primary { color: #17191B; background: #B9A37B; border-color: #B9A37B; }
QPushButton#primary:hover { background: #D0B991; }
QToolButton#activityButton { background: transparent; color: #A9B4C0; border: none;
                            border-left: 3px solid transparent; padding: 10px 4px; }
QToolButton#activityButton:hover { background: #242C35; color: #F2F4F6; }
QToolButton#activityButton:checked { background: #252C35; color: #E9D8BC;
                                    border-left: 3px solid #B9A37B; }
QPushButton#headerAction { background: transparent; border: 1px solid transparent; }
QPushButton#headerAction:hover { background: #29323B; border-color: #36424F; }
QTabWidget::pane { background: #171C23; border: 1px solid #343D49; }
QTabBar::tab { background: #1D242B; color: #A6B1BF; border: 1px solid #303841;
               padding: 8px 14px; min-width: 90px; }
QTabBar::tab:selected { background: #2B333D; color: #F2F2F1;
                        border-top: 2px solid #B9A37B; }
QTabBar::tab:hover:!selected { background: #262D36; }
QDockWidget { color: #D7DDE6; font-weight: 600; titlebar-close-icon: none; }
QDockWidget::title { padding: 8px 11px; background: #1D242C; border-bottom: 1px solid #343D49; }
QDockWidget::close-button, QDockWidget::float-button { background: #2B333D; }
QPlainTextEdit, QTextEdit, QTextBrowser, QLineEdit, QComboBox, QSpinBox,
QTreeWidget, QTreeView, QTableView, QTableWidget, QListWidget {
    background: #171C23; color: #E0E5EC; border: 1px solid #343D49;
    border-radius: 4px; selection-background-color: #465465;
    alternate-background-color: #1D242D;
}
QPlainTextEdit { font-family: "Cascadia Code", "Consolas", monospace;
                 font-size: 10pt; padding: 6px; }
QLineEdit { padding: 7px 9px; }
QTreeView::item, QTreeWidget::item, QListWidget::item { padding: 5px 8px; }
QTreeView::item:selected, QTreeWidget::item:selected, QListWidget::item:selected {
    background: #334150; color: #F2F4F6;
}
QHeaderView::section { background: #252D36; color: #AEBBCB; padding: 7px;
                       border: none; border-bottom: 1px solid #343D49; }
QSplitter::handle { background: #303841; }
QProgressBar { background: #27303A; border: 0; height: 8px; border-radius: 4px; }
QProgressBar::chunk { background: #83B9A3; border-radius: 4px; }
QStatusBar { background: #181D24; color: #A6B2BE;
             border-top: 1px solid #343D49; }
QScrollArea { background: #11151A; border: none; }
QFrame#notebookCell { background: #1B222A; border: 1px solid #38434F;
                      border-radius: 7px; }
QLabel#notebookCellTitle { color: #B7C2CF; font-weight: 700; }
QFrame#testInspector { background: #1B2027; border: 1px solid #343D49; }
QDialog { background: #1B2027; }
QToolTip { color: #E0E5EC; background: #29323B; border: 1px solid #526173; padding: 4px; }
QMenu { background: #252C35; border: 1px solid #45505D; padding: 4px; }
QMenu::item:selected { background: #405066; }
"""
