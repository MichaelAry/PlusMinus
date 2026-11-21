# Automatic Studio 5 source-build launcher for Windows x64.
# Requires a trusted local checkout and winget for missing system tools.
# Does NOT modify the original Qt launcher, Studio 4 settings, or user data.
param(
  [switch]$Check,
  [switch]$NoInstall,
  [switch]$Help
)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Log([string]$message) { Write-Host "[Studio 5] $message" }
function Die([string]$message) { throw "[Studio 5] $message" }
function Has([string]$tool) { return [bool](Get-Command $tool -ErrorAction SilentlyContinue) }

# PowerShell 5.1 converts native stderr to ErrorRecords when output is captured
# and ErrorActionPreference=Stop. rustup may print informational diagnostics
# ("info: syncing channel updates ...") even when exit code is 0.
# Probe external tools via Process and decide from the EXIT CODE, not stderr.
# Probes never request rustup toolchain updates and have a bounded timeout.
function Probe([string]$tool, [string]$arguments) {
  $resolved = Get-Command $tool -ErrorAction SilentlyContinue
  if (-not $resolved) {
    return [pscustomobject]@{ ExitCode = 127; Output = ''; ErrorText = "$tool not found" }
  }
  $start = New-Object System.Diagnostics.ProcessStartInfo
  $start.FileName = $resolved.Source
  $start.Arguments = $arguments
  $start.UseShellExecute = $false
  $start.RedirectStandardOutput = $true
  $start.RedirectStandardError = $true
  $start.CreateNoWindow = $true
  $process = New-Object System.Diagnostics.Process
  $process.StartInfo = $start
  try {
    if (-not $process.Start()) {
      return [pscustomobject]@{ ExitCode = 127; Output = ''; ErrorText = "$tool could not start" }
    }
    $stdout = $process.StandardOutput.ReadToEndAsync()
    $stderr = $process.StandardError.ReadToEndAsync()
    if (-not $process.WaitForExit(10000)) {
      $process.Kill()
      $process.WaitForExit()
      return [pscustomobject]@{ ExitCode = 124; Output = ''; ErrorText = "$tool probe timed out" }
    }
    return [pscustomobject]@{
      ExitCode = $process.ExitCode
      Output = $stdout.Result
      ErrorText = $stderr.Result
    }
  } catch {
    return [pscustomobject]@{ ExitCode = 127; Output = ''; ErrorText = $_.Exception.Message }
  } finally {
    $process.Dispose()
  }
}

function Refresh-Path {
  $machine = [Environment]::GetEnvironmentVariable('Path', 'Machine')
  $user = [Environment]::GetEnvironmentVariable('Path', 'User')
  $cargo = Join-Path $HOME '.cargo\bin'
  # Keep caller PATH first (for portable tools and CI stub binaries), then
  # add any newly installed user/machine paths. Do not lose the VS dev shell.
  $seen = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
  $env:Path = ((@($env:Path, $cargo, $user, $machine) -join ';') -split ';' |
    Where-Object { $_ -and $seen.Add($_) }) -join ';'
}

function Native([string]$tool, [string[]]$arguments) {
  Log ("Running: " + $tool + " " + ($arguments -join ' '))
  # Do not convert harmless native stderr (npm/cargo/rustup emit progress here)
  # into terminating PowerShell errors. The actual exit code remains fatal.
  $previousPreference = $ErrorActionPreference
  $exitCode = 1
  try {
    $ErrorActionPreference = 'Continue'
    & $tool @arguments
    $exitCode = $LASTEXITCODE
  } finally {
    $ErrorActionPreference = $previousPreference
  }
  if ($exitCode -ne 0) {
    Die "$tool failed with exit code $exitCode"
  }
}

function Install-Winget([string]$id, [string[]]$extra = @()) {
  if (-not (Has 'winget.exe')) {
    Die 'winget is unavailable. Install App Installer from Microsoft, then relaunch.'
  }
  Log "Installing missing dependency $id (Windows may request administrator approval)."
  $wingetArguments = @('install', '--id', $id, '--exact', '--source', 'winget',
    '--accept-source-agreements', '--accept-package-agreements') + $extra
  Native 'winget.exe' $wingetArguments
  Refresh-Path
}

function Test-Node {
  if (-not (Has 'node.exe') -or -not (Has 'npm.cmd')) { return $false }
  $probe = Probe 'node.exe' '--version'
  if ($probe.ExitCode -ne 0) { return $false }
  if ($probe.Output.Trim() -match '^v([0-9]+)\.') { return ([int]$Matches[1] -ge 22) }
  return $false
}

