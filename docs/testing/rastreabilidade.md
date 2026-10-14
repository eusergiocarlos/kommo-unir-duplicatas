# Matriz de rastreabilidade

Liga cada requisito ([funcionais](../requirements/funcionais.md) e [não funcionais](../requirements/nao-funcionais.md))
aos testes automatizados que o verificam e aponta as lacunas. Nomes no formato `arquivo::função` (arquivos em
`tests/`); testes parametrizados aparecem uma vez. Conferido contra a suíte de 14/10/2026 (revisão T11): **453 testes, todos
passando**. Estratégia geral: [estrategia.md](estrategia.md).

Legenda da coluna **Cobertura**: **A** = automatizada (simulador/fixture/stub) · **M** = só manual ·
**—** = nenhuma.

## 1. Requisitos funcionais → testes

| Req. | Resumo | Testes automatizados | Cobertura | Lacunas |
|---|---|---|---|---|
| FR-001 | Execução do código-fonte (`iniciar.*`, `main.py`) | `test_main.py::test_sem_argumentos_abre_ui_e_propaga_codigo`, `test_cli_recebe_argv_sem_o_marcador`, `test_cli_sem_argumentos_extras`, `test_ajuda_nao_abre_ui`, `test_cli_help_real_sai_com_zero` | A (ponto de entrada) / M | `iniciar.bat` e `iniciar.sh` sem teste; `iniciar.sh` nunca executado |
| FR-002 | Modo portátil, `KOMMO_DATA_DIR` | `test_paths.py::test_portatil_codigo_fonte`, `test_portatil_frozen_com_espacos_e_acentos`, `test_kommo_data_dir_tem_precedencia`, `test_kommo_data_dir_relativo_e_relativo_ao_programa`, `test_independe_do_cwd`, `test_app_dir_codigo_fonte_e_a_raiz_do_repositorio`, `test_profile_dir_por_canal`; `test_config.py::test_dados_ficam_na_raiz_de_dados` | A | Executável real não exercitado |
| FR-003 | Pasta de dados não gravável | `test_paths.py::test_nao_gravavel_por_permissao`, `test_nao_gravavel_quando_escrita_real_falha`, `test_nao_gravavel_sem_mock`, `test_erro_nao_e_engolido_por_except_oserror`, `test_ensure_writable_nao_deixa_lixo`; `test_config.py::test_pasta_nao_gravavel_nao_e_engolida`; `test_logs.py::test_falha_de_pasta_nao_derruba`; `test_ui_integracao.py::test_main_data_dir_nao_gravavel_mostra_erro_e_nao_abre` | A | "Arquivos de Programas" real: manual |
| FR-004 | Subdomínio | `test_kommo.py::test_normalizar_empresa`; `test_config.py::test_padrao_sem_empresa` | A | Mensagens da UI para empresa vazia/inválida sem teste |
| FR-005 | Leads × Contatos | `test_kommo.py::test_montar_url`, `test_seletores_fonte_unica_e_aliases`; `test_kommo_js.py::test_clica_item_do_tipo_certo`, `test_nao_clica_item_de_outra_entidade`, `test_nao_clica_item_invisivel`; `test_kommo_porta.py::test_clicar_item_passa_tipo_e_seletores`, `test_clicar_item_tipo_desconhecido_nem_avalia`; `test_merger.py::test_tipo_errado_aborta_sem_abrir_nem_clicar`, `test_job_invalido_nao_abre_sessao`, `test_validacoes_puras` | A | HTML real do Kommo |
| FR-006 | Quantidade e validação | `test_limite.py` (todos); `test_ui_integracao.py::test_limite_custom_persistido_e_restaurado`; `test_cli.py::test_limite_invalido_rejeitado`, `test_erros_de_uso_saem_com_64` | A | — |
| FR-007 | Limite por cliques | `test_merger.py::test_caminho_feliz_para_exatamente_no_limite`, `test_leads_sem_texto_concluida_tudo_incerto_e_limite_por_cliques`, `test_uniao_sem_resultado_conta_como_clique_e_registra_erro`, `test_clique_que_falha_conta_e_tres_falhas_param`; invariante `checar_seguranca` | A | — |
| FR-008 | Confirmação da conta | `test_merger.py::test_confirmacao_sem_resposta_nao_clica`, `test_confirmacao_recusada_nao_clica`, `test_confirmacao_aceita_segue`, `test_parar_durante_a_confirmacao`; `test_ui_integracao.py::test_confirmacao_*` (12 funções), `test_iniciar_cria_job_sem_pergunta_previa`; `test_ui_pura.py::test_confirmacao_*`, `test_regra_exige_digitar_e_palavra`; `test_cli.py::test_pergunta_e_recusa`, `test_confirmacao_eof_e_nao`, `test_sim_confirma_sem_perguntar_e_imprime_resumo`, `test_pergunta_m_mostra_a_conta_so_no_terminal` | A | — |
| FR-009 | Modo ensaio | `test_merger.py::test_ensaio_nao_clica_em_unir`, `test_ensaio_tambem_pede_confirmacao_quando_ligada`; `test_ui_integracao.py::test_ensaio_muda_botao_e_job`, `test_resumo_do_ensaio`, `test_confirmacao_ensaio_botao`; `test_ui_pura.py::test_resumo_ensaio`, `test_confirmacao_ensaio`; `test_cli.py::test_pergunta_e_aceita_com_ensaio` | A + M | Ensaio no Kommo real: manual |
| FR-010 | Espera do login | `test_merger.py::test_login_espera_com_reavisos_e_continua`, `test_login_teto_da_erro_claro`, `test_login_hostname_por_substring_nao_vale`, `test_navegador_fechado_durante_o_login_mensagem_amigavel`, `test_parar_antes_do_login`; `test_kommo.py::test_hostname_confere` | A + M | Login real (OAuth, 2FA) |
| FR-011 | Validação antes de cada clique | `test_merger.py::test_hostname_muda_antes_do_clique_aborta`, `test_modal_que_nao_e_de_duplicatas_aborta`, `test_tipo_errado_aborta_sem_abrir_nem_clicar`, `test_validacoes_puras` | A | — |
| FR-012 | Laço de uniões | `test_merger.py::test_caminho_feliz_para_exatamente_no_limite`, `test_sem_recarga_proximo_grupo_direto`, `test_todas_ate_acabar_conclui_sem_duplicatas`, `test_incerto_reconfere_estado_antes_de_reclicar`, `test_uniao_sem_resultado_conta_como_clique_e_registra_erro`, `test_clique_que_falha_conta_e_tres_falhas_param`; `test_fluxo.py::test_sequencia_com_fake` | A + M | Kommo real só manual |
| FR-013 | Regra de confirmação (`avaliar_uniao`) | `test_fluxo.py::test_avaliar_uniao`, `test_progresso_concluido`, `test_sequencia_com_fake`, `test_fake_implementa_porta`; `test_merger.py::test_leads_sem_texto_concluida_tudo_incerto_e_limite_por_cliques`; `test_kommo_js.py::test_estado_progresso_e_concluido` | A | **Texto de conclusão em Leads não confirmado no Kommo real** |
| FR-014 | Parada em dois níveis | `test_merger.py::test_parar_no_meio_da_uniao_espera_o_resultado`, `test_segundo_pedido_forca_saida_imediata`, `test_parar_durante_a_busca_sai_sem_clicar`, `test_ui_setando_o_event_direto_equivale_a_parar`, `test_solicitar_parada_duas_vezes_forca`, `test_thread_nao_daemon_e_parar_e_aguardar`; `test_ui_integracao.py::test_parar_dois_niveis_e_fim_reabilita`; `test_cli.py::test_ctrl_c_pede_parada_e_drena_a_fila` | A | — |
| FR-015 | Fechamento seguro da janela | `test_ui_integracao.py::test_fechar_sem_thread_fecha_direto`, `test_fechar_com_thread_e_resposta_nao_mantem_tudo`, `test_fechar_com_thread_espera_ela_terminar`, `test_fechar_forca_depois_do_teto`, `test_fechar_thread_travada_avisa_e_nao_destroi` | A | Com navegador real: manual |
| FR-016 | Fechamento seguro do modal | invariante `checar_seguranca`; `test_merger.py::test_parar_no_meio_da_uniao_espera_o_resultado`; `test_kommo_porta.py::test_cancelar_modal_so_clica_se_existir`, `test_fechar_modal_ordem_x_cancelar_escape`; `test_kommo_js.py::test_clicar_unir_e_cancelar`, `test_fechar_modal_usa_o_x` | A | — |
| FR-017 | Busca, "Algo deu errado", reabertura | `test_merger.py::test_algo_deu_errado_tenta_reabre_uma_vez_e_falha`, `test_erro_some_e_volta_ao_normal`, `test_houve_erro_persiste_durante_o_carregamento`, `test_pagina_recarrega_durante_a_uniao_reabre_pelo_menu`; `test_kommo_js.py::test_estado_detecta_erro_do_modal` | A | Kommo real só manual |
| FR-018 | Sem duplicatas × sessão expirada | `test_merger.py::test_sessao_expirada_nao_vira_concluido`, `test_lista_sem_nenhuma_duplicata`, `test_todas_ate_acabar_conclui_sem_duplicatas` | A | Expiração real |
| FR-019 | Navegador fechado/indisponível, erros transitórios | `test_merger.py::test_navegador_fechado_no_meio_da_uniao`, `test_navegador_fechado_durante_o_login_mensagem_amigavel`, `test_falha_ao_abrir_o_navegador_ainda_emite_fim`, `test_excecao_no_meio_da_uniao_preserva_contadores_e_fecha`, `test_excecao_do_roteiro_do_fakekommo`, `test_sessao_playwright_fecha_mesmo_com_excecao_e_navegador_fechado`; `test_kommo_porta.py::test_estado_navegacao_vira_navegou`, `test_estado_timeout_do_playwright_vira_navegou`, `test_estado_erro_desconhecido_propaga`, `test_acoes_com_navegacao_devolvem_valor_seguro`, `test_cliques_com_timeout_e_falha_vira_false`; `test_kommo_js.py::test_timeout_do_evaluate`, `test_clicar_unir_invisivel_falha_rapido`; `test_ui_integracao.py::test_kommopage_esta_fechada` | A | — |
| FR-020 | Total de grupos | `test_kommo.py::test_parse_total`; `test_ui_pura.py::test_deve_registrar`; `test_ui_integracao.py::test_fim_registra_execucao_quando_motivo_normal` | A | — |
| FR-021 | Progresso ao vivo | `test_ui_pura.py::test_texto_progresso`, `test_texto_progresso_com_incertas`, `test_texto_progresso_sem_total_e_todas`, `test_fracao_barra_usa_cliques` | A + M | Texto real do Kommo |
| FR-022 | Resumo final | invariante `checar_seguranca`; `test_ui_pura.py::test_resumo_*`, `test_texto_detalhes`, `test_texto_resumo_conta`; `test_cli.py::test_sim_confirma_sem_perguntar_e_imprime_resumo` | A | Rede de segurança "thread morreu sem FimEvt" (`App.bombear`) sem teste |
| FR-023 | Log com data/hora e rotação | `test_logs.py` (8) | A | — |
| FR-024 | Modo privacidade no navegador | `test_privacy_js.py` (11); `test_privacy.py` (13); `test_merger.py::test_privacidade_reforco_espacado_e_desligada_sem_chamadas`, `test_sessao_playwright_init_script_canal_e_fecha`, `test_sessao_playwright_config_quebrada_nao_derruba` | A (fixture) + M | **Kommo real ao vivo**; *push* do service worker; barra de endereço (impossível) |
| FR-025 | Privacidade na janela | `test_ui_pura.py::test_mascarar_*`, `test_mascara_nao_revela_tamanho`, `test_texto_inicio_com_privacidade_e_ensaio`; `test_ui_integracao.py::test_logs_do_motor_sao_mascarados`, `test_confirmacao_privacidade_mascara_e_mostrar_conta`; `test_cli.py::test_privacidade_padrao_mascara_terminal_e_log`, `test_sem_privacidade_mostra_conta_e_totais`, `test_pergunta_m_mostra_a_conta_so_no_terminal`, `test_confirmacao_com_privacidade_mascara_host_e_total` | A | — |
| FR-026 | Diagnóstico sem PII | `test_kommo_js.py::test_diagnostico_sem_pii`; `test_merger.py::test_screenshot_so_com_debug`, `test_uniao_sem_resultado_conta_como_clique_e_registra_erro`, `test_kommo_debug_*` (3); `test_kommo_porta.py::test_screenshot_erro_nao_transitorio_propaga` | A | Conteúdo da captura `KOMMO_DEBUG` |
| FR-027 | Esquecer login | `test_paths.py::test_esquecer_login`, `test_esquecer_login_com_navegador_aberto`, `test_esquecer_login_recusa_link`, `test_dentro_da_raiz`; `test_ui_integracao.py::test_esquecer_login_ok_e_vazio`, `test_esquecer_login_cancelado_e_bloqueado_rodando`, `test_esquecer_login_erro_mostra_mensagem` | A | — |
| FR-028 | Config atômica e tipos validados | `test_config.py` (21, inclui `test_tipos_errados_voltam_ao_padrao_com_aviso`) | A | — |
| FR-029 | Navegador e perfil por canal | `test_browser.py` (19); `test_paths.py::test_profile_dir_por_canal`; `test_merger.py::test_sessao_playwright_init_script_canal_e_fecha`; `test_ui_pura.py::test_nome_canal` | A (stub) + M | Abertura real de Chrome/Edge; Linux |
| FR-030 | Modo texto | `test_cli.py` (16); `test_main.py::test_cli_recebe_argv_sem_o_marcador`, `test_cli_help_real_sai_com_zero` | A | — |
| FR-031 | Verificador de privacidade | `test_verificador.py` (26) | A | AppImage real (`unsquashfs`) |
| FR-032 | Build, empacotamento, checksums | — | M | `empacotar.py`, `build_windows.ps1`, `build_linux.sh`, workflows: **sem teste**; Linux e CI **não validados**; reprodutibilidade não medida |
| FR-033 | Erros inesperados na UI | `test_ui_integracao.py::test_excecao_em_callback_nao_derruba_a_janela`; `test_ui_pura.py::test_janela_abre_e_fecha` | A | Demais caminhos de `_aviso_seguro` |
| FR-034 | Não encerrar por falso "navegador fechado" (troca de aba, T10) | `test_merger.py::test_t10_aba_original_fechada_com_outra_aberta_continua_esperando_o_login`, `test_t10_aba_nova_aparece_logo_depois_dentro_da_tolerancia`, `test_t10_todas_as_abas_fechadas_encerra_com_aviso`, `test_t10_aba_adotada_de_outra_conta_nao_clica`, `test_t10_parada_forcada_durante_a_tolerancia`, `test_sessao_playwright_aba_substituida_no_goto_adota_e_segue`; `test_kommo_porta.py::test_porta_tem_os_metodos_de_aba_do_contrato`, `test_sem_ctx_paginas_abertas_e_nao_adota`, `test_aba_atual_aberta_nao_troca`, `test_adota_a_aba_mais_recente_do_kommo_e_reaplica_config`, `test_adota_aba_de_fora_se_for_a_unica`, `test_todas_fechadas_ou_contexto_quebrado_nao_adota`; `test_t10_troca_de_aba.py::test_aba_fechada_e_outra_aberta_no_contexto_e_adotada`, `test_todas_as_abas_fechadas_e_navegador_fechado` | A + M | Login real do Kommo trocando de aba não re-exercitado |

