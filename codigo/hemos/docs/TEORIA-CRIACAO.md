# Um sistema determinístico pode aprender e criar?

Resposta curta: **sim, com um limite exato e demonstrável.** Este documento
separa o que é teorema do que é engenharia, e aponta onde cada parte é medida
por `testes/teste_criatividade.py`.

## 1. O limite (o que é impossível, e por quê)

> **Desigualdade de processamento de dados.** Se $X \to Y \to Z$ formam uma
> cadeia de Markov (isto é, $Z$ é obtido processando $Y$), então
> $$I(X; Z) \le I(X; Y).$$

Em português: **nenhum processamento cria informação sobre o mundo.** Se o
sistema sabe $I(X;Y)$ sobre o doador, nenhuma arquitetura — determinística,
neural ou mágica — faz esse número crescer sem uma nova observação. Um LLM
gigante não escapa disso; ele apenas já embutiu muita observação no treino.

Consequência prática, e é a que mata o mito: **"o sistema aprende sozinho" é
falso para qualquer sistema.** Todo aprendizado é incorporação de informação
vinda do ambiente. A pergunta boa não é *se* precisa de dado, é *de onde vem o
dado* e *qual é a regra de incorporação*.

## 2. O que é irrestrito (o que sua intuição acertou)

Criar **estrutura** não é criar **informação**, e não tem limite prático.

O Jogo da Vida é determinístico, cabe em cinco linhas, e gerou objetos que
Conway não imaginava — planadores, canhões, uma máquina de Turing. A novidade é
genuína: o autor não previa. O que não existe é *imprevisibilidade*.

Então:

$$\textbf{criatividade} = \textbf{gerador} + \textbf{seletor}$$

O gerador pode ser inteiramente determinístico. O que faz o resultado prestar é
o seletor. E aqui está a peça que já existia neste projeto sem eu ter notado:

> A busca adversarial é um gerador procurando **violar** um invariante.
> Troque o sinal e ela vira um gerador procurando **satisfazer** o invariante
> em regiões ainda não exploradas.
>
> **A mesma máquina que prova, cria.**

## 3. Os três mecanismos, do mais sólido ao mais especulativo

### M1 — Aprendizado por rótulo grátis (`aprendiz.py`) · **provado**

A zona de rejeição não é só defesa, é **fábrica de rótulos**. Quando o
resolvedor se recusa a chutar, o menu aparece e o doador escolhe. Nasce o par:

```
texto que o sistema não entendeu  →  significado verdadeiro (dito por humano)
```

Custo de anotação: zero. E a propriedade bonita é auto-reforçante: **quanto
mais honesto o sistema é sobre o que não sabe, mais rápido ele aprende.** Um
sistema que chuta não gera dado; ele gera erro silencioso.

A informação vem do mundo (M1 respeita §1). O determinismo está na **regra de
incorporação**, que é explícita, reprodutível e auditável — em vez de um
gradiente opaco.

**Medido:** 563 rejeições viraram rótulo; 11 formas novas incorporadas;
rejeição sobre fala de rua **93% → 14%**. Ninguém programou nenhuma delas.

### M2 — Criação composicional por ontologia (`ontologia.py`) · **provado**

M1 aprende formas novas de dizer coisas conhecidas — o espaço de significados
não cresce. M2 faz o espaço crescer.

Ninguém consegue listar todo procedimento estético que existe; ano que vem
aparece um nome que hoje não existe. A saída não é enumerar o mundo, é enumerar
a **estrutura** dele. "Microagulhamento" não precisa estar em lista nenhuma: é
um *procedimento com agulha na pele*, e a norma não fala de tatuagem — fala de
**exposição percutânea**. A carência é da classe, não do termo.

```
termo desconhecido ──morfologia──► classe ──herança──► carência da norma
```

O sistema passa a cobrir o **fecho** da ontologia em vez de uma lista digitada.

**Medido:** 15/15 termos que não existem em lugar nenhum do código resolvidos
corretamente; 6/6 falsos amigos ("tatuagem de henna", "vacina de gripe")
corretamente ignorados. Silêncio vale mais que invenção: quando a ontologia não
alcança, ela se cala.

### M0 — Pré-treinamento por destilação (`forja.py`) · **provado**

M1 aprende com tráfego real, então o sistema **nasce burro** e leva meses de
operação para ficar bom. A forja resolve isso: um LLM roda **uma vez, na
bancada**, e despeja o vocabulário do domínio. O que entra em produção não são
pesos — é `conhecimento/destilado.py`, um arquivo de texto legível, versionado
e removível linha a linha. Produção continua sem LLM nenhum.

|  | papel |
|---|---|
| LLM | **gerador** — falível, criativo, caro, roda uma vez |
| crivo | **seletor** — determinístico, barato, roda sempre |
| médico | homologa o que o crivo marcou como controverso |

A alucinação deixa de ser um problema a evitar e vira **ruído a filtrar**. O
gerador pode errar porque ele não decide nada.

