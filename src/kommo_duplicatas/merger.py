"""Motor: uma thread que dirige o Kommo e une as duplicatas uma a uma.

A interface (ui.py) e o modo texto (cli.py) conversam com ele só por eventos numa fila:

- `LogEvt(nivel, msg)`                  linha de log ("info" | "ok" | "aviso" | "erro");
- `ProgEvt(feitos, limite, total, ...)` progresso (`feitos` = uniões CONFIRMADAS; `incertas`/`cliques` à parte);
- `ConfirmarEvt(host, tipo, total, limite, ensaio)` pede a confirmação da conta antes do 1º clique em "Unir";
  o motor fica BLOQUEADO até `Merger.responder(aceito)` (ou parada, ou `TEMPO_CONFIRMACAO`);
- `FimEvt(feitos, segundos, erros, interrompido, total, ...)` resumo final — emitido SEMPRE, uma única vez.

Estrutura (testável sem navegador):

- `Merger.run()` só cuida da sessão (Playwright: abrir contexto, init script de privacidade,
  `KommoPage(page, ctx=ctx)`, navegar) e chama `self._executar(porta)` dentro de try/except/finally (o `finally` emite o `FimEvt`; o
  contexto do navegador é fechado no `finally` da sessão).
- `_executar(porta)` contém TODO o fluxo: esperar login, validar a página, abrir o modal, confirmar a conta,
  laço de uniões. Recebe a porta (`kommo.PortaKommo`) e usa o relógio injetável (`Relogio`); os testes usam
  `tests/fakes.py` (FakeKommo/KommoSimulado + RelogioFalso), sem navegador e sem sleep real.

Regras de segurança (a união é IRREVERSÍVEL):

- O LIMITE conta CLIQUES em "Unir" disparados (confirmados + não confirmados): nunca mais do que `Job.limite`.
- Uma união sem confirmação (INCERTO) não é sucesso nem "falha que reclica": o motor espera a tela estabilizar e
  reconfere `estado()` antes de qualquer novo clique.
- PARAR (`solicitar_parada()`) só é atendido ENTRE uniões: a espera de uma união em andamento não checa a
  parada (só a forçada); a parada também é conferida logo antes de cada clique em "Unir". O segundo pedido
  (`solicitar_parada(forcar=True)`, ou dois pedidos) é atendido no PRÓXIMO ponto de checagem (laços de espera,
  entre tentativas de abrir a página) — não interrompe um `goto`/abertura do navegador já em curso.
- Antes de cada clique: hostname exato da empresa, caminho coerente com o tipo (/leads… ou
  /contacts/list/contacts…) e modal de duplicatas (título com "duplicat"). Antes do 1º clique: confirmação da conta
  (`Job.confirmar_conta`).
- "Sem duplicatas" só com EVIDÊNCIA POSITIVA (`Estado.vazio`: texto de "nenhuma duplicata" num modal visível,
  heurístico, a validar no Kommo real), sem erro pendente e com a sessão ainda logada. Busca que estoura o tempo sem
  modal e sem essa evidência NUNCA é sucesso: o motor refaz a busca (TEMPOS_REBUSCA) e, persistindo, termina com
  `busca_sem_resposta` (aviso).

Valores de `FimEvt.motivo` (ver `MOTIVOS`):

    limite               atingiu a quantidade pedida (cliques em Unir == limite)
    sem_duplicatas       o Kommo mostrou "nenhuma duplicata" (evidência positiva), sessão ok e sem erro pendente
    busca_sem_resposta   a busca não mostrou grupo nem "nenhuma duplicata" mesmo refeita (TEMPO_BUSCA + TEMPOS_REBUSCA):
                         pode não haver mais duplicatas ou a busca estar lenta — NÃO é sucesso (aviso; CLI sai com 3)
    parado               PARAR atendido entre uniões (ou antes do login/da confirmação)
    forcado              parada forçada: abortou na hora, a união em andamento ficou como "não confirmada"
    ensaio               modo ensaio: modal aberto e validado, nada unido
    recusado             o usuário recusou a confirmação da conta (nada unido)
    sem_resposta         ninguém respondeu à confirmação em TEMPO_CONFIRMACAO (nada unido)
    sessao_expirada      a sessão caiu / a página foi redirecionada para fora da lista
    validacao            conta/página/modal não conferem (abortou sem clicar)
    login_timeout        login não confirmado em TEMPO_LOGIN
    navegador_fechado    o navegador foi fechado durante a execução (nenhuma aba aberta no contexto; se só a aba
                         usada fechou e há outra aberta, o motor a adota e segue — T10)
    navegador_indisponivel  não foi possível abrir um navegador (ou o perfil está em uso)
    falhas               FALHAS_MAX uniões seguidas sem resultado (tempo esgotado / erro do Kommo)
    erro                 erro do Kommo persistente, item do menu ausente ou erro inesperado
"""
import contextlib
import os
import queue
import threading
import time
import unicodedata
from dataclasses import dataclass
from urllib.parse import urlsplit

from . import browser, config, kommo, paths, privacy
from .fluxo import Resultado, avaliar_uniao

VALORES_VERDADEIROS = ("1", "true", "yes", "on")


def debug_ligado(environ=None) -> bool:
    """KOMMO_DEBUG liga o modo diagnóstico só com valor verdadeiro: "1", "true", "yes", "on" (sem diferenciar
    maiúsculas, espaços ignorados). "0", "false", "no", "off", "" ou ausente NÃO ligam."""
    environ = os.environ if environ is None else environ
    return str(environ.get("KOMMO_DEBUG") or "").strip().lower() in VALORES_VERDADEIROS


# ---------------------------------------------------------------------------------------------- trabalho e eventos
@dataclass
class Job:
    empresa: str
    tipo: str                    # "leads" | "contatos"
    limite: int                  # 0 = todas
    privacidade: bool = True
    ensaio: bool = False         # abre o modal, lê total/validação e NÃO clica em Unir
    confirmar_conta: bool = True  # emite ConfirmarEvt e espera responder() antes do 1º clique


@dataclass
class LogEvt:
    nivel: str
    msg: str


@dataclass
class ProgEvt:
    feitos: int          # uniões CONFIRMADAS (compatibilidade com a UI)
    limite: int
    total: int           # total de grupos que o Kommo informou no início (0 = não informado)
    incertas: int = 0    # cliques em Unir sem confirmação do Kommo
    cliques: int = 0     # cliques em Unir disparados (= feitos + incertas, mais a união em andamento)


