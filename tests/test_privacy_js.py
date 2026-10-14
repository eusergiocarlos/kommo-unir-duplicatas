"""Testes REAIS do JS do modo privacidade, no Chromium headless do Playwright (sem Kommo, sem perfil do usuário).

A fixture é servida por `page.route` num endereço fictício (https://kommo.test/...), para o init script rodar como
numa navegação de verdade (início do documento). Nenhum teste chama `aplicar()`/`JS_APLICAR` (sem polling), exceto
onde está dito explicitamente.
"""
import os
import time

import pytest

from kommo_duplicatas import privacy

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
URL = "https://kommo.test/leads/list/"

# Verdadeiro se o elemento ou algum ancestral tem filtro de blur aplicado (o que de fato aparece na tela).
JS_BORRADO = """(sel) => {
  let e = document.querySelector(sel);
  if (!e) throw new Error('não achei ' + sel);
  for (; e && e.nodeType === 1; e = e.parentElement) {
    if ((getComputedStyle(e).filter || '').includes('blur')) return true;
  }
  return false;
}"""


def _html(nome: str) -> str:
    with open(os.path.join(FIXTURES, nome), encoding="utf-8") as f:
        return f.read()


@pytest.fixture(scope="module")
def navegador():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:  # pragma: no cover - depende do ambiente
        pytest.skip(f"Playwright não instalado: {e}")
    pw = sync_playwright().start()
    try:
        b = pw.chromium.launch(headless=True)
    except Exception as e:  # noqa: BLE001 - ex.: Chromium do Playwright não baixado
        pw.stop()
        pytest.skip(f"Não foi possível lançar o Chromium headless do Playwright: {e}")
    yield b
    b.close()
    pw.stop()


def _abrir(navegador, ligado: bool, html: str | None = None, extras=()):
    """Contexto novo com init_script(ligado) e a fixture servida por rota; devolve (ctx, page)."""
    ctx = navegador.new_context()
    ctx.add_init_script(privacy.init_script(ligado))
    for s in extras:
        ctx.add_init_script(s)
    corpo = html if html is not None else _html("privacy_kommo_lista.html")
    ctx.route("https://kommo.test/**",
              lambda r: r.fulfill(status=200, content_type="text/html; charset=utf-8", body=corpo))
    page = ctx.new_page()
    page.goto(URL, wait_until="load")
    return ctx, page


SENSIVEIS = ["#total-classe", "#total-livre", "#aviso-limite", "#uso-conta", "#nome-1", "#valor-1", "#tel-1",
             "#nome-2", "#mail-2", "#fr-nome", "#fr-texto", "#mf-nome", "#cb-texto", "#tooltip", "#toast", "#avatar"]
PROCESSO = ["#caption", "#btn-unir", "#btn-pular", "#progresso", "#menu-mais", "#texto-neutro"]


# (a) tudo que é sensível já está borrado sem nenhuma chamada de polling
def test_a_borra_sensiveis_sem_polling(navegador):
    ctx, page = _abrir(navegador, True)
    try:
        assert page.evaluate("document.documentElement.classList.contains('kp-privacy')")
        nao = [s for s in SENSIVEIS if not page.evaluate(JS_BORRADO, s)]
        assert nao == [], f"não borrados: {nao}"
        # "9195 leads: R$ 4.596" num div sem classe conhecida foi pego pela regex (kp-sens), não pelo CSS de classe
        assert page.evaluate("document.querySelector('#total-livre').classList.contains('kp-sens')")
        # tooltips: title retirado dentro da lista, mas o title="Mais" usado pelo kommo.py fica
        assert page.evaluate("document.querySelector('#nome-1').getAttribute('title')") is None
        assert page.evaluate("document.querySelector('#nome-1').getAttribute('data-kp-title')") == "Fulano de Tal"
        assert page.evaluate("document.querySelector('#menu-mais').getAttribute('title')") == "Mais"
    finally:
        ctx.close()


