#!/usr/bin/env python3
"""Fila do Karaokê — servidor local para a rede Wi-Fi.

Rode no celular (Android com Termux) ou em qualquer computador:
    python fila_karaoke.py

Os convidados abrem o endereço mostrado na tela e colocam o nome na fila.
Quem comanda abre /palco com o PIN e toca em "OK" quando a pessoa terminar.
Só usa a biblioteca padrão do Python; não precisa de internet.
"""

import json
import os
import random
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

PORTA = int(os.environ.get("PORTA", "8000"))
PIN = os.environ.get("PIN") or f"{random.randint(0, 9999):04d}"
ARQUIVO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fila.json")

trava = threading.Lock()
estado = {"fila": [], "proximo_id": 1, "ultimo_removido": None, "versao": 0}


def carregar():
    try:
        with open(ARQUIVO, encoding="utf-8") as f:
            dados = json.load(f)
        estado["fila"] = dados.get("fila", [])
        estado["proximo_id"] = dados.get("proximo_id", 1)
    except (FileNotFoundError, ValueError):
        pass


def salvar():
    tmp = ARQUIVO + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"fila": estado["fila"], "proximo_id": estado["proximo_id"]}, f, ensure_ascii=False)
    os.replace(tmp, ARQUIVO)


def mudou():
    estado["versao"] += 1
    salvar()


def ip_local():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))  # não envia nada, só descobre a interface
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


PAGINA_BASE = """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITULO__</title>
<style>
:root{--bg:#14101f;--card:#211a33;--linha:#3a2f55;--fg:#f4f0ff;--fraco:#a99cc9;--neon:#ff4fa3;--neon2:#4fd8ff;--ok:#3ddc84;--perigo:#ff6b6b}
*{box-sizing:border-box}
[hidden]{display:none!important}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.4 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;padding:20px 16px 40px}
main{max-width:560px;margin:0 auto;display:flex;flex-direction:column;gap:18px}
h1{margin:0;font-size:1.9rem;letter-spacing:.02em;text-wrap:balance}
h1 span{color:var(--neon);text-shadow:0 0 18px rgba(255,79,163,.55)}
.sub{color:var(--fraco);margin:4px 0 0}
.card{background:var(--card);border:1px solid var(--linha);border-radius:14px;padding:16px}
label{display:block;font-size:.8rem;text-transform:uppercase;letter-spacing:.08em;color:var(--fraco);margin:0 0 6px}
input{width:100%;font:inherit;font-size:1.1rem;padding:12px 14px;border-radius:10px;border:1px solid var(--linha);background:var(--bg);color:var(--fg)}
input:focus{outline:2px solid var(--neon2);outline-offset:1px}
form{display:flex;flex-direction:column;gap:12px}
button{font:inherit;font-weight:700;font-size:1.05rem;border:0;border-radius:10px;padding:13px 16px;cursor:pointer;color:#14101f;background:var(--neon)}
button:focus-visible{outline:3px solid var(--neon2);outline-offset:2px}
button:disabled{opacity:.5;cursor:default}
button.ok{background:var(--ok);font-size:1.4rem;padding:18px}
button.sec{background:transparent;color:var(--fraco);border:1px solid var(--linha);font-weight:600;font-size:.9rem;padding:8px 12px}
.agora{border-color:var(--neon);box-shadow:0 0 0 1px var(--neon),0 0 28px rgba(255,79,163,.25)}
.tag{font-size:.75rem;text-transform:uppercase;letter-spacing:.1em;color:var(--neon);font-weight:700}
.nome-grande{font-size:2rem;font-weight:800;margin:4px 0 0;word-break:break-word}
.musica{color:var(--fraco);word-break:break-word}
ol{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:8px}
li{display:flex;align-items:center;gap:12px;padding:10px 12px;border-radius:10px;background:var(--bg);border:1px solid var(--linha)}
li .pos{font-variant-numeric:tabular-nums;color:var(--neon2);font-weight:800;min-width:2ch;text-align:right}
li .txt{flex:1;min-width:0}
li .n{font-weight:700;word-break:break-word}
li.voce{border-color:var(--neon2)}
.vazio{color:var(--fraco);text-align:center;padding:12px 0}
.msg{min-height:1.4em;color:var(--ok);font-weight:600}
.msg.erro{color:var(--perigo)}
.end{font-size:1.3rem;font-weight:800;color:var(--neon2);word-break:break-all}
.linha{display:flex;gap:8px;flex-wrap:wrap;align-items:center;justify-content:space-between}
@media (prefers-reduced-motion:no-preference){.agora{transition:box-shadow .3s}}
</style></head><body><main>__CORPO__</main>
<script>
const $=s=>document.querySelector(s);
async function api(url,dados){
  const r=await fetch(url,dados?{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(dados)}:{cache:"no-store"});
  const j=await r.json().catch(()=>({}));
  if(!r.ok) throw new Error(j.erro||"Não deu certo. Tente de novo.");
  return j;
}
function el(tag,cls,txt){const e=document.createElement(tag);if(cls)e.className=cls;if(txt!=null)e.textContent=txt;return e}
__SCRIPT__
</script></body></html>"""

