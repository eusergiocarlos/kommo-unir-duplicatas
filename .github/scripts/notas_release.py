"""Monta as notas de um Release (rascunho) a partir da seção da versão no CHANGELOG.md. Só stdlib.

    python .github/scripts/notas_release.py 1.2.0 notas.md
    python .github/scripts/notas_release.py 1.2.0 notas.md --repositorio dono/repo

Aceita títulos de seção nos formatos "## 1.2.0", "## v1.2.0", "## [1.2.0]" e "## [1.2.0] - 2026-01-31".
A seção vai até o próximo título de nível 2 ("## "). Se a versão não estiver no CHANGELOG → código 1 (o
workflow de release falha: não se publica versão sem changelog).

Depois da seção são acrescentados, sempre, os avisos fixos: como conferir o SHA-256, a ausência de assinatura
de código (Authenticode) e o status do build Linux.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]


def extrair_secao(changelog: str, versao: str) -> str | None:
    v = re.escape(versao.lstrip("v"))
    inicio = re.compile(rf"^##\s+\[?v?{v}\]?(?=\s|$).*$", re.M)
    m = inicio.search(changelog)
    if not m:
        return None
    resto = changelog[m.end():]
    prox = re.search(r"^##\s", resto, re.M)
    corpo = resto[:prox.start()] if prox else resto
    return corpo.strip()


def avisos(repositorio: str) -> str:
    verificar_attest = (f"gh attestation verify <arquivo> --repo {repositorio}" if repositorio
                        else "gh attestation verify <arquivo> --repo <dono>/<repositório>")
    return f"""
---

### Antes de usar

- **Baixe só desta página de Releases.** Confira o SHA-256 com o `SHA256SUMS.txt`:
  - Windows (PowerShell): `Get-FileHash .\\<arquivo>.zip -Algorithm SHA256` e compare com a linha do arquivo;
  - Linux: `sha256sum -c SHA256SUMS.txt --ignore-missing`.
- Proveniência do build (quando disponível): `{verificar_attest}`.
- **Sem assinatura de código (Authenticode).** O Windows SmartScreen e alguns antivírus podem avisar ou
  bloquear executáveis do PyInstaller (falso positivo comum). Só prossiga se o hash conferir.
- **Linux: build NÃO validado numa máquina real** — trate o `.tar.gz`/AppImage como experimental.
- **A união de duplicatas no Kommo é irreversível.** Teste primeiro com um número pequeno.
- SBOM (CycloneDX, dependências de execução) anexado como `*.cdx.json`.
"""


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("versao")
    p.add_argument("saida", type=Path)
    p.add_argument("--changelog", type=Path, default=RAIZ / "CHANGELOG.md")
    p.add_argument("--repositorio", default="", help="dono/repo (no CI: github.repository)")
    a = p.parse_args(argv)
    try:
        texto = a.changelog.read_text(encoding="utf-8")
    except OSError as e:
        print(f"ERRO: não consegui ler {a.changelog}: {e}", file=sys.stderr)
        return 1
    secao = extrair_secao(texto, a.versao)
    if secao is None:
        print(f"ERRO: a versão {a.versao} não tem seção no {a.changelog.name} (ex.: '## {a.versao}').",
              file=sys.stderr)
        return 1
    if not secao:
        print(f"ERRO: a seção da versão {a.versao} no {a.changelog.name} está vazia.", file=sys.stderr)
        return 1
    a.saida.write_text(f"## Novidades\n\n{secao}\n{avisos(a.repositorio)}", encoding="utf-8", newline="\n")
    print(f"Notas da versão {a.versao} gravadas em {a.saida}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