def test_a_borra_desde_o_inicio_do_documento(navegador):
    """Um script inline no meio do parse já vê a classe ligada e o elemento sensível anterior marcado."""
    html = ("<!doctype html><html><head><title>Kommo: Login, Empresa</title></head><body>"
            "<div id='v'>R$ 99,90</div>"
            "<script>window.__durante = {classe: document.documentElement.classList.contains('kp-privacy'),"
            " sens: document.getElementById('v').classList.contains('kp-sens'),"
            " filtro: getComputedStyle(document.getElementById('v')).filter, titulo: document.title};</script>"
            "</body></html>")
    ctx, page = _abrir(navegador, True, html)
    try:
        d = page.evaluate("window.__durante")
        assert d["classe"] is True
        assert d["sens"] is True
        assert "blur" in d["filtro"]
        assert d["titulo"] == "Kommo"
    finally:
        ctx.close()


# (b) elemento inserido depois é marcado na mesma microtarefa (antes da próxima pintura)
def test_b_elemento_dinamico_marcado_em_ms(navegador):
    ctx, page = _abrir(navegador, True)
    try:
        r = page.evaluate("""async () => {
          const t0 = performance.now();
          const d = document.createElement('div'); d.id = 'novo'; d.textContent = 'R$ 1.234,00';
          document.body.appendChild(d);
          await Promise.resolve();          // o callback do MutationObserver roda antes desta continuação
          const ms = performance.now() - t0;
          return {sens: d.classList.contains('kp-sens'), filtro: getComputedStyle(d).filter, ms};
        }""")
        print(f"\n[medido] elemento dinâmico marcado em {r['ms']:.3f} ms")
        assert r["sens"] is True
        assert "blur" in r["filtro"]
        # texto que deixa de ser sensível perde a classe (SPA reaproveita o elemento)
        assert page.evaluate("""async () => {
          const d = document.getElementById('novo'); d.textContent = 'Sem dado';
          await Promise.resolve();
          return d.classList.contains('kp-sens');
        }""") is False
        # characterData: texto alterado num nó de texto existente
        assert page.evaluate("""async () => {
          const d = document.getElementById('texto-neutro'); d.firstChild.data = 'Total 12 contatos';
          await Promise.resolve();
          return d.classList.contains('kp-sens');
        }""") is True
        # title adicionado depois num elemento da lista é retirado
        assert page.evaluate("""async () => {
          const a = document.getElementById('valor-1'); a.setAttribute('title', 'Fulano');
          await Promise.resolve();
          return a.getAttribute('title');
        }""") is None
    finally:
        ctx.close()


# (c) o título fica "Kommo" mesmo com a página tentando trocar (setter, <title> direto, durante o parse)
def test_c_titulo_travado(navegador):
    ctx, page = _abrir(navegador, True)
    try:
        page.wait_for_timeout(120)       # os setTimeout(20/40 ms) da fixture já rodaram
        assert page.title() == "Kommo"
        assert page.evaluate("document.querySelector('title').textContent") == "Kommo"
        titulo = page.evaluate("""async () => {
          document.title = 'Kommo: Leads, Outra';
          const t = document.createElement('title'); t.textContent = 'Kommo: Leads, Mais Uma';
          document.head.appendChild(t);
          await Promise.resolve();
          return document.title;
        }""")
        assert titulo == "Kommo"
        # sem laço: depois de estabilizar, o observer fica parado
        lotes = page.evaluate("window.__kpEstado().stats.lotes")
        page.wait_for_timeout(100)
        assert page.evaluate("window.__kpEstado().stats.lotes") == lotes
    finally:
        ctx.close()


# (d) os textos do processo continuam legíveis
def test_d_processo_nao_borrado(navegador):
    ctx, page = _abrir(navegador, True)
    try:
        borrados = [s for s in PROCESSO if page.evaluate(JS_BORRADO, s)]
        assert borrados == [], f"borrados indevidamente: {borrados}"
    finally:
        ctx.close()


