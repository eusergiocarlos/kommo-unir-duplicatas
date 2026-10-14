# Changelog

Todas as mudanças relevantes deste projeto são registradas aqui. O formato segue o
[Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o projeto usa
[versionamento semântico](https://semver.org/lang/pt-BR/).

## [Não lançado]

Rodada de profissionalização: motor reescrito com foco em segurança da união (irreversível), modo portátil,
privacidade reforçada, build reproduzível, CI/CD e documentação.

### Adicionado

- **Confirmação da conta antes da 1ª união:** diálogo com conta, tipo, total informado pelo Kommo e quantidade
  pedida (com privacidade, a conta aparece mascarada até "Mostrar conta"). Para "Todas" ou mais de 500, é
  preciso digitar `UNIR`. No modo texto: pergunta `[s/N]` ou `--sim`.
- **Ensaio** ("Só simular (não une nada)" na interface, `--ensaio` no modo texto): abre o modal, confere conta,
  lista e modal e encerra sem clicar em "Unir".
- **Esquecer login salvo:** apaga só `data/profile/*`, recusando caminhos fora da pasta de dados e links.
- **PARAR em dois níveis:** o 1º pedido para entre uniões; o 2º (FORÇAR PARADA, ou Ctrl+C duas vezes) aborta na
  hora. Fechar a janela com execução em andamento pede a parada e espera a união terminar.
- **Validação da quantidade** (`limite.py`): aceita separador de milhar, `0` = todas, máximo 999.999; recusa
  negativos, decimais, letras e caracteres invisíveis com mensagem em português.
- **Modo texto** com `--ensaio`, `--sim`, `--sem-privacidade` e códigos de saída (0 ok, 2 parado/recusado,
  1 erro, 64 erro de uso). Com privacidade (padrão), terminal e log saem mascarados como na janela; na pergunta de
  confirmação, `m` mostra a conta só no terminal.
- **`--help`/`-h`** no ponto de entrada (`python main.py --help`): mostra as formas de uso sem abrir a janela.
- **Troca de aba durante o login (T10):** se o login/redirecionamento fechar ou substituir a aba do Kommo, o
  motor adota outra aba aberta do mesmo contexto (de preferência em `*.kommo.com`) e continua; "navegador
  fechado" só quando não sobra nenhuma aba (com 3 s de tolerância). Testes em `tests/test_t10_troca_de_aba.py` e
  `test_t10_*` de `tests/test_merger.py`.
- **Cobertura de testes:** `pytest-cov` em `requirements-dev.in`/`.lock`; o CI mede e publica `coverage.xml`.
- **Verificador de links** da documentação (`.github/scripts/verificar_links.py`) e gerador de notas de release.
- **CI/CD** (GitHub Actions): lint com ruff, testes em Windows e Linux, `pip-audit`, `detect-secrets`,
  verificador de privacidade, revisão de dependências, links; workflow de release que gera **rascunho** com
  SBOM e atestação de proveniência; Dependabot; modelos de issue e PR.
- `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `CLAUDE.md`.
- Documentação em `docs/`: requisitos funcionais e não funcionais, SLO, arquitetura, jornadas, modelo de dados,
  decisões, instalação, execução, build e distribuição, recuperação de falhas, estratégia de testes,
  rastreabilidade e segurança.
- Suíte de testes ampliada (453 testes), com falsos do Kommo e do relógio (`tests/fakes.py`) e testes do
  JavaScript em Chromium headless contra fixtures HTML anonimizadas.
- Scripts de Linux (`iniciar.sh`, `scripts/build_linux.sh`, `packaging/linux/`) — **não testados**.

### Alterado

- **Dados em modo portátil:** configuração, logs e perfil do navegador passam a ficar em
  `<pasta do programa>/data` (em código-fonte, a raiz do repositório), e **não mais em
  `%APPDATA%\KommoUnirDuplicatas`**. A pasta antiga não é lida: **quem usava a 1.0.0 precisa entrar no Kommo de
  novo** e refazer as preferências. Se `data/` não for gravável, o app mostra o erro e a solução (mover a pasta
  ou definir `KOMMO_DATA_DIR`) em vez de usar outra pasta em silêncio. `KOMMO_DATA_DIR` relativo é resolvido a
  partir da pasta do programa.
- **Motor reescrito** sobre a porta `PortaKommo` (`KommoPage` real; falsos nos testes) e a regra pura
  `fluxo.avaliar_uniao`, com relógio injetável.
- **Contagem de uniões:** a união conta como feita quando o Kommo mostra "concluída" **ou** quando, depois do
  clique, o modal fecha/recarrega ou o contador do título avança (em Leads o Kommo não mostra "concluída").
  Só fica "não confirmada" o caso ambíguo: o mesmo grupo volta após o progresso, sem erro.
- **O limite passa a contar cliques** em "Unir" (confirmados + não confirmados): nunca mais do que o pedido.
- **Validações antes de cada clique:** hostname exato da empresa, caminho coerente com o tipo e modal de
  duplicatas; "sem duplicatas" só com a sessão ainda logada e sem erro pendente.
- **Perfil do navegador por canal** (`data/profile/chrome`, `msedge`, `chromium`); o canal que funcionou é
  lembrado; perfil em uso gera mensagem clara em vez de tentar outro navegador com o mesmo login.
- **Modo privacidade** passa a ser um init script registrado no contexto (cobre login e primeira carga) com
  `MutationObserver`, título da aba travado, `title` de tooltips retirado e notificações da página neutralizadas;
  na janela do app, subdomínio e totais são mascarados (também no log em arquivo).
- **Build oficial:** pasta portátil (PyInstaller onedir) zipada, `KommoUnirDuplicatas-<versão>-win64.zip`, com
  `SHA256SUMS.txt` e zip determinístico, em `dist\windows\` (`scripts/build_windows.ps1`). O `.exe` único virou
  opção (`-OneFile`; `scripts/build_exe.ps1` agora gera em `dist\windows\`).
- **Dependências travadas** em `requirements.lock` / `requirements-dev.lock` com hashes (instalação com
  `--require-hashes`); `iniciar.bat` usa o `.venv` local e o lock.
- **Configuração** com gravação atômica; arquivo corrompido é guardado como `config.json.corrompido`; campo com
  tipo errado (ex.: `"limite": "abc"`) volta ao padrão só nele, com aviso, sem impedir a janela de abrir.
- **Código de saída da janela propagado:** `1` quando a pasta de dados não é gravável (antes saía sempre `0`).
- **Erros de uso da CLI saem com 64** (EX_USAGE) em vez de 2, que significa parado/recusado/sem resposta.
- **`KOMMO_DEBUG`:** só `1`, `true`, `yes`, `on` ligam (antes qualquer valor não vazio, inclusive `0`).
- **Interno:** máscaras de privacidade num módulo comum (`mascara.py`, usado por janela e CLI); `privacy.py`
  importa os seletores do processo de `kommo.SELETORES` (sem cópia); removidos `paths.temp_dir()` e
  `limite.precisa_confirmar`/`LIMITE_CONFIRMAR` (sem uso); configurações do VS Code separam ensaio de união real.

### Segurança

- Navegador aberto com `chromium_sandbox=True`, notificações e pedidos de permissão negados.
- **Diagnóstico sem dados de clientes:** o log recebe só um resumo estrutural do modal; capturas de tela apenas
  com `KOMMO_DEBUG`.
- **Logs sanitizados** (caracteres de controle removidos, linhas truncadas) e **rotação** (logs com mais de 30
  dias são apagados).
- **Verificador de privacidade fail-closed:** varre bytes de todos os arquivos e o conteúdo de zip, tar.gz,
  executáveis do PyInstaller e AppImage; o que não conseguir ler vira erro; termos mascarados na saída. O build
  falha se houver achados.
- Política de segurança com canal privado de relato e modelo de ameaça (`SECURITY.md`).

## [1.0.0]

- Primeira versão: unir duplicatas de **Leads** e **Contatos** em qualquer conta `*.kommo.com`.
- Quantidade 100 / 200 / 500 / todas / valor livre; contador, barra de progresso e resumo final com o total da conta.
- Log com data e hora (tela + arquivo diário).
- **Modo privacidade** (antes "modo gravação"): borra dados sensíveis para gravar a tela.
- Perfil/config/logs em `%APPDATA%\KommoUnirDuplicatas`; nada da empresa dentro do projeto ou do `.exe`.
- Empacotamento em `.exe` (PyInstaller) e script de verificação de privacidade.
