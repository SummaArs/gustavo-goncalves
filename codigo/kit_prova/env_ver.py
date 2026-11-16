"""Mostra as chaves de um .env e se estão preenchidas — nunca o valor.
Uso: python3 env_ver.py caminho/.env"""
import sys

for linha in open(sys.argv[1], encoding="utf-8"):
    linha = linha.strip()
    if not linha or linha.startswith("#") or "=" not in linha:
        continue
    chave, valor = linha.split("=", 1)
    valor = valor.strip().strip("'\"")
    print(f"{chave.strip()}: {'preenchida (' + str(len(valor)) + ' car.)' if valor else 'VAZIA'}")
