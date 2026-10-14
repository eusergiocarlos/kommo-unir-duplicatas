"""Modo privacidade: borra no navegador tudo que é dado sensível, para poder gravar a tela / apresentar o app.

Base (desde a T7): um script de início de documento montado em Python com o estado embutido
(`init_script(ligado)`), registrado com `context.add_init_script`. Ele roda em toda navegação, antes dos scripts
da página, e por isso cobre também a tela de login, a primeira carga da lista e a primeira execução (não depende
de `localStorage`). Camadas:

1. CSS por seletores conhecidos (`SELETORES`: linhas das listas, nomes, telefones, e-mails, conta, chat, modal de
   duplicatas, tooltips, toasts...), ativado pela classe `kp-privacy` no `<html>`. A folha entra por
   `document.adoptedStyleSheets` (funciona mesmo antes de existir `<html>`/`<head>`).
2. `MutationObserver` (childList + subtree + characterData + atributo `title`) que só examina os nós
   adicionados/alterados — nunca o documento inteiro a cada mudança. Elementos "folha" cujo texto casa com
   `REGEX_SENSIVEL` (R$, "N leads/contatos/empresas", %, N/NNN, "limite") recebem `kp-sens`; se o texto deixa de ser
   sensível a classe é retirada. A leitura do texto para em 60 caracteres (TreeWalker), então elementos grandes não
   custam O(n). Os registros de uma mesma tarefa chegam juntos num único callback (microtarefa, antes da pintura):
   não há quadro intermediário sem borrão.
3. Título da aba travado em "Kommo": `document.title` é interceptado e o `<title>` é observado (o reforço só
   escreve quando o valor difere, então não há laço).
4. Tooltips: o atributo `title` é retirado (guardado em `data-kp-title`) de elementos sensíveis, de elementos dentro
   das listas/modal/chat e de qualquer `title` cujo texto case com a regex.
5. Notificações do navegador criadas pela página (`new Notification(...)` e
   `ServiceWorkerRegistration.showNotification`) saem com título "Kommo" e sem corpo/ícone.

O estado pode ser trocado em tempo de execução por `window.__kpSet(on)` (é o que `aplicar()` faz). O polling do
Python virou só reforço: `aplicar(page, ligado)`.

Compatibilidade: `JS_INIT`, `JS_APLICAR` e `CSS` continuam existindo e funcionando para o `merger.py` atual, mas
estão OBSOLETOS — use `init_script()` e `aplicar()`.

LIMITAÇÕES REAIS (o que este módulo não consegue esconder):
- Barra de endereço do navegador: mostra `<empresa>.kommo.com` e não é acessível por página/CSS.
- Notificações do sistema operacional disparadas pelo service worker do Kommo a partir de um *push* (sem passar
  pela página) não passam pelo script — o init script não roda em workers. Mitigação fora deste módulo: abrir o
  navegador com notificações bloqueadas (ex.: argumento `--disable-notifications` do Chromium ou permissão negada
  no perfil) quando a privacidade estiver ligada.
- Este módulo cuida só do NAVEGADOR. A janela do app (Tkinter) e o arquivo de log se protegem à parte
  (`mascara.py`/`ui.py`: subdomínio "a***e" e totais "••••" com a privacidade ligada); o subdomínio aparece em claro
  só enquanto o campo "Empresa" está em edição. No navegador, o título do modal ("N de TOTAL") e a barra de endereço
  continuam legíveis de propósito/por limitação (ver docs/security/seguranca.md, limitações conhecidas).
- Título: o parser pode pôr o título original no `<title>` e o observer o troca na mesma microtarefa; em teoria o
  navegador pode chegar a repassar o valor original à barra de tarefas por milissegundos antes da troca.
- Telas, pop-ups e widgets não mapeados (novas versões do Kommo, integrações em iframe de outra origem, PDFs,
  diálogos nativos `alert/confirm`) podem mostrar dados. Confira antes de gravar e acrescente seletores em
  `SELETORES`.
- Os seletores por prefixo/substring de classe (marcados "heurístico") usam `:has()`; num navegador sem suporte a
  `:has()` eles simplesmente não casam (o resto do CSS continua valendo, porque ficam dentro de `:is()`).
"""
import json

# Seletores do PROCESSO vêm da fonte única (kommo.SELETORES), com outro nome porque `SELETORES` aqui é a lista de
# CSS da privacidade. Sem ciclo: kommo.py só importa este módulo de forma tardia (KommoPage.aplicar_privacidade).
from .kommo import SELETORES as SEL_KOMMO

