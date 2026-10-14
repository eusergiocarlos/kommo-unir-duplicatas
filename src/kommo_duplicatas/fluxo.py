"""Regras puras do fluxo de união (sem Playwright, sem tempo, sem I/O) — testáveis com tabelas de casos.

O motor lê `Estado`s da página (via `kommo.PortaKommo`) e pergunta aqui o que eles significam.
"""
import re
import unicodedata
from enum import Enum

from .kommo import Estado

_RE_CONCLUIDO = re.compile(r"conclu", re.IGNORECASE)


class Resultado(Enum):
    SUCESSO = "sucesso"   # união confirmada pelo texto de conclusão do Kommo
    INCERTO = "incerto"   # algo mudou, mas sem confirmação — NÃO contar como união feita
    AGUARDA = "aguarda"   # ainda não dá para decidir; continue observando
    ERRO = "erro"         # o Kommo mostrou erro no modal


def _sem_acentos(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texto or "") if not unicodedata.combining(c))


def progresso_concluido(texto: str) -> bool:
    """True se o texto de h2.progress__header indica conclusão (/conclu/i, ignorando acentos e caixa).

    'União de contatos concluída com sucesso' -> True; 'Realizando união' / 'Unindo leads' -> False.
    """
    return bool(_RE_CONCLUIDO.search(_sem_acentos(texto)))


def avaliar_uniao(antes: Estado, depois: Estado, visto_progresso: bool, ultimo_progresso: str) -> Resultado:
    """Decide o resultado de um clique em "Unir esta duplicata".

    Parâmetros:
        antes            — estado lido logo antes do clique (grupo atual; `antes.caption` é o título dele);
        depois           — estado lido agora;
        visto_progresso  — se algum h2.progress__header apareceu desde o clique;
        ultimo_progresso — último texto não vazio de progresso visto desde o clique.

    "concluído" = `progresso_concluido(depois.progresso)` ou `progresso_concluido(ultimo_progresso)`.
    "visto"     = `visto_progresso` ou há texto de progresso em `depois.progresso`/`ultimo_progresso`.

    Tabela de decisão (avaliada de cima para baixo; a primeira linha que casar vale):

    | # | Condição em `depois`                                  | concluído | visto | Resultado |
    |---|-------------------------------------------------------|-----------|-------|-----------|
    | 1 | erro no modal (.js-modal-error)                       |     -     |   -   | ERRO      |
    | 2 | navegou (leitura falhou: página recarregando)         |    sim    |   -   | SUCESSO   |
    | 3 | navegou                                               |    não    |   -   | AGUARDA   |
    | 4 | progresso ainda visível (inclusive "…concluída")      |     -     |   -   | AGUARDA   |
    |4a | modal informa "nenhuma duplicata" (`vazio`, heurístico)|    sim    |   -   | SUCESSO   |
    |4b | modal informa "nenhuma duplicata"                     |    não    |   -   | INCERTO   |
    | 5 | botão Unir visível (próximo grupo; título igual ou    |    sim    |   -   | SUCESSO   |
    |   | diferente — Leads "1 de muitas" repete o título)      |           |       |           |
    | 6 | botão Unir visível                                    |    não    |  sim  | INCERTO   |
    |   | (progresso apareceu e sumiu sem conclusão)            |           |       |           |
    | 7 | botão Unir visível, título diferente do de `antes`    |    não    |  não  | INCERTO   |
    | 8 | botão Unir visível, mesmo título                      |    não    |  não  | AGUARDA   |
    |   | (nada mudou ainda)                                    |           |       |           |
    | 9 | modal fechado (Kommo recarregando a busca)            |    sim    |   -   | SUCESSO   |
    |10 | modal fechado, e `antes` também estava sem modal      |    não    |  não  | AGUARDA   |
    |11 | modal fechado                                         |    não    |   -   | INCERTO   |
    |12 | qualquer outro caso (modal aberto carregando, sem     |     -     |   -   | AGUARDA   |
    |   | botão nem progresso)                                  |           |       |           |

    Só há SUCESSO com o texto de conclusão do Kommo **e** um estado seguinte coerente (próximo grupo visível,
    modal fechado, "nenhuma duplicata" ou página recarregando). A tela de carregamento (`carregando`) não é modal:
    cai nas linhas 9–11 (modal fechado). Enquanto o próprio "…concluída" ainda está na tela, aguarda (linha 4).
    O motor é quem aplica o tempo limite: AGUARDA por tempo demais vira falha lá, não aqui.
    """
    concluido = progresso_concluido(depois.progresso) or progresso_concluido(ultimo_progresso)
    visto = bool(visto_progresso or depois.progresso or ultimo_progresso)

    if depois.erro:                                            # 1
        return Resultado.ERRO
    if depois.navegou:                                         # 2, 3
        return Resultado.SUCESSO if concluido else Resultado.AGUARDA
    if depois.progresso:                                       # 4
        return Resultado.AGUARDA
    if depois.vazio and not depois.pode:                       # 4a, 4b
        return Resultado.SUCESSO if concluido else Resultado.INCERTO
    if depois.pode:
        if concluido:                                          # 5
            return Resultado.SUCESSO
        if depois.caption != antes.caption:                    # 6, 7: o contador do título andou = próximo grupo
            return Resultado.SUCESSO
        if visto:                                              # 6b: mesmo grupo de volta após progresso
            return Resultado.INCERTO
        return Resultado.AGUARDA                               # 8
    if not depois.modal:
        if concluido:                                          # 9
            return Resultado.SUCESSO
        if not visto and not antes.modal:                      # 10
            return Resultado.AGUARDA
        return Resultado.SUCESSO                               # 11: o Kommo fecha o modal ao unir (Leads não mostra "concluída")
    return Resultado.AGUARDA                                   # 12
