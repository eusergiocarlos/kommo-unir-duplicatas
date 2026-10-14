# CI/CD — integração contínua e releases

Este documento explica os workflows do GitHub Actions, como configurar o repositório no GitHub, como fazer uma
release e **o que ainda não foi validado**. Arquivos envolvidos:

| Arquivo | Para quê |
|---|---|
| [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml) | lint, testes (Windows + Linux), segurança, links da documentação |
| [`.github/workflows/release.yml`](../../.github/workflows/release.yml) | testes → builds → SBOM → atestação → Release **rascunho** |
| [`.github/dependabot.yml`](../../.github/dependabot.yml) | PRs semanais de atualização (pip e Actions) |
| [`.github/scripts/verificar_links.py`](../../.github/scripts/verificar_links.py) | links relativos e âncoras em Markdown |
| [`.github/scripts/notas_release.py`](../../.github/scripts/notas_release.py) | notas do Release a partir do `CHANGELOG.md` |
| [`.github/ISSUE_TEMPLATE/`](../../.github/ISSUE_TEMPLATE/), [`pull_request_template.md`](../../.github/pull_request_template.md) | modelos com avisos de privacidade |
| [`.github/CODEOWNERS`](../../.github/CODEOWNERS) | **comentado** até haver dono definido |
| [`.pre-commit-config.yaml`](../../.pre-commit-config.yaml) | opcional: ruff + verificador de privacidade antes do commit |
| [`pyproject.toml`](../../pyproject.toml) | regras do ruff e configuração de cobertura |

## 1. `ci.yml`

**Gatilhos:** push no `main`, qualquer pull request, execução manual (`workflow_dispatch`) e chamada pelo
`release.yml` (`workflow_call`). **Permissões:** só `contents: read`. **Concorrência:** um novo push no mesmo
ref cancela a execução anterior (grupo `ci-<evento>-<ref>`, com prefixo fixo para não colidir com o release).

| Job | O que faz | Bloqueia? |
|---|---|---|
| `lint (ruff)` | `ruff check` com as regras de `pyproject.toml` (ruff 0.17.0 fixo) | sim |
| | `ruff format --check` | **não** (informativo) |
| `testes (<so>, py<versão>)` | matriz `windows-latest` + `ubuntu-latest` × Python 3.12, 3.13 e 3.14 | sim (todas as versões) |
| `segurança` | `pip-audit` nos dois locks, `detect-secrets`, `verificar_privacidade.py` | sim |
| `revisão de dependências (PR)` | `actions/dependency-review-action` (falha em severidade ≥ moderada) | sim, só em PR |
| `docs (links relativos)` | `.github/scripts/verificar_links.py` | sim |

### Detalhes dos testes

- **Instalação:** o `requirements-dev.lock` foi resolvido para uma versão do Python (cabeçalho do arquivo; hoje
  3.14). Se a versão do job é a mesma, instala o lock com `--require-hashes` em modo **estrito**. Nas outras
  versões tenta o lock e, se não instalar, cai para `requirements-dev.txt` (faixas abertas) com aviso no log.
  Assim a matriz não quebra por um lock de outra versão, e a versão de referência continua reprodutível.
- `python -m playwright install chromium` (no Linux com `--with-deps`) para os testes que rodam o JS de verdade
  (`tests/test_privacy_js.py`, `tests/test_kommo_js.py`); sem isso eles seriam pulados.
- No Linux os testes rodam com `xvfb-run -a` (o teste da janela Tk precisa de display).
- Comando: `python -m pytest -q -p no:cacheprovider -rs` (`-rs` lista os testes pulados e o motivo).
- **Cobertura:** o `pytest-cov` está em `requirements-dev.in`/`.txt`/`.lock` (lock: `pytest-cov==7.1.0`); o job
  adiciona `--cov` quando ele está instalado e publica `coverage.xml` como artefato. Configuração em
  `[tool.coverage.*]` do `pyproject.toml`.
- **Python 3.14** é obrigatório (sem `continue-on-error`): é a versão do lock (`requirements*.lock`, instalado em
  modo estrito com `--require-hashes` nesse job) e a do build de release. 3.12 e 3.13 continuam na matriz para quem
  roda pelo código-fonte (instalam o lock ou, se não der, `requirements-dev.txt`).

