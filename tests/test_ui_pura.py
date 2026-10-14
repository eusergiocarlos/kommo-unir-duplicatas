"""Lógica pura da interface: máscaras, textos do contador/resumo/confirmação, fontes e geometria.

O único teste que abre Tk é pulado sem display e sempre destrói a janela (dados em pasta temporária)."""
import pytest

from kommo_duplicatas import temas
from kommo_duplicatas.limite import LIMITE_EXIGE_DIGITAR, PALAVRA_CONFIRMACAO, exige_digitar, palavra_confere
from kommo_duplicatas.merger import MOTIVOS, FimEvt
from kommo_duplicatas.ui import (OCULTO, dados_confirmacao, deve_registrar, fracao_barra, mascarar_empresa,
                                 mascarar_host, mascarar_mensagem, nome_canal, texto_detalhes, texto_inicio,
                                 texto_motivo, texto_pedir_palavra, texto_progresso, texto_resumo_conta,
                                 textos_resumo)


@pytest.mark.parametrize("entrada,saida", [
    ("acme", "a***e"),
    ("minhaempresa", "m***a"),
    ("abc", "a***c"),
    ("ab", "***"),
    ("a", "***"),
    ("", ""),
    (None, ""),
    ("  acme  ", "a***e"),
])
def test_mascarar_empresa(entrada, saida):
    assert mascarar_empresa(entrada) == saida


def test_mascara_nao_revela_tamanho():
    assert len(mascarar_empresa("abcd")) == len(mascarar_empresa("abcdefghijkl"))


def test_mascarar_mensagem_subdominio_e_totais():
    msg = "Abrindo https://acme.kommo.com/leads/list/"
    assert mascarar_mensagem(msg, "acme", True) == "Abrindo https://a***e.kommo.com/leads/list/"
    assert mascarar_mensagem(msg, "acme", False) == msg
    assert mascarar_mensagem("Modal aberto: Localizar e unir duplicatas — 1 de 42.761", "acme", True) \
        .endswith(f"1 de {OCULTO}")
    assert mascarar_mensagem("Total de duplicatas na conta: 42.761", "acme", True) == \
        f"Total de duplicatas na conta: {OCULTO}"
    assert "ACME" not in mascarar_mensagem("Erro em ACME.kommo.com", "acme", True)


def test_mascarar_mensagem_nao_estraga_texto_comum():
    # nome curto só é trocado colado ao domínio
    assert mascarar_mensagem("Abrindo leads", "le", True) == "Abrindo leads"
    assert "l***e.kommo.com" not in mascarar_mensagem("Abrindo leads", "le", True)
    assert mascarar_mensagem("x.kommo.com", "xy", True) == "x.kommo.com"
    assert mascarar_mensagem("xy.kommo.com/leads", "xy", True) == "***.kommo.com/leads"
    assert mascarar_mensagem("União 3/100 concluída em 5.3s", "acme", True) == "União 3/100 concluída em 5.3s"
    assert mascarar_mensagem("1 de muitas", "acme", True) == "1 de muitas"


def test_texto_inicio_com_privacidade_e_ensaio():
    assert "acme" not in texto_inicio("acme", "leads", 100, True)
    assert "a***e.kommo.com" in texto_inicio("acme", "leads", 100, True)
    assert "acme.kommo.com" in texto_inicio("acme", "leads", 0, False)
    assert "todas" in texto_inicio("acme", "leads", 0, False)
    assert "ENSAIO" in texto_inicio("acme", "leads", 10, True, ensaio=True)
    assert "ENSAIO" not in texto_inicio("acme", "leads", 10, True)


def test_mascarar_mensagem_total_informado_pelo_kommo():
    # linha real do motor: antes o total vazava com privacidade ligada
    msg = "Total de grupos de duplicatas informado pelo Kommo: 42.761"
    assert mascarar_mensagem(msg, "acme", True) == f"Total de grupos de duplicatas informado pelo Kommo: {OCULTO}"
    assert mascarar_mensagem(msg, "acme", False) == msg


def test_mascarar_host():
    assert mascarar_host("acme.kommo.com") == "a***e.kommo.com"
    assert mascarar_host("ACME.kommo.com ") == "a***e.kommo.com"
    assert mascarar_host("xy.kommo.com") == "***.kommo.com"
    assert mascarar_host("") == ""


