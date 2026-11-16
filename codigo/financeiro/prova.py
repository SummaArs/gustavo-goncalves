"""
prova.py — prova de fogo do núcleo financeiro.

Cada caso é uma sequência aleatória de operações (válidas, inválidas, repetidas,
com a mesma chave e conteúdo diferente). Depois de CADA operação, todos os
invariantes são conferidos; no fim, o livro é relido do disco e comparado.

Depois, os mutantes: o mesmo arnês roda contra cópias do núcleo com um defeito
plantado. Mutante que passa = prova cega naquele ponto.

    python3 prova.py            # 3.000 sequências + 7 mutantes
"""

import os
import sys
import tempfile
import types

AQUI = os.path.dirname(os.path.abspath(__file__))
import importlib.util  # noqa: E402  (o arnês do kit tem o mesmo nome deste arquivo: carregar pelo caminho)
_esp = importlib.util.spec_from_file_location("kit_prova", os.path.join(AQUI, "..", "kit_ferramentas", "prova.py"))
_kit = importlib.util.module_from_spec(_esp)
_esp.loader.exec_module(_kit)
provar, executar = _kit.provar, _kit.executar

FONTE = open(os.path.join(AQUI, "nucleo.py"), encoding="utf-8").read()


def carregar(fonte):
    m = types.ModuleType("nucleo_teste")
    exec(compile(fonte, "nucleo.py", "exec"), m.__dict__)
    return m


DATAS = [f"2026-{m:02d}-{d:02d}" for m in range(1, 13) for d in (1, 10, 20, 28)]


