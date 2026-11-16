#!/usr/bin/env python3
"""Servidor local. Nada sai desta maquina: bind em 127.0.0.1, arquivos
processados em memoria, so as suas decisoes vao para disco (~/.conciliador).
"""
from __future__ import annotations

import base64
import csv
import io
import json
import mimetypes
import os
import sys
import threading
from datetime import date
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

from nucleo.dinheiro import fichas, reais
from nucleo.livro import Livro, caixas
from nucleo.montagem import identificar, montar_lancamentos, montar_titulos
from nucleo.motor import Config, gerar_candidatos, resolver
from nucleo.rotulos import pares_internos, rotular
from nucleo.simulador import gerar

TETO_UPLOAD = 48 * 1024 * 1024


class Sessao:
    def __init__(self):
        self.trava = threading.RLock()
        self.zerar()

    def zerar(self):
        self.lancs, self.tits, self.cands = [], [], []
        self.res = None
        self.cfg = Config()
        self.livro = Livro("padrao")
        self.fontes = {}

    # ------------------------------------------------------------ carga
    def carregar(self, arquivos, caixa="padrao"):
        with self.trava:
            self.livro = Livro(caixa)
            lancs, tits, fontes = [], [], {}
            pendentes = []
            for a in arquivos:
                bytes_ = base64.b64decode(a["dados"])
                if len(bytes_) > TETO_UPLOAD:
                    raise ValueError(f"{a['nome']}: arquivo acima de 48 MB")
                papel = a.get("papel") or identificar(a["nome"], bytes_)[0]
                pendentes.append((a["nome"], bytes_, papel))
            if len({p for _, _, p in pendentes}) == 1 and len(pendentes) == 2:
                # os dois foram lidos como a mesma coisa: o de confianca menor cede
                notas = [(identificar(n, b)[1], i) for i, (n, b, _) in enumerate(pendentes)]
                pior = min(notas)[1]
                atual = pendentes[pior][2]
                outro = "titulos" if atual == "extrato" else "extrato"
                pendentes[pior] = (*pendentes[pior][:2], outro)
            for nome, bytes_, papel in pendentes:
                if papel == "extrato":
                    itens, meta = montar_lancamentos(nome, bytes_)
                    lancs += itens
                else:
                    itens, meta = montar_titulos(nome, bytes_)
                    tits += itens
                fontes[nome] = {"papel": papel, **meta}
            self.lancs, self.tits, self.fontes = lancs, tits, fontes
            self.recalcular(regerar=True)
            return self.instantaneo()

    def exemplo(self, semente=7, n=45):
        with self.trava:
            self.livro = Livro("exemplo")
            self.lancs, self.tits, _ = gerar(semente, n)
            self.fontes = {
                "extrato_exemplo.ofx": {"papel": "extrato", "formato": "OFX",
                                        "linhas": len(self.lancs), "colunas": {}},
                "titulos_exemplo.csv": {"papel": "titulos", "formato": "tabela",
                                        "linhas": len(self.tits), "colunas": {}},
            }
            self.recalcular(regerar=True)
            return self.instantaneo()

    # ------------------------------------------------------------ motor
    def recalcular(self, regerar=False):
        with self.trava:
            est = self.livro.estado()
            if regerar or not self.cands:
                self.cands, self.lancs, self.tits = gerar_candidatos(
                    self.lancs, self.tits, self.cfg
                )
            self.res = resolver(self.cands, self.lancs, self.tits, self.cfg,
                                excluidos=est["travados"], rejeitados=est["rejeitados"])
            return self.res

    def decidir(self, vinculo, acao):
        with self.trava:
            todos = {c.iid: c for c in (self.res.certos + self.res.sugestoes)}
            c = todos.get(vinculo)
            if not c:
                return {"ok": False, "erro": "vínculo não está mais em aberto"}
            if acao == "aprovar":
                self.livro.registrar("aprovado", vinculo=c.iid, lanc=list(c.lanc),
                                     tits=list(c.tits), escore=round(c.escore, 4),
                                     dif=c.dif, forma=c.forma,
                                     motivos=list(c.motivos), caixa=self.livro.caixa)
            else:
                self.livro.registrar("rejeitado", vinculo=c.iid, lanc=list(c.lanc),
                                     tits=list(c.tits))
            self.recalcular()
            return {"ok": True, **self.instantaneo()}

    def aprovar_tudo(self):
        with self.trava:
            n = 0
            for c in list(self.res.certos):
                self.livro.registrar("aprovado", vinculo=c.iid, lanc=list(c.lanc),
                                     tits=list(c.tits), escore=round(c.escore, 4),
                                     dif=c.dif, forma=c.forma,
                                     motivos=list(c.motivos), caixa=self.livro.caixa)
                n += 1
            self.recalcular()
            return {"ok": True, "confirmados": n, **self.instantaneo()}

    def desfazer(self, vinculo):
        with self.trava:
            self.livro.registrar("rejeitado", vinculo=vinculo)
            self.recalcular()
            return {"ok": True, **self.instantaneo()}

    def rotular_sobra(self, chave, rotulo):
        with self.trava:
            self.livro.registrar("rotulo", chave=chave, rotulo=rotulo)
            return {"ok": True, **self.instantaneo()}

    def ajustar(self, campos):
        with self.trava:
            for k, v in campos.items():
                if hasattr(self.cfg, k):
                    atual = getattr(self.cfg, k)
                    setattr(self.cfg, k, type(atual)(v))
            self.recalcular(regerar=True)
            return {"ok": True, **self.instantaneo()}

    # ------------------------------------------------------------ visao
    def instantaneo(self):
        with self.trava:
            if self.res is None:
                return {"vazio": True, "caixas": caixas()}
            est = self.livro.estado()
            L = {l.iid: l for l in self.lancs}
            T = {t.iid: t for t in self.tits}
            aprovados = []
            for ev in est["aprovados"].values():
                aprovados.append({
                    "id": ev["vinculo"],
                    "forma": ev.get("forma", ""),
                    "motivos": ev.get("motivos", []),
                    "escore": ev.get("escore", 0),
                    "lanc": [_vl(L[x]) for x in ev.get("lanc", []) if x in L],
                    "tits": [_vt(T[y]) for y in ev.get("tits", []) if y in T],
                })
            aprovados.sort(key=lambda a: (a["lanc"][0]["data"] if a["lanc"] else "", a["id"]))
            internos = dict()
            for a, b in pares_internos(self.res.lanc_sobra):
                internos[a] = internos[b] = True
            sobras = []
            for l in self.res.lanc_sobra:
                rot, origem = rotular(l.descricao, est["rotulos"], l.cent)
                if l.iid in internos and origem == "aberto":
                    rot, origem = "Movimentação interna", "par +/-"
                sobras.append({**_vl(l), "rotulo": rot, "origem": origem,
                               "chave": " ".join(sorted(fichas(l.descricao)))})
            m = dict(self.res.metricas)
            m["aprovados"] = len(aprovados)
            m["valor_aprovado_cent"] = sum(
                abs(x["cent"]) for a in aprovados for x in a["lanc"])
            m["total_lanc_original"] = len(self.lancs)
            m["total_tit_original"] = len(self.tits)
            return {
                "vazio": False,
                "caixa": self.livro.caixa,
                "caixas": caixas(),
                "fontes": self.fontes,
                "metricas": m,
                "cfg": self.cfg.__dict__,
                "certos": [_vv(c, L, T) for c in self.res.certos],
                "fila": [_vv(c, L, T) for c in self.res.sugestoes],
                "aprovados": aprovados,
                "sobras": sobras,
                "abertos": [_vt(t) for t in sorted(
                    self.res.tit_sobra, key=lambda t: (str(t.data_ref), t.iid))],
                "duplicados": [[a, b] for a, b in self.res.duplicados],
            }


