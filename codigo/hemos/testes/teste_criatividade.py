"""
HEMOS — o experimento: um sistema determinístico pode aprender e criar?

Não é uma demonstração, é uma medição com hipótese que pode falhar.

  E1  APRENDIZADO  — o sistema entende, depois de operar, expressões que não
      entendia antes, sem ninguém programá-las. Mede-se a queda da taxa de
      rejeição.

  E2  SEGURANÇA SOB APRENDIZADO (I11) — depois de aprender, o número de erros
      confiantes continua ZERO, e nenhuma norma foi alterada. Se falhar aqui,
      todo o resto é inútil: um sistema clínico que fica mais esperto às custas
      de ficar mais errado é pior que um sistema burro.

  E3  CRIAÇÃO COMPOSICIONAL — o sistema responde corretamente sobre eventos
      que NÃO estão no seu código, por herança na ontologia. Mede-se quantos
      termos nunca programados são resolvidos.

  E4  O LIMITE — sem informação nova, o aprendizado produz exatamente nada.
      É a desigualdade de processamento de dados aparecendo no experimento:
      I(X; f(Y)) ≤ I(X; Y). Se este teste "passasse" produzindo aprendizado do
      nada, seria prova de bug, não de inteligência.
"""

from __future__ import annotations

import random
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import aprendiz as ap
import lexico as lx
import normas
import ontologia as ont
import resolvedor as rv
from teste_nucleo import CORPUS, CTX_BOOL, CTX_DATA, HOJE

falhas: list[str] = []
contagem = 0


def checa(cond: bool, rotulo: str) -> None:
    global contagem
    contagem += 1
    if not cond:
        falhas.append(rotulo)


def titulo(t: str) -> None:
    print(f"\n\033[1m{t}\033[0m")


# ── E1/E2: aprendizado a partir da zona de rejeição ─────────────────────────
# Gírias e formas reais que NÃO estão no léxico curado. É o que o sistema
# rejeitaria hoje — e é exatamente o que ele deve aprender operando.
FALA_DE_RUA: tuple[tuple[str, int], ...] = (
    ("blz", lx.SIM),
    ("bora", lx.SIM),
    ("pode crer", lx.SIM),
    ("ta certo", lx.SIM),
    ("que nada", lx.NAO),
    ("nem a pau", lx.NAO),
    ("que eu saiba nao", lx.NAO),
    ("ni", lx.NAO),                      # curta demais: deve ser RECUSADA
    ("sim mas nao", lx.SIM),             # ambígua: deve ser RECUSADA
    ("ce lembra", lx.NAO_SEI),
    ("num faco ideia", lx.NAO_SEI),
    ("zero ideia", lx.NAO_SEI),
    ("jamais na vida", lx.NUNCA),
    ("nunca nem vi", lx.NUNCA),
)


def taxa_rejeicao(amostras: tuple[tuple[str, int], ...]) -> float:
    ctx = CTX_BOOL | CTX_DATA
    n = sum(1 for t, _ in amostras if not rv.resolver(t, ctx, HOJE).entendeu)
    return 100.0 * n / len(amostras)


def erros_confiantes() -> int:
    """Roda o corpus de referência e conta resoluções erradas com confiança."""
    n = 0
    for texto, ctx, esperado in CORPUS:
        r = rv.resolver(texto, ctx, HOJE)
        if esperado is None:
            n += 1 if r.entendeu else 0
        elif r.entendeu and r.id != esperado:
            n += 1
    return n


