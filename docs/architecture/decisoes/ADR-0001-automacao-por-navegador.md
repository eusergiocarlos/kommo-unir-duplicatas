# ADR-0001 — Automação por navegador (Playwright) em vez da API do Kommo

- **Status:** aceita
- **Data:** 2026-10 (registro retroativo de decisão tomada na v1.0.0)

## Contexto

O recurso "Localizar e unir duplicatas" do Kommo vive na **interface** (menu "⋯" das listas de Leads e de
Contatos): um modal mostra um grupo por vez e a pessoa clica em "Unir esta duplicata". O objetivo é repetir esse
fluxo milhares de vezes com o **mesmo resultado** que o usuário teria à mão, em qualquer conta
`https://<empresa>.kommo.com`, sem exigir configuração técnica do usuário.

Não foi encontrado, na API pública do Kommo, um equivalente direto a esse fluxo (busca de grupos de duplicatas +
união com as regras de mesclagem da interface). Usar a API exigiria também criar uma integração, obter tokens e
reimplementar regras de mesclagem de campos — com risco de resultado diferente do da interface.
*Esta avaliação da API foi feita na v1 e não foi revalidada nesta documentação.*

## Decisão

Automatizar a **interface web** com **Playwright**, num navegador real com o **perfil persistente** do app
(login feito pelo próprio usuário na janela do navegador). Tudo que depende do HTML fica isolado em
`src/kommo_duplicatas/kommo.py` (`Seletores`, JS de leitura, `KommoPage`) e documentado em
[KOMMO_DOM.md](../../KOMMO_DOM.md).

## Alternativas consideradas

| Alternativa | Por que não |
|---|---|
| API REST do Kommo | sem equivalente direto ao fluxo da interface (avaliação da v1); exigiria integração/token e reimplementar a mesclagem |
| Extensão de navegador | instalação mais difícil para o usuário final, publicação em lojas, sem janela própria de controle |
| Selenium | Playwright oferece contexto persistente, esperas por estado e driver embutível mais simples |
| Gravação de macro (cliques por coordenada) | frágil, sem leitura de estado, sem validações de segurança |

## Consequências

- **+** Mesmo comportamento da interface; nenhuma credencial de API; o app nunca vê a senha.
- **+** Validações fortes possíveis antes de cada clique (hostname exato, caminho, título do modal).
- **−** Quebra quando o Kommo muda o HTML → ajuste localizado em `kommo.py` + `KOMMO_DOM.md` + fixtures.
- **−** Lento (uma união por vez, ~2–7 s observados) e dependente do navegador instalado ([ADR-0006](ADR-0006-perfil-por-canal-navegador-do-sistema.md)).
- **−** Pode depender de termos de uso do Kommo sobre automação — responsabilidade de quem usa (aviso no README).
- **−** Testes reais exigem uma conta; por isso a porta de testes ([ADR-0003](ADR-0003-porta-kommo-e-regra-pura.md)).
