"""Motor de conciliacao.

Tese: a maquina so decide sozinha o que é CERTEZA. Certeza aqui tem definicao
formal, nao vibe:

  (1) valor bate ao centavo (diferenca == 0);
  (2) a direcao do dinheiro bate (saida<->pagar, entrada<->receber);
  (3) a data cabe na janela;
  (4) identidade confirmada por documento OU por nome com peso de informacao;
  (5) EXCLUSIVIDADE MUTUA: nenhum outro candidato plausivel disputa esses
      mesmos lancamentos/titulos.

Falhando (5), o par vai para a fila humana mesmo que pareca perfeito - porque
"parece perfeito" duas vezes e exatamente como se erra em conciliacao.
"""
from __future__ import annotations

import bisect
import hashlib
import itertools
from dataclasses import dataclass, field, replace

from .dinheiro import (dias, fichas, documentos, peso_de, pesos_idf,
                       similaridade, so_digitos)

# --------------------------------------------------------------- entidades


@dataclass(frozen=True)
class Lancamento:
    iid: str
    data: object
    cent: int                # sinal = direcao (negativo = saiu da conta)
    descricao: str
    documento: str = ""
    linha: int = 0

    @property
    def saida(self) -> bool:
        return self.cent < 0


@dataclass(frozen=True)
class Titulo:
    iid: str
    tipo: str                # 'pagar' | 'receber'
    cent: int                # sempre positivo (modulo)
    data: object = None      # data de pagamento/baixa, se houver
    vencimento: object = None
    contraparte: str = ""
    documento: str = ""
    categoria: str = ""
    linha: int = 0

    @property
    def data_ref(self):
        return self.data or self.vencimento


@dataclass
class Vinculo:
    lanc: tuple
    tits: tuple
    escore: float
    dif: int                 # centavos nao explicados (tarifa/juros/desconto)
    confianca: str           # 'certeza' | 'sugestao'
    motivos: tuple = ()
    rivais: int = 0

    @property
    def iid(self) -> str:
        cru = "|".join(sorted(self.lanc)) + "#" + "|".join(sorted(self.tits))
        return hashlib.sha1(cru.encode()).hexdigest()[:12]

    @property
    def forma(self) -> str:
        return f"{len(self.lanc)}:{len(self.tits)}"


@dataclass
class Config:
    janela_pago: int = 7          # dias entre extrato e data de baixa do titulo
    janela_venc: int = 45         # dias entre extrato e vencimento (fallback)
    tolerancia_cent: int = 500    # diferenca maxima aceita como tarifa/juros
    tolerancia_frac: float = 0.01
    limiar_certeza: float = 0.70
    limiar_nome: float = 0.62
    limiar_rival: float = 0.45
    margem_rival: float = 0.75    # rival = escore >= 75% do escore do melhor
    max_grupo: int = 4            # titulos por pagamento em lote
    max_sugestoes: int = 4        # por lancamento/titulo, na fila humana


@dataclass
class Resultado:
    certos: list = field(default_factory=list)
    sugestoes: list = field(default_factory=list)
    lanc_sobra: list = field(default_factory=list)
    tit_sobra: list = field(default_factory=list)
    duplicados: list = field(default_factory=list)
    metricas: dict = field(default_factory=dict)


# --------------------------------------------------------------- ids


def id_de(papel: str, *partes) -> str:
    cru = papel + "|" + "|".join(str(p) for p in partes)
    return papel[0] + hashlib.sha1(cru.encode()).hexdigest()[:11]


# --------------------------------------------------------------- motor


def conciliar(lancs, tits, cfg=None, travados=None, rejeitados=None) -> Resultado:
    """Atalho: gera candidatos e resolve numa tacada."""
    cfg = cfg or Config()
    cands, lancs, tits = gerar_candidatos(lancs, tits, cfg, travados)
    return resolver(cands, lancs, tits, cfg, rejeitados=rejeitados)