def e1_e2_aprendizado() -> None:
    titulo("E1/E2 — aprender operando, sem piorar a segurança")

    antes_rej = taxa_rejeicao(FALA_DE_RUA)
    antes_err = erros_confiantes()
    normas_antes = {k: (p.dias, p.fonte) for k, p in normas.CARENCIA.items()}

    # Simula operação: doadores escrevem gíria, o resolvedor rejeita, o menu
    # aparece, e a escolha do doador vira rótulo. Nada aqui é anotado à mão.
    a = ap.Aprendiz(arquivo=Path("/dev/null"))
    rng = random.Random(7)
    conversas = 0
    for _ in range(600):
        texto, verdadeiro = FALA_DE_RUA[rng.randrange(len(FALA_DE_RUA))]
        ctx = CTX_BOOL | CTX_DATA
        if rv.resolver(texto, ctx, HOJE).entendeu:
            continue  # já entendia: não gera rótulo
        conversas += 1
        if texto == "sim mas nao":
            # Contraexemplo realista: doadores diferentes escolhem opções
            # diferentes para a mesma frase ambígua. É o que deve BARRAR a
            # promoção — e barra por unanimidade, não por heurística.
            a.observar(texto, rng.choice([lx.SIM, lx.NAO]))
        else:
            a.observar(texto, verdadeiro)

    promovidas = a.promover(CORPUS)

    depois_rej = taxa_rejeicao(FALA_DE_RUA)
    depois_err = erros_confiantes()
    normas_depois = {k: (p.dias, p.fonte) for k, p in normas.CARENCIA.items()}

    print(f"  {conversas} rejeições viraram rótulo (custo humano: zero)")
    print(f"  aprendeu {len(promovidas)} formas novas:")
    for p in promovidas:
        print(f"     \033[92m+ {p}\033[0m")
    if a.recusadas:
        print(f"  recusou {len(a.recusadas)} pelo crivo:")
        for forma, id_, motivo in a.recusadas[:6]:
            print(f"     \033[93m- {forma!r} → {lx.nome(id_)}: {motivo}\033[0m")

    checa(len(promovidas) > 0, "E1 não aprendeu nada")
    checa(depois_rej < antes_rej, "E1 a taxa de rejeição não caiu")
    print(f"  rejeição sobre fala de rua: {antes_rej:.0f}% → \033[92m{depois_rej:.0f}%\033[0m")

    # E2 — a garantia. Este é o teste que importa.
    checa(depois_err == antes_err == 0,
          f"I11 aprendizado gerou erro confiante: {antes_err} → {depois_err}")
    checa(normas_antes == normas_depois,
          "I11 o aprendizado alterou uma norma clínica (deveria ser impossível)")

    # O teste acima, sozinho, é CIRCULAR: o crivo de promoção usa este mesmo
    # corpus como regressão, então ele não poderia falhar. A verificação
    # independente é rodar a busca adversarial INTEIRA com o léxico já
    # aprendido — 50.000 entradas mutadas que o crivo nunca viu.
    import adversario
    n, erros_adv, rejeicoes, _ = adversario.a1_resolvedor(50000)
    checa(erros_adv == 0,
          f"I11 com léxico aprendido, a busca adversarial achou {erros_adv} "
          f"erros confiantes")
    print(f"  erros confiantes no corpus: {antes_err} → \033[92m{depois_err}\033[0m | "
          f"normas clínicas alteradas: \033[92m0\033[0m")
    print(f"  verificação independente: {n} mutações contra o léxico JÁ "
          f"APRENDIDO → \033[92m{erros_adv} erros confiantes\033[0m "
          f"({100*rejeicoes/n:.1f}% rejeitadas)")

    # e o crivo tem que ter barrado exatamente os dois casos perigosos
    formas_promovidas = {p.forma for p in promovidas}
    checa("ni" not in formas_promovidas, "I11 promoveu forma curta demais")
    checa("sim mas nao" not in formas_promovidas, "I11 promoveu forma ambígua")


# ── E3: criação composicional ───────────────────────────────────────────────
# Termos que NÃO existem em lugar nenhum do código do HEMOS. Se o sistema
# responder certo sobre eles, respondeu sobre algo que ninguém programou.
NUNCA_PROGRAMADOS: tuple[tuple[str, int | None], ...] = (
    ("microagulhamento", lx.EV_TATUAGEM),
    ("micropigmentação labial", lx.EV_TATUAGEM),
    ("preenchimento com ácido hialurônico", lx.EV_TATUAGEM),
    ("apliquei botox", lx.EV_TATUAGEM),
    ("sessão de acupuntura", lx.EV_TATUAGEM),
    ("mesoterapia capilar", lx.EV_TATUAGEM),
    ("coloquei um alargador", lx.EV_TATUAGEM),
    ("fiz escarificação", lx.EV_TATUAGEM),
    ("cistoscopia", lx.EV_ENDOSCOPIA),
    ("artroscopia no joelho", lx.EV_ENDOSCOPIA),
    ("broncoscopia", lx.EV_ENDOSCOPIA),
    ("retossigmoidoscopia", lx.EV_ENDOSCOPIA),
    ("tomei a Qdenga", lx.EV_VACINA_ATENUADA),
    ("vacina de febre amarela", lx.EV_VACINA_ATENUADA),
    ("tomei BCG", lx.EV_VACINA_ATENUADA),
    # falsos amigos: a ontologia TEM que se calar
    ("tatuagem de henna", None),
    ("vacina de gripe", None),
    ("vacina de tetano", None),
    ("cortei o cabelo", None),
    ("fiz um exame de sangue", None),
    ("comprei um adesivo", None),
)


