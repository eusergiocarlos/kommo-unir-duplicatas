"""Paleta do Kommo, fontes por plataforma e geometria da janela (sem criar widgets; testável)."""
import sys

BG, PAINEL, TXT, MUTED = "#14111f", "#211c33", "#f1eefc", "#9a92b8"
ROXO, ROXO_HOVER, CLARO = "#5b3fd0", "#6d52e0", "#a995ff"     # roxo do Kommo / destaque / números
VERMELHO, AMARELO, OK = "#ff6b81", "#f5b942", "#5fd38d"
TRILHA, LOG_BG, LOG_FG = "#2f2848", "#0d0b15", "#cfd6e0"
BRANCO = "#ffffff"
FOCO = CLARO               # cor do anel de foco (teclado)

# Preferência de fontes por plataforma; a primeira instalada vence.
FONTES = {
    "win32": {"sans": ("Segoe UI", "Tahoma", "Arial"), "mono": ("Consolas", "Courier New")},
    "linux": {"sans": ("Cantarell", "DejaVu Sans", "Liberation Sans"),
              "mono": ("DejaVu Sans Mono", "Liberation Mono")},
    "darwin": {"sans": ("Helvetica Neue", "Helvetica"), "mono": ("Menlo", "Monaco")},
}
# Nomes que o Tk sempre resolve (mapeia para uma fonte do sistema), se nenhuma preferida estiver instalada.
GENERICAS = {"sans": "Helvetica", "mono": "Courier"}


def _chave_plataforma(plataforma: str) -> str:
    if plataforma.startswith("win"):
        return "win32"
    if plataforma == "darwin":
        return "darwin"
    return "linux"


def escolher_fontes(familias, plataforma: str = sys.platform) -> dict:
    """Devolve {'sans': nome, 'mono': nome} com a primeira família preferida que existe em `familias`."""
    disponiveis = {f.lower() for f in familias}
    prefs = FONTES[_chave_plataforma(plataforma)]
    out = {}
    for tipo, nomes in prefs.items():
        out[tipo] = next((n for n in nomes if n.lower() in disponiveis), GENERICAS[tipo])
    return out


def calcular_geometria(tela_l: int, tela_a: int, larg: int = 560, alt: int = 660, fracao: float = 0.9):
    """(largura, altura, x, y): no máximo `fracao` da tela, centralizada e sempre dentro dela."""
    w = max(1, min(larg, int(tela_l * fracao)))
    h = max(1, min(alt, int(tela_a * fracao)))
    x = max(0, (tela_l - w) // 2)
    # um pouco acima do centro: deixa espaço para a barra de tarefas embaixo
    y = max(0, min((tela_a - h) // 3, tela_a - h))
    return w, h, x, y
