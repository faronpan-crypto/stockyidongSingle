# -*- coding: utf-8 -*-
"""💰 跨平台比价 — MVP 版

数据源优先级:
  L1 万邦 OneBound (t1j.item_search_bijia) — 真正跨平台统一比价 API, 覆盖淘宝/天猫/京东/拼多多/唯品会/当当/苏宁
     注册 https://open.onebound.cn/ 免费拿 key+secret, 新用户送调用额度
  L2 TMAPI (api.tmapi.top) — 淘宝/天猫/京东/拼多多 聚合, 有历史价接口, REST + apikey
  L3 淘宝 TOP 官方 taobao.items.search / taobao.item.get — 需企业资质, 合规首选
  L4 京东联盟 jd.union.open.goods.detail.query — 实名认证即可, 券后价/佣金/月销量都能拿
  L5 本站直抓 HTML — 所有平台都有反爬/风控, 全挂时兜底用, 拿不到数据时弹窗提示用户直接点 🌐 官网跳转按钮

⚠️ 盒马/叮咚/奥乐齐/联华 无任何公开接口, 只能抓包 (需 cookie+x-sign), 合规灰区。
   本期先跳过, 用万邦 OneBound 跨平台比价接口覆盖淘宝/京东/拼多多主流电商。

API Key 管理:
  在 ~/.qclaw/price_compare_config.json 里存 key+secret, 格式:
    {"onebound_key": "xxx", "onebound_secret": "xxx", "tmapi_key": "xxx"}
"""
from __future__ import annotations
import ssl as _ssl
import re as _re
import json as _json
import os as _os
import urllib.parse as _up
from urllib.request import Request, urlopen
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional
from html import unescape as _hunesc

# ========== API Key 管理 ==========
def _load_api_keys() -> Dict[str, str]:
    """从本地 JSON 读取聚合 API key, 优先用户显式配置, 兜底环境变量"""
    _home = _os.path.expanduser("~")
    _cfg_path = _os.path.join(_home, ".qclaw", "price_compare_config.json")
    keys: Dict[str, str] = {}
    if _os.path.exists(_cfg_path):
        try:
            d = _json.load(open(_cfg_path))
            keys.update({k: v for k, v in d.items() if v})
        except Exception:
            pass
    # 环境变量兜底
    for en, k in [("ONEBOUND_KEY", "onebound_key"),
                   ("ONEBOUND_SECRET", "onebound_secret"),
                   ("TMAPI_KEY", "tmapi_key")]:
        if _os.environ.get(en):
            keys[k] = _os.environ[en]
    return keys

def _save_api_key(name: str, val: str):
    """写入 ~/.qclaw/price_compare_config.json"""
    _home = _os.path.expanduser("~")
    _cfg_dir = _os.path.join(_home, ".qclaw")
    _cfg_path = _os.path.join(_cfg_dir, "price_compare_config.json")
    _os.makedirs(_cfg_dir, exist_ok=True)
    existing = {}
    if _os.path.exists(_cfg_path):
        try: existing = _json.load(open(_cfg_path))
        except Exception: pass
    existing[name] = val
    _json.dump(existing, open(_cfg_path, "w"), ensure_ascii=False, indent=2)

_CTX = _ssl._create_unverified_context()
_HDR = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
_TIMEOUT = 12


def _get(url: str, extra_headers: Optional[Dict] = None) -> str:
    hdrs = dict(_HDR)
    if extra_headers:
        hdrs.update(extra_headers)
    req = Request(url, headers=hdrs)
    with urlopen(req, timeout=_TIMEOUT, context=_CTX) as resp:
        raw = resp.read()
        # 淘宝/京东/拼多多 用 gzip
        try:
            import gzip
            raw2 = gzip.decompress(raw)
            return raw2.decode("utf-8", errors="ignore")
        except Exception:
            try:
                return raw.decode("utf-8", errors="ignore")
            except Exception:
                return raw.decode("gbk", errors="ignore")


# ========== L1 万邦 OneBound 跨平台比价 ==========
def _fetch_onebound(keyword: str) -> List[Dict]:
    """t1j.item_search_bijia — 真正跨平台统一比价, 返回的 items[].name 是平台名"""
    out: List[Dict] = []
    keys = _load_api_keys()
    k, s = keys.get("onebound_key", ""), keys.get("onebound_secret", "")
    if not k or not s:
        print("[OneBound] 未配置 onebound_key / onebound_secret, 跳过")
        return out
    try:
        url = (f"https://api-gw.onebound.cn/t1j/item_search_bijia/"
               f"?key={k}&secret={s}&q={_up.quote(keyword)}&mode=")
        r = _get(url)
        try:
            data = _json.loads(r)
        except Exception:
            print(f"[OneBound] JSON 解析失败: {r[:200]}"); return out
        # 错误码处理: 4005 = key/secret错 或 接口未开通
        if data.get("success") == 0 or data.get("error_code"):
            _ec = data.get("error_code", "")
            _em = data.get("error", "") or data.get("reason", "")
            print(f"[OneBound] ❌ {_em[:120]} (code={_ec})")
            # 关键错误码: 4005 接口未开通 / key错; 4010 无数据; 4003 额度用完
            if _ec in ("4005", 4005) and "无权访问" in _em:
                print("[OneBound] ⚠️ key 已验证, 但 t1j 跨平台比价接口未开通 —")
                print("    请登 https://open.onebound.cn/ 控制台 → 接口管理 → 开通 t1j.item_search_bijia")
                print("    或联系 QQ 3142401606 / 微信 onebound1997 开通")
            # 不 raise, 返回空让 UI 继续走兜底
            return out
        items = []
        if "items" in data and isinstance(data["items"], dict):
            items = data["items"].get("item", []) or []
        for it in items[:30]:
            try:
                pname = it.get("name", "OneBound")
                nm = it.get("title", "") or it.get("name", "")
                pr = it.get("price", 0)
                img = it.get("pic_url", "") or it.get("pic", "")
                href = it.get("detail_url", "")
                if nm and pr:
                    out.append({
                        "platform": pname,
                        "name": str(nm).strip(),
                        "price": float(pr),
                        "price_str": f"¥{float(pr):.2f}",
                        "image": img,
                        "url": href,
                    })
            except Exception:
                continue
        print(f"[OneBound] ✅ 返回 {len(out)} 条跨平台比价数据")
    except Exception as e:
        print(f"[OneBound FAIL] {e}")
    return out


