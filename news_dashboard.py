#!/usr/bin/env python3
"""
资讯看板 (News Dashboard)
=========================
读取 StockYiDongMac「一键分析 / 一键资讯」的落盘产物 —— SQLite 数据库 news_info 表，
以网页看板形式可视化展示，前端每 30 秒自动刷新。

数据流：
  StockYiDongMac GUI[一键分析] -> analyze_stock_keywords_local()
                     [一键资讯] -> save_news_info_to_db() -> news_info 表
  本看板 -------------------------------> 读取 news_info 表 -> 网页展示

数据源：stockyidong_project/data/stock_analysis.db  (news_info 表)
约束：
  - 不独立启动 GUI 程序，只读库，避免触发 Tkinter 主循环
  - 所有内容来自 news_info 真实落盘数据，不编造
  - 零依赖：标准库 http.server + 原生 HTML/Canvas，离线可用

启动：
  python3 news_dashboard.py                  # 默认端口 8778，自动开浏览器
  python3 news_dashboard.py --port 9000 --no-browser
"""
import argparse
import json
import os
import sqlite3
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE_DIR = "/Users/faronpan/Agent/stockyidong_project"
DB_PATH = os.path.join(BASE_DIR, "data", "stock_analysis.db")
DEFAULT_PORT = 8778

# 类型归类规则：(key, 中文名, [关键词])，按出现顺序匹配
TYPE_RULES = [
    ("analysis",  "分析结果",   ["右侧_分析", "右侧_分析结果", "分析结果", "AI分析结果",
                                "右侧_jiuya", "右侧_taogu", "右侧_雪球", "右侧_同花顺",
                                "右侧_选股宝", "右侧_东方财富", "右侧_OCR识别", "右侧_蜘蛛读取", "右侧_通义千问", "右侧_豆包", "右侧_行鱼复盘", "右侧_财联社", "右侧_纳米"]),
    ("mindmap",   "思维导图",   ["思维导图"]),
    ("logictable","逻辑表格",   ["逻辑表格"]),
    ("leader",    "龙头补涨",   ["龙头补涨分析"]),
    ("daily",     "日报/推荐",  ["斯东克日报", "凯均日报", "每日推荐", "晨会", "午间热点",
                                "日内汇总", "市场情绪", "报告｜", "主推荐", "板块强势股", "热门股"]),
    ("jiuyan",    "韭研公社",   ["jiuyang", "韭研", "韭研公社", "左侧_jiuyang", "右侧_jiuyan", "左侧_韭研", "右侧_韭研"]),
    ("taoguba",   "淘股吧",     ["taoguba", "淘股吧", "左侧_taogu", "右侧_taogu", "左侧_淘股吧", "右侧_淘股吧", "淘股宝"]),
    ("ths",       "同花顺",     ["同花顺", "左侧_同花顺", "右侧_同花顺", "同花顺热"]),
    ("eastmoney", "东方财富",   ["东方财富"]),
    ("xueqiu",    "雪球",       ["雪球"]),
    ("xuangubao", "选股宝",     ["选股宝"]),
    ("warn",      "警示",       ["警示失败", "警示成功", "暴跌提示", "周期涨跌幅", "均线仓位", "MA20"]),
    ("wordcloud", "词云",       ["词云"]),
    ("excel",     "Excel/爬虫", ["Excel", "左侧_Excel", "右侧_Excel", "jiuyang_gongshe", "taoguba_100", "批量爬取资讯", "参考爬取", "蜘蛛读取"]),
    ("raw",       "原资讯(左侧)", ["左侧_"]),
]

def classify(tab_name):
    n = tab_name or ""
    for key, name, kws in TYPE_RULES:
        for kw in kws:
            if kw in n:
                return key, name
    return "other", "其他"

# ----------------------------- 数据层 -----------------------------
def db_connect():
    return sqlite3.connect(DB_PATH)

