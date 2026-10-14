"""Tudo que depende da página do Kommo: URLs, seletores do DOM e leitura do estado do modal.

Se o Kommo mudar o HTML, o ajuste é só aqui (veja docs/KOMMO_DOM.md).

Organização:
- `SELETORES` é a **única fonte da verdade** dos seletores. O JavaScript não repete literais: recebe os seletores
  como argumento (`{"sel": SELETORES.como_dict(), ...}`).
- `Estado` é a leitura do modal num instante; `PortaKommo` é a porta (interface) que o motor usa para falar com a
  página. `KommoPage` é a implementação real com Playwright; nos testes usa-se um falso (tests/fakes.py).
- Este módulo não importa o Playwright: `KommoPage` recebe um objeto `page` já aberto (duck typing).
"""
import json
import re
from dataclasses import asdict, dataclass
from typing import Protocol, runtime_checkable
from urllib.parse import urlsplit

DOMINIO = "kommo.com"

URL_LEADS = "https://{empresa}.{dominio}/leads/list/"
URL_CONTATOS = "https://{empresa}.{dominio}/contacts/list/contacts/?skip_filter=Y"

TIPOS = ("leads", "contatos")

# Subdomínio válido (rótulo DNS): 1 a 63 caracteres, letras/números/hífen, sem hífen nas pontas.
RE_EMPRESA = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")


@dataclass(frozen=True)
class Seletores:
    """Seletores do DOM do Kommo (docs/KOMMO_DOM.md). Única fonte da verdade — Python e JS leem daqui."""
    menu_mais: str = 'button.button-input-with-menu[title="Mais"]'
    menu_qualquer: str = "button.button-input-with-menu"
    item_leads: str = "li.js-duplicate-search"
    item_contatos: str = "li.js-list-duplicate-contacts-search"
    caption: str = "h2.modal-body__caption"
    unir: str = "button.js-merge-start"
    progresso: str = "h2.progress__header"
    erro: str = ".js-modal-error"
    tentar_novamente: str = "button.js-modal-try-again"
    fechar_modal: str = ".modal-body__close"
    cancelar: str = ".actions__doubles_action button.button-cancel"
    # HEURÍSTICO (A VALIDAR NO KOMMO REAL): contêineres onde se procuram os textos de "nenhuma duplicata" e da tela
    # de carregamento (TEXTOS abaixo). Só o texto VISÍVEL (innerText) é testado e só um booleano sai da página.
    conteiner_modal: str = ".modal, .modal-body, [class*='modal']"

    def item(self, tipo: str) -> str:
        """Seletor do item "Localizar duplicatas" do tipo pedido ('' se o tipo não existe)."""
        return {"leads": self.item_leads, "contatos": self.item_contatos}.get(tipo, "")

    def como_dict(self) -> dict:
        """Formato passado ao JavaScript: campos simples + `itens` por tipo."""
        d = asdict(self)
        d["itens"] = {t: self.item(t) for t in TIPOS}
        return d


SELETORES = Seletores()


@dataclass(frozen=True)
class Textos:
    """Expressões regulares (sintaxe comum a Python e JavaScript) testadas no texto VISÍVEL dos contêineres de modal,
    já sem acentos e sem diferenciar maiúsculas. Ficam fora de `Seletores` porque não são CSS.

    ATENÇÃO — A VALIDAR NO KOMMO REAL: ainda não se sabe como o Kommo mostra "nenhuma duplicata" nem o HTML exato
    da tela de carregamento. As duas regras são conservadoras e configuráveis aqui:

    sem_duplicatas — EVIDÊNCIA POSITIVA de que a busca terminou sem grupos. É a ÚNICA forma de o motor concluir
                     "sem duplicatas"; sem ela, busca sem resposta nunca é sucesso (motivo `busca_sem_resposta`).
    carregando     — tela de carregamento com o uso da conta ("Você atingiu 83% do limite…"). Só melhora o log e
                     evita reabrir a busca enquanto o Kommo ainda procura; NÃO conta como modal.
    """
    sem_duplicatas: str = (r"nenhuma\s+duplicat"
                           r"|nao\s+(?:ha|foram\s+encontrad[ao]s|existem|encontramos)\s+(?:mais\s+)?(?:nenhuma\s+)?"
                           r"duplicat"
                           r"|no\s+duplicates?\s+(?:were\s+)?found")
    carregando: str = r"\d+\s*%\s+do\s+limite|reached\s+\d+\s*%\s+of"

    def como_dict(self) -> dict:
        return asdict(self)


