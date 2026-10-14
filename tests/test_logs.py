import os
from datetime import datetime

import pytest

from kommo_duplicatas import logs, paths


@pytest.fixture(autouse=True)
def _isolar(monkeypatch, tmp_path):
    monkeypatch.setenv("KOMMO_DATA_DIR", str(tmp_path / "dados"))
    monkeypatch.setattr(paths, "_verificadas", set())
    monkeypatch.setattr(logs, "_limpeza_feita", False)
    monkeypatch.setattr(logs, "ultimo_erro", None)


def test_sanitiza_caracteres_de_controle():
    linha = logs.formatar("info", "a\nb\r\tc\x00d\x1b[31me\x7ff\x85g\x9fh")
    assert "\n" not in linha and "\r" not in linha and "\x1b" not in linha
    assert all(not (0 <= ord(c) <= 0x1f or 0x7f <= ord(c) <= 0x9f) for c in linha)
    assert linha.endswith("a b  c d [31me f g h")


def test_preserva_acentos_e_espacos():
    assert logs.formatar("ok", "União concluída — ação ✓").endswith("OK    União concluída — ação ✓")


def test_trunca_linhas_longas():
    linha = logs.formatar("erro", "x" * 10_000)
    assert len(linha) == logs.MAX_LINHA
    assert "caracteres]" in linha
    curta = logs.formatar("info", "y" * 100)
    assert "caracteres]" not in curta


def test_niveis_nao_existe_mais():
    assert not hasattr(logs, "NIVEIS")


def test_gravar_cria_arquivo_do_dia(tmp_path):
    linha = logs.gravar("aviso", "linha\ncom quebra")
    arquivo = tmp_path / "dados" / "logs" / (datetime.now().strftime("%Y-%m-%d") + ".log")
    assert arquivo.read_text(encoding="utf-8") == linha + "\n"
    assert "AVISO linha com quebra" in linha


def _criar_logs(pasta, nomes):
    pasta.mkdir(parents=True, exist_ok=True)
    for n in nomes:
        (pasta / n).write_text("x", encoding="utf-8")


def test_limpar_antigos(tmp_path):
    pasta = tmp_path / "logs"
    _criar_logs(pasta, ["2026-01-01.log", "2026-09-12.log", "2026-09-13.log", "2026-10-13.log",
                        "anotacoes.txt", "2026-02-30.log", "debug.log"])
    apagados = logs.limpar_antigos(30, pasta=str(pasta), hoje=datetime(2026, 10, 13, 12, 0))
    assert apagados == 2
    assert sorted(os.listdir(pasta)) == ["2026-02-30.log", "2026-09-13.log", "2026-10-13.log",
                                         "anotacoes.txt", "debug.log"]


def test_primeiro_gravar_limpa_antigos_uma_vez(tmp_path):
    pasta = tmp_path / "dados" / "logs"
    _criar_logs(pasta, ["2000-01-01.log"])
    logs.gravar("info", "primeira")
    assert not (pasta / "2000-01-01.log").exists()
    _criar_logs(pasta, ["2000-01-02.log"])
    logs.gravar("info", "segunda")                      # só limpa no primeiro gravar do processo
    assert (pasta / "2000-01-02.log").exists()


def test_falha_de_pasta_nao_derruba(monkeypatch):
    def falhar():
        raise paths.DataDirNotWritable("X:\\sem acesso", "teste")

    monkeypatch.setattr(paths, "logs_dir", falhar)
    linha = logs.gravar("erro", "algo")
    assert linha.endswith("ERRO  algo")
    assert logs.ultimo_erro and "sem acesso" in logs.ultimo_erro
    assert logs.limpar_antigos() == 0
