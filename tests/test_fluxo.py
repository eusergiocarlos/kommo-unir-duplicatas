import pytest

from kommo_duplicatas.fluxo import Resultado, avaliar_uniao, progresso_concluido
from kommo_duplicatas.kommo import Estado

CAP_1 = "Localizar e unir duplicatas — 1 de 42770"
CAP_2 = "Localizar e unir duplicatas — 1 de 42769"
CAP_MUITAS = "Localizar e unir duplicatas — 1 de muitas"
CONCLUIDO = "União de contatos concluída com sucesso"
UNINDO = "Realizando união"

ANTES = Estado(modal=True, pode=True, caption=CAP_1)
ANTES_MUITAS = Estado(modal=True, pode=True, caption=CAP_MUITAS)


@pytest.mark.parametrize("texto,esperado", [
    (CONCLUIDO, True),
    ("UNIÃO DE LEADS CONCLUÍDA", True),
    ("Uniao de leads concluida", True),
    ("Concluído", True),
    (UNINDO, False),
    ("Unindo leads", False),
    ("", False),
    (None, False),
])
def test_progresso_concluido(texto, esperado):
    assert progresso_concluido(texto) is esperado


CASOS = [
    # (nome, antes, depois, visto_progresso, ultimo_progresso, esperado)
    ("título muda + concluída", ANTES, Estado(modal=True, pode=True, caption=CAP_2), True, CONCLUIDO,
     Resultado.SUCESSO),
    ("título muda sem progresso visto", ANTES, Estado(modal=True, pode=True, caption=CAP_2), False, "",
     Resultado.SUCESSO),
    ("título muda após progresso sem conclusão", ANTES, Estado(modal=True, pode=True, caption=CAP_2), True, UNINDO,
     Resultado.SUCESSO),
    ("'muitas' com título igual + concluída", ANTES_MUITAS, Estado(modal=True, pode=True, caption=CAP_MUITAS),
     True, "União de leads concluída", Resultado.SUCESSO),
    ("progresso some e o mesmo grupo volta", ANTES, Estado(modal=True, pode=True, caption=CAP_1), True, UNINDO,
     Resultado.INCERTO),
    ("modal fecha após progresso concluído", ANTES, Estado(), True, CONCLUIDO, Resultado.SUCESSO),
    ("modal fecha após progresso sem conclusão", ANTES, Estado(), True, UNINDO, Resultado.SUCESSO),
    ("modal fecha sem progresso", ANTES, Estado(), False, "", Resultado.SUCESSO),
    ("erro no modal durante a união", ANTES, Estado(modal=True, erro=True), True, UNINDO, Resultado.ERRO),
    ("erro mesmo com conclusão", ANTES, Estado(modal=True, erro=True), True, CONCLUIDO, Resultado.ERRO),
    ("nada mudou, sem progresso", ANTES, Estado(modal=True, pode=True, caption=CAP_1), False, "",
     Resultado.AGUARDA),
    ("progresso em andamento", ANTES, Estado(modal=True, progresso=UNINDO), True, UNINDO, Resultado.AGUARDA),
    ("'concluída' ainda na tela", ANTES, Estado(modal=True, progresso=CONCLUIDO), True, CONCLUIDO,
     Resultado.AGUARDA),
    ("página navegando após conclusão", ANTES, Estado(navegou=True), True, CONCLUIDO, Resultado.SUCESSO),
    ("página navegando sem conclusão", ANTES, Estado(navegou=True), True, UNINDO, Resultado.AGUARDA),
    ("modal aberto carregando, sem botão", ANTES, Estado(modal=True, caption=CAP_1), True, UNINDO,
     Resultado.AGUARDA),
    ("nunca houve modal e continua sem", Estado(), Estado(), False, "", Resultado.AGUARDA),
    ("conclusão só em depois.progresso, sem ultimo_progresso", ANTES, Estado(modal=True, progresso=CONCLUIDO),
     False, "", Resultado.AGUARDA),
]


@pytest.mark.parametrize("nome,antes,depois,visto,ultimo,esperado", CASOS, ids=[c[0] for c in CASOS])
def test_avaliar_uniao(nome, antes, depois, visto, ultimo, esperado):
    assert avaliar_uniao(antes, depois, visto, ultimo) is esperado


def test_sequencia_com_fake():
    """Roteiro típico de Contatos lido por um FakeKommo: só o último estado confirma."""
    from fakes import FakeKommo

    fake = FakeKommo([
        Estado(modal=True, progresso=UNINDO),
        Estado(modal=True, progresso=CONCLUIDO),
        Estado(modal=True, pode=True, caption=CAP_2),
    ])
    visto, ultimo, resultados = False, "", []
    for _ in range(3):
        est = fake.estado()
        if est.progresso:
            visto, ultimo = True, est.progresso
        resultados.append(avaliar_uniao(ANTES, est, visto, ultimo))
    assert resultados == [Resultado.AGUARDA, Resultado.AGUARDA, Resultado.SUCESSO]
    assert fake.chamadas == ["estado"] * 3
    assert fake.estado() == Estado(modal=True, pode=True, caption=CAP_2)   # repete o último


def test_fake_implementa_porta():
    from fakes import FakeKommo

    from kommo_duplicatas.kommo import PortaKommo
    assert isinstance(FakeKommo(), PortaKommo)
