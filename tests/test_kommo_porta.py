"""KommoPage com um `page` falso (stub): conversão de erros de navegação, cliques e valores seguros.

Nada aqui abre navegador nem fala com o Kommo.
"""
import pytest

from kommo_duplicatas import kommo
from kommo_duplicatas.kommo import Estado, KommoPage, PortaKommo

ERRO_CONTEXTO = "Execution context was destroyed, most likely because of a navigation"
ERRO_FECHADO = "Target page, context or browser has been closed"


class TimeoutError(Exception):  # noqa: A001 - mesmo nome da exceção do Playwright
    pass


class Teclado:
    def __init__(self):
        self.teclas = []

    def press(self, tecla):
        self.teclas.append(tecla)


class PageStub:
    """Imita só o que KommoPage usa de playwright.sync_api.Page."""

    def __init__(self, url="https://acme.kommo.com/leads/list/", evaluate=None, falhas_clique=(), presentes=()):
        self.url = url
        self._evaluate = evaluate
        self.falhas_clique = set(falhas_clique)
        self.presentes = set(presentes)
        self.keyboard = Teclado()
        self.cliques = []
        self.avaliacoes = []

    def evaluate(self, js, arg=None):
        self.avaliacoes.append((js, arg))
        if isinstance(self._evaluate, BaseException):
            raise self._evaluate
        return self._evaluate(js, arg) if callable(self._evaluate) else self._evaluate

    def click(self, seletor, timeout=None):
        assert timeout, "todo clique precisa de timeout explícito"
        self.cliques.append((seletor, timeout))
        if seletor in self.falhas_clique:
            raise TimeoutError(f"Timeout {timeout}ms exceeded waiting for {seletor}")

    def query_selector(self, seletor):
        return object() if seletor in self.presentes else None

    def screenshot(self, path, timeout=None):
        assert timeout
        raise Exception(ERRO_FECHADO)


def test_kommopage_implementa_porta():
    assert isinstance(KommoPage(PageStub()), PortaKommo)


@pytest.mark.parametrize("msg", [ERRO_CONTEXTO, ERRO_FECHADO, "Target closed", "Navigation interrupted",
                                 "Frame was detached", "Error: kp-timeout 5000ms"])
def test_estado_navegacao_vira_navegou(msg):
    porta = KommoPage(PageStub(evaluate=Exception(msg)))
    assert porta.estado() == Estado(navegou=True)


def test_estado_timeout_do_playwright_vira_navegou():
    assert KommoPage(PageStub(evaluate=TimeoutError("Timeout"))).estado().navegou


def test_estado_erro_desconhecido_propaga():
    with pytest.raises(ValueError):
        KommoPage(PageStub(evaluate=ValueError("bug no JS"))).estado()


def test_estado_le_dict_e_passa_seletores_com_timeout():
    stub = PageStub(evaluate={"erro": False, "modal": True, "caption": "X — 1 de 3", "pode": True, "progresso": ""})
    est = KommoPage(stub, timeout_ms=1234).estado()
    assert est == Estado(modal=True, caption="X — 1 de 3", pode=True)
    js, arg = stub.avaliacoes[0]
    assert arg["t"] == 1234
    assert arg["a"]["sel"]["unir"] == kommo.SELETORES.unir
    # o JS não repete literais de seletor: eles chegam pelo argumento
    for literal in (kommo.SELETORES.unir, kommo.SELETORES.caption, kommo.SELETORES.progresso):
        assert literal not in js


def test_acoes_com_navegacao_devolvem_valor_seguro():
    porta = KommoPage(PageStub(evaluate=Exception(ERRO_CONTEXTO)))
    assert porta.abrir_menu() is False
    assert porta.clicar_item_duplicatas("leads") is False
    assert "navegando" in porta.diagnostico()
    porta.aplicar_privacidade(True, "css")   # não propaga
    porta.screenshot("x.png")                # navegação/fechamento é ignorado


def test_clicar_item_tipo_desconhecido_nem_avalia():
    stub = PageStub(evaluate=True)
    assert KommoPage(stub).clicar_item_duplicatas("empresas") is False
    assert stub.avaliacoes == []


def test_clicar_item_passa_tipo_e_seletores():
    stub = PageStub(evaluate=lambda js, arg: arg["a"]["tipo"] == "contatos")
    porta = KommoPage(stub)
    assert porta.clicar_item_duplicatas("contatos") is True
    assert stub.avaliacoes[0][1]["a"]["sel"]["itens"]["contatos"] == kommo.SELETORES.item_contatos


def test_cliques_com_timeout_e_falha_vira_false():
    stub = PageStub(falhas_clique={kommo.SELETORES.unir})
    porta = KommoPage(stub, timeout_clique_ms=777)
    assert porta.clicar_unir() is False
    assert porta.tentar_novamente() is True
    assert stub.cliques == [(kommo.SELETORES.unir, 777), (kommo.SELETORES.tentar_novamente, 777)]


