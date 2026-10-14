## O que muda

<!-- Descreva a mudança e o motivo. Se resolve uma issue, cite: "Resolve #123". -->

## Tipo

- [ ] Correção de bug
- [ ] Nova funcionalidade
- [ ] Seletores do Kommo (`kommo.py` / `privacy.py` + `docs/KOMMO_DOM.md`)
- [ ] Build / empacotamento / CI
- [ ] Documentação

## Como foi testado

<!-- Comandos rodados e resultado. Testes manuais: com que conta de TESTE e com qual limite pequeno. -->

- [ ] `python -m pytest -q -p no:cacheprovider` passou
- [ ] `python -B scripts/verificar_privacidade.py` passou (sem achados)
- [ ] Teste manual no Kommo (se aplicável) feito em conta de **teste/ensaio**, com limite pequeno (ex.: 3)

## Privacidade e segurança

- [ ] Nenhum dado real no PR: sem `data/`, logs, `config.json`, capturas de tela, diagnósticos, subdomínio,
      nomes, telefones ou e-mails de clientes (inclusive em fixtures, testes e descrições)
- [ ] Prints/GIFs anexados (se houver) foram feitos com o **modo privacidade** ligado e conferidos
- [ ] Mudou seletor do Kommo? `docs/KOMMO_DOM.md` e um teste foram atualizados

## Documentação

- [ ] `CHANGELOG.md` atualizado (se a mudança aparece para quem usa)
- [ ] README / `docs/` atualizados (se aplicável)
