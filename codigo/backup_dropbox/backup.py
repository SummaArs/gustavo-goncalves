#!/usr/bin/env python3
"""Backup de tudo que fazemos (código + Claude) para o Dropbox PESSOAL do Gustavo.

Regras (o porquê de cada uma está no LEIA-ME.md):
  - só copia o que mudou (tamanho ou data diferentes) e NUNCA apaga no destino:
    apagar aqui não apaga lá — é exatamente o acidente que o backup protege;
  - pasta .git não vai como pasta (Dropbox corrompe repositório): cada repositório
    vira um git bundle = 1 arquivo com o histórico inteiro;
  - segredo (.env, .pem, .pfx, .key, .p12) não sai da máquina; só o NOME vai para a lista;
  - node_modules, venv, caches: não é código nosso, se reinstala.

Uso:  python3 backup.py                 (destino achado sozinho)
      python3 backup.py --conferir      (confere TODOS os arquivos por sha256)
      python3 backup.py --destino X --fontes A B   (usado pela prova)
"""
import argparse, fcntl, hashlib, json, os, shutil, subprocess, sys, time

H = os.path.expanduser('~')
FONTES = [H + '/Python', H + '/.claude', H + '/Documents/DEV']
PASTA_BACKUP = 'AIRBPO-backup'
PULA_DIR = {'node_modules', '.venv', 'venv', '__pycache__', '.git', '.pytest_cache',
            '.mypy_cache', '.next', '.cache', 'site-packages', '.Trash'}
# dentro de ~/.claude: lixo de execução, não memória
PULA_CAMINHO = {H + '/.claude/' + x for x in ('file-history', 'shell-snapshots', 'debug',
                'session-env', 'statsig', 'telemetry', 'ide', 'daemon', 'bridge-spawn')}
SEGREDO_EXT = ('.pem', '.pfx', '.key', '.p12')
PULA_ARQ = {'.DS_Store', '.credentials.json'}


def eh_segredo(nome):
    return nome.startswith('.env') or nome.endswith(SEGREDO_EXT) or nome == '.credentials.json'


def acha_destino():
    """Dropbox pessoal = a única pasta Dropbox em CloudStorage que não é a da AIRBPO.
    Zero ou duas candidatas -> falha fechado (não chuta)."""
    base = H + '/Library/CloudStorage'
    cand = [os.path.join(base, d) for d in os.listdir(base)
            if d.startswith('Dropbox') and 'AIRBPO' not in d.upper()]
    if len(cand) != 1:
        sys.exit(f'ERRO: esperava 1 Dropbox pessoal em {base}, achei {cand}. Vincule a conta pessoal no app Dropbox.')
    return os.path.join(cand[0], PASTA_BACKUP)


def rel_destino(fonte, p):
    # ~/Python/x -> Python/x ; ~/.claude/x -> claude/x ; ~/Documents/DEV/x -> Documents-DEV/x
    fonte = os.path.abspath(fonte)
    base = os.path.relpath(fonte, H) if fonte.startswith(H + '/') else os.path.basename(fonte)
    nome = base.replace('/', '-').lstrip('.')  # nunca "../": não escapa do destino
    return os.path.normpath(os.path.join(nome, os.path.relpath(p, fonte)))  # raiz: "X/." -> "X"


def varre(fonte):
    """Gera (arquivo, repo_git) e devolve via listas; não segue link simbólico."""
    arqs, repos, segredos = [], [], []
    for d, ds, fs in os.walk(fonte):
        if os.path.isdir(os.path.join(d, '.git')):
            repos.append(d)
        ds[:] = sorted(x for x in ds if x not in PULA_DIR and os.path.join(d, x) not in PULA_CAMINHO
                       and not os.path.islink(os.path.join(d, x)))
        for f in sorted(fs):
            p = os.path.join(d, f)
            if f in PULA_ARQ or os.path.islink(p):
                if eh_segredo(f): segredos.append(p)
                continue
            if eh_segredo(f):
                segredos.append(p)
                continue
            arqs.append(p)
    return arqs, repos, segredos


