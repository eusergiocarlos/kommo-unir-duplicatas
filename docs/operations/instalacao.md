# Instalação

Como instalar, atualizar e desinstalar o **Kommo — Unir Duplicatas**. O formato principal é a **pasta portátil
zipada para Windows** ([ADR-0008](../architecture/decisoes/ADR-0008-pyinstaller-onedir-zip.md)); todos os dados
ficam em `data/` dentro da pasta do programa ([ADR-0005](../architecture/decisoes/ADR-0005-modo-portatil-data-ao-lado.md)).

> **Estado de validação:** o build Windows é feito localmente por `scripts/build_windows.ps1`. **Nenhum Release foi
> publicado pelo workflow do GitHub até agora**, o pacote Linux **nunca foi testado** numa máquina Linux, e esta
> documentação não executou o app contra o Kommo real.

Veja também: [execução](execucao.md) · [recuperação de falhas](recuperacao-falhas.md) ·
[modelo de dados](../architecture/modelo-de-dados.md) · [segurança](../security/seguranca.md).

## 1. Windows (pacote zip)

### 1.1 Requisitos

| Item | Requisito |
|---|---|
| Sistema | Windows 10 ou 11, 64 bits (declarado no README; não há matriz de versões testadas) |
| Navegador | **Google Chrome ou Microsoft Edge** instalados. Sem eles o app tenta o Chromium do Playwright, que **não** vem no pacote |
| Disco | pasta **gravável** pelo seu usuário (Documentos, Área de Trabalho, `C:\Ferramentas\…`) |
| Permissão | usuário comum; **não** precisa de administrador |
| Rede | HTTPS para `https://<empresa>.kommo.com` |

### 1.2 Baixar e conferir o SHA-256

1. Na página **Releases** do repositório, baixe `KommoUnirDuplicatas-<versão>-win64.zip` **e** `SHA256SUMS.txt` do
   mesmo Release. Não use cópias repassadas por terceiros.
2. Confira o hash no PowerShell:

   ```powershell
   Get-FileHash .\KommoUnirDuplicatas-1.0.0-win64.zip -Algorithm SHA256
   Get-Content .\SHA256SUMS.txt
   ```

   O valor `Hash` (sem diferenciar maiúsculas) precisa ser **igual** ao da linha do zip em `SHA256SUMS.txt`.
   Se não for, **não use** o arquivo.
3. (Opcional, se o Release tiver atestação) `gh attestation verify <arquivo> --repo <dono>/<repositório>`
   ([ci-cd.md](ci-cd.md)).

### 1.3 Extrair

