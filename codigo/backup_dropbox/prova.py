"""Prova adversarial do backup.py. Uso: python3 prova.py [rodadas] [semente]  (--autoteste planta bugs)

Invariantes (o que NUNCA pode acontecer):
  I1 arquivo comum da fonte ausente ou diferente (sha256) no destino
  I2 segredo (.env*, .pem, .pfx, .key, .p12) aparece no destino
  I3 arquivo apagado na fonte some do destino
  I4 rodar de novo sem mudança copia alguma coisa (idempotência)
  I5 nada de node_modules/__pycache__/.git no destino; nada fora do destino
  I6 bundle do repositório não clona ou perde commit
  I7 --conferir não acusa um arquivo corrompido no destino
"""
import hashlib, os, random, shutil, subprocess, sys, tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
# repo real, só leitura, com ramo FORA do HEAD (8 commits no total, 6 no HEAD): pega bundle que só leva o HEAD
REPO = os.path.expanduser('~/Documents/DEV/repo/central/projeto-teste')
NOMES = ['a.py', 'Ação ç.txt', 'com espaço.md', 'x' * 120 + '.js', 'vazio', '.env', '.env.local',
         'chave.pem', 'cert.pfx', 'id.key', 'ok.json', 'NFD_ação.txt', 'dados.db', '.oculto']
DIRS = ['', 'sub', 'sub/deep', 'node_modules/pkg', '__pycache__', 'proj/.venv/lib', 'Pasta Ç']
SEG = lambda n: n.startswith('.env') or n.endswith(('.pem', '.pfx', '.key', '.p12'))


def sha(p): return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def roda(script, *a):
    r = subprocess.run([sys.executable, script, *a], capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def tentativa(rng, script, tmp):
    fonte, dest = os.path.join(tmp, 'fonte'), os.path.join(tmp, 'dest')
    for d in DIRS:
        for _ in range(rng.randint(0, 4)):
            p = os.path.join(fonte, d, rng.choice(NOMES))
            os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, 'wb').write(os.urandom(rng.choice([0, 1, 100, 70000])))
    if rng.random() < .3:
        os.symlink('/etc/hosts', os.path.join(fonte, 'link'))
    roda(script, '--destino', dest, '--fontes', fonte, REPO)
    comuns = []
    for d, ds, fs in os.walk(fonte):
        ds[:] = [x for x in ds if x not in ('node_modules', '__pycache__', '.venv')]
        comuns += [os.path.join(d, f) for f in fs if not SEG(f) and not os.path.islink(os.path.join(d, f))]
    alvo = lambda p: os.path.join(dest, 'fonte', os.path.relpath(p, fonte))
    for p in comuns:
        if not os.path.exists(alvo(p)) or sha(p) != sha(alvo(p)): return f'I1 {p}'
    for d, ds, fs in os.walk(dest):
        for f in fs:
            if SEG(f): return f'I2 {f}'
        for x in ds:
            if x in ('node_modules', '__pycache__', '.git', '.venv'): return f'I5 {x}'
    if os.path.exists(os.path.join(tmp, 'link')) or len(os.listdir(tmp)) != 2: return 'I5 fora do destino'
    # I4
    _, out = roda(script, '--destino', dest, '--fontes', fonte, REPO)
    if ' copiados=0 ' not in out or ' bundles=0 ' not in out: return 'I4 ' + out.splitlines()[0]
    # I3 + atualização: apaga um, altera outro
    if comuns:
        apagado = rng.choice(comuns); os.remove(apagado)
        vivos = [p for p in comuns if p != apagado]
        if vivos:
            mud = rng.choice(vivos); open(mud, 'ab').write(b'mudou')
            os.utime(mud, (1, 1700000000 + rng.randint(1, 10**6)))
        roda(script, '--destino', dest, '--fontes', fonte, REPO)
        if not os.path.exists(alvo(apagado)): return 'I3'
        if vivos and sha(mud) != sha(alvo(mud)): return 'I1 alteração não propagou'
    # I6
    b = os.path.join(dest, '_git', 'Documents-DEV-repo-central-projeto-teste.bundle')
    if not os.path.exists(b): return 'I6 sem bundle'
    clone = os.path.join(tmp, 'clone')
    r = subprocess.run(['git', 'clone', '-q', '--mirror', '--template=', b, clone], capture_output=True)
    n = lambda g: subprocess.run(['git', '-C', g, 'rev-list', '--all', '--count'], capture_output=True, text=True).stdout.strip()
    if r.returncode or n(clone) != n(REPO): return f'I6 commits {n(clone)} != {n(REPO)}'
    shutil.rmtree(clone)
    # I7
    vivos = [p for p in comuns if os.path.exists(p) and os.path.getsize(p) > 0]
    if vivos:
        c, _ = roda(script, '--destino', dest, '--fontes', fonte, REPO, '--conferir')
        if c != 0: return 'I7 conferir acusou sem corrupção'
        v = alvo(rng.choice(vivos))
        with open(v, 'r+b') as f:  # inverte o 1º byte: sempre muda (\x00 por cima de \x00 não mudava)
            b0 = f.read(1); f.seek(0); f.write(bytes([b0[0] ^ 0xFF]))
        c, _ = roda(script, '--destino', dest, '--fontes', fonte, REPO, '--conferir')
        if c == 0: return 'I7 corrupção não acusada'
    return None


