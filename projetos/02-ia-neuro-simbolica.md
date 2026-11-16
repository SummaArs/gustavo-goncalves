# Pesquisa em IA neuro-simbólica

A ideia que amarra tudo aqui: a rede neural serve pra compreender, o símbolo serve pra garantir. Modelo de linguagem é bom pra entender texto bagunçado e ruim pra ser o último elo de uma decisão. Então eu monto sistemas onde a IA traduz e a regra decide.

## Cascata por custo

Montei uma cascata de inferência em quatro degraus: matemática pura, aprendizado de máquina leve (um Naive Bayes que eu escrevi do zero), IA local rodando no Mac pelo Ollama e, só em último caso, IA na nuvem. Cada pedido sobe um degrau só quando o de baixo não tem confiança. Tudo em biblioteca padrão, sem numpy, de propósito: queria mostrar que IA é função com otimização e não mistério.

Escrevi uma proposta comercial disso e depois revisei com olho de CTO cético. Troquei "risco zero de alucinação" por "alucinação contida e que não decide", porque a tradução neural pode errar, mas a regra tipada rejeita o fato inconsistente antes dele virar decisão. Troquei "custo zero" por "custo que sai de variável pra fixo", que é o que realmente acontece. E os números bonitos viraram meta a calibrar no piloto, não resultado medido.

## Herus, a camada do significado

Começou como um relógio que transmitia significado em vez de texto e virou uma coisa maior: uma camada onde o significado existe, acima do transporte e abaixo do idioma. 24 bytes de significado atravessam 8 idiomas e passam pelo ar como som. O que destravou foi perceber que nos três limites que eu tinha (léxico escrito à mão em C, nenhum canal medido, nada extensível) o problema era o mesmo: o dado estava dentro do código. 97 suítes de prova. O código é público em [github.com/SummaArs/herus](https://github.com/SummaArs/herus).

## Atendimento de banco de sangue sem LLM

Me pediram atendimento de WhatsApp pra triagem de doador de sangue, com lógica e sem IA generativa. A sacada veio do Herus: o espaço de significados de uma triagem é finito, uns 50 símbolos. Então o texto do doador vira o id de um léxico fechado logo na entrada, e daí pra frente a máquina de estados, as regras e o log só trabalham com ids. Não tem como o sistema inventar uma resposta médica, porque ele não gera texto livre. 102.000 tentativas adversariais, 0 violações. [Código](../codigo/hemos/).

## Copiloto de terminal

Autocomplete que conserta o que eu digito errado no terminal. Mais uma cascata: cache em SQLite (3 ms), depois matemática pura com distância de edição normalizada (4 a 6 ms), e só então IA local (cerca de 1 s). A camada matemática resolve 77,3% dos erros sem acordar a IA, e quando está abaixo do limiar ela não chuta.

O que eu aprendi aqui vale pra qualquer coisa que recebe saída de IA: tratar como entrada hostil. Casar a sintaxe de um comando perigoso perde pra variações bobas, tipo um emoji no meio do `rm`. Tem que descrever o perigo pelo token, não pela forma. E o teste que pergunta ao próprio produto se a saída é perigosa fica cego junto quando o produto quebra, então escrevi um oráculo separado que nunca olha a implementação. [Código](../codigo/copiloto/).

## Revisão honesta de um sistema de detecção

Revisei um projeto de P&D de detecção de ataque por "queda de coerência" entre especialistas, com 7 versões e uns 6.800 linhas. Provei três coisas. Ele nunca rodou (um erro de formato no treino aparece nas 7 versões). A tal coerência media a geometria da máscara e não a rede: numa dimensão coberta por 1 de 4 especialistas a razão dá raiz de 3, constante, então uma versão alertava sempre e a outra nunca. E o benchmark gerava a métrica a partir do gabarito. Deixei escrito o caminho pra consertar na ordem certa, com baseline obrigatório antes de qualquer coisa sofisticada. Mostrar aqueles números pra cliente seria desonesto, e eu prefiro saber disso cedo.

## Agente de segurança local

Um agente de segurança defensiva que conversa em português no terminal e roda até em PC fraco: detecta o hardware e, se não couber IA, funciona só com regra. A parte que eu mais gosto é a caixa-preta forense, um log que só cresce, encadeado por hash e selado com assinatura pós-quântica, que aponta a entrada exata que foi adulterada. Fui honesto na pesquisa: a primitiva já existe, o novo é a combinação offline.
