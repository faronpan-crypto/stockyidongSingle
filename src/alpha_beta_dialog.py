#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
α/β 阿尔法贝塔配置参考 + 实时数据工作台 (alpha_beta_dialog.py)
独立子程序，可由 stockyidong mac.py 主程序按钮调用，也可单独运行。
功能：
  1. 概念定义 / 配置框架 / 风控清单（参考手册）
  2. 实时数据工具：指数对比、个股β计算器、ETF扫描
依赖：tkinter, akshare, pandas, numpy（可选，缺失时数据工具自动降级）
"""
import os
import sys
import math
import threading
import time
import datetime as _dt
import tkinter as tk
import tkinter.messagebox as _mb
from tkinter import ttk, scrolledtext

# ---------- 可选依赖 ----------
HAS_AK = False
HAS_PD = False
HAS_NP = False
try:
    import akshare as _ak; HAS_AK = True
except Exception:
    _ak = None
try:
    import pandas as _pd; HAS_PD = True
except Exception:
    _pd = None
try:
    import numpy as _np; HAS_NP = True
except Exception:
    _np = None

# ---------- 样式（匹配主程序 dark 主题）----------
FONT_TITLE  = ("Microsoft YaHei", 14, "bold")
FONT_SECTION = ("Microsoft YaHei", 12, "bold")
FONT_CONTENT = ("Microsoft YaHei", 11)
FONT_BTN    = ("Microsoft YaHei", 11, "bold")
FONT_TAB    = ("Microsoft YaHei", 12, "bold")
COLOR_BG     = "#1A1A2E"
COLOR_PANEL  = "#ECEFF1"   # 浅灰工具面板
COLOR_CARD   = "#FFFFFF"
COLOR_FG     = "#E0E0E0"
COLOR_DARK   = "#263238"
COLOR_ACCENT = "#FFD700"   # 金
COLOR_ALPHA  = "#E53935"   # 红 α
COLOR_BETA   = "#1E88E5"   # 蓝 β
COLOR_WARN   = "#FF6F00"
COLOR_UP     = "#E53935"   # 涨=红
COLOR_DOWN   = "#43A047"   # 跌=绿


# ============================================================================
# 静态内容（参考手册）
# ============================================================================

CONCEPT_TEXT = """
╔══════════════════════════════════════════════════════════════╗
║  📐 CAPM 底层框架                                            ║
║     总收益 = β 收益 + α 收益 + 残余波动                      ║
╚══════════════════════════════════════════════════════════════╝

🔵 β（贝塔）— 市场给你的钱（顺水推舟）
─────────────────────────────────────
  · 跟随指数或赛道获得的系统性收益
  · 不需要你比市场聪明，方向对了就赚
  · 基准指数的 β = 1.0（宽基 ETF 的 β）

    β > 1   → 进攻型（成长、周期、高波动）
    β ≈ 1   → 与指数同步（纯宽基）
    β < 1   → 防御型（红利、公用事业）
    β ≈ 0   → 与市场无关（债券、量化中性）
    β < 0   → 与市场反向（避险资产如黄金/国债）

🔴 α（阿尔法）— 你自己赚的能力钱（认知变现）
─────────────────────────────────────
  · 超出基准（经风险调整）的超额收益
  · 来自深度研究、精准择股、动态交易
  · Jensen's Alpha:  α = R − Rf − β(Rm − Rf)
    R = 组合收益  Rf = 无风险利率  Rm = 市场收益

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 一句话本质：β 不需要你比市场聪明；α 需要。
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ 常见陷阱
──────────
  1. 贝塔幻觉：上行周期里 β 的涨幅让你误以为自己有 α
  2. 伪 α 陷阱：短期高 α 只是踩中风口，并非持续能力
  3. 费用吞噬：α=2% 但费用 1.5% → 到手仅 0.5%
  4. 最典型亏损：用 β 逻辑买入、用 α 逻辑持有（周期一转露馅）

📊 工具映射
──────────
  宽基 ETF        → 纯 β
  主动权益基金    → β + α（核心看 α 是否稳定为正）
  量化指数增强    → β（跟随指数）+ α（因子/量价）
  量化中性/对冲   → 纯 α（剥离 β）
  聪明 β          → 风格因子 β（低波、红利、质量）
"""

FRAMEWORK_TEXT = """
╔══════════════════════════════════════════════════════════════╗
║  🏗️ 核心-卫星模型（主推配置框架）                            ║
╚══════════════════════════════════════════════════════════════╝

  ┌─────────────────────────────────────────────┐
  │  核心仓 60–80%   (β 打底)                    │
  │  ├─ 宽基指数 ETF (沪深300 / A500 / 2000)    │
  │  ├─ 红利低波 ETF (防御压舱石)               │
  │  └─ 少量债券 / 黄金 (低相关、控波动)        │
  │  作用：压舱石，不踏空市场，控制波动          │
  ├─────────────────────────────────────────────┤
  │  卫星仓 20–40%   (α 进攻)                    │
  │  ├─ 量化指增 (抓因子α)                      │
  │  ├─ 长期 α 稳定的主动权益基金               │
  │  └─ 行业 / 风格增强 (精选个股)              │
  │  作用：博取超额，增厚回报                    │
  └─────────────────────────────────────────────┘

🔄 动态再平衡
──────────
  · 市场越涨 → 卫星浮盈移回核心（锁定 α）
  · 大跌 → 核心占比下降 → 加回卫星（捡便宜 α）
  · 季度/半年度调仓；不追高、不恐慌割肉

🌲 决策树
──────────
  选 β 只问一个问题：周期在哪里？
  → 判断周期位置 → 设退出触发 → 控仓位承受中途高波动

  选 α 看三件事：
  ① 长期（3–5 年）超额是否稳定为正？
  ② 风格是否漂移？（从价值转向成长 → 可能是追热点）
  ③ 费用是否吞掉超额？

  避开：短期冠军基金、热点基金、风格漂移的经理

📈 进阶：风险平价 + 主动 α
──────────
  · 股票/债券/商品按波动率定中枢仓位（对组合风险贡献均衡）
  · α 部分围绕中枢做超配/低配，但主动偏离受比例上限约束
  · 波动率飙升时先降该类资产比例，再降整体杠杆
"""

CONFIG_TEXT = """
╔══════════════════════════════════════════════════════════════╗
║  📅 当前时点配置建议（2026年9月下旬–四季度）                  ║
╚══════════════════════════════════════════════════════════════╝

🌍 市场环境快照
──────────────
  · 上证 3952 站稳 3900，成交连续 2 万亿+
  · 美联储 9/16 加息 25bp → 3.75–4.00%（外部流动性收紧）
  · 10Y 美债破 5%，CME 定价 10 月再加息 49.8%
  · 机构共识：攻守均衡、风格再平衡
  · 行情重心从「板块 β」转向「个股 α」

🔵 β 配置（赚市场/风格的钱）
─────────────────────────────
  ① 宽基 β
     沪深 300 / 中证 A500 → 机构低配、有修复空间
     中证 2000            → 高弹性

  ② 防御 β（底仓必备）
     红利低波 ETF、银行/煤炭/公用事业/高股息

  ③ 顺周期 β
     地产链/基建链/有色/基础化工/钢铁

  ④ 产业 β
     AI 算力链（半导体设备、通信、光通信/PCB/液冷）
     上游有色新材料

🔴 α 配置（赚能力的钱）
─────────────────────────────
  量化指增性价比排序（2026 前 7 月数据）：

  🥇 中证 2000 指增   平均超额 +7.37%  ←「α 之王」
  🥈 沪深 300 指增    平均超额 +3.79%
  中证 A500 / 中证 1000 指增 → 机构认为更有性价比
  ⚠️ 中证 500 指增    平均超额 −0.99%  ← 红海，谨慎！

  📌 注：2026 上半年私募量化多头平均收益 16.25%
        但超额仅 3.11%（去年同期 14.17%）
        → α 获取难度显著增大
        → 百亿以上管理人因算力/投研储备反而超额更稳