@dataclass
class FimEvt:
    feitos: int          # = confirmadas (compatibilidade com a UI)
    segundos: float
    erros: int
    interrompido: bool
    total: int
    confirmadas: int = 0
    incertas: int = 0
    cliques: int = 0
    motivo: str = ""     # ver MOTIVOS
    avisos: int = 0
    espera_busca: float = 0.0   # busca_sem_resposta: segundos esperados pela última busca sem resposta


@dataclass
class ConfirmarEvt:
    host: str            # "<empresa>.kommo.com" da aba logada
    tipo: str
    total: int           # 0 = o Kommo não informou ("muitas")
    limite: int          # 0 = todas
    ensaio: bool = False


MOTIVOS = {
    "limite": "limite atingido",
    "sem_duplicatas": "sem duplicatas restantes",
    "busca_sem_resposta": "o Kommo não mostrou novos grupos de duplicatas (não confirmado)",
    "parado": "interrompido pelo usuário",
    "forcado": "parada forçada pelo usuário",
    "ensaio": "ensaio (nada unido)",
    "recusado": "conta não confirmada (nada unido)",
    "sem_resposta": "sem resposta à confirmação (nada unido)",
    "sessao_expirada": "sessão do Kommo expirada ou redirecionada",
    "validacao": "conta, página ou modal não conferem",
    "login_timeout": "login não confirmado a tempo",
    "navegador_fechado": "navegador fechado",
    "navegador_indisponivel": "navegador indisponível",
    "falhas": "falhas seguidas",
    "erro": "erro",
}

# ---------------------------------------------------------------------------------------------- tempos (segundos)
TEMPO_UNIAO = 120            # teto para uma união chegar a um estado estável
TEMPO_BUSCA = 90             # teto para o Kommo (re)carregar a busca de duplicatas
TEMPOS_REBUSCA = (120, 180)  # busca sem resposta: refaz (ou continua esperando) até 2x, com tetos estendidos
CONFIRMAR_VAZIO = 2          # leituras seguidas com "nenhuma duplicata" antes de concluir sem_duplicatas
TEMPO_LOGIN = 600            # teto para o usuário fazer login (depois: erro claro)
TEMPO_CONFIRMACAO = 600      # teto para a resposta da confirmação da conta
REAVISO_LOGIN = 60           # repete o aviso de login a cada N s
GRACA_FECHAMENTO = 3.0       # aba fechada sem outra aberta: espera isso antes de concluir "navegador fechado" (T10)
POLL_GRACA = 0.5
ERRO_TENTATIVAS = 5          # cliques em "Tentar novamente" por ciclo de busca, antes de reabrir pelo menu
REABERTURAS_MAX = 1          # reaberturas pelo menu por ciclo de busca (último recurso)
FALHAS_MAX = 3               # uniões seguidas sem resultado (tempo esgotado/erro) antes de parar
POLL_UNIAO = 0.2             # amostragem durante a união (rápida, para ver os textos de progresso)
POLL_BUSCA = 0.5
POLL_LOGIN = 1.5
POLL_CONFIRMACAO = 0.5
PAUSA_ERRO = 2.0             # depois de "Tentar novamente"
PAUSA_MENU = 0.6             # entre abrir o menu "⋯" e clicar no item
ESTABILIZAR = 1.0            # depois de uma união não confirmada, antes de reconferir o estado
INTERVALO_PRIVACIDADE = 3.0  # reforço do modo privacidade (o init script é a base)
TIMEOUT_PAGINA_MS = 15_000   # page.set_default_timeout
TIMEOUT_NAVEGACAO_MS = 60_000

_NOME_TIPO = {"leads": "Leads", "contatos": "Contatos"}
# Prefixo de caminho aceito por tipo: Leads pode redirecionar para um filtro salvo (/leads/list/pipeline/…), por isso
# só "/leads"; Contatos exige a lista de CONTATOS (a de empresas, /contacts/list/companies, não serve).
_CAMINHO_TIPO = {"leads": "/leads", "contatos": "/contacts/list/contacts"}


# ---------------------------------------------------------------------------------------------- relógio e exceções
class Relogio:
    """Tempo real. Nos testes, `tests/fakes.RelogioFalso` avança o tempo na hora (sem sleep real)."""

    def agora(self) -> float:
        return time.monotonic()

    def dormir(self, segundos: float) -> None:
        time.sleep(max(0.0, segundos))

    def esperar(self, evento: threading.Event, segundos: float) -> bool:
        """Espera o evento por até `segundos` (acorda antes se ele for setado). Devolve evento.is_set()."""
        return evento.wait(max(0.0, segundos))


class FimDoFluxo(Exception):
    """Encerra a execução com um motivo (FimEvt.motivo) e uma mensagem já pronta para o usuário."""
    motivo = "erro"
    nivel = "erro"

    def __init__(self, msg: str, motivo: str | None = None, nivel: str | None = None):
        super().__init__(msg)
        if motivo:
            self.motivo = motivo
        if nivel:
            self.nivel = nivel


class Interrompido(FimDoFluxo):
    """Parada pedida pelo usuário. É aviso, nunca conta como erro."""
    motivo = "parado"
    nivel = "aviso"

    def __init__(self, msg: str, forcado: bool = False):
        super().__init__(msg, motivo="forcado" if forcado else "parado")
        self.forcado = forcado


class SessaoExpirada(FimDoFluxo):
    motivo = "sessao_expirada"


class NavegadorFechado(FimDoFluxo):
    motivo = "navegador_fechado"


# ---------------------------------------------------------------------------------------------- utilidades puras
def _sem_acentos(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texto or "") if not unicodedata.combining(c))


def caminho_confere(url: str, tipo: str) -> bool:
    """True se o caminho da URL é da lista do tipo pedido (/leads… para leads, /contacts/list/contacts… para
    contatos — /contacts/list/companies/ é a lista de empresas e NÃO confere)."""
    prefixo = _CAMINHO_TIPO.get(tipo)
    if not prefixo:
        return False
    try:
        caminho = (urlsplit(url or "").path or "").lower()
    except ValueError:
        return False
    return caminho == prefixo or caminho.startswith(prefixo + "/")


