"""Procura dados pessoais/da empresa no projeto e nos artefatos de build ANTES de publicar.

Uso:
    python scripts/verificar_privacidade.py                      # projeto inteiro (inclui dist/)
    python scripts/verificar_privacidade.py --termo minhaempresa # termo extra (repetível)
    python scripts/verificar_privacidade.py --somente-dist --dist dist/windows   # só o resultado do build
    python scripts/verificar_privacidade.py --json               # saída para máquina/CI

O que é varrido (recursivamente, sem pular nada além de .git/.venv/venv/.tox — ver PASTAS_IGNORADAS):
- todo arquivo, de qualquer extensão, como BYTES (texto, .pyc, .png, .log, .dll ...), em UTF-8 e UTF-16LE;
- .zip / .whl / .tar(.gz/.bz2/.xz) / .gz: cada membro é aberto e varrido, recursivamente (zip dentro de zip);
- executáveis do PyInstaller (.exe do Windows, ELF do Linux), onefile ou onedir: o pacote CArchive é lido
  (parser próprio, sem precisar do PyInstaller instalado) e cada item é descomprimido; o PYZ (módulos .pyc
  comprimidos) também;
- AppImage (ELF + squashfs): extrai com `unsquashfs` se existir; se não existir, é ERRO (não dá para olhar dentro).

FAIL-CLOSED: qualquer coisa que não consiga abrir/ler/descomprimir vira ERRO e o código de saída é 1. Nunca
"AVISO e segue".

Termos padrão (dados da máquina de quem roda): usuário do SO, nome do computador, %USERPROFILE% (caminho
completo e forma curta 8.3, ex. FULANO~1), nome da pasta home, `git config user.name`/`user.email` (se o git
existir), mais KOMMO_TERMOS_SENSIVEIS (vírgulas) e --termo. Termos com menos de 4 caracteres são descartados
(gerariam falso positivo em qualquer binário); termos com menos de 6 caracteres só casam com limite de palavra.

Termo da CONFIGURAÇÃO do app (sempre, inclusive com --sem-termos-padrao; desligue com --sem-config): o campo
"empresa" (subdomínio) de `config.json` na raiz de dados — `<raiz>/data/config.json` e, se a variável
KOMMO_DATA_DIR estiver definida, `<KOMMO_DATA_DIR>/config.json` (caminho relativo = relativo à raiz do projeto, como
no app). Só é lido quando o arquivo existe; JSON inválido ou sem "empresa" é ignorado (não é erro). Como os demais,
o termo nunca é impresso em claro (origem "config.json").

Por padrão os termos NÃO são impressos em claro (log de CI): aparecem mascarados, ex. "ful***#3fa9c1"
(3 primeiros caracteres + hash curto). Use --mostrar-termos para ver em claro (só no seu terminal).

Códigos de saída: 0 = limpo; 1 = achados OU erro de leitura OU uso inválido.

O módulo é importável (funções puras) — ver tests/test_verificador.py.
"""
from __future__ import annotations

import argparse
import bz2
import fnmatch
import getpass
import gzip
import hashlib
import io
import json
import lzma
import marshal
import os
import platform
import shutil
import struct
import subprocess
import sys
import tarfile
import tempfile
import zipfile
import zlib
from dataclasses import asdict, dataclass, field
from pathlib import Path

RAIZ_PADRAO = Path(__file__).resolve().parent.parent
NOME_APP = "KommoUnirDuplicatas"

# Pastas nunca varridas. Justificativa: .git (metadados do VCS, não vão no zip/exe), .venv/venv/.tox
# (dependências de terceiros instaladas localmente; o pyvenv.cfg SEMPRE contém o caminho da home de quem criou,
# então seria falso positivo permanente). Nenhuma delas é publicada: .gitignore e os scripts de build as excluem.
# ATENÇÃO: __pycache__, .pytest_cache, build/, dist/ NÃO são ignoradas de propósito (o zip publicado à mão já
# vazou caminhos C:\Users\<usuario>\... via .pyc).
PASTAS_IGNORADAS = {".git", ".venv", "venv", ".tox"}

TAMANHO_MINIMO_TERMO = 4      # abaixo disso: descartado (casaria em qualquer lugar)
TAMANHO_TERMO_CURTO = 6       # abaixo disso: exige limite de palavra (não pode estar colado a letra/dígito)
PROFUNDIDADE_MAXIMA = 8       # zip dentro de zip dentro de ... (proteção contra bomba de compressão)
TAMANHO_MAXIMO_MEMBRO = 1 << 31   # 2 GiB descomprimido por membro: acima disso é ERRO (fail-closed)

