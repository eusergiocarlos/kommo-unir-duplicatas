"""Motor (merger.py) com KommoSimulado + RelogioFalso: sem navegador, sem Kommo real e sem sleep real.

A união é IRREVERSÍVEL: estes testes provam que o motor nunca clica mais do que o pedido, nunca clica fora de hora,
nunca fecha/cancela no meio de uma união e sempre emite o FimEvt.
"""
import queue
import threading
from contextlib import contextmanager

import pytest
from fakes import CAPTION, FakeKommo, KommoSimulado, RelogioFalso

from kommo_duplicatas import browser, merger
from kommo_duplicatas.kommo import Estado, montar_url
from kommo_duplicatas.merger import (ConfirmarEvt, FimEvt, Job, LogEvt, Merger, ProgEvt, caminho_confere,
                                     modal_de_duplicatas)

CAP_MUITAS = "Localizar e unir duplicatas — 1 de muitas"


# ---------------------------------------------------------------------------------------------- utilidades
class Cenario:
    """Monta Merger + KommoSimulado + RelogioFalso e uma sessão falsa que registra o fechamento."""

    def __init__(self, limite=3, total=10, tipo="contatos", job_tipo=None, sim_kw=None, debug=False,
                 empresa="acme", **job_kw):
        self.rel = RelogioFalso()
        self.sim = KommoSimulado(self.rel, total, tipo=tipo, empresa=empresa, **(sim_kw or {}))
        self.fila = queue.Queue()
        self.fechou = []
        job_kw.setdefault("confirmar_conta", False)
        self.job = Job(empresa, job_tipo or tipo, limite, **job_kw)

        @contextmanager
        def sessao():
            try:
                yield self.sim
            finally:
                self.fechou.append(True)

        self.m = Merger(self.job, self.fila, threading.Event(), relogio=self.rel, abrir_sessao=sessao, debug=debug)
        self.eventos = []

    def rodar(self):
        self.m.run()
        while True:
            try:
                self.eventos.append(self.fila.get_nowait())
            except queue.Empty:
                break
        return self.fim

    @property
    def fins(self):
        return [e for e in self.eventos if isinstance(e, FimEvt)]

    @property
    def fim(self) -> FimEvt:
        assert len(self.fins) == 1, "FimEvt deve ser emitido exatamente uma vez"
        return self.fins[0]

    def logs(self, nivel=None):
        return [e.msg for e in self.eventos if isinstance(e, LogEvt) and (nivel is None or e.nivel == nivel)]

    def texto(self):
        return "\n".join(self.logs())

    def n(self, nome):
        return self.sim.chamadas.count(nome)


def checar_seguranca(c: Cenario):
    """Invariantes que valem em QUALQUER cenário."""
    f = c.fim
    assert c.eventos[-1] is f, "FimEvt é o último evento"
    assert c.fechou == [True], "o contexto do navegador sempre é fechado"
    assert all(fase == "grupo" for fase in c.sim.fases_cliques), "clique em Unir só com o botão visível"
    assert not any(fase in ("unindo", "concluido") for fase in c.sim.fases_fechar), \
        "nunca fecha/cancela o modal no meio de uma união"
    assert f.cliques == f.confirmadas + f.incertas
    assert f.feitos == f.confirmadas
    if c.job.limite:
        assert f.cliques <= c.job.limite, "o limite (cliques) nunca é ultrapassado"
    assert "Traceback" not in c.texto()


# ---------------------------------------------------------------------------------------------- caminho feliz
def test_caminho_feliz_para_exatamente_no_limite():
    c = Cenario(limite=3, total=10)
    f = c.rodar()
    checar_seguranca(c)
    assert (f.motivo, f.confirmadas, f.incertas, f.cliques) == ("limite", 3, 0, 3)
    assert c.sim.unioes == 3 and c.n("clicar_unir") == 3
    assert f.total == 10 and f.erros == 0 and not f.interrompido
    progs = [e for e in c.eventos if isinstance(e, ProgEvt)]
    assert progs[-1].feitos == 3 and progs[-1].total == 10 and progs[-1].limite == 3
    assert "União 3/3 confirmada" in c.texto()
    assert c.sim.privacidade and all(c.sim.privacidade)          # reforço da privacidade ligado


def test_todas_ate_acabar_conclui_sem_duplicatas():
    c = Cenario(limite=0, total=4)
    f = c.rodar()
    checar_seguranca(c)
    assert (f.motivo, f.confirmadas, f.cliques) == ("sem_duplicatas", 4, 4)
    assert c.sim.unioes == 4
    assert "Nenhuma duplicata restante" in c.texto()
    assert f.erros == 0


def test_sem_recarga_proximo_grupo_direto():
    c = Cenario(limite=5, total=10, sim_kw={"recarrega": False})
    f = c.rodar()
    checar_seguranca(c)
    assert (f.motivo, f.confirmadas) == ("limite", 5)