💼 组合示例（核心-卫星，权益账户）
─────────────────────────────
  📦 核心仓 70%（β 打底）
  ├─ 沪深 300 ETF          30%
  ├─ 红利低波 ETF          25%
  └─ 中证 A500 ETF         15%

  🚀 卫星仓 30%（α 进攻）
  ├─ 中证 2000/沪深 300 指增   15%
  ├─ 长期 α 稳定的主动基金      10%
  └─ 黄金 ETF / 量化对冲基金    5%
"""

RISK_TEXT = """
╔══════════════════════════════════════════════════════════════╗
║  🛡️ 风控纪律 — 结合既有交易纪律                             ║
╚══════════════════════════════════════════════════════════════╝

❌ 绝对禁止
──────────
  1. 回避年内涨幅 >100% 的标的 → 高 β 在周期末端最危险
  2. 回避处于 P3 出货区的标的
  3. 不追利好涨停板，等回踩第二波产业逻辑

⚠️ 高度警惕
──────────
  1. 中秋国庆节前降低高 β 暴露 → 防交易型资金避险收缩
  2. 量化超额收窄期（当前）→ 降低对纯 α 的预期
  3. 贝塔幻觉最危险 → 上行周期的 β 涨幅会让你误判自己有 α

📡 持续跟踪
──────────
  1. 10 月底 FOMC 议息会议
  2. 美债 10Y 收益率（是否突破 5%）
  3. 国际油价走势
  4. 外部流动性是 β 的主要逆风

📋 退出触发清单
─────────────────────────────
  · 宽基 β：跌破 MA60 → 减仓 30%
  · 顺周期 β：大宗商品连续 3 日暴跌 → 平仓
  · 产业 β：龙头股跌破 20 日均线且放量
  · α 基金：连续 3 个月跑输基准 5%+ → 换经理
  · 组合整体：从历史高点回撤 >15% → 全转国债 ETF，空仓 1 个月

🎯 情景应对
─────────────────────────────
  · FOMC 加息超预期 → 降 β 到 50%，增配防御 β（红利）
  · 美债 10Y 破 5.2% → 减成长 β，加黄金/国债
  · A 股放量突破 4000 → β 加仓至 80%（不加高 β 个股）
  · 量化超额进一步收窄 → 卫星仓 80% 转纯 β
"""


# ============================================================================
# 研读区内容（右侧面板）
# ============================================================================

CASE_TEXT = """
╔══════════════════════════════════════════════════════════════╗
║  🏆 α/β 成功案例 — 用 β 搭台、α 唱戏                        ║
╚══════════════════════════════════════════════════════════════╝

① 桥水基金 (Ray Dalio) · 风险平价 + α
─────────────────────────────────────
  核心：股票 / 债券 / 商品 / 外汇 按波动率配平 (β 打底)
  α：Pure Alpha 策略 (主动偏离中枢仓位)
  结果：穿越 2008 年金融危机 (当年仅 −4%)
  启示：β 定中枢 + α 小偏离，不靠大方向吃满

② 文艺复兴 Medallion (Jim Simons) · 纯 α 量化
─────────────────────────────────────
  β ≈ 0 (剥离市场)，纯靠高频量价信号
  年化 66% (1988–2023)，费用 5% + 44% 业绩
  启示：真·α 极其稀少，费用也极其昂贵

③ 耶鲁捐赠基金 (David Swensen) · 另类资产 α
─────────────────────────────────────
  股票 30% / 固定收益 10% / PE 20% / 对冲基金 20% / 实物 20%
  60 年长期年化 13.1%，远高于 60/40 基准
  启示：β 打底 + 另类资产 α (PE/实物/对冲) 增厚

④ 先锋基金 John Bogle · 纯 β 信仰
─────────────────────────────────────
  "不要寻找 α，低成本持有全市场 β"
  先锋指数基金把 β 的费用降到 0.03%，跑赢 90% 主动基金
  启示：多数人不需要 α，低成本 β 已经够用

⑤ 国内私募：幻方 / 九坤 (中性策略) · 纯 α 剥离 β
─────────────────────────────────────
  中证 500 中性：多头量化选股 + 空头股指期货
  年化 β ≈ 0，α 约 8–15%
  启示：在震荡市尤其有价值，牛市可能跑输宽基

⑥ 国内量化指增：天弘 / 嘉实 / 招商
─────────────────────────────────────
  中证 2000 指增超额 +7.37% (2026 前 7 月, 据需求文档)
  沪深 300 指增超额 +3.79%
  中证 500 指增 −0.99% (红海拥挤)
  启示：α 之王在小市值，红海在中盘
"""

BOOK_TEXT = """
╔══════════════════════════════════════════════════════════════╗
║  📚 α/β 相关书籍 — 从入门到进阶                              ║
╚══════════════════════════════════════════════════════════════╝

【入门】
──────────────────────────────────────────────────────
  《漫步华尔街》(A Random Walk Down Wall Street)
  Burton G. Malkiel
  · 第 1 章就讲 CAPM / α / β
  · 用通俗故事讲清有效市场、指数基金、主动管理
  · 推荐：先读第 1–4 章建立框架，后面跳读

  《投资最重要的事》(The Most Important Thing)
  Howard Marks (橡树资本创始人)
  · 不直接讲 α/β，但讲清"风险"是 β 的同义词
  · "第二层思维"就是获取 α 的能力
  · 推荐：全书慢读，每章都有金句

【进阶】
──────────────────────────────────────────────────────
  《主动投资的主动失败》(Active Portfolio Management)
  Grinold & Kahn (BGI/BlackRock)
  · 机构级 α/β 配置实战手册
  · 信息比率 (IR) / 基本法则 / 因子投资
  · 推荐：如果做专业投资，这是圣经

  《聪明的 α 与 β 策略》(Smart Beta)
  Rob Arnott (Research Affiliates)
  · 风格因子 β 不是 α！
  · 低波 / 红利 / 价值 / 动量 都是"聪明 β"
  · 推荐：想做 ETF 轮动必读

  《量化投资：如何建立自己的算法交易事业》
  Ernest P. Chan
  · 用 Python + numpy 实现 β 对冲 / 配对交易
  · 第 8 章：CAPM 回归与 α 因子
  · 推荐：程序员视角，代码可跑

【高阶】
──────────────────────────────────────────────────────
  《风险平价》(Risk Parity)
  Edward Qian (PanAgora)
  · 桥水 All Weather 的数学基础
  · 用波动率平衡组合风险，而非资金平衡
  · 推荐：想做全球配置必读

  《因子投资：方法与实践》
  石川 / 刘洋溢 / 连祥
  · 国内团队写的因子教科书
  · A 股有效因子：价值 / 质量 / 动量 / 低波 / 小盘
  · 推荐：本土因子 α 获取路径

  《对冲基金风云录》(Hedge Fund Mirage)
  Aaron Brown (Renaissance)
  · 文艺复兴内部人写的 α 真实面目
  · 量化 α 的技术壁垒和人才门槛
  · 推荐：打消"我也能搞量化"的幻想
