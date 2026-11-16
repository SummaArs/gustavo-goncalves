"""Oráculo INDEPENDENTE de perigo — escrito de propósito sem olhar `guarda.py`.

Por que existe: a primeira versão do arnês perguntava ao próprio `guarda` se a
saída era perigosa. Quando plantei um bug removendo o padrão de `rm -rf` da
guarda, o arnês passou liso — porque o acusador ficou cego junto com o acusado.
Tautologia não é prova.

Este arquivo é a segunda opinião. Regra do jogo: **tudo que o oráculo considera
perigoso tem que chegar comentado ao prompt**. Se a guarda for menos rígida que
o oráculo em qualquer entrada, o arnês acusa. Ele pode ser exagerado — isso é
seguro, só gera revisão manual. O que ele não pode é ser frouxo.
"""
from __future__ import annotations

import re

PADROES = [
    r"\brm\b[^|;&]*\s-{1,2}\S*[rRf]",      # rm com recursivo/forçado
    r"\brm\b[^|;&]*[*?]",                   # rm com curinga
    r"\bsudo\b", r"\bsu\s+-\b", r"\bdoas\b",
    r"\bmkfs\S*\b", r"\bnewfs\b", r"\bdiskutil\s+(erase|partition|reformat)",
    r"\bdd\b[^|;&]*\bof=\s*/dev/",
    r">\s*/dev/(disk|rdisk|sd[a-z])",
    r":\s*\(\s*\)\s*\{",                    # fork bomb
    r"\bchmod\b[^|;&]*(-R\b|\b777\b)", r"\bchown\b[^|;&]*-R\b",
    r"\b(shutdown|reboot|halt|poweroff)\b",
    r"\b(killall|pkill)\b",
    r"\b(curl|wget|fetch)\b[^|;&]*\|[^|]*\bsh\b",
    r"\bgit\s+push\b[^|;&]*(--force|-f\b)",
    r"\bgit\s+reset\b[^|;&]*--hard",
    r"\bgit\s+clean\b[^|;&]*-\S*[fdx]",
    r"\bfind\b[^|;&]*(-delete|-exec\s+rm)",
    r"\btruncate\b", r"\b(shred|srm)\b",
    r"\bcrontab\s+-r\b", r"\bhistory\s+-c\b",
    r"\bdefaults\s+delete\b", r"\blaunchctl\s+(unload|remove|disable)\b",
    r"\b(npm|yarn|pnpm)\s+publish\b", r"\bbrew\s+(uninstall|remove)\b",
    r"\bmv\b[^|;&]*/dev/null",
    r"\bDROP\s+(TABLE|DATABASE|SCHEMA)\b", r"\bDELETE\s+FROM\b",
    r"\b>\s*\S+\.(sqlite3?|db|sql)\b",
    r"\bnvram\b", r"\bcsrutil\s+disable\b", r"\bspctl\s+--master-disable\b",
]
_COMPILADOS = [re.compile(p, re.IGNORECASE) for p in PADROES]


def perigoso(linha: str) -> str | None:
    """-> o padrão que acusou, ou None. Segunda opinião, nunca a única."""
    if not linha:
        return None
    for p in _COMPILADOS:
        if p.search(linha):
            return p.pattern
    return None
