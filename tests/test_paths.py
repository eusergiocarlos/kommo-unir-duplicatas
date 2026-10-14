import os
import sys

import pytest

from kommo_duplicatas import paths


@pytest.fixture(autouse=True)
def _isolar(monkeypatch, tmp_path):
    """Nenhum teste usa a pasta real do programa nem o %APPDATA% do usuário."""
    monkeypatch.delenv("KOMMO_DATA_DIR", raising=False)
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata_falso"))
    monkeypatch.setattr(paths, "_verificadas", set())


def _congelar(monkeypatch, pasta_exe):
    pasta_exe.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(pasta_exe / "KommoUnirDuplicatas.exe"))


def _fonte_em(monkeypatch, raiz):
    """Simula o código-fonte instalado em <raiz>/src/kommo_duplicatas/paths.py."""
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.setattr(paths, "__file__", str(raiz / "src" / "kommo_duplicatas" / "paths.py"))


def test_app_dir_codigo_fonte_e_a_raiz_do_repositorio():
    # Só leitura: não cria nada na pasta real.
    raiz = paths.app_dir()
    assert os.path.isfile(os.path.join(raiz, "pyproject.toml"))
    assert os.path.isdir(os.path.join(raiz, "src", "kommo_duplicatas"))


def test_portatil_codigo_fonte(tmp_path, monkeypatch):
    raiz = tmp_path / "Meu Repositório"
    _fonte_em(monkeypatch, raiz)
    assert paths.app_dir() == str(raiz)
    assert paths.data_dir() == str(raiz / "data")
    assert (raiz / "data").is_dir()


def test_portatil_frozen_com_espacos_e_acentos(tmp_path, monkeypatch):
    pasta = tmp_path / "Programas Ação" / "Kommo Unir Duplicatas"
    _congelar(monkeypatch, pasta)
    assert paths.app_dir() == str(pasta)
    d = paths.data_dir()
    assert d == str(pasta / "data")
    assert paths.config_file() == str(pasta / "data" / "config.json")
    assert paths.logs_dir() == str(pasta / "data" / "logs") and os.path.isdir(paths.logs_dir())
    assert paths.debug_dir() == str(pasta / "data" / "debug")
    assert paths.profile_dir() == str(pasta / "data" / "profile")
    # não caiu para o APPDATA
    assert not (tmp_path / "appdata_falso").exists()


def test_independe_do_cwd(tmp_path, monkeypatch):
    pasta = tmp_path / "app"
    _congelar(monkeypatch, pasta)
    antes = paths.data_dir()
    outro = tmp_path / "outro lugar"
    outro.mkdir()
    monkeypatch.chdir(outro)
    assert paths.data_dir() == antes
    assert not (outro / "data").exists()


def test_kommo_data_dir_tem_precedencia(tmp_path, monkeypatch):
    _congelar(monkeypatch, tmp_path / "app")
    alvo = tmp_path / "Dados Pessoais çã"
    monkeypatch.setenv("KOMMO_DATA_DIR", str(alvo))
    assert paths.data_dir() == str(alvo)
    assert not (tmp_path / "app" / "data").exists()


def test_kommo_data_dir_relativo_e_relativo_ao_programa(tmp_path, monkeypatch):
    _congelar(monkeypatch, tmp_path / "app")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("KOMMO_DATA_DIR", "meus-dados")
    assert paths.data_dir() == str(tmp_path / "app" / "meus-dados")


def test_profile_dir_por_canal(tmp_path, monkeypatch):
    monkeypatch.setenv("KOMMO_DATA_DIR", str(tmp_path))
    assert paths.profile_dir("chrome") == str(tmp_path / "profile" / "chrome")
    assert paths.profile_dir("MSEdge") == str(tmp_path / "profile" / "msedge")
    for invalido in ("..", "a/b", "c:\\x", ""):
        with pytest.raises(ValueError):
            paths.profile_dir(invalido)


