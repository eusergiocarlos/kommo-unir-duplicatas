# ADR-0010 — Confirmação da conta e ensaio antes de uma operação irreversível

- **Status:** aceita (substitui a confirmação prévia de "Todas" feita só pela UI na v1.0.0)
- **Data:** 2026-10

## Contexto

Duplicatas unidas não podem ser separadas. O perfil persistente pode estar logado numa conta **diferente** da que
o usuário pensa (várias empresas, login antigo), e a UI só conhece o subdomínio digitado — não a conta realmente
aberta no navegador. Perguntar "tem certeza?" antes de abrir o navegador confirma o que foi digitado, não o que vai
ser afetado.

## Decisão

- A confirmação é emitida **pelo motor**, depois do login, das validações de hostname/caminho e da abertura do
  modal: `ConfirmarEvt(host, tipo, total, limite, ensaio)`. O motor fica bloqueado até `responder()`, parada ou
  `TEMPO_CONFIRMACAO` (600 s → motivo `sem_resposta`). Recusa → motivo `recusado`. Nada é clicado antes disso.
- UI (`DialogoConfirmacao`): mostra conta, tipo, grupos na conta e quantidade; **"Cancelar" é o padrão** (foco
  inicial; Enter, Esc e X cancelam); "Unir agora" só por clique/Espaço; para "todas" ou mais de 500
  (`LIMITE_EXIGE_DIGITAR`) é preciso digitar **UNIR**. Com privacidade, conta/total mascarados com "Mostrar conta".
- CLI: pergunta `[s/N]` (vazio/EOF = não); `--sim` responde sim.
- **Ensaio** (`Job.ensaio`, "Só simular", `--ensaio`): faz tudo, inclusive a confirmação, e encerra sem clicar
  (motivo `ensaio`). Não é persistido: cada abertura começa no modo real.
- Validações antes de **cada** clique: hostname exato, caminho do tipo, título do modal com "duplicat".

## Alternativas consideradas

| Alternativa | Por que não |
|---|---|
| Confirmar na UI antes de iniciar | confirma o digitado, não a conta logada; era o modelo antigo |
| Confirmar só "Todas" | erros de conta também são graves com 100 uniões |
| Sem confirmação, só ensaio opcional | deixa a barreira a critério da memória do usuário |
| Confirmar a cada N uniões | interrompe execuções longas sem ganho (a conta não muda no meio; as validações por clique cobrem redirecionamentos) |

## Consequências

- **+** O usuário vê a conta **realmente logada** antes do primeiro clique; o caminho padrão (Enter) é seguro.
- **+** Testado em `tests/test_merger.py` (sem resposta, recusa, aceite, parada durante a confirmação) e
  `tests/test_ui_integracao.py` (X, Esc/Enter, digitar UNIR, resposta única).
- **−** Uma interação obrigatória por execução; automação sem supervisão exige `--sim` (remove a barreira).
- **−** Com privacidade ligada, o usuário precisa clicar "Mostrar conta" para conferir de fato.
- `limite.precisa_confirmar`/`LIMITE_CONFIRMAR = 20` (regra antiga, sem uso depois desta decisão) foram removidos do
  código na T11.