def modal_de_duplicatas(caption: str) -> bool:
    """True se o título do modal é o de duplicatas ("Localizar e unir duplicatas — …", "Find duplicates"…)."""
    return "duplicat" in _sem_acentos(caption).lower()


def _eh_fechamento(exc: BaseException) -> bool:
    """Erro do Playwright de navegador/aba/contexto fechado."""
    if type(exc).__name__ == "TargetClosedError":
        return True
    msg = str(exc).lower()
    return "has been closed" in msg or "target closed" in msg or "browser has disconnected" in msg


def _porta_fechada(porta) -> bool:
    """True se a aba do navegador foi fechada. Usa `porta.esta_fechada()` (KommoPage e os falsos a implementam);
    `porta.page.is_closed()` fica só como reserva para portas antigas sem o método."""
    try:
        fn = getattr(porta, "esta_fechada", None)
        if callable(fn):
            return bool(fn())
        pg = getattr(porta, "page", None)
        fn = getattr(pg, "is_closed", None)
        return bool(callable(fn) and fn())
    except Exception:  # noqa: BLE001 - na dúvida, não é fechamento (as leituras seguintes dirão)
        return False


def _curto(texto: str, n: int = 80) -> str:
    t = " ".join(str(texto or "").split())
    return t if len(t) <= n else t[: n - 1] + "…"


