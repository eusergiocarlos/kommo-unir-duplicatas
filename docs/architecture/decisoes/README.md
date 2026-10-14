# Registro de decisões de arquitetura (ADRs)

Cada arquivo registra **uma** decisão: contexto, decisão, alternativas consideradas, consequências e status.
Decisões tomadas antes deste registro foram documentadas retroativamente em 2026-10, conferidas no código atual.

| ADR | Decisão | Status |
|---|---|---|
| [ADR-0001](ADR-0001-automacao-por-navegador.md) | Automação por navegador (Playwright) em vez da API do Kommo | aceita |
| [ADR-0002](ADR-0002-python-tkinter-playwright-sync.md) | Python + Tkinter + Playwright (API síncrona) | aceita |
| [ADR-0003](ADR-0003-porta-kommo-e-regra-pura.md) | Porta `PortaKommo` e regra pura de término (`fluxo.avaliar_uniao`) | aceita |
| [ADR-0004](ADR-0004-confirmacao-por-texto-e-contagem-por-cliques.md) | Confirmação pelo texto "concluída" e contagem por cliques (limite nunca ultrapassado) | aceita — risco aberto em Leads |
| [ADR-0005](ADR-0005-modo-portatil-data-ao-lado.md) | Modo portátil com `data/` ao lado do app (sem `%APPDATA%`) | aceita |
| [ADR-0006](ADR-0006-perfil-por-canal-navegador-do-sistema.md) | Perfil por canal e uso do Chrome/Edge do sistema | aceita |
| [ADR-0007](ADR-0007-privacidade-init-script-observer.md) | Modo privacidade por init script + MutationObserver | aceita |
| [ADR-0008](ADR-0008-pyinstaller-onedir-zip.md) | PyInstaller onedir zipado como formato principal no Windows | aceita |
| [ADR-0009](ADR-0009-verificador-privacidade-fail-closed.md) | Verificador de privacidade fail-closed | aceita |
| [ADR-0010](ADR-0010-confirmacao-de-conta-e-ensaio.md) | Confirmação da conta e ensaio antes de operação irreversível | aceita |
| [ADR-0011](ADR-0011-sem-telemetria-auto-update-sla.md) | Sem telemetria, sem atualização automática, sem SLA | aceita |

## Como propor uma nova decisão

1. Copie a estrutura de um ADR existente para `ADR-00NN-titulo-curto.md` (próximo número livre).
2. Preencha **Contexto**, **Decisão**, **Alternativas consideradas**, **Consequências** e **Status/Data**.
3. Se substituir uma decisão anterior, marque a antiga como "substituída por ADR-00NN" (não apague).
4. Acrescente a linha nesta tabela e, se a arquitetura mudar, atualize [arquitetura.md](../arquitetura.md).
