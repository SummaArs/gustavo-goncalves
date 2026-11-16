"""
HEMOS — a forja é segura? (contenção de alucinação)

Usar um LLM como gerador só se sustenta se for IMPOSSÍVEL que o que ele
produziu contamine a decisão clínica. Aqui isso é medido, não prometido.

  F1  TRAVA DE NORMA — depois da forja, normas.CARENCIA sai byte a byte
      idêntico. O LLM ensina o sistema a falar, nunca a decidir.

  F2  CONTENÇÃO — nada que o gerador produziu passa sem crivo, e o crivo tem
      que barrar até o que o próprio gerador escreveu errado.

  F3  SEGURANÇA PÓS-FORJA — com o léxico destilado carregado, a busca
      adversarial inteira continua achando ZERO erros confiantes.

  F4  O CORPUS QUE O GERADOR ESCREVEU CONTRA SI MESMO — o LLM foi usado
      também para imaginar entradas difíceis (negação dupla, ironia, unidade
      trocada, tentativa de manipulação). O sistema tem que acertar ou
      rejeitar. Nunca errar com confiança.

  F5  GANHO — a forja tem que valer a pena: cobertura antes vs. depois.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import forja
import lexico as lx
import normas
import ontologia as ont
import resolvedor as rv
from conhecimento import destilado as dst
from teste_nucleo import CTX_BOOL, CTX_DATA, HOJE

falhas: list[str] = []
contagem = 0


def checa(cond: bool, rotulo: str) -> None:
    global contagem
    contagem += 1
    if not cond:
        falhas.append(rotulo)


def titulo(t: str) -> None:
    print(f"\n\033[1m{t}\033[0m")


CTX_PESO = {lx.VALOR_PESO, lx.NAO_SEI, lx.VOLTAR, lx.PARAR, lx.HUMANO}
CONTEXTOS = {"BOOL": CTX_BOOL, "DATA": CTX_DATA, "PESO": CTX_PESO}


def amostra_cobertura() -> list[tuple[str, str]]:
    """Toda forma do destilado, com seu contexto — para medir cobertura."""
    fora: list[tuple[str, str]] = []
    for nome, formas in dst.PARAFRASES.items():
        ctx = "BOOL" if nome in ("SIM", "NAO", "NAO_SEI") else "DATA"
        fora += [(f, ctx) for f, _ in formas]
    fora += [(f, "DATA") for f in dst.TEMPO_VAGO]
    return fora


def cobertura(amostra) -> float:
    n = sum(1 for t, c in amostra if rv.resolver(t, CONTEXTOS[c], HOJE).entendeu)
    return 100.0 * n / len(amostra)


def main() -> int:
    print("\033[1mHEMOS — contenção da forja\033[0m")

    amostra = amostra_cobertura()
    antes_cob = cobertura(amostra)
    carencia_antes = {k: (p.dias, p.fonte, p.homologado)
                      for k, p in normas.CARENCIA.items()}
    radicais_antes = ont.fecho_estimado()

    # ── roda a forja ────────────────────────────────────────────────────────
    titulo("F1/F2 — trava de norma e contenção")
    a, aceitos, barrados, revisao = forja.processar(verboso=False)

    carencia_depois = {k: (p.dias, p.fonte, p.homologado)
                       for k, p in normas.CARENCIA.items()}
    checa(carencia_antes == carencia_depois,
          "F1 a forja alterou normas.CARENCIA — o LLM tocou na decisão clínica")
    checa(all(not hasattr(p, "_forja") for p in normas.CARENCIA.values()),
          "F1 marcador de origem de LLM encontrado numa norma")
    print(f"  normas clínicas antes/depois: \033[92midênticas\033[0m "
          f"({len(carencia_antes)} parâmetros)")
    print(f"  candidatos: {len(aceitos)} aceitos | {len(barrados)} barrados | "
          f"{len(revisao)} para o médico")

    checa(len(barrados) > 0,
          "F2 o crivo não barrou NADA — ou o gerador foi perfeito (improvável) "
          "ou o crivo está desligado")
    for forma, alvo, motivo in barrados:
        print(f"    \033[91m✗\033[0m {forma!r} → {lx.nome(alvo)}: \033[90m{motivo}\033[0m")
    checa(any("negador" in m for _, _, m in barrados),
          "F2 o crivo deixou passar uma forma que inverteria polaridade")

    # nada marcado como controverso pode ter entrado sozinho
    controversos = {f for formas in dst.PARAFRASES.values()
                    for f, c in formas if c == "controversa"}
    controversos |= {r for rads in dst.RADICAIS.values()
                     for r, c in rads if c == "controversa"}
    entraram = {f for f, _, _ in aceitos} | {
        r for lst in ont.RADICAIS_EXTRA.values() for r in lst}
    checa(not (controversos & entraram),
          f"F2 item controverso entrou sem homologação: {controversos & entraram}")
    print(f"  itens controversos que entraram sozinhos: \033[92m0\033[0m "
          f"(de {len(controversos)})")

    # ── F3: busca adversarial com o léxico já destilado ─────────────────────
    titulo("F3 — busca adversarial COM o léxico destilado carregado")
    import adversario
    n, erros, rejeicoes, _ = adversario.a1_resolvedor(50000)
    checa(erros == 0, f"F3 pós-forja a busca achou {erros} erros confiantes")
    print(f"  {n} mutações | \033[{'91' if erros else '92'}m{erros} erros "
          f"confiantes\033[0m | {100*rejeicoes/n:.1f}% rejeitadas")

    # ── F4: o corpus que o gerador escreveu contra si mesmo ─────────────────
    titulo("F4 — entradas difíceis imaginadas pelo próprio gerador")
    acertos = recusas = erros_conf = 0
    for texto, ctx_nome, esperado in dst.ADVERSARIAL:
        r = rv.resolver(texto, CONTEXTOS[ctx_nome], HOJE)
        alvo = getattr(lx, esperado) if esperado else None
        if alvo is None:
            if r.entendeu:
                erros_conf += 1
                print(f"    \033[91m✗ {texto!r} ({ctx_nome}) deveria ser "
                      f"rejeitado, veio {lx.nome(r.id)}\033[0m")
            else:
                recusas += 1
        elif r.id == alvo:
            acertos += 1
        elif not r.entendeu:
            recusas += 1
            print(f"    \033[93m~ {texto!r} recusado (esperava "
                  f"{lx.nome(alvo)}) — seguro, mas é atrito\033[0m")
        else:
            erros_conf += 1
            print(f"    \033[91m✗ {texto!r} → {lx.nome(r.id)}, "
                  f"esperado {lx.nome(alvo)}\033[0m")
    checa(erros_conf == 0, f"F4 {erros_conf} erros confiantes no corpus do gerador")
    print(f"  {len(dst.ADVERSARIAL)} entradas | {acertos} acertos | "
          f"{recusas} recusas seguras | \033[{'91' if erros_conf else '92'}m"
          f"{erros_conf} erros confiantes\033[0m")

    # ── F5: valeu a pena? ───────────────────────────────────────────────────
    titulo("F5 — ganho do pré-treinamento")
    depois_cob = cobertura(amostra)
    checa(depois_cob > antes_cob, "F5 a forja não aumentou a cobertura")
    print(f"  cobertura do vocabulário real: {antes_cob:.0f}% → "
          f"\033[92m{depois_cob:.0f}%\033[0m ({len(amostra)} formas)")
    print(f"  radicais na ontologia: {radicais_antes} → "
          f"\033[92m{radicais_antes + sum(len(v) for v in ont.RADICAIS_EXTRA.values())}"
          f"\033[0m")
    print(f"  \033[90mtudo isso sem uma linha de peso: o artefato é "
          f"conhecimento/destilado.py, legível e removível\033[0m")

    print()
    if falhas:
        print(f"\033[91m✗ {len(falhas)} de {contagem} verificações falharam:\033[0m")
        for f in falhas:
            print(f"   - {f}")
        return 1
    print(f"\033[92m✓ {contagem} verificações, 0 violações\033[0m")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