CLASSE_ATIVA = "kp-privacy"      # colocada no <html> quando o modo está ligado
CLASSE_SENSIVEL = "kp-sens"      # colocada pelo observer (e pelo JS_APLICAR legado)
ID_STYLE = "kp-privacy-css"
CHAVE_STORAGE = "kp_privacy"     # usada só pelo JS_INIT/JS_APLICAR legados
ATRIBUTO_TITLE_GUARDADO = "data-kp-title"
TITULO_ABA = "Kommo"

# Elementos do PROCESSO, que devem continuar legíveis na gravação (origem: docs/KOMMO_DOM.md, "Modal de duplicatas").
SEL_TITULO_MODAL = SEL_KOMMO.caption             # "Localizar e unir duplicatas — N de TOTAL"
SEL_PROGRESSO = SEL_KOMMO.progresso              # "Realizando união", "Unindo leads"...
SEL_BOTAO_UNIR = SEL_KOMMO.unir                  # "Unir esta duplicata"
# Só a privacidade precisa deste (o motor nunca clica em "Pular"), por isso não está em kommo.SELETORES.
SEL_BOTAO_PULAR = "button.js-merge-next"         # "Pular esta duplicata"
SEL_PROCESSO = f"{SEL_TITULO_MODAL}, {SEL_PROGRESSO}"
# A varredura de texto nunca marca estes elementos (nem botões e seus filhos).
SEL_NAO_BORRAR_TEXTO = f"{SEL_PROCESSO}, button, button *"
# kommo.py localiza o menu "⋯" por `[title="Mais"]`: este title nunca pode ser retirado.
SEL_PRESERVAR_TITLE = SEL_KOMMO.menu_qualquer

# Texto sensível: R$ 1.234 · 9195 leads/contatos/empresas · 83% · 5238/90000 · "limite".
REGEX_SENSIVEL = r"R\$\s?[\d.,]+|\d[\d.\s]*\s+(leads|contatos|empresas)\b|\d+\s*%|\d+\s*\/\s*\d{3,}|limite"
# Tags examinadas pela varredura de texto (elementos "folha": até 2 filhos e texto < 60 caracteres).
TAGS_TEXTO = "span,div,a,b,strong,em,small,p,li,label,h1,h2,h3,h4,td,th"
LIMITE_TEXTO = 60


def _por_classe(*fragmentos: str, prefixo: bool = True) -> str:
    """Seletor heurístico por prefixo (ou substring) de classe, protegido.

    - nunca casa com <html>/<body> nem com botões;
    - nunca casa com um contêiner que tenha dentro o título/progresso/botões do processo (`:has`);
    - fica dentro de `:is()` (lista "tolerante"): se o navegador não entender `:has()`, só este seletor deixa de
      valer — a regra CSS inteira não é descartada.
    """
    if prefixo:
        partes = [f'[class^="{f}"], [class*=" {f}"]' for f in fragmentos]
    else:
        partes = [f'[class*="{f}"]' for f in fragmentos]
    processo = f"{SEL_PROCESSO}, {SEL_BOTAO_UNIR}, {SEL_BOTAO_PULAR}"
    return f":is(:is({', '.join(partes)}):not(html, body, button, :has({processo})))"