function Get-Python {
  if (Has 'py.exe') {
    $probe = Probe 'py.exe' '-3 -c "import sys; print(sys.executable)"'
    if ($probe.ExitCode -eq 0 -and $probe.Output.Trim()) {
      return ($probe.Output.Trim() -split "[`r`n]+")[0]
    }
  }
  if (Has 'python.exe') {
    $probe = Probe 'python.exe' '-c "import sys; print(sys.executable)"'
    if ($probe.ExitCode -eq 0 -and $probe.Output.Trim()) {
      return ($probe.Output.Trim() -split "[`r`n]+")[0]
    }
  }
  return $null
}

function Get-Msvc {
  $programFilesX86 = [Environment]::GetFolderPath('ProgramFilesX86')
  $vswhere = Join-Path $programFilesX86 'Microsoft Visual Studio\Installer\vswhere.exe'
  if (-not (Test-Path -LiteralPath $vswhere)) { return $null }
  $whereArgs = '-latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64'
  $path = Probe $vswhere ($whereArgs + ' -property installationPath')
  if ($path.ExitCode -ne 0 -or -not $path.Output.Trim()) { return $null }
  $version = Probe $vswhere ($whereArgs + ' -property installationVersion')
  if ($version.ExitCode -ne 0 -or -not $version.Output.Trim()) { return $null }
  return [pscustomobject]@{
    Path = $path.Output.Trim()
    Version = $version.Output.Trim()
  }
}

function Test-Rust {
  if (-not (Has 'rustc.exe') -or -not (Has 'cargo.exe')) { return $false }
  if (Has 'rustup.exe') {
    # "rustc -vV" through the rustup shim may synchronize channels. List
    # locally installed toolchains first; do not download anything in -Check.
    $list = Probe 'rustup.exe' 'toolchain list'
    if ($list.ExitCode -ne 0 -or
        $list.Output -notmatch '(?m)^stable-x86_64-pc-windows-msvc(?:\s|$)') {
      return $false
    }
    $info = Probe 'rustup.exe' 'run stable-x86_64-pc-windows-msvc rustc -vV'
  } else {
    $info = Probe 'rustc.exe' '-vV'
  }
  return ($info.ExitCode -eq 0 -and
    $info.Output.Contains('host: x86_64-pc-windows-msvc'))
}

function Test-WebView2 {
  $guid = '{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}'
  $registry = @(
    'HKLM:\SOFTWARE\Microsoft\EdgeUpdate\Clients',
    'HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients',
    'HKCU:\SOFTWARE\Microsoft\EdgeUpdate\Clients'
  )
  foreach ($base in $registry) {
    $key = Join-Path $base $guid
    if (Test-Path $key) {
      $info = Get-ItemProperty -LiteralPath $key -ErrorAction SilentlyContinue
      if ($info -and $info.PSObject.Properties.Match('pv').Count -gt 0) {
        $version = $info.pv
        if ($version -and $version -ne '0.0.0.0') { return $true }
      }
    }
  }
  $programFilesX86 = [Environment]::GetFolderPath('ProgramFilesX86')
  return (Test-Path (Join-Path $programFilesX86 'Microsoft\EdgeWebView\Application'))
}

function Missing {
  $issues = @()
  if (-not (Test-Node)) { $issues += 'Node.js 22+ and npm' }
  if (-not (Has 'cmake.exe')) { $issues += 'CMake' }
  if (-not (Get-Python)) { $issues += 'Python 3 for the existing C++ native-test generator' }
  if (-not (Get-Msvc)) { $issues += 'MSVC x64 / Visual Studio Build Tools' }
  if (-not (Test-WebView2)) { $issues += 'Edge WebView2 Runtime' }
  if (-not (Test-Rust)) { $issues += 'Rust stable x86_64-pc-windows-msvc / Cargo' }
  return $issues
}

if ($Help) {
  Write-Host 'Usage: Start-PlusMinus-Studio5.cmd [-Check] [-NoInstall]'
  Write-Host '  Default: install missing tools with winget, build sidecars and run Tauri Studio 5.'
  Write-Host '  -Check: check prerequisites without changes.'
  Write-Host '  -NoInstall: fail instead of installing missing tools.'
  exit 0
}

