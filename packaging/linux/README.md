# Empacotamento Linux

> **Status: NÃO TESTADO.** Os arquivos desta pasta e `scripts/build_linux.sh`, `scripts/gerar_lock.sh` e
> `iniciar.sh` foram escritos e revisados no Windows, sem acesso a uma máquina Linux (nem WSL/Docker).
> Antes de publicar um build Linux, siga a seção [Como testar](#como-testar-numa-distro-limpa).

## Arquivos

| Arquivo | Para quê |
|---|---|
| `scripts/build_linux.sh` | PyInstaller **onedir** → `dist/linux/KommoUnirDuplicatas/`, `.tar.gz` portátil, AppImage opcional, `SHA256SUMS.txt`, verificação de privacidade (fail-closed) |
| `packaging/linux/AppRun` | ponto de entrada do AppImage; define `KOMMO_DATA_DIR` ao lado do `.AppImage` (o AppImage é montado somente leitura) |
| `packaging/linux/kommo-unir-duplicatas.desktop` | atalho de menu dentro do AppImage |
| ícone | **placeholder neutro** (quadrado cinza) gerado no build por `scripts/empacotar.py icone`; não há ícone oficial e não usamos a marca do Kommo |

`packaging/out/` está no `.gitignore` caso você queira usar essa pasta para testes manuais.

## Dependências

### Na máquina de BUILD

- Python 3.10+ com `venv` e **tkinter** (Debian/Ubuntu: `python3-venv python3-tk`; Fedora: `python3-tkinter`;
  Arch: `tk`). O PyInstaller copia `_tkinter` e as bibliotecas Tcl/Tk para dentro do pacote.
- Internet na primeira vez (instala `requirements-dev.lock` no `.venv` local).
- Opcional, para o AppImage: `appimagetool` (baixe do projeto oficial, confira o checksum, exporte
  `APPIMAGETOOL=/caminho`) **e** `squashfs-tools` (`unsquashfs`, usado pelo verificador para olhar dentro do
  AppImage — sem ele o AppImage não é gerado).
- **glibc:** o binário só roda em distros com glibc igual ou mais nova que a da máquina de build. Gere na distro
  mais antiga que quer suportar (ex.: Ubuntu 22.04 / Debian 12).
- O lock (`requirements-dev.lock`) gerado no Windows inclui pacotes só-Windows (`pywin32-ctypes`, `pefile`,
  `colorama`); são Python puro e instalam no Linux, mas o ideal é gerar o lock no Linux:
  `bash scripts/gerar_lock.sh`.

### Na máquina de quem USA

- **Inevitável: Google Chrome, Microsoft Edge ou Chromium instalado.** O app não embute navegador; o Playwright
  só traz o *driver* (Node.js) dentro do pacote. Sem Chrome/Edge, o app tenta o Chromium do Playwright, que NÃO
  vem no pacote (precisaria de `playwright install chromium`, impossível a partir do binário congelado).
- Bibliotecas gráficas comuns de qualquer desktop (X11/Wayland com XWayland, `libX11`, `libXft`, `fontconfig`)
  — usadas pelo Tk embutido. **Não** é preciso instalar `python3` nem `python3-tk`: vão dentro do pacote.
- AppImage: FUSE 2 (`libfuse2`/`fuse2`) para montar; sem FUSE dá para rodar com
  `./KommoUnirDuplicatas-*.AppImage --appimage-extract-and-run`.

## Onde ficam os dados (login do Kommo, config, logs)

- `.tar.gz`: em `data/` **dentro da pasta extraída** (modo portátil). Não compartilhe essa pasta depois de usar.
- AppImage: em `KommoUnirDuplicatas-data/` **ao lado do arquivo `.AppImage`** (definido pelo `AppRun`), porque
  o conteúdo do AppImage é somente leitura. `KOMMO_DATA_DIR` sobrescreve.

## Como testar numa distro limpa

1. Numa VM/contêiner com desktop (ex.: Ubuntu 22.04), como usuário comum (sem sudo no script):
   ```bash
   sudo apt install python3-venv python3-tk git     # manual, só na máquina de build
   bash scripts/build_linux.sh
   ```
   Confira: termina com "OK: nenhum dado pessoal..." e `dist/linux/SHA256SUMS.txt` existe.
2. `cd dist/linux && sha256sum -c SHA256SUMS.txt`
3. Numa **segunda** VM limpa (sem Python de desenvolvimento), com Chrome instalado:
   ```bash
   tar xzf KommoUnirDuplicatas-*-linux-x86_64.tar.gz
   ./KommoUnirDuplicatas/KommoUnirDuplicatas        # deve abrir a janela
   ```
   Feche sem iniciar uma união (não teste contra uma conta real sem querer). Confira que `KommoUnirDuplicatas/data/`
   foi criada **e não foi parar em `$HOME`**.
4. AppImage (se gerado): `chmod +x *.AppImage && ./KommoUnirDuplicatas-*.AppImage`; confira
   `KommoUnirDuplicatas-data/` ao lado do arquivo.
5. `python3 scripts/verificar_privacidade.py --somente-dist --dist dist/linux` deve sair com código 0.
