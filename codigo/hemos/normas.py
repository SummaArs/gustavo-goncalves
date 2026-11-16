"""
HEMOS — Normas: a camada que DECIDE. Nenhum modelo estatístico entra aqui.

A álgebra
─────────
Toda a triagem colapsa numa fórmula só, porque toda pergunta do roteiro é
"quando foi a última vez?" (ver conversa.py):

    libera_em = max_i ( evento_i + carência_i )        APTO ⟺ libera_em ≤ hoje

Impedimento definitivo é apenas carência = ∞. Critérios de estado (peso,
idade) entram como bloqueios sem data.

O veredito vive num reticulado com ordem   APTO < TEMPORÁRIO < DEFINITIVO,
e a combinação de regras é o *join* (supremo). Isso dá de graça a propriedade
que mais importa num sistema clínico:

    MONOTONICIDADE DE SEGURANÇA
    acrescentar um evento clínico ao conjunto de fatos jamais pode tornar o
    veredito mais permissivo.

Ela é verdadeira por construção — cada regra é avaliada de forma independente
e o resultado final é a UNIÃO dos motivos, e união só cresce. O arnês em
testes/adversario.py tenta refutá-la mesmo assim, por busca.

(Exceção declarada e testada: fatos de *qualificação* — sexo biológico, data de
nascimento — refinam o critério em vez de acrescentá-lo, e podem relaxar. Ex.:
quem não informa sexo recebe o intervalo mais restritivo, 90 dias. Por isso a
invariante é enunciada sobre EVENTOS, não sobre fatos em geral.)

Fonte dos parâmetros
────────────────────
RDC Anvisa nº 34/2014 e Portaria de Consolidação nº 5/2017 (Anexo IV) do
Ministério da Saúde, com as práticas correntes dos hemocentros brasileiros.
Os valores abaixo são PADRÕES DE PARTIDA: cada serviço de hemoterapia tem
autonomia técnica sobre parte deles. Todo parâmetro carrega `homologado=False`
até que o médico responsável do hemocentro assine — e o relatório mostra isso.
Ver a invariante "toda regra cita fonte" em testes/teste_normas.py.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta

import lexico as lx

INF = math.inf


class _Desconhecido:
    """Marca uma resposta 'não sei'. NÃO é o mesmo que 'nunca aconteceu'.

    Tratar dúvida como ausência de evento seria liberar por falta de
    informação — exatamente o contrário de falhar fechado. Aqui ela vira
    LACUNA: não gera impedimento (seria injusto reprovar quem foi honesto ao
    dizer que não lembra), mas impede o sistema de afirmar aptidão plena, e
    aparece nominalmente para a triagem presencial confirmar.
    """

    def __repr__(self) -> str:  # pragma: no cover
        return "DESCONHECIDO"


DESCONHECIDO = _Desconhecido()

APTO, TEMPORARIO, DEFINITIVO = 0, 1, 2
ROTULO_NIVEL = {APTO: "APTO", TEMPORARIO: "INAPTO TEMPORÁRIO", DEFINITIVO: "INAPTO DEFINITIVO"}


@dataclass(frozen=True)
class Parametro:
    dias: float
    fonte: str
    descricao: str
    homologado: bool = False


# ── carências (evento -> dias) ──────────────────────────────────────────────
CARENCIA: dict[int, Parametro] = {
    lx.EV_TATUAGEM: Parametro(
        180, "RDC 34/2014; prática corrente dos hemocentros",
        "tatuagem, piercing ou maquiagem definitiva"),
    lx.EV_CIRURGIA_MENOR: Parametro(
        90, "RDC 34/2014", "cirurgia de pequeno porte"),
    lx.EV_CIRURGIA_MAIOR: Parametro(
        180, "RDC 34/2014", "cirurgia de grande porte"),
    lx.EV_GRIPE: Parametro(
        7, "RDC 34/2014", "gripe, resfriado ou febre (contado do fim dos sintomas)"),
    lx.EV_COVID_SINTOMAS: Parametro(
        30, "Nota Técnica MS/Anvisa sobre COVID-19 em hemoterapia",
        "COVID-19 (contado da recuperação)"),
    lx.EV_DENTISTA_EXTRACAO: Parametro(
        7, "RDC 34/2014", "extração dentária ou tratamento de canal"),
    lx.EV_ENDOSCOPIA: Parametro(
        180, "RDC 34/2014", "endoscopia, colonoscopia ou exame com endoscópio flexível"),
    lx.EV_TRANSFUSAO: Parametro(
        365, "RDC 34/2014", "transfusão de sangue ou hemocomponentes"),
    lx.EV_VACINA_INATIVADA: Parametro(
        2, "RDC 34/2014", "vacina inativada (gripe, COVID inativada, tétano)"),
    lx.EV_VACINA_ATENUADA: Parametro(
        28, "RDC 34/2014", "vacina de vírus vivo atenuado (febre amarela, tríplice viral)"),
    lx.EV_PARTO: Parametro(
        90, "RDC 34/2014", "parto normal"),
    lx.EV_PARTO_CESAREA: Parametro(
        180, "RDC 34/2014", "parto cesáreo"),
    lx.EV_ALCOOL: Parametro(
        1, "RDC 34/2014 (12 horas; arredondado para 1 dia)",
        "consumo de bebida alcoólica"),
    lx.EV_AREA_MALARIA: Parametro(
        365, "RDC 34/2014; Guia de Vigilância em Saúde (malária)",
        "permanência em área endêmica de malária"),
    lx.EV_ANTIBIOTICO: Parametro(
        14, "RDC 34/2014 (contado do término do tratamento)",
        "uso de antibiótico"),
    # definitivos
    lx.EV_HEPATITE_APOS_11: Parametro(
        INF, "RDC 34/2014", "hepatite após os 11 anos de idade"),
    lx.EV_DOENCA_CHAGAS: Parametro(
        INF, "RDC 34/2014", "doença de Chagas"),
    # Presentes no léxico mas FORA do roteiro de WhatsApp — ver conversa.py.
    lx.EV_DROGA_INJETAVEL: Parametro(
        INF, "RDC 34/2014", "uso de droga ilícita injetável"),
    lx.EV_EXPOSICAO_RISCO: Parametro(
        365, "RDC 34/2014 conforme ADI 5543/STF (critério comportamental, "
             "avaliado em entrevista confidencial presencial)",
        "situação de exposição de risco"),
}

# ── critérios de estado ─────────────────────────────────────────────────────
PESO_MINIMO = Parametro(50.0, "RDC 34/2014", "peso mínimo de 50 kg")
IDADE_MINIMA = Parametro(16, "RDC 34/2014 / Portaria de Consolidação nº 5/2017",
                         "idade mínima de 16 anos (16 e 17 exigem consentimento formal "
                         "do responsável, presente no ato)")
IDADE_MAXIMA = Parametro(69, "RDC 34/2014", "idade máxima de 69 anos, 11 meses e 29 dias")
IDADE_MAXIMA_PRIMEIRA = Parametro(60, "RDC 34/2014",
                                  "primeira doação somente até 60 anos incompletos")
INTERVALO = {
    "M": Parametro(60, "RDC 34/2014", "intervalo mínimo de 60 dias entre doações"),
    "F": Parametro(90, "RDC 34/2014", "intervalo mínimo de 90 dias entre doações"),
}
FREQUENCIA_ANUAL = {
    "M": Parametro(4, "RDC 34/2014", "máximo de 4 doações em 12 meses"),
    "F": Parametro(3, "RDC 34/2014", "máximo de 3 doações em 12 meses"),
}
# Quem não informa sexo biológico recebe o critério mais restritivo: falha
# fechada. A pergunta nunca precisa ser obrigatória.
SEXO_PADRAO = "F"


@dataclass(frozen=True)
class Motivo:
    codigo: str
    nivel: int
    texto: str
    fonte: str
    libera_em: date | None = None  # None = depende de mudança de condição
    homologado: bool = False


@dataclass(frozen=True)
class Veredito:
    motivos: tuple[Motivo, ...] = ()
    condicoes: tuple[str, ...] = ()  # apto, porém com exigência (ex.: responsável)
    lacunas: tuple[str, ...] = ()  # perguntas respondidas com "não sei"

    @property
    def nivel(self) -> int:
        return max((m.nivel for m in self.motivos), default=APTO)

    @property
    def libera_em(self) -> date | None:
        """Data em que TODOS os impedimentos temporais terão vencido."""
        if self.nivel == DEFINITIVO:
            return None
        datas = [m.libera_em for m in self.motivos if m.libera_em]
        return max(datas) if datas else None

    @property
    def indeterminado(self) -> bool:
        """Há impedimento sem data (ex.: peso) — depende do doador, não do tempo."""
        return any(m.libera_em is None and m.nivel == TEMPORARIO for m in self.motivos)

    @property
    def rotulo(self) -> str:
        return ROTULO_NIVEL[self.nivel]

    @property
    def conclusivo(self) -> bool:
        """Sem lacunas, o sistema pode afirmar aptidão. Com elas, só indicar."""
        return not self.lacunas

    def unir(self, outro: "Veredito") -> "Veredito":
        """Join do reticulado: união de motivos. Só cresce -> monotônico."""
        return Veredito(self.motivos + outro.motivos,
                        self.condicoes + outro.condicoes,
                        self.lacunas + outro.lacunas)


APTIDAO_PLENA = Veredito()


def _anos_completos(nascimento: date, hoje: date) -> int:
    return hoje.year - nascimento.year - ((hoje.month, hoje.day) < (nascimento.month, nascimento.day))


def _aniversario(nascimento: date, idade: int) -> date:
    """Data em que a pessoa completa `idade` anos (trata 29/02)."""
    try:
        return nascimento.replace(year=nascimento.year + idade)
    except ValueError:
        return nascimento.replace(year=nascimento.year + idade, day=28)


def avaliar(fatos: dict[int, object], hoje: date | None = None) -> Veredito:
    """Fatos (ids -> valores) -> veredito. Determinístico e puro.

    Convenções de `fatos`:
      - chave ausente  = não perguntado (não gera motivo, gera lacuna)
      - valor None     = "nunca aconteceu" / não se aplica
      - date           = data do evento
    """
    hoje = hoje or date.today()
    v = APTIDAO_PLENA

    # ── 1. carências temporais: o max( evento + carência ) da tese ──────────
    for evento, par in CARENCIA.items():
        quando = fatos.get(evento)
        if quando is DESCONHECIDO:
            v = v.unir(Veredito(lacunas=(par.descricao,)))
            continue
        if not isinstance(quando, date):
            continue
        if par.dias == INF:
            v = v.unir(Veredito((Motivo(
                f"CAR-{lx.nome(evento)}", DEFINITIVO,
                f"Impedimento definitivo: {par.descricao}.",
                par.fonte, None, par.homologado),)))
            continue
        libera = quando + timedelta(days=int(par.dias))
        if libera > hoje:
            v = v.unir(Veredito((Motivo(
                f"CAR-{lx.nome(evento)}", TEMPORARIO,
                f"{par.descricao.capitalize()}: carência de {int(par.dias)} dias.",
                par.fonte, libera, par.homologado),)))

    # ── 2. idade (a partir da data de nascimento: dá data exata) ────────────
    nasc = fatos.get(lx.VALOR_NASCIMENTO)
    if isinstance(nasc, date):
        idade = _anos_completos(nasc, hoje)
        if idade < IDADE_MINIMA.dias:
            v = v.unir(Veredito((Motivo(
                "IDADE-MIN", TEMPORARIO,
                f"Idade mínima para doar é {int(IDADE_MINIMA.dias)} anos.",
                IDADE_MINIMA.fonte, _aniversario(nasc, int(IDADE_MINIMA.dias)),
                IDADE_MINIMA.homologado),)))
        elif idade < 18:
            v = v.unir(Veredito((), (
                "Doador com 16 ou 17 anos: é obrigatória a autorização formal do "
                "responsável legal, que deve estar presente no ato da doação.",)))
        if idade > IDADE_MAXIMA.dias:
            v = v.unir(Veredito((Motivo(
                "IDADE-MAX", DEFINITIVO,
                f"Idade acima do limite de {int(IDADE_MAXIMA.dias)} anos, "
                "11 meses e 29 dias.", IDADE_MAXIMA.fonte, None,
                IDADE_MAXIMA.homologado),)))
        elif fatos.get(lx.EV_ULTIMA_DOACAO, "?") is None and idade >= IDADE_MAXIMA_PRIMEIRA.dias:
            # Nunca doou e já passou de 60: a primeira doação não é permitida.
            v = v.unir(Veredito((Motivo(
                "IDADE-1A", DEFINITIVO,
                f"A primeira doação só é permitida até {int(IDADE_MAXIMA_PRIMEIRA.dias)} "
                "anos incompletos.", IDADE_MAXIMA_PRIMEIRA.fonte, None,
                IDADE_MAXIMA_PRIMEIRA.homologado),)))

    # ── 3. peso ─────────────────────────────────────────────────────────────
    peso = fatos.get(lx.VALOR_PESO)
    if isinstance(peso, (int, float)) and peso < PESO_MINIMO.dias:
        v = v.unir(Veredito((Motivo(
            "PESO-MIN", TEMPORARIO,
            f"Peso mínimo para doar é {PESO_MINIMO.dias:.0f} kg.",
            PESO_MINIMO.fonte, None, PESO_MINIMO.homologado),)))

    # ── 4. intervalo e frequência (dependem do sexo biológico) ──────────────
    sexo = fatos.get(lx.VALOR_SEXO_BIOLOGICO)
    sexo = sexo if sexo in INTERVALO else SEXO_PADRAO  # falha fechada
    ultima = fatos.get(lx.EV_ULTIMA_DOACAO)
    if isinstance(ultima, date):
        par = INTERVALO[sexo]
        libera = ultima + timedelta(days=int(par.dias))
        if libera > hoje:
            v = v.unir(Veredito((Motivo(
                "INTERVALO", TEMPORARIO, par.descricao.capitalize() + ".",
                par.fonte, libera, par.homologado),)))
        n = fatos.get(lx.VALOR_DOACOES_12M)
        teto = FREQUENCIA_ANUAL[sexo]
        if isinstance(n, int) and n >= teto.dias:
            # Conservador: sem o histórico completo, libera 12 meses após a
            # última doação conhecida. Documentado como aproximação segura.
            v = v.unir(Veredito((Motivo(
                "FREQ-ANUAL", TEMPORARIO,
                f"Limite de {int(teto.dias)} doações em 12 meses já atingido.",
                teto.fonte, ultima + timedelta(days=365), teto.homologado),)))

    # ── 5. estados gestacionais ─────────────────────────────────────────────
    if fatos.get(lx.EV_GESTACAO_ATUAL) is True:
        v = v.unir(Veredito((Motivo(
            "GESTACAO", TEMPORARIO, "Gestação em curso.", "RDC 34/2014", None),)))
    if fatos.get(lx.EV_AMAMENTACAO) is True:
        v = v.unir(Veredito((Motivo(
            "AMAMENTACAO", TEMPORARIO,
            "Amamentação (impedimento até 12 meses após o parto).",
            "RDC 34/2014", None),)))

    return v


def lacunas(fatos: dict[int, object], roteiro: tuple[int, ...]) -> tuple[int, ...]:
    """Perguntas do roteiro ainda sem resposta (inclusive as respondidas com
    'não sei' — que ficam como lacuna, nunca como 'não')."""
    return tuple(p for p in roteiro if p not in fatos)
