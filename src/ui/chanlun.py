# -*- coding: utf-8 -*-
"""
🌀 缠论 (Chan Theory) 完整实现
=========================================
Step 1. 包含处理 (inclusion handling) — 相邻K线高低点互相包含时合并成一根
Step 2. 分型 (fractal)                — 顶/底分型
Step 3. 笔 (stroke / bi)              — 顶底分型交替 + 独立K线间隔
Step 4. 中枢 (zhongshu / pivot)       — 3笔重叠区间 [ZG, ZD]
Step 5. 背驰 (beichi / divergence)    — 价格新高/低但动能(MACD面积)减弱
Step 6. 买卖点 (6 types)             — 一买/二买/三买 + 一卖/二卖/三卖

输出: {"han": [...], "fractals": [...], "strokes": [...],
       "zhongshus": [...], "beichi": {...}, "signals": [...], "summary": [...]}
"""
import numpy as np
from typing import List, Dict, Any, Tuple, Optional


# ============================================================
# Step 1. 包含处理
# ============================================================
def process_inclusions(opens, highs, lows, closes, direction="auto"):
    """
    处理 K 线包含关系:
    - 上升趋势 (direction='up'): 两根 K 线互相包含时, 取高点更高的合并 (向上合并)
    - 下降趋势 (direction='down'): 取低点更低的合并 (向下合并)
    - 'auto': 自动判断前两根高低点关系

    返回: (new_h, new_l) — 处理后的高低点序列, 以及对应的原始索引映射
    """
    n = len(highs)
    if n < 3: return highs, lows, list(range(n))

    # auto 判断初始方向
    if direction == "auto":
        direction = "up" if highs[1] > highs[0] else "down"

    new_h = [float(highs[0])]
    new_l = [float(lows[0])]
    idx_map = [0]

    for i in range(1, n):
        h = float(highs[i]); l = float(lows[i])

        # 包含关系判断: 当前K线被前一根包含 or 包含前一根
        is_contained = (h <= new_h[-1] and l >= new_l[-1]) or \
                       (h >= new_h[-1] and l <= new_l[-1])

        if is_contained:
            if direction == "up":
                # 上升中, 包含处理: 高取更高, 低取更高 (向上合并, K线抬高)
                new_h[-1] = max(new_h[-1], h)
                new_l[-1] = max(new_l[-1], l)
            else:
                # 下降中: 高取更低, 低取更低 (向下合并, K线下沉)
                new_h[-1] = min(new_h[-1], h)
                new_l[-1] = min(new_l[-1], l)
            idx_map[-1] = i  # 合并后的索引指向最新 K 线
        else:
            # 无包含: 直接追加 + 更新方向
            if h > new_h[-1]:
                direction = "up"
            elif l < new_l[-1]:
                direction = "down"
            new_h.append(h); new_l.append(l); idx_map.append(i)

    return np.array(new_h), np.array(new_l), idx_map


# ============================================================
# Step 2. 分型 (顶/底)
# ============================================================
def find_fractals(highs, lows):
    """
    在包含处理后的高低点序列上找分型:
    - 顶分型: 中间K线高点最高, 低点也最高 (三根K线)
    - 底分型: 中间K线低点最低, 高点也最低
    返回: {"top": [(idx, price), ...], "bot": [(idx, price), ...],
           "merged": [("top"/"bot", idx, price), ...]}
    """
    tops, bots = [], []
    m = len(highs)
    for i in range(1, m - 1):
        h_prev, h_i, h_next = highs[i-1], highs[i], highs[i+1]
        l_prev, l_i, l_next = lows[i-1], lows[i], lows[i+1]

        # 顶分型
        if h_i > h_prev and h_i > h_next and l_i > l_prev and l_i > l_next:
            tops.append((i, h_i))
        # 底分型
        elif l_i < l_prev and l_i < l_next and h_i < h_prev and h_i < h_next:
            bots.append((i, l_i))

    # 合并 + 排序 (索引顺序)
    merged = [("top", i, p) for i, p in tops] + [("bot", i, p) for i, p in bots]
    merged.sort(key=lambda x: x[1])

    return {"top": tops, "bot": bots, "merged": merged}


