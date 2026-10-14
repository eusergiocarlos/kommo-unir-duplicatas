# ADR-0011 — Sem telemetria, sem atualização automática, sem SLA

- **Status:** aceita
- **Data:** 2026-10

## Contexto

O app roda na máquina do usuário com um navegador logado no CRM da empresa, que contém dados pessoais de clientes
(LGPD/GDPR). É um projeto pequeno, mantido por voluntários, sem servidor próprio.

## Decisão

- **Sem telemetria:** o app não envia nada a servidores próprios ou de terceiros; o único tráfego é o do
  navegador com `https://<empresa>.kommo.com` (e o que o próprio Kommo carregar). Logs e diagnósticos ficam só em
  `data/` (o diagnóstico é estrutural, sem texto de clientes).
- **Sem atualização automática:** nenhuma verificação de versão nem download. Atualizar = baixar a nova versão
  nos Releases, conferir o SHA-256 e substituir a pasta (preservando `data/` se quiser manter o login).
- **Sem SLA:** prazos de segurança são **metas** ([SECURITY.md](../../../SECURITY.md)); objetivos de
  confiabilidade estão em [docs/operations/slo.md](../../operations/slo.md).

## Alternativas consideradas

| Alternativa | Por que não |
|---|---|
| Telemetria opcional de erros | exige servidor, política de dados e consentimento; risco de vazar dados do CRM em mensagens de erro |
| Auto-update | exige infraestrutura e assinatura de código confiável; um update comprometido teria acesso ao CRM logado |
| Aviso de nova versão (consulta à API do GitHub) | seria o único tráfego fora do Kommo; adiado para manter a garantia simples |

## Consequências

- **+** Garantia simples e verificável de privacidade; nada para operar no servidor.
- **−** Falhas só são conhecidas se o usuário relatar (com o log, mascarado).
- **−** Usuários podem ficar em versões antigas com seletores quebrados ou correções de segurança faltando.
- **−** Sem compromisso de prazo de suporte.
