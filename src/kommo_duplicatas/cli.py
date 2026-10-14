"""Modo texto (sem janela): útil para testar e para rodar em terminal.

    python main.py --cli minhaempresa contatos 10
    python main.py --cli minhaempresa leads 0 --sem-privacidade     (0 = todas)
    python main.py --cli minhaempresa leads 3 --ensaio              (abre e confere, não une nada)
    python main.py --cli minhaempresa contatos 10 --sim              (confirma a conta sem perguntar)

Antes da 1ª união o motor pede a confirmação da conta (a ação é irreversível): o terminal pergunta [s/N], ou
`--sim` responde que sim. Ctrl+C uma vez: para depois da união em andamento; duas vezes: força a parada.

Privacidade (padrão; `--sem-privacidade` desliga): o que é impresso no terminal e gravado no arquivo de log sai
com o subdomínio mascarado ("a***e") e os totais da conta como "••••" — mesma regra da janela (mascara.py).
Na pergunta de confirmação, responder "m" mostra a conta completa só no terminal (não vai para o log).

Código de saída: 0 = terminou bem (limite, sem duplicatas, ensaio); 2 = parado/recusado/sem resposta;
3 = não confirmado (`busca_sem_resposta`: o Kommo não mostrou novos grupos nem "nenhuma duplicata" — pode não haver
mais duplicatas ou a busca estar lenta; confira no Kommo); 1 = qualquer erro; 64 = erro de uso (argumentos
inválidos — EX_USAGE, para não se confundir com o 2).
"""
import argparse
import queue
import threading

from . import kommo, logs
from .mascara import OCULTO, mascarar_host, mascarar_mensagem
from .merger import MOTIVOS, ConfirmarEvt, FimEvt, Job, LogEvt, Merger

MOTIVOS_OK = ("limite", "sem_duplicatas", "ensaio")
MOTIVOS_PARADA = ("parado", "forcado", "recusado", "sem_resposta")
EX_NAO_CONFIRMADO = 3   # busca_sem_resposta: nunca é sucesso (A1)
EX_USAGE = 64   # erro de uso da linha de comando (sysexits.h); o argparse sairia com 2, que aqui é "parado"


class Parser(argparse.ArgumentParser):
    """ArgumentParser cujos erros de uso saem com 64 (EX_USAGE) em vez do 2 padrão do argparse."""

    def error(self, message):
        self.print_usage()
        self.exit(EX_USAGE, f"{self.prog}: erro: {message}\n")


def limite_valido(texto: str) -> int:
    """Tipo do argparse: inteiro >= 0 (0 = todas)."""
    try:
        n = int(texto)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError(f"quantidade inválida: {texto!r} (use um inteiro; 0 = todas)") from None
    if n < 0:
        raise argparse.ArgumentTypeError("a quantidade não pode ser negativa (0 = todas)")
    return n


def _linha_conta(ev: ConfirmarEvt, mascarar: bool) -> str:
    """'Conta logada: … · lista: … · total informado pelo Kommo: …' (host/total mascarados se `mascarar`)."""
    host = mascarar_host(ev.host) if mascarar else (ev.host or "?")
    if not ev.total:
        total = "não informado"
    else:
        total = OCULTO if mascarar else f"{ev.total}"
    return f"Conta logada: {host} · lista: {ev.tipo} · total informado pelo Kommo: {total}"


