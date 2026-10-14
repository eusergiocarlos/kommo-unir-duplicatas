# Execução (uso diário)

Como usar o app no dia a dia, pela janela ou pelo terminal. Conferido no código atual (`ui.py`, `cli.py`,
`merger.py`, `browser.py`, `paths.py`). Jornadas detalhadas com mensagens reais: [jornadas](../architecture/jornadas.md).

> A união é **irreversível**. Comece sempre com **ensaio** e com um número pequeno (ex.: 3) numa conta que você
> possa conferir.

## 1. Pela janela

1. Abra `KommoUnirDuplicatas.exe` (ou `python main.py` / `iniciar.bat`).
2. **Empresa:** o subdomínio (`minhaempresa`, `minhaempresa.kommo.com` ou a URL completa). Com o modo privacidade
   ligado, o campo mostra `m***a` quando não está em edição.
3. **O que unir:** "Leads" ou "Apenas contatos".
4. **Quantas uniões:** 100 · 200 · 500 · Todas, ou "outro valor" (0 = todas; aceita `1.000`/`1 000`; máximo
   999.999; sem decimais/negativos). Ao lado aparece "→ vale N" ou "valor inválido".
5. **Modo privacidade** (salvo nas preferências) e **Só simular** (não salvo).
6. **INICIAR** / **SIMULAR** (ou Enter fora de um botão).
7. Se pedido, faça login na janela do navegador; o app continua sozinho.
8. Confira o diálogo **"Confira a conta antes de unir"** (com privacidade, use "Mostrar conta"). "Cancelar" é o
   padrão; para "Todas" ou mais de 500 é preciso digitar **UNIR**.
9. Acompanhe: contador = uniões **confirmadas**; barra = cliques em Unir / limite; o log mostra cada união.
10. **PARAR** termina a união em andamento e para; um 2º clique (**FORÇAR PARADA**) aborta na hora.
11. Resumo: confirmadas, não confirmadas ("confira no Kommo"), cliques, motivo, tempo, erros/avisos.

Outros controles: **"Esquecer login salvo"** (apaga `data/profile/`, só sem execução em andamento); o rótulo
"Navegador: …" mostra o último navegador usado.

## 2. Pelo terminal (CLI)

Sintaxe (`cli.py`):

```text
python main.py --cli <empresa> {leads|contatos} <quantidade> [--sem-privacidade] [--ensaio] [--sim]
```

| Argumento | Efeito |
|---|---|
| `<empresa>` | subdomínio (inválido → erro de uso, código 64) |
| `leads` / `contatos` | tipo de lista |
| `<quantidade>` | inteiro ≥ 0; `0` = todas (aqui **não** se aceita `1.000`) |
| `--sem-privacidade` | não borra nada no navegador e mostra subdomínio/totais em claro no terminal e no log |
| `--ensaio` | abre o modal, confere e não une |
| `--sim` | confirma a conta sem perguntar (**remove a última barreira humana**) |

Exemplos reais (do docstring de `cli.py`):

```text
python main.py --cli minhaempresa contatos 10
python main.py --cli minhaempresa leads 0 --sem-privacidade     (0 = todas)
python main.py --cli minhaempresa leads 3 --ensaio              (abre e confere, não une nada)
python main.py --cli minhaempresa contatos 10 --sim              (confirma a conta sem perguntar)
```

- Sem `--sim`, o terminal pergunta "Confirma? [s/N]" (só `s`/`sim`/`y`/`yes` confirmam). Com privacidade a
  pergunta é "Confirma? [s/N, m = mostrar a conta]": `m` mostra a conta e o total em claro só no terminal.