def test_lista_sem_nenhuma_duplicata():
    c = Cenario(limite=3, total=0)
    f = c.rodar()
    checar_seguranca(c)
    assert f.motivo == "sem_duplicatas" and f.cliques == 0 and c.n("clicar_unir") == 0


# ---------------------------------------------------------------------------------------------- INCERTO e limite
def test_leads_sem_texto_concluida_conta_pelo_modal_e_respeita_limite():
    """Leads real: o Kommo não mostra "concluída"; o modal fecha/recarrega e o contador do título anda = união feita."""
    c = Cenario(limite=5, total=50, tipo="leads",
                sim_kw={"texto_concluido": None, "texto_progresso": "Unindo leads", "caption": CAP_MUITAS})
    f = c.rodar()
    checar_seguranca(c)
    assert (f.motivo, f.confirmadas, f.incertas, f.cliques) == ("limite", 5, 0, 5)
    assert c.sim.unioes == 5
    assert f.total == 0                                         # "muitas"
    # cada texto de progresso distinto aparece uma vez (calibração), sem inundar o log
    assert sum("Unindo leads" in m for m in c.logs()) == 1


def test_incerto_reconfere_estado_antes_de_reclicar():
    c = Cenario(limite=3, total=10, sim_kw={"texto_concluido": None, "recarrega": False})
    f = c.rodar()
    checar_seguranca(c)
    assert f.confirmadas + f.incertas == 3 and f.cliques == 3
    ch = c.sim.chamadas
    idx = [i for i, n in enumerate(ch) if n == "clicar_unir"]
    for a, b in zip(idx, idx[1:]):
        # entre dois cliques: ao menos a leitura que deu o resultado e uma reconferência
        assert ch[a + 1:b].count("estado") >= 1


def test_uniao_sem_resultado_conta_como_clique_e_registra_erro():
    c = Cenario(limite=1, total=10, sim_kw={"dur_uniao": 10_000})
    f = c.rodar()
    checar_seguranca(c)
    assert (f.motivo, f.confirmadas, f.incertas, f.cliques) == ("limite", 0, 1, 1)
    assert f.erros == 1
    assert "diagnostico-falso" in c.texto()                      # diagnóstico estrutural no log


def test_clique_que_falha_conta_e_tres_falhas_param():
    c = Cenario(limite=10, total=10)
    c.sim.resposta_unir = False
    f = c.rodar()
    checar_seguranca(c)
    assert f.motivo == "falhas" and f.cliques == merger.FALHAS_MAX and f.incertas == merger.FALHAS_MAX
    assert c.sim.unioes == 0


# ---------------------------------------------------------------------------------------------- PARAR
def test_parar_no_meio_da_uniao_espera_o_resultado():
    c = Cenario(limite=10, total=10)

    def gancho(nome):
        if nome == "estado" and c.sim.fase == "unindo" and not c.m.parar.is_set():
            c.m.solicitar_parada()
    c.sim.ao_chamar = gancho
    f = c.rodar()
    checar_seguranca(c)
    assert (f.motivo, f.confirmadas, f.incertas, f.cliques) == ("parado", 1, 0, 1)
    assert f.interrompido and f.erros == 0
    assert c.sim.unioes == 1
    # o modal só foi cancelado DEPOIS da conclusão
    assert c.sim.fases_fechar and c.sim.fases_fechar[0] not in ("unindo", "concluido")
    assert c.sim.chamadas.index("cancelar_modal") > c.sim.chamadas.index("clicar_unir")


def test_ui_setando_o_event_direto_equivale_a_parar():
    c = Cenario(limite=10, total=10)

    def gancho(nome):
        if nome == "estado" and c.sim.fase == "unindo":
            c.m.parar.set()                                    # UI atual (ui.py) faz isto
    c.sim.ao_chamar = gancho
    f = c.rodar()
    checar_seguranca(c)
    assert f.motivo == "parado" and f.confirmadas == 1 and f.cliques == 1


def test_segundo_pedido_forca_saida_imediata():
    c = Cenario(limite=10, total=10)
    pedidos = []

    def gancho(nome):
        if nome == "estado" and c.sim.fase == "unindo" and len(pedidos) < 2:
            pedidos.append(1)
            c.m.solicitar_parada()                             # 1º: normal; 2º: forçado
    c.sim.ao_chamar = gancho
    f = c.rodar()
    checar_seguranca(c)
    assert len(pedidos) == 2
    assert (f.motivo, f.confirmadas, f.incertas, f.cliques) == ("forcado", 0, 1, 1)
    assert f.interrompido and f.erros == 0                     # Interrompido é aviso, não erro
    assert c.sim.fases_fechar == []                            # não clicou Cancelar/fechar: só fechou o navegador
    assert c.m.parada_forcada


