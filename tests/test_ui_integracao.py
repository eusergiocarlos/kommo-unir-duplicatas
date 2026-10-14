"""Integração da janela (Tkinter) com um Merger FALSO: confirmação da conta, PARAR em dois níveis, fechamento
seguro, resumo, ensaio, esquecer login e inicialização robusta.

Nada aqui abre navegador nem fala com o Kommo: `ui.Merger` é trocado por `MergerFalso` (uma thread que só
espera ser liberada e anota as chamadas). Os dados vão para uma pasta temporária (KOMMO_DATA_DIR). Sem display,
os testes que abrem janela são pulados. Toda janela é destruída no fim (fixture).
"""
import threading
import time

import pytest

tk = pytest.importorskip("tkinter")

from kommo_duplicatas import config, kommo, paths, ui  # noqa: E402
from kommo_duplicatas.merger import ConfirmarEvt, FimEvt, LogEvt, ProgEvt  # noqa: E402


class MergerFalso(threading.Thread):
    """Mesmas assinaturas que a UI usa do Merger real; não abre nada. Fica vivo até `liberar`."""

    def __init__(self, job, fila, parar=None, **_kw):
        super().__init__(name="MergerFalso", daemon=True)
        self.job, self.fila, self.parar = job, fila, parar
        self.respostas: list[bool] = []
        self.paradas: list[bool] = []
        self.liberar = threading.Event()
        self.termina_ao_parar = False     # True: a 1ª parada (normal) já encerra a thread
        self.so_forcado = False           # True: só a parada forçada encerra a thread

    def run(self):
        self.liberar.wait(30)

    def solicitar_parada(self, forcar: bool = False) -> None:
        self.paradas.append(bool(forcar))
        if (self.termina_ao_parar and not self.so_forcado) or (self.so_forcado and forcar):
            self.liberar.set()

    def responder(self, aceito: bool) -> None:
        self.respostas.append(bool(aceito))

    def encerrar(self):
        self.liberar.set()
        self.join(5)


@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    monkeypatch.setenv("KOMMO_DATA_DIR", str(tmp_path))     # nunca toca os dados reais do usuário
    criados: list[MergerFalso] = []

    def fabrica(job, fila, parar=None, **kw):
        m = MergerFalso(job, fila, parar, **kw)
        criados.append(m)
        return m

    monkeypatch.setattr(ui, "Merger", fabrica)
    perguntas, erros = [], []
    respostas_sim_nao = {"valor": True}

    def askyesno(titulo, msg, **_kw):
        perguntas.append((titulo, msg))
        return respostas_sim_nao["valor"]

    monkeypatch.setattr(ui.messagebox, "askyesno", askyesno)
    monkeypatch.setattr(ui.messagebox, "showerror", lambda titulo, msg, **_kw: erros.append((titulo, msg)))
    return {"criados": criados, "perguntas": perguntas, "erros": erros, "sim_nao": respostas_sim_nao,
            "tmp": tmp_path}


def _nova_app():
    # No Windows o Tcl às vezes falha ao (re)ler auto.tcl quando muitas janelas Tk são criadas seguidas no mesmo
    # processo; tenta de novo antes de concluir que não há display.
    app, erro = None, None
    for _ in range(4):
        try:
            app = ui.App()
            break
        except tk.TclError as e:
            erro = e
            time.sleep(0.3)
    if app is None:
        pytest.skip(f"sem display: {erro}")
    app.destroidas = []
    original = app.destroy

    def destroy():                       # registra se a thread estava viva NO MOMENTO da destruição
        th = app.th
        app.destroidas.append(bool(th is not None and th.is_alive()))
        original()

    app.destroy = destroy
    return app


@pytest.fixture
def app(ambiente):
    a = _nova_app()
    try:
        a.update()
        yield a
    finally:
        for m in ambiente["criados"]:
            m.liberar.set()
        try:
            if not a.destroidas:
                a.destroy()
        except tk.TclError:
            pass


def bombear_ate(app, cond, timeout=5.0) -> bool:
    fim = time.monotonic() + timeout
    while time.monotonic() < fim:
        if cond():
            return True
        try:
            app.update()
        except tk.TclError:              # janela destruída
            return cond()
        time.sleep(0.02)
    return cond()


def log(app) -> str:
    return app.caixa.get("1.0", "end")