SELETORES = [
    f".{CLASSE_SENSIVEL}",
    # --- Origem: docs/KOMMO_DOM.md ("Elementos sensíveis") -----------------------------------------------------
    # totais e resumos de listas / funil
    ".list-top-search__summary", ".js-list_summary", ".pipeline_status__head_info", ".pipeline_status__head_sum",
    # linhas das listas (leads e contatos)
    ".js-list-row:not(.js-list-row-head)", ".content-table__item__inner", ".note-lead__pipe", ".note-lead__status",
    ".js-list-row .list-row__cell:not(.list-row__cell-head)",
    ".list-row__template-name__name", ".list-row__template-name__table-wrapper__name-link",
    # contato: telefone, e-mail e campos
    "a[href^='tel:']", "a[href^='mailto:']", ".tel", ".linked-form__field__value",
    ".card-entity-form__fields input", ".card-entity-form__fields .linked-form__field__value",
    # conta / usuário
    ".nav__top__userbar__userinfo", ".nav__top__userpic__holder", ".js-avatar-wrapper", ".n-avatar",
    # conversas e funil
    ".feed-note", ".feed-compose", ".notes-wrapper", ".feed-note__body",
    ".pipeline_leads__item", ".pipeline_leads__item-name", ".digital-pipeline__lead", ".pipeline-unsorted__item",
    # modal de duplicatas
    ".control-checkbox__text", ".form-result__text", ".element__text", ".control-radio-label-text",
    ".modal-body__caption + * .js-duplicate-row", ".merge-form__field-value", ".merge-form__result",
    # outros (já usados desde a v1)
    ".users-select__body__item", ".js-card-name", ".card-holder__name", "[data-entity-name]", ".content-table__cell-name",
    # --- Heurísticos (T7): blocos BEM conhecidos estendidos por prefixo + componentes genéricos ------------------
    # Nomes no modal de duplicatas: os campos .form-result__* e .merge-form__* (blocos vistos no modal) — heurístico.
    _por_classe("form-result__", "merge-form__"),
    # Seletor de usuários (responsável), bloco .users-select__* já usado acima — heurístico.
    _por_classe("users-select"),
    # Tooltips e popovers (podem repetir nomes/valores) — heurístico, nomes de classe genéricos.
    _por_classe("tooltip", "popover"),
    # Toasts/notificações internas e contador do sino — heurístico (".notification*", ".js-notifications*",
    # ".nav__notifications*").
    _por_classe("notification", "js-notifications", "nav__notifications"),
    # Avatares (chat, responsáveis, usuário): .n-avatar e .js-avatar-wrapper estão no KOMMO_DOM; o resto é
    # heurístico por substring "avatar".
    _por_classe("avatar", prefixo=False),
]

CSS = (f"html.{CLASSE_ATIVA} " + f",\nhtml.{CLASSE_ATIVA} ".join(SELETORES)
       + " { filter: blur(7px) !important; user-select: none !important; }")

# Onde todo `title` (tooltip) é retirado, mesmo sem texto "sensível" pela regex: elementos borrados + contêineres
# de listas/modal/chat. ".js-list-row", ".content-table", ".notes-wrapper", ".feed-compose" vêm do KOMMO_DOM/
# SELETORES; ".modal-body" é o bloco de `h2.modal-body__caption`; ".modal" e ".pipeline_leads" são heurísticos.
SELETORES_CONTAINER_TITLE = [
    ".js-list-row", ".content-table", ".modal-body", ".modal", ".pipeline_leads", ".notes-wrapper", ".feed-compose",
]


def _config(ligado: bool) -> dict:
    """Parâmetros embutidos no script de início (tudo que o JS precisa, sem depender do armazenamento do site)."""
    return {
        "on": bool(ligado),
        "css": CSS,
        "classeAtiva": CLASSE_ATIVA,
        "classeSens": CLASSE_SENSIVEL,
        "idStyle": ID_STYLE,
        "attrTitle": ATRIBUTO_TITLE_GUARDADO,
        "titulo": TITULO_ABA,
        "re": REGEX_SENSIVEL,
        "tags": TAGS_TEXTO,
        "limite": LIMITE_TEXTO,
        "naoBorrar": SEL_NAO_BORRAR_TEXTO,
        "processo": SEL_PROCESSO,
        "preservarTitle": SEL_PRESERVAR_TITLE,
        "containersRapidos": ", ".join([f".{CLASSE_SENSIVEL}"] + SELETORES_CONTAINER_TITLE),
        "containersTitle": ", ".join(SELETORES),
    }


