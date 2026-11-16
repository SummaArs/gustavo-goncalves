"""
HEMOS — invariantes do núcleo.

Não é uma lista de casos de teste. Cada bloco declara uma PROPRIEDADE que o
sistema deve satisfazer para qualquer entrada; testes/adversario.py depois roda
uma busca cuja função objetivo é violá-las.

  I1  Determinismo          mesma entrada -> mesmo símbolo, sempre.
  I2  Zona de rejeição      o resolvedor ou acerta ou rejeita; nunca devolve
                            um símbolo ERRADO com confiança.
  I3  Aritmética das normas libera_em = max(evento + carência), exato ao dia.
  I4  Falha fechada         informação ausente/duvidosa nunca relaxa o critério.
  I5  Rastreabilidade       todo motivo emitido cita a norma que o gerou.
  I6  Não-discriminação     nenhum critério do sistema usa orientação sexual
                            ou identidade de gênero (ADI 5543/2020, STF).
  I7  Isocronia             a sequência de perguntas é idêntica para todos os
                            doadores; nenhum veredito parcial vaza no caminho.
  I8  Terminação            toda conversa termina em número limitado de passos.
"""

from __future__ import annotations

import random
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import conversa as cv
import lexico as lx
import normas
import resolvedor as rv

HOJE = date(2026, 7, 29)
falhas: list[str] = []
contagem = 0


def checa(condicao: bool, rotulo: str) -> None:
    global contagem
    contagem += 1
    if not condicao:
        falhas.append(rotulo)


def titulo(t: str) -> None:
    print(f"\n\033[1m{t}\033[0m")


# ── I1/I2: resolvedor ───────────────────────────────────────────────────────
# (texto, contexto, esperado)  — esperado None significa "deve rejeitar".
CTX_DATA = {lx.VALOR_DATA, lx.NUNCA, lx.NAO, lx.NAO_SEI, lx.VOLTAR, lx.PARAR, lx.HUMANO}
CTX_BOOL = {lx.SIM, lx.NAO, lx.NAO_SEI, lx.VOLTAR, lx.PARAR, lx.HUMANO}
CTX_MENU = {lx.QUERO_DOAR, lx.QUERO_HORARIOS, lx.QUERO_ENDERECO, lx.QUERO_DOCUMENTOS,
            lx.QUERO_ESTOQUE, lx.HUMANO, lx.PARAR}

CORPUS: tuple[tuple[str, set, int | None], ...] = (
    # afirmação e negação — o par mais perigoso do sistema
    ("sim", CTX_BOOL, lx.SIM),
    ("Sim!", CTX_BOOL, lx.SIM),
    ("SIM 👍", CTX_BOOL, lx.SIM),
    ("nao", CTX_BOOL, lx.NAO),
    ("não", CTX_BOOL, lx.NAO),
    ("Não.", CTX_BOOL, lx.NAO),
    ("nunca tive", CTX_BOOL, lx.NAO),
    ("não tenho", CTX_BOOL, lx.NAO),
    ("não, nunca fiz isso", CTX_BOOL, lx.NAO),
    ("nao sei", CTX_BOOL, lx.NAO_SEI),
    ("não lembro", CTX_BOOL, lx.NAO_SEI),
    ("não tenho certeza", CTX_BOOL, lx.NAO_SEI),
    # negação com escopo: negador ANTES do gatilho inverte
    ("não tive", CTX_BOOL, lx.NAO),
    ("nao fiz", CTX_BOOL, lx.NAO),
    # datas
    ("15/03/2026", CTX_DATA, lx.VALOR_DATA),
    ("ontem", CTX_DATA, lx.VALOR_DATA),
    ("mês passado", CTX_DATA, lx.VALOR_DATA),
    ("há 3 meses", CTX_DATA, lx.VALOR_DATA),
    ("faz uns 2 anos", CTX_DATA, lx.VALOR_DATA),
    ("12 de março de 2025", CTX_DATA, lx.VALOR_DATA),
    ("nunca", CTX_DATA, lx.NUNCA),
    ("nunca aconteceu", CTX_DATA, lx.NUNCA),
    # intenções
    ("quero doar sangue", CTX_MENU, lx.QUERO_DOAR),
    ("oi, gostaria de doar", CTX_MENU, lx.QUERO_DOAR),
    ("que horas vocês abrem?", CTX_MENU, lx.QUERO_HORARIOS),
    ("onde fica?", CTX_MENU, lx.QUERO_ENDERECO),
    ("o que preciso levar", CTX_MENU, lx.QUERO_DOCUMENTOS),
    ("quero falar com atendente", CTX_MENU, lx.HUMANO),
    # devem REJEITAR: fora do contexto, ambíguo ou sem sentido
    ("asdkjhasd", CTX_BOOL, None),
    ("", CTX_BOOL, None),
    ("🙂🙂🙂", CTX_BOOL, None),
    ("quero doar sangue", CTX_BOOL, None),  # intenção fora do contexto de resposta
    ("32/13/2026", CTX_DATA, None),  # data impossível
    ("01/01/2099", CTX_DATA, None),  # futuro
)


