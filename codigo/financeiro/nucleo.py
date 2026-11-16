"""
nucleo.py — o financeiro (contas a receber/pagar + razão) como livro que só cresce.

Modelo estudado no Odoo 18 (addons/account): lançamento de partidas dobradas
(account.move/line), conciliação parcial (account.partial.reconcile) e
situação de pagamento derivada. Mudanças nossas, cada uma tapando um buraco de lá:

  * dinheiro é int de centavos — o Odoo soma float e arredonda no SQL;
  * nada se apaga nem volta a rascunho — correção é ESTORNO (o Odoo tem button_draft);
  * saldo em aberto e situação são DERIVADOS do livro a cada leitura — não há cópia
    guardada que possa divergir;
  * toda entrada tem chave de intenção: reenviar a mesma intenção é confirmação,
    não duplicata; mesma chave com conteúdo diferente é recusa;
  * cada linha do livro carrega o hash da anterior — adulteração no arquivo é detectada.

Estado = replay(eventos). Eventos: titulo, baixa, estorno, fechamento.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import date

BANCO = "1.1 Caixa e bancos"
CLIENTES = "1.2 Clientes a receber"
FORNECEDORES = "2.1 Fornecedores a pagar"


class Recusa(ValueError):
    """Entrada inválida na fronteira. O livro não muda."""


def _dia(s, campo):
    try:
        return date.fromisoformat(s).isoformat()
    except (TypeError, ValueError):
        raise Recusa(f"{campo}: data inválida ({s!r}), use AAAA-MM-DD")


def _centavos(v, campo):
    if type(v) is not int or v <= 0:
        raise Recusa(f"{campo}: valor deve ser inteiro de centavos > 0 ({v!r})")
    return v


def _texto(v, campo):
    if not isinstance(v, str) or not v.strip():
        raise Recusa(f"{campo}: obrigatório")
    return v.strip()


def _canon(o):
    return json.dumps(o, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


class Livro:
    def __init__(self, caminho=None):
        self.caminho = caminho
        self.eventos = []          # o que está no arquivo, na ordem
        self.por_chave = {}
        self._zerar()
        if caminho and os.path.exists(caminho):
            ant = ""
            with open(caminho, encoding="utf-8") as f:
                for n, linha in enumerate(f, 1):
                    e = json.loads(linha)
                    if e["ant"] != ant or e["hash"] != self._hash(e):
                        raise RuntimeError(f"livro adulterado na linha {n} — recuso abrir")
                    self._aplicar(e["tipo"], e["dados"], e["chave"])
                    self.eventos.append(e)
                    self.por_chave[e["chave"]] = e
                    ant = e["hash"]

    # ── escrita ──────────────────────────────────────────────────────────
    def registrar(self, tipo, dados, chave):
        """Única porta de escrita. Valida, aplica, grava. Idempotente por chave."""
        chave = _texto(chave, "chave")
        if not isinstance(dados, dict):
            raise Recusa("dados: objeto esperado")
        try:
            dados = json.loads(_canon(dados))      # cópia, só tipos JSON
        except (TypeError, ValueError):
            raise Recusa("dados: só texto, número inteiro e lista")
        if chave in self.por_chave:
            e = self.por_chave[chave]
            if e["tipo"] == tipo and e["dados"] == dados:
                return e["id"]                     # mesma intenção: confirmação
            raise Recusa("chave já usada por outro conteúdo")
        id_ = self._aplicar(tipo, dados, chave)    # levanta Recusa sem tocar no estado
        ant = self.eventos[-1]["hash"] if self.eventos else ""
        e = {"seq": len(self.eventos) + 1, "chave": chave, "tipo": tipo,
             "dados": dados, "id": id_, "ant": ant}
        e["hash"] = self._hash(e)
        if self.caminho:
            try:
                with open(self.caminho, "a", encoding="utf-8") as f:
                    f.write(_canon(e) + "\n")
                    f.flush()
                    os.fsync(f.fileno())
            except OSError:
                self.__init__(self.caminho)        # disco recusou: volta ao que está gravado
                raise
        self.eventos.append(e)
        self.por_chave[chave] = e
        return id_

    @staticmethod
    def _hash(e):
        corpo = {k: e[k] for k in ("seq", "chave", "tipo", "dados", "id", "ant")}
        return hashlib.sha256(_canon(corpo).encode()).hexdigest()

    # ── replay ───────────────────────────────────────────────────────────
    def _zerar(self):
        self.titulos = {}       # id -> dict
        self.baixas = {}        # id -> dict
        self.lancamentos = []   # partidas dobradas
        self.estornados = set()
        self.fechado_ate = ""   # data de fechamento ('' = aberto)

    def _aplicar(self, tipo, d, chave):
        if tipo == "titulo":
            return self._titulo(d)
        if tipo == "baixa":
            return self._baixa(d)
        if tipo == "estorno":
            return self._estorno(d)
        if tipo == "fechamento":
            data = _dia(d.get("data"), "data")
            if data <= self.fechado_ate:
                raise Recusa("fechamento só avança")
            self.fechado_ate = data
            return "F-" + data
        raise Recusa(f"tipo desconhecido: {tipo!r}")

    def _aberto(self, data):
        if data <= self.fechado_ate:
            raise Recusa(f"período fechado até {self.fechado_ate}")

    def _titulo(self, d):
        natureza = d.get("natureza")
        if natureza not in ("receber", "pagar"):
            raise Recusa("natureza: 'receber' ou 'pagar'")
        t = {"natureza": natureza,
             "contraparte": _texto(d.get("contraparte"), "contraparte"),
             "descricao": _texto(d.get("descricao"), "descricao"),
             "categoria": _texto(d.get("categoria"), "categoria"),
             "valor": _centavos(d.get("valor"), "valor"),
             "emissao": _dia(d.get("emissao"), "emissao"),
             "vencimento": _dia(d.get("vencimento"), "vencimento")}
        if t["vencimento"] < t["emissao"]:
            raise Recusa("vencimento antes da emissão")
        self._aberto(t["emissao"])
        id_ = f"T-{len(self.titulos) + 1:05d}"
        t["id"] = id_
        v = t["valor"]
        if natureza == "receber":
            linhas = [(CLIENTES, v, 0), ("3 Receita · " + t["categoria"], 0, v)]
        else:
            linhas = [("4 Despesa · " + t["categoria"], v, 0), (FORNECEDORES, 0, v)]
        self.titulos[id_] = t
        self._lancar(id_, t["emissao"], f"{t['descricao']} — {t['contraparte']}", linhas, id_)
        return id_

    def _baixa(self, d):
        tid = d.get("titulo")
        if tid not in self.titulos:
            raise Recusa("título inexistente")
        t = self.titulos[tid]
        if tid in self.estornados:
            raise Recusa("título estornado")
        valor = _centavos(d.get("valor"), "valor")
        data = _dia(d.get("data"), "data")
        self._aberto(data)
        if data < t["emissao"]:
            raise Recusa("baixa antes da emissão")
        if valor > self.residual(tid):
            raise Recusa(f"baixa maior que o saldo em aberto ({self.residual(tid)})")
        id_ = f"B-{len(self.baixas) + 1:05d}"
        self.baixas[id_] = {"id": id_, "titulo": tid, "valor": valor, "data": data}
        if t["natureza"] == "receber":
            linhas = [(BANCO, valor, 0), (CLIENTES, 0, valor)]
        else:
            linhas = [(FORNECEDORES, valor, 0), (BANCO, 0, valor)]
        self._lancar(id_, data, f"Baixa {tid} — {t['contraparte']}", linhas, tid)
        return id_

    def _estorno(self, d):
        alvo = d.get("alvo")
        data = _dia(d.get("data"), "data")
        motivo = _texto(d.get("motivo"), "motivo")
        orig = next((l for l in self.lancamentos if l["origem"] == alvo), None)
        if orig is None or not (alvo in self.titulos or alvo in self.baixas):
            raise Recusa("só se estorna título ou baixa existente")
        if alvo in self.estornados:
            raise Recusa("já estornado")
        self._aberto(data)
        if data < orig["data"]:
            raise Recusa("estorno antes do lançamento original")
        if alvo in self.titulos and any(
                b["titulo"] == alvo and b["id"] not in self.estornados for b in self.baixas.values()):
            raise Recusa("estorne as baixas deste título primeiro")
        self.estornados.add(alvo)
        linhas = [(l["conta"], l["credito"], l["debito"]) for l in orig["linhas"]]
        tid = orig["linhas"][0]["titulo"]
        self._lancar("E-" + alvo, data, f"Estorno de {alvo}: {motivo}", linhas, tid)
        return "E-" + alvo

    def _lancar(self, origem, data, historico, linhas, titulo):
        debito = sum(l[1] for l in linhas)
        assert debito == sum(l[2] for l in linhas) and debito > 0, "lançamento desequilibrado"
        self.lancamentos.append({
            "origem": origem, "data": data, "historico": historico,
            "linhas": [{"conta": c, "debito": dv, "credito": cv, "titulo": titulo}
                       for c, dv, cv in linhas]})

    # ── leitura (tudo derivado) ──────────────────────────────────────────
    def residual(self, tid):
        """Saldo em aberto pelo SUBRAZÃO: valor − baixas ativas (0 se estornado)."""
        if tid in self.estornados:
            return 0
        pago = sum(b["valor"] for b in self.baixas.values()
                   if b["titulo"] == tid and b["id"] not in self.estornados)
        return self.titulos[tid]["valor"] - pago

    def situacao(self, tid, hoje):
        t = self.titulos[tid]
        if tid in self.estornados:
            return "estornado"
        r = self.residual(tid)
        if r == 0:
            return "pago"
        base = "parcial" if r < t["valor"] else "aberto"
        return "vencido" if t["vencimento"] < hoje else base

    def saldos(self):
        s = {}
        for l in self.lancamentos:
            for x in l["linhas"]:
                s[x["conta"]] = s.get(x["conta"], 0) + x["debito"] - x["credito"]
        return s

    def painel(self, hoje):
        hoje = _dia(hoje, "hoje")
        faixas = ["a vencer", "1–30", "31–60", "61–90", "90+"]
        idade = {n: dict.fromkeys(faixas, 0) for n in ("receber", "pagar")}
        titulos = []
        for tid, t in self.titulos.items():
            r = self.residual(tid)
            if r:
                atraso = (date.fromisoformat(hoje) - date.fromisoformat(t["vencimento"])).days
                faixa = ("a vencer" if atraso <= 0 else "1–30" if atraso <= 30 else
                         "31–60" if atraso <= 60 else "61–90" if atraso <= 90 else "90+")
                idade[t["natureza"]][faixa] += r
            titulos.append(dict(t, residual=r, situacao=self.situacao(tid, hoje),
                                baixas=[b for b in self.baixas.values() if b["titulo"] == tid],
                                estornado=tid in self.estornados))
        s = self.saldos()
        return {"hoje": hoje, "fechado_ate": self.fechado_ate,
                "banco": s.get(BANCO, 0), "receber": s.get(CLIENTES, 0),
                "pagar": -s.get(FORNECEDORES, 0), "idade": idade, "faixas": faixas,
                "titulos": titulos[::-1], "saldos": s,
                "lancamentos": self.lancamentos[::-1][:200],
                "estornados": sorted(self.estornados),
                "integridade": self.eventos[-1]["hash"][:16] if self.eventos else "—",
                "eventos": len(self.eventos)}
