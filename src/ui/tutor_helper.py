# -*- coding: utf-8 -*-
"""📚 家教辅导助手 — 上海小学生专属 (部编版体系)
作者: 小朋友的家庭学习小帮手 🦊
配色: 天蓝/粉红/薄荷绿/向日葵黄/草莓红/薰衣草紫 — 小朋友喜欢的马卡龙色
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import webbrowser
import json
import os
import random
import tempfile
from datetime import datetime

# 可选依赖 — 缺失时优雅降级
try:
    from PIL import Image
    HAS_PIL = True
except Exception:
    HAS_PIL = False

try:
    import pytesseract
    HAS_TESSERACT = True
except Exception:
    HAS_TESSERACT = False

try:
    import matplotlib
    matplotlib.use("TkAgg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    HAS_MATPLOTLIB = True
except Exception:
    HAS_MATPLOTLIB = False

# ─────────────────────────────────────────────
# 🎨 马卡龙主题配色 (小朋友喜欢)
# ─────────────────────────────────────────────
PALETTE = {
    "bg": "#FFF8F0",           # 奶油底色
    "pink": "#FFD6E8",         # 草莓奶盖
    "pink_dark": "#FF6B9D",    # 草莓酱
    "sky": "#A8D8EA",          # 天空蓝
    "sky_dark": "#4EA8DE",     # 飞机蓝
    "mint": "#C8F0DB",         # 薄荷绿
    "mint_dark": "#3DBA78",    # 草地绿
    "sun": "#FFE492",          # 向日葵黄
    "sun_dark": "#FFB703",     # 蜂蜜黄
    "lavender": "#E0D4F5",     # 薰衣草紫
    "lavender_dark": "#9B7ED8",# 葡萄紫
    "white": "#FFFFFF",
    "text": "#2C3E50",         # 深夜蓝 (主文字)
    "text_light": "#7F8C8D",
    "title_font": ("Comic Sans MS", 22, "bold"),
    "body_font": ("Microsoft YaHei", 16),
    "body_bold": ("Microsoft YaHei", 16, "bold"),
    "small_font": ("Microsoft YaHei", 14),
    "emoji_font": ("Apple Color Emoji", 20),
}

# ─────────────────────────────────────────────
# 🔧 全局字体调节 (A-/A+) — 支持电视大屏 3x 缩放!
# ─────────────────────────────────────────────
_FONT_SCALE = 1.0   # 默认 1.0, 范围 0.8 ~ 3.0 (电视大屏需要3倍!)
_FONT_WIDGETS = []  # (widget, base_font_tuple) 注册表


def _reg_font(widget, base_font):
    """注册一个需要字体跟随缩放的 widget (Label/Button/Text 都支持)"""
    try:
        _FONT_WIDGETS.append((widget, base_font))
        family, size, *rest = (*base_font, "")
        new_size = max(8, int(size * _FONT_SCALE))
        widget.config(font=(family, new_size, *rest))
    except Exception:
        pass


def _apply_font_scale(scale):
    """批量重设所有注册 widget 的字体"""
    global _FONT_SCALE
    _FONT_SCALE = scale
    for widget, base_font in _FONT_WIDGETS:
        try:
            family, size, *rest = (*base_font, "")
            new_size = max(8, int(size * scale))
            widget.config(font=(family, new_size, *rest))
        except Exception:
            pass

# ─────────────────────────────────────────────
# 💾 本地数据持久化
# ─────────────────────────────────────────────
DATA_DIR = os.path.expanduser("~/.tutor_helper")
DATA_FILE = os.path.join(DATA_DIR, "kid_profile.json")


def _ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def _load_profile():
    _ensure_data_dir()
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "kid_name": "小朋友",
        "grade": "三年级",
        "school": "",
        "district": "上海",
        "weakness": "",
        "strengths": "",
        "concept_gaps": "",
        "notes": "",
    }


def _save_profile(data):
    _ensure_data_dir()
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ─────────────────────────────────────────────
# 🔗 软件网址数据 (带功能点和❓注释)
# ─────────────────────────────────────────────
SOFTWARE_LIST = [
    # 官方免费
    {"cat": "🎁 官方免费", "name": "国家中小学智慧教育平台",
     "url": "https://basic.smartedu.cn",
     "func": "教育部主办 · 10大版块 · 名师微课15-20分钟/节 · 部编版/人教版/苏教版/北师大版全教材切换 · 电子课本全免费",
     "tip": "✅ 首选! 零成本零风险, 永远先上这个. 上海的话配合「空中课堂」进度最贴"},
    {"cat": "🎁 官方免费", "name": "上海空中课堂",
     "url": "https://shtv.hebeea.edu.cn",
     "func": "上海本地资源 · 沪教版同步 · 课后习题精讲",
     "tip": "上海孩子的专属福利, 进度100%贴合课堂"},
    # 作业批改
    {"cat": "✏️ 作业批改", "name": "小猿AI (原小猿口算)",
     "url": "https://www.xiaoyuanshe.com",
     "func": "全科拍照批改 · 五重错因分析 · AI分步追问 · 错题本自动推同类变式题 · 口算/竖式批改最准",
     "tip": "❓ 搜题尽量家长操作, 先让孩子独立想10分钟再查! 严禁拍照直接抄"},
    {"cat": "✏️ 作业批改", "name": "作业帮",
     "url": "https://www.zuoyebang.com",
     "func": "题库最大(3亿+) · 作文批改 · 单词查询",
     "tip": "⚠️ 广告多, 解析偏简, 建议只用来搜题和看作文范文"},
    {"cat": "✏️ 作业批改", "name": "爱作业",
     "url": "https://www.izuoye.com",
     "func": "一线小学老师自己用 · 手写识别强 · 错题按'计算错误/概念混淆/审题不清'分类",
     "tip": "很多老师也在用, 错题分类标签特别好用"},
    {"cat": "✏️ 作业批改", "name": "快对",
     "url": "https://www.kuaiduizuoye.com",
     "func": "答案核对 · 批量打印PDF · 连打印机出卷",
     "tip": "❓ 配合错题本打印最香, 不用手抄! 需要配打印机"},
    {"cat": "✏️ 作业批改", "name": "爱立熊",
     "url": "https://www.ailixiong.com",
     "func": "错题'擦掉批改痕迹再打印' · 免手抄 · 配专用热敏打印机",
     "tip": "如果孩子错题多, 这个太省妈了!"},
    # 同步课程
    {"cat": "📖 同步课程", "name": "学而思轻课",
     "url": "https://www.xueersi.com/qingke",
     "func": "动画化课 · 拍教材搜课程 · 学科地图+学情报告 · 部编版语文+PEP英语同步",
     "tip": "低年级坐不住的孩子首选! 动画课比普通微课吸引力强10倍"},
    {"cat": "📖 同步课程", "name": "洋葱学园",
     "url": "https://www.yangcong345.com",
     "func": "几分钟动画讲透一个概念 · 只适合课前预习",
     "tip": "❓ 没有督学闭环, 别当主课用! 课前5分钟看一眼就行"},
    {"cat": "📖 同步课程", "name": "猿辅导",
     "url": "https://www.yuanfudao.com",
     "func": "语数英全科系统班 · 15亿题库 · AI学情诊断 · A/A+/S分层班型 · 班主任双师伴学",
     "tip": "付费! 先试听, 单次缴费不超3个月/5000元, 走'校外培训家长端'APP"},
    {"cat": "📖 同步课程", "name": "101网校",
     "url": "https://www.chinaedu.com",
     "func": "30年老牌 · 录播微课为主 · 时间自由 · 多教材版本 · AI学情诊断",
     "tip": "适合自律的孩子, 时间自由但需要自己安排"},
    {"cat": "📖 同步课程", "name": "高途",
     "url": "https://www.gaotu100.com",
     "func": "直播大班双师 · 基础/提升/培优分层 · 语文阅读写作+数学思维口碑最好",
     "tip": "语文想提分, 高途是真的有东西!"},
    # 英语专项
    {"cat": "🔤 英语专项", "name": "纳米盒",
     "url": "https://www.namibox.com",
     "func": "课本点读 · 课文跟读 · 生字听写 · 古诗朗读 · 纠发音 · 界面干净无社交",
     "tip": "低中段英语最实用! 课本点读功能是刚需"},
    {"cat": "🔤 英语专项", "name": "伴鱼少儿英语",
     "url": "https://www.palfish.com",
     "func": "长期自然拼读+外教口语路线 · 一对多小班",
     "tip": "先试听! 别直接买大课包 —— 单次缴费不超5000元"},
    {"cat": "🔤 英语专项", "name": "趣趣ABC",
     "url": "https://www.ququabc.com",
     "func": "启蒙+口语 · 自然拼读主线",
     "tip": "英语不敢开口的孩子, 周末1次外教比什么都管用"},
    # 思维拓展
    {"cat": "🧠 思维拓展", "name": "编程猫",
     "url": "https://www.codemao.cn",
     "func": "1-3年级入门编程 · Scratch图形化",
     "tip": "编程是最好的逻辑训练, 但别急, 三年级以后再说"},
    {"cat": "🧠 思维拓展", "name": "奥数网",
     "url": "https://www.aoshu.com",
     "func": "奥赛题库 · 视频讲解 · 分年级专题",
     "tip": "奥数先看孩子兴趣, 别强塞 —— 强塞会讨厌数学"},
]

# ─────────────────────────────────────────────
# 🧮 解题思路数据
# ─────────────────────────────────────────────
SOLUTION_DB = {
    "数学逻辑": """
📐 学好数学的 5 个秘诀 (上海版)

1️⃣ 计算是地基 — 每天5分钟口算计时, 别嫌麻烦!
   上海卷计算占比 30%+, 算错一分没。
   → 小猿AI每日口算 + 快对打印练习卷

2️⃣ 错题本是金矿 — 错因分三类:
   ✅ 计算错 → 回去练计算
   ✅ 概念混淆 → 回课本看定义
   ✅ 审题不清 → 圈关键词 (圈完再读一遍!)

3️⃣ 画图解题 — 几何题画辅助线, 应用题画线段图, 一试一个准!

4️⃣ 变式训练 — 同一道题换数字换情境, 真正"懂"了才会变。