# (e) desligado: nada borrado, título original; __kpSet liga e desliga em tempo de execução
def test_e_desligado_nao_borra_e_kpset_alterna(navegador):
    ctx, page = _abrir(navegador, False)
    try:
        borrados = [s for s in SENSIVEIS + PROCESSO if page.evaluate(JS_BORRADO, s)]
        assert borrados == []
        assert page.evaluate("document.documentElement.classList.contains('kp-privacy')") is False
        assert page.evaluate("document.querySelectorAll('.kp-sens').length") == 0
        assert page.title() != "Kommo"
        assert page.evaluate("document.querySelector('#nome-1').getAttribute('title')") == "Fulano de Tal"

        page.evaluate("window.__kpSet(true)")
        assert all(page.evaluate(JS_BORRADO, s) for s in SENSIVEIS)
        assert page.title() == "Kommo"
        page.evaluate("window.__kpSet(false)")
        assert not any(page.evaluate(JS_BORRADO, s) for s in SENSIVEIS)
        assert page.title() != "Kommo"
        assert page.evaluate("document.querySelector('#nome-1').getAttribute('title')") == "Fulano de Tal"
    finally:
        ctx.close()


def test_e_ultimo_init_script_decide(navegador):
    """Registrar init_script(novo) depois persiste a troca nas próximas navegações (sem storage)."""
    ctx, page = _abrir(navegador, True, extras=[privacy.init_script(False)])
    try:
        assert page.evaluate("window.__kpEstado().on") is False
        assert not page.evaluate(JS_BORRADO, "#total-livre")
    finally:
        ctx.close()


def test_init_script_nao_usa_storage(navegador):
    """Primeira execução: storage vazio/bloqueado não muda nada."""
    bloquear = ("Object.defineProperty(window, 'localStorage', {get() { throw new Error('bloqueado'); }});"
                "Object.defineProperty(window, 'sessionStorage', {get() { throw new Error('bloqueado'); }});")
    ctx = navegador.new_context()
    ctx.add_init_script(bloquear)
    ctx.add_init_script(privacy.init_script(True))
    corpo = _html("privacy_kommo_lista.html")
    ctx.route("https://kommo.test/**", lambda r: r.fulfill(status=200, content_type="text/html", body=corpo))
    try:
        page = ctx.new_page()
        page.goto(URL, wait_until="load")
        assert page.evaluate(JS_BORRADO, "#total-livre")
    finally:
        ctx.close()


def test_notificacoes_do_navegador_anonimizadas(navegador):
    ctx, page = _abrir(navegador, True)
    try:
        r = page.evaluate("""() => {
          const n = new Notification('Fulano de Tal', {body: 'Oi, tudo bem?', icon: 'https://x/a.png'});
          const swr = window.ServiceWorkerRegistration;
          return {titulo: n.title, corpo: n.body, icone: n.icon, perm: Notification.permission,
                  sw: !!(swr && swr.prototype.showNotification.__kp)};
        }""")
        assert r["titulo"] == "Kommo"
        assert r["corpo"] == ""
        assert r["icone"] == ""
        assert r["perm"] in ("default", "denied", "granted")   # estático herdado continua funcionando
        assert r["sw"] is True
        page.evaluate("window.__kpSet(false)")
        assert page.evaluate("new Notification('Fulano', {body: 'x'}).title") == "Fulano"
    finally:
        ctx.close()


def test_aplicar_reforco_usa_kpset(navegador):
    """aplicar() (reforço do Python) usa o init script; sem ele cai no JS_APLICAR legado."""
    ctx, page = _abrir(navegador, True)
    try:
        assert privacy.aplicar(page, False) is True
        assert not page.evaluate(JS_BORRADO, "#total-livre")
        assert privacy.aplicar(page, True) is True
        assert page.evaluate(JS_BORRADO, "#total-livre")
    finally:
        ctx.close()
    ctx = navegador.new_context()
    try:
        page = ctx.new_page()
        page.set_content(_html("privacy_kommo_lista.html"))
        assert privacy.aplicar(page, True) is False          # fallback legado
        assert page.evaluate(JS_BORRADO, "#total-classe")
    finally:
        ctx.close()


# (f) desempenho: 5.000 linhas inseridas
LINHAS_JS = """(n) => {
  const frag = document.createDocumentFragment();
  for (let i = 0; i < n; i++) {
    const r = document.createElement('div'); r.className = 'js-list-row list-row';
    r.innerHTML = '<div class="list-row__cell"><a class="list-row__template-name__name" title="Nome ' + i + '">Nome '
      + i + '</a></div><div class="list-row__cell"><span class="v">R$ ' + i + ',00</span></div>'
      + '<div class="list-row__cell"><span>' + (i % 50) + ' contatos</span></div>'
      + '<div class="list-row__cell"><span>Etapa inicial</span></div>';
    frag.appendChild(r);
  }
  return frag;
}"""


