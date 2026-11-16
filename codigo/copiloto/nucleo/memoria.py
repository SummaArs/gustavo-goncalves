"""Cache, corpus e diário — em SQLite, sem dependência externa.

Três papéis distintos, de propósito:
  cache   — pedido idêntico no mesmo contexto responde em ~1 ms (camada 0)
  corpus  — o que VOCÊ aceitou vira exemplo para as próximas sugestões (Lei 5)
  diario  — uma linha por decisão, COM a razão. Sem isso não há melhoria (Lei 7)
"""
from __future__ import annotations

import hashlib
import os
import sqlite3
import time
from contextlib import closing

RAIZ = os.path.expanduser("~/.copiloto")
BANCO = os.path.join(RAIZ, "copiloto.db")

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS cache (
  chave TEXT PRIMARY KEY, comando TEXT NOT NULL,
  camada TEXT, criado_em REAL NOT NULL);
CREATE TABLE IF NOT EXISTS corpus (
  pedido TEXT NOT NULL, comando TEXT NOT NULL, pasta TEXT,
  usos INTEGER NOT NULL DEFAULT 1, visto_em REAL NOT NULL,
  PRIMARY KEY (pedido, comando));
CREATE TABLE IF NOT EXISTS diario (
  ts REAL NOT NULL, pedido TEXT, camada TEXT, comando TEXT,
  risco TEXT, motivo TEXT, ms INTEGER, aceito INTEGER DEFAULT 0);
CREATE INDEX IF NOT EXISTS idx_diario_ts ON diario(ts);
"""
TTL_CACHE = 3600.0     # a pasta muda; uma hora é generoso e seguro


def _conectar() -> sqlite3.Connection:
    os.makedirs(RAIZ, exist_ok=True)
    con = sqlite3.connect(BANCO, timeout=3.0)
    con.execute("PRAGMA journal_mode=WAL")   # não travar entre abas do terminal
    con.executescript(_ESQUEMA)
    return con


def chave(pedido: str, digest_ctx: str, alt: int = 0) -> str:
    cru = f"{pedido}\x00{digest_ctx}\x00{alt}"
    return hashlib.sha256(cru.encode()).hexdigest()


def ler_cache(k: str) -> tuple[str, str] | None:
    try:
        with closing(_conectar()) as con:
            r = con.execute(
                "SELECT comando, camada, criado_em FROM cache WHERE chave=?",
                (k,)).fetchone()
    except sqlite3.Error:
        return None
    if not r or time.time() - r[2] > TTL_CACHE:
        return None
    return r[0], r[1]


def gravar_cache(k: str, comando: str, camada: str) -> None:
    try:
        with closing(_conectar()) as con, con:
            con.execute("INSERT OR REPLACE INTO cache VALUES (?,?,?,?)",
                        (k, comando, camada, time.time()))
    except sqlite3.Error:
        pass


def aprender(pedido: str, comando: str, pasta: str = "") -> None:
    """Idempotente: aprender o mesmo par duas vezes só incrementa o contador."""
    if not pedido.strip() or not comando.strip():
        return
    try:
        with closing(_conectar()) as con, con:
            con.execute(
                "INSERT INTO corpus (pedido, comando, pasta, usos, visto_em) "
                "VALUES (?,?,?,1,?) ON CONFLICT(pedido, comando) DO UPDATE SET "
                "usos = usos + 1, visto_em = excluded.visto_em",
                (pedido.strip(), comando.strip(), pasta, time.time()))
    except sqlite3.Error:
        pass


def _fichas(texto: str) -> set[str]:
    return {p for p in "".join(
        c if c.isalnum() else " " for c in texto.casefold()).split() if len(p) > 2}


def exemplos(pedido: str, limite: int = 3) -> list[tuple[str, str]]:
    """Vizinhos mais próximos por sobreposição de palavras (Jaccard).

    Barato e suficiente: são poucos milhares de linhas, e o que importa é
    lembrar do jargão da SUA casa (`oon-prove`, `npm run ooncore:docs`).
    """
    alvo = _fichas(pedido)
    if not alvo:
        return []
    try:
        with closing(_conectar()) as con:
            linhas = con.execute(
                "SELECT pedido, comando, usos FROM corpus "
                "ORDER BY visto_em DESC LIMIT 400").fetchall()
    except sqlite3.Error:
        return []
    pontuados = []
    for p, c, usos in linhas:
        f = _fichas(p)
        if not f:
            continue
        jaccard = len(alvo & f) / len(alvo | f)
        if jaccard > 0.12:
            pontuados.append((jaccard + 0.01 * min(usos, 10), p, c))
    pontuados.sort(reverse=True)
    return [(p, c) for _, p, c in pontuados[:limite]]


def registrar(pedido: str, camada: str, comando: str, risco: str,
              motivo: str, ms: int) -> None:
    try:
        with closing(_conectar()) as con, con:
            con.execute("INSERT INTO diario "
                        "(ts,pedido,camada,comando,risco,motivo,ms) "
                        "VALUES (?,?,?,?,?,?,?)",
                        (time.time(), pedido, camada, comando, risco, motivo, ms))
    except sqlite3.Error:
        pass


def marcar_aceito(comando: str) -> None:
    try:
        with closing(_conectar()) as con, con:
            con.execute("UPDATE diario SET aceito=1 WHERE rowid = ("
                        "SELECT rowid FROM diario WHERE comando=? "
                        "ORDER BY ts DESC LIMIT 1)", (comando,))
    except sqlite3.Error:
        pass


def relatorio() -> str:
    """O entregável é a prova (Lei 7): o copiloto se mede em público."""
    try:
        with closing(_conectar()) as con:
            total, aceitos = con.execute(
                "SELECT COUNT(*), COALESCE(SUM(aceito),0) FROM diario").fetchone()
            por_camada = con.execute(
                "SELECT camada, COUNT(*), CAST(AVG(ms) AS INT), "
                "MAX(ms) FROM diario GROUP BY camada ORDER BY 2 DESC").fetchall()
            corpus, = con.execute("SELECT COUNT(*) FROM corpus").fetchone()
            riscos = con.execute("SELECT COUNT(*) FROM diario "
                                 "WHERE risco='REVISAR'").fetchone()[0]
    except sqlite3.Error as e:
        return f"diário indisponível: {e}"
    if not total:
        return "Diário vazio — use Ctrl+G algumas vezes e volte."
    linhas = [f"Sugestões: {total}   aceitas e executadas: {aceitos} "
              f"({100 * aceitos / total:.0f}%)",
              f"Bloqueadas como REVISAR: {riscos}   "
              f"Exemplos aprendidos: {corpus}", "",
              f"{'camada':<14}{'usos':>6}{'média ms':>10}{'pior ms':>9}"]
    for camada, n, media, pior in por_camada:
        linhas.append(f"{camada or '?':<14}{n:>6}{media or 0:>10}{pior or 0:>9}")
    return "\n".join(linhas)
