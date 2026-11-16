#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Escriba — transcrição de áudio → texto, 100% local no seu Mac.
Motor: faster-whisper (int8, VAD). Interface: web local via stdlib.
Nada sai do seu computador. Não precisa de internet depois de baixar o modelo.

Uso:  python3 escriba.py
"""

import http.server
import socketserver
import json
import os
import sys
import tempfile
import threading
import time
import webbrowser
from urllib.parse import urlparse, parse_qs, unquote

PORTA = 8756
HOST = "127.0.0.1"

# ---------------------------------------------------------------------------
# Motor de transcrição (carregado sob demanda e mantido em cache por modelo)
# ---------------------------------------------------------------------------
_modelos = {}
_lock = threading.Lock()


def carregar_modelo(nome: str):
    """Carrega (uma vez) o modelo faster-whisper otimizado para CPU arm64."""
    with _lock:
        if nome not in _modelos:
            from faster_whisper import WhisperModel
            # int8 = rápido e leve em RAM; cpu_threads=0 => usa todos os núcleos.
            _modelos[nome] = WhisperModel(
                nome, device="cpu", compute_type="int8", cpu_threads=0
            )
        return _modelos[nome]


# Pasta temporária para os uploads (limpa ao fechar).
TMP = tempfile.mkdtemp(prefix="escriba_")


# ---------------------------------------------------------------------------
# Servidor HTTP
# ---------------------------------------------------------------------------
class Handler(http.server.BaseHTTPRequestHandler):

    # silencia o log padrão barulhento
    def log_message(self, *a):
        pass

    # -------------------------- GET --------------------------
    def do_GET(self):
        rota = urlparse(self.path)
        if rota.path == "/":
            self._enviar_html()
        elif rota.path == "/stream":
            self._stream(parse_qs(rota.query))
        else:
            self.send_error(404)

    # -------------------------- POST -------------------------
    def do_POST(self):
        rota = urlparse(self.path)
        if rota.path == "/upload":
            self._upload()
        else:
            self.send_error(404)

    # ---------------------- implementações -------------------
    def _enviar_html(self):
        corpo = HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def _upload(self):
        """Recebe o arquivo como corpo bruto (header X-Filename)."""
        try:
            tamanho = int(self.headers.get("Content-Length", 0))
            nome = unquote(self.headers.get("X-Filename", "audio"))
            nome = os.path.basename(nome) or "audio"
            destino = os.path.join(TMP, f"{int(time.time()*1000)}_{nome}")
            restante = tamanho
            with open(destino, "wb") as f:
                while restante > 0:
                    bloco = self.rfile.read(min(1 << 20, restante))
                    if not bloco:
                        break
                    f.write(bloco)
                    restante -= len(bloco)
            resp = json.dumps({"id": os.path.basename(destino)}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp)))
            self.end_headers()
            self.wfile.write(resp)
        except Exception as e:
            self.send_error(500, str(e))

    def _sse(self, evento: str, dado: dict):
        """Envia um evento Server-Sent Events."""
        msg = f"event: {evento}\ndata: {json.dumps(dado, ensure_ascii=False)}\n\n"
        self.wfile.write(msg.encode("utf-8"))
        self.wfile.flush()

    def _baixar_youtube(self, url: str) -> str:
        """Baixa apenas a faixa de áudio de um link (YouTube etc.) via yt-dlp."""
        import yt_dlp

        ultimo = [0]

        def hook(d):
            if d.get("status") == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                baixado = d.get("downloaded_bytes", 0)
                pct = int(baixado / total * 100) if total else 0
                if pct != ultimo[0]:
                    ultimo[0] = pct
                    self._sse("progress", {"pct": pct})
                    self._sse("status", {"msg": f"Baixando do YouTube… {pct}%"})

        modelo = os.path.join(TMP, f"yt_{int(time.time()*1000)}.%(ext)s")
        opts = {
            "format": "bestaudio/best",
            "outtmpl": modelo,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "progress_hooks": [hook],
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info)

    def _stream(self, q):
        """Transcreve em streaming: cada segmento é enviado assim que sai."""
        modelo_nome = q.get("model", ["small"])[0]
        idioma = q.get("lang", ["auto"])[0]
        url = (q.get("url", [""])[0] or "").strip()

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        try:
            if url:
                self._sse("status", {"msg": "Conectando ao YouTube…"})
                try:
                    caminho = self._baixar_youtube(url)
                except Exception as e:
                    self._sse("error", {"msg": f"Não consegui baixar o vídeo: {e}"})
                    return
                self._sse("progress", {"pct": 0})
            else:
                caminho = os.path.join(TMP, os.path.basename(q.get("id", [""])[0]))

            if not os.path.exists(caminho):
                self._sse("error", {"msg": "Arquivo não encontrado."})
                return

            self._sse("status", {"msg": f"Carregando modelo “{modelo_nome}”…"})
            modelo = carregar_modelo(modelo_nome)

            self._sse("status", {"msg": "Analisando o áudio…"})
            t0 = time.time()
            segmentos, info = modelo.transcribe(
                caminho,
                language=None if idioma == "auto" else idioma,
                beam_size=1,                 # greedy = mais rápido
                vad_filter=True,             # pula silêncios
                vad_parameters={"min_silence_duration_ms": 500},
            )
            duracao = float(getattr(info, "duration", 0) or 0)
            self._sse("info", {
                "language": getattr(info, "language", "?"),
                "duration": duracao,
            })

            for seg in segmentos:
                self._sse("seg", {
                    "start": round(seg.start, 2),
                    "end": round(seg.end, 2),
                    "text": seg.text.strip(),
                })
                if duracao:
                    pct = min(99, int(seg.end / duracao * 100))
                    self._sse("progress", {"pct": pct})

            self._sse("done", {
                "elapsed": round(time.time() - t0, 1),
                "duration": duracao,
            })
        except BrokenPipeError:
            pass  # usuário fechou a aba
        except Exception as e:
            try:
                self._sse("error", {"msg": str(e)})
            except Exception:
                pass
        finally:
            try:
                if os.path.exists(caminho):
                    os.remove(caminho)  # apaga o áudio após transcrever (privacidade)
            except Exception:
                pass


class Servidor(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


# ---------------------------------------------------------------------------
# Interface (HTML + CSS + JS, tudo embutido)
# ---------------------------------------------------------------------------
HTML = r"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Escriba — áudio para texto, local</title>
<style>
  :root{
    --tx:#eaf0fb; --mut:#a9b4cc;
    --ac:#5b8cff; --ac2:#8b5cff; --ok:#2ee6a6;
    --glass:rgba(255,255,255,.06); --brd:rgba(255,255,255,.14);
    --field:rgba(255,255,255,.05); --shadow:0 24px 70px rgba(6,10,25,.55);
    --blur:24px;
  }
  @media (prefers-color-scheme:light){
    :root{
      --tx:#0e1424; --mut:#5a6a86;
      --ac:#3b6dff; --ac2:#7c4dff; --ok:#12b886;
      --glass:rgba(255,255,255,.55); --brd:rgba(255,255,255,.75);
      --field:rgba(255,255,255,.6); --shadow:0 24px 60px rgba(40,60,120,.16);
    }
  }
  *{box-sizing:border-box;margin:0;padding:0}
  html,body{height:100%}
  body{font:15px/1.55 -apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI",Inter,sans-serif;
       color:var(--tx);min-height:100vh;padding:40px 20px;position:relative;overflow-x:hidden;
       background:
         radial-gradient(1000px 700px at 15% -5%, #6d4bff33, transparent 55%),
         radial-gradient(900px 650px at 90% 5%, #3b82ff38, transparent 55%),
         radial-gradient(800px 600px at 60% 110%, #ff5cc733, transparent 55%),
         #070b16;
       background-attachment:fixed}
  @media (prefers-color-scheme:light){
    body{background:
         radial-gradient(1000px 700px at 15% -5%, #b9a3ff66, transparent 55%),
         radial-gradient(900px 650px at 90% 5%, #a9c6ff77, transparent 55%),
         radial-gradient(800px 600px at 60% 110%, #ffc0e588, transparent 55%),
         #eef1fb; background-attachment:fixed}
  }
  /* blobs de cor desfocados flutuando ao fundo */
  body::before, body::after{content:"";position:fixed;z-index:-1;border-radius:50%;
       filter:blur(70px);opacity:.55;pointer-events:none}
  body::before{width:420px;height:420px;left:-80px;top:8%;
       background:radial-gradient(circle at 30% 30%,#7c5cff,#3b82ff);animation:flo 18s ease-in-out infinite}
  body::after{width:380px;height:380px;right:-60px;bottom:4%;
       background:radial-gradient(circle at 60% 40%,#ff5cc7,#7c5cff);animation:flo 22s ease-in-out infinite reverse}
  @keyframes flo{0%,100%{transform:translate(0,0)}50%{transform:translate(40px,-30px)}}

  .wrap{max-width:820px;margin:0 auto;position:relative;z-index:1}
  header{text-align:center;margin-bottom:30px}
  .logo{display:inline-flex;align-items:center;gap:14px;font-size:34px;font-weight:800;letter-spacing:-.03em}
  .logo .mark{width:56px;height:56px;border-radius:18px;display:grid;place-items:center;font-size:28px;
       background:linear-gradient(135deg,var(--ac),var(--ac2));
       box-shadow:0 10px 30px rgba(91,110,255,.5), inset 0 1px 0 rgba(255,255,255,.5)}
  header p{color:var(--mut);margin-top:10px;font-size:15.5px}
  .badge{display:inline-flex;gap:7px;align-items:center;margin-top:14px;font-size:12.5px;color:var(--mut);
       background:var(--glass);border:1px solid var(--brd);padding:6px 14px;border-radius:999px;
       backdrop-filter:blur(var(--blur)) saturate(160%);-webkit-backdrop-filter:blur(var(--blur)) saturate(160%)}
  .dot{width:8px;height:8px;border-radius:50%;background:var(--ok);box-shadow:0 0 12px var(--ok)}

  .card{background:var(--glass);border:1px solid var(--brd);border-radius:26px;box-shadow:var(--shadow);
       backdrop-filter:blur(var(--blur)) saturate(180%);-webkit-backdrop-filter:blur(var(--blur)) saturate(180%);
       overflow:hidden}
  .drop{padding:48px 24px;text-align:center;cursor:pointer;transition:.2s}
  .drop.hover{background:linear-gradient(135deg,rgba(91,140,255,.16),rgba(140,92,255,.16))}
  .drop .ic{width:72px;height:72px;margin:0 auto 16px;border-radius:22px;display:grid;place-items:center;font-size:34px;
       background:linear-gradient(135deg,var(--ac),var(--ac2));
       box-shadow:0 12px 34px rgba(91,110,255,.45), inset 0 1px 0 rgba(255,255,255,.45)}
  .drop h2{font-size:20px;margin-bottom:5px;font-weight:700}
  .drop small{color:var(--mut)}
  .fname{color:var(--ac);font-weight:700}

  .ytrow{display:flex;align-items:center;gap:11px;padding:16px 22px;border-top:1px solid var(--brd)}
  .ytic{width:28px;height:28px;border-radius:8px;display:grid;place-items:center;flex:0 0 auto;
       background:#ff0033;color:#fff;font-size:12px;box-shadow:0 4px 12px rgba(255,0,51,.4)}
  .ytrow input{flex:1;background:var(--field);color:var(--tx);border:1px solid var(--brd);
       border-radius:12px;padding:11px 14px;font-size:14px;outline:none;transition:.15s;
       backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px)}
  .ytrow input::placeholder{color:var(--mut)}
  .ytrow input:focus{border-color:var(--ac);box-shadow:0 0 0 3px rgba(91,140,255,.22)}
  .controls{display:flex;gap:14px;flex-wrap:wrap;align-items:flex-end;justify-content:center;
       padding:18px 22px;border-top:1px solid var(--brd)}
  .controls label{font-size:12px;color:var(--mut);display:flex;flex-direction:column;gap:6px;font-weight:600}
  select{background:var(--field);color:var(--tx);border:1px solid var(--brd);border-radius:12px;
       padding:10px 12px;font-size:14px;min-width:150px;cursor:pointer;
       backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px)}
  .btn{margin-left:auto;background:linear-gradient(135deg,var(--ac),var(--ac2));color:#fff;border:0;
       padding:12px 26px;border-radius:14px;font-size:15px;font-weight:700;cursor:pointer;
       box-shadow:0 10px 26px rgba(91,110,255,.45), inset 0 1px 0 rgba(255,255,255,.4);transition:.18s}
  .btn:hover{transform:translateY(-2px);box-shadow:0 14px 32px rgba(91,110,255,.55)}
  .btn:active{transform:translateY(0)}
  .btn:disabled{opacity:.45;cursor:not-allowed;transform:none;box-shadow:none}

  .prog{display:none;margin-top:20px;background:var(--glass);border:1px solid var(--brd);
       border-radius:18px;padding:20px 22px;
       backdrop-filter:blur(var(--blur)) saturate(180%);-webkit-backdrop-filter:blur(var(--blur)) saturate(180%)}
  .prog.on{display:block}
  .bar{height:9px;background:var(--field);border-radius:999px;overflow:hidden;margin-top:12px}
  .bar i{display:block;height:100%;width:0;border-radius:999px;transition:width .3s;
       background:linear-gradient(90deg,var(--ac),var(--ac2));box-shadow:0 0 14px rgba(91,140,255,.6)}
  .st{font-size:13px;color:var(--mut)}

  .out{display:none;margin-top:20px}
  .out.on{display:block;animation:rise .4s ease}
  @keyframes rise{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
  .tabs{display:flex;gap:7px;margin-bottom:14px;flex-wrap:wrap}
  .tab{background:var(--glass);border:1px solid var(--brd);color:var(--mut);padding:9px 17px;
       border-radius:12px;cursor:pointer;font-size:13.5px;font-weight:600;
       backdrop-filter:blur(var(--blur));-webkit-backdrop-filter:blur(var(--blur))}
  .tab.sel{color:#fff;background:linear-gradient(135deg,var(--ac),var(--ac2));border-color:transparent;
       box-shadow:0 8px 20px rgba(91,110,255,.4)}
  .acts{margin-left:auto;display:flex;gap:8px}
  .mini{background:var(--glass);border:1px solid var(--brd);color:var(--tx);padding:9px 15px;
       border-radius:12px;cursor:pointer;font-size:13px;font-weight:600;
       backdrop-filter:blur(var(--blur));-webkit-backdrop-filter:blur(var(--blur))}
  .mini:hover{border-color:var(--ac)}
  .view{background:var(--glass);border:1px solid var(--brd);border-radius:18px;padding:22px;
       max-height:52vh;overflow:auto;white-space:pre-wrap;font-size:14.5px;line-height:1.6;
       backdrop-filter:blur(var(--blur)) saturate(180%);-webkit-backdrop-filter:blur(var(--blur)) saturate(180%)}
  .seg{display:flex;gap:16px;padding:8px 0;border-bottom:1px solid var(--brd)}
  .seg:last-child{border:0}
  .ts{color:var(--ac);font-variant-numeric:tabular-nums;font-size:12.5px;flex:0 0 78px;padding-top:2px;font-weight:600}
  .meta{display:flex;gap:18px;flex-wrap:wrap;justify-content:center;margin-top:14px;font-size:12.5px;color:var(--mut)}
  .err{color:#ff6b6b;text-align:center;margin-top:16px}
  footer{text-align:center;color:var(--mut);font-size:12px;margin-top:30px}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="logo"><span class="mark">🖋️</span> Escriba</div>
    <p>Áudio para texto — rápido, preciso e <b>100% no seu Mac</b>.</p>
    <span class="badge"><span class="dot"></span> Offline · nada sai do computador</span>
  </header>

  <div class="card">
    <div class="drop" id="drop">
      <div class="ic">🎧</div>
      <h2 id="dropTitle">Arraste um áudio ou vídeo aqui</h2>
      <small id="dropSub">ou clique para escolher · MP3, WAV, M4A, FLAC, AAC, OGG, MP4, MOV…</small>
      <input type="file" id="file" accept="audio/*,video/*" hidden>
    </div>
    <div class="ytrow">
      <span class="ytic">▶</span>
      <input id="yt" type="text" placeholder="…ou cole um link do YouTube aqui">
      <button class="mini" id="ytclear" title="limpar" style="display:none">✕</button>
    </div>
    <div class="controls">
      <label>Modelo
        <select id="model">
          <option value="tiny">tiny · ultra rápido</option>
          <option value="base">base · rápido</option>
          <option value="small" selected>small · equilíbrio ⭐</option>
          <option value="medium">medium · preciso</option>
          <option value="large-v3">large-v3 · máximo</option>
        </select>
      </label>
      <label>Idioma
        <select id="lang">
          <option value="auto" selected>Detectar</option>
          <option value="pt">Português</option>
          <option value="en">Inglês</option>
          <option value="es">Espanhol</option>
        </select>
      </label>
      <button class="btn" id="go" disabled>Transcrever</button>
    </div>
  </div>

  <div class="prog" id="prog">
    <div class="st" id="st">Preparando…</div>
    <div class="bar"><i id="fill"></i></div>
  </div>

  <div class="err" id="err"></div>

  <div class="out" id="out">
    <div class="tabs">
      <div class="tab sel" data-v="seg">Com tempos</div>
      <div class="tab" data-v="txt">Texto puro</div>
      <div class="tab" data-v="srt">SRT</div>
      <div class="tab" data-v="vtt">VTT</div>
      <div class="acts">
        <button class="mini" id="copy">Copiar</button>
        <button class="mini" id="save">Baixar</button>
      </div>
    </div>
    <div class="view" id="view"></div>
    <div class="meta" id="meta"></div>
  </div>

  <footer>Escriba · motor faster-whisper (int8) · feito para o Gustavo 🇧🇷</footer>
</div>

<script>
const $=s=>document.querySelector(s);
let arquivo=null, segs=[], vista="seg", info={};

const drop=$("#drop"), file=$("#file");
drop.onclick=()=>file.click();
["dragover","dragenter"].forEach(e=>drop.addEventListener(e,ev=>{ev.preventDefault();drop.classList.add("hover")}));
["dragleave","drop"].forEach(e=>drop.addEventListener(e,ev=>{ev.preventDefault();drop.classList.remove("hover")}));
drop.addEventListener("drop",ev=>{if(ev.dataTransfer.files[0])escolher(ev.dataTransfer.files[0])});
file.onchange=()=>{if(file.files[0])escolher(file.files[0])};

const yt=$("#yt"), ytclear=$("#ytclear");
function escolher(f){
  arquivo=f; yt.value="";
  $("#dropTitle").innerHTML='<span class="fname">'+f.name+'</span>';
  $("#dropSub").textContent=(f.size/1048576).toFixed(1)+" MB · pronto para transcrever";
  atualizarBotao();
}
yt.addEventListener("input",()=>{
  const v=yt.value.trim();
  ytclear.style.display=v?"block":"none";
  if(v){ arquivo=null;
    $("#dropTitle").textContent="Arraste um áudio ou vídeo aqui";
    $("#dropSub").textContent="ou clique para escolher · MP3, WAV, M4A, MP4…"; }
  atualizarBotao();
});
ytclear.onclick=()=>{yt.value="";ytclear.style.display="none";atualizarBotao();};
function ehYoutube(){return yt.value.trim().length>0;}
function atualizarBotao(){$("#go").disabled=!(arquivo||ehYoutube());}

$("#go").onclick=async()=>{
  if(!arquivo && !ehYoutube())return;
  $("#go").disabled=true; $("#err").textContent="";
  $("#out").classList.remove("on"); segs=[];
  $("#prog").classList.add("on");
  const comum="&model="+$("#model").value+"&lang="+$("#lang").value;
  try{
    let url;
    if(ehYoutube()){
      setBar(0,"Conectando ao YouTube…");
      url="/stream?url="+encodeURIComponent(yt.value.trim())+comum;
    }else{
      setBar(0,"Enviando o áudio…");
      const r=await fetch("/upload",{method:"POST",
        headers:{"X-Filename":encodeURIComponent(arquivo.name)}, body:arquivo});
      const {id}=await r.json();
      url="/stream?id="+encodeURIComponent(id)+comum;
    }
    const es=new EventSource(url);
    es.addEventListener("status",e=>setBar(3,JSON.parse(e.data).msg));
    es.addEventListener("info",e=>{info=JSON.parse(e.data)});
    es.addEventListener("progress",e=>setBar(JSON.parse(e.data).pct));
    es.addEventListener("seg",e=>{segs.push(JSON.parse(e.data)); render(); });
    es.addEventListener("done",e=>{
      es.close(); info=Object.assign(info,JSON.parse(e.data));
      setBar(100,"Concluído"); setTimeout(()=>$("#prog").classList.remove("on"),600);
      $("#go").disabled=false; render(); metaLine();
    });
    es.addEventListener("error",e=>{
      es.close(); $("#prog").classList.remove("on"); $("#go").disabled=false;
      let m="Falha ao transcrever."; try{m=JSON.parse(e.data).msg}catch(_){}
      $("#err").textContent="⚠ "+m;
    });
  }catch(err){
    $("#prog").classList.remove("on"); $("#go").disabled=false;
    $("#err").textContent="⚠ "+err.message;
  }
};

function setBar(p,txt){ $("#fill").style.width=p+"%"; if(txt)$("#st").textContent=txt;
  else $("#st").textContent="Transcrevendo… "+p+"%"; }

// ---- montagem das visões ----
function fmt(t){const h=Math.floor(t/3600),m=Math.floor(t%3600/60),s=Math.floor(t%60);
  return (h?String(h).padStart(2,"0")+":":"")+String(m).padStart(2,"0")+":"+String(s).padStart(2,"0");}
function fmtMs(t,sep){const ms=Math.floor((t%1)*1000);
  return fmt(t)+ (sep||",") +String(ms).padStart(3,"0");}

function textoPuro(){return segs.map(s=>s.text).join(" ").replace(/\s+/g," ").trim();}
function srt(){return segs.map((s,i)=>(i+1)+"\n"+fmtMs(s.start)+" --> "+fmtMs(s.end)+"\n"+s.text+"\n").join("\n");}
function vtt(){return "WEBVTT\n\n"+segs.map(s=>fmtMs(s.start,".")+" --> "+fmtMs(s.end,".")+"\n"+s.text).join("\n\n");}

function conteudo(){return vista==="txt"?textoPuro():vista==="srt"?srt():vista==="vtt"?vtt():null;}

function render(){
  $("#out").classList.add("on");
  const v=$("#view");
  if(vista==="seg"){
    v.innerHTML=segs.map(s=>'<div class="seg"><span class="ts">'+fmt(s.start)+'</span><span>'+esc(s.text)+'</span></div>').join("")||"<i>(sem fala detectada)</i>";
  }else{ v.textContent=conteudo(); }
  v.scrollTop=v.scrollHeight;
}
function esc(t){return t.replace(/&/g,"&amp;").replace(/</g,"&lt;");}

function metaLine(){
  $("#meta").innerHTML=
    "🗣️ idioma: <b>"+(info.language||"?")+"</b>"+
    " &nbsp;·&nbsp; ⏱️ áudio: <b>"+fmt(info.duration||0)+"</b>"+
    " &nbsp;·&nbsp; ⚡ processado em <b>"+(info.elapsed||0)+"s</b>"+
    " &nbsp;·&nbsp; 🧩 <b>"+segs.length+"</b> segmentos";
}

document.querySelectorAll(".tab").forEach(t=>t.onclick=()=>{
  document.querySelectorAll(".tab").forEach(x=>x.classList.remove("sel"));
  t.classList.add("sel"); vista=t.dataset.v; render();
});

$("#copy").onclick=()=>{const c=vista==="seg"?textoPuro():conteudo();
  navigator.clipboard.writeText(c); $("#copy").textContent="Copiado ✓";
  setTimeout(()=>$("#copy").textContent="Copiar",1200);};

$("#save").onclick=()=>{
  const ext=vista==="srt"?"srt":vista==="vtt"?"vtt":"txt";
  const c=vista==="seg"?textoPuro():conteudo();
  const nome=(arquivo?arquivo.name.replace(/\.[^.]+$/,""):"transcricao")+"."+ext;
  const a=document.createElement("a");
  a.href=URL.createObjectURL(new Blob([c],{type:"text/plain;charset=utf-8"}));
  a.download=nome; a.click();
};
</script>
</body>
</html>
"""


def main():
    print("\n  🖋️  Escriba — transcrição local")
    print("  " + "-" * 34)
    endereco = f"http://{HOST}:{PORTA}"
    try:
        srv = Servidor((HOST, PORTA), Handler)
    except OSError:
        print(f"  ⚠ A porta {PORTA} já está em uso. Feche a outra janela e tente de novo.")
        sys.exit(1)
    print(f"  Abrindo {endereco} no navegador…")
    print("  (deixe esta janela aberta enquanto usa; Ctrl+C para encerrar)\n")
    threading.Timer(0.8, lambda: webbrowser.open(endereco)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n  Até logo! 👋")
        srv.shutdown()


if __name__ == "__main__":
    main()