# ---------------------------------------------------------------------- diálogo de confirmação da conta
def _valores(d):
    return dict(d["linhas"])


def test_confirmacao_privacidade_ligada_mascara_host_e_total():
    d = dados_confirmacao("acme.kommo.com", "leads", 42761, 100, False, privacidade=True)
    v = _valores(d)
    assert v["Conta"] == "a***e.kommo.com"
    assert v["Grupos de duplicatas na conta"] == OCULTO
    assert v["Tipo"] == "Leads" and v["Quantidade pedida"] == "até 100"
    assert "IRREVERSÍVEL" in d["aviso"] and d["botao"] == "Unir agora"
    assert d["pode_revelar"] is True and d["exige_digitar"] is False
    texto = repr(d)
    assert "acme" not in texto and "42.761" not in texto and "42761" not in texto


def test_confirmacao_revelar_mostra_conta_real():
    v = _valores(dados_confirmacao("acme.kommo.com", "contatos", 42761, 0, False, True, revelar=True))
    assert v["Conta"] == "acme.kommo.com" and v["Grupos de duplicatas na conta"] == "42.761"
    assert v["Tipo"] == "Contatos" and v["Quantidade pedida"].startswith("todas")


def test_confirmacao_privacidade_desligada():
    d = dados_confirmacao("acme.kommo.com", "leads", 0, 300, False, privacidade=False)
    v = _valores(d)
    assert v["Conta"] == "acme.kommo.com"
    assert v["Grupos de duplicatas na conta"] == "não informado"
    assert d["pode_revelar"] is False


def test_confirmacao_total_nao_informado_com_privacidade():
    assert _valores(dados_confirmacao("acme.kommo.com", "leads", 0, 10, False, True))[
        "Grupos de duplicatas na conta"] == "não informado"


@pytest.mark.parametrize("limite,ensaio,exige", [
    (0, False, True),                                  # todas
    (LIMITE_EXIGE_DIGITAR + 1, False, True),
    (LIMITE_EXIGE_DIGITAR, False, False),              # 500 ainda não exige
    (100, False, False),
    (0, True, False),                                  # ensaio nunca une: não exige digitar
    (10_000, True, False),
])
def test_confirmacao_regra_digitar_unir(limite, ensaio, exige):
    assert dados_confirmacao("acme.kommo.com", "leads", 5, limite, ensaio, False)["exige_digitar"] is exige


def test_confirmacao_ensaio():
    d = dados_confirmacao("acme.kommo.com", "leads", 5, 100, True, False)
    assert d["botao"] == "Fazer ensaio" and "nada será unido" in d["aviso"]
    assert "ensaio" in d["titulo"].lower()


def test_regra_exige_digitar_e_palavra():
    assert LIMITE_EXIGE_DIGITAR == 500 and PALAVRA_CONFIRMACAO == "UNIR"
    assert exige_digitar(0) and exige_digitar(501) and not exige_digitar(500) and not exige_digitar(1)
    assert palavra_confere("UNIR") and palavra_confere(" unir ") and palavra_confere("Unir")
    for errado in ("", "UNI", "UNIR!", "UNIRR", "sim", None):
        assert not palavra_confere(errado)
    assert "TODAS" in texto_pedir_palavra(0) and "UNIR" in texto_pedir_palavra(0)
    assert "mais de 500" in texto_pedir_palavra(1000)


@pytest.mark.parametrize("priv", [True, False])
def test_texto_progresso(priv):
    t = texto_progresso(3, 100, 42761, priv)
    assert t.startswith("duplicatas unificadas de 100")
    if priv:
        assert f"3 de {OCULTO} duplicatas da conta" in t
        assert "42.761" not in t and "restam" not in t
    else:
        assert "3 de 42.761 duplicatas da conta" in t and "restam 42.758" in t


def test_texto_progresso_sem_total_e_todas():
    assert texto_progresso(5, 0, 0, False) == "duplicatas unificadas"
    assert texto_progresso(5, 0, 0, True) == "duplicatas unificadas"
    assert texto_progresso(1500, 2000, 0, False) == "duplicatas unificadas de 2.000"


