# ADR-0005 — Modo portátil: `data/` ao lado do programa

- **Status:** aceita (substitui o uso de `%APPDATA%\KommoUnirDuplicatas` da v1.0.0)
- **Data:** 2026-10

## Contexto

A v1.0.0 gravava perfil do navegador, `config.json` e logs em `%APPDATA%\KommoUnirDuplicatas\`. Isso escondia do
usuário onde estavam os **cookies da sessão do CRM**, deixava resíduos depois de "desinstalar" (apagar o `.exe`)
e dificultava levar o app junto ou usar contas diferentes em cópias diferentes. Além disso, `os.access(W_OK)` no
Windows ignora ACLs, então uma pasta protegida podia parecer gravável.

## Decisão

- A raiz de dados é `<pasta do programa>/data` (`paths.app_dir()`: pasta do `.exe` ou raiz do repositório), ou
  `KOMMO_DATA_DIR` (relativo → relativo à pasta do programa).
- A escrita é testada de verdade (criar e apagar arquivo).
- Sem permissão: `paths.DataDirNotWritable` com explicação e duas soluções (mover a pasta ou definir
  `KOMMO_DATA_DIR`). **Nunca** cai em silêncio para `%APPDATA%` ou outro lugar.
- `DataDirNotWritable` herda de `RuntimeError` para não ser engolida por `except OSError`.
- AppImage (Linux, **não testado**): `AppRun` aponta `KOMMO_DATA_DIR` para uma pasta ao lado do `.AppImage`.

## Alternativas consideradas

| Alternativa | Por que não |
|---|---|
| `%APPDATA%` / `~/.config` | dados sensíveis "invisíveis"; resíduos após apagar o app; era o comportamento antigo |
| Portátil com *fallback* automático para `%APPDATA%` | o usuário não saberia onde ficou o login; dois lugares para limpar |
| Perguntar a pasta na primeira execução | mais um passo para usuário não técnico; `KOMMO_DATA_DIR` cobre o caso avançado |

## Consequências

- **+** Tudo num lugar visível; desinstalar = apagar a pasta; várias cópias independentes possíveis.
- **+** Mensagem clara quando a pasta é protegida (testado em `tests/test_paths.py` e `test_ui_integracao.py`).
- **−** Não funciona em `C:\Program Files` nem em mídia somente leitura sem `KOMMO_DATA_DIR`.
- **−** Quem copiar/compartilhar a pasta do programa **depois de usar** compartilha os cookies (aviso em
  [instalação](../../operations/instalacao.md)); o verificador de privacidade bloqueia `data/` nos builds.
- **−** Documentos antigos (`README.md`, `CHANGELOG.md`, `docs/ESTRUTURA.md`, trecho de `SECURITY.md`) ainda citam
  `%APPDATA%`.
