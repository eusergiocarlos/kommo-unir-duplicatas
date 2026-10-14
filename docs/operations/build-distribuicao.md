# Build e distribuição

Como gerar os pacotes, conferir hashes e privacidade, manter o lock e publicar. Conferido em
`scripts/build_windows.ps1`, `scripts/build_exe.ps1`, `scripts/build_linux.sh`, `scripts/empacotar.py`,
`scripts/verificar_privacidade.py`, `scripts/gerar_lock.*`, `packaging/linux/` e `.github/workflows/`.
Pipeline do GitHub em detalhe: [ci-cd.md](ci-cd.md). Decisões: [ADR-0008](../architecture/decisoes/ADR-0008-pyinstaller-onedir-zip.md),
[ADR-0009](../architecture/decisoes/ADR-0009-verificador-privacidade-fail-closed.md).

## 1. Build local no Windows (formato principal)

Pré-requisitos: Python 3.10+ no PATH (`py -3` ou `python`), internet na primeira vez (ou `-SemInstalar` com o
`.venv` já pronto). O lock atual foi gerado com **Python 3.14**: com outra versão o `pip install --require-hashes`
pode falhar.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1            # onedir + zip (padrão)
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1 -OneFile   # .exe único (alternativa)
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1 -SemInstalar
powershell -ExecutionPolicy Bypass -File scripts\build_exe.ps1                # = -OneFile (compatibilidade)
```

O que o script faz, em ordem:

1. Usa/cria `.venv` (nunca o Python global) e exige Python ≥ 3.10.
2. Instala `requirements-dev.lock` com `--require-hashes --no-deps`; sem lock, instala `requirements-dev.txt` com
   **aviso** (build não reproduzível).
3. Lê a versão de `src/kommo_duplicatas/__init__.py` (`empacotar.py versao`).
4. Limpa só os artefatos em `dist\windows\`; avisa se houver `build\` ou `.spec` antigos no projeto.
5. PyInstaller `--onedir` (ou `--onefile`) `--windowed --collect-all playwright --exclude-module pytest`, com
   `--workpath`/`--specpath` numa pasta temporária apagada no fim; `PYTHONDONTWRITEBYTECODE=1`.
6. Zip determinístico (`empacotar.py zip`) e `SHA256SUMS.txt` (`empacotar.py sha256`).
7. **Verificador de privacidade** `--somente-dist --dist dist\windows`; se falhar, o build **falha** com
   "verificação de privacidade FALHOU — NÃO publique o conteúdo de dist\windows."

### Resultado

```text
dist\windows\
├─ KommoUnirDuplicatas\                      pasta do programa (KommoUnirDuplicatas.exe + _internal\)
├─ KommoUnirDuplicatas-<versão>-win64.zip    o que se publica
└─ SHA256SUMS.txt                            "<sha256>  <nome>" (formato GNU)
```

Com `-OneFile`: `dist\windows\KommoUnirDuplicatas.exe` + `SHA256SUMS.txt`.

> Pode existir um `dist\KommoUnirDuplicatas.exe` antigo (formato v1.0.0) na raiz de `dist\`; o script atual não o
> gera nem o apaga. Não o publique.

### Conferir

```powershell
Get-FileHash dist\windows\KommoUnirDuplicatas-1.0.0-win64.zip -Algorithm SHA256
Get-Content dist\windows\SHA256SUMS.txt
```

Teste o zip num Windows limpo: extraia, abra, faça um **ensaio** (nada é unido). Confira que `data\` foi criada
**dentro** da pasta extraída.

## 2. Verificador de privacidade

```powershell
python -B scripts\verificar_privacidade.py                         # projeto inteiro (inclui dist\)
python -B scripts\verificar_privacidade.py --termo minhaempresa    # + nome da empresa (repetível)
python -B scripts\verificar_privacidade.py --somente-dist --dist dist\windows
python -B scripts\verificar_privacidade.py --json
```

- Termos padrão: usuário do SO, nome do computador, home (e forma 8.3), `git user.name/email`, mais
  `KOMMO_TERMOS_SENSIVEIS` (vírgulas) e `--termo`. `--sem-termos-padrao` desliga os do sistema (usado no CI).
- Abre zip/tar/gz, o CArchive e o PYZ do PyInstaller e AppImage (com `unsquashfs`).
- **Fail-closed:** achado **ou** arquivo ilegível → código 1. Termos aparecem mascarados (`ful***#3fa9c1`), salvo
  `--mostrar-termos`.
