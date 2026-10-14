"""Testes do scripts/verificar_privacidade.py — só com termos FALSOS e artefatos montados em tmp_path.

Nada aqui usa o usuário/hostname reais: todas as chamadas passam --sem-termos-padrao (ou termos explícitos).
"""
import importlib.util
import io
import json
import marshal
import struct
import sys
import tarfile
import zipfile
import zlib
from importlib.util import MAGIC_NUMBER
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "verificar_privacidade.py"
_spec = importlib.util.spec_from_file_location("verificar_privacidade", _SCRIPT)
vp = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = vp            # dataclasses precisa do módulo registrado
_spec.loader.exec_module(vp)

TERMO = "fulanodetal"            # termo falso (>= 6 caracteres)
CURTO = "zeca"                   # termo falso curto (4-5 → exige limite de palavra)


def _pyc_com_caminho(caminho_fonte: str) -> bytes:
    """Gera bytes de um .pyc real cujo co_filename é `caminho_fonte` (como o Python grava em __pycache__)."""
    code = compile("x = 1\n", caminho_fonte, "exec")
    return MAGIC_NUMBER + b"\0" * 12 + marshal.dumps(code)


def _zip_bytes(membros: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for nome, dados in membros.items():
            z.writestr(nome, dados)
    return buf.getvalue()


def _pyz(modulos: dict) -> bytes:
    """Monta um PYZ no formato do PyInstaller 6 (PYZ\\0 + magic + offset da TOC + blobs zlib + TOC marshal)."""
    corpo = b""
    toc = []
    base = 12
    for nome, code in modulos.items():
        blob = zlib.compress(marshal.dumps(code))
        toc.append((nome, (0, base + len(corpo), len(blob))))
        corpo += blob
    toc_off = base + len(corpo)
    return b"PYZ\0" + MAGIC_NUMBER + struct.pack("!i", toc_off) + corpo + marshal.dumps(toc)


def _exe_pyinstaller(itens: dict) -> bytes:
    """Executável falso: cabeçalho MZ + CArchive do PyInstaller (itens comprimidos com zlib) + cookie."""
    dados = b""
    toc = b""
    for nome, (bloco, tipo) in itens.items():
        comp = zlib.compress(bloco)
        nome_b = nome.encode()
        pad = (16 - (struct.calcsize("!IIIIBc") + len(nome_b)) % 16) % 16
        nome_b += b"\0" * pad
        ent_len = struct.calcsize("!IIIIBc") + len(nome_b)
        toc += struct.pack("!IIIIBc", ent_len, len(dados), len(comp), len(bloco), 1, tipo) + nome_b
        dados += comp
    toc_off = len(dados)
    pkg = dados + toc
    tam_cookie = struct.calcsize("!8sIIII64s")
    cookie = struct.pack("!8sIIII64s", vp.MAGIC_CARCHIVE, len(pkg) + tam_cookie, toc_off, len(toc), 314,
                         b"python314.dll")
    return b"MZ" + b"\0" * 200 + pkg + cookie


def _rodar(capsys, *args):
    rc = vp.main(["--sem-termos-padrao", *args])
    return rc, capsys.readouterr().out


def _projeto_limpo(raiz: Path) -> Path:
    (raiz / "src" / "pacote").mkdir(parents=True)
    (raiz / "src" / "pacote" / "__init__.py").write_text("VERSAO = '1.0'\n", encoding="utf-8")
    (raiz / "README.md").write_text("# Projeto de exemplo\nSem dados pessoais aqui.\n", encoding="utf-8")
    (raiz / "dist").mkdir()
    return raiz


# ------------------------------------------------------------------------------------------- achados
def test_projeto_limpo_passa(tmp_path, capsys):
    raiz = _projeto_limpo(tmp_path / "proj")
    (raiz / "dist" / "app.zip").write_bytes(_zip_bytes({"app/leia.txt": b"conteudo neutro"}))
    rc, out = _rodar(capsys, "--raiz", str(raiz), "--termo", TERMO)
    assert rc == 0, out
    assert "OK:" in out


def test_zip_com_pyc_contendo_caminho(tmp_path, capsys):
    raiz = _projeto_limpo(tmp_path / "proj")
    pyc = _pyc_com_caminho(rf"C:\Users\{TERMO}\proj\src\pacote\mod.py")
    (raiz / "dist" / "pacote.zip").write_bytes(_zip_bytes({"src/pacote/__pycache__/mod.cpython-314.pyc": pyc}))
    rc, out = _rodar(capsys, "--raiz", str(raiz), "--termo", TERMO, "--mostrar-termos")
    assert rc == 1
    assert "dist/pacote.zip!/src/pacote/__pycache__/mod.cpython-314.pyc" in out


def test_pycache_no_projeto_nao_e_pulado(tmp_path, capsys):
    raiz = _projeto_limpo(tmp_path / "proj")
    cache = raiz / "src" / "pacote" / "__pycache__"
    cache.mkdir()
    (cache / "mod.cpython-314.pyc").write_bytes(_pyc_com_caminho(f"/home/{TERMO}/proj/mod.py"))
    rc, out = _rodar(capsys, "--raiz", str(raiz), "--termo", TERMO)
    assert rc == 1
    assert "__pycache__/mod.cpython-314.pyc" in out


def test_texto_em_pasta(tmp_path, capsys):
    raiz = _projeto_limpo(tmp_path / "proj")
    (raiz / "docs").mkdir()
    (raiz / "docs" / "notas.md").write_text(f"autor: {TERMO.upper()}\n", encoding="utf-8")
    rc, out = _rodar(capsys, "--raiz", str(raiz), "--termo", TERMO)
    assert rc == 1
    assert "docs/notas.md" in out


def test_binario_utf16le(tmp_path, capsys):
    raiz = _projeto_limpo(tmp_path / "proj")
    (raiz / "dist" / "recurso.bin").write_bytes(b"\x00\x01" * 50 + TERMO.encode("utf-16-le") + b"\xff" * 50)
    rc, out = _rodar(capsys, "--raiz", str(raiz), "--termo", TERMO)
    assert rc == 1
    assert "dist/recurso.bin" in out


def test_zip_aninhado(tmp_path, capsys):
    raiz = _projeto_limpo(tmp_path / "proj")
    interno = _zip_bytes({"profundo/segredo.log.txt": f"C:/Users/{TERMO}/x".encode()})
    meio = _zip_bytes({"meio/interno.zip": interno})
    (raiz / "dist" / "externo.zip").write_bytes(_zip_bytes({"externo/meio.zip": meio}))
    rc, out = _rodar(capsys, "--raiz", str(raiz), "--termo", TERMO)
    assert rc == 1
    assert "dist/externo.zip!/externo/meio.zip!/meio/interno.zip!/profundo/segredo.log.txt" in out


def test_tar_gz(tmp_path, capsys):
    raiz = _projeto_limpo(tmp_path / "proj")
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        dados = f"home/{TERMO}".encode()
        info = tarfile.TarInfo("app/arquivo.txt")
        info.size = len(dados)
        tar.addfile(info, io.BytesIO(dados))
    (raiz / "dist" / "app.tar.gz").write_bytes(buf.getvalue())
    rc, out = _rodar(capsys, "--raiz", str(raiz), "--termo", TERMO)
    assert rc == 1
    assert "app/arquivo.txt" in out


def test_exe_pyinstaller_com_pyz(tmp_path, capsys):
    raiz = _projeto_limpo(tmp_path / "proj")
    code = compile("y = 2\n", rf"C:\Users\{TERMO}\proj\src\pacote\interno.py", "exec")
    exe = _exe_pyinstaller({
        "PYZ.pyz": (_pyz({"pacote.interno": code}), b"z"),
        "leia.txt": (b"neutro", b"x"),
    })
    (raiz / "dist" / "KommoUnirDuplicatas.exe").write_bytes(exe)
    rc, out = _rodar(capsys, "--raiz", str(raiz), "--termo", TERMO)
    assert rc == 1
    assert "KommoUnirDuplicatas.exe!/PYZ.pyz!/pacote.interno" in out


def test_onedir_inteira_e_dados_ao_lado_do_exe(tmp_path, capsys):
    dist = tmp_path / "dist" / "windows"
    app = dist / "KommoUnirDuplicatas"
    (app / "_internal").mkdir(parents=True)
    (app / "KommoUnirDuplicatas.exe").write_bytes(_exe_pyinstaller({"leia.txt": (b"neutro", b"x")}))
    (app / "_internal" / "base_library.zip").write_bytes(
        _zip_bytes({"m.pyc": _pyc_com_caminho(f"/home/{TERMO}/m.py")}))
    (app / "data").mkdir()                       # modo portátil: dados criados ao rodar o app da pasta dist
    (app / "data" / "config.json").write_text("{}", encoding="utf-8")
    rc, out = _rodar(capsys, "--somente-dist", "--dist", str(dist), "--termo", TERMO)
    assert rc == 1
    assert "_internal/base_library.zip!/m.pyc" in out
    assert "[dados_usuario]" in out


def test_dados_usuario_e_artefato_fora_de_dist(tmp_path, capsys):
    raiz = _projeto_limpo(tmp_path / "proj")
    (raiz / "data").mkdir()
    (raiz / "Projeto.zip").write_bytes(_zip_bytes({"a.txt": b"neutro"}))
    rc, out = _rodar(capsys, "--raiz", str(raiz), "--termo", TERMO)
    assert rc == 1
    assert "[dados_usuario] data/" in out
    assert "[artefato_fora_de_dist] Projeto.zip" in out


# ------------------------------------------------------------------------------------------- fail-closed
def test_zip_corrompido_falha(tmp_path, capsys):
    raiz = _projeto_limpo(tmp_path / "proj")
    bom = _zip_bytes({"a.txt": b"x" * 1000})
    (raiz / "dist" / "quebrado.zip").write_bytes(bom[: len(bom) // 2])
    rc, out = _rodar(capsys, "--raiz", str(raiz), "--termo", TERMO)
    assert rc == 1
    assert "ERRO" in out and "quebrado.zip" in out


def test_membro_zip_com_crc_errado_falha(tmp_path, capsys):
    raiz = _projeto_limpo(tmp_path / "proj")
    bom = bytearray(_zip_bytes({"a.txt": b"conteudo"}))
    zipfile.ZipFile(io.BytesIO(bytes(bom)))      # válido antes de estragar
    i = bom.find(b"conteudo")
    if i == -1:                                  # comprimido: estraga o primeiro byte dos dados
        i = 30 + len("a.txt")
    bom[i] ^= 0xFF
    (raiz / "dist" / "crc.zip").write_bytes(bytes(bom))
    rc, out = _rodar(capsys, "--raiz", str(raiz), "--termo", TERMO)
    assert rc == 1
    assert "ERRO" in out


def test_arquivo_ilegivel_falha(tmp_path, capsys, monkeypatch):
    raiz = _projeto_limpo(tmp_path / "proj")
    (raiz / "bloqueado.txt").write_text("qualquer", encoding="utf-8")
    original = vp.ler_arquivo

    def ler(c):
        if Path(c).name == "bloqueado.txt":
            raise PermissionError(13, "Permissão negada")
        return original(c)

    monkeypatch.setattr(vp, "ler_arquivo", ler)
    rc, out = _rodar(capsys, "--raiz", str(raiz), "--termo", TERMO)
    assert rc == 1
    assert "bloqueado.txt" in out and "ilegível" in out


def test_exe_pyinstaller_truncado_falha(tmp_path, capsys):
    raiz = _projeto_limpo(tmp_path / "proj")
    exe = _exe_pyinstaller({"leia.txt": (b"neutro" * 100, b"x")})
    cookie = exe.rfind(vp.MAGIC_CARCHIVE)
    estragado = exe[:210] + exe[cookie:]         # remove os dados, mantém o cookie
    (raiz / "dist" / "KommoUnirDuplicatas.exe").write_bytes(estragado)
    rc, out = _rodar(capsys, "--raiz", str(raiz), "--termo", TERMO)
    assert rc == 1
    assert "ERRO" in out


def test_formato_nao_suportado_falha(tmp_path, capsys):
    raiz = _projeto_limpo(tmp_path / "proj")
    (raiz / "dist" / "pacote.7z").write_bytes(b"7z\xbc\xaf\x27\x1c" + b"\0" * 100)
    rc, out = _rodar(capsys, "--raiz", str(raiz), "--termo", TERMO)
    assert rc == 1
    assert "não suportado" in out


def test_sem_termos_falha(tmp_path, capsys):
    raiz = _projeto_limpo(tmp_path / "proj")
    rc, out = _rodar(capsys, "--raiz", str(raiz))
    assert rc == 1
    assert "nenhum termo" in out


def test_somente_dist_inexistente_falha(tmp_path, capsys):
    rc, out = _rodar(capsys, "--somente-dist", "--dist", str(tmp_path / "nao_existe"), "--termo", TERMO)
    assert rc == 1


def test_uso_invalido_sai_com_1(capsys):
    assert vp.main(["--flag-que-nao-existe"]) == 1


# ------------------------------------------------------------------------------------------- termos e saída
def test_termo_curto_exige_limite_de_palavra():
    t = [vp.Termo(CURTO, "teste")]
    assert vp.procurar_termos(b"ola zecalho mundo", t) == {}
    assert vp.procurar_termos(b"autor: Zeca.", t) == {t[0]: 1}
    assert vp.procurar_termos("x zeca y".encode("utf-16-le"), t) == {t[0]: 1}
    assert vp.procurar_termos("xzecay".encode("utf-16-le"), t) == {}


def test_termos_menores_que_4_sao_descartados():
    termos, descartados = vp.normalizar_termos([vp.Termo("ab", "x"), vp.Termo("abc", "x"), vp.Termo("abcd", "x"),
                                                vp.Termo("ABCD", "y"), vp.Termo(" ", "z")])
    assert [t.valor for t in termos] == ["abcd"]
    assert descartados == 2


def test_binario_de_terceiro_so_conta_formato_de_caminho():
    t = [vp.Termo(TERMO, "teste")]
    assert vp.eh_binario_terceiro("_internal/playwright/driver/node.exe")
    assert vp.procurar_termos(b"tabela icu " + TERMO.encode(), t, somente_caminho=True) == {}
    assert vp.procurar_termos(rb"C:\Users" + b"\\" + TERMO.encode(), t, somente_caminho=True) == {t[0]: 1}


def test_saida_mascara_termos_por_padrao(tmp_path, capsys):
    raiz = _projeto_limpo(tmp_path / "proj")
    (raiz / f"notas-{TERMO}.txt").write_text(TERMO, encoding="utf-8")
    rc, out = _rodar(capsys, "--raiz", str(raiz), "--termo", TERMO)
    assert rc == 1
    assert TERMO not in out.lower()
    assert "ful***#" in out
    rc, out = _rodar(capsys, "--raiz", str(raiz), "--termo", TERMO, "--mostrar-termos")
    assert TERMO in out


def test_saida_json(tmp_path, capsys):
    raiz = _projeto_limpo(tmp_path / "proj")
    (raiz / "a.txt").write_text(TERMO, encoding="utf-8")
    rc, out = _rodar(capsys, "--raiz", str(raiz), "--termo", TERMO, "--json")
    d = json.loads(out)
    assert rc == 1 and d["ok"] is False
    assert d["achados"][0]["local"] == "a.txt"
    assert TERMO not in out


def test_variavel_de_ambiente_e_argumentos(monkeypatch, tmp_path):
    monkeypatch.setenv("KOMMO_DATA_DIR", str(tmp_path))   # não ler o config.json real do usuário
    monkeypatch.setenv("KOMMO_TERMOS_SENSIVEIS", "empresaxyz, outraempresa ,")
    termos, _ = vp.coletar_termos(["argumentoabc"], incluir_sistema=False, raiz=tmp_path)
    assert {t.valor for t in termos} == {"empresaxyz", "outraempresa", "argumentoabc"}


def test_termos_do_sistema_nao_falham_sem_git(monkeypatch):
    monkeypatch.setattr(vp.shutil, "which", lambda _n: None)
    termos = vp.termos_do_sistema({"USERPROFILE": "", "HOME": ""})
    assert all(isinstance(t, vp.Termo) for t in termos)


@pytest.mark.skipif(not hasattr(vp, "caminho_curto_windows"), reason="sem função")
def test_caminho_curto_nao_explode():
    assert isinstance(vp.caminho_curto_windows(str(Path.home())), str)