CONVIDADO_CORPO = """
<header><h1>Fila do <span>Karaokê</span></h1>
<p class="sub">Coloque seu nome e espere sua vez. Quem entra vai para o fim da fila.</p></header>
<section class="card">
  <form id="f">
    <div><label for="nome">Seu nome</label><input id="nome" maxlength="40" autocomplete="name" required placeholder="Ex.: Ana"></div>
    <div><label for="musica">Música (opcional)</label><input id="musica" maxlength="80" placeholder="Ex.: Evidências"></div>
    <button id="btn">Entrar na fila</button>
    <div class="msg" id="msg" role="status"></div>
  </form>
</section>
<section class="card agora" id="agora" hidden>
  <div class="tag">Cantando agora</div>
  <div class="nome-grande" id="agoraNome"></div>
  <div class="musica" id="agoraMus"></div>
</section>
<section class="card">
  <div class="linha"><label style="margin:0">Fila</label><span class="sub" id="total" style="margin:0"></span></div>
  <ol id="lista" style="margin-top:10px"></ol>
</section>
"""

CONVIDADO_SCRIPT = """
let meus=[];try{meus=JSON.parse(localStorage.getItem("meus")||"[]")}catch(e){}
try{$("#nome").value=localStorage.getItem("nome")||""}catch(e){}
$("#f").addEventListener("submit",async ev=>{
  ev.preventDefault();
  const nome=$("#nome").value.trim(),musica=$("#musica").value.trim();
  if(!nome) return;
  $("#btn").disabled=true;$("#msg").className="msg";$("#msg").textContent="";
  try{
    const j=await api("/api/entrar",{nome,musica});
    meus.push(j.id);
    try{localStorage.setItem("meus",JSON.stringify(meus.slice(-20)));localStorage.setItem("nome",nome)}catch(e){}
    $("#msg").textContent="Pronto! Você é o número "+j.posicao+" da fila.";
    $("#musica").value="";
    desenhar(await api("/api/fila"));
  }catch(e){$("#msg").className="msg erro";$("#msg").textContent=e.message}
  $("#btn").disabled=false;
});
function desenhar(d){
  const f=d.fila, lista=$("#lista");
  lista.replaceChildren();
  $("#agora").hidden=!f.length;
  if(f.length){$("#agoraNome").textContent=f[0].nome;$("#agoraMus").textContent=f[0].musica||""}
  const resto=f.slice(1);
  $("#total").textContent=resto.length?resto.length+" esperando":"";
  if(!resto.length){lista.append(el("div","vazio",f.length?"Ninguém esperando. Entre agora!":"A fila está vazia. Seja o primeiro!"));return}
  resto.forEach((p,i)=>{
    const li=el("li",meus.includes(p.id)?"voce":"");
    li.append(el("span","pos",i+1));
    const t=el("div","txt");t.append(el("div","n",p.nome+(meus.includes(p.id)?" (você)":"")));
    if(p.musica)t.append(el("div","musica",p.musica));
    li.append(t);lista.append(li);
  });
}
async function atualizar(){try{desenhar(await api("/api/fila"))}catch(e){}}
atualizar();setInterval(atualizar,3000);
"""