# ============================================================
# Step 3. 笔 (Stroke / Bi)
# ============================================================
def build_strokes(fractals_merged, highs, lows, min_gap=4):
    """
    从分型构建笔 (缠论标准笔规则):
    - 顶底分型交替出现 (连续同方向合并, 保留更极端)
    - 两个分型之间索引差 >= min_gap (默认 4: 笔起点+中间独立K线+笔终点)

    返回: [{"type": "up"/"down", "start_idx": int, "end_idx": int,
            "start_price": float, "end_price": float, "amp": float}]
    """
    merged = list(fractals_merged)  # [("top", idx, price), ...]
    if len(merged) < 2: return []

    # 第 1 步: 合并连续同方向分型 (顶取更高 / 底取更低)
    filtered = [merged[0]]
    for i in range(1, len(merged)):
        last = filtered[-1]
        cur = merged[i]
        if last[0] != cur[0]:
            filtered.append(cur)
        else:
            if last[0] == "top":
                if cur[2] > last[2]: filtered[-1] = cur
            else:
                if cur[2] < last[2]: filtered[-1] = cur

    if len(filtered) < 2: return []

    # 第 2 步: 贪心构建笔 (保证方向交替 + 间隔足够)
    strokes = []
    prev = filtered[0]
    for i in range(1, len(filtered)):
        cur = filtered[i]
        # 方向必须相反
        if prev[0] == cur[0]: continue

        gap = abs(cur[1] - prev[1])
        if gap < min_gap:
            # 间隔不够: 跳过当前分型, 继续等更远的
            continue

        # 间隔够了: 确认这一笔
        if prev[0] == "bot" and cur[0] == "top":
            strokes.append({
                "type": "up",
                "start_idx": prev[1], "end_idx": cur[1],
                "start_price": prev[2], "end_price": cur[2],
                "amp": cur[2] - prev[2],
            })
        else:  # prev top → cur bot
            strokes.append({
                "type": "down",
                "start_idx": prev[1], "end_idx": cur[1],
                "start_price": prev[2], "end_price": cur[2],
                "amp": cur[2] - prev[2],
            })
        prev = cur  # 推进到下一个分型

    return strokes


# ============================================================
# Step 4. 中枢 (Zhongshu / Pivot)
# ============================================================
def find_zhongshus(strokes):
    """
    中枢: 至少 3 笔重叠区间
    - ZG (中枢上沿) = min(3 笔的高点)  — 3笔高点里最低的
    - ZD (中枢下沿) = max(3 笔的低点)  — 3笔低点里最高的
    - 重叠成立条件: ZG > ZD
    - 中枢延伸: 后续笔落入 [ZD, ZG] 区间内则扩展中枢

    返回: [{"ZG": float, "ZD": float, "start_idx": int, "end_idx": int,
            "strokes_count": int, "level": 1}]
    """
    if len(strokes) < 3: return []

    zhongshus = []
    i = 0
    while i <= len(strokes) - 3:
        # 取连续 3 笔
        s1, s2, s3 = strokes[i], strokes[i+1], strokes[i+2]
        # 3 笔的四个端点
        all_idx = [s1["start_idx"], s1["end_idx"], s2["end_idx"], s3["end_idx"]]
        all_prices = []
        for s in (s1, s2, s3):
            all_prices.append((s["start_price"], s["end_price"]))

        # 每笔的高低点
        # s1, s2, s3 交替 up/down
        highs_i = [max(s1["start_price"], s1["end_price"]),
                   max(s2["start_price"], s2["end_price"]),
                   max(s3["start_price"], s3["end_price"])]
        lows_i  = [min(s1["start_price"], s1["end_price"]),
                   min(s2["start_price"], s2["end_price"]),
                   min(s3["start_price"], s3["end_price"])]

        zg = min(highs_i)   # 中枢上沿
        zd = max(lows_i)    # 中枢下沿
        if zg <= zd:
            i += 1
            continue  # 不重叠

        zs_start_idx = min(all_idx)
        zs_end_idx = max(all_idx)

        # 中枢延伸: 从 i+3 开始, 若后续笔仍落入 [ZD, ZG] 就扩展
        j = i + 3
        while j < len(strokes):
            sj = strokes[j]
            h_j = max(sj["start_price"], sj["end_price"])
            l_j = min(sj["start_price"], sj["end_price"])
            # 笔与中枢重叠 → 中枢扩展
            if l_j < zg and h_j > zd:
                zs_end_idx = max(zs_end_idx, sj["end_idx"])
                j += 1
            else:
                break

        zhongshus.append({
            "ZG": zg, "ZD": zd,
            "start_idx": zs_start_idx, "end_idx": zs_end_idx,
            "strokes_count": j - i,
        })
        i = j  # 从中枢之后的笔继续找下一个中枢

    return zhongshus