# ========== L2 TMAPI 聚合 ==========
def _fetch_tmapi(keyword: str) -> List[Dict]:
    """api.tmapi.top — 需要 apikey, 支持 taobao / jd / pdd 单独搜索"""
    out: List[Dict] = []
    keys = _load_api_keys()
    ak = keys.get("tmapi_key", "")
    if not ak:
        print("[TMAPI] 未配置 tmapi_key, 跳过")
        return out
    for pname, api in [("淘宝/天猫", "taobao.item_search"),
                       ("京东", "jd.item_search"),
                       ("拼多多", "pdd.item_search")]:
        try:
            url = (f"https://api.tmapi.top/{api}"
                   f"?apikey={ak}&q={_up.quote(keyword)}&sort=price-asc")
            r = _get(url)
            try:
                data = _json.loads(r)
            except Exception:
                continue
            items = data.get("items") or data.get("result") or []
            if isinstance(items, dict): items = items.get("item", []) or []
            for it in items[:10]:
                try:
                    nm = it.get("title") or it.get("name", "")
                    pr = it.get("price") or 0
                    img = it.get("pic_url") or it.get("img", "")
                    href = it.get("detail_url") or it.get("url", "")
                    if nm and pr:
                        out.append({
                            "platform": pname,
                            "name": str(nm).strip(),
                            "price": float(pr),
                            "price_str": f"¥{float(pr):.2f}",
                            "image": img,
                            "url": href,
                        })
                except Exception:
                    continue
        except Exception as e:
            print(f"[TMAPI {pname} FAIL] {e}")
    return out


# ========== 淘宝 ==========
def _fetch_taobao(kw: str) -> List[Dict]:
    out: List[Dict] = []
    try:
        url = f"https://s.taobao.com/search?q={_up.quote(kw)}&sort=price-asc&s=0"
        html = _get(url)
        # 淘宝 PC 版把搜索结果塞进 g_page_config JSON
        m = _re.search(r'g_page_config\s*=\s*(\{.*?\});', html, _re.DOTALL)
        if not m:
            # 新版: 从 window.__INITIAL_STATE__ 里扒
            m = _re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});\s*</script>', html, _re.DOTALL)
        items = []
        if m:
            try:
                data = _json.loads(m.group(1))
                # 可能多层嵌套
                def _walk(obj):
                    if isinstance(obj, dict):
                        if "itemList" in obj and isinstance(obj["itemList"], list):
                            items.extend(obj["itemList"])
                        for v in obj.values():
                            _walk(v)
                    elif isinstance(obj, list):
                        for v in obj:
                            _walk(v)
                _walk(data)
            except Exception:
                pass
        # 兜底: 正则抓 list-item
        if not items:
            for m2 in _re.finditer(r'<div[^>]+class="list-item"[^>]*>(.*?)</div>', html, _re.DOTALL):
                items.append(m2.group(1))
        for it in items[:20]:
            try:
                if isinstance(it, str):
                    txt = it
                else:
                    txt = _json.dumps(it, ensure_ascii=False)
                # 名字
                nm = ""
                if isinstance(it, dict):
                    nm = it.get("title", "") or it.get("raw_title", "")
                if not nm:
                    mm = _re.search(r'title="([^"]{4,80})"', txt)
                    if mm: nm = mm.group(1)
                # 价格
                pr = ""
                if isinstance(it, dict):
                    pr = it.get("view_price") or it.get("price") or ""
                if not pr:
                    mm = _re.search(r'view_price["\s:=]+["\']?([0-9]+\.?[0-9]*)', txt)
                    if mm: pr = mm.group(1)
                if not pr:
                    mm = _re.search(r'¥\s*([0-9]+\.?[0-9]*)', txt)
                    if mm: pr = mm.group(1)
                # 图片
                img = ""
                if isinstance(it, dict):
                    img = it.get("pic_url") or it.get("img") or ""
                if not img:
                    mm = _re.search(r'(?:pic_url|img|image)["\s:=]+["\']?(https?://[^"\']+\.(?:jpg|png|webp))', txt)
                    if mm: img = mm.group(1)
                # 链接
                href = ""
                if isinstance(it, dict):
                    href = it.get("detail_url") or ""
                    if href and not href.startswith("http"):
                        href = "https:" + href
                if not href:
                    mm = _re.search(r'(detail_url|item\.taobao\.com|detail\.tmall\.com)[^"\'< ]+', txt)
                    if mm:
                        raw = mm.group(0)
                        if raw.startswith("http"): href = raw
                        else: href = "https:" + raw
                if nm and pr:
                    out.append({
                        "platform": "淘宝/天猫",
                        "name": _hunesc(nm).strip(),
                        "price": float(pr) if _re.match(r'^[0-9.]+$', pr) else pr,
                        "price_str": f"¥{pr}",
                        "image": img or "",
                        "url": href or "",
                    })
            except Exception:
                continue
    except Exception as e:
        print(f"[淘宝抓取失败] {e}")
    return out


# ========== 京东 ==========
def _fetch_jd(kw: str) -> List[Dict]:
    out: List[Dict] = []
    try:
        url = f"https://search.jd.com/Search?keyword={_up.quote(kw)}&enc=utf-8&wq={_up.quote(kw)}"
        html = _get(url)
        # 京东 PC 版 <li class="gl-item">
        for m in _re.finditer(r'<li[^>]*class="gl-item"[^>]*>(.*?)</li>', html, _re.DOTALL):
            blk = m.group(1)
            try:
                # 名字
                tn = _re.search(r'<div[^>]+class="p-name"[^>]*>.*?<em>(.*?)</em>', blk, _re.DOTALL)
                if not tn: continue
                nm = _re.sub(r'<[^>]+>', '', tn.group(1)).strip()
                if not nm: continue
                # 价格
                tp = _re.search(r'<i>([0-9]+\.[0-9]+)</i>', blk)
                pr = tp.group(1) if tp else ""
                # 图片
                ti = _re.search(r'data-lazy-img="(https?://[^"]+)"', blk)
                if not ti:
                    ti = _re.search(r'<img[^>]+src="(https?://[^"]+)"', blk)
                img = ti.group(1) if ti else ""
                # 链接
                ta = _re.search(r'href="(https?://item\.jd\.com/[^"]+)"', blk)
                href = ta.group(1) if ta else ""
                if nm and pr:
                    out.append({
                        "platform": "京东",
                        "name": _hunesc(nm),
                        "price": float(pr) if _re.match(r'^[0-9.]+$', pr) else pr,
                        "price_str": f"¥{pr}",
                        "image": img,
                        "url": href,
                    })
            except Exception:
                continue
    except Exception as e:
        print(f"[京东抓取失败] {e}")
    return out