def gerar_candidatos(lancs: list[Lancamento], tits: list[Titulo],
                     cfg: Config | None = None, travados: set | None = None):
    """Fase caras: le tudo e monta as hipoteses. Roda UMA vez por arquivo."""
    cfg = cfg or Config()
    travados = travados or set()          # ids ja conciliados em rodada anterior
    # ordem canonica: o resultado nao pode depender da ordem das linhas do
    # arquivo. Sem isso, empates sao resolvidos por acidente de exportacao.
    lancs = sorted((l for l in lancs if l.iid not in travados),
                   key=lambda l: (str(l.data), l.cent, l.iid))
    tits = sorted((t for t in tits if t.iid not in travados),
                  key=lambda t: (str(t.data_ref), t.cent, t.iid))

    peso = peso_de(pesos_idf([t.contraparte for t in tits] + [l.descricao for l in lancs]))
    fl = {l.iid: fichas(l.descricao) for l in lancs}
    ft = {t.iid: fichas(f"{t.contraparte} {t.categoria}") for t in tits}
    dl = {l.iid: documentos(l.descricao) | documentos(l.documento) for l in lancs}
    dt = {t.iid: documentos(t.documento) for t in tits}
    porid_l = {l.iid: l for l in lancs}
    porid_t = {t.iid: t for t in tits}

    def nota(lanc: list[Lancamento], tit: list[Titulo], dif: int) -> tuple[float, tuple]:
        motivos = []
        # data: usa a melhor distancia entre qualquer par (grupo)
        d_pago = min((dias(l.data, t.data) for l in lanc for t in tit if t.data), default=9999)
        d_venc = min((dias(l.data, t.vencimento) for l in lanc for t in tit if t.vencimento), default=9999)
        if d_pago <= cfg.janela_pago:
            s_data = 1.0 - 0.6 * (d_pago / max(1, cfg.janela_pago))
            motivos.append(f"baixa a {d_pago}d")
        elif d_venc <= cfg.janela_venc:
            s_data = 0.85 - 0.50 * (d_venc / max(1, cfg.janela_venc))
            motivos.append(f"vencimento a {d_venc}d")
        else:
            return -1.0, ()
        # identidade
        fL = frozenset().union(*[fl[l.iid] for l in lanc]) if lanc else frozenset()
        fT = frozenset().union(*[ft[t.iid] for t in tit]) if tit else frozenset()
        s_nome = similaridade(fT, fL, peso)
        dL = frozenset().union(*[dl[l.iid] for l in lanc]) if lanc else frozenset()
        dT = frozenset().union(*[dt[t.iid] for t in tit]) if tit else frozenset()
        s_doc = 1.0 if (dL & dT) else 0.0
        if s_doc:
            motivos.append("documento " + ",".join(sorted(dL & dT)[:2]))
        if s_nome >= cfg.limiar_nome:
            motivos.append(f"nome {int(s_nome * 100)}%")
        s_val = 1.0 if dif == 0 else max(0.0, 1.0 - abs(dif) / max(1, _teto(sum(abs(t.cent) for t in tit), cfg)))
        if dif:
            motivos.append(f"diferenca {dif/100:+.2f}")
        # identidade e um OU, nao uma soma: documento forte basta, nome forte
        # basta. Ter os dois e bonus, nao requisito.
        ident = max(s_nome, s_doc)
        e = 0.30 * s_data + 0.55 * ident + 0.15 * (s_nome * s_doc)
        e *= 1.0 if dif == 0 else 0.75 * s_val
        return e, tuple(motivos)

    # ---- geracao de candidatos
    cands: list[Vinculo] = []

    por_valor: dict[int, list[Titulo]] = {}
    for t in tits:
        por_valor.setdefault(abs(t.cent), []).append(t)
    # indice ordenado: acha titulos numa faixa de valor em log(n) em vez de
    # varrer a carteira inteira por lancamento (era O(n^2)).
    escala = sorted(por_valor)
    tem_1a1 = set()          # ids com par 1:1 plausivel - dispensam analise de lote

    for l in lancs:
        alvo = abs(l.cent)
        teto = _teto(alvo, cfg)
        faixa = escala[bisect.bisect_left(escala, alvo - teto):
                       bisect.bisect_right(escala, alvo + teto)]
        for v in faixa:
            for t in por_valor[v]:
                if not _direcao_ok(l, t):
                    continue
                dif = alvo - abs(t.cent)
                e, m = nota([l], [t], dif)
                if e <= 0:
                    continue
                cands.append(Vinculo((l.iid,), (t.iid,), e, dif, "?", m))
                if e >= cfg.limiar_rival:
                    tem_1a1.add(l.iid)
                    tem_1a1.add(t.iid)

    # 1:N - um pagamento em lote quita varios titulos da mesma contraparte.
    # So para lancamentos sem par 1:1 plausivel: onde ja existe um par direto,
    # o lote seria no maximo um rival - e rival nao vira certeza de todo jeito.
    for l in lancs:
        if l.iid in tem_1a1:
            continue
        alvo = abs(l.cent)
        compat = [t for t in tits if _direcao_ok(l, t)]
        for grupo in _subconjuntos(compat, alvo, cfg, fl[l.iid], ft, peso, l):
            dif = alvo - sum(abs(t.cent) for t in grupo)
            e, m = nota([l], grupo, dif)
            if e > 0:
                cands.append(
                    Vinculo((l.iid,), tuple(sorted(t.iid for t in grupo)), e, dif,
                            "?", m + (f"lote de {len(grupo)} titulos",))
                )

    # N:1 - titulo quitado por varios lancamentos (parcelas / pagamento dividido)
    for t in tits:
        if t.iid in tem_1a1:
            continue
        alvo = abs(t.cent)
        compat = [l for l in lancs if _direcao_ok(l, t) and abs(l.cent) < alvo]
        for grupo in _subconjuntos_l(compat, alvo, cfg, t, ft[t.iid], fl, peso):
            dif = sum(abs(l.cent) for l in grupo) - alvo
            e, m = nota(grupo, [t], -dif if False else dif)
            if e > 0:
                cands.append(
                    Vinculo(tuple(sorted(l.iid for l in grupo)), (t.iid,), e, dif, "?",
                            m + (f"{len(grupo)} lancamentos",))
                )

    return cands, lancs, tits


