"""
HEMOS — onde este paradigma quebra?

O HEMOS funciona com ~50 símbolos. Isso não prova nada sobre arquitetura: um
sistema de 50 símbolos pode ser só uma tabela grande com boa apresentação. A
pergunta que decide se há um princípio aqui é de ESCALA.

A hipótese (que pode ser refutada aqui)
───────────────────────────────────────
Um Transformer considera todo o vocabulário a cada passo: o custo e a
ambiguidade crescem com |Σ|, o tamanho do que o sistema sabe. O HEMOS considera
~7 símbolos por pergunta, porque o ESTADO restringe o que é admissível agora.

    H: o que limita um resolvedor discreto não é |Σ|, é |Σ_contexto|.

Se H for verdadeira, então crescer o léxico de 50 para 20.000 símbolos deve
deixar latência e rejeição praticamente PLANAS enquanto o contexto for pequeno —
e deve degradar visivelmente quando o contexto for o léxico inteiro.

Se as duas curvas subirem juntas, H é falsa: o sistema só funciona porque é
pequeno, não porque é contextual. Aí não há paradigma nenhum, e é melhor saber.

Como se mede
────────────
Léxico sintético determinístico com N símbolos. Cada consulta é uma superfície
conhecida com ruído de digitação. Dois regimes idênticos, exceto pelo contexto:

    amplo   — todos os N símbolos são admissíveis  (o regime do Transformer)
    estreito— 7 símbolos são admissíveis           (o regime do HEMOS)

Mede-se latência por consulta, taxa de acerto, taxa de rejeição e — o que
importa de verdade — ERRO CONFIANTE: responder outro símbolo com confiança.
"""

from __future__ import annotations

import random
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import lexico as lx
import resolvedor as rv

SEMENTE = 20260729
TAMANHOS = (50, 200, 1_000, 5_000, 20_000)
CONSULTAS = 400
CONTEXTO_ESTREITO = 7

VERDE, AMAR, VERM, CINZA, NEG, N = (
    "\033[92m", "\033[93m", "\033[91m", "\033[90m", "\033[1m", "\033[0m")

SILABAS = ("ba", "be", "bi", "ca", "co", "da", "de", "fa", "fe", "gi", "go",
           "la", "le", "li", "ma", "me", "mi", "na", "ne", "no", "pa", "pe",
           "ra", "re", "ri", "sa", "se", "so", "ta", "te", "to", "va", "vi")


def palavra(rng: random.Random) -> str:
    return "".join(rng.choice(SILABAS) for _ in range(rng.randint(2, 4)))


def gerar_lexico(n: int, rng: random.Random) -> list[lx.Simbolo]:
    """N símbolos sintéticos, cada um com 3 a 6 superfícies de 1 a 3 palavras.

    Pseudo-palavras, não português: o objetivo é medir a ESTRUTURA do problema
    (quantos candidatos disputam uma consulta), sem que frequência de uso ou
    morfologia do português enviesem o resultado.
    """
    simbolos = []
    for i in range(n):
        sups = tuple(
            " ".join(palavra(rng) for _ in range(rng.randint(1, 3)))
            for _ in range(rng.randint(3, 6))
        )
        simbolos.append(lx.Simbolo(0x8000 + i, f"SYN_{i}", sups, f"syn{i}"))
    return simbolos


def ruidar(texto: str, rng: random.Random) -> str:
    """Ruído de digitação realista: troca, remoção, duplicação, caixa."""
    if rng.random() < 0.35:
        return texto
    chars = list(texto)
    for _ in range(rng.randint(1, 2)):
        if not chars:
            break
        i = rng.randrange(len(chars))
        op = rng.random()
        if op < 0.4 and len(chars) > 3:
            del chars[i]
        elif op < 0.7:
            chars.insert(i, chars[i])
        else:
            chars[i] = rng.choice("abcdefghijklmnopqrstuvwxyz")
    return "".join(chars)


def medir(simbolos: list[lx.Simbolo], contexto_tam: int | None,
          rng: random.Random) -> dict:
    """Roda CONSULTAS resoluções e devolve as métricas do regime."""
    por_id = {s.id: s for s in simbolos}
    todos = set(por_id)
    acertos = rejeicoes = erros = 0
    tempos: list[float] = []

    # Troca o léxico ativo (e seus índices) pelo sintético.
    original = lx.CATALOGO
    lx.reindexar(tuple(simbolos))
    try:
        for _ in range(CONSULTAS):
            alvo = rng.choice(simbolos)
            texto = ruidar(rng.choice(alvo.superficies), rng)
            if contexto_tam is None:
                ctx = todos
            else:
                outros = rng.sample(list(todos - {alvo.id}),
                                    min(contexto_tam - 1, len(todos) - 1))
                ctx = set(outros) | {alvo.id}
            t0 = time.perf_counter()
            r = rv.resolver(texto, ctx, None)
            tempos.append((time.perf_counter() - t0) * 1000)
            if not r.entendeu:
                rejeicoes += 1
            elif r.id == alvo.id:
                acertos += 1
            else:
                erros += 1
    finally:
        lx.reindexar(original)

    return {
        "acerto": 100 * acertos / CONSULTAS,
        "rejeicao": 100 * rejeicoes / CONSULTAS,
        "erro": 100 * erros / CONSULTAS,
        "ms": statistics.median(tempos),
        "ms_p95": sorted(tempos)[int(0.95 * len(tempos))],
    }


