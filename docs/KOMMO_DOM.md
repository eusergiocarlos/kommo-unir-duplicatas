# Mapa do Kommo observado (DOM e comportamento)

Levantado manualmente no navegador, em contas reais, para Leads e Contatos (v1). Os seletores do **fluxo** vivem
em `src/kommo_duplicatas/kommo.py` (classe `Seletores` / `SELETORES`, única fonte para Python e JS); os do **modo
privacidade** em `src/kommo_duplicatas/privacy.py` (lista `SELETORES`; os seletores do processo — título, progresso, "Unir", menu — são importados de
`kommo.SELETORES`, sem cópia). Se o
Kommo atualizar a interface, comece por conferir esta lista. Atualizado em 2026-10 para refletir o código atual.

> Comportamentos marcados *(observado)* vêm do levantamento manual da v1 e **não** foram revalidados nesta revisão.
> O texto de conclusão de união em **Leads não foi validado** no Kommo real.

## URLs

| Lista | URL (`kommo.URL_LEADS` / `kommo.URL_CONTATOS`) | Caminho aceito pelo app |
|---|---|---|
| Leads | `https://<empresa>.kommo.com/leads/list/` (o Kommo pode redirecionar para um filtro salvo) | `/leads` ou `/leads/…` |
| Contatos | `https://<empresa>.kommo.com/contacts/list/contacts/?skip_filter=Y` | `/contacts` ou `/contacts/…` |

O hostname precisa ser **exatamente** `<empresa>.kommo.com` (`kommo.hostname_confere`, nunca por substring).

## Abrir "Localizar duplicatas"

| Elemento | Seletor (`kommo.Seletores`) |
|---|---|
| Botão de menu "⋯" | `button.button-input-with-menu[title="Mais"]` (`menu_mais`; o visível é preferido), senão `button.button-input-with-menu` (`menu_qualquer`) |
| Item — Leads | `li.js-duplicate-search` (`item_leads`) |
| Item — Contatos | `li.js-list-duplicate-contacts-search` (`item_contatos`) |

- **Não há mais *fallback* por texto** ("qualquer `li` com 'duplicat'"): o item é clicado só pelo seletor do tipo
  pedido e só se estiver visível (`_JS_CLICAR_ITEM`), para nunca abrir a busca de outra entidade.
- O login é considerado confirmado quando o hostname confere **e** existe `button.button-input-with-menu`.
- O modo privacidade **nunca** retira o atributo `title` de `button.button-input-with-menu` (o seletor do menu
  depende de `[title="Mais"]`).

## Modal de duplicatas

| Elemento | Seletor / valor | Uso no app |
|---|---|---|
| Título | `h2.modal-body__caption` → "Localizar e unir duplicatas — N de TOTAL" (Leads pode mostrar "N de muitas") | `Estado.caption`; precisa conter "duplicat" (sem acento/caixa); `parse_total` lê `de <número>` no fim |
| Unir | `button.js-merge-start` ("Unir esta duplicata") | `Estado.pode`; clique com `page.click` (timeout 3 s) |
| Pular | `button.js-merge-next` ("Pular esta duplicata") | o app **não** usa; só é mantido legível no modo privacidade |
| Cancelar | `.actions__doubles_action button.button-cancel` | fecha o modal no fim (só se existir e sem progresso na tela) |
| Erro da busca | `.js-modal-error` ("Ops! Algo deu errado") | `Estado.erro` |
| Tentar novamente | `button.js-modal-try-again` | até 5 cliques por ciclo de busca |
| Fechar modal | `.modal-body__close` | ao reabrir a busca (depois "Cancelar", depois Escape) |
| Progresso | `h2.progress__header` ("Realizando união", "Unindo leads", "União de contatos concluída com sucesso") | `Estado.progresso`; `/conclu/i` = união **confirmada** |

"Visível" = `offsetParent !== null`. `Estado.modal` = título, Unir, progresso ou erro visível.

## Comportamento

