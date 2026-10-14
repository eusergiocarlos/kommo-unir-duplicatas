<#
.SYNOPSIS
  Build oficial para Windows: pasta portátil (onedir) zipada + SHA256SUMS + verificação de privacidade.

.DESCRIPTION
  Gera:
    dist\windows\KommoUnirDuplicatas\                       (pasta do programa: .exe + _internal\)
    dist\windows\KommoUnirDuplicatas-<versão>-win64.zip      (o que se publica)
    dist\windows\SHA256SUMS.txt
  Com -OneFile gera dist\windows\KommoUnirDuplicatas.exe (arquivo único; formato antigo, alternativa).

  - Usa SEMPRE o ambiente virtual local .venv (cria se faltar); nunca instala no Python global.
  - Instala de requirements-dev.lock (versões fixas + hashes, --require-hashes) se existir; senão de
    requirements-dev.txt com AVISO (build não reproduzível). Gere o lock com scripts\gerar_lock.ps1.
  - build\ e .spec do PyInstaller vão para uma pasta temporária, apagada no fim (nada fica no projeto).
  - No fim roda scripts\verificar_privacidade.py --somente-dist (fail-closed): se achar algo, o build FALHA.
  - Versão lida de src\kommo_duplicatas\__init__.py (__version__).

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
  powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1 -OneFile
