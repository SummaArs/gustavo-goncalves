"""Verificação — o pedaço pequeno que dá independência à ferramenta.

Nenhuma sugestão chega ao seu prompt sem passar por aqui:
  1. forma (pura, µs)
  2. o programa existe nesta máquina?  (mata a alucinação de ferramenta)
  3. o zsh consegue *analisar* a linha?  (`zsh -n` só analisa, nunca executa)

Se reprova, o motivo volta para o modelo e ele tenta de novo — é a diferença
entre um copiloto e um chute bonito.
"""
from __future__ import annotations

import re
import shutil
import subprocess

from .contexto import BUILTINS, Contexto

_SEPARADOR = re.compile(r"\|\||&&|[|;&]")
_ATRIBUICAO = re.compile(r"^[A-Za-z_][A-Za-z_0-9]*=")
_ENVOLTORIO = frozenset({"sudo", "env", "time", "nohup", "xargs", "command",
                         "builtin", "noglob", "nocorrect", "then", "do", "else"})


def programas(comando: str) -> list[str]:
    """Nomes de programa invocados na linha (um por segmento do pipeline)."""
    nomes: list[str] = []
    for segmento in _SEPARADOR.split(comando):
        for token in segmento.strip().split():
            if _ATRIBUICAO.match(token) or token.startswith(("-", "(", "!", "$")):
                continue
            if token in _ENVOLTORIO:
                continue
            nomes.append(token.strip("(){}"))
            break
    return nomes


def checagens_puras(comando: str, ctx: Contexto) -> tuple[bool, str]:
    if not comando or not comando.strip():
        return False, "vazio"
    if "\n" in comando:
        return False, "mais de uma linha"
    if comando.lstrip().startswith("#"):
        return True, "comentado (inofensivo)"
    desconhecidos = [p for p in programas(comando)
                     if not ctx.conhece(p) and p not in BUILTINS
                     and not p.startswith("./") and "/" not in p]
    if desconhecidos:
        return False, f"programa não existe nesta máquina: {desconhecidos[0]}"
    return True, "forma ok"


def sintaxe_ok(comando: str) -> tuple[bool, str]:
    """`zsh -n` analisa a gramática e sai. Não roda nada — é o linter do zsh."""
    zsh = shutil.which("zsh") or "/bin/zsh"
    try:
        r = subprocess.run([zsh, "-n", "-c", comando],
                           capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError) as e:
        return True, f"linter indisponível ({type(e).__name__})"  # não bloqueia
    if r.returncode == 0:
        return True, "sintaxe ok"
    erro = (r.stderr or "").strip().splitlines()
    return False, "sintaxe inválida: " + (erro[-1] if erro else "?")


def validar(comando: str, ctx: Contexto) -> tuple[bool, str]:
    ok, motivo = checagens_puras(comando, ctx)
    if not ok:
        return False, motivo
    if comando.lstrip().startswith("#"):
        return True, motivo
    return sintaxe_ok(comando)