def iniciar(app, ambiente, empresa="acme", custom=""):
    app.empresa.set(empresa)
    app._empresa_vis.set(empresa)
    app.custom.set(custom)
    app.iniciar()
    assert app._rodando
    return ambiente["criados"][-1]


def confirmar_evt(app, limite=100, total=42761, ensaio=False, privacidade=True):
    app.privacidade.set(privacidade)
    app.fila.put(ConfirmarEvt("acme.kommo.com", "leads", total, limite, ensaio))
    app.bombear()
    assert app._dlg_conf is not None, "o diálogo de confirmação deveria ter aberto"
    return app._dlg_conf


# ---------------------------------------------------------------------- iniciar
def test_iniciar_cria_job_sem_pergunta_previa(app, ambiente):
    m = iniciar(app, ambiente, custom="1.000")
    assert ambiente["perguntas"] == []                  # o askyesno antigo foi removido
    assert (m.job.empresa, m.job.tipo, m.job.limite, m.job.ensaio) == ("acme", "leads", 1000, False)
    assert m.job.confirmar_conta is True and m.parar is app.parar
    assert str(app.bt_ini["state"]) == "disabled" and str(app.bt_par["state"]) == "normal"
    assert str(app.bt_esquecer["state"]) == "disabled" and str(app.chk_ensaio["state"]) == "disabled"
    app.iniciar()                                       # duplo clique: ignorado
    assert len(ambiente["criados"]) == 1


def test_limite_custom_persistido_e_restaurado(app, ambiente):
    iniciar(app, ambiente, custom="300")
    assert config.carregar()["limite_custom"] == 300
    b = _nova_app()
    try:
        assert b.custom.get() == "300" and "vale 300" in b.lbl_custom["text"]
    finally:
        b.destroy()


def test_ensaio_muda_botao_e_job(app, ambiente):
    assert app.bt_ini["text"] == ui.TXT_INICIAR
    app.ensaio.set(True)
    assert app.bt_ini["text"] == ui.TXT_SIMULAR
    m = iniciar(app, ambiente)
    assert m.job.ensaio is True
    assert "ENSAIO" in log(app)
    assert "ensaio" not in config.carregar()            # não persistido


# ---------------------------------------------------------------------- confirmação da conta
def test_confirmacao_aceitar(app, ambiente):
    m = iniciar(app, ambiente)
    dlg = confirmar_evt(app)
    assert dlg.bt_ok["text"] == "Unir agora" and str(dlg.bt_ok["state"]) == "normal"
    dlg.bt_ok.invoke()
    assert m.respostas == [True]
    assert app._dlg_conf is None and not dlg.winfo_exists()


def test_confirmacao_cancelar_registra_no_log(app, ambiente):
    m = iniciar(app, ambiente)
    dlg = confirmar_evt(app)
    dlg.bt_cancelar.invoke()
    assert m.respostas == [False]
    assert ui.MSG_CANCELADO in log(app)
    assert not dlg.winfo_exists()


def test_confirmacao_fechar_no_x_responde_nao(app, ambiente):
    m = iniciar(app, ambiente)
    dlg = confirmar_evt(app)
    dlg.tk.call(dlg.protocol("WM_DELETE_WINDOW"))       # o mesmo comando que o X da janela dispara
    assert m.respostas == [False]
    assert not dlg.winfo_exists()


@pytest.mark.parametrize("tecla", ["<Escape>", "<Return>"])
def test_confirmacao_esc_e_enter_cancelam(app, ambiente, tecla):
    m = iniciar(app, ambiente)
    dlg = confirmar_evt(app)
    dlg.bt_cancelar.focus_force()                       # eventos de tecla vão para o widget com foco
    app.update()
    dlg.bt_cancelar.event_generate(tecla, when="now")
    app.update()
    assert m.respostas == [False]


def test_confirmacao_responde_uma_vez_so(app, ambiente):
    m = iniciar(app, ambiente)
    dlg = confirmar_evt(app)
    dlg.responder(True)
    dlg.responder(False)
    assert m.respostas == [True]


