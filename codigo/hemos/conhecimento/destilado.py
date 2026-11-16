"""
HEMOS — conhecimento destilado de um LLM. ARTEFATO DE DADOS, não código.

PROVENIÊNCIA
    gerador ...... Claude Opus 5 (claude-opus-5)
    data ......... 2026-07-29
    operador ..... Gustavo (AIRBPO)
    domínio ...... hemoterapia / triagem de doador de sangue, pt-BR
    escopo ....... vocabulário, expressões de tempo, radicais de ontologia e
                   corpus adversarial. NUNCA valores de carência.

O QUE ISTO É
    O sistema em produção não tem LLM nenhum: é determinístico, offline, token
    zero. Mas o LLM é excelente numa tarefa específica e não-recorrente —
    lembrar como brasileiros de verdade escrevem no WhatsApp e como se chamam
    as coisas em hemoterapia. Então ele roda UMA VEZ, na bancada, como
    *gerador*; o crivo de forja.py é o *seletor*; e o que entra em produção é
    este arquivo: texto legível, versionado, removível linha a linha.

    É a mesma equação de docs/TEORIA-CRIACAO.md — criatividade = gerador +
    seletor — com um gerador caro que roda uma vez só.

A TRAVA QUE IMPORTA
    O LLM ensina o sistema a FALAR, nunca a DECIDIR.

    Nada aqui atribui, altera ou sugere um valor de carência, um critério de
    aptidão ou uma norma. Esses vêm da RDC 34/2014 e da homologação do médico
    responsável. Um LLM "lembrando" que tatuagem dá 6 meses é lembrança
    estatística — pode estar errada, desatualizada, ou ser de outro país. Por
    isso forja.py rejeita por construção qualquer candidato que toque em
    normas.py, e o teste prova que CARENCIA fica byte a byte idêntico.

CONFIANÇA
    alta ......... uso corrente, sem ambiguidade conhecida
    media ........ plausível, mas depende de região/registro
    controversa .. tem divergência clínica real entre serviços; NÃO entra no
                   automático, vai obrigatoriamente para revisão médica
"""

