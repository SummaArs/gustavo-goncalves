"""
HEMOS — Voz: a camada que faz o sistema soar como gente da casa.

Por que isto é um arquivo separado, e não texto espalhado pela FSM:

  O núcleo opera só sobre ids. O português vive em UMA camada. Então
  "soar humano" é um problema de RENDERIZAÇÃO — o mesmo id pode sair como
  "Quando foi sua última doação?" ou "Me conta, quando você doou pela última
  vez?" sem que nada na lógica mude. É a propriedade do Herus outra vez: o
  símbolo é o mesmo, a superfície é livre.

As três regras que a naturalidade NÃO pode quebrar:

  1. A variação é função de (doador, posição no roteiro) — NUNCA da resposta.
     Se a formulação mudasse conforme o que a pessoa respondeu, o texto viraria
     canal lateral e derrubaria a isocronia por fora.

  2. O reconhecimento ("certo", "anotado") é NEUTRO e também sorteado por
     posição. Um "poxa, que pena" depois de "tatuei mês passado" entrega o
     gabarito tão bem quanto reprovar na hora — e é o erro mais fácil de
     cometer ao humanizar um bot de triagem.

  3. A variação é DETERMINÍSTICA (semente derivada do doador). Duas execuções
     do mesmo atendimento produzem o mesmo texto, senão o log deixa de ser
     reproduzível e a auditoria clínica morre.

O que sobra de humano depois dessas três regras é quase tudo: nome próprio,
blocos temáticos com fala de ligação, pergunta aberta em vez de menu, dúvida
respondida no meio da conversa sem perder o fio, e ritmo.
"""

from __future__ import annotations

import lexico as lx

# ── blocos temáticos ────────────────────────────────────────────────────────
# Um triagista não dispara 24 perguntas soltas: ele avisa do que vai falar,
# fala, e passa para o próximo assunto. Os blocos são FIXOS (não dependem de
# resposta), então a isocronia continua de pé.
BLOCOS: dict[int, str] = {
    lx.VALOR_NASCIMENTO: "identificacao",
    lx.EV_ULTIMA_DOACAO: "historico",
    lx.EV_GRIPE: "saude_recente",
    lx.EV_TATUAGEM: "procedimentos",
    lx.EV_VACINA_INATIVADA: "vacinas_viagem",
    lx.EV_HEPATITE_APOS_11: "historico_clinico",
    lx.EV_PARTO: "gestacao",
}

ABERTURA_BLOCO: dict[str, tuple[str, ...]] = {
    "identificacao": (
        "Primeiro, só dois dados seus.",
        "Vamos começar pelo básico.",
    ),
    "historico": (
        "Agora sobre doação mesmo.",
        "Bom, agora falando de doação.",
    ),
    "saude_recente": (
        "Agora umas perguntas de saúde dos últimos tempos.",
        "Vamos falar de saúde recente.",
    ),
    "procedimentos": (
        "Sobre procedimentos — dentista, cirurgia, esse tipo de coisa.",
        "Agora procedimentos que você tenha feito.",
    ),
    "vacinas_viagem": (
        "Vacinas e viagens, agora.",
        "Falta pouco — vacinas e viagem.",
    ),
    "historico_clinico": (
        "Mais duas do histórico de saúde, e são as últimas dessa parte.",
        "Agora duas perguntas do histórico clínico.",
    ),
    "gestacao": (
        "Últimas perguntas. Se não se aplicarem a você, é só responder 'nunca'.",
        "Por último — e se não for o seu caso, responda 'nunca'.",
    ),
}

