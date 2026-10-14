"""Abre o navegador com perfil persistente (o login do Kommo fica salvo entre execuções).

Ordem de preferência por sistema (ver `canais_padrao`):
- Windows / macOS: Google Chrome -> Microsoft Edge -> Chromium do Playwright;
- Linux: Google Chrome -> Chromium do Playwright (Edge só entra se estiver instalado).
Assim o executável não precisa carregar um navegador dentro dele. Para forçar um deles:
variável de ambiente KOMMO_BROWSER = chrome | msedge | chromium.

Cada canal tem o SEU perfil (data/profile/<canal>, ver `paths.profile_dir`). Um perfil criado pelo Chrome não é
reaberto pelo Edge: se o Chrome falhar por causa do perfil (em uso/travado), o app para com uma mensagem clara em
vez de tentar outro navegador com o mesmo login.
"""
import os
import socket
import shutil
import sys
from urllib.parse import urlsplit

from . import paths

try:   # erros do Playwright (inclui TimeoutError). Outros erros (bugs) NÃO são engolidos pelo laço de canais.
    from playwright.sync_api import Error as _ErroPlaywright
except ImportError:  # pragma: no cover - sem playwright o app nem abre; mantém o módulo importável nos testes
    _ErroPlaywright = Exception

CANAIS_VALIDOS = ("chrome", "msedge", "chromium")

ARGS_NAVEGADOR = ["--start-maximized", "--disable-notifications", "--deny-permission-prompts"]

# Arquivos que o Chrome/Edge criam no diretório do perfil enquanto ele está aberto.
ARQUIVOS_TRAVA = ("SingletonLock", "SingletonCookie", "SingletonSocket", "lockfile")

# Textos de erro do Chromium/Playwright quando o perfil já está em uso.
TEXTOS_TRAVA = (
    "ProcessSingleton",
    "existing browser session",
    "sessão de navegador",
    "SingletonLock",
    "profile is already in use",
    "user data directory is already in use",
)

# Textos de erro que indicam "esse navegador não está instalado" (aí vale tentar o próximo canal).
TEXTOS_SEM_EXECUTAVEL = (
    "executable doesn't exist",
    "is not found at",
    "distribution",          # "Chromium distribution 'chrome' is not found ..."
    "enoent",
    "no such file",
    "playwright install",
)


class NavegadorIndisponivel(RuntimeError):
    pass


# ---------------------------------------------------------------------------------------------- ambiente
def _plataforma(plataforma: str | None = None) -> str:
    p = plataforma or sys.platform
    if p.startswith("win"):
        return "win"
    if p == "darwin":
        return "mac"
    return "linux"


def configurar_browsers_path(frozen: bool | None = None, plataforma: str | None = None,
                             environ: dict | None = None) -> str | None:
    """No .exe (Windows) o Playwright procuraria o Chromium dentro do pacote: aponta para a instalação padrão
    do usuário (%LOCALAPPDATA%\\ms-playwright). No Linux/macOS NÃO mexe (o padrão do Playwright,
    ~/.cache/ms-playwright ou ~/Library/Caches/ms-playwright, já é o correto). Devolve o valor definido ou None.
    """
    environ = os.environ if environ is None else environ
    frozen = getattr(sys, "frozen", False) if frozen is None else frozen
    if not frozen or environ.get("PLAYWRIGHT_BROWSERS_PATH") or _plataforma(plataforma) != "win":
        return None
    base = environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Local")
    environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(base, "ms-playwright")
    return environ["PLAYWRIGHT_BROWSERS_PATH"]


configurar_browsers_path()


def edge_instalado_linux(which=shutil.which, existe=os.path.exists) -> bool:
    nomes = ("microsoft-edge", "microsoft-edge-stable", "microsoft-edge-beta", "microsoft-edge-dev")
    return any(which(n) for n in nomes) or existe("/opt/microsoft/msedge/msedge")


def canais_padrao(plataforma: str | None = None, which=shutil.which, existe=os.path.exists) -> list[str]:
    """Ordem de tentativa por sistema operacional (sem abrir navegador)."""
    so = _plataforma(plataforma)
    if so == "linux":
        canais = ["chrome", "chromium"]
        if edge_instalado_linux(which, existe):
            canais.insert(1, "msedge")
        return canais
    return ["chrome", "msedge", "chromium"]


