"""Camada 2 — o NEURAL. Só interpreta; nunca decide sozinho.

Tudo que sai daqui é tratado como texto hostil e passa por `guarda` e
`validador`. Se o modelo cair, o copiloto fica burro (cai na camada 1), nunca
errado — é a regra "LLM não é o último elo".
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import time
import urllib.error
import urllib.request

from . import memoria
from .contexto import Contexto

HOST = os.environ.get("COPILOTO_HOST", "127.0.0.1")
PORTA = int(os.environ.get("COPILOTO_PORTA", "11434"))
MODELO = os.environ.get("COPILOTO_MODELO", "llama3.2:3b")
URL = f"http://{HOST}:{PORTA}/api/generate"
TETO_PROMPT = 7000     # I12: prompt gigante trava o modelo e come RAM


def porta_aberta(espera: float = 0.4) -> bool:
    with socket.socket() as s:
        s.settimeout(espera)
        return s.connect_ex((HOST, PORTA)) == 0


def garantir_servidor(limite: float = 25.0) -> bool:
    """Sobe `ollama serve` sozinho na primeira vez do dia."""
    if porta_aberta():
        return True
    exe = next((p for p in ("/opt/homebrew/bin/ollama", "/usr/local/bin/ollama")
                if os.path.exists(p)), None)
    if not exe:
        return False
    try:
        os.makedirs(memoria.RAIZ, exist_ok=True)
        with open(os.path.join(memoria.RAIZ, "ollama.log"), "ab") as log:
            subprocess.Popen([exe, "serve"], stdout=log, stderr=log,
                             stdin=subprocess.DEVNULL, start_new_session=True)
    except OSError:
        return False
    fim = time.monotonic() + limite
    while time.monotonic() < fim:
        time.sleep(0.4)
        if porta_aberta():
            return True
    return False


REGRAS = """Você é um copiloto de terminal no macOS (zsh). Traduza o pedido em UM comando.

Regras absolutas:
- Responda SÓ o comando, uma linha. Sem explicação, sem markdown, sem crase, sem "$".
- Use exatamente os nomes de arquivos e pastas listados no contexto. Nunca invente nome.
- Nunca use molde tipo <arquivo> ou /caminho/para. Se falta informação, use o que existe.
- Prefira ferramentas nativas do macOS/BSD (ls, find, grep, sed, awk, du, lsof, git).
- Se o pedido já é um comando com erro de digitação, devolva a versão corrigida.
- Se for impossível com o que há aqui, responda exatamente: echo "não sei"
"""


EXEMPLOS_BASE: tuple[tuple[str, str], ...] = (
    ("quantos arquivos python tem aqui contando as subpastas",
     "find . -name '*.py' | wc -l"),
    ("as 5 maiores pastas daqui", "du -sh */ | sort -rh | head -5"),
    ("quem está usando a porta 3000", "lsof -nP -iTCP:3000 -sTCP:LISTEN"),
    ("arquivos mexidos nas últimas 24 horas", "find . -type f -mtime -1"),
    ("procurar a palavra senha dentro dos arquivos", "grep -rn 'senha' ."),
    ("processos que mais gastam memória", "ps aux | sort -nrk 4 | head -10"),
    ("o que eu mudei no git", "git diff --stat"),
    ("quanto espaço livre tem no disco", "df -h /"),
    ("arquivos maiores que 10 mega", "find . -type f -size +10M"),
    ("matar o processo que está na porta 8080",
     "lsof -nP -iTCP:8080 -sTCP:LISTEN -t | xargs kill"),
)


def montar_prompt(pedido: str, ctx: Contexto, evitar: tuple[str, ...] = (),
                  erro: str = "") -> str:
    """Contexto só com NOMES — nunca conteúdo de arquivo (invariante I9)."""
    partes = [REGRAS, "", f"Pasta atual: {ctx.cwd}"]
    if ctx.itens:
        partes.append("Itens da pasta (pasta marcada com /): " + ", ".join(
            n + "/" if n in ctx.pastas else n for n in ctx.itens[:60]))
    if ctx.scripts:
        partes.append("Comandos de projeto disponíveis: " + ", ".join(ctx.scripts))
    if ctx.git_ramo:
        partes.append(f"Git: ramo {ctx.git_ramo}"
                      + (" com alterações não commitadas" if ctx.git_sujo else " limpo"))
    if ctx.ultimo_comando and ctx.ultimo_codigo:
        partes.append(f"Último comando falhou (código {ctx.ultimo_codigo}): "
                      f"{ctx.ultimo_comando}")

    # Âncoras: um modelo de 3B sabe shell, mas erra a FORMA da resposta. Estes
    # exemplos custam ~400 bytes de prompt e consertaram casos que ele errava
    # (ele respondia `du -h | grep python` para "quantos arquivos python").
    partes.append("\nExemplos de referência:")
    for p, c in EXEMPLOS_BASE:
        partes.append(f"Pedido: {p}\nComando: {c}")

    exemplos = memoria.exemplos(pedido)
    if exemplos:
        # Depois das âncoras, porque o que ESTE usuário aprovou vale mais.
        partes.append("\nExemplos que este usuário já aprovou:")
        for p, c in exemplos:
            partes.append(f"Pedido: {p}\nComando: {c}")
    if evitar:
        partes.append("\nNÃO repita estes comandos: " + " | ".join(evitar[:4]))
    if erro:
        partes.append(f"\nSua tentativa anterior foi REPROVADA porque: {erro}. "
                      "Corrija exatamente isso.")
    partes.append(f"\nPedido: {pedido}\nComando:")
    prompt = "\n".join(partes)
    return prompt if len(prompt) <= TETO_PROMPT else prompt[-TETO_PROMPT:]


def _chamar(prompt: str, temperatura: float, teto_tokens: int,
            espera: float) -> str:
    corpo = json.dumps({
        "model": MODELO, "prompt": prompt, "stream": False,
        "keep_alive": "30m",
        "options": {"temperature": temperatura, "num_predict": teto_tokens,
                    "top_p": 0.9, "stop": ["\n\n", "Pedido:", "```"]},
    }).encode()
    req = urllib.request.Request(URL, data=corpo,
                                headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=espera) as r:
            return json.loads(r.read()).get("response", "") or ""
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        return ""


def sugerir(pedido: str, ctx: Contexto, evitar: tuple[str, ...] = (),
            erro: str = "", tentativa: int = 0, espera: float = 45.0) -> str:
    if not garantir_servidor():
        return ""
    temperatura = 0.1 if tentativa == 0 and not evitar else 0.45
    return _chamar(montar_prompt(pedido, ctx, evitar, erro),
                   temperatura, 120, espera)


def explicar(comando: str, ctx: Contexto, espera: float = 45.0) -> str:
    if not garantir_servidor():
        return "IA local fora do ar."
    prompt = (
        "Explique em português do Brasil, para quem está aprendendo terminal, o "
        "que este comando faz. Máximo 3 linhas curtas. Diga o que cada opção "
        "significa e avise se é destrutivo. Não repita o comando.\n\n"
        f"Pasta atual: {ctx.cwd}\nComando: {comando}\nExplicação:")
    return _chamar(prompt, 0.2, 220, espera).strip()
