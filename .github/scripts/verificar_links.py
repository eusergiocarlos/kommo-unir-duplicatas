"""Confere links RELATIVOS em arquivos Markdown (usado pelo CI; só stdlib).

    python .github/scripts/verificar_links.py            # varre o repositório a partir da raiz
    python .github/scripts/verificar_links.py docs/      # só uma pasta ou arquivo

O que confere:
- [texto](caminho), [texto](caminho#ancora) e ![img](caminho): o arquivo/pasta precisa existir;
- [texto](#ancora) e [texto](outro.md#ancora): a âncora precisa existir como título no arquivo de destino
  (slug no estilo do GitHub: minúsculas, sem pontuação, espaços viram "-", acentos mantidos);
- definições de referência: [rotulo]: caminho

O que NÃO confere (de propósito): links http(s)/mailto (dependem de rede), links dentro de blocos de código e
de `código em linha`, âncoras de arquivos que não são Markdown.

Saída: 0 = tudo certo; 1 = algum link quebrado (lista arquivo:linha).
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from urllib.parse import unquote

RAIZ = Path(__file__).resolve().parents[2]
PASTAS_IGNORADAS = {".git", ".venv", "venv", ".tox", "node_modules", "dist", "build", "__pycache__",
                    ".pytest_cache", ".ruff_cache", "htmlcov"}

RE_LINK = re.compile(r"!?\[(?:[^\[\]]|\[[^\]]*\])*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
RE_REF = re.compile(r"^\s{0,3}\[[^\]]+\]:\s*<?(\S+?)>?(?:\s+.*)?$")
RE_TITULO = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
RE_CERCA = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
RE_CODIGO_LINHA = re.compile(r"`+[^`]*`+")
RE_ANCORA_HTML = re.compile(r"<a\s+(?:name|id)=[\"']([^\"']+)[\"']", re.I)
ESQUEMAS = ("http://", "https://", "mailto:", "ftp://", "tel:", "data:")


def slug(titulo: str) -> str:
    """Âncora que o GitHub gera para um título (aproximação fiel aos casos comuns)."""
    t = re.sub(r"<[^>]+>", "", titulo)                         # tags HTML
    t = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", t)          # links → só o texto
    t = t.replace("`", "").strip().lower()
    t = re.sub(r"[^\w\- ]", "", t)                              # pontuação/emoji fora; letras acentuadas ficam
    return t.replace(" ", "-")


def linhas_fora_de_codigo(texto: str):
    """(número, linha) das linhas fora de blocos cercados por ``` ou ~~~."""
    cerca = None
    for n, linha in enumerate(texto.splitlines(), 1):
        m = RE_CERCA.match(linha)
        if m:
            marca = m.group(1)[0]
            if cerca is None:
                cerca = marca
            elif cerca == marca:
                cerca = None
            continue
        if cerca is None:
            yield n, linha


def ancoras(arquivo: Path, cache: dict[Path, set[str]]) -> set[str]:
    if arquivo not in cache:
        vistos: dict[str, int] = {}
        out: set[str] = set()
        texto = arquivo.read_text(encoding="utf-8", errors="replace")
        for _n, linha in linhas_fora_de_codigo(texto):
            m = RE_TITULO.match(linha)
            if m:
                base = slug(m.group(2))
                k = vistos.get(base, 0)
                out.add(base if k == 0 else f"{base}-{k}")          # títulos repetidos: -1, -2 ...
                vistos[base] = k + 1
            out.update(a.lower() for a in RE_ANCORA_HTML.findall(linha))
        cache[arquivo] = out
    return cache[arquivo]


def arquivos_markdown(alvos: list[Path]) -> list[Path]:
    out: list[Path] = []
    for alvo in alvos:
        if alvo.is_file():
            out.append(alvo)
            continue
        for atual, dirs, arqs in os.walk(alvo):
            dirs[:] = sorted(d for d in dirs if d not in PASTAS_IGNORADAS)
            out += [Path(atual, a) for a in sorted(arqs) if a.lower().endswith(".md")]
    return out


def verificar(arquivo: Path, cache: dict[Path, set[str]]) -> list[str]:
    erros: list[str] = []
    texto = arquivo.read_text(encoding="utf-8", errors="replace")
    try:
        rel = arquivo.relative_to(RAIZ).as_posix()
    except ValueError:
        rel = arquivo.as_posix()
    for n, linha in linhas_fora_de_codigo(texto):
        sem_codigo = RE_CODIGO_LINHA.sub("", linha)
        alvos = [m.group(1) for m in RE_LINK.finditer(sem_codigo)]
        m = RE_REF.match(sem_codigo)
        if m:
            alvos.append(m.group(1))
        for alvo in alvos:
            if alvo.lower().startswith(ESQUEMAS) or alvo.startswith("//"):
                continue
            caminho, _, ancora = alvo.partition("#")
            caminho = unquote(caminho.split("?", 1)[0])
            if caminho:
                destino = (RAIZ / caminho.lstrip("/")) if caminho.startswith("/") else (arquivo.parent / caminho)
                destino = destino.resolve()
                if not destino.exists():
                    erros.append(f"{rel}:{n}: arquivo/pasta não existe: {alvo}")
                    continue
            else:
                destino = arquivo
            if ancora and destino.is_file() and destino.suffix.lower() == ".md":
                if unquote(ancora).lower() not in ancoras(destino, cache):
                    erros.append(f"{rel}:{n}: âncora não encontrada: {alvo}")
    return erros


def main(argv: list[str]) -> int:
    alvos = [Path(a).resolve() for a in argv] or [RAIZ]
    cache: dict[Path, set[str]] = {}
    arquivos = arquivos_markdown(alvos)
    erros: list[str] = []
    for a in arquivos:
        erros += verificar(a, cache)
    for e in erros:
        print(f"ERRO {e}")
    print(f"{len(arquivos)} arquivo(s) Markdown verificados; {len(erros)} link(s) quebrado(s).")
    return 1 if erros else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
