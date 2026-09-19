#!/usr/bin/env python3
"""
斯东克 · 股票当日实时报告数据看板（零依赖本地服务）

- 实时读取 StockYiDong 桌面程序写入的 src/config/ai_config.json
- 自动计算 龙头股 / 15Min / 同花顺 三标签的共振度、覆盖度、板块热度
- 浏览器打开后每 30 秒自动刷新，反映桌面程序最新持仓变化

启动：
  python3 realtime_dashboard.py                 # 默认端口 8777，自动打开浏览器
  python3 realtime_dashboard.py --port 9000     # 指定端口
  python3 realtime_dashboard.py --no-browser    # 不自动打开浏览器

说明：
  - 板块分类为本地静态常识映射（SECTOR_MAP），仅供分布参考，非实时行情数据
  - 所有指标均由持仓标签实时计算，不编造数据
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "src", "config", "ai_config.json")
EXPORT_SCRIPT = os.path.join(BASE_DIR, "src", "stockyidong_export.py")

# 三个核心标签页（与 stockyidong_export.py 对齐）
TABS = [
    ("holding_stocks_2", "龙头股"),
    ("holding_stocks_3", "15Min"),
    ("holding_stocks_6", "同花顺"),
]

# ---- 行业板块静态常识映射（代码 -> 大类）----
# 备注：基于 A 股常识的人工归类，用于板块分布展示，非实时数据，可自由编辑
SECTOR_MAP = {
    # 半导体
    "000021": "半导体", "000636": "半导体", "001270": "半导体", "001309": "半导体",
    "002156": "半导体", "002185": "半导体", "002409": "半导体", "002617": "半导体",
    "300285": "半导体", "600206": "半导体", "600460": "半导体", "600584": "半导体",
    "600667": "半导体", "603893": "半导体", "603986": "半导体", "605358": "半导体",
    "688008": "半导体", "688012": "半导体", "688041": "半导体", "688082": "半导体",
    "688256": "半导体", "688261": "半导体", "688262": "半导体", "688347": "半导体",
    "688432": "半导体", "688548": "半导体", "688702": "半导体", "688981": "半导体",
    "002371": "半导体", "301308": "半导体",
    # 算力/AI
    "000034": "算力/AI", "000066": "算力/AI", "000815": "算力/AI", "000938": "算力/AI",
    "000977": "算力/AI", "002261": "算力/AI", "002837": "算力/AI", "300017": "算力/AI",
    "300990": "算力/AI", "600410": "算力/AI", "600602": "算力/AI", "601138": "算力/AI",
    "603019": "算力/AI", "603629": "算力/AI", "603881": "算力/AI",
    # 通信设备
    "000063": "通信设备", "000889": "通信设备", "002396": "通信设备", "000988": "通信设备",
    "601869": "通信设备", "603118": "通信设备", "688629": "通信设备", "301165": "通信设备",
    # 光模块
    "002281": "光模块", "300308": "光模块", "300394": "光模块", "300502": "光模块",
    "600105": "光模块", "600487": "光模块", "600522": "光模块",
    # PCB
    "002463": "PCB", "002636": "PCB", "300476": "PCB", "600183": "PCB",
    "603459": "PCB", "301377": "PCB",
    # 消费电子
    "000100": "消费电子", "000725": "消费电子", "002384": "消费电子", "002600": "消费电子",
    "300136": "消费电子", "603296": "消费电子",
    # 医药生物
    "000566": "医药生物", "002038": "医药生物", "002432": "医药生物", "300534": "医药生物",
    "300759": "医药生物", "300896": "医药生物", "600513": "医药生物", "600664": "医药生物",
    "603127": "医药生物", "603259": "医药生物", "603538": "医药生物",
    # 新能源电力
    "001248": "新能源电力", "001258": "新能源电力", "001896": "新能源电力", "002407": "新能源电力",
    "300274": "新能源电力", "600396": "新能源电力", "600726": "新能源电力", "600744": "新能源电力",
    "601991": "新能源电力", "603137": "新能源电力",
    # 军工
    "000547": "军工", "002342": "军工", "300065": "军工", "600118": "军工",
    "600879": "军工", "601698": "军工", "603698": "军工",
    # 有色小金属
    "000657": "有色小金属", "002167": "有色小金属", "002428": "有色小金属", "301217": "有色小金属",
    "600988": "有色小金属", "601899": "有色小金属", "603993": "有色小金属",
    # 化工材料
    "600176": "化工材料", "600722": "化工材料", "603065": "化工材料", "603823": "化工材料",
    "603580": "化工材料", "603928": "化工材料", "605090": "化工材料",
    # 机械设备
    "002008": "机械设备", "002141": "机械设备", "002490": "机械设备", "002747": "机械设备",
    "300164": "机械设备", "300503": "机械设备", "301583": "机械设备", "300209": "机械设备",
    # 金融消费
    "000676": "金融消费", "002352": "金融消费", "002354": "金融消费", "002759": "金融消费",
    "300795": "金融消费", "600519": "金融消费", "601318": "金融消费",
}

SECTOR_COLORS = {
    "半导体": "#4f8cff", "算力/AI": "#00d4a0", "通信设备": "#7b61ff",
    "光模块": "#ffb020", "PCB": "#ff7ab6", "消费电子": "#2dd4bf",
    "医药生物": "#ff6b6b", "新能源电力": "#ffd166", "军工": "#9b8cff",
    "有色小金属": "#f4a261", "化工材料": "#8d99ae", "机械设备": "#06d6a0",
    "金融消费": "#ef476f", "未分类": "#555555",
}

TAG_INDEX = {"龙头股": 0, "15Min": 1, "同花顺": 2}


def _valid(key: str, cfg: dict) -> list[dict]:
    return [s for s in cfg.get(key, []) if (s.get("stock_name") or "").strip()]


def build_dashboard() -> dict:
    """实时读取配置，计算共振与分布。"""
    snap = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception as e:
        return {"error": f"读取配置失败: {e}", "snapshot_time": snap}

    # 各标签有效股票 -> code -> name
    tab_stocks: dict[str, dict[str, str]] = {}
    for key, label in TABS:
        tab_stocks[label] = {s["stock_code"]: s["stock_name"] for s in _valid(key, cfg)}

    counts = {label: len(tab_stocks[label]) for _, label in TABS}

    # 去重股票全集
    all_codes: set[str] = set()
    for m in tab_stocks.values():
        all_codes |= set(m.keys())

    # 每只股票的标签与覆盖度
    all_stocks = []
    for code in all_codes:
        tags = [label for label in ("龙头股", "15Min", "同花顺") if code in tab_stocks[label]]
        coverage = len(tags)
        name = next((tab_stocks[t][code] for t in tags if code in tab_stocks[t]), code)
        sector = SECTOR_MAP.get(code, "未分类")
        # 综合评分（纯数据驱动，透明）
        score = 40 if coverage == 1 else (70 if coverage == 2 else 100)
        score += 8 if "龙头股" in tags else 0
        score += 8 if "同花顺" in tags else 0
        score += 6 if "15Min" in tags else 0
        all_stocks.append({
            "code": code, "name": name, "sector": sector,
            "tags": tags, "coverage": coverage, "score": score,
        })

    # 共振集合
    s_long = set(tab_stocks["龙头股"])
    s_min = set(tab_stocks["15Min"])
    s_ths = set(tab_stocks["同花顺"])
    triple = s_long & s_min & s_ths
    lt_ths = (s_long & s_ths) - triple
    lt_min = (s_long & s_min) - triple
    min_ths = (s_min & s_ths) - triple

    name_of = {s["code"]: s["name"] for s in all_stocks}

    def pack(codeset):
        return sorted(
            [{"code": c, "name": name_of.get(c, c),
              "sector": SECTOR_MAP.get(c, "未分类")} for c in codeset],
            key=lambda x: x["name"])

    # 覆盖度分布（去重股票）
    cov = {1: 0, 2: 0, 3: 0}
    for s in all_stocks:
        cov[s["coverage"]] += 1

    # 板块热度（该板块下所有去重股票的覆盖度之和，三标签=3/两=2/单=1）
    sector_heat: dict[str, int] = {}
    for s in all_stocks:
        sector_heat[s["sector"]] = sector_heat.get(s["sector"], 0) + s["coverage"]
    sector_heat_sorted = sorted(
        [{"sector": k, "heat": v, "color": SECTOR_COLORS.get(k, "#555")}
         for k, v in sector_heat.items()],
        key=lambda x: x["heat"], reverse=True)

    # 检索便捷：code -> stock
    by_code = {s["code"]: s for s in all_stocks}

    triple_list = []
    for c in triple:
        st = by_code[c]
        triple_list.append({**st})
    triple_list.sort(key=lambda x: x["score"], reverse=True)

    return {
        "snapshot_time": snap,
        "config_mtime": datetime.datetime.fromtimestamp(
            os.path.getmtime(CONFIG_PATH)).strftime("%Y-%m-%d %H:%M:%S") if os.path.exists(CONFIG_PATH) else "",
        "counts": counts,
        "resonance": {
            "triple": triple_list,
            "lt_ths": pack(lt_ths),
            "lt_min": pack(lt_min),
            "min_ths": pack(min_ths),
        },
        "coverage": cov,
        "sector_heat": sector_heat_sorted,
        "all_stocks": sorted(all_stocks, key=lambda x: x["score"], reverse=True),
    }


HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>斯东克 · 股票实时报告看板</title>
<style>
  :root{
    --bg:#0d1117; --panel:#161b22; --panel2:#1c2230; --line:#2a3340;
    --txt:#e6edf3; --dim:#8b97a7; --up:#ff4d4f; --down:#26a69a;
    --gold:#ffd166; --accent:#4f8cff;
  }
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:var(--bg);color:var(--txt);font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;padding:18px;font-size:14px}
  h1{font-size:20px;font-weight:700;letter-spacing:1px}
  .topbar{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;margin-bottom:16px;
    border-bottom:1px solid var(--line);padding-bottom:14px}
  .topbar .meta{color:var(--dim);font-size:12px;display:flex;gap:18px;align-items:center;flex-wrap:wrap}
  .dot{width:8px;height:8px;border-radius:50%;background:var(--down);display:inline-block;box-shadow:0 0 8px var(--down);animation:pulse 1.6s infinite}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
  .grid{display:grid;gap:14px}
  .kpis{grid-template-columns:repeat(4,1fr)}
  @media(max-width:820px){.kpis{grid-template-columns:repeat(2,1fr)}}
  .card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px}
  .kpi .label{color:var(--dim);font-size:12px;margin-bottom:6px}
  .kpi .val{font-size:30px;font-weight:800}
  .kpi .sub{color:var(--dim);font-size:11px;margin-top:4px}
  .kpi.gold .val{color:var(--gold)} .kpi.accent .val{color:var(--accent)}
  .row2{grid-template-columns:1.1fr 1fr;align-items:start}
  @media(max-width:820px){.row2{grid-template-columns:1fr}}
  .card h2{font-size:15px;margin-bottom:12px;display:flex;align-items:center;gap:8px}
  .card h2 .tag{font-size:11px;background:var(--panel2);color:var(--dim);padding:2px 8px;border-radius:20px;font-weight:400}
  canvas{display:block;margin:0 auto}
  .chart-wrap{display:flex;justify-content:center;padding:6px 0}
  .legend{display:flex;flex-wrap:wrap;gap:8px 14px;justify-content:center;margin-top:10px;font-size:12px;color:var(--dim)}
  .legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px;vertical-align:middle}
  .stock-card{border:1px solid var(--line);border-radius:10px;padding:12px;margin-bottom:10px;background:var(--panel2)}
  .stock-card.top{border-color:var(--gold)}
  .stock-card .nm{font-size:16px;font-weight:700}
  .stock-card .cd{color:var(--dim);font-size:12px;margin-left:6px}
  .badges{margin:8px 0;display:flex;gap:6px;flex-wrap:wrap}
  .badge{font-size:11px;padding:2px 8px;border-radius:6px;background:#22304a;color:#9cc2ff}
  .badge.min{background:#3a2a44;color:#d3a6ff}
  .badge.ths{background:#1f3a30;color:#7fe3c4}
  .badge.sec{background:#2a2a2a;color:var(--dim)}
  .stock-card .logic{color:var(--dim);font-size:12px;line-height:1.6;margin-top:6px}
  .stock-card .score{float:right;font-size:20px;font-weight:800;color:var(--gold)}
  details{border:1px solid var(--line);border-radius:8px;padding:8px 12px;margin-bottom:8px;background:var(--panel2)}
  summary{cursor:pointer;font-weight:600;color:var(--accent)}
  details .cnt{color:var(--dim);font-weight:400;font-size:12px;margin-left:6px}
  .pill{display:inline-block;background:#22304a;color:#9cc2ff;font-size:11px;padding:1px 7px;border-radius:5px;margin:2px 3px}
  .tools{display:flex;gap:10px;flex-wrap:wrap;margin:6px 0 12px}
  .tools input,.tools button{background:var(--panel2);border:1px solid var(--line);color:var(--txt);
    padding:7px 12px;border-radius:8px;font-size:13px}
  .tools input{flex:1;min-width:160px}
  .tools button{cursor:pointer}
  .tools button:hover{border-color:var(--accent)}
  table{width:100%;border-collapse:collapse;font-size:13px}
  th,td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--line)}
  th{color:var(--dim);font-weight:600;position:sticky;top:0;background:var(--panel)}
  tbody tr:hover{background:var(--panel2)}
  .mini-badge{font-size:10px;padding:1px 5px;border-radius:4px;margin-right:3px}
  .secbar-row{display:flex;align-items:center;gap:10px;margin:7px 0;font-size:12px}
  .secbar-name{width:84px;color:var(--txt);text-align:right;flex:none}
  .secbar-track{flex:1;background:var(--panel2);border-radius:6px;height:16px;overflow:hidden}
  .secbar-fill{height:100%;border-radius:6px}
  .secbar-val{width:30px;text-align:right;color:var(--dim);flex:none}
  .err{color:var(--up);padding:20px}
  .foot{color:var(--dim);font-size:11px;margin-top:18px;text-align:center;line-height:1.7}
</style>
</head>
<body>
  <div class="topbar">
    <div>
      <h1>📊 斯东克 · 股票实时报告看板</h1>
      <div class="meta" style="margin-top:6px">
        <span><span class="dot"></span> 实时刷新中</span>
        <span>数据快照：<b id="snap">--</b></span>
        <span>配置文件更新：<b id="mtime">--</b></span>
        <span>下次刷新：<b id="cd">30</b>s</span>
      </div>
    </div>
    <div class="meta">
      <span id="clock">--:--:--</span>
    </div>
  </div>

  <div class="grid kpis" id="kpis"></div>

  <div class="grid row2" style="margin-top:14px">
    <div class="card">
      <h2>标签共振度分布 <span class="tag">三标签 / 两两 / 单标签</span></h2>
      <div class="chart-wrap"><canvas id="cvRes" width="300" height="300"></canvas></div>
      <div class="legend" id="resLegend"></div>
    </div>
    <div class="card">
      <h2>板块热度 Top <span class="tag">覆盖度加权</span></h2>
      <div id="sectorBars"></div>
    </div>
  </div>

  <div class="grid row2" style="margin-top:14px">
    <div class="card">
      <h2>🔥 三标签共振 · 核心推荐 <span class="tag" id="tripleCnt">0 只</span></h2>
      <div id="tripleList"></div>
    </div>
    <div class="card">
      <h2>两两共振分组</h2>
      <details open><summary>龙头股 ∩ 同花顺<span class="cnt" id="c_lt_ths"></span></summary><div id="g_lt_ths"></div></details>
      <details><summary>龙头股 ∩ 15Min<span class="cnt" id="c_lt_min"></span></summary><div id="g_lt_min"></div></details>
      <details><summary>15Min ∩ 同花顺<span class="cnt" id="c_min_ths"></span></summary><div id="g_min_ths"></div></details>
    </div>
  </div>

  <div class="card" style="margin-top:14px">
    <h2>全部持仓股票 <span class="tag" id="allCnt"></span></h2>
    <div class="tools">
      <input id="search" placeholder="搜索股票名称 / 代码…">
      <button data-f="all" class="fbtn">全部</button>
      <button data-f="triple" class="fbtn">三标签</button>
      <button data-f="long" class="fbtn">龙头股</button>
      <button data-f="min" class="fbtn">15Min</button>
      <button data-f="ths" class="fbtn">同花顺</button>
    </div>
    <div style="max-height:420px;overflow:auto">
      <table><thead><tr><th>名称</th><th>代码</th><th>板块</th><th>标签</th><th>覆盖</th><th>评分</th></tr></thead>
      <tbody id="allBody"></tbody></table>
    </div>
  </div>

  <div class="foot">
    数据来源：StockYiDong 桌面程序实时写入的持仓配置（src/config/ai_config.json） · 所有指标由标签实时计算<br>
    板块分类为本地静态常识映射，仅供分布参考，非实时行情；综合评分 = 覆盖度基线 + 标签加成（纯数据驱动，不编造）
  </div>

<script>
const COLORS=["#4f8cff","#00d4a0","#ffb020","#ff7ab6","#2dd4bf","#ff6b6b","#ffd166","#9b8cff","#f4a261","#8d99ae","#06d6a0","#ef476f"];
let DATA=null, filter="all", timer=30;

function donut(canvas, segs){
  const ctx=canvas.getContext('2d'); const cx=150,cy=150,R=110,r=62;
  ctx.clearRect(0,0,300,300);
  let tot=segs.reduce((a,s)=>a+s.v,0)||1; let ang=-Math.PI/2;
  segs.forEach(s=>{const a2=ang+s.v/tot*Math.PI*2;
    ctx.beginPath();ctx.moveTo(cx,cy);ctx.arc(cx,cy,R,ang,a2);ctx.closePath();
    ctx.fillStyle=s.c;ctx.fill();ang=a2;});
  ctx.beginPath();ctx.arc(cx,cy,r,0,Math.PI*2);ctx.fillStyle='#161b22';ctx.fill();
  ctx.fillStyle='#e6edf3';ctx.font='bold 30px sans-serif';ctx.textAlign='center';ctx.textBaseline='middle';
  ctx.fillText(tot,cx,cy-8);ctx.fillStyle='#8b97a7';ctx.font='12px sans-serif';ctx.fillText('股票数',cx,cy+16);
}

function render(){
  if(!DATA||DATA.error){document.body.insertAdjacentHTML('afterbegin','<div class="err">⚠️ '+DATA.error+'</div>');return;}
  document.getElementById('snap').textContent=DATA.snapshot_time;
  document.getElementById('mtime').textContent=DATA.config_mtime;
  const c=DATA.counts;
  // KPI
  document.getElementById('kpis').innerHTML=`
    <div class="card kpi accent"><div class="label">龙头股</div><div class="val">${c['龙头股']}</div><div class="sub">中线机构持仓</div></div>
    <div class="card kpi"><div class="label">15Min 异动</div><div class="val">${c['15Min']}</div><div class="sub">短线资金信号</div></div>
    <div class="card kpi"><div class="label">同花顺热度</div><div class="val">${c['同花顺']}</div><div class="sub">平台人气标签</div></div>
    <div class="card kpi gold"><div class="label">三标签共振</div><div class="val">${DATA.resonance.triple.length}</div><div class="sub">最高优先级</div></div>`;
  // 共振度
  const cov=DATA.coverage;
  const segs=[{v:cov[3],c:'#ffd166',n:'三标签'},{v:cov[2],c:'#4f8cff',n:'两标签'},{v:cov[1],c:'#8d99ae',n:'单标签'}];
  donut(document.getElementById('cvRes'),segs);
  document.getElementById('resLegend').innerHTML=segs.map(s=>`<span><i style="background:${s.c}"></i>${s.n} ${s.v}</span>`).join('');
  // 板块热度
  const top=DATA.sector_heat.slice(0,10);
  const mx=top.length?top[0].heat:1;
  document.getElementById('sectorBars').innerHTML=top.map(s=>
    `<div class="secbar-row"><div class="secbar-name">${s.sector}</div>
     <div class="secbar-track"><div class="secbar-fill" style="width:${s.heat/mx*100}%;background:${s.color}"></div></div>
     <div class="secbar-val">${s.heat}</div></div>`).join('');
  // 三标签共振
  document.getElementById('tripleCnt').textContent=DATA.resonance.triple.length+' 只';
  document.getElementById('tripleList').innerHTML=DATA.resonance.triple.map(s=>stockCard(s,true)).join('')||'<div class="dim">无</div>';
  // 两两
  fillGroup('g_lt_ths','c_lt_ths',DATA.resonance.lt_ths);
  fillGroup('g_lt_min','c_lt_min',DATA.resonance.lt_min);
  fillGroup('g_min_ths','c_min_ths',DATA.resonance.min_ths);
  // 全部
  renderAll();
}

function stockCard(s,top){
  const tb=s.tags.map(t=>{const cls=t==='15Min'?'min':(t==='同花顺'?'ths':'');return `<span class="badge ${cls}">${t}</span>`;}).join('');
  const logic=`同时覆盖 ${s.tags.join(' / ')} 共 ${s.coverage} 个标签${s.coverage===3?'（共振度最高）':''}，所属板块：${s.sector}。综合评分 ${s.score}。`;
  return `<div class="stock-card ${top?'top':''}">
    <span class="score">${s.score}</span>
    <div><span class="nm">${s.name}</span><span class="cd">${s.code}</span></div>
    <div class="badges">${tb}<span class="badge sec">${s.sector}</span></div>
    <div class="logic">${logic}</div></div>`;
}

function fillGroup(elId,cntId,arr){
  document.getElementById(cntId).textContent='（'+arr.length+' 只）';
  document.getElementById(elId).innerHTML=arr.map(s=>`<span class="pill" title="${s.sector}">${s.name}</span>`).join('')||'<span class="dim">无</span>';
}

function renderAll(){
  const q=(document.getElementById('search').value||'').trim();
  let rows=DATA.all_stocks;
  if(filter==='triple')rows=rows.filter(s=>s.coverage===3);
  else if(filter==='long')rows=rows.filter(s=>s.tags.includes('龙头股'));
  else if(filter==='min')rows=rows.filter(s=>s.tags.includes('15Min'));
  else if(filter==='ths')rows=rows.filter(s=>s.tags.includes('同花顺'));
  if(q)rows=rows.filter(s=>s.name.includes(q)||s.code.includes(q));
  document.getElementById('allCnt').textContent='共 '+rows.length+' 只';
  document.getElementById('allBody').innerHTML=rows.map(s=>{
    const tb=s.tags.map(t=>{const cls=t==='15Min'?'mini-badge" style="background:#3a2a44;color:#d3a6ff':(t==='同花顺'?'mini-badge" style="background:#1f3a30;color:#7fe3c4':'mini-badge" style="background:#22304a;color:#9cc2ff');return `<span class="${cls}">${t}</span>`;}).join('');
    return `<tr><td>${s.name}</td><td>${s.code}</td><td>${s.sector}</td><td>${tb}</td><td>${s.coverage}</td><td>${s.score}</td></tr>`;
  }).join('');
}

async function load(){
  try{const r=await fetch('/api/dashboard');DATA=await r.json();render();timer=30;}
  catch(e){console.error(e);}
}

document.getElementById('search').addEventListener('input',renderAll);
document.querySelectorAll('.fbtn').forEach(b=>b.addEventListener('click',()=>{filter=b.dataset.f;renderAll();}));

// 时钟
setInterval(()=>{const d=new Date();document.getElementById('clock').textContent=d.toLocaleTimeString('zh-CN',{hour12:false});},1000);
// 自动刷新倒计时
setInterval(()=>{timer--;if(timer<=0){load();}else{document.getElementById('cd').textContent=timer;}},1000);

load();
</script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body: bytes, ctype: str = "application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        p = urlparse(self.path).path
        if p in ("/", "/index.html"):
            self._send(200, HTML.encode("utf-8"), "text/html; charset=utf-8")
        elif p == "/api/dashboard":
            data = build_dashboard()
            self._send(200, json.dumps(data, ensure_ascii=False).encode("utf-8"))
        elif p == "/api/refresh":
            # 重新导出 txt（无害，仅写文件），并重新读取
            try:
                import subprocess
                subprocess.run(["python3", EXPORT_SCRIPT, "--out", os.path.join(BASE_DIR, "src")],
                               capture_output=True, timeout=60)
                ok = True
            except Exception:
                ok = False
            self._send(200, json.dumps({"ok": ok}, ensure_ascii=False).encode("utf-8"))
        else:
            self._send(404, b"not found", "text/plain; charset=utf-8")

    def log_message(self, *a):
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8777)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    # 启动前先算一次，校验数据可用
    test = build_dashboard()
    if test.get("error"):
        print(f"[警告] 读取配置异常: {test['error']}")
    else:
        c = test["counts"]
        print(f"[OK] 数据快照 {test['snapshot_time']} | 龙头股 {c['龙头股']} / 15Min {c['15Min']} / 同花顺 {c['同花顺']} | 三标签共振 {len(test['resonance']['triple'])} 只")

    srv = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    url = f"http://127.0.0.1:{args.port}/"
    print(f"[启动] 实时看板服务：{url}")
    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n[停止] 看板服务已关闭")
        srv.shutdown()


if __name__ == "__main__":
    main()