_JS_INIT_SCRIPT = r"""
(() => {
  const C = __CONFIG__;
  // Já instalado neste documento (outro init_script registrado antes): o último registrado decide o estado.
  if (typeof window.__kpSet === 'function') { window.__kpSet(C.on); return; }

  const RE = new RegExp(C.re, 'i');
  const SENS = C.classeSens;
  const TAGS = new Set(C.tags.split(',').map((t) => t.trim().toUpperCase()));
  const st = { on: false, obs: null, sheet: null, estilo: false, notif: false, tituloTravado: false,
               tituloPagina: null, stats: { lotes: 0, elementos: 0, ms: 0, msMax: 0, marcados: 0, titles: 0 } };
  let ultimoTexto = new WeakMap();   // elemento -> último texto curto examinado (evita reprocessar)
  const descTitulo = Object.getOwnPropertyDescriptor(Document.prototype, 'title');
  const MO_OPCOES = { childList: true, subtree: true, characterData: true,
                      attributes: true, attributeFilter: ['title'] };

  // ---------------------------------------------------------------- estilo e classe
  function garantirEstilo() {
    if (!st.sheet) {
      try {
        const sh = new CSSStyleSheet(); sh.replaceSync(C.css);
        document.adoptedStyleSheets = [...document.adoptedStyleSheets, sh];
        st.sheet = sh;
      } catch (e) { st.sheet = null; }
    }
    if (st.sheet) st.sheet.disabled = false;
    const r = document.documentElement;
    if (r && !document.getElementById(C.idStyle)) {
      // Com adoptedStyleSheets o <style> fica vazio: serve só de marcador (o JS_APLICAR legado procura este id).
      const s = document.createElement('style'); s.id = C.idStyle; s.textContent = st.sheet ? '' : C.css;
      (document.head || r).appendChild(s);
    }
  }
  function garantirClasse() {
    const r = document.documentElement;
    if (r && !r.classList.contains(C.classeAtiva)) r.classList.add(C.classeAtiva);
  }

  // ---------------------------------------------------------------- título da aba
  function instalarTitulo() {
    if (st.tituloTravado || !descTitulo) return;
    st.tituloTravado = true;
    try {
      Object.defineProperty(document, 'title', {
        configurable: true, enumerable: true,
        get() { return descTitulo.get.call(document); },
        set(v) { st.tituloPagina = String(v); descTitulo.set.call(document, st.on ? C.titulo : v); },
      });
    } catch (e) {}
  }
  function reforcarTitulo() {
    if (!st.on || !descTitulo) return;
    const atual = descTitulo.get.call(document);
    if (atual !== C.titulo) {            // só escreve quando difere: a mutação que isso gera não reescreve (sem laço)
      if (atual) st.tituloPagina = atual;
      descTitulo.set.call(document, C.titulo);
    }
  }

  // ---------------------------------------------------------------- notificações do navegador
  function limparOpcoes(o) {
    const c = Object.assign({}, o || {});
    c.body = ''; c.actions = [];
    delete c.icon; delete c.image; delete c.badge; delete c.data;
    return c;
  }
  function protegerNotificacoes() {
    if (st.notif) return;
    st.notif = true;
    const N = window.Notification;
    if (typeof N === 'function') {
      try {
        class Notification extends N {
          constructor(titulo, opcoes) {
            super(st.on ? C.titulo : titulo, st.on ? limparOpcoes(opcoes) : opcoes);
          }
        }
        Object.defineProperty(window, 'Notification',
          { value: Notification, writable: true, configurable: true, enumerable: false });
      } catch (e) {}
    }
    const SWR = window.ServiceWorkerRegistration;
    if (SWR && SWR.prototype && typeof SWR.prototype.showNotification === 'function') {
      const orig = SWR.prototype.showNotification;
      const show = function showNotification(titulo, opcoes) {
        return st.on ? orig.call(this, C.titulo, limparOpcoes(opcoes)) : orig.call(this, titulo, opcoes);
      };
      show.__kp = true;
      SWR.prototype.showNotification = show;
    }
  }

  // ---------------------------------------------------------------- texto sensível
  // Texto do elemento se tiver menos de C.limite caracteres; null se for maior (para cedo, sem ler tudo).
  function textoCurto(el) {
    if (el.childElementCount === 0) {    // caso comum (folha de verdade): textContent já é barato
      const t = el.textContent;
      return t.length < C.limite ? t : null;
    }
    // Com filhos (pode ser o wrapper de uma tabela enorme): lê só até o limite.
    const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    let s = '';
    for (let n = w.nextNode(); n; n = w.nextNode()) {
      s += n.data;
      if (s.length >= C.limite) return null;
    }
    return s;
  }
  function avaliar(el) {
    if (!TAGS.has(el.tagName)) return;
    st.stats.elementos++;
    const txt = el.childElementCount <= 2 ? textoCurto(el) : null;
    if (ultimoTexto.has(el) && ultimoTexto.get(el) === txt) return;
    ultimoTexto.set(el, txt);
    const sens = txt !== null && RE.test(txt) && !el.matches(C.naoBorrar) && !el.querySelector(C.processo);
    if (sens) {
      if (!el.classList.contains(SENS)) { el.classList.add(SENS); st.stats.marcados++; }
    } else if (el.classList.contains(SENS)) {
      el.classList.remove(SENS);         // o texto deixou de ser sensível (elemento reaproveitado pela SPA)
    }
  }
  function tratarTitle(el) {
    const v = el.getAttribute('title');
    if (!v || el.matches(C.preservarTitle)) return;
    let sens = RE.test(v) || el.classList.contains(SENS);
    // primeiro os contêineres (lista curta, barata); só depois a lista completa de SELETORES
    if (!sens) { try { sens = !!el.closest(C.containersRapidos); } catch (e) { sens = false; } }
    if (!sens) { try { sens = !!el.closest(C.containersTitle); } catch (e) { sens = false; } }
    if (sens) {
      el.setAttribute(C.attrTitle, v);
      el.removeAttribute('title');       // gera outra mutação de title, que encontra o atributo vazio e para
      st.stats.titles++;
    }
  }
  function varrer() {
    if (!st.on || !document.documentElement) return;
    const t0 = performance.now();
    avaliar(document.documentElement);
    document.querySelectorAll(C.tags).forEach(avaliar);
    document.querySelectorAll('[title]').forEach(tratarTitle);
    st.stats.ms += performance.now() - t0;
  }

  // ---------------------------------------------------------------- observer
  function aoMudar(registros) {
    if (!st.on) return;
    const t0 = performance.now();
    garantirClasse();
    reforcarTitulo();
    const elems = new Set();
    const titulos = new Set();
    for (const r of registros) {
      if (r.type === 'attributes') { titulos.add(r.target); continue; }
      // o alvo e até 2 ancestrais: o texto deles mudou junto (um "folha" pode ter até 2 filhos)
      let alvo = r.type === 'characterData' ? r.target.parentElement : r.target;
      for (let i = 0; alvo && alvo.nodeType === 1 && i < 3; i++, alvo = alvo.parentElement) elems.add(alvo);
      if (r.type !== 'childList') continue;
      for (const n of r.addedNodes) {
        if (n.nodeType !== 1) continue;
        elems.add(n);
        if (n.firstElementChild) {
          n.querySelectorAll(C.tags).forEach((e) => elems.add(e));
          n.querySelectorAll('[title]').forEach((e) => titulos.add(e));
        }
        if (n.hasAttribute('title')) titulos.add(n);
      }
    }
    elems.forEach(avaliar);              // primeiro marca kp-sens: tratarTitle consulta a classe
    titulos.forEach(tratarTitle);
    const dt = performance.now() - t0;
    st.stats.lotes++; st.stats.ms += dt; if (dt > st.stats.msMax) st.stats.msMax = dt;
  }
  function instalarObserver() {
    if (!st.obs) st.obs = new MutationObserver(aoMudar);
    st.obs.observe(document, MO_OPCOES);
  }

  // ---------------------------------------------------------------- liga / desliga
  function ligar() {
    st.on = true;
    garantirEstilo();
    garantirClasse();
    instalarTitulo();
    reforcarTitulo();
    protegerNotificacoes();
    instalarObserver();
    varrer();
  }
  function desligar() {
    st.on = false;
    if (st.obs) { st.obs.takeRecords(); st.obs.disconnect(); }   // descarta o que estava pendente
    const r = document.documentElement;
    if (r) r.classList.remove(C.classeAtiva);
    if (st.sheet) st.sheet.disabled = true;
    const s = document.getElementById(C.idStyle);
    if (s) s.remove();
    document.querySelectorAll('.' + SENS).forEach((e) => e.classList.remove(SENS));
    document.querySelectorAll('[' + C.attrTitle + ']').forEach((e) => {
      if (!e.hasAttribute('title')) e.setAttribute('title', e.getAttribute(C.attrTitle));
      e.removeAttribute(C.attrTitle);
    });
    ultimoTexto = new WeakMap();
    if (st.tituloPagina !== null && descTitulo) descTitulo.set.call(document, st.tituloPagina);
  }

  // Troca o estado em tempo de execução. Idempotente: com o mesmo estado só reforça classe/estilo/título.
  window.__kpSet = function (on) {
    on = !!on;
    if (on && st.on) { garantirEstilo(); garantirClasse(); reforcarTitulo(); return true; }
    if (on) ligar(); else desligar();
    return on;
  };
  // Diagnóstico (testes e logs): estado atual e custo acumulado do observer.
  window.__kpEstado = () => ({ on: st.on, stats: Object.assign({}, st.stats) });

  if (C.on) ligar(); else desligar();    // desligado: só limpa resquícios de classe/estilo, se houver
  const reforco = () => { if (st.on) { garantirEstilo(); garantirClasse(); reforcarTitulo(); varrer(); } };
  document.addEventListener('DOMContentLoaded', reforco);
  window.addEventListener('load', reforco);
})();
"""


