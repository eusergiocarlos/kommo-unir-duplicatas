# ADR-0008 — PyInstaller onedir zipado como formato principal no Windows

- **Status:** aceita (substitui o `--onefile` da v1.0.0, mantido como alternativa)
- **Data:** 2026-10

## Contexto

A v1.0.0 distribuía um único `KommoUnirDuplicatas.exe` (`--onefile`). Problemas: o *onefile* se extrai num
diretório temporário a cada execução (mais lento, mais alarmes de antivírus), e o modo portátil
([ADR-0005](ADR-0005-modo-portatil-data-ao-lado.md)) precisa de uma **pasta do programa** estável onde criar
`data/`. Um `.exe` solto na pasta Downloads criaria `data/` ali, misturado com outros arquivos.

## Decisão

- `scripts/build_windows.ps1` gera, por padrão, **onedir** `--windowed` com `--collect-all playwright`
  (driver Node.js embutido) e `--exclude-module pytest`:
  - `dist\windows\KommoUnirDuplicatas\` (o `.exe` + `_internal\`);
  - `dist\windows\KommoUnirDuplicatas-<versão>-win64.zip` (o que se publica), criado por `scripts/empacotar.py`
    de forma **determinística** (ordem alfabética, data fixa `SOURCE_DATE_EPOCH`, pasta raiz dentro do zip);
  - `dist\windows\SHA256SUMS.txt` (formato GNU `sha256sum`).
- `-OneFile` (ou `scripts/build_exe.ps1`) continua gerando `dist\windows\KommoUnirDuplicatas.exe`.
- Build sempre no `.venv` local, a partir de `requirements-dev.lock` com `--require-hashes`; arquivos temporários
  do PyInstaller fora do projeto; verificador de privacidade no fim ([ADR-0009](ADR-0009-verificador-privacidade-fail-closed.md)).

## Alternativas consideradas

| Alternativa | Por que não |
|---|---|
| `--onefile` como principal | extração a cada execução, sem pasta estável para `data/`, mais falso positivo de antivírus |
| Instalador (MSI/Inno Setup) | instalaria em Program Files (sem escrita para `data/`) e exigiria administrador; mais uma ferramenta no build |
| Nuitka/cx_Freeze | PyInstaller já resolve o `--collect-all playwright`; sem ganho claro que justificasse a troca |

## Consequências

- **+** Pasta autocontida; o zip carrega a pasta raiz (não "espalha" arquivos ao extrair); hashes reproduzíveis.
- **+** Início mais rápido que o *onefile*.
- **−** O usuário precisa **extrair** o zip (rodar de dentro do zip não funciona bem e não grava `data/`).
- **−** **Sem assinatura de código** (Authenticode): SmartScreen/antivírus podem alertar. Assinar exige certificado
  pago — decisão do dono, ainda não tomada.
- **−** Navegador não incluso: depende de Chrome/Edge ([ADR-0006](ADR-0006-perfil-por-canal-navegador-do-sistema.md)).
- **−** O `dist/` local ainda pode conter um `KommoUnirDuplicatas.exe` antigo na raiz de `dist/` (formato v1);
  ele não é gerado pelo script atual.