# ============================================================
# Step 5. 背驰 (Beichi / Divergence)
# ============================================================
def calc_macd_area(closes, fast=12, slow=26, signal=9):
    """计算 MACD 柱面积 (绝对值累加) 用于判断动能衰减"""
    def _ema(a, w):
        r = np.empty_like(a, dtype=float)
        r[0] = a[0]; k = 2/(w+1)
        for i in range(1, len(a)): r[i] = a[i]*k + r[i-1]*(1-k)
        return r
    c = np.asarray(closes, dtype=float)
    dif = _ema(c, fast) - _ema(c, slow)
    dea = _ema(dif, signal)
    macd = (dif - dea) * 2
    return macd, dif, dea


def detect_beichi(strokes, closes):
    """
    背驰判断:
    - 趋势背驰: 两笔同向 (都 up 或都 down), 价格创新高/低, 但 MACD 面积减小
    - 返回: [{"type": "top"/"bot", "stroke_idx_1": int, "stroke_idx_2": int,
              "price_1": float, "price_2": float,
              "area_1": float, "area_2": float,
              "desc": "..."}]
    """
    if len(strokes) < 4 or closes is None or len(closes) < 30: return []
    macd, _, _ = calc_macd_area(closes)
    beichi_list = []

    # 遍历每一对同向笔 (up 对 up, down 对 down)
    for i in range(len(strokes) - 2):
        s1 = strokes[i]
        for j in range(i + 2, min(i + 6, len(strokes))):
            s2 = strokes[j]
            if s1["type"] != s2["type"]: continue

            # 计算 s1 区间的 MACD 柱面积 (累加)
            i1a, i1b = min(s1["start_idx"], s1["end_idx"]), max(s1["start_idx"], s1["end_idx"])
            i2a, i2b = min(s2["start_idx"], s2["end_idx"]), max(s2["start_idx"], s2["end_idx"])
            if i1b >= len(macd) or i2b >= len(macd): continue
            area1 = float(np.sum(np.abs(macd[i1a:i1b+1])))
            area2 = float(np.sum(np.abs(macd[i2a:i2b+1])))

            if s1["type"] == "up":
                # 上涨背驰: s2 价格更高, 但 MACD 面积更小 → 顶背驰
                if s2["end_price"] > s1["end_price"] * 1.001 and area2 < area1 * 0.85:
                    beichi_list.append({
                        "type": "top",
                        "stroke_idx_1": i, "stroke_idx_2": j,
                        "price_1": s1["end_price"], "price_2": s2["end_price"],
                        "area_1": area1, "area_2": area2,
                        "desc": f"顶背驰! 笔{i+1}高{s1['end_price']:.2f} → 笔{j+1}高{s2['end_price']:.2f} "
                                f"(+{(s2['end_price']/s1['end_price']-1)*100:.1f}%) MACD面积 {area1:.0f}→{area2:.0f} (-{(1-area2/area1)*100:.0f}%)",
                    })
            else:
                # 下跌背驰: s2 价格更低, MACD 面积更小 → 底背驰
                if s2["end_price"] < s1["end_price"] * 0.999 and area2 < area1 * 0.85:
                    beichi_list.append({
                        "type": "bot",
                        "stroke_idx_1": i, "stroke_idx_2": j,
                        "price_1": s1["end_price"], "price_2": s2["end_price"],
                        "area_1": area1, "area_2": area2,
                        "desc": f"底背驰! 笔{i+1}低{s1['end_price']:.2f} → 笔{j+1}低{s2['end_price']:.2f} "
                                f"({(s2['end_price']/s1['end_price']-1)*100:.1f}%) MACD面积 {area1:.0f}→{area2:.0f} (-{(1-area2/area1)*100:.0f}%)",
                    })

    return beichi_list


