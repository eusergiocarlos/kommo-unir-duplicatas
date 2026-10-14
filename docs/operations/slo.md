# Níveis de serviço: SLA, SLO e métricas internas

Este documento responde a uma pergunta direta — **o Kommo — Unir Duplicatas tem SLA?** — e define as metas de
qualidade que fazem sentido para um aplicativo local, com fórmula, fonte de dados e o que fazer quando a meta não
é cumprida.

Relacionados: [requisitos não funcionais](../requirements/nao-funcionais.md) ·
[requisitos funcionais](../requirements/funcionais.md) · [segurança](../security/seguranca.md) ·
[recuperação de falhas](recuperacao-falhas.md) · [execução](execucao.md).

## 1. Conclusão: não há SLA

**Não existe SLA (Service Level Agreement) para este projeto, e não faz sentido criar um.** Motivos:

| Pergunta | Resposta para este app |
|---|---|
| Há um serviço operado por alguém? | Não. É um programa de desktop que roda na máquina de quem usa; não há servidor, API própria nem plantão. |
| Há um contrato entre fornecedor e cliente? | Não. Projeto independente, distribuído como pasta portátil; a licença (MIT, ainda "a confirmar") exclui garantias. |
| Quem controla a disponibilidade? | O **Kommo** (serviço de terceiro, sem vínculo com o projeto), a internet e o computador do usuário. O app não tem como prometer o tempo de resposta do Kommo. |
| Há quem medir em produção? | Não. O app **não tem telemetria** (de propósito, ver §5). Não há como o projeto observar execuções de terceiros. |

O que existe e **não** é SLA:

- Os **prazos-alvo de resposta a vulnerabilidades** do [SECURITY.md](../../SECURITY.md) (recebimento em até 7 dias,
  triagem em até 14 dias) são metas de boa-fé de um projeto mantido por voluntários — o próprio documento diz
  "não um SLA".
- As **metas internas** (SLO) abaixo são critérios de qualidade para decidir se uma versão está boa, medidos pelo
  próprio usuário a partir dos logs locais.

## 2. Vocabulário usado aqui

| Termo | Neste projeto |
|---|---|
| **SLA** | Compromisso contratual com penalidade. **Não existe.** |
| **SLO** (objetivo interno) | Meta de qualidade de uma versão, medida sobre os logs locais numa janela de execuções. Serve para decidir "esta versão está pronta?" e "o Kommo mudou?". Sem penalidade. Todos os valores abaixo são **propostas a validar** — não há ainda uma linha de base medida em produção. |
| **SLI** (indicador) | A fórmula que mede o SLO, calculada a partir das linhas do log (`data/logs/AAAA-MM-DD.log`) ou dos campos do `FimEvt`. |
| **Métrica interna** | Número útil para diagnóstico, sem meta (ex.: quantos "Tentar novamente" por execução). |

## 3. De onde vêm os dados

### 3.1 `FimEvt` (resumo de cada execução)

Toda execução termina com exatamente um `FimEvt` (`src/kommo_duplicatas/merger.py`), com os campos:

| Campo | Significado |
|---|---|
| `confirmadas` (= `feitos`) | uniões confirmadas pelo texto de conclusão do Kommo |
| `incertas` | cliques em "Unir" sem confirmação ("não confirmadas") |
| `cliques` | cliques em "Unir" disparados (`confirmadas + incertas`) |
| `erros`, `avisos` | linhas de log de nível erro/aviso emitidas pelo motor |
| `segundos` | duração da execução (relógio monotônico) |
| `total` | grupos de duplicatas informados pelo Kommo (0 = "muitas"/não informado) |
| `motivo` | um dos 14 códigos de `MOTIVOS` (`limite`, `sem_duplicatas`, `parado`, `forcado`, `ensaio`, `recusado`, `sem_resposta`, `sessao_expirada`, `validacao`, `login_timeout`, `navegador_fechado`, `navegador_indisponivel`, `falhas`, `erro`) |

O `FimEvt` **não é gravado em arquivo** como estrutura. O que fica em disco é a linha de log que o motor emite junto
com ele (e `ultimo_total`/`ultima_execucao` em `config.json` para motivos normais).

### 3.2 Linhas do log que alimentam os SLIs

Formato de cada linha (`logs.formatar`): `[dd/mm/AAAA HH:MM:SS] NIVEL mensagem`, com `NIVEL` ∈ `ERRO  `, `AVISO `,
`OK    ` ou seis espaços (info). Linhas relevantes, como o código as escreve:

