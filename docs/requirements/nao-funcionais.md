# Requisitos não funcionais

Requisitos de qualidade (NFR) do **Kommo — Unir Duplicatas**, cada um com métrica, método de verificação, status e
evidência. Os números foram **medidos nesta revisão** (13/10/2026, Windows 11 Pro 10.0.26200, Python 3.14.6) ou vêm de
observação manual registrada no repositório — a origem está sempre indicada. Onde não há linha de base, ela é
estabelecida aqui e a meta aparece como **"proposta a validar"**.

- Requisitos funcionais: [funcionais.md](funcionais.md)
- Metas operacionais (SLI/SLO): [../operations/slo.md](../operations/slo.md)
- Rastreabilidade: [../testing/rastreabilidade.md](../testing/rastreabilidade.md)
- Segurança: [../security/seguranca.md](../security/seguranca.md)

Status possíveis: *Implementado e testado* · *Implementado sem teste automatizado* · *Parcial* · *Pendente* ·
*Não aplicável*. Nenhum teste automatizado acessa o Kommo real.

## Medições de referência desta revisão

| Medida | Valor | Como foi medido |
|---|---|---|
| Testes coletados | **453** (18 arquivos) | `python -m pytest -q -p no:cacheprovider --co -q` |
| Resultado da suíte | **453 de 453 passaram**, 0 pulados, em **26,3 s** em 14/10/2026, revisão T11 (execuções anteriores: 419 testes em 41,4 s; 401 em 83,5 s; 394 em 147,4 s — a duração varia com a carga da máquina) — ver [estrategia.md](../testing/estrategia.md#3-contagem-real-de-testes) | `python -B -m pytest -q -p no:cacheprovider -rs` |
| Modo privacidade — elemento inserido dinamicamente marcado | **0,1–0,2 ms** (3 execuções) | `tests/test_privacy_js.py::test_b_elemento_dinamico_marcado_em_ms` com `-s` (linha `[medido]`) |
| Modo privacidade — observer sobre 5.000 linhas num lote | **137–253 ms** (3 execuções; 139,5 · 137,2 · 252,8 ms) | `tests/test_privacy_js.py::test_f_desempenho_5000_linhas` com `-s` |
| Idem, incluindo recálculo de estilo/layout (CSS com `:has`) | **472–958 ms** | mesmo teste (`+estilo/layout`) |
| 200 linhas, uma por tarefa, com ~10.000 já na página | observer **69–132 ms** no total (400 lotes) | mesmo teste |
| Varredura legada `JS_APLICAR` no mesmo DOM (comparação) | **102–201 ms** por varredura | mesmo teste |
| Tempo por união no Kommo real | **~2–7 s** (Contatos ~2–6 s; Leads ~5–7 s) | observação manual registrada em [KOMMO_DOM.md](../KOMMO_DOM.md) (anterior a esta revisão; não re-medido) |
| Espera da busca de duplicatas no Kommo real | **~10–45 s** | idem |
| Tamanho do executável | 51.657.666 bytes (~49,3 MiB) | `dist/KommoUnirDuplicatas.exe` de 08/10/2026 — formato antigo (arquivo único); o pacote atual (onedir zip) não foi gerado nesta revisão |

Uma medição anterior do observer citada pela equipe (~215 ms para 5.000 linhas) não está registrada no repositório;
ela cai dentro da faixa medida acima. A variação entre execuções (137 × 253 ms) mostra sensibilidade à carga da
máquina: o teste **não** tem asserção de tempo, só de correção (5.000 marcados, nenhum `title` restante).

---

## 1. Segurança

### NFR-001 — Nenhum clique de união fora da conta e da lista pedidas

- **Métrica:** nº de cliques em "Unir" com hostname ≠ `<empresa>.kommo.com`, caminho fora de `/leads`/`/contacts`
  do tipo, ou modal sem "duplicat" no título. **Meta: 0.**
- **Verificação:** testes com URL trocada (outra conta, domínio parecido `acme.kommo.com.evil.io`) e modal de outro
  tipo; comparação de hostname exata (nunca substring).
- **Status:** **Implementado e testado.**
- **Evidência:** `kommo.py:hostname_confere`; `merger.py:Merger._validar_pagina`, `_validar_modal`, `_aguardar_login`;
  `tests/test_merger.py::test_hostname_muda_antes_do_clique_aborta`, `test_login_hostname_por_substring_nao_vale`,
  `test_modal_que_nao_e_de_duplicatas_aborta`; `tests/test_kommo.py::test_hostname_confere`.

### NFR-002 — Navegador com isolamento padrão e sem prompts

- **Métrica:** o contexto é aberto com `chromium_sandbox=True`, `--disable-notifications`,
  `--deny-permission-prompts`; nenhuma opção que desligue a sandbox.
- **Verificação:** teste com stub de `launch_persistent_context` conferindo os argumentos.
- **Status:** **Implementado e testado** (argumentos). O efeito real de `--disable-notifications` sobre notificações
  *push* do service worker do Kommo **não foi verificado**.
- **Evidência:** `browser.py:ARGS_NAVEGADOR`, `abrir_contexto`;
  `tests/test_browser.py::test_abre_com_sandbox_args_e_perfil_por_canal`.

### NFR-003 — Perfil do navegador isolado por canal e nunca compartilhado entre navegadores

- **Métrica:** cada canal usa `data/profile/<canal>`; perfil em uso → para (não tenta outro canal com o mesmo login);
  nome de canal com `/`, `\`, `:` ou `..` é recusado.
- **Verificação:** testes de `browser.py` e `paths.py`.
- **Status:** **Implementado e testado.**
- **Evidência:** `paths.py:profile_dir`; `browser.py:perfil_em_uso`, `abrir_contexto`;
  `tests/test_paths.py::test_profile_dir_por_canal`; `tests/test_browser.py::test_perfil_em_uso_windows_nao_chama_launch`,
  `test_trava_por_texto_nao_tenta_outro_canal`, `test_navegador_ausente_tenta_proximo_com_outro_perfil`.

### NFR-004 — Nenhum segredo no código, no repositório ou nos pacotes

- **Métrica:** 0 senhas/tokens no código; o app não guarda credenciais (só cookies no perfil); `.gitignore` bloqueia
  `data/`, `profile/`, `config.json`, logs, `debug/`, `.env`; 0 achados do `detect-secrets` e do verificador de
  privacidade.
- **Verificação:** leitura do código (nenhuma credencial em `config.PADRAO`); `detect-secrets` e
  `verificar_privacidade.py` no CI; verificador no fim de cada build.
- **Status:** **Parcial** — controles implementados; o job de segurança do CI **nunca foi executado no GitHub**
  ([ci-cd.md](../operations/ci-cd.md#5-o-que-não-foi-validado)).
- **Evidência:** `config.py:PADRAO`; `.gitignore`; `.github/workflows/ci.yml` (job `seguranca`);
  `tests/test_verificador.py` (26 testes).

### NFR-005 — Cadeia de suprimentos verificável

- **Métrica:** dependências instaladas de `requirements*.lock` com `--require-hashes`; `pip-audit --strict` sem
  vulnerabilidades; SBOM CycloneDX e atestação de proveniência no release; Dependabot semanal.
- **Verificação:** scripts de build e `iniciar.bat` usam `--require-hashes`; jobs `seguranca`, `sbom`, `atestacao`.
- **Status:** **Parcial.** Locks com hashes e scripts: implementados. CI/release **não executados no GitHub**; actions
  fixadas por versão *major*, não por SHA (pendência registrada em [ci-cd.md](../operations/ci-cd.md)); atestação
  exige plano compatível (`continue-on-error`).
- **Evidência:** `requirements.lock`, `requirements-dev.lock` (cabeçalho pip-compile, Python 3.14); `scripts/gerar_lock.ps1`;
  `.github/workflows/release.yml`; `.github/dependabot.yml`.

---

## 2. Privacidade e LGPD

O app trata dados pessoais de clientes do usuário (nomes, telefones, e-mails exibidos pelo Kommo) **apenas na tela
do navegador**; não os extrai, copia ou envia. O controlador desses dados é a empresa dona da conta Kommo; o app é uma
ferramenta local operada por ela. Não há base legal nova a avaliar porque nada sai da máquina — mas os requisitos
abaixo reduzem a exposição local.

### NFR-006 — Minimização: nada sai da máquina

- **Métrica:** 0 conexões de rede iniciadas pelo app além do navegador abrindo `https://<empresa>.kommo.com/...`;
  0 telemetria.
- **Verificação:** inspeção do código (nenhum cliente HTTP; a única URL montada é `kommo.montar_url`).
- **Status:** **Implementado sem teste automatizado** (verificação por inspeção; não há teste de rede).
- **Evidência:** `kommo.py:montar_url`; `merger.py:Merger._abrir_url`; ausência de `urllib.request`/`requests`/
  `http.client` em `src/`.

### NFR-007 — Logs e diagnósticos sem dados de clientes

- **Métrica:** o diagnóstico nunca lê `innerText`/`textContent`/`value` para exibir; o log tem caracteres de controle
  neutralizados e linhas limitadas a 2.000 caracteres; retenção de 30 dias; com privacidade ligada a janela **e o
  modo texto** mascaram subdomínio e totais no log.
- **Verificação:** teste do diagnóstico sobre fixture com dados fictícios; testes de `logs.py` e das máscaras.
- **Status:** **Parcial.**
  - Implementado e testado: diagnóstico sem PII, sanitização, truncamento, retenção, máscara na UI e na CLI
    (T11, `mascara.py`).
  - Lacunas reais: (a) com a privacidade desligada (`--sem-privacidade` na CLI) o subdomínio e o total vão para o
    log; (b) mensagens de erro de configuração/pasta incluem **caminhos locais** (que contêm o nome de usuário do
    Windows); (c) `Erro inesperado: <tipo>: <mensagem>` grava até 300 caracteres da mensagem da exceção; (d) a
    captura com `KOMMO_DEBUG` ligado é uma imagem da tela (borrada só se FR-024 funcionar).
- **Evidência:** `kommo.py:_JS_DIAGNOSTICO`; `logs.py:sanitizar`, `formatar`, `limpar_antigos`;
  `mascara.py:mascarar_mensagem`; `cli.py:main`; `tests/test_kommo_js.py::test_diagnostico_sem_pii`;
  `tests/test_logs.py`; `tests/test_ui_integracao.py::test_logs_do_motor_sao_mascarados`;
  `tests/test_cli.py::test_privacidade_padrao_mascara_terminal_e_log`.

### NFR-008 — Modo privacidade em tela (gravação/apresentação)

- **Métrica:** 100 % dos elementos sensíveis da fixture `tests/fixtures/privacy_kommo_lista.html` borrados desde o
  início do documento; 0 elementos do processo borrados; título da aba = "Kommo"; notificações criadas pela página
  sem corpo/ícone.
- **Verificação:** JS real no Chromium headless (`tests/test_privacy_js.py`); conferência manual no Kommo real antes
  de gravar.
- **Status:** **Parcial** — testado na fixture; **não é garantia** no Kommo real (barra de endereço, *push* do
  service worker, iframes de outra origem, diálogos nativos, telas não mapeadas). Ver riscos residuais em
  [seguranca.md](../security/seguranca.md#5-riscos-residuais).
- **Evidência:** `privacy.py` (docstring "LIMITAÇÕES REAIS"); `tests/test_privacy_js.py` (11 testes);
  `tests/test_privacy.py` (13 testes).

### NFR-009 — Dados locais sob controle do usuário

- **Métrica:** todos os dados ficam numa única pasta conhecida (`data/` ou `KOMMO_DATA_DIR`); "Esquecer login"
  apaga o perfil sem tocar em nada fora de `data/profile`; logs expiram em 30 dias.
- **Verificação:** testes de `paths.py` e `logs.py`.
- **Status:** **Implementado e testado.** Não há função para apagar logs/config pela interface (o usuário apaga a
  pasta `data/`).
- **Evidência:** `paths.py:esquecer_login`, `dentro_da_raiz`; `tests/test_paths.py::test_esquecer_login*`;
  `tests/test_logs.py::test_limpar_antigos`.

---

## 3. Desempenho

### NFR-010 — Custo do modo privacidade no navegador

- **Linha de base (medida nesta revisão):** elemento dinâmico marcado em 0,1–0,2 ms; observer em lote de 5.000
  linhas 137–253 ms; com estilo/layout 472–958 ms; custo incremental com ~10.000 linhas ≈ 0,2–0,3 ms por lote
  pequeno (69–132 ms / 400 lotes). Complexidade: o observer examina só nós adicionados/alterados (não o documento
  inteiro), e a leitura de texto para em 60 caracteres.
- **Meta (proposta a validar):** elemento dinâmico marcado na mesma microtarefa (antes da pintura) e em ≤ 1 ms;
  observer ≤ 300 ms por lote de 5.000 linhas na máquina de referência; nenhum quadro intermediário sem borrão.
- **Verificação:** `tests/test_privacy_js.py::test_f_desempenho_5000_linhas` e `test_b_elemento_dinamico_marcado_em_ms`
  com `-s` (imprimem `[medido]`). **O teste não falha por tempo** — a meta é acompanhada manualmente.
- **Status:** **Implementado e testado** (correção); **meta de tempo sem asserção automatizada**.
- **Evidência:** `privacy.py:_JS_INIT_SCRIPT` (`aoMudar`, `textoCurto`); saída `[medido]` do teste.

### NFR-011 — Sobrecarga do app sobre o tempo de união

- **Linha de base:** a união em si é do Kommo (~2–7 s observados manualmente). O app amostra o estado a cada
  `POLL_UNIAO` = 0,2 s (detecção ≤ 0,2 s depois do estado estável) e só espera `ESTABILIZAR` = 1 s depois de uma
  união **não** confirmada; reforço de privacidade no máximo a cada 3 s.
- **Meta (proposta a validar):** sobrecarga do app ≤ 0,5 s por união confirmada; mediana de tempo por união ≤ 7 s
  (ver SLI-03 em [slo.md](../operations/slo.md#sli-03--tempo-por-união-confirmada)).
- **Verificação:** linhas `União i/L confirmada em X.Xs` do log; teste confirma que o reforço de privacidade é
  espaçado (bem menos chamadas que leituras de estado).
- **Status:** **Parcial** — parâmetros implementados e reforço espaçado testado; tempo real por união **não
  re-medido** com a versão atual.
- **Evidência:** `merger.py:POLL_UNIAO`, `ESTABILIZAR`, `INTERVALO_PRIVACIDADE`;
  `tests/test_merger.py::test_privacidade_reforco_espacado_e_desligada_sem_chamadas`.

### NFR-012 — Interface responsiva durante a execução

- **Métrica:** o navegador é dirigido numa thread separada; a UI consome a fila a cada 150 ms, no máximo 500 eventos
  por ciclo, sem chamadas bloqueantes na thread principal.
- **Verificação:** inspeção do código; testes de integração da UI com motor falso.
- **Status:** **Implementado sem teste automatizado de desempenho** (não há medição de latência da janela).
- **Evidência:** `ui.py:App.bombear`; `merger.py:Merger` (thread não-daemon).

### NFR-013 — Tempos-limite explícitos (nada espera para sempre)

- **Métrica:** login ≤ 600 s; confirmação ≤ 600 s; busca ≤ 90 s por ciclo (renovado após "Tentar novamente"/
  reabertura); união ≤ 120 s; `page.evaluate` ≤ 5 s (timer no JS); cliques ≤ 3 s; navegação ≤ 60 s (2 tentativas);
  fechar a janela: parada normal ≤ 150 s, forçada + 20 s.
- **Verificação:** testes com `RelogioFalso` (sem espera real) e JS com timeout.
- **Status:** **Implementado e testado.**
- **Evidência:** `merger.py:TEMPO_*`, `TIMEOUT_*`; `kommo.py:_js_com_timeout`; `ui.py:App.TETO_FECHAR`;
  `tests/test_merger.py::test_login_teto_da_erro_claro`, `test_confirmacao_sem_resposta_nao_clica`,
  `test_uniao_sem_resultado_conta_como_clique_e_registra_erro`; `tests/test_kommo_js.py::test_timeout_do_evaluate`;
  `tests/test_ui_integracao.py::test_fechar_forca_depois_do_teto`.

---

## 4. Compatibilidade e portabilidade

### NFR-014 — Sistemas operacionais

- **Métrica / situação:**

  | Plataforma | Situação |
  |---|---|
  | Windows 11 | **Testado**: suíte completa nesta revisão (Windows 11 Pro 10.0.26200). Uso real anterior registrado em [ESTRUTURA.md](../ESTRUTURA.md). |
  | Windows 10 | Declarado como suportado no README; **não testado nesta revisão**. |
  | Linux | **Não testado.** Ramos de código e scripts existem (`browser.canais_padrao`, `temas.FONTES`, `iniciar.sh`, `build_linux.sh`) mas nunca rodaram numa máquina Linux. A matriz do CI inclui `ubuntu-latest`, mas o CI nunca foi executado. |
  | macOS | Não suportado (só ramos de código, sem build/teste). |

- **Status:** **Parcial.**
- **Evidência:** `browser.py:_plataforma`, `canais_padrao`, `configurar_browsers_path`; `temas.py:FONTES`;
  `.github/workflows/ci.yml` (matriz).

### NFR-015 — Versões de Python e navegadores

- **Métrica:** Python ≥ 3.10 (`pyproject.toml`); navegador Chrome, Edge ou Chromium do Playwright; Playwright
  `>=1.40,<2` (`requirements.in`).
- **Verificação:** suíte executada só em **Python 3.14.6** nesta revisão. Matriz do CI (3.12, 3.13; 3.14
  experimental) **não executada**. A abertura de cada navegador é testada com stub, não com o navegador instalado;
  o Chromium headless do Playwright é usado de verdade nos testes de JS.
- **Status:** **Parcial** (3.10–3.13 não verificados nesta revisão; ruff configurado com `target-version = py310`).
- **Evidência:** `pyproject.toml`; `requirements.in`; `tests/test_browser.py`.

### NFR-016 — Modo portátil

- **Métrica:** o app funciona a partir de qualquer pasta gravável (inclusive com espaços e acentos), sem depender do
  diretório de trabalho nem de caminhos da máquina do autor; não escreve em `%APPDATA%`.
- **Verificação:** testes de `paths.py` com executável simulado (`sys.frozen`).
- **Status:** **Implementado e testado.**
- **Evidência:** `paths.py`; `tests/test_paths.py::test_portatil_frozen_com_espacos_e_acentos`, `test_independe_do_cwd`.

---

## 5. Manutenibilidade, testabilidade e reprodutibilidade

### NFR-017 — Manutenibilidade

- **Métrica:** (a) seletores do Kommo numa única fonte (`kommo.SELETORES`), passados como argumento ao JS — sem
  literais repetidos; (b) regras de decisão puras e tabeladas (`fluxo.py`, `limite.py`, funções de texto de
  `ui.py`); (c) UI sem acesso ao navegador; (d) `ruff check` com regras `E,F,W,B,UP` sem achados.
- **Verificação:** `tests/test_kommo.py::test_seletores_fonte_unica_e_aliases`; `ruff check .`.
- **Status:** **Implementado e testado.** (a)–(c) implementados; (a) testado também para `privacy.py`, que importa
  os seletores do processo de `kommo.SELETORES` (sem literais repetidos — T11); (d) `ruff check .` (ruff 0.17.0)
  sem achados na revisão T11. Módulos grandes: `ui.py` (~1.000 linhas) e `merger.py` (~870 linhas).
- **Evidência:** `kommo.py:Seletores`, `_com_padrao`; `privacy.py:SEL_KOMMO`/`SEL_TITULO_MODAL`;
  `tests/test_privacy.py::test_seletores_do_processo_vem_de_kommo_sem_ciclo`,
  `test_selectores_do_processo_sem_duplicacao`; `pyproject.toml` (`[tool.ruff]`).

### NFR-018 — Testabilidade

- **Métrica:** motor testável sem navegador e sem espera real (porta `PortaKommo`, `Relogio` injetável,
  `abrir_sessao` injetável); **453 testes** coletados; 0 pulados nesta máquina; cobertura de linhas/ramos.
- **Verificação:** coleta e execução da suíte.
- **Status:** **Parcial** — injeção de dependências e suíte implementadas; `pytest-cov` está no
  `requirements-dev.lock` e o CI mede a cobertura ([ci-cd.md](../operations/ci-cd.md#detalhes-dos-testes)), mas
  **nenhum número de cobertura foi medido nesta revisão** (CI nunca executado; pytest-cov não instalado no Python
  local) e não há meta mínima.
- **Evidência:** `kommo.py:PortaKommo`; `merger.py:Relogio`, `Merger.__init__(abrir_sessao=...)`; `tests/fakes.py`;
  contagem por arquivo em [estrategia.md](../testing/estrategia.md#3-contagem-real-de-testes).

### NFR-019 — Reprodutibilidade de instalação e build

- **Métrica:** instalação a partir de lock com versões exatas e hashes SHA-256; zip/tar.gz determinísticos (ordem
  alfabética, data fixa por `SOURCE_DATE_EPOCH`, permissões normalizadas); Python do build fixado (3.14, igual ao
  cabeçalho do lock).
- **Meta (proposta a validar):** dois builds do mesmo commit, mesmo `SOURCE_DATE_EPOCH` e mesmo runner geram o
  **mesmo SHA-256** do zip.
- **Status:** **Parcial** — mecanismos implementados; **reprodutibilidade byte a byte nunca medida**; o PyInstaller
  pode embutir variações próprias (não verificado).
- **Evidência:** `requirements*.lock`; `scripts/empacotar.py` (`EPOCA`, `criar_zip`, `criar_targz`);
  `.github/workflows/release.yml` (`PYTHON_BUILD`, `SOURCE_DATE_EPOCH`).

---

## 6. Usabilidade e acessibilidade

### NFR-020 — Operação por teclado e foco visível

- **Métrica (o que existe):** Tab alcança todos os controles; botões e caixas têm anel de foco (moldura na cor
  `FOCO`); as opções "Leads/Contatos" e as quantidades andam com ←/→ e selecionam com Espaço; Enter fora de botão
  inicia; foco inicial no campo vazio ou no INICIAR; diálogos: Esc/Enter cancelam, "Cancelar" tem o foco, "Unir
  agora" só por clique ou Espaço.
- **Verificação:** testes de integração do diálogo (Esc/Enter); inspeção do código para o resto.
- **Status:** **Parcial.** **Não auditado:** leitor de tela (rótulos `tk.Label` clicáveis não expõem papel de botão),
  contraste WCAG das cores, alta DPI/escala do Windows, tamanho de fonte ajustável, navegação por teclado completa
  sem mouse (só verificada em partes).
- **Evidência:** `ui.py:Escolha`, `com_anel`, `DialogoConfirmacao`, `App._tecla_enter`;
  `tests/test_ui_integracao.py::test_confirmacao_esc_e_enter_cancelam`, `test_confirmacao_exige_digitar_unir`.

### NFR-021 — Mensagens compreensíveis

- **Métrica:** todos os textos ao usuário em português; erros dizem o que aconteceu **e** o que fazer (pasta não
  gravável, perfil em uso, navegador ausente, login, quantidade inválida); nenhum *traceback* no log do motor.
- **Verificação:** testes conferem trechos de mensagens e a ausência de "Traceback" (`checar_seguranca`).
- **Status:** **Implementado e testado** (para as mensagens com teste). Sem teste de usabilidade com usuários.
- **Evidência:** `paths.py:DataDirNotWritable`; `browser.py:mensagem_perfil_em_uso`, `mensagem_sem_navegador`;
  `limite.py:parse_limite`; `tests/test_browser.py::test_mensagens_por_so`; `tests/test_limite.py`.

### NFR-022 — Janela adaptada à tela

- **Métrica:** a janela ocupa no máximo 90 % da tela, centralizada, nunca fora dela; fontes escolhidas por
  plataforma com fallback.
- **Status:** **Implementado e testado.**
- **Evidência:** `temas.py:calcular_geometria`, `escolher_fontes`; `tests/test_ui_pura.py::test_geometria_cabe_na_tela`,
  `test_geometria_tela_grande_mantem_tamanho_original`, `test_escolher_fontes`.

### NFR-023 — Facilidade de instalação

- **Métrica:** usuário final: descompactar o zip e abrir o `.exe`, sem instalador e sem administrador; pré-requisito:
  Chrome ou Edge. Código-fonte: um clique em `iniciar.bat` (cria `.venv` e instala do lock).
- **Verificação:** manual (checklist em [estrategia.md](../testing/estrategia.md#4-testes-manuais-antes-de-cada-release)).
- **Status:** **Implementado sem teste automatizado.** Atritos conhecidos: SmartScreen "editor desconhecido" e
  possível falso positivo de antivírus (sem Authenticode); o Chromium do Playwright **não** vai no pacote (sem
  Chrome/Edge o executável não tem navegador); pasta em local protegido exige mover a pasta (FR-003).
- **Evidência:** `scripts/build_windows.ps1`; `iniciar.bat`; [SECURITY.md](../../SECURITY.md) (recomendações).

---

## 7. Observabilidade, recuperação, integridade e confiabilidade

### NFR-024 — Observabilidade local

- **Métrica:** cada linha com data/hora e nível; motivo de término explícito (14 códigos); diagnóstico estrutural
  automático em falhas; textos de progresso do Kommo registrados uma vez; captura opcional com `KOMMO_DEBUG`.
- **Status:** **Implementado e testado.** Sem telemetria (de propósito; ver [slo.md](../operations/slo.md#5-sem-telemetria-de-propósito)).
- **Evidência:** `logs.py`; `merger.py:MOTIVOS`, `_diagnostico`, `_aguardar_uniao`; `tests/test_logs.py`;
  `tests/test_merger.py::test_screenshot_so_com_debug`.

### NFR-025 — Recuperação automática de falhas transitórias

- **Métrica:** "Algo deu errado" → até 5 "Tentar novamente" + 1 reabertura por ciclo; página recarregada → reabre
  pelo menu; navegação lenta → 2 tentativas; leitura durante navegação → estado "navegou" em vez de exceção;
  `config.json` corrompido → isolado e padrão restaurado; perfil travado → mensagem com solução.
- **Status:** **Implementado e testado.**
- **Evidência:** `merger.py:_esperar_busca`, `_abrir_url`; `kommo.py:KommoPage.estado`; `config.py:_isolar_corrompido`;
  `tests/test_merger.py::test_algo_deu_errado_tenta_reabre_uma_vez_e_falha`, `test_erro_some_e_volta_ao_normal`,
  `test_pagina_recarrega_durante_a_uniao_reabre_pelo_menu`, `test_sessao_playwright_init_script_canal_e_fecha`;
  `tests/test_config.py::test_arquivo_corrompido_volta_ao_padrao`. Procedimentos manuais:
  [recuperacao-falhas.md](../operations/recuperacao-falhas.md).

### NFR-026 — Integridade das uniões (operação irreversível)

- **Métrica, em todos os cenários simulados:** cliques ≤ limite; clique só com o botão "Unir" visível; nunca
  fechar/cancelar o modal durante uma união; `cliques = confirmadas + não confirmadas`; união sem confirmação nunca
  conta como feita; nenhuma conclusão "sem duplicatas" com erro pendente ou sessão caída.
- **Verificação:** invariante `checar_seguranca` aplicada aos cenários de `tests/test_merger.py`.
- **Status:** **Implementado e testado** (simulador). Contra o Kommo real: depende da fidelidade do simulador ao
  comportamento observado ([KOMMO_DOM.md](../KOMMO_DOM.md)).
- **Evidência:** `merger.py:_laco`, `_fechar_modal_seguro`, `_busca_sem_grupo`; `fluxo.py:avaliar_uniao`;
  `tests/test_merger.py::checar_seguranca`.

### NFR-027 — Integridade dos arquivos locais

- **Métrica:** `config.json` nunca fica pela metade (temporário + `fsync` + `os.replace`, 5 tentativas); nenhum
  temporário sobra; zip/tar.gz gravados como `.parcial` e renomeados.
- **Status:** **Implementado e testado** (config); empacotamento sem teste.
- **Evidência:** `config.py:_gravar_atomico`; `scripts/empacotar.py:criar_zip`;
  `tests/test_config.py::test_escrita_atomica_nao_estraga_o_arquivo`, `test_salvar_nao_deixa_temporarios`.

### NFR-028 — Confiabilidade do ciclo de vida

- **Métrica:** `FimEvt` exatamente uma vez, como último evento, inclusive com exceções; contexto do navegador sempre
  fechado; thread do motor **não-daemon** (o processo não morre no meio de uma união); a UI nunca fica com INICIAR
  travado (reabilita ao receber `FimEvt` e também se a thread morrer sem ele); a janela nunca é destruída com a
  thread viva.
- **Status:** **Implementado e testado** (a rede de segurança "thread morreu sem FimEvt" não tem teste dedicado).
- **Evidência:** `merger.py:Merger.run`, `_emitir_fim`; `ui.py:App.bombear`, `App.fechar`;
  `tests/test_merger.py::test_thread_nao_daemon_e_parar_e_aguardar`, `test_falha_ao_abrir_o_navegador_ainda_emite_fim`,
  `test_excecao_no_meio_da_uniao_preserva_contadores_e_fecha`; `tests/test_ui_integracao.py::test_fechar_thread_travada_avisa_e_nao_destroi`.

---

## 8. Resumo de status

| Status | NFR |
|---|---|
| Implementado e testado | NFR-001, 002, 003, 009, 010 (correção), 013, 016, 021, 022, 024, 025, 026, 027, 028 |
| Implementado sem teste automatizado | NFR-006, 012, 023 |
| Parcial | NFR-004, 005, 007, 008, 011, 014, 015, 017, 018, 019, 020 |
| Pendente | — (itens pendentes aparecem como lacunas dentro dos "Parcial": cobertura, CI no GitHub, Linux, auditoria de acessibilidade, reprodutibilidade medida) |
