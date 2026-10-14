# Requisitos funcionais

Catálogo dos requisitos funcionais (FR) do **Kommo — Unir Duplicatas** na versão do código-fonte atual
(`__version__ = "1.0.0"`). Cada requisito foi conferido no código e nos testes do repositório; nada aqui descreve
comportamento planejado como se já existisse.

- Requisitos não funcionais: [nao-funcionais.md](nao-funcionais.md)
- Matriz requisito → teste: [../testing/rastreabilidade.md](../testing/rastreabilidade.md)
- Estratégia de testes: [../testing/estrategia.md](../testing/estrategia.md)
- Segurança: [../security/seguranca.md](../security/seguranca.md)

## Como ler este catálogo

| Campo | Significado |
|---|---|
| **Prioridade** | Alta = ligado à integridade das uniões (irreversíveis) ou a dados de clientes; Média = operação/usabilidade; Baixa = conveniência |
| **Dependências** | Outros FR (ou módulos) dos quais o requisito depende |
| **Testes** | Nomes reais `arquivo::função` em `tests/`. Testes parametrizados contam como um nome aqui |
| **Status** | Um de: *Implementado e testado* · *Implementado sem teste automatizado* · *Parcial* · *Pendente* · *Não aplicável* |

"Implementado e testado" significa: existe teste automatizado que passa (suíte executada em 13/10/2026 no Windows 11,
Python 3.14.6: todos os testes coletados passaram). **Nenhum teste automatizado fala com o Kommo real** — o motor é
testado contra simuladores (`tests/fakes.py`). Onde o comportamento depende do Kommo real, isso está dito no status.

Abreviações de evidência: `merger.py:Merger._laco` = arquivo `src/kommo_duplicatas/merger.py`, método
`Merger._laco`. Os módulos citados ficam em `src/kommo_duplicatas/` salvo indicação contrária.

---

## 1. Instalação, execução e dados locais

### FR-001 — Execução a partir do código-fonte com ambiente local

- **Descrição:** o app roda do código-fonte por `iniciar.bat` (Windows) ou `iniciar.sh` (Linux), que criam/usam um
  `.venv` local (nunca o Python global), instalam dependências só quando o arquivo de requisitos muda e preferem
  `requirements.lock` com `--require-hashes`. `python main.py` também funciona sem instalar o pacote.
- **Prioridade:** Média
- **Dependências:** FR-002
- **Critérios de aceitação:**
  1. Sem `.venv`, `iniciar.bat` cria o ambiente (`py -3 -m venv`, depois `python -m venv`); sem Python 3.10+ mostra
     erro e sai com código 1.
  2. Com `requirements.lock` presente, instala com `--require-hashes`; senão usa `requirements.txt`.
  3. Dependências só são reinstaladas quando o arquivo difere de `.venv\.requisitos-instalados`.
  4. `python main.py` sem argumentos abre a interface; `--cli` roda o modo texto; `--help`/`-h` mostra o uso sem
     abrir janela; o código de saída da UI/CLI é propagado.
- **Testes relacionados:** `tests/test_main.py::test_sem_argumentos_abre_ui_e_propaga_codigo`,
  `test_cli_recebe_argv_sem_o_marcador`, `test_cli_sem_argumentos_extras`, `test_ajuda_nao_abre_ui`,
  `test_cli_help_real_sai_com_zero` (só o ponto de entrada).
- **Status:** **Implementado sem teste automatizado** para `iniciar.bat`/`iniciar.sh` (scripts de shell; não há
  teste que os execute). `iniciar.sh` traz no próprio cabeçalho "NÃO TESTADO LOCALMENTE". O despacho de
  `__main__.py` é *implementado e testado*.
- **Evidência:** `iniciar.bat`, `iniciar.sh`, `main.py`, `__main__.py:main`.

### FR-002 — Modo portátil: raiz de dados ao lado do programa

- **Descrição:** configuração, logs, perfil do navegador, capturas de depuração e temporários ficam numa única raiz
  `<pasta do programa>/data/` (pasta do `.exe` quando empacotado; raiz do repositório no código-fonte). A variável
  `KOMMO_DATA_DIR` tem precedência (caminho relativo é resolvido a partir da pasta do programa, nunca do diretório
  de trabalho). O app **não** cai em silêncio para `%APPDATA%`.
- **Prioridade:** Alta
- **Dependências:** —
- **Critérios de aceitação:**
  1. Código-fonte: dados em `<repo>/data`; executável: `<pasta do exe>/data`, inclusive com espaços e acentos no
     caminho.
  2. `KOMMO_DATA_DIR` absoluto ou relativo substitui a raiz; relativo é relativo à pasta do programa.
  3. Mudar o diretório de trabalho não muda a raiz.
  4. Subpastas: `config.json`, `logs/`, `profile/<canal>/`, `debug/`, `tmp/`.
- **Testes relacionados:** `tests/test_paths.py::test_portatil_codigo_fonte`,
  `test_portatil_frozen_com_espacos_e_acentos`, `test_kommo_data_dir_tem_precedencia`,
  `test_kommo_data_dir_relativo_e_relativo_ao_programa`, `test_independe_do_cwd`,
  `test_app_dir_codigo_fonte_e_a_raiz_do_repositorio`, `test_profile_dir_por_canal`;
  `tests/test_config.py::test_dados_ficam_na_raiz_de_dados`.
- **Status:** **Implementado e testado.**
- **Evidência:** `paths.py:app_dir`, `raiz_configurada`, `data_dir`, `profile_dir`, `config_file`, `logs_dir`,
  `debug_dir`.

### FR-003 — Erro claro quando a pasta de dados não é gravável

- **Descrição:** se a raiz de dados não puder ser criada ou não aceitar escrita (teste real de criar/apagar um
  arquivo, porque `os.access` ignora ACLs no Windows), o app levanta `DataDirNotWritable` com o caminho, a causa e
  duas soluções (mover a pasta ou definir `KOMMO_DATA_DIR`). A interface mostra o erro numa caixa de diálogo e não
  abre; o motor encerra com `FimEvt`.
- **Prioridade:** Alta
- **Dependências:** FR-002
- **Critérios de aceitação:**
  1. Sem permissão (ou escrita real falhando) → `DataDirNotWritable` com mensagem explicativa.
  2. A exceção **não** é engolida por `except OSError` (herda de `RuntimeError`).
  3. `ui.main()` devolve 1 e mostra o erro sem abrir a janela principal.
  4. `config.salvar` não engole o erro; `logs.gravar` não derruba o app (guarda o motivo em `logs.ultimo_erro`).
  5. O teste de escrita não deixa arquivos temporários.
- **Testes relacionados:** `tests/test_paths.py::test_nao_gravavel_por_permissao`,
  `test_nao_gravavel_quando_escrita_real_falha`, `test_nao_gravavel_sem_mock`,
  `test_erro_nao_e_engolido_por_except_oserror`, `test_ensure_writable_nao_deixa_lixo`;
  `tests/test_config.py::test_pasta_nao_gravavel_nao_e_engolida`;
  `tests/test_logs.py::test_falha_de_pasta_nao_derruba`;
  `tests/test_ui_integracao.py::test_main_data_dir_nao_gravavel_mostra_erro_e_nao_abre`.
- **Status:** **Implementado e testado.** O cenário real "pasta em Arquivos de Programas" não foi exercitado por
  teste automatizado (o teste `test_nao_gravavel_sem_mock` usa permissões do sistema de arquivos local).
- **Evidência:** `paths.py:DataDirNotWritable`, `ensure_writable`; `ui.py:main`, `_erro_fatal`;
  `merger.py:Merger.run` (ramo `paths.DataDirNotWritable`).

---

## 2. Parâmetros da execução

### FR-004 — Subdomínio da empresa: normalização e validação

- **Descrição:** o campo "Empresa" aceita `minhaempresa`, `minhaempresa.kommo.com` ou a URL completa e extrai só o
  subdomínio, que precisa ser um rótulo DNS válido (1–63 caracteres, letras/números/hífen, sem hífen nas pontas).
  Recusa `usuario@...`, outros domínios, subníveis (`x.acme.kommo.com`) e sublinhado.
- **Prioridade:** Alta
- **Dependências:** —
- **Critérios de aceitação:**
  1. `normalizar_empresa` devolve o subdomínio em minúsculas ou `""` se inválido.
  2. Campo vazio → mensagem "Informe o subdomínio…"; inválido → mensagem com exemplo; nada é iniciado.
  3. CLI: subdomínio inválido → erro de uso do `argparse` (código 64, EX_USAGE).
  4. O campo começa vazio na primeira execução (sem subdomínio padrão).
