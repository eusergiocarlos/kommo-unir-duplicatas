"""T10 com Chromium headless real: a aba do login é fechada/substituída por outra aba do MESMO contexto.

Sem internet e sem Kommo: `ctx.route` responde *.kommo.com com HTML local (a lista vem de tests/fixtures/). O motor
roda na thread do teste (`Merger.run()`), com RelogioFalso; as trocas de aba acontecem no gancho `ao_dormir`
(mesma thread do Playwright sync). Modo ensaio: nada é unido. Se o Chromium não abrir, os testes são pulados.
"""
import os
import queue
from contextlib import contextmanager

import pytest
from fakes import RelogioFalso

from kommo_duplicatas import kommo, merger

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "kommo_pagina.html")
LOGIN = "<html><body><h1>login (fictício)</h1></body></html>"


@pytest.fixture(scope="module")
def navegador():
    sync_api = pytest.importorskip("playwright.sync_api")
    try:
        p = sync_api.sync_playwright().start()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Playwright não iniciou: {e}")
    try:
        b = p.chromium.launch(headless=True)
    except Exception as e:  # noqa: BLE001
        p.stop()
        pytest.skip(f"Chromium do Playwright não abriu: {e}")
    yield b
    b.close()
    p.stop()


@pytest.fixture
def ctx(navegador):
    with open(FIXTURE, encoding="utf-8") as f:
        lista = f.read()
    c = navegador.new_context()
    c.route("https://**.kommo.com/**", lambda r: r.fulfill(
        status=200, content_type="text/html", body=lista if "acme.kommo.com/leads" in r.request.url else LOGIN))
    yield c
    c.close()


def _rodar(ctx, ao_dormir_fn):
    pg1 = ctx.new_page()
    pg1.goto("https://www.kommo.com/oauth/login/")
    rel = RelogioFalso()
    rel.ao_dormir = lambda t: ao_dormir_fn(rel, pg1)
    portas = []

    @contextmanager
    def sessao():
        porta = kommo.KommoPage(pg1, ctx=ctx, ao_trocar=merger.Merger._configurar_pagina)
        portas.append(porta)
        yield porta

    fila = queue.Queue()
    merger.Merger(merger.Job("acme", "leads", 1, False, ensaio=True, confirmar_conta=False), fila,
                  relogio=rel, abrir_sessao=sessao).run()
    evs = [fila.get_nowait() for _ in range(fila.qsize())]
    return evs, portas[0], pg1


def test_aba_fechada_e_outra_aberta_no_contexto_e_adotada(ctx):
    feito = []

    def ao_dormir(rel, pg1):
        if rel.decorrido >= 6 and not feito:
            feito.append(1)
            nova = ctx.new_page()
            nova.goto("https://acme.kommo.com/leads/list/")       # o login "terminou" numa aba nova
            pg1.close()
    evs, porta, pg1 = _rodar(ctx, ao_dormir)
    fim = evs[-1]
    msgs = [e.msg for e in evs if isinstance(e, merger.LogEvt)]
    assert isinstance(fim, merger.FimEvt) and fim.motivo == "ensaio" and fim.cliques == 0, msgs
    assert pg1.is_closed() and porta.page is not pg1 and not porta.page.is_closed()
    assert any("passou a acompanhar a outra aba" in m for m in msgs)
    assert not any("navegador foi fechado" in m for m in msgs)
    assert "unir" not in porta.page.evaluate("window.__cliques")    # ensaio: nunca clica em Unir


def test_todas_as_abas_fechadas_e_navegador_fechado(ctx):
    def ao_dormir(rel, pg1):
        if rel.decorrido >= 6 and not pg1.is_closed():
            pg1.close()
    evs, porta, _ = _rodar(ctx, ao_dormir)
    fim = evs[-1]
    assert fim.motivo == "navegador_fechado" and fim.erros == 0 and fim.cliques == 0
    assert porta.paginas_abertas() == 0
