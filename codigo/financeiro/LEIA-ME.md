# Financeiro — contas a receber/pagar + razão

Estudado no Odoo 18 (`addons/account`, lido com o REA + o código-fonte em
`~/Python/rea/alvos/odoo18`) e refeito com o que lá falta. Só biblioteca padrão.

```bash
python3 servidor.py           # livro real em dados/livro.jsonl → http://127.0.0.1:8790
python3 servidor.py --demo    # livro de demonstração (dados/demo.jsonl)
python3 prova.py              # prova de fogo + 7 mutantes
```

| Odoo 18 | Aqui |
|---|---|
| dinheiro em `float` + `ROUND` no SQL | centavos `int`; equilíbrio exato |
| lançamento postado volta a rascunho (`button_draft`) | livro que só cresce; correção = **estorno** |
| saldo em aberto/situação cacheados no banco | derivados do livro a cada leitura |
| sem chave de idempotência | chave por intenção: repetir = confirmação; mesma chave com outro conteúdo = recusa |
| — | cada linha leva o hash da anterior: arquivo adulterado não abre |

Copiado do Odoo por ser bom: partidas dobradas, baixa parcial
(`partial_reconcile`), situações aberto/parcial/pago/estornado, data de fechamento.

## Prova (15/10/2026)
- 3.000 sequências aleatórias (≈12,7 mil títulos, 11,8 mil baixas, 1,4 mil estornos aceitos;
  o resto recusado de propósito), 9 invariantes **depois de cada operação**: lançamento
  equilibrado, balancete zera, `0 ≤ saldo ≤ valor`, **duas testemunhas** (subrazão do título =
  razão contábil marcada com o título), Clientes/Fornecedores = soma dos abertos, banco = baixas
  ativas, recusa não muda nada, nada entra em período fechado, replay do disco = memória,
  adulteração detectada. **0 violações.**
- **7/7 mutantes acusados** (defeito plantado no próprio fonte).
- No navegador, pela tela: lançar, baixa parcial, estorno, recusa de baixa acima do saldo,
  colisão de chave. Conferido no livro pela API, não pelo que a tela dizia.
- Contraste medido: fundo ≥ 23,1 de L* abaixo do cartão (claro) e 23,2 (escuro).

## Não feito / não verificado
- Multiempresa, várias contas bancárias, impostos, NF-e, importação de extrato (o
  Conciliador já faz isso), usuários e permissões, integração com o Omie (via Eclusa).
- Concorrência entre dois processos no mesmo arquivo (o servidor serializa com trava;
  dois servidores no mesmo livro não são suportados).
