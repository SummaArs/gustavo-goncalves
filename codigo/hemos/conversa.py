"""
HEMOS — Conversa: a máquina de estados. Opera só sobre ids.

A decisão de projeto que manda neste arquivo é a ISOCRONIA.

  No Herus, Tier 0.5 e Tier 0/1 usavam quadros de tamanhos diferentes. A cripto
  estava certa, mas o *airtime* denunciava o tier: dava para classificar o
  tráfego sem quebrar nada. O conserto foi igualar tudo em 34 B / 246,8 ms.

  Aqui existe o mesmo vazamento por canal lateral, e o dano é clínico. Se o bot
  reprovasse na hora em que o doador respondesse "tatuei mês passado", ele
  aprenderia qual resposta reprova — e na próxima vez mentiria. Triagem que
  ensina o próprio gabarito produz doação de risco, que é exatamente o que a
  triagem existe para impedir.

  Conserto idêntico: forma uniforme.
    1. O roteiro tem tamanho FIXO. Nenhuma pergunta é condicional — por isso
       toda pergunta é "quando foi a última vez?" em vez de "você tem X?".
    2. O menu de faixas de tempo é IGUAL em todas as perguntas (nunca / este
       mês / 1-3 / 3-6 / 6-12 / mais de 1 ano). Um menu recortado na carência
       de cada evento entregaria o limiar de bandeja.
    3. Nenhum veredito parcial vaza durante o roteiro. O resultado sai no fim,
       de uma vez.
  `testes/teste_conversa.py` prova as três por busca sobre trajetos.

O que este roteiro deliberadamente NÃO pergunta
───────────────────────────────────────────────
Exposição sexual de risco e uso de drogas injetáveis estão no léxico e nas
normas, mas ficam FORA do WhatsApp, por três razões que se somam:
  - é dado sensível de saúde (LGPD art. 11) num canal que o doador costuma
    ler em público e com histórico no aparelho de terceiros;
  - a norma exige entrevista confidencial individual — o critério é
    comportamental e o STF (ADI 5543/2020) vedou recorte por orientação
    sexual, que só some de verdade quando um profissional conduz a conversa;
  - respondida por escrito, essa pergunta tem a pior taxa de sinceridade de
    todo o questionário.
São feitas presencialmente. O relatório final diz isso ao doador.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

import lexico as lx
import normas
import resolvedor as rv
import voz

# Faixas de tempo — as MESMAS para toda pergunta de evento (ver isocronia).
# Cada faixa vira a data mais RECENTE compatível: incerteza sempre resolve
# para o lado mais restritivo.
FAIXAS: tuple[tuple[str, int | None], ...] = (
    ("nunca aconteceu", None),
    ("nos últimos 30 dias", 0),
    ("de 1 a 3 meses atrás", 30),
    ("de 3 a 6 meses atrás", 90),
    ("de 6 a 12 meses atrás", 180),
    ("há mais de 1 ano", 365),
)

CONTROLE = {lx.VOLTAR, lx.PARAR, lx.HUMANO, lx.REPETIR}

# Quantas dúvidas soltas o doador pode fazer no meio da triagem antes de a
# conversa passar a tratar tudo como rejeição. Existe só para garantir I8
# (terminação): sem teto, quem só faz perguntas nunca termina o roteiro.
LIMITE_DUVIDAS = 5

# strftime("%a") depende do locale do servidor; um hemocentro não pode receber
# "Thu" numa mensagem para o doador.
DIAS_SEMANA = ("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo")


@dataclass(frozen=True)
class Pergunta:
    chave: int
    texto: str
    tipo: str  # DATA | NASCIMENTO | PESO | SEXO | DOACOES | BOOL
    opcoes: tuple[str, ...] = ()

    @property
    def esperado(self) -> set[int]:
        base = set(CONTROLE) | {lx.NAO_SEI}
        if self.tipo == "DATA":
            return base | {lx.VALOR_DATA, lx.NUNCA, lx.NAO}
        if self.tipo == "NASCIMENTO":
            return base | {lx.VALOR_DATA}
        if self.tipo == "PESO":
            return base | {lx.VALOR_PESO}
        if self.tipo == "SEXO":
            return base | {lx.VALOR_SEXO_BIOLOGICO, lx.NAO}
        if self.tipo == "DOACOES":
            return base | {lx.VALOR_CONTAGEM, lx.NUNCA, lx.NAO}
        if self.tipo == "BOOL":
            return base | {lx.SIM, lx.NAO}
        return base


_D = "DATA"
ROTEIRO: tuple[Pergunta, ...] = (
    Pergunta(lx.VALOR_NASCIMENTO, "Qual a sua data de nascimento? (dd/mm/aaaa)", "NASCIMENTO"),
    Pergunta(lx.VALOR_PESO, "Quanto você pesa, aproximadamente? (em kg)", "PESO"),
    Pergunta(lx.VALOR_SEXO_BIOLOGICO,
             "Para calcular o intervalo entre doações, preciso do sexo biológico. "
             "Ele não influencia a aptidão.", "SEXO",
             ("masculino", "feminino", "prefiro não informar")),
    Pergunta(lx.EV_ULTIMA_DOACAO, "Quando foi a sua última doação de sangue?", _D),
    Pergunta(lx.VALOR_DOACOES_12M, "Quantas vezes você doou nos últimos 12 meses?", "DOACOES"),
    Pergunta(lx.EV_GRIPE, "Quando você teve gripe, resfriado ou febre pela última vez?", _D),
    Pergunta(lx.EV_COVID_SINTOMAS, "E COVID-19, quando foi a última vez?", _D),
    Pergunta(lx.EV_ANTIBIOTICO, "Quando terminou o último tratamento com antibiótico?", _D),
    Pergunta(lx.EV_TATUAGEM, "Quando você fez tatuagem, piercing ou maquiagem definitiva "
                             "pela última vez?", _D),
    Pergunta(lx.EV_DENTISTA_EXTRACAO, "Quando foi sua última extração de dente ou "
                                      "tratamento de canal?", _D),
    Pergunta(lx.EV_CIRURGIA_MENOR, "Quando você fez a última cirurgia de pequeno porte?", _D),
    Pergunta(lx.EV_CIRURGIA_MAIOR, "E cirurgia de grande porte, quando foi a última?", _D),
    Pergunta(lx.EV_ENDOSCOPIA, "Quando fez endoscopia, colonoscopia ou exame parecido?", _D),
    Pergunta(lx.EV_TRANSFUSAO, "Quando você recebeu transfusão de sangue pela última vez?", _D),
    Pergunta(lx.EV_VACINA_INATIVADA, "Quando tomou a última vacina comum "
                                     "(gripe, tétano, COVID)?", _D),
    Pergunta(lx.EV_VACINA_ATENUADA, "E vacina de vírus vivo (febre amarela, tríplice viral), "
                                    "quando foi a última?", _D),
    Pergunta(lx.EV_AREA_MALARIA, "Quando você esteve pela última vez em área de "
                                 "malária (Amazônia Legal, garimpo, zona rural de risco)?", _D),
    Pergunta(lx.EV_ALCOOL, "Quando você bebeu álcool pela última vez?", _D),
    Pergunta(lx.EV_HEPATITE_APOS_11, "Quando você teve hepatite, se já teve, "
                                     "depois dos 11 anos de idade?", _D),
    Pergunta(lx.EV_DOENCA_CHAGAS, "Quando recebeu diagnóstico de doença de Chagas, "
                                  "se já recebeu?", _D),
    Pergunta(lx.EV_PARTO, "Quando foi seu último parto normal? "
                          "(responda 'nunca' se não se aplica)", _D),
    Pergunta(lx.EV_PARTO_CESAREA, "E parto por cesárea, quando foi o último? "
                                  "(responda 'nunca' se não se aplica)", _D),
    Pergunta(lx.EV_GESTACAO_ATUAL, "Você está gestante neste momento?", "BOOL"),
    Pergunta(lx.EV_AMAMENTACAO, "Você está amamentando neste momento?", "BOOL"),
)

TAMANHO_ROTEIRO = len(ROTEIRO)

INICIO, TRIAGEM, RESULTADO, AGENDA, FIM = "INICIO", "TRIAGEM", "RESULTADO", "AGENDA", "FIM"


@dataclass
class Sessao:
    """Estado de um doador. O histórico é semântico: só ids, nunca texto.

    É o que torna o log auditável e ao mesmo tempo compatível com a LGPD —
    dá para reconstruir e reproduzir a decisão inteira sem ter guardado uma
    palavra do que a pessoa escreveu.
    """

    hoje: date = field(default_factory=date.today)
    telefone: str = "anonimo"
    nome: str | None = None  # vem do cadastro do hemocentro, quando existe
    estado: str = INICIO
    i: int = 0
    fatos: dict[int, object] = field(default_factory=dict)
    historico: list[tuple[str, int, object]] = field(default_factory=list)
    tentativas: int = 0
    duvidas: int = 0
    menu_visivel: bool = False
    perguntas_feitas: int = 0
    agendamento: object = None
    lembrete: object = None  # data em que o inapto temporário será chamado
    veredito: object = None

    # ── auxiliares ──────────────────────────────────────────────────────────
    @property
    def semente(self) -> int:
        """Escolhe as formulações. Depende do doador, jamais das respostas."""
        return voz.semente(self.telefone)

    @property
    def pergunta(self) -> Pergunta | None:
        return ROTEIRO[self.i] if self.i < TAMANHO_ROTEIRO else None

    def _registrar(self, direcao: str, id_: int, valor: object = None) -> None:
        self.historico.append((direcao, id_, valor))

    def _menu(self, p: Pergunta) -> str:
        if p.tipo == "DATA":
            itens = [r for r, _ in FAIXAS]
        elif p.tipo == "BOOL":
            itens = ["sim", "não", "não sei"]
        elif p.tipo == "SEXO":
            itens = list(p.opcoes)
        else:
            return ""
        return "\n".join(f"{n}. {r}" for n, r in enumerate(itens, 1))

    def _texto_pergunta(self, p: Pergunta, com_menu: bool = False) -> str:
        """Renderiza a pergunta na voz da casa (ver voz.py).

        O menu numerado NÃO aparece de saída: um atendente pergunta aberto e só
        oferece alternativas quando a pessoa não entendeu. Ele entra na
        reapresentação — que é exatamente a zona de rejeição do resolvedor.
        """
        primeira_do_bloco = p.chave in voz.BLOCOS
        texto = voz.pergunta(p.chave, self.semente, self.i, primeira_do_bloco)
        menu = self._menu(p) if com_menu else ""
        # Número só vale como opção quando o menu está de fato na tela: sem
        # isso, quem responde "1" à pergunta de data pode estar dizendo
        # "1 mês" e o sistema leria "nunca aconteceu".
        self.menu_visivel = bool(menu)
        return f"{texto}\n{menu}" if menu else texto

    # ── o passo ─────────────────────────────────────────────────────────────
    def passo(self, texto: str) -> list[str]:
        if self.estado == INICIO:
            return self._iniciar(texto)
        if self.estado == TRIAGEM:
            return self._triagem(texto)
        if self.estado == RESULTADO:
            return self._resultado_pos(texto)
        if self.estado == AGENDA:
            return self._agenda(texto)
        return ["Atendimento encerrado. Mande *oi* para começar de novo."]

    def _iniciar(self, texto: str) -> list[str]:
        r = rv.resolver(texto, {lx.QUERO_DOAR, lx.QUERO_AGENDAR, lx.QUERO_HORARIOS,
                                lx.QUERO_ENDERECO, lx.QUERO_DOCUMENTOS, lx.QUERO_ESTOQUE,
                                lx.QUERO_RESULTADO, lx.HUMANO, lx.PARAR}, self.hoje)
        self._registrar("<", r.id, r.valor)
        if r.id in (lx.QUERO_DOAR, lx.QUERO_AGENDAR):
            self.estado = TRIAGEM
            return [
                voz.saudacao(self.nome),
                voz.explicacao_inicial(),
                self._texto_pergunta(ROTEIRO[0]),
            ]
        if r.id == lx.QUERO_HORARIOS:
            return ["Atendemos de segunda a sábado, das 7h às 18h30 "
                    "(última triagem às 17h30)."]
        if r.id == lx.QUERO_ENDERECO:
            return ["Hemocentro — Av. das Doações, 1000, Centro. "
                    "Estacionamento gratuito para doadores."]
        if r.id == lx.QUERO_DOCUMENTOS:
            return ["Leve um documento oficial com foto (RG, CNH ou passaporte), "
                    "emitido há menos de 20 anos. Venha alimentado e evite gordura "
                    "nas 4 horas antes."]
        if r.id == lx.QUERO_ESTOQUE:
            return ["Hoje o estoque crítico é de *O-* e *A-*. "
                    "Se for o seu tipo, sua doação vale ouro. 🩸"]
        if r.id == lx.HUMANO:
            self.estado = FIM
            return ["Certo, vou chamar um atendente. Em horário comercial "
                    "alguém responde aqui mesmo."]
        if r.id == lx.PARAR:
            self.estado = FIM
            return ["Tudo bem. Quando quiser, é só chamar."]
        return ["Oi! Posso te ajudar com:\n"
                "1. Doar sangue (pré-triagem)\n"
                "2. Horários\n3. Endereço\n4. O que levar\n5. Estoque de hoje\n"
                "Responda com o número ou escreva o que precisa."]

    def _triagem(self, texto: str) -> list[str]:
        p = self.pergunta
        assert p is not None
        r = self._interpretar(texto, p)
        self._registrar("<", r.id, r.valor)

        if r.id == lx.PARAR:
            self.estado = FIM
            return ["Triagem cancelada. Nada foi guardado. Volte quando quiser."]
        if r.id == lx.HUMANO:
            self.estado = FIM
            return ["Certo, um atendente vai te responder aqui."]
        if r.id == lx.VOLTAR:
            if self.i > 0:
                self.i -= 1
                self.perguntas_feitas -= 1
                self.fatos.pop(ROTEIRO[self.i].chave, None)
            return [self._texto_pergunta(self.pergunta)]
        if r.id == lx.NAO_ENTENDI and self.duvidas < LIMITE_DUVIDAS:
            # Dúvida solta no meio da triagem ("vocês abrem sábado?"). Um
            # atendente responde e retoma de onde parou — é o que mais dá
            # sensação de gente do outro lado. Só é tentado DEPOIS que a
            # resposta à pergunta atual não casou, então responder nunca
            # perde para uma dúvida. O limite garante a terminação (I8).
            d = rv.resolver(texto, set(voz.RESPOSTAS_RAPIDAS) | {lx.QUERO_DOAR}, self.hoje)
            if d.id in voz.RESPOSTAS_RAPIDAS:
                self.duvidas += 1
                self._registrar("<", d.id, None)
                return [voz.RESPOSTAS_RAPIDAS[d.id],
                        "Voltando: " + self._texto_pergunta(p)]

        if r.id == lx.REPETIR or r.id == lx.NAO_ENTENDI:
            self.tentativas += 1
            # Zona de rejeição: em vez de adivinhar, oferece o menu. Duas
            # rejeições seguidas e a conversa cai para atendente humano —
            # falha fechada, nunca fecha no chute.
            if self.tentativas >= 3:
                self.estado = FIM
                return ["Acho melhor uma pessoa te atender aqui — já chamei "
                        "alguém da equipe pra continuar com você."]
            return ["Desculpa, não peguei — e nessa parte eu prefiro perguntar "
                    "de novo a chutar. Se ficar mais fácil, escolhe uma:\n"
                    + self._texto_pergunta(p, com_menu=True)]

        self.tentativas = 0
        self.fatos[p.chave] = self._valor(r, p)
        self.i += 1
        self.perguntas_feitas += 1
        if self.i < TAMANHO_ROTEIRO:
            return [self._texto_pergunta(self.pergunta)]
        self.estado = RESULTADO
        return self._relatorio()

    def _interpretar(self, texto: str, p: Pergunta) -> rv.Resolucao:
        """Aplica o atalho de menu numérico e delega ao resolvedor."""
        t = rv.normalizar(texto)
        if t.isdigit() and self.menu_visivel and p.tipo in ("DATA", "BOOL", "SEXO"):
            n = int(t)
            if p.tipo == "DATA" and 1 <= n <= len(FAIXAS):
                dias = FAIXAS[n - 1][1]
                if dias is None:
                    return rv.Resolucao(lx.NUNCA, None, 99.0, 99.0)
                return rv.Resolucao(lx.VALOR_DATA, self.hoje - timedelta(days=dias), 99.0, 99.0)
            if p.tipo == "BOOL" and 1 <= n <= 3:
                return rv.Resolucao((lx.SIM, lx.NAO, lx.NAO_SEI)[n - 1], None, 99.0, 99.0)
            if p.tipo == "SEXO" and 1 <= n <= 3:
                if n == 3:
                    return rv.Resolucao(lx.NAO, None, 99.0, 99.0)
                return rv.Resolucao(lx.VALOR_SEXO_BIOLOGICO, "MF"[n - 1], 99.0, 99.0)
            return rv.Resolucao(lx.NAO_ENTENDI)
        return rv.resolver(texto, p.esperado, self.hoje)

    def _valor(self, r: rv.Resolucao, p: Pergunta) -> object:
        """Converte o símbolo resolvido no valor que normas.avaliar() consome."""
        if p.tipo == "DATA":
            if r.id == lx.VALOR_DATA:
                return r.valor
            if r.id in (lx.NUNCA, lx.NAO):
                return None  # nunca aconteceu -> sem carência
            return normas.DESCONHECIDO  # "não sei" NÃO é "nunca" — vira lacuna
        if p.tipo == "NASCIMENTO":
            return r.valor
        if p.tipo == "PESO":
            return r.valor
        if p.tipo == "SEXO":
            return r.valor if r.id == lx.VALOR_SEXO_BIOLOGICO else None
        if p.tipo == "DOACOES":
            return int(r.valor) if r.id == lx.VALOR_CONTAGEM else 0
        if p.tipo == "BOOL":
            if r.id == lx.SIM:
                return True
            return False if r.id == lx.NAO else normas.DESCONHECIDO
        return r.valor

    # ── relatório ───────────────────────────────────────────────────────────
    def _relatorio(self) -> list[str]:
        v = normas.avaliar(self.fatos, self.hoje)
        self.veredito = v
        self._registrar(">", 0x0F00 + v.nivel, v.libera_em)
        linhas: list[str] = []

        primeiro = f"Pronto, {self.nome.split()[0]}, terminamos. " if self.nome \
            else "Pronto, terminamos. "
        if v.nivel == normas.APTO and not v.conclusivo:
            # Houve "não sei". O sistema NÃO afirma aptidão — indica, e diz
            # exatamente o que ficou em aberto para a triagem presencial.
            linhas.append(primeiro + "🔎 *Pelo que você me contou, nada impede a "
                          "doação — mas ficaram alguns pontos em aberto*, e é a "
                          "equipe daqui que confirma esses:")
            linhas.append("\n".join(f"• {l}" for l in v.lacunas))
        elif v.nivel == normas.APTO:
            linhas.append(primeiro + "✅ *Não vi nada que te impeça de doar.*")
        elif v.nivel == normas.TEMPORARIO:
            if v.libera_em and not v.indeterminado:
                linhas.append(primeiro + "🕒 *Hoje ainda não dá — mas é só uma "
                              "questão de tempo.*\nVocê fica liberado(a) a partir de "
                              f"*{v.libera_em.strftime('%d/%m/%Y')}*.")
            else:
                linhas.append(primeiro + "🕒 *Hoje ainda não é possível doar.*")
        else:
            linhas.append(primeiro + "❌ *Pelas regras da doação, você não pode "
                          "doar sangue.*\nIsso não tira nem um pouco do seu gesto — "
                          "e você ainda ajuda muito divulgando e trazendo alguém "
                          "para doar.")

        if v.motivos:
            linhas.append("*Por quê:*\n" + "\n".join(
                f"• {m.texto}" + (f" Liberação em {m.libera_em.strftime('%d/%m/%Y')}."
                                  if m.libera_em else "")
                for m in v.motivos))
        for c in v.condicoes:
            linhas.append(f"⚠️ {c}")

        nao_sei = [ROTEIRO[j].texto for j in range(TAMANHO_ROTEIRO)
                   if self.fatos.get(ROTEIRO[j].chave, "?") is None
                   and ROTEIRO[j].tipo == "BOOL"]
        _ = nao_sei

        linhas.append(
            "ℹ️ Só pra deixar claro: isso aqui é uma *pré-triagem*, pelas regras da "
            "RDC 34/2014 da Anvisa. Serve pra você não vir até aqui à toa. A triagem "
            "de verdade é presencial, individual e sigilosa, com um profissional de "
            "saúde — e é ela que vale."
        )
        if v.nivel == normas.APTO:
            linhas.append("Quer que eu já marque um horário pra você?")
        elif v.libera_em and not v.indeterminado:
            linhas.append("Quer que eu te avise no dia em que você estiver liberado(a)?")
        return linhas

    def _resultado_pos(self, texto: str) -> list[str]:
        r = rv.resolver(texto, {lx.SIM, lx.NAO, lx.PARAR, lx.HUMANO, lx.QUERO_AGENDAR},
                        self.hoje)
        self._registrar("<", r.id, r.valor)
        # Trava: só quem a norma liberou entra na agenda. O relatório nem
        # oferece agendamento a inaptos, mas a máquina não pode depender da
        # mensagem — quem decide é o veredito, não o texto.
        apto = self.veredito is not None and self.veredito.nivel == normas.APTO
        if r.id in (lx.SIM, lx.QUERO_AGENDAR) and apto:
            self.estado = AGENDA
            return ["Tenho estes horários:\n" + "\n".join(
                f"{n}. {DIAS_SEMANA[q.weekday()]}, {q.strftime('%d/%m às %Hh%M')}"
                for n, q in enumerate(self._slots(), 1))
                + "\nQual fica melhor pra você?"]
        self.estado = FIM
        if not apto:
            v = self.veredito
            if r.id == lx.SIM and v is not None and v.libera_em:
                # O arco que mais recupera doador: quem é inapto TEMPORÁRIO
                # normalmente é recusado na recepção, se frustra e some. Aqui
                # ele sai da conversa como doador agendado no futuro — a
                # convocação o encontra sozinha na data.
                self.lembrete = v.libera_em
                self._registrar(">", lx.QUERO_AGENDAR, v.libera_em)
                return [f"Combinado! Vou te chamar em "
                        f"*{v.libera_em.strftime('%d/%m/%Y')}*, quando você "
                        "estiver liberado(a). Obrigado por querer doar — "
                        "isso já ajuda muito. 🩸"]
            return ["Tudo bem. Quando quiser, é só me chamar aqui. "
                    "Se ficou alguma dúvida sobre o motivo, responda "
                    "*atendente* que alguém da equipe te explica."]
        return ["Combinado. Você pode aparecer sem agendar também, "
                "de segunda a sábado, das 7h às 18h30. 🩸"]

    def _slots(self) -> list[date]:
        from datetime import datetime, time
        base = self.hoje + timedelta(days=1)
        while base.weekday() == 6:  # domingo fechado
            base += timedelta(days=1)
        return [datetime.combine(base, time(h, 30)) for h in (8, 10, 15)]

    def _agenda(self, texto: str) -> list[str]:
        t = rv.normalizar(texto)
        if t.isdigit() and 1 <= int(t) <= 3:
            escolhido = self._slots()[int(t) - 1]
            self.agendamento = escolhido
            self.estado = FIM
            self._registrar(">", lx.QUERO_AGENDAR, escolhido)
            return [f"Agendado para *{escolhido.strftime('%d/%m às %Hh%M')}*. ✅\n"
                    "Leve documento oficial com foto, venha alimentado e evite "
                    "gordura nas 4 horas antes. Te espero!"]
        self.estado = FIM
        return ["Sem problema — pode vir sem agendar, de segunda a sábado, "
                "das 7h às 18h30."]
