# Conciliador

Conciliação bancária sem planilha. Você solta o extrato do banco e a carteira de
títulos do ERP; o sistema casa o que tem **certeza**, mostra **por quê**, e te
entrega só o que precisa de decisão humana.

```bash
python3 conciliar.py
```

Abre em `http://127.0.0.1:8777`. Só biblioteca padrão do Python — nada para instalar.
Nada sai da máquina: os arquivos são processados em memória e apenas as suas
decisões vão para disco, em `~/.conciliador/`.

| comando | o que faz |
|---|---|
| `python3 conciliar.py` | abre a interface no navegador |
| `python3 conciliar.py extrato.ofx titulos.xlsx` | concilia direto no terminal |
| `python3 conciliar.py --prova` | roda o arnês adversarial |

Entra: **OFX/QFX** (extrato), **CSV** (qualquer separador, qualquer acentuação) e
**XLSX**. Sai: dois CSVs prontos para o Excel — os conciliados com a justificativa
de cada casamento, e as pendências com a ação sugerida para cada linha.

## O que é "certeza"

O sistema conciliar sozinho é uma promessa forte, então ela tem definição formal.
Um vínculo só é automático quando as cinco condições valem ao mesmo tempo:

1. **valor bate ao centavo** — diferença exatamente zero (dinheiro é `int` de centavos, nunca `float`);
2. **direção do dinheiro bate** — saída da conta casa com título a pagar, entrada com a receber;
3. **data cabe na janela** — 7 dias da baixa, ou 45 do vencimento;
4. **identidade confirmada** — o número do documento aparece nos dois lados, ou o nome
   casa com peso de informação alto;
5. **exclusividade mútua** — nenhuma outra hipótese de força comparável disputa as
   mesmas linhas.

Falhando a (5), o par vai para a fila humana mesmo parecendo perfeito. É esse o
ponto: *"parece perfeito" duas vezes* é exatamente como se erra em conciliação.

Duas decisões de projeto que vêm daí:

- **diferença nunca é automática.** Tarifa, juros e desconto são reconhecidos e
  mostrados ("falta R$ 3,40"), mas quem confirma é você.
- **lote (1:N e N:1) exige mais.** Um Pix que quitou três boletos é reconhecido
  como grupo, mas só vira certeza com identidade quase perfeita — a chance de uma
  soma coincidir por acaso cresce com o tamanho do grupo.

## Como ele se compara ao nome que casa

O peso de cada palavra não é uma lista que eu mantenho à mão: é **IDF calculado
sobre os seus próprios dados**. Numa carteira cheia de "COMÉRCIO LTDA", essas
palavras valem quase nada e "ALFA" vale tudo. Prefixo de 4 letras casa a 85%,
o que absorve o truncamento do extrato ("TECNOCEL COM" ainda encontra "ALFA
COMERCIO DE ELETRONICOS LTDA").

## Cada decisão sua melhora a próxima

O `~/.conciliador/<caixa>.jsonl` é um livro de eventos append-only — nada é
sobrescrito, tudo é reversível:

- **confirmar** trava aquelas linhas: no mês seguinte elas não voltam à fila;
- **recusar** é memória negativa: aquele par nunca é sugerido de novo;
- **classificar uma sobra** ensina o rótulo: a próxima igual já vem classificada.

E há um efeito colateral bom: confirmar um vínculo remove um rival, e isso pode
**promover** outra sugestão a certeza automaticamente. A fila encolhe mais rápido
do que o número de cliques.

## O que sobra do extrato não é erro

Tarifa, DARF, FGTS, folha, aplicação, rendimento, estorno — o que nunca teve
título é classificado por léxico com **direção contábil**: `RENDIMENTO APLICAÇÃO`
numa entrada é receita financeira; a mesma palavra numa saída é movimentação
interna. Transferência entre contas próprias é detectada como par `+X / −X`
próximo no tempo.

## A prova

`python3 conciliar.py --prova` gera carteiras sintéticas com a **verdade conhecida**
e mede uma coisa: *o motor já conciliou sozinho algo errado?* As armadilhas são as
que derrubam quem concilia no Excel — dois fornecedores com títulos de valor
idêntico no mesmo dia, descrição sem nome nenhum, lançamento duplicado no extrato,
juros por atraso, pagamento em lote, título não pago.

Três cenários: carteira normal (60 títulos), carteira grande e suja (200 títulos,
20% de ruído bancário, 16% de títulos em aberto) e carteira minúscula (5 títulos,
onde o IDF quase não tem dados). A meta de precisão é **1,0000 e nada menos** —
um erro automático custa mais caro que dez pendências. Recall é desejável, nunca
às custas da precisão.

Além da precisão, cada rodada verifica os invariantes: nenhuma linha em dois
vínculos, conservação de valor no grupo, direção nunca invertida, nenhum id
sumindo entre "conciliado / na fila / sem par", resultado idêntico ao reprocessar
e **independente da ordem das linhas do arquivo**.

## Estrutura

```
conciliar.py            ponto de entrada (interface, terminal, prova)
prova.py                arnês adversarial
servidor.py             HTTP local + API JSON + exportação CSV
web/interface.html      interface (uma página, sem framework)
nucleo/dinheiro.py      centavos, datas BR, fichas de nome, IDF
nucleo/leitura.py       CSV/XLSX/OFX + descoberta de colunas
nucleo/montagem.py      arquivo bruto -> lançamentos e títulos
nucleo/motor.py         geração de candidatos, certeza, invariantes
nucleo/rotulos.py       classificação do que sobra
nucleo/livro.py         livro de eventos append-only
nucleo/simulador.py     carteiras sintéticas com verdade conhecida
```

## Limites conhecidos

- Grupos são buscados até 4 títulos e 14 candidatos por contraparte; um lote de 7
  boletos não é montado sozinho (aparece como títulos em aberto).
- Multi-moeda não é tratada — um extrato em outra moeda entra como se fosse BRL.
- Carteira de 5.000 títulos leva ~40s na primeira leitura; depois disso cada
  decisão é instantânea, porque as hipóteses são geradas uma única vez.
