"""
exemplo_parcelamento.py — demonstra o método com um caso real de BPO:
dividir um valor em N parcelas.

Rode:  python3 exemplo_parcelamento.py
Ele PROVA duas coisas:
  1) o arnês ENCONTRA a brecha da versão ingênua (a que "passou nos testes");
  2) a versão corrigida sobrevive a dezenas de milhares de tentativas adversariais.
"""

from prova import provar, executar


# ---------------------------------------------------------------- ingênua
def parcelar_ingenuo(total: float, n: int):
    """Como quase todo mundo escreve. Passa em `parcelar(100, 2)`. Vaza dinheiro."""
    p = round(total / n, 2)
    return [p] * n


# --------------------------------------------------------------- corrigida
def parcelar(total: float, n: int):
    """Dinheiro é inteiro em centavos. O resto vai nas primeiras parcelas."""
    if n <= 0:
        raise ValueError("n deve ser >= 1")
    centavos = int(round(total * 100))
    base, resto = divmod(centavos, n)
    return [(base + (1 if i < resto else 0)) / 100 for i in range(n)]


# --------------------------------------------------------------- gerador
def gerador(rnd, escala):
    return {
        "total": round(rnd.uniform(0.01, 1 + 999_999 * escala), 2),
        "n": rnd.randint(1, 1 + int(59 * escala)),
    }


# ------------------------------------------------------------ invariantes
def soma_bate(fn):
    def inv(caso):
        p = fn(caso["total"], caso["n"])
        return int(round(sum(p) * 100)) == int(round(caso["total"] * 100))
    return inv


def sem_parcela_negativa(fn):
    def inv(caso):
        return all(x >= 0 for x in fn(caso["total"], caso["n"]))
    return inv


def diferenca_maxima_um_centavo(fn):
    def inv(caso):
        p = fn(caso["total"], caso["n"])
        return int(round((max(p) - min(p)) * 100)) <= 1
    return inv


if __name__ == "__main__":
    print("\n>>> 1. O arnês precisa ACHAR o bug da versão ingênua:")
    executar([
        provar("INGENUO: soma das parcelas == total",
               gerador, soma_bate(parcelar_ingenuo), 20_000),
    ], titulo="CACA A BRECHA")

    print("\n>>> 2. A versão corrigida precisa sobreviver:")
    codigo = executar([
        provar("soma das parcelas == total",
               gerador, soma_bate(parcelar), 20_000),
        provar("nenhuma parcela negativa",
               gerador, sem_parcela_negativa(parcelar), 20_000),
        provar("diferenca entre parcelas <= 1 centavo",
               gerador, diferenca_maxima_um_centavo(parcelar), 20_000),
    ])
    raise SystemExit(codigo)
