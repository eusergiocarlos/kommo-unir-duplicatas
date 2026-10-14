import pytest

from kommo_duplicatas import kommo


@pytest.mark.parametrize("entrada,esperado", [
    ("minhaempresa", "minhaempresa"),
    ("  MinhaEmpresa  ", "minhaempresa"),
    ("minhaempresa.kommo.com", "minhaempresa"),
    ("https://minhaempresa.kommo.com/leads/list/", "minhaempresa"),
    ("http://minha-empresa.kommo.com", "minha-empresa"),
    ("", ""),
    ("com espaço", ""),
    ("-invalido", ""),
    ("a/b", "a"),
    ("invalido-", ""),
    ("a" * 63, "a" * 63),
    ("a" * 64, ""),
    ("acme.kommo.com:443/leads", "acme"),
    ("x.acme.kommo.com", ""),
    ("acme.outrodominio.com", ""),
    ("usuario@acme.kommo.com", ""),
    ("acme_1", ""),
])
def test_normalizar_empresa(entrada, esperado):
    assert kommo.normalizar_empresa(entrada) == esperado


@pytest.mark.parametrize("url,empresa,esperado", [
    ("https://acme.kommo.com/leads/list/", "acme", True),
    ("https://ACME.kommo.com/contacts/list/contacts/", "acme", True),
    ("https://xacme.kommo.com/leads/list/", "acme", False),
    ("https://acme.kommo.com.evil.io/leads/", "acme", False),
    ("https://evil.io/acme.kommo.com/leads/", "acme", False),
    ("https://www.kommo.com/oauth?next=acme.kommo.com", "acme", False),
    ("https://acme.kommo.com/leads/", "", False),
    ("", "acme", False),
    ("about:blank", "acme", False),
])
def test_hostname_confere(url, empresa, esperado):
    assert kommo.hostname_confere(url, empresa) is esperado


def test_seletores_fonte_unica_e_aliases():
    s = kommo.SELETORES
    assert kommo.SEL_UNIR == s.unir and kommo.SEL_CANCELAR == s.cancelar
    assert kommo.SEL_MENU_QUALQUER == s.menu_qualquer and kommo.SEL_FECHAR_MODAL == s.fechar_modal
    assert kommo.SEL_TENTAR_NOVAMENTE == s.tentar_novamente
    assert s.item("leads") == s.item_leads and s.item("contatos") == s.item_contatos and s.item("x") == ""
    assert not hasattr(kommo, "SEL_MENU_MAIS") and not hasattr(kommo, "SEL_ITEM_LEADS")
    # o JS só contém os seletores dentro do bloco de padrão gerado (json), não como literais no corpo
    assert "duplicat" not in kommo._JS_CLICAR_ITEM


def test_montar_url():
    assert kommo.montar_url("acme", "leads") == "https://acme.kommo.com/leads/list/"
    assert kommo.montar_url("acme", "contatos") == "https://acme.kommo.com/contacts/list/contacts/?skip_filter=Y"


@pytest.mark.parametrize("caption,total", [
    ("Localizar e unir duplicatas — 1 de 42770", 42770),
    ("Localizar e unir duplicatas — 3 de 1.175", 1175),
    ("Localizar e unir duplicatas — 1 de muitas", None),
    ("", None),
])
def test_parse_total(caption, total):
    assert kommo.parse_total(caption) == total
