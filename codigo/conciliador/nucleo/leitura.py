"""Le o que o banco e o ERP cospem: CSV, XLSX e OFX. Só stdlib.

O usuario nao configura nada: as colunas sao descobertas pelo cabecalho E
confirmadas pelo conteudo (uma coluna chamada "Data" que nao contem datas nao
e a coluna de data).
"""
from __future__ import annotations

import csv
import io
import re
import zipfile
from xml.etree import ElementTree

from .dinheiro import acentos_fora, centavos, ler_data

# ---------------------------------------------------------------- CSV

def _texto(bytes_: bytes) -> str:
    for cod in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return bytes_.decode(cod)
        except UnicodeDecodeError:
            continue
    return bytes_.decode("latin-1", "replace")


def ler_csv(bytes_: bytes) -> list[list]:
    txt = _texto(bytes_)
    amostra = "\n".join(txt.splitlines()[:40])
    try:
        dial = csv.Sniffer().sniff(amostra, delimiters=";,\t|")
        sep = dial.delimiter
    except csv.Error:
        sep = max(";,\t|", key=lambda c: amostra.count(c))
    linhas = [l for l in csv.reader(io.StringIO(txt), delimiter=sep)]
    return [l for l in linhas if any(str(c).strip() for c in l)]


# ---------------------------------------------------------------- XLSX

_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_FMT_DATA = re.compile(r"(?<!\\)(yy|mm?/|dd|d/|m/d|y{2,4})", re.I)


def ler_xlsx(bytes_: bytes) -> list[list]:
    with zipfile.ZipFile(io.BytesIO(bytes_)) as z:
        partilhadas = []
        if "xl/sharedStrings.xml" in z.namelist():
            raiz = ElementTree.fromstring(z.read("xl/sharedStrings.xml"))
            for si in raiz.findall(f"{_NS}si"):
                partilhadas.append("".join(t.text or "" for t in si.iter(f"{_NS}t")))
        estilos_data = _estilos_de_data(z)
        alvo = next(
            (n for n in z.namelist() if n.startswith("xl/worksheets/sheet") and n.endswith(".xml")),
            None,
        )
        if not alvo:
            return []
        raiz = ElementTree.fromstring(z.read(alvo))
        linhas = []
        for tr in raiz.iter(f"{_NS}row"):
            linha, ultima = [], 0
            for td in tr.findall(f"{_NS}c"):
                ref = td.get("r") or ""
                col = _coluna_para_indice("".join(c for c in ref if c.isalpha()))
                while len(linha) < col:
                    linha.append("")
                linha.append(_valor_celula(td, partilhadas, estilos_data))
                ultima = col
            if any(str(c).strip() for c in linha):
                linhas.append(linha)
        return linhas


def _estilos_de_data(z) -> set[int]:
    """Indices de estilo cujo formato de numero e uma data."""
    try:
        raiz = ElementTree.fromstring(z.read("xl/styles.xml"))
    except KeyError:
        return set()
    embutidos = set(range(14, 23)) | {45, 46, 47}
    codigos = {}
    for nf in raiz.iter(f"{_NS}numFmt"):
        cid = int(nf.get("numFmtId", "0"))
        if _FMT_DATA.search(nf.get("formatCode", "")):
            codigos[cid] = True
    saida = set()
    xfs = raiz.find(f"{_NS}cellXfs")
    if xfs is None:
        return saida
    for i, xf in enumerate(xfs.findall(f"{_NS}xf")):
        nid = int(xf.get("numFmtId", "0"))
        if nid in embutidos or codigos.get(nid):
            saida.add(i)
    return saida


def _coluna_para_indice(letras: str) -> int:
    n = 0
    for c in letras.upper():
        n = n * 26 + (ord(c) - 64)
    return max(0, n - 1)


