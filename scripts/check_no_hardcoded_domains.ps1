param(
  [string]$Root = "."
)

$ErrorActionPreference = "Stop"

$defaultForbiddenParts = @("nas", "tlsi", "top")
$defaultForbidden = @($defaultForbiddenParts -join ".")

$forbidden = @()
if ($env:FORBIDDEN_DOMAINS) {
  $forbidden = $env:FORBIDDEN_DOMAINS.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ }
} else {
  $forbidden = $defaultForbidden
}

# Allow domain declarations only in configuration files.
$allowPatterns = @(
  "\\.env$",
  "\\.env\\.example$",
  "frontend\\.env$",
  "frontend\\.env\\.example$"
)

$rootPath = (Resolve-Path $Root).Path
$files = Get-ChildItem -Path $rootPath -Recurse -File -ErrorAction SilentlyContinue
$violations = @()

foreach ($file in $files) {
  $path = $file.FullName

  if (
    $path -match '\\\.git\\' -or
    $path -match '\\bak3\.2\\' -or
    $path -match '\\archive\\' -or
    $path -match '__pycache__' -or
    $path -match '\\\.pytest_cache\\' -or
    $path -match '\\node_modules\\' -or
    $path.EndsWith('.bak', [System.StringComparison]::OrdinalIgnoreCase)
  ) { continue }

  try {
    $content = Get-Content -Path $path -Raw -Encoding UTF8 -ErrorAction Stop
  } catch {
    continue
  }
  foreach ($item in $forbidden) {
    if ($content -match [regex]::Escape($item)) {
      $allowed = $false
      foreach ($pattern in $allowPatterns) {
        if ($path -match $pattern) {
          $allowed = $true
          break
        }
      }
      if (-not $allowed) {
        $violations += "$path => $item"
      }
    }
  }
}

if ($violations.Count -gt 0) {
  Write-Error "Found forbidden hardcoded domain(s) in non-config files:`n$($violations | Sort-Object -Unique | ForEach-Object { ' - ' + $_ } | Out-String)"
  exit 1
}

Write-Output "No forbidden hardcoded domains found."
