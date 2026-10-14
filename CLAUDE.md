# CLAUDE.md — Kommo — Unir Duplicatas

Guia operacional para o Claude Code neste repositório. Não duplica `docs/`: aponta para lá.

## Finalidade e arquitetura (resumo)

- App de desktop (Windows; Linux escrito e não testado) que automatiza o "Localizar e unir duplicatas" do Kommo,
  em Leads e Contatos, pela interface web, com o login do próprio usuário. **A união é irreversível.**
- `ui.py` (Tkinter) ou `cli.py` criam um `Job` e iniciam a thread `Merger` (`merger.py`); a conversa é só por
  eventos numa `queue.Queue` (`LogEvt`, `ProgEvt`, `ConfirmarEvt`, `FimEvt`).
- `merger.py` fala com a página só pela porta `kommo.PortaKommo` (`KommoPage` real; falsos em `tests/fakes.py`).
- `fluxo.py` tem a regra pura `avaliar_uniao`: só há SUCESSO com o texto de conclusão do Kommo.
- O limite conta **cliques** em "Unir"; PARAR é atendido entre uniões; o 2º pedido força a parada.
- `privacy.py`: init script + `MutationObserver` que borram dados na tela; `browser.py`: Playwright com perfil
  persistente por canal; `paths.py`: modo portátil em `<pasta do programa>/data`.
- Arquitetura completa: [docs/architecture/arquitetura.md](docs/architecture/arquitetura.md).

## Estrutura de pastas

```
main.py, iniciar.bat, iniciar.sh   entrada / rodar com .venv local
src/kommo_duplicatas/              app: ui, cli, mascara, merger, fluxo, kommo, privacy, browser, paths, config, logs, limite, temas
tests/                             pytest; fakes.py; fixtures/ (HTML anonimizado)
scripts/                           build_windows.ps1, build_exe.ps1, build_linux.sh, empacotar.py, gerar_lock.*, verificar_privacidade.py
packaging/linux/                   AppRun, .desktop (não testado)
docs/                              architecture/, requirements/, operations/, testing/, security/, KOMMO_DOM.md
.github/                           workflows ci.yml/release.yml, scripts/verificar_links.py, notas_release.py, modelos
data/                              DADOS DO USUÁRIO (gitignored) — nunca ler, copiar ou versionar
```

## Tecnologias (versões reais)

- Python: `requires-python >= 3.10`; ambiente de desenvolvimento em **3.14.x** (locks gerados com 3.14); CI
  testa 3.12, 3.13 e 3.14 (todas obrigatórias); build de release com 3.14.
- `playwright==1.63.0`, `pyinstaller==6.22.3`, `pytest==9.1.1` (`requirements*.lock`, com hashes).
- `pytest-cov==7.1.0` no `requirements-dev.lock`. `ruff==0.17.0` no CI e no extra `dev` do `pyproject.toml` (não
  está nos `.in`/`.lock`). Tkinter da biblioteca padrão.

## Comandos

| O quê | Comando |
|---|---|
| Instalar (dev, reproduzível) | `python -m venv .venv` e `.venv\Scripts\python -m pip install --require-hashes --no-deps -r requirements-dev.lock` |
| Instalar (faixas abertas) | `python -m pip install -r requirements-dev.txt` |
| Rodar interface | `python main.py` (ou `iniciar.bat`) |
| Rodar CLI | `python main.py --cli <empresa> {leads,contatos} <limite> [--ensaio] [--sim] [--sem-privacidade]` (saída 0 ok · 2 parado/recusado · 1 erro · 64 erro de uso) |
| Testes | `python -m pytest -q -p no:cacheprovider` (453 aprovados na última conferência, 14/10/2026); `--cov` com pytest-cov (no lock) |
| Lint | `ruff check .` (regras em `pyproject.toml`) |
| Verificador de privacidade | `python -B scripts/verificar_privacidade.py [--termo X]` |
| Links da documentação | `python -B .github/scripts/verificar_links.py` |
| Build Windows | `powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1` (`-OneFile`, `-SemInstalar`) |
| Build Linux (não testado) | `bash scripts/build_linux.sh` |
| Regenerar locks (internet) | `scripts\gerar_lock.ps1` / `scripts/gerar_lock.sh` |

Use `-B` / `-p no:cacheprovider`: `.pyc` e caches guardam o caminho absoluto da máquina.

## Convenções de código

- **pt-BR** em tudo que o usuário vê (UI, log, erros, docs) e nos comentários.
- Mantenha os nomes existentes (`Merger`, `Job`, `KommoPage`, `PortaKommo`, `Estado`, `SELETORES`,
  `Resultado`...). Nada de abstração desnecessária; prefira a mudança simples e local.
- **Seletores do Kommo só em `kommo.py` (classe `Seletores`) e `privacy.py` (`SELETORES`, a lista de CSS da
  privacidade; os seletores do processo vêm de `kommo.SELETORES`, importado como `SEL_KOMMO`).** Mudar um seletor
  exige atualizar [docs/KOMMO_DOM.md](docs/KOMMO_DOM.md) e os testes (`tests/fixtures/`, `test_kommo_js.py`,
  `test_privacy_js.py`).
- A UI nunca fala com o navegador. Regras de decisão vão em funções puras testáveis (`fluxo.py`, `limite.py`,
  textos de `ui.py`).
- Comente o porquê de esperas, limites e *fallbacks*. Lint conservador; não reformatar arquivos existentes.