# ========== 拼多多 ==========
def _fetch_pdd(kw: str) -> List[Dict]:
    out: List[Dict] = []
    try:
        url = f"https://mobile.yangkeduo.com/search_result.html?search_key={_up.quote(kw)}"
        html = _get(url)
        # 拼多多小程序版把结果塞在 window.rawData
        m = _re.search(r'window\.rawData\s*=\s*(\{.*?\})\s*;\s*</script>', html, _re.DOTALL)
        if not m:
            m = _re.search(r'"goods_list"\s*:\s*(\[.*?\])\s*,\s*"', html, _re.DOTALL)
        if m:
            try:
                data = _json.loads(m.group(1))
                items = []
                if isinstance(data, dict):
                    def _walk(o):
                        if isinstance(o, dict):
                            for k, v in o.items():
                                if "list" in k.lower() and isinstance(v, list):
                                    items.extend(v)
                                _walk(v)
                        elif isinstance(o, list):
                            for v in o: _walk(v)
                    _walk(data)
                elif isinstance(data, list):
                    items = data
                for it in items[:20]:
                    try:
                        nm = it.get("goods_name", "") or it.get("title", "")
                        pr = it.get("price", 0) or 0
                        # 拼多多价格是分
                        pr_yuan = pr / 100 if isinstance(pr, (int, float)) and pr > 100 else pr
                        img = it.get("thumb_url") or it.get("image_url") or ""
                        goods_id = it.get("goods_id", "")
                        href = f"https://mobile.yangkeduo.com/goods.html?goods_id={goods_id}" if goods_id else ""
                        if nm and pr_yuan:
                            out.append({
                                "platform": "拼多多",
                                "name": nm,
                                "price": float(pr_yuan),
                                "price_str": f"¥{pr_yuan:.2f}",
                                "image": img,
                                "url": href,
                            })
                    except Exception:
                        continue
            except Exception:
                pass
    except Exception as e:
        print(f"[拼多多抓取失败] {e}")
    return out


# ========== 盒马 ==========
def _fetch_hema(kw: str) -> List[Dict]:
    out: List[Dict] = []
    try:
        # 盒马 PC 搜索接口 (官方的, 不过需要 cookie)
        url = (f"https://m.hemaos.com/x/pc/online/search?keyword={_up.quote(kw)}"
               f"&page=1&size=20&latitude=31.23&longitude=121.47")
        hdrs = dict(_HDR)
        hdrs["Referer"] = "https://m.hemaos.com/"
        html = _get(url, hdrs)
        try:
            data = _json.loads(html)
            items = (data.get("data", {}).get("item_list")
                     or data.get("result", [])
                     or data.get("data", []))
            for it in items[:20]:
                try:
                    nm = it.get("name", "") or it.get("title", "")
                    pr = (it.get("sale_price") or it.get("price")
                          or it.get("promotion_price") or "")
                    img = it.get("pic") or it.get("image") or it.get("pic_url") or ""
                    sid = it.get("sku_id") or it.get("item_id") or ""
                    href = f"https://m.hemaos.com/item/{sid}" if sid else ""
                    if nm and pr:
                        out.append({
                            "platform": "盒马",
                            "name": nm,
                            "price": float(pr) if _re.match(r'^[0-9.]+$', str(pr)) else pr,
                            "price_str": f"¥{pr}",
                            "image": img,
                            "url": href,
                        })
                except Exception:
                    continue
        except Exception:
            # 不是 JSON, 尝试 HTML
            for m in _re.finditer(r'<div[^>]+class="[^"]*item[^"]*"[^>]*>(.*?)</div>', html, _re.DOTALL):
                blk = m.group(1)
                try:
                    tn = _re.search(r'>([^<]{4,60})<', blk)
                    ti = _re.search(r'(?:data-src|src)="(https?://[^"]+)"', blk)
                    tp = _re.search(r'¥\s*([0-9]+\.?[0-9]*)', blk)
                    if tn and tp:
                        out.append({
                            "platform": "盒马",
                            "name": _hunesc(tn.group(1)).strip(),
                            "price": float(tp.group(1)),
                            "price_str": f"¥{tp.group(1)}",
                            "image": ti.group(1) if ti else "",
                            "url": "",
                        })
                except Exception:
                    continue
    except Exception as e:
        print(f"[盒马抓取失败] {e}")
    return out


# ========== 主入口 ==========
def fetch_all_platforms(keyword: str, platforms=None) -> Dict[str, List[Dict]]:
    """并行拉多平台, 返回 {platform_name: [item_dict, ...]}

    数据源优先级: L1 OneBound → L2 TMAPI → L5 HTML 直抓 (兜底)
    如果配置了聚合 API key, 优先走合规稳定的聚合接口, 直抓 HTML 只当兜底。
    """
    if platforms is None:
        platforms = ["淘宝/天猫", "京东", "拼多多", "抖音", "盒马", "唯品会", "奥乐齐", "联华"]

    _keys = _load_api_keys()
    has_onebound = bool(_keys.get("onebound_key") and _keys.get("onebound_secret"))
    has_tmapi = bool(_keys.get("tmapi_key"))

    results: Dict[str, List[Dict]] = {p: [] for p in platforms}

    # 有聚合 API → 直接用, 把跨平台结果映射回用户选的分组
    if has_onebound:
        print("[比价] 用 OneBound (L1 聚合 API)")
        ob_items = _fetch_onebound(keyword)
        # OneBound 返回 items[].name 就是平台名, 原样塞进去
        for it in ob_items:
            pname = it["platform"]
            if pname not in results:
                results[pname] = []
            results[pname].append(it)
    elif has_tmapi:
        print("[比价] 用 TMAPI (L2 聚合 API)")
        tm_items = _fetch_tmapi(keyword)
        for it in tm_items:
            pname = it["platform"]
            if pname not in results:
                results[pname] = []
            results[pname].append(it)
    else:
        # 兜底: HTML 直抓 (大概率被反爬)
        print("[比价] 无聚合 API key, 用 HTML 直抓兜底 (大概率反爬拦截)")
        _fns = {
            "淘宝/天猫": _fetch_taobao,
            "京东": _fetch_jd,
            "拼多多": _fetch_pdd,
            "盒马": _fetch_hema,
        }
        with ThreadPoolExecutor(max_workers=len(platforms)) as ex:
            futs = {ex.submit(_fns[p], keyword): p for p in platforms if p in _fns}
            for fut in as_completed(futs):
                p = futs[fut]
                try:
                    results[p] = fut.result()
                except Exception as e:
                    print(f"[{p} 异常] {e}")
                    results[p] = []
    return results


