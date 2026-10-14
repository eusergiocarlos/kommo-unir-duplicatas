"""Atalho para rodar sem instalar o pacote:  python main.py   (ou  python main.py --cli ...).
Também é o ponto de entrada usado para gerar o .exe (scripts/build_exe.ps1)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from kommo_duplicatas.__main__ import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
