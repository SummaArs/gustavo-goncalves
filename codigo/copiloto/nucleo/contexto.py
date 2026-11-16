"""O que o copiloto sabe sobre "aqui e agora".

Separado de propósito: `Contexto` é um dado inerte (dataclass) que os testes
constroem à mão, e `capturar()` é a única parte que toca o disco. Assim o núcleo
de decisão continua puro e testável sozinho.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
import unicodedata
from dataclasses import dataclass, field

# Builtins do zsh que não aparecem no PATH mas são comandos válidos.
BUILTINS = frozenset("""
cd pwd echo print printf export unset alias unalias source . eval exec exit
set setopt unsetopt bindkey zle autoload typeset local declare integer float
read let test true false jobs fg bg kill wait disown pushd popd dirs hash
history fc which whence type command builtin functions unfunction trap emulate
compinit compdef zstyle zmodload zparseopts getopts shift return break continue
if then else elif fi for while until do done case esac function time ulimit
umask limit sched zcompile suspend log noglob nocorrect repeat select
""".split())

CACHE_PATH = os.path.expanduser("~/.copiloto/vocabulario.json")
CACHE_TTL = 86400  # o PATH muda pouco; reler a cada comando custaria ~50 ms


def normalizar(texto: str) -> str:
    """Achata o que o humano erra sem querer: acento, caixa, hífen, sublinhado.

    É essa normalização que faz `teste_g` encontrar `teste-gustavo-...`:
    ambos viram `testeg` / `testegustavo...`, e aí um é prefixo do outro.
    """
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return "".join(c for c in texto.casefold() if c.isalnum())


@dataclass
class Contexto:
    cwd: str = "/"
    itens: tuple[str, ...] = ()          # nomes na pasta atual (sem ocultos)
    pastas: frozenset[str] = frozenset()  # quais desses itens são pastas
    scripts: tuple[str, ...] = ()         # scripts do package.json / Makefile
    git_ramo: str | None = None
    git_sujo: bool = False
    comandos: frozenset[str] = frozenset()   # executáveis do PATH + builtins
    aliases: frozenset[str] = frozenset()
    ultimo_comando: str = ""
    ultimo_codigo: int = 0
    _digest: str = field(default="", repr=False)

    def existe(self, nome: str) -> bool:
        return nome in self.itens

    def conhece(self, comando: str) -> bool:
        return comando in self.comandos or comando in self.aliases \
            or comando in BUILTINS

    def digest(self) -> str:
        """Impressão digital do contexto — chave do cache."""
        if not self._digest:
            cru = self.cwd + "|" + "\x00".join(sorted(self.itens))
            object.__setattr__(self, "_digest",
                               hashlib.sha256(cru.encode()).hexdigest()[:16])
        return self._digest


def _vocabulario() -> frozenset[str]:
    """Todos os executáveis alcançáveis, com cache em disco de 24 h."""
    try:
        with open(CACHE_PATH, encoding="utf-8") as f:
            dados = json.load(f)
        if dados.get("path") == os.environ.get("PATH") \
                and time.time() - dados["ts"] < CACHE_TTL:
            return frozenset(dados["comandos"])
    except (OSError, ValueError, KeyError):
        pass

    nomes: set[str] = set()
    for pasta in os.environ.get("PATH", "").split(os.pathsep):
        try:
            with os.scandir(pasta) as it:
                for e in it:
                    if not e.name.startswith(".") and os.access(e.path, os.X_OK):
                        nomes.add(e.name)
        except OSError:
            continue
    try:
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        tmp = CACHE_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"ts": time.time(), "path": os.environ.get("PATH"),
                       "comandos": sorted(nomes)}, f)
        os.replace(tmp, CACHE_PATH)   # troca atômica: nunca deixa cache torto
    except OSError:
        pass
    return frozenset(nomes)


def _git(cwd: str) -> tuple[str | None, bool]:
    if not shutil.which("git"):
        return None, False
    import subprocess
    try:
        r = subprocess.run(["git", "status", "--porcelain=v1", "--branch"],
                           cwd=cwd, capture_output=True, text=True, timeout=1.5)
        if r.returncode != 0:
            return None, False
        linhas = r.stdout.splitlines()
        ramo = None
        if linhas and linhas[0].startswith("##"):
            ramo = linhas[0][3:].split("...")[0].strip()
        return ramo, any(not l.startswith("##") for l in linhas)
    except (OSError, subprocess.SubprocessError):
        return None, False


def _scripts(cwd: str) -> tuple[str, ...]:
    achados: list[str] = []
    pj = os.path.join(cwd, "package.json")
    if os.path.exists(pj):
        try:
            with open(pj, encoding="utf-8") as f:
                achados += ["npm run " + s for s in json.load(f).get("scripts", {})]
        except (OSError, ValueError):
            pass
    mk = os.path.join(cwd, "Makefile")
    if os.path.exists(mk):
        try:
            with open(mk, encoding="utf-8") as f:
                for linha in f:
                    if ":" in linha and not linha[0].isspace() \
                            and not linha.startswith((".", "#")):
                        alvo = linha.split(":", 1)[0].strip()
                        if alvo and " " not in alvo:
                            achados.append("make " + alvo)
        except OSError:
            pass
    return tuple(achados[:25])


def capturar(cwd: str | None = None) -> Contexto:
    cwd = cwd or os.getcwd()
    try:
        entradas = sorted(os.scandir(cwd), key=lambda e: e.name)
    except OSError:
        entradas = []
    itens, pastas = [], set()
    for e in entradas:
        if e.name.startswith("."):
            continue                      # oculto não entra: nem no prompt da IA
        itens.append(e.name)
        try:
            if e.is_dir():
                pastas.add(e.name)
        except OSError:
            pass
    ramo, sujo = _git(cwd)
    aliases = frozenset(
        a for a in os.environ.get("COPILOTO_ALIASES", "").split() if a)
    return Contexto(
        cwd=cwd, itens=tuple(itens[:120]), pastas=frozenset(pastas),
        scripts=_scripts(cwd), git_ramo=ramo, git_sujo=sujo,
        comandos=_vocabulario(), aliases=aliases,
        ultimo_comando=os.environ.get("COPILOTO_ULTIMO", ""),
        ultimo_codigo=int(os.environ.get("COPILOTO_CODIGO") or 0),
    )