def _valor_celula(td, partilhadas, estilos_data):
    tipo = td.get("t")
    v = td.find(f"{_NS}v")
    if tipo == "s":
        try:
            return partilhadas[int(v.text)]
        except (TypeError, ValueError, IndexError):
            return ""
    if tipo == "inlineStr":
        it = td.find(f"{_NS}is")
        return "".join(t.text or "" for t in it.iter(f"{_NS}t")) if it is not None else ""
    if v is None or v.text is None:
        return ""
    bruto = v.text
    estilo = td.get("s")
    if estilo is not None and int(estilo) in estilos_data:
        d = ler_data(float(bruto)) if _numero(bruto) else None
        if d:
            return d
    if _numero(bruto):
        f = float(bruto)
        return int(f) if f == int(f) else f
    return bruto


def _numero(s: str) -> bool:
    try:
        float(s)
        return True
    except (TypeError, ValueError):
        return False


# ---------------------------------------------------------------- OFX

def ler_ofx(bytes_: bytes) -> list[dict]:
    """Extrai transacoes de OFX 1.x (SGML) e 2.x (XML) com regex tolerante."""
    txt = _texto(bytes_)
    saida = []
    for bloco in re.findall(r"<STMTTRN>(.*?)</STMTTRN>", txt, re.S | re.I):
        def campo(tag):
            m = re.search(rf"<{tag}>([^<\r\n]*)", bloco, re.I)
            return (m.group(1).strip() if m else "")
        data = campo("DTPOSTED")[:8]
        memo = " ".join(x for x in (campo("MEMO"), campo("NAME")) if x)
        saida.append(
            {
                "data": ler_data(data),
                "centavos": centavos(campo("TRNAMT")),
                "descricao": memo,
                "documento": campo("CHECKNUM") or campo("REFNUM") or campo("FITID"),
            }
        )
    return [t for t in saida if t["data"] and t["centavos"] is not None]


# ---------------------------------------------------------------- roteador

def ler_arquivo(nome: str, bytes_: bytes) -> tuple[str, object]:
    """('ofx', [dict]) ou ('tabela', [[celulas]])."""
    n = nome.lower()
    cabeca = bytes_[:400].lower()
    if n.endswith(".ofx") or n.endswith(".qfx") or b"<ofx" in cabeca or b"ofxheader" in cabeca:
        return "ofx", ler_ofx(bytes_)
    if n.endswith((".xlsx", ".xlsm")) or bytes_[:2] == b"PK":
        return "tabela", ler_xlsx(bytes_)
    return "tabela", ler_csv(bytes_)


# ---------------------------------------------------------------- colunas

PISTAS = {
    "data": ("data", "data mov", "dt", "data lancamento", "data pagamento", "data baixa",
             "data de pagamento", "data credito", "data debito", "competencia", "emissao",
             "data de emissao", "liquidacao", "data de liquidacao", "pagamento"),
    "vencimento": ("vencimento", "venc", "data vencimento", "data de vencimento", "dt venc"),
    "valor": ("valor", "vlr", "valor documento", "valor titulo", "montante", "total",
              "valor pago", "valor liquido", "amount", "valor r", "valor original"),
    "debito": ("debito", "saida", "pagamentos", "valor debito", "vlr debito", "saidas"),
    "credito": ("credito", "entrada", "recebimentos", "valor credito", "vlr credito", "entradas"),
    "tipo_dc": ("d c", "dc", "tipo mov", "tipo lancamento", "natureza", "d/c"),
    "descricao": ("historico", "descricao", "memo", "lancamento", "detalhe", "observacao",
                  "obs", "complemento", "historico completo"),
    "contraparte": ("cliente", "fornecedor", "razao social", "nome", "cliente fornecedor",
                    "favorecido", "beneficiario", "pagador", "sacado", "cedente",
                    "nome cliente", "nome fornecedor", "razao"),
    "documento": ("documento", "doc", "numero documento", "nf", "nota", "num nf",
                  "numero", "titulo", "num titulo", "nosso numero", "boleto", "n doc"),
    "categoria": ("categoria", "conta", "plano de contas", "classificacao", "centro de custo"),
    "tipo": ("tipo", "especie", "natureza titulo", "operacao"),
    "saldo": ("saldo", "saldo atual"),
}


