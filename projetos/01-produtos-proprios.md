# Produtos próprios

Coisas que eu desenhei pra resolver um problema de vez, e não pra um cliente só.

## Eclusa, a porta única pro ERP

Problema: O ERP que a gente mais usa bloqueia a chave de acesso por 30 minutos se você erra 10 vezes o mesmo método. E ele responde erro de negócio (tipo "esse cliente já existe") com HTTP 500, que parece falha de rede. Qualquer automação com retry automático fazia o cliente ficar parado meia hora por causa de 4 lançamentos errados.

O que fiz: Um hub em Python puro com SQLite, que virou a única porta entre qualquer automação minha e esse ERP. São cinco decisões: recusa escrita sem código de integração antes de ir pra rede, grava no disco antes de tentar, só repete o que não foi processado ("já cadastrado" conta como confirmação), tem disjuntor que abre em 5 erros por minuto e guarda o orçamento de erro por máquina.

Como cheguei: A primeira versão contava o orçamento de erro por banco de dados. A busca adversarial achou 7 casos que eu nunca teria imaginado: o ERP conta por IP, então duas instâncias rodando juntas somavam 10 erros e tomavam bloqueio. Separei o banco de saúde por máquina e acabou.

Prova: No mesmo lote de 30 lançamentos com metade inválida, o jeito ingênuo fez 86 requisições, gravou 2 e tomou 1 bloqueio. A Eclusa fez 6 requisições, gravou 1 e não tomou bloqueio. 200 rodadas adversariais, 0 violações, incluindo `kill -9` de verdade no meio da gravação.

## Mini ERP de documentos

Problema: Um escritório de BPO com 61 clientes recebia documento de todo lado e alguém tinha que arquivar cada um na pasta certa do Dropbox, com o nome no padrão.

O que fiz: Um app que lê o documento (boleto, guia, nota de serviço, extrato), entende o que é e arquiva sozinho quando tem certeza. Quando não tem, deixa pra pessoa e aprende com a correção.

Como cheguei: Na versão 3 eu achava que estava bom. O usuário disse "não está classificando direito" e estava certo. Montei um teste honesto: os documentos já arquivados viram gabarito, tirando o próprio documento do modelo. Resultado inicial: 0 de 24. Depois de refazer o roteador por vizinhança, chegou em 57,2% de pasta exata e 66,4% dentro de um nível em 3.200 documentos. O mais importante: o que ele arquiva sozinho, ele acerta. 783 de 783.

Esse projeto me ensinou um monte sobre documento brasileiro. Valor de guia de arrecadação não está onde parece na linha digitável, nota de serviço nacional tem que pegar o líquido e não o bruto, e um `-2.381.85` digitado errado lido ao pé da letra vira 100 vezes o valor. Tá tudo em [LICOES.md](../LICOES.md).

Prova: 459 invariantes. O piso de acerto virou invariante também, então se alguma mudança piorar a classificação, a prova fica vermelha.

## Conciliador bancário

Problema: Conciliação de extrato contra contas a pagar e receber feita em planilha, linha por linha.

O que fiz: Lê OFX, CSV ou XLSX, descobre as colunas sozinho e casa cada movimento com o título certo. A ideia central é decidir só o que é certeza, e eu defini certeza em 5 condições: valor exato no centavo, direção do dinheiro, janela de data, identidade pelo documento ou nome, e exclusividade.

Como cheguei: A quinta condição é a que faz a precisão. No começo qualquer rival bloqueava o casamento, e quase nada era decidido. Mudei pra rival relativo: alternativa fraca não atrapalha, mas se tem outra hipótese com força parecida (75% do melhor escore), vai pra fila humana.

Prova: Precisão 1,0000 em 2.200 cenários simulados. [Código](../codigo/conciliador/).

## Módulo financeiro de um ERP próprio

Primeiro pedaço de um ERP meu. Estudei como o Odoo 18 organiza o financeiro por engenharia reversa do código aberto dele e fiz do meu jeito: livro só de acréscimo, em centavos, estorno em vez de apagar, e hash encadeado pra ninguém mexer no passado sem deixar rastro. Tem títulos, baixa parcial, fechamento, razão e balancete, com interface que eu desenhei medindo contraste.

Me pediram antes pra copiar um ERP comercial. Recusei: é software fechado, tem direito autoral, e a regra de verdade mora no servidor deles.

Prova: 3.000 sequências aleatórias de operações, 0 violações, 7 de 7 bugs plantados pegos. [Código](../codigo/financeiro/).

## Motor fiscal brasileiro

Um módulo pro Odoo 18 que calcula imposto de nota de entrada e saída: ICMS, ST com MVA ajustada, DIFAL de base única e dupla, FCP, IPI, PIS e COFINS. O motor é puro (centavos, alíquota em pontos-base, fração exata) e guarda junto de cada valor a fórmula e de onde veio. O Odoo só desenha a tela.

O que mais me ensinou foi conferir contra a vida real. Rodei contra 5.579 notas de venda de uma indústria cliente. A conciliação pegou um erro que o oráculo e o motor cometiam juntos (reais lidos como centavos, 100 vezes a mais). Quando os dois lados usam a mesma convenção errada, a prova fica cega. E pegou um erro do emissor do próprio cliente: em abril, 231 itens com PIS e COFINS 10 vezes menor que o certo.

Prova: 80.001 tentativas, 0 violações, 23 de 23 mutantes, e 14.272 itens reais batendo 100%.

## Plataforma de notas sem toque

Desenhei pra um varejista que vende em 5 marketplaces e fatura uns R$ 5 milhões por mês: pedido pago vira nota fiscal autorizada, etiqueta na impressora térmica e lançamento no ERP, sem ninguém encostar. O núcleo está pronto em Python puro, com fila durável e idempotência pela chave marketplace + pedido, e um catálogo de 14 falhas com o contorno de cada uma (webhook duplicado, SEFAZ fora, certificado vencido, impressora offline, chargeback). A decisão que eu mais gosto: não reinventar a SEFAZ, usar uma API de emissão pronta.

## Diagnóstico de maturidade de gestão

A empresa usava um painel no Looker Studio alimentado por planilha pra dar nota de maturidade de gestão pros clientes. Juntei formulário, cálculo e relatório num site só: 19 setores, 72 blocos, 332 perguntas, admin e cliente com visões diferentes. Está no ar, com login em 2 fatores pro admin e um registro de quem tentou invadir. 92 invariantes provados, e um teste de ataque com 446 tentativas e 0 entradas.
