"""Falsos para testar o motor sem o Kommo real (nunca rode testes contra a conta de produção).

Uso:
    from fakes import FakeKommo
    from kommo_duplicatas.kommo import Estado

    fake = FakeKommo([Estado(modal=True, pode=True, caption="… 1 de 10"),
                      Estado(modal=True, progresso="Realizando união"),
                      Estado(modal=True, progresso="União de contatos concluída com sucesso"),
                      Estado(modal=True, pode=True, caption="… 1 de 9")])
    fake.estado()   # devolve os Estados do roteiro em ordem; depois do último, repete o último
    fake.chamadas   # lista com o nome de cada método chamado, na ordem (ex.: ["estado", "clicar_unir"])

As respostas das ações são configuráveis pelos atributos públicos (ex.: `fake.resposta_unir = False`).

Extensões (T5, compatíveis com o uso acima):
- um item do roteiro pode ser uma exceção: `estado()` a levanta (simula bug/erro inesperado da página);
- `fake.ao_chamar = func(nome)` é chamado a cada método (ganchos de teste: pedir parada, mudar a URL, levantar);
- `fake.fechado = True` simula a aba/navegador fechado (`esta_fechada()`);
- `fake.outras_paginas = [url, ...]` simula outras abas abertas no contexto (T10): com a aba atual fechada,
  `adotar_pagina()` troca para uma delas (registrada em `fake.adocoes`); sem outras abas = navegador fechado;
- `fake.outras_com_menu = {url, ...}` (A4): dessas outras abas, as que têm o menu "⋯" (logadas). Durante a espera do
  login, `adotar_aba_logada(empresa)` troca para a mais recente com hostname EXATO da empresa e menu;
- `RelogioFalso`: relógio do motor que avança o tempo na hora (sem sleep real);
- `KommoSimulado`: Kommo com estado e tempo (busca, união, conclusão, recarga, erros) dirigido pelo RelogioFalso.
  Separa "busca lenta" (`dur_busca`/`dur_recarga` grandes, `busca_infinita`: a tela de carregamento continua) de
  "lista vazia CONFIRMADA" (`fim_confirmado=True`: o Kommo mostra "nenhuma duplicata" = `Estado(vazio=True)`).
  Com `fim_confirmado=False` o fim real das duplicatas é só "nada na tela" — sem evidência positiva.
"""
import threading

from kommo_duplicatas.kommo import Estado, montar_url


class RelogioEstourou(BaseException):
    """O teste passou do tempo simulado máximo (provável laço infinito). BaseException: o motor não a engole."""


class RelogioFalso:
    """Implementa `merger.Relogio` sem esperar de verdade: `dormir(s)` só soma `s` ao tempo atual.

    `ao_dormir(t)` (opcional) é chamado depois de cada avanço — útil para responder a confirmação ou pedir parada
    num instante simulado. `maximo` protege contra laços infinitos.
    """

    def __init__(self, inicio: float = 1000.0, maximo: float = 200_000.0):
        self.t = float(inicio)
        self.inicio = float(inicio)
        self.maximo = maximo
        self.dormidas: list[float] = []
        self.ao_dormir = None

    def agora(self) -> float:
        return self.t

    def dormir(self, segundos: float) -> None:
        self.t += max(0.0, float(segundos))
        self.dormidas.append(segundos)
        if self.t - self.inicio > self.maximo:
            raise RelogioEstourou(f"tempo simulado passou de {self.maximo}s")
        if self.ao_dormir:
            self.ao_dormir(self.t)

    def esperar(self, evento: threading.Event, segundos: float) -> bool:
        if evento.is_set():
            return True
        self.dormir(segundos)
        return evento.is_set()

    @property
    def decorrido(self) -> float:
        return self.t - self.inicio