### Lint (ruff)

Regras: `E`, `F`, `W`, `B`, `UP`, com `target-version = py310`, `line-length = 120` e as exceções justificadas em
`pyproject.toml`:

- `E501` (linha longa) ignorada — strings de log/JS passam um pouco de 120 em poucos lugares;
- `UP031` ignorada — `%s` usado de propósito nos modelos de JS (`privacy.py`);
- `B905` ignorada só em `tests/`;
- **`I` (isort) não está ativo:** o estilo de imports do projeto (parênteses alinhados) seria reescrito em ~8
  arquivos. Reavaliar se o projeto adotar `ruff format` (hoje reformataria ~30 arquivos — por isso o
  `format --check` é só informativo).

### Segurança

- **pip-audit** (`--strict --disable-pip`): audita as versões exatas de `requirements.lock` e
  `requirements-dev.lock` contra a base de vulnerabilidades do PyPI, sem instalar nada.
- **Segredos — detect-secrets** (PyPI, versão fixa). **Por que não `gitleaks/gitleaks-action`:** a action exige
  uma licença (`GITLEAKS_LICENSE`) quando o repositório pertence a uma *organização*, e ainda não sabemos se
  este repositório ficará numa conta pessoal ou numa organização; baixar o binário do gitleaks exigiria fixar e
  conferir um checksum que não pudemos verificar offline. O detect-secrets não precisa de token nem licença e
  não imprime o valor do segredo (só tipo, arquivo e linha). **Limitação:** varre só a árvore atual, não o
  histórico do git. Se o repositório for de conta pessoal, a gitleaks-action (que varre o histórico) é uma boa
  adição.
- **Verificador de privacidade** (`python -B scripts/verificar_privacidade.py --sem-termos-padrao --termo <aleatório>`):
  - `--sem-termos-padrao`: no runner, usuário/host/home são do GitHub (ex.: `runner`) — não identificam ninguém e
    dariam falso positivo;
  - termo-sentinela **aleatório** (nunca existe nos arquivos) só para as checagens estruturais rodarem sempre
    (pastas `data/`/`profile/`, logs, artefatos fora de `dist/`, arquivos ilegíveis), já que o verificador é
    fail-closed sem nenhum termo;
  - termos reais (ex.: o nome da empresa) vêm de `KOMMO_TERMOS_SENSIVEIS` — ver seção 3.
- **Dependency review** em PRs: precisa do *Dependency graph* ativo; em repositório **privado** exige GitHub
  Advanced Security (sem isso o job falha — remova-o ou ative o recurso).

### Docs

`verificar_links.py` confere links relativos (arquivo existe) e âncoras (`#titulo`, slug no estilo do GitHub)
em todos os `.md`, ignorando blocos de código e links externos. Mermaid não é validado.

## 2. `release.yml`

**Gatilhos:** push de tag `v*.*.*` e execução manual. **Permissões padrão:** nenhuma; cada job declara as suas.
**Nada é publicado automaticamente.**

| Job | O que faz |
|---|---|
| `versão e notas` | confere tag = `__version__` (`src/kommo_duplicatas/__init__.py`) = `pyproject.toml`; extrai a seção da versão do `CHANGELOG.md` (falha se não houver) e acrescenta os avisos fixos |
| `CI` | reaproveita **todo** o `ci.yml` (lint, testes, segurança, docs) |
| `build Windows` | `windows-latest`, Python 3.14 (= lock): `scripts/build_windows.ps1` → `dist/windows/*.zip` + `SHA256SUMS.txt` + verificador de privacidade (fail-closed); confere os hashes |
| `build Linux` | `ubuntu-22.04`: `scripts/build_linux.sh` → `.tar.gz` — **experimental**, `continue-on-error: true` |
| `SBOM` | `cyclonedx-py requirements` sobre `requirements.lock` → `KommoUnirDuplicatas-<versão>.cdx.json` |
| `atestação` | `actions/attest-build-provenance` sobre zip/tar.gz/SBOM; **único** job com `id-token: write` e `attestations: write`; `continue-on-error` |
| `Release (rascunho)` | `environment: release` (aprovação manual) → `gh release create --draft --verify-tag` com zip, tar.gz/AppImage (se houver), SBOM e um `SHA256SUMS.txt` único |

