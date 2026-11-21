"""Studio 4.0 Research Workbench: activity navigation and dockable Qt shell.

The existing Studio controller continues to own C++ execution and test services.
The shell only composes their views; it does not duplicate or simulate data.
"""
from pathlib import Path
import sys
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDockWidget, QFileSystemModel, QFrame, QHBoxLayout, QLabel, QListWidget,
    QMenu, QPushButton, QTabWidget, QToolButton, QTreeView, QVBoxLayout, QWidget,
)
from command_palette import CommandPalette
from git_view import GitPanel
from notebook_view import NotebookView
from research_theme import GRAPHITE_QSS
from test_analysis_view import TestAnalysisPanel


PAGE_NAMES = (
    "Overview", "Code Editor", "Test Center", "Profiler", "Resources",
    "Benchmarks", "History & Reports", "Code Analysis", "Notebooks",
)
MODE_TARGETS = {
    "Develop": 1, "Test Lab": 2, "Notebooks": 8,
    "Language Lab": 7, "Performance": 3, "Source Control": 6,
}


class TaskCenter(QWidget):
    """Lightweight activity log: child-process work stays outside the UI thread."""
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        heading = QHBoxLayout()
        label = QLabel("BACKGROUND TASKS")
        label.setObjectName("researchEyebrow")
        heading.addWidget(label, 1)
        clear = QPushButton("Clear finished")
        clear.clicked.connect(self.clear_finished)
        heading.addWidget(clear)
        layout.addLayout(heading)
        self.items = QListWidget()
        layout.addWidget(self.items, 1)

    def append(self, message):
        self.items.addItem(str(message))
        self.items.scrollToBottom()

    def clear_finished(self):
        for row in reversed(range(self.items.count())):
            item = self.items.item(row)
            if item is not None and '· running' not in item.text():
                self.items.takeItem(row)

    def track(self, job, title):
        item = self.items.addItem(f"◌  {title} · running")
        # QListWidget.addItem() returns None; retain the inserted QListWidgetItem.
        record = self.items.item(self.items.count() - 1)
        job.finished.connect(lambda r=record, t=title: r.setText(f"✓  {t} · finished"))


class ResearchController:
    def __init__(self, host, explorer, inspector, console, controls, explorer_tree):
        self.host = host
        self.explorer = explorer
        self.inspector = inspector
        self.console = console
        self.controls = controls
        self.explorer_tree = explorer_tree
        self.active_mode = "Develop"

    def activate(self, mode):
        row = MODE_TARGETS.get(mode)
        if row is None:
            return
        self.active_mode = mode
        self.host.nav.setCurrentRow(row)
        for name, button in self.controls.items():
            button.setChecked(name == mode)
        if mode == "Source Control":
            self.host.history_sections.setCurrentIndex(2)
            self.inspector.show()
        elif mode == "Test Lab":
            self.host.test_suites.setCurrentIndex(2)
            self.inspector.hide()
        elif mode == "Notebooks":
            self.inspector.hide()
        elif mode == "Performance":
            self.inspector.hide()
        else:
            self.inspector.show()
        self.console.setVisible(mode not in ("Notebooks",))

    def sync_navigation(self, index):
        mapping = {
            0: "Develop", 1: "Develop", 2: "Test Lab",
            3: "Performance", 4: "Performance", 5: "Performance",
            6: "Source Control", 7: "Language Lab", 8: "Notebooks",
        }
        current = mapping.get(index, "Develop")
        if current != self.active_mode:
            self.active_mode = current
            for name, button in self.controls.items():
                button.setChecked(name == current)

    def open_path(self, index):
        path = Path(self.explorer_tree.model().filePath(index))
        if not path.is_file():
            return
        if path.suffix.lower() == ".ipynb":
            self.activate("Notebooks")
            self.host.notebooks.open_file(path)
        elif path.suffix.lower() in (".pm", ".cpp", ".h", ".hpp", ".py", ".txt", ".md"):
            self.host.read_file(path)

    def palette(self):
        host = self.host
        commands = [
            ("File: Open source / notebook", host.open_file),
            ("File: New PlusMinus source", host.new_file),
            ("File: Save source", host.save_file),
            ("Notebook: New document", lambda: (self.activate("Notebooks"), host.notebooks.new_file())),
            ("Notebook: Run all cells (isolated)", lambda: (self.activate("Notebooks"), host.notebooks.run_all())),
            ("Build: Rebuild C++ interpreter", host.rebuild_language),
            ("Run: Current PlusMinus source", lambda: host.launch("run")),
            ("Run: Profile current source", lambda: host.launch("run", profile=True)),
            ("Run: Record VM trace", lambda: host.launch("trace")),
            ("Tests: Run quick C++ suite", lambda: host.start_native_tests("quick")),
            ("Tests: Run all C++ methods", lambda: host.start_native_tests("full")),
            ("Tests: Compare baseline", host.compare_native_baseline),
            ("Tests: Open C++ analysis", lambda: self.activate("Test Lab")),
            ("Language: Open native C++ internals", host.open_language_internals),
            ("Workspace: Develop", lambda: self.activate("Develop")),
            ("Workspace: Test Lab", lambda: self.activate("Test Lab")),
            ("Workspace: Notebooks", lambda: self.activate("Notebooks")),
            ("Workspace: Language Lab", lambda: self.activate("Language Lab")),
            ("Workspace: Performance", lambda: self.activate("Performance")),
            ("Workspace: Source Control", lambda: self.activate("Source Control")),
            ("Panels: Toggle project explorer", lambda: self.explorer.setVisible(not self.explorer.isVisible())),
            ("Panels: Toggle inspector", lambda: self.inspector.setVisible(not self.inspector.isVisible())),
            ("Panels: Toggle output", lambda: self.console.setVisible(not self.console.isVisible())),
            ("Workspace: Restore default layout", self.reset_layout),
            ("Execution: Interrupt active tasks", host.stop),
        ]
        dialog = CommandPalette(host, commands)
        dialog.exec()

    def reset_layout(self):
        self.explorer.show()
        self.inspector.show()
        self.console.show()
        self.host.resizeDocks(
            [self.explorer, self.inspector],
            [300, 315], Qt.Orientation.Horizontal)
        self.host.resizeDocks([self.console], [205], Qt.Orientation.Vertical)
        self.activate("Develop")
        self.host.statusBar().showMessage("Default Research Workbench layout restored", 4000)

    def restore_layout(self):
        state = self.host.settings.value("research_docks_v4")
        if state:
            self.host.restoreState(state, 4)
        mode = self.host.settings.value("research_mode_v4", "")
        if mode in MODE_TARGETS:
            self.active_mode = mode
            self.host.nav.setCurrentRow(MODE_TARGETS[mode])
            for name, button in self.controls.items():
                button.setChecked(name == mode)
        # Dock visibility comes from restoreState(), not from activating presets.

    def save_layout(self):
        self.host.settings.setValue("research_docks_v4", self.host.saveState(4))
        self.host.settings.setValue("research_mode_v4", self.active_mode)


