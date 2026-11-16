"""A camada que GARANTE. Puro, sem I/O, sem modelo.

Premissa de projeto: **a saída do modelo é entrada hostil**. Não importa o que a
IA cuspir — texto com ANSI, três comandos grudados, `rm -rf /` com desculpa
educada — o que chega ao seu prompt sai daqui, e daqui só sai uma de duas
coisas: uma linha segura de rodar como está, ou uma linha comentada (que o
Enter ignora).
"""
from __future__ import annotations

import re

SEGURO, REVISAR = "SEGURO", "REVISAR"
MARCA = "# REVISE ANTES DE RODAR: "
LIMITE = 500          # comando maior que isso é alucinação, não comando

# Critério: PRESENÇA de token perigoso na linha, não sintaxe exata.
#
# A primeira versão casava a sintaxe certinha (`git clean -fdx`) e o arnês a
# furou em minutos jogando lixo no meio: `git clean -😀fdx`, `git reset.--hard`,
# `rm -ç\x00rf /`. Descrever a forma exata do perigo é jogo perdido — descrever
# o token e aceitar qualquer coisa entre eles não é. Cada padrão traz o motivo,
# porque log sem razão é palpite (Lei 7).
_M = r"[^|;&]*"       # "qualquer coisa dentro do mesmo comando da corrente"
PERIGOS: tuple[tuple[str, str], ...] = (
    # `rm` inteiro, sem exceção: arquivo perdido não volta, e o custo de errar
    # para o lado seguro é você apagar um `#`.
    (r"\brm\b", "remoção de arquivo"),
    (r"\b(sudo|doas)\b|\bsu\s+-", "privilégio de administrador"),
    (r"\bmkfs\S*|\bdiskutil" + _M + r"(erase|partition|reformat)|\bnewfs",
     "formatação de disco"),
    (r"\bnvram\b|\bcsrutil" + _M + r"disable|\bspctl" + _M + r"master-disable",
     "desliga proteção do sistema"),
    (r"\bdd\b" + _M + r"\bof=\s*/dev/", "escrita crua em dispositivo"),
    (r">\s*/dev/(disk|rdisk|sd[a-z])", "redirecionamento para disco"),
    (r":\s*\(\s*\)\s*\{", "fork bomb"),
    (r"\bchmod\b" + _M + r"(-R\b|777)|\bchown\b" + _M + r"-R\b",
     "permissão recursiva"),
    (r"\b(shutdown|reboot|halt|poweroff)\b", "desliga a máquina"),
    (r"\b(killall|pkill)\b", "mata processos em lote"),
    (r"\b(curl|wget|fetch)\b[^|]*\|" + r"[^|]*\bsh\b", "baixa e executa script"),
    # `-f` sem exigir espaço antes: o arnês passou `git push-f` por essa fresta.
    (r"\bgit\b" + _M + r"(\bclean\b|--hard|--force|-f\b|\bfilter-branch\b)",
     "git destrutivo"),
    (r"\bfind\b" + _M + r"(-delete|-exec\s+rm)", "apaga em varredura"),
    (r"\btruncate\b|>\s*\S+\.(sql|db|sqlite3?)\b", "trunca base de dados"),
    (r"\bcrontab" + _M + r"-r\b|\bdefaults" + _M + r"delete\b|"
     r"\blaunchctl" + _M + r"(unload|remove|disable)\b",
     "mexe em configuração do sistema"),
    (r"\bhistory" + _M + r"-c\b|>\s*~?/?\.z?sh_history", "apaga o histórico"),
    (r"\b(npm|pnpm|yarn)\b" + _M + r"\bpublish\b|\bbrew\b" + _M +
     r"\b(uninstall|remove)\b", "publica ou desinstala"),
    (r"\bmv\b" + _M + r"/dev/null", "move para o nada"),
    (r"\bDROP\s+(TABLE|DATABASE|SCHEMA)\b|\bDELETE\s+FROM\b", "SQL destrutivo"),
    (r"\b(shred|srm)\b", "apaga sem volta"),
)
_PERIGOS = tuple((re.compile(p, re.IGNORECASE), motivo) for p, motivo in PERIGOS)

# Sinais de que o modelo entregou molde em vez de comando.
_MOLDE = re.compile(r"<[a-zA-Z_ ]{2,}>|\{\{|\bSEU_|\bseu_arquivo\b|"
                    r"\bcaminho/para\b|/path/to/|\bnome_do_\b|\.\.\.$|\[opções\]")
_ANSI = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")


def sanitizar(bruto: str) -> str:
    """Texto qualquer -> uma linha de comando plausível, ou "".

    Não julga se é perigoso (isso é `classificar`); só garante forma: uma linha,
    sem cerca de markdown, sem ANSI, sem caractere de controle, sem molde.
    """
    if not isinstance(bruto, str):
        return ""
    texto = _ANSI.sub("", bruto).replace("\r", "\n")
    texto = re.sub(r"```[a-zA-Z]*", "\n", texto)      # cerca de markdown
    for linha in texto.split("\n"):
        # Descascar até PARAR de mudar: um passe só não é ponto fixo, e sem
        # ponto fixo `blindar(blindar(x)) != blindar(x)` (invariante I16).
        anterior = None
        while linha != anterior:
            anterior = linha
            linha = linha.strip().strip("`")
        linha = re.sub(r"^(\$|>|#+|\d+\.|[-*])\s+", "", linha)  # prompt/lista
        # tira caractere de controle, mantém só o que dá para digitar
        linha = "".join(c for c in linha if c == "\t" or ord(c) >= 32)
        linha = linha.strip()
        if not linha or linha.startswith("#"):
            continue
        if _MOLDE.search(linha):
            continue                       # molde não é comando: descarta
        if len(linha) > LIMITE:
            return ""                      # falha fechado (Lei 4)
        return linha
    return ""


def classificar(comando: str) -> tuple[str, str]:
    """-> (SEGURO|REVISAR, motivo). Em dúvida, REVISAR."""
    if not comando or not comando.strip():
        return REVISAR, "vazio"
    for padrao, motivo in _PERIGOS:
        if padrao.search(comando):
            return REVISAR, motivo
    if ";" in comando or "&&" in comando or "|" in comando:
        # encadeado não é proibido, mas merece um olho: só revisa se houver
        # qualquer verbo de escrita no meio da corrente.
        if re.search(r"\b(rm|mv|dd|tee|chmod|chown|kill)\b", comando):
            return REVISAR, "encadeado com escrita"
    return SEGURO, "sem padrão de risco"


def blindar(comando: str) -> tuple[str, str, str]:
    """Porta de saída ÚNICA do copiloto.

    -> (linha_final, risco, motivo). Se o risco é REVISAR, a linha volta
    comentada: apertar Enter não faz nada. Invariante I2 do arnês.
    """
    if isinstance(comando, str) and comando.startswith(MARCA):
        comando = comando[len(MARCA):]      # blindar(blindar(x)) == blindar(x)
    limpo = sanitizar(comando)
    if not limpo:
        return "", REVISAR, "nada aproveitável"
    risco, motivo = classificar(limpo)
    if risco == REVISAR:
        return MARCA + limpo, risco, motivo
    return limpo, risco, motivo
