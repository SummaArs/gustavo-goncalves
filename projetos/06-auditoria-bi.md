# Auditoria e BI

## Auditoria de importação de uma importadora de vinhos

A auditoria externa precisava da composição de fornecedores internacionais, adiantamentos e importação em andamento de 15 meses. Escrevi um extrator que lê as planilhas (inclusive o formato binário antigo do Excel, com um leitor que eu fiz na mão porque não dava pra instalar biblioteca), regras puras num núcleo separado, e um relatório num HTML único cifrado com senha.

A primeira versão era bonita e confusa. O pedido foi "tem que gritar o que resolver". Refiz como 5 problemas em ordem de valor, cada um com o que está errado, quanto vale, um gráfico que prova e quem tem que fazer o quê. Depois veio o cruzamento com câmbio, declaração de importação e financiamento: 25 mil tentativas adversariais e 7 bugs plantados.

## Contrato contra nota fiscal

Uma empresa de software emitia nota pra uma companhia aérea seguindo um contrato em dólar com marcos "Month 21", "Month 24" e assim por diante, sem data. Cada marco gera 4 notas em real. A prova que fecha: as 3 notas de implantação de um marco têm que sair de uma taxa de câmbio única aplicada às bases do contrato, no centavo. Testei por interseção de intervalos com fração exata, sem tolerância chutada. 4 marcos, 12 notas, 0 violações, e 194.259 adulterações plantadas sem nenhuma escapar.

## Portal de colaboradores para um BPO de RH

A dor era gente sobrescrevendo a mesma planilha ao mesmo tempo. Fiz um portal em cima do Google (formulário, planilha como banco e site em Apps Script), pra que o dado não saia do Google delas. Cada linha tem versão, então conflito não sobrescreve. Excluir nunca apaga, vai pra lixeira. Ação perigosa exige digitar o nome do alvo e só quem tem permissão de aprovar executa. Tem CPF e RG ali dentro, então o isolamento por empresa é decidido no servidor. Prova com 3.000 rodadas e 6 de 6 mutantes.