def test_parar_durante_a_busca_sai_sem_clicar():
    c = Cenario(limite=10, total=10)

    def gancho(nome):
        if nome == "estado" and c.sim.fase == "buscando":
            c.m.solicitar_parada()
    c.sim.ao_chamar = gancho
    f = c.rodar()
    checar_seguranca(c)
    assert f.motivo == "parado" and f.cliques == 0 and c.n("clicar_unir") == 0


# ---------------------------------------------------------------------------------------------- exceções / navegação
def test_excecao_no_meio_da_uniao_preserva_contadores_e_fecha():
    c = Cenario(limite=10, total=10)

    def gancho(nome):
        if nome == "estado" and c.sim.unioes == 2 and c.sim.fase == "unindo":
            raise RuntimeError("bug simulado")
    c.sim.ao_chamar = gancho
    f = c.rodar()
    checar_seguranca(c)
    assert (f.motivo, f.confirmadas, f.incertas, f.cliques) == ("erro", 1, 1, 2)
    assert f.erros >= 1
    assert "Erro inesperado: RuntimeError" in c.texto()


def test_navegador_fechado_no_meio_da_uniao():
    class TargetClosedError(Exception):
        pass

    c = Cenario(limite=10, total=10)

    def gancho(nome):
        if nome == "estado" and c.sim.fase == "unindo":
            raise TargetClosedError("Target page, context or browser has been closed")
    c.sim.ao_chamar = gancho
    f = c.rodar()
    checar_seguranca(c)
    assert f.motivo == "navegador_fechado" and f.incertas == 1 and f.cliques == 1
    assert "O navegador foi fechado" in c.texto()
    assert f.erros == 1                                         # havia união em andamento: é erro


def test_pagina_recarrega_durante_a_uniao_reabre_pelo_menu():
    c = Cenario(limite=2, total=10)
    c.sim.navegar_na_uniao = True
    f = c.rodar()
    checar_seguranca(c)
    assert (f.motivo, f.cliques, f.confirmadas) == ("limite", 2, 2)   # recarga após o clique = união feita
    assert len(c.sim.itens_clicados) == 2                         # abriu + reabriu pelo menu
    assert "Nenhuma duplicata restante" not in c.texto()


def test_excecao_do_roteiro_do_fakekommo():
    """FakeKommo simples (roteiro) levantando exceção no meio: FimEvt e fechamento garantidos."""
    rel = RelogioFalso()
    fake = FakeKommo([Estado(modal=True, pode=True, caption=CAPTION.format(n=5)),      # busca inicial
                      Estado(modal=True, pode=True, caption=CAPTION.format(n=5)),      # reconferência no laço
                      Estado(modal=True, progresso="Realizando união"),
                      ValueError("falha de leitura")],
                     url="https://acme.kommo.com/contacts/list/contacts/?skip_filter=Y")
    fechou = []

    @contextmanager
    def sessao():
        try:
            yield fake
        finally:
            fechou.append(True)
    fila = queue.Queue()
    Merger(Job("acme", "contatos", 3, confirmar_conta=False), fila, relogio=rel, abrir_sessao=sessao).run()
    evs = []
    while not fila.empty():
        evs.append(fila.get_nowait())
    fins = [e for e in evs if isinstance(e, FimEvt)]
    assert len(fins) == 1 and evs[-1] is fins[0]
    assert (fins[0].motivo, fins[0].cliques, fins[0].incertas) == ("erro", 1, 1)
    assert fechou == [True]


def test_falha_ao_abrir_o_navegador_ainda_emite_fim():
    fila = queue.Queue()

    @contextmanager
    def sessao():
        raise browser.NavegadorIndisponivel("Não consegui abrir um navegador.")
        yield  # pragma: no cover

    Merger(Job("acme", "leads", 1), fila, relogio=RelogioFalso(), abrir_sessao=sessao).run()
    evs = [fila.get_nowait() for _ in range(fila.qsize())]
    assert isinstance(evs[-1], FimEvt) and evs[-1].motivo == "navegador_indisponivel" and evs[-1].erros == 1


# ---------------------------------------------------------------------------------------------- "Algo deu errado"
def test_algo_deu_errado_tenta_reabre_uma_vez_e_falha():
    c = Cenario(limite=10, total=10)

    def gancho(nome):
        if nome == "clicar_unir":
            c.sim.erros_busca = 1000                           # todas as buscas seguintes dão erro
    c.sim.ao_chamar = gancho
    f = c.rodar()
    checar_seguranca(c)
    assert f.motivo == "erro" and f.confirmadas == 1 and f.cliques == 1
    assert c.n("tentar_novamente") == merger.ERRO_TENTATIVAS   # contador COMPARTILHADO no ciclo
    assert len(c.sim.itens_clicados) == 2                       # abriu + 1 reabertura
    assert "continua mostrando 'Algo deu errado'" in c.texto()
    assert "Nenhuma duplicata restante" not in c.texto()


