"""Dinheiro, datas e nomes — sem float, sem dependência externa.

Regra de ouro: dinheiro é SEMPRE int de centavos. Float em conciliacao
produz 0,01 fantasma e destroi qualquer invariante de soma.
"""
from __future__ import annotations

import datetime as _dt
import re
import unicodedata

# ---------------------------------------------------------------- dinheiro

_LIXO_VALOR = re.compile(r"[^\d,.\-+()]")


def centavos(bruto) -> int | None:
    """Converte texto/numero em centavos (int). None se nao for dinheiro.

    Aceita: 1.234,56 (BR)  1,234.56 (US)  1234.56  1234,56  -50  (50)  R$ 50
    Parenteses e sufixo D/C sao tratados por quem chama (coluna de tipo).
    """
    if bruto is None:
        return None
    if isinstance(bruto, int) and not isinstance(bruto, bool):
        return bruto * 100
    if isinstance(bruto, float):
        return int(round(bruto * 100))
    s = str(bruto).strip()
    if not s:
        return None
    negativo = False
    if s.startswith("(") and s.endswith(")"):
        negativo, s = True, s[1:-1]
    s = _LIXO_VALOR.sub("", s)
    if not s:
        return None
    if s.startswith("-"):
        negativo, s = True, s[1:]
    elif s.startswith("+"):
        s = s[1:]
    s = s.replace("(", "").replace(")", "")
    if not s or not any(c.isdigit() for c in s):
        return None

    tem_v, tem_p = "," in s, "." in s
    if tem_v and tem_p:
        # o separador decimal e o ultimo a aparecer
        dec = "," if s.rindex(",") > s.rindex(".") else "."
        s = s.replace("," if dec == "." else ".", "").replace(dec, ".")
    elif tem_v or tem_p:
        sep = "," if tem_v else "."
        partes = s.split(sep)
        # milhar: todos os grupos apos o primeiro tem exatamente 3 digitos
        milhar = len(partes) > 1 and all(len(p) == 3 for p in partes[1:]) and 1 <= len(partes[0]) <= 3
        # virgula com 1-2 casas e sempre decimal (1,5 / 1,50)
        if sep == "," and len(partes) == 2 and len(partes[1]) in (1, 2):
            milhar = False
        if sep == "." and len(partes) == 2 and len(partes[1]) in (1, 2):
            milhar = False
        s = s.replace(sep, "") if milhar else s.replace(sep, ".")

    try:
        inteiro, _, frac = s.partition(".")
        inteiro = inteiro or "0"
        frac = (frac + "00")[:2]
        v = int(inteiro) * 100 + int(frac)
    except ValueError:
        return None
    return -v if negativo else v


def _milhar_provavel(s: str) -> bool:
    """'1.234' e milhar; '10.50' e decimal. Heuristica: grupos de 3 exatos."""
    sep = "." if "." in s else ","
    partes = s.split(sep)
    if len(partes) < 2:
        return False
    return all(len(p) == 3 for p in partes[1:]) and 1 <= len(partes[0]) <= 3


def reais(c: int) -> str:
    sinal = "-" if c < 0 else ""
    c = abs(int(c))
    inteiro, cent = divmod(c, 100)
    txt = f"{inteiro:,}".replace(",", ".")
    return f"{sinal}{txt},{cent:02d}"


# ---------------------------------------------------------------- datas

_FORMATOS = (
    "%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y",
    "%Y/%m/%d", "%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S",
    "%Y%m%d", "%d%m%Y",
)
_EPOCA_EXCEL = _dt.date(1899, 12, 30)


def ler_data(bruto) -> _dt.date | None:
    if bruto is None:
        return None
    if isinstance(bruto, _dt.datetime):
        return bruto.date()
    if isinstance(bruto, _dt.date):
        return bruto
    if isinstance(bruto, (int, float)) and not isinstance(bruto, bool):
        n = int(bruto)
        if 20000 <= n <= 80000:          # serial do Excel (1954..2119)
            return _EPOCA_EXCEL + _dt.timedelta(days=n)
        return None
    s = str(bruto).strip()
    if not s:
        return None
    s = s.split("T")[0].strip() if ("T" in s and "-" in s[:10]) else s
    for f in _FORMATOS:
        try:
            return _dt.datetime.strptime(s, f).date()
        except ValueError:
            continue
    if s.isdigit() and 5 <= len(s) <= 5 + 0:
        return None
    if s.replace(".", "").isdigit():
        try:
            n = int(float(s))
            if 20000 <= n <= 80000:
                return _EPOCA_EXCEL + _dt.timedelta(days=n)
        except ValueError:
            pass
    return None