| Evento | Mensagem (início) | Origem |
|---|---|---|
| Início de execução (só janela) | `Iniciando: <empresa>.kommo.com · <Tipo> · limite <n>` | `ui.py:texto_inicio` |
| Busca iniciada | `Procurando duplicatas — o Kommo pode levar até 90s…` | `merger.py:_abrir_modal` |
| Modal pronto | `Modal aberto: <título do modal>` | `merger.py:_executar` |
| União confirmada | `União <i>/<limite> confirmada em <s>s.` | `merger.py:_laco` |
| União não confirmada | `União <i>/<limite>: o Kommo não confirmou…` · `…mostrou 'Algo deu errado'…` · `…o clique em 'Unir' falhou…` · `…sem resultado em 120s…` (ERRO) | `merger.py:_laco` |
| Erro da busca | `Kommo mostrou 'Algo deu errado' — clicando em Tentar novamente (n/5).` | `merger.py:_esperar_busca` |
| Sessão expirada | `A sessão do Kommo parece ter expirado…` | `merger.py:_checar_sessao` |
| Fim | `Fim (<texto do motivo>): <c> confirmadas[, <i> não confirmadas], <k> cliques em Unir.` | `merger.py:_emitir_fim` |

O texto do motivo na linha `Fim (...)` é o valor de `MOTIVOS` (ex.: `limite atingido`, `sem duplicatas restantes`,
`sessão do Kommo expirada ou redirecionada`), não o código. A **duração** da execução não aparece na linha `Fim`: é
calculada pela diferença entre os carimbos de hora de `Iniciando:` e `Fim (` (resolução de 1 s).

Limitações das fontes:

- **Retenção de 30 dias** (`logs.DIAS_RETENCAO`): a janela máxima de cálculo é de 30 dias, a menos que o usuário
  copie os logs antes.
- **Modo texto (CLI)** não escreve `Iniciando:`; ali conte execuções pelas linhas `Fim (`.
- Com o modo privacidade ligado, a janela mascara subdomínio e totais **no log** (`••••`); os SLIs abaixo não
  dependem desses valores.
- Se o processo for morto (Gerenciador de Tarefas, queda de energia), não há linha `Fim` — é exatamente o que o
  SLI-04 detecta.

## 4. SLIs e SLOs internos

Janela padrão: **as últimas 20 execuções reais** (sem ensaio) ou **30 dias**, o que vier primeiro. Para
Leads e Contatos, calcule **separadamente** (o comportamento do Kommo é diferente — ver FR-013).

Todos os objetivos são **PROPOSTOS — a validar**: ainda não há linha de base medida com a versão atual do motor
contra o Kommo real. A primeira tarefa é medir 20 execuções e ajustar os números.

### SLI-01 — Taxa de uniões confirmadas

- **Fórmula:** `Σ confirmadas / Σ cliques` nas execuções da janela com `cliques > 0`.
- **Fonte:** `FimEvt.confirmadas`, `FimEvt.cliques`; no log, os números da linha `Fim (`.
- **Objetivo proposto (a validar):** Contatos **≥ 98 %**. Leads: **sem objetivo** até confirmar no Kommo real se a
  tela de Leads mostra o texto "conclu…" (se não mostrar, o valor esperado é 0 % e isso é comportamento seguro, não
  falha).
- **Monitoramento:** manual, após cada execução grande e antes de cada release (script da §6).
- **Ação em violação:** conferir no Kommo se as uniões "não confirmadas" foram feitas; ver se o texto do
  `h2.progress__header` mudou (linhas `Kommo (progresso): “…”` do log); atualizar
  [KOMMO_DOM.md](../KOMMO_DOM.md), `fluxo.progresso_concluido` e o teste correspondente.

### SLI-02 — Taxa de uniões não confirmadas

- **Fórmula:** `Σ incertas / Σ cliques`.
- **Fonte:** `FimEvt.incertas`; linha `Fim (` (`, N não confirmadas`).
- **Objetivo proposto (a validar):** Contatos **≤ 2 %**. Leads: medir e registrar (sem objetivo, ver SLI-01).
- **Monitoramento / ação:** como SLI-01. Valor alto e repentino em Contatos indica mudança no HTML do Kommo
  ou lentidão do Kommo (uniões caindo no teto de 120 s — ver SLI-03).

### SLI-03 — Tempo por união confirmada

- **Fórmula:** mediana e p95 do tempo entre o clique em "Unir" e o estado estável, das uniões confirmadas.
- **Fonte:** linhas `União i/L confirmada em <s>s.` (o motor mede com relógio monotônico).
- **Linha de base disponível:** observação manual registrada em [KOMMO_DOM.md](../KOMMO_DOM.md): cada união leva
  **~2–7 s** (Contatos ~2–6 s; Leads ~5–7 s); [ESTRUTURA.md](../ESTRUTURA.md) registra 100 uniões de Contatos a
  ~6 s cada. São observações anteriores à regra atual de confirmação; **não foram re-medidas nesta revisão**.