@pytest.mark.parametrize("limite", [0, 501, 10_000])
def test_confirmacao_exige_digitar_unir(app, ambiente, limite):
    m = iniciar(app, ambiente)
    dlg = confirmar_evt(app, limite=limite)
    assert dlg.ent_palavra is not None
    assert str(dlg.bt_ok["state"]) == "disabled"
    dlg.bt_ok.invoke()                                  # desabilitado: não faz nada
    dlg._confirmar()                                    # nem pelo método
    assert m.respostas == []
    dlg.palavra.set("UNI")
    assert str(dlg.bt_ok["state"]) == "disabled"
    dlg.palavra.set("unir")
    assert str(dlg.bt_ok["state"]) == "normal"
    dlg.ent_palavra.event_generate("<Return>")          # Enter no campo não confirma nem cancela
    app.update()
    assert m.respostas == []
    dlg.bt_ok.invoke()
    assert m.respostas == [True]


def test_confirmacao_500_nao_exige_digitar(app, ambiente):
    iniciar(app, ambiente)
    dlg = confirmar_evt(app, limite=500)
    assert dlg.ent_palavra is None and str(dlg.bt_ok["state"]) == "normal"
    dlg.bt_cancelar.invoke()


def test_confirmacao_privacidade_mascara_e_mostrar_conta(app, ambiente):
    iniciar(app, ambiente)
    dlg = confirmar_evt(app, privacidade=True)
    assert dlg.valores["Conta"]["text"] == "a***e.kommo.com"
    assert dlg.valores["Grupos de duplicatas na conta"]["text"] == ui.OCULTO
    assert dlg.bt_revelar is not None and dlg.bt_revelar["text"] == "Mostrar conta"
    dlg.bt_revelar.invoke()
    assert dlg.valores["Conta"]["text"] == "acme.kommo.com"
    assert dlg.valores["Grupos de duplicatas na conta"]["text"] == "42.761"
    assert dlg.bt_revelar["text"] == "Ocultar conta"
    dlg.bt_revelar.invoke()
    assert dlg.valores["Conta"]["text"] == "a***e.kommo.com"
    dlg.bt_cancelar.invoke()


def test_confirmacao_sem_privacidade_mostra_conta(app, ambiente):
    iniciar(app, ambiente)
    dlg = confirmar_evt(app, privacidade=False)
    assert dlg.valores["Conta"]["text"] == "acme.kommo.com" and dlg.bt_revelar is None
    dlg.bt_cancelar.invoke()


def test_confirmacao_ensaio_botao(app, ambiente):
    app.ensaio.set(True)
    m = iniciar(app, ambiente)
    dlg = confirmar_evt(app, limite=0, ensaio=True)
    assert dlg.bt_ok["text"] == "Fazer ensaio" and dlg.ent_palavra is None
    dlg.bt_ok.invoke()
    assert m.respostas == [True]


def test_confirmacao_fecha_sozinha_se_a_thread_termina(app, ambiente):
    m = iniciar(app, ambiente)
    dlg = confirmar_evt(app)
    m.encerrar()
    app.bombear()
    assert app._dlg_conf is None and not dlg.winfo_exists()
    assert "terminou antes da confirmação" in log(app)


def test_confirmacao_fecha_quando_chega_o_fim(app, ambiente):
    m = iniciar(app, ambiente)
    dlg = confirmar_evt(app)
    app.fila.put(FimEvt(0, 600, 0, False, 42761, 0, 0, 0, "sem_resposta", 1))
    app.bombear()
    assert not dlg.winfo_exists() and app._dlg_conf is None
    assert str(app.bt_ini["state"]) == "normal"
    m.encerrar()


