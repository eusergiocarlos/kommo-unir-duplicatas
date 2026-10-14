"""Interface (Tkinter) nas cores do Kommo: empresa, o que unir, quantidade, modo privacidade, contador e log.

Privacidade na própria janela: com a opção ligada, o app também se protege ao ser gravado/apresentado —
o subdomínio aparece mascarado ("a***e") no campo Empresa (enquanto ele não está sendo editado), nas
mensagens, no diálogo de confirmação e no arquivo de log; o total de duplicatas da conta vira "••••" no
contador, no log e no resumo. O valor real continua indo para o motor (`Job`). Enquanto uma execução roda, a caixa
"Modo privacidade" fica desabilitada e a máscara do log usa a privacidade DA EXECUÇÃO (`Job.privacidade`). Os textos ficam em funções
puras (testadas em tests/test_ui_pura.py); a classe `App` só monta widgets e consome a fila de eventos.

Protocolo com o motor (merger.py), sempre pela thread principal:
- `ConfirmarEvt` → diálogo modal de confirmação da conta → `Merger.responder(True/False)` (SEMPRE, uma vez);
- PARAR: 1º clique `solicitar_parada()` (para entre uniões), 2º clique `solicitar_parada(forcar=True)`;
- fechar a janela com a thread viva: pede parada e só destrói a janela depois que a thread terminar.
"""
import queue
import sys
import threading
import time
import tkinter as tk
import traceback
from tkinter import font as tkfont
from tkinter import messagebox, scrolledtext

from . import APP_NOME, __version__, config, kommo, logs, paths
from .limite import (LIMITE_EXIGE_DIGITAR, PALAVRA_CONFIRMACAO, descrever_limite, exige_digitar, palavra_confere,
                     parse_limite)
from .mascara import OCULTO, mascarar_empresa, mascarar_host, mascarar_mensagem  # noqa: F401 (reexportados)
from .merger import MOTIVOS, ConfirmarEvt, FimEvt, Job, LogEvt, Merger, ProgEvt
from .temas import (AMARELO, BG, BRANCO, CLARO, FOCO, LOG_BG, LOG_FG, MUTED, OK, PAINEL, ROXO, ROXO_HOVER,
                    TRILHA, TXT, VERMELHO, calcular_geometria, escolher_fontes)

TIPOS = {"leads": "Leads", "contatos": "Contatos"}
NOMES_CANAL = {"chrome": "Google Chrome", "msedge": "Microsoft Edge", "chromium": "Chromium"}
DICA_VAZIA = "Informe a empresa e clique INICIAR (ou tecle Enter)."
TXT_INICIAR = "▶  INICIAR"
TXT_SIMULAR = "▶  SIMULAR"
TXT_PARAR = "■  PARAR"
TXT_FORCAR = "■  FORÇAR PARADA"
MSG_CANCELADO = "Cancelado — nada foi unido."
MSG_PARANDO = "Parando após a união em andamento…"
MSG_FORCADO = ("Parada forçada: a união em andamento pode ter ficado não confirmada — confira no Kommo.")
MSG_ESQUECER = "Isto apaga o login salvo do Kommo neste computador. Você precisará entrar de novo."
# Motivos em que a execução terminou "de verdade" e vale guardar o total da conta nas preferências.
# `busca_sem_resposta` fica de fora de propósito: não é conclusão confirmada.
MOTIVOS_REGISTRAR = ("limite", "sem_duplicatas", "parado")