# Binários de TERCEIROS conhecidos e grandes, embutidos no build sem modificação. Neles NÃO procuramos o termo
# solto (tabelas de texto/ICU/dicionários contêm praticamente qualquer palavra de 4+ letras → falso positivo),
# mas continuamos procurando o termo em FORMATO DE CAMINHO ("Users\<termo>", "Users/<termo>", "home/<termo>"),
# que é o que indicaria vazamento da máquina de build. Os demais arquivos (o nosso código, .pyc, PYZ, dados)
# são varridos por completo.
BINARIOS_TERCEIROS = (
    "node.exe", "node",                       # runtime Node.js do driver do Playwright (~80 MB, dados ICU)
    "python3*.dll", "libpython3*.so*", "python3*.so*",   # interpretador Python
    "vcruntime*.dll", "msvcp*.dll", "ucrtbase.dll", "api-ms-win-*.dll", "concrt*.dll",  # runtime do MSVC
    "libcrypto*", "libssl*", "libffi*", "sqlite3.dll", "libsqlite3*",   # OpenSSL/libffi/sqlite do Python
    "tcl86*.dll", "tk86*.dll", "libtcl*", "libtk*",     # Tcl/Tk do tkinter
    "zlib*.dll", "liblzma*", "libbz2*", "libexpat*", "libz.so*",
)
PREFIXOS_CAMINHO = ("users\\", "users/", "users\\\\", "home/", "documents and settings\\")

# Nomes de dados do usuário que NUNCA podem estar no projeto nem ao lado do executável.
PASTAS_DADOS = {"data", "profile", ".perfil", "debug", "logs"}
ARQUIVOS_DADOS = {"config.json", "log.txt"}
# Artefatos de distribuição que só podem existir dentro de dist/ (fora disso → publicaria sem querer).
SUFIXOS_ARTEFATO = (".zip", ".exe", ".appimage", ".tar.gz", ".tgz")

MAGIC_CARCHIVE = b"MEI\014\013\012\013\016"
FORMATO_COOKIE = "!8sIIII64s"
FORMATO_TOC = "!IIIIBc"


# ============================================================================================ estruturas
@dataclass(frozen=True)
class Termo:
    valor: str
    origem: str

    @property
    def curto(self) -> bool:
        return len(self.valor) < TAMANHO_TERMO_CURTO

    def mascarado(self) -> str:
        h = hashlib.sha256(self.valor.lower().encode("utf-8")).hexdigest()[:6]
        return f"{self.valor[:3]}***#{h}"


@dataclass
class Achado:
    tipo: str        # "termo" | "dados_usuario" | "artefato_fora_de_dist"
    local: str       # caminho relativo; membros aninhados como "a.zip!/b/c.pyc"
    detalhe: str
    termo: str = ""  # já mascarado (ou em claro com --mostrar-termos)


@dataclass
class Resultado:
    termos: list[Termo] = field(default_factory=list)
    descartados: int = 0
    achados: list[Achado] = field(default_factory=list)
    erros: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    arquivos: int = 0

    @property
    def ok(self) -> bool:
        return not self.achados and not self.erros


class ErroLeitura(Exception):
    """Algo não pôde ser aberto/lido/descomprimido. Vira ERRO (fail-closed)."""


# ============================================================================================ termos
def _executar(cmd: list[str]) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10,
                           encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError):
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


def caminho_curto_windows(caminho: str) -> str:
    """Forma 8.3 (ex. C:\\Users\\FULANO~1) via GetShortPathNameW. '' fora do Windows ou se não existir."""
    if os.name != "nt" or not caminho:
        return ""
    try:
        import ctypes
        from ctypes import wintypes
        f = ctypes.windll.kernel32.GetShortPathNameW
        f.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
        f.restype = wintypes.DWORD
        buf = ctypes.create_unicode_buffer(1024)
        n = f(caminho, buf, 1024)
        return buf.value if 0 < n < 1024 else ""
    except (OSError, AttributeError):
        return ""


def termos_do_sistema(env: dict | None = None, raiz: Path | None = None) -> list[Termo]:
    """Termos que identificam quem está rodando (não falha se algo não existir)."""
    env = os.environ if env is None else env
    t: list[Termo] = []

    def add(valor, origem):
        if valor:
            t.append(Termo(str(valor).strip(), origem))

    try:
        add(getpass.getuser(), "usuario")
    except Exception:  # noqa: BLE001 - getuser pode falhar sem variáveis de ambiente
        pass
    add(platform.node(), "hostname")
    perfil = env.get("USERPROFILE") or env.get("HOME") or ""
    add(perfil, "userprofile")
    curto = caminho_curto_windows(perfil)
    if curto and curto.lower() != perfil.lower():
        add(curto, "userprofile_8.3")
        add(Path(curto).name, "userprofile_8.3_nome")
    try:
        add(Path.home().name, "home")
    except RuntimeError:
        pass
    if shutil.which("git"):
        # identidade global E a do repositório da raiz (pode ser diferente); nunca depende do cwd de quem chama
        for escopo in (["git", "config", "--global"], ["git", "-C", str(raiz or RAIZ_PADRAO), "config"]):
            add(_executar(escopo + ["--get", "user.name"]), "git_nome")
            email = _executar(escopo + ["--get", "user.email"])
            add(email, "git_email")
            if "@" in email:
                add(email.split("@", 1)[0], "git_email_local")
    return t


