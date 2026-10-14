#!/usr/bin/env bash
# Gera requirements.lock e requirements-dev.lock (versões exatas + hashes) com pip-compile.
# Equivalente Linux/macOS de scripts/gerar_lock.ps1 — NÃO TESTADO localmente (escrito/validado só no Windows).
#
#   bash scripts/gerar_lock.sh            # gera
#   bash scripts/gerar_lock.sh --upgrade  # atualiza para as versões mais novas dentro das faixas do .in
#
# pip-tools fica num venv TEMPORÁRIO (apagado no fim); nada é instalado no Python do sistema. Sem sudo.
set -euo pipefail

raiz="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$raiz"
export PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONDONTWRITEBYTECODE=1

falhar() { echo "ERRO: $*" >&2; exit 1; }

if [[ -x .venv/bin/python ]]; then py=.venv/bin/python
elif command -v python3 >/dev/null 2>&1; then py=python3
else falhar "python3 não encontrado (instale python3 e python3-venv pelo gerenciador da sua distro)."
fi

extra=()
[[ "${1:-}" == "--upgrade" ]] && extra+=(--upgrade)

tmp="$(mktemp -d -t kommo-lock-XXXXXX)"
trap 'rm -rf "$tmp"' EXIT

"$py" -m venv "$tmp/venv" || falhar "não consegui criar o venv temporário (no Debian/Ubuntu: python3-venv)."
"$tmp/venv/bin/python" -m pip install -q "pip-tools>=7.4" || falhar "não consegui instalar pip-tools (sem internet?)"

for par in "requirements.in:requirements.lock" "requirements-dev.in:requirements-dev.lock"; do
    entrada="${par%%:*}"; saida="${par##*:}"
    echo "==> $entrada -> $saida"
    "$tmp/venv/bin/python" -m piptools compile --quiet --generate-hashes --allow-unsafe --strip-extras \
        --no-emit-index-url --resolver=backtracking ${extra[@]+"${extra[@]}"} --output-file "$saida" "$entrada" \
        || falhar "pip-compile falhou para $entrada"
done
echo "OK: requirements.lock e requirements-dev.lock atualizados. Revise o diff antes de versionar."