# ---------------------------------------------------------------------------------------------- motor
class Merger(threading.Thread):
    """Thread NÃO-daemon que executa um `Job`.

    API para a UI/CLI:
        Merger(job, fila, parar=None, *, relogio=None, abrir_sessao=None, debug=None)
        .start() / .is_alive() / .join()
        .solicitar_parada(forcar=False)   1º pedido: para ENTRE uniões; 2º pedido (ou forcar=True): aborta na hora
        .responder(aceito)                resposta ao ConfirmarEvt
        .parar_e_aguardar(timeout=None, forcar=False) -> bool   pede parada e espera a thread (True se terminou)
        .cliques / .confirmadas / .incertas / .erros / .avisos / .total / .motivo   (atualizados a cada passo)

    `parar` é o Event compartilhado com a UI (compatibilidade: setá-lo direto equivale a solicitar_parada()).
    `abrir_sessao` (testes): fábrica de context manager que entrega a porta; padrão: sessão Playwright real.
    """

    def __init__(self, job: Job, fila: queue.Queue, parar: threading.Event | None = None, *,
                 relogio: Relogio | None = None, abrir_sessao=None, debug: bool | None = None):
        super().__init__(name="Merger", daemon=False)
        self.job, self.fila = job, fila
        self.parar = parar if parar is not None else threading.Event()
        self.relogio = relogio or Relogio()
        self._abrir_sessao = abrir_sessao or self._sessao_playwright
        self.debug = debug_ligado() if debug is None else bool(debug)
        self._forcar = threading.Event()
        self._evt_resposta = threading.Event()
        self._trava = threading.Lock()
        self._resposta: bool | None = None
        # contadores (atributos de instância: sobrevivem a qualquer exceção)
        self.erros = 0
        self.avisos = 0
        self.total = 0
        self.cliques = 0
        self.confirmadas = 0
        self.incertas = 0
        self.motivo = ""
        self.host = f"{kommo.normalizar_empresa(job.empresa)}.{kommo.DOMINIO}"
        self._uniao_pendente = False
        self._nav_na_uniao = False
        self._ultimo_estado = kommo.Estado()
        self._ultimo_lido = kommo.Estado()     # última leitura da busca (qualquer que seja)
        self._viu_carregando = False
        self._espera_busca = 0.0
        self._textos_progresso: set[str] = set()
        self._ult_priv: float | None = None
        self._t_ini: float | None = None
        self._fim_emitido = False

    # ------------------------------------------------------------------ API pública (thread da UI)
    def solicitar_parada(self, forcar: bool = False) -> None:
        """1º pedido: termina a união em andamento e para ENTRE uniões. 2º pedido (ou forcar=True): aborta no
        PRÓXIMO ponto de checagem — os laços de espera (login, busca, união, tolerância de aba) checam a cada
        amostragem (≤ 1,5 s) e `_abrir_url` checa entre as tentativas — e fecha o navegador sem esperar a união em
        andamento (que fica como "não confirmada"). Não interrompe instantaneamente um `goto` ou a abertura do
        navegador já em curso (podem levar até TIMEOUT_NAVEGACAO_MS)."""
        if forcar or self.parar.is_set():
            self._forcar.set()
        self.parar.set()
        self._evt_resposta.set()          # acorda a espera da confirmação (sem resposta = parada)

    def responder(self, aceito: bool) -> None:
        """Resposta ao ConfirmarEvt: True continua; False encerra sem clicar (motivo "recusado")."""
        with self._trava:
            self._resposta = bool(aceito)
        self._evt_resposta.set()

    def parar_e_aguardar(self, timeout: float | None = None, forcar: bool = False) -> bool:
        """Pede a parada e espera a thread terminar (até `timeout` s). True se terminou."""
        self.solicitar_parada(forcar)
        if self.is_alive():
            self.join(timeout)
        return not self.is_alive()

    @property
    def parada_forcada(self) -> bool:
        return self._forcar.is_set()

    # ------------------------------------------------------------------ eventos
    def log(self, msg: str, nivel: str = "info") -> None:
        if nivel == "erro":
            self.erros += 1
        elif nivel == "aviso":
            self.avisos += 1
        self.fila.put(LogEvt(nivel, msg))

    def _progresso(self) -> None:
        self.fila.put(ProgEvt(self.confirmadas, self.job.limite, self.total, self.incertas, self.cliques))

    def _emitir_fim(self) -> None:
        if self._fim_emitido:
            return
        self._fim_emitido = True
        self._contar_pendente()
        motivo = self.motivo or "erro"
        segundos = max(0.0, self.relogio.agora() - (self._t_ini if self._t_ini is not None else self.relogio.agora()))
        # True só quando a parada interrompeu a execução (motivo parado/forcado). Parada pedida que não chegou a
        # interromper nada (ex.: o limite foi atingido na mesma união) não marca interrompido.
        interrompido = motivo in ("parado", "forcado")
        partes = [f"{self.confirmadas} confirmadas"]
        if self.incertas:
            partes.append(f"{self.incertas} não confirmadas")
        partes.append(f"{self.cliques} cliques em Unir")
        if motivo in ("limite", "sem_duplicatas", "ensaio"):
            nivel_fim = "ok"
        else:
            nivel_fim = "aviso" if motivo == "busca_sem_resposta" else "info"
        self.log(f"Fim ({MOTIVOS.get(motivo, motivo)}): " + ", ".join(partes) + ".", nivel_fim)
        self._progresso()
        espera = round(self._espera_busca, 1) if motivo == "busca_sem_resposta" else 0.0
        self.fila.put(FimEvt(self.confirmadas, segundos, self.erros, interrompido, self.total,
                             self.confirmadas, self.incertas, self.cliques, motivo, self.avisos, espera_busca=espera))

    def _contar_pendente(self) -> None:
        """Uma união clicada cujo resultado não foi lido (exceção/parada forçada) conta como não confirmada."""
        if self._uniao_pendente:
            self._uniao_pendente = False
            self.incertas += 1
            self.log("A união em andamento não pôde ser confirmada (contada como não confirmada).", "aviso")

    # ------------------------------------------------------------------ execução
    def run(self) -> None:
        self._t_ini = self.relogio.agora()
        try:
            self._validar_job()
            with self._abrir_sessao() as porta:
                self.motivo = self._executar(porta)
        except FimDoFluxo as e:
            self._contar_pendente()
            self.motivo = e.motivo
            self.log(str(e), e.nivel)
        except browser.NavegadorIndisponivel as e:
            self.motivo = "navegador_indisponivel"
            self.log(str(e), "erro")
        except paths.DataDirNotWritable as e:
            self.motivo = "erro"
            self.log(str(e), "erro")
        except Exception as e:  # noqa: BLE001 - nada pode impedir o FimEvt
            self._contar_pendente()
            if _eh_fechamento(e):
                self.motivo = "navegador_fechado"
                self.log("O navegador foi fechado — execução encerrada.", "erro" if self.cliques else "aviso")
            elif kommo.eh_transitorio(e):
                self.motivo = "erro"
                self.log(f"A página do Kommo parou de responder ({type(e).__name__}). Tente de novo.", "erro")
            else:
                self.motivo = "erro"
                self.log(f"Erro inesperado: {type(e).__name__}: {_curto(str(e), 300)}", "erro")
        finally:
            self._emitir_fim()

    def _validar_job(self) -> None:
        if self.job.tipo not in kommo.TIPOS:
            raise FimDoFluxo(f"Tipo inválido: {self.job.tipo!r} (use leads ou contatos).", motivo="validacao")
        if not kommo.normalizar_empresa(self.job.empresa) or self.job.limite is None or int(self.job.limite) < 0:
            raise FimDoFluxo("Empresa ou quantidade inválida.", motivo="validacao")

    @contextlib.contextmanager
    def _sessao_playwright(self):
        """Sessão real: navegador com perfil persistente, init script de privacidade, KommoPage na lista."""
        from playwright.sync_api import sync_playwright   # import tardio: o motor é testável sem Playwright

        url = kommo.montar_url(self.job.empresa, self.job.tipo)
        with sync_playwright() as p:
            ctx = None
            try:
                canal = None
                try:
                    canal = config.carregar().get("canal_navegador") or None
                except Exception:  # noqa: BLE001 - preferência acessória
                    pass
                info: dict = {}
                ctx = browser.abrir_contexto(p, paths.profile_dir(), self.log, canal_preferido=canal, info=info)
                if info.get("canal"):
                    try:
                        config.salvar(canal_navegador=info["canal"])
                    except Exception as e:  # noqa: BLE001 - falha de config não derruba a execução
                        self.log(f"Não foi possível lembrar o navegador usado ({type(e).__name__}).", "aviso")
                try:
                    ctx.add_init_script(privacy.init_script(self.job.privacidade))
                except Exception as e:  # noqa: BLE001
                    if self.job.privacidade:
                        self.log(f"Não foi possível registrar o modo privacidade no início das páginas "
                                 f"({type(e).__name__}); usando só o reforço periódico.", "aviso")
                page = ctx.pages[0] if ctx.pages else ctx.new_page()
                self._configurar_pagina(page)
                # A porta conhece o contexto: se a aba for fechada/substituída (login/redirecionamento), ela adota
                # outra aba aberta em vez de o motor concluir "navegador fechado" (T10).
                porta = kommo.KommoPage(page, ctx=ctx, ao_trocar=self._configurar_pagina)
                self._abrir_url(porta, url)
                yield porta
            finally:
                self._fechar_contexto(ctx)

    @staticmethod
    def _configurar_pagina(page) -> None:
        """O que é por aba (a privacidade é init script do contexto e vale para todas as abas)."""
        try:
            page.set_default_timeout(TIMEOUT_PAGINA_MS)
            page.set_default_navigation_timeout(TIMEOUT_NAVEGACAO_MS)
        except Exception:  # noqa: BLE001
            pass

    def _abrir_url(self, porta, url: str) -> None:
        """Navega a aba da porta até a lista. Aceita uma `page` crua (compatibilidade) ou a porta (KommoPage)."""
        self.log(f"Abrindo a lista de {_NOME_TIPO.get(self.job.tipo, self.job.tipo)}: {url}")
        for tentativa in (1, 2):
            self._checar_forcado()              # A13: parada forçada atendida entre as tentativas
            page = getattr(porta, "page", porta)
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_NAVEGACAO_MS)
                return
            except Exception as e:  # noqa: BLE001
                fechada = False
                try:
                    fechada = page.is_closed()
                except Exception:  # noqa: BLE001
                    pass
                if fechada or _eh_fechamento(e):
                    if tentativa == 1 and porta is not page and self._adotar(porta):
                        continue                # a aba foi substituída: tenta de novo na aba adotada
                    raise NavegadorFechado("O navegador foi fechado antes de abrir o Kommo.", nivel="aviso") from e
                if tentativa == 2:
                    atual = ""
                    try:
                        atual = page.url or ""
                    except Exception:  # noqa: BLE001
                        pass
                    if atual and not atual.startswith("about:"):
                        self.log("A página do Kommo demorou para carregar; seguindo com o que abriu.", "aviso")
                        return
                    raise FimDoFluxo(f"Não consegui abrir a página do Kommo ({type(e).__name__}). "
                                     "Confira a internet e tente de novo.") from e
                self.log("A página do Kommo demorou para abrir; tentando de novo…", "aviso")
                self._checar_forcado()
                self.relogio.dormir(3)

    @staticmethod
    def _fechar_contexto(ctx) -> None:
        if ctx is None:
            return
        try:
            ctx.close()
        except Exception:  # noqa: BLE001 - já fechado pelo usuário
            pass

    # ------------------------------------------------------------------ fluxo (testável com porta falsa)
    def _executar(self, porta) -> str:
        """Fluxo completo sobre a porta. Devolve o motivo do término normal; anomalias saem por exceção."""
        self._aguardar_login(porta)
        self._validar_pagina(porta)
        self._reforcar_privacidade(porta, agora=True)

        res = self._abrir_modal(porta)
        if res == "parado":
            return self._fim_parado(porta, "antes de abrir as duplicatas")
        if res != "pronto":
            return self._busca_sem_grupo(porta, res, inicial=True)

        est = self._ultimo_estado
        self._registrar_total(est.caption)
        self._validar_modal(est)
        self.log(f"Modal aberto: {est.caption}")

        if self.job.confirmar_conta:
            motivo = self._confirmar(porta)
            if motivo:
                return motivo

        if self.job.ensaio:
            self.log("Ensaio concluído: conta, lista e modal de duplicatas conferidos. Nada foi unido.", "ok")
            self._fechar_modal_seguro(porta)
            return "ensaio"

        return self._laco(porta)

    def _laco(self, porta) -> str:
        """Laço de uniões. Parada e limite só são checados ENTRE uniões."""
        meta = int(self.job.limite) if self.job.limite else None
        falhas = 0
        self._nav_na_uniao = False
        while True:
            if meta is not None and self.cliques >= meta:
                self.log("Quantidade pedida atingida.", "ok")
                break
            if self.parar.is_set():
                return self._fim_parado(porta, "depois da união em andamento")
            # devolve na hora se o botão Unir já está visível; se a página recarregou durante a união, o modal não
            # volta sozinho: a busca reabre pelo menu. Busca sem resposta é refeita (TEMPOS_REBUSCA), nunca sucesso.
            res = self._buscar(porta, navegou_antes=self._nav_na_uniao)
            self._nav_na_uniao = False
            if res == "parado":
                return self._fim_parado(porta, "depois da união em andamento")
            if res != "pronto":
                return self._busca_sem_grupo(porta, res)
            antes = self._ultimo_estado
            self._validar_pagina(porta)
            self._validar_modal(antes)
            # A16: última checagem imediatamente antes do clique (a parada pode ter chegado durante a busca)
            self._checar_forcado()
            if self.parar.is_set():
                return self._fim_parado(porta, "antes do próximo clique em Unir")

            self.cliques += 1                           # conta ANTES: o limite nunca é ultrapassado
            self._uniao_pendente = True
            t0 = self.relogio.agora()
            if porta.clicar_unir():
                r = self._aguardar_uniao(porta, antes)
            else:
                r = "clique_falhou"
            dur = self.relogio.agora() - t0
            self._uniao_pendente = False
            rotulo = f"União {self.cliques}/{self.job.limite or 'todas'}"

            if r is Resultado.SUCESSO:
                self.confirmadas += 1
                falhas = 0
                self.log(f"{rotulo} confirmada em {dur:.1f}s.")
            elif r is Resultado.INCERTO:
                self.incertas += 1
                self.log(f"{rotulo}: o Kommo não confirmou a conclusão ({dur:.1f}s) — contada como não "
                         "confirmada; reconferindo a tela antes de seguir.", "aviso")
            elif r is Resultado.ERRO:
                self.incertas += 1
                falhas += 1
                self.log(f"{rotulo}: o Kommo mostrou 'Algo deu errado' durante a união — contada como não "
                         "confirmada.", "aviso")
            elif r == "clique_falhou":
                self.incertas += 1
                falhas += 1
                self.log(f"{rotulo}: o clique em 'Unir' falhou — contado como não confirmado para não "
                         "ultrapassar a quantidade pedida.", "aviso")
            else:                                        # None: tempo esgotado
                self.incertas += 1
                falhas += 1
                self.log(f"{rotulo}: sem resultado em {TEMPO_UNIAO}s (falha {falhas}/{FALHAS_MAX}).", "erro")
                self._diagnostico(porta, "uniao_sem_resultado")
            self._progresso()

            if falhas >= FALHAS_MAX:
                raise FimDoFluxo(f"Parando após {FALHAS_MAX} uniões seguidas sem resultado.", motivo="falhas")
            if r is not Resultado.SUCESSO and not (meta is not None and self.cliques >= meta) \
                    and not self.parar.is_set():
                self.relogio.dormir(ESTABILIZAR)        # INCERTO: deixa a tela assentar e reconfere no topo

        self._fechar_modal_seguro(porta)
        return "limite"

    # ------------------------------------------------------------------ login e validações
    def _aguardar_login(self, porta) -> None:
        """Espera hostname EXATO da empresa + botão de menu "⋯". Reaviso a cada REAVISO_LOGIN s; teto TEMPO_LOGIN."""
        t0 = self.relogio.agora()
        proximo_aviso = t0
        primeira = True
        while True:
            self._checar_forcado()
            self._checar_fechado(porta)
            if self.parar.is_set():
                raise Interrompido("Interrompido antes do login.")
            if kommo.hostname_confere(porta.url_atual(), self.job.empresa) and porta.tem_menu():
                self.log(f"Login confirmado ({self.host}).", "ok")
                return
            if self._adotar_logada(porta):      # A4: login concluído em outra aba do contexto
                continue
            agora = self.relogio.agora()
            if agora - t0 >= TEMPO_LOGIN:
                raise FimDoFluxo(f"O login no Kommo não foi confirmado em {TEMPO_LOGIN // 60} min. Entre na conta "
                                 f"{self.host} e inicie de novo.", motivo="login_timeout")
            if agora >= proximo_aviso:
                if primeira:
                    self.log("Faça login na janela do Kommo — o app continua sozinho depois.", "aviso")
                    primeira = False
                else:
                    atual = porta.hostname() or "página em branco"
                    resta = max(1, -int(-(TEMPO_LOGIN - (agora - t0)) // 60))     # minutos, arredondado p/ cima
                    self.log(f"Ainda aguardando o login (página atual: {atual}; o app espera mais ~{resta} min). "
                             f"Depois de entrar, abra a lista de {_NOME_TIPO.get(self.job.tipo, self.job.tipo)} "
                             f"de {self.host}.", "aviso")
                proximo_aviso = agora + REAVISO_LOGIN
            self.relogio.dormir(POLL_LOGIN)

    def _validar_pagina(self, porta) -> None:
        """Hostname exato da empresa e caminho coerente com o tipo. Senão aborta SEM clicar."""
        url = porta.url_atual()
        if not kommo.hostname_confere(url, self.job.empresa):
            raise FimDoFluxo(f"A aba não está na conta {self.host} (está em {porta.hostname() or '?'}). "
                             "Encerrado por segurança, sem unir.", motivo="validacao")
        if not caminho_confere(url, self.job.tipo):
            raise FimDoFluxo(f"A página aberta não é a lista de {_NOME_TIPO.get(self.job.tipo, self.job.tipo)}. "
                             "Encerrado por segurança, sem unir.", motivo="validacao")

    def _validar_modal(self, est) -> None:
        if not modal_de_duplicatas(est.caption):
            raise FimDoFluxo("O modal aberto não é o de 'Localizar e unir duplicatas'. Encerrado por segurança, "
                             "sem unir.", motivo="validacao")

    def _checar_sessao(self, porta) -> None:
        """Sessão ainda logada na lista certa (hostname exato + caminho + menu). Senão: SessaoExpirada."""
        url = porta.url_atual()
        if kommo.hostname_confere(url, self.job.empresa) and caminho_confere(url, self.job.tipo) \
                and porta.tem_menu():
            return
        raise SessaoExpirada(f"A sessão do Kommo parece ter expirado ou a página foi redirecionada (página atual: "
                             f"{porta.hostname() or '?'}). Nada foi dado como concluído — entre de novo e reinicie.")

    def _checar_forcado(self) -> None:
        if self._forcar.is_set():
            raise Interrompido("Parada forçada: o navegador foi fechado sem esperar a união em andamento.",
                               forcado=True)

    def _checar_fechado(self, porta) -> None:
        """Só conclui "navegador fechado" quando NÃO resta nenhuma aba no contexto (T10).

        Se a aba usada foi fechada/substituída (login/redirecionamento do Kommo abrindo outra aba), adota a outra
        aba aberta e segue esperando. Sem outra aba, dá `GRACA_FECHAMENTO` s para uma aba nova aparecer (a troca não
        é atômica) antes de encerrar. As validações de conta/página/modal continuam valendo antes de qualquer clique.
        """
        if not _porta_fechada(porta) or self._adotar(porta):
            return
        fim = self.relogio.agora() + GRACA_FECHAMENTO
        while self.relogio.agora() < fim:
            self._checar_forcado()
            self.relogio.dormir(POLL_GRACA)
            if not _porta_fechada(porta) or self._adotar(porta):
                return
        raise NavegadorFechado("O navegador foi fechado — execução encerrada.",
                               nivel="erro" if self.cliques else "aviso")

    def _adotar(self, porta) -> bool:
        """Pede à porta para usar outra aba aberta do contexto. True se trocou (e registra no log)."""
        fn = getattr(porta, "adotar_pagina", None)
        if not callable(fn):
            return False
        try:
            trocou = bool(fn())
        except Exception:  # noqa: BLE001 - na dúvida, não trocou (a tolerância decide)
            return False
        if trocou:
            self.log(f"A aba do Kommo foi fechada ou substituída; o app passou a acompanhar a outra aba aberta "
                     f"({porta.hostname() or 'página em branco'}).", "aviso")
            self._reforcar_privacidade(porta, agora=True)
        return trocou

    def _adotar_logada(self, porta) -> bool:
        """Durante a espera do login: se OUTRA aba do contexto está logada na empresa (hostname exato + menu "⋯"),
        passa a acompanhá-la (A4). True se trocou (e registra no log)."""
        fn = getattr(porta, "adotar_aba_logada", None)
        if not callable(fn):
            return False
        try:
            trocou = bool(fn(self.job.empresa))
        except Exception:  # noqa: BLE001 - na dúvida, não trocou
            return False
        if trocou:
            self.log(f"O login foi concluído em outra aba ({self.host}); o app passou a acompanhar essa aba.", "aviso")
            self._reforcar_privacidade(porta, agora=True)
        return trocou

    # ------------------------------------------------------------------ confirmação da conta
    def _confirmar(self, porta) -> str | None:
        """Emite ConfirmarEvt e BLOQUEIA até responder()/parada/teto. Devolve o motivo de término ou None (ok)."""
        with self._trava:
            self._resposta = None
            if not self.parar.is_set():
                self._evt_resposta.clear()
        self.fila.put(ConfirmarEvt(self.host, self.job.tipo, self.total, self.job.limite, self.job.ensaio))
        self.log("Aguardando a confirmação da conta antes da primeira união…")
        fim = self.relogio.agora() + TEMPO_CONFIRMACAO
        while True:
            with self._trava:
                resposta = self._resposta
            if resposta is not None:
                break
            self._checar_forcado()
            if self.parar.is_set():
                return self._fim_parado(porta, "antes da primeira união")
            if self.relogio.agora() >= fim:
                self.log(f"Sem resposta à confirmação em {TEMPO_CONFIRMACAO // 60} min — nada foi unido.", "aviso")
                self._fechar_modal_seguro(porta)
                return "sem_resposta"
            self.relogio.esperar(self._evt_resposta, POLL_CONFIRMACAO)
        if not resposta:
            self.log("Conta não confirmada — nada foi unido.", "aviso")
            self._fechar_modal_seguro(porta)
            return "recusado"
        self.log("Conta confirmada.", "ok")
        return None

    # ------------------------------------------------------------------ modal e busca
    def _abrir_menu_item(self, porta):
        """Menu "⋯" -> item "Localizar duplicatas" do tipo. True | False (item não achado) | "parado"."""
        for _ in range(3):
            self._checar_forcado()
            self._checar_fechado(porta)
            if self.parar.is_set():
                return "parado"
            if not porta.abrir_menu():
                self.log("Botão de menu (⋯) não encontrado; aguardando…", "aviso")
                self.relogio.dormir(2)
                continue
            self.relogio.dormir(PAUSA_MENU)
            if not porta.clicar_item_duplicatas(self.job.tipo):
                self.log("Item 'Localizar duplicatas' não encontrado no menu.", "aviso")
                porta.fechar_modal()
                self.relogio.dormir(1.5)
                continue
            return True
        return False

    def _abrir_modal(self, porta) -> str:
        r = self._abrir_menu_item(porta)
        if r == "parado":
            return "parado"
        if not r:
            return "sem_item"
        self.log(f"Procurando duplicatas — o Kommo pode levar até {TEMPO_BUSCA}s…")
        return self._buscar(porta)

    def _reabrir(self, porta) -> bool:
        """Último recurso (1x por ciclo): fecha o modal e abre "Localizar duplicatas" de novo pelo menu."""
        self.log("Reabrindo a busca de duplicatas pelo menu…", "aviso")
        porta.fechar_modal()
        self.relogio.dormir(1.5)
        return self._abrir_menu_item(porta) is True

    def _buscar(self, porta, navegou_antes: bool = False) -> str:
        """`_esperar_busca` com nova tentativa quando o Kommo não responde (A1).

        "sem_resposta" (o teto passou sem modal e sem a evidência de "nenhuma duplicata") NUNCA vira sucesso: até
        len(TEMPOS_REBUSCA) vezes, com tetos estendidos, o motor espera de novo — continuando a mesma busca se a tela
        de carregamento do Kommo ainda está visível (reabrir recomeçaria a busca dele), ou fechando e reabrindo
        "Localizar duplicatas" pelo menu se não há nada na tela. Antes de cada nova tentativa confere a sessão
        (`_checar_sessao`: sessão caída vira `sessao_expirada`, nunca nova busca). Persistindo, devolve "sem_resposta" e guarda o
        tempo total esperado em `self._espera_busca`. Qualquer outro resultado é devolvido como veio.
        """
        t0 = self.relogio.agora()
        self._espera_busca = 0.0
        res = self._esperar_busca(porta, navegou_antes)
        n = len(TEMPOS_REBUSCA)
        for i, tempo in enumerate(TEMPOS_REBUSCA, 1):
            if res != "sem_resposta":
                return res
            self._checar_sessao(porta)          # sessão caída/redirecionada: SessaoExpirada, sem reabrir nada
            esperado = int(self.relogio.agora() - t0)
            if self._ultimo_lido.carregando:
                self.log(f"O Kommo ainda está procurando duplicatas depois de {esperado}s (tela de carregamento "
                         f"visível) — esperando mais até {tempo}s ({i}/{n})…", "aviso")
            else:
                self.log(f"O Kommo não mostrou nenhum grupo de duplicatas em {esperado}s — refazendo a busca pelo "
                         f"menu e esperando até {tempo}s ({i}/{n})…", "aviso")
                if i == 1:
                    self._diagnostico(porta, "busca_sem_resposta")
                if not self._reabrir(porta):
                    return "parado" if self.parar.is_set() else "sem_item"
            res = self._esperar_busca(porta, tempo=tempo)
        if res == "sem_resposta":
            self._espera_busca = self.relogio.agora() - t0
        return res

    def _esperar_busca(self, porta, navegou_antes: bool = False, tempo: float | None = None) -> str:
        """Espera o botão "Unir" (novo grupo). Usada ao abrir o modal E depois de cada união (via `_buscar`).

        Devolve "pronto" (Unir visível; estado em self._ultimo_estado), "vazio" (EVIDÊNCIA POSITIVA: "nenhuma
        duplicata" em CONFIRMAR_VAZIO leituras seguidas, sem erro), "sem_resposta" (o teto passou sem modal e sem
        evidência — NÃO é "vazio"), "erro" (erro persistiu após ERRO_TENTATIVAS + reabertura), "travado" (modal
        visível sem botão até o teto), "sem_item" (reabertura pelo menu falhou) ou "parado" (parada pedida — aqui não
        há união em andamento). `tempo` = teto desta espera (padrão TEMPO_BUSCA). A tela de carregamento
        (`Estado.carregando`) não conta como modal; só é registrada no log uma vez por execução.

        Um ciclo = esta chamada. O contador de "Tentar novamente" é compartilhado no ciclo e `houve_erro` só zera
        quando o botão Unir volta (ou seja, fim do ciclo). Página navegando (recarga) também força a reabertura antes
        de concluir "vazio", porque o modal não volta sozinho depois de um recarregamento (`navegou_antes`: a
        recarga foi vista durante a união).
        """
        teto = TEMPO_BUSCA if tempo is None else tempo
        tentativas = 0
        reaberturas = 0
        vazios = 0
        houve_erro = False
        houve_nav = bool(navegou_antes)
        fim = self.relogio.agora() + teto
        while True:
            self._checar_forcado()
            self._checar_fechado(porta)
            if self.parar.is_set():
                return "parado"
            self._reforcar_privacidade(porta)
            est = porta.estado()
            self._ultimo_lido = est
            if est.carregando and not self._viu_carregando:
                self._viu_carregando = True
                self.log("Kommo procurando duplicatas (tela de carregamento com o uso da conta)…")
            if est.navegou:
                houve_nav = True
                vazios = 0
            elif est.erro:
                houve_erro = True
                if tentativas < ERRO_TENTATIVAS:
                    tentativas += 1
                    self.log(f"Kommo mostrou 'Algo deu errado' — clicando em Tentar novamente "
                             f"({tentativas}/{ERRO_TENTATIVAS}).", "aviso")
                    porta.tentar_novamente()
                    fim = self.relogio.agora() + teto
                    self.relogio.dormir(PAUSA_ERRO)
                    continue
                if reaberturas < REABERTURAS_MAX:
                    reaberturas += 1
                    self._diagnostico(porta, "erro_busca")
                    if self._reabrir(porta):
                        fim = self.relogio.agora() + teto
                        continue
                return "erro"
            elif est.pode and not est.progresso:
                self._ultimo_estado = est
                return "pronto"
            elif est.vazio and not est.progresso:
                vazios += 1
                if vazios >= CONFIRMAR_VAZIO and not houve_erro:
                    return "vazio"
            else:
                vazios = 0
            if self.relogio.agora() >= fim:
                if (houve_erro or houve_nav) and reaberturas < REABERTURAS_MAX:
                    reaberturas += 1
                    self._diagnostico(porta, "busca_sem_grupo")
                    if self._reabrir(porta):
                        fim = self.relogio.agora() + teto
                        continue
                    return "erro" if houve_erro else "sem_item"
                if houve_erro:
                    return "erro"
                if est.modal:
                    return "travado"
                return "sem_resposta"         # sem modal e sem evidência de "nenhuma duplicata": NÃO é vazio
            self.relogio.dormir(POLL_BUSCA)

    def _busca_sem_grupo(self, porta, res: str, inicial: bool = False) -> str:
        """A busca não trouxe um grupo: decide entre "sem_duplicatas" (só com evidência positiva e sessão ok),
        "busca_sem_resposta" (sem evidência, sessão ok — aviso, nunca sucesso) e erro."""
        if res == "vazio":
            self._checar_sessao(porta)
            if inicial:
                self.log("O Kommo informou que não há duplicatas nesta lista.", "ok")
            else:
                self.log("Nenhuma duplicata restante: concluído.", "ok")
            self._fechar_modal_seguro(porta)
            return "sem_duplicatas"
        if res == "sem_resposta":
            self._checar_sessao(porta)
            seg = int(round(self._espera_busca))
            if inicial:
                self.log(f"Não foi possível confirmar se há duplicatas: o Kommo não mostrou nenhum grupo em {seg}s "
                         "(nem a mensagem de que não há duplicatas). Pode não haver duplicatas ou a busca estar "
                         "lenta — confira no Kommo.", "aviso")
            else:
                self.log(f"O Kommo não mostrou novos grupos de duplicatas em {seg}s. Pode não haver mais duplicatas "
                         "ou a busca estar lenta — confira no Kommo.", "aviso")
            self._fechar_modal_seguro(porta)
            return "busca_sem_resposta"
        self._diagnostico(porta, "busca_" + res)
        if res == "erro":
            raise FimDoFluxo("O Kommo continua mostrando 'Algo deu errado'. Tente de novo em alguns minutos.")
        if res == "travado":
            raise FimDoFluxo(f"A busca de duplicatas não terminou em {TEMPO_BUSCA}s (modal aberto sem o botão "
                             "'Unir'). Tente de novo.")
        raise FimDoFluxo("Não encontrei o item 'Localizar duplicatas' no menu (⋯) da lista.")

    def _aguardar_uniao(self, porta, antes):
        """Observa a união até um estado estável. NÃO checa a parada normal (só a forçada).

        Devolve Resultado.SUCESSO | INCERTO | ERRO, ou None se passou TEMPO_UNIAO aguardando.
        Registra no log (info) cada texto de progresso ainda não visto nesta execução (calibração de Leads).
        """
        t0 = self.relogio.agora()
        visto, ultimo = False, ""
        self._nav_na_uniao = False
        while True:
            self._checar_forcado()
            self._checar_fechado(porta)
            self._reforcar_privacidade(porta)
            est = porta.estado()
            if est.navegou:
                self._nav_na_uniao = True
            if est.progresso:
                visto, ultimo = True, est.progresso
                chave = _curto(est.progresso)
                if chave not in self._textos_progresso:
                    self._textos_progresso.add(chave)
                    self.log(f"Kommo (progresso): “{chave}”")
            r = avaliar_uniao(antes, est, visto, ultimo)
            if r is not Resultado.AGUARDA:
                return r
            if self.relogio.agora() - t0 >= TEMPO_UNIAO:
                return None
            self.relogio.dormir(POLL_UNIAO)

    # ------------------------------------------------------------------ acessórios
    def _registrar_total(self, caption: str) -> None:
        total = kommo.parse_total(caption)
        if total and not self.total:
            self.total = total
            self.log(f"Total de grupos de duplicatas informado pelo Kommo: {total:,}".replace(",", "."), "ok")
        elif not total:
            self.log("O Kommo não informou o total de duplicatas (aparece como 'muitas').")
        self._progresso()

    def _fim_parado(self, porta, quando: str) -> str:
        self.log(f"Interrompido pelo usuário ({quando}).", "aviso")
        self._fechar_modal_seguro(porta)
        return "parado"

    def _fechar_modal_seguro(self, porta) -> None:
        """Fecha o modal com "Cancelar" (só se existir). Chamado apenas com o estado estável; mesmo assim, se ainda
        houver progresso de união na tela (ex.: depois de TEMPO_UNIAO), não clica em nada."""
        try:
            if porta.estado().progresso:
                self.log("O Kommo ainda mostra uma união em andamento; o modal não foi cancelado.", "aviso")
                return
            porta.cancelar_modal()
        except Exception:  # noqa: BLE001
            pass

    def _reforcar_privacidade(self, porta, agora: bool = False) -> None:
        """Reforço do modo privacidade (o init script é a base). No máximo a cada INTERVALO_PRIVACIDADE s."""
        if not self.job.privacidade:
            return
        t = self.relogio.agora()
        if not agora and self._ult_priv is not None and t - self._ult_priv < INTERVALO_PRIVACIDADE:
            return
        self._ult_priv = t
        try:
            pg = getattr(porta, "page", None)
            if pg is not None:
                privacy.aplicar(pg, True)
            else:
                porta.aplicar_privacidade(True, privacy.CSS)
        except Exception:  # noqa: BLE001 - página navegando: tenta de novo no próximo reforço
            pass

    def _diagnostico(self, porta, rotulo: str) -> None:
        """Diagnóstico estrutural (sem texto de clientes) no log; captura de tela só com KOMMO_DEBUG."""
        try:
            texto = porta.diagnostico()
        except Exception as e:  # noqa: BLE001
            texto = f"(diagnóstico indisponível: {type(e).__name__})"
        self.log(f"Diagnóstico ({rotulo}): " + " | ".join(str(texto).splitlines()))
        if not self.debug:
            return
        try:
            self._reforcar_privacidade(porta, agora=True)
            caminho = os.path.join(paths.debug_dir(), f"{rotulo}.png")
            porta.screenshot(caminho)
            self.log(f"Captura de depuração salva em {caminho}")
        except Exception as e:  # noqa: BLE001
            self.log(f"Falha ao salvar a captura de depuração ({type(e).__name__}).", "aviso")