def bloco_resolvedor() -> None:
    titulo("I1/I2 — resolvedor: determinismo e zona de rejeição")
    erros_confiantes = 0
    recusas = 0
    for texto, ctx, esperado in CORPUS:
        r1 = rv.resolver(texto, ctx, HOJE)
        r2 = rv.resolver(texto, ctx, HOJE)
        checa(r1.id == r2.id and r1.valor == r2.valor, f"I1 determinismo: {texto!r}")
        if esperado is None:
            checa(not r1.entendeu, f"I2 deveria rejeitar {texto!r}, veio {lx.nome(r1.id)}")
        elif r1.id == esperado:
            pass
        elif not r1.entendeu:
            recusas += 1
        else:
            erros_confiantes += 1
            falhas.append(f"I2 ERRO CONFIANTE: {texto!r} -> {lx.nome(r1.id)} "
                          f"(esperado {lx.nome(esperado)})")
    checa(erros_confiantes == 0, "I2 erro confiante > 0")
    entendidos = sum(1 for t, c, e in CORPUS if e is not None) - recusas
    total = sum(1 for t, c, e in CORPUS if e is not None)
    print(f"  corpus: {len(CORPUS)} entradas | acertos {entendidos}/{total} "
          f"| recusas {recusas} | erros confiantes {erros_confiantes}")


# ── I3/I4/I5: normas ────────────────────────────────────────────────────────
def bloco_lexico() -> None:
    titulo("I9 — léxico: nenhuma colisão sob a forma canônica")
    # O resolvedor colapsa letras repetidas ("simmm" -> "sim") para absorver
    # ênfase. Isso só é seguro se a canonização não fundir dois significados
    # diferentes. Aqui isso deixa de ser esperança e vira invariante.
    visto: dict[str, int] = {}
    for s in lx.CATALOGO:
        for sup in s.superficies:
            chave = " ".join(rv.canonizar(t) for t in sup.split())
            dono = visto.get(chave)
            checa(dono is None or dono == s.id,
                  f"I9 colisão canônica: {sup!r} pertence a {lx.nome(s.id)} e "
                  f"{lx.nome(dono)}" if dono else "ok")
            visto[chave] = s.id
    # e a afirmação mais comum do sistema jamais pode ser lida como negação
    checa(not rv.eh_negador("sim"), "I9 'sim' classificado como negador")
    checa(not rv.eh_negador("simmm"), "I9 'simmm' classificado como negador")
    checa(rv.eh_negador("nao") and rv.eh_negador("nãoo".replace("ã", "a"))
          and rv.eh_negador("naot") and rv.eh_negador("nunca"),
          "I9 negador com ruído não foi reconhecido")
    print(f"  {len(visto)} superfícies canônicas, todas sem colisão")


