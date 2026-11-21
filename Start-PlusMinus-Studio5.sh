#!/usr/bin/env bash
# Self-bootstrapping Windows/Linux Stage 5 candidate: Linux x64 entrypoint.
# Does not overwrite the Qt launcher, user files, or the C++ interpreter.
set -Eeuo pipefail
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)"
APP="$ROOT/apps/studio"
BUILD="$ROOT/build/studio5-auto-linux"
NODE_HOME="$HOME/.local/share/plusminus/studio5-tools/node24"
STAMP="$APP/node_modules/.plusminus-studio5-deps"
INSTALL=1
CHECK=0
log() { printf '[Studio 5] %s\n' "$*"; }
die() { printf '[Studio 5] ERROR: %s\n' "$*" >&2; exit 1; }
trap 'code=$?; echo "[Studio 5] Failed (exit $code); review the error above." >&2' ERR

for option in "$@"; do
  case "$option" in
    --no-install) INSTALL=0 ;;
    --check) CHECK=1; INSTALL=0 ;;
    --help|-h)
      printf '%s\n' 'Usage: bash Start-PlusMinus-Studio5.sh [--check] [--no-install]' \
        '  No flags: install missing dependencies, build sidecars, run Tauri Studio 5.' \
        '  --check: check prerequisites without modifying the computer.' \
        '  --no-install: stop if any dependency is missing.'
      exit 0 ;;
    *) die "Unknown option: $option" ;;
  esac
done

[[ "$(uname -s)" == Linux && "$(uname -m)" == x86_64 ]] ||
  die 'This launcher supports Linux x86_64 only.'
[[ -f "$APP/package.json" && -f "$ROOT/scripts/stage-native.mjs" ]] ||
  die 'A complete PlusMinus checkout is required.'

export PATH="$NODE_HOME/bin:$HOME/.cargo/bin:$PATH"
node_ready() {
  command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1 || return 1
  local major
  major="$(node -p 'Number(process.versions.node.split(".")[0])' 2>/dev/null)" || return 1
  [[ "$major" =~ ^[0-9]+$ && "$major" -ge 22 ]]
}
rust_ready() {
  command -v rustc >/dev/null 2>&1 &&
  command -v cargo >/dev/null 2>&1 &&
  rustc -vV | grep -q '^host: x86_64-unknown-linux-gnu$'
}
system_ready() {
  command -v cmake >/dev/null 2>&1 &&
  command -v c++ >/dev/null 2>&1 &&
  command -v python3 >/dev/null 2>&1 &&
  command -v curl >/dev/null 2>&1 &&
  command -v tar >/dev/null 2>&1 &&
  command -v sha256sum >/dev/null 2>&1 &&
  command -v pkg-config >/dev/null 2>&1 &&
  pkg-config --exists webkit2gtk-4.1 &&
  pkg-config --exists openssl
}
elevate() {
  if [[ "$(id -u)" -eq 0 ]]; then "$@"
  else
    command -v sudo >/dev/null 2>&1 || die 'sudo is required to install system packages.'
    sudo "$@"
  fi
}
install_system() {
  log 'Installing Linux C++/CMake/Python/WebKitGTK 4.1 prerequisites.'
  if command -v apt-get >/dev/null 2>&1; then
    elevate apt-get update
    elevate env DEBIAN_FRONTEND=noninteractive apt-get install -y \
      cmake g++ make python3 pkg-config libwebkit2gtk-4.1-dev \
      curl wget file xz-utils libxdo-dev libssl-dev libayatana-appindicator3-dev librsvg2-dev
  elif command -v dnf >/dev/null 2>&1; then
    elevate dnf install -y cmake gcc-c++ make python3 pkgconf-pkg-config \
      webkit2gtk4.1-devel openssl-devel curl wget file xz \
      libappindicator-gtk3-devel librsvg2-devel libxdo-devel
  elif command -v pacman >/dev/null 2>&1; then
    elevate pacman -S --needed --noconfirm cmake base-devel python pkgconf \
      webkit2gtk-4.1 curl wget file xz openssl appmenu-gtk-module \
      libappindicator-gtk3 librsvg xdotool
  else
    die 'Unsupported package manager. Supported: apt, dnf, pacman.'
  fi
  system_ready || die 'WebKitGTK 4.1, OpenSSL, or another native build dependency is still unavailable.'
}
install_node() {
  # The official Node.js 24 LTS binary is checked against its SHA256 manifest.
  local tmp filename hash
  tmp="$(mktemp -d)"
  log 'Installing Node.js 24 LTS into the user home (verified SHA256).'
  curl --fail --location --retry 3 --silent --show-error \
    https://nodejs.org/dist/latest-v24.x/SHASUMS256.txt -o "$tmp/SHASUMS256.txt"
  filename="$(awk '$2 ~ /^node-v[0-9]+\.[0-9]+\.[0-9]+-linux-x64\.tar\.xz$/ {print $2; exit}' "$tmp/SHASUMS256.txt")"
  [[ -n "$filename" ]] || die 'Could not select an official Node.js Linux x64 archive.'
  hash="$(awk -v n="$filename" '$2==n {print $1; exit}' "$tmp/SHASUMS256.txt")"
  curl --fail --location --retry 3 --silent --show-error \
    "https://nodejs.org/dist/latest-v24.x/$filename" -o "$tmp/$filename"
  (cd "$tmp"; printf '%s  %s\n' "$hash" "$filename" | sha256sum --check --status) ||
    die 'The Node.js download failed SHA256 verification.'
  mkdir -p "$NODE_HOME"
  tar -xJf "$tmp/$filename" --strip-components=1 -C "$NODE_HOME"
  rm -rf -- "$tmp"
  export PATH="$NODE_HOME/bin:$PATH"
  node_ready || die 'Node.js installation was unsuccessful.'
}
install_rust() {
  local tmp
  tmp="$(mktemp -d)"
  log 'Installing official Rust stable toolchain for this user.'
  curl --fail --location --retry 3 --silent --show-error \
    --proto '=https' --tlsv1.2 https://sh.rustup.rs -o "$tmp/install-rustup.sh"
  sh "$tmp/install-rustup.sh" -y --profile minimal --default-toolchain stable
  rm -rf -- "$tmp"
  export PATH="$HOME/.cargo/bin:$PATH"
  rust_ready || die 'Rust compiler/Cargo were not installed correctly.'
}