## Segurança e privacidade (inegociável)

- **Nunca** commitar `data/`, `profile/`, `config.json`, logs, `debug/`, capturas de tela ou diagnósticos com
  dados de clientes, nem artefatos (`dist/`, `.zip`, `.exe`, `.tar.gz`, `.AppImage`).
- **Nunca** rodar o app contra conta de produção sem antes um ensaio (`--ensaio`) e depois um limite pequeno
  (ex.: 3). A união é irreversível. No `.vscode/launch.json`, as configurações de CLI com "ENSAIO" no nome usam
  `--ensaio`; só a "⚠ CLI — UNIR 3 (REAL, irreversível)" une de verdade (e ainda pergunta `[s/N]`).
- Com privacidade (padrão), janela **e** CLI mascaram subdomínio/totais na tela e no log (`mascara.py`).
- Testes **nunca** acessam o Kommo real: use `tests/fakes.py` e `KOMMO_DATA_DIR` em `tmp_path`.
- **Nunca** imprimir termos sensíveis (subdomínio real, nomes, `KOMMO_TERMOS_SENSIVEIS`); não usar
  `--mostrar-termos` em CI ou em relatórios. Exemplos sempre com `acme` / `<empresa>`.
- Rodar o verificador de privacidade antes de qualquer commit ou publicação; ele é fail-closed.
- Não abrir nem ler a pasta de dados real do usuário (`data/`, ou `%APPDATA%\KommoUnirDuplicatas` da 1.0.0).

## Segredos

O app não tem segredos: não há API, token ou senha no código ou na configuração. O login do Kommo existe só no
perfil do navegador em `data/profile/<canal>` (apagável com "Esquecer login salvo"). No CI, o único valor
sensível opcional é o secret `KOMMO_TERMOS_SENSIVEIS` (ver [docs/operations/ci-cd.md](docs/operations/ci-cd.md)).

## Distribuição

Pasta portátil (PyInstaller onedir) zipada + `SHA256SUMS.txt`, gerada por `scripts/build_windows.ps1`, que
termina rodando o verificador sobre `dist\windows` (falha = não publicar). Release via tag `vX.Y.Z` →
`release.yml` → Release em **rascunho** com aprovação manual. Versão igual em `src/kommo_duplicatas/__init__.py`,
`pyproject.toml` e seção no `CHANGELOG.md`. Sem assinatura de código. Nenhuma release publicada até agora.
Detalhes: [docs/operations/build-distribuicao.md](docs/operations/build-distribuicao.md).

## Validação de uma mudança

1. `python -m pytest -q -p no:cacheprovider` passando (cole a contagem real no relatório).
2. `ruff check .` sem erros (se disponível).
3. `python -B scripts/verificar_privacidade.py` saindo com 0.
4. `python -B .github/scripts/verificar_links.py` se mexeu em Markdown.
5. Checklist manual de [docs/testing/estrategia.md](docs/testing/estrategia.md) quando a mudança tocar o fluxo
   real (só com conta de teste, ensaio primeiro, limite pequeno).

## Regras de delegação (sessões com subagentes)

- O **orquestrador não implementa**: planeja, delega, revisa e integra.
- **Um subagente por tarefa**, com escopo e arquivos explícitos.
- Paralelizar **só** tarefas que não editam os mesmos arquivos.
- Distribuição de modelos:
  - **Fable 5.1** — arquitetura, bugs complexos, revisão crítica;
  - **Opus 5.5** — implementação, testes, documentação, refatoração;
  - **Haiku 4.5** — levantamentos e resumos.
- Se um modelo estiver indisponível, **declarar** isso e usar o mais adequado disponível.
- Exigir de cada subagente um **relatório com evidências**: arquivos alterados, comandos executados com a saída
  real, pendências e inconsistências encontradas.

## Critérios de aceitação

- Testes, lint e verificador passando; nenhuma regressão nas regras de segurança do motor (limite por cliques,
  confirmação de conta, validação de hostname/caminho/modal, PARAR entre uniões).
- Nada de dados reais ou da máquina em código, testes, docs ou artefatos.
- Comandos e caminhos citados na documentação existem de fato.
- **Documentar toda mudança: docs/, CHANGELOG e CLAUDE.md no mesmo commit.**

## Referências

- [README.md](README.md) · [CHANGELOG.md](CHANGELOG.md) · [CONTRIBUTING.md](CONTRIBUTING.md) ·
  [SECURITY.md](SECURITY.md)
- Arquitetura: [arquitetura](docs/architecture/arquitetura.md), [jornadas](docs/architecture/jornadas.md),
  [modelo de dados](docs/architecture/modelo-de-dados.md), [decisões](docs/architecture/decisoes/)
- Requisitos: [funcionais](docs/requirements/funcionais.md), [não funcionais](docs/requirements/nao-funcionais.md)
- Operação: [instalação](docs/operations/instalacao.md), [execução](docs/operations/execucao.md),
  [build e distribuição](docs/operations/build-distribuicao.md),
  [recuperação de falhas](docs/operations/recuperacao-falhas.md), [SLO](docs/operations/slo.md),
  [CI/CD](docs/operations/ci-cd.md)
- Testes: [estratégia](docs/testing/estrategia.md), [rastreabilidade](docs/testing/rastreabilidade.md)
- Segurança: [docs/security/seguranca.md](docs/security/seguranca.md) · DOM do Kommo:
  [docs/KOMMO_DOM.md](docs/KOMMO_DOM.md)
