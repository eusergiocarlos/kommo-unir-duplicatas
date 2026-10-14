# Como contribuir

Obrigado pelo interesse! Antes de começar, leia o [README](README.md), a [arquitetura do projeto](docs/architecture/arquitetura.md),
a [política de segurança](SECURITY.md) e o [código de conduta](CODE_OF_CONDUCT.md).

> ⚠️ **A união de duplicatas no Kommo é irreversível.** Nunca teste uma mudança contra uma conta de produção sem
> antes ensaiar com os testes automatizados e, no teste manual, use uma conta de teste e um **limite pequeno**
> (ex.: 3).

## Ambiente de desenvolvimento

Requisitos: Python 3.10+ (o CI testa 3.12, 3.13 e 3.14 — todas obrigatórias; 3.14 é a do lock e do build), Git, Chrome ou Edge.

```powershell
python -m venv .venv
.venv\Scripts\activate                     # Linux: source .venv/bin/activate
# reproduzível (versões exatas + hashes):
python -m pip install --require-hashes --no-deps -r requirements-dev.lock
# alternativa (faixas abertas), se o lock não instalar na sua versão do Python:
python -m pip install -r requirements-dev.txt
python -m playwright install chromium      # só para os testes reais de JS (Chromium headless, sem Kommo)
```

O lock é gerado por `scripts/gerar_lock.ps1` (Windows) ou `scripts/gerar_lock.sh` (Linux) a partir de
`requirements.in` / `requirements-dev.in`. Para mudar uma dependência, edite o `.in` (e o `.txt`
correspondente) e regenere o lock.

No VS Code há tarefas prontas (*Terminal → Run Task*) para instalar, testar, gerar build e verificar privacidade.

## Comandos do dia a dia

| O quê | Comando |
|---|---|
| Testes | `python -m pytest -q -p no:cacheprovider` |
| Testes com cobertura (pytest-cov já vem no `requirements-dev.lock`) | `python -m pytest -q -p no:cacheprovider --cov` |
| Verificar privacidade (projeto inteiro) | `python -B scripts/verificar_privacidade.py` |
| … com termo extra (ex.: nome da empresa) | `python -B scripts/verificar_privacidade.py --termo minhaempresa` |
| Lint (ruff 0.17.0, a mesma versão do CI; não está no lock) | `ruff check .` (regras em `pyproject.toml`) |
| Build Windows | `powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1` |
| Build Linux (**não testado**) | `bash scripts/build_linux.sh` |
| Links da documentação | `python -B .github/scripts/verificar_links.py` |

`-B` / `-p no:cacheprovider` evitam criar `__pycache__` e `.pytest_cache` — os `.pyc` guardam o caminho
absoluto da sua máquina (e o seu nome de usuário).

Opcional: `pre-commit install` usa o `.pre-commit-config.yaml` (ruff + verificador de privacidade) antes de cada
commit. O `pre-commit` não faz parte das dependências do projeto; instale à parte se quiser.

## Convenções de código

- **Textos para o usuário em português** (interface, log, mensagens de erro, documentação).
- Siga os **nomes já existentes** (`Merger`, `Job`, `KommoPage`, `Estado`, `SELETORES`...). Não renomeie sem
  motivo.
- **Sem abstrações desnecessárias:** prefira a solução simples e local. Tudo que depende do HTML do Kommo fica
  em `kommo.py`; tudo do modo privacidade em `privacy.py`. A UI nunca fala com o navegador diretamente.
- Comente o **porquê** de decisões não óbvias (esperas, *fallbacks*, limites).
- O CI roda `ruff check` com regras conservadoras; não é exigido reformatar arquivos existentes.

## Regras de segurança e privacidade

- **Nunca versione** `data/`, `profile/`, `config.json`, logs (`*.log`), `debug/`, capturas de tela,
  diagnósticos, `dist/` ou artefatos (`.zip`, `.exe`, `.tar.gz`, `.AppImage`). O `.gitignore` já bloqueia, mas
  confira o `git status` antes do commit.
