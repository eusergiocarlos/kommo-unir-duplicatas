"""Ponto de entrada (kommo_duplicatas.__main__): despacho UI × CLI × ajuda e propagação do código de saída.

Nada abre janela nem navegador: `ui` e `cli` são trocados por módulos falsos em sys.modules (monkeypatch), então
nem o tkinter nem o Playwright são carregados aqui."""
import sys
import types

import pytest

from kommo_duplicatas import __main__ as entrada


def _falso(monkeypatch, nome: str, retorno: int) -> list:
    """Instala kommo_duplicatas.<nome> falso cujo main() anota os argumentos e devolve `retorno`."""
    chamadas: list = []

    def main(*args):
        chamadas.append(args)
        return retorno

    mod = types.ModuleType(f"kommo_duplicatas.{nome}")
    mod.main = main
    monkeypatch.setitem(sys.modules, f"kommo_duplicatas.{nome}", mod)
    return chamadas


@pytest.mark.parametrize("codigo", [0, 1])
def test_sem_argumentos_abre_ui_e_propaga_codigo(monkeypatch, codigo):
    ui = _falso(monkeypatch, "ui", codigo)
    cli = _falso(monkeypatch, "cli", 99)
    monkeypatch.setattr(sys, "argv", ["kommo-unir-duplicatas"])
    assert entrada.main() == codigo
    assert ui == [()] and cli == []


def test_cli_recebe_argv_sem_o_marcador(monkeypatch):
    ui = _falso(monkeypatch, "ui", 0)
    cli = _falso(monkeypatch, "cli", 3)
    monkeypatch.setattr(sys, "argv", ["prog", "--cli", "acme", "leads", "10", "--ensaio"])
    assert entrada.main() == 3
    assert cli == [(["acme", "leads", "10", "--ensaio"],)] and ui == []


def test_cli_sem_argumentos_extras(monkeypatch):
    cli = _falso(monkeypatch, "cli", 2)
    _falso(monkeypatch, "ui", 0)
    monkeypatch.setattr(sys, "argv", ["prog", "--cli"])
    assert entrada.main() == 2
    assert cli == [([],)]


@pytest.mark.parametrize("opcao", ["--help", "-h"])
def test_ajuda_nao_abre_ui(monkeypatch, capsys, opcao):
    ui = _falso(monkeypatch, "ui", 1)
    cli = _falso(monkeypatch, "cli", 1)
    monkeypatch.setattr(sys, "argv", ["prog", opcao])
    assert entrada.main() == 0
    assert ui == [] and cli == []
    saida = capsys.readouterr().out
    assert "--cli" in saida and "Uso" in saida


def test_cli_help_real_sai_com_zero(monkeypatch, capsys):
    """`--cli --help` usa o argparse do cli real: SystemExit(0) sobe intacto (sem abrir nada)."""
    monkeypatch.setattr(sys, "argv", ["prog", "--cli", "--help"])
    with pytest.raises(SystemExit) as exc:
        entrada.main()
    assert exc.value.code == 0
    assert "empresa" in capsys.readouterr().out
