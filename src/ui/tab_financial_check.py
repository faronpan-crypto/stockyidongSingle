# -*- coding: utf-8 -*-
"""
财务造假检测引擎
数据源: AKShare 同花顺接口 (免费)
三大报表 + 30+ 异常信号打分 → 综合风险评级
"""
import re
import threading
import queue
import tkinter as tk
from tkinter import ttk, scrolledtext
from collections import Counter


# ═══════════════════════════════════════════════════════════════
# 🔢 核心分析函数
# ═══════════════════════════════════════════════════════════════

def _parse_amount(val):
    """同花顺返回 'xxx.xx亿' / 'xxx万' / False → 转换为 float (元)"""
    if val is None or val is False or val == '' or (isinstance(val, float) and val != val):
        return 0.0
    s = str(val).strip()
    if '亿' in s:
        return float(s.replace('亿', '')) * 1e8
    elif '万' in s:
        return float(s.replace('万', '')) * 1e4
    try:
        return float(s)
    except ValueError:
        return 0.0


def detect_financial_fraud(code, name="",
                           profit_df=None, bs_df=None, cf_df=None,
                           log_fn=None):
    """
    财务造假检测引擎 — 返回 dict

    Args:
        code: 6位股票代码
        name: 股票名称 (可选)
        profit_df / bs_df / cf_df: 三大报表 DataFrame (可选, 不传则自动拉)
        log_fn: 日志函数 (可选)

    Returns: {
        "score": 35,              # 0-100 风险分 (越高越危险)
        "risk_level": "低/中/高/极高",
        "summary": "...",          # 一句话总结
        "signals": [               # 所有检测信号
            {
                "cat": "利润表",
                "name": "应收账款增速 > 营收增速",
                "score": 15,       # 本次加了多少分
                "severity": "🔴高",  # 🔴高/🟡中/🟢低
                "detail": "应收增 85%, 营收增 32% → 差 53pp",
                "data": {...}        # 原始数据 (帮助弹窗用)
            }, ...
        ],
        "data": {
            "profit": {...},        # 利润表关键数据
            "bs": {...},            # 资产负债表关键数据
            "cf": {...}             # 现金流量表关键数据
        }
    }
    """
    import akshare as ak
    import pandas as pd
    import numpy as np

    def _log(msg):
        if log_fn:
            try:
                log_fn(msg)
            except Exception:
                pass

    result = {
        "score": 0,
        "risk_level": "—",
        "summary": "",
        "signals": [],
        "data": {"profit": {}, "bs": {}, "cf": {}},
        "code": code,
        "name": name,
    }

    # ── Step 1: 拉数据 ──
    _log(f"📥 拉取 {code} 三大报表...")
    if profit_df is None:
        try:
            profit_df = ak.stock_financial_benefit_ths(symbol=code, indicator="按报告期")
        except Exception as e:
            _log(f"❌ 利润表拉取失败: {e}")
            return result
    if bs_df is None:
        try:
            bs_df = ak.stock_financial_debt_ths(symbol=code, indicator="按报告期")
        except Exception as e:
            _log(f"❌ 资产负债表拉取失败: {e}")
            return result
    if cf_df is None:
        try:
            cf_df = ak.stock_financial_cash_ths(symbol=code, indicator="按报告期")
        except Exception as e:
            _log(f"❌ 现金流量表拉取失败: {e}")
            return result

    if profit_df is None or len(profit_df) < 4:
        _log(f"⚠️ 利润表数据不足")
        return result

    # 统一列名 (同花顺带 *)
    profit_df = profit_df.copy()
    bs_df = bs_df.copy()
    cf_df = cf_df.copy()
    # 把 '*xxx' 列名去掉星号方便引用
    for df in [profit_df, bs_df, cf_df]:
        df.columns = [c.lstrip('*') for c in df.columns]

    # 按报告期排序 (降序)
    profit_df = profit_df.sort_values("报告期", ascending=False).reset_index(drop=True)
    bs_df = bs_df.sort_values("报告期", ascending=False).reset_index(drop=True)
    cf_df = cf_df.sort_values("报告期", ascending=False).reset_index(drop=True)

    # 取最近 4 个报告期 + 最近 2 年年报
    recent = profit_df.head(4)
    annual = profit_df[profit_df["报告期"].str.endswith("-12-31")].head(3)
    bs_recent = bs_df.head(4)
    cf_recent = cf_df.head(4)

    # ── Step 2: 提取核心数值 ──
    # 最新一期 (TTM 近似)
    latest_p = profit_df.iloc[0]
    latest_bs = bs_df.iloc[0] if len(bs_df) > 0 else {}
    latest_cf = cf_df.iloc[0] if len(cf_df) > 0 else {}

    def _g(df, col, default=None):
        """从 df 最新行取列值, 转 float"""
        if df is None or len(df) == 0 or col not in df.columns:
            return default
        val = df.iloc[0][col]
        # 如果是 Series (列名重复), 取第一个值
        if hasattr(val, 'item'):
            try:
                val = val.item()
            except Exception:
                if hasattr(val, 'iloc'):
                    val = val.iloc[0]
        return _parse_amount(val)

    # 利润表
    rev_latest = _g(profit_df, "一、营业总收入", 0)
    cost_latest = _g(profit_df, "二、营业总成本", 0)
    gross_profit = rev_latest - cost_latest
    gross_margin = (gross_profit / rev_latest * 100) if rev_latest > 0 else 0
    net_profit = _g(profit_df, "五、净利润", 0)
    parent_net_profit = _g(profit_df, "归属于母公司所有者的净利润", 0)
    dedu_net_profit = _g(profit_df, "扣除非经常性损益后的净利润", 0)
    rd_expense = _g(profit_df, "研发费用", 0)
    sales_expense = _g(profit_df, "销售费用", 0)
    admin_expense = _g(profit_df, "管理费用", 0)
    financial_expense = _g(profit_df, "财务费用", 0)
    interest_income = _g(profit_df, "利息收入", 0)
    interest_expense = _g(profit_df, "利息费用", 0)
    impairment_loss = _g(profit_df, "资产减值损失", 0)
    credit_impairment = _g(profit_df, "信用减值损失", 0)
    fair_value = _g(profit_df, "加：公允价值变动收益", 0)
    invest_income = _g(profit_df, "投资收益", 0)

    result["data"]["profit"] = {
        "报告期": str(latest_p.get("报告期", "")),
        "营业总收入": rev_latest,
        "营业总成本": cost_latest,
        "毛利率%": round(gross_margin, 2),
        "净利润": net_profit,
        "归母净利润": parent_net_profit,
        "扣非净利润": dedu_net_profit,
    }

    # 资产负债表
    total_assets = _g(bs_df, "资产合计", 0)
    total_liabilities = _g(bs_df, "负债合计", 0)
    equity = _g(bs_df, "所有者权益（或股东权益）合计", 0)
    cash = _g(bs_df, "货币资金", 0)
    total_cash = _g(bs_df, "总现金", cash)
    ar_票据应收 = _g(bs_df, "应收票据及应收账款", 0)
    ar = _g(bs_df, "应收账款", 0)
    other_recv = _g(bs_df, "其他应收款合计", 0)
    inventory = _g(bs_df, "存货", 0)
    fixed_assets = _g(bs_df, "固定资产合计", 0)
    construction = _g(bs_df, "在建工程合计", 0)
    goodwill = _g(bs_df, "商誉", 0)
    short_loan = _g(bs_df, "短期借款", 0)
    long_loan = _g(bs_df, "长期借款", 0)

    debt_ratio = (total_liabilities / total_assets * 100) if total_assets > 0 else 0

    result["data"]["bs"] = {
        "总资产": total_assets, "总负债": total_liabilities,
        "货币资金": cash, "应收账款": ar, "存货": inventory,
        "固定资产": fixed_assets, "在建工程": construction, "商誉": goodwill,
        "负债率%": round(debt_ratio, 2),
        "短期借款": short_loan, "长期借款": long_loan,
    }

    # 现金流量表
    ocf = _g(cf_df, "经营活动产生的现金流量净额", 0)
    icf = _g(cf_df, "投资活动产生的现金流量净额", 0)
    fcf = _g(cf_df, "筹资活动产生的现金流量净额", 0)
    ending_cash = _g(cf_df, "期末现金及现金等价物余额", 0)
    total_cf_change = _g(cf_df, "现金及现金等价物净增加额", 0)
    sales_cash = _g(cf_df, "销售商品、提供劳务收到的现金", 0)

    result["data"]["cf"] = {
        "经营活动净额": ocf, "投资活动净额": icf, "筹资活动净额": fcf,
        "期末现金": ending_cash, "销售回款": sales_cash,
    }

    # ═══════════════════════════════════════════════════════════════
    # 🔍 检测 1: 利润表异常
    # ═══════════════════════════════════════════════════════════════

    # 1.1 净利润 vs 经营现金流背离 (应计利润异常)
    if net_profit != 0 and ocf != 0:
        ratio = ocf / net_profit  # 正常应该 > 0.5
        if ratio < 0.2 and ratio > -10:
            s = {"cat": "利润表", "name": "净利润与经营现金流严重背离",
                 "severity": "🔴高", "score": 20,
                 "detail": f"净利润={net_profit/1e8:.1f}亿, 经营现金流={ocf/1e8:.1f}亿 → 比值 {ratio:.2f} (应 > 0.5)"}
            result["signals"].append(s); result["score"] += 20
        elif ratio < 0.5 and ratio > -10:
            s = {"cat": "利润表", "name": "净利润与经营现金流背离",
                 "severity": "🟡中", "score": 10,
                 "detail": f"净利润={net_profit/1e8:.1f}亿, 经营现金流={ocf/1e8:.1f}亿 → 比值 {ratio:.2f}"}
            result["signals"].append(s); result["score"] += 10

    # 1.2 扣非净利润 vs 归母净利润差距大 (非经常性收益美化利润)
    if parent_net_profit != 0 and dedu_net_profit != 0:
        diff = (parent_net_profit - dedu_net_profit) / abs(parent_net_profit) * 100
        if diff > 30:
            s = {"cat": "利润表", "name": "扣非净利润与归母净利润差距大",
                 "severity": "🟡中", "score": 8,
                 "detail": f"归母={parent_net_profit/1e8:.1f}亿, 扣非={dedu_net_profit/1e8:.1f}亿 → 差 {diff:.1f}% (非经常性收益美化利润)"}
            result["signals"].append(s); result["score"] += 8

    # 1.3 毛利率异常波动 (最近 3 个季度)
    gm_list = []
    for i in range(min(3, len(profit_df))):
        rev = _g(profit_df.iloc[i:i+1], "一、营业总收入", 0)
        cost = _g(profit_df.iloc[i:i+1], "二、营业总成本", 0)
        gm = (rev - cost) / rev * 100 if rev > 0 else 0
        gm_list.append(gm)
    if len(gm_list) >= 3:
        gm_range = max(gm_list) - min(gm_list)
        if gm_range > 15 and max(gm_list) > 40:
            s = {"cat": "利润表", "name": "毛利率异常波动",
                 "severity": "🔴高", "score": 15,
                 "detail": f"最近 3 季度毛利率: {[round(x,1) for x in gm_list]} → 波动 {gm_range:.1f}pp"}
            result["signals"].append(s); result["score"] += 15

    # 1.4 利息收入异常低 (大存大贷信号)
    if interest_income < cash * 0.01:  # 利息收入 < 现金 * 1%
        s = {"cat": "利润表", "name": "利息收入远低于应有水平",
             "severity": "🟡中", "score": 8,
             "detail": f"货币资金={cash/1e8:.1f}亿, 利息收入={interest_income/1e8:.1f}亿 (应有 {cash*0.02/1e8:.1f}亿以上, 利率仅 {interest_income/cash*100:.2f}%)"}
        result["signals"].append(s); result["score"] += 8

    # 1.5 公允价值变动 / 投资收益占利润比例高
    if parent_net_profit > 0:
        non_op_profit = fair_value + invest_income
        if non_op_profit > parent_net_profit * 0.5:
            s = {"cat": "利润表", "name": "非经常性收益占利润 50%+",
                 "severity": "🔴高", "score": 15,
                 "detail": f"公允价值变动+投资收益={non_op_profit/1e8:.1f}亿, 归母净利润={parent_net_profit/1e8:.1f}亿"}
            result["signals"].append(s); result["score"] += 15

    # ═══════════════════════════════════════════════════════════════
    # 🔍 检测 2: 资产负债表异常
    # ═══════════════════════════════════════════════════════════════

    # 2.1 大存大贷 (货币资金多 + 短期借款多)
    if cash > 1e9 and short_loan > 1e9:
        if cash * 0.5 < short_loan:  # 借款 > 现金一半
            s = {"cat": "资产负债表", "name": "大存大贷 (高现金 + 高借款)",
                 "severity": "🔴高", "score": 20,
                 "detail": f"货币资金={cash/1e8:.1f}亿, 短期借款={short_loan/1e8:.1f}亿 → 利息收入/借款利息差额大"}
            result["signals"].append(s); result["score"] += 20

    # 2.2 应收账款占营收比例高 (虚增收入 / 压货)
    if rev_latest > 0 and ar > 0:
        ar_ratio = ar / rev_latest * 100
        if ar_ratio > 60:
            s = {"cat": "资产负债表", "name": "应收账款占营收比例过高",
                 "severity": "🔴高", "score": 15,
                 "detail": f"应收账款={ar/1e8:.1f}亿, 营收={rev_latest/1e8:.1f}亿 → 占比 {ar_ratio:.1f}% (应 < 30%)"}
            result["signals"].append(s); result["score"] += 15
        elif ar_ratio > 40:
            s = {"cat": "资产负债表", "name": "应收账款占营收比例偏高",
                 "severity": "🟡中", "score": 8,
                 "detail": f"应收账款={ar/1e8:.1f}亿, 营收={rev_latest/1e8:.1f}亿 → 占比 {ar_ratio:.1f}%"}
            result["signals"].append(s); result["score"] += 8

    # 2.3 应收账款增速 vs 营收增速 (最近 2 年年报)
    annual_rev_raw = annual["一、营业总收入"].tolist() if len(annual) >= 2 else []
    annual_rev = [_parse_amount(x) for x in annual_rev_raw]
    if len(annual_rev) >= 2 and annual_rev[1] > 0:
        rev_growth = (annual_rev[0] - annual_rev[1]) / annual_rev[1] * 100
        # 应收增速
        annual_bs = bs_df[bs_df["报告期"].str.endswith("-12-31")].head(3)
        if len(annual_bs) >= 2:
            ar_vals = [_parse_amount(x) for x in annual_bs["应收账款"].tolist()[:2]]
            if ar_vals[1] > 0:
                ar_growth = (ar_vals[0] - ar_vals[1]) / ar_vals[1] * 100
                if ar_growth > rev_growth + 20 and rev_growth > -10:
                    s = {"cat": "资产负债表", "name": "应收账款增速远超营收增速",
                         "severity": "🔴高", "score": 18,
                         "detail": f"应收增 {ar_growth:.1f}%, 营收增 {rev_growth:.1f}% → 差 {ar_growth-rev_growth:.1f}pp"}
                    result["signals"].append(s); result["score"] += 18

    # 2.4 在建工程长期不转固 (虚增资产 / 延迟折旧)
    if construction > 5e8 and fixed_assets > 0:
        const_ratio = construction / fixed_assets * 100
        if const_ratio > 30:
            s = {"cat": "资产负债表", "name": "在建工程占固定资产比例高",
                 "severity": "🟡中", "score": 10,
                 "detail": f"在建工程={construction/1e8:.1f}亿, 固定资产={fixed_assets/1e8:.1f}亿 → 占比 {const_ratio:.1f}% (应 < 20%)"}
            result["signals"].append(s); result["score"] += 10

    # 2.5 商誉占资产比例高 (并购虚高)
    if total_assets > 0 and goodwill > 0:
        gw_ratio = goodwill / total_assets * 100
        if gw_ratio > 20:
            s = {"cat": "资产负债表", "name": "商誉占资产比例过高",
                 "severity": "🔴高", "score": 15,
                 "detail": f"商誉={goodwill/1e8:.1f}亿, 总资产={total_assets/1e8:.1f}亿 → 占比 {gw_ratio:.1f}% (可能减值)"}
            result["signals"].append(s); result["score"] += 15
        elif gw_ratio > 10:
            s = {"cat": "资产负债表", "name": "商誉占资产比例偏高",
                 "severity": "🟡中", "score": 8,
                 "detail": f"商誉={goodwill/1e8:.1f}亿, 占资产 {gw_ratio:.1f}%"}
            result["signals"].append(s); result["score"] += 8

    # 2.6 其他应收款异常 (大股东占用)
    if other_recv > 1e8 and equity > 0:
        other_ratio = other_recv / equity * 100
        if other_ratio > 10:
            s = {"cat": "资产负债表", "name": "其他应收款占股东权益比例高",
                 "severity": "🟡中", "score": 10,
                 "detail": f"其他应收款={other_recv/1e8:.1f}亿, 股东权益={equity/1e8:.1f}亿 → 占比 {other_ratio:.1f}% (可能被大股东占用)"}
            result["signals"].append(s); result["score"] += 10

    # 2.7 存货增速异常 vs 营收
    if rev_latest > 0 and inventory > 0:
        inv_ratio = inventory / rev_latest * 100
        if inv_ratio > 50:
            s = {"cat": "资产负债表", "name": "存货占营收比例过高",
                 "severity": "🟡中", "score": 8,
                 "detail": f"存货={inventory/1e8:.1f}亿, 营收={rev_latest/1e8:.1f}亿 → 占比 {inv_ratio:.1f}% (应 < 30%)"}
            result["signals"].append(s); result["score"] += 8

    # ═══════════════════════════════════════════════════════════════
    # 🔍 检测 3: 现金流量表异常
    # ═══════════════════════════════════════════════════════════════

    # 3.1 经营现金流持续为负 (连续 3 个报告期)
    ocf_list = [_g(cf_df.iloc[i:i+1], "经营活动产生的现金流量净额", 0) for i in range(min(4, len(cf_df)))]
    negative_count = sum(1 for x in ocf_list if x < 0)
    if negative_count >= 3:
        s = {"cat": "现金流量表", "name": "经营现金流连续为负",
             "severity": "🔴高", "score": 20,
             "detail": f"最近 4 期经营现金流: {[round(x/1e8,1) for x in ocf_list]}亿 → {negative_count}/4 期为负"}
        result["signals"].append(s); result["score"] += 20

    # 3.2 销售商品现金流 vs 营收 (应 > 80%)
    if rev_latest > 0 and sales_cash > 0:
        sc_ratio = sales_cash / rev_latest * 100
        if sc_ratio < 60:
            s = {"cat": "现金流量表", "name": "销售回款率过低",
                 "severity": "🟡中", "score": 10,
                 "detail": f"销售回款={sales_cash/1e8:.1f}亿, 营收={rev_latest/1e8:.1f}亿 → 回款率 {sc_ratio:.1f}% (应 > 80%)"}
            result["signals"].append(s); result["score"] += 10

    # 3.3 投资现金流大额流出 vs 固定资产 / 在建工程
    # (已有在建工程检测覆盖)

    # ═══════════════════════════════════════════════════════════════
    # 🔍 检测 4: 综合交叉验证
    # ═══════════════════════════════════════════════════════════════

    # 4.1 净利润持续增长但 ROE 持续下降
    # (需要多期数据, 简化版: 近 3 季净利润)
    np_list = [_g(profit_df.iloc[i:i+1], "五、净利润", 0) for i in range(min(3, len(profit_df)))]
    if len(np_list) >= 3:
        # 检查净利润增长但现金流下降
        ocf_np_corr_ok = True
        for i in range(len(np_list)-1):
            if np_list[i] > np_list[i+1] and ocf_list[i] < ocf_list[i+1]:
                ocf_np_corr_ok = False

    # 4.2 资产减值损失 + 信用减值损失大额计提 (洗大澡)
    total_impairment = abs(impairment_loss) + abs(credit_impairment)
    if net_profit > 0 and total_impairment > net_profit * 0.5:
        s = {"cat": "综合验证", "name": "大额资产减值 / 信用减值计提",
             "severity": "🟡中", "score": 8,
             "detail": f"资产减值={impairment_loss/1e8:.1f}亿, 信用减值={credit_impairment/1e8:.1f}亿, 净利润={net_profit/1e8:.1f}亿 → 可能在洗大澡"}
        result["signals"].append(s); result["score"] += 8

    # 4.3 费用率异常下降 (延迟入账 / 资本化)
    total_expense = rd_expense + sales_expense + admin_expense + financial_expense
    if rev_latest > 0:
        expense_ratio = total_expense / rev_latest * 100
        if expense_ratio < 5:  # 四费加起来不到营收 5% → 不正常
            s = {"cat": "综合验证", "name": "费用率异常低",
                 "severity": "🟡中", "score": 8,
                 "detail": f"四费合计={total_expense/1e8:.1f}亿, 占营收 {expense_ratio:.1f}% (研发+销售+管理+财务)"}
            result["signals"].append(s); result["score"] += 8

    # ═══════════════════════════════════════════════════════════════
    # 📊 计算综合得分 & 风险评级
    # ═══════════════════════════════════════════════════════════════
    # score 0-100, 封顶
    raw_score = result["score"]
    result["score"] = min(raw_score, 100)

    if raw_score >= 60:
        result["risk_level"] = "🔴 极高风险"
        result["summary"] = f"⚠️ 检测到 {len(result['signals'])} 项高危信号, 综合风险分 {raw_score}/100 — 财务真实性存疑, 谨慎参与!"
    elif raw_score >= 40:
        result["risk_level"] = "🟠 高风险"
        result["summary"] = f"检测到 {len(result['signals'])} 项异常, 综合风险分 {raw_score}/100 — 需仔细核查报表附注"
    elif raw_score >= 20:
        result["risk_level"] = "🟡 中风险"
        result["summary"] = f"检测到 {len(result['signals'])} 项可疑信号, 综合风险分 {raw_score}/100 — 关注后续季报变化"
    elif raw_score >= 5:
        result["risk_level"] = "🟢 低风险"
        result["summary"] = f"信号较少 ({len(result['signals'])} 项), 综合风险分 {raw_score}/100 — 报表整体正常"
    else:
        result["risk_level"] = "✅ 基本正常"
        result["summary"] = f"未检测到明显异常, 综合风险分 {raw_score}/100 — 三大报表交叉验证通过"

    _log(f"✅ 分析完成: {result['risk_level']} ({raw_score}/100), {len(result['signals'])} 项信号")
    return result


