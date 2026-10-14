"""Máscaras de privacidade para textos exibidos/gravados (janela, terminal e arquivo de log).

Com o modo privacidade ligado, o subdomínio da conta vira "a***e" e os totais da conta viram "••••".
Funções puras, usadas pela interface (ui.py — que reexporta os mesmos nomes) e pelo modo texto (cli.py).
"""
import re

from .kommo import DOMINIO

OCULTO = "••••"                    # o que aparece no lugar de números da conta com privacidade ligada


def mascarar_empresa(s: str) -> str:
    """'acme' -> 'a***e'. Sempre 3 asteriscos (não revela o tamanho); até 2 letras vira só '***'."""
    s = (s or "").strip()
    if not s:
        return ""
    if len(s) <= 2:
        return "***"
    return f"{s[0]}***{s[-1]}"


def mascarar_host(host: str) -> str:
    """'acme.kommo.com' -> 'a***e.kommo.com' (só o subdomínio é mascarado)."""
    host = (host or "").strip().lower()
    sufixo = "." + DOMINIO
    if host.endswith(sufixo):
        return mascarar_empresa(host[: -len(sufixo)]) + sufixo
    return mascarar_empresa(host)


def mascarar_mensagem(msg: str, empresa: str, privacidade: bool) -> str:
    """Esconde subdomínio e totais da conta numa linha de log (só com privacidade ligada).

    - subdomínio: troca `empresa` (sem diferenciar maiúsculas) pela versão mascarada; nomes com menos de
      4 letras só são trocados quando colados em ".kommo.com" (evita estragar palavras comuns);
    - totais: "… 3 de 42.761" -> "… 3 de ••••", "na conta: 42.761" -> "na conta: ••••" e
      "pelo Kommo: 42.761" -> "pelo Kommo: ••••".
    """
    if not privacidade or not msg:
        return msg
    if empresa:
        masc = mascarar_empresa(empresa)
        if len(empresa) >= 4:
            padrao = r"(?<![a-z0-9-])" + re.escape(empresa) + r"(?![a-z0-9-])"
        else:
            padrao = r"(?<![a-z0-9-])" + re.escape(empresa) + r"(?=\." + re.escape(DOMINIO) + ")"
        msg = re.sub(padrao, masc, msg, flags=re.IGNORECASE)
    msg = re.sub(r"(\bde\s+)\d[\d.]*", r"\g<1>" + OCULTO, msg)
    msg = re.sub(r"(na conta:\s*)\d[\d.]*", r"\g<1>" + OCULTO, msg)
    msg = re.sub(r"(pelo Kommo:\s*)\d[\d.]*", r"\g<1>" + OCULTO, msg)
    return msg
