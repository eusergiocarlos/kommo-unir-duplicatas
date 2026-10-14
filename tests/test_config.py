import json
import os

import pytest

from kommo_duplicatas import config, paths


@pytest.fixture(autouse=True)
def _isolar(monkeypatch):
    monkeypatch.setattr(paths, "_verificadas", set())
    monkeypatch.setattr(config, "ultimo_aviso", None)


def test_dados_ficam_na_raiz_de_dados(tmp_path, monkeypatch):
    monkeypatch.setenv("KOMMO_DATA_DIR", str(tmp_path))
    assert paths.config_file().startswith(str(tmp_path))
    assert paths.profile_dir().startswith(str(tmp_path))


def test_padrao_sem_empresa(tmp_path, monkeypatch):
    monkeypatch.setenv("KOMMO_DATA_DIR", str(tmp_path))
    cfg = config.carregar()
    assert cfg["empresa"] == ""
    assert cfg["limite_custom"] is None and cfg["canal_navegador"] == ""


def test_salvar_e_carregar(tmp_path, monkeypatch):
    monkeypatch.setenv("KOMMO_DATA_DIR", str(tmp_path))
    config.salvar(empresa="acme", limite=200, campo_desconhecido=1)
    cfg = config.carregar()
    assert cfg["empresa"] == "acme" and cfg["limite"] == 200
    assert "campo_desconhecido" not in cfg


def test_migra_nome_antigo_da_opcao(tmp_path, monkeypatch):
    monkeypatch.setenv("KOMMO_DATA_DIR", str(tmp_path))
    (tmp_path / "config.json").write_text(json.dumps({"blur": False}), encoding="utf-8")
    assert config.carregar()["privacidade"] is False


def test_limite_custom_e_canal(tmp_path, monkeypatch):
    monkeypatch.setenv("KOMMO_DATA_DIR", str(tmp_path))
    config.salvar(limite_custom="350", canal_navegador=" MSEdge ")
    cfg = config.carregar()
    assert cfg["limite_custom"] == 350 and cfg["canal_navegador"] == "msedge"
    config.salvar(limite_custom="abc")
    assert config.carregar()["limite_custom"] is None
    config.salvar(limite_custom=-5)
    assert config.carregar()["limite_custom"] is None
    config.salvar(limite_custom=None)
    assert config.carregar()["limite_custom"] is None


def test_escrita_atomica_nao_estraga_o_arquivo(tmp_path, monkeypatch):
    monkeypatch.setenv("KOMMO_DATA_DIR", str(tmp_path))
    config.salvar(empresa="original")
    antes = (tmp_path / "config.json").read_text(encoding="utf-8")

    def falhar(*a, **k):
        raise OSError("disco cheio (simulado)")

    monkeypatch.setattr(config.os, "replace", falhar)
    with pytest.raises(OSError):
        config.salvar(empresa="nova")
    monkeypatch.undo()
    assert (tmp_path / "config.json").read_text(encoding="utf-8") == antes
    assert [n for n in os.listdir(tmp_path) if n.endswith(".tmp")] == []   # temporário removido


def test_salvar_nao_deixa_temporarios(tmp_path, monkeypatch):
    monkeypatch.setenv("KOMMO_DATA_DIR", str(tmp_path / "Dados com espaço ç"))
    for i in range(5):
        config.salvar(limite=i)
    pasta = tmp_path / "Dados com espaço ç"
    assert sorted(os.listdir(pasta)) == ["config.json"]
    assert config.carregar()["limite"] == 4


@pytest.mark.parametrize("conteudo", ["{nao é json", "[1, 2, 3]", "\x00\x01lixo"])
def test_arquivo_corrompido_volta_ao_padrao(tmp_path, monkeypatch, conteudo):
    monkeypatch.setenv("KOMMO_DATA_DIR", str(tmp_path))
    (tmp_path / "config.json").write_text(conteudo, encoding="utf-8")
    cfg, aviso = config.carregar_detalhado()
    assert cfg == config.PADRAO
    assert aviso and "corrompido" in aviso and config.ultimo_aviso == aviso
    assert not (tmp_path / "config.json").exists()
    assert (tmp_path / "config.json.corrompido").read_text(encoding="utf-8") == conteudo
    config.salvar(empresa="acme")                          # e volta a funcionar normalmente
    assert config.carregar_detalhado() == ({**config.PADRAO, "empresa": "acme"}, None)


def test_bytes_invalidos_em_utf8(tmp_path, monkeypatch):
    monkeypatch.setenv("KOMMO_DATA_DIR", str(tmp_path))
    (tmp_path / "config.json").write_bytes(b"\xff\xfe\xfa{")
    cfg, aviso = config.carregar_detalhado()
    assert cfg == config.PADRAO and aviso
    assert (tmp_path / "config.json.corrompido").exists()


def test_pasta_nao_gravavel_nao_e_engolida(tmp_path, monkeypatch):
    arquivo = tmp_path / "arquivo.txt"
    arquivo.write_text("x", encoding="utf-8")
    monkeypatch.setenv("KOMMO_DATA_DIR", str(arquivo / "dados"))
    with pytest.raises(paths.DataDirNotWritable):
        config.carregar()
    with pytest.raises(paths.DataDirNotWritable):
        config.salvar(empresa="acme")


def test_tipos_errados_voltam_ao_padrao_com_aviso(tmp_path, monkeypatch):
    """config.json com tipos errados: cada campo inválido volta ao padrão, com aviso; nada levanta exceção."""
    monkeypatch.setenv("KOMMO_DATA_DIR", str(tmp_path))
    errado = {"empresa": 123, "tipo": "pedidos", "limite": "abc", "privacidade": "sim", "limite_custom": [1],
              "canal_navegador": 5, "ultimo_total": -3, "ultima_execucao": None}
    (tmp_path / "config.json").write_text(json.dumps(errado), encoding="utf-8")
    cfg, aviso = config.carregar_detalhado()
    assert cfg == config.PADRAO
    assert aviso and "valor inválido" in aviso and config.ultimo_aviso == aviso
    for campo in errado:
        assert campo in aviso
    assert (tmp_path / "config.json").exists()                  # não é tratado como arquivo corrompido


@pytest.mark.parametrize("campo,valor", [("limite", True), ("limite", -1), ("limite", 1.5), ("tipo", "LEADS"),
                                         ("privacidade", 1), ("limite_custom", "-5"), ("empresa", None)])
def test_um_campo_invalido_nao_afeta_os_outros(tmp_path, monkeypatch, campo, valor):
    monkeypatch.setenv("KOMMO_DATA_DIR", str(tmp_path))
    salvo = {"empresa": "acme", "tipo": "contatos", "limite": 200, "privacidade": False, "limite_custom": 7}
    salvo[campo] = valor
    (tmp_path / "config.json").write_text(json.dumps(salvo), encoding="utf-8")
    cfg, aviso = config.carregar_detalhado()
    assert cfg[campo] == config.PADRAO[campo] and aviso and campo in aviso
    for outro, v in salvo.items():
        if outro != campo:
            assert cfg[outro] == v


def test_valores_validos_nao_geram_aviso(tmp_path, monkeypatch):
    monkeypatch.setenv("KOMMO_DATA_DIR", str(tmp_path))
    bom = {"empresa": "acme", "tipo": "contatos", "limite": 0, "privacidade": False, "limite_custom": None,
           "canal_navegador": "msedge", "ultimo_total": 10, "ultima_execucao": "2026-01-01T10:00:00"}
    (tmp_path / "config.json").write_text(json.dumps(bom), encoding="utf-8")
    assert config.carregar_detalhado() == (bom, None)