def init_script(ligado: bool) -> str:
    """Script para `context.add_init_script` com o estado do modo privacidade EMBUTIDO.

    Ligado: desde o início do documento injeta o CSS, põe `kp-privacy` no `<html>`, instala o MutationObserver
    (marca `kp-sens`, retira tooltips), trava o título em "Kommo" e neutraliza notificações. Desligado: não instala
    nada; só remove classe/estilo se existirem. Nos dois casos expõe `window.__kpSet(on)` para trocar o estado em
    tempo de execução, e `window.__kpEstado()` para diagnóstico.

    Se mais de um init script for registrado no mesmo contexto, o último registrado decide o estado de cada nova
    página (é assim que se persiste uma troca feita durante a execução: registre `init_script(novo_estado)`).
    """
    return _JS_INIT_SCRIPT.replace("__CONFIG__", json.dumps(_config(ligado), ensure_ascii=False))


# Reforço chamado pelo Python: usa a função do init script quando existe; senão avisa (False) para o fallback.
JS_REFORCO = "(on) => (typeof window.__kpSet === 'function') ? (window.__kpSet(!!on), true) : false"


def aplicar(page_like, ligado: bool) -> bool:
    """Reforça o estado do modo privacidade numa página (ou frame) já aberta. É reforço, não a base.

    Usa `window.__kpSet` do `init_script`; se a página não o tiver (init script ausente), cai no `JS_APLICAR`
    legado. Devolve True se o init script estava ativo na página, False se precisou do fallback ou se a página
    estava navegando (erro engolido: o próximo reforço tenta de novo).
    """
    try:
        if page_like.evaluate(JS_REFORCO, bool(ligado)):
            return True
        page_like.evaluate(JS_APLICAR, [bool(ligado), CSS])
    except Exception:  # noqa: BLE001 - a página pode estar navegando; tenta de novo no próximo reforço
        pass
    return False