def test_erro_some_e_volta_ao_normal():
    c = Cenario(limite=3, total=10)
    c.sim.erros_busca = 2
    f = c.rodar()
    checar_seguranca(c)
    assert f.motivo == "limite" and f.confirmadas == 3 and c.n("tentar_novamente") == 2


def test_houve_erro_persiste_durante_o_carregamento():
    """Erro -> Tentar novamente -> carregando para sempre: NÃO pode virar "sem duplicatas"."""
    c = Cenario(limite=10, total=10)

    def gancho(nome):
        if nome == "clicar_unir":
            c.sim.erros_busca = 1
        if nome == "tentar_novamente":
            c.sim.busca_infinita = True
    c.sim.ao_chamar = gancho
    f = c.rodar()
    checar_seguranca(c)
    assert f.motivo == "erro"
    assert len(c.sim.itens_clicados) == 2                       # reabriu uma vez antes de desistir
    assert "Nenhuma duplicata restante" not in c.texto()


# ---------------------------------------------------------------------------------------------- sessão / fim
def test_sessao_expirada_nao_vira_concluido():
    c = Cenario(limite=10, total=10)
    c.sim.expira_apos = 1
    f = c.rodar()
    checar_seguranca(c)
    assert f.motivo == "sessao_expirada" and f.confirmadas == 1
    assert f.erros >= 1
    assert "Nenhuma duplicata restante" not in c.texto()
    assert "www.kommo.com" in c.texto()                         # mostra o host atual (sem PII)


# ---------------------------------------------------------------------------------------------- validação pré-clique
def test_tipo_errado_aborta_sem_abrir_nem_clicar():
    c = Cenario(limite=3, tipo="contatos", job_tipo="leads")
    f = c.rodar()
    checar_seguranca(c)
    assert f.motivo == "validacao" and c.n("clicar_unir") == 0 and c.sim.itens_clicados == []


@pytest.mark.parametrize("url", ["https://outra.kommo.com/contacts/list/contacts/",
                                 "https://acme.kommo.com.evil.io/contacts/list/contacts/"])
def test_hostname_muda_antes_do_clique_aborta(url):
    c = Cenario(limite=3)

    def gancho(nome):
        if nome == "clicar_item_duplicatas":
            c.sim.url = url
    c.sim.ao_chamar = gancho
    f = c.rodar()
    checar_seguranca(c)
    assert f.motivo == "validacao" and c.n("clicar_unir") == 0


def test_modal_que_nao_e_de_duplicatas_aborta():
    c = Cenario(limite=3, sim_kw={"caption": "Exportar contatos — 1 de {n}"})
    f = c.rodar()
    checar_seguranca(c)
    assert f.motivo == "validacao" and c.n("clicar_unir") == 0
    assert f.erros == 1


def test_validacoes_puras():
    assert caminho_confere("https://acme.kommo.com/leads/list/pipeline/1", "leads")
    assert caminho_confere("https://acme.kommo.com/contacts/list/contacts/?skip_filter=Y", "contatos")
    assert not caminho_confere("https://acme.kommo.com/contacts/list/", "leads")
    assert not caminho_confere("https://acme.kommo.com/leadsx/", "leads")
    assert not caminho_confere("https://acme.kommo.com/leads/", "empresas")
    assert modal_de_duplicatas("Localizar e unir duplicatas — 1 de 5")
    assert modal_de_duplicatas("Find and merge duplicates")
    assert not modal_de_duplicatas("") and not modal_de_duplicatas("Exportar")


# ---------------------------------------------------------------------------------------------- ensaio e confirmação
def test_ensaio_nao_clica_em_unir():
    c = Cenario(limite=5, ensaio=True)
    f = c.rodar()
    checar_seguranca(c)
    assert f.motivo == "ensaio" and f.cliques == 0 and c.n("clicar_unir") == 0
    assert f.total == 10 and c.n("cancelar_modal") == 1


def test_confirmacao_sem_resposta_nao_clica():
    c = Cenario(limite=5, confirmar_conta=True)
    f = c.rodar()
    checar_seguranca(c)
    conf = [e for e in c.eventos if isinstance(e, ConfirmarEvt)]
    assert conf == [ConfirmarEvt("acme.kommo.com", "contatos", 10, 5, False)]
    assert f.motivo == "sem_resposta" and c.n("clicar_unir") == 0
    assert c.rel.decorrido >= merger.TEMPO_CONFIRMACAO