- *(observado)* Antes do modal aparece uma **tela de carregamento** com o uso da conta ("Você atingiu 83% do
  limite…") por ~10 a 45 s. O app espera até **90 s** (`TEMPO_BUSCA`) por ciclo de busca.
- *(observado)* Cada **união** leva ~2–7 s (contatos ~2–6 s; leads ~5–7 s). O app espera até **120 s**
  (`TEMPO_UNIAO`), lendo o estado a cada 0,2 s.
- *(observado)* Entre uma união e outra o Kommo pode **fechar o modal e recarregar a busca** ou **recarregar a
  página**. O app só conclui "sem duplicatas" se a busca terminar sem modal em 90 s, **sem** erro pendente e com a
  sessão ainda na lista certa; se viu a página recarregar (inclusive durante a união), reabre a busca pelo menu
  (1 vez por ciclo) antes de concluir.
- *(observado)* Em Leads, com busca longa (~50 s+), o Kommo pode mostrar **"Ops! Algo deu errado"**. O app clica
  "Tentar novamente" (até 5 vezes, 2 s de pausa) e, persistindo, fecha e reabre pelo menu (1 vez); depois desiste
  com erro.
- **Confirmação de união:** só conta como **confirmada** quando o texto de `h2.progress__header` contém "conclu"
  **e** o estado seguinte é coerente (próximo grupo, modal fechado ou página recarregando) — tabela em
  [arquitetura §6](architecture/arquitetura.md#6-regra-pura-de-término-de-uma-união). Contatos: "União de contatos
  concluída com sucesso" *(observado)*. **Leads: sem texto "concluída"; conta-se pelo modal fechar/contador avançar**; o app registra no log cada
  texto de progresso novo ("Kommo (progresso): …") para calibrar.
- *(observado)* O Kommo mostra o total exato de grupos em Contatos (ex.: "1 de 42770" / "1 de 42.770") e pode
  mostrar "muitas" em Leads (total = não informado).
- A ação é **irreversível**.

## Elementos sensíveis (para o modo privacidade)

Lista real em `privacy.SELETORES` (CSS `filter: blur(7px)` sob `html.kp-privacy`):

| Onde | Seletores |
|---|---|
| Marcados pelo observer | `.kp-sens` |
| Totais da lista / funil | `.list-top-search__summary`, `.js-list_summary` (ex.: "9195 leads: R$ 4.596"), `.pipeline_status__head_info`, `.pipeline_status__head_sum` |
| Linhas de lista | `.js-list-row:not(.js-list-row-head)`, `.js-list-row .list-row__cell:not(.list-row__cell-head)`, `.content-table__item__inner`, `.note-lead__pipe`, `.note-lead__status`, `.list-row__template-name__name`, `.list-row__template-name__table-wrapper__name-link` |
| Contato | `a[href^='tel:']`, `a[href^='mailto:']`, `.tel`, `.linked-form__field__value`, `.card-entity-form__fields input`, `.card-entity-form__fields .linked-form__field__value` |
| Conta/usuário | `.nav__top__userbar__userinfo`, `.nav__top__userpic__holder`, `.js-avatar-wrapper`, `.n-avatar` |
| Chat/funil | `.feed-note`, `.feed-compose`, `.notes-wrapper`, `.feed-note__body`, `.pipeline_leads__item`, `.pipeline_leads__item-name`, `.digital-pipeline__lead`, `.pipeline-unsorted__item` |
| Modal de duplicatas | `.control-checkbox__text`, `.form-result__text`, `.element__text`, `.control-radio-label-text`, `.modal-body__caption + * .js-duplicate-row`, `.merge-form__field-value`, `.merge-form__result` |
| Outros | `.users-select__body__item`, `.js-card-name`, `.card-holder__name`, `[data-entity-name]`, `.content-table__cell-name` |
| Heurísticos (prefixo/substring de classe, com `:has()`; nunca `html`/`body`/botões nem contêineres do processo) | `form-result__*`, `merge-form__*`, `users-select*`, `tooltip*`, `popover*`, `notification*`, `js-notifications*`, `nav__notifications*`, qualquer classe contendo `avatar` |
| Texto livre (regex `REGEX_SENSIVEL`) | `R$ 1.234`, `N leads/contatos/empresas`, `83%`, `5238/90000`, "limite" → classe `kp-sens` em elementos "folha" (até 2 filhos, < 60 caracteres) |
| Tooltips (`title`) | retirados (guardados em `data-kp-title`) em elementos sensíveis, dentro de `.js-list-row`, `.content-table`, `.modal-body`, `.modal`, `.pipeline_leads`, `.notes-wrapper`, `.feed-compose`, ou quando o texto casa a regex |
| Título da aba | `document.title` → "Kommo" (travado) |
| Notificações criadas pela página | título "Kommo", sem corpo/ícone |

**Nunca borrados** (para a gravação mostrar o processo): `h2.modal-body__caption`, `h2.progress__header`, botões
(`button`, `button *`, inclusive `button.js-merge-start` e `button.js-merge-next`).

Não dá para borrar a **barra de endereço** do navegador (mostra `<empresa>.kommo.com`), nem notificações de *push*
do service worker do Kommo (o navegador é aberto com `--disable-notifications`, o que mitiga).
