# Ferramentas pessoais

## Escriba

Transcrição de áudio e vídeo pra texto, 100% no Mac, sem mandar nada pra nuvem. Um arquivo Python só, servidor da biblioteca padrão, motor faster-whisper em int8 e link do YouTube baixando só o áudio. O resultado vai aparecendo na tela enquanto transcreve. Apaga o áudio depois, por privacidade. Uns 1,3 s pra 6 s de áudio no modelo small. [Código](../codigo/escriba/).

## COSMOS, segundo cérebro

App de notas onde a tela é um sistema solar: você é o sol, as notas são planetas e as pastas são portais que você mergulha. Cofre com frase-senha, scrypt e AES-256-GCM, trava sozinho depois de 15 minutos. Escrita atômica com backup diário. Dois bugs que me marcaram: a ponte entre as janelas do app só passava os argumentos declarados e engolia o terceiro sem erro; e uma otimização sem alocação fazia todos os embeddings apontarem pro mesmo buffer, então tudo ficava 100% parecido com tudo. [Uma versão antiga](../codigo/cosmos/).

## Backup e recuperação

Em novembro de 2026 apaguei código antigo pra liberar espaço no disco e perdi coisa. Recuperei o que deu de três lugares: os 27 repositórios do GitHub com histórico inteiro, a lixeira, e o histórico das sessões de programação, de onde reconstruí 68 arquivos reaplicando cada edição em ordem. Antes de confiar no reconstrutor, rodei ele em arquivos que ainda existiam pra ver se batia, e plantei um bug pra ver se a conferência pegava.

Depois fiz o backup automático pra isso não acontecer de novo: copia tudo a cada 6 horas pro meu Dropbox pessoal, nunca apaga lá o que eu apaguei aqui (foi exatamente o meu acidente), cada repositório vira um arquivo único com o histórico, e senha nenhuma sai da máquina. 200 tentativas adversariais, 0 violações, 8 de 8 bugs plantados pegos. [Código](../codigo/backup_dropbox/).

## Kit de prova

O arnês que eu uso em quase tudo: invariante, busca aleatória com semente reproduzível e encolhimento do contraexemplo até o menor caso. Tem versão em Python e em PowerShell. Junto vai um conferidor de `.env` que mostra só o nome da variável e se está preenchida, nunca o valor. [Código](../codigo/kit_prova/).

## Este portfólio

Tem um portão que roda antes de cada envio pro GitHub e bloqueia nome de cliente, nome de pessoa, e-mail, CPF, CNPJ, telefone, IP interno, token e qualquer arquivo de dado. A lista de nomes proibidos fica fora do repositório, porque a lista de clientes já seria vazamento. 400 tentativas plantando dado sujo, 0 passaram, 6 de 6 bugs pegos.
