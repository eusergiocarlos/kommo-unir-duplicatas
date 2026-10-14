# Política de segurança

## Versões suportadas

Só a **última versão publicada** na página de Releases recebe correções de segurança. Versões antigas não são
corrigidas: atualize.

| Versão | Suporte |
|---|---|
| Última release | ✅ |
| Anteriores | ❌ |

## Como relatar uma vulnerabilidade

**Não abra issue pública** para falhas de segurança.

Use o **aviso privado do GitHub** (Private Vulnerability Reporting): na aba **Security** do repositório, clique
em **Report a vulnerability**. O relato fica visível só para os mantenedores.

> Para o mantenedor: o recurso precisa estar **ativado** em *Settings → Code security → Private vulnerability
> reporting* (ver [docs/operations/ci-cd.md](docs/operations/ci-cd.md)). Enquanto não estiver, abra uma issue
> **sem nenhum detalhe técnico** pedindo um canal privado, e aguarde o contato.

Inclua no relato (sem dados reais de clientes — mascare subdomínio, nomes, telefones e e-mails):

- versão do app e forma de uso (`.zip`, `.exe`, código-fonte, Linux);
- o que um atacante consegue fazer e em que condições;
- passos para reproduzir, de preferência sem precisar de uma conta Kommo real.

### Prazos-alvo

São **metas**, não um SLA (o projeto é mantido por voluntários):

| Etapa | Meta |
|---|---|
| Confirmar o recebimento | até 7 dias |
| Triagem inicial (confirmar ou descartar, avaliar gravidade) | até 14 dias |
| Correção | conforme a gravidade; você é avisado do andamento |

### Divulgação coordenada

- Pedimos que você **não divulgue** detalhes até haver uma correção publicada (ou até combinarmos uma data).
- Depois da correção publicamos um *security advisory* no GitHub descrevendo o problema e a versão corrigida.
- Damos crédito a quem relatou, se você quiser.

## Escopo

**Dentro do escopo:**

- o aplicativo (`src/kommo_duplicatas/`) e o `main.py`;
- os pacotes publicados nos Releases (`.zip`/`.exe` do Windows, `.tar.gz`/AppImage do Linux) e o `SHA256SUMS.txt`;
- os scripts de build, empacotamento e verificação (`scripts/`) e os workflows (`.github/`).

**Fora do escopo** (relate ao fornecedor correspondente):

- vulnerabilidades do **Kommo** (o serviço/site em si);
- vulnerabilidades do **Google Chrome, Microsoft Edge, Chromium** ou do **Playwright**;
- problemas que exigem acesso prévio de administrador à máquina do usuário ou à pasta de dados dele.

## Modelo de ameaça (resumo)

- O app **controla um navegador logado no CRM** do usuário. Quem consegue executar código na máquina enquanto o
  app roda tem o mesmo poder que o usuário logado no Kommo.
- **A união de duplicatas é irreversível.** Um defeito ou uso indevido pode unir registros errados; por isso o
  app pede a confirmação de **toda** execução mostrando a conta realmente logada antes do 1º clique em "Unir"
  (na janela, para "Todas" ou mais de 500 o botão só libera depois de digitar `UNIR`; no modo texto, `[s/N]` ou
  `--sim`), oferece o **modo ensaio** (não une nada) e recomenda testar com poucos registros.
- **Dados sensíveis ficam na pasta de dados** (`data/` ao lado do programa no modo portátil, ou a pasta
  definida em `KOMMO_DATA_DIR`): o **perfil do navegador com os cookies da sessão**, configuração (subdomínio) e
  logs. (Histórico: a versão 1.0.0 usava `%APPDATA%\KommoUnirDuplicatas\`; a versão atual não lê nem grava lá.) **Não compartilhe, não sincronize e não envie essa pasta** — com os cookies,
  outra pessoa pode entrar na conta.
- O app não tem servidor próprio, telemetria nem envia dados a terceiros: fala só com `https://<empresa>.kommo.com`
  pelo navegador.
- O **modo privacidade** borra dados na tela para gravação/apresentação. Ele **não é garantia absoluta**: telas
  não mapeadas podem mostrar dados e a barra de endereço mostra o subdomínio. Confira antes de gravar.
- O build roda `scripts/verificar_privacidade.py` (fail-closed) para impedir que dados da máquina de build ou da
  empresa entrem nos pacotes.

## Recomendações a quem usa

- **Baixe só da página de Releases** deste repositório. Não use cópias repassadas por terceiros.
- **Confira o SHA-256** do arquivo com o `SHA256SUMS.txt` do mesmo Release:
  - Windows (PowerShell): `Get-FileHash .\arquivo.zip -Algorithm SHA256`
  - Linux: `sha256sum -c SHA256SUMS.txt --ignore-missing`
- Mantenha **Chrome/Edge atualizados** (o app usa o navegador instalado).
- **Sem assinatura de código (Authenticode):** o Windows SmartScreen pode avisar "editor desconhecido" e alguns
  antivírus marcam executáveis do PyInstaller como suspeitos (**falso positivo** conhecido). Só prossiga se o
  hash conferir. Se o antivírus bloquear, prefira enviar o arquivo para análise do fornecedor do antivírus a
  desativá-lo.
- Não rode o app com uma conta de administrador do Windows sem necessidade.

## Licença

O repositório traz um arquivo [LICENSE](LICENSE) (MIT); a licença ainda está **a confirmar** pelo dono do projeto.
