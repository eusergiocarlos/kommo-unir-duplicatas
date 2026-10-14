# Modelo de dados

O app **não tem banco de dados nem servidor**. Os dados que existem são: arquivos locais na pasta de dados
(`data/`), estruturas em memória trocadas entre a interface e o motor, variáveis de ambiente e códigos de saída.
Tudo abaixo foi conferido no código (`src/kommo_duplicatas/`).

Veja também: [arquitetura](arquitetura.md) · [jornadas](jornadas.md) ·
[recuperação de falhas](../operations/recuperacao-falhas.md) · [segurança](../security/seguranca.md).

## 1. Pasta de dados

### 1.1 Onde fica

Precedência (`paths.raiz_configurada()`):

1. variável de ambiente `KOMMO_DATA_DIR` — aspas e espaços nas pontas são removidos, `~` e variáveis
   (`%VAR%`/`$VAR`) são expandidas; caminho **relativo** é resolvido a partir da pasta do programa (nunca do
   diretório atual);
2. `<pasta do programa>/data`, onde "pasta do programa" (`paths.app_dir()`) é:
   - executável PyInstaller: a pasta do `.exe` (ex.: `...\KommoUnirDuplicatas\data\`);
   - código-fonte: a raiz do repositório (dois níveis acima de `src/kommo_duplicatas/`);
3. se a pasta não puder ser criada ou não aceitar escrita → `paths.DataDirNotWritable`. **Não existe** queda
   silenciosa para `%APPDATA%` ([ADR-0005](decisoes/ADR-0005-modo-portatil-data-ao-lado.md)).

A escrita é testada **de verdade** (`tempfile.mkstemp` + `write` + `remove`), porque no Windows `os.access(W_OK)`
ignora ACLs. O resultado fica em cache por processo.

> **Histórico:** a 1.0.0 usava `%APPDATA%\KommoUnirDuplicatas\`; essa pasta só aparece como histórico no
> `CHANGELOG.md` (seção 1.0.0), no `README.md`/`SECURITY.md` (nota de migração) e nos ADRs. O código atual **não
> usa** `%APPDATA%`.

### 1.2 Estrutura

```text
data/
├─ config.json               preferências (ver §2)
├─ config.json.corrompido    só existe se um config.json inválido foi isolado
├─ logs/
│  └─ AAAA-MM-DD.log         um arquivo por dia; apagados após 30 dias
├─ profile/
│  ├─ chrome/                perfil persistente do Google Chrome usado pelo app
│  ├─ msedge/                perfil do Microsoft Edge (se já foi usado)
│  └─ chromium/              perfil do Chromium do Playwright (se já foi usado)
└─ debug/                    capturas <rótulo>.png (só com KOMMO_DEBUG)
```

| Item | Criado por | Quando |
|---|---|---|
| `data/` | `paths.ensure_writable()` | ao abrir a janela (`ui.main`) ou na primeira chamada a qualquer caminho |
| `config.json` | `config.salvar()` | ao clicar INICIAR (UI); ao abrir o navegador (`canal_navegador`); no fim (`ultimo_total`) |
| `logs/` | `logs.gravar()` | na primeira linha de log |
| `profile/<canal>/` | o próprio Chrome/Edge (via Playwright) | na primeira execução com aquele canal |
| `debug/` | `Merger._diagnostico()` | só com `KOMMO_DEBUG` e em situações de diagnóstico |

Fora de `data/`, o Playwright usa o `%TEMP%` do sistema para os seus temporários e, no `.exe` Windows, procura o
Chromium em `%LOCALAPPDATA%\ms-playwright` (só se o usuário o tiver instalado).

## 2. `config.json`

JSON UTF-8, objeto na raiz, `indent=2`. Gravação **atômica** (`tempfile.mkstemp` na mesma pasta, `fsync`,
`os.replace`; até 5 tentativas com espera curta se o antivírus/indexador estiver lendo).

| Campo | Tipo | Padrão (`config.PADRAO`) | Quem grava | Validação ao carregar |
|---|---|---|---|---|
| `empresa` | string | `""` | UI ao INICIAR (já normalizado por `kommo.normalizar_empresa`) | precisa ser string; a UI normaliza de novo ao iniciar |
| `tipo` | string | `"leads"` | UI ao INICIAR | precisa ser `"leads"` ou `"contatos"` (exatamente) |
| `limite` | int | `100` | UI ao INICIAR (opção marcada: 100, 200, 500 ou 0 = todas) | int ≥ 0 (`true`/`false` e `1.5` não valem) |
| `limite_custom` | int ou `null` | `null` | UI ao INICIAR (valor do campo "outro", já validado por `parse_limite`) | `""`/`null` → `null`; int ≥ 0 ou texto só com dígitos (`"350"` → 350); outro valor → padrão (`null`) |
| `privacidade` | bool | `true` | UI ao INICIAR | precisa ser bool; a chave antiga `blur` é aceita se `privacidade` não existir |
| `canal_navegador` | string | `""` | motor, depois que o navegador abre | precisa ser string (ou `null` → `""`); `strip().lower()`; valores esperados `chrome`, `msedge`, `chromium` ou `""` |
| `ultimo_total` | int | `0` | UI no `FimEvt` (só motivos `limite`, `sem_duplicatas`, `parado` com total > 0) | int ≥ 0 |
| `ultima_execucao` | string ISO 8601 (segundos) | `""` | idem (`datetime.now().isoformat(timespec="seconds")`) | precisa ser string |

Regras de carga (`config.carregar_detalhado()`):

- chaves desconhecidas são **descartadas**;
- arquivo inexistente → padrões, sem aviso;
- JSON inválido, conteúdo que não é objeto ou bytes inválidos → o arquivo é **renomeado** para
  `config.json.corrompido` (sobrescrevendo um anterior), o app usa os padrões e registra um aviso no log;
- campo com **tipo/valor inválido** (tabela acima) → só **aquele campo** volta ao padrão; o arquivo **não** é
  renomeado e o aviso ("… tem valor inválido em: limite, tipo. Usando o padrão nesses campos.") segue o mesmo
  caminho do arquivo corrompido (retorno de `carregar_detalhado()`, `config.ultimo_aviso` e log). A janela abre
  normalmente (`tests/test_config.py::test_tipos_errados_voltam_ao_padrao_com_aviso`);
- erro de leitura (permissão etc.) → padrões + aviso;
- `paths.DataDirNotWritable` **não** é engolida.

O modo **CLI não lê nem grava** `empresa`/`tipo`/`limite`/`privacidade` (usa os argumentos), mas o motor ainda lê e
grava `canal_navegador`.

> Desde a T11 os tipos são validados ao carregar (antes, um `config.json` editado à mão com `"limite": "abc"`
> podia impedir a janela de abrir). Recuperação manual, se preciso: apagar ou corrigir o arquivo
> ([recuperação de falhas](../operations/recuperacao-falhas.md)).

Exemplo (fictício):

```json
{
  "empresa": "acme",
  "tipo": "contatos",
  "limite": 100,
  "limite_custom": 3,
  "privacidade": true,
  "canal_navegador": "chrome",
  "ultimo_total": 42761,
  "ultima_execucao": "2026-10-13T15:04:05"
}
```

## 3. Eventos e estruturas em memória

Definidos em `merger.py` (eventos, `Job`), `kommo.py` (`Estado`) e `fluxo.py` (`Resultado`).

### `Job` (UI/CLI → motor)

| Campo | Tipo | Padrão | Significado |
|---|---|---|---|
| `empresa` | str | – | subdomínio (o motor valida com `normalizar_empresa`) |
| `tipo` | str | – | `"leads"` ou `"contatos"` (outro valor → motivo `validacao`) |
| `limite` | int | – | quantidade de cliques em Unir; `0` = todas; negativo → `validacao` |
| `privacidade` | bool | `True` | registra `init_script(True)` e faz o reforço periódico |
| `ensaio` | bool | `False` | abre o modal, valida e **não clica** em Unir |
| `confirmar_conta` | bool | `True` | emite `ConfirmarEvt` e espera `responder()` antes do 1º clique (UI e CLI sempre usam `True`) |

### Eventos (motor → UI/CLI)

| Evento | Campos | Notas |
|---|---|---|
| `LogEvt` | `nivel: str`, `msg: str` | `nivel` ∈ `info`, `ok`, `aviso`, `erro` |
| `ProgEvt` | `feitos`, `limite`, `total`, `incertas=0`, `cliques=0` | `feitos` = confirmadas; `total` = grupos informados pelo Kommo no título (0 = "muitas"/não informado) |
| `ConfirmarEvt` | `host`, `tipo`, `total`, `limite`, `ensaio=False` | `host` = `<empresa>.kommo.com` |
| `FimEvt` | `feitos`, `segundos`, `erros`, `interrompido`, `total`, `confirmadas=0`, `incertas=0`, `cliques=0`, `motivo=""`, `avisos=0` | emitido uma única vez; `motivo` ∈ chaves de `merger.MOTIVOS`; `interrompido` = motivo `parado`/`forcado` ou parada pedida |

### `Estado` (leitura do modal num instante — `kommo.Estado`, imutável)

| Campo | Tipo | Origem no DOM |
|---|---|---|
| `erro` | bool | `.js-modal-error` visível |
| `modal` | bool | título, Unir, progresso ou erro visível |
| `caption` | str | texto de `h2.modal-body__caption` (ex.: "Localizar e unir duplicatas — 3 de 42.761") |
| `pode` | bool | `button.js-merge-start` visível |
| `progresso` | str | texto de `h2.progress__header` |
| `navegou` | bool | a leitura falhou por navegação/fechamento/timeout (os outros campos ficam vazios) |

"Visível" = `elemento.offsetParent !== null`.

### `Resultado` (`fluxo.Resultado`)

`SUCESSO`, `INCERTO`, `AGUARDA`, `ERRO` — ver a tabela de decisão em
[arquitetura §6](arquitetura.md#6-regra-pura-de-término-de-uma-união).

### Contadores do motor (`Merger`)

`cliques` (cliques em Unir disparados — **é o que o limite conta**), `confirmadas`, `incertas` (não confirmadas,
inclusive cliques que falharam e a união pendente numa parada forçada), `erros`, `avisos`, `total`, `motivo`.

## 4. Variáveis de ambiente

Levantadas com busca por `environ`/`getenv` em `src/`, `scripts/`, `.github/` e `packaging/`.

### Lidas pelo aplicativo

| Variável | Onde | Efeito |
|---|---|---|
| `KOMMO_DATA_DIR` | `paths.py` | muda a raiz de dados (ver §1.1) |
| `KOMMO_BROWSER` | `browser.py` | restringe a um canal: `chrome`, `msedge` ou `chromium` (sem diferenciar maiúsculas). Valor inválido → `NavegadorIndisponivel` ("KOMMO_BROWSER='…' não é válido…"). Lembre: cada canal tem **seu** perfil |
| `KOMMO_DEBUG` | `merger.py` (`debug_ligado()`) | só `1`, `true`, `yes`, `on` ligam (sem diferenciar maiúsculas; espaços ignorados); `0`, `false`, vazio etc. não ligam. Ligado: salva `data/debug/<rótulo>.png` nos diagnósticos |
| `PLAYWRIGHT_BROWSERS_PATH` | `browser.py` | se já definida, é respeitada; senão, no `.exe` Windows, o app a define como `%LOCALAPPDATA%\ms-playwright` |
| `LOCALAPPDATA` | `browser.py` | base do caminho acima (padrão `~\AppData\Local`) |

### Lidas por scripts de build/verificação

| Variável | Onde | Efeito |
|---|---|---|
| `KOMMO_TERMOS_SENSIVEIS` | `scripts/verificar_privacidade.py` | termos extras (separados por vírgula) |
| `USERPROFILE` / `HOME` | `scripts/verificar_privacidade.py` | caminho da home vira termo sensível |
| `SOURCE_DATE_EPOCH` | `scripts/empacotar.py` | data fixa dentro do zip/tar.gz (padrão 2020-01-01) |
| `SEM_INSTALAR` | `scripts/build_linux.sh` | não instala dependências (equivale a `-SemInstalar` do `.ps1`) |
| `APPIMAGETOOL` | `scripts/build_linux.sh` | caminho do `appimagetool` |
| `APPIMAGE` | `packaging/linux/AppRun` | caminho do `.AppImage` (definido pelo runtime do AppImage); usado para definir `KOMMO_DATA_DIR` |

Os scripts também **definem** `PYTHONDONTWRITEBYTECODE=1` e `PIP_DISABLE_PIP_VERSION_CHECK=1`.

## 5. Códigos de saída

### Modo CLI (`python main.py --cli …` / `KommoUnirDuplicatas.exe --cli …`)

| Código | Quando (`cli.main`) |
|---|---|
| `0` | motivo `limite`, `sem_duplicatas` ou `ensaio` **e** nenhum `LogEvt` de nível `erro` |
| `2` | motivo `parado`, `forcado`, `recusado` ou `sem_resposta` |
| `64` | erro de uso (`EX_USAGE`): argumentos do `argparse` inválidos — subdomínio inválido, tipo fora de `leads`/`contatos`, quantidade inválida, opção desconhecida, argumento faltando (`cli.Parser.error`). Antes era `2` e colidia com o código de parada |
| `1` | qualquer outro motivo, ou motivo "ok" com erros registrados, ou o processo terminou sem `FimEvt` |

> No `.exe` gerado com `--windowed`, o Windows não anexa console: a saída do modo CLI pode não aparecer no
> terminal. **Não validado** com o executável; o modo CLI foi testado a partir do código-fonte (`tests/test_cli.py`).

### Modo janela

`ui.main()` devolve `1` quando a pasta de dados não é gravável (a janela nem abre) e `0` caso contrário;
`__main__.main()` **propaga** esse código para o processo (`tests/test_main.py::test_sem_argumentos_abre_ui_e_propaga_codigo`).
`--help`/`-h` mostra o uso e sai com `0` sem abrir a janela.

### Scripts

`scripts/verificar_privacidade.py`: `0` limpo, `1` achados/erro de leitura/uso inválido.
`scripts/build_windows.ps1` / `build_linux.sh`: `0` sucesso, `1` falha (inclusive verificação de privacidade).
`.github/scripts/verificar_links.py`: `0` ok, `1` link quebrado.

## 6. Formato do log

Arquivo `data/logs/AAAA-MM-DD.log` (data local do momento da escrita), UTF-8, modo *append*:

```text
[13/10/2026 15:04:05]       Abrindo a lista de Contatos: https://a***e.kommo.com/contacts/list/contacts/?skip_filter=Y
[13/10/2026 15:04:20] AVISO Faça login na janela do Kommo — o app continua sozinho depois.
[13/10/2026 15:05:02] OK    Login confirmado (a***e.kommo.com).
[13/10/2026 15:06:11] ERRO  União 3/100: sem resultado em 120s (falha 1/3).
```

- Prefixo (6 caracteres): `ERRO  `, `AVISO `, `OK    ` ou 6 espaços (`info`).
- Caracteres de controle (`\x00-\x1f`, `\x7f-\x9f`, inclusive quebras de linha e ESC) viram espaço.
- Linhas com mais de 2000 caracteres são truncadas com `… [+N caracteres]`.
- **Rotação:** no primeiro `gravar` de cada processo, apaga arquivos cujo **nome** é `AAAA-MM-DD.log` com data
  anterior a hoje − 30 dias. Outros arquivos da pasta não são tocados.
- **Fail-safe:** se não der para gravar, a linha ainda aparece na tela e o motivo fica em `logs.ultimo_erro`.
- **Máscara:** UI e CLI gravam a linha **já mascarada** quando a privacidade está ligada (subdomínio → `a***e`,
  totais → `••••`; regra única em `mascara.py`). Com privacidade desligada (`--sem-privacidade` na CLI) aparecem
  em claro.

## 7. Dados sensíveis e como limpar

| Onde | O que contém | Sensibilidade | Como limpar |
|---|---|---|---|
| `data/profile/<canal>/` | perfil completo do navegador: **cookies da sessão do Kommo**, armazenamento local, cache de páginas (pode conter dados de clientes), histórico | **Alta** — com os cookies, outra pessoa pode entrar na conta | botão **"Esquecer login salvo"** (apaga `data/profile/*`, recusa links e itens fora da raiz) com o navegador do app fechado; ou apagar a pasta à mão |
| `data/config.json` | subdomínio da empresa, preferências, último total de duplicatas e data | Média (identifica a empresa) | apagar o arquivo (o app recria com padrões) |
| `data/logs/*.log` | horários, contadores, URL da lista, mensagens de erro (até 300 caracteres da exceção), textos de progresso do Kommo, diagnóstico **estrutural** (sem texto de clientes). Com privacidade desligada (janela ou `--sem-privacidade`): subdomínio e totais em claro | Média | apagar os arquivos; apagados automaticamente após 30 dias |
| `data/debug/*.png` | captura da tela do navegador. Com privacidade **ligada** o reforço é aplicado antes da captura; com privacidade **desligada**, mostra nomes/telefones de clientes | **Alta** | apagar a pasta `debug/`; não definir `KOMMO_DEBUG` sem necessidade |
| `data/config.json.corrompido` | cópia do config inválido | Média | apagar |
| `%LOCALAPPDATA%\ms-playwright` | Chromium do Playwright (se o usuário instalou) | Baixa (não tem dados da conta) | `python -m playwright uninstall` ou apagar a pasta |

O app **não guarda senhas nem tokens**. Desinstalar = fechar o app e o navegador aberto por ele e apagar a pasta do
programa (que contém `data/`), ou a pasta apontada por `KOMMO_DATA_DIR` se ela estiver fora
([instalação](../operations/instalacao.md)).