# ---------------------------------------------------------------------- PARAR e fim
def test_parar_dois_niveis_e_fim_reabilita(app, ambiente):
    m = iniciar(app, ambiente)
    app.bt_par.invoke()
    assert m.paradas == [False]
    assert app.bt_par["text"] == ui.TXT_FORCAR and str(app.bt_par["state"]) == "normal"
    assert ui.MSG_PARANDO in log(app)
    app.bt_par.invoke()
    assert m.paradas == [False, True]
    assert str(app.bt_par["state"]) == "disabled"
    assert "Parada forçada" in log(app) and "confira no Kommo" in log(app)
    app.bt_par.invoke()                                 # 3º clique: nada
    assert m.paradas == [False, True]

    m.encerrar()
    app.fila.put(ProgEvt(3, 100, 42761, 1, 4))
    app.fila.put(FimEvt(3, 12.0, 0, True, 42761, 3, 1, 4, "forcado", 1))
    app.bombear()
    assert str(app.bt_ini["state"]) == "normal" and str(app.bt_par["state"]) == "disabled"
    assert app.bt_par["text"] == ui.TXT_PARAR and app.bt_ini["text"] == ui.TXT_INICIAR
    assert str(app.bt_esquecer["state"]) == "normal" and str(app.chk_ensaio["state"]) == "normal"
    assert app.contador["text"] == "3" and "1 não confirmada" in app.lbl["text"]
    d = app._dlg_resumo
    textos = [w["text"] for w in d.winfo_children() if isinstance(w, tk.Label)]
    assert "1 não confirmada — confira no Kommo" in textos
    assert any(t.startswith("Motivo: parada forçada") for t in textos)
    assert any(ui.OCULTO in t for t in textos) and not any("42.761" in t for t in textos)
    assert config.carregar()["ultimo_total"] == 0       # 'forcado' não registra
    d.destroy()


def test_fim_registra_execucao_quando_motivo_normal(app, ambiente):
    m = iniciar(app, ambiente)
    m.encerrar()
    app.fila.put(FimEvt(10, 30.0, 0, False, 500, 10, 0, 10, "limite", 0))
    app.bombear()
    assert config.carregar()["ultimo_total"] == 500
    app._dlg_resumo.destroy()


def test_resumo_do_ensaio(app, ambiente):
    app.ensaio.set(True)
    m = iniciar(app, ambiente)
    m.encerrar()
    app.fila.put(FimEvt(0, 8.0, 0, False, 42761, 0, 0, 0, "ensaio", 0))
    app.bombear()
    d = app._dlg_resumo
    assert d.title() == "Resumo do ensaio"
    textos = [w["text"] for w in d.winfo_children() if isinstance(w, tk.Label)]
    assert "nada foi unido" in textos and "Conta, lista e modal de duplicatas conferidos." in textos
    assert config.carregar()["ultimo_total"] == 0
    d.destroy()


def test_logs_do_motor_sao_mascarados(app, ambiente):
    m = iniciar(app, ambiente)
    app.privacidade.set(True)
    app.fila.put(LogEvt("ok", "Login confirmado (acme.kommo.com)."))
    app.fila.put(LogEvt("ok", "Total de grupos de duplicatas informado pelo Kommo: 42.761"))
    app.bombear()
    texto = log(app)
    assert "a***e.kommo.com" in texto and "acme" not in texto and "42.761" not in texto
    m.encerrar()


# ---------------------------------------------------------------------- fechar a janela
def test_fechar_sem_thread_fecha_direto(app, ambiente):
    app.fechar()
    assert app.destroidas == [False] and ambiente["perguntas"] == []


def test_fechar_com_thread_e_resposta_nao_mantem_tudo(app, ambiente):
    m = iniciar(app, ambiente)
    ambiente["sim_nao"]["valor"] = False
    app.fechar()
    assert ambiente["perguntas"] and "Parar e fechar?" in ambiente["perguntas"][-1][1]
    assert m.paradas == [] and app.destroidas == [] and not app._fechando


def test_fechar_com_thread_espera_ela_terminar(app, ambiente):
    m = iniciar(app, ambiente)
    dlg = confirmar_evt(app)                            # com confirmação pendente: vira NÃO
    app.INTERVALO_FECHAR_MS = 20
    app.fechar()
    assert m.paradas == [False] and m.respostas == [False]
    assert not dlg.winfo_exists()
    assert "Encerrando" in app.title()
    bombear_ate(app, lambda: False, timeout=0.4)        # thread viva: a janela NÃO pode ser destruída
    assert app.destroidas == [] and app.winfo_exists()
    m.liberar.set()
    assert bombear_ate(app, lambda: bool(app.destroidas), timeout=5)
    assert app.destroidas == [False]                    # destruída só com a thread morta


def test_fechar_forca_depois_do_teto(app, ambiente):
    m = iniciar(app, ambiente)
    m.so_forcado = True                                 # ignora a parada normal
    app.INTERVALO_FECHAR_MS = 20
    app.TETO_FECHAR = 0.3
    app.fechar()
    assert bombear_ate(app, lambda: bool(app.destroidas), timeout=5)
    assert m.paradas == [False, True]
    assert app.destroidas == [False]