def test_confirmacao_recusada_nao_clica():
    c = Cenario(limite=5, confirmar_conta=True)
    c.rel.ao_dormir = lambda t: c.m.responder(False)
    f = c.rodar()
    checar_seguranca(c)
    assert f.motivo == "recusado" and c.n("clicar_unir") == 0 and f.erros == 0


def test_confirmacao_aceita_segue():
    c = Cenario(limite=2, confirmar_conta=True)
    c.rel.ao_dormir = lambda t: c.m.responder(True)
    f = c.rodar()
    checar_seguranca(c)
    assert f.motivo == "limite" and f.confirmadas == 2


def test_ensaio_tambem_pede_confirmacao_quando_ligada():
    c = Cenario(limite=2, confirmar_conta=True, ensaio=True)
    c.rel.ao_dormir = lambda t: c.m.responder(True)
    f = c.rodar()
    assert f.motivo == "ensaio" and c.n("clicar_unir") == 0
    assert [e.ensaio for e in c.eventos if isinstance(e, ConfirmarEvt)] == [True]


def test_parar_durante_a_confirmacao():
    c = Cenario(limite=5, confirmar_conta=True)
    c.rel.ao_dormir = lambda t: c.m.solicitar_parada() if any(isinstance(e, ConfirmarEvt)
                                                               for e in list(c.fila.queue)) else None
    f = c.rodar()
    checar_seguranca(c)
    assert f.motivo == "parado" and c.n("clicar_unir") == 0


# ---------------------------------------------------------------------------------------------- login
def _deslogar(sim):
    sim.url = "https://www.kommo.com/oauth/login/"
    sim.menu_presente = False


def test_login_espera_com_reavisos_e_continua():
    c = Cenario(limite=1)
    _deslogar(c.sim)

    def ao_dormir(t):
        if c.rel.decorrido >= 130:
            c.sim.url = "https://acme.kommo.com/contacts/list/contacts/?skip_filter=Y"
            c.sim.menu_presente = True
    c.rel.ao_dormir = ao_dormir
    f = c.rodar()
    checar_seguranca(c)
    assert f.motivo == "limite" and f.confirmadas == 1
    avisos = c.logs("aviso")
    assert sum("Faça login" in m for m in avisos) == 1
    reavisos = [m for m in avisos if "Ainda aguardando o login" in m]
    assert len(reavisos) == 2 and "www.kommo.com" in reavisos[0]


def test_login_teto_da_erro_claro():
    c = Cenario(limite=1)
    _deslogar(c.sim)
    f = c.rodar()
    checar_seguranca(c)
    assert f.motivo == "login_timeout" and f.erros == 1 and c.n("clicar_unir") == 0
    assert merger.TEMPO_LOGIN <= c.rel.decorrido < merger.TEMPO_LOGIN + 10


def test_login_hostname_por_substring_nao_vale():
    c = Cenario(limite=1)
    c.sim.url = "https://xacme.kommo.com/contacts/list/contacts/"
    f = c.rodar()
    assert f.motivo == "login_timeout" and c.n("clicar_unir") == 0


def test_navegador_fechado_durante_o_login_mensagem_amigavel():
    c = Cenario(limite=1)
    _deslogar(c.sim)
    c.rel.ao_dormir = lambda t: setattr(c.sim, "fechado", c.rel.decorrido >= 10)
    f = c.rodar()
    checar_seguranca(c)
    assert f.motivo == "navegador_fechado" and f.erros == 0      # sem união: aviso, não erro
    assert "O navegador foi fechado" in c.texto()
    assert "Error" not in c.texto()


def test_parar_antes_do_login():
    c = Cenario(limite=1)
    _deslogar(c.sim)
    c.rel.ao_dormir = lambda t: c.m.solicitar_parada()
    f = c.rodar()
    assert f.motivo == "parado" and f.erros == 0 and f.interrompido


def test_login_teto_reavisa_a_cada_minuto():
    """A espera do login não encerra cedo: dura TEMPO_LOGIN e reavisa a cada REAVISO_LOGIN s."""
    c = Cenario(limite=1)
    _deslogar(c.sim)
    f = c.rodar()
    assert f.motivo == "login_timeout"
    reavisos = [m for m in c.logs("aviso") if "Ainda aguardando o login" in m]
    assert len(reavisos) == merger.TEMPO_LOGIN // merger.REAVISO_LOGIN - 1
    assert "espera mais ~" in reavisos[0]


# ---------------------------------------------------------------------------------------------- T10: troca de aba
# Bug T10: no login/redirecionamento a aba original era fechada/substituída por outra aba do mesmo contexto e o
# motor concluía "O navegador foi fechado" ~10 s depois de abrir, fechando o Chrome antes do login.
EMPRESAS_T10 = ["teste", "acme-demo"]   # subdomínios fictícios (simulados, sem rede)


