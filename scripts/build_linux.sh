#!/usr/bin/env bash
# =====================================================================================================
#  Build Linux: pasta portátil (PyInstaller onedir) em .tar.gz + AppImage (se appimagetool existir)
#  + SHA256SUMS + verificação de privacidade (fail-closed).
#
#  *** NÃO TESTADO LOCALMENTE *** — escrito no Windows, sem WSL/Docker. Valide numa máquina Linux antes de
#  confiar (ver packaging/linux/README.md, seção "Como testar").
#
#  Uso:   bash scripts/build_linux.sh            (na raiz ou de qualquer lugar)
#         SEM_INSTALAR=1 bash scripts/build_linux.sh   # usa o .venv como está (sem internet)
#
#  Saída (dist/linux/):
#    KommoUnirDuplicatas/                                  pasta do programa (executável + _internal/)
#    KommoUnirDuplicatas-<versão>-linux-<arch>.tar.gz      o que se publica (portátil)
#    KommoUnirDuplicatas-<versão>-<arch>.AppImage          opcional (precisa de appimagetool + unsquashfs)
#    SHA256SUMS.txt
#
#  Nunca usa sudo. Nunca baixa ferramentas sozinho: se faltar algo, explica o que instalar.
#  O binário só roda em distros com glibc >= à da máquina de build → gere na distro MAIS ANTIGA que quer suportar.
# =====================================================================================================
set -euo pipefail

falhar() { echo; echo "ERRO: $*" >&2; exit 1; }
etapa()  { echo; echo "==> $*"; }
aviso()  { echo "AVISO: $*" >&2; }

[[ "$(uname -s)" == "Linux" ]] || falhar "este script é só para Linux (no Windows use scripts/build_windows.ps1)."

raiz="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$raiz"
nome="KommoUnirDuplicatas"
saida="$raiz/dist/linux"
venv_py="$raiz/.venv/bin/python"
arch="$(uname -m)"
export PYTHONDONTWRITEBYTECODE=1 PIP_DISABLE_PIP_VERSION_CHECK=1

[[ -f main.py && -f src/kommo_duplicatas/__init__.py ]] || falhar "rode a partir do projeto (main.py/src não encontrados)."

# Argumentos extras do verificador de privacidade. No CI (GitHub Actions define CI=true) o usuário do runner
# ("runner"/"runneradmin") e o hostname não identificam ninguém e "runner" é substring de módulos do próprio
# Python embutidos no pacote (ex.: asyncio/runners.py) → falso positivo que derrubaria o build. Por isso, só no
# CI: --sem-termos-padrao (sem usuário/host/git), mais um termo-sentinela ALEATÓRIO (nunca existe nos arquivos)
# porque o verificador é fail-closed sem nenhum termo; assim as checagens estruturais continuam rodando. Termos
# reais vêm de KOMMO_TERMOS_SENSIVEIS (secret), lido pelo próprio verificador. Localmente: termos padrão.
priv_extra=()
if [[ "${CI:-}" == "true" ]]; then
    sentinela="sentinela-ci-$(od -An -N8 -tx1 /dev/urandom | tr -d ' \n')"
    priv_extra=(--sem-termos-padrao --termo "$sentinela")
    echo "CI detectado: verificador sem termos do sistema (só KOMMO_TERMOS_SENSIVEIS + checagens estruturais)."
fi

# ------------------------------------------------------------------ 1. ambiente virtual
etapa "Ambiente virtual (.venv)"
if [[ ! -x "$venv_py" ]]; then
    command -v python3 >/dev/null 2>&1 || falhar "python3 não encontrado. Instale python3 (3.10+) pelo gerenciador da distro."
    python3 -m venv "$raiz/.venv" || falhar "não consegui criar o .venv (Debian/Ubuntu: instale python3-venv)."
fi
"$venv_py" -c 'import sys; assert sys.version_info >= (3, 10), sys.version' || falhar "o .venv precisa de Python 3.10+."
# tkinter é necessário NA MÁQUINA DE BUILD (o PyInstaller copia _tkinter + Tcl/Tk para dentro do pacote);
# quem só USA o binário não precisa instalar python3-tk.
"$venv_py" -c 'import tkinter' 2>/dev/null \
    || falhar "tkinter ausente no Python de build. Debian/Ubuntu: python3-tk · Fedora: python3-tkinter · Arch: tk."

# ------------------------------------------------------------------ 2. dependências
if [[ -z "${SEM_INSTALAR:-}" ]]; then
    etapa "Dependências"
    if [[ -f requirements-dev.lock ]]; then
        "$venv_py" -m pip install --require-hashes --no-deps -q -r requirements-dev.lock \
            || falhar "pip install do lock falhou (lock gerado no Windows? gere no Linux: bash scripts/gerar_lock.sh)."
    else
        aviso "requirements-dev.lock não existe → instalando de requirements-dev.txt (build NÃO reproduzível)."
        aviso "Gere o lock com: bash scripts/gerar_lock.sh"
        "$venv_py" -m pip install -q -r requirements-dev.txt || falhar "pip install falhou."
    fi