def get_meta():
    try:
        conn = db_connect(); cur = conn.cursor()
        cur.execute("SELECT COUNT(*), MAX(created_at) FROM news_info")
        total, latest = cur.fetchone()
        cur.execute("SELECT tab_name FROM news_info")
        names = [r[0] for r in cur.fetchall()]
        conn.close()
        types = {}
        for nm in names:
            k, cn = classify(nm)
            if k not in types:
                types[k] = [cn, 0]
            types[k][1] += 1
        type_list = sorted(({"key": k, "name": v[0], "count": v[1]} for k, v in types.items()),
                           key=lambda x: -x["count"])
        analysis_count = next((t["count"] for t in type_list if t["key"] == "analysis"), 0)
        return {"total": total or 0, "latest": latest or "", "type_count": len(type_list),
                "analysis_count": analysis_count, "types": type_list}
    except Exception as e:
        return {"error": str(e)}

def query_news(limit=200, type_key="", q=""):
    try:
        conn = db_connect(); cur = conn.cursor()
        cur.execute("SELECT id, tab_name, content, created_at FROM news_info ORDER BY created_at DESC")
        rows = cur.fetchall(); conn.close()
    except Exception as e:
        return {"error": str(e)}
    items = []
    for rid, name, content, ts in rows:
        k, cn = classify(name)
        if type_key and k != type_key:
            continue
        if q:
            if q not in (name or "") and q not in (content or ""):
                continue
        content = content or ""
        pv = content[:240].replace("\r", "")
        if len(content) > 240:
            pv += " …"
        items.append({
            "id": rid, "tab_name": name, "type_key": k, "type_name": cn,
            "created_at": ts, "len": len(content), "preview": pv
        })
        if len(items) >= limit:
            break
    return items

def get_news_detail(nid):
    try:
        conn = db_connect(); cur = conn.cursor()
        cur.execute("SELECT id, tab_name, content, created_at FROM news_info WHERE id=?", (nid,))
        r = cur.fetchone(); conn.close()
        if not r:
            return None
        return {"id": r[0], "tab_name": r[1], "content": r[2] or "", "created_at": r[3]}
    except Exception as e:
        return {"error": str(e)}

# ----------------------------- HTTP 层 -----------------------------
class Handler(BaseHTTPRequestHandler):
    def _send(self, code, ctype, body_bytes):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body_bytes)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body_bytes)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        try:
            if path in ("/", "/index.html"):
                self._send(200, "text/html; charset=utf-8", HTML_PAGE.encode("utf-8"))
            elif path == "/api/news":
                qs = urllib.parse.parse_qs(parsed.query)
                limit = int((qs.get("limit") or ["200"])[0])
                type_key = (qs.get("type") or [""])[0]
                q = (qs.get("q") or [""])[0]
                meta = get_meta()
                items = query_news(limit, type_key, q)
                if isinstance(items, dict) and "error" in items:
                    items = []
                latest = items[0]["created_at"] if items else (meta.get("latest") or "")
                payload = {"items": items, "meta": {**meta, "latest": latest}}
                self._send(200, "application/json; charset=utf-8",
                           json.dumps(payload, ensure_ascii=False).encode("utf-8"))
            elif path.startswith("/api/news/") and len(path.split("/")) == 4:
                nid = path.split("/")[-1]
                try:
                    nid = int(nid)
                except Exception:
                    nid = None
                detail = get_news_detail(nid) if nid else {"error": "invalid id"}
                self._send(200, "application/json; charset=utf-8",
                           json.dumps(detail, ensure_ascii=False).encode("utf-8"))
            else:
                self._send(404, "application/json; charset=utf-8",
                           json.dumps({"error": "not found"}, ensure_ascii=False).encode("utf-8"))
        except Exception as e:
            self._send(500, "application/json; charset=utf-8",
                       json.dumps({"error": str(e)}, ensure_ascii=False).encode("utf-8"))

    def log_message(self, *a):
        pass