Observações:

- Execução manual a partir de **branch** = **ensaio**: gera os artefatos (baixáveis na página do workflow) e não
  cria Release. A partir de uma **tag**, segue o fluxo completo.
- `SOURCE_DATE_EPOCH` = data do commit → zip/tar.gz reproduzíveis (`scripts/empacotar.py`).
- Só usa o `GITHUB_TOKEN` (e o secret opcional `KOMMO_TERMOS_SENSIVEIS`). Nenhum segredo no código.
- No build **dentro do CI** (`CI=true`, definido pelo GitHub Actions), `scripts/build_windows.ps1` e
  `scripts/build_linux.sh` chamam o verificador com `--sem-termos-padrao` + um **termo-sentinela aleatório** + os
  termos de `KOMMO_TERMOS_SENSIVEIS`: o usuário/hostname do runner (`runner`, `runneradmin`) não identificam
  ninguém e não viram termo (evita o falso positivo com textos como `asyncio.runners`). Fora do CI, o build usa
  os termos padrão da máquina (usuário, hostname, git), como sempre.
- **Sem assinatura Authenticode:** não há certificado de assinatura de código. As notas avisam sobre SmartScreen
  e falso positivo de antivírus. Assinar exigiria comprar um certificado e guardar a chave como secret — decisão
  do dono.
- **AppImage:** o workflow não baixa o `appimagetool` (não dá para fixar/verificar o checksum aqui); o script
  então gera só o `.tar.gz`.
- **Atestação** em repositório privado exige GitHub Enterprise Cloud; em repositório público funciona em qualquer
  plano. Verificação: `gh attestation verify <arquivo> --repo <dono>/<repositório>`.
- Se o Release (rascunho) da tag já existir, o job falha; apague o rascunho antigo antes de rodar de novo.

## 3. Configurar o GitHub (passo a passo, feito pelo dono)

1. **Repositório**: crie e faça o primeiro push (fora do escopo deste documento). Confirme a licença (o `LICENSE`
   MIT está **a confirmar**).
2. **Private Vulnerability Reporting**: *Settings → Code security → Private vulnerability reporting → Enable*.
   O `SECURITY.md` aponta para ele. Em `.github/ISSUE_TEMPLATE/config.yml`, descomente o `contact_links` e troque
   `<dono>/<repositório>` (o GitHub exige URL absoluta ali; não foi preenchida para não inventar o endereço).
3. **Environment `release`**: *Settings → Environments → New environment* → nome `release` → marque
   **Required reviewers** e adicione quem aprova releases; em *Deployment branches and tags*, restrinja a
   tags `v*.*.*`. Sem revisores configurados, o job de rascunho roda sem pausa (continua sendo só rascunho).
4. **Proteção do `main`** (*Settings → Branches* ou *Rules → Rulesets*): exigir PR, exigir os checks
   `lint (ruff)`, `testes (...)` das versões 3.12/3.13, `segurança (...)`, `docs (links relativos)` e, em PRs,
   `revisão de dependências (PR)`; bloquear force-push. Opcional: *Require review from Code Owners* depois de
   preencher o `CODEOWNERS`.
5. **`KOMMO_TERMOS_SENSIVEIS`** (termos extras, separados por vírgula — ex.: nome da empresa, subdomínio):
   - **recomendado: como *secret*** (*Settings → Secrets and variables → Actions → Secrets*): o valor aparece
     mascarado (`***`) nos logs;
   - também é aceito como *variável* de repositório (aba *Variables*), mas **o valor aparece em claro no log**
     (no bloco `env:` do passo) — num repositório público isso expõe exatamente o termo que se quer proteger.
     Use variável só se o repositório for privado.
   - Secrets não chegam a PRs de forks nem do Dependabot: nesses casos o passo roda só as checagens
     estruturais e avisa no log.
6. **Dependabot**: *Settings → Code security* → ative *Dependency graph*, *Dependabot alerts* e *Dependabot
   security updates*. O `dependabot.yml` já agenda PRs semanais.