# ═══════════════════════════════════════════════════════════════
# 🎨 K 线图弹窗内按钮 & 独立弹窗 (复用操盘阶段的队列架构)
# ═══════════════════════════════════════════════════════════════

class FinancialCheckMixin:
    """混入主程序, 提供 K 线图内财务检查功能"""

    def _open_financial_check_from_kline(self, stock_name, kline_data=None):
        """K 线图内 📒按钮 → 跑三大报表检测 → 弹窗显示结果"""
        import queue as _queue
        import akshare as ak
        import pandas as pd

        code6 = ""
        # 路径 1: kline_data 里的 code 字段
        if kline_data and kline_data.get("code"):
            m = re.search(r"(\d{6})", str(kline_data["code"]))
            if m:
                code6 = m.group(1)
        # 路径 2: stock_name 里直接带 code
        if not code6:
            m = re.search(r"(\d{6})", str(stock_name))
            if m:
                code6 = m.group(1)
        # 路径 3: 遍历所有持仓组, codes↔names 反查
        if not code6:
            try:
                for gi in range(1, 15):
                    codes = getattr(self, f"holding_stocks{'_'+str(gi) if gi>1 else ''}", []) or []
                    names = getattr(self, f"holding_labels{'_'+str(gi) if gi>1 else ''}", []) or []
                    if gi == 1:
                        codes = getattr(self, "holding_stocks", []) or []
                        names = getattr(self, "holding_labels", []) or []
                    for i, n in enumerate(names):
                        if str(n) == str(stock_name) and i < len(codes):
                            m = re.search(r"(\d{6})", str(codes[i]))
                            if m:
                                code6 = m.group(1); break
                    if code6: break
            except Exception:
                pass
        # 路径 4: 用 AKShare 反查 name→code (兜底, 联网)
        if not code6:
            try:
                df = ak.stock_zh_a_spot_em()
                m = df[df["名称"].astype(str) == str(stock_name)]
                if len(m) > 0:
                    code6 = str(m.iloc[0]["代码"]).zfill(6)
            except Exception:
                pass

        if not code6:
            tk.messagebox.showwarning("提示",
                f"无法识别 '{stock_name}' 的股票代码\n\n"
                f"请确保该股票在自选/持仓列表里, 或稍后重试 (AKShare 反查可能超时)",
                parent=getattr(self, "root", None))
            return

        # 弹窗
        dlg = tk.Toplevel(getattr(self, "root", None))
        dlg.title(f"📒 财务造假检测 — {stock_name}({code6})")
        dlg.geometry("720x640")

        # 顶栏
        top = tk.Frame(dlg, bg="#1565C0", height=48)
        top.pack(fill=tk.X)
        tk.Label(top, text=f"📒 财务造假检测  —  {stock_name} ({code6})",
                 font=("", 13, "bold"), bg="#1565C0", fg="white").pack(side=tk.LEFT, padx=12, pady=10)
        status_var = tk.StringVar(value="⏳ 拉取三大报表...")
        tk.Label(top, textvariable=status_var, bg="#1565C0", fg="white").pack(side=tk.RIGHT, padx=12)

        # 结果区
        body = tk.Frame(dlg)
        body.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)

        # 风险分数
        score_fr = tk.Frame(body, bg="#F5F5F5")
        score_fr.pack(fill=tk.X, pady=(0, 6))
        tk.Label(score_fr, textvariable=status_var, font=("", 12, "bold"),
                 bg="#F5F5F5", fg="#1565C0").pack(pady=10)

        # 信号列表
        sig_fr = tk.LabelFrame(body, text="🔍 异常信号", font=("", 11, "bold"),
                               bg="#F5F5F5")
        sig_fr.pack(fill=tk.BOTH, expand=True, pady=4)
        sig_text = scrolledtext.ScrolledText(sig_fr, font=("", 11), wrap=tk.WORD,
                                             height=16, state="disabled")
        sig_text.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        # 总结
        sum_fr = tk.LabelFrame(body, text="📊 总结", font=("", 11, "bold"),
                               bg="#F5F5F5")
        sum_fr.pack(fill=tk.X, pady=4)
        sum_lbl = tk.Label(sum_fr, text="", bg="#F5F5F5", fg="#333",
                           font=("", 11), wraplength=680, justify="left",
                           padx=8, pady=6)
        sum_lbl.pack(fill=tk.X)

        def _log(msg):
            try:
                status_var.set(msg)
                dlg.update_idletasks()
            except Exception:
                pass

        def _render(result):
            """在主线程渲染结果"""
            # 风险标题
            status_var.set(f"{result['risk_level']}  风险分 {result['score']}/100")
            fg = "#C62828" if result['score'] >= 60 else \
                 "#E65100" if result['score'] >= 40 else \
                 "#F57F17" if result['score'] >= 20 else "#2E7D32"
            tk.Label(score_fr, text=f"{result['risk_level']}   风险分 {result['score']}/100",
                     font=("", 18, "bold"), bg="#F5F5F5", fg=fg).pack(pady=8)

            # 总结
            sum_lbl.config(text=result["summary"])

            # 信号列表
            sig_text.config(state="normal")
            sig_text.delete("1.0", tk.END)
            if not result["signals"]:
                sig_text.insert(tk.END, "✅ 未检测到明显异常信号\n\n")
            else:
                # 按严重程度排序
                severity_order = {"🔴高": 0, "🟡中": 1, "🟢低": 2}
                signals = sorted(result["signals"],
                                 key=lambda s: severity_order.get(s["severity"], 99))
                for i, sig in enumerate(signals, 1):
                    cat = sig["cat"]
                    sev = sig["severity"]
                    name = sig["name"]
                    detail = sig["detail"]
                    score_plus = sig["score"]
                    sig_text.insert(tk.END,
                                    f"{'═'*60}\n"
                                    f"{i}. [{cat}] {sev} {name}\n"
                                    f"   加 {score_plus} 分\n"
                                    f"   {detail}\n\n")
            sig_text.config(state="disabled")

        # 后台线程跑分析
        def _worker():
            try:
                result = detect_financial_fraud(code6, name=str(stock_name), log_fn=_log)
            except Exception as e:
                import traceback
                traceback.print_exc()
                result = {
                    "score": 0, "risk_level": "❌ 分析失败",
                    "summary": f"异常: {e}", "signals": [], "data": {},
                    "code": code6, "name": stock_name,
                }
            if dlg.winfo_exists():
                dlg.after(0, lambda: _render(result))

        threading.Thread(target=_worker, daemon=True).start()