def normalizar_termos(termos: list[Termo]) -> tuple[list[Termo], int]:
    """Remove vazios/duplicados (sem diferenciar maiúsculas) e descarta os curtos demais."""
    vistos: dict[str, Termo] = {}
    descartados = 0
    for termo in termos:
        v = termo.valor.strip()
        if not v:
            continue
        if len(v) < TAMANHO_MINIMO_TERMO:
            descartados += 1
            continue
        vistos.setdefault(v.lower(), Termo(v, termo.origem))
    return sorted(vistos.values(), key=lambda x: (-len(x.valor), x.valor.lower())), descartados


def _empresa_normalizada(valor) -> str:
    """'MinhaEmpresa.kommo.com' / 'https://minhaempresa.kommo.com/' -> 'minhaempresa' ('' se vazio/inválido)."""
    v = str(valor or "").strip().lower()
    for prefixo in ("https://", "http://"):
        if v.startswith(prefixo):
            v = v[len(prefixo):]
    v = v.split("/", 1)[0]
    if v.endswith(".kommo.com"):
        v = v[: -len(".kommo.com")]
    return v.strip(".")


def arquivos_config(raiz: Path | None = None, env: dict | None = None) -> list[Path]:
    """Onde o app guarda o config.json: <raiz>/data e, se definido, KOMMO_DATA_DIR (relativo à raiz)."""
    env = os.environ if env is None else env
    raiz = Path(raiz or RAIZ_PADRAO)
    caminhos = [raiz / "data" / "config.json"]
    override = str(env.get("KOMMO_DATA_DIR") or "").strip().strip('"')
    if override:
        pasta = Path(os.path.expandvars(os.path.expanduser(override)))
        if not pasta.is_absolute():
            pasta = raiz / pasta
        caminhos.append(pasta / "config.json")
    vistos, out = set(), []
    for c in caminhos:
        chave = os.path.normcase(os.path.abspath(c))
        if chave not in vistos:
            vistos.add(chave)
            out.append(c)
    return out