if __name__ == "__main__":
    import sys
    kw = sys.argv[1] if len(sys.argv) > 1 else "恰恰瓜子"
    print(f"\n🔍 搜索: {kw}")
    r = fetch_all_platforms(kw)
    for p, items in r.items():
        print(f"\n=== {p} ({len(items)} 条) ===")
        for it in items[:5]:
            print(f"  {it['price_str']:>8}  {it['name'][:30]}")


# ============================================================
# 🖥️ Tkinter 弹窗
# ============================================================
def show_price_compare_dialog(parent_win=None, call_ai_fn=None):
    """💰 比价弹窗 — 搜索词 → 多平台并行抓价 → Treeview 展示 + AI 兜底建议"""
    import tkinter as tk
    from tkinter import ttk, messagebox
    import threading
    import webbrowser

    win = tk.Toplevel(parent_win) if parent_win else tk.Tk()
    win.title("💰 跨平台比价")
    win.geometry("1200x860")
    win.minsize(960, 720)
    win.configure(bg="#F5F5F5")

    # ===== 顶栏 =====
    top = tk.Frame(win, bg="#1A237E"); top.pack(fill=tk.X)
    tk.Label(top, text="💰 跨平台比价", bg="#1A237E", fg="#FFD54F",
             font=("", 14, "bold")).pack(side=tk.LEFT, padx=14, pady=10)

    ctrl = tk.Frame(top, bg="#1A237E"); ctrl.pack(side=tk.LEFT, padx=10)
    tk.Label(ctrl, text="商品:", bg="#1A237E", fg="white", font=("", 10)).pack(side=tk.LEFT)
    kw_var = tk.StringVar(value="恰恰瓜子 150g")
    entry = tk.Entry(ctrl, textvariable=kw_var, width=32, font=("", 11))
    entry.pack(side=tk.LEFT, padx=4)
    entry.bind("<Return>", lambda _e: _do_search())

    platforms_chk = tk.Frame(top, bg="#1A237E"); platforms_chk.pack(side=tk.LEFT, padx=8)
    _platforms_list = ["淘宝/天猫", "京东", "拼多多", "抖音", "盒马", "唯品会", "奥乐齐", "联华"]
    _platform_vars = {p: tk.BooleanVar(value=True) for p in _platforms_list}
    for p, v in _platform_vars.items():
        tk.Checkbutton(platforms_chk, text=p, variable=v,
                       bg="#1A237E", fg="white", selectcolor="#1A237E",
                       activebackground="#1A237E", font=("", 9)).pack(side=tk.LEFT, padx=2)

    status_var = tk.StringVar(value="输入商品名 → 点搜索 (并行抓淘宝/京东/拼多多/盒马)")
    tk.Label(top, textvariable=status_var, bg="#1A237E", fg="#BDBDBD",
             font=("", 8)).pack(side=tk.RIGHT, padx=12)

    # ===== 按钮 =====
    btn_row = tk.Frame(win, bg="#F5F5F5"); btn_row.pack(fill=tk.X, pady=(6, 2))
    def _do_search():
        kw = kw_var.get().strip()
        if not kw:
            messagebox.showinfo("提示", "请输入商品名")
            return
        sel_p = [p for p in _platforms_list if _platform_vars[p].get()]
        if not sel_p:
            messagebox.showinfo("提示", "请至少选一个平台")
            return
        status_var.set(f"⏳ 并行搜索 {sel_p} ...")
        # 清空 Treeview
        for item in tv.get_children():
            tv.delete(item)
        summary_var.set("")

        def _bg_html():
            try:
                res = fetch_all_platforms(kw, platforms=sel_p)
                win.after(0, lambda: _render(res))
            except Exception as e:
                win.after(0, lambda: status_var.set(f"❌ 搜索失败: {e}"))

        # ⚡ 并行启动: HTML 搜索 + AI 购买建议 同时跑 (不用等反爬完)
        threading.Thread(target=_bg_html, daemon=True).start()
        threading.Thread(target=_fetch_ai_advice, args=(kw,), daemon=True).start()

    tk.Button(btn_row, text="🔍 搜索", command=_do_search, bg="#FFD54F", fg="#1A237E",
              font=("", 10, "bold"), relief=tk.FLAT, padx=14).pack(side=tk.LEFT, padx=10)
    tk.Button(btn_row, text="🤖 AI重跑", command=lambda: threading.Thread(
        target=_fetch_ai_advice, args=(kw_var.get().strip(),), daemon=True).start(),
              bg="#FF9800", fg="white", relief=tk.FLAT, padx=8, font=("", 9, "bold")
              ).pack(side=tk.LEFT, padx=2)

    def _open_api_settings():
        """弹窗让用户填 OneBound / TMAPI 的 key+secret"""
        dlg = tk.Toplevel(win); dlg.title("🔑 比价 API 设置")
        dlg.geometry("480x380"); dlg.configure(bg="#FAFAFA")
        tk.Label(dlg, text="🔑 聚合 API Key 设置 (有一个就能用)", bg="#FAFAFA",
                 fg="#1A237E", font=("", 11, "bold")).pack(pady=(10, 4))
        tk.Label(dlg, text="注册后把 key+secret 填进来, 比价就能返回真实价格",
                 bg="#FAFAFA", fg="#666", font=("", 8)).pack()

        keys_now = _load_api_keys()

        # OneBound 区
        f1 = tk.LabelFrame(dlg, text="万邦 OneBound (推荐, 跨平台统一比价)", bg="#FAFAFA", fg="#1A237E")
        f1.pack(fill=tk.X, padx=14, pady=(10, 4))
        tk.Label(f1, text="key:", bg="#FAFAFA").grid(row=0, column=0, sticky="e", padx=4, pady=2)
        e1k = tk.Entry(f1, width=40); e1k.grid(row=0, column=1, padx=4, pady=2)
        e1k.insert(0, keys_now.get("onebound_key", ""))
        tk.Label(f1, text="secret:", bg="#FAFAFA").grid(row=1, column=0, sticky="e", padx=4, pady=2)
        e1s = tk.Entry(f1, width=40, show="•"); e1s.grid(row=1, column=1, padx=4, pady=2)
        e1s.insert(0, keys_now.get("onebound_secret", ""))
        tk.Label(f1, text="注册: https://open.onebound.cn/", bg="#FAFAFA", fg="#1976D2",
                 cursor="hand2").grid(row=2, column=0, columnspan=2, sticky="w", padx=4, pady=(0, 4))

        # TMAPI 区
        f2 = tk.LabelFrame(dlg, text="TMAPI (备选, 单平台 APIKEY)", bg="#FAFAFA", fg="#1A237E")
        f2.pack(fill=tk.X, padx=14, pady=(4, 10))
        tk.Label(f2, text="apikey:", bg="#FAFAFA").grid(row=0, column=0, sticky="e", padx=4, pady=2)
        e2k = tk.Entry(f2, width=40); e2k.grid(row=0, column=1, padx=4, pady=2)
        e2k.insert(0, keys_now.get("tmapi_key", ""))
        tk.Label(f2, text="注册: https://api.tmapi.top/", bg="#FAFAFA", fg="#1976D2",
                 cursor="hand2").grid(row=1, column=0, columnspan=2, sticky="w", padx=4, pady=(0, 4))

        def _save():
            if e1k.get().strip(): _save_api_key("onebound_key", e1k.get().strip())
            if e1s.get().strip(): _save_api_key("onebound_secret", e1s.get().strip())
            if e2k.get().strip(): _save_api_key("tmapi_key", e2k.get().strip())
            dlg.destroy()
            messagebox.showinfo("保存成功", "API Key 已保存到 ~/.qclaw/price_compare_config.json\n下一次搜索自动生效")

        tk.Button(dlg, text="💾 保存并关闭", command=_save, bg="#1A237E", fg="white",
                  relief=tk.FLAT, padx=16, pady=6, font=("", 10, "bold")).pack(pady=(4, 8))
        tk.Button(dlg, text="取消", command=dlg.destroy, bg="#ECEFF1", fg="#333",
                  relief=tk.FLAT, padx=10).pack()

    api_btn_txt = "🔑 设置API" if _load_api_keys() else "🔑 填API Key (未配置)"
    tk.Button(btn_row, text=api_btn_txt, command=_open_api_settings,
              bg="#37474F", fg="white", relief=tk.FLAT, padx=8).pack(side=tk.LEFT, padx=4)

    _platform_btns = [
        ("🌐 淘宝", "#FF5722", "https://s.taobao.com/search?q="),
        ("🌐 京东", "#E53935", "https://search.jd.com/Search?keyword="),
        ("🌐 拼多多", "#E91E63", "https://mobile.yangkeduo.com/search_result.html?search_key="),
        ("🌐 抖音", "#000000", "https://www.douyin.com/search/"),
        ("🌐 盒马", "#4CAF50", "https://m.hemaos.com/search?keyword="),
        ("🌐 唯品会", "#FF9800", "https://search.vip.com/?q="),
        ("🌐 奥乐齐", "#3F51B5", "https://www.aldi.com.cn/search?q="),
        ("🌐 联华", "#FFC107", "https://www.lianhuashop.com/search?keyword="),
    ]
    for label, color, base_url in _platform_btns:
        tk.Button(btn_row, text=label,
                  command=lambda u=base_url: webbrowser.open(u + webbrowser.quote(kw_var.get().strip())),
                  bg=color, fg="white", relief=tk.FLAT, padx=8).pack(side=tk.LEFT, padx=3)

    # ===== 汇总栏 =====
    summary_var = tk.StringVar(value="")
    summ_f = tk.Frame(win, bg="#FFF9C4"); summ_f.pack(fill=tk.X, padx=10, pady=4)
    tk.Label(summ_f, textvariable=summary_var, bg="#FFF9C4", fg="#333",
             font=("", 10, "bold"), anchor="w").pack(fill=tk.X, padx=8, pady=4)

    # ====== 主布局: PanedWindow 嵌套 ======
    # 上 30%: Treeview + 下 70% (左右分: AI 建议 + matplotlib 图形化比价)
    try:
        pw_v = tk.PanedWindow(win, orient=tk.VERTICAL, bg="#F5F5F5",
                              sashwidth=6, sashrelief=tk.RAISED)
        pw_v.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 6))
        pw_h_parent = tk.Frame(pw_v, bg="#F5F5F5")
    except Exception:
        pw_v = None
        pw_h_parent = tk.Frame(win, bg="#F5F5F5")
        pw_h_parent.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 6))

    # --- 上: Treeview + summary ---
    top_container = tk.Frame(pw_v or pw_h_parent, bg="#FAFAFA")
    cols = ("平台", "商品", "价格", "最低价", "链接")
    tv = ttk.Treeview(top_container, columns=cols, show="headings", height=10)
    for c, w in [("平台", 90), ("商品", 420), ("价格", 100), ("最低价", 80), ("链接", 300)]:
        tv.heading(c, text=c); tv.column(c, width=w, anchor="w")
    sb = ttk.Scrollbar(top_container, orient=tk.VERTICAL, command=tv.yview)
    tv.configure(yscrollcommand=sb.set)
    tv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True); sb.pack(side=tk.RIGHT, fill=tk.Y)
    tv.tag_configure("min", background="#C8E6C9")
    tv.tag_configure("max", background="#FFCDD2")

    # --- 下 70%: 水平分 AI / 图形 ---
    try:
        pw_h = tk.PanedWindow(pw_h_parent, orient=tk.HORIZONTAL, bg="#F5F5F5",
                              sashwidth=6, sashrelief=tk.RAISED)
        pw_h.pack(fill=tk.BOTH, expand=True)
    except Exception:
        pw_h = None

    ai_container = tk.Frame(pw_h or pw_h_parent, bg="#F5F5F5")
    chart_container = tk.Frame(pw_h or pw_h_parent, bg="#F5F5F5")

    if pw_v:
        pw_v.add(top_container, minsize=120)
        pw_v.add(pw_h_parent, minsize=200)
    else:
        top_container.pack(fill=tk.BOTH, expand=False, pady=(0, 4))

    if pw_h:
        pw_h.add(ai_container, minsize=300)
        pw_h.add(chart_container, minsize=300)
    else:
        ai_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 3))
        chart_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(3, 0))

    # ===== 左: AI 建议区 =====
    ai_f = tk.LabelFrame(ai_container, text="🤖 AI 智能购买建议",
                         bg="#FFF3E0", fg="#E65100", font=("", 10, "bold"))
    ai_f.pack(fill=tk.BOTH, expand=True, pady=2)
    # 字号调节
    ai_bar = tk.Frame(ai_f, bg="#FFF3E0")
    ai_bar.pack(fill=tk.X, padx=6, pady=(4, 0))
    tk.Label(ai_bar, text="🔤 字体:", bg="#FFF3E0", fg="#5D4037").pack(side=tk.LEFT)
    _ai_fsize_var = tk.IntVar(value=14)
    def _ai_fsize_apply():
        try:
            ai_text.configure(font=("", int(_ai_fsize_var.get())))
        except Exception:
            pass
    for delta, sym in [(-2, "A-"), (-1, "a-"), (1, "A+"), (2, "A++")]:
        tk.Button(ai_bar, text=sym, width=3, command=lambda d=delta: (
            _ai_fsize_var.set(max(10, min(22, int(_ai_fsize_var.get()) + d))), _ai_fsize_apply()),
                  bg="#FFE0B2", fg="#5D4037", relief=tk.FLAT).pack(side=tk.LEFT, padx=1)
    _fsize_spin = tk.Spinbox(ai_bar, from_=10, to=22, width=3, textvariable=_ai_fsize_var,
                             command=_ai_fsize_apply, bg="#FFFBF2")
    _fsize_spin.pack(side=tk.LEFT, padx=2)

    # Text with url + platform bold tag
    ai_text = tk.Text(ai_f, bg="#FFFBF2", fg="#333",
                      font=("", 14), wrap=tk.WORD, relief=tk.FLAT, padx=10, pady=8,
                      state=tk.DISABLED, cursor="hand2")
    ai_text.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
    ai_text.tag_configure("url", foreground="#1976D2", font=("", 14, "underline"))
    ai_text.tag_configure("platform", foreground="#C62828", font=("", 14, "bold"))
    ai_text.tag_configure("header", foreground="#4527A0", font=("", 15, "bold"))
    ai_text.tag_configure("bold", foreground="#333", font=("", 14, "bold"))

    def _show_ai(text: str):
        """把 AI 返回写到 Text 区 — 智能识别加粗/链接/标题"""
        import re as _re_ai
        ai_text.configure(state=tk.NORMAL)
        ai_text.delete("1.0", tk.END)
        t = (text or "(AI 没返回内容)").strip()
        # 逐行解析
        for line in t.split("\n"):
            line = line.rstrip()
            # 判断行级样式
            _hdr_match = _re_ai.match(r"^【(.+?)】", line)
            _lvl = "header" if _hdr_match else None
            _lvl = _lvl or ("bold" if line.startswith(("今天最划算", "✅", "❌", "💰", "🎯")) else None)
            # 拆 URL 加粗
            parts = _re_ai.split(r"(https?://\S+)", line)
            _url_kw = ("淘宝", "天猫", "京东", "拼多多", "抖音", "盒马", "奥乐齐", "联华", "叮咚", "唯品会", "当当", "苏宁", "美团")
            for seg in parts:
                if not seg: continue
                if _re_ai.match(r"^https?://", seg):
                    ai_text.insert(tk.END, seg, "url")
                elif any(seg.strip().startswith(k) for k in _url_kw):
                    ai_text.insert(tk.END, seg, "platform")
                elif _lvl:
                    ai_text.insert(tk.END, seg, _lvl)
                else:
                    ai_text.insert(tk.END, seg)
            ai_text.insert(tk.END, "\n")
        ai_text.configure(state=tk.DISABLED)
        _ai_fsize_apply()

    # ===== 右: matplotlib 图形化比价 =====
    try:
        import matplotlib
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
        from matplotlib.figure import Figure
        matplotlib.use("TkAgg")
        import matplotlib.pyplot as plt
        plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "PingFang SC", "Heiti SC", "SimHei"]
        plt.rcParams["axes.unicode_minus"] = False
        _MPL_OK = True
    except Exception:
        _MPL_OK = False

    chart_f = tk.LabelFrame(chart_container, text="📊 图形化比价分析",
                            bg="#E8F5E9", fg="#2E7D32", font=("", 10, "bold"))
    chart_f.pack(fill=tk.BOTH, expand=True, pady=2)

    fig = None; canvas = None
    _chart_placeholder = tk.Label(chart_f, text="⏳ 搜索完成后自动生成图形化比价...\n\n(价位对比条 / 差价对比 / 省钱雷达 / 最佳购买渠道)",
                                   bg="#E8F5E9", fg="#666", font=("", 10))
    _chart_placeholder.pack(fill=tk.BOTH, expand=True, pady=20)

    def _render_chart(data_from_tree: Dict[str, List[Dict]]):
        """把 Treeview 真实数据 / AI 价位 hint / 兜底价位 → matplotlib 4 小图"""
        nonlocal fig, canvas
        if not _MPL_OK: return
        try:
            _chart_placeholder.pack_forget()
        except Exception: pass
        # 收集真实价格 (Treeview 抓到的)
        real_prices: Dict[str, List[float]] = {}
        for p, items in data_from_tree.items():
            for it in items:
                try:
                    pv = float(it.get("price") or 0)
                    if pv > 0: real_prices.setdefault(p, []).append(pv)
                except Exception: pass

        # AI 兜底价位 (硬编码, 当 AI hint 和 real 都没有时用)
        _ai_fallback = {
            "淘宝/天猫": (8, 14), "京东": (8, 15), "拼多多": (5, 10),
            "抖音": (6, 13), "盒马": (10, 18), "唯品会": (7, 16),
            "奥乐齐": (4, 9), "联华": (5, 10), "叮咚": (7, 14),
        }
        # 优先级: real_prices > AI hint > hard fallback
        _effective_ranges: Dict[str, tuple] = {}
        for p in list(_ai_fallback.keys()) + list(_current_ai_hint.keys()):
            if p in real_prices and real_prices[p]:
                _effective_ranges[p] = (min(real_prices[p]), max(real_prices[p]))
            elif p in _current_ai_hint:
                _effective_ranges[p] = _current_ai_hint[p]
            elif p in _ai_fallback:
                _effective_ranges[p] = _ai_fallback[p]

        _all_platforms = ["淘宝/天猫", "京东", "拼多多", "抖音", "盒马", "唯品会", "奥乐齐", "联华"]
        platforms_used = [p for p in _all_platforms if p in _effective_ranges] or list(_effective_ranges.keys())
        if not platforms_used: platforms_used = list(_ai_fallback.keys())[:4]

        fig = Figure(figsize=(6.5, 5.5), dpi=92, facecolor="#E8F5E9")
        ax1 = fig.add_subplot(2, 2, 1)   # 横向价位条形 (真实最低价)
        ax2 = fig.add_subplot(2, 2, 2)   # 差价对比 (条形)
        ax3 = fig.add_subplot(2, 2, 3)   # 雷达图
        ax4 = fig.add_subplot(2, 2, 4)   # 省钱大字 + emoji
        fig.subplots_adjust(left=0.08, right=0.98, top=0.92, bottom=0.05, wspace=0.35, hspace=0.45)

        _colors = {"淘宝/天猫": "#FF5722", "京东": "#E53935", "拼多多": "#E91E63",
                   "抖音": "#000000", "盒马": "#4CAF50", "唯品会": "#FF9800",
                   "奥乐齐": "#3F51B5", "联华": "#FFC107", "叮咚": "#00BCD4"}

        # --- 图1: 各平台最低价横向条形 ---
        names_bar = []; mins_bar = []; maxs_bar = []; bars_col = []
        for p in platforms_used:
            lo, hi = _effective_ranges.get(p, (5, 12))
            names_bar.append(p); mins_bar.append(lo); maxs_bar.append(hi)
            bars_col.append(_colors.get(p, "#78909C"))
        y_pos = range(len(names_bar))
        ax1.barh(list(y_pos), maxs_bar, color=bars_col, alpha=0.4, label="最高价")
        ax1.barh(list(y_pos), mins_bar, color=bars_col, alpha=0.9, label="最低价")
        for i, (mn, mx) in enumerate(zip(mins_bar, maxs_bar)):
            ax1.text(mn, i, f" ¥{mn:.1f}", va="center", fontsize=9, fontweight="bold")
        ax1.set_yticks(list(y_pos)); ax1.set_yticklabels(names_bar, fontsize=9)
        ax1.set_title("📉 各平台价位对比", fontsize=10, fontweight="bold")
        ax1.set_xlabel("价格 (元)", fontsize=8); ax1.grid(axis="x", alpha=0.3)

        # --- 图2: 差价对比 (与最低价的差距) ---
        if mins_bar:
            global_min = min(mins_bar)
            diffs = [m - global_min for m in mins_bar]
            bars2 = ax2.bar(names_bar, diffs, color=bars_col)
            for i, d in enumerate(diffs):
                ax2.text(i, d + 0.1, f"+¥{d:.1f}" if d > 0 else "最低",
                         ha="center", fontsize=9, fontweight="bold",
                         color="#2E7D32" if d == 0 else "#C62828")
            ax2.axhline(0, color="#999", linewidth=0.5)
            ax2.set_title("💰 差价对比 (vs 最低价)", fontsize=10, fontweight="bold")
            ax2.set_ylabel("额外花 (元)", fontsize=8); ax2.grid(axis="y", alpha=0.3)
            ax2.tick_params(axis="x", rotation=30, labelsize=8)

        # --- 图3: 雷达图 (平台性价比 6 维) ---
        _radar_labels = ["价格", "品质", "物流", "品控", "售后", "覆盖"]
        _radar_preset = {  # 预设各平台各维度 0-10 (价格/品质/物流/品控/售后/覆盖)
            "淘宝/天猫": [7, 7, 7, 6, 7, 9], "京东": [6, 9, 10, 9, 9, 7],
            "拼多多": [10, 6, 6, 5, 6, 7], "抖音": [8, 7, 7, 6, 7, 9],
            "盒马": [5, 9, 10, 9, 8, 5], "唯品会": [7, 8, 8, 8, 8, 5],
            "奥乐齐": [10, 7, 5, 7, 5, 4], "联华": [7, 6, 6, 6, 6, 5],
        }
        from math import pi as _pi
        n_rad = len(_radar_labels)
        angles_rad = [_pi * 2 * i / n_rad for i in range(n_rad)] + [_pi * 2]
        ax3_radar = fig.add_subplot(2, 2, 3, polar=True)
        ax3_radar.set_theta_offset(_pi / 2); ax3_radar.set_theta_direction(-1)
        for p in platforms_used[:3]:  # 最多 3 个平台同图
            vals = _radar_preset.get(p, [5]*6)
            vals = vals + vals[:1]
            ax3_radar.plot(angles_rad, vals, "o-", linewidth=1.5, label=p, color=_colors.get(p))
            ax3_radar.fill(angles_rad, vals, alpha=0.12, color=_colors.get(p))
        ax3_radar.set_thetagrids([a * 180 / _pi for a in angles_rad[:-1]], _radar_labels, fontsize=8)
        ax3_radar.set_ylim(0, 10)
        ax3_radar.set_title("🎯 平台性价比雷达图", fontsize=10, fontweight="bold", pad=10)
        ax3_radar.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1), fontsize=8)

        # --- 图4: 省钱大字 ---
        ax4.axis("off")
        global_max = max(maxs_bar) if maxs_bar else 10
        global_min_p = min(mins_bar) if mins_bar else 5
        savings_amt = global_max - global_min_p
        savings_pct = savings_amt / global_max * 100 if global_max else 0
        best_p = names_bar[mins_bar.index(global_min_p)] if mins_bar else "—"
        worst_p = names_bar[maxs_bar.index(global_max)] if maxs_bar else "—"
        ax4.text(0.5, 0.9, "🎯 最佳购买渠道", ha="center", va="center",
                 fontsize=12, fontweight="bold", transform=ax4.transAxes, color="#2E7D32")
        ax4.text(0.5, 0.65, f"🛒 {best_p}", ha="center", va="center",
                 fontsize=18, fontweight="bold", transform=ax4.transAxes, color="#1565C0")
        ax4.text(0.5, 0.4, f"💸 每次省 ¥{savings_amt:.1f} ({savings_pct:.0f}%)",
                 ha="center", va="center", fontsize=14, fontweight="bold",
                 transform=ax4.transAxes, color="#C62828")
        ax4.text(0.5, 0.15, f"对比平台: {worst_p} → {best_p}",
                 ha="center", va="center", fontsize=9,
                 transform=ax4.transAxes, color="#666")

        # 嵌入 Tkinter
        if canvas:
            try: canvas.get_tk_widget().destroy()
            except Exception: pass
        canvas = FigureCanvasTkAgg(fig, master=chart_f)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

    def _parse_price_ranges_from_ai(text: str) -> Dict[str, tuple]:
        """从 AI 返回里解析各平台价位区间 (可失败, 失败返回空 dict)"""
        import re as _pr
        _res: Dict[str, tuple] = {}
        # 匹配 "淘宝:X-Y元" 或 "淘宝:X至Y元" 或 "淘宝 ￥X-Y"
        _pat = r"(淘宝|天猫|京东|拼多多|盒马|奥乐齐|联华|叮咚|唯品会|当当|苏宁)\s*[:：]?\s*[￥¥]?\s*(\d+(?:\.\d+)?)\s*[-~至到]\s*[￥¥]?\s*(\d+(?:\.\d+)?)元?"
        for m in _pr.finditer(_pat, text):
            pname = m.group(1).replace("天猫", "淘宝/天猫")
            try:
                lo, hi = float(m.group(2)), float(m.group(3))
                if 0.5 <= lo <= hi <= 9999:
                    _res[pname] = (lo, hi)
            except Exception: pass
        return _res

    # 让 _render_chart 能被 AI 结果触发 — 把当前 price_hint 存在闭包里
    _current_ai_hint: Dict[str, tuple] = {}

    def _fetch_ai_advice(kw: str):
        """后台线程: 调 call_ai_model 生成购买建议 + 解析价位区间给 matplotlib"""
        nonlocal _current_ai_hint
        if not call_ai_fn:
            win.after(0, lambda: _show_ai(
                "⚠️ 未配置 AI 模型\n请先在程序 AI 设置里填 deepseek/豆包 API key"
            ))
            return
        win.after(0, lambda: _show_ai("⏳ AI 正在生成购买建议... (首次联网拉模型, 约 10-30s)"))
        system_p = "你是中国电商比价专家, 熟悉淘宝/天猫/京东/拼多多/抖音/盒马/唯品会/奥乐齐/联华/叮咚 定价。回答用中文, 紧凑简洁。"
        prompt = (f"商品「{kw}」跨平台购买建议, 请按以下结构输出 (每段 1-3 行):\n\n"
                  f"【各平台常规价】淘宝:X-X元 | 京东:X-X元 | 拼多多:X-X元 | 抖音:X-X元 | 盒马:X-X元 | 唯品会:X-X元\n\n"
                  f"【今天最划算】通货品牌→去___买 (理由:___) | 自有品牌→去___买 | 生鲜→去___买\n\n"
                  f"【直达链接】淘宝 https://s.taobao.com/search?q={kw.replace(' ','')}\n"
                  f"京东 https://search.jd.com/Search?keyword={kw.replace(' ','')}\n"
                  f"拼多多 https://mobile.yangkeduo.com/search_result.html?search_key={kw.replace(' ','')}\n"
                  f"抖音 https://www.douyin.com/search/{kw.replace(' ','')}\n"
                  f"盒马 https://m.hemaos.com/search?keyword={kw.replace(' ','')}\n"
                  f"唯品会 https://search.vip.com/?q={kw.replace(' ','')}\n\n"
                  f"⚠️ 注意: 【各平台常规价】里的 X-X 必须是该商品在该平台的真实常规价位区间 (单位元), "
                  f"例如「恰恰瓜子 150g」应写 淘宝:12-18元 而非 8-14元。请根据商品实际价格填写, 不要用通用占位价。")
        try:
            res = call_ai_fn(prompt, system_prompt=system_p, max_tokens=500)
            if isinstance(res, str) and len(res) > 10:
                _current_ai_hint = _parse_price_ranges_from_ai(res)
                win.after(0, lambda: _show_ai(res))
                # AI 返回后立刻重绘 matplotlib (用 AI 给的真实价位, 图会随商品变化)
                win.after(0, lambda: _render_chart({}))  # 传空让 AI hint 覆盖兜底
            else:
                win.after(0, lambda: _show_ai(f"⚠️ AI 返回异常: {str(res)[:200]}"))
        except Exception as e:
            win.after(0, lambda: _show_ai(f"⚠️ AI 调用失败: {e}\n\n你也可以直接点上方 🌐 平台按钮跳转官网搜。"))

    def _open_link(_e=None):
        sel = tv.selection()
        if not sel: return
        vals = tv.item(sel[0], "values")
        if vals and vals[-1]:
            webbrowser.open(vals[-1])
    tv.bind("<Double-1>", _open_link)

    def _render(res: Dict[str, List[Dict]]):
        for item in tv.get_children():
            tv.delete(item)
        all_prices = []  # (price_val, platform, idx_in_tv)
        row_idx = 0
        for p, items in res.items():
            if not items:
                tv.insert("", tk.END, values=(p, "— (无结果/反爬拦截)", "", "", ""))
                continue
            # 每个平台取前 8 条, 取最低价那条参与跨平台比较
            for it in items[:8]:
                pv = it.get("price") or 0
                # 统一 price 为 float
                try:
                    pv_f = float(pv) if isinstance(pv, (int, float)) else None
                except Exception:
                    pv_f = None
                href = it.get("url") or ""
                tv.insert("", tk.END, iid=f"row_{row_idx}",
                           values=(p, it.get("name", "")[:60],
                                   it.get("price_str", ""), "",
                                   "打开商品页 →" if href else ""))
                if pv_f and pv_f > 0:
                    all_prices.append((pv_f, p, f"row_{row_idx}", href))
                row_idx += 1

        if all_prices:
            prices_only = [x[0] for x in all_prices]
            mn = min(prices_only); mx = max(prices_only)
            avg = sum(prices_only) / len(prices_only)
            # 跨平台最低价平台
            mn_item = min(all_prices, key=lambda x: x[0])
            mx_item = max(all_prices, key=lambda x: x[0])
            # 标最低价绿, 最高价红 (同平台内也标)
            for pv, pname, rid, href in all_prices:
                if rid not in tv.get_children(): continue
                tag = ""
                if rid == mn_item[2]: tag = "min"
                elif rid == mx_item[2]: tag = "max"
                if tag:
                    tv.item(rid, tags=(tag,))
            summary_var.set(
                f"📊 {len(all_prices)} 个有效商品 | "
                f"💰 最低价 {mn:.2f} ({mn_item[1]}) | "
                f"💸 最高价 {mx:.2f} ({mx_item[1]}) | "
                f"📉 价差 {mx-mn:.2f} | "
                f"📈 均价 {avg:.2f}"
            )
        else:
            summary_var.set("⚠️ 所有平台都没抓到结构化数据（反爬/风控拦截） → AI 购买建议正在并行生成中...")
        status_var.set("✅ 搜索完成 | 双击行打开商品页 | 绿色=跨平台最低价 红色=最高价")
        # ⚡ 每次搜索都渲染图形化比价 (反爬时用预设价位兜底)
        try:
            _render_chart(res)
        except Exception as _echart:
            print(f"[比价图形] _render_chart 异常: {_echart}")

    # 默认自动搜一次
    win.after(200, _do_search)
    win.mainloop()


if __name__ == "__main__":
    show_price_compare_dialog()

