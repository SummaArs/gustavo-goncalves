# Lições

Cada uma custou um erro de verdade. Deixo aqui pra não pagar duas vezes.

## A prova que mente

- Prova sobre lista vazia é decoração. Quando o trabalho acabou, o plano ficou vazio e toda conferência do tipo "todos os itens estão certos" passou sem testar nada. Os bugs plantados caíram de 8 pegos pra 1 sem eu mudar uma linha. Testo sempre com carga.
- Conferência nunca se compara com a constante que ela devia guardar. Eu checava `data == DATA_MOVIMENTO` e o bug que trocava `DATA_MOVIMENTO` passava ileso. Conferência de configuração usa o valor escrito por extenso.
- Total certo não prova composição certa. O ERP gravou 1 lote com o total de 6, e o saldo bateu.
- Quando os dois lados usam a mesma convenção errada, a prova fica cega. Motor e oráculo liam real como centavo, juntos. Só a conferência contra nota real pegou.
- Falha do medidor não é falha do produto. Uma vez minha prova "corrompia" um arquivo escrevendo zero no primeiro byte, e em 1 a cada 256 vezes o byte já era zero. Antes de mexer no produto, pergunto se o erro é da régua.

## APIs e ERPs

- Erro de negócio às vezes chega como HTTP 500. Repetir automaticamente só o que é transitório, senão você toma bloqueio por "consumo redundante".
- O limite do ERP era por IP, não por instância. Duas cópias da automação somavam erro.
- Sistema pode responder OK e apagar o dado em silêncio. Sempre reler depois de gravar.
- Script de "excluir e refazer" precisa de trava de reentrância. Rodado duas vezes, ele apaga o certo e a idempotência recusa recriar.
- Retry de leitura não é luxo. Uma queda de rede entre excluir e recriar deixa tudo pela metade.
- Prefira o marcador estrutural à comparação de valores. O tipo do movimento dizia direto se tinha lote, comparar quantidade era frágil.

## Documento brasileiro

- Boleto: valor nas posições 37 a 47 da linha digitável, em centavos, e o fator de vencimento tem teto 9999. Validar os dígitos verificadores.
- Guia de arrecadação (começa com 8): o valor não está na linha digitável direto. Tem que remontar o código de barras de 44 dígitos e ler de lá, senão sai um valor deslocado que parece plausível.
- Nota de serviço nacional: o que se paga é o líquido. Pegar o bruto erra pelo valor da retenção.
- Valor em nome de arquivo: `-2.381.85` lido ao pé da letra vira 100 vezes o valor. Sem vírgula e com 2 dígitos no último grupo, o ponto é decimal e o valor entra marcado como ambíguo.
- Em regex, `\b` não funciona com `_`, porque `_` conta como letra.
- Data no começo do nome: exigir ano, mês e dia válidos, senão os 8 primeiros dígitos de um CNPJ viram data.

## Tela e design

- Em sistema web, conferir persistência recarregando a página. Nunca pelo que a tela mostra.
- Diferença de luminosidade menor que uns 15 pontos a pessoa simplesmente não vê. Miro em 22 ou mais e meço, não confio no olho.
- Gráfico conhecido ganha do gráfico tecnicamente melhor. Quem lê não quer aprender um gráfico novo.
- Elemento flutuante pousa dentro da moldura. Quem recua é o conteúdo, nunca a moldura.

## Trabalho

- Medir premissa antes de construir em cima dela.
- Ferramenta tem um propósito só. Quando o pedido muda o público, é outra ferramenta.
- Conceito financeiro de cliente passa por revisão de quem entende antes de subir no ERP.
- Real antes de dublê. O ERP de verdade me ensinou um castigo de 30 minutos que o falso não sabia.
