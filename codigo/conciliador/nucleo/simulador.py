"""Gerador de cenarios com verdade conhecida.

Serve para duas coisas: o botao "ver com dados de exemplo" da interface e o
arnes adversarial. As armadilhas aqui sao as que realmente derrubam quem
concilia no Excel.
"""
from __future__ import annotations

import datetime as _dt
import random

from .motor import Lancamento, Titulo, id_de

PARTES = [
    "ALFA COMERCIO LTDA", "BETA DISTRIBUIDORA LTDA",
    "PADARIA SOL NASCENTE ME", "ALFA SERVICOS DE LIMPEZA LTDA",
    "ALFA COMERCIO DE PAPEIS LTDA", "TRANSPORTES ANDORINHA S/A",
    "GRAFICA HORIZONTE EIRELI", "CLINICA VIDA PLENA LTDA",
    "SUPRIMENTOS ZENITE LTDA", "AGUA E LUZ ENERGIA SA",
    "MERCADO BOM PRECO LTDA", "SEGURANCA VIGIL FORTE LTDA",
    "CONTABIL PRECISA ASSESSORIA", "SOFTWARE NUVEM AZUL LTDA",
    "METALURGICA IPE AMARELO LTDA", "ATACADO SAO JORGE LTDA",
]
PREFIXOS = ["PIX ENVIADO", "TED", "PAGAMENTO", "DEB AUTOMATICO", "PAG BOLETO",
            "LIQUIDACAO COBRANCA", "PIX QR CODE", "DOC E"]
PREFIXOS_IN = ["PIX RECEBIDO", "TED RECEBIDA", "CREDITO COBRANCA",
               "LIQUIDACAO TITULO", "DEPOSITO"]
RUIDO_BANCO = [
    ("TARIFA PACOTE DE SERVICOS", -8990), ("TARIFA TED", -1290),
    ("IOF", -437), ("RENDIMENTO APLICACAO AUTOMATICA", 12045),
    ("TRANSFERENCIA ENTRE CONTAS PROPRIAS", -500000),
    ("DARF IRPJ CODIGO 2089", -234567), ("FGTS COMPETENCIA", -87610),
    ("TARIFA MANUTENCAO CONTA", -3500), ("ESTORNO TARIFA", 1290),
]


