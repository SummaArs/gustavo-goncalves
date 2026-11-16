# AIRBPO-backup — o que é e como restaurar

Cópia automática (a cada 6 h) de tudo que o Gustavo e o Claude produzem neste Mac:

| Pasta aqui            | De onde vem                     |
|-----------------------|---------------------------------|
| `Python/`             | `~/Python` (todos os projetos)  |
| `claude/`             | `~/.claude` (memória, skills, CLAUDE.md, configurações, histórico das conversas) |
| `Documents-DEV/`      | `~/Documents/DEV`               |
| `_git/`               | cada repositório git como **1 arquivo `.bundle`** com o histórico inteiro |

## Regras (e o porquê)
- **Nada é apagado aqui quando some do Mac.** Foi assim que perdemos código em nov/2026:
  apagar para liberar espaço. Backup que espelha exclusão não protege disso.
- **`.git` não vem como pasta**: o Dropbox sincroniza arquivo por arquivo e corrompe
  repositório. O `.bundle` é um arquivo só, à prova disso.
- **Chaves (.env, .pem, .pfx, .key) não vêm.** A lista do que existia está em
  `_SEGREDOS_NAO_COPIADOS.txt` — recriar pelo painel de cada serviço.
- **Fora:** `node_modules`, `venv`, caches — se reinstala com `npm install` / `pip install`.

## Restaurar
- Arquivos: copiar a pasta de volta para `~`.
- Repositório: `git clone _git/Python/centrais/meu-projeto.bundle meu-projeto`
  (o `.origem.txt` ao lado diz o remoto original).
- Conferência completa (sha256 de todos os arquivos):
  `python3 ~/Python/kit_ferramentas/backup_dropbox/backup.py --conferir`

`_ULTIMO_BACKUP.txt` = resumo da última execução (data, quantos copiados, erros).
Código: `~/Python/kit_ferramentas/backup_dropbox/`.
