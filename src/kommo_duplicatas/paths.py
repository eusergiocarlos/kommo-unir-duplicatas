"""Onde o app guarda os arquivos operacionais (perfil do navegador, configuração, logs, depuração).

MODO PORTÁTIL (padrão): tudo fica numa única "raiz de dados" DENTRO da pasta do programa:

    <pasta do programa>/data/
        config.json          preferências (empresa, tipo, limite, ...)
        logs/AAAA-MM-DD.log   log diário (apagado após 30 dias)
        profile/<canal>/      perfil persistente do navegador, um por canal (chrome | msedge | chromium)
        debug/                capturas de diagnóstico (KOMMO_DEBUG=1)

"Pasta do programa" (`app_dir()`):
- executável (PyInstaller): a pasta onde está o .exe;
- código-fonte: a raiz do repositório (dois níveis acima de src/kommo_duplicatas).
Nunca depende do diretório de trabalho atual (cwd) nem de caminhos absolutos da máquina do autor.

Precedência da raiz de dados:
1. variável de ambiente KOMMO_DATA_DIR (caminho relativo é resolvido a partir da pasta do programa);
2. <pasta do programa>/data, se for gravável;
3. caso contrário levanta `DataDirNotWritable` com explicação e solução. NÃO cai em silêncio para %APPDATA%.

O app não guarda senhas nem tokens: o login do Kommo fica só no perfil do navegador (`profile/`),
que pode ser apagado com `esquecer_login()`.
"""
import os
import shutil
import sys
import tempfile

NOME_PASTA_DADOS = "data"
VAR_AMBIENTE = "KOMMO_DATA_DIR"

# Raízes já testadas com sucesso neste processo (evita criar/apagar arquivo de teste a cada chamada).
_verificadas: set[str] = set()


class DataDirNotWritable(RuntimeError):
    """A pasta de dados não pode ser criada ou não aceita escrita.

    Herda de RuntimeError (e não de OSError) de propósito: código que faz `except OSError: pass` não deve
    engolir este erro — ele precisa chegar ao usuário.
    """

    def __init__(self, pasta: str, motivo: str = ""):
        self.pasta = pasta
        self.motivo = motivo
        detalhe = f"\nDetalhe técnico: {motivo}" if motivo else ""
        super().__init__(
            f"Não consigo gravar na pasta de dados do programa:\n  {pasta}\n\n"
            "O app guarda configuração, logs e o login do navegador nessa pasta (modo portátil). "
            "Isso costuma acontecer quando o programa está em uma pasta protegida (ex.: 'Arquivos de Programas'), "
            "num pendrive/rede somente leitura ou sem permissão do seu usuário.\n\n"
            "Como resolver (escolha um):\n"
            "  1. Mova a pasta do programa para um local seu (ex.: Documentos ou Área de Trabalho); ou\n"
            f"  2. Defina a variável de ambiente {VAR_AMBIENTE} com uma pasta gravável "
            "(ex.: C:\\Users\\<você>\\KommoDados) e abra o programa de novo."
            + detalhe)


class EsquecerLoginErro(RuntimeError):
    """Não foi possível apagar o perfil do navegador (ex.: navegador do app ainda aberto)."""