def e3_composicao() -> None:
    titulo("E3 — responder sobre eventos que ninguém programou")
    acertos = silencios_corretos = erros = 0
    for termo, esperado in NUNCA_PROGRAMADOS:
        p = ont.classificar(termo)
        obtido = p.classe.evento_base if p else None
        if obtido == esperado:
            acertos += 1 if esperado else 0
            silencios_corretos += 0 if esperado else 1
        else:
            erros += 1
            print(f"     \033[91m✗ {termo!r}: esperado "
                  f"{lx.nome(esperado) if esperado else 'silêncio'}, "
                  f"obtido {lx.nome(obtido) if obtido else 'silêncio'}\033[0m")
    checa(erros == 0, f"E3 {erros} classificações erradas")
    novos = sum(1 for t, e in NUNCA_PROGRAMADOS if e)
    print(f"  {acertos}/{novos} termos inéditos resolvidos por herança "
          f"na ontologia")
    print(f"  {silencios_corretos}/{sum(1 for t, e in NUNCA_PROGRAMADOS if not e)} "
          f"falsos amigos corretamente ignorados (silêncio > invenção)")
    print(f"  fecho: {ont.fecho_estimado()} radicais cobrindo famílias abertas "
          f"de termos — o sistema deixou de cobrir uma lista e passou a cobrir "
          f"uma estrutura")

    # a proposta é PROPOSTA: carência vem da norma, não da máquina
    p = ont.classificar("microagulhamento")
    checa(p is not None and p.carencia_dias == normas.CARENCIA[lx.EV_TATUAGEM].dias,
          "E3 a carência herdada não veio da norma")
    checa(p is not None and "PROPOSTA" in p.texto and "médico" in p.texto,
          "E3 a proposta não está marcada como pendente de homologação")
    print(f"  exemplo: {p.texto}")


# ── E4: o limite ────────────────────────────────────────────────────────────
def e4_limite() -> None:
    titulo("E4 — o limite: sem informação nova, não há aprendizado")
    a = ap.Aprendiz(arquivo=Path("/dev/null"))
    promovidas = a.promover(CORPUS)
    checa(len(promovidas) == 0,
          "E4 o aprendiz produziu conhecimento sem observar nada — isso seria bug")

    # e evidência insuficiente também não basta, por mais consistente que seja
    b = ap.Aprendiz(arquivo=Path("/dev/null"))
    for _ in range(ap.CONFIRMACOES_MINIMAS - 1):
        b.observar("beleza pode ser", lx.SIM)
    checa(len(b.promover(CORPUS)) == 0, "E4 promoveu com evidência insuficiente")
    for _ in range(2):
        b.observar("beleza pode ser", lx.SIM)
    checa(len(b.promover(CORPUS)) == 1, "E4 não promoveu ao atingir o limiar")
    print(f"  0 observações → 0 aprendizados | "
          f"{ap.CONFIRMACOES_MINIMAS - 1} observações → 0 | "
          f"{ap.CONFIRMACOES_MINIMAS + 1} observações → 1")
    print("  a informação vem do mundo; o determinismo só decide como incorporá-la")


def main() -> int:
    print("\033[1mHEMOS — aprendizado e criação determinísticos\033[0m")
    e1_e2_aprendizado()
    e3_composicao()
    e4_limite()
    print()
    if falhas:
        print(f"\033[91m✗ {len(falhas)} de {contagem} hipóteses refutadas:\033[0m")
        for f in falhas:
            print(f"   - {f}")
        return 1
    print(f"\033[92m✓ {contagem} hipóteses sustentadas\033[0m")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
