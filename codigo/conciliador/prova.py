#!/usr/bin/env python3
"""Arnes adversarial. Uma so pergunta importa:

    o motor JA conciliou sozinho algo que estava errado?

Precisao dos vinculos automaticos tem de ser 1,0000. Sempre. Recall (quanto
ele resolve sozinho) e desejavel, mas nunca as custas da precisao - um erro
automatico em conciliacao custa mais caro que dez pendencias.
"""
from __future__ import annotations

import sys
import time

sys.path.insert(0, __file__.rsplit("/", 1)[0])

from nucleo.motor import Config, conciliar
from nucleo.simulador import gerar


def rodar(sementes=300, n_titulos=60, dureza=1.0, verboso=False):
    cfg = Config()
    tot_certos = tot_acertos = tot_verdade = 0
    tot_sug = tot_sug_ok = 0
    erros = []
    quebras = []
    t0 = time.time()
    for s in range(1, sementes + 1):
        lancs, tits, verdade = gerar(s, n_titulos, dureza)
        try:
            r = conciliar(lancs, tits, cfg)
        except AssertionError as e:
            quebras.append((s, str(e)))
            continue
        # idempotencia: mesma entrada, mesmo resultado
        r2 = conciliar(lancs, tits, cfg)
        if [c.iid for c in r.certos] != [c.iid for c in r2.certos]:
            quebras.append((s, "nao deterministico"))
        # ordem das linhas nao pode mudar o resultado
        r3 = conciliar(list(reversed(lancs)), list(reversed(tits)), cfg)
        if sorted(c.iid for c in r.certos) != sorted(c.iid for c in r3.certos):
            quebras.append((s, "sensivel a ordem do arquivo"))

        tot_verdade += len(verdade)
        for c in r.certos:
            tot_certos += 1
            par = (frozenset(c.lanc), frozenset(c.tits))
            if par in verdade:
                tot_acertos += 1
            else:
                erros.append((s, c, par))
        for c in r.sugestoes[:0] if False else []:
            pass
        # a sugestao no topo de cada disputa acerta?
        usados = set()
        for c in r.sugestoes:
            ids = set(c.lanc) | set(c.tits)
            if ids & usados:
                continue
            usados |= ids
            tot_sug += 1
            if (frozenset(c.lanc), frozenset(c.tits)) in verdade:
                tot_sug_ok += 1
    dt = time.time() - t0

    prec = tot_acertos / tot_certos if tot_certos else 1.0
    rec = tot_acertos / tot_verdade if tot_verdade else 0.0
    prec_sug = tot_sug_ok / tot_sug if tot_sug else 0.0
    print(f"cenarios .............. {sementes} ({dt:.1f}s)")
    print(f"pares verdadeiros ..... {tot_verdade}")
    print(f"conciliados sozinho ... {tot_certos}")
    print(f"PRECISAO automatica ... {prec:.4f}   <- tem de ser 1.0000")
    print(f"recall automatico ..... {rec:.4f}")
    print(f"1a sugestao correta ... {prec_sug:.4f} de {tot_sug} sugestoes de topo")
    print(f"invariantes quebrados . {len(quebras)}")
    if quebras[:5]:
        for s, m in quebras[:5]:
            print(f"   semente {s}: {m}")
    if erros:
        print(f"\nERROS AUTOMATICOS ({len(erros)}):")
        for s, c, par in erros[:8]:
            print(f"   semente {s} escore {c.escore:.3f} forma {c.forma} motivos {c.motivos}")
    return prec, rec, len(quebras), len(erros)


if __name__ == "__main__":
    args = dict(a.lstrip("-").split("=") for a in sys.argv[1:] if "=" in a)
    n = int(args.get("sementes", 300))
    print("=" * 62)
    print("PROVA 1 - carteira normal (60 titulos)")
    print("=" * 62)
    p1, r1, q1, e1 = rodar(n, 60, 1.0)
    print()
    print("=" * 62)
    print("PROVA 2 - carteira grande e mais suja (200 titulos, dureza 1.6)")
    print("=" * 62)
    p2, r2, q2, e2 = rodar(max(30, n // 5), 200, 1.6)
    print()
    print("=" * 62)
    print("PROVA 3 - carteira minuscula (5 titulos) - pouco contexto de IDF")
    print("=" * 62)
    p3, r3, q3, e3 = rodar(n, 5, 1.0)
    print()
    ok = (p1 == p2 == p3 == 1.0) and not (q1 + q2 + q3 + e1 + e2 + e3)
    print("VEREDITO:", "APROVADO - zero conciliacao automatica errada"
          if ok else "REPROVADO")
    sys.exit(0 if ok else 1)