7. **Actions**: *Settings → Actions → General* → *Workflow permissions* = **Read repository contents** (o
   padrão mínimo; os workflows pedem o resto explicitamente).
8. **Fixar Actions por SHA (antes da 1ª release pública):** hoje as actions estão fixadas por versão major
   (`actions/checkout@v4`, `actions/setup-python@v5`, `actions/upload-artifact@v4`,
   `actions/download-artifact@v4`, `actions/dependency-review-action@v4`,
   `actions/attest-build-provenance@v2`). O recomendado é trocar por `uses: dono/action@<SHA completo> # vX.Y.Z`;
   o Dependabot (ecossistema `github-actions`) mantém os SHAs atualizados. Os SHAs **não** foram preenchidos
   aqui porque não puderam ser conferidos offline.

## 4. Como fazer uma release

1. Atualize a versão em `src/kommo_duplicatas/__init__.py` **e** `pyproject.toml` (devem ser iguais).
2. Acrescente a seção no `CHANGELOG.md`: `## X.Y.Z` (aceita também `## [X.Y.Z] - AAAA-MM-DD`).
3. Rode localmente: testes, `python -B scripts/verificar_privacidade.py --termo <sua-empresa>` e, se possível, o
   build Windows.
4. Abra PR, espere o CI passar, faça o merge no `main`.
5. (Opcional) Ensaio: *Actions → Release → Run workflow* a partir do `main` → baixe e teste os artefatos.
6. Crie e envie a tag: `git tag vX.Y.Z && git push origin vX.Y.Z`.
7. Acompanhe o workflow *Release*; aprove o environment `release` quando pedir.
8. Na página de **Releases**, abra o **rascunho**: confira notas, anexos e `SHA256SUMS.txt`; baixe o zip num
   Windows limpo e teste (sem iniciar união contra conta real, ou com limite pequeno numa conta de teste).
9. Só então clique em **Publish release**.

## 5. O que NÃO foi validado

- **Nenhum workflow foi executado no GitHub.** Foram validados localmente apenas: sintaxe YAML, existência dos
  caminhos referenciados, `ruff check`, `pip-audit` nos locks, `detect-secrets`, geração do SBOM, o verificador
  de links e o gerador de notas.
- **Build Linux no CI:** `scripts/build_linux.sh` nunca rodou num Linux real; o job continua
  `continue-on-error` até essa validação. O antigo **falso positivo** previsto (usuário `runner` do CI como termo
  sensível, casando com módulos do Python embutidos como `asyncio.runners`) **já foi resolvido**: com `CI=true`
  os scripts de build usam `--sem-termos-padrao` + termo-sentinela aleatório + `KOMMO_TERMOS_SENSIVEIS` (ver
  seção 2). Resolvido no código, mas ainda não exercitado num runner real.
- **Build Windows no CI:** mesma regra (`CI=true` → sem termos do sistema do runner); também não exercitado num
  runner real.
- Python do `setup-python` com Tk no `ubuntu-22.04` e o comportamento do `playwright install --with-deps` em
  `ubuntu-latest` — não verificados.
- Disponibilidade de Python 3.14 nas imagens dos runners (o `setup-python` costuma ter; agora é obrigatório —
  se a imagem não tiver, o job falha e precisa de ajuste).
- Comportamento do Dependabot com os locks com hashes do pip-compile (pode não regenerar os hashes; regenere
  com `scripts/gerar_lock.*` em todo PR de pip).
- `dependency-review-action` e atestação dependem do plano/visibilidade do repositório (ver acima).

## 6. Pendências que dependem do dono

- Confirmar a licença; definir o dono para o `CODEOWNERS`.
- Fazer a configuração da seção 3 (Private Vulnerability Reporting, environment `release`, proteção do `main`,
  secret `KOMMO_TERMOS_SENSIVEIS`, Dependabot, permissões de Actions).
- Validar o build Linux numa distro real e, depois, remover o `continue-on-error` do job.
- Decidir sobre assinatura de código (Authenticode).
- Definir (se quiser) uma meta mínima de cobertura (`--cov-fail-under`); hoje a cobertura só é medida e publicada.
- Fixar as actions por SHA antes da primeira release pública.