def resolver(cands, lancs, tits, cfg=None, excluidos=None, rejeitados=None) -> Resultado:
    """Fase barata: decide o que e certeza. Roda a cada decisao humana - e por
    isso aprovar um vinculo pode PROMOVER outro a certeza, ao remover o rival."""
    cfg = cfg or Config()
    excluidos = set(excluidos or ())
    rejeitados = set(rejeitados or ())
    if excluidos or rejeitados:
        cands = [c for c in cands
                 if c.iid not in rejeitados
                 and not ((set(c.lanc) | set(c.tits)) & excluidos)]
        lancs = [l for l in lancs if l.iid not in excluidos]
        tits = [t for t in tits if t.iid not in excluidos]
    for c in cands:
        c.confianca = "?"
        c.rivais = 0

    # ---- exclusividade mutua
    dono_l: dict[str, list[int]] = {}
    dono_t: dict[str, list[int]] = {}
    for i, c in enumerate(cands):
        for x in c.lanc:
            dono_l.setdefault(x, []).append(i)
        for x in c.tits:
            dono_t.setdefault(x, []).append(i)

    def rivais_de(i: int) -> int:
        """Disputa REAL, nao qualquer alternativa. Se o par tem nome 100% e
        documento (0,95) e a alternativa tem so a data em comum (0,30), nao ha
        duvida - ha uma resposta boa e uma ruim. Duvida e quando duas hipoteses
        tem forca comparavel: e ai que a maquina tem de calar e perguntar."""
        c = cands[i]
        viz = set()
        for x in c.lanc:
            viz |= set(dono_l.get(x, ()))
        for x in c.tits:
            viz |= set(dono_t.get(x, ()))
        viz.discard(i)
        piso = max(cfg.limiar_rival, cfg.margem_rival * c.escore)
        return sum(1 for j in viz if cands[j].escore >= piso)

    certos, sugestoes = [], []
    for i, c in enumerate(cands):
        r = rivais_de(i)
        c.rivais = r
        s_nome_ok = any(m.startswith("nome ") for m in c.motivos)
        s_doc_ok = any(m.startswith("documento") for m in c.motivos)
        grupo = c.forma != "1:1"
        forte = s_doc_ok or (s_nome_ok and (not grupo or c.escore >= 0.85))
        if (c.dif == 0 and r == 0 and c.escore >= cfg.limiar_certeza and forte):
            c.confianca = "certeza"
            certos.append(c)
        else:
            c.confianca = "sugestao"
            sugestoes.append(c)

    # ---- um id nao pode estar em dois vinculos certos (defesa em profundidade)
    vistos: set[str] = set()
    certos.sort(key=lambda c: (-c.escore, c.iid))
    finais = []
    for c in certos:
        ids = set(c.lanc) | set(c.tits)
        if ids & vistos:
            c.confianca = "sugestao"
            sugestoes.append(c)
            continue
        vistos |= ids
        finais.append(c)

    sugestoes.sort(key=lambda c: (-c.escore, c.iid))
    sugestoes = [c for c in sugestoes if not ((set(c.lanc) | set(c.tits)) & vistos)]
    # poda de apresentacao: ninguem revisa 40 hipoteses do mesmo lancamento.
    # Feita DEPOIS do calculo de rivais - podar antes esconderia a duvida.
    quota: dict = {}
    enxuta = []
    for c in sugestoes:
        ids = list(c.lanc) + list(c.tits)
        if all(quota.get(x, 0) < cfg.max_sugestoes for x in ids):
            for x in ids:
                quota[x] = quota.get(x, 0) + 1
            enxuta.append(c)
    sugestoes = enxuta

    # "sem par" = quem nao tem NENHUMA hipotese, nao quem foi podado da fila.
    com_hipotese = set()
    for c in cands:
        if (set(c.lanc) | set(c.tits)) & vistos:
            continue
        com_hipotese |= set(c.lanc) | set(c.tits)
    lanc_sobra = [l for l in lancs if l.iid not in vistos and l.iid not in com_hipotese]
    tit_sobra = [t for t in tits if t.iid not in vistos and t.iid not in com_hipotese]

    res = Resultado(
        certos=finais,
        sugestoes=sugestoes,
        lanc_sobra=lanc_sobra,
        tit_sobra=tit_sobra,
        duplicados=_duplicados(lancs),
    )
    res.metricas = _metricas(res, lancs, tits)
    _invariantes(res, lancs, tits)
    return res