- **Testes relacionados:** `tests/test_kommo.py::test_normalizar_empresa`;
  `tests/test_config.py::test_padrao_sem_empresa`.
- **Status:** **Implementado e testado** (normalização). As mensagens da UI para empresa vazia/inválida
  (`ui.py:App.iniciar`) **não** têm teste dedicado.
- **Evidência:** `kommo.py:RE_EMPRESA`, `normalizar_empresa`; `ui.py:App.iniciar`; `cli.py:main`.

### FR-005 — Escolha de Leads ou Contatos

- **Descrição:** o usuário escolhe "Leads" ou "Apenas contatos". Cada tipo tem URL própria
  (`/leads/list/` e `/contacts/list/contacts/?skip_filter=Y`), item de menu próprio
  (`li.js-duplicate-search` × `li.js-list-duplicate-contacts-search`) e caminho esperado (`/leads…` × `/contacts…`).
  O clique no item é **estrito**: sem fallback por texto, só elemento visível do tipo pedido.
- **Prioridade:** Alta
- **Dependências:** FR-011
- **Critérios de aceitação:**
  1. Tipo desconhecido → `FimEvt(motivo="validacao")` sem abrir o navegador.
  2. O item de menu de outra entidade nunca é clicado; item invisível não é clicado.
  3. URL aberta pelo app aponta para a lista do tipo pedido.
- **Testes relacionados:** `tests/test_kommo.py::test_montar_url`, `test_seletores_fonte_unica_e_aliases`;
  `tests/test_kommo_js.py::test_clica_item_do_tipo_certo`, `test_nao_clica_item_de_outra_entidade`,
  `test_nao_clica_item_invisivel`; `tests/test_kommo_porta.py::test_clicar_item_passa_tipo_e_seletores`,
  `test_clicar_item_tipo_desconhecido_nem_avalia`; `tests/test_merger.py::test_tipo_errado_aborta_sem_abrir_nem_clicar`,
  `test_job_invalido_nao_abre_sessao`, `test_validacoes_puras`.
- **Status:** **Implementado e testado** (em fixture HTML e simulador). Os seletores vêm de observação manual do
  Kommo ([KOMMO_DOM.md](../KOMMO_DOM.md)); mudança de HTML do Kommo não é detectável por teste automatizado.
- **Evidência:** `kommo.py:URL_LEADS`, `URL_CONTATOS`, `Seletores.item`, `_JS_CLICAR_ITEM`;
  `merger.py:caminho_confere`, `Merger._validar_job`.

### FR-006 — Quantidade de uniões e validação

- **Descrição:** opções 100 · 200 · 500 · Todas, mais um campo "outro valor" (0 = todas). O texto é interpretado por
  regras puras: vazio usa a opção marcada; aceita separador de milhar consistente de 3 em 3 (ponto, espaço, NBSP,
  espaço fino); rejeita negativos, decimais, letras, dígitos não ASCII, caracteres invisíveis e valores acima de
  999.999, com mensagem pronta em português. Valor inválido **nunca** cai em silêncio para a opção marcada.
- **Prioridade:** Alta
- **Dependências:** —
- **Critérios de aceitação:**
  1. `parse_limite("1.000", 100) == 1000`; `parse_limite("", 500) == 500`; `parse_limite("0", 500) == 0`.
  2. `"10.00"`, `"1,5"`, `"-3"`, `"²"`, `"1000000"` → `ValueError` com mensagem.
  3. A UI mostra retorno imediato ("→ vale 1.000" / "valor inválido") e, ao iniciar com valor inválido, não inicia
     e põe o foco no campo.
  4. O último valor livre é salvo (`limite_custom`) e restaurado.
  5. CLI: `limite` precisa ser inteiro ≥ 0.
- **Testes relacionados:** `tests/test_limite.py::test_validos`, `test_invalidos_levantam_com_mensagem`,
  `test_nunca_usa_preset_em_silencio_quando_invalido`, `test_maximo`, `test_mensagem_trunca_texto_enorme`,
  `test_descrever`, `test_exige_digitar`; `tests/test_ui_integracao.py::test_limite_custom_persistido_e_restaurado`;
  `tests/test_cli.py::test_limite_invalido_rejeitado`.
- **Status:** **Implementado e testado.**
- **Evidência:** `limite.py:parse_limite`, `descrever_limite`; `ui.py:App._validar_custom`, `App.iniciar`;
  `cli.py:limite_valido`.

### FR-007 — O limite conta cliques em "Unir" e nunca é ultrapassado

- **Descrição:** o limite é aplicado sobre **cliques disparados** em "Unir esta duplicata" (confirmados + não
  confirmados), contados **antes** do clique. Um clique que falha também conta. Assim, mesmo quando o Kommo não
  confirma a conclusão, o app nunca clica mais vezes do que o pedido.
- **Prioridade:** Alta
- **Dependências:** FR-012, FR-013
- **Critérios de aceitação:**
  1. Em qualquer cenário simulado, `FimEvt.cliques <= Job.limite` (quando limite > 0) e
     `cliques == confirmadas + incertas`.
  2. Limite atingido → `motivo="limite"`, com o modal fechado só em estado estável.
  3. Leads sem texto "concluída": 5 cliques → 0 confirmadas, 5 não confirmadas, motivo `limite`.
- **Testes relacionados:** `tests/test_merger.py::test_caminho_feliz_para_exatamente_no_limite`,
  `test_leads_sem_texto_concluida_tudo_incerto_e_limite_por_cliques`,
  `test_uniao_sem_resultado_conta_como_clique_e_registra_erro`, `test_clique_que_falha_conta_e_tres_falhas_param`;
  invariante `checar_seguranca` aplicada na maioria dos testes de `test_merger.py`.
- **Status:** **Implementado e testado** (simulador).
- **Evidência:** `merger.py:Merger._laco` (`self.cliques += 1` antes de `porta.clicar_unir()`).

---

## 3. Segurança da operação irreversível

### FR-008 — Confirmação da conta antes da primeira união

- **Descrição:** depois de abrir o modal e ler o total, e **antes do primeiro clique em "Unir"**, o motor emite
  `ConfirmarEvt(host, tipo, total, limite, ensaio)` e fica bloqueado até a resposta. Na interface abre um diálogo
  modal com conta logada, tipo, total de grupos e quantidade pedida, com o aviso "A união é IRREVERSÍVEL".
  "Cancelar" é o padrão (foco inicial; Esc, Enter e o X da janela cancelam). Para "Todas" (0) ou mais de 500
  uniões, o botão "Unir agora" só habilita depois de digitar `UNIR`. No modo texto, a pergunta é `[s/N]`
  (vazio/EOF = não) ou `--sim`.
- **Prioridade:** Alta
- **Dependências:** FR-010, FR-011, FR-020
- **Critérios de aceitação:**
  1. Recusa → `motivo="recusado"`, zero cliques, sem erro.
  2. Sem resposta em `TEMPO_CONFIRMACAO` (600 s) → `motivo="sem_resposta"`, zero cliques.
  3. Parada durante a confirmação → `motivo="parado"`, zero cliques.
  4. O diálogo responde ao motor **uma única vez**, por qualquer caminho, e fecha sozinho se o processo terminar.
  5. Janela sendo fechada com confirmação pendente = resposta "não".
  6. Com privacidade, conta e total aparecem mascarados até "Mostrar conta".
- **Testes relacionados:** `tests/test_merger.py::test_confirmacao_sem_resposta_nao_clica`,
  `test_confirmacao_recusada_nao_clica`, `test_confirmacao_aceita_segue`, `test_parar_durante_a_confirmacao`;
  `tests/test_ui_integracao.py::test_confirmacao_aceitar`, `test_confirmacao_cancelar_registra_no_log`,
  `test_confirmacao_esc_e_enter_cancelam`, `test_confirmacao_fechar_no_x_responde_nao`,
  `test_confirmacao_responde_uma_vez_so`, `test_confirmacao_exige_digitar_unir`,
  `test_confirmacao_500_nao_exige_digitar`, `test_confirmacao_fecha_sozinha_se_a_thread_termina`,
  `test_confirmacao_fecha_quando_chega_o_fim`, `test_confirmacao_privacidade_mascara_e_mostrar_conta`,
  `test_confirmacao_sem_privacidade_mostra_conta`, `test_iniciar_cria_job_sem_pergunta_previa`,
  `test_fechar_com_thread_espera_ela_terminar`;
  `tests/test_ui_pura.py::test_confirmacao_regra_digitar_unir`, `test_regra_exige_digitar_e_palavra`,
  `test_confirmacao_privacidade_ligada_mascara_host_e_total`, `test_confirmacao_privacidade_desligada`,
  `test_confirmacao_revelar_mostra_conta_real`, `test_confirmacao_total_nao_informado_com_privacidade`;
  `tests/test_cli.py::test_pergunta_e_recusa`, `test_confirmacao_eof_e_nao`,
  `test_sim_confirma_sem_perguntar_e_imprime_resumo`.
