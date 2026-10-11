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
        platforms = ["淘宝/天猫", "京东", "拼多多", "盒马"]

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
def show_price_compare_dialog(parent_win=None):
    """💰 比价弹窗 — 搜索词 → 多平台并行抓价 → Treeview 展示 + 最低/最高/平均 + 点击链接"""
    import tkinter as tk
    from tkinter import ttk, messagebox
    import threading
    import webbrowser

    win = tk.Toplevel(parent_win) if parent_win else tk.Tk()
    win.title("💰 跨平台比价")
    win.geometry("1100x680")
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
    _platforms_list = ["淘宝/天猫", "京东", "拼多多", "盒马"]
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

        def _bg():
            try:
                res = fetch_all_platforms(kw, platforms=sel_p)
                win.after(0, lambda: _render(res))
            except Exception as e:
                win.after(0, lambda: status_var.set(f"❌ 搜索失败: {e}"))

        threading.Thread(target=_bg, daemon=True).start()

    tk.Button(btn_row, text="🔍 搜索", command=_do_search, bg="#FFD54F", fg="#1A237E",
              font=("", 10, "bold"), relief=tk.FLAT, padx=14).pack(side=tk.LEFT, padx=10)

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

    tk.Button(btn_row, text="🌐 淘宝", command=lambda: webbrowser.open(
        f"https://s.taobao.com/search?q={kw_var.get().strip()}"),
              bg="#FF5722", fg="white", relief=tk.FLAT, padx=8).pack(side=tk.LEFT)
    tk.Button(btn_row, text="🌐 京东", command=lambda: webbrowser.open(
        f"https://search.jd.com/Search?keyword={kw_var.get().strip()}"),
              bg="#E53935", fg="white", relief=tk.FLAT, padx=8).pack(side=tk.LEFT, padx=3)
    tk.Button(btn_row, text="🌐 拼多多", command=lambda: webbrowser.open(
        f"https://mobile.yangkeduo.com/search_result.html?search_key={kw_var.get().strip()}"),
              bg="#E91E63", fg="white", relief=tk.FLAT, padx=8).pack(side=tk.LEFT, padx=3)
    tk.Button(btn_row, text="🌐 盒马", command=lambda: webbrowser.open(
        f"https://m.hemaos.com/search?keyword={kw_var.get().strip()}"),
              bg="#4CAF50", fg="white", relief=tk.FLAT, padx=8).pack(side=tk.LEFT, padx=3)

    # ===== 汇总栏 =====
    summary_var = tk.StringVar(value="")
    summ_f = tk.Frame(win, bg="#FFF9C4"); summ_f.pack(fill=tk.X, padx=10, pady=4)
    tk.Label(summ_f, textvariable=summary_var, bg="#FFF9C4", fg="#333",
             font=("", 10, "bold"), anchor="w").pack(fill=tk.X, padx=8, pady=4)

    # ===== Treeview =====
    cols = ("平台", "商品", "价格", "最低价", "链接")
    tv_frame = tk.Frame(win); tv_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=6)
    tv = ttk.Treeview(tv_frame, columns=cols, show="headings", height=18)
    for c, w in [("平台", 90), ("商品", 420), ("价格", 100), ("最低价", 80), ("链接", 300)]:
        tv.heading(c, text=c); tv.column(c, width=w, anchor="w")
    sb = ttk.Scrollbar(tv_frame, orient=tk.VERTICAL, command=tv.yview)
    tv.configure(yscrollcommand=sb.set)
    tv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True); sb.pack(side=tk.RIGHT, fill=tk.Y)
    # tag 颜色
    tv.tag_configure("min", background="#C8E6C9")   # 最低价绿
    tv.tag_configure("max", background="#FFCDD2")   # 最高价红

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
            summary_var.set("⚠️ 所有平台都没抓到结构化数据 — 可能是反爬/风控, 请直接点上方平台按钮跳转官网搜索")
        status_var.set("✅ 搜索完成 | 双击行打开商品页 | 绿色=跨平台最低价 红色=最高价")

    # 默认自动搜一次
    win.after(200, _do_search)
    win.mainloop()


if __name__ == "__main__":
    show_price_compare_dialog()