def _dt(d):
    return d.isoformat() if hasattr(d, "isoformat") else (str(d) if d else "")


def _vl(l):
    return {"id": l.iid, "data": _dt(l.data), "cent": l.cent, "valor": reais(l.cent),
            "desc": l.descricao, "doc": str(l.documento or ""), "linha": l.linha}


def _vt(t):
    return {"id": t.iid, "tipo": t.tipo or "?", "venc": _dt(t.vencimento),
            "data": _dt(t.data), "cent": t.cent, "valor": reais(t.cent),
            "parte": t.contraparte, "doc": str(t.documento or ""),
            "cat": t.categoria, "linha": t.linha}


def _vv(c, L, T):
    return {"id": c.iid, "escore": round(c.escore, 4), "forma": c.forma,
            "dif": c.dif, "dif_txt": reais(c.dif) if c.dif else "",
            "motivos": list(c.motivos), "rivais": c.rivais,
            "confianca": c.confianca,
            "lanc": [_vl(L[x]) for x in c.lanc if x in L],
            "tits": [_vt(T[y]) for y in c.tits if y in T]}


SESSAO = Sessao()


# ---------------------------------------------------------------- exportar

def exportar(tipo: str) -> tuple[str, str]:
    s = SESSAO.instantaneo()
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    hoje = date.today().isoformat()
    if tipo == "conciliado":
        w.writerow(["situacao", "data_extrato", "valor_extrato", "descricao_extrato",
                    "documento_extrato", "titulo_contraparte", "titulo_tipo",
                    "titulo_documento", "titulo_vencimento", "titulo_valor",
                    "titulo_categoria", "forma", "por_que", "confianca"])
        for grupo, situacao in ((s["aprovados"], "conciliado"),
                                (s["certos"], "conciliado (aguardando confirmacao)")):
            for v in grupo:
                for i in range(max(len(v["lanc"]), len(v["tits"]))):
                    l = v["lanc"][i] if i < len(v["lanc"]) else {}
                    t = v["tits"][i] if i < len(v["tits"]) else {}
                    w.writerow([situacao, l.get("data", ""), l.get("valor", ""),
                                l.get("desc", ""), l.get("doc", ""), t.get("parte", ""),
                                t.get("tipo", ""), t.get("doc", ""), t.get("venc", ""),
                                t.get("valor", ""), t.get("cat", ""), v["forma"],
                                " + ".join(v["motivos"]),
                                f"{round(v.get('escore', 0) * 100)}%"])
        return f"conciliado_{hoje}.csv", buf.getvalue()
    if tipo == "pendencias":
        w.writerow(["tipo_pendencia", "data", "valor", "descricao_ou_contraparte",
                    "documento", "classificacao", "acao_sugerida"])
        for v in s["fila"]:
            l = v["lanc"][0] if v["lanc"] else {}
            t = v["tits"][0] if v["tits"] else {}
            w.writerow(["decidir", l.get("data", ""), l.get("valor", ""),
                        f"{l.get('desc','')} <-> {t.get('parte','')}",
                        t.get("doc", ""), " + ".join(v["motivos"]),
                        f"confirmar vinculo {v['forma']} ({round(v['escore']*100)}%)"])
        for l in s["sobras"]:
            w.writerow(["extrato sem titulo", l["data"], l["valor"], l["desc"],
                        l["doc"], l["rotulo"],
                        "lancar no ERP" if l["rotulo"] == "Sem classificação"
                        else f"classificar como {l['rotulo']}"])
        for t in s["abertos"]:
            w.writerow(["titulo sem pagamento", t["venc"] or t["data"], t["valor"],
                        t["parte"], t["doc"], t["tipo"],
                        "cobrar / verificar se foi pago fora do periodo"])
        return f"pendencias_{hoje}.csv", buf.getvalue()
    raise ValueError("tipo desconhecido")