class FakeKommo:
    """Implementa `kommo.PortaKommo` a partir de um roteiro de `Estado`s. Simples de propósito."""

    def __init__(self, roteiro=None, url: str = "https://acme.kommo.com/leads/list/"):
        self.roteiro = list(roteiro or [Estado()])
        self.indice = 0
        self.url = url
        self.chamadas: list[str] = []
        self.itens_clicados: list[str] = []
        self.privacidade: list[bool] = []
        self.screenshots: list[str] = []
        # Respostas configuráveis das ações.
        self.resposta_menu = True
        self.resposta_item = True
        self.resposta_unir = True
        self.resposta_tentar = True
        self.resposta_cancelar = True
        self.menu_presente = True
        self.texto_diagnostico = "diagnostico-falso"
        self.fechado = False
        self.ao_chamar = None
        # T10: outras abas abertas no MESMO contexto (URLs). `adotar_pagina()` troca para a última delas.
        self.outras_paginas: list[str] = []
        self.adocoes: list[str] = []
        self.outras_com_menu: set[str] = set()     # A4: outras abas logadas (com o menu "⋯")

    def _anota(self, nome: str) -> None:
        self.chamadas.append(nome)
        if self.ao_chamar:
            self.ao_chamar(nome)

    def esta_fechada(self) -> bool:
        return self.fechado

    def paginas_abertas(self) -> int:
        return (0 if self.fechado else 1) + len(self.outras_paginas)

    def adotar_pagina(self) -> bool:
        """Aba atual fechada + outra aberta: passa a usar a mais recente (prefere *.kommo.com), como o KommoPage."""
        if not self.fechado or not self.outras_paginas:
            return False
        kommo_ = [u for u in self.outras_paginas if ".kommo.com" in u]
        url = (kommo_ or self.outras_paginas)[-1]
        self.outras_paginas.remove(url)
        self.url, self.fechado = url, False
        self.adocoes.append(url)
        self._anota("adotar_pagina")
        return True

    def adotar_aba_logada(self, empresa: str) -> bool:
        """A4: outra aba com hostname EXATO '<empresa>.kommo.com' e menu → passa a usá-la (a atual continua aberta)."""
        from urllib.parse import urlsplit
        alvo = f"{empresa}.kommo.com"
        for url in reversed(self.outras_paginas):
            if (urlsplit(url).hostname or "") == alvo and url in self.outras_com_menu:
                self.outras_paginas.remove(url)
                if not self.fechado:
                    self.outras_paginas.append(self.url)
                self.url, self.fechado, self.menu_presente = url, False, True
                self.adocoes.append(url)
                self._anota("adotar_aba_logada")
                return True
        return False

    # ------------------------------------------------------------------ leitura
    def estado(self) -> Estado:
        self._anota("estado")
        est = self.roteiro[min(self.indice, len(self.roteiro) - 1)]
        self.indice += 1
        if isinstance(est, BaseException):
            raise est
        return est

    def hostname(self) -> str:
        from urllib.parse import urlsplit
        self._anota("hostname")
        return urlsplit(self.url).hostname or ""

    def url_atual(self) -> str:
        self._anota("url_atual")
        return self.url

    def tem_menu(self) -> bool:
        self._anota("tem_menu")
        return self.menu_presente

    def diagnostico(self) -> str:
        self._anota("diagnostico")
        return self.texto_diagnostico

    # ------------------------------------------------------------------ ações
    def abrir_menu(self) -> bool:
        self._anota("abrir_menu")
        return self.resposta_menu

    def clicar_item_duplicatas(self, tipo: str) -> bool:
        self._anota("clicar_item_duplicatas")
        self.itens_clicados.append(tipo)
        return self.resposta_item

    def clicar_unir(self) -> bool:
        self._anota("clicar_unir")
        return self.resposta_unir

    def tentar_novamente(self) -> bool:
        self._anota("tentar_novamente")
        return self.resposta_tentar

    def fechar_modal(self) -> None:
        self._anota("fechar_modal")

    def cancelar_modal(self) -> bool:
        self._anota("cancelar_modal")
        return self.resposta_cancelar

    def aplicar_privacidade(self, on: bool, css: str) -> None:
        self._anota("aplicar_privacidade")
        self.privacidade.append(bool(on))

    def screenshot(self, path: str) -> None:
        self._anota("screenshot")
        self.screenshots.append(path)


CAPTION = "Localizar e unir duplicatas — 1 de {n}"