def campanha(script, rodadas, semente):
    rng = random.Random(semente)
    for i in range(rodadas):
        tmp = tempfile.mkdtemp()
        try:
            v = tentativa(rng, script, tmp)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        if v: return f'tentativa {i}: {v}'
    return None


MUTANTES = [
    ('não filtra segredo', "    return nome.startswith('.env') or", "    return False and nome.startswith('.env') or"),
    ('apaga no destino o que sumiu', "    sys.exit(1 if n['erros']", "    r = os.path.join(destino, 'fonte'); [os.remove(os.path.join(dp, f)) for dp, _, fs in os.walk(r) for f in fs if not os.path.exists(os.path.join(fontes[0], os.path.relpath(os.path.join(dp, f), r)))]\n    sys.exit(1 if n['erros']"),
    ('nunca atualiza', "if d.st_size == s.st_size and int(d.st_mtime) == int(s.st_mtime):", "if True:"),
    ('recopia sempre', "if d.st_size == s.st_size and int(d.st_mtime) == int(s.st_mtime):", "if False:"),
    ('copia node_modules', "PULA_DIR = {'node_modules', ", "PULA_DIR = {"),
    ('conferir cego', "ok = os.path.exists(dst) and sha(p) == sha(dst)", "ok = os.path.exists(dst)"),
    ('bundle só do HEAD', "'create', tmp, '--all'", "'create', tmp, 'HEAD'"),
    ('escapa do destino', "    nome = base.replace('/', '-').lstrip('.')", "    nome = os.path.relpath(fonte, H)"),
]

if __name__ == '__main__':
    orig = os.path.join(AQUI, 'backup.py')
    if '--autoteste' in sys.argv:
        src = open(orig).read(); pegos = 0
        for nome, de, para in MUTANTES:
            assert de in src, f'mutante desatualizado: {nome}'
            d = tempfile.mkdtemp(); m = os.path.join(d, 'backup.py')
            open(m, 'w').write(src.replace(de, para, 1)); shutil.copy(os.path.join(AQUI, 'LEIA-ME.md'), d)
            v = campanha(m, 15, 7); pegos += bool(v)
            print(('PEGO  ' if v else 'ESCAPOU ') + nome + (f'  -> {v}' if v else ''))
            shutil.rmtree(d)
        print(f'{pegos}/{len(MUTANTES)} mutantes pegos'); sys.exit(pegos != len(MUTANTES))
    rodadas = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    semente = int(sys.argv[2]) if len(sys.argv) > 2 else 2026
    v = campanha(orig, rodadas, semente)
    print(f'{rodadas} tentativas, semente {semente}: ' + (f'VIOLAÇÃO {v}' if v else '0 violações'))
    sys.exit(bool(v))
