# Gustavo Gonçalves

Tenho 18 anos e trabalho com automação de processos em empresas, na AIRBPO. Na prática eu pego um processo que hoje roda na mão, em planilha ou no grito, e transformo em sistema. Pode ser financeiro, fiscal, estoque, cadastro, atendimento, o que aparecer.

Minha base é matemática de algoritmos. Não sou dev de servidor de formação, aprendi construindo. Por isso tudo que eu faço tem uma regra que eu não abro mão: só digo que está pronto quando consigo provar em número. Isso quer dizer rodar milhares de tentativas tentando quebrar o sistema e plantar bug de propósito pra ver se a prova pega.

Esse repositório é meu currículo vivo. Cada projeto que eu fizer daqui pra frente entra aqui, com o problema, o caminho que eu fiz (inclusive o que deu errado) e os números. Os nomes dos clientes estão trocados pelo ramo da empresa, porque o dado é deles.

## Alguns números

- Mais de 40 projetos entre junho e novembro de 2026, de integração com ERP até pesquisa de IA.
- Implantação de ERP de uma locadora: 4.484 produtos e 13.089 unidades em estoque, conferidos relendo o sistema, 0 divergências.
- Conciliação bancária com precisão 1,0000 em 2.200 cenários simulados, porque o sistema só decide o que é certeza e manda o resto pra uma pessoa.
- Motor fiscal conferido contra 5.579 notas reais: 14.272 itens com CFOP, CST, base e alíquota batendo em 100%. A conferência ainda achou um erro do emissor do próprio cliente.
- Porta de integração com ERP que, no mesmo lote, fez 6 requisições onde o jeito ingênuo fazia 86 e tomava bloqueio de 30 minutos.
- Teste de capacidade que disparou um lote de 500 mil ordens de serviço contra um ERP real pra medir onde quebra.

## Onde está cada coisa

| Pasta | O que tem |
|---|---|
| [projetos/](projetos/) | estudos de caso, separados por área |
| [METODO.md](METODO.md) | como eu trabalho e por quê |
| [LICOES.md](LICOES.md) | as cicatrizes, cada lição com o erro que ensinou |
| [DIARIO.md](DIARIO.md) | linha do tempo do que fiz |
| [codigo/](codigo/) | código das ferramentas que são minhas e genéricas |

### Projetos por área

1. [Produtos próprios](projetos/01-produtos-proprios.md): porta segura pro ERP, mini ERP de documentos, conciliador, módulo financeiro, motor fiscal, plataforma de notas, diagnóstico de maturidade
2. [Pesquisa em IA neuro-simbólica](projetos/02-ia-neuro-simbolica.md): cascata de custo, camada do significado, atendimento sem LLM, copiloto de terminal
3. [Centrais e integrações](projetos/03-centrais-integracoes.md): apps em cima de uma plataforma low-code ligando gateway, CRM e ERP
4. [Implantações de ERP](projetos/04-implantacoes-erp.md): migração de sistema legado, estoque com lote, ficha de produção
5. [Automação de navegador](projetos/05-automacao-web.md): extensões que trabalham em sistemas que não têm API
6. [Auditoria e BI](projetos/06-auditoria-bi.md): auditoria de importação, contrato contra nota fiscal, portal de RH
7. [Ferramentas pessoais](projetos/07-ferramentas-pessoais.md): transcrição local, segundo cérebro, backup
8. [Comercial](projetos/08-comercial.md): site de funil e formulário de venda

## Stack

Python só com a biblioteca padrão sempre que dá, porque cada dependência é uma coisa a mais pra quebrar de madrugada. JavaScript e Node quando a plataforma pede. SQLite, MongoDB, HTML e CSS na mão, Chrome extensions, Apps Script, Odoo, APIs de ERP (principalmente Omie), Monday, Fly.io, Ollama pra IA local.
