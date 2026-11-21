# PlusMinus Studio 2.0 — GUI and testing

- **Entry point:** `ide/studio_qt.py` — PySide6 desktop application.
- **Core VM adapter:** `ide/engine.py` — C++ runner communication and OS telemetry.
- **Analytics and persistence:** `ide/analytics.py` — lexical estimates, bytecode counts, built-in suites, SQLite.
- **C++ bridge:** `ide/runner.cpp` — compile/run protocol and VM metrics.
- **Dependencies:** `ide/requirements.txt` — PySide6-Essentials (QtCore, QtGui, QtWidgets) and psutil. Full Qt WebEngine/Addons are not needed.

Launch from the repository root with `python launch.py` or a double-click
platform launcher. The launcher builds the C++ runner, creates `.venv`, installs
required GUI packages, and opens the new interface.

`ide/app.py` remains in the repository as the earlier Tkinter implementation, but
is not the default GUI. Keeping it makes rollback and comparison possible.

The 5 canonical regression checks are in `ide/smoke_test.py`, and the new GUI
has its own built-in startup suite. Automated non-GUI tests are under `tools/`.

For standalone bundling, use `python tools/package.py` after installing PyInstaller.


### Native language source editing

Hold Ctrl and click a keyword or built-in name in the editor to open the
editable source and description in Language Internals. Use Ctrl+Shift+I
to browse all keywords, the modular C++ headers, and the runner adapter. Save with Ctrl+S;
a successful background C++ rebuild triggers the built-in regression suite.
Source editing is disabled in packaged binaries without C++ source files.