"""

INST_TEXT = """
╔══════════════════════════════════════════════════════════════╗
║  🏦 顶级机构的 α/β 配置范式                                  ║
╚══════════════════════════════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
① 桥水 Bridgewater (全球最大对冲基金, 2500 亿美元)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  📦 All Weather 全天候组合:
     股票 30% · 中长债 40% · 通胀债券 15% · 黄金 8% · 商品 7%
  🎯 核心思路: 风险平价 (各资产对整体波动贡献均衡)
  ⚠️ α 部分: Pure Alpha 策略 (主动偏离中枢 + 杠杆)
  🔑 启示: 不赌方向，β 打底 + 小比例 α 杠杆增厚

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
② 耶鲁捐赠基金 Yale Endowment (长期年化 13.1%)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  📦 核心-卫星-另类三层:
     股票 30% · 固收 10% (β 打底)
     对冲基金 20% · PE 20% · VC 10% · 实物 10% (α 进攻)
  🎯 核心思路: PE/实物/对冲 = 低 β + 高 α
  🔑 启示: 60/40 已过时，另类资产是 α 主战场

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
③ 先锋基金 Vanguard (低成本 β 之王)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  📦 纯 β 组合:
     Total Stock Fund (美股全市场) + Total Intl + Total Bond
  🎯 核心思路: α 幻觉 + 费用侵蚀 = 主动基金必然输
  🔑 启示: 普通人最佳策略，年费 0.03% 起步

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
④ 文艺复兴 Renaissance Technologies (纯 α 量化)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  📦 Medallion 基金:
     高频量价信号 (β ≈ 0) + 全球期货/股票/期权
  🎯 核心思路: 剥离所有可对冲 β，纯靠信号 α
  ⚠️ 费用 5% 固定 + 44% 业绩分红
  🔑 启示: 真·α 极度稀缺，也极度昂贵

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⑤ A 股头部量化私募 (幻方 / 九坤 / 明汯 / 灵均)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  📦 中证 500 / 1000 中性策略:
     多头量化选股 + 空头股指期货对冲 (β ≈ 0)
  🎯 核心思路: 因子 α (价值/动量/质量/成长/情绪)
  📊 历史年化: 15–25% (2018–2023)，超额 8–15%
  🔑 启示: A 股小市值定价效率低，α 获取窗口仍存在

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⑥ 核心-卫星标准配置模板 (个人/小机构通用)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  📦 核心 60–70% (β 打底):
     宽基 ETF (沪深300/中证A500/中证2000) 40%
     红利低波 ETF 20%
  🚀 卫星 30–40% (α 进攻):
     量化指增 (场外) 15%
     长期 α 主动基金 10%
     黄金/量化对冲 5%
  ⚠️ 再平衡: 季度检查，卫星浮盈移回核心
"""

LINKS = """
╔══════════════════════════════════════════════════════════════╗
║  🔗 α/β 学习资源 — 网址链接 (点击可打开)                     ║
╚══════════════════════════════════════════════════════════════╝

━━━ 学术 / 理论 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📄 CAPM 原论文 (Sharpe, 1964)
  https://doi.org/10.1111/j.1540-6261.1964.tb02865.x

📄 Fama-French 三因子 / 五因子模型
  https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html

📄 AQR 聪明 β (Smart Beta) 白皮书
  https://www.aqr.com/Insights/Research/White-Papers

━━━ 数据 / 工具 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 akshare (A股 ETF/指数数据, 本程序用的库)
  https://github.com/akfamily/akshare

📊 tushare (A股历史行情)
  https://tushare.pro

📊 ETFrun (全球 ETF 全景 + α/β 指标)
  https://etfrun.com

📊 天天基金网 (国内量化指增基金查询)
  https://fund.eastmoney.com

━━━ 机构公开报告 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🏦 桥水 All Weather 组合白皮书
  https://www.bridgewater.com/research-and-insights

🏦 Vanguard 指数基金 vs 主动基金研究
  https://www.vanguard.ca/en/advisor/advisor-essentials

🏦 富达 Fidelity α/β 资产配置指南
  https://www.fidelity.com/learning-center/trading-investing

━━━ 中文学习社区 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💬 雪球量化投资 (因子/α 实战)
  https://xueqiu.com/hq/qmt

💬 集思录 (ETF/LOF/量化)
  https://www.jisilu.cn

💬 巴比特量化 (crypto 量化, 跨市场 α)
  https://www.8btc.com