def perguntar_confirmacao(ev: ConfirmarEvt, entrada=input, saida=print, privacidade: bool = False) -> bool:
    """Pergunta no terminal se a conta está certa. Só "s"/"sim" confirmam; EOF/vazio = não.

    Com `privacidade`, a conta e o total aparecem mascarados; "m"/"mostrar" reexibe a linha completa (só no
    terminal, nunca no log) e pergunta de novo — equivalente ao botão "Mostrar conta" da janela.
    """
    qtd = "todas as" if not ev.limite else f"até {ev.limite}"
    acao = "ENSAIO (nada será unido)" if ev.ensaio else f"unir {qtd} duplicatas — IRREVERSÍVEL"
    saida(f"\n{_linha_conta(ev, privacidade)}\nAção: {acao}", flush=True)
    pergunta = "Confirma? [s/N, m = mostrar a conta] " if privacidade else "Confirma? [s/N] "
    while True:
        try:
            resp = str(entrada(pergunta) or "").strip().lower()
        except EOFError:
            return False
        if privacidade and resp in ("m", "mostrar"):
            saida(_linha_conta(ev, False), flush=True)
            pergunta = "Confirma? [s/N] "
            continue
        return resp in ("s", "sim", "y", "yes")


def main(argv=None, entrada=input, saida=print) -> int:
    ap = Parser(prog="kommo-unir-duplicatas --cli")
    ap.add_argument("empresa", help="subdomínio (ex.: minhaempresa)")
    ap.add_argument("tipo", choices=["leads", "contatos"])
    ap.add_argument("limite", type=limite_valido, help="quantidade de uniões (0 = todas)")
    ap.add_argument("--sem-privacidade", action="store_true", help="não borrar dados sensíveis")
    ap.add_argument("--ensaio", action="store_true", help="abre o modal e confere a conta, sem unir nada")
    ap.add_argument("--sim", action="store_true", help="confirma a conta automaticamente (sem perguntar)")
    a = ap.parse_args(argv)

    empresa = kommo.normalizar_empresa(a.empresa)
    if not empresa:
        ap.error("subdomínio inválido")
    privacidade = not a.sem_privacidade
    fila = queue.Queue()
    th = Merger(Job(empresa, a.tipo, a.limite, privacidade, ensaio=a.ensaio, confirmar_conta=True),
                fila, threading.Event())
    th.start()
    fim = None
    pedidos = 0
    # Drena a fila até a thread terminar E a fila esvaziar (inclusive depois de Ctrl+C).
    while th.is_alive() or not fila.empty():
        try:
            try:
                ev = fila.get(timeout=0.5)
            except queue.Empty:
                continue
            if isinstance(ev, LogEvt):
                # Mascara ANTES de imprimir e de gravar: terminal e arquivo de log recebem a mesma linha.
                saida(logs.gravar(ev.nivel, mascarar_mensagem(ev.msg, empresa, privacidade)), flush=True)
            elif isinstance(ev, ConfirmarEvt):
                th.responder(True if a.sim else perguntar_confirmacao(ev, entrada, saida, privacidade))
            elif isinstance(ev, FimEvt):
                fim = ev
        except KeyboardInterrupt:
            pedidos += 1
            if pedidos == 1:
                saida("Parando depois da união em andamento… (Ctrl+C de novo força a parada)", flush=True)
                th.solicitar_parada()
            else:
                saida("Forçando a parada…", flush=True)
                th.solicitar_parada(forcar=True)
    th.join()

    if fim is None:
        saida("O processo terminou sem resumo — confira o log.", flush=True)
        return 1
    partes = [f"{fim.confirmadas} confirmadas"]
    if fim.incertas:
        partes.append(f"{fim.incertas} não confirmadas")
    partes += [f"{fim.cliques} cliques em Unir", f"{fim.erros} erros", f"{fim.segundos:.0f}s"]
    saida(f"Resumo: {', '.join(partes)} — {MOTIVOS.get(fim.motivo, fim.motivo)}.", flush=True)
    if fim.motivo == "busca_sem_resposta":
        saida(f"Atenção: o Kommo não mostrou novos grupos de duplicatas em {fim.espera_busca:.0f}s. Pode não haver "
              "mais duplicatas ou a busca estar lenta — confira no Kommo.", flush=True)
    if fim.motivo in MOTIVOS_OK and not fim.erros:
        return 0
    if fim.motivo in MOTIVOS_PARADA:
        return 2
    if fim.motivo == "busca_sem_resposta" and not fim.erros:
        return EX_NAO_CONFIRMADO
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
