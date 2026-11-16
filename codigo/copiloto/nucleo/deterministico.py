"""Camada 1 — a MATEMÁTICA. Função pura, sem I/O, sem modelo, ~1 ms.

Antes de acordar uma IA de 2 GB, resolve o que é conta: distância de edição
entre o que você digitou e os nomes que realmente existem. É essa camada que
conserta `cd teste_g` -> `cd projeto-teste` sem consultar nada.

Porta de confiança (Lei 5): abaixo do limiar ela **não chuta** — devolve nada e
deixa a camada neural tentar. Ferramenta que chuta é pior que ferramenta burra.
"""
from __future__ import annotations

import difflib
import re
import shlex
from dataclasses import dataclass

from .contexto import BUILTINS, Contexto, normalizar

LIMIAR = 0.86        # abaixo disso, escala para a IA
LIMIAR_COMANDO = 0.80  # nome de programa erra mais e é mais fácil de conferir


@dataclass(frozen=True)
class Candidato:
    comando: str
    confianca: float
    camada: str
    motivo: str


# Pedidos curtos que não merecem um modelo de linguagem.
INTENCOES: tuple[tuple[str, str], ...] = (
    ("voltar", "cd .."), ("subir", "cd .."), ("volta", "cd .."),
    ("raiz", "cd /"), ("casa", "cd ~"), ("home", "cd ~"),
    ("ondeestou", "pwd"), ("quepastaeessa", "pwd"), ("pastaatual", "pwd"),
    ("limpar", "clear"), ("limpatela", "clear"), ("limparatela", "clear"),
    ("listar", "ls -lah"), ("listartudo", "ls -lah"),
    ("oqueteaqui", "ls -lah"), ("oquetemaqui", "ls -lah"),
    ("ultimopedido", "fc -ln -1"),
    ("quantoespaco", "df -h ."), ("espacoemdisco", "df -h"),
    ("tamanhodapasta", "du -sh ."),
    ("statusdogit", "git status"), ("gitstatus", "git status"),
    ("oquemudei", "git status"), ("oquemudou", "git diff"),
    ("ramoatual", "git branch --show-current"),
    ("ultimocommit", "git log -1 --stat"),
    ("historico", "git log --oneline -20"),
    ("quemestanaporta", "lsof -nP -iTCP -sTCP:LISTEN"),
    ("meuip", "ipconfig getifaddr en0"),
    ("processospesados", "ps aux | sort -nrk 3 | head -10"),
)
_INTENCOES = {normalizar(k): v for k, v in INTENCOES}

_FLAG = re.compile(r"^-{1,2}[a-zA-Z0-9]")


def _parecido(alvo: str, candidatos, limiar: float) -> list[tuple[str, float]]:
    """Ranqueia candidatos por semelhança do nome NORMALIZADO.

    Duas medidas, e vale a maior:
      1. prefixo — `testeg` é prefixo de `testegustavosidecar...` (0,95)
      2. razão de sequência — cobre letra trocada, faltando ou sobrando
    """
    n_alvo = normalizar(alvo)
    if not n_alvo:
        return []
    achados: list[tuple[str, float]] = []
    for c in candidatos:
        n_c = normalizar(c)
        if not n_c:
            continue
        if n_c == n_alvo:
            achados.append((c, 1.0))
            continue
        razao = difflib.SequenceMatcher(None, n_alvo, n_c).ratio()
        if n_c.startswith(n_alvo):
            # quanto mais do nome o prefixo cobre, mais confiança
            razao = max(razao, 0.90 + 0.05 * (len(n_alvo) / len(n_c)))
        elif n_alvo in n_c:
            razao = max(razao, 0.88)
        if razao >= limiar:
            achados.append((c, round(razao, 4)))
    achados.sort(key=lambda x: (-x[1], len(x[0])))
    return achados


def _citar(nome: str) -> str:
    return shlex.quote(nome) if re.search(r"[\s'\"$`\\*?()\[\]{}]", nome) else nome