━━━ 本程序自带工具 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🛠️ β 计算器 (CAPM 回归) → 「🔧 数据工具」Tab
🛠️ 指数表现对比 → 「🔧 数据工具」Tab
🛠️ ETF 实时扫描 → 「🔧 数据工具」Tab
"""


# ============================================================================
# akshare 工具函数（带重试 + 降级）
# ============================================================================

def _ak_retry(fn, *args, retries=3, sleep=2, **kwargs):
    """重试包装器"""
    if not HAS_AK:
        raise RuntimeError("akshare 未安装")
    last_err = None
    for i in range(retries):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            last_err = e
            if i < retries - 1:
                time.sleep(sleep)
    raise last_err


# 指数代码映射：(akshare symbol, 中文名, 基准类型)
INDEX_MAP = [
    ("000300", "沪深300", "宽基β"),
    ("000905", "中证500", "中盘β"),
    ("000852", "中证1000", "小盘β"),
    ("932000", "中证A500", "宽基β"),
    ("932000", "中证2000", "小盘β"),  # akshare 中证2000 实际可能用 932000
    ("000016", "上证50", "大盘β"),
    ("000688", "科创50", "产业β"),
    ("399006", "创业板指", "成长β"),
]

# ETF 关键词过滤（fund_etf_spot_em 返回后按名称筛选）
ETF_TAGS = {
    "宽基β": ["沪深300", "中证500", "中证1000", "中证A500", "中证2000", "上证50", "创业板ETF"],
    "防御β": ["红利", "低波", "银行ETF", "煤炭ETF", "公用事业"],
    "顺周期β": ["有色", "基建", "地产", "化工ETF", "钢铁ETF"],
    "产业β": ["半导体", "芯片", "AI", "算力", "光通信", "PCB"],
    "避险": ["黄金ETF", "国债ETF", "中证转债"],
}


def fetch_index_performance(symbols=None, days=60, progress_cb=None):
    """拉取多个指数的近 N 天涨跌幅，返回 list[dict]"""
    results = []
    end = _dt.date.today().strftime("%Y%m%d")
    start = (_dt.date.today() - _dt.timedelta(days=days + 30)).strftime("%Y%m%d")

    target_symbols = symbols or [s for s, _, _ in INDEX_MAP]
    seen = set()
    for ak_sym, cn_name, tag in INDEX_MAP:
        if ak_sym not in target_symbols or ak_sym in seen:
            continue
        seen.add(ak_sym)
        if progress_cb:
            progress_cb(f"拉取 {cn_name} ...")
        try:
            df = _ak_retry(_ak.index_zh_a_hist, symbol=ak_sym, period="daily",
                           start_date=start, end_date=end)
            if df is None or len(df) < 2:
                continue
            close_col = [c for c in df.columns if "收盘" in str(c) or "close" in str(c).lower()][0]
            close = df[close_col].astype(float).values
            today = close[-1]
            chg_1d = (close[-1] / close[-2] - 1) * 100 if len(close) >= 2 else 0
            chg_5d = (close[-1] / close[-6] - 1) * 100 if len(close) >= 6 else 0
            chg_20d = (close[-1] / close[-21] - 1) * 100 if len(close) >= 21 else 0
            chg_60d = (close[-1] / close[-61] - 1) * 100 if len(close) >= 61 else 0
            results.append({
                "code": ak_sym, "name": cn_name, "tag": tag,
                "close": round(today, 2),
                "chg_1d": round(chg_1d, 2),
                "chg_5d": round(chg_5d, 2),
                "chg_20d": round(chg_20d, 2),
                "chg_60d": round(chg_60d, 2),
            })
        except Exception as e:
            results.append({
                "code": ak_sym, "name": cn_name, "tag": tag,
                "close": None, "chg_1d": None, "chg_5d": None,
                "chg_20d": None, "chg_60d": None,
                "err": str(e)[:60],
            })
    return results


def fetch_etf_scan(progress_cb=None):
    """拉取 ETF 实时行情，按 ETF_TAGS 分类筛选"""
    if progress_cb:
        progress_cb("拉取全市场 ETF 行情 ...")
    df = _ak_retry(_ak.fund_etf_spot_em)
    if df is None or len(df) == 0:
        return {}
    name_col = [c for c in df.columns if "名称" in str(c)][0]
    code_col = [c for c in df.columns if "代码" in str(c)][0]
    price_col = [c for c in df.columns if "最新价" in str(c) or "现价" in str(c)]
    pct_col = [c for c in df.columns if "涨跌幅" in str(c)]
    chg_col = [c for c in df.columns if "涨跌额" in str(c)]
    vol_col = [c for c in df.columns if "成交额" in str(c)]

    price_col = price_col[0] if price_col else None
    pct_col = pct_col[0] if pct_col else None
    chg_col = chg_col[0] if chg_col else None
    vol_col = vol_col[0] if vol_col else None

    grouped = {}
    for tag, keywords in ETF_TAGS.items():
        rows = []
        for _, r in df.iterrows():
            name = str(r[name_col])
            if any(kw in name for kw in keywords):
                rows.append({
                    "code": str(r[code_col]),
                    "name": name,
                    "price": float(r[price_col]) if price_col and r[price_col] else None,
                    "pct": float(r[pct_col]) if pct_col and r[pct_col] else None,
                    "volume": float(r[vol_col]) if vol_col and r[vol_col] else None,
                })
        grouped[tag] = sorted(rows, key=lambda x: -(x["volume"] or 0))[:20]
    return grouped


def compute_beta(stock_code, benchmark_code="000300", days=250, progress_cb=None):
    """计算个股/ETF 的 β 值（CAPM 回归）
    参数:
        stock_code: 个股代码如 '600519' 或 ETF 代码如 '510300'
        benchmark_code: 基准指数代码如 '000300' (沪深300)
        days: 回归天数，默认 250（约一年）
    返回: dict {beta, alpha, r_squared, vol_stock, vol_bench, data_points}
    """
    if progress_cb:
        progress_cb(f"拉取 {stock_code} 日K ...")
    end = _dt.date.today().strftime("%Y%m%d")
    start = (_dt.date.today() - _dt.timedelta(days=days + 60)).strftime("%Y%m%d")

    # 拉取个股/ETF 数据
    try:
        # 先试 ETF
        df_stock = None
        try:
            df_stock = _ak_retry(_ak.fund_etf_hist_em, symbol=stock_code, period="daily",
                                 start_date=start, end_date=end, adjust="qfq")
        except Exception:
            pass
        if df_stock is None or len(df_stock) < 30:
            # 试个股
            df_stock = _ak_retry(_ak.stock_zh_a_hist, symbol=stock_code, period="daily",
                                 start_date=start, end_date=end, adjust="qfq")
    except Exception as e:
        raise RuntimeError(f"拉取 {stock_code} 数据失败: {e}")

    if progress_cb:
        progress_cb(f"拉取基准 {benchmark_code} 日K ...")
    try:
        df_bench = _ak_retry(_ak.index_zh_a_hist, symbol=benchmark_code, period="daily",
                             start_date=start, end_date=end)
    except Exception as e:
        raise RuntimeError(f"拉取基准 {benchmark_code} 失败: {e}")

    # 提取收盘价
    def _close(df):
        cols = [c for c in df.columns if "收盘" in str(c) or "close" in str(c).lower()]
        if not cols:
            raise RuntimeError("找不到收盘价列")
        return df[cols[0]].astype(float).values

    s = _close(df_stock)
    b = _close(df_bench)

    # 对齐长度（取较短者）
    n = min(len(s), len(b))
    s = s[-n:]
    b = b[-n:]
    if n < 30:
        raise RuntimeError(f"有效数据仅 {n} 天，不足 30 天无法回归")

    # 日收益率
    r_s = _np.diff(s) / s[:-1]
    r_b = _np.diff(b) / b[:-1]

    # β = Cov(Rs, Rb) / Var(Rb)
    cov = _np.cov(r_s, r_b, ddof=1)[0, 1]
    var_b = _np.var(r_b, ddof=1)
    beta = cov / var_b if var_b > 0 else float("nan")

    # α = 平均(Rs) − β × 平均(Rb)
    mean_s = _np.mean(r_s)
    mean_b = _np.mean(r_b)
    alpha_daily = mean_s - beta * mean_b
    alpha_annual = alpha_daily * 252 * 100  # 年化 α %

    # R²
    pred = beta * r_b + alpha_daily
    ss_res = _np.sum((r_s - pred) ** 2)
    ss_tot = _np.sum((r_s - mean_s) ** 2)
    r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else float("nan")

    # 年化波动率
    vol_s = _np.std(r_s, ddof=1) * math.sqrt(252) * 100
    vol_b = _np.std(r_b, ddof=1) * math.sqrt(252) * 100

    # Sharpe（无风险利率取 2%）
    rf_daily = 0.02 / 252
    excess = r_s - rf_daily
    sharpe = _np.mean(excess) / _np.std(excess, ddof=1) * math.sqrt(252) if _np.std(excess, ddof=1) > 0 else float("nan")

    return {
        "beta": round(beta, 3),
        "alpha_daily": round(alpha_daily * 100, 4),
        "alpha_annual": round(alpha_annual, 2),
        "r_squared": round(r_squared, 4),
        "vol_stock": round(vol_s, 2),
        "vol_bench": round(vol_b, 2),
        "sharpe": round(sharpe, 2),
        "data_points": n,
        "benchmark": benchmark_code,
    }


# ============================================================================
# 主应用类
# ============================================================================

class AlphaBetaDialog:
    """α/β 工作台"""

    def __init__(self, root):
        self.root = root
        self._setup_window()
        self._build_ui()

    def _setup_window(self):
        self.root.title("📐 α (阿尔法) / β (贝塔) · 配置工作台")
        self.root.geometry("1280x860")
        self.root.configure(bg=COLOR_BG)

    def _build_ui(self):
        # ---------- 顶部 Banner ----------
        banner = tk.Frame(self.root, bg="#0D47A1", height=64)
        banner.pack(fill=tk.X)
        banner.pack_propagate(False)
        bi = tk.Frame(banner, bg="#0D47A1")
        bi.pack(fill=tk.BOTH, expand=True, padx=16, pady=8)
        tk.Label(bi, text="📐 α (阿尔法) / β (贝塔)", font=("", 18, "bold"),
                 fg="white", bg="#0D47A1").pack(side=tk.LEFT)
        tk.Label(bi, text="  — 配置参考 + 实时数据工作台",
                 font=("", 13), fg="#BBDEFB", bg="#0D47A1").pack(side=tk.LEFT, padx=6)

        ak_status = "✅ akshare 就绪" if HAS_AK else "⚠️ 无 akshare（数据工具不可用）"
        pd_status = "pandas" if HAS_PD else ""
        tk.Label(bi, text=f"{ak_status} · {pd_status}",
                 font=("", 11), fg="#FFD700", bg="#0D47A1").pack(side=tk.RIGHT)

        # ---------- Notebook ----------
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("AB.TNotebook", background=COLOR_BG, borderwidth=0)
        style.configure("AB.TNotebook.Tab",
                        padding=[22, 10],
                        font=FONT_TAB,
                        background="#37474F",
                        foreground="#CFD8DC")
        style.map("AB.TNotebook.Tab",
                  background=[("selected", COLOR_BETA)],
                  foreground=[("selected", "white")])

        # ---------- 左右分栏 PanedWindow ----------
        # 左侧: 原 Notebook (参考手册 + 数据工具)，占比约 65%
        # 右侧: 研读区 (案例/书籍/机构/链接)，占比约 35%
        pw = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        pw.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 左侧主区
        left_main = tk.Frame(pw, bg=COLOR_BG)
        pw.add(left_main, weight=7)  # 左侧占 7/10

        # 右侧研读区
        right_main = self._build_study_panel(pw)
        pw.add(right_main, weight=4)  # 右侧占 4/10

        nb = ttk.Notebook(left_main, style="AB.TNotebook")
        nb.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        # Tab 顺序：参考手册类放前面，数据工具放中间
        self._add_text_tab(nb, "📖 概念定义", CONCEPT_TEXT)
        self._add_text_tab(nb, "🏗️ 配置框架", FRAMEWORK_TEXT)
        self._add_tool_tab(nb)                   # ← 数据工具 Tab
        self._add_text_tab(nb, "📅 近期配置", CONFIG_TEXT)
        self._add_text_tab(nb, "🛡️ 风控清单", RISK_TEXT)

        # ---------- 底部状态栏 ----------
        bottom = tk.Frame(self.root, bg=COLOR_DARK, height=36)
        bottom.pack(fill=tk.X, side=tk.BOTTOM)
        bottom.pack_propagate(False)
        tk.Label(bottom,
                 text="💡 α 是能力、β 是时代 · 牛市靠 β，震荡市靠 α，二者互补而非替代",
                 fg="#CFD8DC", bg=COLOR_DARK, font=("", 10)).pack(side=tk.LEFT, padx=14, pady=8)
        tk.Button(bottom, text="❌ 关闭", font=("", 10),
                  bg="#546E7A", fg="white", padx=14, pady=2, cursor="hand2",
                  command=self.root.destroy).pack(side=tk.RIGHT, padx=10, pady=5)

    # ------------------------------------------------------------------
    # 参考手册 Text Tab（大字号 + 行号+样式简化）
    # ------------------------------------------------------------------
    def _add_text_tab(self, notebook, tab_name, content):
        frame = tk.Frame(notebook, bg=COLOR_CARD)
        notebook.add(frame, text=tab_name)

        txt = scrolledtext.ScrolledText(
            frame, wrap=tk.WORD,
            font=FONT_CONTENT,       # 11pt
            bg=COLOR_CARD, fg="#263238",
            insertbackground="#263238",
            padx=20, pady=16,
            borderwidth=0, highlightthickness=0,
            spacing1=4, spacing3=4,
        )
        txt.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # 标签样式
        txt.tag_configure("h1", font=FONT_TITLE, foreground=COLOR_BETA, spacing1=8, spacing3=4)
        txt.tag_configure("h2", font=FONT_SECTION, foreground="#1565C0", spacing1=6)
        txt.tag_configure("alpha", font=(FONT_CONTENT[0], FONT_CONTENT[1], "bold"), foreground=COLOR_ALPHA)
        txt.tag_configure("beta", font=(FONT_CONTENT[0], FONT_CONTENT[1], "bold"), foreground=COLOR_BETA)
        txt.tag_configure("gold", font=(FONT_CONTENT[0], FONT_CONTENT[1], "bold"), foreground="#F57F17")
        txt.tag_configure("warn", font=(FONT_CONTENT[0], FONT_CONTENT[1], "bold"), foreground=COLOR_WARN)
        txt.tag_configure("code", font=("Menlo", 10), foreground="#6A1B9A", background="#EDE7F6")
        txt.tag_configure("box", background="#E3F2FD", foreground="#0D47A1",
                           font=(FONT_CONTENT[0], FONT_CONTENT[1], "bold"),
                           relief="flat", borderwidth=1)

        self._insert_formatted(txt, content)
        txt.config(state=tk.DISABLED)

    def _insert_formatted(self, txt, content):
        """按行首符号自动选样式"""
        for line in content.split("\n"):
            stripped = line.strip()
            if stripped.startswith("╔") or stripped.startswith("╚") or stripped.startswith("═══"):
                txt.insert(tk.END, line + "\n", "h1")
            elif stripped.startswith("┌") or stripped.startswith("└") or stripped.startswith("├") or stripped.startswith("┐") or stripped.startswith("┤"):
                txt.insert(tk.END, line + "\n", "h2")
            elif stripped.startswith("🔴"):
                txt.insert(tk.END, line + "\n", "alpha")
            elif stripped.startswith("🔵"):
                txt.insert(tk.END, line + "\n", "beta")
            elif stripped.startswith("💡") or stripped.startswith("━━━"):
                txt.insert(tk.END, line + "\n", "gold")
            elif stripped.startswith("⚠️") or stripped.startswith("❌"):
                txt.insert(tk.END, line + "\n", "warn")
            elif "Jensen" in line or "CAPM" in line:
                txt.insert(tk.END, line + "\n", "code")
            else:
                txt.insert(tk.END, line + "\n")

    # ------------------------------------------------------------------
    # 右侧研读区 (成功案例 / 书籍 / 机构配置 / 网址链接)
    # ------------------------------------------------------------------
    def _build_study_panel(self, parent):
        """构建右侧研读面板：4 个小 Tab + 可点击链接"""
        panel = tk.Frame(parent, bg="#0D1B2A")

        # 顶部标题条
        header = tk.Frame(panel, bg="#0D47A1", height=40)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="📚 研读区", font=("", 13, "bold"),
                 fg="white", bg="#0D47A1").pack(side=tk.LEFT, padx=12, pady=6)
        tk.Label(header, text="案例 · 书籍 · 机构 · 链接",
                 font=("", 10), fg="#BBDEFB", bg="#0D47A1").pack(side=tk.LEFT, pady=6)

        # 研读区小 Notebook
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Study.TNotebook", background="#0D1B2A", borderwidth=0)
        style.configure("Study.TNotebook.Tab",
                        padding=[14, 8],
                        font=("", 11, "bold"),
                        background="#1B2838",
                        foreground="#90A4AE")
        style.map("Study.TNotebook.Tab",
                  background=[("selected", COLOR_ACCENT)],
                  foreground=[("selected", "#263238")])

        study_nb = ttk.Notebook(panel, style="Study.TNotebook")
        study_nb.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        self._add_study_tab(study_nb, "🏆 成功案例", CASE_TEXT, enable_links=False)
        self._add_study_tab(study_nb, "📚 推荐书籍", BOOK_TEXT, enable_links=False)
        self._add_study_tab(study_nb, "🏦 机构配置", INST_TEXT, enable_links=False)
        self._add_study_tab(study_nb, "🔗 学习链接", LINKS, enable_links=True)

        return panel

    def _add_study_tab(self, notebook, tab_name, content, enable_links=False):
        """在研读区 Notebook 里加一个 Tab，带可点击链接"""
        frame = tk.Frame(notebook, bg="#0D1B2A")
        notebook.add(frame, text=tab_name)

        txt = scrolledtext.ScrolledText(
            frame, wrap=tk.WORD,
            font=("Microsoft YaHei", 11),
            bg="#0D1B2A", fg="#E0E0E0",
            insertbackground="#E0E0E0",
            padx=16, pady=14,
            borderwidth=0, highlightthickness=0,
            spacing1=3, spacing3=3,
        )
        txt.pack(fill=tk.BOTH, expand=True, padx=3, pady=3)

        # 研读区自己的 tag 样式
        txt.tag_configure("h1", font=("", 12, "bold"), foreground=COLOR_ACCENT, spacing1=6, spacing3=4)
        txt.tag_configure("h2", font=("", 11, "bold"), foreground=COLOR_BETA, spacing1=4)
        txt.tag_configure("alpha", font=("", 11, "bold"), foreground=COLOR_ALPHA)
        txt.tag_configure("beta", font=("", 11, "bold"), foreground=COLOR_BETA)
        txt.tag_configure("gold", font=("", 11, "bold"), foreground="#F57F17")
        txt.tag_configure("warn", font=("", 11, "bold"), foreground=COLOR_WARN)
        txt.tag_configure("sub", font=("", 10), foreground="#78909C")
        txt.tag_configure("url", font=("", 11), foreground="#64B5F6", underline=1)
        txt.tag_configure("box", background="#1B2838", foreground="#90A4AE",
                           font=("", 10), relief="flat", borderwidth=1)

        # 按行首符号自动选样式
        import re as _re
        url_re = _re.compile(r'https?://[^\s\n]+')

        for line in content.split("\n"):
            stripped = line.strip()

            # 先分离 URL（如果这行有）
            urls_in_line = url_re.findall(line)
            text_parts = url_re.split(line)

            for part in text_parts:
                if part in urls_in_line:
                    # 这是 URL，加可点击 tag
                    txt.insert(tk.END, part, ("url",))
                    txt.tag_bind("url", "<Button-1>",
                                 lambda _e, u=part: self._open_url(u))
                    txt.tag_bind("url", "<Enter>",
                                 lambda _e: txt.config(cursor="hand2"))
                    txt.tag_bind("url", "<Leave>",
                                 lambda _e: txt.config(cursor=""))
                elif part:
                    # 非 URL 部分，按行首符号选样式
                    ps = part.strip()
                    if ps.startswith("╔") or ps.startswith("╚") or ps.startswith("═══"):
                        txt.insert(tk.END, part, "h1")
                    elif ps.startswith("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━") or \
                         ps.startswith("① ") or ps.startswith("② ") or ps.startswith("③ ") or \
                         ps.startswith("④ ") or ps.startswith("⑤ ") or ps.startswith("⑥ "):
                        txt.insert(tk.END, part, "h2")
                    elif ps.startswith("🔴"):
                        txt.insert(tk.END, part, "alpha")
                    elif ps.startswith("🔵"):
                        txt.insert(tk.END, part, "beta")
                    elif ps.startswith("💡") or ps.startswith("━━━"):
                        txt.insert(tk.END, part, "gold")
                    elif ps.startswith("⚠️") or ps.startswith("❌"):
                        txt.insert(tk.END, part, "warn")
                    elif ps.startswith("【") or ps.startswith("· ") or ps.startswith("📄") or \
                         ps.startswith("📊") or ps.startswith("🏦") or ps.startswith("💬") or \
                         ps.startswith("🛠️"):
                        txt.insert(tk.END, part, "sub")
                    else:
                        txt.insert(tk.END, part)
            txt.insert(tk.END, "\n")

        txt.config(state=tk.DISABLED)

    @staticmethod
    def _open_url(url):
        """用系统默认浏览器打开 URL"""
        import subprocess
        import platform
        try:
            system = platform.system()
            if system == "Darwin":
                subprocess.Popen(["open", url])
            elif system == "Windows":
                subprocess.Popen(["cmd", "/c", "start", url])
            else:
                subprocess.Popen(["xdg-open", url])
        except Exception:
            pass

    # ------------------------------------------------------------------
    # 数据工具 Tab
    # ------------------------------------------------------------------
    def _add_tool_tab(self, notebook):
        frame = tk.Frame(notebook, bg=COLOR_BG)
        notebook.add(frame, text="🔧 数据工具")

        if not HAS_AK:
            tk.Label(frame, text="⚠️ akshare 未安装 — 数据工具不可用\n"
                                 "请在股票分析.command 使用的 Python 中安装: pip install akshare",
                     font=FONT_CONTENT, fg=COLOR_WARN, bg=COLOR_BG, pady=60).pack()
            return

        # ---- 左侧：指数对比 + ETF扫描 ----
        left = tk.Frame(frame, bg=COLOR_BG)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 4), pady=8)

        # 指数对比卡片
        idx_card = tk.LabelFrame(left, text=" 📊 主要指数表现 (β 风向标) ",
                                 bg=COLOR_DARK, fg=COLOR_ACCENT,
                                 font=FONT_SECTION, padx=8, pady=6)
        idx_card.pack(fill=tk.X, pady=(0, 10))
        btn_bar = tk.Frame(idx_card, bg=COLOR_DARK)
        btn_bar.pack(fill=tk.X, pady=(0, 6))
        self._idx_status = tk.Label(btn_bar, text="点击「🔄 刷新」拉取数据",
                                    bg=COLOR_DARK, fg="#90A4AE", font=FONT_CONTENT)
        self._idx_status.pack(side=tk.LEFT)
        tk.Button(btn_bar, text="🔄 刷新", font=FONT_BTN,
                  bg=COLOR_BETA, fg="white", padx=12, pady=3, cursor="hand2",
                  command=self._thread(self._refresh_indices)).pack(side=tk.RIGHT, padx=4)

        # 指数 Treeview
        idx_cols = ("name", "tag", "close", "chg_1d", "chg_5d", "chg_20d", "chg_60d")
        idx_labels = {"name": "指数", "tag": "类型", "close": "最新",
                      "chg_1d": "日%", "chg_5d": "5日%", "chg_20d": "20日%", "chg_60d": "60日%"}
        idx_widths = {"name": 110, "tag": 70, "close": 80,
                      "chg_1d": 70, "chg_5d": 70, "chg_20d": 70, "chg_60d": 70}
        self._idx_tree = self._make_tree(idx_card, idx_cols, idx_labels, idx_widths, height=8)
        self._idx_tree.pack(fill=tk.BOTH, expand=True)

        # ETF 扫描卡片
        etf_card = tk.LabelFrame(left, text=" 💰 核心 ETF 实时行情 (β/α 工具) ",
                                 bg=COLOR_DARK, fg=COLOR_ACCENT,
                                 font=FONT_SECTION, padx=8, pady=6)
        etf_card.pack(fill=tk.BOTH, expand=True)
        etf_btn_bar = tk.Frame(etf_card, bg=COLOR_DARK)
        etf_btn_bar.pack(fill=tk.X, pady=(0, 6))
        self._etf_status = tk.Label(etf_btn_bar, text="点击「🔄 扫描」拉取 ETF 行情",
                                    bg=COLOR_DARK, fg="#90A4AE", font=FONT_CONTENT)
        self._etf_status.pack(side=tk.LEFT)
        tk.Button(etf_btn_bar, text="🔄 扫描", font=FONT_BTN,
                  bg=COLOR_BETA, fg="white", padx=12, pady=3, cursor="hand2",
                  command=self._thread(self._refresh_etfs)).pack(side=tk.RIGHT, padx=4)

        # ETF 分组 Notebook
        self._etf_nb = ttk.Notebook(etf_card)
        self._etf_nb.pack(fill=tk.BOTH, expand=True)

        # ---- 右侧：β 计算器 ----
        right = tk.Frame(frame, bg=COLOR_BG)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(4, 8), pady=8)

        beta_card = tk.LabelFrame(right, text=" 📐 个股/ETF β 计算器 (CAPM) ",
                                  bg=COLOR_DARK, fg=COLOR_ALPHA,
                                  font=FONT_SECTION, padx=10, pady=8)
        beta_card.pack(fill=tk.X)

        # 输入行
        input_row = tk.Frame(beta_card, bg=COLOR_DARK)
        input_row.pack(fill=tk.X, pady=(0, 8))

        tk.Label(input_row, text="股票/ETF代码:", bg=COLOR_DARK, fg="#CFD8DC",
                 font=FONT_CONTENT).pack(side=tk.LEFT)
        self._entry_code = tk.Entry(input_row, font=FONT_CONTENT, width=12)
        self._entry_code.insert(0, "600519")
        self._entry_code.pack(side=tk.LEFT, padx=(4, 14))

        tk.Label(input_row, text="基准指数:", bg=COLOR_DARK, fg="#CFD8DC",
                 font=FONT_CONTENT).pack(side=tk.LEFT)
        self._bench_var = tk.StringVar(value="沪深300 (000300)")
        bench_opts = ["沪深300 (000300)", "中证500 (000905)", "中证1000 (000852)",
                      "中证A500 (932000)", "上证50 (000016)", "创业板指 (399006)"]
        cb = ttk.Combobox(input_row, textvariable=self._bench_var, values=bench_opts,
                          width=22, font=FONT_CONTENT, state="readonly")
        cb.pack(side=tk.LEFT, padx=(4, 14))

        tk.Label(input_row, text="天数:", bg=COLOR_DARK, fg="#CFD8DC",
                 font=FONT_CONTENT).pack(side=tk.LEFT)
        self._days_var = tk.StringVar(value="250")
        ttk.Combobox(input_row, textvariable=self._days_var,
                     values=["120", "250", "500"], width=6, font=FONT_CONTENT,
                     state="readonly").pack(side=tk.LEFT, padx=4)

        tk.Button(input_row, text="🚀 计算 β", font=FONT_BTN,
                  bg=COLOR_ALPHA, fg="white", padx=12, pady=2, cursor="hand2",
                  command=self._thread(self._compute_beta)).pack(side=tk.LEFT, padx=(12, 0))

        # β 结果卡片
        self._beta_result = tk.Frame(beta_card, bg="#ECEFF1", height=160)
        self._beta_result.pack(fill=tk.X, pady=(4, 0))
        self._beta_result.pack_propagate(False)
        self._beta_labels = {}
        self._build_beta_result_card()

        # β 解读区
        note_card = tk.LabelFrame(right, text=" 💡 β 解读 ",
                                  bg=COLOR_DARK, fg="#B0BEC5",
                                  font=FONT_SECTION, padx=8, pady=8)
        note_card.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        self._beta_note = scrolledtext.ScrolledText(
            note_card, wrap=tk.WORD, font=FONT_CONTENT,
            bg="#0D1B2A", fg="#E0E0E0",
            padx=12, pady=10, borderwidth=0, height=10
        )
        self._beta_note.pack(fill=tk.BOTH, expand=True)
        self._beta_note.insert("1.0",
            "输入股票代码（如 600519 茅台 / 510300 沪深300ETF / 159915 创业板ETF）\n"
            "选择基准指数，点击「🚀 计算 β」\n\n"
            "📖 指标含义：\n"
            "  β = 1.0   → 与基准同步涨跌（如宽基ETF）\n"
            "  β > 1     → 进攻型，涨跌放大（如成长股/周期股）\n"
            "  β < 1     → 防御型，涨跌缩小（如红利/公用事业）\n"
            "  β ≈ 0     → 与大盘无关（如债券、黄金）\n"
            "  β < 0     → 与大盘反向（如某些对冲品种）\n"
            "  R²        → 拟合优度，越接近 1 表示 β 解释力越强\n"
            "  α(年化)   → 剔除市场 β 后的超额收益（CAPM 回归截距年化）\n"
            "  Sharpe    → 风险调整收益（无风险利率按 2% 计算）\n"
            "  波动率    → 年化日收益标准差，衡量总风险\n"
        )
        self._beta_note.config(state=tk.DISABLED)

    def _build_beta_result_card(self):
        """构建 β 结果显示格子（2行 x 4列）"""
        for w in self._beta_result.winfo_children():
            w.destroy()
        layout = [
            ("β 值", "beta", COLOR_ALPHA),
            ("α (年化%)", "alpha_annual", COLOR_ACCENT),
            ("R²", "r_squared", COLOR_BETA),
            ("Sharpe", "sharpe", "#7B1FA2"),
            ("波动率(%)", "vol_stock", "#546E7A"),
            ("基准波动率", "vol_bench", "#546E7A"),
            ("数据点", "data_points", "#546E7A"),
            ("基准", "benchmark", "#546E7A"),
        ]
        for i, (label, key, color) in enumerate(layout):
            cell = tk.Frame(self._beta_result, bg="#FFFFFF", highlightbackground="#CFD8DC",
                            highlightthickness=1)
            cell.grid(row=i // 4, column=i % 4, padx=6, pady=6, sticky="nsew")
            self._beta_result.grid_columnconfigure(i % 4, weight=1)
            self._beta_result.grid_rowconfigure(i // 4, weight=1)
            tk.Label(cell, text=label, bg="#FFFFFF", fg="#78909C",
                     font=("", 10)).pack(pady=(8, 0))
            val_lbl = tk.Label(cell, text="--", bg="#FFFFFF", fg=color,
                               font=("", 18, "bold"))
            val_lbl.pack(pady=(0, 8))
            self._beta_labels[key] = val_lbl

    def _make_tree(self, parent, cols, labels, widths, height=6):
        """创建统一风格 Treeview"""
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("AB.Treeview",
                        background="#FFFFFF",
                        foreground="#263238",
                        fieldbackground="#FFFFFF",
                        rowheight=28,
                        font=FONT_CONTENT,
                        borderwidth=0)
        style.configure("AB.Treeview.Heading",
                        background="#0D47A1",
                        foreground="white",
                        font=(FONT_CONTENT[0], FONT_CONTENT[1], "bold"))
        style.map("AB.Treeview", background=[("selected", "#BBDEFB")])

        tv = ttk.Treeview(parent, columns=cols, show="headings",
                          height=height, style="AB.Treeview")
        for c in cols:
            tv.heading(c, text=labels[c])
            tv.column(c, width=widths[c], anchor="center")
        tv.tag_configure("up", foreground=COLOR_UP)
        tv.tag_configure("down", foreground=COLOR_DOWN)
        tv.tag_configure("na", foreground="#90A4AE")
        return tv

    # ------------------------------------------------------------------
    # 后台线程包装
    # ------------------------------------------------------------------
    def _thread(self, fn):
        """返回一个在后台线程运行的 lambda"""
        def wrapper():
            t = threading.Thread(target=self._safe_run, args=(fn,), daemon=True)
            t.start()
        return wrapper

    def _safe_run(self, fn):
        # ⚠️ PEP 3110: Python 3.1+ 的 except 块退出后异常变量 e 会被自动删除
        # 必须把 str(e) 提前存成普通字符串，让闭包捕获字符串而非 e
        try:
            fn()
        except Exception as e:
            err_msg = f"{type(e).__name__}: {e}"
            def _show(_m=err_msg):
                _mb.showerror("❌ 数据拉取失败", _m)
            self.root.after(0, _show)

    # ------------------------------------------------------------------
    # 刷新指数
    # ------------------------------------------------------------------
    def _refresh_indices(self):
        self.root.after(0, lambda: self._idx_status.config(text="⏳ 拉取中 ...", fg=COLOR_WARN))
        data = fetch_index_performance(progress_cb=lambda m:
            self.root.after(0, lambda: self._idx_status.config(text=f"⏳ {m}", fg=COLOR_WARN)))
        self.root.after(0, lambda: self._fill_idx_tree(data))

    def _fill_idx_tree(self, data):
        for iid in self._idx_tree.get_children():
            self._idx_tree.delete(iid)
        ok = sum(1 for d in data if d.get("close") is not None)
        for d in data:
            tag = "na"
            if d.get("close") is None:
                vals = (d["name"], d.get("tag", ""), "--", "--", "--", "--", "--")
            else:
                def _fmt(x):
                    if x is None: return "--"
                    s = f"{x:+.2f}%"
                    return s
                def _tag(x):
                    if x is None or x == 0: return "na"
                    return "up" if x > 0 else "down"
                vals = (d["name"], d["tag"], f"{d['close']}",
                        _fmt(d["chg_1d"]), _fmt(d["chg_5d"]),
                        _fmt(d["chg_20d"]), _fmt(d["chg_60d"]))
                tag = _tag(d["chg_20d"])
            self._idx_tree.insert("", tk.END, values=vals, tags=(tag,))
        self._idx_status.config(text=f"✅ 已拉取 {ok}/{len(data)} 个指数  ·  {_dt.datetime.now().strftime('%H:%M:%S')}",
                                fg="#4CAF50")

    # ------------------------------------------------------------------
    # 刷新 ETF
    # ------------------------------------------------------------------
    def _refresh_etfs(self):
        self.root.after(0, lambda: self._etf_status.config(text="⏳ 扫描中 ...", fg=COLOR_WARN))
        grouped = fetch_etf_scan(progress_cb=lambda m:
            self.root.after(0, lambda: self._etf_status.config(text=f"⏳ {m}", fg=COLOR_WARN)))
        self.root.after(0, lambda: self._fill_etf_tabs(grouped))

    def _fill_etf_tabs(self, grouped):
        # 清理旧 tab
        for tab in self._etf_nb.tabs():
            self._etf_nb.forget(tab)
        total = 0
        for tag, rows in grouped.items():
            frame = tk.Frame(self._etf_nb, bg=COLOR_CARD)
            self._etf_nb.add(frame, text=f" {tag} ({len(rows)}) ")
            total += len(rows)
            cols = ("code", "name", "price", "pct")
            labels = {"code": "代码", "name": "名称", "price": "现价", "pct": "涨跌幅%"}
            widths = {"code": 80, "name": 260, "price": 80, "pct": 100}
            tree = self._make_tree(frame, cols, labels, widths, height=5)
            tree.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
            for r in rows:
                if r["pct"] is None:
                    tree.insert("", tk.END, values=(r["code"], r["name"],
                                                     f"{r['price']}" if r["price"] else "--", "--"), tags=("na",))
                else:
                    tag = "up" if r["pct"] > 0 else ("down" if r["pct"] < 0 else "na")
                    tree.insert("", tk.END, values=(r["code"], r["name"],
                                                     f"{r['price']}", f"{r['pct']:+.2f}%"),
                                tags=(tag,))
        self._etf_status.config(text=f"✅ 扫描 {total} 只 ETF  ·  {_dt.datetime.now().strftime('%H:%M:%S')}",
                                 fg="#4CAF50")

    # ------------------------------------------------------------------
    # β 计算
    # ------------------------------------------------------------------
    def _compute_beta(self):
        code = self._entry_code.get().strip()
        if not code:
            self.root.after(0, lambda: _mb.showwarning("提示", "请输入股票/ETF 代码"))
            return
        # 从下拉解析代码
        bench_full = self._bench_var.get()
        bench_code = bench_full.split("(")[-1].rstrip(")") if "(" in bench_full else "000300"
        try:
            days = int(self._days_var.get())
        except Exception:
            days = 250

        self.root.after(0, lambda: self._beta_labels["beta"].config(text="⏳"))
        self.root.after(0, lambda: self._beta_labels["benchmark"].config(text=f"{bench_code}"))

        result = compute_beta(code, benchmark_code=bench_code, days=days,
                              progress_cb=lambda m:
                                  self.root.after(0, lambda: self._beta_labels["benchmark"].config(text=m[-10:])))
        self.root.after(0, lambda: self._show_beta_result(code, bench_full, result))

    def _show_beta_result(self, code, bench_full, result):
        for key, lbl in self._beta_labels.items():
            v = result.get(key, "--")
            if v is None:
                v = "--"
            lbl.config(text=str(v))

        # 解读文字
        beta = result["beta"]
        r2 = result["r_squared"]
        note_lines = [f"📌 {code} vs {bench_full}  CAPM 回归结果", "=" * 40, ""]
        # β 解读
        if beta is None or (isinstance(beta, float) and math.isnan(beta)):
            note_lines.append("⚠️ β 计算异常 — 可能数据点不足或基准与标的完全无关")
        elif beta > 1.5:
            note_lines.append(f"🔴 β = {beta}  —— 高进攻性！涨超大盘、跌也超大盘")
            note_lines.append("  适合：牛市加仓 / 震荡市减仓 / 空头不碰")
        elif beta > 1.05:
            note_lines.append(f"🟠 β = {beta}  —— 略进攻，涨跌比大盘多 5-30%")
        elif beta > 0.95:
            note_lines.append(f"🟡 β = {beta}  —— 几乎同步大盘（类似宽基ETF）")
        elif beta > 0.5:
            note_lines.append(f"🟢 β = {beta}  —— 防御型，涨跌比大盘小")
        elif beta >= 0:
            note_lines.append(f"⚪ β = {beta}  —— 低β，与大盘关联弱（红利/公用事业/债券）")
        else:
            note_lines.append(f"🔵 β = {beta}  —— 负β！大盘涨它跌、大盘跌它涨（避险资产特征）")

        # R² 解读
        note_lines.append("")
        if r2 is None or (isinstance(r2, float) and math.isnan(r2)):
            note_lines.append("R² 无效")
        elif r2 > 0.7:
            note_lines.append(f"✅ R² = {r2}  —— 拟合优度高，β 能解释大部分波动")
        elif r2 > 0.4:
            note_lines.append(f"⚠️ R² = {r2}  —— 中度，个股特质因素较多")
        else:
            note_lines.append(f"❌ R² = {r2}  —— 拟合差，这只票的涨跌基本和大盘没关系")

        # α 解读
        a = result.get("alpha_annual")
        if a is not None and not (isinstance(a, float) and math.isnan(a)):
            note_lines.append("")
            if a > 5:
                note_lines.append(f"⭐ α(年化) = {a:+.2f}%  —— 显著跑赢基准！真·α")
            elif a > 0:
                note_lines.append(f"👍 α(年化) = {a:+.2f}%  —— 小幅正超额")
            elif a > -3:
                note_lines.append(f"😐 α(年化) = {a:+.2f}%  —— 基本持平或略亏")
            else:
                note_lines.append(f"❌ α(年化) = {a:+.2f}%  —— 扣除 β 后在亏损，α 为负")

        # 波动率
        vs = result.get("vol_stock")
        vb = result.get("vol_bench")
        if vs is not None and vb is not None:
            note_lines.append("")
            note_lines.append(f"📊 波动率 {vs}% vs 基准 {vb}%  "
                              f"(波动率倍率 {vs/vb:.2f}x)")

        note_lines.append("")
        note_lines.append("💡 操作建议：")
        if beta is not None and not (isinstance(beta, float) and math.isnan(beta)):
            if beta > 1.2:
                note_lines.append("  · 牛市拿住，震荡市减仓 30%+")
                note_lines.append("  · 不要在高β品种上满仓 + 加杠杆")
            elif beta < 0.5:
                note_lines.append("  · 作为组合防御底仓，压舱石用")
                note_lines.append("  · 但也别指望它在牛市里涨得比宽基好")
            elif beta < 0:
                note_lines.append("  · 作为对冲/避险资产，和股票做负相关配置")
                note_lines.append("  · 组合中占比不宜过高（<10%）")
            else:
                note_lines.append("  · 普通β，可作为核心仓配置")
                note_lines.append("  · 搭配卫星 α 品种增强超额")

        self._beta_note.config(state=tk.NORMAL)
        self._beta_note.delete("1.0", tk.END)
        self._beta_note.insert("1.0", "\n".join(note_lines))
        self._beta_note.config(state=tk.DISABLED)


# ============================================================================
# 入口函数
# ============================================================================

def open_alpha_beta_dialog(parent_root=None):
    """被主程序调用入口"""
    if parent_root:
        win = tk.Toplevel(parent_root)
    else:
        win = tk.Tk()
    app = AlphaBetaDialog(win)
    return win, app


def main():
    root = tk.Tk()
    app = AlphaBetaDialog(root)
    root.mainloop()


if __name__ == "__main__":
    main()
