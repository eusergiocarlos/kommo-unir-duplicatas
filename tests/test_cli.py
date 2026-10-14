"""Modo texto (cli.py) com um Merger falso: sem navegador, sem Kommo e sem gravar log em disco."""
import threading

import pytest

from kommo_duplicatas import cli
from kommo_duplicatas.merger import ConfirmarEvt, FimEvt, LogEvt


class MergerFalso(threading.Thread):
    """Emite um roteiro de eventos; se houver ConfirmarEvt, espera responder() e decide o fim pela resposta."""
    ultimo = None

    def __init__(self, job, fila, parar):
        super().__init__(daemon=True)
        self.job, self.fila, self.parar = job, fila, parar
        self.resposta = None
        self.respondido = threading.Event()
        self.paradas = []
        MergerFalso.ultimo = self

    def responder(self, aceito):
        self.resposta = aceito
        self.respondido.set()

    def solicitar_parada(self, forcar=False):
        self.paradas.append(forcar)
        self.parar.set()
        self.respondido.set()

    def run(self):
        # Mensagens com subdomínio e total da conta: com privacidade, terminal e log devem recebê-las mascaradas.
        self.fila.put(LogEvt("info", "Abrindo https://acme.kommo.com/leads/list/"))
        self.fila.put(LogEvt("info", "Grupos de duplicatas na conta: 42.761"))
        self.fila.put(ConfirmarEvt("acme.kommo.com", self.job.tipo, 10, self.job.limite, self.job.ensaio))
        self.respondido.wait(5)
        if self.parar.is_set():
            self.fila.put(FimEvt(0, 1.0, 0, True, 10, 0, 0, 0, "parado", 1))
        elif self.resposta:
            self.fila.put(FimEvt(2, 1.0, 0, False, 10, 2, 1, 3, "limite", 1))
        else:
            self.fila.put(FimEvt(0, 1.0, 0, False, 10, 0, 0, 0, "recusado", 1))


class Saidas(list):
    """Linhas impressas no terminal; `.gravadas` = o que IRIA para o arquivo de log (logs.gravar)."""

    def __init__(self):
        super().__init__()
        self.gravadas = []


@pytest.fixture
def saidas(monkeypatch):
    monkeypatch.setattr(cli, "Merger", MergerFalso)
    linhas = Saidas()

    def gravar(nivel, msg):          # não grava log em disco; só anota
        linhas.gravadas.append(msg)
        return msg
    monkeypatch.setattr(cli.logs, "gravar", gravar)
    return linhas


def _saida(linhas):
    return lambda *a, **k: linhas.append(" ".join(str(x) for x in a))


@pytest.mark.parametrize("limite", ["-1", "abc", "1.5"])
def test_limite_invalido_rejeitado(limite, saidas):
    """Erro de uso sai com 64 (EX_USAGE), nunca com 2 (que na CLI significa parado/recusado)."""
    with pytest.raises(SystemExit) as e:
        cli.main(["acme", "leads", limite])
    assert e.value.code == cli.EX_USAGE == 64


@pytest.mark.parametrize("argv", [["acme", "pedidos", "3"], ["acme", "leads"], ["acme..x", "leads", "3"],
                                  ["acme", "leads", "3", "--opcao-que-nao-existe"]])
def test_erros_de_uso_saem_com_64(argv, saidas, capsys):
    with pytest.raises(SystemExit) as e:
        cli.main(argv)
    assert e.value.code == 64
    assert "erro:" in capsys.readouterr().err


def test_privacidade_padrao_mascara_terminal_e_log(saidas):
    codigo = cli.main(["acme", "leads", "3", "--sim"], saida=_saida(saidas))
    assert codigo == 0
    texto = "\n".join(saidas) + "\n" + "\n".join(saidas.gravadas)
    assert "acme" not in texto and "42.761" not in texto
    assert "a***e.kommo.com" in texto and "na conta: ••••" in texto
    assert len(saidas.gravadas) == 2                               # as duas linhas do motor foram ao log
    assert MergerFalso.ultimo.job.privacidade is True


def test_sem_privacidade_mostra_conta_e_totais(saidas):
    cli.main(["acme", "leads", "3", "--sem-privacidade"], entrada=lambda _: "n", saida=_saida(saidas))
    texto = "\n".join(saidas)
    assert "acme.kommo.com" in texto and "42.761" in texto
    assert MergerFalso.ultimo.job.privacidade is False


def test_sim_confirma_sem_perguntar_e_imprime_resumo(saidas):
    def nao_pergunte(_):
        raise AssertionError("não deveria perguntar com --sim")
    codigo = cli.main(["acme", "contatos", "3", "--sim"], entrada=nao_pergunte, saida=_saida(saidas))
    assert codigo == 0
    assert MergerFalso.ultimo.resposta is True
    resumo = [s for s in saidas if s.startswith("Resumo:")]
    assert resumo and "2 confirmadas" in resumo[0] and "1 não confirmadas" in resumo[0] and "3 cliques" in resumo[0]
    job = MergerFalso.ultimo.job
    assert job.confirmar_conta is True and job.ensaio is False


def test_pergunta_e_recusa(saidas):
    codigo = cli.main(["acme", "leads", "3"], entrada=lambda _: "n", saida=_saida(saidas))
    assert codigo == 2 and MergerFalso.ultimo.resposta is False
    assert any("a***e.kommo.com" in s for s in saidas)            # privacidade (padrão): conta mascarada
    assert not any("acme.kommo.com" in s for s in saidas)


def test_pergunta_m_mostra_a_conta_so_no_terminal(saidas):
    respostas = iter(["m", "s"])
    codigo = cli.main(["acme", "leads", "3"], entrada=lambda _: next(respostas), saida=_saida(saidas))
    assert codigo == 0 and MergerFalso.ultimo.resposta is True
    assert any("acme.kommo.com" in s for s in saidas)             # revelada a pedido, no terminal
    assert all("acme" not in m for m in saidas.gravadas)          # ... mas nunca no arquivo de log


def test_pergunta_e_aceita_com_ensaio(saidas):
    codigo = cli.main(["acme", "leads", "0", "--ensaio"], entrada=lambda _: "s", saida=_saida(saidas))
    assert MergerFalso.ultimo.resposta is True and MergerFalso.ultimo.job.ensaio is True
    assert codigo == 0


def test_ctrl_c_pede_parada_e_drena_a_fila(saidas):
    def ctrl_c(_):
        raise KeyboardInterrupt
    codigo = cli.main(["acme", "leads", "3"], entrada=ctrl_c, saida=_saida(saidas))
    assert MergerFalso.ultimo.paradas == [False]
    assert codigo == 2
    assert any(s.startswith("Resumo:") for s in saidas)          # FimEvt drenado depois do Ctrl+C


def test_confirmacao_eof_e_nao():
    ev = ConfirmarEvt("acme.kommo.com", "leads", 0, 0, False)

    def eof(_):
        raise EOFError
    assert cli.perguntar_confirmacao(ev, eof, lambda *a, **k: None) is False
    assert cli.perguntar_confirmacao(ev, lambda _: "", lambda *a, **k: None) is False
    assert cli.perguntar_confirmacao(ev, lambda _: " SIM ", lambda *a, **k: None) is True


def test_confirmacao_com_privacidade_mascara_host_e_total():
    ev = ConfirmarEvt("acme.kommo.com", "leads", 42761, 3, False)
    linhas = []
    assert cli.perguntar_confirmacao(ev, lambda _: "n", _saida(linhas), privacidade=True) is False
    assert "a***e.kommo.com" in linhas[0] and "••••" in linhas[0] and "42761" not in linhas[0]
