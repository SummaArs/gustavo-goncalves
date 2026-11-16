#!/usr/bin/env python3
"""Conciliador — ponto de entrada.

    python3 conciliar.py            abre a interface no navegador
    python3 conciliar.py --prova    roda o arnes adversarial
    python3 conciliar.py extrato.ofx titulos.csv --csv    concilia no terminal
"""
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))


def terminal(caminhos, exportar=False):
    from nucleo.montagem import identificar, montar_lancamentos, montar_titulos
    from nucleo.motor import Config, conciliar as roda
    from nucleo.dinheiro import reais
    lancs, tits = [], []
    for c in caminhos:
        p = Path(c)
        b = p.read_bytes()
        papel = identificar(p.name, b)[0]
        if papel == "extrato":
            itens, meta = montar_lancamentos(p.name, b)
            lancs += itens
        else:
            itens, meta = montar_titulos(p.name, b)
            tits += itens
        print(f"  {p.name}: {papel}, {meta.get('linhas')} linhas")
    r = roda(lancs, tits, Config())
    m = r.metricas
    print(f"\n  {m['vinculos_certos']} vínculos com certeza  ·  {m['sugestoes']} para decidir"
          f"  ·  {m['lanc_sem_par']} sem título  ·  {m['tit_sem_par']} títulos em aberto")
    print(f"  valor conciliado: R$ {reais(m['valor_conciliado_cent'])}"
          f" de R$ {reais(m['valor_total_cent'])} ({m['cobertura']*100:.1f}%)\n")
    for c in r.certos[:20]:
        l = [x for x in lancs if x.iid == c.lanc[0]][0]
        t = [x for x in tits if x.iid == c.tits[0]][0]
        print(f"  {l.data}  {reais(l.cent):>13}  {l.descricao[:34]:34}  ->  "
              f"{t.contraparte[:30]:30}  [{' + '.join(c.motivos)}]")
    if len(r.certos) > 20:
        print(f"  ... e mais {len(r.certos)-20}")


if __name__ == "__main__":
    argv = sys.argv[1:]
    if "--prova" in argv:
        sys.exit(subprocess.call([sys.executable, str(AQUI / "prova.py")] +
                                 [a for a in argv if a != "--prova"]))
    arquivos = [a for a in argv if not a.startswith("-")]
    if arquivos:
        terminal(arquivos)
    else:
        from servidor import servir
        porta = next((int(a.split("=")[1]) for a in argv if a.startswith("--porta=")), 8777)
        servir(porta, abrir="--nao-abrir" not in argv)