## 2. Requisitos não funcionais → testes

| Req. | Resumo | Testes / verificação | Cobertura | Lacunas |
|---|---|---|---|---|
| NFR-001 | Nenhum clique fora da conta/lista | `test_merger.py::test_hostname_muda_antes_do_clique_aborta`, `test_login_hostname_por_substring_nao_vale`, `test_modal_que_nao_e_de_duplicatas_aborta`; `test_kommo.py::test_hostname_confere` | A | — |
| NFR-002 | Sandbox e sem prompts | `test_browser.py::test_abre_com_sandbox_args_e_perfil_por_canal` | A (argumentos) | Efeito real de `--disable-notifications` sobre *push* |
| NFR-003 | Perfil por canal | `test_paths.py::test_profile_dir_por_canal`; `test_browser.py::test_perfil_em_uso_windows_nao_chama_launch`, `test_trava_por_texto_nao_tenta_outro_canal`, `test_navegador_ausente_tenta_proximo_com_outro_perfil` | A | — |
| NFR-004 | Sem segredos | `test_verificador.py` (26); `detect-secrets` no CI | A + CI | CI nunca executado no GitHub |
| NFR-005 | Cadeia de suprimentos | CI (`pip-audit`, SBOM, atestação) | CI | CI nunca executado; actions por *major* |
| NFR-006 | Nada sai da máquina | inspeção do código | M | Sem teste de rede |
| NFR-007 | Logs/diagnóstico sem PII | `test_kommo_js.py::test_diagnostico_sem_pii`; `test_logs.py`; `test_ui_integracao.py::test_logs_do_motor_sao_mascarados`; `test_cli.py::test_privacidade_padrao_mascara_terminal_e_log` | A | Caminhos locais no log |
| NFR-008 | Privacidade em tela | `test_privacy_js.py`, `test_privacy.py` | A (fixture) + M | Kommo real |
| NFR-009 | Dados sob controle do usuário | `test_paths.py::test_esquecer_login*`; `test_logs.py::test_limpar_antigos` | A | — |
| NFR-010 | Custo do modo privacidade | `test_privacy_js.py::test_f_desempenho_5000_linhas`, `test_b_elemento_dinamico_marcado_em_ms` (`-s`) | A (correção) | **Sem asserção de tempo** |
| NFR-011 | Sobrecarga por união | `test_merger.py::test_privacidade_reforco_espacado_e_desligada_sem_chamadas` | A parcial | Tempo real por união não re-medido |
| NFR-012 | UI responsiva | inspeção | M | Sem medição |
| NFR-013 | Tempos-limite | `test_merger.py::test_login_teto_da_erro_claro`, `test_confirmacao_sem_resposta_nao_clica`, `test_uniao_sem_resultado_conta_como_clique_e_registra_erro`; `test_kommo_js.py::test_timeout_do_evaluate`; `test_ui_integracao.py::test_fechar_forca_depois_do_teto` | A | — |
| NFR-014 | Sistemas operacionais | suíte no Windows 11 | A (Win 11) | Windows 10, Linux não testados |
| NFR-015 | Python/navegadores | suíte em Python 3.14.6 | A (3.14) | 3.10–3.13 não verificados |
| NFR-016 | Portabilidade | `test_paths.py::test_portatil_frozen_com_espacos_e_acentos`, `test_independe_do_cwd` | A | — |
| NFR-017 | Manutenibilidade | `test_kommo.py::test_seletores_fonte_unica_e_aliases`; `test_privacy.py::test_seletores_do_processo_vem_de_kommo_sem_ciclo`, `test_selectores_do_processo_sem_duplicacao`; `ruff check` (CI) | A | — (`ruff check .` 0.17.0 limpo na revisão T11) |
| NFR-018 | Testabilidade | 453 testes | A | Cobertura configurada (pytest-cov no lock, CI), mas nenhum número medido ainda |
| NFR-019 | Reprodutibilidade | — | — | Hash byte a byte nunca comparado |
| NFR-020 | Teclado e foco | `test_ui_integracao.py::test_confirmacao_esc_e_enter_cancelam`, `test_confirmacao_exige_digitar_unir` | A parcial | Leitor de tela, contraste, alta DPI não auditados |
| NFR-021 | Mensagens | `test_browser.py::test_mensagens_por_so`; `test_limite.py::test_invalidos_levantam_com_mensagem`; `checar_seguranca` (sem Traceback) | A | — |
| NFR-022 | Janela cabe na tela | `test_ui_pura.py::test_geometria_cabe_na_tela`, `test_geometria_tela_grande_mantem_tamanho_original`, `test_escolher_fontes` | A | — |
| NFR-023 | Instalação fácil | — | M | SmartScreen/antivírus |
| NFR-024 | Observabilidade | `test_logs.py`; `test_merger.py::test_screenshot_so_com_debug` | A | — |
| NFR-025 | Recuperação | `test_merger.py::test_algo_deu_errado_tenta_reabre_uma_vez_e_falha`, `test_erro_some_e_volta_ao_normal`, `test_pagina_recarrega_durante_a_uniao_reabre_pelo_menu`; `test_config.py::test_arquivo_corrompido_volta_ao_padrao` | A | — |
| NFR-026 | Integridade das uniões | invariante `checar_seguranca` (cenários de `test_merger.py`) | A | Fidelidade do simulador ao Kommo real |
| NFR-027 | Integridade de arquivos | `test_config.py::test_escrita_atomica_nao_estraga_o_arquivo`, `test_salvar_nao_deixa_temporarios` | A | `empacotar.py` sem teste |
| NFR-028 | Ciclo de vida | `test_merger.py::test_thread_nao_daemon_e_parar_e_aguardar`, `test_falha_ao_abrir_o_navegador_ainda_emite_fim`; `test_ui_integracao.py::test_fechar_thread_travada_avisa_e_nao_destroi` | A | "thread sem FimEvt" na UI |

