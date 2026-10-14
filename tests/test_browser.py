"""Testes do browser.py sem abrir navegador real (playwright.chromium é um stub)."""
import os

import pytest
from playwright.sync_api import Error as ErroPW

from kommo_duplicatas import browser, paths


class StubContexto:
    def __init__(self):
        self.handlers = []

    def on(self, evento, fn):
        self.handlers.append((evento, fn))


class StubChromium:
    def __init__(self, *efeitos):
        self.efeitos = list(efeitos)
        self.chamadas = []

    def launch_persistent_context(self, user_data_dir, **kwargs):
        self.chamadas.append((user_data_dir, kwargs))
        efeito = self.efeitos.pop(0)
        if isinstance(efeito, BaseException):
            raise efeito
        return efeito


class StubPlaywright:
    def __init__(self, *efeitos):
        self.chromium = StubChromium(*efeitos)


@pytest.fixture(autouse=True)
def _isolar(monkeypatch, tmp_path):
    monkeypatch.setenv("KOMMO_DATA_DIR", str(tmp_path / "dados"))
    monkeypatch.delenv("KOMMO_BROWSER", raising=False)
    monkeypatch.setattr(paths, "_verificadas", set())
    # ordem fixa, independente do SO onde o teste roda
    monkeypatch.setattr(browser, "canais_padrao", lambda *a, **k: ["chrome", "msedge", "chromium"])


SEM_CHROME = ErroPW("Chromium distribution 'chrome' is not found at C:\\...\\chrome.exe\n"
                    "Run \"npx playwright install chrome\"")
SEM_EDGE = ErroPW("Chromium distribution 'msedge' is not found at C:\\...\\msedge.exe")
SEM_CHROMIUM = ErroPW("Executable doesn't exist at C:\\...\\chrome.exe")


# ------------------------------------------------------------------------------------- abertura
def test_abre_com_sandbox_args_e_perfil_por_canal(tmp_path):
    ctx = StubContexto()
    pw = StubPlaywright(ctx)
    info = {}
    assert browser.abrir_contexto(pw, paths.profile_dir(), info=info) is ctx
    (perfil, kw), = pw.chromium.chamadas
    assert perfil == str(tmp_path / "dados" / "profile" / "chrome") == paths.profile_dir("chrome")
    assert kw["chromium_sandbox"] is True
    assert kw["args"] == ["--start-maximized", "--disable-notifications", "--deny-permission-prompts"]
    assert kw["channel"] == "chrome" and kw["headless"] is False
    assert info == {"canal": "chrome", "perfil": perfil}
    assert ctx.handlers == []                     # bloqueio de abas externas desligado por padrão


def test_perfil_padrao_quando_nao_informado(tmp_path):
    pw = StubPlaywright(StubContexto())
    browser.abrir_contexto(pw)
    assert pw.chromium.chamadas[0][0] == str(tmp_path / "dados" / "profile" / "chrome")


def test_navegador_ausente_tenta_proximo_com_outro_perfil(tmp_path):
    ctx = StubContexto()
    pw = StubPlaywright(SEM_CHROME, SEM_EDGE, ctx)
    avisos = []
    assert browser.abrir_contexto(pw, None, lambda m, n="info": avisos.append((n, m))) is ctx
    perfis = [c[0] for c in pw.chromium.chamadas]
    canais = [c[1]["channel"] for c in pw.chromium.chamadas]
    assert canais == ["chrome", "msedge", None]   # chromium do Playwright = channel None
    assert len(set(perfis)) == 3                  # cada canal com o seu perfil
    assert [os.path.basename(p) for p in perfis] == ["chrome", "msedge", "chromium"]
    assert sum(1 for n, _ in avisos if n == "aviso") == 2


def test_trava_por_texto_nao_tenta_outro_canal():
    pw = StubPlaywright(ErroPW("Failed to create a ProcessSingleton for your profile directory"), StubContexto())
    with pytest.raises(browser.NavegadorIndisponivel) as exc:
        browser.abrir_contexto(pw)
    assert len(pw.chromium.chamadas) == 1
    assert "em uso" in str(exc.value) and "Feche" in str(exc.value)