# ============================================================
# Step 6. 买卖点 (6 types)
# ============================================================
def detect_chan_signals(strokes, zhongshus, beichi_list):
    """
    缠论 6 类买卖点判断:

    - 一买: 下跌趋势出现底背驰后的第一个底分型确认 (笔结束)
    - 二买: 一买之后第一次回踩, 不破中枢 ZD
    - 三买: 中枢上方 (ZD 以上) 回踩不进入中枢 [ZD, ZG] 区间

    - 一卖: 上涨趋势出现顶背驰后的第一个顶分型确认 (笔结束)
    - 二卖: 一卖之后第一次反弹, 不破中枢 ZG
    - 三卖: 中枢下方 (ZG 以下) 反弹不进入中枢 [ZD, ZG] 区间

    返回: [{"type": "一买"/"二买"/"三买"/"一卖"/"二卖"/"三卖",
            "stroke_idx": int, "price": float, "desc": "..."}]
    """
    signals = []
    if not strokes: return signals
    n_strokes = len(strokes)

    # === 一买 / 一卖 ===
    for bc in beichi_list:
        sig = "一卖" if bc["type"] == "top" else "一买"
        sig_emoji = "🔴" if bc["type"] == "top" else "🟢"
        target_stroke_idx = bc["stroke_idx_2"]
        if target_stroke_idx < n_strokes:
            s = strokes[target_stroke_idx]
            price = s["end_price"]
            signals.append({
                "type": sig, "stroke_idx": target_stroke_idx, "price": price,
                "desc": f"{sig_emoji} {sig}! {bc['desc'][:80]}",
            })

    # === 三买 / 三卖 (基于中枢 + 后续笔位置) ===
    for zs in zhongshus:
        zg, zd = zs["ZG"], zs["ZD"]
        # 找到该中枢之后的笔起点索引
        post_start_stroke = None
        for idx, s in enumerate(strokes):
            if s["start_idx"] >= zs["end_idx"] - 1:
                post_start_stroke = idx
                break
        if post_start_stroke is None: continue

        # 中枢上方 (三买区域)
        buy_zone = strokes[post_start_stroke:]
        for s in buy_zone:
            if s["type"] == "down":
                lo = min(s["start_price"], s["end_price"])
                hi = max(s["start_price"], s["end_price"])
                # 三买: 向下笔低点 > ZD (回踩不进中枢)
                if lo > zd * 1.001 and hi > zg:
                    signals.append({
                        "type": "三买",
                        "stroke_idx": strokes.index(s),
                        "price": s["end_price"],
                        "desc": f"🟢 三买! 中枢 [{zd:.2f},{zg:.2f}] 回踩低点 {lo:.2f} > ZD {zd:.2f}",
                    })
                    break

        # 中枢下方 (三卖区域)
        sell_zone = strokes[post_start_stroke:]
        for s in sell_zone:
            if s["type"] == "up":
                lo = min(s["start_price"], s["end_price"])
                hi = max(s["start_price"], s["end_price"])
                # 三卖: 向上笔高点 < ZG (反弹不进中枢)
                if hi < zg * 0.999 and lo < zd:
                    signals.append({
                        "type": "三卖",
                        "stroke_idx": strokes.index(s),
                        "price": s["end_price"],
                        "desc": f"🔴 三卖! 中枢 [{zd:.2f},{zg:.2f}] 反弹高点 {hi:.2f} < ZG {zg:.2f}",
                    })
                    break

    # 去重 + 按 stroke_idx 排序
    seen = set(); out = []
    for s in signals:
        key = (s["type"], s["stroke_idx"])
        if key not in seen:
            seen.add(key); out.append(s)
    out.sort(key=lambda x: x["stroke_idx"])

    return out


