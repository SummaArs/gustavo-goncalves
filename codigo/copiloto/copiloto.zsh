# ══════════════════════════ COPILOTO DE TERMINAL ══════════════════════════
#   Ctrl+O      escreva em português (ou um comando torto) -> vira comando
#   Ctrl+O 2x   cicla alternativas, sem repetir o que já mostrou
#   Ctrl+O      com a linha vazia: conserta o último comando que falhou
#   Ctrl+X G    mesma coisa (acorde reserva)   ·   Ctrl+G se você liberar no Gemini
#   Ctrl+X E    explica em português o comando que está na linha
#   cop         atalho de linha: cop diario | cop diag | cop "pedido"
#
# Nada é executado pelo copiloto. Ele só escreve na sua linha e para.
# ──────────────────────────────────────────────────────────────────────────

_COPILOTO_DIR="${${(%):-%x}:A:h}"
_COPILOTO_PY="$_COPILOTO_DIR/copiloto.py"
[[ -f "$_COPILOTO_PY" ]] || return 0

autoload -Uz add-zsh-hook

# A tecla principal é Ctrl+O porque o app do Gemini (/Applications/Gemini.app)
# registra Ctrl+G como atalho GLOBAL do macOS: ele intercepta a tecla antes de
# qualquer terminal, então o zsh nunca a recebe. `^O` (accept-line-and-down-
# history) e `^Xg` (list-expand) são defaults que ninguém usa na prática.
# Para trocar:  export COPILOTO_TECLA='^K'  antes de carregar este arquivo.
: ${COPILOTO_TECLA:=^O}
# O nome sai da configuração, então mensagem e tecla nunca se descolam.
typeset -g _COPILOTO_NOME_TECLA="Ctrl+${${COPILOTO_TECLA#^}:u}"

# Isto NÃO é cosmético: em zsh interativo o '#' não é comentário por padrão, e
# sem esta opção apertar Enter numa linha blindada roda `#` como se fosse um
# programa ("command not found: #"). Ou seja: a blindagem funcionava por
# acidente. Com INTERACTIVE_COMMENTS, o Enter é um no-op de verdade.
setopt INTERACTIVE_COMMENTS

typeset -g _COPILOTO_PEDIDO="" _COPILOTO_ULTIMA_SUG="" _COPILOTO_EVITAR=""
typeset -gi _COPILOTO_ALT=0 _COPILOTO_CODIGO=0
typeset -g _COPILOTO_FALHOU="" _COPILOTO_EXECUTADO=""

# Roda o copiloto e devolve (saída, etiqueta) sem deixar o zle travado às cegas.
_copiloto_chamar() {
  local modo="$1" pedido="$2" erro_arq
  erro_arq="${TMPDIR:-/tmp}/copiloto.$$.err"
  _COPILOTO_SAIDA="$(
    COPILOTO_ULTIMO="$_COPILOTO_FALHOU" \
    COPILOTO_CODIGO="$_COPILOTO_CODIGO" \
    COPILOTO_ALIASES="${(k)aliases}" \
    python3 "$_COPILOTO_PY" "$modo" --tag 1 --alt "$_COPILOTO_ALT" \
      --evitar "$_COPILOTO_EVITAR" -- "$pedido" 2>"$erro_arq"
  )"
  _COPILOTO_ETIQUETA="$(<"$erro_arq")"
  rm -f "$erro_arq"
}

