"""Ponto de entrada: sem argumentos abre a interface; com --cli roda em modo texto; --help mostra o uso."""
import sys

USO = """Uso:
  kommo-unir-duplicatas                 abre a janela (interface gráfica)
  kommo-unir-duplicatas --cli ARGS...   modo texto (veja: kommo-unir-duplicatas --cli --help)
  kommo-unir-duplicatas --help          mostra esta ajuda"""


def main() -> int:
    """Devolve o código de saída do processo (0 = ok, diferente de 0 = falha)."""
    if len(sys.argv) > 1 and sys.argv[1] == "--cli":
        from .cli import main as cli_main
        return cli_main(sys.argv[2:])
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        # Não abre a janela só para mostrar ajuda.
        print(USO)
        return 0
    from .ui import main as ui_main
    # Propaga o código da interface (1 = não foi possível abrir, ex.: pasta de dados sem escrita).
    return ui_main()


if __name__ == "__main__":
    raise SystemExit(main())
