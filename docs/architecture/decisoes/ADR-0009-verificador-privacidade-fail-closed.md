# ADR-0009 — Verificador de privacidade fail-closed

- **Status:** aceita
- **Data:** 2026-10

## Contexto

Um zip publicado à mão já vazou caminhos `C:\Users\<usuário>\...` por meio de arquivos `.pyc` (registro no próprio
`scripts/verificar_privacidade.py`). O app lida com dados de empresas (subdomínio, cookies), e a pasta `data/`
fica ao lado do programa ([ADR-0005](ADR-0005-modo-portatil-data-ao-lado.md)) — fácil de acabar dentro de um
pacote. Uma verificação que "avisa e segue" quando não consegue ler algo dá falsa segurança.

## Decisão

`scripts/verificar_privacidade.py` (só stdlib, importável e testado em `tests/test_verificador.py`):

- varre **todo arquivo como bytes** (UTF-8 e UTF-16LE), abrindo recursivamente zip/whl/tar/gz, o CArchive e o PYZ
  do PyInstaller (parser próprio) e AppImage (via `unsquashfs`);
- termos: usuário do SO, nome do computador, home (inclusive forma 8.3), `git config user.name/email`,
  `KOMMO_TERMOS_SENSIVEIS` e `--termo`; termos < 4 caracteres descartados, < 6 só com limite de palavra; termos
  mascarados na saída (exceto `--mostrar-termos`);
- checagens estruturais: pastas/arquivos de dados do usuário (`data`, `profile`, `logs`, `debug`, `config.json`…)
  e artefatos fora de `dist/`;
- **fail-closed:** qualquer coisa que não consiga abrir/ler/descomprimir é **erro** (código 1);
- roda no fim de `build_windows.ps1`/`build_linux.sh` (`--somente-dist`) — se falhar, o build falha — e no CI
  (modo projeto, com `--sem-termos-padrao` e um termo-sentinela aleatório).

## Alternativas consideradas

| Alternativa | Por que não |
|---|---|
| Só `.gitignore` | não cobre o conteúdo de binários nem o que entra no pacote |
| `grep` simples | não enxerga dentro de zip/PYZ/CArchive nem UTF-16 |
| Verificador "best effort" (avisa e segue) | dá falsa segurança exatamente nos arquivos que não consegue ler |
| Ferramentas de segredos (detect-secrets/gitleaks) | procuram tokens, não nomes de usuário/empresa; usadas em complemento no CI |

## Consequências

- **+** Barreira automática contra vazamento da máquina de build e da empresa nos pacotes.
- **−** Falsos positivos possíveis: binários de terceiros grandes só são varridos por termo **em formato de
  caminho**; no CI Linux, o usuário `runner` provavelmente casa com módulos do Python embutidos — motivo do job
  Linux ser experimental (ver [ci-cd.md](../../operations/ci-cd.md)). **Não validado no GitHub.**
- **−** AppImage sem `unsquashfs` disponível = erro (por desenho).
- **−** Só encontra termos que conhece: o nome da empresa precisa ser passado (`--termo`/`KOMMO_TERMOS_SENSIVEIS`).
