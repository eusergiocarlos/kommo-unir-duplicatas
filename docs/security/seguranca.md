# Segurança: modelo de ameaças, controles e riscos residuais

Visão de segurança do **Kommo — Unir Duplicatas** conferida no código e nos testes atuais. Para **relatar uma
vulnerabilidade**, siga o [SECURITY.md](../../SECURITY.md) (aviso privado do GitHub; nunca issue pública).

Relacionados: [requisitos não funcionais](../requirements/nao-funcionais.md) ·
[requisitos funcionais](../requirements/funcionais.md) · [estratégia de testes](../testing/estrategia.md) ·
[CI/CD](../operations/ci-cd.md) · [SLO e telemetria](../operations/slo.md).

## 1. Contexto

O app é um programa de desktop que **dirige um navegador logado no CRM Kommo** do usuário e clica em "Unir esta
duplicata" — uma ação **irreversível**. Não tem servidor, API própria nem telemetria; a única comunicação de rede é
o navegador falando com `https://<empresa>.kommo.com` (e o que o próprio Kommo carregar). Os dados ficam na pasta
`data/` ao lado do programa (ou em `KOMMO_DATA_DIR`).

## 2. Modelo de ameaças (resumo)

### 2.1 Ativos

| Ativo | Onde está | Por que importa |
|---|---|---|
| **Sessão do Kommo** (cookies) | `data/profile/<canal>/` (perfil persistente do Chrome/Edge/Chromium) | Quem tiver o perfil entra na conta do CRM com os privilégios do usuário |
| **Dados de clientes** | Tela do navegador; potencialmente em capturas de depuração, logs e diagnósticos | Nomes, telefones, e-mails, valores — dados pessoais (LGPD) |
| **Integridade das uniões** | Conta Kommo | União errada não tem volta |
| **Identificação da empresa** | `config.json` (subdomínio), logs, título da aba, barra de endereço | Revela de quem é a conta numa gravação/apresentação |
| **Cadeia de suprimentos** | Dependências (`requirements*.lock`), pacotes publicados, workflows | Pacote adulterado roda com o poder do usuário logado |
| **Dados da máquina de build** | Caminhos com nome de usuário, hostname, `git user` | Vazariam em `.pyc`/executáveis publicados |

### 2.2 Agentes e cenários

| # | Cenário | Agente |
|---|---|---|
| T1 | O app clica em "Unir" na conta/lista errada, ou mais vezes do que o pedido | Defeito do app, mudança do Kommo, aba trocada pelo usuário |
| T2 | Página maliciosa ou domínio parecido (`acme.kommo.com.evil.io`) é tratado como a conta | Atacante na web / engano do usuário |
| T3 | Cópia ou leitura da pasta `data/` (cookies) | Outra pessoa com acesso ao computador, sincronização em nuvem, pasta compartilhada |
| T4 | Dados de clientes aparecem em gravação de tela, logs, diagnósticos ou capturas | Uso normal do app (gravar/apresentar), compartilhamento de logs em issue |
| T5 | Pacote adulterado ou dependência maliciosa | Terceiro redistribuindo o app; comprometimento de pacote no PyPI |
| T6 | Dados da máquina de build ou da empresa vão para o repositório/pacotes | Descuido do mantenedor |
| T7 | Corrupção de arquivos locais (config pela metade, exclusão fora da pasta) | Queda de energia, antivírus, link simbólico na pasta de dados |

