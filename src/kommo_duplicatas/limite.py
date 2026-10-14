"""Interpretação da quantidade de uniões digitada pelo usuário (lógica pura, sem Tkinter).

Regras (decididas para nunca rodar uma quantidade diferente da que o usuário pediu):

- Texto vazio (ou só espaços/tabs comuns) → vale a opção marcada (`preset`).
- Aceita inteiros com ou sem separador de milhar: "1000", "1.000", "1 000" (espaço comum, NBSP ou espaço fino).
  O separador precisa agrupar de 3 em 3 ("10.00" é rejeitado: parece decimal).
- "0" significa **todas** — o mesmo que a opção "Todas" (0 é o valor que o motor entende como "sem limite").
- Rejeita, com `ValueError` e mensagem em português pronta para exibir: negativos, decimais ("50,"/"1,5"),
  letras, dígitos "especiais" ("²", "١" — `str.isdigit()` aceita, `int()` não), caracteres invisíveis
  (ex.: espaço de largura zero) e valores acima de `LIMITE_MAXIMO`.
"""
import re

LIMITE_MAXIMO = 999_999
# A UI e a CLI confirmam TODA execução pela conta realmente logada (ConfirmarEvt).
# Diálogo de confirmação da conta (UI): para "todas" (0) ou mais do que isto, o botão "Unir agora" só é
# habilitado depois de o usuário digitar PALAVRA_CONFIRMACAO (evita confirmar no automático uma execução enorme).
LIMITE_EXIGE_DIGITAR = 500
PALAVRA_CONFIRMACAO = "UNIR"

# Só dígitos ASCII ([0-9]); separador de milhar consistente (ponto, espaço, NBSP ou espaço fino).
_RE_NUMERO = re.compile(r"[0-9]+|[0-9]{1,3}(?P<sep>[.   ])[0-9]{3}(?:(?P=sep)[0-9]{3})*")

_DICA = "Use só números inteiros (ex.: 300 ou 1.000) ou deixe em branco para usar a opção marcada."


def parse_limite(texto: str, preset: int) -> int:
    """Devolve o limite efetivo (0 = todas). Levanta ValueError com mensagem pronta para o usuário."""
    bruto = "" if texto is None else str(texto)
    t = bruto.strip(" \t")
    if not t:
        return int(preset)
    exibido = t if len(t) <= 20 else t[:20] + "…"
    if t.startswith("-") and _RE_NUMERO.fullmatch(t[1:].strip()):
        raise ValueError(f"Quantidade inválida: \"{exibido}\" — não pode ser negativa. {_DICA}")
    m = _RE_NUMERO.fullmatch(t)
    if not m:
        if re.fullmatch(r"[0-9]+[.,][0-9]*", t) or re.fullmatch(r"[0-9]*[,][0-9]+", t):
            raise ValueError(f"Quantidade inválida: \"{exibido}\" — não use casas decimais. {_DICA}")
        raise ValueError(f"Quantidade inválida: \"{exibido}\". {_DICA}")
    n = int(re.sub(r"[^0-9]", "", t))
    if n > LIMITE_MAXIMO:
        raise ValueError(f"Quantidade muito alta: \"{exibido}\". O máximo é {LIMITE_MAXIMO:,}".replace(",", ".")
                         + " — para unir tudo, escolha \"Todas\".")
    return n


def descrever_limite(n: int) -> str:
    """'todas' para 0; senão o número com ponto de milhar ('1.000')."""
    return "todas" if not n else f"{int(n):,}".replace(",", ".")


def exige_digitar(n: int) -> bool:
    """True para 'todas' (0) e para quantidades acima de LIMITE_EXIGE_DIGITAR (digitar UNIR para habilitar)."""
    return not n or n > LIMITE_EXIGE_DIGITAR


def palavra_confere(texto: str) -> bool:
    """True se o texto digitado é a palavra de confirmação (ignora espaços nas pontas e maiúsculas/minúsculas)."""
    return (texto or "").strip().upper() == PALAVRA_CONFIRMACAO
