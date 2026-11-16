"""O que sobra do extrato nao e erro: e o que nunca teve titulo.

Tarifa, imposto, folha, transferencia entre contas proprias. Aqui isso ganha
nome - primeiro por lexico, depois pelo que VOCE ensinou (uma correcao sua
vale mais que qualquer regra minha).
"""
from __future__ import annotations

from .dinheiro import dias, fichas

# (rotulo, direcao permitida, pistas). Direcao: '-' so saida, '+' so entrada,
# None qualquer. Um rotulo com direcao casada vale mais que um generico: e por
# isso que "RENDIMENTO APLICACAO AUTOMATICA" (entrada) e receita financeira e
# nao movimentacao interna, e que "ESTORNO TARIFA" (entrada) e estorno.
LEXICO = [
    ("Tarifas bancárias", "-", ("tarifa", "iof", "cesta", "pacote", "manutencao",
                                "anuidade", "custodia")),
    ("Impostos e contribuições", "-", ("darf", "irpj", "csll", "inss", "fgts", "iss",
                                       "icms", "das", "gps", "pis", "cofins", "irrf",
                                       "simples nacional", "tributo", "gare", "difal")),
    ("Folha de pagamento", "-", ("salario", "salarios", "folha", "labore", "rescisao",
                                  "ferias", "adiantamento", "beneficio")),
    ("Movimentação interna", None, ("aplicacao", "resgate", "cdb", "poupanca",
                                    "contas proprias", "mesma titularidade",
                                    "investimento", "automatica")),
    ("Receita financeira", "+", ("rendimento", "rendimentos", "remuneracao", "juros")),
    ("Estorno / devolução", None, ("estorno", "estornado", "devolucao", "cancelamento",
                                    "reembolso", "ressarcimento")),
    ("Juros e encargos", "-", ("juros", "multa", "mora", "encargo", "cheque especial")),
    ("Cartão", "-", ("cartao", "fatura cartao")),
    ("Empréstimo / financiamento", "-", ("emprestimo", "financiamento", "leasing",
                                          "consignado")),
]


def rotular(descricao: str, aprendidas: dict | None = None,
            cent: int | None = None) -> tuple[str, str]:
    """(rotulo, origem) - origem = 'aprendido' | 'lexico' | 'aberto'."""
    f = fichas(descricao)
    if aprendidas:
        chave = " ".join(sorted(f))
        if chave in aprendidas:
            return aprendidas[chave], "aprendido"
        for k, v in aprendidas.items():
            ka = set(k.split())
            if ka and len(ka & f) / len(ka) >= 0.8:
                return v, "aprendido"
    baixa = " " + " ".join(sorted(f)) + " "
    # a pista mais especifica ganha: 'RENDIMENTO APLICACAO' e receita
    # financeira, nao movimentacao interna, porque 'rendimento' diz mais.
    melhor, nota = None, 0
    for rotulo, direcao, pistas in LEXICO:
        if direcao and cent is not None:
            if (direcao == "-" and cent > 0) or (direcao == "+" and cent < 0):
                continue
        bonus = 3 if (direcao and cent is not None) else 0
        for p in pistas:
            if f" {p} " in baixa or (" " in p and p in baixa):
                if len(p) + bonus > nota:
                    melhor, nota = rotulo, len(p) + bonus
    return (melhor, "lexico") if melhor else ("Sem classificação", "aberto")


def pares_internos(sobras, janela: int = 3) -> list[tuple]:
    """Transferencia entre contas proprias: +X e -X proximos no tempo.
    Aparece duas vezes no extrato e nao tem titulo nenhum - conciliar isso
    contra o ERP e perda de tempo garantida."""
    porv: dict = {}
    for l in sobras:
        porv.setdefault(abs(l.cent), []).append(l)
    pares, usados = [], set()
    for v, grupo in sorted(porv.items()):
        pos = sorted([l for l in grupo if l.cent > 0], key=lambda l: (str(l.data), l.iid))
        neg = sorted([l for l in grupo if l.cent < 0], key=lambda l: (str(l.data), l.iid))
        for a in pos:
            if a.iid in usados:
                continue
            for b in neg:
                if b.iid in usados or dias(a.data, b.data) > janela:
                    continue
                pares.append((a.iid, b.iid))
                usados.add(a.iid)
                usados.add(b.iid)
                break
    return pares