- **Status:** **Implementado e testado.**
- **Evidência:** `merger.py:Merger._confirmar`, `Merger.responder`; `ui.py:DialogoConfirmacao`,
  `dados_confirmacao`, `App._abrir_confirmacao`; `limite.py:exige_digitar`, `palavra_confere`;
  `cli.py:perguntar_confirmacao`.

### FR-009 — Modo ensaio (simulação sem unir)

- **Descrição:** com "Só simular (não une nada)" (UI) ou `--ensaio` (CLI), o app faz login, valida conta/lista,
  abre o modal, lê o total, pede a confirmação (marcada como ensaio) e encerra **sem clicar em "Unir"**, fechando o
  modal. A opção **não** é persistida: toda abertura do app começa no modo real.
- **Prioridade:** Alta
- **Dependências:** FR-008, FR-010, FR-011
- **Critérios de aceitação:**
  1. `motivo="ensaio"`, `cliques == 0`, nenhuma chamada a `clicar_unir`.
  2. Botão INICIAR vira "SIMULAR"; o `Job` sai com `ensaio=True`.
  3. O resumo do ensaio diz "nada foi unido" e, se por defeito houver clique, mostra alerta.
- **Testes relacionados:** `tests/test_merger.py::test_ensaio_nao_clica_em_unir`,
  `test_ensaio_tambem_pede_confirmacao_quando_ligada`, `test_sessao_playwright_init_script_canal_e_fecha`;
  `tests/test_ui_integracao.py::test_ensaio_muda_botao_e_job`, `test_resumo_do_ensaio`,
  `test_confirmacao_ensaio_botao`; `tests/test_ui_pura.py::test_resumo_ensaio`, `test_confirmacao_ensaio`,
  `test_texto_inicio_com_privacidade_e_ensaio`; `tests/test_cli.py::test_pergunta_e_aceita_com_ensaio`.
- **Status:** **Implementado e testado** (simulador e UI com motor falso).
- **Evidência:** `merger.py:Job.ensaio`, `Merger._executar`; `ui.py:App.ensaio`, `textos_resumo`.

### FR-010 — Espera do login

- **Descrição:** o motor considera a sessão logada só quando o hostname é **exatamente** `<empresa>.kommo.com` e o
  botão de menu "⋯" existe. Avisa uma vez para fazer login, reavisa a cada 60 s com o host atual e desiste depois de
  `TEMPO_LOGIN` (600 s) com mensagem clara.
- **Prioridade:** Alta
- **Dependências:** FR-004
- **Critérios de aceitação:**
  1. Hostname por substring (`xacme.kommo.com`, `acme.kommo.com.evil.io`) não vale.
  2. Login feito depois de 130 s → continua sozinho; 1 aviso + 2 reavisos.
  3. Sem login em 600 s → `motivo="login_timeout"`, 1 erro, zero cliques.
  4. Navegador fechado durante o login → `motivo="navegador_fechado"`, como aviso (não erro).
  5. Parada antes do login → `motivo="parado"`.
- **Testes relacionados:** `tests/test_merger.py::test_login_espera_com_reavisos_e_continua`,
  `test_login_teto_da_erro_claro`, `test_login_hostname_por_substring_nao_vale`,
  `test_navegador_fechado_durante_o_login_mensagem_amigavel`, `test_parar_antes_do_login`;
  `tests/test_kommo.py::test_hostname_confere`.
- **Status:** **Implementado e testado** (simulador).
- **Evidência:** `merger.py:Merger._aguardar_login`, `TEMPO_LOGIN`, `REAVISO_LOGIN`; `kommo.py:hostname_confere`.

### FR-011 — Validação de conta, página e modal antes de cada clique

- **Descrição:** antes de **cada** clique em "Unir" o motor confere: hostname exato da empresa, caminho coerente com
  o tipo (`/leads` ou `/contacts`) e título do modal contendo "duplicat" (sem acento/caixa). Qualquer divergência
  encerra com `motivo="validacao"` **sem clicar**.
- **Prioridade:** Alta
- **Dependências:** FR-004, FR-005
- **Critérios de aceitação:**
  1. URL trocada para outra conta ou domínio parecido antes do clique → zero cliques, `validacao`.
  2. Modal com outro título (ex.: "Exportar contatos") → zero cliques, `validacao`, 1 erro.
- **Testes relacionados:** `tests/test_merger.py::test_hostname_muda_antes_do_clique_aborta`,
  `test_modal_que_nao_e_de_duplicatas_aborta`, `test_tipo_errado_aborta_sem_abrir_nem_clicar`,
  `test_validacoes_puras`.
- **Status:** **Implementado e testado** (simulador).
- **Evidência:** `merger.py:Merger._validar_pagina`, `_validar_modal`, `caminho_confere`, `modal_de_duplicatas`.

---

## 4. Laço de uniões

### FR-012 — Laço de uniões

- **Descrição:** a partir do modal aberto, o motor repete: esperar a busca devolver um grupo (botão "Unir" visível
  e sem progresso), validar (FR-011), contar e clicar, observar até um estado estável (FR-013), registrar o
  resultado e, se não confirmado, esperar `ESTABILIZAR` (1 s) e reconferir o estado antes de qualquer novo clique.
  Para após `FALHAS_MAX` (3) uniões seguidas sem resultado (tempo esgotado de 120 s, erro do Kommo ou clique que
  falhou).
- **Prioridade:** Alta
- **Dependências:** FR-007, FR-011, FR-013, FR-017
- **Critérios de aceitação:**
  1. Clique em "Unir" só com o botão visível (fase "grupo" do simulador).
  2. Depois de uma união não confirmada há pelo menos duas leituras de estado antes do próximo clique.
  3. Três falhas seguidas → `motivo="falhas"`.
  4. União sem resultado em 120 s conta como clique não confirmado, registra **erro** e grava diagnóstico.
  5. Com recarga entre uniões ou com o próximo grupo direto, o laço segue até o limite.
- **Testes relacionados:** `tests/test_merger.py::test_caminho_feliz_para_exatamente_no_limite`,
  `test_sem_recarga_proximo_grupo_direto`, `test_todas_ate_acabar_conclui_sem_duplicatas`,
  `test_incerto_reconfere_estado_antes_de_reclicar`, `test_uniao_sem_resultado_conta_como_clique_e_registra_erro`,
  `test_clique_que_falha_conta_e_tres_falhas_param`; `tests/test_fluxo.py::test_sequencia_com_fake`.
- **Status:** **Implementado e testado** em simulador. No Kommo real, o laço foi exercitado manualmente antes
  desta revisão (registro em [ESTRUTURA.md](../ESTRUTURA.md): "100 uniões seguidas de contatos sem erros (~6 s
  cada) e uniões de leads"); esse registro é anterior à regra atual de confirmação (FR-013) e não foi refeito
  nesta revisão.
- **Evidência:** `merger.py:Merger._laco`, `_aguardar_uniao`, `TEMPO_UNIAO`, `FALHAS_MAX`, `ESTABILIZAR`,
  `POLL_UNIAO`.

### FR-013 — Regra de confirmação de uma união (`fluxo.avaliar_uniao`)

- **Descrição:** cada clique é classificado por uma função pura com tabela de decisão de 12 linhas: **SUCESSO** só
  com o texto de conclusão do Kommo (`/conclu/i`, sem acento) **e** um estado seguinte coerente (próximo grupo
  visível, modal fechado ou página recarregando); **INCERTO** quando algo mudou sem confirmação (não conta como
  feita); **ERRO** quando o modal mostra erro; **AGUARDA** caso contrário (o motor aplica o teto de 120 s). Enquanto
  o próprio "…concluída" está na tela, aguarda. Cada texto de progresso distinto é registrado uma vez no log
  (calibração).