def test_arquivo_de_trava_mais_falha_generica_nao_tenta_outro_canal():
    perfil = paths.profile_dir("chrome")
    os.makedirs(perfil)
    open(os.path.join(perfil, "SingletonLock"), "w").close()
    pw = StubPlaywright(ErroPW("Target page, context or browser has been closed"), StubContexto())
    with pytest.raises(browser.NavegadorIndisponivel) as exc:
        browser.abrir_contexto(pw)
    assert len(pw.chromium.chamadas) == 1
    assert "has been closed" in str(exc.value)


def test_arquivo_de_trava_mas_navegador_nao_instalado_segue():
    perfil = paths.profile_dir("chrome")
    os.makedirs(perfil)
    open(os.path.join(perfil, "lockfile"), "w").close()      # sobra de fechamento anormal, ninguém segurando
    ctx = StubContexto()
    pw = StubPlaywright(SEM_CHROME, ctx)
    assert browser.abrir_contexto(pw) is ctx
    assert len(pw.chromium.chamadas) == 2


def test_erro_que_nao_e_do_playwright_nao_e_engolido():
    pw = StubPlaywright(TypeError("bug no código"), StubContexto())
    with pytest.raises(TypeError):
        browser.abrir_contexto(pw)
    assert len(pw.chromium.chamadas) == 1


def test_nenhum_navegador():
    pw = StubPlaywright(SEM_CHROME, SEM_EDGE, SEM_CHROMIUM)
    with pytest.raises(browser.NavegadorIndisponivel) as exc:
        browser.abrir_contexto(pw)
    msg = str(exc.value)
    assert msg == browser.mensagem_sem_navegador(
        [f"{c}: {str(e).splitlines()[0]}" for c, e in
         (("chrome", SEM_CHROME), ("msedge", SEM_EDGE), ("chromium", SEM_CHROMIUM))])
    assert "chrome:" in msg and "msedge:" in msg and "chromium:" in msg


def test_kommo_browser_forca_um_canal(monkeypatch):
    monkeypatch.setenv("KOMMO_BROWSER", "MSEDGE")
    pw = StubPlaywright(SEM_EDGE)
    with pytest.raises(browser.NavegadorIndisponivel):
        browser.abrir_contexto(pw)
    assert [c[1]["channel"] for c in pw.chromium.chamadas] == ["msedge"]


def test_kommo_browser_invalido(monkeypatch):
    monkeypatch.setenv("KOMMO_BROWSER", "firefox")
    with pytest.raises(browser.NavegadorIndisponivel) as exc:
        browser.canais_disponiveis()
    assert "chrome" in str(exc.value)


def test_canal_preferido_vai_primeiro():
    assert browser.canais_disponiveis(preferido="msedge") == ["msedge", "chrome", "chromium"]
    assert browser.canais_disponiveis(preferido="inexistente") == ["chrome", "msedge", "chromium"]
    pw = StubPlaywright(StubContexto())
    browser.abrir_contexto(pw, canal_preferido="chromium")
    assert pw.chromium.chamadas[0][1]["channel"] is None


def test_bloquear_externos_quando_pedido():
    ctx = StubContexto()
    browser.abrir_contexto(StubPlaywright(ctx), bloquear_externos=True)
    assert [e for e, _ in ctx.handlers] == ["page"]


@pytest.mark.skipif(os.name != "nt", reason="lockfile exclusivo é do Windows")
def test_perfil_em_uso_windows_nao_chama_launch():
    import ctypes
    from ctypes import wintypes

    perfil = paths.profile_dir("chrome")
    os.makedirs(perfil)
    lock = os.path.join(perfil, "lockfile")
    assert browser.perfil_em_uso(perfil) is False            # sem arquivo
    open(lock, "w").close()
    assert browser.perfil_em_uso(perfil) is False            # sobra sem dono
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateFileW.restype = wintypes.HANDLE
    k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                                wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    # Como o Chrome: escrita exclusiva, só compartilha leitura.
    h = k32.CreateFileW(lock, 0x40000000, 0x1, None, 3, 0x80, None)
    assert h not in (None, wintypes.HANDLE(-1).value)
    try:
        assert browser.perfil_em_uso(perfil) is True
        pw = StubPlaywright(StubContexto())
        with pytest.raises(browser.NavegadorIndisponivel):
            browser.abrir_contexto(pw)
        assert pw.chromium.chamadas == []
    finally:
        k32.CloseHandle(h)