# ------------------------------------------------------------------------------------------------ legado (obsoleto)
# OBSOLETO: use init_script(ligado). Roda antes de qualquer script da página: injeta o CSS e religa o modo se o
# localStorage dizia que estava ligado (por isso falha na primeira execução e na tela de login).
JS_INIT = """
(() => {
  const css = %s;
  const aplicar = () => {
    if (document.getElementById('%s')) return;
    const s = document.createElement('style'); s.id = '%s'; s.textContent = css;
    (document.head || document.documentElement).appendChild(s);
  };
  aplicar();
  document.addEventListener('DOMContentLoaded', aplicar);
  try { if (localStorage.getItem('%s') === '1') document.documentElement.classList.add('%s'); } catch (e) {}
})();
""" % (json.dumps(CSS), ID_STYLE, ID_STYLE, CHAVE_STORAGE, CLASSE_ATIVA)

# OBSOLETO: use aplicar(page, ligado). Polling com varredura O(n) do documento inteiro (throttle de 1,5 s):
# page.evaluate(JS_APLICAR, [ligado, css]). Mantido para o merger.py atual e como fallback de aplicar().
JS_APLICAR = r"""([on, css]) => {
  if (!document.getElementById('__ID__')) {
    const st = document.createElement('style'); st.id = '__ID__'; st.textContent = css;
    (document.head || document.documentElement).appendChild(st);
  }
  document.documentElement.classList.toggle('__ATIVA__', !!on);
  try { localStorage.setItem('__KEY__', on ? '1' : '0'); } catch (e) {}
  if (!on) return;
  if (document.title !== 'Kommo') document.title = 'Kommo';
  const agora = Date.now();
  if (window.__kpT && agora - window.__kpT < 1500) return;
  window.__kpT = agora;
  const re = new RegExp(__RE__, 'i');
  document.querySelectorAll('span,div,a,b,p,h1,h2,h3,td').forEach((e) => {
    if (e.children.length <= 2 && e.textContent.length < 60 && re.test(e.textContent)
        && !e.classList.contains('__SENS__')
        && !e.matches(__NAO_BORRAR__)) e.classList.add('__SENS__');
  });
}""".replace("__ID__", ID_STYLE).replace("__ATIVA__", CLASSE_ATIVA).replace("__KEY__", CHAVE_STORAGE) \
    .replace("__SENS__", CLASSE_SENSIVEL).replace("__RE__", json.dumps(REGEX_SENSIVEL)) \
    .replace("__NAO_BORRAR__", json.dumps(SEL_NAO_BORRAR_TEXTO))
