#!/usr/bin/env bash
# Roda o app a partir do código-fonte usando o ambiente LOCAL .venv (equivalente ao iniciar.bat).
# *** NÃO TESTADO LOCALMENTE *** (escrito no Windows).
# Dependências só são instaladas na primeira vez ou quando o arquivo de requisitos muda. Nunca usa sudo.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

py=".venv/bin/python"
req="requirements.txt"; hash=()
if [[ -f requirements.lock ]]; then req="requirements.lock"; hash=(--require-hashes); fi

if [[ ! -x "$py" ]]; then
    command -v python3 >/dev/null 2>&1 || { echo "ERRO: python3 (3.10+) não encontrado." >&2; exit 1; }
    echo "Criando o ambiente local .venv (só na primeira vez)..."
    python3 -m venv .venv || { echo "ERRO: não consegui criar o .venv (Debian/Ubuntu: python3-venv)." >&2; exit 1; }
fi
"$py" -c 'import tkinter' 2>/dev/null \
    || { echo "ERRO: tkinter ausente. Debian/Ubuntu: python3-tk · Fedora: python3-tkinter · Arch: tk." >&2; exit 1; }

if ! cmp -s "$req" .venv/.requisitos-instalados; then
    echo "Instalando dependências a partir de $req (só quando mudam)..."
    "$py" -m pip install -q --disable-pip-version-check ${hash[@]+"${hash[@]}"} -r "$req"
    cp "$req" .venv/.requisitos-instalados
fi

exec "$py" main.py "$@"
