#!/usr/bin/env python3
"""Copiloto de terminal — cascata local, sem nuvem, só biblioteca padrão.

    camada 0  cache        ~1 ms    pedido idêntico, mesmo contexto
    camada 1  matemática   ~2 ms    distância de edição contra o que existe
    camada 2  neural      ~900 ms   Ollama local, só quando as contas não bastam
    ─────────────────────────────────────────────────────────────────
    verificação  SEMPRE            forma + programa existe + zsh -n + guarda

Nunca executa nada: escreve a linha no seu prompt e para. Quem aperta Enter é
você — e se a linha for destrutiva, ela chega comentada.

    copiloto.py sugerir  -- "entrar na pasta do sidecar"
    copiloto.py explicar -- "find . -name '*.py' -mtime -1"
    copiloto.py aprender -- "listar pdfs" "ls -1 *.pdf"
    copiloto.py diario | diag
"""
from __future__ import annotations

import os
import sys
import time
from typing import Callable

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from nucleo import contexto as ctxmod          # noqa: E402
from nucleo import deterministico, guarda, memoria, motor, validador  # noqa: E402

TENTATIVAS_IA = 3


def decidir(pedido: str, ctx: ctxmod.Contexto, alt: int = 0,
            evitar: tuple[str, ...] = (),
            motor_fn: Callable[..., str] | None = None,
            usar_cache: bool = True) -> tuple[str, str, str, str]:
    """O coração. -> (linha_final, camada, risco, motivo).

    `motor_fn` é injetável de fora justamente para o arnês poder alimentar
    saídas hostis de modelo e provar que nada escapa da verificação.
    """
    pedido = (pedido or "").strip()
    if not pedido:
        return "", "nenhuma", guarda.REVISAR, "pedido vazio"

    k = memoria.chave(pedido, ctx.digest(), alt)
    if usar_cache and not evitar:
        achado = memoria.ler_cache(k)
        if achado:
            linha, risco, motivo = guarda.blindar(achado[0])
            if linha:
                return linha, "cache", risco, motivo

    # ── camada 1: matemática ────────────────────────────────────────────
    candidatos = [c for c in deterministico.resolver(pedido, ctx)
                  if c.comando not in evitar]
    if candidatos:
        escolhido = candidatos[min(alt, len(candidatos) - 1)]
        linha, risco, motivo = guarda.blindar(escolhido.comando)
        ok, porque = validador.validar(linha, ctx)
        if linha and ok:
            if usar_cache and not evitar:
                memoria.gravar_cache(k, escolhido.comando, escolhido.camada)
            return (linha, escolhido.camada, risco,
                    f"{escolhido.motivo} (conf. {escolhido.confianca:.2f})")

    # ── camada 2: neural, com o motivo da reprovação realimentado ───────
    fn = motor_fn or motor.sugerir
    erro, evitados = "", list(evitar)
    for tentativa in range(TENTATIVAS_IA):
        bruto = fn(pedido, ctx, tuple(evitados), erro, tentativa)
        linha, risco, motivo = guarda.blindar(bruto)
        if not linha:
            erro = "não veio comando aproveitável"
            continue
        ok, porque = validador.validar(linha, ctx)
        if ok:
            if usar_cache and not evitar and risco == guarda.SEGURO:
                memoria.gravar_cache(k, linha, "neural")
            return linha, "neural", risco, motivo
        erro = porque
        cru = linha[len(guarda.MARCA):] if linha.startswith(guarda.MARCA) else linha
        evitados.append(cru)

    return "", "nenhuma", guarda.REVISAR, erro or "sem sugestão confiável"


# ───────────────────────────── interface ────────────────────────────────

def _argumentos(argv: list[str]) -> tuple[str, list[str], dict[str, str]]:
    modo = argv[1] if len(argv) > 1 else "sugerir"
    opcoes: dict[str, str] = {}
    resto: list[str] = []
    i = 2
    while i < len(argv):
        a = argv[i]
        if a == "--":
            resto = argv[i + 1:]
            break
        if a.startswith("--"):
            nome = a[2:]
            if i + 1 < len(argv) and not argv[i + 1].startswith("--"):
                opcoes[nome] = argv[i + 1]
                i += 1
            else:
                opcoes[nome] = "1"
        else:
            resto.append(a)
        i += 1
    return modo, resto, opcoes


def main(argv: list[str]) -> int:
    modo, resto, opcoes = _argumentos(argv)

    if modo == "diario":
        print(memoria.relatorio())
        return 0

    if modo == "diag":
        ctx = ctxmod.capturar()
        print(f"pasta          {ctx.cwd}")
        print(f"itens          {len(ctx.itens)} (pastas: {len(ctx.pastas)})")
        print(f"vocabulário    {len(ctx.comandos)} programas no PATH")
        print(f"aliases        {len(ctx.aliases)}")
        print(f"git            {ctx.git_ramo or '—'}")
        print(f"ollama porta   {'aberta' if motor.porta_aberta() else 'fechada'}")
        print(f"modelo         {motor.MODELO}")
        print(f"banco          {memoria.BANCO}")
        ok, porque = validador.sintaxe_ok("echo teste")
        print(f"linter zsh -n  {'ok' if ok else porque}")
        return 0

    if modo == "aprender":
        if len(resto) >= 2:
            memoria.aprender(resto[0], " ".join(resto[1:]), os.getcwd())
        return 0

    if modo == "aceito":
        if resto:
            memoria.marcar_aceito(" ".join(resto))
            memoria.aprender(opcoes.get("pedido", ""), " ".join(resto), os.getcwd())
        return 0

    pedido = " ".join(resto).strip() or sys.stdin.read().strip()
    if not pedido:
        return 1
    ctx = ctxmod.capturar()

    if modo == "explicar":
        print(motor.explicar(pedido, ctx))
        return 0

    inicio = time.monotonic()
    evitar = tuple(x for x in opcoes.get("evitar", "").split("\x1f") if x)
    linha, camada, risco, motivo = decidir(
        pedido, ctx, alt=int(opcoes.get("alt", 0) or 0), evitar=evitar)
    ms = int((time.monotonic() - inicio) * 1000)
    memoria.registrar(pedido, camada, linha, risco, motivo, ms)

    if opcoes.get("tag"):        # o widget mostra isto em cinza, acima do prompt
        print(f"{camada}·{ms}ms·{risco.lower()}·{motivo}"[:110], file=sys.stderr)
    if not linha:
        return 1
    print(linha)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
