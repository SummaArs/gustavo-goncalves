"""
servidor.py — abre o financeiro em http://127.0.0.1:8790 (só nesta máquina).

    python3 servidor.py            # livro real em dados/livro.jsonl
    python3 servidor.py --demo     # livro de demonstração em dados/demo.jsonl
"""

import json
import os
import sys
import threading
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from nucleo import Livro, Recusa

AQUI = os.path.dirname(os.path.abspath(__file__))
DEMO = "--demo" in sys.argv
os.makedirs(os.path.join(AQUI, "dados"), exist_ok=True)
LIVRO = Livro(os.path.join(AQUI, "dados", "demo.jsonl" if DEMO else "livro.jsonl"))
TRAVA = threading.Lock()


def semear_demo():
    """Um mês plausível de uma empresa de serviços — só no modo --demo."""
    hoje = date.today()
    d = lambda dias: date.fromordinal(hoje.toordinal() + dias).isoformat()
    T = [("receber", "Alfa", "Implantação Omie", "Serviços", 1850000, -50, -20),
         ("receber", "Epsilon Distribuidora", "Mensalidade BPO", "Serviços", 640000, -40, -10),
         ("receber", "Gama", "Central Monday⇄Omie", "Projetos", 2400000, -25, 5),
         ("receber", "Delta", "Mensalidade BPO", "Serviços", 640000, -12, 18),
         ("receber", "Beta", "Migração Legado", "Projetos", 980000, -70, -45),
         ("receber", "Zeta Agro", "Fichas técnicas", "Projetos", 420000, -5, 25),
         ("pagar", "Imcorptec", "Licença OonCore", "Software", 350000, -30, -2),
         ("pagar", "Locadora Centro", "Aluguel do escritório", "Ocupação", 420000, -20, 10),
         ("pagar", "Contabilidade Alfa", "Honorários", "Serviços de terceiros", 180000, -15, 15),
         ("pagar", "Anthropic", "Assinatura Claude", "Software", 110000, -28, -1)]
    for i, (nat, cp, desc, cat, v, emi, ven) in enumerate(T, 1):
        LIVRO.registrar("titulo", {"natureza": nat, "contraparte": cp, "descricao": desc,
                                   "categoria": cat, "valor": v, "emissao": d(emi),
                                   "vencimento": d(ven)}, f"demo-t{i}")
    for i, (t, v, dia) in enumerate([("T-00001", 1850000, -18), ("T-00002", 300000, -8),
                                     ("T-00007", 350000, -2), ("T-00010", 110000, -1),
                                     ("T-00005", 500000, -30)], 1):
        LIVRO.registrar("baixa", {"titulo": t, "valor": v, "data": d(dia)}, f"demo-b{i}")


class App(BaseHTTPRequestHandler):
    def _json(self, codigo, corpo):
        b = json.dumps(corpo, ensure_ascii=False).encode()
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            b = open(os.path.join(AQUI, "app.html"), "rb").read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)
        elif self.path == "/api/estado":
            with TRAVA:
                self._json(200, dict(LIVRO.painel(date.today().isoformat()), demo=DEMO))
        else:
            self._json(404, {"erro": "não encontrado"})

    def do_POST(self):
        if self.path != "/api/evento":
            return self._json(404, {"erro": "não encontrado"})
        try:
            pedido = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            with TRAVA:
                id_ = LIVRO.registrar(pedido.get("tipo"), pedido.get("dados"), pedido.get("chave"))
            self._json(200, {"id": id_})
        except Recusa as e:
            self._json(422, {"erro": str(e)})
        except (ValueError, AttributeError):
            self._json(400, {"erro": "pedido malformado"})

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    if DEMO and not LIVRO.eventos:
        semear_demo()
    porta = int(os.environ.get("PORTA", 8790))
    print(f"Financeiro em http://127.0.0.1:{porta}" + ("  (demonstração)" if DEMO else ""))
    ThreadingHTTPServer(("127.0.0.1", porta), App).serve_forever()