- **Prioridade:** Alta
- **Dependências:** —
- **Critérios de aceitação:**
  1. As 12 linhas da tabela documentada em `fluxo.avaliar_uniao` são respeitadas na ordem.
  2. `progresso_concluido("UNIÃO DE LEADS CONCLUÍDA") is True`; `"Unindo leads"` → `False`.
  3. Leads "1 de muitas" (título repetido) só vira SUCESSO com o texto de conclusão.
- **Testes relacionados:** `tests/test_fluxo.py::test_avaliar_uniao` (18 casos),
  `test_progresso_concluido` (8 casos), `test_sequencia_com_fake`, `test_fake_implementa_porta`;
  `tests/test_merger.py::test_leads_sem_texto_concluida_tudo_incerto_e_limite_por_cliques`;
  `tests/test_kommo_js.py::test_estado_progresso_e_concluido`.
- **Status:** **Parcial.** A regra está implementada e testada (unidade, simulador e JS em fixture), mas **o texto
  de conclusão em Leads NÃO foi confirmado no Kommo real**: o mapa do DOM registra para Leads só "Unindo leads", e
  o exemplo de conclusão observado é o de Contatos ("União de contatos concluída com sucesso"). Se o Kommo não
  mostrar "conclu…" em Leads, todas as uniões de Leads aparecerão como "não confirmadas" (comportamento seguro,
  coberto pelo teste pessimista acima, mas o contador de confirmadas ficaria em 0).
- **Evidência:** `fluxo.py:avaliar_uniao`, `progresso_concluido`, `Resultado`; `merger.py:Merger._aguardar_uniao`.

### FR-014 — Parada em dois níveis

- **Descrição:** 1º pedido de parada (botão PARAR, ou Ctrl+C no modo texto): termina a união em andamento e para
  **entre uniões**, fechando o modal com segurança. 2º pedido (botão vira "FORÇAR PARADA", ou 2º Ctrl+C): aborta na
  hora, sem clicar em Cancelar; a união em andamento é contada como "não confirmada". Parada é aviso, nunca erro.
- **Prioridade:** Alta
- **Dependências:** FR-016, FR-022
- **Critérios de aceitação:**
  1. Parada no meio da união → o resultado é aguardado; `motivo="parado"`, 1 confirmada, 0 erros; o modal só é
     cancelado depois da conclusão.
  2. Segundo pedido → `motivo="forcado"`, a união pendente vira `incertas=1`, nenhum clique em fechar/cancelar.
  3. Parada durante a busca → zero cliques.
  4. Setar direto o `Event` compartilhado equivale ao 1º pedido.
  5. Ao chegar o `FimEvt`, a UI reabilita INICIAR e restaura os rótulos.
- **Testes relacionados:** `tests/test_merger.py::test_parar_no_meio_da_uniao_espera_o_resultado`,
  `test_segundo_pedido_forca_saida_imediata`, `test_parar_durante_a_busca_sai_sem_clicar`,
  `test_ui_setando_o_event_direto_equivale_a_parar`, `test_solicitar_parada_duas_vezes_forca`,
  `test_parar_antes_do_login`, `test_parar_durante_a_confirmacao`, `test_thread_nao_daemon_e_parar_e_aguardar`;
  `tests/test_ui_integracao.py::test_parar_dois_niveis_e_fim_reabilita`;
  `tests/test_cli.py::test_ctrl_c_pede_parada_e_drena_a_fila`.
- **Status:** **Implementado e testado.**
- **Evidência:** `merger.py:Merger.solicitar_parada`, `_checar_forcado`, `_contar_pendente`; `ui.py:App.parar_tudo`;
  `cli.py:main` (tratamento de `KeyboardInterrupt`).

### FR-015 — Fechamento seguro da janela

- **Descrição:** fechar a janela com a thread viva pergunta "Parar e fechar?" (padrão "não"). Se sim, responde "não"
  a uma confirmação pendente, pede a parada normal e só destrói a janela quando a thread termina. Depois de
  `TETO_FECHAR` (150 s) força a parada; depois de mais `TETO_FORCAR` (20 s) avisa para fechar o navegador e
  **continua esperando** (nunca destrói a janela com a thread viva). Sem thread, fecha direto.
- **Prioridade:** Alta
- **Dependências:** FR-014
- **Critérios de aceitação:** os quatro cenários abaixo nos testes.
- **Testes relacionados:** `tests/test_ui_integracao.py::test_fechar_sem_thread_fecha_direto`,
  `test_fechar_com_thread_e_resposta_nao_mantem_tudo`, `test_fechar_com_thread_espera_ela_terminar`,
  `test_fechar_forca_depois_do_teto`, `test_fechar_thread_travada_avisa_e_nao_destroi`.
- **Status:** **Implementado e testado** (UI com motor falso).
- **Evidência:** `ui.py:App.fechar`, `_aguardar_fechar`, `TETO_FECHAR`, `TETO_FORCAR`.

### FR-016 — Fechamento seguro do modal do Kommo

- **Descrição:** o app só clica em "Cancelar" do modal com o estado estável e só se o botão existir; se ainda houver
  texto de progresso de união na tela, não clica em nada e avisa. Nunca fecha/cancela o modal no meio de uma união.
- **Prioridade:** Alta
- **Dependências:** —
- **Critérios de aceitação:** nenhum fechamento/cancelamento nas fases "unindo" ou "concluído" do simulador em
  nenhum cenário; `cancelar_modal` não espera timeout quando o modal já fechou.
- **Testes relacionados:** invariante `checar_seguranca` em `tests/test_merger.py`;
  `tests/test_merger.py::test_parar_no_meio_da_uniao_espera_o_resultado`;
  `tests/test_kommo_porta.py::test_cancelar_modal_so_clica_se_existir`, `test_fechar_modal_ordem_x_cancelar_escape`;
  `tests/test_kommo_js.py::test_clicar_unir_e_cancelar`, `test_fechar_modal_usa_o_x`.
- **Status:** **Implementado e testado.**
- **Evidência:** `merger.py:Merger._fechar_modal_seguro`; `kommo.py:KommoPage.cancelar_modal`, `fechar_modal`.

### FR-017 — Busca de duplicatas, "Algo deu errado" e reabertura

- **Descrição:** a busca espera até `TEMPO_BUSCA` (90 s) pelo botão "Unir". Se o modal mostra "Ops! Algo deu
  errado", clica em "Tentar novamente" até `ERRO_TENTATIVAS` (5) vezes **por ciclo** (contador compartilhado) e, se
  persistir, reabre a busca pelo menu uma vez (`REABERTURAS_MAX`). Página recarregando (inclusive durante a união)
  força a reabertura antes de concluir "vazio". Resultados: `pronto`, `vazio`, `erro`, `travado` (modal sem botão
  até o teto), `sem_item`, `parado`.
- **Prioridade:** Alta
- **Dependências:** FR-018
- **Critérios de aceitação:**
  1. Erro permanente → 5 "Tentar novamente" + 1 reabertura → `motivo="erro"`, nunca "sem duplicatas".
  2. Erro que some → segue normalmente.
  3. Erro seguido de carregamento infinito → `erro`, nunca "sem duplicatas".
  4. Recarga durante a união → reabre pelo menu e segue.
- **Testes relacionados:** `tests/test_merger.py::test_algo_deu_errado_tenta_reabre_uma_vez_e_falha`,
  `test_erro_some_e_volta_ao_normal`, `test_houve_erro_persiste_durante_o_carregamento`,
  `test_pagina_recarrega_durante_a_uniao_reabre_pelo_menu`; `tests/test_kommo_js.py::test_estado_detecta_erro_do_modal`.
- **Status:** **Implementado e testado** (simulador). O comportamento "Algo deu errado" em Leads foi observado
  manualmente no Kommo real antes desta revisão ([KOMMO_DOM.md](../KOMMO_DOM.md)); a lógica atual não foi
  re-exercitada contra o Kommo real nesta revisão.
- **Evidência:** `merger.py:Merger._esperar_busca`, `_reabrir`, `_busca_sem_grupo`, `ERRO_TENTATIVAS`,
  `REABERTURAS_MAX`, `TEMPO_BUSCA`.

### FR-018 — "Sem duplicatas" só com sessão válida; sessão expirada

- **Descrição:** "sem duplicatas restantes" só é concluído quando a busca termina sem modal, **sem erro pendente** e
  com a sessão ainda logada na lista certa (hostname exato + caminho + menu). Se a sessão caiu ou a página foi
  redirecionada, encerra com `motivo="sessao_expirada"` mostrando só o host atual, e nada é dado como concluído.
