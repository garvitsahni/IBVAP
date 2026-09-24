#!/usr/bin/env python
"""Minimal single-purpose box labeler for the car/bike webcam frames.

Serves http://localhost:8765 — draw boxes, press 1 (car) / 2 (motorcycle),
Enter to save + next, N to skip a frame with nothing labelable, Z to undo.

Saves YOLO-format <stem>.txt (class x_c y_c w h, normalized) into LABEL_DIR
with local class ids: 0=car, 1=motorcycle (remapped to COCO 2/3 at train time).

Stdlib only. Run: venv\\Scripts\\python.exe scripts/label_cars.py [--pool DIR] [--port 8765]
"""
import argparse
import functools
import http.server
import json
import os
import socketserver
import urllib.parse

CLASSES = ["car", "motorcycle"]

PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>car/bike labeler</title>
<style>
body{font-family:sans-serif;background:#111;color:#eee;margin:0;padding:12px}
#bar{display:flex;gap:16px;align-items:center;margin-bottom:8px;flex-wrap:wrap}
#wrap{position:relative;display:inline-block;max-width:96vw}
#img{max-width:96vw;max-height:78vh;display:block}
#box{position:absolute;border:2px solid #0f0;pointer-events:none;display:none}
#box.moto{border-color:#0ff}
.hint{color:#aaa;font-size:13px}
b.k{background:#333;border:1px solid #666;border-radius:4px;padding:0 6px}
#cls{font-weight:bold}
</style></head><body>
<div id="bar"><span id="prog"></span><span>class: <span id="cls">car</span></span>
<span class="hint">drag = box &nbsp; <b class="k">1</b> car &nbsp; <b class="k">2</b> bike &nbsp;
<b class="k">Enter</b> save+next &nbsp; <b class="k">N</b> skip &nbsp; <b class="k">Z</b> undo</span></div>
<div id="wrap"><img id="img"><div id="box"></div></div>
<script>
let cur=null, boxes=[], cls=0, sx=0, sy=0, drawing=false, fname="";
const img=document.getElementById('img'), boxEl=document.getElementById('box'),
      wrap=document.getElementById('wrap');
async function load(){
  const q=await (await fetch('/queue')).json();
  document.getElementById('prog').textContent=`done ${q.done} / ${q.total} (skip empties with N)`;
  if(!q.next){document.body.innerHTML='<h2>All labeled. Done.</h2>';return;}
  fname=q.next; boxes=[]; drawBox(null); img.src='/image?name='+encodeURIComponent(fname);
}
function pos(e){const r=img.getBoundingClientRect();return [(e.clientX-r.left)/r.width,(e.clientY-r.top)/r.height];}
img.onmousedown=e=>{drawing=true;[sx,sy]=pos(e);};
img.onmousemove=e=>{if(!drawing)return;const [x,y]=pos(e);drawBox([sx,sy,x,y]);};
img.onmouseup=e=>{drawing=false;const [x,y]=pos(e);
  boxes.push({cls,x1:Math.min(sx,x),y1:Math.min(sy,y),x2:Math.max(sx,x),y2:Math.max(sy,y)});drawBox(null);};
function drawBox(r){
  if(!r&&!boxes.length){boxEl.style.display='none';return;}
  r=r||[boxes[boxes.length-1].x1,boxes[boxes.length-1].y1,boxes[boxes.length-1].x2,boxes[boxes.length-1].y2];
  const W=img.getBoundingClientRect();
  boxEl.style.display='block';
  boxEl.style.left=r[0]*W.width+'px';boxEl.style.top=r[1]*W.height+'px';
  boxEl.style.width=(r[2]-r[0])*W.width+'px';boxEl.style.height=(r[3]-r[1])*W.height+'px';
  boxEl.className=boxes.length&&boxes[boxes.length-1].cls==1?'moto':'';
  if(boxes.length)boxEl.id='box';
}
document.onkeydown=async e=>{
  if(e.key==='1'){cls=0;document.getElementById('cls').textContent='car';}
  else if(e.key==='2'){cls=1;document.getElementById('cls').textContent='motorcycle';}
  else if(e.key==='z'||e.key==='Z'){boxes.pop();drawBox(null);}
  else if(e.key==='n'||e.key==='N'){await fetch('/skip?name='+encodeURIComponent(fname));load();}
  else if(e.key==='Enter'){
    if(!boxes.length){await fetch('/skip?name='+encodeURIComponent(fname));load();return;}
    boxes.forEach(b=>b.cls=(b.cls===undefined?cls:b.cls));
    // attach current class to boxes drawn before class was set: default already 0; fix: use latest cls for classless
    await fetch('/save',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({name:fname,boxes:boxes})});
    load();
  }
};
// new boxes inherit the currently selected class
const _push=Array.prototype.push;
setInterval(()=>{boxes.forEach(b=>{if(b.cls===undefined)b.cls=cls;});},200);
load();
</script></body></html>
"""


class Handler(http.server.SimpleHTTPRequestHandler):
    pool = ""
    label_dir = ""

    def log_message(self, *a):
        pass

    def _names(self):
        imgs = sorted(f for f in os.listdir(self.pool) if f.endswith(".jpg"))
        done = {f[:-4] + ".txt" for f in os.listdir(self.label_dir)} if os.path.isdir(self.label_dir) else set()
        skipped = set()
        skipfile = os.path.join(self.label_dir, "_skipped.txt")
        if os.path.exists(skipfile):
            skipped = {l.strip() for l in open(skipfile) if l.strip()}
        todo = [i for i in imgs if i[:-4] + ".txt" not in done and i not in skipped]
        return imgs, done, skipped, todo

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/":
            body = PAGE.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif parsed.path == "/queue":
            imgs, done, skipped, todo = self._names()
            body = json.dumps({"done": len(done), "skipped": len(skipped),
                               "total": len(imgs), "next": todo[0] if todo else None}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif parsed.path == "/image":
            name = urllib.parse.parse_qs(parsed.query).get("name", [""])[0]
            safe = os.path.basename(name)
            path = os.path.join(self.pool, safe)
            if not safe.endswith(".jpg") or not os.path.exists(path):
                self.send_error(404)
                return
            data = open(path, "rb").read()
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif parsed.path == "/skip":
            name = os.path.basename(urllib.parse.parse_qs(parsed.query).get("name", [""])[0])
            with open(os.path.join(self.label_dir, "_skipped.txt"), "a") as f:
                f.write(name + "\n")
            self.send_response(200)
            self.end_headers()
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path != "/save":
            self.send_error(404)
            return
        try:
            n = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(n) or b"{}")
            name = os.path.basename(payload.get("name", ""))
            assert name.endswith(".jpg")
            stem = name[:-4]
            img_path = os.path.join(self.pool, name)
            import struct
            with open(img_path, "rb") as f:
                data = f.read()
            # JPEG SOF: find width/height without cv2
            w = h = 0
            i = 2
            while i < len(data) - 9:
                if data[i] != 0xFF:
                    i += 1
                    continue
                m = data[i + 1]
                if m in (0xC0, 0xC1, 0xC2):
                    h = struct.unpack(">H", data[i + 5:i + 7])[0]
                    w = struct.unpack(">H", data[i + 7:i + 9])[0]
                    break
                i += 2 + struct.unpack(">H", data[i + 2:i + 4])[0]
            assert w > 0 and h > 0, "bad jpeg dims"
            lines = []
            for b in payload.get("boxes", []):
                x1, y1, x2, y2 = (max(0.0, min(1.0, float(b[k]))) for k in ("x1", "y1", "x2", "y2"))
                if x2 <= x1 or y2 <= y1:
                    continue
                lines.append("%d %.6f %.6f %.6f %.6f" % (
                    int(b.get("cls", 0)), (x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1))
            if lines:
                with open(os.path.join(self.label_dir, stem + ".txt"), "w") as f:
                    f.write("\n".join(lines) + "\n")
            self.send_response(200)
            self.end_headers()
        except Exception as e:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(str(e).encode())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", default=os.path.join("data", "car-bike-train", "pool"))
    ap.add_argument("--labels", default=os.path.join("data", "car-bike-train", "labels"))
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    os.makedirs(args.labels, exist_ok=True)
    Handler.pool = os.path.abspath(args.pool)
    Handler.label_dir = os.path.abspath(args.labels)
    with socketserver.TCPServer(("127.0.0.1", args.port), Handler) as httpd:
        print(f"labeler at http://127.0.0.1:{args.port} pool={Handler.pool}", flush=True)
        httpd.serve_forever()


if __name__ == "__main__":
    main()