def test_f_desempenho_5000_linhas(navegador):
    ctx, page = _abrir(navegador, True)
    try:
        # 1) um lote só (fragmento com 5.000 linhas)
        r1 = page.evaluate("""async (src) => {
          const criar = eval(src);
          const frag = criar(5000);
          const antes = window.__kpEstado().stats.ms;
          const t0 = performance.now();
          document.getElementById('lista').appendChild(frag);
          await Promise.resolve();
          const tObs = performance.now() - t0;
          document.body.offsetHeight;          // força estilo/layout (custo do CSS com :has)
          const tTotal = performance.now() - t0;
          return {tObs, tTotal, obsMs: window.__kpEstado().stats.ms - antes,
                  marcados: document.querySelectorAll('#lista .v.kp-sens').length,
                  titles: document.querySelectorAll('#lista [title]').length};
        }""", LINHAS_JS)
        # 2) 5.000 appendChild separados na mesma tarefa (5.000 registros num único callback)
        r2 = page.evaluate("""async (src) => {
          const criar = eval(src);
          const filhos = [...criar(5000).children];
          const box = document.createElement('div'); box.id = 'lista2'; document.body.appendChild(box);
          await Promise.resolve();
          const antes = window.__kpEstado().stats.ms;
          const t0 = performance.now();
          for (const f of filhos) box.appendChild(f);
          await Promise.resolve();
          const tObs = performance.now() - t0;
          return {tObs, obsMs: window.__kpEstado().stats.ms - antes,
                  marcados: document.querySelectorAll('#lista2 .v.kp-sens').length};
        }""", LINHAS_JS)
        # 3) 200 linhas, uma por tarefa, com ~10.000 linhas já na página (custo incremental, não O(n))
        r3 = page.evaluate("""async (src) => {
          const criar = eval(src);
          const antes = window.__kpEstado().stats;
          const t0 = performance.now();
          for (let i = 0; i < 200; i++) {
            document.getElementById('lista').appendChild(criar(1).firstChild);
            await new Promise((ok) => setTimeout(ok, 0));
          }
          const depois = window.__kpEstado().stats;
          return {tTotal: performance.now() - t0, obsMs: depois.ms - antes.ms, lotes: depois.lotes - antes.lotes,
                  msMax: depois.msMax};
        }""", LINHAS_JS)
        # referência: a varredura legada (JS_APLICAR) sobre o mesmo documento (~10.000 linhas)
        t0 = time.perf_counter()
        legado = page.evaluate("""(js) => {
          const f = eval(js); window.__kpT = 0;
          const t0 = performance.now(); f([true, '']); return performance.now() - t0;
        }""", privacy.JS_APLICAR)
        ida_volta = (time.perf_counter() - t0) * 1000
        print(f"\n[medido] lote único 5.000 linhas: observer {r1['obsMs']:.1f} ms; inserção+observer "
              f"{r1['tObs']:.1f} ms; +estilo/layout {r1['tTotal']:.1f} ms; marcados {r1['marcados']}; "
              f"titles restantes {r1['titles']}")
        print(f"[medido] 5.000 appendChild separados: observer {r2['obsMs']:.1f} ms; total {r2['tObs']:.1f} ms; "
              f"marcados {r2['marcados']}")
        print(f"[medido] 200 linhas uma por tarefa (~10.000 na página): observer {r3['obsMs']:.1f} ms em "
              f"{r3['lotes']} lotes (máx. por lote desde o início {r3['msMax']:.1f} ms); total {r3['tTotal']:.0f} ms")
        print(f"[medido] varredura legada JS_APLICAR no mesmo DOM: {legado:.1f} ms (ida e volta {ida_volta:.0f} ms)")
        assert r1["marcados"] == 5000
        assert r1["titles"] == 0
        assert r2["marcados"] == 5000
        assert r3["lotes"] >= 200
    finally:
        ctx.close()