- **Prioridade:** Alta
- **Dependências:** FR-010, FR-017
- **Critérios de aceitação:**
  1. Sessão que cai depois de 1 união → `sessao_expirada`, ≥ 1 erro, sem a frase "Nenhuma duplicata restante".
  2. Lista sem nenhum grupo → `sem_duplicatas`, zero cliques.
  3. "Todas" até acabar → `sem_duplicatas` com cliques = total.
- **Testes relacionados:** `tests/test_merger.py::test_sessao_expirada_nao_vira_concluido`,
  `test_lista_sem_nenhuma_duplicata`, `test_todas_ate_acabar_conclui_sem_duplicatas`.
- **Status:** **Implementado e testado** (simulador). Expiração real de sessão do Kommo não foi exercitada.
- **Evidência:** `merger.py:Merger._checar_sessao`, `_busca_sem_grupo`, `SessaoExpirada`.

### FR-019 — Navegador fechado, indisponível ou página que não responde

- **Descrição:** fechar o navegador, falha ao abrir um navegador, perfil em uso, erro transitório do Playwright
  (navegação, contexto destruído, timeout) ou erro inesperado terminam sempre com `FimEvt` e mensagem amigável;
  o contexto do navegador é sempre fechado. Leituras durante navegação viram `Estado(navegou=True)`; cliques que
  falham viram `False`; `page.evaluate` tem timeout no lado do JS. Fechar o navegador sem união em andamento é
  aviso; com união já clicada é erro.
- **Prioridade:** Alta
- **Dependências:** FR-022, FR-029
- **Critérios de aceitação:** cenários dos testes abaixo; "Traceback" nunca aparece no log do motor.
- **Testes relacionados:** `tests/test_merger.py::test_navegador_fechado_no_meio_da_uniao`,
  `test_navegador_fechado_durante_o_login_mensagem_amigavel`, `test_falha_ao_abrir_o_navegador_ainda_emite_fim`,
  `test_excecao_no_meio_da_uniao_preserva_contadores_e_fecha`, `test_excecao_do_roteiro_do_fakekommo`,
  `test_sessao_playwright_fecha_mesmo_com_excecao_e_navegador_fechado`;
  `tests/test_kommo_porta.py::test_estado_navegacao_vira_navegou`, `test_estado_timeout_do_playwright_vira_navegou`,
  `test_estado_erro_desconhecido_propaga`, `test_acoes_com_navegacao_devolvem_valor_seguro`,
  `test_cliques_com_timeout_e_falha_vira_false`; `tests/test_kommo_js.py::test_timeout_do_evaluate`,
  `test_clicar_unir_invisivel_falha_rapido`; `tests/test_ui_integracao.py::test_kommopage_esta_fechada`.
- **Status:** **Implementado e testado.**
- **Evidência:** `merger.py:Merger.run`, `_sessao_playwright`, `_abrir_url`, `_eh_fechamento`;
  `kommo.py:KommoPage`, `eh_transitorio`, `_js_com_timeout`.

---

## 5. Informação ao usuário

### FR-020 — Total de grupos de duplicatas

- **Descrição:** o total é lido do título do modal ("… 3 de 42.761" → 42761); "muitas" (comum em Leads) → não
  informado. O último total e a data/hora da execução são gravados em `config.json` só quando a execução termina de
  forma normal (`limite`, `sem_duplicatas`, `parado`) e o total é conhecido.
- **Prioridade:** Média
- **Dependências:** FR-028
- **Critérios de aceitação:** `parse_total` conforme os casos de teste; `deve_registrar` só para os 3 motivos.
- **Testes relacionados:** `tests/test_kommo.py::test_parse_total`; `tests/test_ui_pura.py::test_deve_registrar`;
  `tests/test_ui_integracao.py::test_fim_registra_execucao_quando_motivo_normal`;
  `tests/test_merger.py::test_caminho_feliz_para_exatamente_no_limite` (total = 10).
- **Status:** **Implementado e testado.**
- **Evidência:** `kommo.py:parse_total`; `merger.py:Merger._registrar_total`; `ui.py:deve_registrar`;
  `config.py:registrar_execucao`.

### FR-021 — Progresso ao vivo

- **Descrição:** contador grande = uniões **confirmadas**; linha de texto com o limite, as não confirmadas e, sem
  privacidade, "N de TOTAL duplicatas da conta · restam X"; barra = cliques / limite (vazia para "Todas"). Cada texto
  de progresso distinto do Kommo vai ao log uma única vez por execução.
- **Prioridade:** Média
- **Dependências:** FR-007, FR-025
- **Critérios de aceitação:** textos conforme `texto_progresso`; barra usa `max(cliques, feitos)/limite`.
- **Testes relacionados:** `tests/test_ui_pura.py::test_texto_progresso`, `test_texto_progresso_com_incertas`,
  `test_texto_progresso_sem_total_e_todas`, `test_fracao_barra_usa_cliques`;
  `tests/test_merger.py::test_leads_sem_texto_concluida_tudo_incerto_e_limite_por_cliques` (texto de progresso uma
  vez).
- **Status:** **Implementado e testado** (funções puras). A exibição do texto de progresso real do Kommo **não**
  foi conferida contra o Kommo real nesta revisão.
- **Evidência:** `ui.py:texto_progresso`, `fracao_barra`, `App.mostrar_progresso`; `merger.py:ProgEvt`.

### FR-022 — Resumo final (confirmadas e não confirmadas)

- **Descrição:** toda execução termina com **exatamente um** `FimEvt`, sempre o último evento, com confirmadas, não
  confirmadas, cliques, erros, avisos, segundos, total e motivo (um dos 14 de `MOTIVOS`). A UI mostra um diálogo de
  resumo (número de unificadas, "N de TOTAL da conta", "X não confirmadas — confira no Kommo", cliques e limite,
  motivo, tempo, erros/avisos); o modo texto imprime uma linha "Resumo: …". O ensaio tem resumo próprio.
- **Prioridade:** Alta
- **Dependências:** —
- **Critérios de aceitação:**
  1. `FimEvt` único e último em todos os cenários do simulador, inclusive exceções e falha ao abrir o navegador.
  2. Se a thread morrer sem `FimEvt`, a UI se recupera e avisa ("O processo terminou sem enviar o resumo").
  3. Motivo desconhecido é exibido literalmente.
- **Testes relacionados:** invariante `checar_seguranca` (`tests/test_merger.py`);
  `tests/test_ui_pura.py::test_resumo_normal_sem_incertas`, `test_resumo_com_incertas_privacidade_e_motivo`,
  `test_resumo_uma_incerta_singular`, `test_resumo_motivo_desconhecido`, `test_resumo_ensaio`, `test_texto_detalhes`,
  `test_texto_resumo_conta`; `tests/test_ui_integracao.py::test_parar_dois_niveis_e_fim_reabilita`;
  `tests/test_cli.py::test_sim_confirma_sem_perguntar_e_imprime_resumo`.
- **Status:** **Implementado e testado.** A rede de segurança "thread morreu sem FimEvt" (`ui.py:App.bombear`) não
  tem teste dedicado.
- **Evidência:** `merger.py:Merger._emitir_fim`, `FimEvt`, `MOTIVOS`; `ui.py:textos_resumo`, `App.resumo`,
  `App.bombear`; `cli.py:main`.

### FR-023 — Log com data/hora, arquivo diário e rotação

- **Descrição:** cada linha tem `[dd/mm/AAAA HH:MM:SS]` e nível (ERRO/AVISO/OK). A mesma linha aparece na tela e vai
  para `data/logs/AAAA-MM-DD.log`. Caracteres de controle viram espaço; linhas com mais de 2.000 caracteres são
  truncadas com marca. No primeiro `gravar` do processo, logs com data (pelo nome) anterior a 30 dias são apagados.
  Falha de gravação não derruba o app.
- **Prioridade:** Média
- **Dependências:** FR-002
- **Critérios de aceitação:** conforme testes.
- **Testes relacionados:** `tests/test_logs.py::test_gravar_cria_arquivo_do_dia`,
  `test_sanitiza_caracteres_de_controle`, `test_preserva_acentos_e_espacos`, `test_trunca_linhas_longas`,
  `test_limpar_antigos`, `test_primeiro_gravar_limpa_antigos_uma_vez`, `test_falha_de_pasta_nao_derruba`,
  `test_niveis_nao_existe_mais`.
- **Status:** **Implementado e testado.**
- **Evidência:** `logs.py:formatar`, `sanitizar`, `gravar`, `limpar_antigos`, `MAX_LINHA`, `DIAS_RETENCAO`.

