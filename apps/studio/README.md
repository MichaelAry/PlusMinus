# PlusMinus Studio 5

Studio 5 is the Tauri 2 / Rust desktop workbench with React, TypeScript,
Monaco and Dockview. It runs the same C++ interpreter and portable native
tests as Qt Studio 4. The repository's default `Start-PlusMinus` launchers
start [Studio 4](../../ide/README.md). Stage 3 desktop acceptance targets
Windows and Linux x64. [Acceptance and rollback](../../docs/migration/STAGE3_WINDOWS_LINUX.md).

## Start from a checkout

| Platform | Launch | Preflight | Skip system tool installation |
|---|---|---|---|
| Windows x64 | Double-click [Start-PlusMinus-Studio5.cmd](../../Start-PlusMinus-Studio5.cmd) | `.\Start-PlusMinus-Studio5.cmd -Check` | `-NoInstall` |
| Linux x64 | `bash ./Start-PlusMinus-Studio5.sh` or the trusted [desktop shortcut](../../Start-PlusMinus-Studio5.desktop) | `bash ./Start-PlusMinus-Studio5.sh --check` | `--no-install` |

Preflight reports missing prerequisites without building. A normal launch
builds and stages `plusminus_runner` and `plusminus_native_tests`, prepares
npm dependencies as needed, and opens the Tauri development app. The
no-install flags skip prerequisite installation and can still run
`npm install` for the checkout. First setup may need network access.

- **Windows.** The bootstrap uses winget for missing Node.js/npm, Rustup,
  CMake, Python, MSVC Build Tools and WebView2. It selects stable Rust for
  `x86_64-pc-windows-msvc` and maps the installed VS 2022 or VS 2026 to its
  CMake generator. Use a CMake version that supports that generator.
  Rustup informational stderr is accepted when the command succeeds.
  If Build Tools requests a restart, reboot and rerun preflight. The CMake
  build is under `build/studio5-auto-windows`.
- **Linux.** The launcher supports apt, dnf and pacman and can request sudo
  for native packages, including WebKitGTK 4.1 and OpenSSL development
  libraries. It accepts Node.js 22+ and installs a SHA-256-checked Node.js 24
  archive in the user's home when needed, plus Rust with rustup. If using
  an existing Node.js 22 installation, use 22.12 or newer for Vite. Use an X11
  or Wayland session with `DISPLAY` or `WAYLAND_DISPLAY` set. The CMake build
  is under `build/studio5-auto-linux`. When loopback port 1420 is occupied,
  the launcher selects a free port and configures Vite and Tauri to use it.

## Build manually

Use Node.js 24 LTS, stable Rust with Cargo, Python 3, CMake, a C++20 toolchain
and the platform's development prerequisites. Windows uses WebView2 and
MSVC, Linux uses WebKitGTK 4.1 and native development libraries, and macOS
Intel CI uses the Apple toolchain. From the repository root:

```sh
cmake -S . -B build/studio5 -DCMAKE_BUILD_TYPE=Release
cmake --build build/studio5 --config Release --parallel 2
ctest --test-dir build/studio5 -C Release --output-on-failure
node scripts/stage-native.mjs --build-dir build/studio5
cd apps/studio
npm install
npm run tauri dev
```

Stage the sidecars again after rebuilding C++. The staging script copies the
target binaries to `src-tauri/binaries/` and writes a source fingerprint.
Direct development mode binds Vite to `127.0.0.1:1420` with a strict port
check. Vite ignores changes under `src-tauri/` in its frontend watcher.

From `apps/studio`, after staging both sidecars:

```sh
npm run test
npm run typecheck
npm run lint:types
npm run build:ui
cargo check --all-targets --manifest-path src-tauri/Cargo.toml
cargo test --manifest-path src-tauri/Cargo.toml
cargo clippy --all-targets --manifest-path src-tauri/Cargo.toml
npm run tauri build
```

The [Studio 5 workflow](../../.github/workflows/studio5.yml) builds x64
packages on Windows, Linux and Intel macOS. The Windows MSI and Linux deb
have package-layout and sidecar smoke scripts. Installed Studio 5 uses the
OS webview and bundled C++ executables.

## Use the workbench

Choose a workspace folder to browse source, C++ files, notebooks and plots.
Explorer lists nested files up to depth four and skips symlinks.
Use the activity rail or **Ctrl+Shift+P** to reach Test Lab, Source Tests,
Notebook, Profiler, Resource graphs, Compiler Explorer, Git Inspector,
Language Internals and Plot Editor. Monaco split panes can edit the same
document. Dockview stores the layout locally and clean tabs can reopen
after you reselect the same workspace. Unsaved source and notebook drafts
stay in memory.

C++ execution modes are Run, Compile, Profile and Trace. Trace replays a
bounded instruction recording after execution. The Rust Resources panel
shows backend CPU/RSS, and the Profiler uses C++ timings and opcode counts.
Notebooks use a fresh process per cell. A source checkout is required to
edit language internals, and native execution checks the build fingerprint
when the workspace is a PlusMinus checkout.

### Plot Editor

Use **Open Plot** in the main toolbar, open a `.pmplot` in the workspace
tree, or select **Ctrl+Shift+P → Open Plot Editor**. In the editor, **New**,
**Open**, **Save** and **Save As** manage one plot document. **Ctrl+S** saves
the active plot. **Detach** opens a separate window when available and can
fall back to a floating panel. **Dock** returns it to the workbench.

The editor restores the last opened or saved plot from disk. Changes in
memory prompt for **Save**, **Discard** or **Cancel** when replacing the
plot or closing the app. If the file changed externally, reopen it or
save your changes to a different path. [Shared examples and controls](../../docs/plot-examples/README.md).

## Local data and limits

- History uses `~/.plusminus/studio-v5.db`. On first history initialization,
  the legacy `studio.db` is opened read-only for SQLite Backup API migration.
  Source tests use a separate `user_tests-v5.json` copy.
- [Qt settings exporter](../../scripts/export-studio4-settings.py) reads
  portable QSettings values. Qt window geometry and Dockview layout have
  different formats.
- Source files are limited to 2 MiB and one runner request to 1 MiB of
  UTF-8 source. Rust caps native output and manages cancellation with
  Linux process groups and Windows `taskkill /T /F` on a best-effort basis.
  [IPC contract](../../docs/migration/IPC_CONTRACT.md).
