"""Portão do portfólio: NADA sobe para o GitHub se houver dado de cliente, pessoa ou segredo.

Falha fechado: na dúvida, bloqueia. Falso positivo revisado à mão vai para permitidos.txt
como "caminho:sha1-da-linha" (se a linha mudar, volta a bloquear).
Uso: python3 portao.py <pasta>   -> exit 0 = limpo; exit 1 = lista do que bloqueou
"""
import hashlib, os, re, sys, unicodedata

AQUI = os.path.dirname(os.path.abspath(__file__))
TEXTO = {'.md', '.py', '.js', '.mjs', '.ts', '.tsx', '.jsx', '.html', '.css', '.json', '.sh', '.zsh',
         '.exp', '.ps1', '.txt', '.svg', '.command', '.plist', '.toml', '.yml', '.yaml', '.gitignore'}
IMAGEM = {'.png', '.ico', '.jpg', '.webp'}  # sem texto para varrer; só entram se pequenas (ícone/print)
PADROES = [
    ('e-mail', r'[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}'),
    ('CNPJ', r'(?<!\d)\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}(?!\d)'),
    ('CPF', r'(?<!\d)\d{3}\.\d{3}\.\d{3}-\d{2}(?!\d)'),
    ('telefone', r'(?<!\d)(?:\+?55\s?)?\(?\d{2}\)?\s?9\d{4}-?\d{4}(?!\d)'),
    ('IP de rede interna', r'(?<!\d)(?:192\.168|10\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}(?!\d)'),
    ('token', r'(?:ghp_|gho_|github_pat_|sk-[a-z0-9]{8}|sk_live|xox[bpa]-|akia[0-9a-z]{12}|whsec_|gsk_|-----begin)'),
    ('chave atribuída', r'(?:app_?key|app_?secret|api_?key|secret|token|senha|password)\s*[:=]\s*["\'][^"\'\s]{12,}["\']'),
    ('UUID', r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'),
    ('segredo longo', r'(?<![a-z0-9])[a-z0-9]{40,}(?![a-z0-9])'),
]


def normaliza(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s.lower()) if unicodedata.category(c) != 'Mn')


def carrega(nome):
    p = os.path.join(AQUI, nome)
    if not os.path.exists(p): return []
    return [normaliza(l.strip()) for l in open(p, encoding='utf-8') if l.strip() and not l.startswith('#')]


def regras():
    termos = carrega('proibidos.txt')
    assert len(termos) > 20, 'lista de proibidos sumiu ou encolheu: portão não pode rodar cego'
    rx = [(f'nome proibido "{t}"', re.compile(r'(?<![a-z0-9])' + re.escape(t) + r'(?![a-z0-9])')) for t in termos]
    return rx + [(n, re.compile(p)) for n, p in PADROES]


def varre(raiz):
    rx, permitidos, achados = regras(), set(carrega('permitidos.txt')), []
    for d, ds, fs in os.walk(raiz):
        ds[:] = [x for x in ds if x != '.git']
        for f in fs:
            p = os.path.join(d, f)
            rel = os.path.relpath(p, raiz)
            ext = os.path.splitext(f)[1].lower() or f.lower()
            if f.startswith('.env') or f == '.git':
                if f != '.git': achados.append((rel, 0, 'arquivo de segredo'))
                continue
            if ext in IMAGEM:
                if os.path.getsize(p) > 300_000: achados.append((rel, 0, 'imagem grande (pode ser print com dado)'))
                continue
            if ext not in TEXTO:
                achados.append((rel, 0, f'tipo não permitido ({ext}): dado/binário não sobe'))
                continue
            try:
                linhas = open(p, encoding='utf-8').read().split('\n')
            except UnicodeDecodeError:
                achados.append((rel, 0, 'não é texto UTF-8')); continue
            for i, linha in enumerate(linhas, 1):
                n = normaliza(linha)
                for nome, r in rx:
                    if r.search(n):
                        chave = normaliza(f'{rel}:{hashlib.sha1(linha.encode()).hexdigest()}')
                        if chave not in permitidos:
                            achados.append((rel, i, nome))
    return achados


if __name__ == '__main__':
    a = varre(sys.argv[1])
    for rel, i, nome in a:
        # mostra onde e o porquê, nunca o conteúdo da linha (pode ser o próprio segredo)
        print(f'BLOQUEADO {rel}:{i}  {nome}')
    print(f'{len(a)} bloqueio(s)' if a else 'portão: limpo')
    sys.exit(1 if a else 0)