# ------------------------------------------------------------------------------------- por SO (sem navegador)
def test_canais_padrao_por_so(monkeypatch):
    monkeypatch.undo()                                   # usa a função real
    sem_nada = dict(which=lambda n: None, existe=lambda p: False)
    assert browser.canais_padrao("win32", **sem_nada) == ["chrome", "msedge", "chromium"]
    assert browser.canais_padrao("darwin", **sem_nada) == ["chrome", "msedge", "chromium"]
    assert browser.canais_padrao("linux", **sem_nada) == ["chrome", "chromium"]
    com_edge = dict(which=lambda n: "/usr/bin/" + n if n == "microsoft-edge-stable" else None,
                    existe=lambda p: False)
    assert browser.canais_padrao("linux", **com_edge) == ["chrome", "msedge", "chromium"]
    assert browser.canais_padrao("linux", which=lambda n: None,
                                 existe=lambda p: p == "/opt/microsoft/msedge/msedge") == ["chrome", "msedge", "chromium"]


def test_mensagens_por_so():
    win = browser.mensagem_sem_navegador(["chrome: x"], "win32")
    assert "Google Chrome" in win and "Microsoft Edge" in win and "chrome: x" in win
    lin = browser.mensagem_sem_navegador([], "linux")
    assert "google-chrome" in lin and "chromium" in lin and "python -m playwright install chromium" in lin
    assert "Edge" not in lin
    mac = browser.mensagem_sem_navegador([], "darwin")
    assert "/Applications" in mac


def test_playwright_browsers_path_so_no_windows_congelado():
    env = {"LOCALAPPDATA": r"C:\Users\Fulano\AppData\Local"}
    assert browser.configurar_browsers_path(True, "win32", env) == r"C:\Users\Fulano\AppData\Local\ms-playwright"
    assert env["PLAYWRIGHT_BROWSERS_PATH"].endswith("ms-playwright")
    for frozen, so in ((True, "linux"), (True, "darwin"), (False, "win32")):
        env = {"LOCALAPPDATA": "x"}
        assert browser.configurar_browsers_path(frozen, so, env) is None
        assert "PLAYWRIGHT_BROWSERS_PATH" not in env
    env = {"PLAYWRIGHT_BROWSERS_PATH": "0"}                  # escolha do usuário é respeitada
    assert browser.configurar_browsers_path(True, "win32", env) is None and env["PLAYWRIGHT_BROWSERS_PATH"] == "0"


def test_deteccao_de_texto():
    assert browser.erro_de_trava("... existing browser session ...")
    assert not browser.erro_de_trava("net::ERR_NAME_NOT_RESOLVED")
    assert browser.erro_sem_executavel(str(SEM_CHROME)) and browser.erro_sem_executavel(str(SEM_CHROMIUM))
    assert not browser.erro_sem_executavel("Target page, context or browser has been closed")


# ------------------------------------------------------------------------------------- abas externas
def test_url_permitida():
    ok = ["https://empresa.kommo.com/leads/list/", "https://kommo.com", "about:blank", "",
          "https://a.b.kommo.com/x"]
    nao = ["https://evilkommo.com", "https://kommo.com.evil.io/", "https://accounts.google.com/o/oauth2",
           "http://192.168.0.1/"]
    assert all(browser.url_permitida(u) for u in ok)
    assert not any(browser.url_permitida(u) for u in nao)


class StubFrame:
    pass


class StubPagina:
    def __init__(self, url):
        self.url = url
        self.main_frame = StubFrame()
        self.handlers = {}
        self.fechada = False

    def on(self, evento, fn):
        self.handlers[evento] = fn

    def close(self):
        self.fechada = True

    def navegar(self, url):
        self.url = url
        self.handlers["framenavigated"](self.main_frame)


def test_bloquear_navegacao_externa():
    ctx = StubContexto()
    avisos = []
    browser.bloquear_navegacao_externa(ctx, "kommo.com", lambda m, n="info": avisos.append(m))
    (evento, nova), = ctx.handlers
    assert evento == "page"

    externa = StubPagina("https://exemplo.org/promo")
    nova(externa)
    assert externa.fechada and "exemplo.org" in avisos[-1]

    interna = StubPagina("https://empresa.kommo.com/leads/")
    nova(interna)
    assert not interna.fechada

    popup = StubPagina("about:blank")                       # nasce em branco e depois navega
    nova(popup)
    assert not popup.fechada
    popup.handlers["framenavigated"](StubFrame())           # iframe navegando: ignora
    assert not popup.fechada
    popup.navegar("https://rastreador.example/")
    assert popup.fechada