# ---------------------------------------------------------------------------------------------- localização
def app_dir() -> str:
    """Pasta do programa: a do .exe (congelado) ou a raiz do repositório (código-fonte)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    # .../<raiz>/src/kommo_duplicatas/paths.py -> sobe: kommo_duplicatas -> src -> <raiz>
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def raiz_padrao() -> str:
    """Raiz de dados portátil (sem considerar KOMMO_DATA_DIR)."""
    return os.path.join(app_dir(), NOME_PASTA_DADOS)


def raiz_configurada() -> str:
    """Caminho da raiz de dados conforme a precedência, SEM criar nem testar escrita."""
    override = (os.environ.get(VAR_AMBIENTE) or "").strip().strip('"')
    if override:
        caminho = os.path.expandvars(os.path.expanduser(override))
        if not os.path.isabs(caminho):            # relativo -> relativo à pasta do programa, nunca ao cwd
            caminho = os.path.join(app_dir(), caminho)
        return os.path.normpath(os.path.abspath(caminho))
    return os.path.normpath(raiz_padrao())


def ensure_writable(pasta: str | None = None) -> str:
    """Garante que `pasta` (padrão: a raiz de dados) existe e aceita escrita; devolve o caminho.

    Faz um teste REAL (cria e apaga um arquivo): no Windows `os.access(W_OK)` só olha o atributo
    "somente leitura" e ignora ACLs (ex.: Program Files), então sozinho não é confiável.
    Levanta `DataDirNotWritable` com mensagem explicativa.
    """
    pasta = os.path.normpath(os.path.abspath(pasta or raiz_configurada()))
    if pasta in _verificadas and os.path.isdir(pasta):
        return pasta
    try:
        os.makedirs(pasta, exist_ok=True)
    except OSError as e:
        raise DataDirNotWritable(pasta, f"{type(e).__name__}: {e}") from e
    if not os.access(pasta, os.W_OK):
        raise DataDirNotWritable(pasta, "sem permissão de escrita")
    try:
        fd, teste = tempfile.mkstemp(prefix=".teste-escrita-", dir=pasta)
        try:
            os.write(fd, b"ok")
        finally:
            os.close(fd)
        os.remove(teste)
    except OSError as e:
        raise DataDirNotWritable(pasta, f"{type(e).__name__}: {e}") from e
    _verificadas.add(pasta)
    return pasta


def data_dir() -> str:
    """Raiz de dados (criada e testada). Ver precedência no topo do módulo."""
    return ensure_writable(raiz_configurada())


def _sub(nome: str, criar: bool = True) -> str:
    d = os.path.join(data_dir(), nome)
    if criar:
        os.makedirs(d, exist_ok=True)
    return d


def profile_dir(canal: str | None = None) -> str:
    """Perfil persistente do navegador (guarda o login do Kommo entre execuções).

    Sem `canal` devolve a pasta-base `data/profile` (compatível com quem já chamava sem argumento);
    com canal ('chrome' | 'msedge' | 'chromium') devolve `data/profile/<canal>` — cada navegador tem o seu
    perfil, porque um perfil do Chrome não deve ser aberto pelo Edge e vice-versa.
    """
    base = os.path.join(data_dir(), "profile")
    if canal is None:
        return base
    canal = str(canal).strip().lower()
    if not canal or canal in (".", "..") or any(c in canal for c in "/\\:"):
        raise ValueError(f"Canal de navegador inválido: {canal!r}")
    return os.path.join(base, canal)


def config_file() -> str:
    return os.path.join(data_dir(), "config.json")


def logs_dir() -> str:
    return _sub("logs")


def debug_dir() -> str:
    return _sub("debug")


# ---------------------------------------------------------------------------------------------- segurança
def dentro_da_raiz(caminho: str, raiz: str | None = None) -> bool:
    """True se `caminho` (resolvido, sem links) está estritamente dentro de `raiz` (padrão: raiz de dados)."""
    raiz_real = os.path.normcase(os.path.realpath(raiz or raiz_configurada()))
    alvo_real = os.path.normcase(os.path.realpath(caminho))
    try:
        comum = os.path.commonpath([raiz_real, alvo_real])
    except ValueError:                      # unidades diferentes no Windows
        return False
    return comum == raiz_real and alvo_real != raiz_real


def _eh_link(caminho: str) -> bool:
    """Link simbólico ou junção do Windows (os.path.isjunction existe a partir do Python 3.12)."""
    eh_juncao = getattr(os.path, "isjunction", None)
    return os.path.islink(caminho) or bool(eh_juncao and eh_juncao(caminho))


def esquecer_login() -> bool:
    """Apaga o perfil do navegador (data/profile/*), ou seja, o login salvo do Kommo.

    Devolve True se havia algo para apagar, False se já estava vazio. Recusa (EsquecerLoginErro) se a pasta
    do perfil não estiver dentro da raiz de dados (ou for um link), e se algum arquivo estiver em uso
    (navegador do app aberto). Nunca toca em nada fora de data/profile.
    """
    raiz = data_dir()
    base = os.path.join(raiz, "profile")
    if not os.path.lexists(base):
        return False
    if _eh_link(base) or not dentro_da_raiz(base, raiz):
        raise EsquecerLoginErro(f"Recusei apagar {base}: não está dentro da pasta de dados {raiz}.")
    itens = os.listdir(base)
    if not itens:
        return False
    falhas = []
    for nome in itens:
        alvo = os.path.join(base, nome)
        try:
            if _eh_link(alvo) or os.path.isfile(alvo):
                os.remove(alvo)               # link: remove só o link, nunca o destino
            elif not dentro_da_raiz(alvo, raiz):
                falhas.append(f"{nome}: fora da pasta de dados")
            else:
                shutil.rmtree(alvo)           # rmtree não segue junções/links (Python >= 3.8)
        except OSError as e:
            falhas.append(f"{nome}: {e.strerror or e}")
    if falhas:
        raise EsquecerLoginErro(
            "Não consegui apagar todo o login salvo. Feche a janela do navegador aberta pelo app e tente de "
            "novo. Detalhes: " + "; ".join(falhas))
    return True
