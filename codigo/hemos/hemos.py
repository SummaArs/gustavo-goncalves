"""
HEMOS — CLI. Simula o WhatsApp no terminal e mostra o log semântico.

    python3 hemos.py                 conversa interativa
    python3 hemos.py --log           idem, mostrando o id de cada mensagem
    python3 hemos.py --demo          roda um roteiro pronto (não interativo)
    python3 hemos.py --hoje 2026-07-29   fixa a data (para testes reprodutíveis)

O canal é um adaptador fino: trocar este arquivo por um webhook da WhatsApp
Cloud API não toca em nenhuma linha de lexico/resolvedor/normas/conversa.
"""

from __future__ import annotations

import sys
from datetime import date, datetime

import lexico as lx
from conversa import Sessao
from aprendiz import carregar_conhecimento

FORMAS_EXTRAS = carregar_conhecimento()

CINZA, VERDE, AMARELO, RESET = "\033[90m", "\033[92m", "\033[93m", "\033[0m"

DEMO = [
    "oi, queria doar sangue",
    "22 de abril de 1979",   # nascimento
    "uns 68",                # peso
    "feminino",              # sexo biológico
    "12 de janeiro",         # última doação
    "uma",                   # doações em 12 meses
    "nunca",                 # gripe
    "faz uns 2 anos",        # covid
    "nunca", "nunca", "nunca", "nunca", "nunca", "nunca", "nunca",
    "mês passado",           # vacina comum
    "nunca", "nunca",
    "não lembro",            # álcool  -> vira LACUNA, não "nunca"
    "nunca", "nunca", "nunca", "nunca",
    "não", "não",            # gestante / amamentando
    "sim", "1",              # agendar, primeiro horário
]


def imprimir(msgs: list[str]) -> None:
    for m in msgs:
        print(f"{VERDE}🤖 {m}{RESET}\n")


def mostrar_log(s: Sessao, desde: int) -> None:
    for direcao, id_, valor in s.historico[desde:]:
        v = f" = {valor}" if valor is not None else ""
        print(f"{CINZA}   [{direcao}] {lx.nome(id_)} (0x{id_:04X}){v}{RESET}")


def main() -> int:
    args = sys.argv[1:]
    hoje = date.today()
    if "--hoje" in args:
        hoje = datetime.strptime(args[args.index("--hoje") + 1], "%Y-%m-%d").date()
    com_log = "--log" in args
    s = Sessao(hoje=hoje)

    print(f"{AMARELO}HEMOS — pré-triagem de doação de sangue "
          f"(simulador de canal). hoje = {hoje}{RESET}")
    print(f"{CINZA}Escreva como escreveria no WhatsApp. Ctrl-C para sair.{RESET}\n")

    if "--demo" in args:
        for entrada in DEMO:
            print(f"👤 {entrada}")
            n = len(s.historico)
            imprimir(s.passo(entrada))
            if com_log:
                mostrar_log(s, n)
            if s.estado == "FIM":
                break
        return 0

    while s.estado != "FIM":
        try:
            entrada = input("👤 ")
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        n = len(s.historico)
        imprimir(s.passo(entrada))
        if com_log:
            mostrar_log(s, n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