def bloco_normas() -> None:
    titulo("I3/I4/I5 — normas: aritmética, falha fechada, rastreabilidade")

    def f(**kw):
        return {getattr(lx, k): v for k, v in kw.items()}

    # intervalo entre doações, exato ao dia
    v = normas.avaliar(f(EV_ULTIMA_DOACAO=HOJE - timedelta(days=59),
                         VALOR_SEXO_BIOLOGICO="M"), HOJE)
    checa(v.nivel == normas.TEMPORARIO and v.libera_em == HOJE + timedelta(days=1),
          "I3 homem 59 dias -> falta 1 dia")
    v = normas.avaliar(f(EV_ULTIMA_DOACAO=HOJE - timedelta(days=60),
                         VALOR_SEXO_BIOLOGICO="M"), HOJE)
    checa(v.nivel == normas.APTO, "I3 homem 60 dias -> apto")
    v = normas.avaliar(f(EV_ULTIMA_DOACAO=HOJE - timedelta(days=60),
                         VALOR_SEXO_BIOLOGICO="F"), HOJE)
    checa(v.nivel == normas.TEMPORARIO, "I3 mulher 60 dias -> ainda não")

    # I4 falha fechada: sem sexo informado, aplica o critério mais restritivo
    v = normas.avaliar(f(EV_ULTIMA_DOACAO=HOJE - timedelta(days=60)), HOJE)
    checa(v.nivel == normas.TEMPORARIO, "I4 sexo não informado -> critério restritivo (90d)")

    # I4 "não sei" NÃO é "nunca aconteceu": vira lacuna, não liberação.
    v = normas.avaliar({lx.EV_TATUAGEM: normas.DESCONHECIDO}, HOJE)
    checa(v.nivel == normas.APTO and not v.conclusivo and len(v.lacunas) == 1,
          "I4 'não sei' deve virar lacuna, não ausência de evento")
    v = normas.avaliar({lx.EV_TATUAGEM: None}, HOJE)
    checa(v.conclusivo, "I4 'nunca' é conclusivo e não gera lacuna")

    # carências: fronteira exata
    v = normas.avaliar(f(EV_TATUAGEM=HOJE - timedelta(days=179)), HOJE)
    checa(v.nivel == normas.TEMPORARIO, "I3 tatuagem 179 dias -> inapto")
    v = normas.avaliar(f(EV_TATUAGEM=HOJE - timedelta(days=180)), HOJE)
    checa(v.nivel == normas.APTO, "I3 tatuagem 180 dias -> apto")

    # libera_em é o MÁXIMO das liberações — a tese em uma linha
    fatos = f(EV_TATUAGEM=HOJE - timedelta(days=100),   # libera +80
              EV_GRIPE=HOJE - timedelta(days=2),        # libera +5
              EV_ENDOSCOPIA=HOJE - timedelta(days=10))  # libera +170
    v = normas.avaliar(fatos, HOJE)
    checa(v.libera_em == HOJE + timedelta(days=170), "I3 libera_em = max das liberações")
    checa(len(v.motivos) == 3, "I3 três motivos acumulados")

    # idade
    v = normas.avaliar(f(VALOR_NASCIMENTO=date(2011, 5, 10)), HOJE)  # 15 anos
    checa(v.nivel == normas.TEMPORARIO and v.libera_em == date(2027, 5, 10),
          "I3 menor de 16 -> libera no 16º aniversário")
    v = normas.avaliar(f(VALOR_NASCIMENTO=date(2009, 5, 10)), HOJE)  # 17 anos
    checa(v.nivel == normas.APTO and v.condicoes, "I3 17 anos -> apto com responsável")
    v = normas.avaliar(f(VALOR_NASCIMENTO=date(1955, 5, 10)), HOJE)  # 71 anos
    checa(v.nivel == normas.DEFINITIVO, "I3 acima de 69 -> definitivo")
    v = normas.avaliar(f(VALOR_NASCIMENTO=date(1963, 5, 10), EV_ULTIMA_DOACAO=None), HOJE)
    checa(v.nivel == normas.DEFINITIVO, "I3 primeira doação após os 60 -> definitivo")
    v = normas.avaliar(f(VALOR_NASCIMENTO=date(1963, 5, 10),
                         EV_ULTIMA_DOACAO=HOJE - timedelta(days=400)), HOJE)
    checa(v.nivel == normas.APTO, "I3 já era doador, 63 anos -> apto")

    # peso e definitivos
    v = normas.avaliar(f(VALOR_PESO=49.9), HOJE)
    checa(v.nivel == normas.TEMPORARIO and v.indeterminado, "I3 peso < 50 -> sem data")
    v = normas.avaliar(f(VALOR_PESO=50.0), HOJE)
    checa(v.nivel == normas.APTO, "I3 peso 50 -> apto")
    v = normas.avaliar(f(EV_HEPATITE_APOS_11=date(2000, 1, 1)), HOJE)
    checa(v.nivel == normas.DEFINITIVO and v.libera_em is None,
          "I3 hepatite após 11 anos -> definitivo sem data")

    # I5 rastreabilidade
    for p in list(normas.CARENCIA.values()) + [normas.PESO_MINIMO, normas.IDADE_MINIMA,
                                               normas.IDADE_MAXIMA, normas.IDADE_MAXIMA_PRIMEIRA]:
        checa(bool(p.fonte.strip()), f"I5 parâmetro sem fonte: {p.descricao}")
    todos = {}
    for ev in normas.CARENCIA:
        todos[ev] = HOJE
    todos[lx.VALOR_PESO] = 40.0
    todos[lx.VALOR_NASCIMENTO] = date(2011, 1, 1)
    v = normas.avaliar(todos, HOJE)
    for m in v.motivos:
        checa(bool(m.fonte.strip()), f"I5 motivo sem fonte: {m.codigo}")
    print(f"  {len(v.motivos)} motivos emitidos, todos com fonte normativa")

    nao_homologados = sum(1 for p in normas.CARENCIA.values() if not p.homologado)
    print(f"  \033[93m{nao_homologados}/{len(normas.CARENCIA)} parâmetros ainda não "
          f"homologados pelo médico responsável\033[0m")


