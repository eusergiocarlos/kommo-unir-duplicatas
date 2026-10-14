# Estratégia de testes

Como o **Kommo — Unir Duplicatas** é testado hoje, o que fica de fora e o que precisa ser conferido à mão antes de
cada release. A regra de ouro vem da natureza do app: **a união de duplicatas é irreversível**, então nenhum teste
automatizado fala com o Kommo real e todo teste manual usa conta de teste e limite pequeno.

Relacionados: [rastreabilidade](rastreabilidade.md) · [requisitos funcionais](../requirements/funcionais.md) ·
[não funcionais](../requirements/nao-funcionais.md) · [CI/CD](../operations/ci-cd.md) ·
[CONTRIBUTING.md](../../CONTRIBUTING.md#como-escrever-testes).

## 1. Pirâmide real do projeto

```
                 ┌───────────────────────────────┐
                 │  Manual no Kommo real          │  checklist da seção 4 (conta de teste, limite 3)
                 └───────────────────────────────┘
            ┌─────────────────────────────────────────┐
            │ UI Tk real + Merger falso (33)           │  tests/test_ui_integracao.py
            │ CLI + Merger falso (8)                    │  tests/test_cli.py
            └─────────────────────────────────────────┘
       ┌──────────────────────────────────────────────────┐
       │ JS real no Chromium headless + fixtures HTML (26) │  tests/test_kommo_js.py, tests/test_privacy_js.py
       └──────────────────────────────────────────────────┘
   ┌────────────────────────────────────────────────────────────┐
   │ Motor com KommoSimulado/FakeKommo + RelogioFalso (56+1+2)   │  tests/test_merger.py, test_fluxo::test_sequencia_com_fake
   │ Adaptadores com stubs do Playwright (44)                    │  tests/test_kommo_porta.py, tests/test_browser.py
   └────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────────────┐
│ Lógica pura e utilidades (≈ 250)                                      │  test_kommo, test_fluxo, test_limite,
│ + verificador de privacidade com artefatos montados em tmp_path (26)  │  test_ui_pura, test_privacy, test_logs,
│                                                                      │  test_config, test_paths, test_main,
│                                                                      │  test_verificador
└──────────────────────────────────────────────────────────────────────┘
```

### 1.1 Camadas

| Camada | O que prova | Como isola o mundo real |
|---|---|---|
| **Lógica pura** | normalização do subdomínio, hostname exato, URLs, `parse_total`, tabela `avaliar_uniao`, `parse_limite`, máscaras e textos da UI, CSS/regex da privacidade, logs, config, caminhos, ponto de entrada | Funções sem I/O; arquivos em `tmp_path` com `KOMMO_DATA_DIR`; `paths._verificadas` zerado por fixture |
| **Adaptadores** | `KommoPage` converte erros de navegação em valores seguros, passa seletores/timeout; `browser.abrir_contexto` escolhe canal, perfil e argumentos | `page` falso (`tests/test_kommo_porta.py`) e `StubChromium` (`tests/test_browser.py`) — nenhum navegador abre |
| **Motor** | fluxo completo de `Merger._executar`: login, validações, confirmação, laço, parada, erros, sessão, fechamento | `KommoSimulado` (máquina de estados com tempo: busca, união, conclusão, recarga, erro, expiração) e `FakeKommo` (roteiro de `Estado`s) de `tests/fakes.py`; `RelogioFalso` avança o tempo sem `sleep` e estoura se passar de 200.000 s simulados (detecta laço infinito) |
| **JS real** | os scripts que rodam na página (`_JS_ESTADO`, menu, item do tipo, diagnóstico sem PII, timeout do `evaluate`; init script de privacidade: borrão, observer, título, notificações, desempenho) | Chromium headless do Playwright; páginas de `tests/fixtures/*.html` (dados fictícios) via `page.set_content` ou `ctx.route("https://kommo.test/**")` — sem internet, sem perfil do usuário |
| **UI** | diálogo de confirmação, PARAR em dois níveis, fechamento seguro, resumo, ensaio, esquecer login, máscaras no log, erro em callback, inicialização com pasta não gravável | Tk real; `ui.Merger` trocado por `MergerFalso` (thread que só anota chamadas); `messagebox` substituído; dados em pasta temporária |
| **CLI** | argumentos, pergunta `[s/N]`, `--sim`, Ctrl+C em dois níveis, códigos de saída | `MergerFalso` com roteiro de eventos; entrada/saída injetadas |
| **Scripts** | `verificar_privacidade.py`: termos, mascaramento, zip/tar aninhados, executável PyInstaller (CArchive + PYZ), fail-closed | Só termos **falsos** e artefatos montados em `tmp_path`; sempre `--sem-termos-padrao` (nunca o usuário/host reais) |

### 1.2 Invariantes de segurança do motor

`tests/test_merger.py::checar_seguranca` é aplicada à maioria dos cenários do motor e falha se qualquer uma for
violada:

1. `FimEvt` emitido exatamente uma vez e como último evento;
2. o contexto do navegador sempre é fechado;
3. clique em "Unir" só com o botão visível (fase `grupo` do simulador);
4. nunca fechar/cancelar o modal durante `unindo`/`concluido`;
5. `cliques == confirmadas + incertas` e `feitos == confirmadas`;
6. `cliques <= limite` quando há limite;
7. nenhum `Traceback` no log.

## 2. Como rodar

| O quê | Comando |
|---|---|
| Suíte completa | `python -m pytest -q -p no:cacheprovider` |
| Como no CI (lista pulados e o motivo) | `python -m pytest -q -p no:cacheprovider -rs` |
| Só coletar (contagem) | `python -m pytest -q -p no:cacheprovider --co -q` |
| Um arquivo / um teste | `python -m pytest -q -p no:cacheprovider tests/test_merger.py -k parar` |
| Medições de desempenho do modo privacidade | `python -m pytest -q -p no:cacheprovider -s tests/test_privacy_js.py -k "desempenho or dinamico"` (linhas `[medido]`) |
| Testes de JS (precisam do Chromium do Playwright) | `python -m playwright install chromium` uma vez |
| Linux sem display (Tk) | `xvfb-run -a python -m pytest -q -p no:cacheprovider` |
| Verificador de privacidade do projeto | `python -B scripts/verificar_privacidade.py` (`--termo <empresa>` para termos extras) |
| Links da documentação | `python -B .github/scripts/verificar_links.py` |

`-p no:cacheprovider` e `python -B` evitam `.pytest_cache`/`__pycache__` (que guardam caminhos absolutos com o nome
do usuário — o verificador de privacidade acusaria). Testes que dependem de display ou do Chromium **pulam com
motivo** quando o recurso não existe; no CI o Chromium é instalado justamente para que não pulem.

## 3. Contagem real de testes

Coleta feita nesta revisão (14/10/2026) com `python -m pytest -q -p no:cacheprovider --co -q`. Casos
parametrizados contam um a um.

| Arquivo | Testes | Camada |
|---|---:|---|
| `tests/test_browser.py` | 19 | adaptador (stub do Playwright) |
| `tests/test_cli.py` | 16 | CLI + Merger falso (inclui máscara de privacidade e código 64) |
| `tests/test_config.py` | 21 | pura / arquivos temporários (inclui tipos errados no `config.json`) |
| `tests/test_fluxo.py` | 28 | pura (+1 sequência com `FakeKommo`) |
| `tests/test_kommo.py` | 32 | pura |
| `tests/test_kommo_js.py` | 15 | JS real (Chromium headless) |
| `tests/test_kommo_porta.py` | 25 | adaptador (page falso) |
| `tests/test_limite.py` | 47 | pura |
| `tests/test_logs.py` | 8 | pura / arquivos temporários |
| `tests/test_main.py` | 7 | ponto de entrada (módulos falsos) |
| `tests/test_merger.py` | 72 | motor (simulador + relógio falso; inclui `KOMMO_DEBUG`) |
| `tests/test_paths.py` | 16 | arquivos temporários |
| `tests/test_privacy.py` | 14 | pura (+1 subprocesso: import sem ciclo) |
| `tests/test_privacy_js.py` | 11 | JS real (Chromium headless) |
| `tests/test_t10_troca_de_aba.py` | 2 | motor + Chromium headless real (troca de aba, HTML local) |
| `tests/test_ui_integracao.py` | 33 | UI Tk + Merger falso |
| `tests/test_ui_pura.py` | 61 | pura (1 teste abre Tk) |
| `tests/test_verificador.py` | 26 | script (artefatos em `tmp_path`) |
| **Total** | **453** | |

Resultado da execução completa nesta revisão (T11): **453 passaram, 0 pulados, em 26,3 s** (Windows 11, Python 3.14.6;
ver [nao-funcionais.md](../requirements/nao-funcionais.md#medições-de-referência-desta-revisão)). Os testes mais
lentos são os de JS real (subir/derrubar o Chromium headless) e os de UI (criar janelas Tk); a duração total variou
entre 26 s e 2,5 minutos entre execuções (carga da máquina).

## 4. Testes manuais antes de cada release

Obrigatórios porque o Kommo real, o navegador instalado e o empacotamento não são cobertos por teste automatizado.
Use **uma conta de teste** (nunca a de produção) e **limite 3**. Registre data, versão, Windows, navegador e o
resultado de cada item.

### 4.1 Pacote e instalação

- [ ] Build Windows (`scripts/build_windows.ps1`) termina com o verificador de privacidade aprovado e o
      `SHA256SUMS.txt` confere (`Get-FileHash` ou `sha256sum -c`).
- [ ] O zip descompactado numa pasta **sem** Python instalado abre o `.exe`; registrar o aviso do SmartScreen e
      qualquer bloqueio do antivírus.
- [ ] Pasta do programa em local **sem permissão de escrita** (ex.: `C:\Program Files\...`): aparece o erro de
      pasta não gravável com as duas soluções, e a janela principal não abre.
- [ ] `KOMMO_DATA_DIR` apontando para outra pasta: os dados vão para lá.

### 4.2 Login e conta

- [ ] Primeira execução (sem perfil): o navegador abre, o log pede login, o login é feito na janela do navegador e
      o app continua sozinho.
- [ ] Login que **abre ou troca de aba** (ex.: entrar com Google): o log mostra "o app passou a acompanhar a outra
      aba aberta" e a execução continua (correção T10, FR-034); fechar **todas** as abas encerra com "navegador
      fechado".
- [ ] Segunda execução: entra direto (perfil lembrado); o rodapé mostra o navegador usado.
- [ ] Diálogo de confirmação mostra a conta certa (com privacidade: mascarada até "Mostrar conta"); "Cancelar"
      encerra sem unir.
- [ ] "Esquecer login salvo" apaga o login (próxima execução pede login de novo); com o navegador do app aberto,
      mostra erro claro.

### 4.3 Ensaio e uniões reais

- [ ] **Ensaio** em **Contatos** e em **Leads**: confirmação marcada como ensaio, resumo "nada foi unido", nenhum
      grupo a menos na conta.
- [ ] **3 uniões em Contatos**: contador chega a 3 confirmadas; o total de grupos no Kommo diminuiu 3; tempos no log
      (`União i/3 confirmada em X s`).
- [ ] **3 uniões em Leads**: anotar quantas ficaram **confirmadas** × **não confirmadas** e conferir no Kommo se as
      3 foram feitas.
- [ ] **Texto de progresso**: copiar do log as linhas `Kommo (progresso): “…”` de Leads e de Contatos e conferir
      se o texto de conclusão contém "conclu" (calibra FR-013; se Leads não mostrar, registrar em
      [KOMMO_DOM.md](../KOMMO_DOM.md)).
- [ ] "Todas" ou mais de 500: o botão "Unir agora" só habilita depois de digitar `UNIR` (cancelar em seguida).

### 4.4 Parada e fechamento

- [ ] PARAR no meio de uma união: a união termina, o app para e o resumo mostra o motivo "interrompido pelo
      usuário".
- [ ] PARAR duas vezes (FORÇAR PARADA): o navegador fecha na hora e o resumo mostra 1 não confirmada.
- [ ] Fechar a janela durante uma união: pergunta "Parar e fechar?"; com "Sim", a janela fecha sozinha depois da
      união em andamento.
- [ ] Fechar o navegador do app durante a espera do login e durante uma união: mensagem amigável, resumo com o
      motivo "navegador fechado".

### 4.5 Privacidade ao vivo

- [ ] Com o modo privacidade ligado, gravar a tela da lista de Leads, da lista de Contatos, do modal de duplicatas
      durante 3 uniões e da tela de login: nomes, telefones, e-mails, valores, totais, avatar/usuário e chat
      aparecem borrados; o título da aba é "Kommo"; os textos do processo (título do modal, progresso, botões)
      estão legíveis.
- [ ] Anotar o que **não** foi borrado (barra de endereço é esperada) e abrir issue sem dados reais com o seletor
      que faltou.
- [ ] Na janela do app: subdomínio mascarado no campo "Empresa" (fora de edição), no log e no resumo; total
      aparece como `••••`.
- [ ] Desligar a privacidade: nada borrado no navegador.

### 4.6 Modo texto

- [ ] `python main.py --cli <empresa-de-teste> contatos 3 --ensaio` pergunta `[s/N, m = mostrar a conta]` com a conta mascarada (`m` revela só no terminal); Enter vazio = não (código 2).
- [ ] `python main.py --cli <empresa-de-teste> contatos 3` com "s": resumo impresso, código 0; Ctrl+C uma vez para
      após a união em andamento.
- [ ] Com privacidade (padrão), terminal e `data/logs/*.log` mostram `a***e.kommo.com` e `••••` (nunca o
      subdomínio real nem o total); `python main.py --cli acme leads abc` sai com código 64.

### 4.7 Linux (enquanto não validado)

- [ ] Seguir [packaging/linux/README.md](../../packaging/linux/README.md) numa distro real. Até isso acontecer, o
      build Linux **não** deve ser anunciado como suportado.

## 5. O que NÃO é coberto

| Lacuna | Por quê / risco | Mitigação atual |
|---|---|---|
| **Kommo real** | Irreversível; nenhuma conta de teste automatizável; o HTML do Kommo muda sem aviso | Simulador fiel ao comportamento observado ([KOMMO_DOM.md](../KOMMO_DOM.md)); validações antes de cada clique; checklist manual 4.3 |
| Texto de conclusão em **Leads** | Não confirmado no Kommo real | Regra segura (vira "não confirmada"); teste pessimista `test_leads_sem_texto_concluida_tudo_incerto_e_limite_por_cliques` |
| **Abertura real de Chrome/Edge** com perfil persistente | Os testes usam stub de `launch_persistent_context` | Manual 4.2 |
| **Linux** e **Windows 10** | Nenhuma execução nesta revisão; CI nunca rodou | Matriz do CI pronta (Windows + Ubuntu); manual 4.7 |
| **Alta DPI** / escala do Windows, múltiplos monitores | Não testado | `calcular_geometria` limita a 90 % da tela |
| **Antivírus / SmartScreen** | Depende de fornecedor; executável sem assinatura | Manual 4.1; orientação no [SECURITY.md](../../SECURITY.md) |
| Leitor de tela e contraste | Não auditado | — |
| Scripts de build (`build_windows.ps1`, `build_linux.sh`, `empacotar.py`), `iniciar.bat`/`iniciar.sh` e workflows | Sem teste automatizado; workflows nunca executados no GitHub | Manual 4.1; verificador de privacidade testado |
| Notificações *push* do service worker, barra de endereço, iframes de outra origem | Fora do alcance do init script | Documentado como risco residual ([seguranca.md](../security/seguranca.md#5-riscos-residuais)) |
| Rede instável real (quedas no meio da união) | Simulado só como "navegou"/erro | Teto de 120 s por união, `FALHAS_MAX` |
| Cobertura de código | `pytest-cov` está no `requirements-dev.lock` e o CI mede/publica `coverage.xml`; não há meta mínima e a cobertura não foi medida nesta máquina (pytest-cov não instalado no Python local) | [ci-cd.md](../operations/ci-cd.md#detalhes-dos-testes) |

## 6. Cenários de falha cobertos automaticamente

| Falha | Teste(s) |
|---|---|
| Busca com "Algo deu errado" persistente / que some / seguida de carregamento infinito | `test_merger.py::test_algo_deu_errado_tenta_reabre_uma_vez_e_falha`, `test_erro_some_e_volta_ao_normal`, `test_houve_erro_persiste_durante_o_carregamento` |
| Página recarrega durante a união | `test_merger.py::test_pagina_recarrega_durante_a_uniao_reabre_pelo_menu` |
| União sem resultado em 120 s; clique que falha; 3 falhas seguidas | `test_merger.py::test_uniao_sem_resultado_conta_como_clique_e_registra_erro`, `test_clique_que_falha_conta_e_tres_falhas_param` |
| Kommo sem texto de conclusão (Leads pessimista) | `test_merger.py::test_leads_sem_texto_concluida_tudo_incerto_e_limite_por_cliques`, `test_incerto_reconfere_estado_antes_de_reclicar` |
| Sessão expirada no meio | `test_merger.py::test_sessao_expirada_nao_vira_concluido` |
| Hostname/página/modal errados antes do clique | `test_merger.py::test_hostname_muda_antes_do_clique_aborta`, `test_modal_que_nao_e_de_duplicatas_aborta`, `test_tipo_errado_aborta_sem_abrir_nem_clicar` |
| Login que não acontece / por substring / navegador fechado no login | `test_merger.py::test_login_teto_da_erro_claro`, `test_login_hostname_por_substring_nao_vale`, `test_navegador_fechado_durante_o_login_mensagem_amigavel` |
| Navegador fechado no meio da união; exceção inesperada; navegador indisponível | `test_merger.py::test_navegador_fechado_no_meio_da_uniao`, `test_excecao_no_meio_da_uniao_preserva_contadores_e_fecha`, `test_excecao_do_roteiro_do_fakekommo`, `test_falha_ao_abrir_o_navegador_ainda_emite_fim` |
| Aba fechada/substituída com outra aberta; aba nova dentro da tolerância; todas fechadas; aba adotada de outra conta (T10) | `test_merger.py::test_t10_*`, `test_sessao_playwright_aba_substituida_no_goto_adota_e_segue`; `test_kommo_porta.py::test_adota_a_aba_mais_recente_do_kommo_e_reaplica_config`, `test_todas_fechadas_ou_contexto_quebrado_nao_adota`; `test_t10_troca_de_aba.py` (Chromium real) |
| Navegação lenta / fechada ao abrir; config quebrada durante a sessão | `test_merger.py::test_sessao_playwright_init_script_canal_e_fecha`, `test_sessao_playwright_fecha_mesmo_com_excecao_e_navegador_fechado`, `test_sessao_playwright_config_quebrada_nao_derruba` |
| Confirmação recusada, sem resposta, parada durante ela | `test_merger.py::test_confirmacao_recusada_nao_clica`, `test_confirmacao_sem_resposta_nao_clica`, `test_parar_durante_a_confirmacao` |
| Erros de navegação/timeout do Playwright nas leituras e cliques | `test_kommo_porta.py::test_estado_navegacao_vira_navegou`, `test_estado_timeout_do_playwright_vira_navegou`, `test_acoes_com_navegacao_devolvem_valor_seguro`; `test_kommo_js.py::test_timeout_do_evaluate` |
| Perfil em uso, navegador ausente, `KOMMO_BROWSER` inválido, erro que não é do Playwright | `test_browser.py::test_perfil_em_uso_windows_nao_chama_launch`, `test_trava_por_texto_nao_tenta_outro_canal`, `test_nenhum_navegador`, `test_kommo_browser_invalido`, `test_erro_que_nao_e_do_playwright_nao_e_engolido` |
| Pasta de dados não gravável | `test_paths.py::test_nao_gravavel_*`; `test_config.py::test_pasta_nao_gravavel_nao_e_engolida`; `test_logs.py::test_falha_de_pasta_nao_derruba`; `test_ui_integracao.py::test_main_data_dir_nao_gravavel_mostra_erro_e_nao_abre` |
| `config.json` corrompido / bytes inválidos; escrita interrompida | `test_config.py::test_arquivo_corrompido_volta_ao_padrao`, `test_bytes_invalidos_em_utf8`, `test_escrita_atomica_nao_estraga_o_arquivo` |
| Esquecer login com navegador aberto / pasta que é link | `test_paths.py::test_esquecer_login_com_navegador_aberto`, `test_esquecer_login_recusa_link` |
| Thread travada ao fechar a janela; exceção em callback do Tk | `test_ui_integracao.py::test_fechar_thread_travada_avisa_e_nao_destroi`, `test_excecao_em_callback_nao_derruba_a_janela` |
| Artefato corrompido, truncado, ilegível ou de formato desconhecido no verificador | `test_verificador.py::test_zip_corrompido_falha`, `test_exe_pyinstaller_truncado_falha`, `test_membro_zip_com_crc_errado_falha`, `test_arquivo_ilegivel_falha`, `test_formato_nao_suportado_falha` |

## 7. Política de regressão

1. **Todo defeito corrigido ganha um teste** que falha antes da correção e passa depois, na camada mais baixa que
   reproduz o problema (pura → simulador → JS em fixture → UI). Os nomes dos testes existentes já seguem essa
   prática (ex.: `test_houve_erro_persiste_durante_o_carregamento`, do caso "parou em 49 de 100 em Leads" registrado
   em [ESTRUTURA.md](../ESTRUTURA.md)).
2. **Mudança de comportamento do Kommo**: atualizar [KOMMO_DOM.md](../KOMMO_DOM.md), a fixture HTML (sem dados
   reais), o `KommoSimulado` se o fluxo mudou, e o teste.
3. **Mudança no motor** (`merger.py`, `fluxo.py`): o cenário novo precisa passar pela invariante
   `checar_seguranca`.
4. **Nada de dados reais** em testes e fixtures: `acme`, nomes fictícios, termos falsos no verificador.
5. Teste que depende de recurso opcional (display, Chromium) **pula com motivo**, não falha; no CI esses recursos
   são instalados.
6. A suíte inteira precisa passar antes de qualquer PR ser aceito (exigência do CI, ver
   [ci-cd.md](../operations/ci-cd.md)), e o checklist da seção 4 antes de publicar um Release.