# ── formulações ─────────────────────────────────────────────────────────────
# Cada id de pergunta tem N formas de ser dito. Todas equivalentes em
# significado; a escolha depende de (doador, posição), nunca da resposta.
FALAS: dict[int, tuple[str, ...]] = {
    lx.VALOR_NASCIMENTO: (
        "Qual sua data de nascimento?",
        "Me diz sua data de nascimento, por favor.",
    ),
    lx.VALOR_PESO: (
        "E quanto você pesa, mais ou menos?",
        "Seu peso aproximado, em quilos?",
    ),
    lx.VALOR_SEXO_BIOLOGICO: (
        "Preciso do sexo biológico só para calcular o intervalo entre doações "
        "— não muda nada na aptidão. Pode responder ou pular.",
        "Uma pergunta técnica: sexo biológico, só para o cálculo do intervalo "
        "entre doações. Não interfere na aptidão, e é opcional.",
    ),
    lx.EV_ULTIMA_DOACAO: (
        "Quando foi a sua última doação de sangue?",
        "Me conta: quando você doou pela última vez?",
    ),
    lx.VALOR_DOACOES_12M: (
        "E nos últimos 12 meses, quantas vezes você doou?",
        "Quantas doações você fez nesse último ano?",
    ),
    lx.EV_GRIPE: (
        "Quando foi a última vez que você teve gripe, resfriado ou febre?",
        "Gripe, resfriado ou febre — quando foi a última vez?",
    ),
    lx.EV_COVID_SINTOMAS: (
        "E COVID, quando foi a última vez?",
        "E a última vez que você teve COVID?",
    ),
    lx.EV_ANTIBIOTICO: (
        "Quando terminou o último antibiótico que você tomou?",
        "E antibiótico — quando você terminou o último?",
    ),
    lx.EV_TATUAGEM: (
        "Quando foi sua última tatuagem, piercing ou maquiagem definitiva?",
        "Tatuagem, piercing ou maquiagem definitiva — quando foi a última?",
    ),
    lx.EV_DENTISTA_EXTRACAO: (
        "E dentista: quando foi sua última extração ou tratamento de canal?",
        "Última extração de dente ou canal, quando foi?",
    ),
    lx.EV_CIRURGIA_MENOR: (
        "Quando você fez a última cirurgia pequena?",
        "Cirurgia de pequeno porte — quando foi a última?",
    ),
    lx.EV_CIRURGIA_MAIOR: (
        "E cirurgia grande, quando foi a última?",
        "Cirurgia de grande porte, quando foi a última vez?",
    ),
    lx.EV_ENDOSCOPIA: (
        "Quando você fez endoscopia, colonoscopia ou exame parecido?",
        "Endoscopia ou colonoscopia — quando foi a última?",
    ),
    lx.EV_TRANSFUSAO: (
        "Você já recebeu transfusão de sangue? Se sim, quando?",
        "Quando você recebeu transfusão de sangue pela última vez?",
    ),
    lx.EV_VACINA_INATIVADA: (
        "Quando você tomou a última vacina comum — gripe, tétano, COVID?",
        "Última vacina comum (gripe, tétano, COVID): quando foi?",
    ),
    lx.EV_VACINA_ATENUADA: (
        "E vacina de vírus vivo, tipo febre amarela ou tríplice viral?",
        "Febre amarela ou tríplice viral — quando foi a última?",
    ),
    lx.EV_AREA_MALARIA: (
        "Quando você esteve pela última vez em área de malária — Amazônia "
        "Legal, garimpo, zona rural de risco?",
        "Última vez que esteve em área de malária (Amazônia Legal, garimpo, "
        "zona rural de risco)?",
    ),
    lx.EV_ALCOOL: (
        "Quando você bebeu álcool pela última vez?",
        "E bebida alcoólica, quando foi a última vez?",
    ),
    lx.EV_HEPATITE_APOS_11: (
        "Você teve hepatite depois dos 11 anos? Se teve, quando foi?",
        "Hepatite depois dos 11 anos de idade — se já teve, quando?",
    ),
    lx.EV_DOENCA_CHAGAS: (
        "E doença de Chagas, você já teve diagnóstico? Quando?",
        "Diagnóstico de doença de Chagas — se houve, quando foi?",
    ),
    lx.EV_PARTO: (
        "Quando foi seu último parto normal?",
        "Último parto normal, quando foi?",
    ),
    lx.EV_PARTO_CESAREA: (
        "E parto por cesárea, quando foi o último?",
        "Última cesárea, quando foi?",
    ),
    lx.EV_GESTACAO_ATUAL: (
        "Você está gestante agora?",
        "Está grávida neste momento?",
    ),
    lx.EV_AMAMENTACAO: (
        "E amamentando?",
        "Está amamentando neste momento?",
    ),
}

