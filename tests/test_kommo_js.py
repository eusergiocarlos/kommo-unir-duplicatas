"""JS do kommo.py rodando de verdade num Chromium headless contra um HTML de fixture (tests/fixtures/).

Não acessa a internet nem o Kommo: a página é montada com `page.set_content`. Se o Chromium do Playwright não
abrir nesta máquina, os testes são pulados (pytest.skip) com o motivo.
"""
import os

import pytest

from kommo_duplicatas import kommo
from kommo_duplicatas.kommo import Estado, KommoPage

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "kommo_pagina.html")


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
def page(navegador):
    pg = navegador.new_page()
    with open(FIXTURE, encoding="utf-8") as f:
        pg.set_content(f.read())
    yield pg
    pg.close()


def mostrar(page, seletor, visivel=True):
    page.evaluate("([s, v]) => document.querySelectorAll(s).forEach(e => e.classList.toggle('oculto', !v))",
                  [seletor, visivel])


def cliques(page):
    return page.evaluate("window.__cliques")


# ------------------------------------------------------------------ estado
def test_estado_modal_com_grupo(page):
    assert KommoPage(page).estado() == Estado(modal=True, caption="Localizar e unir duplicatas — 1 de 42770",
                                              pode=True)


def test_estado_progresso_e_concluido(page):
    mostrar(page, kommo.SELETORES.unir, False)
    mostrar(page, kommo.SELETORES.progresso)
    est = KommoPage(page).estado()
    assert est.progresso == "Realizando união" and not est.pode and est.modal
    page.evaluate("(s) => document.querySelector(s).textContent = 'União de contatos concluída com sucesso'",
                  kommo.SELETORES.progresso)
    assert "concluída" in KommoPage(page).estado().progresso


def test_estado_detecta_erro_do_modal(page):
    mostrar(page, kommo.SELETORES.erro)
    est = KommoPage(page).estado()
    assert est.erro is True and est.modal is True
    assert KommoPage(page).tentar_novamente() is True
    assert cliques(page) == ["tentar"]


def test_estado_modal_fechado(page):
    page.evaluate("document.getElementById('modal').remove()")
    assert KommoPage(page).estado() == Estado()


def test_js_compat_do_merger_sem_argumento(page):
    """O merger atual chama page.evaluate(kommo.JS_ESTADO) sem argumento e JS_CLICAR_ITEM com uma string."""
    d = page.evaluate(kommo.JS_ESTADO)
    assert d["pode"] is True and d["caption"].endswith("1 de 42770")
    assert page.evaluate(kommo.JS_ABRIR_MENU) == "ok"
    assert page.evaluate(kommo.JS_CLICAR_ITEM, "contatos") is True
    assert cliques(page) == ["menu", "item-contatos"]


# ------------------------------------------------------------------ menu e item por tipo
@pytest.mark.parametrize("tipo,anotado", [("leads", "item-leads"), ("contatos", "item-contatos")])
def test_clica_item_do_tipo_certo(page, tipo, anotado):
    porta = KommoPage(page)
    assert porta.abrir_menu() is True
    assert porta.clicar_item_duplicatas(tipo) is True
    assert cliques(page) == ["menu", anotado]


def test_nao_clica_item_de_outra_entidade(page):
    """Sem o item de leads, NÃO pode cair num <li> qualquer com 'duplicat' (empresas/contatos)."""
    page.evaluate("(s) => document.querySelector(s).remove()", kommo.SELETORES.item_leads)
    porta = KommoPage(page)
    assert porta.abrir_menu() is True
    assert porta.clicar_item_duplicatas("leads") is False
    assert porta.clicar_item_duplicatas("empresas") is False
    assert cliques(page) == ["menu"]


def test_nao_clica_item_invisivel(page):
    """Menu fechado (itens ocultos): não clica nada."""
    assert KommoPage(page).clicar_item_duplicatas("contatos") is False
    assert cliques(page) == []


def test_abrir_menu_sem_botao(page):
    page.evaluate("(s) => document.querySelectorAll(s).forEach(e => e.remove())", kommo.SELETORES.menu_qualquer)
    porta = KommoPage(page)
    assert porta.abrir_menu() is False
    assert porta.tem_menu() is False


# ------------------------------------------------------------------ ações no modal
def test_clicar_unir_e_cancelar(page):
    porta = KommoPage(page)
    assert porta.clicar_unir() is True
    assert porta.cancelar_modal() is True
    assert cliques(page) == ["unir", "cancelar"]


def test_clicar_unir_invisivel_falha_rapido(page):
    mostrar(page, kommo.SELETORES.unir, False)
    assert KommoPage(page, timeout_clique_ms=300).clicar_unir() is False
    assert cliques(page) == []


def test_fechar_modal_usa_o_x(page):
    KommoPage(page).fechar_modal()
    assert cliques(page) == ["fechar"]


# ------------------------------------------------------------------ diagnóstico sem PII
def test_diagnostico_sem_pii(page):
    d = KommoPage(page).diagnostico()
    assert "modal-body" in d and "unir: 1 encontrados, 1 visíveis" in d
    for sensivel in ("João", "Silva", "99999", "example.com", "42770", "Ops", "9195", "R$"):
        assert sensivel not in d
    d2 = page.evaluate(kommo.JS_DIAGNOSTICO)    # forma antiga usada pelo merger
    assert "João" not in d2 and "modal-body" in d2


def test_timeout_do_evaluate(page):
    """Função JS que nunca resolve: o embrulho com timeout rejeita com 'kp-timeout' (eh_transitorio -> True)."""
    porta = KommoPage(page, timeout_ms=200)
    with pytest.raises(Exception, match="kp-timeout"):
        porta._avaliar("() => new Promise(() => {})", None)
