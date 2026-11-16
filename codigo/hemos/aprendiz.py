"""
HEMOS — Aprendiz: o léxico cresce sozinho, sem gradiente e sem LLM.

A ideia que faz isto funcionar
──────────────────────────────
A zona de rejeição não é só uma defesa: é uma FÁBRICA DE RÓTULOS.

Quando o resolvedor se recusa a chutar, o sistema mostra o menu, e o doador
escolhe a opção certa. Nesse instante nasce um par perfeitamente rotulado:

        texto que o sistema não entendeu  →  o significado verdadeiro

Rotulado por um humano, de graça, sem ninguém anotar nada. **A recusa em chutar
é exatamente o que produz o dado que ensina.** Quanto mais honesto o sistema é
sobre o que não sabe, mais rápido ele aprende.

Por que isto é aprendizado de verdade (e não truque)
────────────────────────────────────────────────────
Não cria informação do nada — seria impossível (desigualdade de processamento
de dados: I(X; f(Y)) ≤ I(X; Y)). A informação vem do mundo, via doador. O que o
aprendiz faz é INCORPORAR essa informação por uma regra explícita, reprodutível
e auditável, em vez de por retropropagação opaca.

A garantia que separa isto de "deixar o bot aprender sozinho"
─────────────────────────────────────────────────────────────
Aprender NUNCA pode piorar a segurança. Três travas estruturais:

  1. O aprendiz escreve SÓ em superfícies (como se diz algo). Ele não tem
     acesso a normas.py — nenhuma carência, nenhum critério clínico pode ser
     alterado por aprendizado, jamais. O que a norma decide continua sendo
     decidido pela norma.
  2. Toda promoção passa por um TESTE DE REGRESSÃO: a superfície candidata só
     entra se, com ela dentro, todas as resoluções do corpus de referência
     continuarem idênticas. Uma única mudança e a promoção é recusada.
  3. Guarda de polaridade e de colisão canônica (I9): nada que embaralhe
     "sim"/"não" ou funda dois significados entra, por mais evidência que
     tenha.

O resultado é a invariante I11: o sistema fica mais esperto com o tempo e o
número de erros confiantes continua zero — provado rodando a busca adversarial
inteira DEPOIS de aprender.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import lexico as lx
import resolvedor as rv

# Quantas confirmações independentes antes de incorporar uma forma nova.
# Baixo demais aprende ruído; alto demais nunca aprende. 5 é o ponto onde uma
# digitação idiossincrática de uma pessoa só não vira regra do sistema.
CONFIRMACOES_MINIMAS = 5

ARQUIVO_PADRAO = Path(__file__).parent / "lexico_aprendido.json"


@dataclass
class Candidato:
    forma: str  # forma canônica do texto observado
    votos: dict[int, int] = field(default_factory=lambda: defaultdict(int))
    exemplos: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return sum(self.votos.values())

    @property
    def vencedor(self) -> tuple[int, int]:
        id_, n = max(self.votos.items(), key=lambda kv: kv[1])
        return id_, n

    @property
    def unanime(self) -> bool:
        """Sem contraexemplo: a mesma forma nunca significou outra coisa."""
        return len(self.votos) == 1


@dataclass
class Promocao:
    forma: str
    id: int
    confirmacoes: int
    exemplos: tuple[str, ...]

    def __str__(self) -> str:
        return (f"{self.forma!r} → {lx.nome(self.id)} "
                f"({self.confirmacoes} confirmações)")


class Aprendiz:
    def __init__(self, arquivo: Path | None = None) -> None:
        self.arquivo = arquivo or ARQUIVO_PADRAO
        self.candidatos: dict[str, Candidato] = {}
        self.aprendidas: dict[int, list[str]] = defaultdict(list)
        self.recusadas: list[tuple[str, int, str]] = []  # (forma, id, motivo)

    # ── coleta ──────────────────────────────────────────────────────────────
    def observar(self, texto: str, id_verdadeiro: int) -> None:
        """Registra um par (texto rejeitado, significado confirmado pelo menu)."""
        forma = self.canonizar_frase(texto)
        if not forma or len(forma) > 40:
            return
        c = self.candidatos.setdefault(forma, Candidato(forma))
        c.votos[id_verdadeiro] += 1
        if len(c.exemplos) < 3:
            c.exemplos.append(texto)

    @staticmethod
    def canonizar_frase(texto: str) -> str:
        return " ".join(rv.canonizar(t) for t in rv.tokenizar(rv.normalizar(texto)))

    # ── crivo ───────────────────────────────────────────────────────────────
    def _seguro(self, forma: str, alvo: int, corpus) -> tuple[bool, str]:
        """As travas. Qualquer uma que falhe barra a promoção."""
        tokens = forma.split()

        # (a) polaridade: nada com negador vira afirmação, e vice-versa.
        tem_negador = any(rv.eh_negador(t) for t in tokens)
        if alvo == lx.SIM and tem_negador:
            return False, "contém negador e viraria SIM"
        if alvo in (lx.NAO, lx.NUNCA) and any(t in rv.AFIRMADORES for t in tokens):
            return False, "contém afirmador e viraria NAO"

        # (b) colisão canônica (I9): não pode existir em outro símbolo.
        for s in lx.CATALOGO:
            for sup in s.superficies:
                if self.canonizar_frase(sup) == forma and s.id != alvo:
                    return False, f"colide com superfície de {lx.nome(s.id)}"
        for id_, formas in self.aprendidas.items():
            if forma in formas and id_ != alvo:
                return False, f"colide com forma já aprendida de {lx.nome(id_)}"

        # (c) token solitário curto: "n", "s", "ok" são perigosos demais para
        #     entrar por evidência estatística.
        if len(tokens) == 1 and len(tokens[0]) < 3:
            return False, "forma curta demais para ser inequívoca"

        # (d) TESTE DE REGRESSÃO — o crivo que realmente garante I11.
        #     Com a forma dentro, tudo que o sistema já resolvia tem que
        #     continuar resolvendo igual.
        antes = [rv.resolver(t, ctx, None) for t, ctx, _ in corpus]
        lx.EXTRAS.setdefault(alvo, []).append(forma)
        try:
            depois = [rv.resolver(t, ctx, None) for t, ctx, _ in corpus]
        finally:
            lx.EXTRAS[alvo].remove(forma)
        for (t, _, _), a, d in zip(corpus, antes, depois):
            if a.id != d.id:
                return False, (f"mudaria a resolução de {t!r}: "
                               f"{lx.nome(a.id)} → {lx.nome(d.id)}")
        return True, ""

    def avaliar_candidato(self, forma: str, alvo: int, corpus) -> tuple[bool, str]:
        """Aplica o crivo a um candidato de fora (ex.: destilado de um LLM).

        Mesmo crivo do aprendizado em operação. A origem do candidato não lhe
        dá privilégio nenhum: vindo de doador ou de modelo, passa pelas mesmas
        travas. É isso que torna seguro usar um gerador falível.
        """
        return self._seguro(self.canonizar_frase(forma), alvo, corpus)

    def incorporar(self, forma: str, alvo: int) -> None:
        canon = self.canonizar_frase(forma)
        if canon not in self.aprendidas[alvo]:
            self.aprendidas[alvo].append(canon)
            lx.EXTRAS.setdefault(alvo, []).append(canon)

    def promover(self, corpus) -> list[Promocao]:
        """Aplica o crivo em todos os candidatos maduros. Determinístico."""
        promovidas: list[Promocao] = []
        for forma in sorted(self.candidatos):  # ordem estável => reprodutível
            c = self.candidatos[forma]
            if c.total < CONFIRMACOES_MINIMAS:
                continue
            if not c.unanime:
                self.recusadas.append((forma, c.vencedor[0], "houve contraexemplo"))
                continue
            alvo, n = c.vencedor
            if forma in self.aprendidas.get(alvo, []):
                continue
            ok, motivo = self._seguro(forma, alvo, corpus)
            if not ok:
                self.recusadas.append((forma, alvo, motivo))
                continue
            self.aprendidas[alvo].append(forma)
            lx.EXTRAS.setdefault(alvo, []).append(forma)
            promovidas.append(Promocao(forma, alvo, n, tuple(c.exemplos)))
        return promovidas

    # ── persistência ────────────────────────────────────────────────────────
    def salvar(self) -> None:
        dados = {lx.nome(i): sorted(f) for i, f in self.aprendidas.items() if f}
        self.arquivo.write_text(json.dumps(dados, ensure_ascii=False, indent=2))

    def carregar_de(self, arquivo: Path) -> int:
        """Carrega um léxico gravado. Devolve quantas formas entraram."""
        if not arquivo.exists():
            return 0
        dados = json.loads(arquivo.read_text())
        n = 0
        for nome, formas in dados.items():
            simbolo = lx.POR_NOME.get(nome)
            if simbolo is None:  # símbolo aposentado: ignora, não quebra
                continue
            for f in formas:
                if f not in lx.EXTRAS.setdefault(simbolo.id, []):
                    lx.EXTRAS[simbolo.id].append(f)
                    self.aprendidas[simbolo.id].append(f)
                    n += 1
        return n

    def carregar(self) -> None:
        if not self.arquivo.exists():
            return
        dados = json.loads(self.arquivo.read_text())
        for nome, formas in dados.items():
            id_ = lx.POR_NOME[nome].id
            self.aprendidas[id_] = list(formas)
            lx.EXTRAS.setdefault(id_, []).extend(formas)


def carregar_conhecimento(base: Path | None = None) -> int:
    """Carrega, na inicialização, tudo que o sistema já sabe além do curado.

    São dois arquivos, separados de propósito:
      lexico_destilado.json  — veio da forja (LLM na bancada), ver forja.py
      lexico_aprendido.json  — veio da operação real, ver Aprendiz

    Ambos são texto legível. Apagar qualquer um deles devolve o sistema ao
    léxico escrito por gente, sem quebrar nada — é essa a diferença entre isto
    e um modelo com pesos.
    """
    base = base or Path(__file__).parent
    a = Aprendiz()
    n = a.carregar_de(base / "lexico_destilado.json")
    n += a.carregar_de(base / "lexico_aprendido.json")
    return n