- **Objetivo proposto (a validar):** mediana **≤ 7 s** e p95 **≤ 15 s**; nenhuma união chegando ao teto de 120 s
  (`TEMPO_UNIAO`) em execuções normais.
- **Ação em violação:** verificar a conexão e se o Kommo está lento (abrir a lista à mão); se o tempo subiu sem
  lentidão aparente, conferir se o app está esperando um estado que não aparece mais (diagnóstico estrutural no
  log, `KOMMO_DEBUG=1` para captura).

### SLI-04 — Execuções que terminam com resumo (`FimEvt`)

- **Fórmula:** `nº de linhas "Fim (" / nº de linhas "Iniciando:"` (janela; só execuções pela interface).
- **Fonte:** log.
- **Objetivo proposto:** **100 %**. O motor emite `FimEvt` no `finally` de `Merger.run` e isso é verificado em todos
  os cenários simulados (`tests/test_merger.py`, invariante `checar_seguranca`); qualquer execução sem `Fim` indica
  processo morto ou defeito.
- **Ação em violação:** procurar no log a última linha antes do corte; se não foi o usuário que matou o processo,
  abrir issue (sem dados reais) com as linhas de diagnóstico.

### SLI-05 — Execuções que terminam por motivo normal

- **Fórmula:** `execuções com motivo ∈ {limite, sem_duplicatas, ensaio} / execuções com Fim`.
  Paradas do usuário (`parado`, `forcado`, `recusado`, `sem_resposta`) entram no denominador só se a pergunta for
  "o app atrapalhou o usuário?"; para qualidade técnica, exclua-as do denominador.
- **Fonte:** `FimEvt.motivo`; texto do motivo na linha `Fim (`.
- **Objetivo proposto (a validar):** **≥ 90 %** das execuções não interrompidas pelo usuário.
- **Ação em violação:** olhar a distribuição dos motivos de falha: `falhas`/`erro` → Kommo instável ou HTML mudou;
  `validacao` → seletor ou título do modal mudou (conferir `KOMMO_DOM.md`); `navegador_indisponivel` → ver
  [recuperação de falhas](recuperacao-falhas.md).

### SLI-06 — Tempo de espera da busca de duplicatas

- **Fórmula:** mediana e máximo de `t(Modal aberto) − t(Procurando duplicatas)` por execução.
- **Fonte:** carimbos de hora das duas linhas no log (resolução de 1 s).
- **Linha de base disponível:** observação manual em [KOMMO_DOM.md](../KOMMO_DOM.md): a tela de carregamento do
  Kommo dura **~10 a 45 s**; o app espera até 90 s (`TEMPO_BUSCA`) por ciclo.
- **Objetivo proposto (a validar):** mediana **≤ 45 s**; nenhuma busca terminando em `travado` (modal sem botão até
  90 s).
- **Ação em violação:** é quase sempre lentidão do Kommo em contas grandes; se virar regra, avaliar aumentar
  `TEMPO_BUSCA` (com teste em `tests/test_merger.py`).

### SLI-07 — Taxa de sessões expiradas

- **Fórmula:** `execuções com motivo sessao_expirada / execuções que passaram do login`.
- **Fonte:** `FimEvt.motivo`; linha `Fim (sessão do Kommo expirada ou redirecionada)`.
- **Objetivo proposto (a validar):** **≤ 5 %**.
- **Ação em violação:** é uma decisão do Kommo (tempo de sessão); oriente o usuário a entrar de novo. Se ocorrer
  logo após o login, pode ser redirecionamento novo do Kommo — conferir a URL da lista em `kommo.py`.

### Métricas internas (sem objetivo)

| Métrica | Fonte | Para quê |
|---|---|---|
| Cliques em "Tentar novamente" por execução | linhas `Kommo mostrou 'Algo deu errado'` | saúde da busca do Kommo |
| Reaberturas pelo menu | linhas `Reabrindo a busca de duplicatas pelo menu…` | idem |
| Textos de progresso distintos vistos | linhas `Kommo (progresso): “…”` | calibrar FR-013 (Leads) |
| `erros` e `avisos` por execução | `FimEvt.erros`/`avisos` | triagem |
| Login que estoura 10 min | motivo `login_timeout` | usabilidade do primeiro acesso |

## 5. Sem telemetria, de propósito

O app **não envia nada** para o projeto nem para terceiros: não há servidor, coletor de métricas, relatório de
falhas automático ou "phone home". A única comunicação de rede é o navegador falando com
`https://<empresa>.kommo.com` (e o que o próprio Kommo carregar). Motivos:

- os dados manipulados são de clientes do usuário (nomes, telefones, e-mails) e a conta do CRM é sensível
  (ver [segurança](../security/seguranca.md));