def test_texto_resumo_conta():
    assert texto_resumo_conta(10, 0, True) is None
    assert texto_resumo_conta(10, 42761, False) == "10 de 42.761 duplicatas da conta"
    assert texto_resumo_conta(10, 42761, True) == f"10 de {OCULTO} duplicatas da conta"


def test_texto_detalhes():
    assert texto_detalhes(65, 0, False) == "Tempo: 1min 05s  ·  sem erros"
    assert texto_detalhes(3725, 2, True) == "Tempo: 1h 02min 05s  ·  2 erro(s) — veja o log\n(interrompido pelo usuário)"
    assert texto_detalhes(-1, 0, False).startswith("Tempo: 0min 00s")
    assert texto_detalhes(65, 0, False, avisos=3) == "Tempo: 1min 05s  ·  sem erros  ·  3 aviso(s) — veja o log"


def test_texto_progresso_com_incertas():
    t = texto_progresso(3, 100, 0, False, incertas=2)
    assert "2 não confirmadas" in t
    assert "1 não confirmada" in texto_progresso(3, 100, 0, False, incertas=1)
    assert "não confirmada" not in texto_progresso(3, 100, 0, False)


def test_fracao_barra_usa_cliques():
    assert fracao_barra(5, 3, 10) == 0.5          # cliques, não confirmadas
    assert fracao_barra(0, 4, 10) == 0.4          # ProgEvt antigo sem cliques
    assert fracao_barra(50, 50, 0) == 0.0         # todas: sem barra
    assert fracao_barra(20, 20, 10) == 1.0


# ---------------------------------------------------------------------- resumo final
def _fim(**kw):
    base = dict(feitos=8, segundos=65, erros=0, interrompido=False, total=42761, confirmadas=8, incertas=0,
                cliques=8, motivo="limite", avisos=0)
    base.update(kw)
    return FimEvt(**base)


def _textos(t):
    return [x for x, _ in t["linhas"]]


def test_resumo_normal_sem_incertas():
    t = textos_resumo(_fim(), 10, privacidade=False)
    assert t["numero"] == "8" and t["rotulo"] == "duplicatas unificadas"
    linhas = _textos(t)
    assert "8 de 42.761 duplicatas da conta" in linhas
    assert not any("não confirmada" in x for x in linhas)
    assert any("8 clique(s) em Unir" in x and "limite 10" in x for x in linhas)
    assert f"Motivo: {MOTIVOS['limite']}" in linhas
    assert t["detalhes"] == "Tempo: 1min 05s  ·  sem erros"


def test_resumo_com_incertas_privacidade_e_motivo():
    t = textos_resumo(_fim(confirmadas=7, feitos=7, incertas=2, cliques=9, motivo="forcado", erros=1, avisos=2),
                      0, privacidade=True)
    linhas = _textos(t)
    assert t["numero"] == "7"
    assert "2 não confirmadas — confira no Kommo" in linhas
    assert any("podem ter sido feitas" in x or "pode(m) ter sido feita(s)" in x for x in linhas)
    assert f"7 de {OCULTO} duplicatas da conta" in linhas
    assert not any("42.761" in x for x in linhas)
    assert any("limite todas" in x for x in linhas)
    assert f"Motivo: {MOTIVOS['forcado']}" in linhas
    assert "1 erro(s)" in t["detalhes"] and "2 aviso(s)" in t["detalhes"] and t["detalhes_estilo"] == "aviso"
    assert dict(t["linhas"])["2 não confirmadas — confira no Kommo"] == "aviso"


def test_resumo_uma_incerta_singular():
    assert "1 não confirmada — confira no Kommo" in _textos(textos_resumo(_fim(incertas=1), 10, False))


def test_resumo_motivo_desconhecido():
    assert texto_motivo("xyz") == "Motivo: xyz"
    assert texto_motivo("") == "Motivo: desconhecido"


