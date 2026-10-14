import pytest

from kommo_duplicatas.limite import (LIMITE_EXIGE_DIGITAR, LIMITE_MAXIMO, descrever_limite, exige_digitar,
                                     parse_limite)


@pytest.mark.parametrize("texto,preset,esperado", [
    ("", 500, 500),                 # vazio → opção marcada
    ("   ", 200, 200),
    ("\t", 100, 100),
    ("", 0, 0),                     # preset "Todas"
    (None, 100, 100),
    ("1000", 100, 1000),
    ("1.000", 100, 1000),
    ("1 000", 100, 1000),
    ("1 000", 100, 1000),      # espaço não separável
    ("1 000", 100, 1000),      # espaço fino
    ("  300  ", 100, 300),
    ("12.345", 100, 12345),
    ("999.999", 100, 999999),
    ("1", 500, 1),
    ("007", 500, 7),
    ("0", 500, 0),                  # texto "0" = todas
    ("000", 500, 0),
])
def test_validos(texto, preset, esperado):
    assert parse_limite(texto, preset) == esperado


@pytest.mark.parametrize("texto,trecho", [
    ("-5", "negativa"),
    ("-1.000", "negativa"),
    ("50,", "decimais"),
    ("1,5", "decimais"),
    ("1.5", "decimais"),
    ("10.00", "decimais"),
    (",5", "decimais"),
    ("abc", "inválida"),
    ("10a", "inválida"),
    ("²", "inválida"),               # "²".isdigit() é True — o bug antigo
    ("1²", "inválida"),
    ("١٢", "inválida"),              # dígitos árabe-índicos
    ("​", "inválida"),          # espaço de largura zero
    ("1​000", "inválida"),
    ("1.000 000", "inválida"),       # separadores misturados
    ("1..000", "inválida"),
    ("1.0000", "inválida"),
    ("+5", "inválida"),
    ("1e3", "inválida"),
    ("1000000", "muito alta"),
    ("1.000.000", "muito alta"),
])
def test_invalidos_levantam_com_mensagem(texto, trecho):
    with pytest.raises(ValueError) as exc:
        parse_limite(texto, 500)
    msg = str(exc.value)
    assert trecho in msg
    assert "Quantidade" in msg          # mensagem pronta para exibir, em português


def test_nunca_usa_preset_em_silencio_quando_invalido():
    for texto in ("1,000", "50,", "x"):
        with pytest.raises(ValueError):
            parse_limite(texto, 500)


def test_mensagem_trunca_texto_enorme():
    with pytest.raises(ValueError) as exc:
        parse_limite("x" * 500, 100)
    assert len(str(exc.value)) < 300


def test_maximo():
    assert parse_limite(str(LIMITE_MAXIMO), 0) == LIMITE_MAXIMO


@pytest.mark.parametrize("n,txt", [(0, "todas"), (1, "1"), (100, "100"), (1000, "1.000"), (123456, "123.456")])
def test_descrever(n, txt):
    assert descrever_limite(n) == txt


def test_exige_digitar():
    assert exige_digitar(0)                           # todas
    assert not exige_digitar(1)
    assert not exige_digitar(LIMITE_EXIGE_DIGITAR)
    assert exige_digitar(LIMITE_EXIGE_DIGITAR + 1)
