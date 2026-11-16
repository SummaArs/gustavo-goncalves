"""
HEMOS — Léxico semântico (o "codebook").

Ideia herdada do Herus: não se transmite a FORMA, transmite-se o SIGNIFICADO.
Lá, um id de 2 bytes num léxico compartilhado substitui o áudio. Aqui, um id
substitui o texto do doador: a partir do resolvedor, NADA no sistema vê string
em português — máquina de estados, regras e log operam só sobre ids.

Consequências (as mesmas do Herus):
  1. Não é preciso LLM. O espaço de significados de uma triagem é finito e
     conhecido (~50 símbolos). Mapear entrada suja -> significado num espaço
     finito é tabela + distância, não modelo estatístico.
  2. Tradução/canal saem de graça: espanhol, áudio transcrito, botão do
     WhatsApp e totem da recepção produzem o MESMO id. Só muda `superficies`.
  3. Privacidade semântica (LGPD art. 11 — dado de saúde é sensível): o log
     auditável da decisão é uma sequência de ids; o texto do doador não
     precisa ser persistido em lugar nenhum.

CONTRATO DE ID (regra de protocolo, igual ao Herus):
  - id é estável e público. Uma vez atribuído, NUNCA é reutilizado para outro
    significado, mesmo que o símbolo seja aposentado. Log antigo tem que
    continuar decodificando.
  - Faixas:
      0x00xx  controle da conversa
      0x01xx  respostas genéricas (sim / não / não sei / nunca)
      0x02xx  intenções (agendar, horário, endereço, ...)
      0x03xx  eventos clínicos com data (o coração da triagem)
      0x04xx  grandezas com valor (peso, idade, data)
"""

from dataclasses import dataclass, field


# ── controle ────────────────────────────────────────────────────────────────
NAO_ENTENDI = 0x0001  # zona de rejeição: o resolvedor se recusa a adivinhar
VOLTAR = 0x0002
PARAR = 0x0003
HUMANO = 0x0004
REPETIR = 0x0005

# ── respostas genéricas ─────────────────────────────────────────────────────
SIM = 0x0101
NAO = 0x0102
NAO_SEI = 0x0103
NUNCA = 0x0104  # "nunca aconteceu" — distinto de "não" para eventos com data

# ── intenções ───────────────────────────────────────────────────────────────
QUERO_DOAR = 0x0201
QUERO_AGENDAR = 0x0202
QUERO_HORARIOS = 0x0203
QUERO_ENDERECO = 0x0204
QUERO_DOCUMENTOS = 0x0205
QUERO_CANCELAR = 0x0206
QUERO_ESTOQUE = 0x0207
QUERO_RESULTADO = 0x0208

# ── grandezas ───────────────────────────────────────────────────────────────
VALOR_PESO = 0x0401  # payload: kg (float)
VALOR_IDADE = 0x0402  # payload: anos (int)
VALOR_DATA = 0x0403  # payload: datetime.date
VALOR_SEXO_BIOLOGICO = 0x0404  # payload: "M" | "F"  (critério fisiológico de
#                                intervalo entre doações — NÃO é identidade
#                                de gênero e NÃO é critério de aptidão)
VALOR_DOACOES_12M = 0x0405  # payload: int (nº de doações nos últimos 12 meses)
VALOR_NASCIMENTO = 0x0406  # payload: date (preferido sobre VALOR_IDADE:
#                            permite calcular a data exata de liberação)
VALOR_CONTAGEM = 0x0407  # payload: int >= 0 (quantidade pequena, ex.: nº de
#                          doações). Separado de VALOR_IDADE de propósito: a
#                          idade tem faixa plausível 5..120, e reusar o mesmo
#                          parser tornava "1 doação" indecifrável.


@dataclass(frozen=True)
class Simbolo:
    """Um significado. `superficies` é a única parte que fala português."""

    id: int
    nome: str
    superficies: tuple[str, ...] = ()
    renderizacao: str = ""  # como o significado volta a virar texto
    polaridade: int = 0  # +1 afirmativo, -1 negativo, 0 neutro
    # Símbolo afirmativo negado vira este id (ex.: "não" + "sim" -> NAO).
    negado_vira: int | None = None


def _s(id_, nome, superficies, renderizacao="", polaridade=0, negado_vira=None):
    return Simbolo(id_, nome, tuple(superficies), renderizacao or nome, polaridade, negado_vira)