def test_nao_gravavel_por_permissao(tmp_path, monkeypatch):
    pasta = tmp_path / "Program Files" / "Kommo"
    _congelar(monkeypatch, pasta)
    alvo = os.path.normpath(str(pasta / "data"))
    acesso_real = os.access
    monkeypatch.setattr(paths.os, "access",
                        lambda p, modo, **k: False if os.path.normpath(str(p)) == alvo else acesso_real(p, modo, **k))
    with pytest.raises(paths.DataDirNotWritable) as exc:
        paths.data_dir()
    msg = str(exc.value)
    assert alvo in msg and "KOMMO_DATA_DIR" in msg and "Mova" in msg
    assert not (tmp_path / "appdata_falso").exists()          # sem fallback silencioso


def test_nao_gravavel_quando_escrita_real_falha(tmp_path, monkeypatch):
    # No Windows os.access ignora ACLs: o teste de escrita real é que decide.
    _congelar(monkeypatch, tmp_path / "app")

    def negar(*a, **k):
        raise PermissionError(13, "Acesso negado")

    monkeypatch.setattr(paths.tempfile, "mkstemp", negar)
    with pytest.raises(paths.DataDirNotWritable):
        paths.ensure_writable()


def test_nao_gravavel_sem_mock(tmp_path, monkeypatch):
    arquivo = tmp_path / "isto-e-um-arquivo.txt"
    arquivo.write_text("x", encoding="utf-8")
    monkeypatch.setenv("KOMMO_DATA_DIR", str(arquivo / "dados"))
    with pytest.raises(paths.DataDirNotWritable):
        paths.config_file()


def test_erro_nao_e_engolido_por_except_oserror():
    assert not issubclass(paths.DataDirNotWritable, OSError)


def test_ensure_writable_nao_deixa_lixo(tmp_path):
    alvo = tmp_path / "com espaço"
    assert paths.ensure_writable(str(alvo)) == str(alvo)
    assert list(alvo.iterdir()) == []


def test_dentro_da_raiz(tmp_path):
    raiz = tmp_path / "data"
    raiz.mkdir()
    assert paths.dentro_da_raiz(str(raiz / "profile"), str(raiz))
    assert not paths.dentro_da_raiz(str(raiz), str(raiz))
    assert not paths.dentro_da_raiz(str(raiz / ".." / "fora"), str(raiz))
    assert not paths.dentro_da_raiz(str(tmp_path / "data2"), str(raiz))


def test_esquecer_login(tmp_path, monkeypatch):
    monkeypatch.setenv("KOMMO_DATA_DIR", str(tmp_path / "dados"))
    assert paths.esquecer_login() is False                    # nada salvo ainda
    perfil = tmp_path / "dados" / "profile" / "chrome" / "Default"
    perfil.mkdir(parents=True)
    (perfil / "Cookies").write_bytes(b"sessao")
    (tmp_path / "dados" / "config.json").write_text("{}", encoding="utf-8")
    assert paths.esquecer_login() is True
    assert list((tmp_path / "dados" / "profile").iterdir()) == []
    assert (tmp_path / "dados" / "config.json").exists()      # só o perfil é apagado
    assert paths.esquecer_login() is False


def test_esquecer_login_recusa_link(tmp_path, monkeypatch):
    monkeypatch.setenv("KOMMO_DATA_DIR", str(tmp_path / "dados"))
    (tmp_path / "dados" / "profile" / "chrome").mkdir(parents=True)
    monkeypatch.setattr(paths, "_eh_link", lambda p: True)
    with pytest.raises(paths.EsquecerLoginErro):
        paths.esquecer_login()
    assert (tmp_path / "dados" / "profile" / "chrome").exists()


@pytest.mark.skipif(os.name != "nt", reason="arquivo aberto só bloqueia exclusão no Windows")
def test_esquecer_login_com_navegador_aberto(tmp_path, monkeypatch):
    monkeypatch.setenv("KOMMO_DATA_DIR", str(tmp_path / "dados"))
    perfil = tmp_path / "dados" / "profile" / "chrome"
    perfil.mkdir(parents=True)
    with open(perfil / "lockfile", "w") as f:                 # simula o Chrome segurando o arquivo
        f.write("x")
        with pytest.raises(paths.EsquecerLoginErro) as exc:
            paths.esquecer_login()
    assert "Feche" in str(exc.value)
