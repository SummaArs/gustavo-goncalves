# Automação de navegador

Quando o sistema não tem API, a tela é a API. Aprendi a regra dos dois cliques: se cliquei duas vezes e nada aconteceu, paro de clicar e vou ler o código que trata aquele clique.

## Casador de anúncios

Num hub de marketplaces, cada anúncio precisa ser associado ao produto do catálogo, um por um. Fiz uma extensão do Chrome que percorre todas as páginas da loja e casa cada anúncio com o produto mais parecido. O casamento usa similaridade de Dice entre palavras com limiar de 0,75 e exige pelo menos uma palavra forte em comum (não genérica tipo cor ou kit). Na versão 3 descobri que o botão de confirmar só clicava num botão escondido que chamava uma rota, então passei a chamar a rota direto, sem abrir janela. E como a tela é um app de página única, a extensão virou um vigia que se injeta em qualquer aba.

Pegadinha boa: se aparecer "0 casados" do nada, é a sessão que expirou. A busca passa a devolver a página de login em vez da lista.

## Corretor de produtos de marketplace

Produto que não sobe no marketplace porque falta campo. A extensão preenche o que falta (informação regulatória, ficha técnica, origem, NCM) e salva. Regra dura: nunca mexer em produto bloqueado, e nunca chutar NCM. Se o NCM já veio válido, fica; se está vazio, usa uma tabela interna de palavra-chave, e se não tiver certeza deixa pra pessoa. O erro genérico "Erro ao processar" era NCM obrigatório faltando.

## Extensão + motor local

Desenhei uma alternativa a construir software separado: uma extensão do Chrome que é só a cara, e um motor que roda no Mac 24 horas (fila SQLite, idempotência, disjuntor, chave no chaveiro do sistema). Fechei o desenho lendo a documentação do Chrome e não supondo, porque várias coisas que eu queria fazer o navegador simplesmente não deixa.

## Engenharia reversa

Uso ferramentas de engenharia reversa pra entender sites e apps, mas aprendi a não confiar no "exato" que elas dizem. Medi uma: acertou 4 de 4 em armazenamento e 0 de 1 em rede, marcando parâmetro de busca como endpoint com confiança máxima. Serve de mapa pra saber onde olhar, e a confirmação é sempre no código.