- Clique com o botão direito no zip → **Extrair tudo…** → escolha uma pasta sua (ex.: `Documentos`).
- O zip contém uma pasta `KommoUnirDuplicatas\` com `KommoUnirDuplicatas.exe` e `_internal\`.
- **Não** rode de dentro do zip e **não** extraia em `C:\Program Files` (sem permissão de escrita → o app
  mostra a mensagem de pasta de dados e não abre — [jornada (i)](../architecture/jornadas.md#i-pasta-sem-permissão-de-escrita)).

### 1.4 Primeira execução

1. Abra `KommoUnirDuplicatas\KommoUnirDuplicatas.exe`. O app cria `KommoUnirDuplicatas\data\`.
2. Siga a [jornada (a)](../architecture/jornadas.md#a-primeira-execução-e-login): subdomínio, **Só simular**,
   SIMULAR, login na janela do navegador.

### 1.5 SmartScreen e antivírus

- O executável **não tem assinatura de código** (Authenticode). O Windows SmartScreen pode mostrar "O Windows
  protegeu o computador" / editor desconhecido. Só prossiga (**Mais informações → Executar assim mesmo**) se o
  SHA-256 conferiu.
- Alguns antivírus marcam executáveis do PyInstaller como suspeitos (falso positivo conhecido). Prefira enviar o
  arquivo para análise do fornecedor do antivírus a desativá-lo. Se o antivírus apagar arquivos de `_internal\`,
  o app não abre: restaure a pasta a partir do zip conferido.

### 1.6 Atualizar

O app **não se atualiza sozinho** ([ADR-0011](../architecture/decisoes/ADR-0011-sem-telemetria-auto-update-sla.md)).

1. Baixe e confira a nova versão (1.2).
2. Extraia numa pasta nova.
3. Para manter o login e as preferências, feche o app antigo **e** o navegador aberto por ele e copie a pasta
   `data\` da versão antiga para dentro da nova. (Procedimento simples de arquivos; não há migração de formato
   entre versões até hoje.)
4. Apague a pasta antiga.

## 2. Linux (escrito, NÃO testado)

> **Status: NÃO TESTADO.** `scripts/build_linux.sh`, `packaging/linux/*` e `iniciar.sh` foram escritos no Windows,
> sem máquina Linux. O job de build Linux do `release.yml` é experimental (`continue-on-error`). Detalhes em
> [packaging/linux/README.md](../../packaging/linux/README.md).

O que está previsto:

- **`.tar.gz`** (`KommoUnirDuplicatas-<versão>-linux-<arch>.tar.gz`): `tar xzf …` e rodar
  `./KommoUnirDuplicatas/KommoUnirDuplicatas`. Dados em `KommoUnirDuplicatas/data/`.
- **AppImage** (opcional, só se o build tiver `appimagetool` e `unsquashfs`): `chmod +x` e executar. Como o AppImage
  é somente leitura, o `AppRun` define `KOMMO_DATA_DIR` como `KommoUnirDuplicatas-data/` **ao lado** do arquivo
  `.AppImage`.
- Conferir: `sha256sum -c SHA256SUMS.txt --ignore-missing`.

Dependências inevitáveis na máquina de quem usa:

- **Google Chrome, Microsoft Edge ou Chromium** instalado (o pacote não traz navegador; não dá para rodar
  `playwright install` a partir do binário congelado).
- Bibliotecas gráficas comuns de desktop (X11 ou Wayland com XWayland, `libX11`, `libXft`, `fontconfig`) para o Tk
  embutido.
- AppImage: FUSE 2 (`libfuse2`/`fuse2`), ou `--appimage-extract-and-run`.
- **glibc** igual ou mais nova que a da máquina de build (o CI usaria `ubuntu-22.04`).

## 3. A partir do código-fonte

Requisitos: Python **3.10+** (o lock atual foi gerado com **3.14**), Git, Chrome ou Edge.

### Windows (atalho)

`iniciar.bat` cria `.venv` (com `py -3` ou `python`), instala `requirements.lock` com `--require-hashes` (ou
`requirements.txt` se não houver lock) só quando o arquivo muda, e roda `main.py`.

### Manual (Windows / Linux)

```powershell
python -m venv .venv
.venv\Scripts\activate                       # Linux: source .venv/bin/activate
# execução, reproduzível (versões exatas + hashes):
python -m pip install --require-hashes -r requirements.lock
# se o lock não instalar na sua versão do Python (foi gerado com 3.14):
python -m pip install -r requirements.txt
python main.py                               # interface
python main.py --cli <empresa> contatos 3 --ensaio
```

- Para desenvolver/buildar use `requirements-dev.lock` (ou `requirements-dev.txt`) — ver
  [CONTRIBUTING.md](../../CONTRIBUTING.md) e [build e distribuição](build-distribuicao.md).
- Sem Chrome/Edge: `python -m playwright install chromium` (no Linux, se faltarem bibliotecas:
  `python -m playwright install-deps chromium`).
- No código-fonte a pasta de dados é `<raiz do repositório>/data/` (ignorada pelo `.gitignore`). **Nunca** a
  versione.
- Linux pelo código-fonte precisa de `python3-venv` e `python3-tk` (`iniciar.sh` verifica o `tkinter`) — **não
  testado**.

## 4. Desinstalar

Não há instalador nem entradas no registro.

1. Feche o app e a janela do navegador aberta por ele.
2. Apague a pasta do programa (`KommoUnirDuplicatas\`). Isso apaga junto `data\`, que guarda:
   - `profile\<canal>\` — **cookies da sessão do Kommo** (login), cache e histórico do navegador do app;
   - `config.json` — subdomínio da empresa e preferências;
   - `logs\` — logs diários;
   - `debug\` — capturas de diagnóstico (se `KOMMO_DEBUG` foi usado).
3. Se você definiu `KOMMO_DATA_DIR`, apague também essa pasta e remova a variável de ambiente.
4. Opcional: se instalou o Chromium do Playwright, `%LOCALAPPDATA%\ms-playwright` (Windows) ou
   `~/.cache/ms-playwright` (Linux).

> **Não compartilhe** a pasta do programa depois de usá-la: `data\profile\` permite entrar na conta do Kommo.
> Para entregar o app a outra pessoa, envie o zip original do Release.
