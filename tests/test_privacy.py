import json
import os
import re
import subprocess
import sys
from pathlib import Path

from kommo_duplicatas import kommo, privacy


def test_css_tem_um_seletor_por_regra_e_blur():
    assert privacy.CSS.count("blur(7px)") == 1
    for sel in privacy.SELETORES:
        assert f"html.{privacy.CLASSE_ATIVA} {sel}" in privacy.CSS


def test_cobre_o_essencial():
    css = privacy.CSS
    for trecho in ("tel:", "mailto:", ".list-top-search__summary", ".js-list-row", ".control-checkbox__text"):
        assert trecho in css


def test_cobre_os_novos_alvos_da_t7():
    css = privacy.CSS
    for trecho in ('"form-result__"', '"merge-form__"', '"users-select"', '"tooltip"', '"popover"',
                   '"notification"', '"js-notifications"', '"nav__notifications"', '[class*="avatar"]'):
        assert trecho in css, trecho


def test_heuristicos_protegidos_e_tolerantes():
    """Seletores por prefixo nunca pegam html/body/botões nem contêineres do processo, e ficam dentro de :is()."""
    heur = [s for s in privacy.SELETORES if s.startswith(":is(")]
    assert len(heur) >= 5
    for s in heur:
        assert ":not(html, body, button, :has(" in s
        assert privacy.SEL_TITULO_MODAL in s and privacy.SEL_PROGRESSO in s and privacy.SEL_BOTAO_UNIR in s
        assert s.count("(") == s.count(")")


def test_js_sem_marcadores_pendentes():
    for marcador in ("__ID__", "__ATIVA__", "__KEY__", "__SENS__", "__RE__", "__NAO_BORRAR__"):
        assert marcador not in privacy.JS_APLICAR
    for ligado in (True, False):
        assert "__CONFIG__" not in privacy.init_script(ligado)


def test_titulo_da_aba_e_anonimizado():
    assert "document.title = 'Kommo'" in privacy.JS_APLICAR
    assert privacy.TITULO_ABA == "Kommo"


def test_selectores_do_processo_sem_duplicacao():
    """Os seletores do modal NÃO são literais em privacy.py (vêm de kommo.SELETORES); o JS usa as constantes."""
    with open(privacy.__file__, encoding="utf-8") as f:
        fonte = f.read()
    for literal in ("h2.modal-body__caption", "h2.progress__header", "button.js-merge-start"):
        assert fonte.count(f"'{literal}'") + fonte.count(f'"{literal}"') == 0, literal
    assert json.dumps(privacy.SEL_NAO_BORRAR_TEXTO) in privacy.JS_APLICAR
    assert privacy.SEL_TITULO_MODAL in privacy.SEL_NAO_BORRAR_TEXTO
    assert privacy.SEL_PROGRESSO in privacy.SEL_NAO_BORRAR_TEXTO


def _config_embutida(script: str) -> dict:
    m = re.search(r"const C = (\{.*?\});\n", script, re.S)
    assert m, "config não encontrada no script"
    return json.loads(m.group(1))


def test_init_script_embute_o_estado():
    on = _config_embutida(privacy.init_script(True))
    off = _config_embutida(privacy.init_script(False))
    assert on["on"] is True and off["on"] is False
    assert on["css"] == privacy.CSS
    assert on["re"] == privacy.REGEX_SENSIVEL
    assert on["preservarTitle"] == privacy.SEL_PRESERVAR_TITLE


def test_init_script_nao_depende_de_storage():
    s = privacy.init_script(True)
    assert "localStorage" not in s and "sessionStorage" not in s
    assert "MutationObserver" in s and "window.__kpSet" in s


def test_regex_casa_com_os_exemplos_do_kommo_dom():
    # A regex é JS; a sintaxe usada aqui também é válida em Python.
    r = re.compile(privacy.REGEX_SENSIVEL, re.I)
    for t in ("R$ 1.234", "9195 leads: R$ 4.596", "Você atingiu 83% do limite", "5238/90000", "12 contatos",
              "R$ 4.596"):
        assert r.search(t), t
    for t in ("Unir esta duplicata", "Localizar e unir duplicatas — 1 de 42770", "Realizando união", "Unindo leads"):
        assert not r.search(t), t


class _PaginaFalsa:
    def __init__(self, tem_init: bool, erro: bool = False):
        self.tem_init, self.erro, self.chamadas = tem_init, erro, []

    def evaluate(self, js, arg=None):
        if self.erro:
            raise RuntimeError("Execution context was destroyed")
        self.chamadas.append((js, arg))
        return self.tem_init if js == privacy.JS_REFORCO else None


def test_aplicar_usa_kpset_quando_ha_init_script():
    p = _PaginaFalsa(tem_init=True)
    assert privacy.aplicar(p, True) is True
    assert p.chamadas == [(privacy.JS_REFORCO, True)]


def test_aplicar_cai_no_legado_sem_init_script():
    p = _PaginaFalsa(tem_init=False)
    assert privacy.aplicar(p, False) is False
    assert p.chamadas[-1] == (privacy.JS_APLICAR, [False, privacy.CSS])


def test_aplicar_engole_erro_de_navegacao():
    assert privacy.aplicar(_PaginaFalsa(tem_init=True, erro=True), True) is False



def test_seletores_do_processo_vem_de_kommo_sem_ciclo():
    """privacy.py não repete literais do processo: usa kommo.SELETORES (e kommo.py não importa privacy no topo)."""
    s = kommo.SELETORES
    assert privacy.SEL_KOMMO is s
    assert privacy.SEL_TITULO_MODAL == s.caption and privacy.SEL_PROGRESSO == s.progresso
    assert privacy.SEL_BOTAO_UNIR == s.unir and privacy.SEL_PRESERVAR_TITLE == s.menu_qualquer
    # Importar privacy ANTES de kommo, num processo limpo, não pode dar import circular.
    src = str(Path(__file__).resolve().parents[1] / "src")
    cod = "import kommo_duplicatas.privacy as p, kommo_duplicatas.kommo as k; assert p.SEL_KOMMO is k.SELETORES"
    r = subprocess.run([sys.executable, "-B", "-c", cod], capture_output=True, text=True, timeout=60,
                       env={**os.environ, "PYTHONPATH": src})
    assert r.returncode == 0, r.stderr