def termos_da_config(raiz: Path | None = None, env: dict | None = None) -> list[Termo]:
    """Subdomínio ("empresa") dos config.json do app que EXISTIREM (ver docstring do módulo)."""
    t: list[Termo] = []
    for caminho in arquivos_config(raiz, env):
        try:
            if not caminho.is_file():
                continue
            dados = json.loads(caminho.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        empresa = _empresa_normalizada(dados.get("empresa")) if isinstance(dados, dict) else ""
        if empresa:
            t.append(Termo(empresa, "config.json"))
    return t


def coletar_termos(extras=(), env: dict | None = None, incluir_sistema: bool = True,
                   raiz: Path | None = None, incluir_config: bool = True) -> tuple[list[Termo], int]:
    env = os.environ if env is None else env
    t = termos_do_sistema(env, raiz) if incluir_sistema else []
    if incluir_config:
        t += termos_da_config(raiz, env)
    t += [Termo(x, "KOMMO_TERMOS_SENSIVEIS") for x in env.get("KOMMO_TERMOS_SENSIVEIS", "").split(",")]
    t += [Termo(x, "argumento") for x in extras]
    return normalizar_termos(t)


# ============================================================================================ busca em bytes
def _variantes(valor: str, enc: str) -> set[bytes]:
    out = set()
    for v in {valor, valor.lower(), valor.upper(), valor.casefold()}:
        try:
            out.add(v.encode(enc).lower())   # bytes.lower só mexe em ASCII: ok para os dois encodings
        except UnicodeEncodeError:
            pass
    return out


def _alnum_antes(baixo: bytes, pos: int, unidade: int) -> bool:
    if pos < unidade:
        return False
    c = baixo[pos - unidade:pos]
    return (c[:1].isalnum() and (unidade == 1 or c[1:] == b"\x00"))


def _alnum_depois(baixo: bytes, fim: int, unidade: int) -> bool:
    c = baixo[fim:fim + unidade]
    return len(c) == unidade and c[:1].isalnum() and (unidade == 1 or c[1:] == b"\x00")


def _precedido_por_caminho(baixo: bytes, pos: int, enc: str) -> bool:
    for p in PREFIXOS_CAMINHO:
        pb = p.encode(enc)
        if baixo[max(0, pos - len(pb)):pos] == pb:
            return True
    return False


def procurar_termos(dados: bytes, termos: list[Termo], somente_caminho: bool = False) -> dict[Termo, int]:
    """Conta ocorrências de cada termo em `dados` (UTF-8 e UTF-16LE, sem diferenciar maiúsculas em ASCII).

    - termo curto (< 6): só conta se não estiver colado a letra/dígito (limite de palavra);
    - somente_caminho=True (binários de terceiros): só conta se vier logo após "Users\\", "home/" etc.
    """
    if not dados or not termos:
        return {}
    baixo = dados.lower()
    achou: dict[Termo, int] = {}
    for termo in termos:
        n = 0
        for enc, unidade in (("utf-8", 1), ("utf-16-le", 2)):
            for agulha in _variantes(termo.valor, enc):
                ini = baixo.find(agulha)
                while ini != -1:
                    fim = ini + len(agulha)
                    valido = True
                    if termo.curto and (_alnum_antes(baixo, ini, unidade) or _alnum_depois(baixo, fim, unidade)):
                        valido = False
                    if valido and somente_caminho and not _precedido_por_caminho(baixo, ini, enc):
                        valido = False
                    if valido:
                        n += 1
                    ini = baixo.find(agulha, ini + 1)
        if n:
            achou[termo] = n
    return achou


def eh_binario_terceiro(nome: str) -> bool:
    base = nome.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return any(fnmatch.fnmatch(base, p) for p in BINARIOS_TERCEIROS)


def nomes_com_termo(texto: str, termos: list[Termo]) -> list[Termo]:
    """Termos que aparecem em um NOME (caminho de arquivo/membro)."""
    return list(procurar_termos(texto.encode("utf-8"), termos).keys())


# ============================================================================================ formatos
def _parse_carchive(dados: bytes) -> list[tuple[str, bytes]] | None:
    """Lê o CArchive (PKG) do PyInstaller embutido no fim de um executável. None se não houver cookie.

    Formato (PyInstaller 6.x, PyInstaller/archive/readers.py): cookie '!8sIIII64s' no fim; TOC de entradas
    '!IIIIBc' + nome com padding. Cada item pode estar comprimido com zlib. Erro de formato → ErroLeitura.
    """
    pos = dados.rfind(MAGIC_CARCHIVE)
    if pos == -1:
        return None
    try:
        tam_cookie = struct.calcsize(FORMATO_COOKIE)
        _m, tam_pkg, toc_off, toc_len, _pyver, pylib = struct.unpack(
            FORMATO_COOKIE, dados[pos:pos + tam_cookie])
        if not pylib.strip(b"\0"):
            raise ErroLeitura("cookie do PyInstaller sem nome da biblioteca Python")
        fim = pos + tam_cookie
        inicio = fim - tam_pkg
        if inicio < 0 or toc_off + toc_len > tam_pkg:
            raise ErroLeitura("cookie do PyInstaller com tamanhos inválidos (arquivo truncado?)")
        toc = dados[inicio + toc_off:inicio + toc_off + toc_len]
        tam_ent = struct.calcsize(FORMATO_TOC)
        itens = []
        cur = 0
        while cur < len(toc):
            ent_len, off, dlen, _ulen, comp, tipo = struct.unpack(FORMATO_TOC, toc[cur:cur + tam_ent])
            if ent_len < tam_ent:
                raise ErroLeitura("TOC do PyInstaller corrompida")
            nome = toc[cur + tam_ent:cur + ent_len].rstrip(b"\0").decode("utf-8")
            cur += ent_len
            if tipo == b"o":          # opção de runtime: não tem dados
                continue
            bloco = dados[inicio + off:inicio + off + dlen]
            if len(bloco) != dlen:
                raise ErroLeitura(f"item '{nome}' do PyInstaller truncado")
            if comp:
                bloco = zlib.decompress(bloco)
            itens.append((nome, bloco))
        return itens
    except ErroLeitura:
        raise
    except (struct.error, zlib.error, UnicodeDecodeError, ValueError) as e:
        raise ErroLeitura(f"pacote PyInstaller ilegível: {type(e).__name__}: {e}") from e


def _parse_pyz(dados: bytes) -> list[tuple[str, bytes]]:
    """PYZ do PyInstaller: 'PYZ\\0' + magic do Python (4) + offset da TOC; TOC marshal {nome: (tipo, off, len)};
    cada módulo é zlib(marshal(code)). Devolvemos os bytes descomprimidos (contêm co_filename e constantes)."""
    try:
        if dados[:4] != b"PYZ\0":
            raise ErroLeitura("PYZ sem assinatura")
        (toc_off,) = struct.unpack("!i", dados[8:12])
        toc = dict(marshal.loads(dados[toc_off:]))
        out = []
        for nome, (tipo, off, tam) in toc.items():
            if tipo == 3:     # pacote namespace (PEP 420): sem dados
                continue
            out.append((nome, zlib.decompress(dados[off:off + tam])))
        return out
    except ErroLeitura:
        raise
    except (struct.error, zlib.error, ValueError, EOFError, TypeError) as e:
        raise ErroLeitura(f"PYZ ilegível: {type(e).__name__}: {e}") from e


def _offset_squashfs_appimage(dados: bytes) -> int:
    """No AppImage tipo 2 o squashfs começa logo após o fim do ELF (e_shoff + e_shentsize * e_shnum)."""
    classe = dados[4]
    ordem = "<" if dados[5] == 1 else ">"
    if classe == 2:
        shoff = struct.unpack(ordem + "Q", dados[0x28:0x30])[0]
        shentsize, shnum = struct.unpack(ordem + "HH", dados[0x3A:0x3E])
    else:
        shoff = struct.unpack(ordem + "I", dados[0x20:0x24])[0]
        shentsize, shnum = struct.unpack(ordem + "HH", dados[0x2E:0x32])
    return shoff + shentsize * shnum


# ============================================================================================ varredura
class Varredor:
    def __init__(self, termos: list[Termo], mostrar_termos: bool = False):
        self.termos = termos
        self.mostrar = mostrar_termos
        self.res = Resultado(termos=termos)

    # ---- registro
    def _rot(self, t: Termo) -> str:
        return t.valor if self.mostrar else t.mascarado()

    def termo_em(self, local: str, dados: bytes, nome: str) -> None:
        so_caminho = eh_binario_terceiro(nome)
        for t, n in procurar_termos(dados, self.termos, somente_caminho=so_caminho).items():
            extra = " (binário de terceiro: só ocorrência em formato de caminho)" if so_caminho else ""
            self.res.achados.append(Achado("termo", local, f"{n} ocorrência(s) no conteúdo{extra}", self._rot(t)))

    def nome_com_termo(self, nome: str, local: str | None = None) -> None:
        local = local or nome
        for t in nomes_com_termo(nome, self.termos):
            self.res.achados.append(Achado("termo", local, "termo no NOME do arquivo/caminho", self._rot(t)))

    def erro(self, local: str, msg: str) -> None:
        self.res.erros.append(f"{local}: {msg}")

    # ---- dados de um arquivo (ou membro), com recursão por formato
    def varrer_dados(self, dados: bytes, local: str, nome: str, prof: int = 0) -> None:
        self.res.arquivos += 1
        if prof > PROFUNDIDADE_MAXIMA:
            self.erro(local, f"aninhamento acima de {PROFUNDIDADE_MAXIMA} níveis (não inspecionado)")
            return
        try:
            self._despachar(dados, local, nome, prof)
        except ErroLeitura as e:
            self.erro(local, str(e))

    def _despachar(self, dados: bytes, local: str, nome: str, prof: int) -> None:
        cab = dados[:16]
        baixo = nome.lower()
        if cab[:4] in (b"PK\x03\x04", b"PK\x05\x06") or (baixo.endswith((".zip", ".whl")) and dados):
            self._zip(dados, local, prof)
            return
        if cab[:2] == b"\x1f\x8b" or cab[:3] == b"BZh" or cab[:6] == b"\xfd7zXZ\x00":
            self._comprimido(dados, local, nome, prof)
            return
        if len(dados) > 262 and dados[257:262] == b"ustar":
            self._tar(dados, local, prof)
            return
        if cab[:6] == b"7z\xbc\xaf\x27\x1c" or cab[:4] in (b"Rar!", b"MSCF") or cab[:4] == b"hsqs":
            raise ErroLeitura("formato compactado não suportado (7z/rar/cab/squashfs): não dá para inspecionar")
        if cab[:4] == b"\x7fELF" and dados[8:11] == b"AI\x02":
            self._appimage(dados, local, prof)
            return
        # conteúdo bruto (texto, .pyc, imagens, DLLs, executáveis...)
        self.termo_em(local, dados, nome)
        if cab[:2] == b"MZ" or cab[:4] == b"\x7fELF" or cab[:4] in (b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe"):
            itens = _parse_carchive(dados)
            if itens is not None:
                for sub, bloco in itens:
                    sublocal = f"{local}!/{sub}"
                    if bloco[:4] == b"PYZ\0":
                        self.res.arquivos += 1
                        for mod, cod in _parse_pyz(bloco):
                            self.res.arquivos += 1
                            self.termo_em(f"{sublocal}!/{mod}", cod, mod)
                    else:
                        self.varrer_dados(bloco, sublocal, sub, prof + 1)
            elif baixo.replace("\\", "/").rsplit("/", 1)[-1] in (NOME_APP.lower() + ".exe", NOME_APP.lower()):
                # o NOSSO executável tem de ter o pacote PyInstaller; se não reconheço, não sei o que há dentro
                raise ErroLeitura("executável do app sem pacote PyInstaller reconhecível (corrompido?)")
        elif cab[:4] == b"PYZ\0":
            for mod, cod in _parse_pyz(dados):
                self.termo_em(f"{local}!/{mod}", cod, mod)

    def _zip(self, dados: bytes, local: str, prof: int) -> None:
        try:
            with zipfile.ZipFile(io.BytesIO(dados)) as z:
                for info in z.infolist():
                    sub = f"{local}!/{info.filename}"
                    self.nome_com_termo(info.filename, sub)
                    self._dados_em_arquivo_compactado(info.filename, sub)
                    if info.is_dir():
                        continue
                    if info.flag_bits & 0x1:
                        self.erro(sub, "membro criptografado (não dá para inspecionar)")
                        continue
                    if info.file_size > TAMANHO_MAXIMO_MEMBRO:
                        self.erro(sub, "membro grande demais para inspecionar")
                        continue
                    try:
                        conteudo = z.read(info)
                    except (zipfile.BadZipFile, zlib.error, RuntimeError, NotImplementedError, EOFError,
                            OSError) as e:
                        self.erro(sub, f"membro ilegível: {type(e).__name__}: {e}")
                        continue
                    self.varrer_dados(conteudo, sub, info.filename, prof + 1)
        except (zipfile.BadZipFile, zipfile.LargeZipFile, OSError, EOFError, ValueError) as e:
            raise ErroLeitura(f"zip ilegível/corrompido: {type(e).__name__}: {e}") from e

    def _comprimido(self, dados: bytes, local: str, nome: str, prof: int) -> None:
        try:
            if dados[:2] == b"\x1f\x8b":
                bruto = gzip.decompress(dados)
            elif dados[:3] == b"BZh":
                bruto = bz2.decompress(dados)
            else:
                bruto = lzma.decompress(dados)
        except (OSError, EOFError, lzma.LZMAError, ValueError) as e:
            raise ErroLeitura(f"arquivo comprimido ilegível: {type(e).__name__}: {e}") from e
        interno = nome[:-3] if nome.lower().endswith(".gz") else nome
        if nome.lower().endswith(".tgz"):
            interno = nome[:-4] + ".tar"
        self.varrer_dados(bruto, f"{local}!/", interno, prof + 1)

    def _tar(self, dados: bytes, local: str, prof: int) -> None:
        try:
            with tarfile.open(fileobj=io.BytesIO(dados), mode="r:") as tar:
                for m in tar.getmembers():
                    sub = f"{local}!/{m.name}"
                    self.nome_com_termo(m.name, sub)
                    self._dados_em_arquivo_compactado(m.name, sub)
                    if not m.isfile():
                        continue
                    f = tar.extractfile(m)
                    if f is None:
                        self.erro(sub, "membro do tar ilegível")
                        continue
                    self.varrer_dados(f.read(), sub, m.name, prof + 1)
        except (tarfile.TarError, OSError, EOFError) as e:
            raise ErroLeitura(f"tar ilegível/corrompido: {type(e).__name__}: {e}") from e

    def _appimage(self, dados: bytes, local: str, prof: int) -> None:
        # o runtime ELF em si é varrido como bytes; o squashfs é comprimido → precisa extrair
        self.termo_em(local, dados, local)
        unsq = shutil.which("unsquashfs")
        if not unsq:
            raise ErroLeitura("AppImage: 'unsquashfs' (squashfs-tools) não encontrado — instale para inspecionar "
                              "o conteúdo, ou verifique o AppDir/onedir usado para gerá-lo")
        try:
            off = _offset_squashfs_appimage(dados)
        except (struct.error, IndexError) as e:
            raise ErroLeitura(f"AppImage com cabeçalho ELF inválido: {e}") from e
        if dados[off:off + 4] != b"hsqs":
            raise ErroLeitura("AppImage sem squashfs no offset esperado")
        with tempfile.TemporaryDirectory(prefix="verif-appimage-") as tmp:
            arq = os.path.join(tmp, "img")
            with open(arq, "wb") as f:
                f.write(dados)
            destino = os.path.join(tmp, "raiz")
            r = subprocess.run([unsq, "-q", "-n", "-o", str(off), "-d", destino, arq],
                               capture_output=True, text=True)
            if r.returncode != 0:
                raise ErroLeitura(f"unsquashfs falhou (código {r.returncode}): {r.stderr.strip()[:200]}")
            self.varrer_pasta(Path(destino), f"{local}!", prof + 1)

    # ---- disco
    def _dados_em_arquivo_compactado(self, nome_membro: str, local: str) -> None:
        """Dentro de zip/tar: data/, profile/, config.json... no topo ou logo abaixo da pasta do app."""
        partes = [p for p in nome_membro.replace("\\", "/").split("/") if p]
        for i, p in enumerate(partes):
            if i > 1:
                break
            ultimo = i == len(partes) - 1
            if (not ultimo or nome_membro.endswith("/")) and p.lower() in PASTAS_DADOS:
                self.res.achados.append(Achado("dados_usuario", local, f"pasta de dados do usuário '{p}/' empacotada"))
                return
            if ultimo and p.lower() in ARQUIVOS_DADOS:
                self.res.achados.append(Achado("dados_usuario", local, f"arquivo de dados do usuário '{p}' empacotado"))
                return
        if partes and partes[-1].lower().endswith(".log"):
            self.res.achados.append(Achado("dados_usuario", local, "arquivo de log empacotado"))

    def varrer_pasta(self, pasta: Path, prefixo: str, prof: int = 0, base: Path | None = None) -> None:
        base = base or pasta

        def onerror(e: OSError):
            self.erro(f"{prefixo}/{e.filename}", f"pasta ilegível: {e.strerror or e}")

        for atual, dirs, arquivos in os.walk(pasta, onerror=onerror, followlinks=False):
            dirs[:] = sorted(d for d in dirs if d not in PASTAS_IGNORADAS)
            for d in list(dirs):
                c = Path(atual, d)
                if c.is_symlink():
                    self.res.avisos.append(f"{_rel(c, base, prefixo)}: link simbólico não seguido")
            for nome in sorted(arquivos):
                c = Path(atual, nome)
                rel = _rel(c, base, prefixo)
                self.nome_com_termo(rel)
                if c.is_symlink():
                    self.res.avisos.append(f"{rel}: link simbólico não seguido")
                    continue
                try:
                    dados = ler_arquivo(c)
                except OSError as e:
                    self.erro(rel, f"arquivo ilegível: {type(e).__name__}: {e.strerror or e}")
                    continue
                self.varrer_dados(dados, rel, nome, prof)


def ler_arquivo(caminho: Path) -> bytes:
    """Ponto único de leitura (os testes substituem para simular arquivo ilegível)."""
    with open(caminho, "rb") as f:
        return f.read()


def _rel(c: Path, base: Path, prefixo: str) -> str:
    try:
        r = c.relative_to(base).as_posix()
    except ValueError:
        r = c.name
    return f"{prefixo}/{r}" if prefixo else r


# ============================================================================================ regras do projeto
def dados_usuario_no_projeto(raiz: Path, dist: Path) -> list[Achado]:
    """Pastas/arquivos de dados do usuário na raiz do projeto ou ao lado do executável dentro de dist/, e
    artefatos (.zip/.exe/.AppImage/.tar.gz) fora de dist/."""
    achados: list[Achado] = []

    def checar_pasta_app(pasta: Path, rot: str):
        for nome in sorted(os.listdir(pasta)):
            c = pasta / nome
            n = nome.lower()
            if c.is_dir() and n in PASTAS_DADOS:
                achados.append(Achado("dados_usuario", f"{rot}{nome}/", "pasta de dados do usuário — não publique"))
            elif c.is_file() and (n in ARQUIVOS_DADOS or n.endswith(".log")):
                achados.append(Achado("dados_usuario", f"{rot}{nome}", "arquivo de dados do usuário — não publique"))

    if raiz.is_dir():
        checar_pasta_app(raiz, "")
    if dist.is_dir():
        # qualquer pasta que contenha o executável do app = "pasta do programa" (modo portátil grava data/ ali)
        for atual, dirs, arquivos in os.walk(dist):
            dirs[:] = [d for d in dirs if d.lower() not in PASTAS_DADOS and d != "_internal"]
            if any(a.lower() in (NOME_APP.lower(), NOME_APP.lower() + ".exe") for a in arquivos):
                rot = _rel(Path(atual), raiz, "") + "/" if Path(atual) != raiz else ""
                checar_pasta_app(Path(atual), rot if rot != "./" else "")
    # logs em qualquer lugar do projeto (podem conter subdomínio/nome de clientes)
    for atual, dirs, arquivos in os.walk(raiz):
        dirs[:] = [d for d in dirs if d not in PASTAS_IGNORADAS]
        for a in arquivos:
            if a.lower().endswith(".log"):
                rel = _rel(Path(atual, a), raiz, "")
                if not any(x.local == rel for x in achados):
                    achados.append(Achado("dados_usuario", rel, "arquivo de log — não publique"))
    # artefatos fora de dist/
    dist_res = dist.resolve()
    for atual, dirs, arquivos in os.walk(raiz):
        dirs[:] = [d for d in dirs if d not in PASTAS_IGNORADAS and Path(atual, d).resolve() != dist_res]
        for a in arquivos:
            if a.lower().endswith(SUFIXOS_ARTEFATO):
                achados.append(Achado("artefato_fora_de_dist", _rel(Path(atual, a), raiz, ""),
                                      "artefato de distribuição fora de dist/ — remova ou mova (pode conter "
                                      "código compilado com caminhos da sua máquina)"))
    return achados


def verificar(raiz: Path, dist: Path | None = None, termos: list[Termo] | None = None,
              somente_dist: bool = False, mostrar_termos: bool = False, descartados: int = 0) -> Resultado:
    """Função principal (pura em relação ao ambiente: recebe os termos já coletados)."""
    raiz = Path(raiz).resolve()
    dist = Path(dist).resolve() if dist else raiz / "dist"
    v = Varredor(termos or [], mostrar_termos)
    v.res.descartados = descartados
    if not v.termos:
        v.res.erros.append("nenhum termo sensível para procurar (fail-closed)")
        return v.res
    if somente_dist:
        if not dist.exists():
            v.res.erros.append(f"pasta/arquivo de build não existe: {dist.name} (nada para verificar)")
            return v.res
        if dist.is_file():
            try:
                v.varrer_dados(ler_arquivo(dist), dist.name, dist.name)
            except OSError as e:
                v.erro(dist.name, f"arquivo ilegível: {e.strerror or e}")
        else:
            v.varrer_pasta(dist, dist.name)
        if dist.is_dir():
            for atual, dirs, arquivos in os.walk(dist):
                dirs[:] = [d for d in dirs if d != "_internal"]
                if any(a.lower() in (NOME_APP.lower(), NOME_APP.lower() + ".exe") for a in arquivos):
                    for nome in os.listdir(atual):
                        n = nome.lower()
                        if n in PASTAS_DADOS or n in ARQUIVOS_DADOS:
                            v.res.achados.append(Achado("dados_usuario", _rel(Path(atual, nome), dist, dist.name),
                                                        "dados do usuário ao lado do executável — não publique"))
        return v.res
    if not raiz.is_dir():
        v.res.erros.append("raiz do projeto não existe")
        return v.res
    v.varrer_pasta(raiz, "")
    if dist.exists() and raiz not in dist.parents and dist != raiz:
        v.varrer_pasta(dist, dist.name) if dist.is_dir() else v.varrer_dados(ler_arquivo(dist), dist.name, dist.name)
    v.res.achados += dados_usuario_no_projeto(raiz, dist)
    return v.res


# ============================================================================================ saída
def mascarar_texto(texto: str, termos: list[Termo]) -> str:
    """Troca qualquer termo (sem diferenciar maiúsculas) pela forma mascarada — usado em toda a saída."""
    import re
    for t in termos:
        texto = re.sub(re.escape(t.valor), t.mascarado(), texto, flags=re.I)
    return texto


def formatar_texto(res: Resultado, mostrar: bool = False) -> str:
    linhas = []
    if mostrar:
        desc = ", ".join(f"{t.valor} [{t.origem}]" for t in res.termos)
    else:
        desc = ", ".join(f"{t.mascarado()} [{t.origem}]" for t in res.termos)
    linhas.append(f"Termos verificados: {len(res.termos)} ({desc})")
    if res.descartados:
        linhas.append(f"Termos descartados por serem curtos demais (< {TAMANHO_MINIMO_TERMO}): {res.descartados}")
    linhas.append(f"Itens inspecionados (arquivos + membros): {res.arquivos}")
    for a in res.avisos:
        linhas.append(f"AVISO: {a}")
    if res.erros:
        linhas.append("")
        linhas.append(f"ERRO — {len(res.erros)} item(ns) não puderam ser inspecionados (fail-closed):")
        linhas += [f"  - {e}" for e in res.erros]
    if res.achados:
        linhas.append("")
        linhas.append(f"ENCONTRADO — {len(res.achados)} achado(s); não publique antes de resolver:")
        for a in res.achados:
            t = f" termo={a.termo}" if a.termo else ""
            linhas.append(f"  - [{a.tipo}] {a.local}: {a.detalhe}{t}")
        if any("__pycache__" in a.local for a in res.achados):
            linhas.append("  Dica: .pyc guardam o caminho absoluto da sua máquina. Apague as pastas __pycache__ "
                          "antes de zipar o projeto à mão (o git já as ignora).")
    if res.ok:
        linhas.append("OK: nenhum dado pessoal/da empresa encontrado e nada ficou sem inspecionar.")
    texto = "\n".join(linhas)
    return texto if mostrar else mascarar_texto(texto, res.termos)


def formatar_json(res: Resultado, mostrar: bool = False) -> str:
    d = {
        "ok": res.ok,
        "termos": [{"termo": t.valor if mostrar else t.mascarado(), "origem": t.origem} for t in res.termos],
        "descartados": res.descartados,
        "itens_inspecionados": res.arquivos,
        "achados": [asdict(a) for a in res.achados],
        "erros": res.erros,
        "avisos": res.avisos,
    }
    texto = json.dumps(d, ensure_ascii=False, indent=2)
    return texto if mostrar else mascarar_texto(texto, res.termos)


# ============================================================================================ CLI
def criar_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Procura dados pessoais no projeto e nos artefatos de build.")
    p.add_argument("termos_posicionais", nargs="*", metavar="TERMO", help="termos extras (compatibilidade)")
    p.add_argument("--termo", action="append", default=[], help="termo sensível extra (repetível)")
    p.add_argument("--raiz", type=Path, default=RAIZ_PADRAO, help="raiz do projeto (padrão: a deste script)")
    p.add_argument("--dist", type=Path, default=None, help="pasta (ou arquivo) de build (padrão: <raiz>/dist)")
    p.add_argument("--somente-dist", action="store_true", help="varre só --dist (usado pelos scripts de build)")
    p.add_argument("--json", action="store_true", help="saída JSON")
    p.add_argument("--mostrar-termos", action="store_true", help="mostra os termos em claro (não use em CI)")
    p.add_argument("--sem-termos-padrao", action="store_true",
                   help="não usa usuário/hostname/git (só --termo e KOMMO_TERMOS_SENSIVEIS; para testes/CI)")
    p.add_argument("--sem-config", action="store_true",
                   help="não lê o subdomínio de data/config.json nem de KOMMO_DATA_DIR/config.json")
    return p


def main(argv: list[str] | None = None) -> int:
    try:
        args = criar_parser().parse_args(argv)
    except SystemExit as e:
        return 0 if e.code == 0 else 1     # --help → 0; uso inválido → 1
    termos, descartados = coletar_termos(args.termo + args.termos_posicionais,
                                         incluir_sistema=not args.sem_termos_padrao, raiz=args.raiz,
                                         incluir_config=not args.sem_config)
    try:
        res = verificar(args.raiz, args.dist, termos, args.somente_dist, args.mostrar_termos, descartados)
    except Exception as e:  # noqa: BLE001 - qualquer falha inesperada também é fail-closed
        res = Resultado(termos=termos, descartados=descartados,
                        erros=[f"falha inesperada no verificador: {type(e).__name__}: {e}"])
    saida = formatar_json(res, args.mostrar_termos) if args.json else formatar_texto(res, args.mostrar_termos)
    try:
        print(saida)
    except UnicodeEncodeError:
        print(saida.encode("ascii", "replace").decode("ascii"))
    return 0 if res.ok else 1


if __name__ == "__main__":
    sys.exit(main())