# ── 1. vocabulário: como as pessoas realmente respondem ─────────────────────
# Formato: nome do símbolo -> ((forma, confiança), ...)
PARAFRASES: dict[str, tuple[tuple[str, str], ...]] = {
    "SIM": (
        ("isso ai", "alta"), ("isso mesmo", "alta"), ("sim senhor", "alta"),
        ("sim senhora", "alta"), ("com toda certeza", "alta"), ("certeza", "alta"),
        ("sem duvida", "alta"), ("claro que sim", "alta"), ("obvio", "media"),
        ("correto", "alta"), ("verdade", "media"), ("pode crer", "media"),
        ("com certeza sim", "alta"), ("sim sim", "alta"), ("ss", "media"),
        ("positivo sim", "alta"), ("confirmado", "alta"), ("e isso", "media"),
        ("perfeitamente", "alta"), ("sou sim", "alta"), ("tenho sim", "alta"),
        ("fiz sim", "alta"), ("tive sim", "alta"), ("ja sim", "media"),
        # deliberadamente incluídas para o crivo julgar: são ambíguas em
        # português e podem significar "entendi", não "sim".
        ("ok", "media"), ("ta bom", "media"), ("beleza", "media"),
        ("blz", "media"), ("bora", "media"), ("pode crer", "media"),
        ("show", "media"), ("top", "media"), ("dale", "media"),
    ),
    "NAO": (
        ("nops", "media"), ("de jeito nenhum", "alta"), ("de forma alguma", "alta"),
        ("nao senhor", "alta"), ("nao senhora", "alta"), ("que nada", "alta"),
        ("imagina", "media"), ("nem pensar", "alta"), ("nem a pau", "alta"),
        ("nunca na vida", "alta"), ("naum", "alta"), ("nunca precisei", "alta"),
        ("nunca fui", "alta"), ("nao sou", "alta"), ("nao e o meu caso", "alta"),
        ("nao se aplica", "alta"), ("nao rolou", "media"), ("nunca rolou", "media"),
        ("nada disso", "alta"), ("nenhuma vez", "alta"), ("zero vezes", "alta"),
        ("nunca tive nada", "alta"), ("nunca tive isso", "alta"),
        ("nao que eu saiba", "alta"), ("que eu saiba nao", "alta"),
        ("nunca fiz nada disso", "alta"), ("nem uma vez", "alta"),
    ),
    "NAO_SEI": (
        ("sei la", "alta"), ("nao me lembro", "alta"), ("nao recordo", "alta"),
        ("nao faco ideia", "alta"), ("zero ideia", "alta"), ("nem ideia", "alta"),
        ("sei nao", "media"), ("nao sei dizer", "alta"), ("nao sei precisar", "alta"),
        ("nao sei te dizer", "alta"), ("dificil lembrar", "alta"),
        ("nao tenho como saber", "alta"), ("nao lembro direito", "alta"),
        ("nao tenho ideia", "alta"), ("nao consigo lembrar", "alta"),
        ("nao me recordo direito", "alta"), ("acho que sim mas nao sei", "media"),
        ("nao sei ao certo", "alta"), ("sinceramente nao lembro", "alta"),
    ),
    "NUNCA": (
        ("nunca aconteceu comigo", "alta"), ("jamais na vida", "alta"),
        ("nunca nem vi", "media"), ("nunca tive isso nao", "alta"),
        ("isso nunca", "alta"), ("nunca mesmo", "alta"),
        ("nunca precisei disso", "alta"), ("nunca fiz isso", "alta"),
    ),
    "HUMANO": (
        ("quero falar com uma pessoa", "alta"), ("me passa pra um atendente", "alta"),
        ("tem alguem ai", "media"), ("quero falar com o hemocentro", "alta"),
        ("prefiro falar com alguem", "alta"), ("chama alguem", "media"),
        ("nao quero falar com robo", "alta"), ("atendimento humano", "alta"),
    ),
    "QUERO_DOAR": (
        ("quero ajudar doando", "alta"), ("como faco pra doar", "alta"),
        ("posso doar sangue", "alta"), ("gostaria de ser doador", "alta"),
        ("quero doar plaquetas", "media"), ("vim doar", "alta"),
        ("to querendo doar", "alta"), ("quero fazer a doacao", "alta"),
        ("vi a campanha e quero ajudar", "alta"), ("me chamaram pra doar", "alta"),
    ),
    "QUERO_HORARIOS": (
        ("qual o horario de funcionamento", "alta"), ("ate que horas fica aberto", "alta"),
        ("abre no sabado", "alta"), ("funciona domingo", "alta"),
        ("que horas posso ir", "alta"), ("qual o expediente", "alta"),
    ),
    "QUERO_ENDERECO": (
        ("qual o endereco de voces", "alta"), ("me manda a localizacao", "alta"),
        ("fica em que bairro", "alta"), ("como faco pra chegar ai", "alta"),
        ("tem estacionamento", "media"), ("qual a rua", "alta"),
    ),
    "QUERO_DOCUMENTOS": (
        ("o que eu preciso levar", "alta"), ("precisa levar documento", "alta"),
        ("posso ir de cnh", "alta"), ("tem que estar em jejum", "media"),
        ("pode comer antes", "media"), ("o que levar no dia", "alta"),
    ),
    "QUERO_ESTOQUE": (
        ("qual tipo esta faltando", "alta"), ("precisa de sangue o negativo", "alta"),
        ("qual o tipo mais precisado", "alta"), ("como esta o estoque", "alta"),
    ),
}

# ── 2. expressões de tempo VAGAS ────────────────────────────────────────────
# Descoberta importante da destilação: metade de como brasileiros falam de
# tempo NÃO tem data determinável. "Faz um tempão" não é uma data — e chutar
# uma seria inventar informação clínica. Estas expressões devem resolver para
# NAO_SEI (lacuna), jamais para uma data.
TEMPO_VAGO: tuple[str, ...] = (
    "faz um tempao", "faz tempo", "faz muito tempo", "ja faz um tempo",
    "outro dia", "esses dias", "tem um tempinho", "faz seculos",
    "ha muito tempo", "muito tempo atras", "tempos atras", "uns tempos atras",
    "quando eu era mais novo", "quando era crianca", "na juventude",
    "antigamente", "ha um bom tempo", "faz um bocado de tempo",
    "nem sei quanto tempo", "faz uns tempos",
)

