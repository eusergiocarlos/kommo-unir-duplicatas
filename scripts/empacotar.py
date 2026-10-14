"""Empacotamento determinístico usado por build_windows.ps1 e build_linux.sh (só stdlib, roda em qualquer SO).

    python scripts/empacotar.py zip    <pasta> <saida.zip>
    python scripts/empacotar.py targz  <pasta> <saida.tar.gz>
    python scripts/empacotar.py sha256 <saida SHA256SUMS.txt> <arquivo> [<arquivo> ...]
    python scripts/empacotar.py icone  <saida.png>          # ícone placeholder neutro (quadrado cinza 256x256)
    python scripts/empacotar.py versao <arquivo __init__.py>  # imprime __version__

Determinismo: entradas em ordem alfabética, data fixa (SOURCE_DATE_EPOCH se definido, senão 2020-01-01),
dono uid/gid 0 no tar, permissões normalizadas (0755 para executáveis/pastas, 0644 para o resto).
A pasta é gravada DENTRO do pacote com o próprio nome (ex.: KommoUnirDuplicatas/...), para não "espalhar"
arquivos ao descompactar.
"""
from __future__ import annotations

import gzip
import hashlib
import os
import re
import stat
import struct
import sys
import tarfile
import time
import zipfile
import zlib
from pathlib import Path

EPOCA = int(os.environ.get("SOURCE_DATE_EPOCH", "1577836800"))   # 2020-01-01T00:00:00Z


def _arquivos(pasta: Path) -> list[Path]:
    itens = []
    for atual, dirs, arqs in os.walk(pasta, followlinks=False):
        dirs.sort()
        for a in sorted(arqs):
            itens.append(Path(atual, a))
    return itens


def _executavel(c: Path) -> bool:
    try:
        return bool(c.stat().st_mode & stat.S_IXUSR) and os.name != "nt"
    except OSError:
        return False


def criar_zip(pasta: Path, saida: Path) -> None:
    pasta = pasta.resolve()
    data = time.gmtime(max(EPOCA, 315532800))[:6]          # zip não aceita antes de 1980
    tmp = saida.with_suffix(saida.suffix + ".parcial")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for c in _arquivos(pasta):
            if c.is_symlink():
                raise SystemExit(f"ERRO: link simbólico não suportado no zip: {c.relative_to(pasta)}")
            nome = f"{pasta.name}/{c.relative_to(pasta).as_posix()}"
            info = zipfile.ZipInfo(nome, date_time=data)
            info.compress_type = zipfile.ZIP_DEFLATED
            modo = 0o755 if _executavel(c) else 0o644
            info.external_attr = (stat.S_IFREG | modo) << 16
            with open(c, "rb") as f:
                z.writestr(info, f.read())
    os.replace(tmp, saida)


def criar_targz(pasta: Path, saida: Path) -> None:
    pasta = pasta.resolve()

    def normalizar(ti: tarfile.TarInfo) -> tarfile.TarInfo:
        ti.uid = ti.gid = 0
        ti.uname = ti.gname = ""
        ti.mtime = EPOCA
        if ti.isdir() or (ti.mode & 0o111):
            ti.mode = 0o755
        else:
            ti.mode = 0o644
        return ti

    tmp = saida.with_suffix(saida.suffix + ".parcial")
    with open(tmp, "wb") as bruto:
        # mtime=EPOCA e filename vazio no cabeçalho gzip → mesmo conteúdo gera o mesmo .tar.gz
        with gzip.GzipFile(filename="", mode="wb", fileobj=bruto, mtime=EPOCA, compresslevel=9) as gz:
            with tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as tar:
                tar.add(pasta, arcname=pasta.name, recursive=False, filter=normalizar)
                for atual, dirs, arqs in os.walk(pasta, followlinks=False):
                    dirs.sort()
                    for d in dirs:
                        c = Path(atual, d)
                        tar.add(c, arcname=f"{pasta.name}/{c.relative_to(pasta).as_posix()}", recursive=False,
                                filter=normalizar)
                    for a in sorted(arqs):
                        c = Path(atual, a)
                        tar.add(c, arcname=f"{pasta.name}/{c.relative_to(pasta).as_posix()}", recursive=False,
                                filter=normalizar)
    os.replace(tmp, saida)


def sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def gravar_sha256sums(saida: Path, arquivos: list[Path]) -> None:
    """Formato do `sha256sum` (GNU): '<hash>  <nome>' — confere com `sha256sum -c` ou Get-FileHash."""
    linhas = [f"{sha256(a)}  {a.name}\n" for a in sorted(arquivos, key=lambda p: p.name)]
    saida.write_text("".join(linhas), encoding="ascii", newline="\n")


def icone_placeholder(saida: Path, tam: int = 256) -> None:
    """PNG cinza neutro (sem marca de ninguém). Substitua por um ícone próprio quando houver."""
    linha = b"\x00" + bytes((0x80, 0x80, 0x80)) * tam
    dados = zlib.compress(linha * tam, 9)

    def chunk(tipo: bytes, conteudo: bytes) -> bytes:
        return struct.pack(">I", len(conteudo)) + tipo + conteudo + struct.pack(">I", zlib.crc32(tipo + conteudo))

    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", tam, tam, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", dados) + chunk(b"IEND", b""))
    saida.write_bytes(png)


def ler_versao(init_py: Path) -> str:
    m = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', init_py.read_text(encoding="utf-8"), re.M)
    if not m:
        raise SystemExit(f"ERRO: __version__ não encontrado em {init_py}")
    return m.group(1)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1
    cmd, *args = argv
    if cmd == "zip" and len(args) == 2:
        criar_zip(Path(args[0]), Path(args[1]))
    elif cmd == "targz" and len(args) == 2:
        criar_targz(Path(args[0]), Path(args[1]))
    elif cmd == "sha256" and len(args) >= 2:
        gravar_sha256sums(Path(args[0]), [Path(a) for a in args[1:]])
    elif cmd == "icone" and len(args) == 1:
        icone_placeholder(Path(args[0]))
    elif cmd == "versao" and len(args) == 1:
        print(ler_versao(Path(args[0])))
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