# Ordem NÃO importa para o resultado (o resolvedor pontua por especificidade),
# mas superfícies longas vencem curtas — por isso "nao sei" convive com "nao".
CATALOGO: tuple[Simbolo, ...] = (
    # controle
    _s(VOLTAR, "VOLTAR", ["voltar", "volta", "anterior", "corrigir", "errei"], "voltar"),
    _s(PARAR, "PARAR", ["parar", "sair", "cancelar tudo", "desistir", "encerrar"], "encerrar"),
    _s(HUMANO, "HUMANO", ["atendente", "humano", "pessoa", "falar com alguem",
                          "falar com uma pessoa", "quero falar com atendente"], "atendente"),
    _s(REPETIR, "REPETIR", ["repetir", "de novo", "nao entendi a pergunta",
                            "pode repetir", "como assim"], "repetir"),
    # respostas
    # ASSIMETRIA DE RISCO — decisão de projeto, não descuido.
    # Verbos neutros ("tive", "fiz", "tenho", "já") NÃO são gatilho de SIM.
    # A distância entre "tive" e "não tive" é uma única palavra: basta um typo
    # comer o negador para a resposta inverter de sentido. A busca adversarial
    # achou exatamente isso ('nãoo tivee' -> SIM). Só entram aqui formas que já
    # são afirmativas por si mesmas. Quem escrever só "tive" cai no menu — custo
    # baixo, e um falso SIM numa triagem clínica não tem o mesmo preço que um
    # pedido de esclarecimento.
    _s(SIM, "SIM", ["sim", "s", "isso", "positivo", "com certeza", "afirmativo",
                    "aham", "uhum", "claro", "confirmo", "isso mesmo",
                    "sim tenho", "sim ja", "yes"],
       # "exato" foi removido: fica a uma edição de "então" ("enato" -> SIM),
       # que é recheio conversacional comuníssimo. Gatilho barato de escrever,
       # caro de errar. As formas restantes cobrem o mesmo sentido.
       "sim", polaridade=+1, negado_vira=NAO),
    _s(NAO, "NAO", ["nao", "n", "negativo", "nunca tive", "nunca fiz", "jamais",
                    "nenhum", "nenhuma", "de jeito nenhum", "nao tenho", "nao fiz",
                    "nao tive", "nada disso", "no"], "não", polaridade=-1),
    _s(NAO_SEI, "NAO_SEI", ["nao sei", "nao lembro", "nao me recordo", "nao tenho certeza",
                            "acho que sim", "acho que nao", "talvez", "sei la",
                            "nao faco ideia", "duvida"], "não sei"),
    _s(NUNCA, "NUNCA", ["nunca", "nunca aconteceu", "jamais aconteceu", "nunca na vida",
                        "nao se aplica", "nao aplica", "n/a"], "nunca"),
    # intenções
    _s(QUERO_DOAR, "QUERO_DOAR", ["quero doar", "doar sangue", "doacao", "quero doar sangue",
                                  "posso doar", "gostaria de doar", "sou doador",
                                  "quero ser doador", "doar"], "doar sangue"),
    _s(QUERO_AGENDAR, "QUERO_AGENDAR", ["agendar", "marcar", "agendamento", "marcar horario",
                                        "quero marcar", "agenda"], "agendar"),
    _s(QUERO_HORARIOS, "QUERO_HORARIOS", ["horario", "horarios", "que horas", "funciona ate",
                                          "abre que horas", "expediente", "atendimento"],
       "horários"),
    _s(QUERO_ENDERECO, "QUERO_ENDERECO", ["endereco", "onde fica", "localizacao", "como chegar",
                                          "onde e", "rua", "mapa"], "endereço"),
    _s(QUERO_DOCUMENTOS, "QUERO_DOCUMENTOS", ["documento", "documentos", "o que levar",
                                              "preciso levar", "rg", "identidade"], "documentos"),
    _s(QUERO_CANCELAR, "QUERO_CANCELAR", ["cancelar agendamento", "desmarcar", "cancelar minha",
                                          "nao vou poder ir", "remarcar"], "cancelar agendamento"),
    _s(QUERO_ESTOQUE, "QUERO_ESTOQUE", ["estoque", "precisa de sangue", "qual tipo falta",
                                        "esta faltando", "campanha"], "estoque"),
    _s(QUERO_RESULTADO, "QUERO_RESULTADO", ["resultado", "meus exames", "sorologia",
                                            "resultado do exame"], "resultado de exame"),
)

POR_ID: dict[int, Simbolo] = {s.id: s for s in CATALOGO}
POR_NOME: dict[str, Simbolo] = {s.nome: s for s in CATALOGO}

# Superfícies APRENDIDAS em operação (ver aprendiz.py). Ficam separadas do
# CATALOGO curado de propósito: dá para auditar, versionar e descartar tudo que
# a máquina aprendeu sem tocar no que uma pessoa escreveu. Nenhum id novo nasce
# aqui — só formas novas de dizer ids que já existem.
EXTRAS: dict[int, list[str]] = {}


def reindexar(catalogo: tuple["Simbolo", ...]) -> None:
    """Troca o catálogo ativo e reconstrói os índices.

    O resolvedor indexa por id (POR_ID); trocar CATALOGO sem reindexar deixaria
    o índice apontando para o léxico anterior.
    """
    global CATALOGO, POR_ID, POR_NOME
    CATALOGO = catalogo
    POR_ID = {s.id: s for s in catalogo}
    POR_NOME = {s.nome: s for s in catalogo}


def superficies(simbolo: "Simbolo") -> tuple[str, ...]:
    """Superfícies curadas + aprendidas de um símbolo."""
    extra = EXTRAS.get(simbolo.id)
    return simbolo.superficies + tuple(extra) if extra else simbolo.superficies


