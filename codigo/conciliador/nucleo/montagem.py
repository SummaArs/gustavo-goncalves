"""De arquivo bruto a entidades. Ninguem configura coluna nenhuma."""
from __future__ import annotations

from .dinheiro import centavos, ler_data, so_digitos
from .leitura import celula, ler_arquivo, mapear
from .motor import Lancamento, Titulo, id_de

PAGAR = ("pagar", "pagamento", "despesa", "debito", "saida", "fornecedor", "p", "d")
RECEBER = ("receber", "recebimento", "receita", "credito", "entrada", "cliente", "r", "c")


def classificar(nome: str, kind: str, mapa: dict, linhas: list) -> tuple[str, float]:
    """'extrato' ou 'titulos', com confianca. O extrato tem saldo, debito/credito
    e sinais mistos; a carteira do ERP tem vencimento e contraparte nomeada."""
    if kind == "ofx":
        return "extrato", 1.0
    n = nome.lower()
    e = t = 0.0
    if "saldo" in mapa:
        e += 2
    if "debito" in mapa or "credito" in mapa or "tipo_dc" in mapa:
        e += 2
    if "vencimento" in mapa:
        t += 2.5
    if "contraparte" in mapa:
        t += 1.5
    if "categoria" in mapa:
        t += 1
    for pista, peso in (("extrato", 3), ("bancari", 2), ("ofx", 2), ("conta corrente", 2)):
        if pista in n:
            e += peso
    for pista, peso in (("pagar", 3), ("receber", 3), ("titulo", 2), ("carteira", 2),
                        ("razonete", 1), ("omie", 1), ("erp", 1), ("aberto", 1)):
        if pista in n:
            t += peso
    if "descricao" in mapa and "vencimento" not in mapa:
        e += 1
    return ("extrato", e / (e + t)) if e >= t else ("titulos", t / (e + t or 1))


def _valor(linha, mapa) -> int | None:
    if "debito" in mapa or "credito" in mapa:
        d = centavos(celula(linha, mapa.get("debito"))) or 0
        c = centavos(celula(linha, mapa.get("credito"))) or 0
        if d or c:
            return abs(c) - abs(d)
    v = centavos(celula(linha, mapa.get("valor")))
    if v is None:
        return None
    if "tipo_dc" in mapa:
        marca = str(celula(linha, mapa["tipo_dc"])).strip().lower()[:1]
        if marca in ("d", "s", "-"):
            return -abs(v)
        if marca in ("c", "e", "+"):
            return abs(v)
    return v


def _txt(linha, mapa, *papeis) -> str:
    return " ".join(
        str(celula(linha, mapa[p])).strip() for p in papeis if p in mapa
    ).strip()


def montar_lancamentos(nome: str, bytes_: bytes) -> tuple[list, dict]:
    kind, dados = ler_arquivo(nome, bytes_)
    if kind == "ofx":
        saida = [
            Lancamento(
                iid=id_de("lanc", nome, i, t["data"], t["centavos"], t["descricao"]),
                data=t["data"], cent=t["centavos"], descricao=t["descricao"],
                documento=str(t["documento"] or ""), linha=i + 1,
            )
            for i, t in enumerate(dados)
        ]
        return saida, {"formato": "OFX", "colunas": {}, "linhas": len(saida)}

    i_cab, mapa = mapear(dados)
    saida, ignoradas = [], 0
    for i, linha in enumerate(dados[i_cab + 1:], start=i_cab + 2):
        d = ler_data(celula(linha, mapa.get("data")))
        v = _valor(linha, mapa)
        if d is None or v is None or v == 0:
            ignoradas += 1
            continue
        desc = _txt(linha, mapa, "descricao", "contraparte") or _txt(linha, mapa, "categoria")
        saida.append(
            Lancamento(
                iid=id_de("lanc", nome, i, d, v, desc),
                data=d, cent=v, descricao=desc,
                documento=str(celula(linha, mapa.get("documento")) or ""), linha=i,
            )
        )
    return saida, {"formato": "tabela", "colunas": mapa, "linhas": len(saida),
                   "ignoradas": ignoradas, "cabecalho": i_cab + 1}


def montar_titulos(nome: str, bytes_: bytes) -> tuple[list, dict]:
    kind, dados = ler_arquivo(nome, bytes_)
    if kind == "ofx":
        return [], {"erro": "OFX é extrato bancário, não carteira de títulos"}
    i_cab, mapa = mapear(dados)
    n = nome.lower()
    padrao = "pagar" if "pagar" in n else ("receber" if "receber" in n else "")
    saida, ignoradas = [], 0
    for i, linha in enumerate(dados[i_cab + 1:], start=i_cab + 2):
        v = centavos(celula(linha, mapa.get("valor")))
        venc = ler_data(celula(linha, mapa.get("vencimento")))
        pago = ler_data(celula(linha, mapa.get("data")))
        if v is None or v == 0 or (venc is None and pago is None):
            ignoradas += 1
            continue
        tipo = padrao
        if "tipo" in mapa:
            marca = str(celula(linha, mapa["tipo"])).strip().lower()
            if any(marca.startswith(p) for p in PAGAR):
                tipo = "pagar"
            elif any(marca.startswith(p) for p in RECEBER):
                tipo = "receber"
        if not tipo and v < 0:
            tipo = "pagar"
        elif not tipo and "cliente" in " ".join(str(c).lower() for c in dados[i_cab]):
            tipo = "receber"
        saida.append(
            Titulo(
                iid=id_de("titulo", nome, i, v, venc, pago),
                tipo=tipo, cent=abs(v), data=pago, vencimento=venc,
                contraparte=_txt(linha, mapa, "contraparte") or _txt(linha, mapa, "descricao"),
                documento=str(celula(linha, mapa.get("documento")) or ""),
                categoria=str(celula(linha, mapa.get("categoria")) or ""), linha=i,
            )
        )
    return saida, {"formato": "tabela", "colunas": mapa, "linhas": len(saida),
                   "ignoradas": ignoradas, "cabecalho": i_cab + 1}


def identificar(nome: str, bytes_: bytes) -> tuple[str, float]:
    kind, dados = ler_arquivo(nome, bytes_)
    if kind == "ofx":
        return "extrato", 1.0
    _, mapa = mapear(dados)
    return classificar(nome, kind, mapa, dados)
