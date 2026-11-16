# Como eu trabalho

Isso aqui não saiu de livro. Cada regra apareceu depois de um erro que me custou tempo, dinheiro de cliente ou noite de sono.

## Começo pelo que eu não sei

Todo projeto tem uma metade que eu já sei fazer e uma metade que eu não faço ideia. O risco de prazo mora na segunda. Então eu ataco ela primeiro. Se a API do cliente tem um limite escondido, eu quero descobrir no primeiro dia e não na véspera da entrega.

Junto com isso, peço tudo que depende de gente de uma vez só, antes de escrever a primeira linha: chave de acesso, login, planilha, decisão. Pedir aos pouquinhos trava o projeto cinco vezes em vez de uma.

## Pronto é provado, não escrito

Antes de codar eu transformo o pedido em algo que dá pra conferir. Bug vira um teste que fica vermelho, depois o conserto deixa verde. Migração vira "a soma do sistema novo é igual à do antigo, linha por linha".

A prova que eu uso mais é a busca adversarial. Escrevo o que nunca pode acontecer (cobrar duas vezes, sumir um registro, vazar uma senha) e rodo milhares de tentativas aleatórias tentando fazer acontecer. Quando acha, o caso que quebrou é encolhido até o menor exemplo e vira teste fixo.

E aí vem a parte que mais me ensinou: antes de confiar num "0 violações", eu planto um bug de propósito no código e vejo se a prova reclama. Prova que nunca falha não está testando nada. Já tive suíte inteira verde porque a lista que ela conferia estava vazia, e só descobri porque os bugs plantados pararam de ser pegos.

## Confiro na fonte, não no que a ferramenta diz

Ferramenta mente. Já vi ERP responder "OK" e apagar em silêncio o nome de um cliente chinês, porque não guardava aquele tipo de letra. Já vi relatório dizer "falhou" tendo gravado certo. Por isso eu sempre releio no sistema de origem depois de escrever. Se não releu, não está feito.

## Falhar fechado

Quando o sistema não tem certeza, ele para e coloca na fila pra uma pessoa olhar. Nunca chuta. Toda escrita num sistema externo tem chave de idempotência, senão uma tentativa repetida vira a segunda cobrança. E tem disjuntor: se a API começa a dar erro, a automação para antes de tomar bloqueio.

Uma regra que eu uso pra decidir isso: nada que eu construo pode precisar que alguém acorde às 2 da manhã pra arrumar.

## IA compreende, regra decide

Eu uso IA, mas nunca como o último passo de uma decisão. Ela serve pra ler o que é bagunçado (um e-mail, um PDF torto, uma mensagem de WhatsApp) e transformar em dado. A partir daí quem decide é regra escrita, que dá pra testar e auditar. Se a IA cair, o sistema fica mais burro, mas não fica errado.

Dinheiro é sempre em centavos inteiros. Nunca número quebrado.

## Simples primeiro

Biblioteca padrão antes de dependência. O mínimo de código que resolve. Se dá pra fazer em um quarto das linhas, eu reescrevo. Código que não existe não quebra.

## Com quem eu construo

Programo junto com IA (Claude Code) como par. Eu decido qual é o problema, qual regra vale, o que conta como prova e o que entra ou não. Ela escreve muito código rápido, e por isso mesmo eu não confio em nada que ela diz que fez sem conferir. Boa parte do método acima nasceu dessa desconfiança.