def main() -> int:
    print(f"\n{NEG}HEMOS — experimento de escala{N}")
    print(f"{CINZA}H: o que limita um resolvedor discreto não é |Σ|, "
          f"é |Σ_contexto|.{N}")
    print(f"{CINZA}{CONSULTAS} consultas por ponto, com ruído de digitação. "
          f"Léxico sintético determinístico.{N}\n")

    print(f"  {'':>8} │ {'CONTEXTO ESTREITO (7)':^38} │ "
          f"{'CONTEXTO AMPLO (todo o léxico)':^38}")
    print(f"  {'|Σ|':>8} │ {'acerto':>7} {'rejeit':>7} {'erro':>6} "
          f"{'mediana':>8} {'p95':>7} │ {'acerto':>7} {'rejeit':>7} {'erro':>6} "
          f"{'mediana':>8} {'p95':>7}")
    print(f"  {'─'*8}─┼─{'─'*38}─┼─{'─'*38}")

    linhas = []
    for n in TAMANHOS:
        rng = random.Random(SEMENTE + n)
        simbolos = gerar_lexico(n, rng)
        estreito = medir(simbolos, CONTEXTO_ESTREITO, random.Random(SEMENTE))
        amplo = medir(simbolos, None, random.Random(SEMENTE))
        linhas.append((n, estreito, amplo))

        def cor_erro(v):
            return f"{VERDE if v == 0 else VERM}{v:5.1f}%{N}"

        print(f"  {n:>8} │ {estreito['acerto']:6.1f}% {estreito['rejeicao']:6.1f}% "
              f"{cor_erro(estreito['erro'])} {estreito['ms']:7.2f}ms "
              f"{estreito['ms_p95']:6.2f}ms │ "
              f"{amplo['acerto']:6.1f}% {amplo['rejeicao']:6.1f}% "
              f"{cor_erro(amplo['erro'])} {amplo['ms']:7.2f}ms "
              f"{amplo['ms_p95']:6.2f}ms")

    # ── veredito ────────────────────────────────────────────────────────────
    print()
    p, u = linhas[0], linhas[-1]
    fator_lat_estreito = u[1]["ms"] / max(p[1]["ms"], 1e-9)
    fator_lat_amplo = u[2]["ms"] / max(p[2]["ms"], 1e-9)
    delta_rej_estreito = u[1]["rejeicao"] - p[1]["rejeicao"]
    delta_rej_amplo = u[2]["rejeicao"] - p[2]["rejeicao"]
    fator_lexico = TAMANHOS[-1] / TAMANHOS[0]

    print(f"{NEG}  Crescendo o léxico {fator_lexico:.0f}× "
          f"({TAMANHOS[0]} → {TAMANHOS[-1]} símbolos):{N}")
    print(f"    contexto estreito: latência ×{fator_lat_estreito:.1f}, "
          f"rejeição {delta_rej_estreito:+.1f} pontos")
    print(f"    contexto amplo:    latência ×{fator_lat_amplo:.1f}, "
          f"rejeição {delta_rej_amplo:+.1f} pontos")

    erros_estreito = sum(1 for _, e, _ in linhas if e["erro"] > 0)
    erros_amplo = sum(1 for _, _, a in linhas if a["erro"] > 0)
    print(f"    erro confiante: {erros_estreito}/{len(linhas)} pontos no "
          f"estreito, {erros_amplo}/{len(linhas)} no amplo")

    print()
    sustentada = (fator_lat_estreito < fator_lat_amplo / 3
                  and delta_rej_estreito < delta_rej_amplo)
    if sustentada:
        print(f"  {VERDE}H SUSTENTADA{N} — o custo segue |Σ_contexto|, não |Σ|. "
              f"O léxico pode crescer\n  sem que a conversa fique mais cara ou "
              f"mais ambígua, DESDE QUE o estado\n  saiba restringir o que é "
              f"admissível agora.")
    else:
        print(f"  {VERM}H REFUTADA{N} — as duas curvas sobem juntas. O sistema "
              f"funciona por ser\n  pequeno, não por ser contextual. Não há "
              f"princípio a generalizar aqui.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