---

## 6. Privacidade

### FR-024 — Modo privacidade no navegador

- **Descrição:** com a opção ligada (padrão), um script de início de documento (`context.add_init_script`) com o
  estado embutido: (1) injeta CSS `filter: blur(7px)` por seletores conhecidos (linhas de lista, nomes, telefones,
  e-mails, conta, chat, funil, modal de duplicatas, tooltips, toasts, avatares); (2) instala um `MutationObserver`
  que marca com `kp-sens` elementos "folha" cujo texto casa com a regex de valores sensíveis (R$, "N
  leads/contatos/empresas", %, N/NNN, "limite") e retira a marca se o texto deixa de ser sensível; (3) trava o
  título da aba em "Kommo"; (4) retira atributos `title` sensíveis; (5) anonimiza notificações criadas pela página.
  Os textos do processo (título do modal, progresso, botões) continuam legíveis. Não depende de `localStorage`.
  O motor reforça o estado no máximo a cada 3 s; com a opção desligada não faz nenhuma chamada de reforço.
- **Prioridade:** Alta
- **Dependências:** FR-019
- **Critérios de aceitação:**
  1. Todos os elementos sensíveis da fixture borrados sem nenhum polling, desde o início do documento.
  2. Elemento inserido depois é marcado antes da próxima pintura (mesma microtarefa).
  3. Título "Kommo" mesmo com a página tentando trocar; sem laço no observer.
  4. Desligado: nada borrado; `__kpSet` alterna em tempo de execução.
  5. 5.000 linhas inseridas: todas marcadas, nenhum `title` restante.
- **Testes relacionados:** `tests/test_privacy_js.py` (11 testes: `test_a_borra_sensiveis_sem_polling`,
  `test_a_borra_desde_o_inicio_do_documento`, `test_b_elemento_dinamico_marcado_em_ms`, `test_c_titulo_travado`,
  `test_d_processo_nao_borrado`, `test_e_desligado_nao_borra_e_kpset_alterna`, `test_e_ultimo_init_script_decide`,
  `test_init_script_nao_usa_storage`, `test_notificacoes_do_navegador_anonimizadas`, `test_aplicar_reforco_usa_kpset`,
  `test_f_desempenho_5000_linhas`); `tests/test_privacy.py` (13 testes);
  `tests/test_merger.py::test_privacidade_reforco_espacado_e_desligada_sem_chamadas`,
  `test_sessao_playwright_init_script_canal_e_fecha`, `test_sessao_playwright_config_quebrada_nao_derruba`.
- **Status:** **Parcial.** Implementado e testado contra a fixture HTML no Chromium headless. **Não é garantia:** a
  barra de endereço, notificações *push* do service worker, iframes de outra origem, diálogos nativos e telas não
  mapeadas não são cobertos (limitações documentadas em `privacy.py`). A eficácia sobre o Kommo real (gravação de
  tela "ao vivo") é verificação manual (ver [estrategia.md](../testing/estrategia.md#4-testes-manuais-antes-de-cada-release)).
- **Evidência:** `privacy.py:init_script`, `aplicar`, `SELETORES`, `REGEX_SENSIVEL`, `_JS_INIT_SCRIPT`;
  `merger.py:Merger._sessao_playwright`, `_reforcar_privacidade`, `INTERVALO_PRIVACIDADE`.

### FR-025 — Privacidade na janela do próprio app

- **Descrição:** com a privacidade ligada, o subdomínio aparece mascarado (`a***e`, sempre 3 asteriscos) no campo
  "Empresa" fora de edição, nas mensagens, no diálogo de confirmação e no arquivo de log da UI; o total da conta vira
  `••••` no contador, log e resumo. O valor real continua indo para o motor. O diálogo de confirmação tem "Mostrar
  conta" para conferir a conta de verdade. O modo texto aplica a mesma regra (`mascara.py`) ao terminal e ao log;
  na pergunta de confirmação, `m` revela a conta só no terminal.
- **Prioridade:** Alta
- **Dependências:** FR-008, FR-023
- **Critérios de aceitação:** máscaras conforme testes; o log gravado pela UI **e pela CLI** (privacidade ligada) não
  contém o subdomínio nem o total.
- **Testes relacionados:** `tests/test_ui_pura.py::test_mascarar_empresa`, `test_mascara_nao_revela_tamanho`,
  `test_mascarar_host`, `test_mascarar_mensagem_subdominio_e_totais`, `test_mascarar_mensagem_nao_estraga_texto_comum`,
  `test_mascarar_mensagem_total_informado_pelo_kommo`, `test_texto_inicio_com_privacidade_e_ensaio`;
  `tests/test_ui_integracao.py::test_logs_do_motor_sao_mascarados`,
  `test_confirmacao_privacidade_mascara_e_mostrar_conta`; `tests/test_cli.py::test_privacidade_padrao_mascara_terminal_e_log`,
  `test_sem_privacidade_mostra_conta_e_totais`, `test_pergunta_m_mostra_a_conta_so_no_terminal`,
  `test_confirmacao_com_privacidade_mascara_host_e_total`, `test_pergunta_e_recusa`.
- **Status:** **Implementado e testado** na interface gráfica e no modo texto (T11: antes a CLI gravava o log sem
  máscara).
- **Evidência:** `mascara.py:mascarar_empresa`, `mascarar_host`, `mascarar_mensagem` (reexportados em `ui.py`);
  `ui.py:App.escrever`, `App._sync_empresa`; `cli.py:main`, `perguntar_confirmacao`.

### FR-026 — Diagnóstico sem dados pessoais

- **Descrição:** em falhas (união sem resultado, busca sem grupo, erro persistente) o motor grava no log um
  diagnóstico **estrutural**: contagem/visibilidade de cada seletor conhecido, booleanos ("progresso_concluido",
  "caption_tem_total") e classes dos modais visíveis — nunca `innerText`/`value`. Captura de tela só com
  `KOMMO_DEBUG` verdadeiro (`1`, `true`, `yes`, `on`, sem diferenciar maiúsculas; `0`/`false`/vazio não ligam),
  depois de reforçar a privacidade, salva em `data/debug/`.
- **Prioridade:** Alta
- **Dependências:** FR-024
- **Critérios de aceitação:** diagnóstico sobre fixture com nomes/telefones não contém esses textos; sem
  `KOMMO_DEBUG` nenhuma captura; com ele, a captura vem imediatamente depois do reforço de privacidade.
- **Testes relacionados:** `tests/test_kommo_js.py::test_diagnostico_sem_pii`;
  `tests/test_merger.py::test_screenshot_so_com_debug`, `test_uniao_sem_resultado_conta_como_clique_e_registra_erro`,
  `test_kommo_debug_valores_verdadeiros_ligam`, `test_kommo_debug_outros_valores_nao_ligam`,
  `test_kommo_debug_ausente_nao_liga_e_merger_usa_a_funcao`;
  `tests/test_kommo_porta.py::test_screenshot_erro_nao_transitorio_propaga`.
- **Status:** **Implementado e testado.** A captura com `KOMMO_DEBUG` é uma imagem da tela; o quanto ela fica
  borrada depende de FR-024 (não é garantia).
- **Evidência:** `kommo.py:_JS_DIAGNOSTICO`, `KommoPage.diagnostico`, `KommoPage.screenshot`;
  `merger.py:Merger._diagnostico`, `debug_ligado`.

### FR-027 — Esquecer login salvo

- **Descrição:** o link "Esquecer login salvo" (desabilitado durante uma execução) pede confirmação (padrão "não") e
  apaga `data/profile/*`. Recusa se a pasta do perfil for link/junção ou estiver fora da raiz de dados; links internos
  são removidos sem seguir o destino; arquivos em uso (navegador do app aberto) geram erro claro.
- **Prioridade:** Média
- **Dependências:** FR-002
- **Critérios de aceitação:** conforme testes.
- **Testes relacionados:** `tests/test_paths.py::test_esquecer_login`, `test_esquecer_login_com_navegador_aberto`,
  `test_esquecer_login_recusa_link`, `test_dentro_da_raiz`;
  `tests/test_ui_integracao.py::test_esquecer_login_ok_e_vazio`,
  `test_esquecer_login_cancelado_e_bloqueado_rodando`, `test_esquecer_login_erro_mostra_mensagem`.
- **Status:** **Implementado e testado.**
- **Evidência:** `paths.py:esquecer_login`, `dentro_da_raiz`, `_eh_link`, `EsquecerLoginErro`;
  `ui.py:App.esquecer_login`.

---

## 7. Configuração e navegador

### FR-028 — Configuração persistente com escrita atômica

- **Descrição:** `data/config.json` guarda empresa, tipo, limite, último valor livre, privacidade, canal do navegador
  que funcionou, último total e última execução — sem senhas nem tokens. Escrita atômica (temporário na mesma pasta
  + `fsync` + `os.replace`, com até 5 tentativas se o antivírus segurar o arquivo). JSON corrompido é renomeado para
  `config.json.corrompido` e o app volta ao padrão com aviso. Chaves desconhecidas são descartadas; o nome antigo
  `blur` é migrado para `privacidade`. Tipos validados ao carregar (empresa=str, tipo∈{leads, contatos},
  limite=int≥0, privacidade=bool, limite_custom=int≥0|null, canal_navegador=str, ultimo_total=int≥0,
  ultima_execucao=str): campo inválido volta ao padrão com o mesmo aviso, sem impedir a janela de abrir.
- **Prioridade:** Média
- **Dependências:** FR-002, FR-003
- **Critérios de aceitação:** conforme testes.
- **Testes relacionados:** `tests/test_config.py::test_salvar_e_carregar`, `test_padrao_sem_empresa`,
  `test_limite_custom_e_canal`, `test_arquivo_corrompido_volta_ao_padrao`, `test_bytes_invalidos_em_utf8`,
  `test_migra_nome_antigo_da_opcao`, `test_escrita_atomica_nao_estraga_o_arquivo`,
  `test_salvar_nao_deixa_temporarios`, `test_pasta_nao_gravavel_nao_e_engolida`, `test_dados_ficam_na_raiz_de_dados`,
  `test_tipos_errados_voltam_ao_padrao_com_aviso`, `test_um_campo_invalido_nao_afeta_os_outros`,
  `test_valores_validos_nao_geram_aviso`.
- **Status:** **Implementado e testado.**
- **Evidência:** `config.py:carregar_detalhado`, `_gravar_atomico`, `salvar`, `_isolar_corrompido`, `_normalizar`,
  `_validar`.

### FR-029 — Seleção de navegador e perfil por canal

- **Descrição:** ordem de tentativa Chrome → Edge → Chromium do Playwright (Linux: Edge só se instalado). O canal que
  funcionou é lembrado e tentado primeiro; `KOMMO_BROWSER` força um canal (valor inválido = erro claro). Cada canal
  tem o próprio perfil (`data/profile/<canal>`). Perfil em uso/travado → para com mensagem clara, **sem** tentar outro
  navegador. Navegador não instalado → tenta o próximo. Abre com sandbox do Chromium ligado,
  `--disable-notifications`, `--deny-permission-prompts`, locale pt-BR. A interface mostra o navegador usado.
- **Prioridade:** Média
- **Dependências:** FR-002, FR-028
- **Critérios de aceitação:** conforme testes.
- **Testes relacionados:** `tests/test_browser.py` (19 testes, ex.: `test_abre_com_sandbox_args_e_perfil_por_canal`,
  `test_canais_padrao_por_so`, `test_canal_preferido_vai_primeiro`, `test_kommo_browser_forca_um_canal`,
  `test_kommo_browser_invalido`, `test_navegador_ausente_tenta_proximo_com_outro_perfil`,
  `test_trava_por_texto_nao_tenta_outro_canal`, `test_arquivo_de_trava_mais_falha_generica_nao_tenta_outro_canal`,
  `test_perfil_em_uso_windows_nao_chama_launch`, `test_nenhum_navegador`, `test_erro_que_nao_e_do_playwright_nao_e_engolido`,
  `test_playwright_browsers_path_so_no_windows_congelado`); `tests/test_paths.py::test_profile_dir_por_canal`;
  `tests/test_merger.py::test_sessao_playwright_init_script_canal_e_fecha`; `tests/test_ui_pura.py::test_nome_canal`.
- **Status:** **Implementado e testado** com stub do Playwright. A abertura real de Chrome/Edge no Windows é
  verificação manual; no Linux não foi testada.
- **Evidência:** `browser.py:abrir_contexto`, `canais_disponiveis`, `canais_padrao`, `perfil_em_uso`, `ARGS_NAVEGADOR`.

---

## 8. Modo texto, verificação e distribuição

### FR-030 — Modo texto (CLI)

- **Descrição:** `python main.py --cli <empresa> <leads|contatos> <limite> [--sem-privacidade] [--ensaio] [--sim]`.
  Imprime e grava cada linha de log, pergunta a confirmação (FR-008), trata Ctrl+C em dois níveis (FR-014), drena a
  fila até o fim e imprime o resumo. Com privacidade (padrão) terminal e log saem mascarados (FR-025). Códigos de
  saída: 0 = `limite`/`sem_duplicatas`/`ensaio` sem erros; 2 = `parado`/`forcado`/`recusado`/`sem_resposta`;
  64 = erro de uso (argumentos inválidos — EX_USAGE); 1 = qualquer outro caso (inclui terminar sem resumo).
- **Prioridade:** Média
- **Dependências:** FR-008, FR-014, FR-022
- **Critérios de aceitação:** conforme testes.
- **Testes relacionados:** `tests/test_cli.py` (11 funções de teste); `tests/test_main.py::test_cli_recebe_argv_sem_o_marcador`,
  `test_cli_help_real_sai_com_zero`.
- **Status:** **Implementado e testado** (com motor falso).
- **Evidência:** `cli.py:main`, `MOTIVOS_OK`, `MOTIVOS_PARADA`, `EX_USAGE`, `Parser`, `perguntar_confirmacao`,
  `limite_valido`.

### FR-031 — Verificação de privacidade do projeto e do build (fail-closed)

- **Descrição:** `scripts/verificar_privacidade.py` procura termos da máquina (usuário, computador, home, forma curta
  8.3, `git user.name/email`), `KOMMO_TERMOS_SENSIVEIS` e `--termo` em **todos** os arquivos como bytes (UTF-8 e
  UTF-16LE), dentro de zip/tar/gz aninhados, executáveis PyInstaller (CArchive + PYZ) e AppImage (via `unsquashfs`).
  Aponta pastas de dados do usuário no projeto ou ao lado do executável e artefatos fora de `dist/`. Qualquer coisa
  ilegível, sem termos ou formato não suportado é **erro** (código 1). Termos são mascarados na saída por padrão.
  Os scripts de build o rodam no fim e falham se ele falhar.
- **Prioridade:** Alta
- **Dependências:** —
- **Critérios de aceitação:** conforme os 26 testes.
- **Testes relacionados:** `tests/test_verificador.py` (26 testes, ex.: `test_sem_termos_falha`,
  `test_projeto_limpo_passa`, `test_zip_aninhado`, `test_exe_pyinstaller_com_pyz`,
  `test_exe_pyinstaller_truncado_falha`, `test_membro_zip_com_crc_errado_falha`, `test_formato_nao_suportado_falha`,
  `test_arquivo_ilegivel_falha`, `test_dados_usuario_e_artefato_fora_de_dist`, `test_onedir_inteira_e_dados_ao_lado_do_exe`,
  `test_saida_mascara_termos_por_padrao`, `test_pycache_no_projeto_nao_e_pulado`, `test_binario_utf16le`).
- **Status:** **Implementado e testado.** A varredura de AppImage depende de `unsquashfs` (sem ele = erro) e não
  foi exercitada num AppImage real.
- **Evidência:** `scripts/verificar_privacidade.py:verificar`, `Varredor`, `dados_usuario_no_projeto`, `main`.

### FR-032 — Build, empacotamento e checksums

- **Descrição:** `scripts/build_windows.ps1` gera, num `.venv` local instalado de `requirements-dev.lock`
  (`--require-hashes`), a pasta portátil PyInstaller *onedir* e o zip
  `dist/windows/KommoUnirDuplicatas-<versão>-win64.zip` + `SHA256SUMS.txt`, com arquivos temporários do PyInstaller
  fora do projeto; `-OneFile` (ou `build_exe.ps1`) gera o `.exe` único. `scripts/build_linux.sh` gera `.tar.gz`
  (+ AppImage opcional). `scripts/empacotar.py` cria zip/tar.gz determinísticos (ordem alfabética,
  `SOURCE_DATE_EPOCH`, permissões normalizadas) e o `SHA256SUMS`. Ambos os builds terminam com o verificador de
  privacidade (FR-031); no CI usam `--sem-termos-padrao` + termo-sentinela. O workflow `release.yml` monta um
  Release **rascunho** com SBOM e atestação.
- **Prioridade:** Média
- **Dependências:** FR-031, NFR de reprodutibilidade
- **Critérios de aceitação:**
  1. Build Windows termina com zip + `SHA256SUMS.txt` conferível (`sha256sum -c`).
  2. Verificador falhou → build falha e não publica.
  3. Dois builds do mesmo commit com o mesmo `SOURCE_DATE_EPOCH` geram zips com o mesmo hash (meta de
     reprodutibilidade).
- **Testes relacionados:** nenhum teste automatizado de `empacotar.py`, `build_windows.ps1`, `build_linux.sh` ou dos
  workflows. O verificador chamado no fim tem os testes de FR-031.
- **Status:** **Parcial.**
  - Windows: implementado **sem teste automatizado**; a execução do build no formato atual (onedir + zip) não foi
    confirmada nesta revisão (o único artefato presente em `dist/` é um `KommoUnirDuplicatas.exe` de 08/10/2026, do
    formato antigo de arquivo único). Reprodutibilidade byte a byte **não medida**.
  - Linux: **não validado** — `build_linux.sh` nunca rodou numa máquina Linux real (aviso no próprio script e em
    [packaging/linux/README.md](../../packaging/linux/README.md)).
  - CI/Release: **nenhum workflow foi executado no GitHub** ([ci-cd.md](../operations/ci-cd.md#5-o-que-não-foi-validado)).
- **Evidência:** `scripts/build_windows.ps1`, `scripts/build_linux.sh`, `scripts/empacotar.py`,
  `.github/workflows/release.yml`.

### FR-033 — Tolerância a erros inesperados na interface

- **Descrição:** exceção não tratada num callback do Tk é gravada no log (mascarada) e mostrada numa caixa única, sem
  derrubar a janela; falha ao exibir um evento, ao salvar preferências ou ao mostrar o resumo vira aviso no log; o
  consumo da fila é limitado a 500 eventos por ciclo de 150 ms e sempre se reagenda.
- **Prioridade:** Média
- **Dependências:** FR-023
- **Critérios de aceitação:** exceção num callback não fecha a janela e é registrada.
- **Testes relacionados:** `tests/test_ui_integracao.py::test_excecao_em_callback_nao_derruba_a_janela`;
  `tests/test_ui_pura.py::test_janela_abre_e_fecha`.
- **Status:** **Implementado e testado** (callback). Os demais caminhos de aviso (`_aviso_seguro`) não têm teste
  dedicado.
- **Evidência:** `ui.py:App.report_callback_exception`, `App._aviso_seguro`, `App.bombear`.

### FR-034 — Não encerrar por falso "navegador fechado" (troca de aba, correção T10)

- **Descrição:** se a aba que o motor acompanha for fechada ou substituída (ex.: login ou redirecionamento que abre
  outra aba), o app **adota outra aba aberta do mesmo contexto** do navegador — de preferência a mais recente de
  `*.kommo.com`, senão a mais recente — reaplica as configurações por aba (timeouts) e o reforço de privacidade,
  registra um aviso no log e continua. Sem outra aba, espera `GRACA_FECHAMENTO` (3 s, amostrando a cada 0,5 s) por
  uma aba nova antes de encerrar com `motivo="navegador_fechado"`. Também vale para a aba substituída durante a
  navegação inicial (`goto`). Todas as validações de conta/página/modal (FR-011) continuam valendo na aba adotada.
- **Prioridade:** Alta
- **Dependências:** FR-010, FR-011, FR-019
- **Critérios de aceitação:**
  1. Aba original fechada com outra aberta → o login continua sendo esperado na aba adotada e a execução segue.
  2. Aba nova que aparece dentro da tolerância → adotada.
  3. Todas as abas fechadas → `navegador_fechado` como aviso (sem união em andamento).
  4. Aba adotada de outra conta → nenhum clique em "Unir".
  5. Parada forçada durante a tolerância é atendida.
- **Testes relacionados:** `tests/test_merger.py::test_t10_aba_original_fechada_com_outra_aberta_continua_esperando_o_login`,
  `test_t10_aba_nova_aparece_logo_depois_dentro_da_tolerancia`, `test_t10_todas_as_abas_fechadas_encerra_com_aviso`,
  `test_t10_aba_adotada_de_outra_conta_nao_clica`, `test_t10_parada_forcada_durante_a_tolerancia`,
  `test_sessao_playwright_aba_substituida_no_goto_adota_e_segue`;
  `tests/test_kommo_porta.py::test_porta_tem_os_metodos_de_aba_do_contrato`, `test_sem_ctx_paginas_abertas_e_nao_adota`,
  `test_aba_atual_aberta_nao_troca`, `test_adota_a_aba_mais_recente_do_kommo_e_reaplica_config`,
  `test_adota_aba_de_fora_se_for_a_unica`, `test_todas_fechadas_ou_contexto_quebrado_nao_adota`;
  `tests/test_t10_troca_de_aba.py::test_aba_fechada_e_outra_aberta_no_contexto_e_adotada`,
  `test_todas_as_abas_fechadas_e_navegador_fechado` (Chromium headless real, sem Kommo).
- **Status:** **Implementado e testado** (código de 14/10/2026; simulador, stub e Chromium headless com HTML local).
  O cenário real que motivou a correção (login do Kommo trocando de aba) **não foi re-exercitado contra o Kommo
  real** nesta revisão.
- **Evidência:** `kommo.py:KommoPage.adotar_pagina`, `trocar_pagina`, `paginas_abertas`; `merger.py:Merger._checar_fechado`,
  `_adotar`, `_abrir_url`, `GRACA_FECHAMENTO`, `POLL_GRACA`.

---

## 9. Resumo de status

| Status | Requisitos |
|---|---|
| Implementado e testado | FR-002, FR-003, FR-004, FR-005, FR-006, FR-007, FR-008, FR-009, FR-010, FR-011, FR-012, FR-014, FR-015, FR-016, FR-017, FR-018, FR-019, FR-020, FR-021, FR-022, FR-023, FR-025 (só UI), FR-026, FR-027, FR-028, FR-029, FR-030, FR-031, FR-033, FR-034 |
| Implementado sem teste automatizado | FR-001 (scripts `iniciar.*`; o despacho de `__main__.py` é testado) |
| Parcial | FR-013 (texto de conclusão em Leads não confirmado no Kommo real), FR-024 (privacidade não é garantia; só fixture), FR-032 (build sem teste; Linux e CI não validados) |
| Pendente | — |

"Implementado e testado" refere-se a testes contra simuladores/fixtures. **Nenhum requisito foi re-verificado
contra o Kommo real nesta revisão** — ver o checklist manual em
[estrategia.md](../testing/estrategia.md#4-testes-manuais-antes-de-cada-release).

## 10. Fora de escopo

O que o app **não** faz, de propósito ou por limitação atual (conferido no código):

- **API do Kommo:** o app automatiza a interface web; não usa a API nem guarda tokens.
- **Outras entidades:** só Leads e Contatos (`kommo.TIPOS`); "Empresas" ou outras listas não são suportadas.
- **Outros domínios:** só `*.kommo.com` (`kommo.DOMINIO` fixo); `amocrm` e domínios próprios não.
- **Escolher como unir:** o app clica em "Unir esta duplicata" com a regra padrão do Kommo; não escolhe campos nem
  o registro principal, e **nunca** usa "Pular esta duplicata".
- **Desfazer uniões:** impossível — a união é irreversível no Kommo.
- **Pausar e retomar** uma execução, agendar execuções, rodar várias contas em paralelo ou rodar sem janela de
  navegador (*headless*): não implementados (o navegador abre sempre visível, `headless=False`).
- **Guardar senha** ou fazer login automático: o login é feito pelo usuário na janela do navegador; só os cookies do
  perfil persistem.
- **Telemetria, servidor próprio ou envio de dados a terceiros:** não existem (ver
  [../operations/slo.md](../operations/slo.md)).
- **Bloquear abas externas:** `browser.bloquear_navegacao_externa` existe, mas fica **desligado** em
  `abrir_contexto` (quebraria login OAuth, integrações e ajuda do Kommo).
- **macOS:** há ramos de código (fontes, mensagens), mas nenhum build nem teste para macOS.
- **Instalador** (MSI/assistente) e **atualização automática:** a distribuição é uma pasta portátil zipada.
- **Assinatura de código (Authenticode):** não existe (ver [../security/seguranca.md](../security/seguranca.md)).