def _button(title, callback=None, primary=False):
    btn = QPushButton(title)
    if primary:
        btn.setObjectName("primary")
    else:
        btn.setObjectName("headerAction")
    if callback:
        btn.clicked.connect(callback)
    return btn


def _dock(host, name, widget, area):
    dock = QDockWidget(name, host)
    dock.setObjectName("research" + name.replace(" ", "") + "Dock")
    dock.setFeatures(
        QDockWidget.DockWidgetFeature.DockWidgetMovable |
        QDockWidget.DockWidgetFeature.DockWidgetFloatable |
        QDockWidget.DockWidgetFeature.DockWidgetClosable)
    dock.setWidget(widget)
    host.addDockWidget(area, dock)
    return dock


def build_research_shell(host, root):
    """Populate a Studio QMainWindow while preserving existing view methods."""
    host.research_mode = True
    host.setWindowTitle("PlusMinus Studio 4.0  /  Research Workbench")
    host.setStyleSheet(GRAPHITE_QSS)
    host.resize(1530, 945)
    host.setMinimumSize(875, 610)
    host.setDockNestingEnabled(True)
    host.nav = QListWidget()
    host.nav.addItems(list(PAGE_NAMES))
    host.engine_status = QLabel("●  Checking native runtime...")
    host.engine_status.setObjectName("researchEyebrow")
    host.statusBar().addPermanentWidget(host.engine_status)

    central = QWidget(host)
    frame = QVBoxLayout(central)
    frame.setSpacing(0)
    frame.setContentsMargins(0, 0, 0, 0)
    header = QFrame()
    header.setObjectName("researchHeader")
    bar = QHBoxLayout(header)
    bar.setContentsMargins(15, 7, 13, 7)
    brand = QLabel("＋／－    PLUSMINUS  /  RESEARCH")
    brand.setObjectName("researchBrand")
    bar.addWidget(brand)
    bar.addStretch(1)
    bar.addWidget(_button("Open", host.open_file))
    bar.addWidget(_button("Save", host.save_file))
    bar.addWidget(_button("Run  F5", lambda: host.launch("run"), True))
    bar.addWidget(_button("Trace  F7", lambda: host.launch("trace")))
    bar.addWidget(_button("Native tests", lambda: host.start_native_tests("quick")))
    bar.addWidget(_button("Stop", host.stop))
    palette_btn = _button("⌕  Commands")
    bar.addWidget(palette_btn)
    frame.addWidget(header)

    # Build original operational panels once; only their layout is replaced.
    from workspace import WorkspaceTabs
    host.workspace = WorkspaceTabs()
    host.stack = host.workspace
    pages = (
        host.make_overview, host.make_editor, host.make_tests, host.make_profiler,
        host.make_resources, host.make_benchmarks, host.make_history,
        host.make_analysis,
    )
    for title, factory in zip(PAGE_NAMES, pages):
        host.workspace.register_page(title, factory())
    notebook_root = (Path.home() / "Documents") if getattr(sys, "frozen", False) else root
    if not notebook_root.is_dir():
        notebook_root = Path.home()
    host.notebooks = NotebookView(notebook_root, host)
    host.notebooks.statusChanged.connect(host.statusBar().showMessage)
    host.workspace.register_page("Notebooks", host.notebooks)
    frame.addWidget(host.workspace, 1)
    host.setCentralWidget(central)

    # Test-specific source inspector uses the same actual C++ test history.
    host.test_analysis = TestAnalysisPanel(root, host.native_history)
    host.test_suites.addTab(host.test_analysis, "C++ Test Analysis")
    host.test_analysis.openSourceRequested.connect(host.open_native_source)
    host.test_analysis.testRequested.connect(host.run_native_identifier)
    host.test_analysis.compareRequested.connect(host.compare_native_baseline)

    navigation = QWidget()
    navigation_layout = QHBoxLayout(navigation)
    navigation_layout.setContentsMargins(0, 0, 0, 0)
    navigation_layout.setSpacing(0)
    rail = QFrame()
    rail.setObjectName("activityRail")
    rail.setFixedWidth(64)
    rail_layout = QVBoxLayout(rail)
    rail_layout.setContentsMargins(1, 8, 1, 8)
    rail_layout.setSpacing(6)
    controls = {}
    for mode, glyph in [
        ("Develop", "D"), ("Test Lab", "T"), ("Notebooks", "N"),
        ("Language Lab", "L"), ("Performance", "P"), ("Source Control", "G"),
    ]:
        tool = QToolButton()
        tool.setObjectName("activityButton")
        tool.setText(glyph)
        tool.setToolTip(mode)
        tool.setCheckable(True)
        tool.setMinimumHeight(49)
        tool.setAccessibleName(mode)
        rail_layout.addWidget(tool)
        controls[mode] = tool
    rail_layout.addStretch(1)
    navigation_layout.addWidget(rail)

    sidebar = QTabWidget()
    explorer_model = QFileSystemModel(sidebar)
    explorer_model.setRootPath(str(root))
    explorer_tree = QTreeView()
    explorer_tree.setModel(explorer_model)
    explorer_tree.setRootIndex(explorer_model.index(str(root)))
    explorer_tree.setHeaderHidden(True)
    for col in (1, 2, 3):
        explorer_tree.hideColumn(col)
    sidebar.addTab(explorer_tree, "Project")
    sidebar.addTab(host.nav, "Sections")
    navigation_layout.addWidget(sidebar, 1)
    explorer_dock = _dock(host, "Explorer", navigation, Qt.DockWidgetArea.LeftDockWidgetArea)

    inspector_tabs = QTabWidget()
    inspector_tabs.addTab(host.research_inspector_widget, "Code Insights")
    inspector_tabs.addTab(GitPanel(root), "Git")
    inspector_dock = _dock(host, "Inspector", inspector_tabs,
                           Qt.DockWidgetArea.RightDockWidgetArea)

    host.task_center = TaskCenter()
    host.result_tabs.addTab(host.task_center, "Tasks")
    console_dock = _dock(host, "Output and Diagnostics", host.result_tabs,
                         Qt.DockWidgetArea.BottomDockWidgetArea)

    controller = ResearchController(host, explorer_dock, inspector_dock,
                                     console_dock, controls, explorer_tree)
    host.research_controller = controller
    explorer_tree.doubleClicked.connect(controller.open_path)
    for mode, tool in controls.items():
        tool.clicked.connect(lambda checked=False, selected=mode: controller.activate(selected))
    host.nav.currentRowChanged.connect(host.workspace.open_page)
    host.nav.currentRowChanged.connect(controller.sync_navigation)
    host.workspace.pageActivated.connect(host.nav.setCurrentRow)
    palette_btn.clicked.connect(controller.palette)
    for keys, callback in [
        ("F5", lambda: host.launch("run")),
        ("F6", lambda: host.launch("run", profile=True)),
        ("F7", lambda: host.launch("trace")),
        ("Ctrl+S", host.save_file),
        ("Ctrl+O", host.open_file),
        ("Ctrl+N", host.new_file),
        ("Ctrl+F", host.find_in_file),
        ("Ctrl+G", host.go_to_line),
        ("Ctrl+Shift+I", host.open_language_internals),
        ("Ctrl+Shift+P", controller.palette),
        ("Ctrl+Shift+N", lambda: controller.activate("Notebooks")),
    ]:
        action = QAction(host)
        action.setShortcut(keys)
        action.triggered.connect(callback)
        host.addAction(action)
    host.nav.setCurrentRow(0)
    controls["Develop"].setChecked(True)
    host.resizeDocks([explorer_dock, inspector_dock],
                     [300, 315], Qt.Orientation.Horizontal)
    host.resizeDocks([console_dock], [205], Qt.Orientation.Vertical)
    return controller