PALCO_CORPO = """
<header><h1>Palco do <span>Karaokê</span></h1>
<p class="sub">Endereço para os convidados:</p><div class="end" id="end"></div></header>
<section class="card" id="travado">
  <form id="fpin"><div><label for="pin">PIN do palco</label><input id="pin" inputmode="numeric" maxlength="12" required></div>
  <button>Entrar</button><div class="msg erro" id="pinmsg" role="status"></div></form>
</section>
<div id="painel" hidden style="display:flex;flex-direction:column;gap:18px">
<section class="card agora">
  <div class="tag">Cantando agora</div>
  <div class="nome-grande" id="agoraNome">Ninguém na fila</div>
  <div class="musica" id="agoraMus"></div>
  <div style="display:flex;flex-direction:column;gap:10px;margin-top:14px">
    <button class="ok" id="ok" disabled>OK, próximo</button>
    <div class="linha"><span class="msg" id="msg" role="status"></span><button class="sec" id="desfazer" disabled>Desfazer</button></div>
  </div>
</section>
<section class="card">
  <div class="linha"><label style="margin:0">Próximos</label><span class="sub" id="total" style="margin:0"></span></div>
  <ol id="lista" style="margin-top:10px"></ol>
</section>
</div>
"""

PALCO_SCRIPT = """
$("#end").textContent=location.origin;
let pin="";try{pin=localStorage.getItem("pin")||""}catch(e){}
let atual=null;
function abrir(){$("#travado").hidden=true;$("#painel").hidden=false;atualizar();setInterval(atualizar,2000)}
$("#fpin").addEventListener("submit",async ev=>{
  ev.preventDefault();pin=$("#pin").value.trim();
  try{await api("/api/pin",{pin});try{localStorage.setItem("pin",pin)}catch(e){}abrir()}
  catch(e){$("#pinmsg").textContent=e.message}
});
async function acao(url,dados){
  $("#msg").className="msg";$("#msg").textContent="";
  try{const d=await api(url,Object.assign({pin},dados));desenhar(d);return d}
  catch(e){$("#msg").className="msg erro";$("#msg").textContent=e.message;atualizar()}
}
$("#ok").addEventListener("click",async()=>{
  if(!atual)return;$("#ok").disabled=true;
  const d=await acao("/api/ok",{id:atual.id});
  if(d)$("#msg").textContent=d.fila.length?"Agora: "+d.fila[0].nome:"Fila vazia";
});
$("#desfazer").addEventListener("click",()=>acao("/api/desfazer",{}));
function desenhar(d){
  const f=d.fila;atual=f[0]||null;
  $("#agoraNome").textContent=atual?atual.nome:"Ninguém na fila";
  $("#agoraMus").textContent=atual&&atual.musica?atual.musica:"";
  $("#ok").disabled=!atual;$("#desfazer").disabled=!d.pode_desfazer;
  const lista=$("#lista");lista.replaceChildren();
  const resto=f.slice(1);
  $("#total").textContent=resto.length?resto.length+" esperando":"";
  if(!resto.length){lista.append(el("div","vazio","Ninguém esperando."));return}
  resto.forEach((p,i)=>{
    const li=el("li");li.append(el("span","pos",i+1));
    const t=el("div","txt");t.append(el("div","n",p.nome));if(p.musica)t.append(el("div","musica",p.musica));li.append(t);
    const b=el("button","sec","Tirar");b.addEventListener("click",()=>acao("/api/tirar",{id:p.id}));li.append(b);
    lista.append(li);
  });
}
async function atualizar(){try{desenhar(await api("/api/fila"))}catch(e){}}
if(pin){api("/api/pin",{pin}).then(abrir).catch(()=>{try{localStorage.removeItem("pin")}catch(e){}})}
"""


def pagina(titulo, corpo, script):
    return (PAGINA_BASE.replace("__TITULO__", titulo)
            .replace("__CORPO__", corpo).replace("__SCRIPT__", script)).encode("utf-8")