# ── I6: não-discriminação ───────────────────────────────────────────────────
PROIBIDOS = ("homossexual", "gay", "lesbica", "orientacao sexual", "hsh",
             "identidade de genero", "travesti", "transexual", "promiscu")


def bloco_nao_discriminacao() -> None:
    titulo("I6 — nenhum critério por orientação sexual ou identidade de gênero")
    alvo = " ".join(p.texto.lower() for p in cv.ROTEIRO)
    alvo += " " + " ".join(s for p in cv.ROTEIRO for s in p.opcoes)
    alvo += " " + " ".join(par.descricao.lower() for par in normas.CARENCIA.values())
    alvo = rv.normalizar(alvo)
    for termo in PROIBIDOS:
        checa(rv.normalizar(termo) not in alvo, f"I6 termo proibido no roteiro: {termo}")
    # o único uso de sexo é fisiológico (intervalo) e opcional
    p_sexo = [p for p in cv.ROTEIRO if p.chave == lx.VALOR_SEXO_BIOLOGICO]
    checa(len(p_sexo) == 1 and "não influencia a aptidão" in p_sexo[0].texto,
          "I6 pergunta de sexo deve declarar que não afeta aptidão")
    checa("prefiro não informar" in p_sexo[0].opcoes, "I6 sexo deve ser opcional")
    print("  roteiro limpo; sexo biológico usado só para o intervalo entre doações")


