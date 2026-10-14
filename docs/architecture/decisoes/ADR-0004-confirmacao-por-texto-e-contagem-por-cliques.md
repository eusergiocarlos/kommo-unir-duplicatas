# ADR-0004 — Confirmação da união pelo texto "concluída" e contagem por cliques

- **Status:** aceita (com risco aberto em Leads)
- **Data:** 2026-10

## Contexto

Depois de um clique em "Unir esta duplicata" o Kommo mostra um progresso (`h2.progress__header`, ex.: "Realizando
união", "Unindo leads"), às vezes um texto final ("União de contatos concluída com sucesso"), e em seguida pode:
mostrar o próximo grupo, fechar o modal e recarregar a busca, ou recarregar a página. Versões antigas consideravam
"sucesso" quando o título mudava ou o progresso sumia — o que pode contar como feita uma união que falhou, e
deixava o limite ser ultrapassado quando um resultado era mal interpretado.

## Decisão

1. **Sucesso só com o texto de conclusão:** `fluxo.progresso_concluido()` procura `/conclu/i` (sem acentos/caixa)
   e `avaliar_uniao` só devolve `SUCESSO` com esse texto **e** um estado seguinte coerente (próximo grupo visível,
   modal fechado ou página recarregando). Qualquer outra mudança vira `INCERTO` ("não confirmada").
2. **Limite conta cliques:** `Merger._laco` faz `cliques += 1` **antes** de clicar; o laço para quando
   `cliques >= limite`. Cliques que falharam, uniões incertas, com erro ou sem resultado **também contam**.
   Resultado: a quantidade pedida **nunca é ultrapassada**.
3. A UI mostra confirmadas no contador, e cliques na barra; o resumo lista as "não confirmadas — confira no Kommo".
4. `INCERTO` não conta como falha seguida; `ERRO`, clique que falhou e tempo esgotado contam (`FALHAS_MAX = 3`).
5. Cada texto de progresso distinto é registrado uma vez no log ("Kommo (progresso): …") para calibrar Leads.

## Alternativas consideradas

| Alternativa | Por que não |
|---|---|
| Sucesso = título mudou | Leads mostra "1 de muitas" repetido; título pode mudar sem a união ter ocorrido |
| Sucesso = progresso sumiu | o progresso também some em falhas |
| Conferir a contagem total do Kommo | Leads não informa o total ("muitas"); exigiria reabrir a busca a cada união |
| Limite contando só confirmadas | uniões não confirmadas (que podem ter ocorrido) fariam o app unir **mais** do que o pedido |

## Consequências

- **+** Nenhuma união não confirmada é declarada como feita; o limite é uma garantia forte.
- **−** O app pode unir **menos** que o pedido (cliques que falharam também consomem o limite).
- **−** **Risco em Leads (aberto):** o texto de conclusão de Leads **não foi validado** no Kommo real. Se Leads
  nunca mostrar "conclu…":
  - com progresso visível, toda união vira "não confirmada" (o limite ainda é respeitado; testado em
    `test_leads_sem_texto_concluida_tudo_incerto_e_limite_por_cliques`);
  - sem progresso e com o mesmo título ("1 de muitas"), cada união espera `TEMPO_UNIAO` (120 s), conta como falha
    e, após 3 seguidas, o app para com motivo `falhas`.
  Mitigação: o log registra os textos de progresso vistos; validar numa conta de teste e ajustar
  `progresso_concluido`/a tabela se necessário.
- **−** Se o Kommo trocar o texto (idioma, redação) as uniões passam a "não confirmadas" até o ajuste.