def dias(a: _dt.date | None, b: _dt.date | None) -> int:
    if a is None or b is None:
        return 9999
    return abs((a - b).days)


# ---------------------------------------------------------------- nomes

_RUIDO = {
    "ltda", "me", "eireli", "sa", "s", "a", "epp", "mei", "cia", "e", "de", "da",
    "do", "das", "dos", "the", "pagamento", "pag", "pgto", "ted", "doc", "pix",
    "transf", "transferencia", "recebimento", "rec", "deb", "cred", "debito",
    "credito", "titulo", "boleto", "cobranca", "liquidacao", "conta", "cc",
    "banco", "bco", "para", "por", "em", "no", "na", "ref", "nf", "nfe", "fatura",
    "enviado", "recebido", "eletronico", "eletronica", "compensacao", "interna",
}
_SO_LETRAS = re.compile(r"[^a-z0-9 ]")


def acentos_fora(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )


def fichas(texto: str) -> frozenset[str]:
    """Tokens significativos de um nome/descricao, normalizados."""
    if not texto:
        return frozenset()
    s = _SO_LETRAS.sub(" ", acentos_fora(str(texto)).lower())
    saida = set()
    for t in s.split():
        if t in _RUIDO or (len(t) <= 2 and not t.isdigit()):
            continue
        saida.add(t)
    return frozenset(saida)


def similaridade(a: frozenset[str], b: frozenset[str], peso=None) -> float:
    """Quanto do nome de referencia (o conjunto menor) aparece no outro.

    Nao e Jaccard: a descricao do extrato e longa e cheia de ruido, o nome do
    fornecedor e curto. Cada ficha vale seu peso de informacao - `peso` vem do
    IDF calculado sobre os proprios dados (fichas comuns valem quase nada).
    Token com prefixo de 4 letras igual conta 0,85 (erro de digitacao/truncagem).
    """
    if not a or not b:
        return 0.0
    peso = peso or (lambda t: 1.0)
    menor, maior = (a, b) if len(a) <= len(b) else (b, a)
    total = sum(peso(t) for t in menor)
    if total <= 0:
        return 0.0
    ganho = 0.0
    for t in menor:
        if t in maior:
            ganho += peso(t)
        elif len(t) >= 4 and any(
            (o.startswith(t[:4]) or t.startswith(o[:4])) and abs(len(o) - len(t)) <= 3
            for o in maior
        ):
            ganho += 0.85 * peso(t)
    return min(1.0, ganho / total)


def pesos_idf(textos) -> dict:
    """Peso de informacao de cada ficha: log(N/df). Ficha que aparece em todo
    lugar ('comercio', 'ltda') vale quase zero; ficha rara vale muito."""
    import math
    from collections import Counter
    df = Counter()
    n = 0
    for t in textos:
        n += 1
        df.update(fichas(t))
    if n == 0:
        return {}
    return {t: math.log((n + 1) / (c + 0.5)) for t, c in df.items()}


def peso_de(tabela: dict, padrao: float = 1.0):
    if not tabela:
        return lambda t: padrao
    teto = max(tabela.values()) or 1.0
    return lambda t: max(0.08, tabela.get(t, teto) / teto)


_DIGITOS = re.compile(r"\d+")


def documentos(texto: str) -> frozenset[str]:
    """Numeros com 3+ digitos dentro de um texto (NF, boleto, contrato)."""
    if not texto:
        return frozenset()
    return frozenset(
        d.lstrip("0") or "0" for d in _DIGITOS.findall(str(texto)) if len(d) >= 3
    )


def so_digitos(s) -> str:
    return "".join(c for c in str(s or "") if c.isdigit())
