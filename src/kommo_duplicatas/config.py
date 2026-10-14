"""Preferências do usuário (última empresa, tipo, limite, modo privacidade, navegador que funcionou).

O arquivo fica em <raiz de dados>/config.json (ver paths.py). Não guarda senhas nem tokens.
- Escrita ATÔMICA: grava num temporário na mesma pasta e troca com os.replace (nunca deixa o JSON pela metade).
- Arquivo corrompido: é renomeado para config.json.corrompido, o app volta ao padrão e avisa
  (`carregar_detalhado()` devolve o aviso; `ultimo_aviso` guarda o último; também vai para o log).
- Campo com TIPO errado (ex.: "limite": "abc", "tipo": "pedidos", "privacidade": "sim"): só aquele campo volta
  ao padrão, com o mesmo aviso (arquivo não é renomeado). Nunca impede a janela de abrir.
- Pasta de dados não gravável: `paths.DataDirNotWritable` NÃO é engolida — a UI deve mostrá-la ao usuário.
"""
import json
import os
import tempfile
import time
from datetime import datetime

from . import paths

PADRAO = {
    "empresa": "",
    "tipo": "leads",          # "leads" | "contatos"
    "limite": 100,            # 0 = todas
    "limite_custom": None,    # último valor digitado no campo "outro" (int) ou None
    "privacidade": True,
    "canal_navegador": "",    # canal que abriu da última vez: "chrome" | "msedge" | "chromium" | ""
    "ultimo_total": 0,
    "ultima_execucao": "",
}

SUFIXO_CORROMPIDO = ".corrompido"

ultimo_aviso: str | None = None


TIPOS_VALIDOS = ("leads", "contatos")


def _inteiro(v):
    """int de verdade (bool não conta, apesar de ser subclasse de int) ou None."""
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def _validar(k: str, v):
    """Valida UM campo. Devolve (ok, valor_normalizado); ok=False -> o chamador usa o padrão daquele campo."""
    if k in ("empresa", "ultima_execucao"):
        return isinstance(v, str), v
    if k == "tipo":
        return v in TIPOS_VALIDOS, v
    if k in ("limite", "ultimo_total"):
        n = _inteiro(v)
        return n is not None and n >= 0, n
    if k == "privacidade":
        return isinstance(v, bool), v
    if k == "limite_custom":
        if v is None or v == "":
            return True, None
        if isinstance(v, str) and v.strip().isdigit():     # texto do campo "outro" (ex.: "350")
            return True, int(v.strip())
        n = _inteiro(v)
        return n is not None and n >= 0, n
    if k == "canal_navegador":
        if v is None:
            return True, ""
        return isinstance(v, str), str(v).strip().lower()
    return False, None


def _normalizar(campos: dict, invalidos: list | None = None) -> dict:
    """Mantém só chaves conhecidas e valida os TIPOS: valor inválido -> padrão daquele campo.

    Campos: empresa=str, tipo∈{leads,contatos}, limite=int>=0, limite_custom=int>=0|None, privacidade=bool,
    canal_navegador=str, ultimo_total=int>=0, ultima_execucao=str. Os nomes dos campos inválidos vão para
    `invalidos` (se dado) — `carregar_detalhado()` transforma isso num aviso, sem impedir a janela de abrir.
    """
    saida = {}
    for k, v in campos.items():
        if k not in PADRAO:
            continue
        ok, valor = _validar(k, v)
        if not ok:
            if invalidos is not None:
                invalidos.append(k)
            valor = PADRAO[k]
        saida[k] = valor
    return saida


def _avisar(msg: str) -> None:
    global ultimo_aviso
    ultimo_aviso = msg
    try:
        from . import logs           # import tardio: logs não depende de config
        logs.gravar("aviso", msg)
    except Exception:  # noqa: BLE001 - aviso é acessório; o retorno de carregar_detalhado já carrega a mensagem
        pass


def _isolar_corrompido(arquivo: str, motivo: str) -> str:
    destino = arquivo + SUFIXO_CORROMPIDO
    try:
        os.replace(arquivo, destino)
        msg = (f"O arquivo de configuração estava corrompido e foi guardado em {destino}. "
               f"Usando as preferências padrão. ({motivo})")
    except OSError as e:
        msg = (f"O arquivo de configuração {arquivo} está corrompido e não pôde ser renomeado ({e}). "
               "Usando as preferências padrão.")
    return msg


def carregar_detalhado() -> tuple[dict, str | None]:
    """Devolve (configuração, aviso). `aviso` é None quando tudo está bem."""
    cfg = dict(PADRAO)
    arquivo = paths.config_file()
    try:
        with open(arquivo, encoding="utf-8") as f:
            salvo = json.load(f)
        if not isinstance(salvo, dict):
            raise ValueError("conteúdo não é um objeto JSON")
    except FileNotFoundError:
        return cfg, None
    except (ValueError, UnicodeDecodeError) as e:      # JSON inválido / bytes estranhos
        aviso = _isolar_corrompido(arquivo, f"{type(e).__name__}: {e}")
        _avisar(aviso)
        return cfg, aviso
    except OSError as e:
        aviso = f"Não consegui ler {arquivo} ({e}). Usando as preferências padrão."
        _avisar(aviso)
        return cfg, aviso
    if "blur" in salvo and "privacidade" not in salvo:   # nome antigo da opção
        salvo["privacidade"] = salvo["blur"]
    invalidos: list = []
    cfg.update(_normalizar(salvo, invalidos))
    if invalidos:
        aviso = (f"O arquivo de configuração {arquivo} tem valor inválido em: {', '.join(invalidos)}. "
                 "Usando o padrão nesses campos.")
        _avisar(aviso)
        return cfg, aviso
    return cfg, None


def carregar() -> dict:
    return carregar_detalhado()[0]


def _gravar_atomico(arquivo: str, dados: dict) -> None:
    pasta = os.path.dirname(arquivo)
    fd, tmp = tempfile.mkstemp(prefix=".config-", suffix=".tmp", dir=pasta)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        # No Windows o os.replace pode falhar por alguns ms se antivírus/indexador estiver lendo o destino.
        for tentativa in range(5):
            try:
                os.replace(tmp, arquivo)
                return
            except PermissionError:
                if tentativa == 4:
                    raise
                time.sleep(0.05 * (tentativa + 1))
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def salvar(**campos) -> None:
    cfg = carregar()
    cfg.update(_normalizar(campos))
    _gravar_atomico(paths.config_file(), cfg)


def registrar_execucao(total: int) -> None:
    salvar(ultimo_total=int(total), ultima_execucao=datetime.now().isoformat(timespec="seconds"))
