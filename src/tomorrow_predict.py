#!/usr/bin/env python3
"""
明日涨跌预测打分 - 自持股监测专用
========================================
对最近9-10个交易日的涨跌幅数据打分，输出明日涨跌概率和操作建议。
可用于：
  1. 命令行单只票
  2. 命令行批量（从CSV/JSON）
  3. Python程序调用
  4. 集成到 stockyidong_project（见项目接入指南.md）
========================================
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass


# ============== 数据结构 ==============
@dataclass
class StockPredictInput:
    """输入：每只票的最近N日数据"""
    code: str
    name: str
    changes: list[float]   # 最近N日涨跌幅%，N=9或10
    total: float = 0.0     # 累计涨幅%
    ma10_dist: float | None = None  # 距10日线%


@dataclass
class StockPredictResult:
    """输出：每只票的预测结果"""
    code: str
    name: str
    score: float            # 综合得分 0-10
    signal: str             # 信号类型
    outlook: str            # 明日预期
    suggestion: str         # 操作建议
    confidence: float       # 信心度 0-1
    detail: dict            # 各维度明细
    last_change: float      # 昨日涨跌幅


# ============== 打分模型 ==============

def calc_total_pct(changes: list[float]) -> float:
    """根据每日涨跌幅反推累计涨幅（复利）"""
    cum = 1.0
    for c in changes:
        cum *= (1 + c / 100)
    return round((cum - 1) * 100, 2)


def score_total_pct(total: float) -> tuple[float, str]:
    """维度1：累计涨幅得分（0-10）
    
    评分逻辑：
    - 累计涨幅过高（>20%）：超买，次日容易回调
    - 累计涨幅过低（<-10%）：超卖，次日容易反弹
    - 累计涨幅适中（-5%~+15%）：健康
    """
    if total >= 30:
        return 3.0, "严重超买"
    elif total >= 20:
        return 4.5, "超买"
    elif total >= 10:
        return 7.0, "强势"
    elif total >= 0:
        return 8.5, "健康上行"
    elif total >= -5:
        return 9.0, "健康震荡"
    elif total >= -10:
        return 8.0, "超卖反弹区"
    elif total >= -15:
        return 6.5, "超卖"
    else:
        return 4.5, "深度超卖(但风险高)"


def score_consistency(changes: list[float]) -> tuple[float, str]:
    """维度2：上涨一致性（0-10）"""
    if not changes:
        return 5.0, "无数据"
    up_days = sum(1 for c in changes if c > 0)
    down_days = sum(1 for c in changes if c < 0)
    total = len(changes)
    consistency = up_days / total
    
    # 一致性高 + 向上 = 强势
    # 一致性高 + 向下 = 弱势
    # 一致性低 = 震荡
    if consistency >= 0.78:
        return 8.5, f"高一致性({up_days}/{total}涨)"
    elif consistency >= 0.6:
        return 7.5, f"较高一致性({up_days}/{total}涨)"
    elif consistency >= 0.45:
        return 6.0, f"中性({up_days}/{total}涨)"
    elif consistency >= 0.3:
        return 4.5, f"偏弱({up_days}/{total}涨)"
    else:
        return 3.0, f"弱势({up_days}/{total}涨)"


def score_last_change(last: float, total: float) -> tuple[float, str]:
    """维度3：昨日表现（0-10）
    
    关键场景：
    - 累计跌 + 昨日大涨 = 强反转信号
    - 累计涨 + 昨日温和续涨 = 延续
    - 累计涨 + 昨日滞涨/跌 = 见顶信号
    """
    if last >= 9.5:
        # 涨停或近涨停
        if total < -5:
            return 9.5, f"止跌反转(+{last:.1f}%)"
        elif total > 20:
            return 4.0, f"高位涨停(累计{total:+.1f}%)"
        else:
            return 8.0, f"强势涨停(+{last:.1f}%)"
    elif last >= 5:
        if total < 0:
            return 8.5, f"反弹启动(+{last:.1f}%)"
        elif total > 15:
            return 5.5, "加速上涨(注意超买)"
        else:
            return 7.5, f"强势上涨(+{last:.1f}%)"
    elif last >= 2:
        return 7.0, f"温和上涨(+{last:.1f}%)"
    elif last >= 0:
        return 6.0, f"微涨(+{last:.1f}%)"
    elif last >= -2:
        return 5.0, f"微跌({last:.1f}%)"
    elif last >= -5:
        return 4.0, f"下跌({last:.1f}%)"
    else:
        return 3.0, f"大跌({last:.1f}%)"


def score_trend_continuity(changes: list[float]) -> tuple[float, str]:
    """维度4：趋势持续性（0-10）
    
    用末段3天 vs 前段6天的方向对比判断
    """
    if len(changes) < 6:
        return 6.0, "数据不足"
    last3 = sum(changes[-3:])
    prev = sum(changes[:-3])
    diff = last3 - prev / 2  # 归一化到3天
    
    if last3 > 5 and diff > 0:
        return 8.5, f"加速上行(末3日+{last3:.1f}%)"
    elif last3 > 0 and diff > 0:
        return 7.0, "末段走强"
    elif last3 > 0 and diff < 0:
        return 6.0, "前弱后强"
    elif last3 < 0 and diff > 0:
        return 5.0, "前强后弱(注意)"
    elif last3 < 0 and diff < 0:
        return 3.5, "持续走弱"
    else:
        return 5.5, "震荡"


def score_ma10_dist(ma10_dist: float | None, total: float) -> tuple[float, str]:
    """维度5：距10日线偏离度（0-10）"""
    if ma10_dist is None:
        return 6.0, "无10日线数据"
    
    # 偏离10日线越远，回归概率越大
    if abs(ma10_dist) < 1.5:
        return 6.5, f"贴近10日线({ma10_dist:+.1f}%)"
    elif ma10_dist > 8:
        if total > 20:
            return 4.0, f"远离10日线({ma10_dist:+.1f}%,超买)"
        return 5.0, f"远离10日线({ma10_dist:+.1f}%)"
    elif ma10_dist > 4:
        return 5.5, f"高于10日线({ma10_dist:+.1f}%)"
    elif ma10_dist < -8:
        return 8.5, f"严重低于10日线({ma10_dist:+.1f}%,超卖反弹)"
    elif ma10_dist < -4:
        return 8.0, f"低于10日线({ma10_dist:+.1f}%,反弹机会)"
    else:
        return 7.0, f"略低于10日线({ma10_dist:+.1f}%)"


def classify_signal(total: float, last: float, up_days: int, total_days: int) -> str:
    """综合分类信号"""
    if total >= 20 and last > 0:
        return "🔥超买警惕"
    elif total >= 20 and last < 0:
        return "⚠️高位回调"
    elif total >= 10 and up_days / total_days >= 0.6:
        return "🟢强势持有"
    elif up_days / total_days >= 0.6 and total >= 0:
        return "🟢稳健上行"
    elif total < -5 and last >= 5:
        return "🟡止跌反弹"
    elif total < -5 and last < 0:
        return "🔴弱势回避"
    elif up_days / total_days <= 0.4 and total < 0:
        return "🟡震荡偏弱"
    else:
        return "⚪震荡"


def gen_suggestion(score: float, signal: str) -> str:
    """根据得分和信号给出操作建议"""
    if "超买" in signal:
        return "建议减仓/止盈"
    elif "回调" in signal:
        return "建议减仓观望"
    elif "强势" in signal:
        return "可继续持有"
    elif "稳健" in signal:
        return "安心持有"
    elif "止跌" in signal:
        return "可轻仓试多"
    elif "弱势" in signal:
        return "建议回避"
    elif "震荡" in signal:
        if score >= 6.5:
            return "持有观望"
        else:
            return "观望为主"
    else:
        return "观望"


def calc_confidence(changes: list[float]) -> float:
    """信心度：基于数据质量"""
    if not changes:
        return 0.0
    # 数据越完整、波动越小，信心度越高
    base = min(len(changes) / 9, 1.0)
    abs_vals = [abs(c) for c in changes]
    avg_abs = sum(abs_vals) / len(abs_vals)
    # 平均日波动 < 3% 表示稳定
    stability = max(0, 1 - avg_abs / 15)
    return round(base * 0.5 + stability * 0.5, 2)


# ============== 主函数 ==============

def predict_tomorrow(stock: StockPredictInput) -> StockPredictResult:
    """预测单只票的明日涨跌"""
    changes = stock.changes
    if not changes:
        return StockPredictResult(
            code=stock.code, name=stock.name,
            score=5.0, signal="⚪无数据", outlook="无法预测",
            suggestion="数据不足", confidence=0.0,
            detail={}, last_change=0.0
        )
    
    total = stock.total if stock.total != 0 else calc_total_pct(changes)
    last = changes[-1]
    up_days = sum(1 for c in changes if c > 0)
    total_days = len(changes)
    
    # 各维度打分
    s1, c1 = score_total_pct(total)
    s2, c2 = score_consistency(changes)
    s3, c3 = score_last_change(last, total)
    s4, c4 = score_trend_continuity(changes)
    s5, c5 = score_ma10_dist(stock.ma10_dist, total)
    
    # 加权综合
    weights = [0.30, 0.20, 0.20, 0.20, 0.10]
    scores = [s1, s2, s3, s4, s5]
    final_score = sum(s * w for s, w in zip(scores, weights))
    final_score = round(final_score, 2)
    
    # 信号
    signal = classify_signal(total, last, up_days, total_days)
    
    # 明日预期
    if final_score >= 8.0:
        outlook = "🟢强烈看涨"
    elif final_score >= 6.5:
        outlook = "🟢看涨"
    elif final_score >= 5.5:
        outlook = "⚪震荡偏多"
    elif final_score >= 4.5:
        outlook = "🟡震荡偏空"
    elif final_score >= 3.5:
        outlook = "🟠看跌"
    else:
        outlook = "🔴强烈看跌"
    
    # 建议
    suggestion = gen_suggestion(final_score, signal)
    
    # 信心度
    confidence = calc_confidence(changes)
    
    detail = {
        "累计涨幅得分": (s1, c1),
        "上涨一致性得分": (s2, c2),
        "昨日表现得分": (s3, c3),
        "趋势持续性得分": (s4, c4),
        "距10日线得分": (s5, c5),
        "总累计涨幅": f"{total:+.2f}%",
        "上涨天数": f"{up_days}/{total_days}",
        "波动率": f"{sum(abs(c) for c in changes)/len(changes):.2f}%",
    }
    
    return StockPredictResult(
        code=stock.code, name=stock.name,
        score=final_score, signal=signal,
        outlook=outlook, suggestion=suggestion,
        confidence=confidence, detail=detail,
        last_change=last
    )


def batch_predict(stocks: list[StockPredictInput]) -> list[StockPredictResult]:
    """批量预测"""
    results = [predict_tomorrow(s) for s in stocks]
    # 按得分降序
    results.sort(key=lambda x: x.score, reverse=True)
    return results


# ============== CLI ==============

def _print_table(results: list[StockPredictResult]):
    """打印表格"""
    print(f"\n{'='*100}")
    print(f"{'代码':<10}{'名称':<12}{'得分':<8}{'信号':<14}{'明日预期':<14}{'建议':<14}{'昨日':<8}{'信心度':<8}")
    print(f"{'='*100}")
    for r in results:
        print(f"{r.code:<10}{r.name:<12}{r.score:>5.1f}  {r.signal:<14}{r.outlook:<14}{r.suggestion:<14}{r.last_change:>+6.2f}%  {r.confidence:>5.0%}")
    print(f"{'='*100}")
    
    # Top5 看涨
    print("\n🟢 明日最可能涨 (Top5):")
    for r in results[:5]:
        print(f"  {r.code} {r.name:<10} 得分{r.score:.1f}  {r.outlook}  {r.suggestion}")
    
    # Top5 看跌
    print("\n🔴 明日最可能跌 (Top5):")
    for r in results[-5:]:
        print(f"  {r.code} {r.name:<10} 得分{r.score:.1f}  {r.outlook}  {r.suggestion}")


def main():
    """命令行入口"""
    import argparse
    parser = argparse.ArgumentParser(description='明日涨跌预测 - 自持股监测专用')
    parser.add_argument('--code', help='股票代码')
    parser.add_argument('--name', help='股票名称')
    parser.add_argument('--changes', help='9-10日涨跌幅，逗号分隔，例如 "4.87,1.94,-2.87,-1.31,-0.46,-9.78,2.67,2.75,20.01"')
    parser.add_argument('--total', type=float, default=0, help='累计涨幅%（可选，不填则自动计算）')
    parser.add_argument('--ma10', type=float, default=None, help='距10日线%（可选）')
    parser.add_argument('--csv', help='从CSV批量预测，列：code,name,changes(分号分隔)')
    parser.add_argument('--json', help='从JSON批量预测')
    parser.add_argument('--output', help='输出到JSON文件')
    args = parser.parse_args()
    
    stocks = []
    if args.csv:
        with open(args.csv, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                changes = [float(x.strip()) for x in row['changes'].split(';') if x.strip()]
                stocks.append(StockPredictInput(
                    code=row['code'], name=row['name'],
                    changes=changes,
                    total=float(row.get('total', 0) or 0),
                    ma10_dist=float(row['ma10']) if row.get('ma10') else None
                ))
    elif args.json:
        with open(args.json, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for item in data:
            stocks.append(StockPredictInput(**item))
    elif args.code and args.changes:
        changes = [float(x.strip()) for x in args.changes.split(',') if x.strip()]
        stocks.append(StockPredictInput(
            code=args.code, name=args.name or args.code,
            changes=changes, total=args.total, ma10_dist=args.ma10
        ))
    else:
        parser.print_help()
        print('\n示例:')
        print('  python3 tomorrow_predict.py --code 300598 --name 诚迈科技 --changes "4.87,1.94,-2.87,-1.31,-0.46,-9.78,2.67,2.75,20.01" --total 1.61 --ma10 0.38')
        return
    
    results = batch_predict(stocks)
    _print_table(results)
    
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump([asdict(r) for r in results], f, ensure_ascii=False, indent=2)
        print(f"\n结果已保存到: {args.output}")


if __name__ == '__main__':
    main()