def _teto(valor: int, cfg: Config) -> int:
    return max(cfg.tolerancia_cent, int(abs(valor) * cfg.tolerancia_frac))


def _direcao_ok(l: Lancamento, t: Titulo) -> bool:
    if t.tipo == "pagar":
        return l.cent < 0
    if t.tipo == "receber":
        return l.cent > 0
    return True


def _canon(f: frozenset) -> tuple:
    """Assinatura estavel de um nome: as fichas ordenadas. Duas linhas da mesma
    contraparte tem a mesma assinatura - sem escolher 'a melhor ficha', que
    fragmentava o espaco de candidatos e escondia rivais."""
    return tuple(sorted(f))


def _combos(itens, alvo, teto, kmax, valor):
    """Subconjuntos de 2..kmax itens cuja soma cabe no alvo. Ordem canonica ->
    resultado identico independente da ordem de entrada."""
    itens = sorted(itens, key=lambda x: (-abs(valor(x)), x.iid))[:14]
    saida = []
    for n in range(2, min(kmax, len(itens)) + 1):
        for combo in itertools.combinations(itens, n):
            s = sum(abs(valor(x)) for x in combo)
            if abs(alvo - s) <= teto:
                saida.append(list(combo))
                if len(saida) >= 200:
                    return saida
    return saida


def _subconjuntos(tits, alvo, cfg, f_lanc, ft, peso, lanc):
    """Lotes candidatos: titulos que (a) se parecem com a descricao do
    lancamento OU (b) sao da mesma contraparte entre si."""
    viaveis = [t for t in tits
               if abs(t.cent) < alvo and dias(lanc.data, t.data_ref) <= cfg.janela_venc]
    if len(viaveis) < 2:
        return []
    teto = _teto(alvo, cfg)
    conjuntos = []
    por_nome = [t for t in viaveis if similaridade(ft[t.iid], f_lanc, peso) >= 0.5]
    if len(por_nome) >= 2:
        conjuntos.append(por_nome)
    mesma: dict = {}
    for t in viaveis:
        mesma.setdefault(_canon(ft[t.iid]), []).append(t)
    for chave, grupo in sorted(mesma.items()):
        if chave and len(grupo) >= 2:
            conjuntos.append(grupo)
    vistos, saida = set(), []
    for conj in conjuntos:
        for combo in _combos(conj, alvo, teto, cfg.max_grupo, lambda t: t.cent):
            k = tuple(sorted(t.iid for t in combo))
            if k not in vistos:
                vistos.add(k)
                saida.append(combo)
    return saida