# ----------------------------- 前端页面 -----------------------------
HTML_PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>斯东克 · 资讯看板</title>
<style>
  :root{
    --bg:#0d1117; --panel:#161b22; --panel2:#1c2230; --border:#2d333b;
    --txt:#e6edf3; --sub:#8b949e; --accent:#58a6ff; --green:#3fb950;
    --orange:#f0883e; --purple:#bc8cff; --red:#f85149; --yellow:#e3b341;
  }
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:var(--bg);color:var(--txt);font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;font-size:14px}
  header{position:sticky;top:0;z-index:20;background:var(--panel);border-bottom:1px solid var(--border);padding:14px 20px;display:flex;align-items:center;gap:18px;flex-wrap:wrap}
  header h1{font-size:18px;font-weight:700}
  header h1 .em{color:var(--accent)}
  .kpis{display:flex;gap:14px;flex-wrap:wrap;margin-left:auto}
  .kpi{background:var(--panel2);border:1px solid var(--border);border-radius:8px;padding:6px 12px;text-align:center;min-width:84px}
  .kpi .v{font-size:18px;font-weight:700;color:var(--accent)}
  .kpi .l{font-size:11px;color:var(--sub);margin-top:2px}
  .toolbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
  #q{background:var(--panel2);border:1px solid var(--border);color:var(--txt);border-radius:6px;padding:7px 10px;width:200px;font-size:13px}
  button{cursor:pointer;background:var(--panel2);border:1px solid var(--border);color:var(--txt);border-radius:6px;padding:7px 12px;font-size:13px}
  button:hover{border-color:var(--accent)}
  #status{font-size:12px;color:var(--sub);margin-left:auto}
  #bell{color:var(--yellow);font-weight:700;display:none;margin-left:10px}
  .layout{display:flex;gap:0;align-items:flex-start}
  aside{width:210px;flex:0 0 210px;position:sticky;top:64px;height:calc(100vh - 64px);overflow-y:auto;padding:14px;border-right:1px solid var(--border);background:var(--panel)}
  aside h3{font-size:12px;color:var(--sub);text-transform:uppercase;letter-spacing:1px;margin-bottom:10px}
  .typeItem{display:flex;justify-content:space-between;align-items:center;padding:7px 10px;border-radius:6px;cursor:pointer;border:1px solid transparent;margin-bottom:4px}
  .typeItem:hover{background:var(--panel2)}
  .typeItem.active{background:var(--panel2);border-color:var(--accent)}
  .typeItem .tn{display:flex;align-items:center;gap:7px}
  .dot{width:9px;height:9px;border-radius:50%;flex:0 0 9px}
  .typeItem .cnt{font-size:12px;color:var(--sub)}
  main{flex:1;padding:16px 20px;min-width:0}
  .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:14px}
  .card{background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:14px;cursor:pointer;transition:border-color .15s;display:flex;flex-direction:column;gap:8px}
  .card:hover{border-color:var(--accent)}
  .card .top{display:flex;justify-content:space-between;align-items:center;gap:8px}
  .badge{font-size:11px;padding:2px 8px;border-radius:20px;font-weight:600;white-space:nowrap}
  .card .tname{font-size:13px;font-weight:600;color:var(--txt);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1}
  .card .meta{font-size:11px;color:var(--sub);display:flex;gap:10px}
  .card .prev{font-size:12px;color:#c9d1d9;line-height:1.5;max-height:84px;overflow:hidden;white-space:pre-wrap;word-break:break-word}
  .empty{text-align:center;color:var(--sub);padding:60px 20px}
  #modal{position:fixed;inset:0;background:rgba(0,0,0,.6);display:none;z-index:50;align-items:flex-start;justify-content:center;padding:40px 16px;overflow-y:auto}
  #modalBox{background:var(--panel);border:1px solid var(--border);border-radius:12px;max-width:900px;width:100%;padding:22px}
  #modalBox h2{font-size:16px;margin-bottom:6px;word-break:break-word}
  #modalBox .mmeta{font-size:12px;color:var(--sub);margin-bottom:14px}
  #modalContent{white-space:pre-wrap;word-break:break-word;font-size:13px;line-height:1.65;max-height:62vh;overflow-y:auto;background:var(--bg);border:1px solid var(--border);border-radius:8px;padding:14px;font-family:"SF Mono",Menlo,Consolas,monospace}
  #modalClose{float:right}
  .hint{font-size:11px;color:var(--sub);margin-top:8px;line-height:1.6}
  .t-accent{background:rgba(88,166,255,.15);color:var(--accent)}
  .t-green{background:rgba(63,185,80,.15);color:var(--green)}
  .t-orange{background:rgba(240,136,62,.15);color:var(--orange)}
  .t-purple{background:rgba(188,140,255,.15);color:var(--purple)}
  .t-red{background:rgba(248,81,73,.15);color:var(--red)}
  .t-yellow{background:rgba(227,179,65,.15);color:var(--yellow)}
  .t-gray{background:rgba(139,148,158,.15);color:var(--sub)}
</style>
</head>
<body>
<header>
  <h1>📰 斯东克 · <span class="em">资讯看板</span></h1>
  <div class="kpis">
    <div class="kpi"><div class="v" id="kTotal">–</div><div class="l">资讯总数</div></div>
    <div class="kpi"><div class="v" id="kType">–</div><div class="l">类型数</div></div>
    <div class="kpi"><div class="v" id="kAna">–</div><div class="l">分析结果</div></div>
    <div class="kpi"><div class="v" id="kLatest">–</div><div class="l">最新更新</div></div>
  </div>
</header>
<div style="padding:10px 20px;border-bottom:1px solid var(--border);background:var(--panel)">
  <div class="toolbar">
    <input id="q" placeholder="搜索标题 / 内容关键词…" />
    <button onclick="applyQ()">🔍 搜索</button>
    <button onclick="loadNews(true)">🔄 同步最新分析</button>
    <span id="bell">🔔 发现新分析</span>
    <span id="status"></span>
    <div class="hint" style="width:100%">
      数据源：StockYiDongMac「一键分析 / 一键资讯」落盘的 <code>news_info</code> 表。
      在桌面程序点「一键分析」→「一键资讯」后，点上方「同步最新分析」或等待自动刷新（30s）即可看到结果。
    </div>
  </div>
</div>
<div class="layout">
  <aside>
    <h3>类型筛选</h3>
    <div id="types"></div>
  </aside>
  <main>
    <div class="grid" id="grid"></div>
    <div class="empty" id="empty" style="display:none">暂无符合条件的资讯</div>
  </main>
</div>
<div id="modal" onclick="if(event.target===this)closeModal()">
  <div id="modalBox">
    <button id="modalClose" onclick="closeModal()">✕ 关闭</button>
    <h2 id="modalTitle"></h2>
    <div class="mmeta" id="modalMeta"></div>
    <div id="modalContent"></div>
  </div>
</div>
<script>
const TYPE_STYLE = {
  analysis:{cls:'t-accent',color:'#58a6ff'},
  mindmap:{cls:'t-purple',color:'#bc8cff'},
  logictable:{cls:'t-purple',color:'#bc8cff'},
  leader:{cls:'t-orange',color:'#f0883e'},
  daily:{cls:'t-green',color:'#3fb950'},
  jiuyan:{cls:'t-yellow',color:'#e3b341'},
  taoguba:{cls:'t-orange',color:'#f0883e'},
  ths:{cls:'t-accent',color:'#58a6ff'},
  eastmoney:{cls:'t-green',color:'#3fb950'},
  xueqiu:{cls:'t-red',color:'#f85149'},
  xuangubao:{cls:'t-orange',color:'#f0883e'},
  warn:{cls:'t-red',color:'#f85149'},
  wordcloud:{cls:'t-gray',color:'#8b949e'},
  excel:{cls:'t-gray',color:'#8b949e'},
  raw:{cls:'t-gray',color:'#8b949e'},
  other:{cls:'t-gray',color:'#8b949e'}
};
let curType="", curQ="", lastLatest="";
const $ = id => document.getElementById(id);

function setStatus(t){ $('status').textContent = t; }
function esc(s){ return (s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }

async function loadNews(manual){
  setStatus("加载中…");
  let url = "/api/news?limit=300";
  if(curType) url += "&type="+encodeURIComponent(curType);
  if(curQ) url += "&q="+encodeURIComponent(curQ);
  try{
    const r = await fetch(url); const d = await r.json();
    if(d.meta){ renderKPI(d.meta); renderTypes(d.meta.types);
      if(d.meta.latest && lastLatest && d.meta.latest>lastLatest && !manual){
        $('bell').style.display='inline';
      }
      if(d.meta.latest) lastLatest = d.meta.latest;
    }
    renderList(d.items||[]);
    setStatus("更新于 "+new Date().toLocaleTimeString());
  }catch(e){ setStatus("加载失败: "+e.message); }
}
function renderKPI(m){
  $('kTotal').textContent = m.total;
  $('kType').textContent = m.type_count;
  $('kAna').textContent = m.analysis_count;
  $('kLatest').textContent = (m.latest||"").slice(5,16);
}
function renderTypes(types){
  const box = $('types'); box.innerHTML="";
  const all = mkType("","全部", (types||[]).reduce((s,t)=>s+t.count,0));
  box.appendChild(all);
  (types||[]).forEach(t=>{ box.appendChild(mkType(t.key,t.name,t.count)); });
}
function mkType(key,name,count){
  const st = TYPE_STYLE[key]||TYPE_STYLE.other;
  const d = document.createElement("div");
  d.className = "typeItem"+(key===curType?" active":"");
  d.innerHTML = `<span class="tn"><span class="dot" style="background:${st.color}"></span>${esc(name)}</span><span class="cnt">${count}</span>`;
  d.onclick = ()=>{ curType = (curType===key?"":key); loadNews(true); };
  return d;
}
function renderList(items){
  const grid = $('grid'); grid.innerHTML="";
  $('empty').style.display = items.length? "none":"block";
  items.forEach(it=>{
    const st = TYPE_STYLE[it.type_key]||TYPE_STYLE.other;
    const c = document.createElement("div"); c.className="card";
    c.innerHTML = `
      <div class="top">
        <span class="badge ${st.cls}">${esc(it.type_name)}</span>
        <span class="tname" title="${esc(it.tab_name)}">${esc(it.tab_name)}</span>
      </div>
      <div class="meta"><span>🕒 ${esc(it.created_at)}</span><span>📏 ${it.len}字</span></div>
      <div class="prev">${esc(it.preview)}</div>`;
    c.onclick = ()=>openDetail(it.id, it.tab_name, it.type_name, it.created_at, it.len);
    grid.appendChild(c);
  });
}
async function openDetail(id,name,typeName,ts,len){
  const box = $('modalBox');
  $('modalTitle').textContent = name;
  $('modalMeta').textContent = `类型：${typeName} ｜ 时间：${ts} ｜ 长度：${len}字`;
  $('modalContent').textContent = "加载中…";
  $('modal').style.display="flex";
  try{
    const r = await fetch("/api/news/"+id); const d = await r.json();
    $('modalContent').textContent = d.content || "(空)";
  }catch(e){ $('modalContent').textContent = "加载失败: "+e.message; }
}
function closeModal(){ $('modal').style.display="none"; }
function applyQ(){ curQ=$('q').value.trim(); loadNews(true); }
$('q').addEventListener('keydown',e=>{ if(e.key==='Enter') applyQ(); });
document.addEventListener('keydown',e=>{ if(e.key==='Escape') closeModal(); });
loadNews(true);
setInterval(()=>{ if($('bell').style.display!=='inline') loadNews(false); }, 30000);
</script>
</body>
</html>"""

# ----------------------------- 启动 -----------------------------
def run(port, open_browser):
    if not os.path.isfile(DB_PATH):
        print(f"⚠️ 未找到数据库: {DB_PATH}")
        return
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"✅ 资讯看板已启动: http://127.0.0.1:{port}/")
    print(f"   数据源: {DB_PATH}")
    if open_browser:
        threading.Timer(1.0, lambda: webbrowser.open(f"http://127.0.0.1:{port}/")).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="斯东克资讯看板")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()
    run(args.port, not args.no_browser)