CANAIS_PADRAO = canais_padrao()


def canais_disponiveis(forcado: str | None = None, preferido: str | None = None,
                       plataforma: str | None = None, which=shutil.which, existe=os.path.exists) -> list[str]:
    """Lista de canais a tentar, em ordem.

    - `forcado` (padrão: KOMMO_BROWSER) restringe a um só canal; valor inválido -> NavegadorIndisponivel.
    - `preferido` (ex.: o canal que funcionou da última vez, salvo em config) vai para a frente da fila.
    """
    if forcado is None:
        forcado = os.environ.get("KOMMO_BROWSER") or ""
    forcado = forcado.strip().lower()
    if forcado:
        if forcado not in CANAIS_VALIDOS:
            raise NavegadorIndisponivel(
                f"KOMMO_BROWSER='{forcado}' não é válido. Use um destes: {', '.join(CANAIS_VALIDOS)}.")
        return [forcado]
    canais = canais_padrao(plataforma, which, existe)
    preferido = (preferido or "").strip().lower()
    if preferido in canais:
        canais.remove(preferido)
        canais.insert(0, preferido)
    return canais


# ---------------------------------------------------------------------------------------------- mensagens
def mensagem_sem_navegador(erros: list[str], plataforma: str | None = None) -> str:
    so = _plataforma(plataforma)
    if so == "win":
        dica = ("Instale o Google Chrome ou o Microsoft Edge "
                "(ou rode 'python -m playwright install chromium').")
    elif so == "mac":
        dica = ("Instale o Google Chrome ou o Microsoft Edge em /Applications "
                "(ou rode 'python -m playwright install chromium').")
    else:
        dica = ("Instale o google-chrome (pacote google-chrome-stable) ou o chromium, ou rode "
                "'python -m playwright install chromium' (e, se faltarem bibliotecas, "
                "'python -m playwright install-deps chromium').")
    detalhes = " | ".join(erros) if erros else "nenhum navegador tentado"
    return f"Não consegui abrir um navegador. {dica} Detalhes: {detalhes}"


def mensagem_perfil_em_uso(canal: str, perfil: str) -> str:
    return (f"O perfil do app para o navegador '{canal}' parece estar em uso ou travado:\n  {perfil}\n"
            "Feche a janela do navegador aberta pelo app (e outras execuções do app) e tente de novo. "
            "Se o navegador fechou de forma anormal e o problema continuar, use 'Esquecer login' "
            "(será preciso entrar no Kommo de novo).")


# ---------------------------------------------------------------------------------------------- trava do perfil
def arquivos_de_trava(perfil: str) -> list[str]:
    """Arquivos de trava presentes no perfil (lexists: SingletonLock no Linux é um link quebrado de propósito)."""
    return [n for n in ARQUIVOS_TRAVA if os.path.lexists(os.path.join(perfil, n))]


def erro_de_trava(texto: str) -> bool:
    t = (texto or "").lower()
    return any(m.lower() in t for m in TEXTOS_TRAVA)


def erro_sem_executavel(texto: str) -> bool:
    t = (texto or "").lower()
    return any(m in t for m in TEXTOS_SEM_EXECUTAVEL)


def perfil_em_uso(perfil: str, plataforma: str | None = None) -> bool:
    """Verificação ANTES de abrir (melhor esforço; na dúvida devolve False e deixa o launch decidir).

    - Windows: o Chrome mantém `lockfile` aberto sem compartilhar escrita; se não dá para abri-lo para escrita,
      o perfil está em uso. Se abrir, era sobra de um fechamento anormal (não bloqueia).
    - Linux/macOS: `SingletonLock` é um link "host-pid"; se o host é este e o pid está vivo, está em uso.
    """
    so = _plataforma(plataforma)
    if so == "win":
        lock = os.path.join(perfil, "lockfile")
        if not os.path.exists(lock):
            return False
        try:
            fd = os.open(lock, os.O_RDWR)
        except PermissionError:
            return True
        except OSError:
            return False
        os.close(fd)
        return False
    lock = os.path.join(perfil, "SingletonLock")
    try:
        destino = os.readlink(lock)
    except OSError:
        return False
    host, _, pid = destino.rpartition("-")
    if not pid.isdigit() or host != socket.gethostname():
        return False
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