TEXTOS = Textos()


def _sem_acentos_minusculo(texto: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", texto or "") if not unicodedata.combining(c)).lower()


def texto_sem_duplicatas(texto: str, textos: Textos = TEXTOS) -> bool:
    """Mesma regra do JS (`Estado.vazio`) em Python puro — usada nos testes e na documentação."""
    return bool(re.search(textos.sem_duplicatas, _sem_acentos_minusculo(texto)))


def texto_carregando(texto: str, textos: Textos = TEXTOS) -> bool:
    """Mesma regra do JS (`Estado.carregando`) em Python puro."""
    return bool(re.search(textos.carregando, _sem_acentos_minusculo(texto)))

# Aliases usados pelo merger.py atual (compatibilidade; a fonte continua sendo SELETORES).
SEL_MENU_QUALQUER = SELETORES.menu_qualquer
SEL_UNIR = SELETORES.unir
SEL_TENTAR_NOVAMENTE = SELETORES.tentar_novamente
SEL_FECHAR_MODAL = SELETORES.fechar_modal
SEL_CANCELAR = SELETORES.cancelar


def _com_padrao(js: str) -> str:
    """Embrulha uma função JS que recebe `{sel, tipo}` para também aceitar a chamada antiga do merger.

    - `page.evaluate(JS)` sem argumento -> usa os seletores padrão;
    - `page.evaluate(JS, "leads")` (string) -> vira `{sel: padrão, tipo: "leads"}`;
    - `page.evaluate(JS, {"sel": ..., "tipo": ...})` -> usado como veio.
    Os seletores padrão são gerados de `SELETORES` (não há literal repetido no JS).
    """
    padrao = json.dumps(SELETORES.como_dict())
    txt = json.dumps(TEXTOS.como_dict())
    return ("(a) => (" + js + ")((a && typeof a === 'object') ? Object.assign({txt: " + txt + "}, a) : "
            "{sel: " + padrao + ", txt: " + txt + ", tipo: a})")


# Lê o estado do modal de duplicatas. Recebe {sel, txt}.
# `vazio` e `carregando` são HEURÍSTICOS (ver `Textos`): testam o innerText (só o visível, até 3000 caracteres) dos
# primeiros 40 contêineres de modal visíveis e devolvem SÓ um booleano — nenhum texto de cliente sai da página.
_JS_ESTADO = """({sel, txt}) => {
  const vis = (e) => !!e && e.offsetParent !== null;
  const cap = document.querySelector(sel.caption);
  const ini = document.querySelector(sel.unir);
  const prog = document.querySelector(sel.progresso);
  const err = document.querySelector(sel.erro);
  let vazio = false, carregando = false;
  try {
    const t = txt || {};
    const reVazio = t.sem_duplicatas ? new RegExp(t.sem_duplicatas, 'i') : null;
    const reCarr = t.carregando ? new RegExp(t.carregando, 'i') : null;
    if ((reVazio || reCarr) && sel.conteiner_modal) {
      const conts = [...document.querySelectorAll(sel.conteiner_modal)].filter(vis).slice(0, 40);
      for (const c of conts) {
        const s = String(c.innerText || '').slice(0, 3000).normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');
        if (reVazio && reVazio.test(s)) vazio = true;
        if (reCarr && reCarr.test(s)) carregando = true;
        if (vazio && carregando) break;
      }
    }
  } catch (e) { /* regra heurística inválida: não decide nada */ }
  return {
    erro: vis(err),
    modal: !!(vis(cap) || vis(ini) || vis(prog) || vis(err)),
    caption: vis(cap) ? cap.textContent.trim() : '',
    pode: vis(ini),
    progresso: vis(prog) ? prog.textContent.trim() : '',
    vazio: vazio,
    carregando: carregando,
  };
}"""

# Abre o menu "⋯" (prefere o botão visível com title="Mais"). Recebe {sel}. Devolve 'ok' | 'sem-botao'.
_JS_ABRIR_MENU = """({sel}) => {
  const vis = (e) => !!e && e.offsetParent !== null;
  const todos = [...document.querySelectorAll(sel.menu_mais), ...document.querySelectorAll(sel.menu_qualquer)];
  const btn = todos.find(vis) || todos[0];
  if (!btn) return 'sem-botao';
  btn.click();
  return 'ok';
}"""

# Clica no item "Localizar duplicatas" DO TIPO PEDIDO. Recebe {sel, tipo}.
# Estrito: sem fallback por texto (um <li> qualquer com "duplicat" poderia ser de outra entidade).
# Só clica em elemento visível; devolve false se o tipo for desconhecido ou o item não estiver visível.
_JS_CLICAR_ITEM = """({sel, tipo}) => {
  const alvo = sel.itens && sel.itens[tipo];
  if (!alvo) return false;
  const li = [...document.querySelectorAll(alvo)].find((e) => e.offsetParent !== null);
  if (!li) return false;
  li.click();
  return true;
}"""

# Diagnóstico SEM dados pessoais: só estrutura (tags, classes, visibilidade e contagens de seletores conhecidos).
# Nunca lê innerText/textContent/value — o texto do modal traz nomes, telefones etc. de clientes.
_JS_DIAGNOSTICO = """({sel}) => {
  const vis = (e) => !!e && e.offsetParent !== null;
  const linhas = [];
  for (const [nome, s] of Object.entries(sel)) {
    if (typeof s !== 'string') continue;
    const els = [...document.querySelectorAll(s)];
    linhas.push(nome + ': ' + els.length + ' encontrados, ' + els.filter(vis).length + ' visíveis');
  }
  const prog = document.querySelector(sel.progresso);
  if (vis(prog)) linhas.push('progresso_concluido: ' + /conclu/i.test(prog.textContent.normalize('NFD')));
  const cap = document.querySelector(sel.caption);
  if (vis(cap)) linhas.push('caption_tem_total: ' + /\\bde\\s+[\\d.]+\\s*$/.test(cap.textContent.trim()));
  const modais = [...document.querySelectorAll(sel.conteiner_modal)].filter(vis).slice(0, 40);
  linhas.push('modais visíveis: ' + modais.length);
  for (const e of modais) {
    const cls = (typeof e.className === 'string' ? e.className : '').replace(/\\s+/g, ' ').trim().slice(0, 200);
    linhas.push('  <' + e.tagName.toLowerCase() + '> ' + cls + ' (filhos: ' + e.children.length + ')');
  }
  return linhas.join('\\n');
}"""

# Constantes públicas (aceitam a chamada antiga do merger e a nova com {sel, tipo}).
JS_ESTADO = _com_padrao(_JS_ESTADO)
JS_ABRIR_MENU = _com_padrao(_JS_ABRIR_MENU)
JS_CLICAR_ITEM = _com_padrao(_JS_CLICAR_ITEM)
JS_DIAGNOSTICO = _com_padrao(_JS_DIAGNOSTICO)


# ---------------------------------------------------------------------------------------------- utilidades puras
def normalizar_empresa(texto: str) -> str:
    """Aceita 'minhaempresa', 'minhaempresa.kommo.com' ou a URL completa; devolve só o subdomínio ('' se inválido).

    O subdomínio precisa casar inteiro com `RE_EMPRESA` (rótulo DNS de 1 a 63 caracteres).
    """
    t = (texto or "").strip().lower()
    if not t:
        return ""
    if not re.match(r"^[a-z][a-z0-9+.-]*://", t):
        t = "https://" + t
    try:
        partes = urlsplit(t)
        host = partes.hostname or ""
    except ValueError:
        return ""
    if "@" in partes.netloc:          # "usuario@outro.com" — não é um subdomínio digitado
        return ""
    sufixo = "." + DOMINIO
    if host.endswith(sufixo):
        host = host[: -len(sufixo)]
    return host if RE_EMPRESA.fullmatch(host) else ""


def hostname_confere(url: str, empresa: str) -> bool:
    """True só se o hostname da URL for exatamente '<empresa>.kommo.com' (nunca por substring).

    'https://acme.kommo.com/leads' confere com 'acme'; 'https://xacme.kommo.com' e
    'https://acme.kommo.com.evil.io' não.
    """
    emp = normalizar_empresa(empresa)
    if not emp:
        return False
    try:
        host = urlsplit(url or "").hostname or ""
    except ValueError:
        return False
    return host == f"{emp}.{DOMINIO}"


def montar_url(empresa: str, tipo: str) -> str:
    modelo = URL_CONTATOS if tipo == "contatos" else URL_LEADS
    return modelo.format(empresa=empresa, dominio=DOMINIO)


def parse_total(caption: str):
    """'Localizar e unir duplicatas — 3 de 42.761' -> 42761. 'muitas' (ou sem número) -> None."""
    m = re.search(r"\bde\s+([\d.]+)\s*$", caption or "")
    return int(m.group(1).replace(".", "")) if m else None


# ---------------------------------------------------------------------------------------------- estado e porta
@dataclass(frozen=True)
class Estado:
    """Leitura do modal de duplicatas num instante.

    erro      — "Ops! Algo deu errado" (.js-modal-error) visível
    modal     — alguma parte do modal visível (título, Unir, progresso ou erro)
    caption   — título "Localizar e unir duplicatas — N de TOTAL" ('' se invisível)
    pode      — botão "Unir esta duplicata" visível
    progresso — texto de h2.progress__header ('' se invisível)
    navegou   — não deu para ler porque a página estava navegando/recarregando (os outros campos ficam vazios)
    vazio     — HEURÍSTICO (a validar no Kommo real): um modal visível mostra o texto de "nenhuma duplicata"
                (`TEXTOS.sem_duplicatas`). É a evidência positiva exigida para concluir "sem duplicatas".
    carregando — HEURÍSTICO: tela de carregamento com o uso da conta ("Você atingiu 83% do limite…",
                `TEXTOS.carregando`). NÃO conta como modal (`modal` continua falso); só melhora o log e evita reabrir
                a busca enquanto o Kommo ainda procura.
    """
    erro: bool = False
    modal: bool = False
    caption: str = ""
    pode: bool = False
    progresso: str = ""
    navegou: bool = False
    vazio: bool = False
    carregando: bool = False

    @classmethod
    def de_dict(cls, d: dict) -> "Estado":
        d = d or {}
        return cls(erro=bool(d.get("erro")), modal=bool(d.get("modal")), caption=str(d.get("caption") or ""),
                   pode=bool(d.get("pode")), progresso=str(d.get("progresso") or ""), navegou=bool(d.get("navegou")),
                   vazio=bool(d.get("vazio")), carregando=bool(d.get("carregando")))


@runtime_checkable
class PortaKommo(Protocol):
    """Tudo que o motor precisa da página do Kommo. Implementações: `KommoPage` (real) e `FakeKommo` (testes)."""

    def estado(self) -> Estado: ...
    def abrir_menu(self) -> bool: ...
    def clicar_item_duplicatas(self, tipo: str) -> bool: ...
    def clicar_unir(self) -> bool: ...
    def tentar_novamente(self) -> bool: ...
    def fechar_modal(self) -> None: ...
    def cancelar_modal(self) -> bool: ...
    def hostname(self) -> str: ...
    def tem_menu(self) -> bool: ...
    def url_atual(self) -> str: ...
    def aplicar_privacidade(self, on: bool, css: str) -> None: ...
    def diagnostico(self) -> str: ...
    def screenshot(self, path: str) -> None: ...
    def esta_fechada(self) -> bool: ...
    def paginas_abertas(self) -> int: ...
    def adotar_pagina(self) -> bool: ...
    def adotar_aba_logada(self, empresa: str) -> bool: ...


# Mensagens do Playwright que indicam que a página navegou/fechou no meio da operação.
_MARCAS_TRANSITORIAS = (
    "execution context was destroyed",
    "target closed",
    "target page, context or browser has been closed",
    "has been closed",
    "navigat",
    "frame was detached",
    "cannot find context",
    "kp-timeout",
)


def eh_transitorio(exc: BaseException) -> bool:
    """True para erros de navegação/fechamento/timeout — a leitura falhou, mas não é bug do app."""
    if type(exc).__name__ == "TimeoutError":
        return True
    msg = str(exc).lower()
    return any(m in msg for m in _MARCAS_TRANSITORIAS)


def _js_com_timeout(js: str) -> str:
    """Embrulha uma função JS `(a) => ...` numa corrida contra um timer (o `page.evaluate` não tem timeout).

    Recebe `{a, t}`: `a` é o argumento original e `t` o limite em ms. Se estourar, rejeita com 'kp-timeout'.
    Limite: se a página travar o thread principal do navegador, o timer também não roda.
    """
    return ("async ({a, t}) => { let h; try { return await Promise.race(["
            "Promise.resolve().then(() => (" + js + ")(a)),"
            "new Promise((_, r) => { h = setTimeout(() => r(new Error('kp-timeout ' + t + 'ms')), t); })"
            "]); } finally { clearTimeout(h); } }")


class KommoPage:
    """Implementação real de `PortaKommo` sobre uma `playwright.sync_api.Page`.

    Regras:
    - todo evaluate/click tem timeout explícito;
    - erros de navegação ("Execution context was destroyed", "Target closed", "navigat…") e timeouts não propagam:
      `estado()` devolve `Estado(navegou=True)`, cliques devolvem False, leituras devolvem um valor seguro;
    - os seletores vão como argumento do evaluate (vindos de `SELETORES`);
    - troca de aba (T10): com `ctx` (o BrowserContext), se a aba usada for fechada/substituída durante o login ou um
      redirecionamento, `adotar_pagina()` passa a usar outra aba aberta do MESMO contexto (de preferência uma de
      *.kommo.com). `ao_trocar(page)` reaplica o que é por aba (timeouts padrão). Só não há mais aba quando
      `paginas_abertas() == 0` — é isso que o motor trata como "navegador fechado".
    """

    def __init__(self, page, timeout_ms: int = 5000, timeout_clique_ms: int = 3000, seletores: Seletores = SELETORES,
                 *, ctx=None, ao_trocar=None, textos: Textos = TEXTOS):
        self.page = page
        self.ctx = ctx
        self.ao_trocar = ao_trocar
        self.timeout_ms = timeout_ms
        self.timeout_clique_ms = timeout_clique_ms
        self.sel = seletores
        self._sel_js = seletores.como_dict()
        self._txt_js = textos.como_dict()

    # ------------------------------------------------------------------ abas do contexto (T10)
    @staticmethod
    def _aberta(pg) -> bool:
        try:
            fn = getattr(pg, "is_closed", None)
            return not (callable(fn) and fn())
        except Exception:  # noqa: BLE001 - não dá para consultar: trata como fechada
            return False

    def _abertas_do_contexto(self) -> list:
        """Abas ainda abertas do contexto (lista vazia sem ctx, com o navegador desconectado ou em erro)."""
        if self.ctx is None:
            return []
        try:
            return [pg for pg in list(self.ctx.pages) if self._aberta(pg)]
        except Exception:  # noqa: BLE001 - contexto/navegador já fechado
            return []

    def paginas_abertas(self) -> int:
        """Quantas abas do navegador continuam abertas (a atual incluída). 0 = o navegador foi fechado de verdade."""
        if self.ctx is None:
            return 0 if self.esta_fechada() else 1
        abertas = self._abertas_do_contexto()
        if not self.esta_fechada() and not any(pg is self.page for pg in abertas):
            abertas.append(self.page)
        return len(abertas)

    def adotar_pagina(self) -> bool:
        """Se a aba atual foi fechada, passa a usar outra aba aberta do contexto. True se trocou de aba.

        Preferência: a mais recente cujo hostname é *.kommo.com; senão a mais recente (ex.: login com Google que
        depois volta ao Kommo — o motor continua esperando o hostname exato antes de qualquer ação)."""
        if not self.esta_fechada():
            return False
        candidatas = [pg for pg in self._abertas_do_contexto() if pg is not self.page]
        if not candidatas:
            return False

        def do_kommo(pg) -> bool:
            try:
                host = (urlsplit(pg.url or "").hostname or "").lower()
            except Exception:  # noqa: BLE001
                return False
            return host == DOMINIO or host.endswith("." + DOMINIO)

        preferidas = [pg for pg in candidatas if do_kommo(pg)]
        self.trocar_pagina((preferidas or candidatas)[-1])
        return True

    def adotar_aba_logada(self, empresa: str) -> bool:
        """Login concluído em OUTRA aba (A4): se outra aba aberta do contexto tem o hostname EXATO da empresa e o
        botão de menu "⋯" (mesmo critério de `tem_menu`), passa a usá-la. True se trocou.

        Usado só durante a espera do login, quando a aba atual ainda não confirma. Aba de outra conta (hostname
        diferente) nunca é adotada por aqui; as validações de conta/página/modal continuam valendo antes de clicar."""
        emp = normalizar_empresa(empresa)
        if not emp:
            return False
        alvo = f"{emp}.{DOMINIO}"
        for pg in reversed(self._abertas_do_contexto()):
            if pg is self.page:
                continue
            try:
                host = (urlsplit(pg.url or "").hostname or "").lower()
                if host != alvo or pg.query_selector(self.sel.menu_qualquer) is None:
                    continue
            except Exception:  # noqa: BLE001 - aba navegando/fechando: ignora
                continue
            self.trocar_pagina(pg)
            return True
        return False

    def trocar_pagina(self, page) -> None:
        """Passa a usar `page` (mesmo contexto) e reaplica as configurações por aba via `ao_trocar`."""
        self.page = page
        if self.ao_trocar is not None:
            try:
                self.ao_trocar(page)
            except Exception:  # noqa: BLE001 - configuração acessória (timeouts): não impede a troca
                pass

    # ------------------------------------------------------------------ primitivas
    def _avaliar(self, js: str, arg):
        """page.evaluate com timeout (no lado do JS). Propaga exceções — quem chama decide o valor seguro."""
        return self.page.evaluate(_js_com_timeout(js), {"a": arg, "t": self.timeout_ms})

    def _clicar(self, seletor: str, timeout_ms: int | None = None) -> bool:
        """Clique do Playwright (espera visível/estável/habilitado até o timeout). Qualquer falha -> False."""
        try:
            self.page.click(seletor, timeout=timeout_ms or self.timeout_clique_ms)
            return True
        except Exception:  # noqa: BLE001 - clique que falha não derruba o motor
            return False

    # ------------------------------------------------------------------ leitura
    def estado(self) -> Estado:
        try:
            return Estado.de_dict(self._avaliar(_JS_ESTADO, {"sel": self._sel_js, "txt": self._txt_js}))
        except Exception as e:  # noqa: BLE001
            if eh_transitorio(e):
                return Estado(navegou=True)
            raise

    def hostname(self) -> str:
        try:
            return urlsplit(self.page.url or "").hostname or ""
        except Exception:  # noqa: BLE001
            return ""

    def url_atual(self) -> str:
        try:
            return self.page.url or ""
        except Exception:  # noqa: BLE001
            return ""

    def esta_fechada(self) -> bool:
        """True se a aba foi fechada (`page.is_closed()`). Falha ao consultar -> False (as leituras seguintes
        dirão; na dúvida não é fechamento)."""
        try:
            fn = getattr(self.page, "is_closed", None)
            return bool(callable(fn) and fn())
        except Exception:  # noqa: BLE001
            return False

    def tem_menu(self) -> bool:
        try:
            return self.page.query_selector(self.sel.menu_qualquer) is not None
        except Exception:  # noqa: BLE001
            return False

    def diagnostico(self) -> str:
        """Resumo estrutural do modal (classes, contagens, visibilidade). Não contém texto de clientes."""
        try:
            return str(self._avaliar(_JS_DIAGNOSTICO, {"sel": self._sel_js}))
        except Exception as e:  # noqa: BLE001
            return f"(diagnóstico indisponível: {'página navegando' if eh_transitorio(e) else type(e).__name__})"

    # ------------------------------------------------------------------ ações
    def abrir_menu(self) -> bool:
        try:
            return self._avaliar(_JS_ABRIR_MENU, {"sel": self._sel_js}) == "ok"
        except Exception:  # noqa: BLE001
            return False

    def clicar_item_duplicatas(self, tipo: str) -> bool:
        if not self.sel.item(tipo):
            return False
        try:
            return bool(self._avaliar(_JS_CLICAR_ITEM, {"sel": self._sel_js, "tipo": tipo}))
        except Exception:  # noqa: BLE001
            return False

    def clicar_unir(self) -> bool:
        return self._clicar(self.sel.unir)

    def tentar_novamente(self) -> bool:
        return self._clicar(self.sel.tentar_novamente)

    def fechar_modal(self) -> None:
        """Fecha o modal: tenta o "X" (.modal-body__close), depois "Cancelar", depois a tecla Escape."""
        if self._clicar(self.sel.fechar_modal):
            return
        if self._clicar(self.sel.cancelar):
            return
        try:
            self.page.keyboard.press("Escape")
        except Exception:  # noqa: BLE001
            pass

    def cancelar_modal(self) -> bool:
        """Clica "Cancelar" só se o botão existir (não espera o timeout quando o modal já fechou)."""
        try:
            if self.page.query_selector(self.sel.cancelar) is None:
                return False
        except Exception:  # noqa: BLE001
            return False
        return self._clicar(self.sel.cancelar)

    def aplicar_privacidade(self, on: bool, css: str) -> None:
        from . import privacy   # import tardio: privacy.py importa SELETORES daqui (evita import circular)
        try:
            self._avaliar(privacy.JS_APLICAR, [bool(on), css])
        except Exception:  # noqa: BLE001 - a página pode estar navegando; o motor reaplica no próximo passo
            pass

    def screenshot(self, path: str) -> None:
        """Salva a captura. Erros de navegação são ignorados; outros (ex.: disco) propagam para o chamador logar."""
        try:
            self.page.screenshot(path=path, timeout=max(self.timeout_ms, 10000))
        except Exception as e:  # noqa: BLE001
            if not eh_transitorio(e):
                raise
