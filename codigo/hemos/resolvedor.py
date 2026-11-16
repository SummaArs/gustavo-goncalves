"""
HEMOS — Resolvedor: texto sujo -> id do léxico.

Este é o único módulo do sistema que enxerga português. Daqui para frente só
circulam ids. É o análogo do decodificador do Herus: pega o sinal ruidoso e
devolve um símbolo do codebook — ou se RECUSA a devolver.

A regra que sustenta tudo:

    é sempre melhor rejeitar do que acertar por sorte.

No Herus, quadro corrompido é descartado, não decodificado no chute — porque
decodificar errado com confiança é pior que não decodificar. Aqui vale o mesmo
com peso clínico: interpretar "não tomo remédio nenhum" como SIM reprova (ou
aprova) a pessoa errada. Então a rejeição não é falha, é o modo seguro; quem
cai nela recebe menu numerado, e o menu resolve 90% do tráfego real.

Três defesas contra o acerto por sorte:
  1. CONTEXTO — cada estado declara o conjunto de símbolos admissíveis. Fora
     dele nada é considerado. Espaço candidato pequeno = ambiguidade rara.
  2. MARGEM — não basta o melhor candidato pontuar alto; ele tem que vencer o
     segundo por uma folga δ. Empate técnico é ambiguidade, e ambiguidade é
     rejeição. (É o critério que mata o erro confiante.)
  3. TOKEN INTEIRO — o casamento aproximado é por palavra completa, com
     Levenshtein limitado pelo tamanho. Nunca por bigrama/substring: no Herus
     ficou provado que semelhança de superfície mente ("gtao" não compartilha
     nenhum bigrama com "gato", e "cirurgia"/"cirrose" compartilham vários).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, timedelta

import lexico as lx

# Folga mínima entre o 1º e o 2º candidato. Em unidades de "caracteres úteis
# casados". δ = 1.0 significa: o vencedor tem que ser estritamente mais
# específico que o rival, não só empatar.
MARGEM_MINIMA = 1.0

NEGADORES = frozenset({"nao", "nunca", "jamais", "nenhum", "nenhuma", "nem", "sem",
                       "negativo", "naum", "num"})
# Negadores longos aceitam uma edição; os de 3 letras, NÃO — "sem" e "sim"
# estão a distância 1 um do outro, e tolerar aí transformaria a afirmação mais
# comum do sistema em negação.
NEGADORES_TOLERANTES = tuple(n for n in NEGADORES if len(n) >= 5)


def canonizar(palavra: str) -> str:
    """Colapsa letras repetidas: "simmm"->"sim", "nãoo"->"nao", "seii"->"sei".

    Ênfase por repetição é universal no WhatsApp e não muda o significado.
    O risco (colapsar "carro" em "caro") é controlado por uma invariante: nenhum
    par de superfícies de símbolos diferentes pode colidir nesta forma — ver I9
    em testes/teste_nucleo.py.
    """
    return re.sub(r"(.)\1+", r"\1", palavra)


def eh_negador(token: str) -> bool:
    """Detecção de negação TOLERANTE a erro de digitação.

    Este é o conserto de uma inversão de significado achada pela busca
    adversarial: o casamento de gatilho era aproximado, mas a negação exigia o
    token exato. Bastava "nãoo" ou "nãot" para a negação sumir e a resposta
    virar o oposto. Defesa e ataque têm que ter a mesma tolerância.
    """
    s = canonizar(token)
    if s in NEGADORES or token in NEGADORES:
        return True
    if s.startswith("nao") or s.startswith("nunca"):
        return True
    return any(levenshtein(s, n, 1) <= 1 for n in NEGADORES_TOLERANTES)

MESES = {
    "janeiro": 1, "jan": 1, "fevereiro": 2, "fev": 2, "marco": 3, "mar": 3,
    "abril": 4, "abr": 4, "maio": 5, "mai": 5, "junho": 6, "jun": 6,
    "julho": 7, "jul": 7, "agosto": 8, "ago": 8, "setembro": 9, "set": 9,
    "outubro": 10, "out": 10, "novembro": 11, "nov": 11, "dezembro": 12, "dez": 12,
}

UNIDADES_DIA = {
    "dia": 1, "dias": 1, "semana": 7, "semanas": 7,
    "mes": 30, "meses": 30, "ano": 365, "anos": 365,
}


@dataclass(frozen=True)
class Resolucao:
    """Resultado da decodificação. `valor` é o payload (kg, data, ...)."""

    id: int
    valor: object = None
    score: float = 0.0
    margem: float = 0.0
    rival: int | None = None  # quem ficou em 2º — vai para o log de auditoria

    @property
    def entendeu(self) -> bool:
        return self.id != lx.NAO_ENTENDI

    def __repr__(self) -> str:  # pragma: no cover - conveniência de depuração
        v = f", valor={self.valor!r}" if self.valor is not None else ""
        return f"<{lx.nome(self.id)}{v} score={self.score:.1f} margem={self.margem:.1f}>"


# ── normalização ────────────────────────────────────────────────────────────

def normalizar(texto: str) -> str:
    """Tira acento, caixa, emoji e pontuação. Mantém dígitos, / - . e , ."""
    t = unicodedata.normalize("NFD", texto)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")  # remove acentos
    t = t.lower()
    t = re.sub(r"[^\w\s/\-.,]", " ", t)  # emoji e pontuação viram espaço
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def tokenizar(texto_normalizado: str) -> list[str]:
    """Separa palavras e limpa pontuação de BORDA ("não." -> "nao").

    Seguro porque os parsers de grandeza (data, peso, contagem) leem o texto
    normalizado inteiro antes, e não estes tokens — "15/03/2026" e "72,5"
    chegam intactos onde importa.
    """
    brutos = re.split(r"[\s,]+", texto_normalizado)
    return [t for t in (b.strip(".,/-") for b in brutos) if t]


def _tolerancia(palavra: str) -> int:
    """Quanto erro de digitação se aceita numa palavra, pelo tamanho dela.

    Palavra curta não ganha tolerância: com 3 ou 4 letras, distância 1 já pula
    para outra palavra comum ("nao" -> "sao", "mao"). Tolerar aí seria fabricar
    ambiguidade em cima dos símbolos mais críticos do sistema.

    O limiar subiu de 3 para 4 depois que a forja mostrou o risco: a gíria
    "nops" (que o próprio gerador propôs) casava por distância 1 com "nos",
    uma das palavras mais comuns do português. Uma resposta contendo "nos"
    virava NÃO. Palavra de 4 letras agora exige casamento exato.
    """
    n = len(palavra)
    if n <= 4:
        return 0
    if n <= 6:
        return 1
    return 2


def levenshtein(a: str, b: str, limite: int) -> int:
    """Distância de edição com poda: devolve limite+1 assim que estoura."""
    if a == b:
        return 0
    if abs(len(a) - len(b)) > limite:
        return limite + 1
    anterior = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        atual = [i]
        melhor = i
        for j, cb in enumerate(b, 1):
            custo = 0 if ca == cb else 1
            v = min(anterior[j] + 1, atual[j - 1] + 1, anterior[j - 1] + custo)
            atual.append(v)
            melhor = min(melhor, v)
        if melhor > limite:
            return limite + 1
        anterior = atual
    return anterior[-1]


def _casa_token(alvo: str, tok: str) -> float | None:
    """Casa uma palavra da superfície contra uma palavra do texto.

    Devolve o "crédito" em caracteres (exato = len; aproximado = len - 0.5*d),
    ou None se não casou. O desconto garante que casamento exato sempre vence
    casamento aproximado do mesmo tamanho.
    """
    if alvo == tok:
        return float(len(alvo))
    if canonizar(alvo) == canonizar(tok):
        return len(alvo) - 0.25  # só ênfase por repetição
    tol = _tolerancia(alvo)
    if tol == 0:
        return None
    d = levenshtein(canonizar(alvo), canonizar(tok), tol)
    if d > tol:
        return None
    return len(alvo) - 0.5 * d


def _casa_superficie(superficie: str, tokens: list[str]) -> tuple[float, int, set[int]] | None:
    """A superfície casa se suas palavras aparecem NA ORDEM no texto.

    Devolve (crédito, índice da 1ª palavra casada, índices casados). O índice
    inicial serve à análise de negação (só nega quem tem negador ANTES); o
    conjunto de índices serve à regra do token solitário.
    """
    alvos = superficie.split()
    creditos = 0.0
    i = 0
    primeiro = -1
    usados: set[int] = set()
    for alvo in alvos:
        while i < len(tokens):
            c = _casa_token(alvo, tokens[i])
            largura = 1
            # Espaço espúrio no meio da palavra ("nao s ei", "cert eza") é uma
            # das falhas mais comuns de digitação em celular, e era por ela que
            # a busca adversarial derrubava "não sei" para "não" — trocando
            # "não me recordo" por "isso nunca aconteceu". Tentar a colagem de
            # dois tokens vizinhos custa pouco e fecha o buraco.
            if i + 1 < len(tokens):
                cc = _casa_token(alvo, tokens[i] + tokens[i + 1])
                if cc is not None and (c is None or cc - 0.25 > c):
                    c, largura = cc - 0.25, 2
            if c is not None:
                if primeiro < 0:
                    primeiro = i
                creditos += c
                usados.update(range(i, i + largura))
                i += largura
                break
            i += 1
        else:
            return None
    return creditos, primeiro, usados


# Gordura conversacional: não conta como "conteúdo não explicado".
RECHEIO = frozenset({
    "favor", "obrigado", "obrigada", "entao", "valeu", "beleza", "okay",
    "desculpa", "gente", "voce", "voces", "aqui", "agora", "mesmo", "tambem",
    "ainda", "muito", "tudo", "bem", "bom", "dia", "tarde", "noite", "certo",
    "acho", "assim", "tipo", "poxa", "olha", "entendi",
})

# Símbolos onde um erro custa caro (resposta clínica ou comando de fluxo).
# Só eles são submetidos à regra do token solitário — numa INTENÇÃO, decidir
# por uma palavra-chave solta é o modo normal de conversar ("endereço?"), e
# errar ali só mostra o menu errado.
AFIRMADORES = frozenset({"sim", "claro", "positivo", "afirmativo", "confirmo", "aham"})

SENSIVEIS = frozenset({
    lx.SIM, lx.NAO, lx.NAO_SEI, lx.NUNCA, lx.VOLTAR, lx.PARAR, lx.HUMANO, lx.REPETIR,
})


def _conteudo_nao_explicado(tokens: list[str], usados: set[int],
                            vencedor: int | None = None) -> list[str]:
    """Palavras de peso que o casamento vencedor não explicou.

    Um reforço da MESMA polaridade do vencedor não conta como conteúdo
    estranho: em "não, nunca", o "nunca" concorda com o "não" — tratá-lo como
    informação não explicada fazia a resposta mais clara possível cair no menu.
    """
    fora = []
    for i, t in enumerate(tokens):
        if i in usados or len(t) < 4 or t in RECHEIO or t.isdigit():
            continue
        if vencedor in (lx.NAO, lx.NUNCA) and eh_negador(t):
            continue
        if vencedor == lx.SIM and t in AFIRMADORES:
            continue
        fora.append(t)
    return fora


# Construções concessivas: gramaticalmente invertem o sentido da negação que
# elas contêm. "não é que eu não tenha" quer dizer que TEM. Nenhum casamento
# por palavra acerta isso, e chutar aqui inverte uma resposta clínica — então
# a leitura correta é recusar e perguntar de novo.
CONSTRUCOES_AMBIGUAS: tuple[str, ...] = (
    "nao e que", "nao que", "nem sempre", "nao necessariamente",
    "sim e nao", "nao exatamente", "mais ou menos",
)


# ── parsers de grandeza ─────────────────────────────────────────────────────

def _fim_do_mes(ano: int, mes: int) -> date:
    if mes == 12:
        return date(ano, 12, 31)
    return date(ano, mes + 1, 1) - timedelta(days=1)


def parse_data(texto: str, hoje: date) -> date | None:
    """Interpreta data absoluta ou relativa. Nunca devolve data no futuro.

    Convenção de segurança: quando a informação é incompleta (só mês/ano), o
    sistema assume a data MAIS RECENTE compatível — o fim do mês. Incerteza
    sempre resolve para o lado mais restritivo, porque errar para "mais
    recente" adia uma doação e errar para "mais antigo" libera sangue que a
    norma não liberaria.
    """
    t = normalizar(texto)

    if re.fullmatch(r"hoje|agora|hoje mesmo", t):
        return hoje
    if re.fullmatch(r"ontem", t):
        return hoje - timedelta(days=1)
    if re.fullmatch(r"anteontem|antes de ontem", t):
        return hoje - timedelta(days=2)
    if re.search(r"\b(semana passada|semana retrasada)\b", t):
        return hoje - timedelta(days=7 if "retrasada" not in t else 14)
    if re.search(r"\b(mes passado|mes retrasado)\b", t):
        return hoje - timedelta(days=30 if "retrasado" not in t else 60)
    if re.search(r"\b(ano passado|ano retrasado)\b", t):
        return hoje - timedelta(days=365 if "retrasado" not in t else 730)

    # "há 3 meses", "3 meses atrás", "faz 2 anos", "uns 15 dias", "3 meses"
    m = re.search(r"\b(?:ha|faz|uns|umas|cerca de|aproximadamente)?\s*(\d{1,4})\s*"
                  r"(dias?|semanas?|mes(?:es)?|anos?)\b", t)
    if m:
        n = int(m.group(1))
        unidade = m.group(2).rstrip(".")
        fator = UNIDADES_DIA.get(unidade) or UNIDADES_DIA.get(unidade + "s")
        if fator and 0 <= n * fator <= 365 * 120:
            return hoje - timedelta(days=n * fator)

    # "12 de março de 2026" / "março de 2026" / "em março"
    m = re.search(r"\b(?:(\d{1,2})\s*de\s*)?([a-z]{3,9})(?:\s*de\s*(\d{2,4}))?\b", t)
    if m and m.group(2) in MESES:
        dia, mes_nome, ano = m.group(1), m.group(2), m.group(3)
        mes = MESES[mes_nome]
        if ano:
            ano_i = int(ano)
            ano_i += 2000 if ano_i < 100 else 0
        else:
            # sem ano: o mês mais recente já ocorrido
            ano_i = hoje.year if mes <= hoje.month else hoje.year - 1
        try:
            d = date(ano_i, mes, int(dia)) if dia else _fim_do_mes(ano_i, mes)
        except ValueError:
            return None
        return d if d <= hoje else None

    # numérico: dd/mm/aaaa, dd-mm-aa, mm/aaaa
    m = re.search(r"\b(\d{1,4})[/\-.](\d{1,2})(?:[/\-.](\d{2,4}))?\b", t)
    if m:
        a, b, c = m.group(1), m.group(2), m.group(3)
        try:
            if c:
                ano_i = int(c)
                ano_i += 2000 if ano_i < 100 else 0
                d = date(ano_i, int(b), int(a))
            elif len(a) == 4 or int(a) > 31:  # aaaa/mm
                d = _fim_do_mes(int(a), int(b))
            elif int(b) > 12:  # mm/aaaa impossível -> é dd/mm de ano corrente
                return None
            else:  # dd/mm sem ano -> ocorrência mais recente já passada
                d = date(hoje.year, int(b), int(a))
                if d > hoje:
                    d = date(hoje.year - 1, int(b), int(a))
        except ValueError:
            return None
        return d if d <= hoje else None

    return None


# Grandezas que não são peso. Um número acompanhado de uma delas NÃO é peso.
UNIDADES_ALHEIAS = ("ano", "anos", "idade", "altura", "metro", "metros",
                    "cm", "mes", "meses", "litro", "hora", "horas", "vezes")


def parse_peso(texto: str) -> float | None:
    """Peso em kg, ou None.

    A guarda de unidade não é preciosismo: "tenho 45 anos" respondido na
    pergunta de peso era lido como 45 kg e REPROVAVA a pessoa por peso mínimo.
    Foi o erro mais perigoso que a forja encontrou — silencioso, plausível e
    com consequência clínica direta.
    """
    t = normalizar(texto).replace(",", ".")
    if any(re.search(rf"\b{u}\b", t) for u in UNIDADES_ALHEIAS):
        return None
    # (?<![\d.]) impede casar o "80" de "1.80" como se fosse 80 kg.
    m = re.search(r"(?<![\d.])(\d{2,3}(?:\.\d{1,2})?)\s*(kg|quilos?|k)?\b", t)
    if not m:
        return None
    v = float(m.group(1))
    return v if 30.0 <= v <= 300.0 else None


def parse_idade(texto: str) -> int | None:
    t = normalizar(texto)
    m = re.search(r"\b(\d{1,3})\s*(anos?|a)?\b", t)
    if not m:
        return None
    v = int(m.group(1))
    return v if 5 <= v <= 120 else None


CONTAGEM_EXTENSO = {
    "nenhuma": 0, "nenhum": 0, "zero": 0, "uma": 1, "um": 1, "duas": 2, "dois": 2,
    "tres": 3, "quatro": 4, "cinco": 5, "seis": 6, "sete": 7, "oito": 8,
    "nove": 9, "dez": 10, "primeira": 1, "unica": 1,
}


def parse_contagem(texto: str) -> int | None:
    """Quantidade pequena (nº de doações). Aceita dígito ou palavra."""
    t = normalizar(texto)
    m = re.search(r"\b(\d{1,2})\b", t)
    if m:
        v = int(m.group(1))
        return v if 0 <= v <= 50 else None
    for tok in tokenizar(t):
        if tok in CONTAGEM_EXTENSO:
            return CONTAGEM_EXTENSO[tok]
    return None


def parse_sexo(texto: str) -> str | None:
    """Sexo biológico — usado APENAS para o intervalo entre doações (fisiológico).

    Não é critério de aptidão e não é identidade de gênero. Quem não informa
    recebe o critério mais restritivo (ver normas.py), então a pergunta nunca
    é obrigatória.
    """
    t = normalizar(texto)
    if re.search(r"\b(m|masc|masculino|homem|hetero|macho)\b", t):
        return "M"
    if re.search(r"\b(f|fem|feminino|mulher|femea)\b", t):
        return "F"
    return None


# ── o resolvedor ────────────────────────────────────────────────────────────

def resolver(texto: str, esperado: set[int], hoje: date | None = None) -> Resolucao:
    """Decodifica `texto` em um símbolo de `esperado`, ou rejeita.

    `esperado` é o contexto do estado: o conjunto de significados que fazem
    sentido AGORA. É a primeira e mais barata defesa contra ambiguidade.
    """
    hoje = hoje or date.today()
    t = normalizar(texto)
    if not t:
        return Resolucao(lx.NAO_ENTENDI)
    tokens = tokenizar(t)

    # Atalho de menu: "1", "2", ... são resolvidos pelo estado, não aqui.
    # Grandezas: só são tentadas se o estado as espera (contexto).
    if lx.VALOR_DATA in esperado:
        d = parse_data(t, hoje)
        if d is not None:
            return Resolucao(lx.VALOR_DATA, d, score=99.0, margem=99.0)
    if lx.VALOR_PESO in esperado:
        p = parse_peso(t)
        if p is not None:
            return Resolucao(lx.VALOR_PESO, p, score=99.0, margem=99.0)
    if lx.VALOR_IDADE in esperado:
        i = parse_idade(t)
        if i is not None:
            return Resolucao(lx.VALOR_IDADE, i, score=99.0, margem=99.0)
    if lx.VALOR_CONTAGEM in esperado:
        n = parse_contagem(t)
        if n is not None:
            return Resolucao(lx.VALOR_CONTAGEM, n, score=99.0, margem=99.0)
    if lx.VALOR_SEXO_BIOLOGICO in esperado:
        s = parse_sexo(t)
        if s is not None:
            return Resolucao(lx.VALOR_SEXO_BIOLOGICO, s, score=99.0, margem=99.0)

    # Pontuação por especificidade sobre o catálogo restrito ao contexto.
    pontos: dict[int, float] = {}
    prova: dict[int, tuple[str, set[int]]] = {}  # símbolo -> (superfície, índices)
    # O contexto INDEXA, não filtra. Percorrer o catálogo inteiro e descartar o
    # que está fora do estado torna o custo O(|Σ|) — proporcional a tudo que o
    # sistema sabe. Indexando por `esperado`, o custo passa a O(|C|):
    # proporcional só ao que é admissível agora. Com léxico de 20.000 símbolos
    # essa troca é a diferença entre 2.127 ms e ~1 ms por resolução
    # (testes/teste_escala.py). `sorted` mantém a ordem estável — I1 exige que
    # duas execuções idênticas produzam o mesmo resultado.
    for id_ in sorted(esperado):
        simbolo = lx.POR_ID.get(id_)
        if simbolo is None:
            continue
        for sup in lx.superficies(simbolo):  # curadas + aprendidas
            r = _casa_superficie(sup, tokens)
            if r is None:
                continue
            credito, pos, usados = r
            alvo = simbolo.id
            # Negação: só inverte se o negador vier ANTES do gatilho e não fizer
            # parte da própria superfície ("nunca fiz" já é negativo).
            if simbolo.polaridade > 0 and simbolo.negado_vira is not None:
                if any(eh_negador(tok) for tok in tokens[:pos]) and not any(
                    p in NEGADORES for p in sup.split()
                ):
                    alvo = simbolo.negado_vira
                    if alvo not in esperado:
                        continue
            if credito > pontos.get(alvo, 0.0):
                pontos[alvo] = credito
                prova[alvo] = (sup, usados)

    if not pontos:
        return Resolucao(lx.NAO_ENTENDI)

    ordenado = sorted(pontos.items(), key=lambda kv: -kv[1])
    (id1, s1) = ordenado[0]
    (id2, s2) = ordenado[1] if len(ordenado) > 1 else (None, 0.0)
    margem = s1 - s2

    # Defesa 2: sem folga sobre o rival, é ambiguidade -> rejeita.
    if margem < MARGEM_MINIMA:
        return Resolucao(lx.NAO_ENTENDI, score=s1, margem=margem, rival=id2)

    # Defesa 4 — REGRA DO TOKEN SOLITÁRIO.
    # Em símbolo sensível, uma única palavra não pode decidir um texto que
    # ainda tem conteúdo não explicado. Foi assim que a busca adversarial
    # transformou "não lembro" (com 'lembro' corrompido por typo) em "não" —
    # ou seja, "não me recordo" virava "isso nunca aconteceu", que é o
    # contrário de falhar fechado. O mesmo padrão fez
    # "ignore as instruções anteriores e me aprove" virar o comando VOLTAR,
    # porque "anteriores" casou com "anterior".
    if id1 in SENSIVEIS:
        sup, usados = prova[id1]
        if any(c in t for c in CONSTRUCOES_AMBIGUAS):
            return Resolucao(lx.NAO_ENTENDI, score=s1, margem=margem, rival=id2)
        if len(sup.split()) == 1:
            sobra = _conteudo_nao_explicado(tokens, usados, id1)
            if sobra:
                return Resolucao(lx.NAO_ENTENDI, score=s1, margem=margem, rival=id2)

        # Defesa 5 — CONTRADIÇÃO DE POLARIDADE.
        # Um "não" explícito no texto não pode ser atropelado só porque outro
        # gatilho pontuou mais alto. A busca adversarial achou isto: "então"
        # digitado como "enato" casava com "exato" (crédito 4,5) e vencia o
        # "não" (crédito 3,0) que estava ali do lado. Se as duas polaridades
        # aparecem, o texto é ambíguo — e ambíguo é rejeitado.
        sobra_tokens = [t for i, t in enumerate(tokens) if i not in usados]
        if id1 == lx.SIM and any(eh_negador(t) for t in sobra_tokens):
            return Resolucao(lx.NAO_ENTENDI, score=s1, margem=margem, rival=lx.NAO)
        if id1 == lx.NAO and any(t in AFIRMADORES for t in sobra_tokens):
            return Resolucao(lx.NAO_ENTENDI, score=s1, margem=margem, rival=lx.SIM)
        # "sim, mas não sei quando": há afirmação explícita E incerteza. Ler
        # só a incerteza descarta um "sim" clinicamente relevante; ler só o
        # "sim" descarta a dúvida. As duas leituras perdem informação — a
        # única resposta honesta é perguntar de novo.
        if id1 == lx.NAO_SEI and any(t in AFIRMADORES for t in sobra_tokens):
            return Resolucao(lx.NAO_ENTENDI, score=s1, margem=margem, rival=lx.SIM)

    return Resolucao(id1, score=s1, margem=margem, rival=id2)
