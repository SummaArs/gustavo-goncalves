"""Medidor de vícios de texto de IA no portfólio. Exit 0 = nenhum vício.

Não "engana detector" (detector de IA erra até em texto humano). Mede o que denuncia texto
gerado: travessão, fórmula "não é X, é Y", conectivo de redação, adjetivo de marketing,
negrito/emoji em excesso, frases todas do mesmo tamanho.
Uso: python3 estilo.py <pasta>
"""
import os, re, statistics, sys

VICIOS = [
    ('travessão', r'—|–'),
    ('fórmula "não é X, é Y"', r'\bnão (?:é|era|foi) (?:só |apenas )?[^.\n]{1,40}, (?:é|era|foi|mas)\b'),
    ('conectivo de redação', r'\b(?:além disso|ademais|em suma|em resumo|vale ressaltar|vale destacar|é importante notar|nesse sentido|dessa forma|por fim,|no entanto|todavia|outrossim)\b'),
    ('palavra de marketing', r'\b(?:robust[oa]s?|crucial|fundamental|inovador[a]?|revolucion\w+|alavanc\w+|potencializ\w+|sinergia|jornada|ecossistema|incrível|perfeitamente|sem precedentes|de ponta|transformador[a]?)\b'),
    ('emoji', '[\U0001F300-\U0001FAFF☀-➿]'),
]


def mede(texto):
    v = []
    corpo = re.sub(r'```.*?```', '', texto, flags=re.S)  # código não é prosa
    corpo = re.sub(r'`[^`]*`', '', corpo)
    for nome, p in VICIOS:
        for m in re.finditer(p, corpo, flags=re.I):
            v.append(nome)
    palavras = len(corpo.split())
    if palavras and corpo.count('**') / 2 / palavras > 1 / 120:
        v.append('negrito demais (>1 a cada 120 palavras)')
    frases = [len(f.split()) for f in re.split(r'[.!?]\s', re.sub(r'^[#|>-].*$', '', corpo, flags=re.M)) if len(f.split()) > 3]
    if len(frases) >= 12 and statistics.pstdev(frases) < 4:
        v.append('frases todas do mesmo tamanho (ritmo de máquina)')
    return v


if __name__ == '__main__':
    total = 0
    for d, ds, fs in os.walk(sys.argv[1]):
        ds[:] = [x for x in ds if x not in ('.git', 'codigo')]
        for f in fs:
            if f.endswith('.md'):
                v = mede(open(os.path.join(d, f), encoding='utf-8').read())
                for x in sorted(set(v)):
                    print(f'{os.path.relpath(os.path.join(d, f), sys.argv[1])}: {v.count(x)}x {x}')
                total += len(v)
    print(f'{total} vício(s)' if total else 'estilo: limpo')
    sys.exit(1 if total else 0)