# ── eventos clínicos ────────────────────────────────────────────────────────
# Cada evento é uma PERGUNTA DE DATA ("quando foi a última vez?"), nunca uma
# pergunta de sim/não. Dois motivos:
#   (a) matemático — toda a triagem vira  max(evento + carência), ver normas.py;
#   (b) contra vazamento — pergunta condicional ("se sim, quando?") faz o
#       tamanho da conversa depender da resposta, e isso ensina ao doador qual
#       resposta reprova. Ver a invariante de isocronia em conversa.py.
EV_ULTIMA_DOACAO = 0x0301
EV_TATUAGEM = 0x0302
EV_CIRURGIA_MENOR = 0x0303
EV_CIRURGIA_MAIOR = 0x0304
EV_GRIPE = 0x0305
EV_DENTISTA_EXTRACAO = 0x0306
EV_ENDOSCOPIA = 0x0307
EV_TRANSFUSAO = 0x0308
EV_VACINA_INATIVADA = 0x0309
EV_VACINA_ATENUADA = 0x030A
EV_PARTO = 0x030B
EV_PARTO_CESAREA = 0x030C
EV_AMAMENTACAO = 0x030D
EV_ALCOOL = 0x030E
EV_EXPOSICAO_RISCO = 0x030F
EV_AREA_MALARIA = 0x0310
EV_HEPATITE_APOS_11 = 0x0311
EV_DROGA_INJETAVEL = 0x0312
EV_DOENCA_CHAGAS = 0x0313
EV_GESTACAO_ATUAL = 0x0314
EV_COVID_SINTOMAS = 0x0315
EV_ANTIBIOTICO = 0x0316

EVENTOS: tuple[int, ...] = (
    EV_ULTIMA_DOACAO, EV_TATUAGEM, EV_CIRURGIA_MENOR, EV_CIRURGIA_MAIOR, EV_GRIPE,
    EV_DENTISTA_EXTRACAO, EV_ENDOSCOPIA, EV_TRANSFUSAO, EV_VACINA_INATIVADA,
    EV_VACINA_ATENUADA, EV_PARTO, EV_PARTO_CESAREA, EV_AMAMENTACAO, EV_ALCOOL,
    EV_EXPOSICAO_RISCO, EV_AREA_MALARIA, EV_HEPATITE_APOS_11, EV_DROGA_INJETAVEL,
    EV_DOENCA_CHAGAS, EV_GESTACAO_ATUAL, EV_COVID_SINTOMAS, EV_ANTIBIOTICO,
)

NOME_EVENTO: dict[int, str] = {
    EV_ULTIMA_DOACAO: "EV_ULTIMA_DOACAO",
    EV_TATUAGEM: "EV_TATUAGEM",
    EV_CIRURGIA_MENOR: "EV_CIRURGIA_MENOR",
    EV_CIRURGIA_MAIOR: "EV_CIRURGIA_MAIOR",
    EV_GRIPE: "EV_GRIPE",
    EV_DENTISTA_EXTRACAO: "EV_DENTISTA_EXTRACAO",
    EV_ENDOSCOPIA: "EV_ENDOSCOPIA",
    EV_TRANSFUSAO: "EV_TRANSFUSAO",
    EV_VACINA_INATIVADA: "EV_VACINA_INATIVADA",
    EV_VACINA_ATENUADA: "EV_VACINA_ATENUADA",
    EV_PARTO: "EV_PARTO",
    EV_PARTO_CESAREA: "EV_PARTO_CESAREA",
    EV_AMAMENTACAO: "EV_AMAMENTACAO",
    EV_ALCOOL: "EV_ALCOOL",
    EV_EXPOSICAO_RISCO: "EV_EXPOSICAO_RISCO",
    EV_AREA_MALARIA: "EV_AREA_MALARIA",
    EV_HEPATITE_APOS_11: "EV_HEPATITE_APOS_11",
    EV_DROGA_INJETAVEL: "EV_DROGA_INJETAVEL",
    EV_DOENCA_CHAGAS: "EV_DOENCA_CHAGAS",
    EV_GESTACAO_ATUAL: "EV_GESTACAO_ATUAL",
    EV_COVID_SINTOMAS: "EV_COVID_SINTOMAS",
    EV_ANTIBIOTICO: "EV_ANTIBIOTICO",
}

NOME_SIMBOLO: dict[int, str] = {s.id: s.nome for s in CATALOGO} | NOME_EVENTO | {
    VALOR_PESO: "VALOR_PESO",
    VALOR_IDADE: "VALOR_IDADE",
    VALOR_DATA: "VALOR_DATA",
    VALOR_SEXO_BIOLOGICO: "VALOR_SEXO_BIOLOGICO",
    VALOR_DOACOES_12M: "VALOR_DOACOES_12M",
    VALOR_NASCIMENTO: "VALOR_NASCIMENTO",
    VALOR_CONTAGEM: "VALOR_CONTAGEM",
}


def nome(id_: int) -> str:
    return NOME_SIMBOLO.get(id_, f"0x{id_:04X}")


def renderizar(id_: int) -> str:
    """Significado -> texto. Trocar este mapa é trocar de idioma."""
    s = POR_ID.get(id_)
    return s.renderizacao if s else nome(id_)