5️⃣ 限时模考 — 每月找一套上海区统考卷, 计时做完。
""",
    "奥数解题": """
🧩 奥数解题 7 大武器 (三年级起)

1. 假设法 — 鸡兔同笼经典! 假设全是鸡, 脚数差÷2=兔数
2. 枚举法 — 数字谜/填数, 从范围小的开始试
3. 倒推法 — 知道结果求开始, 一步一步倒着算
4. 配对法 — 1+99=100, 2+98=100... 巧算必备
5. 列表法 — 逻辑推理题, 画表格打√×
6. 抽屉原理 — 3本书放2抽屉, 必有1抽屉≥2本
7. 周期问题 — 找规律, 算余数, 第N个=第几个

⚠️ 奥数先看兴趣! 上海公办小学不教, 纯靠家长自驱
""",
    "学好语文": """
📖 学好语文 6 件小事 (部编版)

1️⃣ 每日朗读 15 分钟 — 语感比刷题重要 100 倍!
   课文+古诗文, 大声读出来

2️⃣ 字词句过关 — 每课生字词听写, 词语手册必做
   上海卷: 看拼音写汉字 4-6 分, 错一个扣一分

3️⃣ 阅读三步法:
   ① 速读 → 写中心句
   ② 细读 → 圈画好词好句
   ③ 做题 → 答案从文中找(别自己编!)

4️⃣ 作文素材本 — 好句子+好段落+好故事, 每周抄3个
   三年级: 看图写话 → 四年级: 记事/写人 → 五年级: 议论文

5️⃣ 古诗文必背 — 上海考纲 135 首! 早背早香

6️⃣ 练字 — 卷面分 3-5 分, 一手好字=白送分
""",
    "学好英语": """
🔤 学好英语 4 件事 (牛津上海版/PEP)

1️⃣ 课本点读跟唱 — 纳米盒打开, 每天 10 分钟
   跟读后录音对比, 纠发音

2️⃣ 单词三读法 — 看音标读, 拼字母读, 看中文读
   上海三年级起学音标, 这是关键!

3️⃣ 造句法 — 每个单词造 1 个句子, 会用了才是你的

4️⃣ 动画浸泡 — Peppa Pig / 小猪佩奇英文版, 每天20分钟
   沉浸式输入, 比背单词有效得多

⚠️ 上海英语特色: 牛津上海版 + 人教版双轨
   考纲词汇量: 三年级 300 / 四年级 600 / 五年级 900 / 六年级 1200
""",
    "学好科学": """
🔬 学好科学 (沪教版/科教版)

上海小学科学从三年级开始, 期末要考!

1️⃣ 重视实验 — 动手做比看书有用10倍
   电路/磁铁/植物生长, 家里就能做

2️⃣ 概念图 — 每单元画一张概念关系图
   如: 动物→脊椎/无脊椎→哺乳/鸟/鱼...

3️⃣ 观察日记 — 种一盆植物, 每天记变化
   既练写作又学科学

4️⃣ 联系生活 — 科学就在身边!
   为什么天空是蓝的? 为什么盐能化雪?

⚠️ 上海各区统考, 科学占比 20-30%, 别忽视!
""",
    "避坑指南": """
🚨 辅导避坑 6 条 (比选哪个软件更重要)

1. 1主攻 + 1工具封顶, 装太多全家都烦
2. 搜题家长操作, 或立规矩: 先想10分钟再查
3. 付费先试听, 单次不超3个月/60课时/5000元
   → 必须走教育部"校外培训家长端"APP缴费
4. 免费平台配固定时段+任务清单, 否则只收藏不执行
5. 屏幕时间每天30-40分钟, 优先平板/电视大屏
6. 判断"懂没懂": 让孩子做一道变式题,
   别问"听懂了吗" (孩子99%说"懂了"其实没懂)
""",
}

# ─────────────────────────────────────────────
# 📚 语文知识点 (部编版)
# ─────────────────────────────────────────────
CHINESE_KNOWLEDGE = {
    "三年级上": """
📖 部编版三年级上册 核心知识点

【生字词】250个生字 + 400个词语
  → 每课"听写本"必过, 词语手册必做

【课文重点】
  1. 《花的学校》— 泰戈尔散文诗, 拟人手法
  2. 《铺满金色巴掌的水泥道》— 比喻+感官描写
  3. 《秋天的雨》— 总分结构, 颜色词积累
  4. 《金色的草地》— 观察日记写法
  5. 《古诗三首》— 《山行》《赠刘景文》《夜书所见》

【语文要素】
  ✅ 预测: 边读边猜"接下来会发生什么"
  ✅ 用多种方法理解词语 (查字典/联系上下文)
  ✅ 习作: 写日记 (格式: 日期+星期+天气)

【必背古诗】38首 (义务教育课标)
""",
    "三年级下": """
📖 部编版三年级下册 核心知识点

【语文要素】
  ✅ 了解消息的写法 (时间/地点/人物/事件/原因)
  ✅ 了解自然段的段式 (总分/并列/顺承)
  ✅ 习作: 写一个身边的人 (抓住特点)

【单元重点】
  1. 第一单元 — 观察春天 (《燕子》《荷花》)
  2. 第二单元 — 寓言故事 (《守株待兔》《陶罐和铁罐》)
  3. 第三单元 — 中华传统节日
  4. 第四单元 — 观察发现 (《花钟》《小虾》)

【古诗文】
  必背: 《绝句》《惠崇春江晚景》《三衢道中》《忆江南》
  文言文入门: 《守株待兔》
""",
    "四年级上": """
📖 部编版四年级上册 核心知识点

【语文要素升级】
  ✅ 提问策略: 针对课文不同角度提问 (内容/写法/启示)
  ✅ 写一件事: 按顺序 + 六要素 (时地人事因果)
  ✅ 写观察日记: 连续观察 + 数据记录

【古诗文重点】
  《观潮》《盘古开天地》《精卫填海》《普罗米修斯》
  必背: 《暮江吟》《题西林壁》《雪梅》《出塞》

【写作模板】
  写事: 开头(场景) → 经过(详写) → 结尾(感受)
  写景: 总 → 分 → 总 (五感+修辞)

⚠️ 四年级是语文分水岭! 阅读题开始考"深层含义"
""",
    "古诗文必背": """
📜 上海小学必背古诗 135 首 (义务教育)

三年级 (18首):
  《咏柳》《春晓》《回乡偶书》《登鹳雀楼》《望庐山瀑布》
  《早发白帝城》《绝句》《赠汪伦》《静夜思》《夜宿山寺》
  《古朗月行》《风》《画》《悯农(一)》《悯农(二)》
  《江上渔者》《游子吟》《舟夜书所见》

四年级 (20首):
  《题西林壁》《雪梅》《暮江吟》《出塞》《凉州词》
  《夏日绝句》《别董大》《送元二使安西》《望天门山》
  《九月九日忆山东兄弟》《山行》《赠刘景文》《夜书所见》
  《江雪》《枫桥夜泊》《鹿柴》《暮江吟》《嫦娥》
  《凉州词(王之涣)》《出塞(王昌龄)》

五年级 (28首):
  《示儿》《题临安邸》《己亥杂诗》《山居秋暝》《枫桥夜泊》
  《长相思》《己亥杂诗》《牧童》《舟过安仁》《清平乐·村居》
  《石灰吟》《竹石》《马诗》《青松》《十五从军征》
  《出塞》《从军行》《秋夜将晓出篱门迎凉有感》《闻官军收河南河北》
  《凉州词(王翰)》《春夜喜雨》《早春呈水部张十八员外》《江上渔者》
  《泊船瓜洲》《游园不值》《卜算子·送鲍浩然之浙东》《浣溪沙》

💡 必背文言文: 《守株待兔》《囊萤夜读》《铁杵成针》
""",
    "写作模板": """
✍️ 小学作文万能模板 (上海卷)

【写人 (30分作文核心)】
  开头: 外貌特征 (2-3句) + 点题 (我有一个...的人)
  中间: 2件事 (一件表现优点, 一件表现"小缺点"→更真实)
    每件事: 前因 → 经过 (详写: 语言+动作+心理) → 结果
  结尾: 总结品质 + 点题 (我敬佩/喜欢/爱...)

【记事】
  开头: 场景 (时间+地点+天气) + 点 (那是我最X的一天)
  中间: 六要素串起来, 用"先...然后...接着...最后..."
  结尾: 感受+道理 (这件事让我明白...)

【写景】
  总: 在哪里? 什么季节? 总体感受?
  分: 按顺序 (从上到下/从远到近/按时间)
    每处景: 所见+所闻+所想 (五感+比喻拟人)
  总: 再次点题 + 抒情感慨

⚠️ 上海卷评分标准:
  一类文(27-30): 立意深+内容具体+语言生动+结构完整
  二类文(23-26): 立意明+内容较具体+语言通顺+结构完整
  三类文(18-22): 立意基本明+内容不够具体+语言基本通顺
  四类文(<18): 偏题+内容空+语病多
""",
}

# ─────────────────────────────────────────────
# 🧮 数学知识点 (人教版/沪教版)
# ─────────────────────────────────────────────
MATH_KNOWLEDGE = {
    "三年级重点": """
🧮 三年级数学重点 (人教版)

【计算 (重中之重!)】
  ✅ 万以内加减法 (进位+退位) — 每天5题, 不能错!
  ✅ 多位数乘一位数 (如 123×4) — 竖式对位
  ✅ 除数是一位数的除法 — 商中间/末尾有0是难点
  ✅ 分数初步认识: 1/2, 1/3, 1/4 (同分母比大小+加减)

【几何】
  ✅ 长方形和正方形周长 = (长+宽)×2 / 边长×4
  ✅ 面积单位: cm² / dm² / m² (进率100)
  ✅ 周长 vs 面积: 很多孩子混! 让孩子用手指"描"一圈周长,
     用手掌"盖"住面积, 一秒分清

【常见量】
  ✅ 时间: 时→分→秒 (60进制, 最容易错!)
  ✅ 质量: 克→千克→吨 (1000进制)
  ✅ 长度: mm→cm→dm→m→km

