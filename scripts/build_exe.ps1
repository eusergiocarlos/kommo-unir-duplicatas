# COMPATIBILIDADE: gera o .exe de arquivo único (formato antigo) chamando o build oficial.
# O formato principal agora é a PASTA portátil zipada:  scripts\build_windows.ps1
# Saída: dist\windows\KommoUnirDuplicatas.exe (antes era dist\KommoUnirDuplicatas.exe).
# Uso:  powershell -ExecutionPolicy Bypass -File scripts\build_exe.ps1
$ErrorActionPreference = "Stop"
& (Join-Path $PSScriptRoot "build_windows.ps1") -OneFile @args
exit $LASTEXITCODE