- **Nada de dados reais** em código, testes, fixtures, issues ou PRs: use `acme`, `<empresa>`, nomes fictícios.
  Fixtures HTML do Kommo devem ser montadas à mão ou anonimizadas por completo.
- Rode `python -B scripts/verificar_privacidade.py` antes de abrir o PR (e com `--termo` para o nome da sua
  empresa/conta).
- Prints e GIFs só com o **modo privacidade** ligado, conferidos inteiros.
- Testes automatizados **nunca** acessam o Kommo real; use os falsos de `tests/fakes.py`.
- Teste manual: comece por `python main.py --cli <empresa-de-teste> contatos 3 --ensaio` (não une nada); só
  depois `python main.py --cli <empresa-de-teste> contatos 3` — conta de teste, limite pequeno, confira o
  resultado na própria conta antes de qualquer número maior. No VS Code, as configurações de CLI com "ENSAIO" no
  nome não unem nada; a "⚠ CLI — UNIR 3 (REAL, irreversível)" une de verdade.

## Ajustar seletores do Kommo

Quando o Kommo muda a interface:

1. Confira no navegador (DevTools) o novo seletor e anote o comportamento.
2. Atualize **`src/kommo_duplicatas/kommo.py`** (classe `Seletores` / JS de estado) e, se a mudança afetar o que é
   borrado, **`src/kommo_duplicatas/privacy.py`** (lista `SELETORES`). Os seletores do processo (título,
   progresso, "Unir", menu) a privacidade já importa de `kommo.SELETORES` — não os copie.
3. Atualize **[`docs/KOMMO_DOM.md`](docs/KOMMO_DOM.md)** com o seletor e o comportamento observado.
4. Atualize/acrescente um **teste**: as fixtures HTML em `tests/fixtures/` (sem dados reais) alimentam
   `tests/test_kommo_js.py` e `tests/test_privacy_js.py`, que rodam o JS de verdade no Chromium headless.
5. Faça o teste manual com limite pequeno.

## Como escrever testes

- Lógica pura: teste direto (ver `tests/test_kommo.py`, `tests/test_limite.py`).
- Modo texto (`cli.py`): `tests/test_cli.py` troca o `Merger` por um falso; troca de aba (T10): ver
  `tests/test_t10_troca_de_aba.py` e os testes `test_t10_*` de `tests/test_merger.py`.
- Motor (`merger.py`): use **`FakeKommo`** (roteiro de `Estado`s), **`KommoSimulado`** e **`RelogioFalso`** de
  `tests/fakes.py` — simulam o Kommo e o tempo sem navegador e sem `sleep` real. A docstring de `fakes.py`
  mostra o uso.
- Dados do usuário: use `tmp_path` e `monkeypatch.setenv("KOMMO_DATA_DIR", ...)` — nunca toque a pasta real.
- Testes que dependem de algo opcional (display, Chromium) devem **pular** com motivo claro, não falhar.

## Processo de PR

1. Abra uma issue antes de mudanças grandes, para combinar a abordagem.
2. Crie um branch a partir do `main`, faça mudanças pequenas e focadas.
3. Atualize `CHANGELOG.md` se a mudança aparece para quem usa, e a documentação relacionada.
4. Preencha o modelo de PR (testes, privacidade, documentação).
5. O CI precisa passar (lint, testes Windows/Linux, segurança, links). Detalhes em
   [docs/operations/ci-cd.md](docs/operations/ci-cd.md).

## Mensagens de commit

Não exigimos um padrão rígido. Escreva mensagens **claras**, no imperativo, dizendo o que muda e, se não for
óbvio, por quê (ex.: "Espera o modal reaparecer antes de concluir que acabaram as duplicatas"). Um assunto por
commit sempre que possível.

## Licença

O repositório traz um [LICENSE](LICENSE) MIT, mas a licença ainda está **a confirmar** pelo dono do projeto. Ao
contribuir, você concorda que sua contribuição seja distribuída sob a licença que vier a ser confirmada para o
projeto.