【应用题类型】
  1. 归一问题 (1台机器3小时产6个, 5台8小时产?)
  2. 归总问题 (每盒8支铅笔5盒, 平均分给10人?)
  3. 和倍问题 (和=40, 倍=4, 求两数)
  4. 差倍问题 (差=18, 倍=3, 求两数)
""",
    "四年级重点": """
🧮 四年级数学重点

【数与代数】
  ✅ 大数: 亿级读写 + 四舍五入到万位/亿位
  ✅ 三位数乘两位数 (如 125×24) — 乘法分配律简算
  ✅ 除数是两位数的除法 — 试商是难点 (四舍五入法)
  ✅ 运算定律: 交换律/结合律/分配律 (简算必用!)
  ✅ 小数意义: 0.1 = 1/10, 0.01 = 1/100 (进率10)

【几何】
  ✅ 平行与垂直 — 用三角板画
  ✅ 平行四边形和梯形特征
  ✅ 三角形内角和 = 180° (剪三个角拼一起最直观)
  ✅ 三角形分类: 按边(等腰/等边/不等边) + 按角(锐/直/钝)

【统计】
  ✅ 条形统计图 (一格代表几个)
  ✅ 平均数 = 总数÷份数

⚠️ 四年级是数学另一分水岭! 开始讲"抽象逻辑",
   应用题从"一步"变"两步/三步"
""",
    "五年级重点": """
🧮 五年级数学重点

【计算升级】
  ✅ 小数乘法 (小数点后位数相加定位)
  ✅ 小数除法 (除数是小数 → 都×10/100 变成整数)
  ✅ 分数加减法 (通分 → 分子变 → 约分 → 带分数)
  ✅ 分数乘除法 (乘=分子×分子/分母×分母, 除=倒过来乘)

【代数入门】
  ✅ 用字母表示数 (a+b=b+a, S=ab)
  ✅ 简易方程: 3x+5=20 → x=?
  ✅ 等式性质: 两边同时±×÷同一个数, 等式仍成立

【几何升级】
  ✅ 平行四边形面积 = 底×高 (割补成长方形!)
  ✅ 三角形面积 = 底×高÷2 (两个拼一个平行四边形)
  ✅ 梯形面积 = (上底+下底)×高÷2
  ✅ 圆的周长 = 2πr = πd, 圆面积 = πr² (π≈3.14)

【解决问题】
  ✅ 行程问题: 路程=速度×时间 (相遇/追及)
  ✅ 工程问题: 工作总量=效率×时间
  ✅ 浓度问题 (上海特色)
""",
    "易错点": """
⚠️ 小学生数学 TOP10 易错点

1. 周长 vs 面积 — 描一描 vs 盖一盖
2. 时间单位换算 — 60进制! (不是10/100)
3. 分数加减 — 忘了通分直接分子加分子
4. 小数乘法 — 小数点位数数错
5. 除法商有0 — 漏写中间的0 (如 306÷3 = 102, 漏0=12)
6. 应用题答句 — 忘了写答 (扣1分!)
7. 单位不统一 — 米和厘米直接算
8. 四舍五入 — 万位后面是5, 但前面是9 (995000≈100万)
9. 几何作图 — 不用尺规, 随手画 (扣过程分)
10. 抄题抄错 — 数字抄反 (9↔6, 3↔8)

💡 检查三步法:
  ① 数字抄对了吗?
  ② 单位统一了吗?
  ③ 答案合理吗? (如 1个苹果重100kg → 显然错)
""",
}

# ─────────────────────────────────────────────
# 📘 英语知识点 (牛津上海版)
# ─────────────────────────────────────────────
ENGLISH_KNOWLEDGE = {
    "三年级起点": """
🔤 三年级英语 (牛津上海版) — 从零开始

【26个字母】大写+小写 + 发音 (Phonics)
  A /æ/  B /b/  C /k/  D /d/  E /e/  F /f/ ...
  → 字母操 + 字母歌, 每天5分钟

【高频单词 (100个)】
  ☀️ 文具: pen, pencil, ruler, eraser, bag
  👨‍👩‍👧 家庭: father, mother, brother, sister, grandpa
  🐶 动物: cat, dog, pig, duck, bird
  🍎 水果: apple, banana, orange, pear, grape
  🎨 颜色: red, blue, green, yellow, black, white
  🔢 数字: one-ten (上海要学到 twenty!)

【基本句型】
  ✅ Hello! / Hi! / Good morning/afternoon/evening
  ✅ I'm + 姓名.  My name is + 姓名.
  ✅ How are you? — I'm fine, thank you.
  ✅ This is + 人/物.  That is + 人/物.
  ✅ Is this/that + 物? — Yes, it is. / No, it isn't.

【上海特色】
  上海三年级学音标! 这是全国多数省份没有的
  → 早学音标 = 早会自主拼读单词
""",
    "四年级进阶": """
🔤 四年级英语 (牛津上海版)

【核心语法】
  1️⃣ 一般现在时 (最重要!)
     I/You/We/They + 动词原形
     He/She/It + 动词s/es (三单!)
     → 动词变三单: 直接+s / s/x/ch/sh/o结尾+es / 辅音+y→i+es

  2️⃣ there be 句型
     There is + 单数/不可数.
     There are + 复数.
     → be动词看"就近原则"

  3️⃣ 情态动词 can
     I can swim.  Can you swim?  Yes, I can. / No, I can't.

【高频句型】
  ✅ What's your hobby? — I like + doing.
  ✅ What does your father do? — He's a + 职业.
  ✅ Would you like + 食物? — Yes, please. / No, thanks.

【考纲词汇量】600+ 词
【音标】48个音标全部学完 (上海进度快!)
""",
    "五年级提升": """
🔤 五年级英语 (牛津上海版)

【语法升级】
  1️⃣ 现在进行时: am/is/are + doing
     I'm reading.  She is dancing.  Are you listening?

  2️⃣ 一般过去时 (三年级没学!)
     规则动词: +ed (walked, played)
     不规则动词: go→went, do→did, have→had, eat→ate,
               see→saw, get→got, take→took, run→ran

  3️⃣ 一般将来时: will + 动词原形 / be going to + 动词原形

  4️⃣ 比较级: tall→taller, big→bigger, good→better, bad→worse
      最高级: tallest, biggest, best, worst

【写作】
  四会句子 (会读+会写+会译+会用)
  作文: 写人/写事/写物 (50-80词)

【考纲词汇量】900+ 词
【写作模板】
  My Hobby
  My hobby is ____.  I like ____ very much.
  I usually ____ on weekends.  ____ makes me happy.
  Do you like ____? Let's ____ together!
""",
    "音标速成": """
📣 48个音标速查表 (上海三年级开始学!)

【元音 (20个)】
  单元音 (12):
    /iː/ 衣长  /ɪ/ 衣短  /e/ 哎  /æ/ 哎扁
    /ɑː/ 啊长  /ɒ/ 哦短  /ɔː/ 哦长  /ʊ/ 乌短
    /uː/ 乌长  /ʌ/ 啊轻  /ɜː/ 额长  /ə/ 额轻
  双元音 (8):
    /eɪ/ 诶  /aɪ/ 爱  /ɔɪ/ 哦衣  /aʊ/ 奥
    /əʊ/ 欧  /ɪə/ 衣额  /eə/ 哎额  /ʊə/ 乌额

【辅音 (28个)】
  清辅音 (11): p/t/k/f/θ/s/ʃ/h/tʃ/tr/ts
  浊辅音 (17): b/d/g/v/ð/z/ʒ/r/dʒ/dr/dz/m/n/ŋ/l/w/j

💡 音标学习法:
  ① 每天学4个, 12天学完
  ② 字母组合记忆: ph=/f/, ck=/k/, sh=/ʃ/, th=/θ/或/ð/
  ③ 拼读练习: 把学过的单词用音标拼出来
""",
    "常见错误": """
❌ 小学生英语 TOP10 常见错误

1. 三单忘加s — "He like apples" → likes
2. there is/are 搞反 — "There are a book" → is
3. 动词原形/ing/ed 混 — "I am run" → running
4. 介词错 — "go to home" → go home (home前不加to!)
5. 字母大小写 — "i am a boy" → I am a boy (I永远大写!)
6. a/an 错 — "a apple" → an apple (元音开头用an)
7. 名词单复数 — "two dog" → two dogs
8. 时态标志词忘用 — "yesterday" 却用一般现在时
9. How many + 可数复数 — "How many apple" → apples
10. 作文忘了写句号 — 最后一个单词后要有 .