def copia(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    tmp = dst + '.copiando'
    shutil.copy2(src, tmp)
    os.replace(tmp, dst)  # quem olha o destino nunca vê arquivo pela metade


def impressao_git(repo):
    r = subprocess.run(['git', '-C', repo, 'for-each-ref', '--format=%(objectname) %(refname)'],
                       capture_output=True, text=True)
    return hashlib.sha256(r.stdout.encode()).hexdigest() if r.returncode == 0 else None


def faz_bundle(repo, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    tmp = dst + '.copiando'
    r = subprocess.run(['git', '-C', repo, 'bundle', 'create', tmp, '--all'], capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(tmp):
        return r.stderr.strip()[-200:] or 'falhou'
    os.replace(tmp, dst)
    url = subprocess.run(['git', '-C', repo, 'remote', 'get-url', 'origin'], capture_output=True, text=True).stdout.strip()
    with open(dst[:-len('.bundle')] + '.origem.txt', 'w') as f:
        f.write(f'pasta original: {repo}\nremoto: {url or "(sem remoto)"}\n'
                f'restaurar: git clone "{os.path.basename(dst)}" nome-da-pasta\n')
    return None


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--destino')
    ap.add_argument('--fontes', nargs='+')
    ap.add_argument('--conferir', action='store_true')
    a = ap.parse_args()
    destino = a.destino or acha_destino()
    fontes = a.fontes or FONTES
    os.makedirs(destino, exist_ok=True)

    trava = open(os.path.join(destino, '.trava'), 'w')
    try:
        fcntl.flock(trava, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        sys.exit('outro backup já está rodando')

    est_p = os.path.join(destino, '_estado.json')
    estado = json.load(open(est_p)) if os.path.exists(est_p) else {}
    t0 = time.time()
    n = {'copiados': 0, 'iguais': 0, 'erros': 0, 'bundles': 0, 'bundles_iguais': 0, 'conferidos': 0, 'divergentes': 0}
    erros, todos_segredos = [], []

    for fonte in fontes:
        if not os.path.isdir(fonte):
            erros.append(f'fonte não existe: {fonte}'); n['erros'] += 1
            continue
        try:
            arqs, repos, segredos = varre(fonte)
        except PermissionError as e:
            erros.append(f'sem permissão de ler {fonte}: {e}'); n['erros'] += 1
            continue
        todos_segredos += segredos
        for p in arqs:
            dst = os.path.join(destino, rel_destino(fonte, p))
            try:
                s = os.stat(p)
                if a.conferir:
                    ok = os.path.exists(dst) and sha(p) == sha(dst)
                    n['conferidos' if ok else 'divergentes'] += 1
                    if not ok: erros.append(f'DIVERGE: {p}')
                    continue
                if os.path.exists(dst):
                    d = os.stat(dst)
                    if d.st_size == s.st_size and int(d.st_mtime) == int(s.st_mtime):
                        n['iguais'] += 1
                        continue
                copia(p, dst)
                n['copiados'] += 1
            except OSError as e:
                n['erros'] += 1; erros.append(f'{p}: {e}')
        if a.conferir:
            continue
        for repo in repos:
            imp = impressao_git(repo)
            dst = os.path.join(destino, '_git', rel_destino(fonte, repo) + '.bundle')
            if imp and estado.get(repo) == imp and os.path.exists(dst):
                n['bundles_iguais'] += 1
                continue
            err = faz_bundle(repo, dst) if imp else 'não é repositório válido'
            if err:
                n['erros'] += 1; erros.append(f'bundle {repo}: {err}')
            else:
                n['bundles'] += 1; estado[repo] = imp

    if not a.conferir:
        json.dump(estado, open(est_p + '.tmp', 'w'), indent=1); os.replace(est_p + '.tmp', est_p)
        with open(os.path.join(destino, '_SEGREDOS_NAO_COPIADOS.txt'), 'w') as f:
            f.write('Estes arquivos têm chaves/senhas e NÃO foram copiados (de propósito).\n'
                    'Se perder o Mac, recrie cada um a partir do painel do serviço.\n\n'
                    + '\n'.join(sorted(todos_segredos)) + '\n')
        shutil.copy2(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'LEIA-ME.md'),
                     os.path.join(destino, 'LEIA-ME.md'))
    resumo = (time.strftime('%Y-%m-%d %H:%M:%S') + f' destino={destino} ' +
              ' '.join(f'{k}={v}' for k, v in n.items()) + f' segredos_pulados={len(todos_segredos)} {time.time()-t0:.0f}s')
    print(resumo)
    for e in erros[:50]: print('  ', e)
    if not a.conferir:
        with open(os.path.join(destino, '_ULTIMO_BACKUP.txt'), 'w') as f:
            f.write(resumo + '\n' + '\n'.join(erros) + '\n')
    sys.exit(1 if n['erros'] or n['divergentes'] else 0)


if __name__ == '__main__':
    main()