#>
[CmdletBinding()]
param(
    [switch]$OneFile,
    # Pula a instalação/atualização de dependências (usa o .venv como está). Útil sem internet.
    [switch]$SemInstalar
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Falhar([string]$msg) {
    Write-Host ""
    Write-Host "ERRO: $msg" -ForegroundColor Red
    exit 1
}
function Etapa([string]$msg) { Write-Host ""; Write-Host "==> $msg" -ForegroundColor Cyan }
function Checar([string]$msg) { if ($LASTEXITCODE -ne 0) { Falhar "$msg (código $LASTEXITCODE)" } }

$raiz = Split-Path -Parent $PSScriptRoot
Set-Location $raiz
$nome = "KommoUnirDuplicatas"
$saida = Join-Path $raiz "dist\windows"
$venvPy = Join-Path $raiz ".venv\Scripts\python.exe"
$env:PYTHONDONTWRITEBYTECODE = "1"      # não criar __pycache__ em src\ (contém caminho absoluto da máquina)
$env:PIP_DISABLE_PIP_VERSION_CHECK = "1"

if (-not (Test-Path (Join-Path $raiz "main.py"))) { Falhar "main.py não encontrado em $raiz" }
if (-not (Test-Path (Join-Path $raiz "src\kommo_duplicatas\__init__.py"))) { Falhar "src\kommo_duplicatas\__init__.py não encontrado" }

# ------------------------------------------------------------------ 1. ambiente virtual
Etapa "Ambiente virtual (.venv)"
if (-not (Test-Path $venvPy)) {
    $base = $null
    if (Get-Command py -ErrorAction SilentlyContinue) { $base = @("py", "-3") }
    elseif (Get-Command python -ErrorAction SilentlyContinue) { $base = @("python") }
    else { Falhar "Python 3.10+ não encontrado no PATH. Instale de https://www.python.org/downloads/ e rode de novo." }
    $exe = $base[0]; $resto = @($base | Select-Object -Skip 1)
    & $exe @resto -m venv (Join-Path $raiz ".venv"); Checar "não consegui criar o .venv"
}
& $venvPy -c "import sys; assert sys.version_info >= (3, 10), sys.version" ; Checar "o .venv precisa de Python 3.10+"

# ------------------------------------------------------------------ 2. dependências
if (-not $SemInstalar) {
    Etapa "Dependências"
    $lock = Join-Path $raiz "requirements-dev.lock"
    if (Test-Path $lock) {
        & $venvPy -m pip install --require-hashes --no-deps -q -r $lock; Checar "pip install do lock falhou"
    } else {
        Write-Host "AVISO: requirements-dev.lock não existe -> instalando de requirements-dev.txt (versões abertas;" -ForegroundColor Yellow
        Write-Host "       build NÃO reproduzível). Gere o lock com: scripts\gerar_lock.ps1" -ForegroundColor Yellow
        & $venvPy -m pip install -q -r (Join-Path $raiz "requirements-dev.txt"); Checar "pip install falhou"
    }
}
& $venvPy -c "import PyInstaller, playwright" ; Checar "PyInstaller/playwright não estão no .venv (rode sem -SemInstalar)"

# ------------------------------------------------------------------ 3. versão
$versao = (& $venvPy (Join-Path $raiz "scripts\empacotar.py") versao (Join-Path $raiz "src\kommo_duplicatas\__init__.py")).Trim()
Checar "não consegui ler __version__"
if ($versao -notmatch '^[0-9A-Za-z.+-]+$') { Falhar "versão inválida: '$versao'" }
Write-Host "Versão: $versao"

# ------------------------------------------------------------------ 4. limpar saída anterior (só dentro de dist\windows)
Etapa "Limpando dist\windows"
New-Item -ItemType Directory -Force $saida | Out-Null
foreach ($alvo in @("$saida\$nome", "$saida\$nome.exe", "$saida\$nome-$versao-win64.zip", "$saida\SHA256SUMS.txt")) {
    if (Test-Path $alvo) { Remove-Item -Recurse -Force $alvo }
}
foreach ($legado in @("$raiz\build", "$raiz\$nome.spec")) {
    if (Test-Path $legado) { Write-Host "AVISO: sobra de build antigo no projeto: $legado (pode apagar)" -ForegroundColor Yellow }
}

# ------------------------------------------------------------------ 5. PyInstaller (work/spec em pasta temporária)
$tmp = Join-Path ([IO.Path]::GetTempPath()) ("kommo-build-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force $tmp | Out-Null
try {
    Etapa ("PyInstaller (" + ($(if ($OneFile) { "onefile" } else { "onedir" })) + ")")
    $modo = if ($OneFile) { "--onefile" } else { "--onedir" }
    $argsPi = @(
        "-m", "PyInstaller", "--noconfirm", "--clean", $modo, "--windowed",
        "--name", $nome,
        "--paths", (Join-Path $raiz "src"),
        "--collect-all", "playwright",
        "--exclude-module", "pytest",
        "--distpath", $saida,
        "--workpath", (Join-Path $tmp "work"),
        "--specpath", (Join-Path $tmp "spec"),
        (Join-Path $raiz "main.py")
    )
    & $venvPy @argsPi; Checar "PyInstaller falhou"

    # ------------------------------------------------------------------ 6. empacotar + hashes
    Etapa "Empacotando"
    $publicar = @()
    if ($OneFile) {
        $exe = Join-Path $saida "$nome.exe"
        if (-not (Test-Path $exe)) { Falhar "PyInstaller não gerou $exe" }
        $publicar += $exe
    } else {
        $pasta = Join-Path $saida $nome
        if (-not (Test-Path (Join-Path $pasta "$nome.exe"))) { Falhar "PyInstaller não gerou $pasta\$nome.exe" }
        $zip = Join-Path $saida "$nome-$versao-win64.zip"
        & $venvPy (Join-Path $raiz "scripts\empacotar.py") zip $pasta $zip; Checar "falha ao criar o zip"
        $publicar += $zip
    }
    $sums = Join-Path $saida "SHA256SUMS.txt"
    & $venvPy (Join-Path $raiz "scripts\empacotar.py") sha256 $sums @publicar; Checar "falha ao gerar SHA256SUMS"
} finally {
    if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue }
}

# ------------------------------------------------------------------ 7. privacidade (fail-closed)
Etapa "Verificando privacidade do resultado (dist\windows)"
# No CI (GitHub Actions define CI=true) o usuário do runner ("runner"/"runneradmin") e o hostname não identificam
# ninguém e "runner" é substring de módulos do próprio Python embutidos no pacote (ex.: asyncio\runners.py) →
# falso positivo que derrubaria o build. Por isso, só no CI: --sem-termos-padrao (sem usuário/host/git), mais
# um termo-sentinela ALEATÓRIO (nunca existe nos arquivos) porque o verificador é fail-closed sem nenhum termo;
# assim as checagens estruturais (data\, logs, arquivos ilegíveis...) continuam rodando. Termos reais vêm de
# KOMMO_TERMOS_SENSIVEIS (secret), lido pelo próprio verificador. Localmente: termos padrão, como sempre.
$argsPriv = @((Join-Path $raiz "scripts\verificar_privacidade.py"), "--somente-dist", "--dist", $saida)
if ($env:CI -eq "true") {
    $sentinela = "sentinela-ci-" + [guid]::NewGuid().ToString("N").Substring(0, 16)
    $argsPriv += @("--sem-termos-padrao", "--termo", $sentinela)
    Write-Host "CI detectado: verificador sem termos do sistema (só KOMMO_TERMOS_SENSIVEIS + checagens estruturais)."
}
& $venvPy @argsPriv
if ($LASTEXITCODE -ne 0) {
    Falhar "verificação de privacidade FALHOU — NÃO publique o conteúdo de dist\windows. Veja os achados acima."
}

Etapa "Pronto"
foreach ($p in $publicar) { Write-Host ("  " + $p + "  (" + [math]::Round((Get-Item $p).Length / 1MB, 1) + " MB)") }
Write-Host "  $sums"
Get-Content $sums | ForEach-Object { Write-Host "    $_" }
exit 0