def _limpa(s) -> str:
    s = acentos_fora(str(s or "")).lower()
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def achar_cabecalho(linhas: list[list]) -> int:
    """Muitos relatorios tem titulo/logo antes da tabela. Acha a linha de
    cabecalho: a primeira com >=2 celulas de texto que casam com as pistas."""
    todas = {p for grupo in PISTAS.values() for p in grupo}
    melhor, nota_melhor = 0, -1
    for i, l in enumerate(linhas[:30]):
        nota = sum(1 for c in l if _limpa(c) in todas)
        preenchidas = sum(1 for c in l if str(c).strip())
        if preenchidas >= 2 and nota > nota_melhor:
            melhor, nota_melhor = i, nota
    return melhor if nota_melhor >= 2 else 0


def mapear(linhas: list[list]) -> tuple[int, dict]:
    """Descobre indice de cada papel. Cabecalho propõe, conteudo confirma."""
    i_cab = achar_cabecalho(linhas)
    cab = [_limpa(c) for c in linhas[i_cab]]
    corpo = linhas[i_cab + 1:]
    largura = max([len(cab)] + [len(l) for l in corpo[:200]] or [0])

    perfil = _perfilar(corpo, largura)
    mapa: dict[str, int] = {}
    usados: set[int] = set()

    # duas passadas: primeiro os cabecalhos que casam EXATO (senao 'Tipo' e
    # capturada por 'tipo mov' antes de 'tipo' chegar a vez dela), depois os
    # parciais com as colunas que sobraram.
    for exigir_exato in (True, False):
     for papel, pistas in PISTAS.items():
        if papel in mapa:
            continue
        candidatos = []
        for j in range(largura):
            nome = cab[j] if j < len(cab) else ""
            if not nome:
                continue
            if nome in pistas:
                nota = 3.0
            elif exigir_exato:
                continue
            elif any(p in nome or nome in p for p in pistas):
                nota = 2.0
            elif any(t in nome.split() for p in pistas for t in p.split() if len(t) > 3):
                nota = 1.0
            else:
                continue
            if papel in ("data", "vencimento") and perfil[j]["data"] < 0.6:
                continue
            if papel in ("valor", "debito", "credito") and perfil[j]["valor"] < 0.6:
                continue
            candidatos.append((nota + perfil[j]["preenchida"], j))
        for _, j in sorted(candidatos, reverse=True):
            if j not in usados:
                mapa[papel], _ = j, usados.add(j)
                break

    # rede de seguranca: sem coluna de data ou valor, usa o conteudo
    if "data" not in mapa:
        livres = [(perfil[j]["data"], j) for j in range(largura) if j not in usados and perfil[j]["data"] >= 0.7]
        if livres:
            mapa["data"] = max(livres)[1]
            usados.add(mapa["data"])
    if "valor" not in mapa and "debito" not in mapa and "credito" not in mapa:
        livres = [(perfil[j]["valor"], j) for j in range(largura) if j not in usados and perfil[j]["valor"] >= 0.7]
        if livres:
            mapa["valor"] = max(livres)[1]
            usados.add(mapa["valor"])
    if "descricao" not in mapa and "contraparte" not in mapa:
        livres = [(perfil[j]["texto"], j) for j in range(largura) if j not in usados]
        if livres and max(livres)[0] >= 0.5:
            mapa["descricao"] = max(livres)[1]
    return i_cab, mapa


def _perfilar(corpo: list[list], largura: int) -> list[dict]:
    perfil = []
    amostra = corpo[:300]
    for j in range(largura):
        vals = [l[j] for l in amostra if j < len(l) and str(l[j]).strip()]
        n = len(vals) or 1
        d = sum(1 for v in vals if ler_data(v) is not None)
        m = sum(1 for v in vals if centavos(v) is not None and not str(v).strip().isalpha())
        t = sum(1 for v in vals if isinstance(v, str) and len(v.strip()) >= 4 and not v.strip().replace(".", "").replace(",", "").replace("-", "").isdigit())
        perfil.append(
            {
                "data": d / n,
                "valor": (m - d) / n if m > d else m / n * (0.2 if d / n > 0.6 else 1.0),
                "texto": t / n,
                "preenchida": len(vals) / max(1, len(amostra)),
            }
        )
    return perfil


def celula(linha: list, j: int | None):
    if j is None or j >= len(linha):
        return ""
    return linha[j]