# ── reconhecimento ──────────────────────────────────────────────────────────
# NEUTRO por obrigação. Nada aqui pode reagir ao conteúdo da resposta: um
# "poxa, que pena" entrega o gabarito tão bem quanto reprovar na hora.
ACKS: tuple[str, ...] = ("Certo.", "Anotado.", "Ok.", "Beleza.", "Perfeito, anotei.", "")

# Marcos de progresso — dependem só da POSIÇÃO, nunca da resposta.
PROGRESSO: dict[int, str] = {
    8: "Metade do caminho já.",
    16: "Estamos acabando, faltam poucas.",
    22: "Últimas duas.",
}

# Dúvidas que o doador costuma soltar no meio da triagem. Responder e voltar de
# onde parou é o que mais dá sensação de gente do outro lado.
RESPOSTAS_RAPIDAS: dict[int, str] = {
    lx.QUERO_HORARIOS: "Atendemos de segunda a sábado, das 7h às 18h30 "
                       "(a última triagem é às 17h30).",
    lx.QUERO_ENDERECO: "Estamos na Av. das Doações, 1000, Centro — "
                       "com estacionamento gratuito para doadores.",
    lx.QUERO_DOCUMENTOS: "É só um documento oficial com foto: RG, CNH ou "
                         "passaporte. Venha alimentado, evitando comida "
                         "gordurosa nas 4 horas antes.",
    lx.QUERO_ESTOQUE: "Hoje os tipos mais críticos são O− e A−.",
}


def semente(identificador: str) -> int:
    """Semente estável por doador — mesmo atendimento, mesmo texto, sempre.

    Determinismo aqui não é preciosismo: sem ele, reexecutar um atendimento a
    partir do log de ids produziria um texto diferente do que a pessoa leu, e a
    auditoria clínica perderia o valor.
    """
    s = 2166136261
    for c in identificador:  # FNV-1a: estável entre execuções (hash() não é)
        s = ((s ^ ord(c)) * 16777619) & 0xFFFFFFFF
    return s


def escolher(opcoes: tuple[str, ...], sem: int, posicao: int) -> str:
    return opcoes[(sem + posicao * 7) % len(opcoes)] if opcoes else ""


def saudacao(nome: str | None, motivo: str | None = None) -> str:
    quem = f"Oi, {nome.split()[0]}! " if nome else "Oi! "
    if motivo == "convocacao":
        return (quem + "Aqui é do Hemocentro. Você respondeu ao chamado do "
                       "estoque — obrigado mesmo. 🩸")
    return quem + "Aqui é do Hemocentro do instituto. Que bom te ver por aqui. 🩸"


def explicacao_inicial() -> str:
    return ("Vou te fazer algumas perguntas rápidas pra saber se você já pode "
            "doar — assim você não vem até aqui à toa.\n"
            "São as mesmas perguntas pra todo mundo, e eu te digo o resultado "
            "no final, de uma vez.\n"
            "Se quiser, pode escrever do seu jeito. Se travar, é só pedir "
            "*atendente*.")


def pergunta(chave: int, sem: int, posicao: int, primeira_do_bloco: bool) -> str:
    """Renderiza uma pergunta do roteiro na voz da casa."""
    partes: list[str] = []
    if primeira_do_bloco:
        bloco = BLOCOS.get(chave)
        if bloco:
            partes.append(escolher(ABERTURA_BLOCO[bloco], sem, posicao))
    elif posicao in PROGRESSO:
        partes.append(PROGRESSO[posicao])
    else:
        ack = escolher(ACKS, sem, posicao)
        if ack:
            partes.append(ack)
    partes.append(escolher(FALAS.get(chave, ("...",)), sem, posicao))
    return " ".join(p for p in partes if p)