def _login_em(c, t_login):
    """Simula o usuário terminando o login (na aba que o motor estiver usando) no instante `t_login`."""
    anterior = c.rel.ao_dormir

    def ao_dormir(t):
        if anterior:
            anterior(t)
        if c.rel.decorrido >= t_login and not c.sim.fechado:
            c.sim.url = montar_url(c.job.empresa, c.job.tipo)
            c.sim.menu_presente = True
    c.rel.ao_dormir = ao_dormir


@pytest.mark.parametrize("empresa", EMPRESAS_T10)
def test_t10_aba_original_fechada_com_outra_aberta_continua_esperando_o_login(empresa):
    c = Cenario(limite=1, tipo="leads", empresa=empresa, ensaio=True)
    _deslogar(c.sim)
    trocou = []

    def ao_dormir(t):
        if c.rel.decorrido >= 10 and not trocou:      # ~10 s: o Kommo/Chrome troca a aba do login
            trocou.append(t)
            c.sim.fechado = True
            c.sim.outras_paginas = ["https://www.kommo.com/oauth/login/"]
    c.rel.ao_dormir = ao_dormir
    _login_em(c, 200)
    f = c.rodar()
    checar_seguranca(c)
    assert f.motivo == "ensaio" and f.cliques == 0 and c.n("clicar_unir") == 0
    assert c.sim.adocoes == ["https://www.kommo.com/oauth/login/"]
    assert "O navegador foi fechado" not in c.texto()
    assert any("passou a acompanhar a outra aba" in m for m in c.logs("aviso"))
    assert f"Login confirmado ({empresa}.kommo.com)" in c.texto()
    assert c.rel.decorrido >= 200                      # esperou o login de verdade


@pytest.mark.parametrize("empresa", EMPRESAS_T10)
def test_t10_aba_nova_aparece_logo_depois_dentro_da_tolerancia(empresa):
    """A troca não é atômica: a aba original some e a nova só aparece 1,5 s depois — não pode encerrar."""
    c = Cenario(limite=1, tipo="leads", empresa=empresa, ensaio=True)
    _deslogar(c.sim)
    marcos = {}

    def ao_dormir(t):
        d = c.rel.decorrido
        if d >= 10 and "fechou" not in marcos:
            marcos["fechou"] = d
            c.sim.fechado = True
        elif "fechou" in marcos and "abriu" not in marcos and d >= marcos["fechou"] + 1.5:
            marcos["abriu"] = d
            c.sim.outras_paginas = ["https://www.kommo.com/oauth/login/"]
    c.rel.ao_dormir = ao_dormir
    _login_em(c, 100)
    f = c.rodar()
    checar_seguranca(c)
    assert f.motivo == "ensaio" and c.sim.adocoes and "O navegador foi fechado" not in c.texto()


@pytest.mark.parametrize("empresa", EMPRESAS_T10)
def test_t10_todas_as_abas_fechadas_encerra_com_aviso(empresa):
    c = Cenario(limite=1, tipo="leads", empresa=empresa)
    _deslogar(c.sim)
    c.rel.ao_dormir = lambda t: setattr(c.sim, "fechado", True) if c.rel.decorrido >= 10 else None
    f = c.rodar()
    checar_seguranca(c)
    assert f.motivo == "navegador_fechado" and f.erros == 0 and c.n("clicar_unir") == 0
    assert c.sim.adocoes == [] and c.sim.paginas_abertas() == 0
    assert "O navegador foi fechado" in c.texto()
    assert c.rel.decorrido < 10 + merger.POLL_LOGIN + merger.GRACA_FECHAMENTO + 1   # encerra logo (tolerância curta)


def test_t10_aba_adotada_de_outra_conta_nao_clica():
    """Depois do login, a aba usada fecha e sobra uma de OUTRA conta: adota, mas a validação aborta sem clicar."""
    c = Cenario(limite=3, tipo="leads")

    def gancho(nome):
        if nome == "clicar_item_duplicatas" and not c.sim.adocoes:
            c.sim.fechado = True
            c.sim.outras_paginas = ["https://outra.kommo.com/leads/list/"]
    c.sim.ao_chamar = gancho
    f = c.rodar()
    checar_seguranca(c)
    assert c.sim.adocoes == ["https://outra.kommo.com/leads/list/"]
    assert f.motivo == "validacao" and c.n("clicar_unir") == 0 and f.cliques == 0


def test_t10_parada_forcada_durante_a_tolerancia():
    c = Cenario(limite=1)
    _deslogar(c.sim)

    def ao_dormir(t):
        if c.rel.decorrido >= 10:
            c.sim.fechado = True
        if c.rel.decorrido >= 11:
            c.m.solicitar_parada(forcar=True)
    c.rel.ao_dormir = ao_dormir
    f = c.rodar()
    assert f.motivo == "forcado" and f.cliques == 0


