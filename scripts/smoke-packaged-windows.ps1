# Validate sidecars from the actual Windows MSI installed payload, not staging.
# Run on GitHub-hosted Windows x64 after 'npm run tauri build'.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$bundle = Join-Path $root "apps/studio/src-tauri/target/release/bundle/msi"
$msi = Get-ChildItem -LiteralPath $bundle -Filter *.msi -File | Select-Object -First 1
if (-not $msi) { throw "Windows MSI package missing: $bundle" }
$dest = Join-Path $env:RUNNER_TEMP "plusminus-studio5-msi-smoke"
New-Item -ItemType Directory -Force -Path $dest | Out-Null
$log = Join-Path $env:RUNNER_TEMP "studio5-msi-extraction.log"
$arguments = @('/a', '"' + $msi.FullName + '"', 'TARGETDIR="' + $dest + '"', '/qn', '/L*v', '"' + $log + '"') -join ' '
$msiexec = Start-Process -FilePath "msiexec.exe" -ArgumentList $arguments -Wait -PassThru
if ($msiexec.ExitCode -ne 0) {
  if (Test-Path $log) { Get-Content $log -Tail 60 | Write-Host }
  throw "MSI administrative extraction failed: $($msiexec.ExitCode)"
}
$runner = Get-ChildItem -Path $dest -Filter "plusminus_runner*.exe" -File -Recurse | Select-Object -First 1
$tests = Get-ChildItem -Path $dest -Filter "plusminus_native_tests*.exe" -File -Recurse | Select-Object -First 1
if (-not $runner -or -not $tests) { throw "Missing packaged plusminus_runner/plusminus_native_tests" }
function Assert-X64($path) {
  $data = [System.IO.File]::ReadAllBytes($path)
  if ($data.Length -lt 128) { throw "Too small for PE binary: $path" }
  $header = [BitConverter]::ToInt32($data, 0x3c)
  $machine = [BitConverter]::ToUInt16($data, $header + 4)
  if ($machine -ne 0x8664) { throw "Not Windows x64 (AMD64) PE: $path machine=$machine" }
}
Assert-X64 $runner.FullName
Assert-X64 $tests.FullName
$reportText = ("print(0);" + [char]10) | & $runner.FullName run
if ($LASTEXITCODE -ne 0) { throw "Packaged runner run failed: exit $LASTEXITCODE" }
$report = ($reportText -join [char]10) | ConvertFrom-Json
if (-not $report.ok -or $report.result -ne "0" -or $report.output -notmatch "0") {
  throw "Packaged runner returned unexpected JSON"
}
$manifestText = & $tests.FullName --list
if ($LASTEXITCODE -ne 0) { throw "Packaged native test discovery failed" }
$manifest = @($manifestText | Where-Object { $_.Trim() } | ForEach-Object { $_ | ConvertFrom-Json })
$ids = @($manifest | ForEach-Object { $_.id } | Select-Object -Unique)
if ($manifest.Count -ne 225 -or $ids.Count -ne 225) {
  throw "Expected 225 packaged native tests, got $($manifest.Count) rows / $($ids.Count) distinct IDs"
}
$first = $manifest | Where-Object { -not $_.slow } | Select-Object -First 1
if (-not $first) { throw "No fast native test available" }
$runText = & $tests.FullName --run $first.id
if ($LASTEXITCODE -ne 0) { throw "Packaged native test execution failed: exit $LASTEXITCODE" }
$testResult = @($runText | Where-Object { $_.Trim() } | ForEach-Object { $_ | ConvertFrom-Json })
if ($testResult.Count -ne 1 -or $testResult[0].type -ne "result" -or
    $testResult[0].id -ne $first.id -or $testResult[0].status -ne "PASS") {
  throw "Packaged native test returned unexpected JSONL"
}
Write-Host "PASS: Windows x64 MSI embeds executable runner and 225 test cases, with one isolated test round-trip."