## 3. Testes que não mapeiam para um requisito específico

Todo arquivo de teste mapeia para ao menos um requisito acima. Testes de apoio sem requisito próprio:
`test_fluxo.py::test_fake_implementa_porta` e `test_kommo_porta.py::test_kommopage_implementa_porta` (garantem que
o falso e a implementação real seguem a mesma porta `PortaKommo`) e `test_merger.py::test_eventos_compativeis_com_a_ui`
(compatibilidade dos eventos entre motor e UI).

## 4. Lacunas priorizadas

| # | Lacuna | Requisitos | Sugestão |
|---|---|---|---|
| 1 | Correção T10 implementada, mas não exercitada no login real do Kommo | FR-034 | Item 4.2 do checklist manual (login que abre outra aba) |
| 2 | Texto de conclusão em Leads não confirmado no Kommo real | FR-013 | Item 4.3 do checklist manual; registrar no `KOMMO_DOM.md` |
| 3 | Build, empacotamento e workflows sem teste; CI nunca executado | FR-032, NFR-004, NFR-005, NFR-019 | Rodar o CI no GitHub; teste de `empacotar.py` (zip determinístico) |
| 4 | Linux e Windows 10 não testados | NFR-014 | Matriz do CI + checklist 4.7 |
| 5 | ~~CLI não mascara o log~~ — resolvido na T11 (`mascara.py`, `tests/test_cli.py`) | FR-025, NFR-007 | — |
| 6 | Cobertura configurada mas sem número medido | NFR-018 | Rodar o CI (publica `coverage.xml`) e, se quiser, definir `--cov-fail-under` |
| 7 | Metas de desempenho sem asserção | NFR-010 | Asserção com folga larga (ex.: observer < 1 s) para pegar regressões grosseiras |
| 8 | Acessibilidade não auditada | NFR-020 | Auditoria com leitor de tela e contraste |
