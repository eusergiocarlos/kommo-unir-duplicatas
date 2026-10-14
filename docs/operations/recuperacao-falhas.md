# Recuperação de falhas

Sintoma → causa provável → ação. Mensagens entre aspas são as reais do código. Antes de qualquer ação, lembre:
**uniões feitas não podem ser desfeitas**; o que o app chama de "não confirmada" pode ter sido feita ou não.

Veja também: [jornadas](../architecture/jornadas.md) · [execução](execucao.md) · [instalação](instalacao.md) ·
[modelo de dados](../architecture/modelo-de-dados.md).

## Tabela rápida

| Sintoma | Causa provável | Ação |
|---|---|---|
| Caixa "… — pasta de dados": "Não consigo gravar na pasta de dados do programa" e a janela não abre | app em pasta protegida (Program Files), pendrive/rede somente leitura, sem permissão | mover a pasta do programa para Documentos/Área de Trabalho **ou** definir `KOMMO_DATA_DIR` para uma pasta gravável |
| "O perfil do app para o navegador '…' parece estar em uso ou travado" | janela do navegador do app ainda aberta, outra instância do app, ou navegador fechado de forma anormal | fechar a janela do navegador do app e outras execuções; conferir no Gerenciador de Tarefas processos `chrome.exe`/`msedge.exe` com o perfil do app; persistindo, "Esquecer login salvo" (novo login) |
| "Não consegui abrir um navegador. Instale o Google Chrome ou o Microsoft Edge…" | nenhum Chrome/Edge/Chromium disponível | instalar Chrome ou Edge; código-fonte: `python -m playwright install chromium` |
| "KOMMO_BROWSER='…' não é válido" | variável com valor errado | usar `chrome`, `msedge` ou `chromium`, ou remover a variável |
| Pede login de novo toda vez / "perdeu o login" | trocou de navegador (outro canal = outro perfil), `KOMMO_BROWSER` mudou, `data\profile\` apagado, sessão expirada no Kommo, versão nova extraída sem copiar `data\` | logar de novo; para manter, copiar `data\` da versão antiga ([instalação §1.6](instalacao.md#16-atualizar)) |
| "O login no Kommo não foi confirmado em 10 min" | não logou, logou em **outra** conta, ou subdomínio digitado errado | conferir o subdomínio e a conta; iniciar de novo |
| O Chrome/aba fecha antes de eu logar | ver [seção própria](#o-chrome-fecha-antes-de-eu-logar) | — |
| "O arquivo de configuração estava corrompido e foi guardado em …config.json.corrompido" | `config.json` inválido (edição manual, disco cheio, desligamento) | nada a fazer: o app voltou ao padrão; apague o `.corrompido` quando quiser |
| "O arquivo de configuração … tem valor inválido em: …. Usando o padrão nesses campos." (no log) | `config.json` editado à mão com tipo errado (ex.: `"limite": "abc"`, `"tipo": "pedidos"`) | nada a fazer: só os campos citados voltaram ao padrão e a janela abre normalmente; corrija o arquivo ou escolha de novo na janela |
| "Procurando duplicatas…" e depois "A busca de duplicatas não terminou em 90s (modal aberto sem o botão 'Unir')" | Kommo lento ou mudança de HTML | tentar de novo mais tarde; se repetir, ver a linha `Diagnóstico (busca_travado)` e [seletores](#seletores-quebrados) |
| "O Kommo continua mostrando 'Algo deu errado'. Tente de novo em alguns minutos." | erro intermitente do Kommo na busca (Leads, busca longa) | esperar alguns minutos e reiniciar |
| "Não encontrei o item 'Localizar duplicatas' no menu (⋯) da lista." / "Botão de menu (⋯) não encontrado" | sem permissão no Kommo para o recurso, ou HTML mudou | conferir manualmente no Kommo se o item existe para o seu usuário; senão [seletores](#seletores-quebrados) |
| "A sessão do Kommo parece ter expirado ou a página foi redirecionada…" | sessão caiu, logout, navegação manual na janela do app | logar de novo e reiniciar; não usar a janela do navegador do app durante a execução |
| "… Encerrado por segurança, sem unir." | aba em outra conta/página ou modal diferente | conferir conta e lista; nada foi clicado |
| Resumo com "N não confirmada(s) — confira no Kommo" | o Kommo não mostrou o texto de conclusão (comum em Leads — não validado), erro durante a união ou parada forçada | [conferir no Kommo](#união-não-confirmada-como-conferir) |
| "Parando após 3 uniões seguidas sem resultado." | uniões sem resultado em 120 s, cliques que falharam ou erro do Kommo seguidos | conferir no Kommo; ver `Diagnóstico (uniao_sem_resultado)` no log; tentar com limite pequeno |
| PARAR "não para" | a união em andamento ainda não terminou (até 120 s) | aguardar ou clicar **FORÇAR PARADA** e depois conferir a última união |
| Janela "Encerrando…" não fecha | thread ainda viva (navegador travado) | após ~170 s o app pede para fechar a janela do navegador aberta pelo app; em último caso encerrar no Gerenciador de Tarefas |
| Navegador do app continua aberto após o app sumir (órfão) | processo encerrado à força (Gerenciador de Tarefas, queda) | fechar a janela do navegador; se o próximo início acusar perfil em uso, ver a linha do perfil travado |
| "O processo terminou sem enviar o resumo — confira o log." | thread morreu sem `FimEvt` (não esperado) | ver o log do dia; relatar com o trecho (mascarado) |
| Antivírus apagou/bloqueou o `.exe` ou arquivos de `_internal\` | falso positivo de executável PyInstaller sem assinatura | conferir SHA-256 do zip, restaurar a pasta, enviar o arquivo para análise do fornecedor do antivírus |
| SmartScreen "O Windows protegeu o computador" | executável sem assinatura de código | só prosseguir se o SHA-256 conferir ([instalação §1.5](instalacao.md#15-smartscreen-e-antivírus)) |
| "Não foi possível esquecer o login: …" | navegador do app aberto (arquivos em uso) | fechar o navegador do app e repetir; ou apagar `data\profile\` com o app fechado |
| Log não é gravado (linhas só na tela) | pasta `data\logs\` sem escrita ou disco cheio | liberar espaço/permissão; a execução segue normalmente |
| Algo apareceu sem borrão na gravação | tela não mapeada, barra de endereço, notificação de *push* | não publicar; acrescentar o seletor em `privacy.SELETORES` e em [KOMMO_DOM.md](../KOMMO_DOM.md) |

## O Chrome fecha antes de eu logar

**Sintoma:** durante o login a janela/aba do Kommo some (por exemplo, o login abre outra aba ou redireciona) e o
app encerra com "O navegador foi fechado — execução encerrada." (motivo `navegador_fechado`).

**Causa (antes da correção T10):** o motor acompanhava **apenas a aba que abriu**; se ela fechasse, encerrava —
mesmo com outras abas do mesmo navegador abertas (falso "navegador fechado").

**Comportamento atual (correção T10, já no código):** quando a aba acompanhada fecha, `KommoPage.adotar_pagina()`
passa a usar outra aba aberta do mesmo contexto (preferindo a mais recente em `*.kommo.com`) e o log mostra
"A aba do Kommo foi fechada ou substituída; o app passou a acompanhar a outra aba aberta (…)." O app só encerra
quando **não resta nenhuma aba** no contexto, depois de uma tolerância de 3 s (`GRACA_FECHAMENTO`). Na
abertura da lista (`_abrir_url`), uma aba substituída também é adotada uma vez antes de desistir com "O navegador foi
fechado antes de abrir o Kommo." Coberto por testes com falsos (`tests/test_t10_troca_de_aba.py`); **não validado**
com o login real do Kommo.

**Se ainda acontecer:**

1. Confira se você fechou a **última** janela do navegador do app (aí o encerramento é correto) — mantenha-a aberta
   até o login terminar.
2. Inicie de novo: se o login chegou a ser concluído em outra aba, o perfil já está logado e a execução segue direto.
3. Prefira o login por e-mail/senha na própria aba a provedores que abrem janelas; persistindo, "Esquecer login
   salvo" e repetir. Relate com o trecho do log (mascarado).

## União não confirmada: como conferir

1. No Kommo (fora do app ou com o app parado), abra a lista do mesmo tipo → menu "⋯" → **"Localizar duplicatas"**.
2. Compare o total "… N de TOTAL" com o do início (log: "Total de grupos de duplicatas informado pelo Kommo: …";
   em Leads costuma aparecer "muitas", e aí não há número para comparar).
3. Abra os registros envolvidos (se você os conhece) e veja se foram mesclados.
4. Rodar o app de novo é seguro: ele trabalha sobre o que o Kommo mostrar como restante e respeita o novo limite.

## Seletores quebrados

Sintomas: menu/item não encontrado, busca "travada", uniões sempre "sem resultado". O log traz linhas
`Diagnóstico (<rótulo>): menu_mais: 0 encontrados, 0 visíveis | …` (estrutural, sem dados de clientes). Com
`KOMMO_DEBUG=1`, uma captura vai para `data\debug\<rótulo>.png` (**com privacidade desligada contém dados de
clientes** — apague depois). Correção: [arquitetura §15](../architecture/arquitetura.md#15-como-evoluir) e
[KOMMO_DOM.md](../KOMMO_DOM.md).

## Limpeza de emergência

Se o computador ou a pasta foi exposto: feche o app e o navegador do app; apague `data\profile\` (cookies da
sessão), `data\debug\` e `data\logs\`; troque a senha do Kommo e encerre as sessões ativas pela própria conta do
Kommo, se disponível. Ver [segurança](../security/seguranca.md).