Fora do escopo (ver [SECURITY.md](../../SECURITY.md#escopo)): vulnerabilidades do Kommo, do Chrome/Edge/Chromium e do
Playwright; atacante que já tem administrador ou código rodando na máquina do usuário.

## 3. Controles implementados

| ID | Controle | Ameaças | Evidência no código | Testes |
|---|---|---|---|---|
| C1 | **Hostname exato** `<empresa>.kommo.com` (nunca substring) para considerar logado e antes de cada clique | T1, T2 | `kommo.py:hostname_confere`; `merger.py:Merger._aguardar_login`, `_validar_pagina`, `_checar_sessao` | `test_kommo.py::test_hostname_confere`; `test_merger.py::test_login_hostname_por_substring_nao_vale`, `test_hostname_muda_antes_do_clique_aborta` |
| C2 | Subdomínio validado como rótulo DNS; recusa `usuario@...`, outros domínios, subníveis | T2 | `kommo.py:RE_EMPRESA`, `normalizar_empresa` | `test_kommo.py::test_normalizar_empresa` |
| C3 | Caminho coerente com o tipo e título do modal com "duplicat" antes de cada clique; item de menu estrito por tipo (sem fallback por texto) | T1 | `merger.py:caminho_confere`, `modal_de_duplicatas`, `_validar_modal`; `kommo.py:_JS_CLICAR_ITEM` | `test_merger.py::test_modal_que_nao_e_de_duplicatas_aborta`, `test_tipo_errado_aborta_sem_abrir_nem_clicar`; `test_kommo_js.py::test_nao_clica_item_de_outra_entidade` |
| C4 | **Confirmação da conta** antes do 1º clique (conta logada, tipo, total, quantidade; "Cancelar" padrão; digitar `UNIR` para "Todas" ou > 500; sem resposta em 10 min = nada unido) | T1 | `merger.py:Merger._confirmar`; `ui.py:DialogoConfirmacao`; `cli.py:perguntar_confirmacao` | `test_merger.py::test_confirmacao_*`; `test_ui_integracao.py::test_confirmacao_*`; `test_cli.py::test_pergunta_e_recusa` |
| C5 | Limite conta **cliques** (antes de clicar); união sem confirmação nunca conta como feita; parada só entre uniões; nunca cancelar o modal no meio | T1 | `merger.py:Merger._laco`, `_fechar_modal_seguro`; `fluxo.py:avaliar_uniao` | invariante `test_merger.py::checar_seguranca`; `test_fluxo.py::test_avaliar_uniao` |
| C6 | Modo ensaio (abre e confere sem unir) | T1 | `merger.py:Job.ensaio`, `_executar` | `test_merger.py::test_ensaio_nao_clica_em_unir` |
| C7 | **Sandbox do Chromium ligado** (`chromium_sandbox=True`), `--disable-notifications`, `--deny-permission-prompts` | T2, T4 | `browser.py:ARGS_NAVEGADOR`, `abrir_contexto` | `test_browser.py::test_abre_com_sandbox_args_e_perfil_por_canal` |
| C8 | **Perfil por canal** (`data/profile/<canal>`); perfil em uso → para em vez de tentar outro navegador; nome de canal sanitizado | T3, T7 | `paths.py:profile_dir`; `browser.py:perfil_em_uso`, `abrir_contexto` | `test_paths.py::test_profile_dir_por_canal`; `test_browser.py::test_perfil_em_uso_windows_nao_chama_launch`, `test_trava_por_texto_nao_tenta_outro_canal` |
| C9 | Nenhuma senha/token guardado; login só no perfil do navegador; "Esquecer login" apaga o perfil, recusa links/junções e nada fora de `data/profile` | T3, T7 | `config.py:PADRAO`; `paths.py:esquecer_login`, `dentro_da_raiz`, `_eh_link` | `test_paths.py::test_esquecer_login*`, `test_dentro_da_raiz` |
| C10 | **Diagnóstico sem PII**: só contagens, visibilidade, classes e booleanos; nunca texto/valor | T4 | `kommo.py:_JS_DIAGNOSTICO` | `test_kommo_js.py::test_diagnostico_sem_pii` |
| C11 | Captura de tela só com `KOMMO_DEBUG` verdadeiro (`1`/`true`/`yes`/`on`; `0`/`false` não ligam), depois de reforçar a privacidade | T4 | `merger.py:Merger._diagnostico`, `debug_ligado` | `test_merger.py::test_screenshot_so_com_debug`, `test_kommo_debug_*` |
| C12 | **Sanitização de logs**: caracteres de controle → espaço (sem quebra/injeção de linha ou sequência de terminal); linhas ≤ 2.000 caracteres; retenção 30 dias | T4, T7 | `logs.py:sanitizar`, `formatar`, `limpar_antigos` | `test_logs.py::test_sanitiza_caracteres_de_controle`, `test_trunca_linhas_longas`, `test_limpar_antigos` |
| C13 | Modo privacidade: init script (CSS por seletor, `MutationObserver` com regex, título "Kommo", retirada de `title`, notificações anonimizadas); máscara de subdomínio/total na janela e no log da UI | T4 | `privacy.py:init_script`; `ui.py:mascarar_mensagem`, `DialogoConfirmacao` | `test_privacy_js.py` (11); `test_privacy.py` (13); `test_ui_integracao.py::test_logs_do_motor_sao_mascarados` |
| C14 | **Escrita atômica** de `config.json` (temporário + `fsync` + `os.replace`); JSON corrompido isolado | T7 | `config.py:_gravar_atomico`, `_isolar_corrompido` | `test_config.py::test_escrita_atomica_nao_estraga_o_arquivo`, `test_arquivo_corrompido_volta_ao_padrao` |
| C15 | Pasta de dados não gravável vira erro explícito (não cai em silêncio para outro lugar) | T3, T7 | `paths.py:ensure_writable`, `DataDirNotWritable` | `test_paths.py::test_nao_gravavel_*` |
| C16 | **Verificador de privacidade fail-closed** no fim de cada build e no CI (termos da máquina + extras, binários/zip/PyInstaller/AppImage; ilegível = erro; termos mascarados na saída) | T6 | `scripts/verificar_privacidade.py`; `scripts/build_windows.ps1`, `scripts/build_linux.sh` | `test_verificador.py` (26) |
| C17 | **Locks com hash** (`--require-hashes`) em `iniciar.bat`, builds e CI | T5 | `requirements.lock`, `requirements-dev.lock`; `scripts/gerar_lock.ps1` | — (CI) |
| C18 | CI com permissões mínimas (`contents: read`), `persist-credentials: false`, `pip-audit --strict`, `detect-secrets`, dependency review; release como **rascunho** com aprovação manual, SBOM CycloneDX e atestação de proveniência | T5, T6 | `.github/workflows/ci.yml`, `release.yml`; `.github/dependabot.yml` | — (**nunca executado no GitHub**) |
| C19 | `SHA256SUMS.txt` publicado; empacotamento determinístico | T5 | `scripts/empacotar.py` | — |
| C20 | `.gitignore` bloqueia `data/`, perfis, `config.json`, logs, `debug/`, capturas, artefatos, `.env` | T6 | `.gitignore` | verificador acusa dados de usuário no projeto (`test_verificador.py::test_dados_usuario_e_artefato_fora_de_dist`) |
| C21 | Timeouts explícitos e `FimEvt` sempre emitido; contexto do navegador sempre fechado; thread não-daemon | T1, T7 | `merger.py:Merger.run`, `TEMPO_*`; `kommo.py:_js_com_timeout` | `test_merger.py::test_thread_nao_daemon_e_parar_e_aguardar`, `test_falha_ao_abrir_o_navegador_ainda_emite_fim` |

## 4. Mapeamento para OWASP Top 10 (2021), ASVS e CWE

Achados das auditorias já tratados no código, com a categoria de referência. O app não é uma aplicação web; o
mapeamento usa as categorias mais próximas.

| Achado tratado | Controle | OWASP Top 10 | ASVS 4.0 (capítulo) | CWE |
|---|---|---|---|---|
| Validação de hostname por substring aceitaria `xacme.kommo.com` / `acme.kommo.com.evil.io` | C1, C2 | A01 Broken Access Control / A04 Insecure Design | V5 Validation | CWE-20, CWE-697 |
| Clique em item de menu por texto podia acertar outra entidade | C3 | A04 Insecure Design | V1 Architecture | CWE-670 |
| Ação irreversível sem confirmação explícita da conta | C4, C6 | A04 Insecure Design | V1, V11 Business Logic | CWE-841 |
| União não confirmada contada como feita; limite ultrapassável | C5 | A04 Insecure Design | V11 Business Logic | CWE-754, CWE-799 |
| Sandbox do navegador desligada | C7 | A05 Security Misconfiguration | V14 Configuration | CWE-250, CWE-693 |
| Mesmo perfil aberto por navegadores diferentes / perfil em uso | C8 | A05 Security Misconfiguration | V14 | CWE-668 |
| Diagnóstico gravava texto do modal (dados de clientes) | C10, C11 | A09 Security Logging and Monitoring Failures | V7 Error Handling and Logging | CWE-532, CWE-359 |
| Mensagens com quebras/sequências de controle no log | C12 | A09 / A03 Injection | V7 | CWE-117, CWE-150 |
| Dados de clientes visíveis em gravação de tela | C13 | A04 Insecure Design | V8 Data Protection | CWE-200, CWE-359 |
| Config podia ficar pela metade | C14 | A08 Software and Data Integrity Failures | V8 | CWE-362, CWE-460 |
| "Esquecer login" poderia seguir link/junção para fora da pasta | C9 | A01 Broken Access Control | V12 Files and Resources | CWE-59 |
| Verificador "avisava e seguia" em arquivo ilegível; `.pyc` com caminho do autor publicado | C16 | A08 / A05 | V14 Build | CWE-200, CWE-636 (fail-open) |
| Dependências sem versão exata/hash | C17 | A06 Vulnerable and Outdated Components / A08 | V14 Dependency | CWE-1104, CWE-494 |
| Workflows com permissões amplas / publicação automática | C18 | A08 | V14 | CWE-269 |
| Queda silenciosa para `%APPDATA%` quando a pasta não é gravável | C15 | A05 | V14 | CWE-276 |

## 5. Riscos residuais

Riscos **aceitos ou ainda não tratados**, com honestidade sobre o que não foi verificado.

| # | Risco | Impacto | Situação / mitigação parcial |
|---|---|---|---|
| R1 | **Perfil com cookies em `data/` legível por quem acessa a pasta.** O perfil não é cifrado pelo app; qualquer pessoa ou programa com acesso de leitura à pasta (outra conta de administrador, backup, sincronização OneDrive/Dropbox, pendrive) pode copiar a sessão. | Alto | Documentado ("não compartilhe, não sincronize"). "Esquecer login" apaga. Recomenda-se pasta dentro do perfil do usuário do Windows. |
| R2 | **Cifragem dos cookies pelo Chrome (DPAPI / App-Bound Encryption) não confirmada** para perfis abertos via Playwright com `user_data_dir` próprio. Pode estar em vigor (dependente da versão do navegador) ou não. | Médio | **Não verificado.** Tratar o perfil como sensível independentemente (R1). |
| R3 | **Modo privacidade não é garantia.** Barra de endereço mostra `<empresa>.kommo.com`; notificações *push* do service worker não passam pelo init script (há `--disable-notifications`, mas o efeito sobre *push* não foi verificado); iframes de outra origem, PDFs, `alert/confirm` nativos e telas não mapeadas podem mostrar dados; o título pode aparecer por milissegundos antes da troca; seletores `:has()` dependem do navegador. Testado só em fixture. | Médio | Documentado em `privacy.py`; checklist manual 4.5 de [estrategia.md](../testing/estrategia.md#4-testes-manuais-antes-de-cada-release). |
| R4 | **`add_init_script` roda em todas as origens** abertas no contexto (inclusive páginas de login OAuth e de terceiros), não só em `*.kommo.com`. O script só lê/borra o DOM e troca título/notificações; não envia nada. | Baixo | Aceito: necessário para cobrir a tela de login. Efeito colateral possível: título "Kommo" e borrões em sites de terceiros abertos no mesmo navegador. |
| R5 | **Navegação externa não é bloqueada** (`bloquear_navegacao_externa` existe mas está desligado), porque o Kommo usa OAuth, integrações e ajuda fora de `kommo.com`. | Baixo | A aba principal é sempre validada por hostname exato antes de cada clique (C1). |
| R6 | **Sem assinatura Authenticode**: SmartScreen "editor desconhecido" e **falso positivo de antivírus** comum em executáveis PyInstaller; usuário pode ser treinado a ignorar avisos. | Médio | `SHA256SUMS.txt`, SBOM e atestação (quando o CI rodar); orientação no [SECURITY.md](../../SECURITY.md). Assinatura depende de decisão/custo do dono. |
| R7 | **Kommo muda o HTML** sem aviso: seletores deixam de casar, o modal pode mudar de título, textos de progresso mudam. | Médio | Validações antes de cada clique param a execução sem unir (C3); uniões sem confirmação viram "não confirmadas". Texto de conclusão em Leads **não confirmado** no Kommo real. |
| R8 | **Logs podem conter identificação**: com a privacidade desligada (janela, ou `--sem-privacidade` na CLI), subdomínio e total vão para o log (com ela ligada, janela e CLI mascaram desde a T11); mensagens de erro incluem caminhos locais (com o nome de usuário do Windows); `Erro inesperado` grava até 300 caracteres da mensagem da exceção. | Baixo/Médio | Retenção de 30 dias; orientação para não publicar logs ([slo.md](../operations/slo.md#6-como-calcular-os-slis-a-partir-de-datalogs)). |
| R9 | **Troca de aba (correção T10):** o motor passa a acompanhar outra aba aberta do mesmo contexto quando a sua fecha — inclusive uma aba **fora** de `*.kommo.com` se for a única. Uma aba adotada errada não leva a clique porque hostname/caminho/modal são validados antes de cada união (C1, C3). | Baixo | Implementado e testado (FR-034); não exercitado no login real do Kommo. |
| R10 | **Cadeia de suprimentos não exercitada**: CI/release nunca executados no GitHub; actions fixadas por versão *major*, não por SHA; Dependabot pode não regenerar hashes; build Linux não validado. | Médio | Pendências em [ci-cd.md](../operations/ci-cd.md#6-pendências-que-dependem-do-dono). |
| R11 | **Quem executa código na máquina** enquanto o app roda controla o navegador logado (mesmo poder do usuário). | Alto | Fora do escopo; recomendação de não usar conta de administrador. |

## 6. Checklist de segurança de release

Antes de publicar um Release (além do checklist funcional em
[estrategia.md](../testing/estrategia.md#4-testes-manuais-antes-de-cada-release)):

- [ ] Suíte completa passando (`python -m pytest -q -p no:cacheprovider -rs`), sem testes pulados no CI.
- [ ] `python -B scripts/verificar_privacidade.py --termo <empresa>` limpo no projeto; o build terminou com o
      verificador aprovado sobre `dist/`.
- [ ] Nenhum `data/`, `profile/`, `config.json`, `*.log`, `debug/`, captura ou artefato no repositório
      (`git status` limpo desses arquivos).
- [ ] `pip-audit --strict` limpo nos dois locks; locks regenerados com `scripts/gerar_lock.*` se houve mudança de
      dependência (diff revisado).
- [ ] `detect-secrets` sem achados.
- [ ] Versão igual em `src/kommo_duplicatas/__init__.py`, `pyproject.toml` e na tag; seção no `CHANGELOG.md`.
- [ ] `chromium_sandbox=True` e `ARGS_NAVEGADOR` inalterados (ou mudança justificada).
- [ ] Mudanças em `kommo.py`/`merger.py`/`fluxo.py` passaram pela invariante `checar_seguranca` e pelo teste manual
      com limite 3 numa conta de teste.
- [ ] Diagnóstico continua sem texto de clientes (`test_diagnostico_sem_pii` passando).
- [ ] Release criado como **rascunho**; `SHA256SUMS.txt` conferido baixando os anexos; SBOM anexado; atestação
      gerada (ou ausência explicada).
- [ ] Notas do Release avisam sobre SmartScreen/antivírus e sobre não compartilhar a pasta `data/`.

## 7. Como reportar

Siga o [SECURITY.md](../../SECURITY.md#como-relatar-uma-vulnerabilidade): aviso privado do GitHub (Private
Vulnerability Reporting), sem dados reais de clientes (mascare subdomínio, nomes, telefones e e-mails). Prazos-alvo
lá descritos são metas, não SLA.