def test_fechar_thread_travada_avisa_e_nao_destroi(app, ambiente):
    m = iniciar(app, ambiente)
    m.solicitar_parada = lambda forcar=False: m.paradas.append(forcar)   # nunca termina
    app.INTERVALO_FECHAR_MS = 20
    app.TETO_FECHAR = 0.1
    app.TETO_FORCAR = 0.1
    app.fechar()
    assert bombear_ate(app, lambda: app._avisou_travado, timeout=5)
    assert app.destroidas == [] and m.paradas == [False, True]
    assert "Feche a janela do navegador" in log(app)
    m.liberar.set()
    assert bombear_ate(app, lambda: bool(app.destroidas), timeout=5)
    assert app.destroidas == [False]


# ---------------------------------------------------------------------- esquecer login
def test_esquecer_login_ok_e_vazio(app, ambiente, monkeypatch):
    chamadas = []
    monkeypatch.setattr(ui.paths, "esquecer_login", lambda: chamadas.append(1) or len(chamadas) == 1)
    app.bt_esquecer.invoke()
    assert "Esquecer login" == ambiente["perguntas"][-1][0] and ui.MSG_ESQUECER in ambiente["perguntas"][-1][1]
    assert "Login salvo do Kommo apagado" in log(app)
    app.bt_esquecer.invoke()
    assert "Não havia login salvo" in log(app)


def test_esquecer_login_erro_mostra_mensagem(app, ambiente, monkeypatch):
    def falha():
        raise paths.EsquecerLoginErro("Feche a janela do navegador aberta pelo app.")
    monkeypatch.setattr(ui.paths, "esquecer_login", falha)
    app.bt_esquecer.invoke()
    assert ambiente["erros"] and "Feche a janela do navegador" in ambiente["erros"][-1][1]
    assert "Não foi possível esquecer o login" in log(app)


def test_esquecer_login_cancelado_e_bloqueado_rodando(app, ambiente, monkeypatch):
    chamadas = []
    monkeypatch.setattr(ui.paths, "esquecer_login", lambda: chamadas.append(1))
    ambiente["sim_nao"]["valor"] = False
    app.esquecer_login()
    assert chamadas == []
    ambiente["sim_nao"]["valor"] = True
    iniciar(app, ambiente)
    app.esquecer_login()                                # thread viva: ignorado
    assert chamadas == [] and str(app.bt_esquecer["state"]) == "disabled"


# ---------------------------------------------------------------------- inicialização e erros do Tk
def test_main_data_dir_nao_gravavel_mostra_erro_e_nao_abre(ambiente, monkeypatch):
    def nao_gravavel(*_a, **_kw):
        raise paths.DataDirNotWritable("C:\\pasta\\protegida", "PermissionError")
    monkeypatch.setattr(ui.paths, "ensure_writable", nao_gravavel)

    def app_proibida():
        raise AssertionError("a janela principal não pode abrir")
    monkeypatch.setattr(ui, "App", app_proibida)
    assert ui.main() == 1
    assert ambiente["erros"], "deveria mostrar messagebox.showerror"
    titulo, msg = ambiente["erros"][-1]
    assert "Não consigo gravar" in msg and "KOMMO_DATA_DIR" in msg


def test_excecao_em_callback_nao_derruba_a_janela(app, ambiente):
    app.after(0, lambda: 1 / 0)
    assert bombear_ate(app, lambda: bool(ambiente["erros"]), timeout=3)
    assert "Erro inesperado na interface (ZeroDivisionError)" in log(app)
    assert app.winfo_exists() and str(app.bt_ini["state"]) == "normal"


# ---------------------------------------------------------------------- porta: esta_fechada (usada pelo motor)
def test_kommopage_esta_fechada():
    class Pg:
        def __init__(self, v):
            self.v = v

        def is_closed(self):
            if isinstance(self.v, Exception):
                raise self.v
            return self.v

    assert kommo.KommoPage(Pg(True)).esta_fechada() is True
    assert kommo.KommoPage(Pg(False)).esta_fechada() is False
    assert kommo.KommoPage(Pg(RuntimeError("x"))).esta_fechada() is False
    assert kommo.KommoPage(object()).esta_fechada() is False
    assert isinstance(kommo.KommoPage(Pg(False)), kommo.PortaKommo)