def test_resumo_ensaio():
    t = textos_resumo(_fim(feitos=0, confirmadas=0, cliques=0, motivo="ensaio"), 100, privacidade=True, ensaio=True)
    linhas = _textos(t)
    assert "ensaio" in t["titulo"].lower() and t["rotulo"] == "nada foi unido"
    assert "Conta, lista e modal de duplicatas conferidos." in linhas
    assert f"Grupos de duplicatas na conta: {OCULTO}" in linhas
    assert any("Nada foi unido" in x for x in linhas)
    t = textos_resumo(_fim(feitos=0, confirmadas=0, cliques=0, motivo="recusado", total=0), 100, False, ensaio=True)
    linhas = _textos(t)
    assert "O ensaio não chegou ao fim." in linhas and f"Motivo: {MOTIVOS['recusado']}" in linhas
    assert "Grupos de duplicatas na conta: não informado pelo Kommo" in linhas


@pytest.mark.parametrize("motivo,total,registra", [
    ("limite", 10, True), ("sem_duplicatas", 10, True), ("parado", 10, True),
    ("limite", 0, False), ("forcado", 10, False), ("erro", 10, False), ("ensaio", 10, False),
    ("recusado", 10, False), ("validacao", 10, False),
])
def test_deve_registrar(motivo, total, registra):
    assert deve_registrar(_fim(motivo=motivo, total=total)) is registra


def test_nome_canal():
    assert nome_canal("msedge") == "Microsoft Edge" and nome_canal("") == "" and nome_canal(None) == ""


@pytest.mark.parametrize("plat,fams,sans,mono", [
    ("win32", ["Segoe UI", "Consolas", "Arial"], "Segoe UI", "Consolas"),
    ("linux", ["DejaVu Sans", "DejaVu Sans Mono"], "DejaVu Sans", "DejaVu Sans Mono"),
    ("linux", ["Cantarell", "DejaVu Sans"], "Cantarell", "Courier"),
    ("darwin", ["Helvetica Neue", "Menlo"], "Helvetica Neue", "Menlo"),
    ("linux", [], "Helvetica", "Courier"),
    ("win32", ["segoe ui"], "Segoe UI", "Courier"),
])
def test_escolher_fontes(plat, fams, sans, mono):
    assert temas.escolher_fontes(fams, plat) == {"sans": sans, "mono": mono}


@pytest.mark.parametrize("tela", [(1920, 1080), (1366, 768), (1024, 600), (800, 480), (3840, 2160)])
def test_geometria_cabe_na_tela(tela):
    w, h, x, y = temas.calcular_geometria(*tela)
    assert w <= 560 and h <= 660
    assert w <= tela[0] * 0.9 + 1 and h <= tela[1] * 0.9 + 1
    assert x >= 0 and y >= 0 and x + w <= tela[0] and y + h <= tela[1]


def test_geometria_tela_grande_mantem_tamanho_original():
    assert temas.calcular_geometria(1920, 1080)[:2] == (560, 660)


def test_janela_abre_e_fecha(tmp_path, monkeypatch):
    """Abre a janela de verdade (sem iniciar nada) e confere estado inicial; pula se não houver display."""
    pytest.importorskip("tkinter")
    monkeypatch.setenv("KOMMO_DATA_DIR", str(tmp_path))     # nunca toca os dados reais do usuário
    from kommo_duplicatas import ui
    # Mesma criação com novas tentativas da integração (o Tcl do Windows às vezes falha ao criar muitas janelas
    # Tk seguidas no mesmo processo); só pula se todas falharem. Import aqui dentro: o módulo de integração faz
    # importorskip("tkinter") no topo e não deve afetar os testes puros deste arquivo.
    from test_ui_integracao import _nova_app
    app = _nova_app()
    try:
        app.withdraw()
        assert str(app.bt_ini["state"]) == "normal" and str(app.bt_par["state"]) == "disabled"
        assert ui.DICA_VAZIA in app.caixa.get("1.0", "end")
        # valor inválido aborta o início (nada de preset em silêncio) e mantém o INICIAR habilitado
        app._empresa_vis.set("acme")
        app.empresa.set("acme")
        app.custom.set("1.000,5")
        app.iniciar()
        assert app.th is None and not app._rodando
        assert "Nada foi iniciado" in app.caixa.get("1.0", "end")
        # privacidade mascara o campo Empresa quando não está em edição
        app.privacidade.set(True)
        assert app._empresa_vis.get() == "a***e"
        app.privacidade.set(False)
        assert app._empresa_vis.get() == "acme"
    finally:
        app.destroy()