fi
"$venv_py" -c 'import PyInstaller, playwright' || falhar "PyInstaller/playwright ausentes no .venv."

# ------------------------------------------------------------------ 3. versão
versao="$("$venv_py" scripts/empacotar.py versao src/kommo_duplicatas/__init__.py)"
[[ "$versao" =~ ^[0-9A-Za-z.+-]+$ ]] || falhar "versão inválida: '$versao'"
echo "Versão: $versao  ·  arquitetura: $arch"

# ------------------------------------------------------------------ 4. limpar saída anterior (só dist/linux)
etapa "Limpando dist/linux"
mkdir -p "$saida"
rm -rf "${saida:?}/$nome" "$saida/$nome-$versao-linux-$arch.tar.gz" "$saida/$nome-$versao-$arch.AppImage" \
       "$saida/SHA256SUMS.txt"

tmp="$(mktemp -d -t kommo-build-XXXXXX)"
trap 'rm -rf "$tmp"' EXIT

# ------------------------------------------------------------------ 5. PyInstaller (work/spec no temporário)
etapa "PyInstaller (onedir)"
"$venv_py" -m PyInstaller --noconfirm --clean --onedir --windowed \
    --name "$nome" \
    --paths "$raiz/src" \
    --collect-all playwright \
    --exclude-module pytest \
    --distpath "$saida" \
    --workpath "$tmp/work" \
    --specpath "$tmp/spec" \
    "$raiz/main.py" || falhar "PyInstaller falhou."
[[ -x "$saida/$nome/$nome" ]] || falhar "PyInstaller não gerou $saida/$nome/$nome"

# ------------------------------------------------------------------ 6. tar.gz portátil
etapa "Empacotando .tar.gz"
tgz="$saida/$nome-$versao-linux-$arch.tar.gz"
"$venv_py" scripts/empacotar.py targz "$saida/$nome" "$tgz" || falhar "falha ao criar o .tar.gz"
publicar=("$tgz")

# ------------------------------------------------------------------ 7. AppImage (opcional)
etapa "AppImage"
appimagetool_bin="${APPIMAGETOOL:-$(command -v appimagetool || true)}"
if [[ -z "$appimagetool_bin" ]]; then
    aviso "appimagetool não encontrado → AppImage NÃO gerado (o .tar.gz basta). Para gerar, baixe o appimagetool"
    aviso "do projeto oficial (github.com/AppImage/appimagetool), confira o checksum e exporte APPIMAGETOOL=/caminho."
elif ! command -v unsquashfs >/dev/null 2>&1; then
    aviso "unsquashfs (squashfs-tools) não encontrado → AppImage NÃO gerado: sem ele o verificador não consegue"
    aviso "olhar dentro do AppImage (fail-closed). Instale squashfs-tools e rode de novo."
else
    appdir="$tmp/AppDir"
    mkdir -p "$appdir/usr/lib/kommo-unir-duplicatas"
    cp -a "$saida/$nome/." "$appdir/usr/lib/kommo-unir-duplicatas/"
    install -m 0755 packaging/linux/AppRun "$appdir/AppRun"
    install -m 0644 packaging/linux/kommo-unir-duplicatas.desktop "$appdir/kommo-unir-duplicatas.desktop"
    # ícone: placeholder neutro gerado (quadrado cinza) — troque por um ícone próprio quando existir
    "$venv_py" scripts/empacotar.py icone "$appdir/kommo-unir-duplicatas.png"
    ln -s kommo-unir-duplicatas.png "$appdir/.DirIcon"
    # verifica o AppDir ANTES de empacotar (mais rápido de diagnosticar do que dentro do squashfs)
    "$venv_py" scripts/verificar_privacidade.py --somente-dist --dist "$appdir" ${priv_extra[@]+"${priv_extra[@]}"} \
        || falhar "verificação de privacidade do AppDir falhou — AppImage não gerado."
    appimg="$saida/$nome-$versao-$arch.AppImage"
    ARCH="$arch" "$appimagetool_bin" --no-appstream "$appdir" "$appimg" || falhar "appimagetool falhou."
    chmod 0755 "$appimg"
    publicar+=("$appimg")
fi

# ------------------------------------------------------------------ 8. hashes
etapa "SHA256SUMS"
"$venv_py" scripts/empacotar.py sha256 "$saida/SHA256SUMS.txt" "${publicar[@]}" || falhar "falha ao gerar SHA256SUMS"

# ------------------------------------------------------------------ 9. privacidade (fail-closed)
etapa "Verificando privacidade do resultado (dist/linux)"
"$venv_py" scripts/verificar_privacidade.py --somente-dist --dist "$saida" ${priv_extra[@]+"${priv_extra[@]}"} \
    || falhar "verificação de privacidade FALHOU — NÃO publique o conteúdo de dist/linux."

etapa "Pronto"
for p in "${publicar[@]}"; do echo "  $p ($(du -h "$p" | cut -f1))"; done
echo "  $saida/SHA256SUMS.txt"
sed 's/^/    /' "$saida/SHA256SUMS.txt"
