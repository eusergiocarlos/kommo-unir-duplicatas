# ADR-0007 — Modo privacidade por init script + MutationObserver

- **Status:** aceita (substitui o modelo "CSS + polling com `localStorage`" da v1.0.0)
- **Data:** 2026-10

## Contexto

O app é usado para gravar a tela e apresentar o processo. A v1.0.0 injetava CSS e fazia uma **varredura O(n) do
documento inteiro** a cada passo do laço (`JS_APLICAR`, throttle de 1,5 s), lembrando o estado em `localStorage`.
Problemas: a primeira carga e a tela de login apareciam sem borrão (o estado ainda não estava no `localStorage`),
havia quadros sem borrão entre uma varredura e outra, o título da aba revelava a empresa e tooltips repetiam nomes.

## Decisão

- **Base:** `privacy.init_script(ligado)` com o estado **embutido**, registrado com `context.add_init_script` antes
  de abrir a página. Roda em toda navegação, antes dos scripts do Kommo.
- **CSS** por seletores conhecidos (+ heurísticos por prefixo de classe protegidos por `:is()`/`:has()`), ativado
  pela classe `kp-privacy` no `<html>`, aplicado via `adoptedStyleSheets`.
- **MutationObserver** que examina só os nós alterados, marca `kp-sens` por regex em elementos curtos e processa
  tudo na mesma microtarefa (sem quadro intermediário sem borrão).
- **Título** travado em "Kommo"; **tooltips** sensíveis retirados para `data-kp-title`; **notificações** criadas pela
  página saem com título "Kommo" e sem corpo.
- **Reforço** Python (`privacy.aplicar`) no máximo a cada 3 s; `window.__kpSet(on)` troca o estado em execução.
- Na janela do app: máscara de subdomínio e totais (`ui.mascarar_*`).

## Alternativas consideradas

| Alternativa | Por que não |
|---|---|
| Manter o polling O(n) | lento em listas grandes; janelas sem borrão; falhava na 1ª carga |
| Borrar a janela inteira do navegador | a gravação perderia o propósito (mostrar o processo) |
| Captura de tela com pós-processamento | fora do escopo; o usuário usa o gravador que quiser |
| Esconder a barra de endereço | não é acessível a partir da página/CSS |

## Consequências

- **+** Borrão desde o primeiro quadro, inclusive no login; custo proporcional às mudanças.
- **+** Testado com JS real no Chromium headless (`tests/test_privacy_js.py`) e fixtures sem dados reais.
- **−** **Não é garantia absoluta:** barra de endereço, notificações de *push* do service worker, iframes de outra
  origem, diálogos nativos e telas não mapeadas podem mostrar dados.
- **−** (Resolvido na T11.) Os seletores do processo (título, progresso, botões) eram **duplicados** em
  `privacy.py`; hoje são importados de `kommo.SELETORES` (sem ciclo: `kommo.py` importa `privacy` de forma tardia).
- **−** Heurísticos com `:has()` não valem em navegadores sem suporte (o resto continua valendo).
- **−** (Resolvido na T11.) O modo CLI não mascarava o log; hoje usa as mesmas máscaras da janela (`mascara.py`).