HTML_CONVIDADO = pagina("Fila do Karaokê", CONVIDADO_CORPO, CONVIDADO_SCRIPT)
HTML_PALCO = pagina("Palco do Karaokê", PALCO_CORPO, PALCO_SCRIPT)


def visao():
    return {"fila": [{"id": p["id"], "nome": p["nome"], "musica": p.get("musica", "")} for p in estado["fila"]],
            "pode_desfazer": estado["ultimo_removido"] is not None}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def enviar(self, codigo, corpo, tipo="application/json; charset=utf-8"):
        if not isinstance(corpo, bytes):
            corpo = json.dumps(corpo, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def do_GET(self):
        caminho = urlparse(self.path).path
        if caminho in ("/", "/index.html"):
            self.enviar(200, HTML_CONVIDADO, "text/html; charset=utf-8")
        elif caminho == "/palco":
            self.enviar(200, HTML_PALCO, "text/html; charset=utf-8")
        elif caminho == "/api/fila":
            with trava:
                self.enviar(200, visao())
        else:
            self.enviar(404, {"erro": "Página não encontrada"})

    def do_POST(self):
        caminho = urlparse(self.path).path
        try:
            tamanho = min(int(self.headers.get("Content-Length", 0)), 4096)
            dados = json.loads(self.rfile.read(tamanho) or b"{}")
            if not isinstance(dados, dict):
                raise ValueError
        except ValueError:
            return self.enviar(400, {"erro": "Pedido inválido"})

        if caminho == "/api/entrar":
            nome = " ".join(str(dados.get("nome", "")).split())[:40]
            musica = " ".join(str(dados.get("musica", "")).split())[:80]
            if not nome:
                return self.enviar(400, {"erro": "Escreva seu nome."})
            with trava:
                if len(estado["fila"]) >= 300:
                    return self.enviar(400, {"erro": "A fila está cheia."})
                pessoa = {"id": estado["proximo_id"], "nome": nome, "musica": musica, "hora": time.time()}
                estado["proximo_id"] += 1
                estado["fila"].append(pessoa)  # sempre no fim
                mudou()
                return self.enviar(200, {"id": pessoa["id"], "posicao": len(estado["fila"])})

        if caminho.startswith("/api/") and str(dados.get("pin", "")) != PIN:
            return self.enviar(403, {"erro": "PIN errado."})

        with trava:
            if caminho == "/api/pin":
                return self.enviar(200, {"ok": True})
            if caminho == "/api/ok":
                fila = estado["fila"]
                if fila and fila[0]["id"] == dados.get("id"):
                    estado["ultimo_removido"] = (0, fila.pop(0))
                    mudou()
                return self.enviar(200, visao())
            if caminho == "/api/tirar":
                for i, p in enumerate(estado["fila"]):
                    if p["id"] == dados.get("id"):
                        estado["ultimo_removido"] = (i, estado["fila"].pop(i))
                        mudou()
                        break
                return self.enviar(200, visao())
            if caminho == "/api/desfazer":
                if estado["ultimo_removido"]:
                    i, p = estado["ultimo_removido"]
                    estado["fila"].insert(min(i, len(estado["fila"])), p)
                    estado["ultimo_removido"] = None
                    mudou()
                return self.enviar(200, visao())
        self.enviar(404, {"erro": "Ação desconhecida"})


def main():
    carregar()
    try:
        servidor = ThreadingHTTPServer(("0.0.0.0", PORTA), Handler)
    except OSError as e:
        sys.exit(f"Não consegui abrir a porta {PORTA}: {e}\nTente: PORTA=8080 python fila_karaoke.py")
    ip = ip_local()
    print("\n  🎤  Fila do Karaokê no ar!\n")
    print(f"  Convidados:  http://{ip}:{PORTA}")
    print(f"  Palco (você): http://{ip}:{PORTA}/palco   PIN: {PIN}\n")
    print("  Deixe esta tela aberta. Ctrl+C para encerrar.\n")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\n  Até a próxima!")


if __name__ == "__main__":
    main()