def gerar(semente: int = 7, n_titulos: int = 60, dureza: float = 1.0):
    """Devolve (lancamentos, titulos, verdade) onde verdade e o conjunto de
    pares (frozenset(lanc_ids), frozenset(tit_ids)) realmente corretos."""
    r = random.Random(semente)
    base = _dt.date(2026, 7, 1)
    tits, lancs, verdade = [], [], []
    seq = [0]

    def novo_tit(parte, cent, tipo, venc, doc, pago=None):
        seq[0] += 1
        t = Titulo(
            iid=id_de("titulo", semente, seq[0], parte, cent, venc),
            tipo=tipo, cent=abs(cent), data=pago, vencimento=venc,
            contraparte=parte, documento=doc, categoria="", linha=seq[0],
        )
        tits.append(t)
        return t

    def novo_lanc(data, cent, desc, doc=""):
        seq[0] += 1
        l = Lancamento(
            iid=id_de("lanc", semente, seq[0], data, cent, desc),
            data=data, cent=cent, descricao=desc, documento=doc, linha=seq[0],
        )
        lancs.append(l)
        return l

    def descreve(parte, entrada=False, com_doc=None, truncar=True):
        pre = r.choice(PREFIXOS_IN if entrada else PREFIXOS)
        nome = parte
        if truncar and r.random() < 0.6:
            nome = " ".join(parte.split()[: r.randint(1, 3)])
        txt = f"{pre} {nome}"
        if com_doc and r.random() < 0.5:
            txt += f" NF {com_doc}"
        return txt[:60]

    for i in range(n_titulos):
        parte = r.choice(PARTES)
        tipo = "receber" if r.random() < 0.35 else "pagar"
        cent = r.choice([r.randint(5000, 900000), r.randrange(10000, 500000, 5000)])
        venc = base + _dt.timedelta(days=r.randint(0, 27))
        doc = str(r.randint(1000, 99999))
        sorte = r.random()

        if sorte < 0.10 * dureza:                    # titulo em aberto: nao pagou
            novo_tit(parte, cent, tipo, venc, doc)
            continue

        atraso = r.choice([0, 0, 1, 1, 2, 3, -1, 5])
        dpag = venc + _dt.timedelta(days=atraso)
        sinal = 1 if tipo == "receber" else -1

        if sorte < 0.10 * dureza + 0.10:             # pagamento em lote (1:N)
            n = r.randint(2, 3)
            grupo = [novo_tit(parte, cent, tipo, venc, str(r.randint(1000, 99999)))]
            for _ in range(n - 1):
                c2 = r.randint(5000, 400000)
                grupo.append(novo_tit(parte, c2, tipo, venc + _dt.timedelta(days=r.randint(-2, 2)), str(r.randint(1000, 99999))))
            total = sum(t.cent for t in grupo)
            l = novo_lanc(dpag, sinal * total, descreve(parte, tipo == "receber"))
            verdade.append((frozenset({l.iid}), frozenset(t.iid for t in grupo)))
            continue

        if sorte < 0.10 * dureza + 0.16:             # juros/multa ou desconto
            t = novo_tit(parte, cent, tipo, venc, doc)
            extra = r.choice([r.randint(50, 400), -r.randint(50, 400)])
            l = novo_lanc(dpag, sinal * (cent + extra), descreve(parte, tipo == "receber", doc))
            verdade.append((frozenset({l.iid}), frozenset({t.iid})))
            continue

        if sorte < 0.10 * dureza + 0.22:             # armadilha: par de valor identico
            p2 = r.choice([p for p in PARTES if p != parte])
            t1 = novo_tit(parte, cent, tipo, venc, doc)
            t2 = novo_tit(p2, cent, tipo, venc, str(r.randint(1000, 99999)))
            l1 = novo_lanc(dpag, sinal * cent, descreve(parte, tipo == "receber", doc))
            l2 = novo_lanc(dpag, sinal * cent, descreve(p2, tipo == "receber", t2.documento))
            verdade.append((frozenset({l1.iid}), frozenset({t1.iid})))
            verdade.append((frozenset({l2.iid}), frozenset({t2.iid})))
            continue

        if sorte < 0.10 * dureza + 0.27:             # descricao anonima (sem nome)
            t = novo_tit(parte, cent, tipo, venc, doc)
            l = novo_lanc(dpag, sinal * cent, r.choice(
                ["PAGAMENTO FORNECEDOR", "PIX ENVIADO", "LIQUIDACAO", "TED SAIDA",
                 "CREDITO EM CONTA", "PIX RECEBIDO"]))
            verdade.append((frozenset({l.iid}), frozenset({t.iid})))
            continue

        if sorte < 0.10 * dureza + 0.31:             # pagamento dividido (N:1)
            t = novo_tit(parte, cent, tipo, venc, doc)
            metade = cent // 2
            l1 = novo_lanc(dpag, sinal * metade, descreve(parte, tipo == "receber"))
            l2 = novo_lanc(dpag + _dt.timedelta(days=1), sinal * (cent - metade), descreve(parte, tipo == "receber"))
            verdade.append((frozenset({l1.iid, l2.iid}), frozenset({t.iid})))
            continue

        t = novo_tit(parte, cent, tipo, venc, doc, pago=dpag if r.random() < 0.5 else None)
        l = novo_lanc(dpag, sinal * cent, descreve(parte, tipo == "receber", doc))
        verdade.append((frozenset({l.iid}), frozenset({t.iid})))

    for _ in range(int(n_titulos * 0.20)):           # ruido puro do banco
        desc, cent = r.choice(RUIDO_BANCO)
        novo_lanc(base + _dt.timedelta(days=r.randint(0, 30)),
                  cent + r.randint(-300, 300), desc)

    if r.random() < 0.7:                             # duplicata no extrato
        if lancs:
            l = r.choice(lancs)
            novo_lanc(l.data, l.cent, l.descricao)

    r.shuffle(lancs)
    r.shuffle(tits)
    return lancs, tits, set(verdade)