def _subconjuntos_l(lancs, alvo, cfg, tit, f_tit, fl, peso):
    """Titulo quitado por varios lancamentos: parcelas ou pagamento dividido."""
    viaveis = [l for l in lancs if dias(l.data, tit.data_ref) <= cfg.janela_venc]
    if len(viaveis) < 2:
        return []
    teto = _teto(alvo, cfg)
    conj = [l for l in viaveis if similaridade(f_tit, fl[l.iid], peso) >= 0.5]
    if len(conj) < 2:
        return []
    return _combos(conj, alvo, teto, cfg.max_grupo, lambda l: l.cent)


def _duplicados(lancs) -> list:
    visto: dict = {}
    saida = []
    for l in lancs:
        k = (l.data, l.cent, " ".join(sorted(fichas(l.descricao))))
        if k in visto:
            saida.append((visto[k], l.iid))
        else:
            visto[k] = l.iid
    return saida


def _metricas(res: Resultado, lancs, tits) -> dict:
    v_certo = sum(abs(porid(lancs, x).cent) for c in res.certos for x in c.lanc)
    v_total = sum(abs(l.cent) for l in lancs)
    n_certo = sum(len(c.lanc) for c in res.certos)
    return {
        "lancamentos": len(lancs),
        "titulos": len(tits),
        "vinculos_certos": len(res.certos),
        "lanc_conciliados": n_certo,
        "tit_conciliados": sum(len(c.tits) for c in res.certos),
        "sugestoes": len(res.sugestoes),
        "lanc_sem_par": len(res.lanc_sobra),
        "tit_sem_par": len(res.tit_sobra),
        "duplicados": len(res.duplicados),
        "valor_total_cent": v_total,
        "valor_conciliado_cent": v_certo,
        "cobertura": round(v_certo / v_total, 4) if v_total else 0.0,
        "automacao": round(n_certo / len(lancs), 4) if lancs else 0.0,
    }


def porid(itens, iid):
    for i in itens:
        if i.iid == iid:
            return i
    raise KeyError(iid)


def _invariantes(res: Resultado, lancs, tits) -> None:
    """Se qualquer um destes quebrar, o resultado esta errado e o sistema
    prefere explodir a entregar numero errado."""
    L = {l.iid: l for l in lancs}
    T = {t.iid: t for t in tits}
    vl, vt = set(), set()
    for c in res.certos:
        for x in c.lanc:
            assert x not in vl, "I1: lancamento em dois vinculos certos"
            assert x in L, "I1b: id fantasma"
            vl.add(x)
        for x in c.tits:
            assert x not in vt, "I1: titulo em dois vinculos certos"
            assert x in T, "I1b: id fantasma"
            vt.add(x)
        soma_l = sum(abs(L[x].cent) for x in c.lanc)
        soma_t = sum(abs(T[x].cent) for x in c.tits)
        assert soma_l - soma_t == c.dif, "I2: conservacao de valor violada"
        assert c.dif == 0, "I3: vinculo certo nunca tem diferenca"
        for x in c.lanc:
            for y in c.tits:
                assert _direcao_ok(L[x], T[y]), "I4: direcao do dinheiro invertida"
    em_sug = set()
    for c in res.sugestoes:
        em_sug |= set(c.lanc) | set(c.tits)
    assert not (em_sug & (vl | vt)), "I5: id conciliado tambem sugerido"
    assert em_sug <= (set(L) | set(T)), "I5b: sugestao com id fantasma"
    # todo id de entrada cai em exatamente um destino: conciliado, com
    # hipotese, ou sem par. Ninguem desaparece no meio do caminho.
    assert not (vl & {l.iid for l in res.lanc_sobra}), "I6: conciliado listado como sem par"
    assert not (vt & {t.iid for t in res.tit_sobra}), "I6: conciliado listado como sem par"
    assert not (em_sug & ({l.iid for l in res.lanc_sobra} | {t.iid for t in res.tit_sobra})), \
        "I6: id na fila e tambem em sem-par"