# ---------------------------------------------------------------------------------------------- navegação externa
def url_permitida(url: str, dominio: str = "kommo.com") -> bool:
    """True para páginas em branco/internas e para <dominio> e seus subdomínios (*.kommo.com)."""
    if not url or url.startswith(("about:", "data:", "blob:", "chrome:", "edge:", "devtools:")):
        return True
    host = (urlsplit(url).hostname or "").lower().rstrip(".")
    dominio = dominio.lower().lstrip(".")
    return host == dominio or host.endswith("." + dominio)


def bloquear_navegacao_externa(ctx, dominio: str = "kommo.com", log=lambda *a, **k: None):
    """Fecha abas/popups NOVOS que naveguem para fora de *.<dominio>. Devolve o handler registrado.

    DESLIGADO por padrão em `abrir_contexto` (bloquear_externos=False) porque o Kommo legitimamente abre páginas
    fora de kommo.com: login com Google/Facebook (OAuth), integrações/widgets, pagamento, ajuda e downloads.
    Fechar essas abas quebraria o login do usuário. A aba principal nunca é afetada.
    """
    def _verificar(page) -> None:
        try:
            url = page.url
        except Exception:  # noqa: BLE001 - página já fechada
            return
        if url_permitida(url, dominio):
            return
        log(f"Aba externa fechada pelo app: {urlsplit(url).hostname or url}", "aviso")
        try:
            page.close()
        except Exception:  # noqa: BLE001 - já pode ter fechado sozinha
            pass

    def _nova_pagina(page) -> None:
        # A aba costuma nascer em about:blank e só depois navegar: verifica agora e a cada navegação do frame principal.
        page.on("framenavigated", lambda frame: _verificar(page) if frame == page.main_frame else None)
        _verificar(page)

    ctx.on("page", _nova_pagina)
    return _nova_pagina


# ---------------------------------------------------------------------------------------------- abertura
def abrir_contexto(playwright, perfil: str | None = None, log=lambda *a, **k: None, *,
                   canal_preferido: str | None = None, bloquear_externos: bool = False,
                   info: dict | None = None):
    """Abre um contexto persistente do Chromium e devolve o BrowserContext.

    `perfil` é a PASTA-BASE dos perfis (padrão: paths.profile_dir()); cada canal usa <perfil>/<canal>.
    `canal_preferido` é tentado primeiro (ex.: config['canal_navegador']). Se `info` for um dict, recebe
    info['canal'] e info['perfil'] do navegador que abriu (para a UI lembrar o canal que funcionou).
    """
    base = perfil or paths.profile_dir()
    canais = canais_disponiveis(preferido=canal_preferido)
    erros: list[str] = []
    for canal in canais:
        dir_perfil = os.path.join(base, canal)
        if perfil_em_uso(dir_perfil):
            raise NavegadorIndisponivel(mensagem_perfil_em_uso(canal, dir_perfil))
        try:
            ctx = playwright.chromium.launch_persistent_context(
                dir_perfil,
                channel=None if canal == "chromium" else canal,
                headless=False,
                viewport=None,
                args=list(ARGS_NAVEGADOR),
                chromium_sandbox=True,
                locale="pt-BR",
            )
        except (_ErroPlaywright, OSError) as e:
            texto = str(e)
            primeira = texto.strip().splitlines()[0] if texto.strip() else type(e).__name__
            # Falha por causa do perfil: NÃO tenta outro canal (cada canal tem seu perfil, e o problema é do usuário
            # fechar a janela). Trava + erro que não é "navegador não instalado" também conta como perfil em uso.
            if erro_de_trava(texto) or (arquivos_de_trava(dir_perfil) and not erro_sem_executavel(texto)):
                raise NavegadorIndisponivel(mensagem_perfil_em_uso(canal, dir_perfil) + f"\nDetalhe: {primeira}") from e
            erros.append(f"{canal}: {primeira}")
            log(f"Navegador '{canal}' indisponível: {primeira}", "aviso")
            continue
        log(f"Navegador: {canal}")
        if info is not None:
            info["canal"], info["perfil"] = canal, dir_perfil
        if bloquear_externos:
            bloquear_navegacao_externa(ctx, log=log)
        return ctx
    raise NavegadorIndisponivel(mensagem_sem_navegador(erros))