try {
  if (-not [Environment]::Is64BitProcess) {
    Die 'Use 64-bit PowerShell on Windows x64.'
  }
  $root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
  $app = Join-Path $root 'apps\studio'
  if (-not (Test-Path (Join-Path $app 'package.json')) -or
      -not (Test-Path (Join-Path $root 'scripts\stage-native.mjs'))) {
    Die 'This launcher needs a complete PlusMinus source checkout.'
  }

  Refresh-Path
  $env:RUSTUP_TOOLCHAIN = 'stable-x86_64-pc-windows-msvc'
  $missing = @(Missing)
  if ($missing.Count) {
    Log ('Missing: ' + ($missing -join ', '))
  } else {
    Log 'Required build/runtime tools are present.'
  }
  if ($Check) {
    if (Test-Rust) { Log 'Rust MSVC toolchain: OK' }
    else { Log 'Rust MSVC toolchain: MISSING' }
    if ($missing.Count) { exit 2 }
    exit 0
  }
  if ($NoInstall -and $missing.Count) {
    Die 'Run again without -NoInstall to install the listed dependencies.'
  }

  if (-not (Test-Node)) { Install-Winget 'OpenJS.NodeJS.LTS' }
  if (-not (Has 'cmake.exe')) { Install-Winget 'Kitware.CMake' }
  if (-not (Get-Python)) { Install-Winget 'Python.Python.3.12' }
  if (-not (Get-Msvc)) {
    Install-Winget 'Microsoft.VisualStudio.2022.BuildTools' @(
      '--override', '--add Microsoft.VisualStudio.Workload.VCTools --includeRecommended --passive --wait --norestart'
    )
  }
  if (-not (Test-WebView2)) { Install-Winget 'Microsoft.EdgeWebView2Runtime' }
  if (-not (Has 'rustup.exe') -and -not (Test-Rust)) {
    Install-Winget 'Rustlang.Rustup'
  }

  Refresh-Path
  if (Has 'rustup.exe') {
    $list = Probe 'rustup.exe' 'toolchain list'
    if ($list.ExitCode -ne 0) {
      Die ('Unable to list Rust toolchains: ' + $list.ErrorText)
    }
    if ($list.Output -notmatch '(?m)^stable-x86_64-pc-windows-msvc(?:\s|$)') {
      Native 'rustup.exe' @('toolchain','install','stable-x86_64-pc-windows-msvc','--profile','minimal')
    }
  }

  $missing = @(Missing)
  if ($missing.Count) {
    Die ('Prerequisites are still missing: ' + ($missing -join ', ') +
      '. Restart Windows if Build Tools requested a reboot, then run this launcher again.')
  }

  $msvc = Get-Msvc
  $vsMajor = [int](($msvc.Version -split '\.')[0])
  if ($vsMajor -eq 17) { $generator = 'Visual Studio 17 2022' }
  elseif ($vsMajor -eq 18) { $generator = 'Visual Studio 18 2026' }
  else { Die "Unsupported installed Visual Studio version: $($msvc.Version)" }

  $python = Get-Python
  $build = Join-Path $root 'build\studio5-auto-windows'
  Log 'Building the original C++20 interpreter and native test sidecars.'
  Native 'cmake.exe' @('-S',$root,'-B',$build,'-G',$generator,'-A','x64',
    "-DPython3_EXECUTABLE=$python")
  Native 'cmake.exe' @('--build',$build,'--config','Release','--parallel','2')

  $release = Join-Path $build 'Release'
  if (-not (Test-Path (Join-Path $release 'plusminus_runner.exe')) -or
      -not (Test-Path (Join-Path $release 'plusminus_native_tests.exe'))) {
    Die 'CMake did not build both native executables. Confirm Python3 was detected.'
  }
  Native 'node.exe' @((Join-Path $root 'scripts\stage-native.mjs'),
    '--build-dir',$build,'--target','x86_64-pc-windows-msvc')

  $stamp = Join-Path $app 'node_modules\.plusminus-studio5-deps'
  $nodeModules = Join-Path $app 'node_modules'
  $tauriCmd = Join-Path $nodeModules '.bin\tauri.cmd'
  $sha256 = [System.Security.Cryptography.SHA256]::Create()
  try {
    $manifest = [System.IO.File]::ReadAllBytes((Join-Path $app 'package.json'))
    $hash = [BitConverter]::ToString($sha256.ComputeHash($manifest)).Replace('-', '')
  } finally { $sha256.Dispose() }
  $oldHash = if (Test-Path $stamp) { (Get-Content $stamp -Raw).Trim() } else { '' }
  if (-not (Test-Path $nodeModules) -or -not (Test-Path $tauriCmd) -or $oldHash -ne $hash) {
    Log 'Installing frontend dependencies with npm.'
    Push-Location $app
    try { Native 'npm.cmd' @('install','--no-audit','--no-fund') }
    finally { Pop-Location }
    Set-Content -LiteralPath $stamp -Value $hash -Encoding Ascii
  }

  Log 'Launching full Studio 5: Tauri + Rust + original C++ runner.'
  Push-Location $app
  try { Native 'npm.cmd' @('run','tauri','dev') }
  finally { Pop-Location }
  exit 0
} catch {
  Write-Host ("[Studio 5] ERROR: " + $_.Exception.Message) -ForegroundColor Red
  exit 1
}
