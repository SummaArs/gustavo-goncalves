"""
HEMOS — Ontologia: criar conhecimento que ninguém programou.

O aprendiz (aprendiz.py) aprende FORMAS NOVAS de dizer coisas que o sistema já
conhece. Isso é útil, mas não é criação — o espaço de significados continua o
mesmo. Aqui é o outro mecanismo: gerar SIGNIFICADO novo por composição.

O argumento
───────────
Ninguém vai conseguir listar todo procedimento estético que existe. Ano que vem
aparece um nome que hoje não existe. Um LLM lidaria com isso por analogia
estatística — e erraria em silêncio.

A saída determinística é a que o Gustavo já usa na arquitetura dele: **grafo**.
Não se enumera o mundo, enumera-se a ESTRUTURA do mundo. "Microagulhamento" não
precisa estar numa lista: ele é um *procedimento com agulha na pele*, e a norma
não fala de tatuagem — fala de **exposição percutânea**. A carência é da classe,
não do termo.

    termo desconhecido ──morfologia──► classe ──herança──► carência da norma

Isso é criação genuína: o sistema responde certo sobre um evento que não estava
no seu código, e a resposta é derivável e auditável. O espaço coberto deixa de
ser a lista que alguém digitou e passa a ser o FECHO da ontologia.

Onde está o limite, dito com todas as letras
────────────────────────────────────────────
A composição gera estrutura nova, não informação nova. O sistema só cobre o que
o fecho da ontologia alcança — se aparecer um procedimento de risco que não é
percutâneo nem endoscópico, nenhuma engenhosidade o deduz. Por isso a
classificação aqui **PROPÕE, nunca decide**: vira lacuna no relatório do doador
e item numa fila de revisão do médico responsável. O que a máquina cria é
hipótese; quem homologa é gente.

E por que morfologia e não similaridade
───────────────────────────────────────
No Herus ficou provado que semelhança de superfície mente ("gtao" não
compartilha bigrama com "gato"). Aqui o casamento NÃO é por similaridade: é por
RADICAL, que é estrutura linguística real — "microagulhamento" contém
"agulh" porque é sobre agulha, não por coincidência de letras. Ainda assim há
falsos positivos possíveis, e por isso existe a lista de exclusões e o teste que
a persegue.
"""

from __future__ import annotations

from dataclasses import dataclass

import lexico as lx
import normas
import resolvedor as rv


@dataclass(frozen=True)
class Classe:
    nome: str
    evento_base: int  # de qual evento a classe herda a carência
    radicais: tuple[str, ...]
    justificativa: str


CLASSES: tuple[Classe, ...] = (
    Classe(
        "exposicao_percutanea", lx.EV_TATUAGEM,
        ("tatu", "piercing", "pearcing", "pigment", "agulh", "preenchim",
         "botox", "toxina", "alargador", "brinco", "escarific", "acupuntur",
         "mesoterap", "microlanc"),
        "procedimento que rompe a pele com material perfurante — a norma trata "
        "pela exposição percutânea, não pelo nome do procedimento",
    ),
    Classe(
        "instrumentacao_endoscopica", lx.EV_ENDOSCOPIA,
        ("endoscop", "colonoscop", "broncoscop", "laringoscop", "artroscop",
         "histeroscop", "cistoscop", "retossigmoid"),
        "exame com endoscópio flexível ou instrumentação de cavidade",
    ),
    Classe(
        "vacina_viva_atenuada", lx.EV_VACINA_ATENUADA,
        ("febre amarela", "triplice", "tetra viral", "sarampo", "caxumba",
         "rubeola", "varicela", "catapora", "bcg", "rotavirus", "qdenga"),
        "vacina de vírus vivo atenuado",
    ),
)

# Falsos amigos: parecem da classe pela forma, mas não são pelo mecanismo.
# Cada exclusão aqui é uma correção clínica, não um detalhe de implementação.
EXCLUSOES: dict[str, str] = {
    "henna": "tatuagem de henna é superficial, não rompe a pele",
    "tatuagem de henna": "não é percutânea",
    "adesivo": "não rompe a pele",
    "maquiagem comum": "não é definitiva nem percutânea",
    "gripe": "vacina de gripe é inativada, não atenuada",
    "tetano": "vacina inativada",
    "hepatite b": "vacina inativada",
}


@dataclass(frozen=True)
class Proposta:
    termo: str
    classe: Classe
    carencia_dias: float
    fonte: str

    @property
    def texto(self) -> str:
        return (f"'{self.termo}' foi classificado como *{self.classe.nome}* "
                f"({self.classe.justificativa}), herdando carência de "
                f"{int(self.carencia_dias)} dias — {self.fonte}. "
                "PROPOSTA: requer confirmação do médico responsável.")


# Radicais acrescentados pela forja (destilação de LLM). Ficam separados dos
# curados pelo mesmo motivo de lexico.EXTRAS: dá para auditar e descartar tudo
# que veio de máquina sem tocar no que uma pessoa escreveu.
RADICAIS_EXTRA: dict[str, list[str]] = {}


def estender(classe: Classe, radical: str) -> None:
    """Acrescenta um radical vindo da forja. Nunca cria classe nem carência."""
    lista = RADICAIS_EXTRA.setdefault(classe.nome, [])
    if radical not in lista:
        lista.append(radical)


def _radicais(classe: Classe) -> tuple[str, ...]:
    return classe.radicais + tuple(RADICAIS_EXTRA.get(classe.nome, ()))


def _conhecido(forma: str) -> bool:
    """Já existe no léxico curado? Então não é termo novo."""
    for s in lx.CATALOGO:
        for sup in lx.superficies(s):
            if forma == rv.normalizar(sup):
                return True
    return False


def classificar(termo: str) -> Proposta | None:
    """Termo desconhecido -> proposta de classe + carência herdada.

    Devolve None quando não há classe aplicável. Silêncio é a resposta correta
    para o que a ontologia não alcança — inventar classe seria o erro que a
    arquitetura inteira existe para evitar.
    """
    forma = rv.normalizar(termo)
    if not forma:
        return None
    for chave, _motivo in EXCLUSOES.items():
        if chave in forma:
            return None
    for classe in CLASSES:
        for radical in _radicais(classe):
            if radical in forma:
                par = normas.CARENCIA[classe.evento_base]
                return Proposta(termo, classe, par.dias, par.fonte)
    return None


def fecho_estimado() -> int:
    """Quantos radicais distintos a ontologia cobre.

    Não é o número de termos cobertos — esse é ilimitado, porque cada radical
    casa com uma família aberta de palavras. É esse o ponto: o sistema deixa de
    cobrir uma lista e passa a cobrir uma estrutura.
    """
    return sum(len(c.radicais) for c in CLASSES)
