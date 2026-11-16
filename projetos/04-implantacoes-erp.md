# Implantações de ERP

Tirar uma empresa do sistema antigo e colocar no ERP novo sem perder nada. Parece trabalho braçal, mas é onde mais aprendi a desconfiar do sistema.

## Indústria agroflorestal

Foi a implantação mais longa. Migrei o plano de custos do ERP legado (uns 180 códigos) pra categorias do ERP novo, e a decisão que estruturou tudo foi perceber que o legado tinha uma dimensão só e o novo tem quatro: categoria, departamento, conta corrente e projeto. Depois vieram as tabelas base, o inventário com lote, o histórico de notas de venda e as fichas de produção.

O inventário fechou com 293 de 330 produtos com saldo igual ao contado, depois 323 de 330 no ar com 1,66 milhão de unidades. Aprendi que a consulta de lote soma todos os locais de estoque, e que verificar o total não prova a composição: o ERP aceitou 6 lotes, gravou 1 com o total, e o saldo bateu exatamente.

Teve um incidente que eu conto sem vergonha porque ensinou muito. Uma importação de notas antigas pela tela, com uma configuração desmarcada, gerou 1.330 títulos falsos somando R$ 7,19 milhões numa conta de um cliente. Estoque não foi mexido. Fiz uma ferramenta de limpeza com 5 invariantes, conferi cada exclusão e deixei intactas as 117 notas que já faziam parte da conciliação. Depois escrevi o guia de como importar certo.

## Locadora de equipamentos

4.484 produtos, 3.872 com saldo, 13.089 unidades, 0 divergências contra o sistema antigo, conferido relendo o ERP e não confiando no retorno. Pra chegar nisso eu deduzi como o importador do ERP valida: ele dá um erro por linha, o primeiro que acha, e as contagens só fecham numa certa ordem. Meses depois troquei todo o comercial pela lista do outro sistema deles via API: 4.523 conferidos, 0 divergências, 2.503 inativados em vez de apagados, porque inativar dá pra desfazer.

## Rede de três farmácias de manipulação

Plano de categorias revisado subido igual nas 3 bases: 62 novas e 9 ajustadas. Conferido relendo a API, 138 linhas e 0 divergências em cada uma. A conferência pegou 10 de 10 bugs plantados.

## Outras

Fichas técnicas de uma agroindústria, onde a regra é que a estrutura do ERP é sempre por 1 kg do produto final, então cada insumo entra como receita dividida pelo rendimento da batelada. Implantação de uma oficina de remap a partir de um sistema que exportava planilha binária antiga, com 350 CPFs de dígito errado na origem que eu separei em vez de subir.

Também homologuei a central de outro time: 29 testes, idempotência sob 12 envios simultâneos, e 4 achados que ainda não estavam corrigidos, entre eles um pedido que travava em silêncio e ficava invisível no painel.

## O que eu levo disso

Você não é o único autor do dado. Uma vez meu script filtrava pela própria chave de idempotência e não via 20 lançamentos feitos à mão na tela. O plano mostrou "0 movimentos" em produtos que tinham saldo, e executar assim teria dobrado 7.280 unidades. Não aconteceu porque todo script meu de escrita tem modo plano, e eu confiro o plano contra a fonte antes de gravar.