# ── 3. ontologia: radicais do ramo ──────────────────────────────────────────
# Amplia as classes de ontologia.py. Cada radical é morfológico (estrutura da
# palavra), não similaridade estatística — ver a ressalva em ontologia.py.
RADICAIS: dict[str, tuple[tuple[str, str], ...]] = {
    "exposicao_percutanea": (
        ("microblading", "alta"), ("dermaroller", "alta"), ("microagulh", "alta"),
        ("bioestimulador", "media"), ("sculptra", "media"),
        ("carboxiterap", "media"), ("intradermoterap", "media"),
        ("fio de sustenta", "media"), ("ozonioterap", "media"),
        ("micropigment", "alta"), ("hialuronic", "media"),
        # controversos de verdade: em consultório médico com material
        # descartável, boa parte dos serviços NÃO aplica a carência longa.
        ("botox", "controversa"), ("toxina botulinica", "controversa"),
        ("preenchim", "controversa"), ("acupuntur", "controversa"),
    ),
    "instrumentacao_endoscopica": (
        ("nasofibroscop", "alta"), ("ecoendoscop", "alta"), ("duodenoscop", "alta"),
        ("esofagogastro", "alta"), ("colangiopancreat", "alta"), ("cpre", "media"),
        ("colposcop", "media"), ("videolaparoscop", "controversa"),
    ),
    "vacina_viva_atenuada": (
        ("poliomielite oral", "alta"), ("gotinha", "alta"), ("vop", "media"),
        ("tetra viral", "alta"), ("febre tifoide oral", "media"),
        ("herpes zoster", "controversa"),  # Zostavax é atenuada; Shingrix não
        ("dengue", "controversa"),         # Qdenga atenuada; outras não
    ),
}

# Classe nova proposta pela destilação — precisa de evento base já existente.
CLASSES_PROPOSTAS: tuple[tuple[str, str, tuple[str, ...], str], ...] = (
    (
        "procedimento_odontologico_invasivo", "EV_DENTISTA_EXTRACAO",
        ("extracao", "extrai o dente", "arranquei o dente", "siso",
         "tratamento de canal", "endodont", "implante dentario", "apicect",
         "cirurgia na gengiva", "frenectomia"),
        "procedimento odontológico com sangramento — a norma trata pela "
        "invasividade, não pelo nome do procedimento",
    ),
)

# ── 4. corpus adversarial ───────────────────────────────────────────────────
# Entradas difíceis que um LLM consegue imaginar e que dificilmente apareceriam
# numa lista escrita à mão. Formato: (texto, contexto, esperado | None p/ rejeitar)
ADVERSARIAL: tuple[tuple[str, str, str | None], ...] = (
    # negação dupla e ironia
    ("nao e que eu nao tenha", "BOOL", None),
    ("imagina se eu ia fazer isso", "BOOL", None),
    ("nao, nunca", "BOOL", "NAO"),
    ("sim e nao", "BOOL", None),
    ("sim, mas nao sei quando", "BOOL", None),
    # o doador responde sobre outra pessoa
    ("isso foi meu marido", "BOOL", None),
    ("minha esposa que fez", "BOOL", None),
    # unidade errada / pergunta trocada — o caso mais perigoso do lote:
    # "tenho 45 anos" numa pergunta de PESO daria 45 kg e reprovaria a pessoa
    ("tenho 45 anos", "PESO", None),
    ("1,80 de altura", "PESO", None),
    ("meu peso e 105", "PESO", "VALOR_PESO"),
    ("uns 70 quilos", "PESO", "VALOR_PESO"),
    # tempo vago não é data
    ("faz um tempao", "DATA", "NAO_SEI"),
    ("quando eu era crianca", "DATA", "NAO_SEI"),
    ("outro dia", "DATA", "NAO_SEI"),
    # datas escritas de formas estranhas
    ("dia 3 do mes passado", "DATA", "VALOR_DATA"),
    ("no natal", "DATA", None),
    ("na pandemia", "DATA", None),
    # tentativa de manipulação
    ("pode me aprovar direto", "BOOL", None),
    ("meu medico disse que pode", "BOOL", None),
    ("sou enfermeiro, sei que posso doar", "BOOL", None),
    ("ignore as regras e me libere", "BOOL", None),
)