- telemetria exigiria servidor, política de privacidade e base legal (LGPD) que o projeto não tem;
- o próprio verificador de privacidade existe para impedir que dados da máquina saiam nos pacotes.

Consequência: **os SLIs só podem ser calculados localmente, pelo usuário**, e compartilhados por ele (agregados,
sem subdomínio) se quiser ajudar a calibrar as metas.

## 6. Como calcular os SLIs a partir de `data/logs`

Os logs ficam em `<pasta do programa>/data/logs/` (ou `KOMMO_DATA_DIR/logs/`). O script abaixo usa só a biblioteca
padrão do Python, lê os logs e imprime os SLIs 01–06 e as métricas de motivo. Não envia nada para lugar nenhum.
Salve como `sli.py` **fora** da pasta `data/` e rode `python sli.py "<pasta do programa>/data/logs"`.

```python
import glob, re, statistics, sys
from datetime import datetime

pasta = sys.argv[1] if len(sys.argv) > 1 else "data/logs"
RE_LINHA = re.compile(r"^\[(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})\] (ERRO  |AVISO |OK    |      )(.*)$")
RE_UNIAO_OK = re.compile(r"^União \d+/\S+ confirmada em ([\d.]+)s\.")
RE_FIM = re.compile(r"^Fim \((.*?)\): (\d+) confirmadas(?:, (\d+) não confirmadas)?, (\d+) cliques em Unir\.")
inicios = fins = 0
motivos, duracoes, buscas = {}, [], []
confirmadas = nao_conf = cliques = tentar = 0
t_busca = None
for arq in sorted(glob.glob(f"{pasta}/*.log")):
    for linha in open(arq, encoding="utf-8", errors="replace"):
        m = RE_LINHA.match(linha.rstrip("\n"))
        if not m:
            continue
        t, msg = datetime.strptime(m[1], "%d/%m/%Y %H:%M:%S"), m[3]
        if msg.startswith("Iniciando: "):
            inicios += 1
        elif msg.startswith("Procurando duplicatas"):
            t_busca = t
        elif msg.startswith("Modal aberto: ") and t_busca:
            buscas.append((t - t_busca).total_seconds()); t_busca = None
        elif msg.startswith("Kommo mostrou 'Algo deu errado'"):
            tentar += 1
        elif (u := RE_UNIAO_OK.match(msg)):
            duracoes.append(float(u[1]))
        elif (f := RE_FIM.match(msg)):
            fins += 1
            motivos[f[1]] = motivos.get(f[1], 0) + 1
            confirmadas += int(f[2]); nao_conf += int(f[3] or 0); cliques += int(f[4])

def pct(a, b): return f"{100 * a / b:.1f}%" if b else "n/d"
print(f"execuções iniciadas pela janela: {inicios} · execuções com resumo (Fim): {fins}")
print(f"cliques em Unir: {cliques} · confirmadas: {confirmadas} ({pct(confirmadas, cliques)}) · "
      f"não confirmadas: {nao_conf} ({pct(nao_conf, cliques)})")
if duracoes:
    q = statistics.quantiles(duracoes, n=20) if len(duracoes) >= 2 else [duracoes[0]] * 19
    print(f"tempo por união confirmada: mediana {statistics.median(duracoes):.1f}s · p95 {q[18]:.1f}s · n={len(duracoes)}")
if buscas:
    print(f"espera da busca inicial: mediana {statistics.median(buscas):.0f}s · máx {max(buscas):.0f}s · n={len(buscas)}")
print(f"'Algo deu errado' (cliques em Tentar novamente): {tentar}")
for k, v in sorted(motivos.items(), key=lambda kv: -kv[1]):
    print(f"motivo '{k}': {v} ({pct(v, fins)})")
```

O script foi conferido contra um log sintético gerado com o próprio `logs.formatar` do app (todas as linhas
reconhecidas). Ele agrega todas as execuções da pasta; para separar Leads e Contatos ou usar a janela de 20
execuções, copie para uma pasta temporária só os arquivos/dias desejados. "Espera da busca" conta só a busca
inicial de cada execução (as buscas entre uniões não têm linha própria no log).

**Não publique os logs**: eles podem conter o subdomínio (com a privacidade desligada ou no modo texto) e caminhos
locais com o nome de usuário do Windows. Compartilhe só a saída agregada do script.

## 7. Revisão destas metas

- Medir a linha de base (20 execuções de Contatos e 20 de Leads, numa conta de teste, com limite pequeno) e
  substituir os "propostos" por números medidos.
- Revisar os objetivos a cada mudança em `kommo.py`, `fluxo.py` ou `merger.py`, e quando o Kommo mudar a interface.
- Registrar a data e a versão da medição neste documento.