- Também acusa pastas/arquivos de dados (`data/`, `profile/`, `logs/`, `debug/`, `config.json`…) e artefatos fora
  de `dist/`.

## 3. Lock e reprodutibilidade

| Arquivo | Papel |
|---|---|
| `requirements.in` | dependência direta de execução (`playwright>=1.40,<2`) |
| `requirements-dev.in` | `-r requirements.in` + `pytest`, `pytest-cov`, `pyinstaller` |
| `requirements.lock` / `requirements-dev.lock` | versões exatas + hashes SHA-256 (gerados com Python 3.14) |
| `requirements.txt` / `requirements-dev.txt` | faixas abertas (instalação rápida; não reproduzível) |

Regenerar (precisa de internet; pip-tools num venv temporário):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\gerar_lock.ps1            # ou -Upgrade
bash scripts/gerar_lock.sh                                                 # Linux — NÃO testado
```

- O lock é resolvido para a plataforma/Python onde foi gerado; o lock gerado no Windows traz pacotes só-Windows
  (`pywin32-ctypes`, `pefile`, `colorama`).
- Zips/tar.gz reproduzíveis: `empacotar.py` usa ordem alfabética, permissões normalizadas e data fixa
  (`SOURCE_DATE_EPOCH`, padrão 2020-01-01; no `release.yml`, a data do commit). O executável do PyInstaller em si
  **não** foi verificado como bit a bit reproduzível.

## 4. Linux (NÃO testado)

```bash
bash scripts/build_linux.sh                 # gera dist/linux/
SEM_INSTALAR=1 bash scripts/build_linux.sh
APPIMAGETOOL=/caminho/appimagetool bash scripts/build_linux.sh
```

Saída prevista: `dist/linux/KommoUnirDuplicatas/`, `KommoUnirDuplicatas-<versão>-linux-<arch>.tar.gz`, AppImage
opcional (só com `appimagetool` **e** `unsquashfs`; ícone placeholder cinza) e `SHA256SUMS.txt`, com o verificador
no fim. Requisitos de build: `python3-venv`, `python3-tk`; glibc da máquina de build define as distros suportadas.
**Nunca rodou numa máquina Linux real**; roteiro de teste em [packaging/linux/README.md](../../packaging/linux/README.md).

## 5. Release pelo GitHub

Resumo (detalhes, configuração e limitações em [ci-cd.md](ci-cd.md)):

- Tag `vX.Y.Z` (igual a `__version__` e `pyproject.toml`; seção no `CHANGELOG.md`) dispara `release.yml`:
  CI completo → build Windows (Python 3.14) → build Linux experimental → SBOM CycloneDX → atestação de
  proveniência (`continue-on-error`) → **Release em rascunho** após aprovação do environment `release`.
- Publicar é **manual**. Passo a passo: [jornada (n)](../architecture/jornadas.md#n-publicar-uma-release-dono-do-projeto).
- **Nenhum workflow foi executado no GitHub até agora.** O falso positivo previsto do verificador no CI (usuário
  `runner` como termo) já foi tratado nos scripts de build: com `CI=true` eles usam `--sem-termos-padrao` + termo-
  sentinela aleatório + `KOMMO_TERMOS_SENSIVEIS` ([ci-cd.md](ci-cd.md#2-releaseyml)).

## 6. Assinatura de código (ausente)

Não há certificado Authenticode. Consequências: avisos do SmartScreen e falsos positivos de antivírus
([instalação §1.5](instalacao.md#15-smartscreen-e-antivírus)). A integridade depende do `SHA256SUMS.txt` (e da
atestação, quando disponível). Assinar exigiria comprar um certificado e guardá-lo como secret — decisão pendente
do dono.
