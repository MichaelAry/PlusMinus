# Regression: Windows PowerShell 5.1 must not throw NativeCommandError when
# rustup prints informational stderr during rustc toolchain inspection.
# No network, install or real rustup update is performed.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$dir = Join-Path $env:RUNNER_TEMP ('studio5-rustup-stderr-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $dir | Out-Null

try {
  $stub = Join-Path $dir 'rustup.exe'
  $source = @'
using System;
public static class Stub {
    public static int Main(string[] args) {
        Console.Error.WriteLine("info: syncing channel updates for stable-x86_64-pc-windows-msvc");
        if (args.Length == 2 && args[0] == "toolchain" && args[1] == "list") {
            Console.WriteLine("stable-x86_64-pc-windows-msvc (default)");
            return 0;
        }
        if (args.Length >= 4 && args[0] == "run" && args[1] == "stable-x86_64-pc-windows-msvc") {
            if (Environment.GetEnvironmentVariable("STUDIO5_TEST_RUSTUP_FAIL") == "1") {
                Console.Error.WriteLine("error: toolchain invocation failed");
                return 42;
            }
            Console.WriteLine("rustc 1.100.0 (mock)");
            Console.WriteLine("host: x86_64-pc-windows-msvc");
            return 0;
        }
        Console.Error.WriteLine("error: unexpected invocation " + String.Join(" ", args));
        return 42;
    }
}
'@
  Add-Type -TypeDefinition $source -OutputAssembly $stub -OutputType ConsoleApplication
  Copy-Item -LiteralPath $stub -Destination (Join-Path $dir 'rustc.exe')
  Copy-Item -LiteralPath $stub -Destination (Join-Path $dir 'cargo.exe')
  $env:Path = "$dir;$env:Path"
  $env:STUDIO5_TEST_RUSTUP_FAIL = '0'
  $lines = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'scripts\bootstrap-studio5.ps1') -Check 2>&1
  $code = $LASTEXITCODE
  $output = ($lines | Out-String)
  Write-Host $output
  if ($code -notin @(0,2)) { throw "Informational stderr triggered a fatal exception (exit $code)." }
  if ($output -notmatch 'Rust MSVC toolchain: OK') {
    throw 'Rustup informational stderr incorrectly caused a missing toolchain.'
  }
  if ($output -match '\[Studio 5\] ERROR:') { throw 'Bootstrap emitted a fatal error for informational stderr.' }

  $env:STUDIO5_TEST_RUSTUP_FAIL = '1'
  $lines = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'scripts\bootstrap-studio5.ps1') -Check 2>&1
  $code = $LASTEXITCODE
  $output = ($lines | Out-String)
  Write-Host $output
  if ($code -ne 2 -or $output -notmatch 'Rust MSVC toolchain: MISSING') {
    throw "A failed rustup invocation was not detected (exit $code)."
  }
  if (git status --porcelain) { throw 'Check-only run modified tracked files.' }
} finally {
  Remove-Item Env:\STUDIO5_TEST_RUSTUP_FAIL -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath $dir -Recurse -Force -ErrorAction SilentlyContinue
}
