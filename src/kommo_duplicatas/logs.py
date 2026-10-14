"""Log em arquivo (um por dia, <raiz de dados>/logs/AAAA-MM-DD.log) com data e hora em cada linha.

- Cada linha é sanitizada: caracteres de controle viram espaço (uma mensagem nunca quebra em várias linhas nem
  injeta sequências de terminal) e linhas longas são truncadas em MAX_LINHA caracteres.
- Rotação: no primeiro `gravar` do processo apaga os logs com mais de DIAS_RETENCAO dias.
- Fail-safe: se a pasta não for gravável, `gravar` não quebra o app; a linha é devolvida mesmo assim e o motivo
  fica em `ultimo_erro` (a UI pode exibir). O erro de pasta não gravável é tratado de verdade em paths/config.
"""
import os
import re
import threading
from datetime import datetime, timedelta

from . import paths

MAX_LINHA = 2000
DIAS_RETENCAO = 30

_CONTROLE = re.compile(r"[\x00-\x1f\x7f-\x9f]")
_NOME_LOG = re.compile(r"^(\d{4})-(\d{2})-(\d{2})\.log$")

_trava = threading.Lock()
_limpeza_feita = False
ultimo_erro: str | None = None


def agora() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")


def sanitizar(texto) -> str:
    """Troca caracteres de controle (\\x00-\\x1f, \\x7f-\\x9f; inclui \\n, \\r, \\t, ESC) por espaço."""
    return _CONTROLE.sub(" ", str(texto))


def formatar(nivel: str, msg: str) -> str:
    prefixo = {"erro": "ERRO  ", "aviso": "AVISO ", "ok": "OK    "}.get(nivel, "      ")
    linha = f"[{agora()}] {prefixo}{sanitizar(msg)}"
    if len(linha) > MAX_LINHA:
        cortados = len(linha) - MAX_LINHA
        marca = f" … [+{cortados} caracteres]"
        linha = linha[:MAX_LINHA - len(marca)] + marca
    return linha


def limpar_antigos(dias: int = DIAS_RETENCAO, pasta: str | None = None, hoje: datetime | None = None) -> int:
    """Apaga AAAA-MM-DD.log com data (pelo NOME do arquivo) anterior a `dias` atrás. Devolve quantos apagou.

    Só toca em arquivos com esse padrão de nome; nunca levanta exceção (é limpeza, não pode derrubar o app).
    """
    try:
        pasta = pasta or paths.logs_dir()
        nomes = os.listdir(pasta)
    except (OSError, paths.DataDirNotWritable):
        return 0
    limite = (hoje or datetime.now()).date() - timedelta(days=dias)
    apagados = 0
    for nome in nomes:
        m = _NOME_LOG.match(nome)
        if not m:
            continue
        try:
            data = datetime(int(m[1]), int(m[2]), int(m[3])).date()
        except ValueError:
            continue
        if data < limite:
            try:
                os.remove(os.path.join(pasta, nome))
                apagados += 1
            except OSError:
                pass
    return apagados


def gravar(nivel: str, msg: str) -> str:
    """Grava a linha em logs/AAAA-MM-DD.log e a devolve (para exibir na tela)."""
    global _limpeza_feita, ultimo_erro
    linha = formatar(nivel, msg)
    with _trava:
        try:
            pasta = paths.logs_dir()
            if not _limpeza_feita:
                _limpeza_feita = True
                limpar_antigos(pasta=pasta)
            nome = datetime.now().strftime("%Y-%m-%d") + ".log"
            with open(os.path.join(pasta, nome), "a", encoding="utf-8") as f:
                f.write(linha + "\n")
            ultimo_erro = None
        except (OSError, paths.DataDirNotWritable) as e:
            ultimo_erro = f"Não foi possível gravar o log: {e}"
    return linha