💡 检查口诀: 时态对吗? 三单加s了吗? 复数加s了吗?
""",
}

# ─────────────────────────────────────────────
# 📝 题库数据 (精选上海小学真题/模拟题)
# ─────────────────────────────────────────────
QUESTION_BANK = {
    "语文": [
        {"q": "看拼音写词语 (上海三年级统考真题):\n\n wén zhāng  (  )\n yǎng wàng  (  )\n huāng yě  (  )\n kǒu dí  (  )",
         "a": "文章 / 仰望 / 荒野 / 口笛",
         "tip": "⚠️ 上海卷看拼音写词语是必考题型, 错一个扣一分! 注意'望'下面是'王'不是'主'"},
        {"q": "按要求写句子:\n例: 湿润的东风走过荒野, 在竹林中吹着口笛。\n(仿写拟人句)",
         "a": "示例: 顽皮的雨滴在伞上尽情地跳舞。\n示例: 温柔的月光穿过树叶, 在地上画圈圈。",
         "tip": "拟人 = 把物当人写! 要有'人的动作/表情/心情'"},
        {"q": "《山行》后两句'停车坐爱枫林晚, 霜叶红于二月花'描绘了什么季节的景象? 表达了诗人什么感情?",
         "a": "深秋时节 · 表达了诗人对秋天枫叶的喜爱和赞美之情",
         "tip": "古诗词鉴赏三步法: ①答季节/景物 ②答特点 ③答情感"},
        {"q": "修改病句:\n  我们要养成良好的学习方法。",
         "a": "我们要养成良好的学习习惯。/ 我们要掌握正确的学习方法。",
         "tip": "词语搭配不当! '养成'配'习惯', '掌握'配'方法'"},
        {"q": "根据意思写成语:\n  ① 形容非常疲劳, 一点力气也没有了。(    )\n  ② 头顶着天, 脚踏着大地, 形容形象高大, 气概雄伟。(    )",
         "a": "① 筋疲力尽 (或精疲力竭)\n② 顶天立地",
         "tip": "成语是上海卷必考! 每天背2个, 积少成多"},
    ],
    "数学": [
        {"q": "一个长方形长8cm, 宽5cm, 它的周长是多少? 面积是多少? (上海三年级期末真题)",
         "a": "周长 = (8+5)×2 = 26 cm\n面积 = 8×5 = 40 cm²",
         "tip": "⚠️ 周长vs面积! 单位不一样! cm vs cm², 这是最容易混的题"},
        {"q": "计算: 125×25×8×4 (用简便方法)",
         "a": "(125×8) × (25×4) = 1000 × 100 = 100,000",
         "tip": "乘法交换律+结合律! 记住: 125×8=1000, 25×4=100, 这俩是黄金搭档"},
        {"q": "鸡兔同笼: 共有头10个, 脚28只, 鸡和兔各几只? (四年级奥数题)",
         "a": "假设全是鸡: 10×2=20只脚\n实际多: 28-20=8只脚\n每只兔多2只脚 → 兔=8÷2=4只\n鸡=10-4=6只",
         "tip": "假设法是鸡兔同笼万能解法! 先假设全是鸡(或全是兔), 再算差"},
        {"q": "解方程: 3x + 5 = 23",
         "a": "3x = 23 - 5 = 18\nx = 18 ÷ 3 = 6\n检验: 3×6+5=23 ✔",
         "tip": "等式性质: 两边同时减5, 再同时除以3. 最后一定要检验!"},
        {"q": "一个梯形, 上底4cm, 下底8cm, 高5cm, 面积是多少?",
         "a": "梯形面积 = (上底+下底)×高÷2 = (4+8)×5÷2 = 30 cm²",
         "tip": "÷2别忘了! 两个完全一样的梯形能拼成一个平行四边形"},
    ],
    "英语": [
        {"q": "用动词的正确形式填空:\nShe ____ (go) to school every day.\nLook! The children ____ (play) football.",
         "a": "goes (一般现在时三单)\nare playing (现在进行时)",
         "tip": "① every day → 一般现在时, she是三单→goes\n② Look! → 现在进行时→be+doing"},
        {"q": "按要求改写句子:\nI like apples. (改成一般疑问句)\n→ ____ you like apples?\nYes, I ____.",
         "a": "Do / do",
         "tip": "一般现在时变疑问句: 加Do/Does (三单用Does), 动词变原形"},
        {"q": "根据答句写问句:\n____? — I'm 10 years old.",
         "a": "How old are you?",
         "tip": "年龄 → How old. 上海三年级就考问句生成了"},
        {"q": "翻译: 我爸爸昨天去了上海。",
         "a": "My father went to Shanghai yesterday.",
         "tip": "yesterday → 一般过去时! go→went. '爸爸'是三单, 但过去时不区分单复数"},
        {"q": "选择: There ____ a pen and two books on the desk.\nA. is  B. are  C. have  D. has",
         "a": "A. is",
         "tip": "there be就近原则! 最近的是a pen(单数)→is. have/has不能和there连用!"},
    ],
    "科学": [
        {"q": "电路中, 电池的正极应该连接小灯泡的哪个金属点? (上海三年级科学真题)",
         "a": "底部的金属圆点 (负极连侧面的金属螺纹)",
         "tip": "电流从正极流出 → 小灯泡 → 回到负极, 形成闭合回路才会亮"},
        {"q": "把盐放入水中, 盐不见了, 水变咸了。这种现象叫什么?",
         "a": "溶解 · 盐溶解在水里形成了盐水溶液",
         "tip": "溶解 ≠ 消失! 盐还在水里, 尝味道就知道了. 可以用蒸发的方法把盐找回来"},
        {"q": "植物生长需要哪些条件? (至少写3个)",
         "a": "阳光 · 水 · 空气 (二氧化碳) · 适宜温度 · 养分",
         "tip": "光合作用: 二氧化碳+水 →(阳光+叶绿素)→ 氧气+有机物"},
        {"q": "磁铁有几个磁极? 分别叫什么? 两个相同磁极靠近会怎样?",
         "a": "2个磁极 · 南极(S)和北极(N) · 相同磁极互相排斥, 不同磁极互相吸引",
         "tip": "记住: 同极相斥, 异极相吸. 这是指南针的原理!"},
        {"q": "下列动物哪些是脊椎动物? 蚂蚁 / 金鱼 / 蜗牛 / 麻雀 / 蜘蛛 / 海豚",
         "a": "脊椎动物: 金鱼 / 麻雀 / 海豚 (有脊椎骨)\n无脊椎动物: 蚂蚁 / 蜗牛 / 蜘蛛",
         "tip": "判断方法: 摸摸自己后背中间, 那根骨头就是脊椎! 鱼/鸟/哺乳动物都是脊椎动物"},
    ],
}

# ─────────────────────────────────────────────
# 🎯 智能试卷题库 (各年级×学科×知识点)
# ─────────────────────────────────────────────
EXAM_BANK = {
    "三年级上": {
        "数学": {
            "万以内加减法": [
                {"q": "计算: 3456 + 2789 = ?", "type": "fill", "answer": "6245", "score": 5, "topic": "计算-加法"},
                {"q": "计算: 7000 - 3654 = ?", "type": "fill", "answer": "3346", "score": 5, "topic": "计算-减法"},
                {"q": "计算: 4567 + 1234 + 890 = ?", "type": "fill", "answer": "6691", "score": 5, "topic": "计算-连加"},
                {"q": "计算: 8000 - 1234 - 567 = ?", "type": "fill", "answer": "6199", "score": 5, "topic": "计算-连减"},
                {"q": "估算: 498 + 302 ≈ ?", "type": "fill", "answer": "800", "score": 5, "topic": "估算"},
            ],
            "多位数乘一位数": [
                {"q": "计算: 123 × 4 = ?", "type": "fill", "answer": "492", "score": 5, "topic": "乘法-基础"},
                {"q": "计算: 250 × 3 = ?", "type": "fill", "answer": "750", "score": 5, "topic": "乘法-有0"},
                {"q": "计算: 105 × 6 = ?", "type": "fill", "answer": "630", "score": 5, "topic": "乘法-中间有0"},
                {"q": "计算: 198 × 5 ≈ ? (先估算)", "type": "fill", "answer": "1000", "score": 5, "topic": "估算乘法"},
                {"q": "判断: 125 × 8 = 1000 (对/错)", "type": "choice", "options": ["对", "错"], "answer": 0, "score": 5, "topic": "乘法-巧算"},
            ],
            "除数是一位数的除法": [
                {"q": "计算: 126 ÷ 3 = ?", "type": "fill", "answer": "42", "score": 5, "topic": "除法-基础"},
                {"q": "计算: 208 ÷ 4 = ?", "type": "fill", "answer": "52", "score": 5, "topic": "除法-基础"},
                {"q": "计算: 306 ÷ 3 = ?", "type": "fill", "answer": "102", "score": 5, "topic": "除法-商中间有0"},
                {"q": "计算: 560 ÷ 7 = ?", "type": "fill", "answer": "80", "score": 5, "topic": "除法-商末尾有0"},
                {"q": "47 ÷ 5 的余数是?", "type": "fill", "answer": "2", "score": 5, "topic": "除法-余数"},
            ],
            "长方形和正方形": [
                {"q": "长方形长6cm, 宽4cm, 周长是多少?", "type": "fill", "answer": "20", "score": 5, "topic": "周长-长方形", "unit": "cm"},
                {"q": "正方形边长5cm, 周长是多少?", "type": "fill", "answer": "20", "score": 5, "topic": "周长-正方形", "unit": "cm"},
                {"q": "长方形长8cm, 宽3cm, 面积是多少?", "type": "fill", "answer": "24", "score": 5, "topic": "面积-长方形", "unit": "cm²"},
                {"q": "正方形边长7cm, 面积是多少?", "type": "fill", "answer": "49", "score": 5, "topic": "面积-正方形", "unit": "cm²"},
                {"q": "周长和面积的单位一样吗? (是/否)", "type": "choice", "options": ["是", "否"], "answer": 1, "score": 5, "topic": "周长vs面积"},
            ],
        },
        "语文": {
            "生字词": [
                {"q": "看拼音写词语: wén zhāng (  )", "type": "fill", "answer": "文章", "score": 5, "topic": "看拼音写字"},
                {"q": "看拼音写词语: yǎng wàng (  )", "type": "fill", "answer": "仰望", "score": 5, "topic": "看拼音写字"},
                {"q": "看拼音写词语: huāng yě (  )", "type": "fill", "answer": "荒野", "score": 5, "topic": "看拼音写字"},
                {"q": "选字填空: (历 厉)史、(在 再)见", "type": "fill", "answer": "历/再", "score": 5, "topic": "形近字"},
                {"q": "给'口'加偏旁, 写3个不同的字", "type": "fill", "answer": "吃/叫/唱/吹/叶...(任意3个)", "score": 5, "topic": "加偏旁写字"},
            ],
            "古诗文": [
                {"q": "《山行》中'停车坐爱枫林晚'的下一句是?", "type": "fill", "answer": "霜叶红于二月花", "score": 5, "topic": "古诗-背诵"},
                {"q": "《赠刘景文》'荷尽已无擎雨盖'的下一句是?", "type": "fill", "answer": "菊残犹有傲霜枝", "score": 5, "topic": "古诗-背诵"},
                {"q": '"一年好景君须记"的下一句是?', "type": "fill", "answer": "最是橙黄橘绿时", "score": 5, "topic": "古诗-背诵"},
                {"q": "《夜书所见》作者是? (朝代+姓名)", "type": "fill", "answer": "南宋·叶绍翁", "score": 5, "topic": "古诗-作者"},
                {"q": '"萧萧梧叶送寒声"中"萧萧"是什么意思?', "type": "fill", "answer": "风吹落叶声", "score": 5, "topic": "古诗-词语解释"},
            ],
            "阅读理解": [
                {"q": "《花的学校》是哪位作家的作品?", "type": "fill", "answer": "泰戈尔", "score": 5, "topic": "课文-作者"},
                {"q": "《铺满金色巴掌的水泥道》中'金色巴掌'指什么?", "type": "fill", "answer": "梧桐树叶", "score": 5, "topic": "课文-比喻"},
                {"q": "《秋天的雨》作者用了什么修辞手法描写颜色?", "type": "fill", "answer": "拟人/比喻", "score": 5, "topic": "课文-修辞"},
                {"q": '"读了《金色的草地》, 草地一天中颜色有什么变化?" 简述', "type": "fill", "answer": "早上绿色→中午金色→傍晚绿色", "score": 5, "topic": "课文-内容理解"},
                {"q": "预测阅读策略: 读故事时应该边读边做什么?", "type": "fill", "answer": "预测接下来会发生什么", "score": 5, "topic": "阅读方法"},
            ],
        },
        "英语": {
            "字母与音标": [
                {"q": "写出字母表中H后面的3个大写字母", "type": "fill", "answer": "I J K", "score": 5, "topic": "字母顺序"},
                {"q": "字母O的音标是?", "type": "fill", "answer": "/ɒ/ 或 /əʊ/", "score": 5, "topic": "音标"},
                {"q": "判断: 字母R的发音里有 /aː/ (对/错)", "type": "choice", "options": ["对", "错"], "answer": 1, "score": 5, "topic": "字母发音"},
                {"q": "Apple 的首字母大写形式是?", "type": "fill", "answer": "A", "score": 5, "topic": "大小写"},
                {"q": "按顺序写出5个元音字母 (大写)", "type": "fill", "answer": "A E I O U", "score": 5, "topic": "元音字母"},
            ],
            "基础词汇": [
                {"q": "英译汉: pencil bag", "type": "fill", "answer": "铅笔袋", "score": 5, "topic": "文具词汇"},
                {"q": "英译汉: father", "type": "fill", "answer": "父亲/爸爸", "score": 5, "topic": "家庭词汇"},
                {"q": "英译汉: orange juice", "type": "fill", "answer": "橙汁", "score": 5, "topic": "食物词汇"},
                {"q": "汉译英: 红色", "type": "fill", "answer": "red", "score": 5, "topic": "颜色词汇"},
                {"q": "汉译英: 十六", "type": "fill", "answer": "sixteen", "score": 5, "topic": "数字"},
            ],
            "基本句型": [
                {"q": "填空: Hello! ____ name is Tom.", "type": "fill", "answer": "My", "score": 5, "topic": "自我介绍"},
                {"q": "____ you fine? — Yes, I am.", "type": "fill", "answer": "Are", "score": 5, "topic": "问候"},
                {"q": "This ____ my book. (is/are)", "type": "choice", "options": ["is", "are"], "answer": 0, "score": 5, "topic": "指示代词"},
                {"q": "Is this your pen? — No, it ____.", "type": "fill", "answer": "isn't", "score": 5, "topic": "一般疑问句"},
                {"q": "翻译: 你好吗?", "type": "fill", "answer": "How are you?", "score": 5, "topic": "中英互译"},
            ],
        },
    },
    "四年级下": {
        "数学": {
            "三位数乘两位数": [
                {"q": "计算: 125 × 16 = ?", "type": "fill", "answer": "2000", "score": 5, "topic": "乘法-基础"},
                {"q": "计算: 248 × 35 = ?", "type": "fill", "answer": "8680", "score": 5, "topic": "乘法-竖式"},
                {"q": "计算: 108 × 24 = ?", "type": "fill", "answer": "2592", "score": 5, "topic": "乘法-中间有0"},
                {"q": "用简便方法: 125 × 8 × 7 = ?", "type": "fill", "answer": "7000", "score": 5, "topic": "乘法-简算"},
                {"q": "估算: 498 × 21 ≈ ?", "type": "fill", "answer": "10000", "score": 5, "topic": "乘法-估算"},
            ],
            "除数是两位数的除法": [
                {"q": "计算: 840 ÷ 35 = ?", "type": "fill", "answer": "24", "score": 5, "topic": "除法-基础"},
                {"q": "计算: 936 ÷ 26 = ?", "type": "fill", "answer": "36", "score": 5, "topic": "除法-竖式"},
                {"q": "计算: 728 ÷ 28 = ?", "type": "fill", "answer": "26", "score": 5, "topic": "除法-竖式"},
                {"q": "试商时, 把28看作30试商, 商可能偏大还是偏小?", "type": "choice", "options": ["偏大", "偏小"], "answer": 1, "score": 5, "topic": "除法-试商"},
                {"q": "625 ÷ 25 = ? (口算)", "type": "fill", "answer": "25", "score": 5, "topic": "除法-巧算"},
            ],
            "运算定律与简便计算": [
                {"q": "用运算定律简算: 25 + 37 + 75 = ?", "type": "fill", "answer": "137", "score": 5, "topic": "加法交换律"},
                {"q": "用运算定律简算: 125 × 32 = ?", "type": "fill", "answer": "4000", "score": 5, "topic": "乘法结合律"},
                {"q": "用运算定律简算: 99 × 36 = ?", "type": "fill", "answer": "3564", "score": 5, "topic": "乘法分配律"},
                {"q": "判断: a × (b + c) = a × b + a × c (对/错)", "type": "choice", "options": ["对", "错"], "answer": 0, "score": 5, "topic": "乘法分配律"},
                {"q": "简算: 48 + 79 + 52 = ?", "type": "fill", "answer": "179", "score": 5, "topic": "加法交换律"},
            ],
            "平行四边形与梯形": [
                {"q": "平行四边形有几组对边平行?", "type": "fill", "answer": "2组", "score": 5, "topic": "平行四边形-特征"},
                {"q": "梯形有几组对边平行?", "type": "fill", "answer": "1组", "score": 5, "topic": "梯形-特征"},
                {"q": "三角形内角和是多少度?", "type": "fill", "answer": "180°", "score": 5, "topic": "三角形-内角和"},
                {"q": "平行四边形面积公式是?", "type": "fill", "answer": "底×高", "score": 5, "topic": "平行四边形-面积"},
                {"q": "梯形面积公式是?", "type": "fill", "answer": "(上底+下底)×高÷2", "score": 5, "topic": "梯形-面积"},
            ],
            "小数的意义和性质": [
                {"q": "0.1 表示几分之一?", "type": "fill", "answer": "十分之一", "score": 5, "topic": "小数-意义"},
                {"q": "0.01 表示几分之一?", "type": "fill", "answer": "百分之一", "score": 5, "topic": "小数-意义"},
                {"q": "比较大小: 0.5 ○ 0.50 (填 > < =)", "type": "choice", "options": [">", "<", "="], "answer": 2, "score": 5, "topic": "小数-性质"},
                {"q": "2.05 米 = 多少厘米?", "type": "fill", "answer": "205", "score": 5, "topic": "小数-单位换算"},
                {"q": "化简小数: 3.200 = ?", "type": "fill", "answer": "3.2", "score": 5, "topic": "小数-化简"},
            ],
        },
        "语文": {
            "古诗文": [
                {"q": "《题西林壁》作者是谁?", "type": "fill", "answer": "苏轼", "score": 5, "topic": "古诗-作者"},
                {"q": '"不识庐山真面目"的下一句是?', "type": "fill", "answer": "只缘身在此山中", "score": 5, "topic": "古诗-背诵"},
                {"q": "《雪梅》'梅须逊雪三分白'的下一句是?", "type": "fill", "answer": "雪却输梅一段香", "score": 5, "topic": "古诗-背诵"},
                {"q": "《暮江吟》'一道残阳铺水中'的下一句是?", "type": "fill", "answer": "半江瑟瑟半江红", "score": 5, "topic": "古诗-背诵"},
                {"q": '"可怜九月初三夜"的下一句是?', "type": "fill", "answer": "露似真珠月似弓", "score": 5, "topic": "古诗-背诵"},
            ],
            "阅读方法": [
                {"q": "阅读时的'提问策略'可以从哪几个角度提问? (写2个)", "type": "fill", "answer": "内容/写法/启示 (任选2)", "score": 5, "topic": "阅读-提问策略"},
                {"q": "写一件事要按什么顺序? (六要素是什么?)", "type": "fill", "answer": "时间/地点/人物/起因/经过/结果", "score": 5, "topic": "写作-六要素"},
                {"q": "写观察日记要连续观察并做什么记录?", "type": "fill", "answer": "数据/变化记录", "score": 5, "topic": "写作-观察日记"},
                {"q": "《爬山虎的脚》作者是谁?", "type": "fill", "answer": "叶圣陶", "score": 5, "topic": "课文-作者"},
                {"q": "《蟋蟀的住宅》作者是谁?", "type": "fill", "answer": "法布尔", "score": 5, "topic": "课文-作者"},
            ],
            "词语与句子": [
                {"q": "写出3个表示时间的四字词语", "type": "fill", "answer": "光阴似箭/日月如梭/白驹过隙...", "score": 5, "topic": "词语积累"},
                {"q": "修改病句: 我们要养成良好的学习方法。", "type": "fill", "answer": "我们要养成良好的学习习惯。", "score": 5, "topic": "修改病句"},
                {"q": "仿写拟人句: 湿润的东风走过荒野。", "type": "fill", "answer": "顽皮的雨滴在伞上跳舞。(示例)", "score": 5, "topic": "仿写-拟人"},
                {"q": "写出一句反问句 (不能加问号以外标点)", "type": "fill", "answer": "难道我们不应该努力学习吗?", "score": 5, "topic": "句式-反问"},
                {"q": "写出一句比喻句", "type": "fill", "answer": "弯弯的月亮像小船。(示例)", "score": 5, "topic": "句式-比喻"},
            ],
        },
        "英语": {
            "一般现在时": [
                {"q": "She ____ (go) to school every day.", "type": "fill", "answer": "goes", "score": 5, "topic": "时态-三单"},
                {"q": "Tom and Jack ____ (play) football after school.", "type": "fill", "answer": "play", "score": 5, "topic": "时态-复数"},
                {"q": "He ____ (not like) apples.", "type": "fill", "answer": "doesn't like", "score": 5, "topic": "时态-否定"},
                {"q": "____ you ____ (have) breakfast every morning?", "type": "fill", "answer": "Do / have", "score": 5, "topic": "时态-疑问"},
                {"q": "动词三单: watch → ____", "type": "fill", "answer": "watches", "score": 5, "topic": "三单变化"},
            ],
            "there be 句型": [
                {"q": "There ____ a pen and two books on the desk.", "type": "choice", "options": ["is", "are", "have"], "answer": 0, "score": 5, "topic": "there be-就近原则"},
                {"q": "There ____ many students in the classroom.", "type": "fill", "answer": "are", "score": 5, "topic": "there be-复数"},
                {"q": "There ____ (not be) any milk in the glass.", "type": "fill", "answer": "isn't", "score": 5, "topic": "there be-否定"},
                {"q": "____ there a library near your home?", "type": "fill", "answer": "Is", "score": 5, "topic": "there be-疑问"},
                {"q": "There be句型和have/has能连用吗? (能/不能)", "type": "choice", "options": ["能", "不能"], "answer": 1, "score": 5, "topic": "there be-区别"},
            ],
            "情态动词 can": [
                {"q": "I ____ swim very well.", "type": "fill", "answer": "can", "score": 5, "topic": "can-能力"},
                {"q": "____ you speak English?", "type": "fill", "answer": "Can", "score": 5, "topic": "can-疑问"},
                {"q": "She ____ (not) ride a bike yet.", "type": "fill", "answer": "can't", "score": 5, "topic": "can-否定"},
                {"q": "Can you help me? — ____ (当然可以)", "type": "fill", "answer": "Sure/Of course/Yes, I can", "score": 5, "topic": "can-回答"},
                {"q": "can 后面动词用什么形式?", "type": "fill", "answer": "原形", "score": 5, "topic": "can-语法"},
            ],
        },
    },
    "五年级上": {
        "数学": {
            "小数乘法": [
                {"q": "计算: 2.5 × 4 = ?", "type": "fill", "answer": "10", "score": 5, "topic": "小数乘法-基础"},
                {"q": "计算: 0.36 × 5 = ?", "type": "fill", "answer": "1.8", "score": 5, "topic": "小数乘法-基础"},
                {"q": "计算: 1.25 × 0.8 = ?", "type": "fill", "answer": "1", "score": 5, "topic": "小数乘法-巧算"},
                {"q": "0.7 × 0.03 的积有几位小数?", "type": "fill", "answer": "3位", "score": 5, "topic": "小数乘法-位数"},
                {"q": "简算: 9.9 × 25 = ?", "type": "fill", "answer": "247.5", "score": 5, "topic": "小数乘法-简算"},
            ],
            "小数除法": [
                {"q": "计算: 12.5 ÷ 5 = ?", "type": "fill", "answer": "2.5", "score": 5, "topic": "小数除法-基础"},
                {"q": "计算: 7.2 ÷ 0.9 = ?", "type": "fill", "answer": "8", "score": 5, "topic": "小数除法-除数是小数"},
                {"q": "计算: 15 ÷ 0.25 = ?", "type": "fill", "answer": "60", "score": 5, "topic": "小数除法-巧算"},
                {"q": "判断: 一个数除以小于1的小数, 商比被除数大 (对/错)", "type": "choice", "options": ["对", "错"], "answer": 0, "score": 5, "topic": "小数除法-规律"},
                {"q": "计算: 3.6 ÷ 0.4 = ?", "type": "fill", "answer": "9", "score": 5, "topic": "小数除法-基础"},
            ],
            "简易方程": [
                {"q": "解方程: 3x + 5 = 20", "type": "fill", "answer": "x = 5", "score": 5, "topic": "方程-基础"},
                {"q": "解方程: 5x - 12 = 33", "type": "fill", "answer": "x = 9", "score": 5, "topic": "方程-基础"},
                {"q": "解方程: 2(x + 3) = 16", "type": "fill", "answer": "x = 5", "score": 5, "topic": "方程-括号"},
                {"q": "用字母表示: 路程 = 速度 × ?", "type": "fill", "answer": "时间 (s = v × t)", "score": 5, "topic": "用字母表示数"},
                {"q": "等式两边同时加/减/乘/除同一个数, 等式还成立吗?", "type": "choice", "options": ["成立", "不成立"], "answer": 0, "score": 5, "topic": "等式性质"},
            ],
            "多边形面积": [
                {"q": "平行四边形底8cm, 高5cm, 面积是?", "type": "fill", "answer": "40", "score": 5, "topic": "平行四边形面积", "unit": "cm²"},
                {"q": "三角形底6cm, 高4cm, 面积是?", "type": "fill", "answer": "12", "score": 5, "topic": "三角形面积", "unit": "cm²"},
                {"q": "梯形上底3cm, 下底7cm, 高5cm, 面积是?", "type": "fill", "answer": "25", "score": 5, "topic": "梯形面积", "unit": "cm²"},
                {"q": "两个完全一样的三角形可以拼成一个什么图形?", "type": "fill", "answer": "平行四边形", "score": 5, "topic": "三角形-拼图"},
                {"q": "三角形面积公式要除以几?", "type": "fill", "answer": "÷2", "score": 5, "topic": "三角形面积-易错点"},
            ],
        },
        "英语": {
            "现在进行时": [
                {"q": "Look! The children ____ (play) football.", "type": "fill", "answer": "are playing", "score": 5, "topic": "时态-进行时"},
                {"q": "Listen! Someone ____ (knock) at the door.", "type": "fill", "answer": "is knocking", "score": 5, "topic": "时态-进行时"},
                {"q": "She ____ (read) a book in her room now.", "type": "fill", "answer": "is reading", "score": 5, "topic": "时态-进行时"},
                {"q": "现在进行时结构: be + ____", "type": "fill", "answer": "doing (现在分词)", "score": 5, "topic": "时态-结构"},
                {"q": "动词现在分词: run → ____", "type": "fill", "answer": "running", "score": 5, "topic": "现在分词变化"},
            ],
            "一般过去时": [
                {"q": "Yesterday I ____ (go) to the park.", "type": "fill", "answer": "went", "score": 5, "topic": "过去时-不规则"},
                {"q": "She ____ (have) lunch at 12:00 yesterday.", "type": "fill", "answer": "had", "score": 5, "topic": "过去时-不规则"},
                {"q": "Tom ____ (play) basketball last Sunday.", "type": "fill", "answer": "played", "score": 5, "topic": "过去时-规则"},
                {"q": "不规则动词: see → ____", "type": "fill", "answer": "saw", "score": 5, "topic": "过去时-不规则表"},
                {"q": "不规则动词: eat → ____", "type": "fill", "answer": "ate", "score": 5, "topic": "过去时-不规则表"},
            ],
            "一般将来时": [
                {"q": "Tomorrow we ____ (visit) the museum.", "type": "fill", "answer": "will visit / are going to visit", "score": 5, "topic": "将来时-will/be going to"},
                {"q": "He ____ (buy) a new bike next month.", "type": "fill", "answer": "will buy / is going to buy", "score": 5, "topic": "将来时"},
                {"q": "一般将来时两种结构是? (写出)", "type": "fill", "answer": "will + 动词原形 / be going to + 动词原形", "score": 5, "topic": "将来时-结构"},
                {"q": "Next week 用什么时态?", "type": "fill", "answer": "一般将来时", "score": 5, "topic": "将来时-时间标志"},
                {"q": "翻译: 我明天要去上海。", "type": "fill", "answer": "I will go to Shanghai tomorrow.", "score": 5, "topic": "将来时-翻译"},
            ],
        },
    },
}

# 薄弱点与知识点标签映射 (用于自动推荐复习)
TOPIC_TO_KNOWLEDGE = {
    # 数学薄弱点 → 数学知识点
    "计算": ("🧮 数学", "三年级重点"),
    "小数": ("🧮 数学", "五年级重点"),
    "运算定律": ("🧮 数学", "四年级重点"),
    "几何": ("🧮 数学", "四年级重点"),
    "方程": ("🧮 数学", "五年级重点"),
    "应用题": ("🧮 数学", "三年级重点"),
    "周长": ("🧮 数学", "三年级重点"),
    "面积": ("🧮 数学", "三年级重点"),
    # 英语薄弱点 → 英语知识点
    "时态": ("🔤 英语", "四年级进阶"),
    "一般现在时": ("🔤 英语", "四年级进阶"),
    "现在进行时": ("🔤 英语", "五年级提升"),
    "一般过去时": ("🔤 英语", "五年级提升"),
    "一般将来时": ("🔤 英语", "五年级提升"),
    "there be": ("🔤 英语", "四年级进阶"),
    "三单": ("🔤 英语", "四年级进阶"),
    "音标": ("🔤 英语", "音标速成"),
    # 语文薄弱点 → 语文知识点
    "古诗": ("📖 语文", "古诗文必背"),
    "写作": ("📖 语文", "写作模板"),
    "阅读": ("📖 语文", "三年级下"),
    "生字": ("📖 语文", "三年级上"),
}

# ─────────────────────────────────────────────
# 🎨 UI 辅助函数
# ─────────────────────────────────────────────
def _mk_color_button(parent, text, bg, command, width=16):
    """小朋友风格的彩色按钮"""
    btn = tk.Button(parent, text=text, font=PALETTE["body_font"],
                    bg=bg, fg=PALETTE["text"],
                    activebackground=PALETTE["white"],
                    relief="flat", bd=0, padx=12, pady=6,
                    width=width, cursor="hand2", command=command)
    return btn


def _mk_hover_tip(widget, tip_text):
    """给任意控件加❓悬浮提示"""
    tip_win = {"win": None, "text": ""}

    def enter(e):
        x = widget.winfo_rootx() + 20
        y = widget.winfo_rooty() + widget.winfo_height() + 5
        tip_win["win"] = tw = tk.Toplevel(widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(tw, text=tip_text, bg=PALETTE["sun"], fg=PALETTE["text"],
                 font=("Microsoft YaHei", 10), padx=8, pady=4,
                 relief="solid", bd=1, justify="left",
                 wraplength=320).pack()

    def leave(e):
        if tip_win["win"]:
            tip_win["win"].destroy()
            tip_win["win"] = None

    widget.bind("<Enter>", enter)
    widget.bind("<Leave>", leave)


def _mk_emoji_label(parent, emoji, text, color=PALETTE["text"]):
    """卡通 emoji label"""
    frame = tk.Frame(parent, bg=PALETTE["bg"])
    tk.Label(frame, text=emoji, font=PALETTE["emoji_font"],
             bg=PALETTE["bg"]).pack(side=tk.LEFT)
    tk.Label(frame, text=text, font=PALETTE["body_font"],
             bg=PALETTE["bg"], fg=color).pack(side=tk.LEFT)
    return frame


# ─────────────────────────────────────────────
# 🚀 主入口: 家教辅导窗口
# ─────────────────────────────────────────────
def _show_tutor_helper(root):
    """📚 家教辅导助手 — 小朋友的学习好帮手"""
    global _FONT_WIDGETS, _FONT_SCALE
    _FONT_WIDGETS = []  # 每次打开重置
    _FONT_SCALE = 1.0

    dlg = tk.Toplevel(root)
    dlg.title("📚 家教辅导小助手 · 上海小学生专属")
    dlg.configure(bg=PALETTE["bg"])
    dlg.geometry("1080x780")
    dlg.minsize(960, 700)

    # 顶部 Banner
    banner = tk.Frame(dlg, bg=PALETTE["pink"], height=60)
    banner.pack(fill=tk.X)
    banner.pack_propagate(False)
    tk.Label(banner, text="🦊 家教辅导小助手",
             font=("Comic Sans MS", 22, "bold"),
             bg=PALETTE["pink"], fg=PALETTE["pink_dark"]).pack(side=tk.LEFT, padx=16, pady=8)
    tk.Label(banner, text="— 上海小学生专属 · 部编版体系 —",
             font=PALETTE["body_bold"],
             bg=PALETTE["pink"], fg=PALETTE["pink_dark"]).pack(side=tk.LEFT, pady=8)

    # 🔧 字体调节控件 (A- / A+)
    font_lbl = tk.Label(banner, text="字体:", font=PALETTE["body_bold"],
                        bg=PALETTE["pink"], fg=PALETTE["pink_dark"])
    font_lbl.pack(side=tk.RIGHT, padx=(0, 8), pady=8)

    def _zoom_out():
        _apply_font_scale(max(0.8, _FONT_SCALE - 0.15))

    def _zoom_in():
        _apply_font_scale(min(3.0, _FONT_SCALE + 0.15))

    btn_a_plus = tk.Button(banner, text="A+", font=("Arial", 13, "bold"),
                           bg=PALETTE["white"], fg=PALETTE["pink_dark"],
                           relief="flat", bd=0, padx=8, pady=2, cursor="hand2",
                           command=_zoom_in)
    btn_a_plus.pack(side=tk.RIGHT, padx=2, pady=10)
    btn_a_minus = tk.Button(banner, text="A-", font=("Arial", 13, "bold"),
                            bg=PALETTE["white"], fg=PALETTE["pink_dark"],
                            relief="flat", bd=0, padx=8, pady=2, cursor="hand2",
                            command=_zoom_out)
    btn_a_minus.pack(side=tk.RIGHT, padx=2, pady=10)

    tk.Label(banner, text=f"📅 {datetime.now().strftime('%Y-%m-%d')}",
             font=PALETTE["body_font"],
             bg=PALETTE["pink"], fg=PALETTE["pink_dark"]).pack(side=tk.RIGHT, padx=16)

    # Notebook Tabs
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except Exception:
        pass
    style.configure("TNotebook", background=PALETTE["bg"], borderwidth=0)
    style.configure("TNotebook.Tab",
                    padding=[16, 8],
                    font=("Comic Sans MS", 12, "bold"))
    style.map("TNotebook.Tab",
              background=[("selected", PALETTE["pink"]), ("!selected", PALETTE["white"])],
              foreground=[("selected", PALETTE["pink_dark"]), ("!selected", PALETTE["text"])])

    nb = ttk.Notebook(dlg)
    nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

    # ═══════════════════════════════════════
    # Tab 1: 🎁 软件网址
    # ═══════════════════════════════════════
    tab_software = tk.Frame(nb, bg=PALETTE["bg"])
    nb.add(tab_software, text="🎁 软件网址")

    # 分类容器
    cats = {}
    for item in SOFTWARE_LIST:
        cats.setdefault(item["cat"], []).append(item)

    sw_canvas = tk.Canvas(tab_software, bg=PALETTE["bg"], highlightthickness=0)
    sw_scroll = ttk.Scrollbar(tab_software, orient="vertical", command=sw_canvas.yview)
    sw_inner = tk.Frame(sw_canvas, bg=PALETTE["bg"])
    sw_inner.bind("<Configure>", lambda e: sw_canvas.configure(scrollregion=sw_canvas.bbox("all")))
    sw_canvas.create_window((0, 0), window=sw_inner, anchor="nw", width=1040)
    sw_canvas.configure(yscrollcommand=sw_scroll.set)
    sw_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    sw_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    cat_colors = {
        "🎁 官方免费": PALETTE["sky"],
        "✏️ 作业批改": PALETTE["sun"],
        "📖 同步课程": PALETTE["mint"],
        "🔤 英语专项": PALETTE["lavender"],
        "🧠 思维拓展": PALETTE["pink"],
    }

    for cat_name, items in cats.items():
        color = cat_colors.get(cat_name, PALETTE["white"])
        cat_frame = tk.Frame(sw_inner, bg=PALETTE["bg"])
        cat_frame.pack(fill=tk.X, padx=6, pady=(12, 4))

        tk.Label(cat_frame, text=cat_name,
                 font=("Comic Sans MS", 14, "bold"),
                 bg=PALETTE["bg"], fg=PALETTE["text"]).pack(anchor="w")

        for item in items:
            card = tk.Frame(cat_frame, bg=color, bd=0, highlightthickness=1,
                            highlightbackground=PALETTE["white"])
            card.pack(fill=tk.X, padx=4, pady=3)

            # 第一行: 名称 + 打开链接按钮
            row1 = tk.Frame(card, bg=color)
            row1.pack(fill=tk.X, padx=10, pady=(8, 2))

            name_lbl = tk.Label(row1, text=f"🔗 {item['name']}",
                                font=PALETTE["title_font"],
                                bg=color, fg=PALETTE["text"], cursor="hand2")
            name_lbl.pack(side=tk.LEFT)
            _reg_font(name_lbl, PALETTE["title_font"])
            name_lbl.bind("<Button-1>", lambda e, u=item["url"]: webbrowser.open(u))
            _mk_hover_tip(name_lbl, f"点击打开: {item['url']}")

            open_btn = _mk_color_button(row1, "打开网页", PALETTE["white"],
                                        lambda u=item["url"]: webbrowser.open(u), width=10)
            open_btn.pack(side=tk.RIGHT, padx=4)

            # 第二行: 网址
            url_lbl = tk.Label(card, text=f"   🌐 {item['url']}",
                               font=PALETTE["small_font"],
                               bg=color, fg=PALETTE["text_light"])
            url_lbl.pack(anchor="w", padx=10)
            _reg_font(url_lbl, PALETTE["small_font"])

            # 第三行: 功能点
            func_lbl = tk.Label(card, text=f"   ✨ {item['func']}",
                                font=PALETTE["body_font"],
                                bg=color, fg=PALETTE["text"],
                                wraplength=980, justify="left")
            func_lbl.pack(anchor="w", padx=10, pady=(2, 2))
            _reg_font(func_lbl, PALETTE["body_font"])

            # 第四行: ❓注释
            tip_row = tk.Frame(card, bg=color)
            tip_row.pack(fill=tk.X, padx=10, pady=(0, 8))
            tip_icon = tk.Label(tip_row, text="❓", font=PALETTE["emoji_font"],
                                bg=color, cursor="hand2")
            tip_icon.pack(side=tk.LEFT)
            tip_text = tk.Label(tip_row, text=item["tip"],
                                font=PALETTE["body_font"],
                                bg=color, fg=PALETTE["pink_dark"],
                                wraplength=960, justify="left")
            tip_text.pack(side=tk.LEFT, padx=4)
            _reg_font(tip_text, PALETTE["body_font"])

        # 分隔线
        tk.Frame(sw_inner, bg=PALETTE["white"], height=2).pack(fill=tk.X, padx=10, pady=4)

    # ═══════════════════════════════════════
    # Tab 2: 👶 小孩学习情况
    # ═══════════════════════════════════════
    tab_profile = tk.Frame(nb, bg=PALETTE["bg"])
    nb.add(tab_profile, text="👶 学习情况")

    tk.Label(tab_profile, text="👶 小朋友的学习档案",
             font=("Comic Sans MS", 16, "bold"),
             bg=PALETTE["bg"], fg=PALETTE["pink_dark"]).pack(pady=(14, 6))
    tk.Label(tab_profile, text="记录薄弱点、优点、概念理解不足 — 知彼知己, 百战不殆!",
             font=("Microsoft YaHei", 10),
             bg=PALETTE["bg"], fg=PALETTE["text_light"]).pack()

    form = tk.Frame(tab_profile, bg=PALETTE["bg"])
    form.pack(fill=tk.X, padx=20, pady=10)

    profile = _load_profile()

    def _row(parent, label, key, is_text=False):
        r = tk.Frame(parent, bg=PALETTE["bg"]); r.pack(fill=tk.X, pady=6)
        tk.Label(r, text=label, font=("Microsoft YaHei", 11, "bold"),
                 bg=PALETTE["bg"], fg=PALETTE["text"],
                 width=16, anchor="w").pack(side=tk.LEFT)
        if is_text:
            t = scrolledtext.ScrolledText(r, height=3, font=PALETTE["body_font"],
                                          bg=PALETTE["white"], fg=PALETTE["text"],
                                          relief="flat", bd=0, wrap="word")
            _reg_font(t, PALETTE["body_font"])
            t.insert("1.0", profile.get(key, ""))
            t.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0))
            return t
        else:
            e = tk.Entry(r, font=("Microsoft YaHei", 11), bg=PALETTE["white"],
                         fg=PALETTE["text"], relief="flat", bd=0)
            e.insert(0, profile.get(key, ""))
            e.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0))
            return e

    e_name = _row(form, "👧 姓名", "kid_name")
    e_grade = _row(form, "🎓 年级", "grade")
    e_school = _row(form, "🏫 学校", "school")
    e_district = _row(form, "📍 上海哪个区", "district")
    t_weak = _row(form, "❌ 薄弱点", "weakness", is_text=True)
    t_strength = _row(form, "✅ 优点强项", "strengths", is_text=True)
    t_gaps = _row(form, "🧩 概念理解不足", "concept_gaps", is_text=True)
    t_notes = _row(form, "📝 备注/下次计划", "notes", is_text=True)

    def _save():
        data = {
            "kid_name": e_name.get().strip(),
            "grade": e_grade.get().strip(),
            "school": e_school.get().strip(),
            "district": e_district.get().strip(),
            "weakness": t_weak.get("1.0", "end").strip(),
            "strengths": t_strength.get("1.0", "end").strip(),
            "concept_gaps": t_gaps.get("1.0", "end").strip(),
            "notes": t_notes.get("1.0", "end").strip(),
        }
        _save_profile(data)
        messagebox.showinfo("保存成功 🎉", f"{data['kid_name']} 的学习档案已保存!")

    btn_frame = tk.Frame(tab_profile, bg=PALETTE["bg"]); btn_frame.pack(pady=12)
    _mk_color_button(btn_frame, "💾 保存档案", PALETTE["mint"], _save, width=14).pack(side=tk.LEFT, padx=6)
    tip_btn = _mk_color_button(btn_frame, "❓ 为什么要填", PALETTE["sun"],
                               lambda: messagebox.showinfo("小贴士",
                                   "记录薄弱点≠给孩子贴标签!\n\n"
                                   "✅ 找到'具体的'薄弱点 (不是'数学差', 而是'除数是两位数的除法试商慢')\n"
                                   "✅ 每个薄弱点配1-2本练习册 + 每天10分钟专项练\n"
                                   "✅ 优点也一定要写! 保持优势比补短板更重要\n\n"
                                   "数据保存在 ~/.tutor_helper/, 不会丢~"), width=14)
    tip_btn.pack(side=tk.LEFT, padx=6)

    # ═══════════════════════════════════════
    # Tab 3: 🧠 解题思路
    # ═══════════════════════════════════════
    tab_solution = tk.Frame(nb, bg=PALETTE["bg"])
    nb.add(tab_solution, text="🧠 解题思路")

    tk.Label(tab_solution, text="🧠 各学科学习方法 & 解题技巧",
             font=("Comic Sans MS", 16, "bold"),
             bg=PALETTE["bg"], fg=PALETTE["lavender_dark"]).pack(pady=(14, 4))

    sol_body = tk.Frame(tab_solution, bg=PALETTE["bg"]); sol_body.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)

    # 左侧按钮栏
    btn_colors = [PALETTE["pink"], PALETTE["sky"], PALETTE["mint"],
                  PALETTE["sun"], PALETTE["lavender"], PALETTE["pink_dark"]]
    btn_list = []
    for i, key in enumerate(SOLUTION_DB.keys()):
        btn = _mk_color_button(sol_body, key, btn_colors[i % len(btn_colors)],
                               lambda k=key: _show_sol_text(txt, k), width=14)
        btn.pack(anchor="w", pady=3)
        btn_list.append(btn)

    # 右侧文本 (解题思路大面板)
    txt = scrolledtext.ScrolledText(sol_body, font=PALETTE["body_font"],
                                    bg=PALETTE["white"], fg=PALETTE["text"],
                                    relief="flat", bd=0, wrap="word",
                                    padx=14, pady=14)
    _reg_font(txt, PALETTE["body_font"])
    txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0))

    def _show_sol_text(widget, key):
        widget.delete("1.0", "end")
        widget.insert("1.0", SOLUTION_DB[key].strip())

    _show_sol_text(txt, "数学逻辑")  # 默认显示

    # ═══════════════════════════════════════
    # Tab 4: 📝 题库
    # ═══════════════════════════════════════
    tab_questions = tk.Frame(nb, bg=PALETTE["bg"])
    nb.add(tab_questions, text="📝 题库")

    q_title = tk.Label(tab_questions, text="📝 上海小学真题精选 (语数英科)",
                       font=PALETTE["title_font"],
                       bg=PALETTE["bg"], fg=PALETTE["mint_dark"])
    q_title.pack(pady=(14, 4))
    _reg_font(q_title, PALETTE["title_font"])

    q_body = tk.Frame(tab_questions, bg=PALETTE["bg"]); q_body.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)

    q_tabs = ttk.Notebook(q_body)
    q_tabs.pack(fill=tk.BOTH, expand=True)

    for subject, questions in QUESTION_BANK.items():
        sub_tab = tk.Frame(q_tabs, bg=PALETTE["bg"])
        q_tabs.add(sub_tab, text=f"   {subject}   ")
        for i, q in enumerate(questions):
            card = tk.Frame(sub_tab, bg=PALETTE["white"], bd=0,
                            highlightthickness=2, highlightbackground=PALETTE["mint"])
            card.pack(fill=tk.X, padx=6, pady=6)

            q_frame = tk.Frame(card, bg=PALETTE["white"]); q_frame.pack(fill=tk.X, padx=12, pady=(10, 4))
            q_num = tk.Label(q_frame, text=f"❓ 第 {i+1} 题",
                             font=PALETTE["body_bold"],
                             bg=PALETTE["white"], fg=PALETTE["mint_dark"])
            q_num.pack(side=tk.LEFT)
            _reg_font(q_num, PALETTE["body_bold"])
            q_lbl = tk.Label(q_frame, text=q["q"],
                             font=PALETTE["body_font"],
                             bg=PALETTE["white"], fg=PALETTE["text"],
                             wraplength=900, justify="left")
            q_lbl.pack(anchor="w", padx=4, pady=2)
            _reg_font(q_lbl, PALETTE["body_font"])

            ans_frame = tk.Frame(card, bg=PALETTE["mint"]); ans_frame.pack(fill=tk.X, padx=6, pady=(0, 8))
            ans_text = tk.Label(ans_frame, text="",
                                font=PALETTE["body_font"],
                                bg=PALETTE["mint"], fg=PALETTE["mint_dark"],
                                wraplength=940, justify="left")
            ans_text.pack(anchor="w", padx=10, pady=6)
            _reg_font(ans_text, PALETTE["body_font"])

            tip_text = tk.Label(ans_frame, text="",
                                font=PALETTE["small_font"],
                                bg=PALETTE["mint"], fg=PALETTE["pink_dark"],
                                wraplength=940, justify="left")
            tip_text.pack(anchor="w", padx=10, pady=(0, 6))
            _reg_font(tip_text, PALETTE["small_font"])

            btn_row = tk.Frame(card, bg=PALETTE["white"]); btn_row.pack(fill=tk.X, padx=12, pady=(0, 10))
            show_btn = _mk_color_button(btn_row, "👀 看答案", PALETTE["sun"],
                                        lambda a=q["a"], t=q["tip"]: (
                                            ans_text.config(text="✅ 答案:\n" + a),
                                            tip_text.config(text="❓ 小贴士: " + t)
                                        ), width=12)
            show_btn.pack(side=tk.LEFT)
            hide_btn = _mk_color_button(btn_row, "🙈 藏起来", PALETTE["white"],
                                        lambda: (ans_text.config(text=""), tip_text.config(text="")),
                                        width=12)
            hide_btn.pack(side=tk.LEFT, padx=6)

    # ═══════════════════════════════════════
    # Tab 5: 📖 语文
    # ═══════════════════════════════════════
    tab_cn = tk.Frame(nb, bg=PALETTE["bg"])
    nb.add(tab_cn, text="📖 语文")

    def _build_knowledge_tab(parent, db, title_color):
        body = tk.Frame(parent, bg=PALETTE["bg"]); body.pack(fill=tk.BOTH, expand=True, padx=10, pady=6)
        btn_frame = tk.Frame(body, bg=PALETTE["bg"]); btn_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        txt = scrolledtext.ScrolledText(body, font=PALETTE["body_font"],
                                        bg=PALETTE["white"], fg=PALETTE["text"],
                                        relief="flat", bd=0, wrap="word",
                                        padx=14, pady=14)
        _reg_font(txt, PALETTE["body_font"])
        txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        for i, key in enumerate(db.keys()):
            btn = _mk_color_button(btn_frame, key, PALETTE["white"],
                                   lambda k=key: _show_knowledge(txt, db, k), width=16)
            btn.pack(anchor="w", pady=3)

        _show_knowledge(txt, db, list(db.keys())[0])

    def _show_knowledge(widget, db, key):
        widget.delete("1.0", "end")
        widget.insert("1.0", db[key].strip())

    _build_knowledge_tab(tab_cn, CHINESE_KNOWLEDGE, PALETTE["pink_dark"])

    # ═══════════════════════════════════════
    # Tab 6: 🧮 数学
    # ═══════════════════════════════════════
    tab_math = tk.Frame(nb, bg=PALETTE["bg"])
    nb.add(tab_math, text="🧮 数学")
    _build_knowledge_tab(tab_math, MATH_KNOWLEDGE, PALETTE["mint_dark"])

    # ═══════════════════════════════════════
    # Tab 7: 🔤 英语
    # ═══════════════════════════════════════
    tab_en = tk.Frame(nb, bg=PALETTE["bg"])
    nb.add(tab_en, text="🔤 英语")
    _build_knowledge_tab(tab_en, ENGLISH_KNOWLEDGE, PALETTE["lavender_dark"])

    # 底部 Footer
    footer = tk.Frame(dlg, bg=PALETTE["white"], height=36)
    footer.pack(fill=tk.X, side=tk.BOTTOM)
    tk.Label(footer, text="💡 提醒: 屏幕时间每天控制在 30-40 分钟内 · 优先平板/电视大屏",
             font=("Microsoft YaHei", 10),
             bg=PALETTE["white"], fg=PALETTE["text_light"]).pack(pady=8)

    dlg.focus_force()
    return dlg


# ─────────────────────────────────────────────
# 🧪 独立测试
# ─────────────────────────────────────────────
if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    _show_tutor_helper(root)
    root.mainloop()
