"""Livro de eventos append-only. Nada e sobrescrito, nada e perdido.

Tres coisas ficam aqui, e as tres fazem o sistema melhorar de mes a mes:
  aprovado  -> ids travados: nao entram na conciliacao do mes seguinte
  rejeitado -> memoria negativa: esse par nunca mais e sugerido
  rotulo    -> voce classificou uma sobra; a proxima igual ja vem classificada
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

PASTA = Path(os.environ.get("CONCILIADOR_DADOS", Path.home() / ".conciliador"))


class Livro:
    def __init__(self, caixa: str = "padrao"):
        PASTA.mkdir(parents=True, exist_ok=True)
        self.caminho = PASTA / f"{_seguro(caixa)}.jsonl"
        self.caixa = caixa
        self._cache = None

    # ------------------------------------------------------------ escrita
    def registrar(self, acao: str, **dados) -> dict:
        ev = {"ts": round(time.time(), 3), "acao": acao, **dados}
        chave = ev.get("vinculo") or ev.get("chave")
        if chave and acao in ("aprovado", "rejeitado"):
            atual = self.estado()
            ja = atual["aprovados"] if acao == "aprovado" else atual["rejeitados"]
            if chave in ja:                       # idempotente: reaplicar nao duplica
                return {"ok": True, "repetido": True}
        with self.caminho.open("a", encoding="utf-8") as f:
            f.write(json.dumps(ev, ensure_ascii=False, default=str) + "\n")
        self._cache = None
        return {"ok": True}

    # ------------------------------------------------------------ leitura
    def eventos(self):
        if not self.caminho.exists():
            return []
        saida = []
        for linha in self.caminho.read_text(encoding="utf-8").splitlines():
            linha = linha.strip()
            if not linha:
                continue
            try:
                saida.append(json.loads(linha))
            except json.JSONDecodeError:
                continue
        return saida

    def estado(self) -> dict:
        if self._cache is not None:
            return self._cache
        est = {"aprovados": {}, "rejeitados": set(), "rotulos": {}, "travados": set()}
        for ev in self.eventos():
            a = ev.get("acao")
            if a == "aprovado":
                est["aprovados"][ev["vinculo"]] = ev
                est["travados"] |= set(ev.get("lanc", [])) | set(ev.get("tits", []))
                est["rejeitados"].discard(ev["vinculo"])
            elif a == "rejeitado":
                est["rejeitados"].add(ev["vinculo"])
                v = est["aprovados"].pop(ev["vinculo"], None)
                if v:                              # desfazer aprovacao
                    est["travados"] -= set(v.get("lanc", [])) | set(v.get("tits", []))
            elif a == "rotulo":
                est["rotulos"][ev["chave"]] = ev["rotulo"]
        est["travados"] = _recomputar_travados(est)
        self._cache = est
        return est


def _recomputar_travados(est) -> set:
    t = set()
    for v in est["aprovados"].values():
        t |= set(v.get("lanc", [])) | set(v.get("tits", []))
    return t


def _seguro(s: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in s)[:60] or "padrao"


def caixas() -> list[str]:
    if not PASTA.exists():
        return []
    return sorted(p.stem for p in PASTA.glob("*.jsonl"))
