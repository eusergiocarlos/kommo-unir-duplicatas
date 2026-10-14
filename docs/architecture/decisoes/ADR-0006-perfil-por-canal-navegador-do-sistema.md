# ADR-0006 — Perfil por canal e uso do Chrome/Edge do sistema

- **Status:** aceita
- **Data:** 2026-10

## Contexto

Embutir um navegador no pacote aumentaria muito o tamanho e o deixaria desatualizado (correções de segurança do
navegador dependeriam de novas versões do app). Os usuários já têm Chrome ou Edge. Porém um diretório de perfil
criado por um navegador não deve ser aberto por outro (formatos/versões diferentes), e um perfil já aberto
(`SingletonLock`/`lockfile`) faz o lançamento falhar com mensagens confusas.

## Decisão

- `browser.abrir_contexto` usa `launch_persistent_context` com `channel` = `chrome`, `msedge` ou o Chromium do
  Playwright (`channel=None`). Ordem: Windows/macOS Chrome → Edge → Chromium; Linux Chrome → (Edge, se instalado)
  → Chromium. O canal que funcionou fica em `config.json` (`canal_navegador`) e é tentado primeiro.
  `KOMMO_BROWSER` força um canal.
- **Um perfil por canal:** `data/profile/<canal>/`.
- Antes de abrir: `perfil_em_uso()` (Windows: `lockfile` sem escrita; Linux/macOS: `SingletonLock` com pid vivo).
  Falha por perfil travado **não** tenta outro canal; mostra `mensagem_perfil_em_uso`.
- Argumentos: `--start-maximized --disable-notifications --deny-permission-prompts`, `headless=False`,
  `chromium_sandbox=True`, `locale="pt-BR"`.
- No `.exe` Windows, `PLAYWRIGHT_BROWSERS_PATH` aponta para `%LOCALAPPDATA%\ms-playwright` (onde ficaria um
  Chromium instalado pelo usuário).

## Alternativas consideradas

| Alternativa | Por que não |
|---|---|
| Embutir o Chromium do Playwright | pacote de centenas de MB; navegador sem atualização automática |
| Perfil único compartilhado entre canais | risco de corromper o perfil ao trocar de navegador |
| Usar o perfil pessoal do usuário no Chrome | conflito com o Chrome aberto; expõe todas as contas/abas pessoais à automação |
| Trocar de canal automaticamente quando o perfil está travado | levaria a um "login perdido" confuso em outro navegador |

## Consequências

- **+** Pacote menor; navegador atualizado pelo próprio sistema; login isolado do perfil pessoal.
- **+** Mensagens claras para "nenhum navegador" e "perfil em uso" (testadas em `tests/test_browser.py`).
- **−** Trocar de navegador (ou definir `KOMMO_BROWSER`) exige **novo login** (outro perfil).
- **−** Sem Chrome/Edge, o `.exe` não consegue instalar o Chromium sozinho (`playwright install` não roda a partir
  do binário congelado).
- **−** Mudanças do Chrome/Edge podem afetar a automação; Linux **não testado**.
