# Centrais e integrações

"Central" é como a gente chama um app de cliente construído em cima de uma plataforma low-code (OonCore). Cada uma liga os sistemas que a empresa já usa e tira a planilha do meio. Faço sozinho, da conversa com o cliente até o app no ar.

## Gateway de pagamento para o ERP

Venda paga no gateway vira título já recebido no ERP, com a taxa separada e o split de cada participante. Migrei pra versão 2 da API deles no meio do projeto. Webhook com assinatura HMAC, limite de 60 chamadas por minuto respeitado, centavos inteiros do começo ao fim. Ponta a ponta provado com o ERP real.

Nessa central eu criei um assistente de chat que virou molde pras outras. A regra dele: a IA só propõe, a ação é sempre um botão que chama a rota que já existe, com permissão e auditoria da plataforma. Se a IA inventar um número, a conferência troca pelo dado cru.

## NFS-e para sellers de uma plataforma global de afiliados

Todo mês chega uma planilha de comissões dos sellers e cada linha tem que virar nota fiscal de serviço no ERP. Validação dura (dígito de CPF e CNPJ, inclusive o CNPJ alfanumérico novo, valor ambíguo recusado), autorização humana, fila durável e emissão.

Dois achados reais. Primeiro, o ERP me castigou: conferir cada ordem a cada 30 segundos conta como "consumo redundante", e isso bloqueou o método por meia hora. Conserto: disjuntor por método, piso de 65 segundos entre repetições e orçamento de 5 erros. Segundo, a primeira planilha do cliente tinha um seller chinês, e descobri que o ERP conta letra fora do Latin-1 em bytes, derruba o pedido com cirílico e apaga em silêncio o que não sabe guardar, respondendo OK. Fiz transliteração pra pinyin e passei a conferir o que ficou gravado.

Provas: 300 planilhas com 125 mil checagens, 150 lotes contra um ERP falso com 243 mil checagens, 25 de 25 mutantes.

## CRM de projetos para o ERP de uma agência

Agência de publicidade e eventos com uns 180 projetos por ano. O CRM é onde a operação vive e o ERP é o financeiro. A central amarra os dois: projeto do CRM vira departamento no ERP (porque o ERP aceita rateio por departamento numa nota de vários projetos, e por projeto não aceita), lançamento sem projeto fica travado, e tem uma tela de custo e margem por projeto que eles não conseguiam medir antes. Fui eu que fiz a demonstração com as chaves reais na reunião.

## Contas a pagar em moeda estrangeira

O ERP só aceita real. A central recebe a conta em dólar ou euro, converte pela PTAX do Banco Central do dia certo e lança. Ensaio real fechou no centavo.

## Torre de SLA e franquia

Interna da AIRBPO. Responde duas perguntas que moravam em planilha: quanto cobrar do cliente no mês (franquia, excedente, honorário) e se o SLA prometido foi cumprido. Tem calendário próprio de dia útil, com Páscoa calculada pelo algoritmo de Meeus pra achar Carnaval, Sexta-feira Santa e Corpus Christi. 34 de 34 na prova.

## Outras centrais

Rateio financeiro de custo e despesa por departamento com regra versionada por competência. Cadastro de cliente e fornecedor sincronizado nos dois sentidos com o ERP, casando pelo documento pra não duplicar. Portal de vendas B2B pra uns 400 compradores de uma indústria, com protótipo aprovado antes de qualquer código.

## Teste de capacidade: 500 mil ordens

Pediram pra medir se o emissor de notas da plataforma e o ERP aguentavam 300 mil ordens de serviço em menos de um mês. Fiz um software à parte que cria cliente, ordem e faturamento a partir de uma lista. Medi tudo: o limite é por método (240 por minuto), o faturamento é assíncrono (uns 85 s), e dá pra conferir várias ordens numa chamada só, o que tirou a conferência do caminho crítico. Resultado: o gargalo era o emissor, uns 1.000 a 1.250 por hora contra 6.700 por hora no ERP direto. Disparei um lote de 500 mil pra ter certeza.

## Ferramentas da frota

Com várias centrais no ar, fiz duas ferramentas pra cuidar delas. Uma compara o contrato da plataforma entre versões e diz o que mudou antes de atualizar, falhando fechado. A lição que ela me deu: alarme só pro que a plataforma realmente lê, porque alarme falso ensina a ignorar o aviso. A outra é um painel local de comando que só lê as rotas públicas de saúde, porque dado de negócio é do cliente. A primeira versão desse painel eu publiquei na nuvem e apaguei no mesmo dia: rota sem `/api` devolvia a página com 200 e não provava nada.

Também escrevi um compilador de intenção: uma especificação de 276 linhas vira 2.456 linhas de manifesto da plataforma.