class KommoSimulado(FakeKommo):
    """Kommo com estado e tempo, dirigido por um RelogioFalso. Fases:

        lista      sem modal (antes de abrir, depois de fechar, ou fim real SEM evidência com fim_confirmado=False)
        buscando   tela de carregamento (sem modal; `Estado(carregando=mostra_carregando)`) por `dur_busca` (ou para
                   sempre com `busca_infinita`) — "busca lenta" é só `dur_busca`/`dur_recarga` grande
        vazio      fim real das duplicatas CONFIRMADO (`fim_confirmado=True`, padrão): modal com "nenhuma duplicata"
                   (`Estado(modal=True, vazio=True)`) — a evidência positiva que o motor exige
        erro       "Ops! Algo deu errado" (modal com .js-modal-error) até `tentar_novamente()`
        grupo      modal com o botão Unir e o título "… 1 de N"
        unindo     progresso `texto_progresso` por `dur_uniao`
        concluido  progresso `texto_concluido` por `dur_concluido` (pulada se texto_concluido=None: Leads pessimista)
        navegando  página recarregando (Estado(navegou=True)) por `dur_navegacao`, depois "lista"

    Depois da união: com `recarrega` o Kommo fecha o modal e refaz a busca (`dur_recarga`); sem, mostra o próximo
    grupo direto. `unioes` conta as uniões REAIS (cliques em Unir com o botão visível); `fases_cliques` e
    `fases_fechar` guardam a fase em cada clique/fechamento (para provar que nada foi clicado/fechado fora de hora).
    """

    def __init__(self, relogio, total: int = 10, *, empresa: str = "acme", tipo: str = "contatos",
                 texto_progresso: str | None = "Realizando união",
                 texto_concluido: str | None = "União de contatos concluída com sucesso",
                 dur_busca: float = 5.0, dur_uniao: float = 3.0, dur_concluido: float = 1.0,
                 recarrega: bool = True, dur_recarga: float = 4.0, caption: str = CAPTION,
                 fim_confirmado: bool = True, mostra_carregando: bool = True):
        super().__init__(url=montar_url(empresa, tipo))
        self.relogio = relogio
        self.restantes = total
        self.texto_progresso = texto_progresso
        self.texto_concluido = texto_concluido
        self.dur_busca, self.dur_uniao, self.dur_concluido = dur_busca, dur_uniao, dur_concluido
        self.recarrega, self.dur_recarga = recarrega, dur_recarga
        self.dur_navegacao = 2.0
        self.caption = caption
        self.fim_confirmado = fim_confirmado       # acabou: mostra "nenhuma duplicata" (True) ou nada (False)
        self.mostra_carregando = mostra_carregando  # a busca mostra a tela de carregamento (Estado.carregando)
        self.fase = "lista"
        self.ate = 0.0
        self.unioes = 0
        self.erros_busca = 0            # quantas das próximas buscas terminam em erro
        self.busca_infinita = False     # a busca nunca termina (nem com erro)
        self.navegar_na_uniao = False   # durante a união a página recarrega (navegou) e volta sem modal
        self.expira_apos: int | None = None   # depois de N uniões a sessão cai (URL de login, sem menu)
        self.fases_cliques: list[str] = []
        self.fases_fechar: list[str] = []
        self.tentativas = 0

    # ------------------------------------------------------------------ máquina de estados
    def _apos_uniao(self, t_fim: float) -> None:
        if self.expira_apos is not None and self.unioes >= self.expira_apos:
            self.url = "https://www.kommo.com/login/"
            self.menu_presente = False
            self.fase = "lista"
        elif self.recarrega:
            self.fase, self.ate = "buscando", t_fim + self.dur_recarga
        else:
            self.fase = self._fim_da_busca()

    def _fim_da_busca(self) -> str:
        if self.restantes > 0:
            return "grupo"
        return "vazio" if self.fim_confirmado else "lista"

    def _avancar(self) -> None:
        t = self.relogio.agora()
        while True:
            if self.fase == "buscando" and not self.busca_infinita and t >= self.ate:
                if self.erros_busca > 0:
                    self.erros_busca -= 1
                    self.fase = "erro"
                else:
                    self.fase = self._fim_da_busca()
            elif self.fase == "unindo" and t >= self.ate:
                if self.navegar_na_uniao:
                    self.fase, self.ate = "navegando", self.ate + self.dur_navegacao
                elif self.texto_concluido:
                    self.fase, self.ate = "concluido", self.ate + self.dur_concluido
                else:
                    self._apos_uniao(self.ate)
            elif self.fase == "concluido" and t >= self.ate:
                self._apos_uniao(self.ate)
            elif self.fase == "navegando" and t >= self.ate:
                self.fase = "lista"
            else:
                return

    def _cap(self) -> str:
        return self.caption.format(n=self.restantes)

    def estado(self) -> Estado:
        self._avancar()
        self._anota("estado")          # o gancho vê a fase já atualizada (e pode mudá-la ou levantar)
        f = self.fase
        if f == "grupo":
            return Estado(modal=True, pode=True, caption=self._cap())
        if f == "unindo":
            return Estado(modal=True, caption=self._cap(), progresso=self.texto_progresso or "")
        if f == "concluido":
            return Estado(modal=True, progresso=self.texto_concluido or "")
        if f == "erro":
            return Estado(modal=True, erro=True)
        if f == "navegando":
            return Estado(navegou=True)
        if f == "vazio":
            return Estado(modal=True, vazio=True, caption="Localizar e unir duplicatas")
        if f == "buscando":
            return Estado(carregando=self.mostra_carregando)
        return Estado()

    # ------------------------------------------------------------------ ações
    def clicar_item_duplicatas(self, tipo: str) -> bool:
        ok = super().clicar_item_duplicatas(tipo)
        if ok:
            self.fase, self.ate = "buscando", self.relogio.agora() + self.dur_busca
        return ok

    def clicar_unir(self) -> bool:
        self._avancar()
        self.fases_cliques.append(self.fase)
        super().clicar_unir()
        if self.fase != "grupo" or not self.resposta_unir:
            return False
        self.unioes += 1
        self.restantes -= 1
        self.fase, self.ate = "unindo", self.relogio.agora() + self.dur_uniao
        return True

    def tentar_novamente(self) -> bool:
        self._avancar()
        super().tentar_novamente()
        self.tentativas += 1
        if self.fase == "erro":
            self.fase, self.ate = "buscando", self.relogio.agora() + self.dur_busca
        return True

    def fechar_modal(self) -> None:
        self._avancar()
        self.fases_fechar.append(self.fase)
        super().fechar_modal()
        self.fase = "lista"

    def cancelar_modal(self) -> bool:
        self._avancar()
        self.fases_fechar.append(self.fase)
        super().cancelar_modal()
        tinha = self.fase in ("grupo", "erro", "vazio")
        self.fase = "lista"
        return tinha