# ---------------------------------------------------------------- http

class Alca(BaseHTTPRequestHandler):
    server_version = "Conciliador"

    def log_message(self, *a):
        pass

    def _envia(self, corpo: bytes, tipo="application/json; charset=utf-8", extra=None):
        self.send_response(200)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(corpo)

    def _json(self, obj, codigo=200):
        corpo = json.dumps(obj, ensure_ascii=False, default=str).encode()
        if codigo != 200:
            self.send_response(codigo)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)
            return
        self._envia(corpo)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path in ("/", "/index.html"):
            html = (AQUI / "web" / "interface.html").read_bytes()
            return self._envia(html, "text/html; charset=utf-8")
        if u.path == "/api/estado":
            return self._json(SESSAO.instantaneo())
        if u.path.startswith("/api/exportar/"):
            try:
                nome, corpo = exportar(u.path.rsplit("/", 1)[1].replace(".csv", ""))
            except Exception as e:
                return self._json({"erro": str(e)}, 400)
            return self._envia(
                "﻿".encode() + corpo.encode("utf-8"),
                "text/csv; charset=utf-8",
                {"Content-Disposition": f'attachment; filename="{nome}"'},
            )
        return self._json({"erro": "rota inexistente"}, 404)

    def do_POST(self):
        u = urlparse(self.path)
        n = int(self.headers.get("Content-Length") or 0)
        if n > TETO_UPLOAD * 2:
            return self._json({"erro": "envio muito grande"}, 413)
        try:
            corpo = json.loads(self.rfile.read(n) or b"{}")
        except json.JSONDecodeError:
            return self._json({"erro": "json inválido"}, 400)
        try:
            if u.path == "/api/carregar":
                return self._json(SESSAO.carregar(corpo["arquivos"],
                                                  corpo.get("caixa", "padrao")))
            if u.path == "/api/exemplo":
                return self._json(SESSAO.exemplo(int(corpo.get("semente", 7)),
                                                 int(corpo.get("n", 45))))
            if u.path == "/api/decidir":
                return self._json(SESSAO.decidir(corpo["vinculo"], corpo["acao"]))
            if u.path == "/api/aprovar-tudo":
                return self._json(SESSAO.aprovar_tudo())
            if u.path == "/api/desfazer":
                return self._json(SESSAO.desfazer(corpo["vinculo"]))
            if u.path == "/api/rotular":
                return self._json(SESSAO.rotular_sobra(corpo["chave"], corpo["rotulo"]))
            if u.path == "/api/ajustar":
                return self._json(SESSAO.ajustar(corpo.get("cfg", {})))
        except Exception as e:
            import traceback
            traceback.print_exc()
            return self._json({"erro": f"{type(e).__name__}: {e}"}, 400)
        return self._json({"erro": "rota inexistente"}, 404)


def servir(porta=8777, abrir=True):
    srv = ThreadingHTTPServer(("127.0.0.1", porta), Alca)
    url = f"http://127.0.0.1:{porta}"
    print(f"\n  Conciliador no ar em {url}")
    print("  (Ctrl+C para encerrar)\n")
    if abrir:
        try:
            import webbrowser
            threading.Timer(0.6, lambda: webbrowser.open(url)).start()
        except Exception:
            pass
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n  encerrado.")


if __name__ == "__main__":
    args = dict(a.lstrip("-").split("=") for a in sys.argv[1:] if "=" in a)
    servir(int(args.get("porta", os.environ.get("PORTA", 8777))),
           abrir="nao-abrir" not in " ".join(sys.argv))