# ============================================================
# 入口: 一次性跑完整缠论分析
# ============================================================
def analyze_chan(opens, highs, lows, closes):
    """
    主入口: 输入 OHLC 数组 (长度 >= 60), 返回完整缠论分析结果
    """
    closes = np.asarray(closes, dtype=float)
    highs = np.asarray(highs, dtype=float)
    lows = np.asarray(lows, dtype=float)
    opens = np.asarray(opens, dtype=float) if opens is not None else closes.copy()
    if len(closes) < 60:
        return {"ok": False, "msg": "缠论分析至少需要 60 根K线"}

    # Step 1: 包含处理
    new_h, new_l, idx_map = process_inclusions(opens, highs, lows, closes)
    han_count = len(new_h)

    # Step 2: 分型
    fractals = find_fractals(new_h, new_l)

    # Step 3: 笔
    strokes = build_strokes(fractals["merged"], new_h, new_l)

    # Step 4: 中枢
    zhongshus = find_zhongshus(strokes)

    # Step 5: 背驰
    beichi = detect_beichi(strokes, closes)

    # Step 6: 买卖点
    signals = detect_chan_signals(strokes, zhongshus, beichi)

    # ===== 汇总 =====
    summary = []
    summary.append(f"📊 K线 {len(closes)} 根 → 包含处理后 {han_count} 根 (-{(1-len(new_h)/len(closes))*100:.0f}%)")
    summary.append(f"🌀 顶分型 {len(fractals['top'])} 个 / 底分型 {len(fractals['bot'])} 个")
    summary.append(f"✒️ 笔 {len(strokes)} 根 ({sum(1 for s in strokes if s['type']=='up')}上 / {sum(1 for s in strokes if s['type']=='down')}下)")
    summary.append(f"🧱 中枢 {len(zhongshus)} 段")
    summary.append(f"💫 背驰 {len(beichi)} 个")
    summary.append(f"🎯 买卖点 {len(signals)} 个")

    # 当前位置判断
    if strokes:
        last = strokes[-1]
        cur_price = closes[-1]
        # 找最近中枢
        last_zs = zhongshus[-1] if zhongshus else None
        if last_zs:
            if cur_price > last_zs["ZG"]:
                pos = "中枢上方 (强势, 找三买)"
            elif cur_price < last_zs["ZD"]:
                pos = "中枢下方 (弱势, 找三卖)"
            else:
                pos = f"中枢内部 [{last_zs['ZD']:.2f},{last_zs['ZG']:.2f}]"
            summary.append(f"📍 当前价 {cur_price:.2f} | {pos}")

        last_amp_pct = (last["end_price"] - last["start_price"]) / last["start_price"] * 100
        summary.append(f"📍 最新笔: {last['type']} {last_amp_pct:+.1f}% "
                       f"({last['start_price']:.2f} → {last['end_price']:.2f})")

    return {
        "ok": True,
        "han_count": han_count,        # 包含处理后的 K 线数
        "fractals": fractals,          # {"top": [...], "bot": [...], "merged": [...]}
        "strokes": strokes,            # 笔列表
        "zhongshus": zhongshus,        # 中枢列表
        "beichi": beichi,              # 背驰列表
        "signals": signals,            # 买卖点列表
        "summary": summary,            # 汇总文本行列表
        "idx_map": idx_map,            # 包含处理后的索引映射 (原始索引)
    }


def format_chan_report(result: Dict) -> List[str]:
    """把 analyze_chan 的 dict 格式化为可展示的文本行列表"""
    if not result.get("ok"):
        return [result.get("msg", "缠论分析失败")]

    lines = result["summary"]
    lines.append("")

    # 中枢详情
    if result["zhongshus"]:
        lines.append("🧱 中枢详情:")
        for i, zs in enumerate(result["zhongshus"]):
            lines.append(f"  #{i+1}: [{zs['ZD']:.2f}, {zs['ZG']:.2f}] "
                         f"(宽度 {(zs['ZG']-zs['ZD'])/zs['ZD']*100:.1f}%) {zs['strokes_count']}笔")
    else:
        lines.append("🧱 中枢: 尚未形成 (需 ≥3 笔重叠)")

    # 背驰详情
    if result["beichi"]:
        lines.append("💫 背驰信号:")
        for bc in result["beichi"][-5:]:  # 最多显示最近 5 个
            lines.append(f"  {'🟢' if bc['type']=='bot' else '🔴'} {bc['desc']}")

    # 买卖点
    if result["signals"]:
        lines.append("🎯 缠论买卖点:")
        for sg in result["signals"]:
            lines.append(f"  {sg['desc']}")
    else:
        lines.append("🎯 买卖点: 暂无触发 (关注中枢突破/回踩)")

    return lines