if [[ "$CHECK" -eq 1 ]]; then
  status=0
  if system_ready; then log 'System prerequisites: OK'; else log 'System prerequisites: MISSING'; status=2; fi
  if node_ready; then log "Node: $(node --version)"; else log 'Node.js 22+: MISSING'; status=2; fi
  if rust_ready; then log "Rust: $(rustc --version)"; else log 'Rust/Cargo x64 GNU: MISSING'; status=2; fi
  exit "$status"
fi

if ! system_ready; then
  [[ "$INSTALL" -eq 1 ]] || die 'Linux build dependencies missing; rerun without --no-install.'
  install_system
fi
if ! node_ready; then
  [[ "$INSTALL" -eq 1 ]] || die 'Node.js 22+ missing; rerun without --no-install.'
  install_node
fi
if ! rust_ready; then
  [[ "$INSTALL" -eq 1 ]] || die 'Rust/Cargo missing; rerun without --no-install.'
  install_rust
fi

[[ -n "$(printenv DISPLAY 2>/dev/null || true)" || -n "$(printenv WAYLAND_DISPLAY 2>/dev/null || true)" ]] ||
  die 'A graphical X11/Wayland desktop session is required.'

log 'Configuring and building the unchanged native C++20 sidecars.'
cmake -S "$ROOT" -B "$BUILD" -DCMAKE_BUILD_TYPE=Release
cmake --build "$BUILD" --config Release --parallel 2
[[ -x "$BUILD/plusminus_runner" && -x "$BUILD/plusminus_native_tests" ]] ||
  die 'The build did not produce both C++ sidecars. Check Python3 during CMake configure.'

node "$ROOT/scripts/stage-native.mjs" --build-dir "$BUILD" --target x86_64-unknown-linux-gnu
package_hash="$(sha256sum "$APP/package.json" | awk '{print $1}')"
if [[ ! -d "$APP/node_modules" || ! -f "$STAMP" || "$(cat "$STAMP")" != "$package_hash" ]]; then
  log 'Installing frontend packages with npm.'
  ( cd "$APP"; npm install --no-audit --no-fund )
  printf '%s\n' "$package_hash" > "$STAMP"
fi
log 'Launching the complete Tauri + Rust + C++ Studio 5.'
cd "$APP"
npm run tauri dev
