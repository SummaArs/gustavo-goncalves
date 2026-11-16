# Copiloto de terminal

Você escreve em português (ou digita um comando torto), aperta **Ctrl+G**, e a
linha vira o comando certo. Roda inteiro no seu Mac: nenhuma requisição sai da
máquina, nenhum token é gasto, funciona sem internet.

```
cd teste_g                      ⌃O →  cd projeto-teste
quantos json tem aqui           ⌃O →  find . -type f -name '*.json' | wc -l
apagar os temporários           ⌃O →  # REVISE ANTES DE RODAR: find . -type f -delete
(linha vazia, após um erro)     ⌃O →  conserta o último comando que falhou
```

> **Por que Ctrl+O e não Ctrl+G:** o app do Gemini (`/Applications/Gemini.app`)
> registra `Ctrl+G` como atalho **global do macOS** — ele intercepta a tecla
> antes de qualquer terminal, então o zsh nunca a recebe. `Ctrl+G` continua
> ligado aqui: volta a funcionar no minuto em que você trocar o atalho no
> Gemini. Para escolher outra tecla: `export COPILOTO_TECLA='^K'` no `.zshrc`,
> antes da linha que carrega o `copiloto.zsh`.

## A tese

**O neural COMPREENDE, o símbolo GARANTE.** A IA só entra onde a entrada é suja
demais para regra — traduzir português. A partir do momento em que vira decisão
("isto pode chegar executável ao prompt?"), quem decide é regra determinística,
auditável e testada. Se o Ollama cair, o copiloto fica **burro, não errado**.

## A cascata

Latência medida do jeito que você sente: do Ctrl+G até a linha trocada,
incluindo subir o processo do Python (~70 ms que nenhuma camada evita).

| # | Camada | Decisão | Da tecla à linha | O que resolve |
|---|---|---|---|---|
| 0 | cache (SQLite) | 1 ms | **80–200 ms** | pedido repetido no mesmo contexto |
| 1 | matemática (pura) | 4–8 ms | **~90 ms** | erro de digitação: distância de edição contra os nomes que existem de fato |
| 2 | neural (Ollama local) | 1–3,5 s | **1–3,5 s** | português livre |
| — | **verificação** | sempre | — | forma + o programa existe? + `zsh -n` + guarda de destrutivo |

A primeira consulta neural do dia custa ~11 s (o Ollama carrega o modelo na
RAM); depois ele fica quente por 30 min. `cop diario` mostra a sua distribuição
real — na minha bateria de aceitação foram 10 respostas de cache a 4 ms contra
10 neurais com média de 5,3 s.

A camada 1 não usa IA nenhuma: normaliza acento, caixa, hífen e sublinhado
(`teste_g` → `testeg`), e aí `testeg` é prefixo de `testegustavosidecarpedidos`.
**Conserta 77,3% dos erros de digitação** (medido em 238 corrupções aleatórias
de 1–2 caracteres). Abaixo do limiar de confiança ela **não chuta**: escala para
a IA. Ferramenta que chuta é pior que ferramenta burra.

## O que nunca pode acontecer

A saída do modelo é tratada como **entrada hostil**. Toda linha passa por uma
porta de saída única (`nucleo/guarda.py`) e sai como: seguro de rodar, ou
comentado com `# REVISE ANTES DE RODAR:` — e o Enter numa linha comentada é um
no-op de verdade (o `copiloto.zsh` liga `INTERACTIVE_COMMENTS`, sem o qual o
zsh tentaria rodar `#` como programa).

16 invariantes, entre elas:

| ID | Invariante |
|---|---|
| I1 | o copiloto **nunca executa** nada (3 sítios de subprocesso, todos auditados: `zsh -n`, `git status`, `ollama serve`) |
| I2 | comando perigoso sempre chega comentado |
| I6 | a camada 1 **nunca inventa** um nome que não está na pasta |
| I9 | o prompt do modelo leva **nomes**, nunca conteúdo de arquivo (`.env` não vaza) |
| I10 | abaixo do limiar de confiança, não sugere (falha fechado) |
| I13 | não aprova comando cujo programa não existe na máquina |

## A prova

```bash
cd ~/Python/copiloto && ./prove.sh
```