**A trava:** o LLM ensina o sistema a FALAR, nunca a DECIDIR. Não existe
caminho que escreva em `normas.py` — o teste prova que `CARENCIA` sai idêntica.
Um LLM "lembrando" que tatuagem dá 6 meses é lembrança estatística: pode estar
errada, desatualizada ou ser de outro país.

**Medido:** 152 candidatos → 139 aceitos, 5 barrados, 8 para revisão médica;
cobertura de vocabulário real **29% → 74%**; ontologia de 33 para 55 radicais;
0 erros confiantes em 50.000 mutações com o léxico destilado carregado.

**O crivo barrou o próprio gerador**, inclusive num erro real: `"sem dúvida" →
SIM` foi recusado porque "sem" é negador no sistema — a forma inverteria o
sentido. E o corpus adversarial que o gerador escreveu *contra si mesmo*
encontrou quatro bugs no resolvedor, sendo um clinicamente grave: **"tenho 45
anos" respondido na pergunta de peso era lido como 45 kg e reprovava a pessoa
por peso mínimo.**

### M3 — Indução de regra a partir de desfecho · **projetado, não implementado**

O hemocentro registra o veredito da triagem presencial. Sempre que ele diverge
do HEMOS, existe um par `(fatos, desfecho real)`. Um indutor simbólico
(no espírito de ILP — *Inductive Logic Programming*) busca o **menor predicado
que separa os casos divergentes** e propõe uma regra nova, com sua evidência.

É onde o sistema deixaria de aplicar a norma e passaria a **descobrir a norma
tácita da casa** — o "mecânico que sente o cheiro do óleo". É o mais valioso e
o mais perigoso, e por isso: **propõe ao médico responsável, nunca aplica.**

## 4. A garantia que separa isto de "deixar o bot aprender sozinho"

Aprendizado só é aceitável num sistema clínico se for **impossível** que ele
piore a segurança. Três travas estruturais, não três boas intenções:

1. **Separação de poderes.** O aprendiz escreve só em *superfícies* — como as
   pessoas dizem as coisas. Ele não tem acesso a `normas.py`. Nenhuma carência,
   nenhum critério clínico pode ser tocado por aprendizado, jamais.
2. **Teste de regressão na promoção.** A forma candidata só entra se, com ela
   dentro, **todas** as resoluções do corpus de referência continuarem
   idênticas. Uma única mudança e a promoção é recusada.
3. **Guardas de polaridade e colisão.** Nada que embaralhe "sim"/"não", nada que
   funda dois significados (I9), nada curto demais para ser inequívoco — por
   mais evidência que tenha.

Isso é a invariante **I11**: *o sistema fica mais esperto e o número de erros
confiantes continua zero.*

### Uma correção que eu tive que fazer no próprio experimento

A primeira versão de I11 era **circular**: o crivo de promoção usa o corpus como
teste de regressão, e eu media o erro nesse mesmo corpus. Não podia falhar.

A verificação honesta é independente: rodar a busca adversarial inteira **com o
léxico já aprendido** — 50.000 entradas mutadas que o crivo nunca viu.
Resultado: **0 erros confiantes**. Só esse número vale como prova.

## 5. O experimento que pode falhar

`python3 testes/teste_criatividade.py`

| | hipótese | resultado |
|---|---|---|
| **E1** | o sistema entende, após operar, o que não entendia antes | rejeição **93% → 14%**, 11 formas aprendidas |
| **E2** | aprender não degrada a segurança (I11) | **0** erros confiantes em 50.000 mutações pós-aprendizado; **0** normas alteradas |
| **E3** | responde certo sobre eventos que ninguém programou | **15/15** inéditos; **6/6** falsos amigos ignorados |
| **E4** | sem informação nova, o aprendizado produz nada | 0 obs → 0; 4 obs → 0; 6 obs → 1 |

**E4 é o mais importante do conjunto**, e existe para poder falhar. Se o
aprendiz produzisse conhecimento a partir de zero observações, isso não seria
inteligência emergente — seria prova de bug. O teste protege contra a tentação
de acreditar na própria tese.

## 6. Então: é um "modelo generalista determinístico"?

Depende do que "generalista" significa, e a distinção é o projeto inteiro:

- **Generalista = responde sobre qualquer assunto do mundo.** Não. Isso exige
  ter absorvido o mundo, e §1 diz de onde essa informação teria que vir.
- **Generalista = generaliza para entradas nunca vistas dentro do domínio.**
  Sim, e está medido: formas de falar que ninguém digitou (M1) e eventos que
  ninguém programou (M2).

O que este sistema é, com precisão: **um generalizador determinístico de domínio
fechado, que amplia sozinho tanto seu vocabulário quanto sua ontologia, sob
invariantes que ele não pode violar nem depois de aprender.**

Não é ficção. Mas também não é um LLM pequeno — é outra coisa, e a vantagem é
justamente o que o LLM não tem: cada coisa que ele aprendeu é uma linha legível
num arquivo, com quantas confirmações a sustentam, removível a qualquer momento
sem retreinar nada.