copiloto-sugerir() {
  emulate -L zsh
  local pedido="$BUFFER"

  # Mesma tecla de novo, sem ter mexido na linha: quero OUTRA opção.
  if [[ -n "$_COPILOTO_ULTIMA_SUG" && "$BUFFER" == "$_COPILOTO_ULTIMA_SUG" \
        && -n "$_COPILOTO_PEDIDO" ]]; then
    pedido="$_COPILOTO_PEDIDO"
    (( _COPILOTO_ALT++ ))
    _COPILOTO_EVITAR="${_COPILOTO_EVITAR:+${_COPILOTO_EVITAR}$'\x1f'}${BUFFER#\# REVISE ANTES DE RODAR: }"
  else
    _COPILOTO_ALT=0
    _COPILOTO_EVITAR=""
    _COPILOTO_PEDIDO="$pedido"
  fi

  # Linha vazia = conserte o estrago anterior.
  if [[ -z "$pedido" ]]; then
    if [[ -z "$_COPILOTO_FALHOU" ]]; then
      zle -M "copiloto: escreva o que você quer (em português) e aperte $_COPILOTO_NOME_TECLA"
      return 0
    fi
    pedido="conserte este comando que falhou: $_COPILOTO_FALHOU"
    _COPILOTO_PEDIDO="$pedido"
  fi

  zle -M "  … copiloto pensando"
  zle -R
  _copiloto_chamar sugerir "$pedido"

  if [[ -n "$_COPILOTO_SAIDA" ]]; then
    BUFFER="$_COPILOTO_SAIDA"
    CURSOR=${#BUFFER}
    _COPILOTO_ULTIMA_SUG="$BUFFER"
    zle -M "  ${_COPILOTO_ETIQUETA}"
  else
    zle -M "  copiloto: nada confiável a sugerir — ${_COPILOTO_ETIQUETA:-sem motivo}"
  fi
  zle reset-prompt
}

copiloto-explicar() {
  emulate -L zsh
  [[ -z "$BUFFER" ]] && { zle -M "copiloto: nada na linha para explicar"; return 0 }
  local alvo="$BUFFER"
  zle -M "  … lendo o comando"
  zle -R
  local texto
  texto="$(COPILOTO_ALIASES="${(k)aliases}" \
           python3 "$_COPILOTO_PY" explicar -- "$alvo" 2>/dev/null)"
  texto="${texto:-(IA local não respondeu)}"
  # `zle -I` é obrigatório antes de escrever na tela de dentro de um widget.
  # Sem ele o zle e o print disputam o cursor — e o shell morre. Comprovado.
  zle -I
  print -P "%F{6}┌ o que este comando faz%f"
  print -r -- "$texto"
  print -P "%F{6}└%f"
  zle reset-prompt
}

# Guarda o comando que você rodou e o código de saída dele.
_copiloto_preexec() { _COPILOTO_EXECUTADO="$1" }

_copiloto_precmd() {
  local codigo=$?
  if [[ -n "$_COPILOTO_EXECUTADO" ]]; then
    if (( codigo != 0 && codigo != 130 )); then
      _COPILOTO_FALHOU="$_COPILOTO_EXECUTADO"
      _COPILOTO_CODIGO=$codigo
      print -P "%F{8}↑ falhou (código $codigo) — $_COPILOTO_NOME_TECLA com a linha vazia conserta%f"
    else
      _COPILOTO_FALHOU=""
      _COPILOTO_CODIGO=0
      # Deu certo E veio de sugestão aceita: o copiloto aprende com você (Lei 5).
      if [[ -n "$_COPILOTO_ULTIMA_SUG" && "$_COPILOTO_EXECUTADO" == "$_COPILOTO_ULTIMA_SUG" \
            && -n "$_COPILOTO_PEDIDO" ]]; then
        ( python3 "$_COPILOTO_PY" aceito --pedido "$_COPILOTO_PEDIDO" \
            -- "$_COPILOTO_EXECUTADO" >/dev/null 2>&1 & ) 2>/dev/null
      fi
    fi
    _COPILOTO_EXECUTADO=""
    _COPILOTO_ULTIMA_SUG=""
  fi
}

add-zsh-hook preexec _copiloto_preexec
add-zsh-hook precmd _copiloto_precmd

zle -N copiloto-sugerir
zle -N copiloto-explicar

bindkey "$COPILOTO_TECLA" copiloto-sugerir
bindkey '^G'  copiloto-sugerir     # volta a funcionar se você liberar no Gemini
bindkey '^Xg' copiloto-sugerir     # acorde reserva, imune a sequestro de app
bindkey '^Xe' copiloto-explicar
bindkey '^XE' copiloto-explicar

cop() {
  case "$1" in
    diario|diag|aprender) python3 "$_COPILOTO_PY" "$@" ;;
    prova) ( cd "$_COPILOTO_DIR" && ./prove.sh "${@:2}" ) ;;
    "") print "uso: cop \"<pedido>\" | cop diario | cop diag | cop prova" ;;
    *) python3 "$_COPILOTO_PY" sugerir --tag 1 -- "$@" ;;
  esac
}
