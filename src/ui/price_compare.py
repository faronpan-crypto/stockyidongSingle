# -*- coding: utf-8 -*-
"""💰 跨平台比价 — MVP 版

平台数据源:
  淘宝/天猫  — s.taobao.com 搜索页 (HTML 正则提取 listItem)
  京东      — search.jd.com 搜索页 (HTML regex)
  拼多多    — mobile.yangkeduo.com 搜索页 (HTML regex)
  盒马      — m.hemaos.com/x/pc/online/search (HTTP JSON)
  联华/叮咚  — 无公开接口, 本期跳过

⚠️ 所有抓取仅做"商品名+价格+图片+链接"基础提取, 不做账号登录/签名逆向。
   若某平台反爬返回空列表 → UI 显示 "-"。

调用:
    results = fetch_all_platforms("恰恰瓜子 150g")
"""
from __future__ import annotations
import ssl as _ssl
import re as _re
import json as _json
import urllib.parse as _up
from urllib.request import Request, urlopen
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional
from html import unescape as _hunesc

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
    """并行拉多平台, 返回 {platform_name: [item_dict, ...]}"""
    if platforms is None:
        platforms = ["淘宝/天猫", "京东", "拼多多", "盒马"]
    _fns = {
        "淘宝/天猫": _fetch_taobao,
        "京东": _fetch_jd,
        "拼多多": _fetch_pdd,
        "盒马": _fetch_hema,
    }
    results: Dict[str, List[Dict]] = {p: [] for p in platforms}
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

