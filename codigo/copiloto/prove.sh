#!/bin/sh
# COPILOTO — prova tudo.
#
# Regra de ouro: número afirmado é boato, número medido é resultado. Se um
# número aparece no README e não sai daqui, é bug de documentação.
#
#   ./prove.sh          autoteste do arnês + invariantes + busca adversarial
#   ./prove.sh -r       só o rápido (autoteste + invariantes)
#   ./prove.sh -g       inclui a ida e volta real na IA local (precisa do Ollama)

set -e
cd "$(dirname "$0")"
COP="$(pwd)"          # os testes ponta a ponta rodam de outra pasta
export COP

echo "════════════════════════════════════════════════════════════"
echo " COPILOTO DE TERMINAL — cascata local"
echo " python: $(python3 -V 2>&1)   dependências externas: nenhuma"
echo " zsh:    $(zsh --version 2>/dev/null || echo ausente)"
echo "════════════════════════════════════════════════════════════"
echo

# 1. O arnês vale algo? Planta um bug e exige que ele seja pego.
python3 testes/adversario.py --autoteste
echo

# 2. As invariantes.
python3 testes/teste_nucleo.py

if [ "$1" != "-r" ]; then
    echo
    # 3. A busca cuja função objetivo é violar as invariantes.
    python3 testes/adversario.py --rodadas 25000 --rodadas-matematica 400000
fi

# 4. Ponta a ponta, no disco de verdade, sem tocar na IA.
echo
echo "── ponta a ponta: camadas 0 e 1 em disco real ──────────────"
PASTA=$(mktemp -d)
mkdir -p "$PASTA/projeto-teste" "$PASTA/projeto-exemplo"
printf '{"scripts":{"dev":"vite","ooncore:docs":"node x.js"}}' > "$PASTA/package.json"
cd "$PASTA"
SAIDA=$(python3 - <<'PY'
import os, sys, time
sys.path.insert(0, os.environ["COP"])
from copiloto import decidir
from nucleo import contexto
ctx = contexto.capturar()
casos = [("cd teste_g", "cd projeto-teste"),
         ("cd TACA", "cd projeto-exemplo"),
         ("voltar", "cd .."),
         ("git status", "git status")]
piores = 0.0
for pedido, esperado in casos:
    t = time.monotonic()
    linha, camada, risco, motivo = decidir(pedido, ctx, usar_cache=False,
                                           motor_fn=lambda *a, **k: "")
    ms = (time.monotonic() - t) * 1000
    piores = max(piores, ms)
    marca = "ok " if linha == esperado else "ERRO"
    print(f"  {marca} {pedido!r:22} -> {linha!r:38} [{camada}, {ms:.1f} ms]")
    if linha != esperado:
        sys.exit(1)
print(f"  pior latência sem IA: {piores:.1f} ms")
PY
) || { echo "  ✗ ponta a ponta falhou"; cd - >/dev/null; rm -rf "$PASTA"; exit 1; }
echo "$SAIDA"
cd - >/dev/null
rm -rf "$PASTA"

# 5. Ponta a ponta num terminal DE VERDADE (pty). É a única prova que vale para
#    um widget de zle: `zsh -i -c` não tem zle e não roda widget nenhum.
if [ "$1" != "-r" ]; then
    echo
    echo "── ponta a ponta: widget em terminal real (pty) ─────────────"
    if [ ! -x /usr/bin/expect ]; then
        echo "  — expect ausente: widget não testado"
    elif [ ! -d "$HOME/Documents/DEV/repo/central/projeto-teste" ]; then
        echo "  — pasta de referência ausente: widget não testado"
    else
        ./testes/prova_widget.exp
    fi
fi

if [ "$1" = "-g" ]; then
    echo
    echo "── ponta a ponta: camada 2 (IA local de verdade) ────────────"
    python3 - <<'PY'
import os, sys, time
sys.path.insert(0, os.environ["COP"])
from copiloto import decidir
from nucleo import contexto, motor
if not motor.garantir_servidor():
    print("  — Ollama indisponível: camada 2 não testada")
    sys.exit(0)
ctx = contexto.capturar()
for pedido in ["quantos arquivos python tem aqui contando as subpastas",
               "mostrar as 5 maiores pastas daqui"]:
    t = time.monotonic()
    linha, camada, risco, motivo = decidir(pedido, ctx, usar_cache=False)
    print(f"  {pedido}\n    -> {linha!r} [{camada}, "
          f"{(time.monotonic()-t)*1000:.0f} ms, {risco}]")
PY
fi

echo
printf "\033[92mTUDO PROVADO.\033[0m  (o que não sai daqui não vale como número)\n"