# ---------------------------------------------------------------------------------------------- privacidade / diag.
def test_privacidade_reforco_espacado_e_desligada_sem_chamadas():
    c = Cenario(limite=5)
    c.rodar()
    reforcos = c.n("aplicar_privacidade")
    assert 0 < reforcos <= c.rel.decorrido / merger.INTERVALO_PRIVACIDADE + 3
    assert reforcos < c.n("estado") / 5                          # bem menos que a amostragem

    c2 = Cenario(limite=2, privacidade=False)
    c2.rodar()
    assert c2.n("aplicar_privacidade") == 0


def test_screenshot_so_com_debug(monkeypatch, tmp_path):
    c = Cenario(limite=1, sim_kw={"dur_uniao": 10_000})
    c.rodar()
    assert c.sim.screenshots == []

    monkeypatch.setattr(merger.paths, "debug_dir", lambda: str(tmp_path))
    c2 = Cenario(limite=1, sim_kw={"dur_uniao": 10_000}, debug=True)
    c2.rodar()
    assert len(c2.sim.screenshots) == 1
    ch = c2.sim.chamadas
    assert ch[ch.index("screenshot") - 1] == "aplicar_privacidade"   # privacidade aplicada antes da captura


# ---------------------------------------------------------------------------------------------- API / thread
def test_eventos_compativeis_com_a_ui():
    assert ProgEvt(1, 2, 3) == ProgEvt(feitos=1, limite=2, total=3, incertas=0, cliques=0)
    f = FimEvt(1, 2.0, 0, False, 10)
    assert (f.confirmadas, f.incertas, f.cliques, f.motivo, f.avisos) == (0, 0, 0, "", 0)
    j = Job("acme", "leads", 5, True)
    assert j.ensaio is False and j.confirmar_conta is True


def test_thread_nao_daemon_e_parar_e_aguardar():
    c = Cenario(limite=2)
    assert c.m.daemon is False
    c.m.start()
    assert c.m.parar_e_aguardar(timeout=30) is True
    assert not c.m.is_alive()
    fins = []
    while not c.fila.empty():
        ev = c.fila.get_nowait()
        if isinstance(ev, FimEvt):
            fins.append(ev)
    assert len(fins) == 1 and c.fechou == [True]


def test_solicitar_parada_duas_vezes_forca():
    m = Merger(Job("acme", "leads", 1), queue.Queue())
    m.solicitar_parada()
    assert m.parar.is_set() and not m.parada_forcada
    m.solicitar_parada()
    assert m.parada_forcada
    m2 = Merger(Job("acme", "leads", 1), queue.Queue())
    m2.solicitar_parada(forcar=True)
    assert m2.parada_forcada


# ---------------------------------------------------------------------------------------------- sessão Playwright
class _PageStub:
    def __init__(self, falhas_goto=()):
        self.falhas_goto = list(falhas_goto)
        self.gotos = []
        self.timeouts = {}
        self.url = "about:blank"
        self.fechada = False

    def set_default_timeout(self, ms):
        self.timeouts["padrao"] = ms

    def set_default_navigation_timeout(self, ms):
        self.timeouts["navegacao"] = ms

    def goto(self, url, wait_until=None, timeout=None):
        assert timeout
        self.gotos.append(url)
        if self.falhas_goto:
            raise self.falhas_goto.pop(0)
        self.url = url

    def is_closed(self):
        return self.fechada


class _CtxStub:
    def __init__(self, page):
        self.pages = [page]
        self.scripts = []
        self.fechado = 0

    def add_init_script(self, script):
        self.scripts.append(script)

    def close(self):
        self.fechado += 1


class _PW:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _preparar_sessao(monkeypatch, page, executar):
    import playwright.sync_api as sapi
    ctx = _CtxStub(page)
    salvos = {}
    monkeypatch.setattr(sapi, "sync_playwright", lambda: _PW())
    monkeypatch.setattr(merger.paths, "profile_dir", lambda: "perfil-falso")
    monkeypatch.setattr(merger.config, "carregar", lambda: {"canal_navegador": "msedge"})
    monkeypatch.setattr(merger.config, "salvar", lambda **kw: salvos.update(kw))

    def abrir(p, perfil, log, *, canal_preferido=None, info=None):
        assert canal_preferido == "msedge" and perfil == "perfil-falso"
        info["canal"] = "chrome"
        return ctx
    monkeypatch.setattr(merger.browser, "abrir_contexto", abrir)
    monkeypatch.setattr(Merger, "_executar", executar)
    return ctx, salvos