def gerador(rnd, escala):
    n = 2 + int(60 * escala)
    ops = []
    for i in range(n):
        r = rnd.random()
        d = rnd.choice(DATAS)
        if r < 0.30:
            emi = rnd.choice(DATAS)
            ops.append(("titulo", {
                "natureza": rnd.choice(["receber", "pagar"] * 5 + ["x"]),
                "contraparte": rnd.choice(["Alfa", "EPSILON", "Gama", "Delta"] * 3 + [" "]),
                "descricao": rnd.choice(["NF 101", "Aluguel", "Licença"] * 4 + [""]),
                "categoria": rnd.choice(["Serviços", "Produtos", "Ocupação"]),
                "valor": rnd.choice([rnd.randint(1, 10 ** rnd.randint(1, 9))] * 15 + [0, -5, 10.5, True, "100"]),
                "emissao": emi,
                "vencimento": rnd.choice([emi, max(emi, d)] * 6 + [d, "2026-02-30", None])}))
        elif r < 0.62:
            ops.append(("baixa", {"titulo": rnd.choice([("T", rnd.randrange(99))] * 9 + ["T-99999"]),
                                  "valor": rnd.choice([rnd.randint(1, 10 ** rnd.randint(1, 9))] * 6 + [0, "1"]),
                                  "data": rnd.choice(DATAS[len(DATAS) * i // n:]), "_parte": rnd.choice([None, 1, 2, 2, 3, 3])}))
        elif r < 0.76:
            alvo = rnd.choice([("T", rnd.randrange(99))] * 4 + [("B", rnd.randrange(99))] * 5 + ["X-1", "E-T-00001"])
            ops.append(("estorno", {"alvo": alvo, "data": d, "motivo": rnd.choice(["erro"] * 6 + [""])}))
        elif r < 0.79:
            ops.append(("fechamento", {"data": rnd.choice(DATAS[:1 + len(DATAS) * i // n])}))
        elif r < 0.92 and ops:
            ops.append(("REPETE", rnd.randrange(len(ops))))           # mesma intenção
        elif ops:
            ops.append(("COLIDE", rnd.randrange(len(ops))))           # mesma chave, outro conteúdo
    return ops


def checar(L):
    nuc = _MOD[0]
    s = L.saldos()
    for l in L.lancamentos:
        dv = sum(x["debito"] for x in l["linhas"])
        cv = sum(x["credito"] for x in l["linhas"])
        assert dv == cv > 0, f"lançamento desequilibrado {l['origem']}"
        assert all(type(x["debito"]) is int and type(x["credito"]) is int for x in l["linhas"]), "não-int"
    assert sum(s.values()) == 0, "balancete não zera"
    rec = pag = banco = 0
    for tid, t in L.titulos.items():
        r = L.residual(tid)
        assert 0 <= r <= t["valor"], f"{tid} residual fora de [0, valor]: {r}"
        conta = nuc.CLIENTES if t["natureza"] == "receber" else nuc.FORNECEDORES
        sinal = 1 if t["natureza"] == "receber" else -1
        razao = sinal * sum(x["debito"] - x["credito"] for l in L.lancamentos
                            for x in l["linhas"] if x["conta"] == conta and x["titulo"] == tid)
        assert razao == r, f"{tid}: subrazão {r} ≠ razão {razao} (duas testemunhas)"
        if t["natureza"] == "receber":
            rec += r
        else:
            pag += r
    for b in L.baixas.values():
        if b["id"] not in L.estornados:
            banco += b["valor"] * (1 if L.titulos[b["titulo"]]["natureza"] == "receber" else -1)
    assert s.get(nuc.CLIENTES, 0) == rec, "conta Clientes ≠ soma dos abertos a receber"
    assert -s.get(nuc.FORNECEDORES, 0) == pag, "conta Fornecedores ≠ soma dos abertos a pagar"
    assert s.get(nuc.BANCO, 0) == banco, "banco ≠ baixas ativas"


_MOD = [None]


def rodar(nuc, ops):
    _MOD[0] = nuc
    with tempfile.TemporaryDirectory() as tmp:
        cam = os.path.join(tmp, "livro.jsonl")
        L = nuc.Livro(cam)
        aceitos = []
        for i, op in enumerate(ops):
            if op[0] in ("REPETE", "COLIDE"):
                j = op[1]
                if j >= len(aceitos) or aceitos[j] is None:
                    continue
                tipo, dados, chave, id_ = aceitos[j]
                antes = len(L.eventos)
                if op[0] == "REPETE":
                    assert L.registrar(tipo, dict(dados), chave) == id_, "repetição devolveu outro id"
                    assert len(L.eventos) == antes, "repetição gravou de novo"
                else:
                    try:
                        L.registrar(tipo, dict(dados, _colide=1), chave)
                        raise AssertionError("mesma chave com outro conteúdo foi aceita")
                    except nuc.Recusa:
                        pass
                    assert len(L.eventos) == antes
                continue
            tipo, dados = op
            dados = dict(dados)
            parte = dados.pop("_parte", None)
            for campo in ("titulo", "alvo"):                      # mira objeto que existe
                if isinstance(dados.get(campo), (tuple, list)):
                    pool = sorted(L.titulos if dados[campo][0] == "T" else L.baixas)
                    dados[campo] = pool[dados[campo][1] % len(pool)] if pool else "T-99999"
            if parte and dados["titulo"] in L.titulos:            # baixa que cabe: parte do saldo
                r = L.residual(dados["titulo"])
                dados["valor"] = max(1, r // parte) if r else 1
            fechado = L.fechado_ate
            foto = (repr(L.painel("2026-12-31")), len(L.eventos))
            chave = f"k{i}"
            try:
                id_ = L.registrar(tipo, dados, chave)
                aceitos.append((tipo, dados, chave, id_))
                data = dados.get("emissao") or dados.get("data")
                assert data > fechado, f"aceitou {tipo} em {data} com período fechado até {fechado}"
            except nuc.Recusa:
                aceitos.append(None)
                assert (repr(L.painel("2026-12-31")), len(L.eventos)) == foto, "recusa mudou o estado"
            checar(L)
        R = nuc.Livro(cam)                                        # releitura do disco
        assert repr(R.painel("2026-12-31")) == repr(L.painel("2026-12-31")), "replay do disco diverge"
        if L.eventos:                                             # adulteração tem que ser pega
            linhas = open(cam, encoding="utf-8").read().splitlines()
            k = len(linhas) // 2
            linhas[k] = linhas[k].replace('"valor":', '"valor":1', 1).replace('"data":"2026', '"data":"2025', 1)
            if linhas[k] != open(cam, encoding="utf-8").read().splitlines()[k]:
                open(cam, "w", encoding="utf-8").write("\n".join(linhas) + "\n")
                try:
                    nuc.Livro(cam)
                    raise AssertionError("livro adulterado foi aberto")
                except RuntimeError:
                    pass
    return True


MUTANTES = {
    "baixa sem teto do saldo": ('if valor > self.residual(tid):', 'if False:'),
    "residual ignora baixa estornada": ('if b["titulo"] == tid and b["id"] not in self.estornados)',
                                        'if b["titulo"] == tid)'),
    "estorno não inverte": ('(l["conta"], l["credito"], l["debito"])', '(l["conta"], l["debito"], l["credito"])'),
    "fechamento ignorado": ('if data <= self.fechado_ate:\n            raise Recusa(f"período',
                            'if False:\n            raise Recusa(f"período'),
    "chave confirma conteúdo diferente": ('e["dados"] == dados', 'True'),
    "hash não conferido": ('e["hash"] != self._hash(e)', 'False'),
    "estorna título com baixa ativa": ('raise Recusa("estorne as baixas', 'print("estorne as baixas'),
}


def main():
    nuc = carregar(FONTE)
    rels = [provar("núcleo financeiro: 9 invariantes por operação", gerador,
                   lambda ops: rodar(nuc, ops), 3000, semente=7)]
    code = executar(rels)
    print("\nMUTANTES (cada um precisa ser acusado):")
    vivos = 0
    for nome, (de, para) in MUTANTES.items():
        assert FONTE.count(de) == 1, f"mutante '{nome}' não achou o trecho"
        mut = carregar(FONTE.replace(de, para))
        r = provar(nome, gerador, lambda ops: rodar(mut, ops), 3000, semente=7, tentativas_encolhimento=0)
        acusado = not r.ok
        vivos += not acusado
        print(f"  {'ACUSADO' if acusado else 'VIVO   '}  {nome}  ({r['violacoes']} violações)"
              + (f" — {r['motivo'][:90]}" if acusado else ""))
    print(f"\n{len(MUTANTES) - vivos}/{len(MUTANTES)} mutantes acusados")
    return 1 if code or vivos else 0


if __name__ == "__main__":
    sys.exit(main())