- Ctrl+C uma vez: para depois da união em andamento; duas vezes: força.
- Códigos de saída: `0` ok (limite, sem duplicatas, ensaio, sem erros) · `2` parado/recusado/sem resposta ·
  `64` erro de uso (argumento inválido, subdomínio inválido, opção desconhecida — EX_USAGE) · `1` demais casos
  ([modelo de dados §5](../architecture/modelo-de-dados.md#5-códigos-de-saída)).
- Com privacidade (padrão), a CLI **mascara** o que imprime e o que grava no log (subdomínio `a***e`, totais
  `••••`), com a mesma regra da janela (`mascara.py`). A CLI não grava as preferências da janela.
- Com o `.exe` (compilado `--windowed`), a saída no console **não foi validada**; prefira o código-fonte para a CLI.

## 3. Variáveis de ambiente

| Variável | Uso | Exemplo (PowerShell) |
|---|---|---|
| `KOMMO_DATA_DIR` | outra pasta de dados (relativa = relativa à pasta do programa) | `$env:KOMMO_DATA_DIR = "C:\Users\voce\KommoDados"` |
| `KOMMO_BROWSER` | forçar `chrome`, `msedge` ou `chromium` (cada um tem seu perfil → novo login) | `$env:KOMMO_BROWSER = "msedge"` |
| `KOMMO_DEBUG` | salvar capturas em `data/debug/` nos diagnósticos; só `1`, `true`, `yes`, `on` ligam (sem diferenciar maiúsculas); `0`, `false`, vazio etc. **não** ligam | `$env:KOMMO_DEBUG = "1"` |
| `PLAYWRIGHT_BROWSERS_PATH` | onde procurar o Chromium do Playwright (o `.exe` define `%LOCALAPPDATA%\ms-playwright` se vazia) | — |

Para remover no PowerShell: `Remove-Item Env:KOMMO_DEBUG`. Para valer em toda abertura do `.exe`, defina como
variável de ambiente do usuário nas configurações do Windows.

## 4. Dicas de limites e tempos

| Situação | Valor no código | Dica |
|---|---|---|
| Busca de duplicatas (cada ciclo) | até 90 s (`TEMPO_BUSCA`) | a primeira busca em contas grandes é a mais lenta (observado 10–45 s) |
| Uma união | até 120 s (`TEMPO_UNIAO`) | observado ~2–7 s; PARAR pode esperar até esse teto |
| Login | até 10 min (`TEMPO_LOGIN`), aviso a cada 60 s | depois disso, inicie de novo |
| Confirmação da conta | até 10 min (`TEMPO_CONFIRMACAO`) | sem resposta → nada é unido |
| "Algo deu errado" | 5× "Tentar novamente" + 1 reabertura por ciclo | persistindo, espere alguns minutos |
| Falhas seguidas | 3 (`FALHAS_MAX`) | o app para sozinho |
| "Digitar UNIR" | Todas ou > 500 | proteção contra confirmar no automático |

- Execuções longas ("Todas") podem levar horas; mantenha o computador ligado e sem suspensão (o app não impede a
  suspensão — não há código para isso).
- **Não use** a janela do navegador do app durante a execução (navegar para outra página aborta por segurança).
- Em Leads, uniões podem aparecer como "não confirmadas" (texto de conclusão não validado —
  [ADR-0004](../architecture/decisoes/ADR-0004-confirmacao-por-texto-e-contagem-por-cliques.md)); confira na conta.
- Rodar de novo é seguro: o app não guarda fila própria; o Kommo mostra os grupos restantes.

## 5. Onde ficam os logs

- Janela: o painel "LOG" mostra as mesmas linhas gravadas em arquivo (mascaradas com privacidade ligada).
- Arquivo: `<pasta do programa>\data\logs\AAAA-MM-DD.log` (ou `KOMMO_DATA_DIR\logs\`). Um por dia; arquivos com
  mais de 30 dias são apagados na primeira gravação de cada execução.
- Formato e conteúdo: [modelo de dados §6](../architecture/modelo-de-dados.md#6-formato-do-log). Ao relatar um
  problema, envie o trecho do log **conferindo que não há subdomínio nem dados de clientes**.
