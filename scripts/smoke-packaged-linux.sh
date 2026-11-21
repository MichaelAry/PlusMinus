#!/usr/bin/env bash
# Installed-layout smoke: unpack the actual Tauri .deb without system install.
set -euo pipefail
repo="$(cd "$(dirname "$0")/.." && pwd)"
bundle="$repo/apps/studio/src-tauri/target/release/bundle/deb"
deb="$(find "$bundle" -maxdepth 1 -name '*.deb' -type f -print -quit)"
test -n "$deb" || { echo "No packaged .deb to inspect" >&2; exit 1; }
temp="$(mktemp -d)"
trap 'rm -rf "$temp"' EXIT
dpkg-deb -x "$deb" "$temp"
runner="$(find "$temp" -type f \( -name plusminus_runner -o -name 'plusminus_runner-*' \) -print -quit)"
tests="$(find "$temp" -type f \( -name plusminus_native_tests -o -name 'plusminus_native_tests-*' \) -print -quit)"
test -n "$runner" && test -x "$runner" || { echo "Runner sidecar missing from .deb" >&2; exit 1; }
test -n "$tests" && test -x "$tests" || { echo "Test sidecar missing from .deb" >&2; exit 1; }
printf 'print(0);\n' | "$runner" run >"$temp/runner.json"
"$tests" --list >"$temp/manifest.jsonl"
python3 - "$temp/runner.json" "$temp/manifest.jsonl" <<'PY'
import json, pathlib, sys
report=json.loads(pathlib.Path(sys.argv[1]).read_text())
assert report["ok"] and report["result"]=="0" and "0" in report["output"],report
manifest=[json.loads(x) for x in pathlib.Path(sys.argv[2]).read_text().splitlines() if x.strip()]
assert len(manifest)==225 and len({case["id"] for case in manifest})==225
print("PASS: packaged sidecars execute unchanged VM and expose 225 tests")
first=next(x["id"] for x in manifest if not x.get("slow"))
pathlib.Path(sys.argv[1]).with_name("first-test-id.txt").write_text(first)
PY
first="$(cat "$temp/first-test-id.txt")"
"$tests" --run "$first" >"$temp/first-test.jsonl"
python3 - "$temp/first-test.jsonl" "$first" <<'PY'
import json, pathlib, sys
events=[json.loads(x) for x in pathlib.Path(sys.argv[1]).read_text().splitlines() if x.strip()]
assert len(events)==1 and events[0]["type"]=="result",events
assert events[0]["id"]==sys.argv[2] and events[0]["status"]=="PASS",events
print("PASS: packaged plusminus_native_tests --run",sys.argv[2])
PY
# Window/process cold-start smoke, not a complete GUI parity test.
app="$temp/usr/bin/plusminus-studio"
test -x "$app" || { echo "Packaged app executable missing at $app" >&2; exit 1; }
set +e
GDK_BACKEND=x11 WEBKIT_DISABLE_COMPOSITING_MODE=1 \
  timeout -k 3s 8s xvfb-run -a "$app" >"$temp/gui.log" 2>&1
code=$?
set -e
if test "$code" -ne 124; then
  cat "$temp/gui.log" >&2
  echo "Packaged Linux GUI quit unexpectedly (exit $code)" >&2
  exit 1
fi
echo "PASS: packaged Linux GUI remained running under Xvfb for 8 seconds"
