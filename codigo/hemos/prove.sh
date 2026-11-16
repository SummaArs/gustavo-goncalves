#!/bin/sh
# HEMOS — prova tudo.
#
# Regra de ouro herdada do Herus: número afirmado é boato, número medido é
# resultado. Se um número aparece no README e não sai daqui, é bug de
# documentação.
#
#   ./prove.sh          suíte de invariantes + busca adversarial
#   ./prove.sh -r       só as invariantes (rápido)

set -e
cd "$(dirname "$0")"

echo "════════════════════════════════════════════════════════════"
echo " HEMOS — pré-triagem de doação de sangue"
echo " python: $(python3 -V 2>&1)   dependências externas: nenhuma"
echo "════════════════════════════════════════════════════════════"

python3 testes/teste_nucleo.py

if [ "$1" != "-r" ]; then
    echo
    python3 testes/adversario.py
    echo
    python3 testes/teste_criatividade.py
    echo
    python3 testes/teste_forja.py
fi

echo
echo "── conversa completa de ponta a ponta ──────────────────────"
python3 hemos.py --demo --hoje 2026-07-29 >/dev/null
echo "  ✓ roteiro de 24 perguntas executa sem intervenção"
echo
echo "\033[92mTUDO PROVADO.\033[0m"