def test_fechar_modal_ordem_x_cancelar_escape():
    stub = PageStub(falhas_clique={kommo.SELETORES.fechar_modal, kommo.SELETORES.cancelar})
    KommoPage(stub).fechar_modal()
    assert [c[0] for c in stub.cliques] == [kommo.SELETORES.fechar_modal, kommo.SELETORES.cancelar]
    assert stub.keyboard.teclas == ["Escape"]

    stub2 = PageStub()
    KommoPage(stub2).fechar_modal()
    assert [c[0] for c in stub2.cliques] == [kommo.SELETORES.fechar_modal]
    assert stub2.keyboard.teclas == []


def test_cancelar_modal_so_clica_se_existir():
    stub = PageStub()
    assert KommoPage(stub).cancelar_modal() is False
    assert stub.cliques == []
    stub2 = PageStub(presentes={kommo.SELETORES.cancelar})
    assert KommoPage(stub2).cancelar_modal() is True


def test_hostname_url_e_menu():
    stub = PageStub(url="https://acme.kommo.com/contacts/list/contacts/?skip_filter=Y",
                    presentes={kommo.SELETORES.menu_qualquer})
    porta = KommoPage(stub)
    assert porta.hostname() == "acme.kommo.com"
    assert porta.url_atual().startswith("https://acme.kommo.com/")
    assert porta.tem_menu() is True
    assert KommoPage(PageStub()).tem_menu() is False


def test_aplicar_privacidade_passa_argumentos():
    stub = PageStub(evaluate=None)
    KommoPage(stub).aplicar_privacidade(1, "body{}")
    assert stub.avaliacoes[0][1]["a"] == [True, "body{}"]


# ------------------------------------------------------------------ T10: abas do contexto
class AbaStub(PageStub):
    def __init__(self, url, fechada=False):
        super().__init__(url=url)
        self.fechada = fechada

    def is_closed(self):
        return self.fechada


class CtxStub:
    def __init__(self, *pages):
        self.pages = list(pages)


def test_porta_tem_os_metodos_de_aba_do_contrato():
    for nome in ("paginas_abertas", "adotar_pagina", "esta_fechada"):
        assert nome in PortaKommo.__dict__


def test_sem_ctx_paginas_abertas_e_nao_adota():
    aba = AbaStub("https://acme.kommo.com/leads/list/")
    porta = KommoPage(aba)
    assert porta.paginas_abertas() == 1 and porta.adotar_pagina() is False
    aba.fechada = True
    assert porta.paginas_abertas() == 0 and porta.adotar_pagina() is False


def test_aba_atual_aberta_nao_troca():
    a1, a2 = AbaStub("https://acme.kommo.com/leads/list/"), AbaStub("https://www.kommo.com/")
    porta = KommoPage(a1, ctx=CtxStub(a1, a2))
    assert porta.paginas_abertas() == 2
    assert porta.adotar_pagina() is False and porta.page is a1


def test_adota_a_aba_mais_recente_do_kommo_e_reaplica_config():
    a1 = AbaStub("https://teste.kommo.com/leads/list/", fechada=True)
    kommo_ = AbaStub("https://www.kommo.com/oauth/login/")
    google = AbaStub("https://accounts.google.com/signin")
    trocas = []
    porta = KommoPage(a1, ctx=CtxStub(a1, kommo_, google), ao_trocar=trocas.append)
    assert porta.esta_fechada() and porta.paginas_abertas() == 2
    assert porta.adotar_pagina() is True
    assert porta.page is kommo_ and trocas == [kommo_]          # prefere *.kommo.com à aba mais nova (Google)
    assert porta.esta_fechada() is False and porta.url_atual() == "https://www.kommo.com/oauth/login/"


def test_adota_aba_de_fora_se_for_a_unica():
    a1 = AbaStub("https://teste.kommo.com/leads/list/", fechada=True)
    google = AbaStub("https://accounts.google.com/signin")
    porta = KommoPage(a1, ctx=CtxStub(a1, google), ao_trocar=lambda pg: (_ for _ in ()).throw(RuntimeError()))
    assert porta.adotar_pagina() is True and porta.page is google   # erro no ao_trocar não impede a troca


def test_todas_fechadas_ou_contexto_quebrado_nao_adota():
    a1 = AbaStub("https://teste.kommo.com/", fechada=True)
    a2 = AbaStub("https://www.kommo.com/", fechada=True)
    porta = KommoPage(a1, ctx=CtxStub(a1, a2))
    assert porta.paginas_abertas() == 0 and porta.adotar_pagina() is False

    class CtxQuebrado:
        @property
        def pages(self):
            raise Exception(ERRO_FECHADO)
    porta2 = KommoPage(a1, ctx=CtxQuebrado())
    assert porta2.paginas_abertas() == 0 and porta2.adotar_pagina() is False


def test_screenshot_erro_nao_transitorio_propaga():
    class Stub(PageStub):
        def screenshot(self, path, timeout=None):
            raise PermissionError("disco")
    with pytest.raises(PermissionError):
        KommoPage(Stub()).screenshot("x.png")