# ── I7/I8: conversa ─────────────────────────────────────────────────────────
VAZAM = ("apto", "inapto", "impede", "carencia", "liberacao", "podera doar",
         "nao pode doar", "reprovado", "motivo")


def trajeto(rng: random.Random) -> cv.Sessao:
    s = cv.Sessao(hoje=HOJE)
    s.passo("quero doar")
    while s.estado == cv.TRIAGEM:
        p = s.pergunta
        assert p is not None
        if p.tipo == "DATA":
            resposta = rng.choice(["1", "2", "3", "4", "5", "6", "nunca", "ontem",
                                   "há 2 meses", "10/01/2025"])
        elif p.tipo == "BOOL":
            resposta = rng.choice(["sim", "nao", "1", "2", "3"])
        elif p.tipo == "SEXO":
            resposta = rng.choice(["1", "2", "3", "masculino", "feminino"])
        elif p.tipo == "PESO":
            resposta = rng.choice(["48", "50", "72,5", "95 kg"])
        elif p.tipo == "DOACOES":
            resposta = rng.choice(["0", "1", "3", "5", "nenhuma"])
        else:
            resposta = rng.choice(["15/03/1998", "01/01/2010", "20/06/1950"])
        s.passo(resposta)
    return s


def bloco_conversa() -> None:
    titulo("I7/I8 — conversa: isocronia e terminação")
    rng = random.Random(20260729)
    assinaturas = set()
    niveis = {0: 0, 1: 0, 2: 0}
    reapresentacoes = perguntas_totais = humanos = 0
    for _ in range(400):
        s = cv.Sessao(hoje=HOJE, telefone=f"5511{rng.randrange(10**8):08d}")
        msgs = s.passo("quero doar")
        sequencia = []
        vazou = None
        while s.estado == cv.TRIAGEM:
            p = s.pergunta
            # Reapresentar a mesma pergunta não é pergunta nova: o número de
            # reapresentações depende de como o doador escreve, não do
            # veredito, logo não vaza nada. O que a isocronia exige é que a
            # sequência de perguntas DO ROTEIRO seja sempre a mesma.
            if not sequencia or sequencia[-1] != p.chave:
                sequencia.append(p.chave)
                perguntas_totais += 1
            else:
                reapresentacoes += 1
            for m in msgs:
                n = rv.normalizar(m)
                for termo in VAZAM:
                    if rv.normalizar(termo) in n:
                        vazou = (p.chave, termo)
            if p.tipo == "DATA":
                # Como a pergunta agora é aberta, o doador responde em
                # português. Pesos realistas: a maioria dos eventos clínicos é
                # "nunca" — sem isso, o sorteio uniforme faz ~97% dos trajetos
                # baterem em hepatite/Chagas e só o ramo DEFINITIVO é exercido.
                r = rng.choices(
                    ["nunca", "nunca aconteceu", "não, nunca", "ontem",
                     "mês passado", "há 3 meses", "faz uns 2 anos",
                     "10/01/2025", "não sei", "1", "6"],
                    weights=[35, 10, 8, 4, 6, 6, 6, 8, 3, 7, 7])[0]
            elif p.tipo == "BOOL":
                r = rng.choices(["sim", "nao", "não", "claro que não", "1", "2"],
                                weights=[1, 4, 4, 2, 1, 4])[0]
            elif p.tipo == "SEXO":
                r = rng.choice(["masculino", "feminino", "prefiro não informar", "1", "2"])
            elif p.tipo == "PESO":
                r = rng.choice(["48", "50", "72,5", "uns 68 kg", "pesos 90"])
            elif p.tipo == "DOACOES":
                r = rng.choice(["0", "1", "5", "nenhuma", "duas"])
            else:
                r = rng.choice(["15/03/1998", "01/01/2010", "20/06/1950"])
            msgs = s.passo(r)
        checa(vazou is None, f"I7 veredito vazou durante a triagem: {vazou}")
        if s.veredito is None:
            # Caminho legítimo: 3 respostas seguidas ininteligíveis encerram em
            # atendente humano. É falha fechada, não violação — mas a taxa
            # importa como número de produto, então é contada.
            humanos += 1
            continue
        checa(s.perguntas_feitas == cv.TAMANHO_ROTEIRO,
              f"I7 número de perguntas variou: {s.perguntas_feitas}")
        assinaturas.add(tuple(sequencia))
        niveis[s.veredito.nivel] += 1
    checa(len(assinaturas) == 1,
          f"I7 a SEQUÊNCIA de perguntas variou entre doadores ({len(assinaturas)} variantes)")
    atrito = 100 * reapresentacoes / max(perguntas_totais, 1)
    print(f"  400 trajetos | 1 única sequência de {cv.TAMANHO_ROTEIRO} perguntas | "
          f"vereditos: {niveis[0]} aptos, {niveis[1]} temporários, {niveis[2]} definitivos")
    print(f"  atrito do fluxo aberto (sem menu): {atrito:.1f}% das perguntas "
          f"precisaram ser reapresentadas")

    # I10 — a VOZ não pode virar canal lateral.
    # Humanizar é livre, desde que a superfície dependa só de (doador, posição)
    # e nunca do que a pessoa respondeu. Se a formulação ou o "certo, anotado"
    # reagissem ao conteúdo, o texto entregaria o gabarito por fora — mesmo com
    # o veredito guardado até o fim. Aqui isso deixa de ser cuidado e vira
    # invariante: mesmo telefone + respostas opostas => textos idênticos.
    respostas_a = {"DATA": "nunca", "BOOL": "nao", "SEXO": "masculino",
                   "PESO": "80", "DOACOES": "0", "NASCIMENTO": "10/10/1990"}
    respostas_b = {"DATA": "ontem", "BOOL": "sim", "SEXO": "feminino",
                   "PESO": "45", "DOACOES": "9", "NASCIMENTO": "01/01/2011"}
    textos: list[list[str]] = []
    for respostas in (respostas_a, respostas_b):
        s = cv.Sessao(hoje=HOJE, telefone="5500000000001", nome="Marta Silva")
        s.passo("quero doar")
        vistos: list[str] = []
        while s.estado == cv.TRIAGEM:
            p = s.pergunta
            vistos.append(s._texto_pergunta(p))
            s.passo(respostas[p.tipo])
        textos.append(vistos)
    checa(textos[0] == textos[1],
          "I10 o texto das perguntas mudou conforme as respostas (canal lateral)")
    # e a voz varia entre doadores diferentes (senão não é voz, é script)
    s2 = cv.Sessao(hoje=HOJE, telefone="5521777776666")
    s2.passo("quero doar")
    variou = s2._texto_pergunta(s2.pergunta) != textos[0][0]
    print(f"  I10 voz estável sob respostas opostas; varia entre doadores: "
          f"{'sim' if variou else 'não'}")

    # I8 terminação: mesmo com entrada hostil, a conversa fecha.
    s = cv.Sessao(hoje=HOJE)
    s.passo("quero doar")
    for _ in range(50):
        if s.estado == cv.FIM:
            break
        s.passo("xxxxxxxx")
    checa(s.estado == cv.FIM, "I8 conversa não terminou sob entrada ininteligível")
    print("  entrada ininteligível repetida -> encerra em atendente humano (falha fechada)")


def main() -> int:
    bloco_resolvedor()
    bloco_lexico()
    bloco_normas()
    bloco_nao_discriminacao()
    bloco_conversa()
    print()
    if falhas:
        print(f"\033[91m✗ {len(falhas)} violação(ões) em {contagem} verificações:\033[0m")
        for f in falhas:
            print(f"   - {f}")
        return 1
    print(f"\033[92m✓ {contagem} verificações, 0 violações\033[0m")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