# ====================================================================== textos (funções puras)
def fmt(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def empresa_exibida(empresa: str, privacidade: bool) -> str:
    """Subdomínio como deve aparecer na tela (mascarado com privacidade)."""
    return mascarar_empresa(empresa) if privacidade else empresa


def texto_inicio(empresa: str, tipo: str, limite: int, privacidade: bool, ensaio: bool = False) -> str:
    txt = (f"Iniciando: {empresa_exibida(empresa, privacidade)}.{kommo.DOMINIO} · "
           f"{TIPOS.get(tipo, tipo)} · limite {descrever_limite(limite)}")
    return txt + (" · ENSAIO (nada será unido)" if ensaio else "")


def dados_confirmacao(host: str, tipo: str, total: int, limite: int, ensaio: bool, privacidade: bool,
                      revelar: bool = False) -> dict:
    """Textos do diálogo de confirmação da conta (ConfirmarEvt).

    Com privacidade (e sem `revelar`) o host e o total da conta saem mascarados — a tela pode estar sendo
    gravada; o botão "Mostrar conta" do diálogo liga `revelar` para o usuário conferir de verdade.
    Devolve {titulo, cabecalho, linhas[(rótulo, valor)], aviso, aviso_sub, botao, exige_digitar, pode_revelar}.
    """
    mascarar = bool(privacidade and not revelar)
    host_txt = mascarar_host(host) if mascarar else (host or "?")
    if not total:
        total_txt = "não informado"
    else:
        total_txt = OCULTO if mascarar else fmt(total)
    qtd = "todas (pode levar horas)" if not limite else f"até {fmt(limite)}"
    exige = bool(not ensaio and exige_digitar(limite))
    if ensaio:
        aviso = "ENSAIO: nada será unido"
        aviso_sub = "O app só confere a conta, a lista e o modal de duplicatas e encerra sem clicar em Unir."
    else:
        aviso = "A união é IRREVERSÍVEL"
        aviso_sub = "Duplicatas unidas não podem ser separadas de novo. Confira a conta antes de continuar."
    return {
        "titulo": "Confirmar o ensaio" if ensaio else "Confirmar a união",
        "cabecalho": "Confira a conta antes do ensaio" if ensaio else "Confira a conta antes de unir",
        "linhas": [("Conta", host_txt), ("Tipo", TIPOS.get(tipo, tipo)),
                   ("Grupos de duplicatas na conta", total_txt), ("Quantidade pedida", qtd)],
        "aviso": aviso,
        "aviso_sub": aviso_sub,
        "botao": "Fazer ensaio" if ensaio else "Unir agora",
        "exige_digitar": exige,
        "pode_revelar": bool(privacidade),
    }


def texto_pedir_palavra(limite: int) -> str:
    """Instrução acima do campo onde se digita UNIR."""
    qual = "TODAS as duplicatas" if not limite else f"mais de {fmt(LIMITE_EXIGE_DIGITAR)} uniões"
    return f"Você pediu {qual}. Para habilitar o botão, digite {PALAVRA_CONFIRMACAO}:"


def texto_progresso(feitos: int, limite: int, total: int, privacidade: bool, incertas: int = 0) -> str:
    """Linha abaixo do contador. Com privacidade, o total da conta e o 'restam' (que o revelaria) somem."""
    txt = "duplicatas unificadas" + (f" de {fmt(limite)}" if limite else "")
    if incertas:
        txt += f"  ·  {fmt(incertas)} não confirmada" + ("s" if incertas != 1 else "")
    if total:
        if privacidade:
            txt += f"  ·  {fmt(feitos)} de {OCULTO} duplicatas da conta"
        else:
            txt += f"  ·  {fmt(feitos)} de {fmt(total)} duplicatas da conta"
            txt += f"  ·  restam {fmt(max(total - feitos, 0))}"
    return txt


def fracao_barra(cliques: int, feitos: int, limite: int) -> float:
    """Barra de progresso = cliques em Unir / limite (0 quando não há limite)."""
    if not limite:
        return 0.0
    usados = max(int(cliques or 0), int(feitos or 0))
    return max(0.0, min(usados / limite, 1.0))


def texto_resumo_conta(feitos: int, total: int, privacidade: bool):
    """Linha 'N de TOTAL duplicatas da conta' do resumo (None se o Kommo não informou o total)."""
    if not total:
        return None
    return f"{fmt(feitos)} de {OCULTO if privacidade else fmt(total)} duplicatas da conta"


def texto_detalhes(segundos: float, erros: int, interrompido: bool, avisos: int = 0) -> str:
    m, s = divmod(int(max(segundos, 0)), 60)
    h, m = divmod(m, 60)
    tempo = f"{h}h {m:02d}min {s:02d}s" if h else f"{m}min {s:02d}s"
    det = f"Tempo: {tempo}  ·  " + (f"{erros} erro(s)" if erros else "sem erros")
    if avisos:
        det += f"  ·  {avisos} aviso(s)"
    if erros or avisos:
        det += " — veja o log"
    if interrompido:
        det += "\n(interrompido pelo usuário)"
    return det


def texto_motivo(motivo: str) -> str:
    return "Motivo: " + MOTIVOS.get(motivo or "", motivo or "desconhecido")


def textos_busca_sem_resposta(segundos: float, cliques: int) -> list[tuple[str, str]]:
    """Linhas do resumo quando o motivo é `busca_sem_resposta` (A1): aviso, nunca verde/ok."""
    seg = int(round(max(float(segundos or 0), 0)))
    linhas = [(f"O Kommo não mostrou novos grupos de duplicatas em {seg} s. Pode não haver mais duplicatas ou a "
               "busca estar lenta — confira no Kommo.", "aviso")]
    if not cliques:
        linhas.append(("Não foi possível confirmar se a lista tem duplicatas: nada foi unido.", "muted"))
    return linhas


def deve_registrar(ev: FimEvt) -> bool:
    """Grava `ultimo_total` só quando há total e a execução terminou de forma normal."""
    return bool(ev.total) and ev.total > 0 and ev.motivo in MOTIVOS_REGISTRAR


def textos_resumo(ev: FimEvt, limite: int, privacidade: bool, ensaio: bool = False) -> dict:
    """Conteúdo do diálogo de resumo. Devolve {titulo, numero, rotulo, linhas[(texto, estilo)], detalhes,
    detalhes_estilo}; estilo ∈ {"txt", "aviso", "muted", "ok"}."""
    confirmadas = ev.confirmadas or ev.feitos
    cliques = ev.cliques or (confirmadas + ev.incertas)
    linhas: list[tuple[str, str]] = []
    detalhes = texto_detalhes(ev.segundos, ev.erros, False, ev.avisos)
    det_estilo = "aviso" if ev.erros else "muted"
    if ensaio:
        if ev.motivo == "ensaio":
            linhas.append(("Conta, lista e modal de duplicatas conferidos.", "ok"))
        else:
            linhas.append(("O ensaio não chegou ao fim.", "aviso"))
            linhas.append((texto_motivo(ev.motivo), "txt"))
            if ev.motivo == "busca_sem_resposta":
                linhas.append(textos_busca_sem_resposta(getattr(ev, "espera_busca", 0), 1)[0])
        if ev.total:
            linhas.append((f"Grupos de duplicatas na conta: {OCULTO if privacidade else fmt(ev.total)}", "txt"))
        else:
            linhas.append(("Grupos de duplicatas na conta: não informado pelo Kommo", "txt"))
        if cliques:      # o motor nunca clica em Unir no ensaio; se acontecer, o resumo não esconde
            linhas.append((f"Atenção: {fmt(cliques)} clique(s) em Unir — confira no Kommo.", "aviso"))
        else:
            linhas.append(("Nada foi unido (nenhum clique em Unir).", "muted"))
        return {"titulo": "Resumo do ensaio", "numero": "Ensaio", "rotulo": "nada foi unido",
                "linhas": linhas, "detalhes": detalhes, "detalhes_estilo": det_estilo}

    conta = texto_resumo_conta(confirmadas, ev.total, privacidade)
    if conta:
        linhas.append((conta, "txt"))
    if ev.incertas:
        n = ev.incertas
        linhas.append((f"{fmt(n)} não confirmada{'s' if n != 1 else ''} — confira no Kommo", "aviso"))
        linhas.append(("O Kommo não mostrou o fim dessa(s) união(ões): pode(m) ter sido feita(s) ou não.", "muted"))
    linhas.append((f"{fmt(cliques)} clique(s) em Unir  ·  limite {descrever_limite(limite)}", "muted"))
    linhas.append((texto_motivo(ev.motivo), "txt"))
    if ev.motivo == "busca_sem_resposta":
        linhas += textos_busca_sem_resposta(getattr(ev, "espera_busca", 0), cliques)
    return {"titulo": "Resumo", "numero": fmt(confirmadas),
            "rotulo": "duplicata unificada" if confirmadas == 1 else "duplicatas unificadas",
            "linhas": linhas, "detalhes": detalhes, "detalhes_estilo": det_estilo}


def nome_canal(canal: str) -> str:
    canal = (canal or "").strip().lower()
    return NOMES_CANAL.get(canal, canal)


# ====================================================================== widgets
class Escolha(tk.Frame):
    """Botões lado a lado; o selecionado fica roxo. Acessível por teclado: Tab chega em cada opção
    (anel de foco claro), Espaço seleciona e ←/→ andam entre as opções."""

    def __init__(self, master, var, opcoes, fonte=("Segoe UI", 10, "bold"), ao_escolher=None):
        super().__init__(master, bg=BG)
        self.var, self.itens, self.ao_escolher = var, [], ao_escolher
        for i, (txt, val) in enumerate(opcoes):
            b = tk.Label(self, text=txt, font=fonte, padx=16, pady=8, cursor="hand2", takefocus=1,
                         highlightthickness=2, highlightcolor=FOCO, highlightbackground=BG)
            b.pack(side="left", padx=(0, 6))
            b.bind("<Button-1>", lambda _e, v=val, w=b: (w.focus_set(), self.escolher(v)))
            b.bind("<space>", lambda _e, v=val: (self.escolher(v), "break")[1])
            b.bind("<Left>", lambda _e, k=i: self._mover(k - 1))
            b.bind("<Right>", lambda _e, k=i: self._mover(k + 1))
            self.itens.append((b, val))
        var.trace_add("write", lambda *_a: self.pintar())
        self.pintar()

    def escolher(self, val) -> None:
        self.var.set(val)
        if self.ao_escolher:
            self.ao_escolher(val)

    def _mover(self, k: int) -> str:
        b, val = self.itens[k % len(self.itens)]
        b.focus_set()
        self.escolher(val)
        return "break"

    def pintar(self):
        atual = self.var.get()
        for b, val in self.itens:
            ativo = val == atual
            b.configure(bg=ROXO if ativo else PAINEL, fg=BRANCO if ativo else TXT)


def com_anel(master, criar):
    """Envolve o widget numa moldura que acende (cor FOCO) quando ele tem o foco do teclado.

    Botões/checkbuttons nativos do Windows ignoram `highlightthickness`; a moldura funciona em qualquer SO."""
    moldura = tk.Frame(master, bg=BG, padx=2, pady=2)
    w = criar(moldura)
    w.pack(fill="both", expand=True)
    w.bind("<FocusIn>", lambda _e: moldura.configure(bg=FOCO), add="+")
    w.bind("<FocusOut>", lambda _e: moldura.configure(bg=BG), add="+")
    return moldura, w


def centralizar(janela, d) -> None:
    """Posiciona o diálogo `d` sobre a `janela` principal, sem sair da tela."""
    d.update_idletasks()
    x = janela.winfo_rootx() + (janela.winfo_width() - d.winfo_reqwidth()) // 2
    y = janela.winfo_rooty() + (janela.winfo_height() - d.winfo_reqheight()) // 3
    x = max(0, min(x, janela.winfo_screenwidth() - d.winfo_reqwidth()))
    y = max(0, min(y, janela.winfo_screenheight() - d.winfo_reqheight()))
    d.geometry(f"+{x}+{y}")


class DialogoConfirmacao(tk.Toplevel):
    """Confirmação ÚNICA da conta (resposta ao ConfirmarEvt). Modal, transient.

    - "Cancelar" é o padrão: tem o foco inicial; Esc, Enter e o X da janela também cancelam.
    - "Unir agora" ("Fazer ensaio" no ensaio) só por clique ou Espaço com o foco nele; para "todas" ou mais de
      LIMITE_EXIGE_DIGITAR uniões ele fica desabilitado até digitar UNIR.
    - `ao_responder(bool)` é chamado UMA única vez (qualquer caminho), e o diálogo se fecha.
    """

    def __init__(self, master, ev: ConfirmarEvt, privacidade: bool, fontes: dict, ao_responder):
        super().__init__(master)
        self.ev, self.privacidade, self.ao_responder = ev, bool(privacidade), ao_responder
        self.revelado = False
        self.respondido = False
        sans = fontes["sans"]
        d = dados_confirmacao(ev.host, ev.tipo, ev.total, ev.limite, ev.ensaio, self.privacidade)
        self.exige = d["exige_digitar"]
        self.title(d["titulo"])
        self.configure(bg=BG, padx=26, pady=18)
        self.transient(master)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", lambda: self.responder(False))

        tk.Label(self, text=d["cabecalho"], bg=BG, fg=TXT, font=(sans, 14, "bold")).pack(anchor="w")
        grade = tk.Frame(self, bg=PAINEL, padx=14, pady=10)
        grade.pack(fill="x", pady=(10, 4))
        self.valores = {}
        for i, (rot, val) in enumerate(d["linhas"]):
            tk.Label(grade, text=rot, bg=PAINEL, fg=MUTED, font=(sans, 9)).grid(row=i, column=0, sticky="w",
                                                                              padx=(0, 14), pady=2)
            lb = tk.Label(grade, text=val, bg=PAINEL, fg=CLARO if i == 0 else TXT, font=(sans, 11, "bold"))
            lb.grid(row=i, column=1, sticky="w", pady=2)
            self.valores[rot] = lb
        self.bt_revelar = None
        if d["pode_revelar"]:
            self.bt_revelar = tk.Button(self, text="Mostrar conta", command=self.alternar_revelar, bg=BG, fg=CLARO,
                                        activebackground=BG, activeforeground=BRANCO, bd=0, cursor="hand2",
                                        font=(sans, 9, "underline"))
            self.bt_revelar.pack(anchor="w")
            tk.Label(self, text="Modo privacidade: a conta aparece mascarada até você clicar em Mostrar conta.",
                     bg=BG, fg=MUTED, font=(sans, 8)).pack(anchor="w")

        cor = AMARELO if ev.ensaio else VERMELHO
        caixa = tk.Frame(self, bg=PAINEL, padx=14, pady=10, highlightthickness=2, highlightbackground=cor)
        caixa.pack(fill="x", pady=(12, 4))
        tk.Label(caixa, text="⚠  " + d["aviso"], bg=PAINEL, fg=cor, font=(sans, 13, "bold")).pack(anchor="w")
        tk.Label(caixa, text=d["aviso_sub"], bg=PAINEL, fg=TXT, font=(sans, 9), wraplength=400,
                 justify="left").pack(anchor="w", pady=(2, 0))

        self.palavra = tk.StringVar()
        self.ent_palavra = None
        if self.exige:
            tk.Label(self, text=texto_pedir_palavra(ev.limite), bg=BG, fg=TXT, font=(sans, 9), wraplength=420,
                     justify="left").pack(anchor="w", pady=(8, 3))
            self.ent_palavra = tk.Entry(self, textvariable=self.palavra, bg=PAINEL, fg=TXT, insertbackground=TXT,
                                        relief="flat", font=(sans, 12, "bold"), width=10, bd=5,
                                        highlightthickness=2, highlightcolor=FOCO, highlightbackground=PAINEL)
            self.ent_palavra.pack(anchor="w")
            # Enter no campo não confirma nem cancela: só o clique/Espaço no botão confirma.
            self.ent_palavra.bind("<Return>", lambda _e: "break")
            self.ent_palavra.bind("<KP_Enter>", lambda _e: "break")
            self.palavra.trace_add("write", lambda *_a: self._atualizar_botao())

        bts = tk.Frame(self, bg=BG)
        bts.pack(fill="x", pady=(16, 0))
        mold, self.bt_cancelar = com_anel(bts, lambda m: tk.Button(
            m, text="Cancelar", command=lambda: self.responder(False), bg=ROXO, fg=BRANCO, bd=0,
            activebackground=ROXO_HOVER, activeforeground=BRANCO, font=(sans, 11, "bold"), padx=22, pady=7,
            cursor="hand2"))
        mold.pack(side="left", fill="x", expand=True, padx=(0, 6))
        mold, self.bt_ok = com_anel(bts, lambda m: tk.Button(
            m, text=d["botao"], command=self._confirmar, bg=PAINEL, fg=cor, bd=0, activebackground=PAINEL,
            activeforeground=cor, disabledforeground=MUTED, font=(sans, 11, "bold"), padx=22, pady=7,
            cursor="hand2"))
        mold.pack(side="left", fill="x", expand=True)
        for b in (self.bt_cancelar, self.bt_ok):
            b.bind("<space>", lambda e: (e.widget.invoke(), "break")[1])
        self.bind("<Escape>", lambda _e: self.responder(False))
        self.bind("<Return>", lambda _e: self.responder(False))
        self.bind("<KP_Enter>", lambda _e: self.responder(False))
        self._atualizar_botao()

        centralizar(master, self)
        self.lift()
        self.bt_cancelar.focus_set()
        try:
            self.grab_set()
        except tk.TclError:                     # janela ainda não visível: segue sem modal
            pass

    def pode_confirmar(self) -> bool:
        return not self.exige or palavra_confere(self.palavra.get())

    def _atualizar_botao(self) -> None:
        self.bt_ok.configure(state="normal" if self.pode_confirmar() else "disabled")

    def alternar_revelar(self) -> None:
        """Mostra/oculta temporariamente a conta e o total (só existe com privacidade ligada)."""
        self.revelado = not self.revelado
        d = dados_confirmacao(self.ev.host, self.ev.tipo, self.ev.total, self.ev.limite, self.ev.ensaio,
                              self.privacidade, revelar=self.revelado)
        for rot, val in d["linhas"]:
            if rot in self.valores:
                self.valores[rot].configure(text=val)
        if self.bt_revelar is not None:
            self.bt_revelar.configure(text="Ocultar conta" if self.revelado else "Mostrar conta")

    def _confirmar(self) -> None:
        if self.pode_confirmar():
            self.responder(True)

    def responder(self, aceito: bool) -> None:
        if self.respondido:
            return
        self.respondido = True
        try:
            self.ao_responder(bool(aceito))
        finally:
            self.fechar()

    def fechar(self) -> None:
        try:
            self.grab_release()
        except tk.TclError:
            pass
        try:
            self.destroy()
        except tk.TclError:
            pass


class App(tk.Tk):
    # Fechar a janela com a thread viva: espera a parada normal até TETO_FECHAR s; depois força e espera mais
    # TETO_FORCAR s; se nem assim terminar, avisa e continua esperando (nunca destrói com a thread viva).
    TETO_FECHAR = 150.0
    TETO_FORCAR = 20.0
    INTERVALO_FECHAR_MS = 200

    def __init__(self):
        super().__init__()
        self.title(f"{APP_NOME}  v{__version__}")
        try:
            self.fontes = escolher_fontes(tkfont.families(self), sys.platform)
        except tk.TclError:
            self.fontes = escolher_fontes((), sys.platform)
        sans, mono = self.fontes["sans"], self.fontes["mono"]
        w, h, x, y = calcular_geometria(self.winfo_screenwidth(), self.winfo_screenheight())
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(min(520, w), min(560, h))
        self.configure(bg=BG)
        self.fila: queue.Queue = queue.Queue()
        self.parar = threading.Event()
        self.th = None
        self._rodando = False
        self._log_vazio = True
        self._empresa_job = ""             # subdomínio da execução atual (para mascarar o log do motor)
        self._limite_job = 0
        self._ensaio_job = False
        self._priv_job = True              # privacidade DA EXECUÇÃO em curso (a caixa fica travada enquanto roda)
        self._nivel_parada = 0             # 0 = rodando; 1 = parada pedida; 2 = parada forçada
        self._dlg_conf: DialogoConfirmacao | None = None
        self._dlg_resumo = None
        self._fechando = False
        self._t_fechar = 0.0
        self._t_forcar: float | None = None
        self._avisou_travado = False
        self._erro_ui_aberto = False
        cfg = config.carregar()

        f = tk.Frame(self, bg=BG, padx=22, pady=18)
        f.pack(fill="both", expand=True)

        def rotulo(t, master=f):
            tk.Label(master, text=t.upper(), bg=BG, fg=MUTED, font=(sans, 8, "bold")).pack(anchor="w", pady=(8, 3))

        def campo(master, var, fonte, **kw):
            return tk.Entry(master, textvariable=var, bg=PAINEL, fg=TXT, insertbackground=TXT, relief="flat",
                            font=fonte, highlightthickness=2, highlightcolor=FOCO, highlightbackground=PAINEL, **kw)

        # --- Empresa: `self.empresa` guarda o valor REAL; o Entry mostra `self._empresa_vis`, que fica
        # mascarado com privacidade ligada enquanto o campo não está em edição (ver _sync_empresa).
        rotulo("Empresa (subdomínio do Kommo)")
        linha = tk.Frame(f, bg=PAINEL)
        linha.pack(fill="x")
        self.empresa = tk.StringVar(value=cfg["empresa"])
        self._empresa_vis = tk.StringVar()
        self._editando_empresa = False
        self.ent_empresa = campo(linha, self._empresa_vis, (sans, 13), bd=6)
        self.ent_empresa.pack(side="left", fill="x", expand=True)
        self.ent_empresa.bind("<FocusIn>", self._empresa_foco_in)
        self.ent_empresa.bind("<FocusOut>", self._empresa_foco_out)
        tk.Label(linha, text=f".{kommo.DOMINIO}", bg=PAINEL, fg=MUTED, font=(sans, 11)).pack(side="right", padx=10)

        rotulo("O que unir")
        self.tipo = tk.StringVar(value=cfg["tipo"])
        Escolha(f, self.tipo, [("Leads", "leads"), ("Apenas contatos", "contatos")],
                fonte=(sans, 10, "bold")).pack(anchor="w")

        rotulo("Quantas uniões")
        self.limite = tk.IntVar(value=cfg["limite"])
        Escolha(f, self.limite, [("100", 100), ("200", 200), ("500", 500), ("Todas", 0)], fonte=(sans, 10, "bold"),
                ao_escolher=lambda _v: self.custom.set("")).pack(anchor="w")
        ln = tk.Frame(f, bg=BG)
        ln.pack(anchor="w", fill="x", pady=(8, 0))
        tk.Label(ln, text="ou outro valor (0 = todas):", bg=BG, fg=MUTED, font=(sans, 9)).pack(side="left")
        custom_salvo = cfg.get("limite_custom")
        self.custom = tk.StringVar(value="" if custom_salvo is None else str(custom_salvo))
        self.ent_custom = campo(ln, self.custom, (sans, 10), width=9, bd=4)
        self.ent_custom.pack(side="left", padx=8)
        self.lbl_custom = tk.Label(ln, text="", bg=BG, fg=MUTED, font=(sans, 9))
        self.lbl_custom.pack(side="left")
        self.custom.trace_add("write", lambda *_a: self._validar_custom())

        self.privacidade = tk.BooleanVar(value=cfg["privacidade"])
        mold, self.chk_priv = com_anel(f, lambda m: tk.Checkbutton(
            m, text="Modo privacidade (borra dados no navegador e mascara empresa/totais aqui)",
            variable=self.privacidade, bg=BG, fg=TXT, selectcolor=PAINEL, activebackground=BG,
            activeforeground=TXT, disabledforeground=MUTED, bd=0, font=(sans, 10), anchor="w", wraplength=480,
            justify="left"))
        mold.pack(anchor="w", fill="x", pady=(10, 0))
        self.privacidade.trace_add("write", lambda *_a: self._privacidade_mudou())

        self.ensaio = tk.BooleanVar(value=False)     # NÃO persistido: toda abertura começa no modo real
        mold, self.chk_ensaio = com_anel(f, lambda m: tk.Checkbutton(
            m, text="Só simular (não une nada)",
            variable=self.ensaio, bg=BG, fg=TXT, selectcolor=PAINEL, activebackground=BG, activeforeground=TXT,
            disabledforeground=MUTED, bd=0, font=(sans, 10), anchor="w", wraplength=480, justify="left"))
        mold.pack(anchor="w", fill="x", pady=(0, 6))
        self.ensaio.trace_add("write", lambda *_a: self._rotulos_botoes())

        bt = tk.Frame(f, bg=BG)
        bt.pack(fill="x", pady=(0, 6))
        mold, self.bt_ini = com_anel(bt, lambda m: tk.Button(
            m, text=TXT_INICIAR, command=self.iniciar, bg=ROXO, fg=BRANCO, bd=0, activebackground=ROXO_HOVER,
            activeforeground=BRANCO, disabledforeground=MUTED, font=(sans, 11, "bold"), pady=10, cursor="hand2"))
        mold.pack(side="left", fill="x", expand=True, padx=(0, 4))
        mold, self.bt_par = com_anel(bt, lambda m: tk.Button(
            m, text=TXT_PARAR, command=self.parar_tudo, bg=PAINEL, fg=VERMELHO, bd=0, activebackground=PAINEL,
            activeforeground=VERMELHO, disabledforeground=MUTED, font=(sans, 11, "bold"), pady=10,
            state="disabled", cursor="hand2"))
        mold.pack(side="left", fill="x", expand=True)
        for b in (self.bt_ini, self.bt_par):
            b.bind("<space>", lambda e: (e.widget.invoke(), "break")[1])

        cont = tk.Frame(f, bg=PAINEL, padx=16, pady=8)
        cont.pack(fill="x", pady=(8, 0))
        self.contador = tk.Label(cont, text="0", bg=PAINEL, fg=CLARO, font=(sans, 34, "bold"))
        self.contador.pack(anchor="w")
        self.lbl = tk.Label(cont, text="duplicatas unificadas", bg=PAINEL, fg=MUTED, font=(sans, 10),
                            anchor="w", justify="left", wraplength=470)
        self.lbl.pack(anchor="w", fill="x")
        self.barra = tk.Canvas(cont, height=6, bg=TRILHA, highlightthickness=0, takefocus=0)
        self.barra.pack(fill="x", pady=(8, 0))
        self.preench = self.barra.create_rectangle(0, 0, 0, 6, fill=ROXO, width=0)
        self._ultimo_prog = None
        self.barra.bind("<Configure>", lambda _e: self._ultimo_prog and self.mostrar_progresso(self._ultimo_prog))

        # cabeçalho do log: "LOG" à esquerda; à direita, discretos, "Esquecer login salvo", o navegador usado e a
        # versão — tudo na mesma linha para não roubar altura do log.
        cab = tk.Frame(f, bg=BG)
        cab.pack(fill="x", pady=(8, 3))
        tk.Label(cab, text="LOG", bg=BG, fg=MUTED, font=(sans, 8, "bold")).pack(side="left")
        tk.Label(cab, text=f"v{__version__}", bg=BG, fg=MUTED, font=(sans, 8)).pack(side="right")
        self.lbl_canal = tk.Label(cab, text="", bg=BG, fg=MUTED, font=(sans, 8))
        self.lbl_canal.pack(side="right", padx=(0, 10))
        self.bt_esquecer = tk.Button(cab, text="Esquecer login salvo", command=self.esquecer_login, bg=BG, fg=MUTED,
                                     activebackground=BG, activeforeground=TXT, disabledforeground=TRILHA, bd=0,
                                     cursor="hand2", font=(sans, 8, "underline"), padx=0, pady=0)
        self.bt_esquecer.pack(side="right", padx=(0, 10))
        self._mostrar_canal(cfg.get("canal_navegador"))

        self.caixa = scrolledtext.ScrolledText(f, height=7, bg=LOG_BG, fg=LOG_FG, font=(mono, 9), takefocus=0,
                                               insertbackground=BRANCO, relief="flat", bd=8, wrap="word")
        self.caixa.pack(fill="both", expand=True)
        for nome, cor in (("erro", VERMELHO), ("ok", OK), ("aviso", AMARELO), ("info", LOG_FG), ("dica", MUTED)):
            self.caixa.tag_config(nome, foreground=cor)
        self.caixa.insert("end", DICA_VAZIA, "dica")
        self.caixa.configure(state="disabled")

        self._sync_empresa()
        self._validar_custom()
        self.bind("<Return>", self._tecla_enter)
        self.bind("<KP_Enter>", self._tecla_enter)
        self.protocol("WM_DELETE_WINDOW", self.fechar)
        # foco inicial: no campo vazio que falta preencher; senão no INICIAR (mantém a empresa mascarada)
        self.after_idle(lambda: (self.ent_empresa if not self.empresa.get() else self.bt_ini).focus_set())
        self.after(150, self.bombear)

    # ------------------------------------------------------------------ erros inesperados do Tk
    def report_callback_exception(self, exc, val, tb) -> None:
        """Exceção não tratada num callback do Tk: grava no log e avisa, sem derrubar a janela."""
        try:
            empresa = self._empresa_job or kommo.normalizar_empresa(self.empresa.get())
            priv = self._privacidade_log()
        except Exception:  # noqa: BLE001
            empresa, priv = "", True
        try:
            detalhe = "".join(traceback.format_exception(exc, val, tb))
            logs.gravar("erro", mascarar_mensagem("Erro inesperado na interface: " + detalhe, empresa, priv))
        except Exception:  # noqa: BLE001
            pass
        nome = getattr(exc, "__name__", str(exc))
        self._aviso_seguro(f"Erro inesperado na interface ({nome}). A janela continua funcionando; "
                           "os detalhes foram gravados no arquivo de log.", nivel="erro", gravar=False)
        if self._erro_ui_aberto:                 # não empilha caixas de erro
            return
        self._erro_ui_aberto = True
        try:
            messagebox.showerror(APP_NOME, "Algo deu errado na janela do app.\n\nA janela continua funcionando e "
                                           "nenhuma união foi iniciada por causa deste erro. Os detalhes foram "
                                           "gravados no arquivo de log.", parent=self)
        except Exception:  # noqa: BLE001
            pass
        finally:
            self._erro_ui_aberto = False

    # ------------------------------------------------------------------ empresa / privacidade
    def _sync_empresa(self) -> None:
        """Atualiza o que o campo Empresa exibe (mascarado com privacidade, se não estiver em edição)."""
        if self._editando_empresa:
            return
        real = self.empresa.get()
        if self.privacidade.get() and real:
            self._empresa_vis.set(mascarar_empresa(kommo.normalizar_empresa(real) or real))
        else:
            self._empresa_vis.set(real)

    def _empresa_foco_in(self, _e=None) -> None:
        self._editando_empresa = True
        self._empresa_vis.set(self.empresa.get())
        self.ent_empresa.icursor("end")

    def _empresa_foco_out(self, _e=None) -> None:
        self.empresa.set(self._empresa_vis.get())
        self._editando_empresa = False
        self._sync_empresa()

    def _empresa_atual(self) -> str:
        if self._editando_empresa:
            self.empresa.set(self._empresa_vis.get())
        return self.empresa.get()

    def _privacidade_mudou(self) -> None:
        self._sync_empresa()
        if self._ultimo_prog:
            self.mostrar_progresso(self._ultimo_prog)

    def _validar_custom(self) -> str | None:
        """Retorno imediato ao lado do campo 'outro valor'. Devolve a mensagem de erro (ou None)."""
        try:
            n = parse_limite(self.custom.get(), self.limite.get())
        except ValueError as e:
            self.lbl_custom.configure(text="valor inválido", fg=VERMELHO)
            return str(e)
        if self.custom.get().strip():
            self.lbl_custom.configure(text=f"→ vale {descrever_limite(n)}", fg=MUTED)
        else:
            self.lbl_custom.configure(text="")
        return None

    def _mostrar_canal(self, canal) -> None:
        nome = nome_canal(canal)
        self.lbl_canal.configure(text=f"Navegador: {nome}" if nome else "")

    def _rotulos_botoes(self) -> None:
        """Texto do INICIAR (SIMULAR no ensaio) e do PARAR conforme o estado."""
        self.bt_ini.configure(text=TXT_SIMULAR if self.ensaio.get() else TXT_INICIAR)
        if not self._rodando:
            self.bt_par.configure(text=TXT_PARAR)

    # ------------------------------------------------------------------ ações
    def _privacidade_log(self) -> bool:
        """Privacidade que vale para o log: a do `Job` em curso enquanto roda (A9); senão, a da caixa."""
        return bool(self._priv_job) if self._rodando else bool(self.privacidade.get())

    def escrever(self, nivel: str, msg: str, gravar: bool = True) -> None:
        """Mostra e grava no arquivo a MESMA linha — já mascarada quando a privacidade está ligada (a da execução em
        curso, não o valor atual da caixa)."""
        empresa = self._empresa_job or kommo.normalizar_empresa(self.empresa.get())
        msg = mascarar_mensagem(msg, empresa, self._privacidade_log())
        linha = logs.gravar(nivel, msg) if gravar else logs.formatar(nivel, msg)
        self.caixa.configure(state="normal")
        if self._log_vazio:
            self.caixa.delete("1.0", "end")
            self._log_vazio = False
        self.caixa.insert("end", linha + "\n", nivel)
        self.caixa.see("end")
        self.caixa.configure(state="disabled")

    def _aviso_seguro(self, msg: str, nivel: str = "aviso", gravar: bool = True) -> None:
        """Escreve um aviso sem nunca propagar exceção (usado nos caminhos de erro)."""
        try:
            self.escrever(nivel, msg, gravar=gravar)
        except Exception:  # noqa: BLE001 - último recurso: a UI não pode travar por causa do log
            pass

    def _tecla_enter(self, e=None):
        # Enter num botão aciona o próprio botão; em qualquer outro lugar, inicia (iniciar() valida tudo).
        if isinstance(getattr(e, "widget", None), tk.Button):
            e.widget.invoke()
        elif not self._rodando:
            self.iniciar()
        return "break"

    def _thread_viva(self) -> bool:
        return bool(self.th is not None and self.th.is_alive())

    def iniciar(self) -> None:
        if self._rodando or self._fechando or self._thread_viva():   # duplo clique / Enter repetido: ignora
            return
        bruto = self._empresa_atual()
        empresa = kommo.normalizar_empresa(bruto)
        if not empresa:
            if bruto.strip():
                self.escrever("erro", "Empresa inválida: use só o subdomínio, com letras, números e hífen "
                                      "(ex.: minhaempresa ou minhaempresa.kommo.com).")
            else:
                self.escrever("erro", "Informe o subdomínio da empresa (ex.: minhaempresa).")
            self.ent_empresa.focus_set()
            return
        try:
            limite = parse_limite(self.custom.get(), self.limite.get())
        except ValueError as e:
            self.escrever("erro", f"{e} Nada foi iniciado.")
            self.ent_custom.focus_set()
            self.ent_custom.select_range(0, "end")
            return
        tipo, priv, ensaio = self.tipo.get(), self.privacidade.get(), bool(self.ensaio.get())
        custom = limite if self.custom.get().strip() else None
        try:
            config.salvar(empresa=empresa, tipo=tipo, limite=self.limite.get(), privacidade=priv,
                          limite_custom=custom)
        except Exception as e:  # noqa: BLE001 - preferências não podem impedir a execução
            self._aviso_seguro(f"Não foi possível salvar as preferências ({type(e).__name__}: {e}). Seguindo assim mesmo.")
        # Sem pergunta aqui: a confirmação ÚNICA (com a conta realmente logada) vem do motor (ConfirmarEvt).
        self._rodando = True
        self._empresa_job = empresa
        self._limite_job = limite
        self._ensaio_job = ensaio
        self._priv_job = bool(priv)
        self._nivel_parada = 0
        self.parar = threading.Event()          # um Event por execução (nada herdado da anterior)
        self.contador.configure(text="0")
        self.lbl.configure(text="duplicatas unificadas")
        self._ultimo_prog = None
        self.barra.coords(self.preench, 0, 0, 0, 6)
        self.bt_ini.configure(state="disabled")
        self.bt_par.configure(state="normal", text=TXT_PARAR)
        self.chk_ensaio.configure(state="disabled")
        self.chk_priv.configure(state="disabled")      # A9: a privacidade da execução não muda no meio
        self.bt_esquecer.configure(state="disabled")
        self.escrever("info", texto_inicio(empresa, tipo, limite, priv, ensaio))
        try:
            self.th = Merger(Job(empresa, tipo, limite, priv, ensaio=ensaio), self.fila, self.parar)
            self.th.start()
        except Exception as e:  # noqa: BLE001
            self.escrever("erro", f"Não foi possível iniciar o processo: {type(e).__name__}: {e}")
            self._finalizar()

    def parar_tudo(self) -> None:
        """1º clique: para depois da união em andamento. 2º clique: parada forçada (aborta na hora)."""
        if not self._rodando or self.th is None:
            return
        if self._nivel_parada == 0:
            self._nivel_parada = 1
            self.th.solicitar_parada()
            self.bt_par.configure(text=TXT_FORCAR)          # continua habilitado para o 2º nível
            self.escrever("aviso", MSG_PARANDO)
        elif self._nivel_parada == 1:
            self._nivel_parada = 2
            self.th.solicitar_parada(forcar=True)
            self.bt_par.configure(state="disabled")
            self.escrever("aviso", MSG_FORCADO)

    def _finalizar(self) -> None:
        """Volta ao estado ocioso: INICIAR habilitado, PARAR desabilitado, rótulos restaurados."""
        self._rodando = False
        self._nivel_parada = 0
        self._fechar_confirmacao(None)
        if self._fechando:
            return
        self.bt_ini.configure(state="normal")
        self.bt_par.configure(state="disabled", text=TXT_PARAR)
        self.chk_ensaio.configure(state="normal")
        self.chk_priv.configure(state="normal")
        self.bt_esquecer.configure(state="normal")
        self._rotulos_botoes()

    # ------------------------------------------------------------------ confirmação da conta
    def _abrir_confirmacao(self, ev: ConfirmarEvt) -> None:
        th = self.th
        if self._fechando or th is None or not th.is_alive():
            # janela fechando (ou processo já encerrado): a resposta é NÃO, sem perguntar
            if th is not None:
                th.responder(False)
            return
        self._fechar_confirmacao(False)                 # nunca dois diálogos abertos
        self._dlg_conf = DialogoConfirmacao(self, ev, self.privacidade.get(), self.fontes,
                                            lambda ok, t=th: self._responder_confirmacao(t, ok))

    def _responder_confirmacao(self, th, aceito: bool) -> None:
        self._dlg_conf = None
        try:
            th.responder(bool(aceito))
        finally:
            if not aceito:
                self.escrever("info", MSG_CANCELADO)
            elif th is not None and th.is_alive():      # A17: só anuncia o início se o processo ainda roda
                self.escrever("info", "Conta confirmada por você — " +
                              ("fazendo o ensaio (nada será unido)." if self._ensaio_job else "iniciando as uniões."))
            else:
                self.escrever("info", "Conta confirmada, mas o processo já tinha terminado — nada foi unido.")

    def _fechar_confirmacao(self, resposta) -> None:
        """Fecha o diálogo aberto. `resposta` None = fecha sem responder (processo já terminou)."""
        dlg, self._dlg_conf = self._dlg_conf, None
        if dlg is None:
            return
        if resposta is None:
            dlg.respondido = True
            dlg.fechar()
        else:
            dlg.responder(bool(resposta))

    # ------------------------------------------------------------------ eventos do motor
    def _tratar(self, ev) -> None:
        if isinstance(ev, LogEvt):
            self.escrever(ev.nivel, ev.msg)
        elif isinstance(ev, ProgEvt):
            self.mostrar_progresso(ev)
        elif isinstance(ev, ConfirmarEvt):
            self._abrir_confirmacao(ev)
        elif isinstance(ev, FimEvt):
            self._finalizar()                   # primeiro: nada abaixo pode deixar o INICIAR travado
            if deve_registrar(ev):
                try:
                    config.registrar_execucao(ev.total)
                except Exception as e:  # noqa: BLE001
                    self._aviso_seguro(f"Não foi possível registrar a execução nas preferências "
                                       f"({type(e).__name__}: {e}).")
            try:
                self._mostrar_canal(config.carregar().get("canal_navegador"))
            except Exception:  # noqa: BLE001 - informação acessória
                pass
            if self._fechando:                  # janela fechando: sem diálogo de resumo
                return
            try:
                self.resumo(ev)
            except Exception as e:  # noqa: BLE001
                self._aviso_seguro(f"Não foi possível mostrar o resumo ({type(e).__name__}: {e}). "
                                   f"Unificadas: {ev.confirmadas or ev.feitos}.")

    def bombear(self) -> None:
        """Consome os eventos do motor (a UI só é tocada pela thread principal). Sempre se reagenda."""
        try:
            for _ in range(500):                # limite por ciclo: a janela continua respondendo
                try:
                    ev = self.fila.get_nowait()
                except queue.Empty:
                    break
                try:
                    self._tratar(ev)
                except Exception as e:  # noqa: BLE001
                    self._aviso_seguro(f"Falha ao exibir um evento ({type(e).__name__}: {e}).")
            vivo = self._thread_viva()
            # o processo terminou com o diálogo de confirmação ainda aberto: fecha sozinho
            if self._dlg_conf is not None and not vivo:
                self._fechar_confirmacao(None)
                self._aviso_seguro("O processo terminou antes da confirmação — nada foi unido.")
            # rede de segurança: a thread morreu sem mandar FimEvt
            if self._rodando and not vivo and self.fila.empty():
                self._finalizar()
                self._aviso_seguro("O processo terminou sem enviar o resumo — confira o log.")
        finally:
            try:
                self.after(150, self.bombear)
            except tk.TclError:                 # janela já destruída
                pass

    def mostrar_progresso(self, ev: ProgEvt) -> None:
        self._ultimo_prog = ev
        self.contador.configure(text=fmt(ev.feitos))
        self.lbl.configure(text=texto_progresso(ev.feitos, ev.limite, ev.total, self.privacidade.get(),
                                                getattr(ev, "incertas", 0)))
        w = self.barra.winfo_width()
        frac = fracao_barra(getattr(ev, "cliques", 0), ev.feitos, ev.limite)
        self.barra.coords(self.preench, 0, 0, w * frac, 6)

    def resumo(self, ev: FimEvt) -> None:
        sans = self.fontes["sans"]
        t = textos_resumo(ev, self._limite_job, self.privacidade.get(), self._ensaio_job)
        cores = {"txt": TXT, "aviso": AMARELO, "muted": MUTED, "ok": OK}
        d = tk.Toplevel(self)
        d.title(t["titulo"])
        d.configure(bg=BG, padx=28, pady=18)
        d.transient(self)
        d.resizable(False, False)
        tk.Label(d, text=t["numero"], bg=BG, fg=CLARO, font=(sans, 54 if t["numero"][:1].isdigit() else 34, "bold")
                 ).pack(pady=(4, 0))
        tk.Label(d, text=t["rotulo"], bg=BG, fg=TXT, font=(sans, 14)).pack()
        for i, (texto, estilo) in enumerate(t["linhas"]):
            tk.Label(d, text=texto, bg=BG, fg=cores.get(estilo, TXT),
                     font=(sans, 11, "bold") if estilo == "aviso" else (sans, 10 if estilo == "muted" else 11),
                     wraplength=420, justify="center").pack(pady=(8 if i == 0 else 2, 0))
        tk.Label(d, text=t["detalhes"], bg=BG, fg=cores.get(t["detalhes_estilo"], MUTED),
                 font=(sans, 10)).pack(pady=12)
        mold, ok = com_anel(d, lambda m: tk.Button(m, text="OK", command=d.destroy, bg=ROXO, fg=BRANCO, bd=0,
                                                   activebackground=ROXO_HOVER, activeforeground=BRANCO,
                                                   font=(sans, 11, "bold"), padx=36, pady=6, cursor="hand2"))
        mold.pack()
        d.bind("<Escape>", lambda _e: d.destroy())
        d.bind("<Return>", lambda _e: d.destroy())
        d.bind("<KP_Enter>", lambda _e: d.destroy())
        centralizar(self, d)
        ok.focus_set()
        try:
            d.grab_set()
        except tk.TclError:                     # janela ainda não visível: segue sem modal
            pass
        self._dlg_resumo = d

    # ------------------------------------------------------------------ esquecer login
    def esquecer_login(self) -> None:
        if self._rodando or self._thread_viva() or self._fechando:
            return
        if not messagebox.askyesno("Esquecer login", MSG_ESQUECER + "\n\nContinuar?", icon="warning",
                                   default="no", parent=self):
            return
        try:
            apagou = paths.esquecer_login()
        except (paths.EsquecerLoginErro, paths.DataDirNotWritable, OSError) as e:
            self._aviso_seguro(f"Não foi possível esquecer o login: {e}", nivel="erro")
            try:
                messagebox.showerror("Esquecer login", str(e), parent=self)
            except Exception:  # noqa: BLE001
                pass
            return
        if apagou:
            self.escrever("ok", "Login salvo do Kommo apagado deste computador. Na próxima execução, entre de novo.")
        else:
            self.escrever("info", "Não havia login salvo do Kommo neste computador.")

    # ------------------------------------------------------------------ fechar a janela
    def _agora(self) -> float:
        return time.monotonic()

    def fechar(self) -> None:
        """Fecha com segurança: com a thread viva, pergunta, pede a parada e só destrói depois que ela terminar."""
        if self._fechando:
            return
        if not self._thread_viva():
            self._fechar_confirmacao(False)
            self.destroy()
            return
        if not messagebox.askyesno("Fechar", "Há uma união em andamento. Parar e fechar?\n\n"
                                             "O app termina a união em andamento antes de fechar.",
                                   icon="warning", default="no", parent=self):
            return
        if not self._thread_viva():             # terminou enquanto a pergunta estava aberta
            self._fechar_confirmacao(False)
            self.destroy()
            return
        self._fechando = True
        self._fechar_confirmacao(False)         # confirmação pendente = NÃO
        self.th.solicitar_parada()
        self._nivel_parada = max(self._nivel_parada, 1)
        self.title(f"Encerrando…  —  {APP_NOME}")
        for b in (self.bt_ini, self.bt_par, self.bt_esquecer, self.chk_ensaio, self.chk_priv):
            try:
                b.configure(state="disabled")
            except tk.TclError:
                pass
        self.bt_par.configure(text="Encerrando…")
        self._aviso_seguro("Encerrando… a janela fecha sozinha assim que a união em andamento terminar.")
        self._t_fechar = self._agora()
        self._t_forcar = None
        self._avisou_travado = False
        self.after(self.INTERVALO_FECHAR_MS, self._aguardar_fechar)

    def _aguardar_fechar(self) -> None:
        if not self._thread_viva():
            self.destroy()
            return
        agora = self._agora()
        if self._t_forcar is None:
            if agora - self._t_fechar >= self.TETO_FECHAR:
                self._t_forcar = agora
                self._nivel_parada = 2
                self.th.solicitar_parada(forcar=True)
                self._aviso_seguro("A união em andamento não terminou a tempo; " + MSG_FORCADO)
        elif agora - self._t_forcar >= self.TETO_FORCAR and not self._avisou_travado:
            self._avisou_travado = True
            self._aviso_seguro("O processo ainda não terminou. Feche a janela do navegador aberta pelo app; "
                               "esta janela fecha sozinha em seguida.")
        try:
            self.after(self.INTERVALO_FECHAR_MS, self._aguardar_fechar)
        except tk.TclError:
            pass


def _erro_fatal(titulo: str, msg: str) -> None:
    """Mostra um erro sem a janela principal (o .exe não tem console) e volta."""
    raiz = None
    try:
        raiz = tk.Tk()
        raiz.withdraw()
        messagebox.showerror(titulo, msg, parent=raiz)
    except Exception:  # noqa: BLE001 - sem display: último recurso é o stderr
        try:
            print(f"{titulo}: {msg}", file=sys.stderr)
        except Exception:  # noqa: BLE001
            pass
    finally:
        if raiz is not None:
            try:
                raiz.destroy()
            except Exception:  # noqa: BLE001
                pass


def main() -> int:
    """Abre a janela. Devolve 0 (ok) ou 1 (não foi possível abrir: pasta de dados sem escrita)."""
    try:
        paths.ensure_writable()
        app = App()
    except paths.DataDirNotWritable as e:
        _erro_fatal(f"{APP_NOME} — pasta de dados", str(e))
        return 1
    app.mainloop()
    return 0
