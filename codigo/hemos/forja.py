"""
HEMOS — Forja: pré-treinamento sem pesos.

    python3 forja.py            processa o destilado e mostra o relatório
    python3 forja.py --gravar   grava o léxico destilado em disco

O problema que ela resolve
──────────────────────────
O aprendiz (aprendiz.py) só aprende com tráfego real. Ótimo, mas significa que
o sistema NASCE BURRO e leva meses de operação para entender como as pessoas
falam. A forja resolve isso: um LLM roda UMA VEZ, na bancada, e despeja o
vocabulário do domínio; o crivo filtra; o que sobra é um arquivo de texto.

Produção continua sem LLM nenhum — offline, determinística, token zero.

Quem é quem
───────────
    LLM ......... gerador. Falível, criativo, caro, roda uma vez.
    crivo ....... seletor. Determinístico, barato, roda sempre.
    médico ...... homologa o que o crivo marcou como controverso.

A alucinação não é um problema a evitar, é ruído a filtrar. Se o modelo inventa
um sinônimo errado, o teste de regressão barra; se inventa um radical
arriscado, ele nasce marcado como controverso e não entra sozinho. O gerador
pode errar porque ele não decide nada.

A trava que não se negocia
──────────────────────────
O LLM ensina o sistema a FALAR, nunca a DECIDIR. Não existe caminho neste
arquivo que escreva em normas.py — nenhuma carência, nenhum critério clínico.
testes/teste_forja.py prova que normas.CARENCIA sai idêntico ao que entrou.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "testes"))

import aprendiz as ap
import lexico as lx
import ontologia as ont
import resolvedor as rv
from conhecimento import destilado as dst

VERDE, AMARELO, VERMELHO, CINZA, RESET = (
    "\033[92m", "\033[93m", "\033[91m", "\033[90m", "\033[0m")


def corpus_referencia():
    """Corpus contra o qual toda promoção é testada por regressão."""
    from teste_nucleo import CORPUS
    return CORPUS


def processar(verboso: bool = True):
    """Aplica o crivo a todo o destilado. Determinístico e reprodutível."""
    corpus = corpus_referencia()
    a = ap.Aprendiz(arquivo=Path(__file__).parent / "lexico_destilado.json")

    aceitos: list[tuple[str, int, str]] = []
    barrados: list[tuple[str, int, str]] = []
    revisao: list[tuple[str, str, str]] = []

    # ── vocabulário ─────────────────────────────────────────────────────────
    for nome_simbolo, formas in sorted(dst.PARAFRASES.items()):
        alvo = lx.POR_NOME[nome_simbolo].id
        for forma, confianca in formas:
            if confianca == "controversa":
                revisao.append((forma, nome_simbolo, "confiança controversa"))
                continue
            ok, motivo = a.avaliar_candidato(forma, alvo, corpus)
            if ok:
                a.incorporar(forma, alvo)
                aceitos.append((forma, alvo, confianca))
            else:
                barrados.append((forma, alvo, motivo))

    # ── expressões de tempo vagas -> NAO_SEI ────────────────────────────────
    # Achado da destilação: metade de como se fala de tempo em português não
    # tem data determinável. Chutar uma data aqui seria inventar informação
    # clínica; o certo é virar lacuna.
    for forma in dst.TEMPO_VAGO:
        ok, motivo = a.avaliar_candidato(forma, lx.NAO_SEI, corpus)
        if ok:
            a.incorporar(forma, lx.NAO_SEI)
            aceitos.append((forma, lx.NAO_SEI, "alta"))
        else:
            barrados.append((forma, lx.NAO_SEI, motivo))

    # ── ontologia ───────────────────────────────────────────────────────────
    radicais_novos = 0
    for nome_classe, radicais in sorted(dst.RADICAIS.items()):
        classe = next((c for c in ont.CLASSES if c.nome == nome_classe), None)
        if classe is None:
            revisao.append((nome_classe, "-", "classe inexistente na ontologia"))
            continue
        for radical, confianca in radicais:
            if confianca == "controversa":
                revisao.append((radical, nome_classe,
                                "divergência clínica real entre serviços"))
                continue
            if radical not in classe.radicais:
                ont.estender(classe, radical)
                radicais_novos += 1

    for nome, evento, radicais, justificativa in dst.CLASSES_PROPOSTAS:
        revisao.append((nome, evento,
                        f"classe NOVA com {len(radicais)} radicais — "
                        "requer homologação médica antes de entrar"))

    if verboso:
        _relatorio(aceitos, barrados, revisao, radicais_novos)
    return a, aceitos, barrados, revisao


def _relatorio(aceitos, barrados, revisao, radicais_novos) -> None:
    print(f"\033[1mHEMOS — forja (pré-treinamento sem pesos)\033[0m")
    print(f"{CINZA}gerador: {dst.__doc__.split('gerador ......')[1].splitlines()[0].strip()}"
          f" · o sistema em produção continua sem LLM{RESET}\n")

    total = len(aceitos) + len(barrados) + len(revisao)
    print(f"  candidatos processados ....... {total}")
    print(f"  {VERDE}aceitos pelo crivo ........... {len(aceitos)}{RESET}")
    print(f"  {VERMELHO}barrados ..................... {len(barrados)}{RESET}")
    print(f"  {AMARELO}para revisão médica .......... {len(revisao)}{RESET}")
    print(f"  radicais novos na ontologia .. {radicais_novos}")

    if barrados:
        print(f"\n  {VERMELHO}barrados pelo crivo:{RESET}")
        for forma, alvo, motivo in barrados:
            print(f"    {VERMELHO}✗{RESET} {forma!r} → {lx.nome(alvo)}: {CINZA}{motivo}{RESET}")

    if revisao:
        print(f"\n  {AMARELO}fila do médico responsável:{RESET}")
        for item, onde, motivo in revisao:
            print(f"    {AMARELO}?{RESET} {item!r} ({onde}): {CINZA}{motivo}{RESET}")


def main() -> int:
    a, aceitos, barrados, revisao = processar()
    if "--gravar" in sys.argv:
        a.salvar()
        print(f"\n  {VERDE}léxico destilado gravado em {a.arquivo.name}{RESET}")
    print(f"\n{CINZA}  Rode ./prove.sh para verificar que nada disso quebrou "
          f"uma invariante.{RESET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
