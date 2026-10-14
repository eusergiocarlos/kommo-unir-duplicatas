<#
.SYNOPSIS
  Gera requirements.lock e requirements-dev.lock (versões exatas + hashes SHA-256) com pip-compile.

.DESCRIPTION
  - pip-tools é instalado num venv TEMPORÁRIO (apagado no fim) — nada vai para o Python global nem para o .venv.
  - Entradas: requirements.in (execução) e requirements-dev.in (dev + build).
  - --generate-hashes: o pip passa a recusar qualquer arquivo com hash diferente (--require-hashes).
  - --allow-unsafe: inclui setuptools/pip no lock (o PyInstaller depende do setuptools; sem isso o
    "pip install --require-hashes" falha por dependência sem hash).
  - Precisa de internet (consulta o PyPI). Rode de novo para atualizar versões (--upgrade).
  - O lock é resolvido para ESTA plataforma/Python; dependências só-Windows (ex.: pywin32-ctypes) podem
    aparecer sem marcador. Para o build Linux, gere o lock no Linux com scripts/gerar_lock.sh.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\gerar_lock.ps1
  powershell -ExecutionPolicy Bypass -File scripts\gerar_lock.ps1 -Upgrade
#>
[CmdletBinding()]
param([switch]$Upgrade)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
function Falhar([string]$msg) { Write-Host "ERRO: $msg" -ForegroundColor Red; exit 1 }
function Checar([string]$msg) { if ($LASTEXITCODE -ne 0) { Falhar "$msg (código $LASTEXITCODE)" } }

$raiz = Split-Path -Parent $PSScriptRoot
Set-Location $raiz
$env:PIP_DISABLE_PIP_VERSION_CHECK = "1"
$env:PYTHONDONTWRITEBYTECODE = "1"

$py = $null
if (Test-Path ".venv\Scripts\python.exe") { $py = @((Resolve-Path ".venv\Scripts\python.exe").Path) }
elseif (Get-Command py -ErrorAction SilentlyContinue) { $py = @("py", "-3") }
elseif (Get-Command python -ErrorAction SilentlyContinue) { $py = @("python") }
else { Falhar "Python 3.10+ não encontrado." }

$tmp = Join-Path ([IO.Path]::GetTempPath()) ("kommo-lock-" + [guid]::NewGuid().ToString("N"))
try {
    $exe = $py[0]; $resto = @($py | Select-Object -Skip 1)
    & $exe @resto -m venv $tmp; Checar "não consegui criar o venv temporário"
    $tpy = Join-Path $tmp "Scripts\python.exe"
    & $tpy -m pip install -q "pip-tools>=7.4"; Checar "não consegui instalar pip-tools (sem internet?)"
    $extra = @(); if ($Upgrade) { $extra += "--upgrade" }
    foreach ($par in @(@("requirements.in", "requirements.lock"), @("requirements-dev.in", "requirements-dev.lock"))) {
        Write-Host "==> $($par[0]) -> $($par[1])" -ForegroundColor Cyan
        & $tpy -m piptools compile --quiet --generate-hashes --allow-unsafe --strip-extras --no-emit-index-url `
            --resolver=backtracking @extra --output-file $par[1] $par[0]
        Checar "pip-compile falhou para $($par[0])"
    }
} finally {
    if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue }
}
Write-Host "OK: requirements.lock e requirements-dev.lock atualizados. Revise o diff antes de versionar." -ForegroundColor Green
