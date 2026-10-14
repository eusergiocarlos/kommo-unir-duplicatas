# ADR-0003 — Porta PortaKommo e regra pura de término

- **Status:** aceita
- **Data:** 2026-10

## Contexto

A união é **irreversível** e o Kommo real não pode ser usado em testes automatizados. Versões anteriores do motor
misturavam leitura do DOM, esperas com `sleep` real e decisões ("a união terminou?") no mesmo laço, o que tornava
impossível testar casos como recarga da página no meio da união, erro "Algo deu errado", sessão expirada ou parada
forçada.

## Decisão

1. **Porta:** `kommo.PortaKommo` (`typing.Protocol`, `runtime_checkable`) define tudo que o motor pede à página
   (`estado()`, `abrir_menu()`, `clicar_item_duplicatas()`, `clicar_unir()`, `tentar_novamente()`,
   `fechar_modal()`, `cancelar_modal()`, `hostname()`, `tem_menu()`, `url_atual()`, `aplicar_privacidade()`,
   `diagnostico()`, `screenshot()`, `esta_fechada()` e, desde a correção T10, `paginas_abertas()` e
   `adotar_pagina()` para trocar de aba dentro do mesmo contexto). Implementação real: `KommoPage`; nos testes:
   `FakeKommo` e `KommoSimulado` (`tests/fakes.py`).
2. **Leitura como valor:** `kommo.Estado` (dataclass imutável) é a fotografia do modal; `navegou=True` representa
   "não deu para ler".
3. **Regra pura:** `fluxo.avaliar_uniao(antes, depois, visto_progresso, ultimo_progresso)` devolve
   `SUCESSO | INCERTO | AGUARDA | ERRO` por uma tabela de decisão de 12 linhas
   ([arquitetura §6](../arquitetura.md#6-regra-pura-de-término-de-uma-união)). Sem I/O, sem tempo.
4. **Injeção:** `Merger(..., relogio=..., abrir_sessao=...)` — relógio falso (`RelogioFalso`) e sessão falsa; o
   `run()` real só abre a sessão Playwright e chama `_executar(porta)`.

## Alternativas consideradas

| Alternativa | Por que não |
|---|---|
| Testar só com Playwright + HTML estático | cobre os seletores (feito em `test_kommo_js.py`), mas não sequências temporais (recarga, erro, timeout) |
| *Mocks* ad hoc do objeto `page` do Playwright | acopla os testes a detalhes da API do Playwright; frágil |
| Classe abstrata (`abc.ABC`) | `Protocol` permite *duck typing* sem herança e mantém `kommo.py` sem importar o Playwright |
| Decidir o término dentro do laço do motor | mistura tempo e regra; foi justamente o que impedia testar |

## Consequências

- **+** O fluxo inteiro roda nos testes sem navegador e sem `sleep` real (`tests/test_merger.py`), inclusive o
  cenário pessimista de Leads e a parada em dois níveis.
- **+** A regra de sucesso é auditável numa tabela e testada por casos (`tests/test_fluxo.py`).
- **−** Os falsos podem divergir do Kommo real; os seletores e o JS são cobertos separadamente por fixtures HTML
  no Chromium headless, mas o **comportamento temporal real não é testado automaticamente**.
- **−** Toda nova capacidade da página exige método novo na porta e nos falsos.