def _partir(linha: str) -> list[str] | None:
    try:
        partes = shlex.split(linha, posix=True)
    except ValueError:
        return None                     # aspas abertas: não é hora de adivinhar
    return partes or None


def resolver(pedido: str, ctx: Contexto) -> list[Candidato]:
    """-> candidatos ordenados por confiança (pode vir vazio)."""
    pedido = (pedido or "").strip()
    if not pedido:
        return []

    chave = normalizar(pedido)
    if chave in _INTENCOES:
        return [Candidato(_INTENCOES[chave], 1.0, "regra", "intenção conhecida")]

    partes = _partir(pedido)
    if partes is None:
        return []
    programa, argumentos = partes[0], partes[1:]

    # Frase em português não é comando quebrado: nem tenta, manda pra IA.
    if len(partes) > 3 and not ctx.conhece(programa):
        return []

    saida: list[Candidato] = []
    motivos: list[str] = []
    confianca = 1.0
    prog_final = programa

    if not ctx.conhece(programa):
        vizinhos = _parecido(programa, set(ctx.comandos) | set(ctx.aliases)
                             | BUILTINS, LIMIAR_COMANDO)
        if not vizinhos:
            return []                   # não sei o programa: falha fechado
        prog_final, conf = vizinhos[0]
        confianca = min(confianca, conf)
        motivos.append(f"programa {programa!r} -> {prog_final!r}")

    # Agora os argumentos que parecem caminho.
    alternativas: list[list[str]] = [[]]
    n = len(argumentos)
    i = 0

    def _passa(arg: str) -> bool:
        """Token que não é para consertar: opção, caminho, curinga, variável."""
        return bool(_FLAG.match(arg)) or arg.startswith(("$", "~", "/", "|", ">")) \
            or "/" in arg or "*" in arg or not arg.rstrip("/")

    while i < n:
        if _passa(argumentos[i]) or ctx.existe(argumentos[i].rstrip("/")):
            for a in alternativas:
                a.append(argumentos[i])
            i += 1
            continue

        universo = ctx.pastas if prog_final == "cd" else ctx.itens
        # Até onde pode ir uma frase: enquanto os tokens forem "consertáveis".
        fim = i
        while fim < n and not _passa(argumentos[fim]) \
                and not ctx.existe(argumentos[fim].rstrip("/")):
            fim += 1
        # Frase mais LONGA primeiro — é assim que `relatorio final.pdf` volta
        # como um único nome, em vez de casar duas vezes com o mesmo arquivo.
        vizinhos, consumidos = [], 1
        for j in range(fim, i, -1):
            trecho = " ".join(argumentos[i:j]).rstrip("/")
            achados = _parecido(trecho, universo, LIMIAR)
            if achados:
                vizinhos, consumidos = achados, j - i
                break
        if not vizinhos:
            return []                   # caminho que não existe e não parece nada
        alvo = " ".join(argumentos[i:i + consumidos])
        confianca = min(confianca, vizinhos[0][1])
        motivos.append(f"{alvo!r} -> {vizinhos[0][0]!r}")
        if len(vizinhos) > 1:
            # ambiguidade real: vira alternativa (Ctrl+G de novo cicla)
            novas: list[list[str]] = []
            for a in alternativas:
                for nome, _ in vizinhos[:3]:
                    novas.append(a + [_citar(nome)])
            alternativas = novas
            confianca = min(confianca, 0.90)
        else:
            for a in alternativas:
                a.append(_citar(vizinhos[0][0]))
        i += consumidos

    if not motivos:
        # Nada a consertar: o que você digitou já é válido. Não piora.
        return [Candidato(pedido, 1.0, "regra", "já era um comando válido")]

    for args in alternativas:
        saida.append(Candidato(" ".join([prog_final, *args]).strip(),
                               confianca, "matemática", "; ".join(motivos)))
    return [c for c in saida if c.confianca >= LIMIAR]
