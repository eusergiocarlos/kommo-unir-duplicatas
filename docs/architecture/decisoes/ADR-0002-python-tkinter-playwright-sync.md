# ADR-0002 — Python + Tkinter + Playwright (API síncrona)

- **Status:** aceita
- **Data:** 2026-10 (registro retroativo)

## Contexto

O app é uma ferramenta de desktop para pessoas não técnicas: uma janela com poucos campos, um contador e um log.
Precisa ser empacotável como executável Windows, abrir rápido e ter poucas dependências. A automação é sequencial
por natureza (um grupo de duplicatas por vez).

## Decisão

- **Python ≥ 3.10** (`pyproject.toml`; o lock atual foi gerado com Python 3.14).
- **Tkinter** (biblioteca padrão) para a interface, com a lógica de textos em funções puras testáveis
  (`ui.py`, `tests/test_ui_pura.py`).
- **Playwright com a API síncrona** (`playwright.sync_api`), executada numa **thread separada** (`Merger`), que
  conversa com a UI por `queue.Queue` ([arquitetura §4](../arquitetura.md#4-fluxo-de-dados-e-eventos)).
- Única dependência de execução: `playwright>=1.40,<2` (`requirements.in`).

## Alternativas consideradas

| Alternativa | Por que não |
|---|---|
| Playwright assíncrono (`asyncio`) | o fluxo é estritamente sequencial; `async` exigiria integrar o laço de eventos com o Tk sem ganho real |
| PySide/PyQt | dependência grande (licença/tamanho do pacote); visual mais rico desnecessário |
| Electron/Node | dois runtimes, pacote maior, nova stack |
| Web local (Flask + navegador) | mais peças (servidor, porta local) para uma janela simples |
| Somente CLI | o público-alvo não usa terminal; a CLI existe como modo secundário |

## Consequências

- **+** Sem dependências de interface; empacotamento simples com PyInstaller ([ADR-0008](ADR-0008-pyinstaller-onedir-zip.md)).
- **+** Fluxo fácil de ler e de testar (sem `async`); tempo injetável (`Relogio`).
- **−** Tkinter tem visual limitado e exige cuidado com threads (widgets só na thread principal: `App.bombear`).
- **−** A API síncrona do Playwright não pode ser usada a partir de mais de uma thread: toda a sessão vive dentro
  da thread `Merger`.
- **−** No Linux, o build precisa de `tkinter` na máquina de build (o PyInstaller copia Tcl/Tk) — **não testado**.