Números da última execução:

- **autoteste do arnês**: planto um bug (removo o padrão de `rm` da guarda) e
  exijo que o arnês o encontre. Se ele não encontrar, ele não está testando nada.
- **199 checagens de invariante**, 0 violações.
- **425.000 tentativas adversariais**, 0 violações (semente 1979, reproduzível).
- **ponta a ponta em terminal real** (`testes/prova_widget.exp`, via pty com
  `expect`): 10 verificações — inclusive arquivos-canário que precisam
  sobreviver ao Enter numa sugestão destrutiva, e `pwd` conferido depois do
  comando (fonte da verdade, não o que a tela mostrou).

O arnês achou 6 defeitos reais durante a construção — todos consertados e
virados em teste permanente:

1. `ls relatorio final.pdf` duplicava o arquivo (nome com espaço) → casamento de
   frase, mais longa primeiro.
2. A guarda descrevia a **sintaxe** do perigo, e `git clean -😀fdx`,
   `git reset.--hard`, `rm -ç\x00rf /` e `git push-f` passavam → passou a
   descrever a **presença do token**.
3. `rm -r` (sem `-f`) não era barrado → qualquer `rm` agora vai comentado.
4. A limpeza do texto não era ponto fixo (`` rm -r` `` virava `rm -r` na segunda
   passada) → descasca até parar de mudar.
5. O arnês perguntava ao próprio produto se algo era perigoso — tautologia. Hoje
   existe um **oráculo independente** (`testes/oraculo.py`) escrito sem olhar a
   guarda; ele é a segunda opinião que faz o autoteste ter dentes.
6. `#` não é comentário em zsh interativo: a blindagem funcionava por acidente
   (porque não existe programa chamado `#`) → `setopt INTERACTIVE_COMMENTS`.

## Teclas

| Tecla | O que faz |
|---|---|
| `Ctrl+O` | traduz/conserta a linha |
| `Ctrl+O` de novo | próxima alternativa (sem repetir o que já mostrou) |
| `Ctrl+O` na linha vazia | conserta o último comando que falhou |
| `Ctrl+X G` | mesma coisa (acorde reserva) |
| `Ctrl+X E` | explica em português o comando que está na linha |
| `→` / `Ctrl+Espaço` | aceita a sugestão cinza do histórico |
| `Tab` | seletor difuso (tolera 2 typos, ignora hífen/caixa/acento) |
| `Ctrl+R` | busca difusa no histórico |

Na linha de comando: `cop "pedido"`, `cop diario`, `cop diag`, `cop prova`.

## Ele aprende com você

Quando você executa uma sugestão e ela dá certo, o par (pedido → comando) entra
no corpus e volta como exemplo nas próximas consultas — vizinho mais próximo por
sobreposição de palavras. É assim que ele aprende o jargão da sua casa
(`oon-prove`, `npm run ooncore:docs`) sem nenhum treinamento.

`cop diario` mostra a prova de si mesmo: sugestões por camada, latência média e
pior caso, quantas você aceitou e quantas foram bloqueadas como REVISAR.

## Arquivos

```
copiloto.py            a cascata (decidir) + interface de linha
copiloto.zsh           os widgets do zsh (Ctrl+G, Ctrl+X E, ganchos)
nucleo/contexto.py     o que existe aqui e agora (dado inerte + captura)
nucleo/deterministico.py  camada 1, função pura
nucleo/guarda.py       a porta de saída única — sanitiza e blinda
nucleo/validador.py    forma + programa existe + zsh -n
nucleo/motor.py        Ollama local, com âncoras e exemplos aprendidos
nucleo/memoria.py      cache, corpus e diário (SQLite, ~/.copiloto)
testes/oraculo.py      segunda opinião, escrita fora do produto
testes/teste_nucleo.py invariantes
testes/adversario.py   busca adversarial + autoteste do arnês
testes/prova_widget.exp prova em terminal real (pty)
prove.sh               roda tudo
```

Dependências externas: **nenhuma**. Só `python3`, `zsh` e (para a camada 2)
`ollama` com `llama3.2:3b`. Trocar de modelo é uma variável:
`export COPILOTO_MODELO=qwen2.5-coder:7b`.