def test_sessao_playwright_init_script_canal_e_fecha(monkeypatch):
    page = _PageStub(falhas_goto=[type("TimeoutError", (Exception,), {})("Timeout 60000ms exceeded")])
    portas = []

    def executar(self, porta):
        portas.append(porta)
        return "ensaio"
    ctx, salvos = _preparar_sessao(monkeypatch, page, executar)
    fila = queue.Queue()
    Merger(Job("acme", "leads", 1, privacidade=True), fila, relogio=RelogioFalso()).run()
    evs = [fila.get_nowait() for _ in range(fila.qsize())]
    assert evs[-1].motivo == "ensaio"
    assert ctx.fechado == 1                                      # B1: sempre fecha
    assert len(ctx.scripts) == 1 and "__kpSet" in ctx.scripts[0] and '"on": true' in ctx.scripts[0]
    assert salvos == {"canal_navegador": "chrome"}
    assert len(page.gotos) == 2                                  # M10: 2 tentativas
    assert page.timeouts["padrao"] == merger.TIMEOUT_PAGINA_MS
    assert portas and portas[0].page is page                     # KommoPage sobre a page


def test_sessao_playwright_fecha_mesmo_com_excecao_e_navegador_fechado(monkeypatch):
    page = _PageStub(falhas_goto=[Exception("Target page, context or browser has been closed")])
    ctx, _ = _preparar_sessao(monkeypatch, page, lambda self, porta: "ensaio")
    fila = queue.Queue()
    Merger(Job("acme", "contatos", 1), fila, relogio=RelogioFalso()).run()
    evs = [fila.get_nowait() for _ in range(fila.qsize())]
    assert evs[-1].motivo == "navegador_fechado" and evs[-1].erros == 0
    assert ctx.fechado == 1


def test_sessao_playwright_aba_substituida_no_goto_adota_e_segue(monkeypatch):
    """T10 na abertura: a aba inicial fecha durante o goto, mas o contexto tem outra — navega nela e segue."""
    page = _PageStub(falhas_goto=[Exception("Target page, context or browser has been closed")])
    page.fechada = True
    outra = _PageStub()
    portas = []

    def executar(self, porta):
        portas.append(porta)
        return "ensaio"
    ctx, _ = _preparar_sessao(monkeypatch, page, executar)
    ctx.pages.append(outra)
    fila = queue.Queue()
    Merger(Job("teste", "leads", 1), fila, relogio=RelogioFalso()).run()
    evs = [fila.get_nowait() for _ in range(fila.qsize())]
    assert evs[-1].motivo == "ensaio"
    assert portas[0].page is outra and outra.gotos == ["https://teste.kommo.com/leads/list/"]
    assert outra.timeouts["padrao"] == merger.TIMEOUT_PAGINA_MS      # config por aba reaplicada
    assert ctx.fechado == 1


def test_sessao_playwright_config_quebrada_nao_derruba(monkeypatch):
    page = _PageStub()
    ctx, _ = _preparar_sessao(monkeypatch, page, lambda self, porta: "ensaio")

    def quebra(**kw):
        raise OSError("disco cheio")
    monkeypatch.setattr(merger.config, "salvar", quebra)
    fila = queue.Queue()
    Merger(Job("acme", "contatos", 1, privacidade=False), fila, relogio=RelogioFalso()).run()
    evs = [fila.get_nowait() for _ in range(fila.qsize())]
    assert evs[-1].motivo == "ensaio" and ctx.fechado == 1
    assert '"on": false' in ctx.scripts[0]


def test_job_invalido_nao_abre_sessao():
    aberta = []

    @contextmanager
    def sessao():
        aberta.append(True)
        yield FakeKommo()

    fila = queue.Queue()
    Merger(Job("acme", "empresas", 1), fila, relogio=RelogioFalso(), abrir_sessao=sessao).run()
    ev = [fila.get_nowait() for _ in range(fila.qsize())][-1]
    assert ev.motivo == "validacao" and aberta == []


# ---------------------------------------------------------------------------------------------- KOMMO_DEBUG
@pytest.mark.parametrize("valor", ["1", "true", "TRUE", "Yes", "on", " On "])
def test_kommo_debug_valores_verdadeiros_ligam(valor):
    assert merger.debug_ligado({"KOMMO_DEBUG": valor}) is True


@pytest.mark.parametrize("valor", ["0", "false", "FALSE", "no", "off", "", "   ", "2", "talvez"])
def test_kommo_debug_outros_valores_nao_ligam(valor):
    assert merger.debug_ligado({"KOMMO_DEBUG": valor}) is False


def test_kommo_debug_ausente_nao_liga_e_merger_usa_a_funcao(monkeypatch):
    assert merger.debug_ligado({}) is False
    monkeypatch.setenv("KOMMO_DEBUG", "0")
    assert Merger(Job("acme", "leads", 1), queue.Queue()).debug is False
    monkeypatch.setenv("KOMMO_DEBUG", "on")
    assert Merger(Job("acme", "leads", 1), queue.Queue()).debug is True
