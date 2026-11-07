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

# 📚 知识点库 + 🤖 AI评分 (新模块)
try:
    from ui.knowledge_base import (KNOWLEDGE, STAGES, GRADE_SIMPLE, SUBJECTS_BY_STAGE,
                                   get_topics as _kb_get_topics, get_topic_names,
                                   get_subjects as _kb_subjects,
                                   search_topic, stats as _kb_stats)
    HAS_KB = True
except Exception:
    HAS_KB = False

try:
    from ui.exam_ai import (call_deepseek, grade_exam_with_ai, TEACHER_STYLES,
                            grade_exam_from_images, grade_pure_from_images)
    HAS_AI = True
except Exception:
    HAS_AI = False

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

# 题库数据库 & Word 导出 (智能试卷 Tab 用)
try:
    from ui.exam_db import (
        init_db, get_questions, count_questions, get_all_grades, get_all_subjects,
        get_topics as db_get_topics, get_stats, add_question, update_question, delete_question,
        pick_random_questions, import_from_json_file, import_from_word_file,
        scan_import_folder, do_import_folder, save_exam as db_save_exam,
    )
    from ui.exam_word import save_exam_docx, open_word_for_print
    HAS_EXAM_DB = True
except Exception:
    HAS_EXAM_DB = False

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
    "title_font": ("Comic Sans MS", 30, "bold"),
    "body_font": ("Microsoft YaHei", 22),
    "body_bold": ("Microsoft YaHei", 22, "bold"),
    "small_font": ("Microsoft YaHei", 18),
    "emoji_font": ("Apple Color Emoji", 28),
}

# ─────────────────────────────────────────────
# 🔧 全局字体调节 (A-/A+) — 支持电视大屏 3x 缩放!
# ─────────────────────────────────────────────
_FONT_SCALE = 1.6   # 默认 1.6, 范围 0.8 ~ 3.0 (45寸电视默认1.6倍)
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
# -*- coding: utf-8 -*-
"""📚 完整 EXAM_BANK — 6 年级 × 4 学科 × 多知识点"""

EXAM_BANK = {
    # ═══════════════════════
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
                {"q": "长方形长6cm, 宽4cm, 周长是多少?", "type": "fill", "answer": "20", "score": 5, "topic": "周长-长方形"},
                {"q": "正方形边长5cm, 周长是多少?", "type": "fill", "answer": "20", "score": 5, "topic": "周长-正方形"},
                {"q": "长方形长8cm, 宽3cm, 面积是多少?", "type": "fill", "answer": "24", "score": 5, "topic": "面积-长方形"},
                {"q": "正方形边长7cm, 面积是多少?", "type": "fill", "answer": "49", "score": 5, "topic": "面积-正方形"},
                {"q": "周长和面积的单位一样吗? (是/否)", "type": "choice", "options": ["是", "否"], "answer": 1, "score": 5, "topic": "周长vs面积"},
            ],
            "分数初步认识": [
                {"q": "1/2 表示把一个东西平均分成几份?", "type": "fill", "answer": "2", "score": 5, "topic": "分数-意义"},
                {"q": "比较大小: 1/3 ○ 1/5 (填 > < =)", "type": "choice", "options": [">", "<", "="], "answer": 0, "score": 5, "topic": "分数-比大小"},
                {"q": "同分母分数相加: 1/5 + 2/5 = ?", "type": "fill", "answer": "3/5", "score": 5, "topic": "分数-加法"},
                {"q": "1里面有几个 1/4?", "type": "fill", "answer": "4", "score": 5, "topic": "分数-单位1"},
                {"q": "比较: 3/7 ○ 5/7", "type": "choice", "options": [">", "<", "="], "answer": 1, "score": 5, "topic": "分数-比大小"},
            ],
        },
        "语文": {
            "生字词": [
                {"q": "看拼音写词语: wén zhāng (  )", "type": "fill", "answer": "文章", "score": 5, "topic": "看拼音写字"},
                {"q": "看拼音写词语: yǎng wàng (  )", "type": "fill", "answer": "仰望", "score": 5, "topic": "看拼音写字"},
                {"q": "看拼音写词语: huāng yě (  )", "type": "fill", "answer": "荒野", "score": 5, "topic": "看拼音写字"},
                {"q": "选字填空: (历 厉)史、(在 再)见", "type": "fill", "answer": "历/再", "score": 5, "topic": "形近字"},
                {"q": "给'口'加偏旁, 写3个不同的字", "type": "fill", "answer": "吃/叫/唱/吹/叶", "score": 5, "topic": "加偏旁写字"},
            ],
            "古诗文": [
                {"q": "《山行》中'停车坐爱枫林晚'的下一句是?", "type": "fill", "answer": "霜叶红于二月花", "score": 5, "topic": "古诗-背诵"},
                {"q": "《赠刘景文》'荷尽已无擎雨盖'的下一句是?", "type": "fill", "answer": "菊残犹有傲霜枝", "score": 5, "topic": "古诗-背诵"},
                {"q": '"一年好景君须记"的下一句是?', "type": "fill", "answer": "最是橙黄橘绿时", "score": 5, "topic": "古诗-背诵"},
                {"q": "《夜书所见》作者是?", "type": "fill", "answer": "叶绍翁", "score": 5, "topic": "古诗-作者"},
                {"q": '"萧萧梧叶送寒声"中"萧萧"是什么意思?', "type": "fill", "answer": "风吹落叶声", "score": 5, "topic": "古诗-词语解释"},
            ],
            "阅读理解": [
                {"q": "《花的学校》作者是谁?", "type": "fill", "answer": "泰戈尔", "score": 5, "topic": "课文-作者"},
                {"q": "《铺满金色巴掌的水泥道》中'金色巴掌'指什么?", "type": "fill", "answer": "梧桐树叶", "score": 5, "topic": "课文-比喻"},
                {"q": "《秋天的雨》用了什么修辞手法?", "type": "fill", "answer": "拟人/比喻", "score": 5, "topic": "课文-修辞"},
                {"q": "阅读时的'预测策略'是指?", "type": "fill", "answer": "边读边猜接下来会发生什么", "score": 5, "topic": "阅读方法"},
                {"q": "写日记的格式是?", "type": "fill", "answer": "日期+星期+天气", "score": 5, "topic": "写作-日记格式"},
            ],
        },
        "英语": {
            "字母与音标": [
                {"q": "写出字母表中H后面的3个大写字母", "type": "fill", "answer": "I J K", "score": 5, "topic": "字母顺序"},
                {"q": "字母O的音标是?", "type": "fill", "answer": "/ɒ/", "score": 5, "topic": "音标"},
                {"q": "按顺序写出5个元音字母 (大写)", "type": "fill", "answer": "A E I O U", "score": 5, "topic": "元音字母"},
                {"q": "Apple 的首字母大写形式是?", "type": "fill", "answer": "A", "score": 5, "topic": "大小写"},
                {"q": "26个字母中第15个字母是?", "type": "fill", "answer": "O", "score": 5, "topic": "字母顺序"},
            ],
            "基础词汇": [
                {"q": "英译汉: pencil bag", "type": "fill", "answer": "铅笔袋", "score": 5, "topic": "文具词汇"},
                {"q": "英译汉: orange juice", "type": "fill", "answer": "橙汁", "score": 5, "topic": "食物词汇"},
                {"q": "汉译英: 红色", "type": "fill", "answer": "red", "score": 5, "topic": "颜色词汇"},
                {"q": "汉译英: 十六", "type": "fill", "answer": "sixteen", "score": 5, "topic": "数字"},
                {"q": "选出不同类的单词: cat / dog / orange / pig", "type": "fill", "answer": "orange", "score": 5, "topic": "词汇-分类"},
            ],
            "基本句型": [
                {"q": "填空: Hello! ____ name is Tom.", "type": "fill", "answer": "My", "score": 5, "topic": "自我介绍"},
                {"q": "____ you fine? — Yes, I am.", "type": "fill", "answer": "Are", "score": 5, "topic": "问候"},
                {"q": "This ____ my book. (is/are)", "type": "choice", "options": ["is", "are"], "answer": 0, "score": 5, "topic": "指示代词"},
                {"q": "Is this your pen? — No, it ____.", "type": "fill", "answer": "isn't", "score": 5, "topic": "一般疑问句"},
                {"q": "翻译: 你好吗?", "type": "fill", "answer": "How are you?", "score": 5, "topic": "中英互译"},
            ],
        },
        "科学": {
            "电路": [
                {"q": "电池正极连接小灯泡的哪个金属点?", "type": "fill", "answer": "底部金属圆点", "score": 5, "topic": "电路-连接"},
                {"q": "要让小灯泡亮, 必须形成什么回路?", "type": "fill", "answer": "闭合回路", "score": 5, "topic": "电路-原理"},
                {"q": "判断: 开关能控制电路的通断 (对/错)", "type": "choice", "options": ["对", "错"], "answer": 0, "score": 5, "topic": "电路-开关"},
                {"q": "铜和塑料哪个是导体?", "type": "fill", "answer": "铜", "score": 5, "topic": "导体-绝缘体"},
                {"q": "电路中电流的方向是?", "type": "fill", "answer": "正极→小灯泡→负极", "score": 5, "topic": "电流方向"},
            ],
            "植物与动物": [
                {"q": "植物生长需要哪些条件? (至少3个)", "type": "fill", "answer": "阳光/水/空气/温度/养分", "score": 5, "topic": "植物-生长条件"},
                {"q": "光合作用需要哪两种物质?", "type": "fill", "answer": "二氧化碳和水", "score": 5, "topic": "植物-光合作用"},
                {"q": "金鱼是脊椎动物还是无脊椎动物?", "type": "fill", "answer": "脊椎动物", "score": 5, "topic": "动物-分类"},
                {"q": "蚂蚁是脊椎动物还是无脊椎动物?", "type": "fill", "answer": "无脊椎动物", "score": 5, "topic": "动物-分类"},
                {"q": "绿色植物通过什么作用制造养料?", "type": "fill", "answer": "光合作用", "score": 5, "topic": "植物-光合作用"},
            ],
            "磁铁": [
                {"q": "磁铁有几个磁极?", "type": "fill", "answer": "2个", "score": 5, "topic": "磁铁-磁极"},
                {"q": "磁铁的两个磁极名称是?", "type": "fill", "answer": "南极(S)和北极(N)", "score": 5, "topic": "磁铁-磁极"},
                {"q": "两个相同的磁极靠近会怎样?", "type": "fill", "answer": "互相排斥", "score": 5, "topic": "磁铁-作用"},
                {"q": "指南针的原理是什么?", "type": "fill", "answer": "磁铁能指示南北方向", "score": 5, "topic": "磁铁-应用"},
                {"q": "磁铁能吸引以下哪些物质? 铁/铜/铝/镍/木头", "type": "fill", "answer": "铁/镍", "score": 5, "topic": "磁铁-性质"},
            ],
        },
    },

    # ═══════════════════════
    "三年级下": {
        "数学": {
            "除数是一位数的除法": [
                {"q": "计算: 84 ÷ 4 = ?", "type": "fill", "answer": "21", "score": 5, "topic": "除法-基础"},
                {"q": "计算: 96 ÷ 3 = ?", "type": "fill", "answer": "32", "score": 5, "topic": "除法-基础"},
                {"q": "计算: 428 ÷ 4 = ?", "type": "fill", "answer": "107", "score": 5, "topic": "除法-商中间有0"},
                {"q": "判断: 0除以任何数都得0 (对/错)", "type": "choice", "options": ["对", "错"], "answer": 1, "score": 5, "topic": "除法-0的问题"},
                {"q": "计算: 255 ÷ 5 = ?", "type": "fill", "answer": "51", "score": 5, "topic": "除法-基础"},
            ],
            "两位数乘两位数": [
                {"q": "计算: 12 × 13 = ?", "type": "fill", "answer": "156", "score": 5, "topic": "乘法-竖式"},
                {"q": "计算: 25 × 40 = ?", "type": "fill", "answer": "1000", "score": 5, "topic": "乘法-有0"},
                {"q": "计算: 36 × 24 = ?", "type": "fill", "answer": "864", "score": 5, "topic": "乘法-竖式"},
                {"q": "估算: 48 × 21 ≈ ?", "type": "fill", "answer": "1000", "score": 5, "topic": "估算乘法"},
                {"q": "计算: 15 × 15 = ? (巧算)", "type": "fill", "answer": "225", "score": 5, "topic": "乘法-巧算"},
            ],
            "面积": [
                {"q": "面积的单位有哪些? (写出3个)", "type": "fill", "answer": "cm² / dm² / m²", "score": 5, "topic": "面积-单位"},
                {"q": "1 dm² = 多少 cm²?", "type": "fill", "answer": "100", "score": 5, "topic": "面积-单位换算"},
                {"q": "长方形长10cm, 宽6cm, 面积是?", "type": "fill", "answer": "60", "score": 5, "topic": "面积-长方形"},
                {"q": "正方形边长8cm, 面积是?", "type": "fill", "answer": "64", "score": 5, "topic": "面积-正方形"},
                {"q": "面积和周长的换算关系是?", "type": "choice", "options": ["能换算", "不能换算", "没关系"], "answer": 1, "score": 5, "topic": "面积vs周长"},
            ],
            "年、月、日": [
                {"q": "一年有多少个月?", "type": "fill", "answer": "12", "score": 5, "topic": "时间-年"},
                {"q": "哪几个月有31天? (写出3个)", "type": "fill", "answer": "1/3/5/7/8/10/12", "score": 5, "topic": "时间-月"},
                {"q": "平年2月有几天? 闰年2月有几天?", "type": "fill", "answer": "28/29", "score": 5, "topic": "时间-平闰年"},
                {"q": "判断: 2024年是平年还是闰年?", "type": "choice", "options": ["平年", "闰年"], "answer": 1, "score": 5, "topic": "时间-平闰年判断"},
                {"q": "一天有多少小时?", "type": "fill", "answer": "24", "score": 5, "topic": "时间-日"},
            ],
            "解决问题": [
                {"q": "归一问题: 3本书24元, 1本多少元?", "type": "fill", "answer": "8", "score": 5, "topic": "应用题-归一"},
                {"q": "归总问题: 每盒6支铅笔, 5盒平均分给10人, 每人几支?", "type": "fill", "answer": "3", "score": 5, "topic": "应用题-归总"},
                {"q": "商店运来5箱苹果, 每箱8千克, 卖出12千克, 还剩多少?", "type": "fill", "answer": "28", "score": 5, "topic": "应用题-购物"},
                {"q": "小明有36颗糖, 分给4个好朋友, 每人几颗?", "type": "fill", "answer": "9", "score": 5, "topic": "应用题-平均分"},
                {"q": "修路队每天修80米, 5天修多少米?", "type": "fill", "answer": "400", "score": 5, "topic": "应用题-行程"},
            ],
        },
        "语文": {
            "古诗文": [
                {"q": "《绝句》'迟日江山丽'的下一句是?", "type": "fill", "answer": "春风花草香", "score": 5, "topic": "古诗-背诵"},
                {"q": "《惠崇春江晚景》作者是谁?", "type": "fill", "answer": "苏轼", "score": 5, "topic": "古诗-作者"},
                {"q": "《三衢道中》'梅子黄时日日晴'的下一句是?", "type": "fill", "answer": "小溪泛尽却山行", "score": 5, "topic": "古诗-背诵"},
                {"q": "《忆江南》作者是谁?", "type": "fill", "answer": "白居易", "score": 5, "topic": "古诗-作者"},
                {"q": '"春来江水绿如蓝"上一句是?', "type": "fill", "answer": "日出江花红胜火", "score": 5, "topic": "古诗-背诵"},
            ],
            "寓言故事": [
                {"q": "《守株待兔》告诉我们什么道理?", "type": "fill", "answer": "不要想着不劳而获", "score": 5, "topic": "寓言-道理"},
                {"q": "《陶罐和铁罐》中谁最后被保留下来?", "type": "fill", "answer": "陶罐", "score": 5, "topic": "寓言-内容"},
                {"q": "《鹿角和鹿腿》中鹿的腿有什么用?", "type": "fill", "answer": "逃跑救命", "score": 5, "topic": "寓言-内容"},
                {"q": "《池子与河流》告诉我们什么道理?", "type": "fill", "answer": "要勤奋不能懒惰", "score": 5, "topic": "寓言-道理"},
                {"q": "《守株待兔》是寓言故事吗? (是/否)", "type": "choice", "options": ["是", "否"], "answer": 0, "score": 5, "topic": "寓言-体裁"},
            ],
            "写作": [
                {"q": "写通知要包含哪些要素? (至少3个)", "type": "fill", "answer": "时间/地点/事件/通知人/日期", "score": 5, "topic": "写作-通知格式"},
                {"q": "写观察日记要记录什么?", "type": "fill", "answer": "日期/观察对象/变化/数据记录", "score": 5, "topic": "写作-观察日记"},
                {"q": "写一个身边的人要抓住什么特点?", "type": "fill", "answer": "人物外貌+性格+典型事件", "score": 5, "topic": "写作-写人"},
                {"q": "按要求写句子: 湿润的东风走过荒野 (仿写拟人句)", "type": "fill", "answer": "顽皮的雨滴在伞上跳舞", "score": 5, "topic": "写作-仿写拟人"},
                {"q": "作文修改时要检查哪些方面? (至少3个)", "type": "fill", "answer": "错别字/语句通顺/标点/内容/结构", "score": 5, "topic": "写作-修改"},
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
                {"q": "判断: There be 和 have/has 能连用 (对/错)", "type": "choice", "options": ["对", "错"], "answer": 1, "score": 5, "topic": "there be-区别"},
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

    # ═══════════════════════
    "四年级上": {
        "数学": {
            "大数的认识": [
                {"q": "从右往左数, 亿位是第几位?", "type": "fill", "answer": "第9位", "score": 5, "topic": "大数-数位"},
                {"q": "读出: 123456789 怎么读?", "type": "fill", "answer": "一亿二千三百四十五万六千七百八十九", "score": 5, "topic": "大数-读法"},
                {"q": "写出: 二亿零三百万五千", "type": "fill", "answer": "203005000", "score": 5, "topic": "大数-写法"},
                {"q": "四舍五入到万位: 995000 ≈ ?", "type": "fill", "answer": "100万", "score": 5, "topic": "大数-四舍五入"},
                {"q": "比较大小: 99999999 ○ 100000000", "type": "choice", "options": [">", "<", "="], "answer": 1, "score": 5, "topic": "大数-比较"},
            ],
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
                {"q": "试商时, 把28看作30试商, 商可能偏大还是偏小?", "type": "choice", "options": ["偏大", "偏小"], "answer": 1, "score": 5, "topic": "除法-试商"},
                {"q": "625 ÷ 25 = ? (口算)", "type": "fill", "answer": "25", "score": 5, "topic": "除法-巧算"},
                {"q": "计算: 728 ÷ 28 = ?", "type": "fill", "answer": "26", "score": 5, "topic": "除法-竖式"},
            ],
            "平行与垂直": [
                {"q": "同一平面内两条直线相交成直角, 这两条直线叫什么?", "type": "fill", "answer": "互相垂直", "score": 5, "topic": "垂直"},
                {"q": "同一平面内不相交的两条直线叫什么?", "type": "fill", "answer": "平行线", "score": 5, "topic": "平行"},
                {"q": "过直线外一点画已知直线的平行线, 能画几条?", "type": "fill", "answer": "1条", "score": 5, "topic": "平行-画法"},
                {"q": "过直线上一点画已知直线的垂线, 能画几条?", "type": "fill", "answer": "1条", "score": 5, "topic": "垂直-画法"},
                {"q": "判断: 平行线永远不相交 (对/错)", "type": "choice", "options": ["对", "错"], "answer": 0, "score": 5, "topic": "平行-性质"},
            ],
            "平行四边形和梯形": [
                {"q": "平行四边形有几组对边平行?", "type": "fill", "answer": "2组", "score": 5, "topic": "平行四边形-特征"},
                {"q": "梯形有几组对边平行?", "type": "fill", "answer": "1组", "score": 5, "topic": "梯形-特征"},
                {"q": "三角形内角和是多少度?", "type": "fill", "answer": "180°", "score": 5, "topic": "三角形-内角和"},
                {"q": "三角形按角分类可以分为哪几类?", "type": "fill", "answer": "锐角三角形/直角三角形/钝角三角形", "score": 5, "topic": "三角形-分类"},
                {"q": "等腰三角形有几条对称轴?", "type": "fill", "answer": "1条", "score": 5, "topic": "三角形-对称性"},
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
            "阅读提问策略": [
                {"q": "阅读时可以从哪些角度提问? (至少3个)", "type": "fill", "answer": "内容/写法/启示/修辞手法/人物/主题", "score": 5, "topic": "阅读-提问策略"},
                {"q": "读《盘古开天地》可以提什么问题? (写1个)", "type": "fill", "answer": "盘古为什么要开天地? 天地是怎么分开的?", "score": 5, "topic": "阅读-提问策略"},
                {"q": "从'写法角度'可以提什么问题?", "type": "fill", "answer": "作者用了什么修辞手法/为什么这样安排结构", "score": 5, "topic": "阅读-提问策略"},
                {"q": "从'启示角度'可以提什么问题?", "type": "fill", "answer": "这个故事告诉我们什么道理/对我们有什么启发", "score": 5, "topic": "阅读-提问策略"},
                {"q": "边读边提问的好处是什么?", "type": "fill", "answer": "加深理解/提高思考能力", "score": 5, "topic": "阅读-提问策略"},
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
        },
    },

    # ═══════════════════════
    "四年级下": {
        "数学": {
            "三位数乘两位数": [
                {"q": "计算: 125 × 16 = ?", "type": "fill", "answer": "2000", "score": 5, "topic": "乘法-基础"},
                {"q": "计算: 248 × 35 = ?", "type": "fill", "answer": "8680", "score": 5, "topic": "乘法-竖式"},
                {"q": "计算: 108 × 24 = ?", "type": "fill", "answer": "2592", "score": 5, "topic": "乘法-中间有0"},
                {"q": "用简便方法: 125 × 8 × 7 = ?", "type": "fill", "answer": "7000", "score": 5, "topic": "乘法-简算"},
                {"q": "估算: 498 × 21 ≈ ?", "type": "fill", "answer": "10000", "score": 5, "topic": "乘法-估算"},
            ],
            "运算定律与简便计算": [
                {"q": "用运算定律简算: 25 + 37 + 75 = ?", "type": "fill", "answer": "137", "score": 5, "topic": "加法交换律"},
                {"q": "用运算定律简算: 125 × 32 = ?", "type": "fill", "answer": "4000", "score": 5, "topic": "乘法结合律"},
                {"q": "用运算定律简算: 99 × 36 = ?", "type": "fill", "answer": "3564", "score": 5, "topic": "乘法分配律"},
                {"q": "判断: a × (b + c) = a × b + a × c (对/错)", "type": "choice", "options": ["对", "错"], "answer": 0, "score": 5, "topic": "乘法分配律"},
                {"q": "简算: 48 + 79 + 52 = ?", "type": "fill", "answer": "179", "score": 5, "topic": "加法交换律"},
            ],
            "小数的意义和性质": [
                {"q": "0.1 表示几分之一?", "type": "fill", "answer": "十分之一", "score": 5, "topic": "小数-意义"},
                {"q": "0.01 表示几分之一?", "type": "fill", "answer": "百分之一", "score": 5, "topic": "小数-意义"},
                {"q": "比较大小: 0.5 ○ 0.50", "type": "choice", "options": [">", "<", "="], "answer": 2, "score": 5, "topic": "小数-性质"},
                {"q": "2.05 米 = 多少厘米?", "type": "fill", "answer": "205", "score": 5, "topic": "小数-单位换算"},
                {"q": "化简小数: 3.200 = ?", "type": "fill", "answer": "3.2", "score": 5, "topic": "小数-化简"},
            ],
            "小数加减法": [
                {"q": "计算: 3.5 + 2.8 = ?", "type": "fill", "answer": "6.3", "score": 5, "topic": "小数加法"},
                {"q": "计算: 10 - 3.6 = ?", "type": "fill", "answer": "6.4", "score": 5, "topic": "小数减法"},
                {"q": "计算: 12.5 + 7.75 = ?", "type": "fill", "answer": "20.25", "score": 5, "topic": "小数加法"},
                {"q": "计算: 8.3 - 4.56 = ?", "type": "fill", "answer": "3.74", "score": 5, "topic": "小数减法"},
                {"q": "小数加减法要注意什么?", "type": "fill", "answer": "小数点对齐", "score": 5, "topic": "小数-计算法则"},
            ],
            "三角形": [
                {"q": "三角形内角和是多少度?", "type": "fill", "answer": "180°", "score": 5, "topic": "三角形-内角和"},
                {"q": "三角形任意两边之和与第三边的关系?", "type": "fill", "answer": "大于第三边", "score": 5, "topic": "三角形-三边关系"},
                {"q": "三角形按角分类有哪几类?", "type": "fill", "answer": "锐角/直角/钝角", "score": 5, "topic": "三角形-分类"},
                {"q": "等腰三角形有几条边相等?", "type": "fill", "answer": "2条", "score": 5, "topic": "三角形-等腰"},
                {"q": "等边三角形每个内角是多少度?", "type": "fill", "answer": "60°", "score": 5, "topic": "三角形-等边"},
            ],
        },
        "语文": {
            "文言文入门": [
                {"q": "《囊萤夜读》中'胤恭勤不倦'的'恭勤'意思是?", "type": "fill", "answer": "恭敬勤勉", "score": 5, "topic": "文言文-词语解释"},
                {"q": "《铁杵成针》的主人公是谁?", "type": "fill", "answer": "李白", "score": 5, "topic": "文言文-人物"},
                {"q": "《囊萤夜读》告诉我们什么道理?", "type": "fill", "answer": "勤奋好学才能成才", "score": 5, "topic": "文言文-道理"},
                {"q": "文言文'以夜继日'是什么意思?", "type": "fill", "answer": "用夜晚接续白天", "score": 5, "topic": "文言文-词语解释"},
                {"q": "《铁杵成针》中'欲'的意思是?", "type": "fill", "answer": "想要", "score": 5, "topic": "文言文-词语解释"},
            ],
            "习作": [
                {"q": "写一件事要按什么顺序? 六要素是?", "type": "fill", "answer": "时间/地点/人物/起因/经过/结果", "score": 5, "topic": "写作-六要素"},
                {"q": "把事情写清楚要注意什么?", "type": "fill", "answer": "有顺序/详略得当/有细节", "score": 5, "topic": "写作-叙事方法"},
                {"q": "写人要抓住什么?", "type": "fill", "answer": "外貌/性格/典型事件", "score": 5, "topic": "写作-写人方法"},
                {"q": "写作中如何把话写生动?", "type": "fill", "answer": "用形容词/比喻/拟人/细节描写", "score": 5, "topic": "写作-生动具体"},
                {"q": "文章的开头和结尾有什么作用?", "type": "fill", "answer": "开头点题吸引读者/结尾总结升华主题", "score": 5, "topic": "写作-结构"},
            ],
        },
        "英语": {
            "一般过去时": [
                {"q": "Yesterday I ____ (go) to the park.", "type": "fill", "answer": "went", "score": 5, "topic": "过去时-不规则"},
                {"q": "She ____ (have) lunch at 12:00 yesterday.", "type": "fill", "answer": "had", "score": 5, "topic": "过去时-不规则"},
                {"q": "Tom ____ (play) basketball last Sunday.", "type": "fill", "answer": "played", "score": 5, "topic": "过去时-规则"},
                {"q": "不规则动词: see → ____", "type": "fill", "answer": "saw", "score": 5, "topic": "过去时-不规则表"},
                {"q": "不规则动词: eat → ____", "type": "fill", "answer": "ate", "score": 5, "topic": "过去时-不规则表"},
            ],
            "一般将来时": [
                {"q": "Tomorrow we ____ (visit) the museum.", "type": "fill", "answer": "will visit", "score": 5, "topic": "将来时-will"},
                {"q": "He ____ (buy) a new bike next month.", "type": "fill", "answer": "will buy/is going to buy", "score": 5, "topic": "将来时"},
                {"q": "一般将来时两种结构是?", "type": "fill", "answer": "will+原形 / be going to+原形", "score": 5, "topic": "将来时-结构"},
                {"q": "Next week 用什么时态?", "type": "fill", "answer": "一般将来时", "score": 5, "topic": "将来时-时间标志"},
                {"q": "翻译: 我明天要去上海。", "type": "fill", "answer": "I will go to Shanghai tomorrow.", "score": 5, "topic": "将来时-翻译"},
            ],
        },
    },

    # ═══════════════════════
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
                {"q": "用字母表示: 路程 = 速度 × ?", "type": "fill", "answer": "时间", "score": 5, "topic": "用字母表示数"},
                {"q": "等式两边同时加/减/乘/除同一个数, 等式还成立吗?", "type": "choice", "options": ["成立", "不成立"], "answer": 0, "score": 5, "topic": "等式性质"},
            ],
            "多边形面积": [
                {"q": "平行四边形底8cm, 高5cm, 面积是?", "type": "fill", "answer": "40", "score": 5, "topic": "平行四边形面积"},
                {"q": "三角形底6cm, 高4cm, 面积是?", "type": "fill", "answer": "12", "score": 5, "topic": "三角形面积"},
                {"q": "梯形上底3cm, 下底7cm, 高5cm, 面积是?", "type": "fill", "answer": "25", "score": 5, "topic": "梯形面积"},
                {"q": "两个完全一样的三角形可以拼成什么?", "type": "fill", "answer": "平行四边形", "score": 5, "topic": "三角形-拼图"},
                {"q": "三角形面积公式为什么要÷2?", "type": "fill", "answer": "因为两个三角形拼成一个平行四边形", "score": 5, "topic": "三角形面积-推导"},
            ],
            "可能性": [
                {"q": "抛一枚硬币, 正面朝上的概率是多少?", "type": "fill", "answer": "1/2", "score": 5, "topic": "概率-基础"},
                {"q": "盒中有3红2蓝球, 摸到红球的可能性大还是蓝球大?", "type": "fill", "answer": "红球", "score": 5, "topic": "概率-比较"},
                {"q": "掷一个骰子, 掷出1的可能性是多少?", "type": "fill", "answer": "1/6", "score": 5, "topic": "概率-骰子"},
                {"q": "太阳从东边升起是确定事件还是随机事件?", "type": "fill", "answer": "确定事件", "score": 5, "topic": "概率-事件分类"},
                {"q": "明天会下雨是什么事件?", "type": "fill", "answer": "随机事件", "score": 5, "topic": "概率-事件分类"},
            ],
        },
        "英语": {
            "现在进行时": [
                {"q": "Look! The children ____ (play) football.", "type": "fill", "answer": "are playing", "score": 5, "topic": "时态-进行时"},
                {"q": "Listen! Someone ____ (knock) at the door.", "type": "fill", "answer": "is knocking", "score": 5, "topic": "时态-进行时"},
                {"q": "She ____ (read) a book now.", "type": "fill", "answer": "is reading", "score": 5, "topic": "时态-进行时"},
                {"q": "现在进行时结构: be + ____", "type": "fill", "answer": "doing (现在分词)", "score": 5, "topic": "时态-结构"},
                {"q": "run 的现在分词是?", "type": "fill", "answer": "running", "score": 5, "topic": "现在分词变化"},
            ],
            "一般过去时": [
                {"q": "Yesterday I ____ (go) to the park.", "type": "fill", "answer": "went", "score": 5, "topic": "过去时-不规则"},
                {"q": "She ____ (have) lunch at 12:00 yesterday.", "type": "fill", "answer": "had", "score": 5, "topic": "过去时-不规则"},
                {"q": "Tom ____ (play) basketball last Sunday.", "type": "fill", "answer": "played", "score": 5, "topic": "过去时-规则"},
                {"q": "不规则动词: see → ____", "type": "fill", "answer": "saw", "score": 5, "topic": "过去时-不规则表"},
                {"q": "不规则动词: eat → ____", "type": "fill", "answer": "ate", "score": 5, "topic": "过去时-不规则表"},
            ],
            "比较级": [
                {"q": "tall 的比较级是?", "type": "fill", "answer": "taller", "score": 5, "topic": "比较级-规则"},
                {"q": "good 的比较级是?", "type": "fill", "answer": "better", "score": 5, "topic": "比较级-不规则"},
                {"q": "big 的比较级是?", "type": "fill", "answer": "bigger", "score": 5, "topic": "比较级-规则"},
                {"q": "She is ____ (tall) than her sister.", "type": "fill", "answer": "taller", "score": 5, "topic": "比较级-应用"},
                {"q": "This book is ____ (good) than that one.", "type": "fill", "answer": "better", "score": 5, "topic": "比较级-应用"},
            ],
        },
    },

    # ═══════════════════════
    "五年级下": {
        "数学": {
            "因数与倍数": [
                {"q": "12 的因数有哪些?", "type": "fill", "answer": "1/2/3/4/6/12", "score": 5, "topic": "因数"},
                {"q": "2 的倍数有什么特征?", "type": "fill", "answer": "个位是0/2/4/6/8", "score": 5, "topic": "2的倍数特征"},
                {"q": "5 的倍数有什么特征?", "type": "fill", "answer": "个位是0或5", "score": 5, "topic": "5的倍数特征"},
                {"q": "3 的倍数有什么特征?", "type": "fill", "answer": "各位数字之和是3的倍数", "score": 5, "topic": "3的倍数特征"},
                {"q": "质数和合数的区别是什么?", "type": "fill", "answer": "质数只有1和它本身两个因数, 合数有更多", "score": 5, "topic": "质数-合数"},
            ],
            "分数的意义和性质": [
                {"q": "把3米长的绳子平均分成5段, 每段长多少米?", "type": "fill", "answer": "3/5米", "score": 5, "topic": "分数-意义"},
                {"q": "约分后分数的大小变吗?", "type": "fill", "answer": "不变", "score": 5, "topic": "分数-基本性质"},
                {"q": "通分的依据是什么?", "type": "fill", "answer": "分数的基本性质", "score": 5, "topic": "分数-通分"},
                {"q": "比较: 3/4 ○ 5/6 (通分后比较)", "type": "choice", "options": [">", "<", "="], "answer": 1, "score": 5, "topic": "分数-比大小"},
                {"q": "把 0.6 化成分数是?", "type": "fill", "answer": "3/5", "score": 5, "topic": "分数-小数互化"},
            ],
            "分数加减法": [
                {"q": "同分母分数相加: 2/7 + 3/7 = ?", "type": "fill", "answer": "5/7", "score": 5, "topic": "同分母分数加法"},
                {"q": "异分母分数相加: 1/2 + 1/3 = ?", "type": "fill", "answer": "5/6", "score": 5, "topic": "异分母分数加法"},
                {"q": "计算: 5/6 - 1/4 = ?", "type": "fill", "answer": "7/12", "score": 5, "topic": "异分母分数减法"},
                {"q": "1 - 3/8 = ?", "type": "fill", "answer": "5/8", "score": 5, "topic": "分数减法-1减"},
                {"q": "计算: 2/5 + 3/10 - 1/2 = ?", "type": "fill", "answer": "2/10或1/5", "score": 5, "topic": "分数加减混合"},
            ],
            "长方体和正方体": [
                {"q": "长方体有几个面? 几条棱? 几个顶点?", "type": "fill", "answer": "6面/12棱/8顶点", "score": 5, "topic": "长方体-特征"},
                {"q": "正方体棱长5cm, 表面积是多少?", "type": "fill", "answer": "150", "score": 5, "topic": "正方体-表面积"},
                {"q": "长方体长4cm, 宽3cm, 高2cm, 体积是?", "type": "fill", "answer": "24", "score": 5, "topic": "长方体-体积"},
                {"q": "1升 = 多少立方厘米?", "type": "fill", "answer": "1000", "score": 5, "topic": "体积-单位换算"},
                {"q": "正方体体积公式是?", "type": "fill", "answer": "棱长×棱长×棱长 (或 a³)", "score": 5, "topic": "正方体-体积公式"},
            ],
            "旋转与对称": [
                {"q": "等边三角形有几条对称轴?", "type": "fill", "answer": "3条", "score": 5, "topic": "对称轴"},
                {"q": "正方形有几条对称轴?", "type": "fill", "answer": "4条", "score": 5, "topic": "对称轴"},
                {"q": "图形旋转时需要确定哪三个要素?", "type": "fill", "answer": "旋转中心/旋转方向/旋转角度", "score": 5, "topic": "旋转-三要素"},
                {"q": "图形平移时什么发生了变化?", "type": "fill", "answer": "位置", "score": 5, "topic": "平移"},
                {"q": "判断: 圆有无数条对称轴 (对/错)", "type": "choice", "options": ["对", "错"], "answer": 0, "score": 5, "topic": "对称轴-圆"},
            ],
        },
        "语文": {
            "古诗文": [
                {"q": "《示儿》作者是谁?", "type": "fill", "answer": "陆游", "score": 5, "topic": "古诗-作者"},
                {"q": '"王师北定中原日"下一句是?', "type": "fill", "answer": "家祭无忘告乃翁", "score": 5, "topic": "古诗-背诵"},
                {"q": "《题临安邸》'山外青山楼外楼'的下一句是?", "type": "fill", "answer": "西湖歌舞几时休", "score": 5, "topic": "古诗-背诵"},
                {"q": "《己亥杂诗》作者是谁?", "type": "fill", "answer": "龚自珍", "score": 5, "topic": "古诗-作者"},
                {"q": '"落红不是无情物"的下一句是?', "type": "fill", "answer": "化作春泥更护花", "score": 5, "topic": "古诗-背诵"},
            ],
            "革命文化": [
                {"q": "《清贫》作者是谁?", "type": "fill", "answer": "方志敏", "score": 5, "topic": "课文-作者"},
                {"q": "《军神》中'军神'指的是谁?", "type": "fill", "answer": "刘伯承", "score": 5, "topic": "课文-人物"},
                {"q": "《青山处处埋忠骨》中毛泽东的儿子叫什么名字?", "type": "fill", "answer": "毛岸英", "score": 5, "topic": "课文-人物"},
                {"q": "《清贫》表现了方志敏什么品质?", "type": "fill", "answer": "清贫朴素/坚定信仰", "score": 5, "topic": "课文-中心思想"},
                {"q": "《军神》作者是谁?", "type": "fill", "answer": "毕必成", "score": 5, "topic": "课文-作者"},
            ],
        },
        "英语": {
            "一般过去时": [
                {"q": "Yesterday I ____ (go) to the park.", "type": "fill", "answer": "went", "score": 5, "topic": "过去时-不规则"},
                {"q": "She ____ (have) lunch at 12:00 yesterday.", "type": "fill", "answer": "had", "score": 5, "topic": "过去时-不规则"},
                {"q": "Tom ____ (play) basketball last Sunday.", "type": "fill", "answer": "played", "score": 5, "topic": "过去时-规则"},
                {"q": "不规则动词: see → ____", "type": "fill", "answer": "saw", "score": 5, "topic": "过去时-不规则表"},
                {"q": "不规则动词: take → ____", "type": "fill", "answer": "took", "score": 5, "topic": "过去时-不规则表"},
            ],
            "比较级和最高级": [
                {"q": "tall 的比较级和最高级分别是?", "type": "fill", "answer": "taller / tallest", "score": 5, "topic": "比较级-规则"},
                {"q": "good 的比较级和最高级分别是?", "type": "fill", "answer": "better / best", "score": 5, "topic": "比较级-不规则"},
                {"q": "This is the ____ (good) book I've ever read.", "type": "fill", "answer": "best", "score": 5, "topic": "最高级-应用"},
                {"q": "She runs ____ (fast) than her friend.", "type": "fill", "answer": "faster", "score": 5, "topic": "比较级-应用"},
                {"q": "big 的比较级是?", "type": "fill", "answer": "bigger", "score": 5, "topic": "比较级-规则"},
            ],
            "过去进行时": [
                {"q": "I ____ (read) when my mother came back.", "type": "fill", "answer": "was reading", "score": 5, "topic": "过去进行时"},
                {"q": "They ____ (play) football at 5pm yesterday.", "type": "fill", "answer": "were playing", "score": 5, "topic": "过去进行时"},
                {"q": "过去进行时结构: was/were + ____", "type": "fill", "answer": "doing (现在分词)", "score": 5, "topic": "过去进行时-结构"},
                {"q": "He was watching TV ____ the bell rang.", "type": "fill", "answer": "when", "score": 5, "topic": "过去进行时-连接词"},
                {"q": "判断: 过去进行时表示过去某个时刻正在进行的动作 (对/错)", "type": "choice", "options": ["对", "错"], "answer": 0, "score": 5, "topic": "过去进行时-意义"},
            ],
        },
        "科学": {
            "地球与宇宙": [
                {"q": "地球绕太阳转一圈是多长时间?", "type": "fill", "answer": "一年", "score": 5, "topic": "地球-公转"},
                {"q": "地球自转一圈是多长时间?", "type": "fill", "answer": "一天", "score": 5, "topic": "地球-自转"},
                {"q": "月球绕地球转一圈是多长时间?", "type": "fill", "answer": "一个月", "score": 5, "topic": "月球-公转"},
                {"q": "四季变化是地球什么运动造成的?", "type": "fill", "answer": "公转", "score": 5, "topic": "四季-成因"},
                {"q": "月食发生时, 日/地/月的位置关系?", "type": "fill", "answer": "地球在太阳和月球中间", "score": 5, "topic": "月食"},
            ],
            "沉与浮": [
                {"q": "物体的沉浮和什么有关? (至少2个)", "type": "fill", "answer": "重量/体积/形状/材质/液体密度", "score": 5, "topic": "沉浮-因素"},
                {"q": "为什么实心铁块在水中下沉, 轮船能浮?", "type": "fill", "answer": "排开水量不同/空心设计增大浮力", "score": 5, "topic": "沉浮-应用"},
                {"q": "改变橡皮泥形状(做成船)能让它浮起来吗?", "type": "fill", "answer": "能", "score": 5, "topic": "沉浮-实验"},
                {"q": "盐水和清水, 鸡蛋在哪个里更容易浮起来?", "type": "fill", "answer": "盐水", "score": 5, "topic": "沉浮-密度"},
                {"q": "物体受到的浮力方向是?", "type": "fill", "answer": "向上", "score": 5, "topic": "浮力-方向"},
            ],
            "简单机械": [
                {"q": "杠杆的三要素是什么?", "type": "fill", "answer": "支点/动力/阻力", "score": 5, "topic": "杠杆-三要素"},
                {"q": "省力杠杆的动力臂和阻力臂关系?", "type": "fill", "answer": "动力臂大于阻力臂", "score": 5, "topic": "杠杆-省力"},
                {"q": "旗杆顶部用的是什么滑轮?", "type": "fill", "answer": "定滑轮", "score": 5, "topic": "滑轮-应用"},
                {"q": "定滑轮能省力吗? 能改变方向吗?", "type": "fill", "answer": "不省力/能改变方向", "score": 5, "topic": "定滑轮-特点"},
                {"q": "斜面有什么作用?", "type": "fill", "answer": "省力/方便搬运重物", "score": 5, "topic": "斜面-应用"},
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

    # Notebook Tabs — 用自定义 style 名, 不污染主程序全局样式!
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except Exception:
        pass
    style.configure("Tutor.TNotebook", background=PALETTE["bg"], borderwidth=0)
    style.configure("Tutor.TNotebook.Tab",
                    padding=[24, 12],
                    font=("Comic Sans MS", 18, "bold"))
    style.map("Tutor.TNotebook.Tab",
              background=[("selected", PALETTE["pink"]), ("!selected", PALETTE["white"])],
              foreground=[("selected", PALETTE["pink_dark"]), ("!selected", PALETTE["text"])])

    nb = ttk.Notebook(dlg, style="Tutor.TNotebook")
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
    # Tab 4: 📝 题库 (可选中 → 加入"我的试卷" → 出题器用)
    # ═══════════════════════════════════════
    tab_questions = tk.Frame(nb, bg=PALETTE["bg"])
    nb.add(tab_questions, text="📝 题库")

    q_title = tk.Label(tab_questions, text="📝 上海小学真题精选 · 看到好题 ➕ 选入试卷",
                       font=PALETTE["title_font"],
                       bg=PALETTE["bg"], fg=PALETTE["mint_dark"])
    q_title.pack(pady=(14, 2))
    _reg_font(q_title, PALETTE["title_font"])

    # "我的试卷" 状态条
    my_paper_frame = tk.Frame(tab_questions, bg=PALETTE["bg"]); my_paper_frame.pack(fill=tk.X, padx=20, pady=2)
    tk.Label(my_paper_frame, text="🎯 我的试卷:",
             font=PALETTE["body_bold"],
             bg=PALETTE["bg"], fg=PALETTE["pink_dark"]).pack(side=tk.LEFT)
    my_paper_count = tk.Label(my_paper_frame, text="0 题",
                              font=PALETTE["body_bold"],
                              bg=PALETTE["bg"], fg=PALETTE["mint_dark"])
    my_paper_count.pack(side=tk.LEFT, padx=4)
    _reg_font(my_paper_count, PALETTE["body_bold"])

    MY_PAPER = []  # [{"q":..., "a":..., "tip":..., "subject":...}, ...]

    def _update_my_paper_count():
        my_paper_count.config(text=f"{len(MY_PAPER)} 题",
                              fg=PALETTE["pink_dark"] if MY_PAPER else PALETTE["text_light"])

    _mk_color_button(my_paper_frame, "🗑️ 清空", PALETTE["white"],
                     lambda: (MY_PAPER.clear(), _update_my_paper_count()),
                     width=8).pack(side=tk.LEFT, padx=4)
    _mk_color_button(my_paper_frame, "📋 去出题器组卷", PALETTE["mint"],
                     lambda: (
                         exam_tabs.select(0),
                         lambda: None  # 不自动填题，让出题器用 DB 抽
                     )[0],
                     width=16).pack(side=tk.RIGHT)
    tk.Label(my_paper_frame, text="💡 选中的题可以加到 SQLite 题库数据库里，出题器会自动抽到!",
             font=("Arial", 11),
             bg=PALETTE["bg"], fg=PALETTE["text_light"]).pack(side=tk.RIGHT, padx=8)

    q_body = tk.Frame(tab_questions, bg=PALETTE["bg"]); q_body.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)

    q_tabs = ttk.Notebook(q_body, style="Tutor.TNotebook")
    q_tabs.pack(fill=tk.BOTH, expand=True)

    for subject, questions in QUESTION_BANK.items():
        sub_tab = tk.Frame(q_tabs, bg=PALETTE["bg"])
        q_tabs.add(sub_tab, text=f"   {subject} ({len(questions)}题)  ")

        for i, q in enumerate(questions):
            card = tk.Frame(sub_tab, bg=PALETTE["white"], bd=0,
                            highlightthickness=2, highlightbackground=PALETTE["mint"])
            card.pack(fill=tk.X, padx=6, pady=6)

            q_frame = tk.Frame(card, bg=PALETTE["white"]); q_frame.pack(fill=tk.X, padx=12, pady=(10, 4))
            q_num = tk.Label(q_frame, text=f"❓ 第 {i+1} 题 [{subject}]",
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

            btn_row = tk.Frame(card, bg=PALETTE["white"]); btn_row.pack(fill=tk.X, padx=12, pady=(4, 10))

            def _add_to_my_paper(subj=subject, qq=q):
                # 加入内存列表
                item = {"q": qq["q"], "a": qq["a"], "tip": qq.get("tip", ""), "subject": subj}
                MY_PAPER.append(item)
                _update_my_paper_count()
                # 同时写入 SQLite 题库数据库
                try:
                    from ui.exam_db import add_question
                    add_question(
                        grade="四年级下",
                        subject=subj if subj in ["语文","数学","英语","科学"] else "数学",
                        topic=f"{subj}精选",
                        q_type="fill" if "=" in qq["q"] or "计算" in qq["q"] else "fill",
                        content=qq["q"],
                        answer=qq["a"],
                        score=5,
                        analysis=qq.get("tip", ""),
                    )
                except Exception:
                    pass
                messagebox.showinfo("✅ 已加入",
                                   f"这道题已加入「我的试卷」!\n\n"
                                   f"当前共 {len(MY_PAPER)} 题\n\n"
                                   f"💡 点顶部「🎯智能试卷」→ 「📋出题器」\n"
                                   f"  → 选好年级学科 → 🎲生成\n"
                                   f"  出题器会从题库数据库自动抽到这道题~")

            def _ai_explain_this_one(qq=q, subj=subject):
                if not HAS_AI:
                    # 没有 AI 就显示答案 + 提示
                    messagebox.showinfo(f"📖 {subj} 第{i+1}题",
                                       f"❓ 题目: {qq['q']}\n\n"
                                       f"✅ 答案: {qq['a']}\n\n"
                                       f"💡 提示: {qq.get('tip', '仔细读题，注意单位和符号')}\n\n"
                                       f"🤖 开启 deepseek AI 后可以获得名师讲解~")
                    return
                # 有 AI 调用
                from ui.exam_ai import call_deepseek
                result = call_deepseek(
                    system_prompt="你是小学" + subj + "名师，用小学生能懂的语言讲解。",
                    user_prompt=f"给小学生讲解这道{qq.get('type','填')}题:\n\n题目: {qq['q']}\n答案: {qq['a']}\n\n要求:\n1. 用通俗语言说题意\n2. 一步步怎么做\n3. 容易错在哪里\n4. 一个类似的小练习题",
                    temperature=0.6, max_tokens=800
                )
                if result:
                    messagebox.showinfo(f"👨‍🏫 AI讲{q_num.cget('text')}", result)
                else:
                    # AI 失败降级
                    messagebox.showinfo(f"📖 第{i+1}题",
                                       f"❓ {qq['q']}\n\n✅ {qq['a']}\n\n💡 {qq.get('tip','仔细读题~')}")

            _mk_color_button(btn_row, "➕ 选入试卷", PALETTE["mint"],
                            _add_to_my_paper, width=12).pack(side=tk.LEFT, padx=2)
            _mk_color_button(btn_row, "👀 看答案", PALETTE["sun"],
                            lambda a=q["a"], t=q.get("tip",""):
                                messagebox.showinfo("✅ 答案",
                                                  f"答案: {a}\n\n💡 提示: {t}"),
                            width=10).pack(side=tk.LEFT, padx=2)
            _mk_color_button(btn_row, "🤖 AI讲解", PALETTE["pink"],
                            _ai_explain_this_one, width=12).pack(side=tk.LEFT, padx=2)

    # ═══════════════════════════════════════
    # Tab 5: 📚 全学科知识点库 (20年级/278主题/913子点)
    # ═══════════════════════════════════════
    tab_knowledge = tk.Frame(nb, bg=PALETTE["bg"])
    nb.add(tab_knowledge, text="📚 知识点")

    _kb_title = tk.Label(tab_knowledge, text="📚 12年级全学科知识点库",
                         font=PALETTE["title_font"],
                         bg=PALETTE["bg"], fg=PALETTE["lavender_dark"])
    _kb_title.pack(pady=(14, 2))
    _kb_hint = tk.Label(tab_knowledge,
                        text="选学段 → 年级 → 学科 → 点击知识点查看详细内容  🔗 联动出题器",
                        font=PALETTE["body_font"],
                        bg=PALETTE["bg"], fg=PALETTE["text_light"])
    _kb_hint.pack()
    _reg_font(_kb_hint, PALETTE["body_font"])

    if HAS_KB:
        _kb_stats_data = _kb_stats()
        _kb_stat_label = tk.Label(tab_knowledge,
                                  text=f"📊 20年级 · {_kb_stats_data['total_topics']}主题 · {_kb_stats_data['total_children']}子知识点",
                                  font=PALETTE["body_bold"],
                                  bg=PALETTE["bg"], fg=PALETTE["pink_dark"])
        _kb_stat_label.pack(pady=(2, 6))
        _reg_font(_kb_stat_label, PALETTE["body_bold"])

    # 三列布局: 学段 | 年级 | 学科 + 搜索 + 内容详情
    _kb_main = tk.Frame(tab_knowledge, bg=PALETTE["bg"]); _kb_main.pack(fill=tk.BOTH, expand=True, padx=12, pady=6)

    # 左列: 学段 + 年级 + 学科 选择
    _kb_left = tk.Frame(_kb_main, bg=PALETTE["bg"], width=200); _kb_left.pack(side=tk.LEFT, fill=tk.Y)
    _kb_left.pack_propagate(False)

    # 搜索框
    tk.Label(_kb_left, text="🔍 搜索知识点:", font=PALETTE["body_bold"],
             bg=PALETTE["bg"], fg=PALETTE["text"]).pack(anchor="w", pady=(0, 2))
    _kb_search_var = tk.StringVar()
    _kb_search_entry = tk.Entry(_kb_left, textvariable=_kb_search_var,
                                font=PALETTE["body_font"], width=22)
    _kb_search_entry.pack(fill=tk.X, pady=(0, 10))

    # 学段选择
    tk.Label(_kb_left, text="🎓 学段:", font=PALETTE["body_bold"],
             bg=PALETTE["bg"], fg=PALETTE["text"]).pack(anchor="w")
    _kb_stage_var = tk.StringVar(value="小学")
    _kb_stage_cb = ttk.Combobox(_kb_left, textvariable=_kb_stage_var, state="readonly",
                                values=["小学", "初中", "高中"], width=18,
                                font=PALETTE["body_font"])
    _kb_stage_cb.pack(fill=tk.X, pady=2)

    # 年级选择
    tk.Label(_kb_left, text="📅 年级:", font=PALETTE["body_bold"],
             bg=PALETTE["bg"], fg=PALETTE["text"]).pack(anchor="w", pady=(8, 0))
    _kb_grade_var = tk.StringVar()
    _kb_grade_cb = ttk.Combobox(_kb_left, textvariable=_kb_grade_var, state="readonly",
                                width=18, font=PALETTE["body_font"])
    _kb_grade_cb.pack(fill=tk.X, pady=2)

    # 学科选择
    tk.Label(_kb_left, text="📚 学科:", font=PALETTE["body_bold"],
             bg=PALETTE["bg"], fg=PALETTE["text"]).pack(anchor="w", pady=(8, 0))
    _kb_subj_var = tk.StringVar()
    _kb_subj_cb = ttk.Combobox(_kb_left, textvariable=_kb_subj_var, state="readonly",
                               width=18, font=PALETTE["body_font"])
    _kb_subj_cb.pack(fill=tk.X, pady=2)

    # 联动更新
    def _kb_update_grades(*_):
        stage = _kb_stage_var.get()
        grades = STAGES.get(stage, [])
        _kb_grade_cb["values"] = grades
        if grades:
            _kb_grade_var.set(grades[0])
            _kb_update_subjects()

    def _kb_update_subjects(*_):
        grade = _kb_grade_var.get()
        subjects = _kb_subjects(grade) if HAS_KB else ["语文", "数学", "英语"]
        _kb_subj_cb["values"] = subjects
        if subjects:
            _kb_subj_var.set(subjects[0])
            _kb_refresh_tree()

    _kb_stage_cb.bind("<<ComboboxSelected>>", _kb_update_grades)
    _kb_grade_cb.bind("<<ComboboxSelected>>", _kb_update_subjects)
    _kb_subj_cb.bind("<<ComboboxSelected>>", lambda _e: _kb_refresh_tree())
    _kb_search_entry.bind("<KeyRelease>", lambda _e: _kb_refresh_tree())

    # 中列: Treeview 树形知识点
    _kb_mid = tk.Frame(_kb_main, bg=PALETTE["bg"]); _kb_mid.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=8)

    _kb_tree = ttk.Treeview(_kb_mid, columns=("count",), show="tree headings", height=20)
    _kb_tree.heading("#0", text="📚 知识点主题 (点击展开)")
    _kb_tree.heading("count", text="子点")
    _kb_tree.column("#0", width=400)
    _kb_tree.column("count", width=60, anchor="center")
    _kb_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    _kb_tree_sb = ttk.Scrollbar(_kb_mid, orient="vertical", command=_kb_tree.yview)
    _kb_tree_sb.pack(side=tk.RIGHT, fill=tk.Y)
    _kb_tree.configure(yscrollcommand=_kb_tree_sb.set)

    # 右列: 详情面板
    _kb_right = tk.Frame(_kb_main, bg=PALETTE["bg"], width=340); _kb_right.pack(side=tk.RIGHT, fill=tk.Y, padx=(4, 0))
    _kb_right.pack_propagate(False)
    tk.Label(_kb_right, text="📖 知识点详情", font=PALETTE["title_font"],
             bg=PALETTE["bg"], fg=PALETTE["lavender_dark"]).pack(anchor="w", pady=(0, 4))

    _kb_detail = scrolledtext.ScrolledText(_kb_right, height=18, wrap=tk.WORD,
                                           font=PALETTE["body_font"],
                                           bg=PALETTE["white"], fg=PALETTE["text"],
                                           relief=tk.FLAT, padx=8, pady=6)
    _kb_detail.pack(fill=tk.BOTH, expand=True)
    _reg_font(_kb_detail, PALETTE["body_font"])

    # 操作按钮
    _kb_btn_row = tk.Frame(_kb_right, bg=PALETTE["bg"]); _kb_btn_row.pack(fill=tk.X, pady=6)

    def _kb_make_exam():
        sel = _kb_tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请先选择一个知识点主题!\n然后点 📋出题器 Tab → 选好年级学科 → 🎲 生成试卷")
            return
        topic_name = _kb_tree.item(sel[0], "text")
        # 切到出题器 Tab
        exam_tabs.select(0)
        gen_topic_var.set(topic_name)
        # 如果学科匹配则保持，不匹配时提示
        messagebox.showinfo("跳转", f"已把知识点 '{topic_name}' 填入出题器!\n点 🎲 生成试卷 即可组卷~")

    _mk_color_button(_kb_btn_row, "🎲 用此知识点出题", PALETTE["pink"], _kb_make_exam, width=18).pack(fill=tk.X, pady=2)

    def _kb_ai_explain():
        if not HAS_AI:
            messagebox.showwarning("AI 不可用", "未配置 deepseek API 或网络不可用。\n请在主程序 config/ai_config.json 中设置。")
            return
        sel = _kb_tree.selection()
        if not sel:
            return
        topic_name = _kb_tree.item(sel[0], "text")
        grade = _kb_grade_var.get()
        subject = _kb_subj_var.get()
        _kb_detail.delete("1.0", tk.END)
        _kb_detail.insert(tk.END, f"⏳ AI 名师正在讲解「{topic_name}」...\n(首次调用较慢，请稍候)\n")
        _kb_detail.update()

        def _do_ai():
            from ui.exam_ai import generate_knowledge_explanation
            result = generate_knowledge_explanation(topic_name, grade, subject)
            _kb_detail.delete("1.0", tk.END)
            _kb_detail.insert(tk.END, f"👨‍🏫 AI 名师讲解 — {topic_name}\n{'='*40}\n\n{result}")

        import threading
        threading.Thread(target=_do_ai, daemon=True).start()

    _ai_btn = _mk_color_button(_kb_btn_row, "🤖 AI深度讲解", PALETTE["sky"], _kb_ai_explain, width=18)
    _ai_btn.pack(fill=tk.X, pady=2)
    if not HAS_AI:
        _ai_btn.config(state=tk.DISABLED)

    def _kb_show_detail(_e=None):
        sel = _kb_tree.selection()
        if not sel:
            return
        item_id = sel[0]
        topic_name = _kb_tree.item(item_id, "text")
        parent = _kb_tree.parent(item_id)
        # 如果是子节点, 也显示父主题完整信息
        if parent:
            parent_name = _kb_tree.item(parent, "text")
            grade = _kb_grade_var.get()
            subject = _kb_subj_var.get()
            children = _kb_tree.get_children(parent)
            _kb_detail.delete("1.0", tk.END)
            _kb_detail.insert(tk.END,
                             f"📖 {grade} · {subject}\n"
                             f"🎯 {parent_name}\n"
                             f"📍 当前: {topic_name}\n\n"
                             f"📋 包含 {len(children)} 个子知识点:\n")
            for c in children:
                mark = "  ✅" if _kb_tree.item(c, "text") == topic_name else "  •"
                _kb_detail.insert(tk.END, f"{mark} {_kb_tree.item(c, 'text')}\n")
            _kb_detail.insert(tk.END,
                             f"\n💡 可以点 🎲 出题器 用此主题组卷\n"
                             f"   或 🤖 AI深度讲解 让名师详细讲一遍")
        else:
            # 父节点: 完整主题详情
            grade = _kb_grade_var.get()
            subject = _kb_subj_var.get()
            _kb_detail.delete("1.0", tk.END)
            _kb_detail.insert(tk.END, f"📖 {grade} · {subject}\n🎯 {topic_name}\n\n")
            children = _kb_tree.get_children(item_id)
            if children:
                _kb_detail.insert(tk.END, f"📋 包含 {len(children)} 个子知识点:\n")
                for c in children:
                    _kb_detail.insert(tk.END, f"  • {_kb_tree.item(c, 'text')}\n")
                _kb_detail.insert(tk.END, f"\n💡 可以点 🎲 出题器按钮用此主题组卷\n   或 🤖 AI深度讲解 让名师详细讲一遍")

    _kb_tree.bind("<<TreeviewSelect>>", _kb_show_detail)

    def _kb_refresh_tree():
        for iid in _kb_tree.get_children():
            _kb_tree.delete(iid)
        if not HAS_KB:
            _kb_tree.insert("", tk.END, text="(知识点库未加载)", values=("0",))
            return
        grade = _kb_grade_var.get()
        subject = _kb_subj_var.get()
        kw = _kb_search_var.get().strip()
        topics_data = _kb_get_topics(grade, subject)
        for t in topics_data:
            tname = t["name"]
            if kw and kw.lower() not in tname.lower() and \
               not any(kw.lower() in c.lower() for c in t.get("children", [])):
                continue
            parent = _kb_tree.insert("", tk.END, text=tname, values=(len(t["children"]),), open=True)
            for child in t.get("children", []):
                if kw and kw.lower() not in child.lower():
                    continue
                _kb_tree.insert(parent, tk.END, text=child, values=(""))

    # 初始化
    _kb_update_grades()

    # ═══════════════════════════════════════
    # Tab 6: 📖 语文 / Tab 7: 🧮 数学 / Tab 9: 🔤 英语
    # Tab 10: 🎯 智能试卷
    # ═══════════════════════════════════════
    tab_exam = tk.Frame(nb, bg=PALETTE["bg"])
    nb.add(tab_exam, text="🎯 智能试卷")

    # ── 进度持久化 ──
    PROGRESS_DIR = os.path.expanduser("~/.tutor_helper")
    PROGRESS_FILE = os.path.join(PROGRESS_DIR, "exam_progress.json")

    def _load_progress():
        if os.path.exists(PROGRESS_FILE):
            try:
                with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"exams": [], "topic_scores": {}}

    def _save_progress(data):
        os.makedirs(PROGRESS_DIR, exist_ok=True)
        with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ── 子 Tab: 出题器 / 在线答题 / 拍照批改 / 薄弱点分析 ──
    exam_tabs = ttk.Notebook(tab_exam, style="Tutor.TNotebook")
    exam_tabs.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

    # ═══════════════════════════════════════
    # 子 Tab 1: 📋 出题器
    # ═══════════════════════════════════════
    tab_gen = tk.Frame(exam_tabs, bg=PALETTE["bg"])
    exam_tabs.add(tab_gen, text="📋 出题器")

    tk.Label(tab_gen, text="📋 智能试卷生成器",
             font=PALETTE["title_font"],
             bg=PALETTE["bg"], fg=PALETTE["lavender_dark"]).pack(pady=(14, 4))
    gen_hint = tk.Label(tab_gen,
                        text="选年级→选学科→选知识点→出题数→时间  🎲 随机抽题生成试卷!",
                        font=PALETTE["body_font"],
                        bg=PALETTE["bg"], fg=PALETTE["text_light"])
    gen_hint.pack()
    _reg_font(gen_hint, PALETTE["body_font"])

    # 表单区
    form_frame = tk.Frame(tab_gen, bg=PALETTE["bg"])
    form_frame.pack(fill=tk.X, padx=30, pady=10)

    # 年级选择 — 用 GRADE_SIMPLE (20个年级全齐)
    row1 = tk.Frame(form_frame, bg=PALETTE["bg"]); row1.pack(fill=tk.X, pady=6)
    tk.Label(row1, text="🎓 年级:", font=PALETTE["body_bold"],
             bg=PALETTE["bg"], fg=PALETTE["text"], width=14, anchor="w").pack(side=tk.LEFT)
    grade_var = tk.StringVar(value="四年级下")  # 默认四年级下
    grade_cb = ttk.Combobox(row1, textvariable=grade_var, state="readonly",
                            values=GRADE_SIMPLE, width=14,
                            font=PALETTE["body_font"])
    grade_cb.pack(side=tk.LEFT, padx=6)

    # 学科选择 — 从 knowledge_base 动态获取
    tk.Label(row1, text="  📚 学科:", font=PALETTE["body_bold"],
             bg=PALETTE["bg"], fg=PALETTE["text"], anchor="w").pack(side=tk.LEFT, padx=(20, 0))
    subject_var = tk.StringVar()
    subject_cb = ttk.Combobox(row1, textvariable=subject_var, state="readonly",
                              width=10, font=PALETTE["body_font"])
    subject_cb.pack(side=tk.LEFT, padx=6)

    # 知识点选择 — 从 knowledge_base 动态获取
    row2 = tk.Frame(form_frame, bg=PALETTE["bg"]); row2.pack(fill=tk.X, pady=6)
    tk.Label(row2, text="🧩 知识点:", font=PALETTE["body_bold"],
             bg=PALETTE["bg"], fg=PALETTE["text"], width=14, anchor="w").pack(side=tk.LEFT)
    topic_var = tk.StringVar(value="全部")
    topic_cb = ttk.Combobox(row2, textvariable=topic_var, state="readonly",
                            values=["全部"], width=22, font=PALETTE["body_font"])
    topic_cb.pack(side=tk.LEFT, padx=6)

    # 题目数 (扩大到 50 题)
    tk.Label(row2, text="  🔢 题目数:", font=PALETTE["body_bold"],
             bg=PALETTE["bg"], fg=PALETTE["text"], anchor="w").pack(side=tk.LEFT, padx=(20, 0))
    num_var = tk.StringVar(value="10")
    num_cb = ttk.Combobox(row2, textvariable=num_var, state="readonly",
                          values=["5", "8", "10", "12", "15", "20", "25", "30", "40", "50"],
                          width=7, font=PALETTE["body_font"])
    num_cb.pack(side=tk.LEFT, padx=6)

    # ── 难度等级 (新增 row) ──
    row2b = tk.Frame(form_frame, bg=PALETTE["bg"]); row2b.pack(fill=tk.X, pady=6)
    tk.Label(row2b, text="🎯 难度等级:", font=PALETTE["body_bold"],
             bg=PALETTE["bg"], fg=PALETTE["pink_dark"],
             width=14, anchor="w").pack(side=tk.LEFT)
    diff_var = tk.StringVar(value="mixed")
    diff_cb = ttk.Combobox(row2b, textvariable=diff_var, state="readonly",
                           values=[
                               "mixed    🎲 混合随机",
                               "easy     😊 轻松入门",
                               "easy_mix 😃 简单为主",
                               "medium   🤔 中等难度",
                               "hard_mix 😤 中等偏难",
                               "hard     🔥 挑战难题",
                               "expert   💀 超级困难",
                           ],
                           width=18, font=PALETTE["body_font"])
    diff_cb.pack(side=tk.LEFT, padx=6)
    diff_map_ui = {
        "mixed    🎲 混合随机": "mixed",
        "easy     😊 轻松入门": "easy",
        "easy_mix 😃 简单为主": "easy_mix",
        "medium   🤔 中等难度": "medium",
        "hard_mix 😤 中等偏难": "hard_mix",
        "hard     🔥 挑战难题": "hard",
        "expert   💀 超级困难": "expert",
    }

    # 答题时间
    row3 = tk.Frame(form_frame, bg=PALETTE["bg"]); row3.pack(fill=tk.X, pady=6)
    tk.Label(row3, text="⏰ 答题时间:", font=PALETTE["body_bold"],
             bg=PALETTE["bg"], fg=PALETTE["text"], width=14, anchor="w").pack(side=tk.LEFT)
    time_var = tk.StringVar(value="30")
    time_cb = ttk.Combobox(row3, textvariable=time_var, state="readonly",
                           values=["10", "15", "20", "25", "30", "40", "50", "60", "90"], width=7,
                           font=PALETTE["body_font"])
    time_cb.pack(side=tk.LEFT, padx=6)
    tk.Label(row3, text="分钟", font=PALETTE["body_font"],
             bg=PALETTE["bg"], fg=PALETTE["text"]).pack(side=tk.LEFT)

    def _on_grade_change(*_):
        """年级变 → 学科变 → 知识点变 (全联动)"""
        g = grade_var.get()
        if HAS_KB:
            subjects = _kb_subjects(g)
        else:
            subjects = list(EXAM_BANK.get(g, {}).keys())
        if not subjects:
            subjects = ["语文", "数学", "英语"]
        subject_cb["values"] = subjects
        subject_var.set(subjects[0])
        _on_subject_change()

    def _on_subject_change(*_):
        """学科变 → 知识点变"""
        g, s = grade_var.get(), subject_var.get()
        if HAS_KB:
            topics = get_topic_names(g, s)
        else:
            topics = list(EXAM_BANK.get(g, {}).get(s, {}).keys())
        topic_cb["values"] = ["全部"] + topics
        topic_var.set("全部")

    grade_cb.bind("<<ComboboxSelected>>", _on_grade_change)
    subject_cb.bind("<<ComboboxSelected>>", _on_subject_change)
    _on_grade_change()  # 初始化联动一遍

    # 试卷预览区
    preview_frame = tk.LabelFrame(tab_gen, text="📄 试卷预览",
                                  font=PALETTE["body_bold"],
                                  bg=PALETTE["bg"], fg=PALETTE["lavender_dark"],
                                  padx=8, pady=6)
    preview_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

    preview_txt = scrolledtext.ScrolledText(preview_frame, font=PALETTE["body_font"],
                                            bg=PALETTE["white"], fg=PALETTE["text"],
                                            relief="flat", bd=0, wrap="word",
                                            padx=14, pady=14, height=14)
    _reg_font(preview_txt, PALETTE["body_font"])
    preview_txt.pack(fill=tk.BOTH, expand=True)

    generated_exam = {"questions": [], "meta": {}}  # 存储当前生成的试卷

    def _generate_exam():
        g, s, t = grade_var.get(), subject_var.get(), topic_var.get()
        num = int(num_var.get())
        topics = [t] if t != "全部" else None
        difficulty = diff_map_ui.get(diff_var.get(), "mixed")

        picked = []
        if HAS_EXAM_DB:
            picked = pick_random_questions(g, s, topics or [], num, difficulty=difficulty)
        if not picked:
            # 降级用内置 EXAM_BANK
            if g in EXAM_BANK and s in EXAM_BANK[g]:
                all_qs = []
                top_keys = [t] if t != "全部" else list(EXAM_BANK[g][s].keys())
                for tp in top_keys:
                    all_qs.extend(EXAM_BANK[g][s].get(tp, []))
                # 按难度过滤内置题库的题
                if all_qs and difficulty != "mixed":
                    from ui.exam_db import _diff_range
                    lo, hi = _diff_range(difficulty)
                    filtered = [q for q in all_qs
                                if lo <= q.get("difficulty", 3) <= hi]
                    if filtered:
                        all_qs = filtered
                if all_qs:
                    pick_n = min(num, len(all_qs))
                    picked = random.sample(all_qs, pick_n)
                    for i, q in enumerate(picked):
                        if "id" not in q:
                            q["id"] = -(i+1)
            else:
                messagebox.showwarning("提示", f"DB和内置都没找到 {g} {s} 的题目")
                return
        if not picked:
            messagebox.showwarning("提示",
                f"按「{diff_var.get()}」难度抽不到足够题目\n"
                f"试试选「混合随机」或导入更多题目!")
            return
        # 预览文本
        time_limit = int(time_var.get())
        lines = [
            f"📝 {g} {s} 练习卷",
            f"🎯 难度: {diff_var.get().split()[0]}   "
            f"⏰ 时间: {time_limit} 分钟   "
            f"🔢 题数: {len(picked)}   "
            f"💯 满分: {sum(q.get('score',5) for q in picked)}",
            f"📅 日期: {datetime.now().strftime('%Y-%m-%d')}",
            "─" * 50,
        ]
        for i, q in enumerate(picked, 1):
            lines.append(f"\n【第{i}题 · {q.get('score',5)}分 · {q.get('topic','')}】")
            lines.append(q.get("content", q.get("q", "")))
            if q.get("q_type", q.get("type")) == "choice" and q.get("options"):
                opts = q["options"]
                if isinstance(opts, list):
                    for j, opt in enumerate(opts):
                        lines.append(f"  {chr(65+j)}. {opt}")
            lines.append("")
        # 答案区
        lines.append("─" * 50)
        lines.append("📎 参考答案 (家长用)")
        for i, q in enumerate(picked, 1):
            ans = q.get("answer", "")
            qt = q.get("q_type", q.get("type", "fill"))
            if qt == "choice" and q.get("options") and isinstance(q["options"], list):
                try:
                    opt = q["options"][q["answer"]]
                    ans = f"{chr(65+q['answer'])}. {opt}"
                except (IndexError, TypeError):
                    pass
            lines.append(f"  {i}. {ans}")
            if q.get("analysis") or q.get("tip"):
                lines.append(f"     💡 {q.get('analysis') or q.get('tip')}")
        preview_txt.delete("1.0", "end")
        preview_txt.insert("1.0", "\n".join(lines))
        generated_exam["questions"] = picked
        generated_exam["meta"] = {
            "grade": g, "subject": s, "topic": t,
            "time_limit": time_limit, "num": len(picked),
            "total_score": sum(q.get("score",5) for q in picked),
            "created_at": datetime.now().isoformat(),
        }
        # 保存试卷 JSON
        os.makedirs(PROGRESS_DIR, exist_ok=True)
        exam_file = os.path.join(PROGRESS_DIR, f"exam_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(exam_file, "w", encoding="utf-8") as f:
            json.dump({"questions": picked, "meta": generated_exam["meta"]},
                      f, ensure_ascii=False, indent=2)
        # 保存到 DB
        if HAS_EXAM_DB and picked:
            try:
                db_save_exam(f"{g}_{s}_{datetime.now().strftime('%H%M')}",
                             g, s, [t], time_limit, picked)
            except Exception:
                pass

    def _export_word():
        """导出 Word 格式试卷 (学生版+答案页), 直接唤起 Word 打印"""
        if not generated_exam["questions"]:
            messagebox.showwarning("提示", "请先生成试卷哦~")
            return
        if not HAS_EXAM_DB:
            messagebox.showwarning("提示", "Word导出需要 exam_db 模块可用")
            return
        try:
            out_path = save_exam_docx(generated_exam["questions"],
                                      generated_exam["meta"])
            messagebox.showinfo("✅ Word已生成",
                                f"📄 {os.path.basename(out_path)}\n"
                                f"📍 路径: {out_path}\n"
                                f"\n即将打开 Word / TextEdit, Cmd+P 直接打印!")
            open_word_for_print(out_path)
        except Exception as e:
            messagebox.showerror("导出失败", str(e))

    def _print_exam():
        if not generated_exam["questions"]:
            messagebox.showwarning("提示", "请先生成试卷哦~")
            return
        content = preview_txt.get("1.0", "end")
        try:
            tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
            tmp.write(content)
            tmp.close()
            os.system(f'open -a "TextEdit" {tmp.name}')
        except Exception as e:
            messagebox.showerror("打印失败", str(e))

    btn_frame_gen = tk.Frame(tab_gen, bg=PALETTE["bg"]); btn_frame_gen.pack(pady=8)
    _mk_color_button(btn_frame_gen, "🎲 随机出题", PALETTE["mint"], _generate_exam, width=16).pack(side=tk.LEFT, padx=6)
    _mk_color_button(btn_frame_gen, "📄 导出Word", PALETTE["lavender"], _export_word, width=16).pack(side=tk.LEFT, padx=6)
    _mk_color_button(btn_frame_gen, "🖨️ 打开打印", PALETTE["sky"], _print_exam, width=16).pack(side=tk.LEFT, padx=6)

    # ═══════════════════════════════════════
    # 子 Tab 1.5: 📜 历史试卷存档
    # ═══════════════════════════════════════
    tab_history = tk.Frame(exam_tabs, bg=PALETTE["bg"])
    exam_tabs.add(tab_history, text="📜 历史试卷")

    tk.Label(tab_history, text="📜 历史试卷存档 · 批卷时直接调用答案",
             font=PALETTE["title_font"],
             bg=PALETTE["bg"], fg=PALETTE["sky_dark"]).pack(pady=(14, 2))

    # 工具条
    hist_toolbar = tk.Frame(tab_history, bg=PALETTE["bg"]); hist_toolbar.pack(fill=tk.X, padx=10, pady=4)

    hist_filter_var = tk.StringVar(value="全部")
    tk.Label(hist_toolbar, text="年级:", font=PALETTE["body_font"],
             bg=PALETTE["bg"]).pack(side=tk.LEFT)
    hist_filter_cb = ttk.Combobox(hist_toolbar, textvariable=hist_filter_var,
                                  state="readonly", width=12,
                                  values=["全部"] + GRADE_SIMPLE[:8],
                                  font=PALETTE["body_font"])
    hist_filter_cb.pack(side=tk.LEFT, padx=4)

    hist_filter_subj = tk.StringVar(value="全部")
    tk.Label(hist_toolbar, text="学科:", font=PALETTE["body_font"],
             bg=PALETTE["bg"]).pack(side=tk.LEFT, padx=(10, 0))
    hist_subj_cb = ttk.Combobox(hist_toolbar, textvariable=hist_filter_subj,
                                state="readonly", width=10,
                                values=["全部", "语文", "数学", "英语", "科学"],
                                font=PALETTE["body_font"])
    hist_subj_cb.pack(side=tk.LEFT, padx=4)

    hist_count_lbl = tk.Label(hist_toolbar, text="",
                              font=PALETTE["body_bold"],
                              bg=PALETTE["bg"], fg=PALETTE["pink_dark"])
    hist_count_lbl.pack(side=tk.RIGHT)

    # 历史试卷列表 (Treeview)
    hist_cols = ("name", "grade", "subject", "num", "total", "time", "created")
    hist_tree = ttk.Treeview(tab_history, columns=hist_cols, show="headings", height=16)
    hist_tree.heading("name", text="📄 试卷名称")
    hist_tree.heading("grade", text="🎓 年级")
    hist_tree.heading("subject", text="📚 学科")
    hist_tree.heading("num", text="📝 题数")
    hist_tree.heading("total", text="⭐ 满分")
    hist_tree.heading("time", text="⏱️ 时长")
    hist_tree.heading("created", text="🕐 生成时间")
    hist_tree.column("name", width=180)
    hist_tree.column("grade", width=80)
    hist_tree.column("subject", width=60)
    hist_tree.column("num", width=50, anchor="center")
    hist_tree.column("total", width=60, anchor="center")
    hist_tree.column("time", width=60, anchor="center")
    hist_tree.column("created", width=150)
    hist_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=6)

    hist_files = []  # [(display_name, filepath), ...]

    def _refresh_history():
        nonlocal hist_files
        # 扫描 JSON 存档目录
        if not os.path.exists(PROGRESS_DIR):
            os.makedirs(PROGRESS_DIR, exist_ok=True)
        hist_files = []
        for f in sorted(os.listdir(PROGRESS_DIR), reverse=True):
            if f.startswith("exam_") and f.endswith(".json"):
                fp = os.path.join(PROGRESS_DIR, f)
                try:
                    with open(fp, encoding="utf-8") as fh:
                        data = json.load(fh)
                    meta = data.get("meta", {})
                    questions = data.get("questions", [])
                    display_name = f"{meta.get('grade','?')}_{meta.get('subject','?')}"
                    if meta.get("topic"):
                        display_name += f"_{meta['topic'][:8]}"
                    hist_files.append((display_name, fp))
                except Exception:
                    pass

        # 清空 + 填充
        for iid in hist_tree.get_children():
            hist_tree.delete(iid)

        grade_f = hist_filter_var.get()
        subj_f = hist_filter_subj.get()
        shown = 0
        for display_name, fp in hist_files:
            try:
                with open(fp, encoding="utf-8") as fh:
                    data = json.load(fh)
                meta = data.get("meta", {})
                questions = data.get("questions", [])
                g = meta.get("grade", "")
                s = meta.get("subject", "")
                if grade_f != "全部" and g != grade_f:
                    continue
                if subj_f != "全部" and s != subj_f:
                    continue
                created = meta.get("created_at", "")
                try:
                    created_dt = datetime.fromisoformat(created)
                    created_str = created_dt.strftime("%Y-%m-%d %H:%M")
                except Exception:
                    created_str = created[:16]
                hist_tree.insert("", tk.END, iid=str(shown),
                                 values=(
                                     display_name,
                                     g, s,
                                     len(questions),
                                     meta.get("total_score", 0),
                                     f"{meta.get('time_limit', 30)}分",
                                     created_str,
                                 ))
                hist_tree.item(str(shown), tags=(fp,))
                shown += 1
            except Exception:
                pass

        hist_count_lbl.config(text=f"📊 共 {shown} 份试卷 ({len(hist_files)}总存档)")

    _refresh_history()
    hist_filter_cb.bind("<<ComboboxSelected>>", lambda _e: _refresh_history())
    hist_subj_cb.bind("<<ComboboxSelected>>", lambda _e: _refresh_history())

    # 历史试卷操作
    def _load_selected_history():
        """选中历史试卷 → 载入为当前试卷 → 可直接去批卷"""
        sel = hist_tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请先点选一份历史试卷~")
            return
        fp = hist_tree.item(sel[0], "tags")[0]
        try:
            with open(fp, encoding="utf-8") as fh:
                data = json.load(fh)
            generated_exam["questions"] = data.get("questions", [])
            generated_exam["meta"] = data.get("meta", {})
            n = len(generated_exam["questions"])
            messagebox.showinfo("✅ 已载入",
                               f"📄 {generated_exam['meta'].get('grade','')} "
                               f"{generated_exam['meta'].get('subject','')}\n"
                               f"📝 {n} 道题, 满分 {generated_exam['meta'].get('total_score',0)}\n\n"
                               f"接下来可以:\n"
                               f"  → 📷 拍照批改 (用这份试卷的答案核对)\n"
                               f"  → ✍️ 在线答题\n"
                               f"  → 📄 导出Word再打印")
            # 切到拍照批改 Tab (子 Tab index 3) 并刷新答题卡片
            exam_tabs.select(3)
            try:
                _build_answer_cards()
            except Exception:
                pass
        except Exception as e:
            messagebox.showerror("加载失败", str(e))

    def _preview_selected():
        """预览试卷内容 (不载入, 只读)"""
        sel = hist_tree.selection()
        if not sel:
            return
        fp = hist_tree.item(sel[0], "tags")[0]
        try:
            with open(fp, encoding="utf-8") as fh:
                data = json.load(fh)
            meta = data.get("meta", {})
            qs = data.get("questions", [])
            preview_dlg = tk.Toplevel(tab_history); preview_dlg.title("📖 试卷预览")
            preview_dlg.geometry("700x560"); preview_dlg.configure(bg=PALETTE["bg"])
            txt = scrolledtext.ScrolledText(preview_dlg, font=PALETTE["body_font"],
                                             bg=PALETTE["white"], wrap="word",
                                             padx=10, pady=8)
            txt.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            txt.insert("1.0",
                      f"📄 {meta.get('grade','')} {meta.get('subject','')} 试卷\n"
                      f"📝 {len(qs)} 题 · 满分 {meta.get('total_score',0)} · {meta.get('time_limit',30)}分钟\n"
                      f"🕐 生成于 {meta.get('created_at','')}\n{'═'*50}\n\n")
            for i, q in enumerate(qs):
                txt.insert("end",
                          f"【第{i+1}题】{q.get('type','fill')} {q.get('score',5)}分\n"
                          f"  {q.get('content','')}\n")
                if q.get("options"):
                    txt.insert("end", f"  选项: {q['options']}\n")
                txt.insert("end", f"  ✅ {q.get('answer','')}")
                if q.get("topic"):
                    txt.insert("end", f"  📚{q['topic']}")
                txt.insert("end", "\n\n")
        except Exception as e:
            messagebox.showerror("预览失败", str(e))

    def _delete_history():
        sel = hist_tree.selection()
        if not sel:
            return
        if not messagebox.askyesno("确认", "确定删除这份历史试卷?\n删了就找不回来咯~"):
            return
        for s in sel:
            fp = hist_tree.item(s, "tags")[0]
            try:
                os.remove(fp)
            except Exception:
                pass
        _refresh_history()
        messagebox.showinfo("✅", "已删除")

    hist_btns = tk.Frame(tab_history, bg=PALETTE["bg"]); hist_btns.pack(fill=tk.X, padx=10, pady=6)
    _mk_color_button(hist_btns, "📖 预览", PALETTE["white"], _preview_selected, width=10).pack(side=tk.LEFT, padx=2)
    _mk_color_button(hist_btns, "📂 载入并批卷", PALETTE["mint"], _load_selected_history, width=16).pack(side=tk.LEFT, padx=2)
    _mk_color_button(hist_btns, "📄 导出Word", PALETTE["lavender"],
                     lambda: (_load_selected_history(), _export_word()),
                     width=12).pack(side=tk.LEFT, padx=2)
    _mk_color_button(hist_btns, "🔄 刷新列表", PALETTE["sky"], _refresh_history, width=10).pack(side=tk.LEFT, padx=2)
    _mk_color_button(hist_btns, "🗑️ 删除", PALETTE["pink"], _delete_history, width=8).pack(side=tk.RIGHT, padx=2)

    # ═══════════════════════════════════════
    # 子 Tab 2: ✍️ 在线答题
    # ═══════════════════════════════════════
    tab_online = tk.Frame(exam_tabs, bg=PALETTE["bg"])
    exam_tabs.add(tab_online, text="✍️ 在线答题")

    tk.Label(tab_online, text="✍️ 在线答题模式",
             font=PALETTE["title_font"],
             bg=PALETTE["bg"], fg=PALETTE["mint_dark"]).pack(pady=(14, 4))

    # 答题控件引用
    exam_state = {"questions": [], "answers": {}, "current": 0, "time_left": 0,
                  "timer_running": False, "timer_id": None}

    online_control = tk.Frame(tab_online, bg=PALETTE["bg"]); online_control.pack(fill=tk.X, padx=20, pady=6)
    timer_lbl = tk.Label(online_control, text="⏰ 时间: --:--", font=PALETTE["body_bold"],
                        bg=PALETTE["bg"], fg=PALETTE["pink_dark"])
    timer_lbl.pack(side=tk.LEFT, padx=10)
    progress_lbl = tk.Label(online_control, text="📊 进度: 0/0", font=PALETTE["body_bold"],
                           bg=PALETTE["bg"], fg=PALETTE["mint_dark"])
    progress_lbl.pack(side=tk.LEFT, padx=10)
    score_lbl = tk.Label(online_control, text="💯 得分: 0", font=PALETTE["body_bold"],
                        bg=PALETTE["bg"], fg=PALETTE["lavender_dark"])
    score_lbl.pack(side=tk.LEFT, padx=10)

    online_body = tk.Frame(tab_online, bg=PALETTE["bg"]); online_body.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

    q_card = tk.Frame(online_body, bg=PALETTE["white"],
                      bd=0, highlightthickness=2, highlightbackground=PALETTE["mint"])
    q_card.pack(fill=tk.BOTH, expand=True)

    q_title = tk.Label(q_card, text="点击上方「📋出题器」先生成试卷, 再回来答题哦!",
                      font=PALETTE["body_font"], bg=PALETTE["white"],
                      fg=PALETTE["text"], wraplength=900, justify="center")
    q_title.pack(pady=30, padx=20)
    _reg_font(q_title, PALETTE["body_font"])

    q_content = tk.Frame(q_card, bg=PALETTE["white"])
    q_content.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

    ans_entry = None
    choice_frame = None
    choice_vars = {}

    online_btn_row = tk.Frame(tab_online, bg=PALETTE["bg"]); online_btn_row.pack(pady=10)

    def _show_online_question(idx):
        nonlocal ans_entry, choice_frame
        for w in q_content.winfo_children():
            w.destroy()
        if idx < 0 or idx >= len(exam_state["questions"]):
            return
        q = exam_state["questions"][idx]
        q_title.config(text=f"【第{idx+1}题 · {q['score']}分 · {q.get('topic', '')}】\n\n{q['q']}")

        if q["type"] == "fill":
            tk.Label(q_content, text="✏️ 请输入答案:", font=PALETTE["body_font"],
                     bg=PALETTE["white"], fg=PALETTE["text"]).pack(anchor="w", pady=(10, 4))
            ans_entry = tk.Entry(q_content, font=PALETTE["body_font"],
                                 bg=PALETTE["bg"], fg=PALETTE["text"], relief="flat", bd=0)
            ans_entry.pack(fill=tk.X, padx=6, ipady=6)
            # 恢复已答
            saved = exam_state["answers"].get(idx, "")
            ans_entry.insert(0, saved)
        elif q["type"] == "choice":
            choice_frame = tk.Frame(q_content, bg=PALETTE["white"]); choice_frame.pack(fill=tk.X, pady=10)
            var = tk.IntVar(value=exam_state["answers"].get(idx, -1))
            choice_vars[idx] = var
            for j, opt in enumerate(q.get("options", [])):
                rb = tk.Radiobutton(choice_frame, text=f"  {chr(65+j)}. {opt}",
                                    variable=var, value=j,
                                    font=PALETTE["body_font"],
                                    bg=PALETTE["white"], fg=PALETTE["text"],
                                    activebackground=PALETTE["white"],
                                    selectcolor=PALETTE["mint"])
                rb.pack(anchor="w", pady=4)

    def _save_current_answer():
        idx = exam_state["current"]
        if idx < 0 or idx >= len(exam_state["questions"]):
            return
        q = exam_state["questions"][idx]
        if q["type"] == "fill" and ans_entry:
            exam_state["answers"][idx] = ans_entry.get().strip()
        elif q["type"] == "choice" and idx in choice_vars:
            v = choice_vars[idx].get()
            exam_state["answers"][idx] = v if v >= 0 else ""

    def _tick_timer():
        if not exam_state["timer_running"]:
            return
        if exam_state["time_left"] <= 0:
            _submit_exam()
            return
        m, s = divmod(exam_state["time_left"], 60)
        timer_lbl.config(text=f"⏰ 时间: {m:02d}:{s:02d}")
        exam_state["time_left"] -= 1
        exam_state["timer_id"] = tab_online.after(1000, _tick_timer)

    def _start_online_exam():
        # 使用已生成的试卷
        if not generated_exam["questions"]:
            messagebox.showinfo("提示", "请先到「📋出题器」Tab 生成试卷哦~")
            exam_tabs.select(0)
            return
        exam_state["questions"] = generated_exam["questions"]
        exam_state["answers"] = {}
        exam_state["current"] = 0
        exam_state["time_left"] = int(generated_exam["meta"]["time_limit"]) * 60
        exam_state["timer_running"] = True
        _show_online_question(0)
        _tick_timer()
        progress_lbl.config(text=f"📊 进度: 1/{len(exam_state['questions'])}")

    def _prev_q():
        _save_current_answer()
        if exam_state["current"] > 0:
            exam_state["current"] -= 1
            _show_online_question(exam_state["current"])
            progress_lbl.config(text=f"📊 进度: {exam_state['current']+1}/{len(exam_state['questions'])}")

    def _next_q():
        _save_current_answer()
        if exam_state["current"] < len(exam_state["questions"]) - 1:
            exam_state["current"] += 1
            _show_online_question(exam_state["current"])
            progress_lbl.config(text=f"📊 进度: {exam_state['current']+1}/{len(exam_state['questions'])}")

    def _submit_exam():
        exam_state["timer_running"] = False
        if exam_state["timer_id"]:
            try: tab_online.after_cancel(exam_state["timer_id"])
            except: pass
        _save_current_answer()
        # 评分
        questions = exam_state["questions"]
        answers = exam_state["answers"]
        results = []
        total = 0
        topic_hits = {}  # topic: [correct, total]
        for i, q in enumerate(questions):
            user_ans = answers.get(i, "")
            if q["type"] == "fill":
                correct = user_ans and _normalize_answer(user_ans) == _normalize_answer(q["answer"])
            else:
                correct = user_ans == q["answer"]
            score = q["score"] if correct else 0
            total += score
            topic = q.get("topic", "其他")
            if topic not in topic_hits:
                topic_hits[topic] = [0, 0]
            topic_hits[topic][1] += 1
            if correct:
                topic_hits[topic][0] += 1
            results.append({"idx": i+1, "question": q["q"][:30],
                            "user_ans": user_ans, "correct": correct,
                            "correct_ans": q["answer"] if q["type"]=="fill" else q["options"][q["answer"]],
                            "score": score, "topic": topic})
        max_score = sum(q["score"] for q in questions)
        # 保存进度
        progress = _load_progress()
        exam_record = {
            "grade": generated_exam["meta"]["grade"],
            "subject": generated_exam["meta"]["subject"],
            "total_score": total,
            "max_score": max_score,
            "accuracy": round(total/max_score*100, 1) if max_score else 0,
            "time": datetime.now().isoformat(),
            "topic_hits": topic_hits,
            "results": results,
        }
        progress["exams"].append(exam_record)
        # 更新 topic 历史
        for tp, (h, t) in topic_hits.items():
            tp_score = progress["topic_scores"].setdefault(tp, {"correct": 0, "total": 0})
            tp_score["correct"] += h
            tp_score["total"] += t
        _save_progress(progress)
        # 显示结果弹窗
        _show_exam_result(exam_record)

    def _normalize_answer(s):
        """简单答案归一化: 去空格去标点小写"""
        import re
        s = re.sub(r'[\s，。、.!！?？,.:;；"\'（）()【】\[\]]', '', s.lower())
        return s

    def _show_exam_result(record):
        win = tk.Toplevel(tab_online)
        win.title("🎉 答题结果")
        win.configure(bg=PALETTE["bg"])
        win.geometry("800x600")
        win.transient(tab_online)
        win.grab_set()

        pct = record["accuracy"]
        emoji = "🏆" if pct >= 90 else ("👍" if pct >= 70 else ("💪" if pct >= 60 else "📚"))
        color = PALETTE["mint_dark"] if pct >= 70 else PALETTE["pink_dark"]

        tk.Label(win, text=f"{emoji} 太棒啦! {record['total_score']}/{record['max_score']} 分 ({pct}%)",
                 font=("Comic Sans MS", 20, "bold"),
                 bg=PALETTE["bg"], fg=color).pack(pady=14)

        result_txt = scrolledtext.ScrolledText(win, font=PALETTE["body_font"],
                                               bg=PALETTE["white"], fg=PALETTE["text"],
                                               relief="flat", bd=0, wrap="word",
                                               padx=14, pady=14, height=18)
        result_txt.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        _reg_font(result_txt, PALETTE["body_font"])

        lines = [f"📚 {record['grade']} {record['subject']} 试卷批改结果",
                 f"📅 {record['time']}", "─"*50, ""]
        for r in record["results"]:
            mark = "✅" if r["correct"] else "❌"
            lines.append(f"{mark} 第{r['idx']}题 [{r['topic']}] — {r['score']}分")
            lines.append(f"   题目: {r['question']}...")
            lines.append(f"   你的答案: {r['user_ans'] or '(未作答)'}")
            lines.append(f"   正确答案: {r['correct_ans']}")
            lines.append("")
        # 薄弱知识点
        weak = [(tp, h[0], h[1]) for tp, h in record["topic_hits"].items() if h[0] < h[1]]
        if weak:
            lines.append("─"*50)
            lines.append("⚠️ 需要加强的知识点:")
            for tp, h, t in weak:
                lines.append(f"  · {tp}: {h}/{t} ({h/t*100:.0f}%)")
        result_txt.insert("1.0", "\n".join(lines))

        btn_row = tk.Frame(win, bg=PALETTE["bg"]); btn_row.pack(pady=10)
        _mk_color_button(btn_row, "📊 薄弱点分析", PALETTE["lavender"],
                        lambda: (win.destroy(), exam_tabs.select(4))[1], width=16).pack(side=tk.LEFT, padx=6)
        _mk_color_button(btn_row, "🆗 关闭", PALETTE["white"], win.destroy, width=12).pack(side=tk.LEFT, padx=6)

    # 在线答题按钮
    btn_row_online = tk.Frame(tab_online, bg=PALETTE["bg"]); btn_row_online.pack(pady=6)
    _mk_color_button(btn_row_online, "🚀 开始答题", PALETTE["mint"],
                    _start_online_exam, width=16).pack(side=tk.LEFT, padx=6)
    _mk_color_button(btn_row_online, "⬅️ 上一题", PALETTE["sky"],
                    _prev_q, width=12).pack(side=tk.LEFT, padx=6)
    _mk_color_button(btn_row_online, "➡️ 下一题", PALETTE["sky"],
                    _next_q, width=12).pack(side=tk.LEFT, padx=6)
    _mk_color_button(btn_row_online, "📝 交卷", PALETTE["pink"],
                    _submit_exam, width=12).pack(side=tk.LEFT, padx=6)

    # ═══════════════════════════════════════
    # 子 Tab 3: 📷 拍照批改 (左多图 + 右答案对比)
    # ═══════════════════════════════════════
    tab_ocr = tk.Frame(exam_tabs, bg=PALETTE["bg"])
    exam_tabs.add(tab_ocr, text="📷 拍照批改")

    tk.Label(tab_ocr, text="📷 拍照批改 · 多图浏览 · AI名师评分",
             font=PALETTE["title_font"],
             bg=PALETTE["bg"], fg=PALETTE["sky_dark"]).pack(pady=(14, 4))

    ocr_hint = tk.Label(tab_ocr,
                        text="🖼️ 左侧可批量选多张答题纸照片 → 📖 右侧显示标准答案 → ✏️ 录入学生答案 → 🤖 AI名师评分",
                        font=PALETTE["body_font"],
                        bg=PALETTE["bg"], fg=PALETTE["text_light"], wraplength=900)
    ocr_hint.pack(pady=(0, 6))
    _reg_font(ocr_hint, PALETTE["body_font"])

    ocr_body = tk.Frame(tab_ocr, bg=PALETTE["bg"]); ocr_body.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)

    # ═══ 左栏: 多图列表 + 大图预览 ═══
    left_col = tk.Frame(ocr_body, bg=PALETTE["bg"]); left_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))

    # 多图缩略图列表
    list_row = tk.Frame(left_col, bg=PALETTE["bg"]); list_row.pack(fill=tk.X)
    tk.Label(list_row, text="🖼️ 图片列表 (点击切换)",
             font=PALETTE["body_bold"],
             bg=PALETTE["bg"], fg=PALETTE["sky_dark"]).pack(side=tk.LEFT)

    ocr_imgs_frame = tk.Frame(left_col, bg=PALETTE["white"], height=140)
    ocr_imgs_frame.pack(fill=tk.X, pady=(4, 6))
    ocr_imgs_frame.pack_propagate(False)

    img_canvas = tk.Canvas(ocr_imgs_frame, bg=PALETTE["white"], highlightthickness=0)
    img_scroll = ttk.Scrollbar(ocr_imgs_frame, orient="horizontal", command=img_canvas.xview)
    img_inner = tk.Frame(img_canvas, bg=PALETTE["white"])
    img_inner.bind("<Configure>", lambda e: img_canvas.configure(scrollregion=img_canvas.bbox("all")))
    img_canvas.create_window((0, 0), window=img_inner, anchor="nw")
    img_canvas.configure(xscrollcommand=img_scroll.set)
    img_canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
    img_scroll.pack(side=tk.BOTTOM, fill=tk.X)

    # 跨鼠标滚轮横向滚动
    def _on_img_mousewheel(e):
        img_canvas.xview_scroll(int(-e.delta / 40), "units")
    img_canvas.bind_all("<MouseWheel>", _on_img_mousewheel)

    # 大图预览
    tk.Label(left_col, text="📷 当前图片预览",
             font=PALETTE["body_bold"],
             bg=PALETTE["bg"], fg=PALETTE["sky_dark"]).pack(pady=(4, 2))
    img_preview = tk.Label(left_col, text="(点击下方按钮添加图片)\n\n可多张一起选!",
                           font=PALETTE["body_font"],
                           bg=PALETTE["white"], fg=PALETTE["text_light"],
                           width=38, height=14, relief="flat", bd=0)
    img_preview.pack(fill=tk.BOTH, expand=True, pady=(0, 4))
    _reg_font(img_preview, PALETTE["body_font"])

    # ═══ 右栏: 🎯 逐题答题界面 ═══
    right_col = tk.Frame(ocr_body, bg=PALETTE["bg"]); right_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0))

    tk.Label(right_col, text="🎯 学生在线答题 (每题一个输入框)",
             font=("Comic Sans MS", 16, "bold"),
             bg=PALETTE["bg"], fg=PALETTE["pink_dark"]).pack(pady=(0, 4))

    # 滚动容器
    q_canvas = tk.Canvas(right_col, bg=PALETTE["bg"], highlightthickness=0)
    q_scroll = ttk.Scrollbar(right_col, orient="vertical", command=q_canvas.yview)
    q_inner = tk.Frame(q_canvas, bg=PALETTE["bg"])
    q_inner.bind("<Configure>", lambda e: q_canvas.configure(scrollregion=q_canvas.bbox("all")))
    q_canvas.create_window((0, 0), window=q_inner, anchor="nw")
    q_canvas.configure(yscrollcommand=q_scroll.set)
    q_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    q_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    # 每题的答题输入控件列表
    answer_inputs = []  # [(q_idx, input_widget, type), ...]  type: "fill" 或 "choice"

    def _build_answer_cards():
        """根据 generated_exam 动态创建逐题答题卡片"""
        # 清空旧卡片
        for w in q_inner.winfo_children():
            w.destroy()
        answer_inputs.clear()

        qs = generated_exam.get("questions", [])
        if not qs:
            tk.Label(q_inner,
                     text="⚠️ 还没有生成试卷!\n\n请先到「📋出题器」\n选好年级/学科 → 🎲生成试卷\n\n回来就能在这里答题啦~",
                     font=PALETTE["body_font"],
                     bg=PALETTE["bg"], fg=PALETTE["text_light"],
                     justify="center").pack(expand=True, pady=40)
            return

        for i, q in enumerate(qs):
            # 每题卡片
            card = tk.Frame(q_inner, bg=PALETTE["white"], bd=0,
                            highlightbackground=PALETTE["lavender"],
                            highlightthickness=2)
            card.pack(fill=tk.X, padx=8, pady=6)

            # 题干标题
            header = tk.Frame(card, bg=PALETTE["white"]); header.pack(fill=tk.X, padx=10, pady=(8, 4))
            type_label = "📝填空" if q["type"] == "fill" else "☑️选择"
            tk.Label(header, text=f"第{i+1}题 [{type_label}]",
                     font=("Comic Sans MS", 14, "bold"),
                     bg=PALETTE["white"], fg=PALETTE["lavender_dark"]).pack(side=tk.LEFT)
            tk.Label(header, text=f"  ⭐ {q['score']}分",
                     font=("Arial", 12),
                     bg=PALETTE["white"], fg=PALETTE["pink_dark"]).pack(side=tk.LEFT)
            if q.get("topic"):
                tk.Label(header, text=f"  📚 {q['topic']}",
                         font=("Arial", 11),
                         bg=PALETTE["white"], fg=PALETTE["sky_dark"]).pack(side=tk.LEFT, padx=6)

            # 题目内容
            content = q["content"]
            # 如果太长截断 + 展开
            if len(content) > 80:
                content_display = content[:80] + "..."
            else:
                content_display = content
            tk.Label(card, text=content_display,
                     font=PALETTE["body_font"],
                     bg=PALETTE["white"], fg=PALETTE["text"],
                     wraplength=560, justify="left").pack(anchor="w", padx=12)

            # 答题区
            ans_area = tk.Frame(card, bg=PALETTE["white"]); ans_area.pack(fill=tk.X, padx=12, pady=(6, 10))

            if q["type"] == "choice" and q.get("options"):
                # 选择题 → RadioButton
                var = tk.StringVar(value="")
                answer_inputs.append((i, var, "choice"))
                for opt_idx, opt_text in enumerate(q["options"]):
                    letter = chr(ord("A") + opt_idx)
                    rb = tk.Radiobutton(ans_area,
                                        text=f"{letter}. {opt_text}",
                                        variable=var, value=letter,
                                        font=PALETTE["body_font"],
                                        bg=PALETTE["white"],
                                        activebackground=PALETTE["lavender"],
                                        anchor="w")
                    rb.pack(anchor="w", pady=1)
            else:
                # 填空题 → Entry 输入框
                entry = tk.Entry(ans_area, font=PALETTE["body_font"],
                                 bg=PALETTE["white"], fg=PALETTE["text"],
                                 width=40, relief="solid", bd=2,
                                 highlightcolor=PALETTE["lavender"],
                                 highlightthickness=1)
                entry.pack(fill=tk.X, ipady=4)
                entry.insert(0, "")
                answer_inputs.append((i, entry, "fill"))

    def _collect_answers():
        """从答题卡片收集所有学生答案"""
        answers = []
        for idx, widget, wtype in answer_inputs:
            if wtype == "choice":
                val = widget.get()  # StringVar
            else:
                val = widget.get().strip()  # Entry
            answers.append(val)
        return answers

    # 标准答案面板 (折叠在底部，家长看)
    def _show_answer_key():
        ans_dlg = tk.Toplevel(tab_ocr); ans_dlg.title("📖 标准答案 (家长查看)")
        ans_dlg.geometry("600x500"); ans_dlg.configure(bg=PALETTE["bg"])
        ans_text_dlg = scrolledtext.ScrolledText(ans_dlg, font=PALETTE["body_font"],
                                                   bg=PALETTE["white"], fg=PALETTE["text"],
                                                   wrap="word", padx=10, pady=8)
        ans_text_dlg.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        qs = generated_exam.get("questions", [])
        meta = generated_exam.get("meta", {})
        ans_text_dlg.insert("1.0", f"📝 {meta.get('grade','')} {meta.get('subject','')} · 标准答案\n{'═'*40}\n\n")
        for i, q in enumerate(qs):
            ans_text_dlg.insert("end", f"【第{i+1}题】 ✅ {q['answer']}  ({q['score']}分)")
            if q.get("topic"):
                ans_text_dlg.insert("end", f"  📚{q['topic']}")
            ans_text_dlg.insert("end", "\n")
            if q.get("analysis"):
                ans_text_dlg.insert("end", f"    💡 {q['analysis'][:100]}\n")
            ans_text_dlg.insert("end", "\n")

    # 首次构建
    _build_answer_cards()

    # 当切换到这个 Tab 或试卷变化时刷新
    def _refresh_cards_if_exam_changed():
        _build_answer_cards()

    # ═══ 图片管理状态 ═══
    ocr_images = []          # [(path, photo_obj), ...]  缩略图 PhotoImage 要保持引用
    ocr_photos_ref = []      # 大图 PhotoImage 引用列表
    ocr_current_idx = tk.IntVar(value=-1)

    def _refresh_thumbnail_list():
        """刷新缩略图列表 — 更大 + 选中红框 + 删图按钮"""
        for w in img_inner.winfo_children():
            w.destroy()
        ocr_photos_ref.clear()
        cur = ocr_current_idx.get()

        if not ocr_images:
            tk.Label(img_inner, text="(暂无图片，点底部 📷批量选图)",
                     font=PALETTE["body_font"], bg=PALETTE["white"],
                     fg=PALETTE["text_light"]).pack(padx=20, pady=30)
            return

        for idx, (path, _) in enumerate(ocr_images):
            # 选中的用粉色高亮边
            bd_color = PALETTE["pink_dark"] if idx == cur else PALETTE["sky"]
            frame = tk.Frame(img_inner, bg=PALETTE["white"],
                             highlightthickness=4,
                             highlightbackground=bd_color,
                             highlightcolor=bd_color)
            frame.pack(side=tk.LEFT, padx=6, pady=4)

            try:
                if HAS_PIL:
                    img = Image.open(path)
                    img.thumbnail((140, 100))  # 更大
                    from PIL import ImageTk
                    photo = ImageTk.PhotoImage(img)
                    ocr_photos_ref.append(photo)
                    lbl = tk.Label(frame, image=photo, bg=PALETTE["white"])
                    lbl.pack()
                else:
                    tk.Label(frame, text=f"图{idx+1}", bg=PALETTE["white"],
                             width=14, height=6).pack()
            except Exception:
                tk.Label(frame, text=f"图{idx+1}\n(加载失败)",
                         bg=PALETTE["white"], width=14, height=5).pack()

            # 底部编号 + 删除
            btn_row = tk.Frame(frame, bg=PALETTE["white"]); btn_row.pack(fill=tk.X)
            tk.Label(btn_row, text=f"📄 #{idx+1}", font=("Arial", 11, "bold"),
                     bg=PALETTE["white"], fg=PALETTE["sky_dark"]).pack(side=tk.LEFT, padx=4)
            # 删除小按钮
            del_btn = tk.Label(btn_row, text="❌", font=("Arial", 10),
                               bg=PALETTE["white"], fg="red", cursor="hand2")
            del_btn.pack(side=tk.RIGHT, padx=2)
            def _del(_e, i=idx):
                ocr_images.pop(i)
                if ocr_current_idx.get() >= len(ocr_images):
                    ocr_current_idx.set(max(0, len(ocr_images) - 1))
                _refresh_thumbnail_list()
                if ocr_images:
                    _show_img(ocr_current_idx.get())
            del_btn.bind("<Button-1>", _del)

            # 点击选中
            for widget in (frame, frame.winfo_children()[0]):
                widget.bind("<Button-1>", lambda _e, i=idx: (
                    _show_img(i), _refresh_thumbnail_list()))

    def _show_img(idx):
        """显示第 idx 张图片的大图预览"""
        if idx < 0 or idx >= len(ocr_images):
            return
        ocr_current_idx.set(idx)
        path = ocr_images[idx][0]
        if HAS_PIL:
            try:
                img = Image.open(path)
                # 自适应预览区大小
                max_w = img_preview.winfo_width() or 500
                max_h = img_preview.winfo_height() or 380
                img.thumbnail((max_w - 20, max_h - 20))
                from PIL import ImageTk
                photo = ImageTk.PhotoImage(img)
                img_preview.config(image=photo, text="")
                img_preview._current_photo = photo  # 保持引用
            except Exception as e:
                img_preview.config(image="", text=f"加载失败: {e}")

    def _select_images_batch():
        """批量选择多张图片"""
        paths = filedialog.askopenfilenames(
            title="选择答题纸照片 (可多选!)",
            filetypes=[("图片", "*.png *.jpg *.jpeg *.bmp *.gif *.tiff")])
        if not paths:
            return
        added = 0
        for p in paths:
            # 避免重复
            if not any(img[0] == p for img in ocr_images):
                ocr_images.append((p, None))
                added += 1
        _refresh_thumbnail_list()
        # 显示第一张
        if ocr_images:
            _show_img(0)
        messagebox.showinfo("添加成功", f"✅ 添加了 {added} 张图片!\n共 {len(ocr_images)} 张在列表中。\n\n💡 可以点底部 🤖AI名师 → 👁️ 直接看图片批改")

    # OCR 提示文字 (保留但不依赖旧 ocr_text)
    def _ocr_all_images():
        """批量 OCR 所有图片内容 (仅供参考，建议用 AI 直接看图)"""
        if not ocr_images:
            messagebox.showwarning("提示", "请先添加答题纸图片!")
            return
        if not (HAS_TESSERACT and HAS_PIL):
            messagebox.showinfo("OCR 不可用", "未检测到 Tesseract OCR。\n\n💡 建议直接用 🤖 AI名师 → 👁️ 直接看图片批改")
            return
        all_texts = []
        for idx, (path, _) in enumerate(ocr_images):
            try:
                img = Image.open(path)
                text = pytesseract.image_to_string(img, lang="chi_sim+eng")
                all_texts.append(f"=== 第{idx+1}张 ===\n{text.strip()}")
            except Exception as e:
                all_texts.append(f"=== 第{idx+1}张 OCR失败: {e} ===")
        # OCR 结果弹框展示 (不再写入答题区)
        msg = "\n\n".join(all_texts)
        messagebox.showinfo("OCR识别结果",
                           f"已识别 {len(ocr_images)} 张图片!\n\n"
                           f"识别内容 (仅供参考):\n\n{msg[:500]}"
                           f"\n\n💡 建议: 请手动在右侧逐题答题框输入学生答案，或用 🤖AI名师 直接看图批改")

    def _grade_by_input():
        """✅ 批改出分 — 自动选模式: 有试卷就对比 / 没试卷有图片就AI纯图片批"""
        has_exam = bool(generated_exam["questions"])
        has_images = bool(ocr_images)

        if has_exam:
            # ─── 有试卷 → 本地逐题对比 ───
            answers = _collect_answers()
            questions = generated_exam["questions"]
            results = []
            total = 0
            topic_hits = {}
            for i, q in enumerate(questions):
                user_ans = answers[i] if i < len(answers) else ""
                if q["type"] == "fill":
                    correct = user_ans and _normalize_answer(user_ans) == _normalize_answer(q["answer"])
                else:
                    try:
                        idx = ord(user_ans.upper()) - ord("A") if user_ans.upper() in "ABCD" else -1
                        correct = idx == q["answer"]
                    except:
                        correct = False
                score = q["score"] if correct else 0
                total += score
                topic = q.get("topic", "其他")
                if topic not in topic_hits:
                    topic_hits[topic] = [0, 0]
                topic_hits[topic][1] += 1
                if correct:
                    topic_hits[topic][0] += 1
                results.append({"idx": i+1, "user_ans": user_ans, "correct": correct,
                                "score": score, "topic": topic})
            max_score = sum(q["score"] for q in questions)
            progress = _load_progress()
            exam_record = {
                "grade": generated_exam["meta"].get("grade", ""),
                "subject": generated_exam["meta"].get("subject", ""),
                "total_score": total,
                "max_score": max_score,
                "accuracy": round(total/max_score*100, 1) if max_score else 0,
                "time": datetime.now().isoformat(),
                "topic_hits": topic_hits,
                "results": results,
                "mode": f"本地批改{' + 图片' if has_images else ''}",
            }
            progress["exams"].append(exam_record)
            for tp, (h, t) in topic_hits.items():
                tp_score = progress["topic_scores"].setdefault(tp, {"correct": 0, "total": 0})
                tp_score["correct"] += h
                tp_score["total"] += t
            _save_progress(progress)
            _show_exam_result(exam_record)
            return

        # ─── 没试卷 → 需要 AI 来批 ───
        if not HAS_AI:
            messagebox.showwarning("提示",
                "没检测到出题器试卷, 而且 AI 不可用。\n\n"
                "两个办法:\n"
                "1. 先到「📋出题器」生成试卷 → 回来录入答案 → 点批改\n"
                "2. 点 🤖AI名师 → 选「📷纯图片批改」(需要配 deepseek API)")
            return

        if not has_images:
            messagebox.showwarning("提示",
                "既没有出题器试卷, 也没有上传图片。\n\n"
                "请先:\n📷 点左下角「📷批量选图」上传答题纸\n或 📋 到出题器生成试卷")
            return

        # 自动走 AI 纯图片批改
        _auto_ai_grade_pure()

    def _auto_ai_grade_pure():
        """没试卷但有图片 → 自动调 AI 纯图片批改"""
        style = "encourage"  # 默认鼓励风格
        style_name = TEACHER_STYLES[style]["name"]
        image_paths = [img[0] for img in ocr_images]

        dlg = tk.Toplevel(tab_ocr); dlg.title(f"✅ 批改出分 — {style_name} 自动批...")
        dlg.geometry("520x140"); dlg.configure(bg=PALETTE["bg"])
        tk.Label(dlg,
                 text=f"⏳ 正在让 AI 从图片里识别题目 + 批改...\n"
                      f"📷 共 {len(image_paths)} 张答题纸\n"
                      f"(deepseek 视觉模型, 需 15-40秒)",
                 font=PALETTE["body_font"],
                 bg=PALETTE["bg"], fg=PALETTE["lavender_dark"],
                 justify="center").pack(expand=True)
        dlg.update()

        def _run():
            result = grade_pure_from_images(
                image_paths=image_paths,
                grade_hint="",
                subject_hint="",
                style=style,
            )
            dlg.after(0, lambda: _show_ai_result(result, style_name))

        import threading
        threading.Thread(target=_run, daemon=True).start()

    def _ai_grade_teacher():
        """🤖 AI 名师评分 — 三种模式: 纯图片/图片+试卷/纯文字"""
        if not HAS_AI:
            messagebox.showwarning("AI 不可用", "请在主程序 config/ai_config.json 中配置 deepseek API")
            return

        has_images = len(ocr_images) > 0
        has_exam = bool(generated_exam["questions"])

        # 如果既没图片也没试卷 → 提示
        if not has_images and not has_exam:
            messagebox.showwarning("提示", "请先:\n📷 上传答题纸图片\n或 📋 先生成试卷 + 录入学生答案")
            return

        style_dlg = tk.Toplevel(tab_ocr); style_dlg.title("👨‍🏫 AI 智能批改")
        style_dlg.geometry("520x420")
        style_dlg.configure(bg=PALETTE["bg"])

        tk.Label(style_dlg, text="👨‍🏫 请选择 AI 批改方式:",
                 font=PALETTE["title_font"],
                 bg=PALETTE["bg"], fg=PALETTE["lavender_dark"]).pack(pady=(14, 8))

        # 模式选择 — 根据当前可用资源动态显示
        mode_frame = tk.LabelFrame(style_dlg, text="🎯 批改模式",
                                   bg=PALETTE["bg"], font=PALETTE["body_bold"])
        mode_frame.pack(fill=tk.X, padx=20, pady=4)

        # 默认优先纯图片模式（如果有图片）
        mode_var = tk.StringVar(value="pure" if has_images else ("vision" if has_images and has_exam else "text"))

        if has_images:
            tk.Radiobutton(mode_frame,
                           text=f"📷 纯图片批改 (AI自己从图片识题+批改) ⭐推荐",
                           variable=mode_var, value="pure",
                           font=PALETTE["body_font"], bg=PALETTE["bg"],
                           fg=PALETTE["pink_dark"], anchor="w").pack(anchor="w", padx=6, pady=2)

        if has_images and has_exam:
            tk.Radiobutton(mode_frame,
                           text=f"📷+📋 图片+试卷对比 (用出题器答案核对)",
                           variable=mode_var, value="vision",
                           font=PALETTE["body_font"], bg=PALETTE["bg"],
                           anchor="w").pack(anchor="w", padx=6, pady=2)

        if has_exam:
            tk.Radiobutton(mode_frame,
                           text="📝 纯文字对比 (右侧录入的学生答案 vs 试卷)",
                           variable=mode_var, value="text",
                           font=PALETTE["body_font"], bg=PALETTE["bg"],
                           anchor="w").pack(anchor="w", padx=6, pady=2)

        # 年级/学科提示 (纯图片模式 AI 需要这个猜测)
        hint_frame = tk.Frame(style_dlg, bg=PALETTE["bg"]); hint_frame.pack(fill=tk.X, padx=20, pady=4)
        tk.Label(hint_frame, text="💡 提示 (纯图片模式建议填):",
                 font=PALETTE["body_bold"],
                 bg=PALETTE["bg"], fg=PALETTE["sky_dark"]).pack(anchor="w")
        hint_row = tk.Frame(hint_frame, bg=PALETTE["bg"]); hint_row.pack(fill=tk.X, pady=2)
        grade_hint_var = tk.StringVar(value=generated_exam["meta"].get("grade", ""))
        subj_hint_var = tk.StringVar(value=generated_exam["meta"].get("subject", ""))
        tk.Label(hint_row, text="年级:", font=PALETTE["body_font"],
                 bg=PALETTE["bg"]).pack(side=tk.LEFT)
        tk.Entry(hint_row, textvariable=grade_hint_var, width=8,
                 font=PALETTE["body_font"]).pack(side=tk.LEFT, padx=4)
        tk.Label(hint_row, text="学科:", font=PALETTE["body_font"],
                 bg=PALETTE["bg"]).pack(side=tk.LEFT, padx=(10, 0))
        tk.Entry(hint_row, textvariable=subj_hint_var, width=8,
                 font=PALETTE["body_font"]).pack(side=tk.LEFT, padx=4)

        tk.Label(style_dlg, text="\n👨‍🏫 请选择名师风格:",
                 font=PALETTE["body_bold"],
                 bg=PALETTE["bg"], fg=PALETTE["text"]).pack(anchor="w", padx=20)

        teacher_style_var = tk.StringVar(value="encourage")
        for key, info in TEACHER_STYLES.items():
            row = tk.Frame(style_dlg, bg=PALETTE["bg"]); row.pack(pady=1, padx=20, anchor="w")
            rb = tk.Radiobutton(row, text=f"{info['emoji']} {info['name']}",
                                variable=teacher_style_var, value=key,
                                font=PALETTE["body_font"],
                                bg=PALETTE["bg"], anchor="w")
            rb.pack(side=tk.LEFT)
            tk.Label(row, text=info["system"][:35] + "...",
                     font=("Arial", 9),
                     bg=PALETTE["bg"], fg=PALETTE["text_light"]).pack(side=tk.LEFT, padx=6)

        def _do_ai():
            mode = mode_var.get()
            style = teacher_style_var.get()
            style_dlg.destroy()
            style_name = TEACHER_STYLES[style]["name"]

            if mode == "pure":
                mode_label = f"📷 纯图片批改 — AI自己识题 ({len(ocr_images)}张)"
            elif mode == "vision":
                mode_label = f"📷+📋 图片+试卷对比 ({len(ocr_images)}张)"
            else:
                mode_label = "📝 纯文字对比"

            dlg = tk.Toplevel(tab_ocr); dlg.title(f"🤖 AI {style_name} 评分中...")
            dlg.geometry("520x140"); dlg.configure(bg=PALETTE["bg"])
            tk.Label(dlg,
                     text=f"⏳ 正在让 {style_name} 批改...\n{mode_label}\n(deepseek API, 需15-40秒)",
                     font=PALETTE["body_font"],
                     bg=PALETTE["bg"], fg=PALETTE["lavender_dark"],
                     justify="center").pack(expand=True)
            dlg.update()

            image_paths = [img[0] for img in ocr_images]

            def _run_ai():
                if mode == "pure":
                    # 📷📷📷 纯图片批改 — 让 AI 自己从图里识题
                    result = grade_pure_from_images(
                        image_paths=image_paths,
                        grade_hint=grade_hint_var.get(),
                        subject_hint=subj_hint_var.get(),
                        style=style,
                    )
                elif mode == "vision":
                    # 📷+📋 图片 + 出题器试卷对比
                    result = grade_exam_from_images(
                        image_paths=image_paths,
                        questions=generated_exam["questions"],
                        grade=generated_exam["meta"].get("grade", ""),
                        subject=generated_exam["meta"].get("subject", ""),
                        style=style,
                        use_vision=True,
                    )
                else:
                    # 📝 纯文字
                    answers = _collect_answers()
                    questions = generated_exam["questions"]
                    user_answers = [answers[i] if i < len(answers) else "(未作答)" for i in range(len(questions))]
                    result = grade_exam_with_ai(
                        questions, user_answers,
                        grade=generated_exam["meta"].get("grade", ""),
                        subject=generated_exam["meta"].get("subject", ""),
                        style=style,
                    )
                dlg.after(0, lambda: _show_ai_result(result, style_name))

            import threading
            threading.Thread(target=_run_ai, daemon=True).start()

        _mk_color_button(style_dlg, "开始 AI 批改 🚀", PALETTE["mint"], _do_ai, width=18).pack(pady=10)

    def _show_ai_result(result, style_name):
        """🎨 漂亮的批改结果 — 大分数卡 + 紧凑表格 + 名师点评"""
        dlg = tk.Toplevel(tab_ocr); dlg.title(f"👨‍🏫 {style_name} · 批改报告")
        dlg.geometry("900x720"); dlg.configure(bg=PALETTE["bg"])

        # ─── 错误处理 ───
        if "error" in result:
            msg = tk.Label(dlg, text=f"❌ AI 出错啦:\n{result['error']}",
                           font=PALETTE["body_font"], bg=PALETTE["bg"],
                           fg="#EF4444", justify="center")
            msg.pack(expand=True)
            if "raw_text" in result:
                raw_txt = scrolledtext.ScrolledText(dlg, height=8, wrap="word",
                                                     font=("Arial", 10),
                                                     bg=PALETTE["white"])
                raw_txt.pack(fill=tk.X, padx=10, pady=(0, 10))
                raw_txt.insert("1.0", result["raw_text"][:800])
            return

        pq = result.get("per_question", [])
        total = result.get("total_score", 0)
        max_t = result.get("max_total", 0) or 1  # 防除0
        rate = result.get("accuracy_rate", 0)
        weak = result.get("weak_topics", [])
        summary = result.get("teacher_summary", "")
        suggestion = result.get("next_step_suggestion", "")
        correct_cnt = sum(1 for p in pq if p.get("correct"))
        wrong_cnt = len(pq) - correct_cnt

        # ═══ 顶部: 大分数卡 ═══
        score_card = tk.Frame(dlg, bg=PALETTE["lavender"],
                              highlightthickness=3, highlightbackground=PALETTE["lavender_dark"])
        score_card.pack(fill=tk.X, padx=16, pady=(14, 8))

        tk.Label(score_card, text="👨‍🏫 批改报告",
                 font=("Comic Sans MS", 20, "bold"),
                 bg=PALETTE["lavender"], fg=PALETTE["lavender_dark"]).pack(pady=(8, 0))

        # 大分数
        big = tk.Frame(score_card, bg=PALETTE["lavender"])
        big.pack(pady=6)
        score_color = "#10B981" if rate >= 80 else "#F59E0B" if rate >= 60 else "#EF4444"
        tk.Label(big, text=str(total), font=("Arial", 60, "bold"),
                 bg=PALETTE["lavender"], fg=score_color).pack(side=tk.LEFT)
        tk.Label(big, text=f" / {max_t}", font=("Arial", 24),
                 bg=PALETTE["lavender"], fg="#6B7280").pack(side=tk.LEFT, pady=(22, 0))

        # 进度条
        bar_bg = tk.Frame(score_card, bg=PALETTE["white"], height=16, width=500,
                          highlightthickness=1, highlightbackground=PALETTE["lavender_dark"])
        bar_bg.pack(pady=4)
        bar_bg.pack_propagate(False)
        bar_fill = tk.Frame(bar_bg, bg=score_color, height=14)
        bar_fill.place(x=0, y=0, width=max(4, int(500 * rate / 100)), height=16)

        # 三行统计
        stats = tk.Frame(score_card, bg=PALETTE["lavender"]); stats.pack(pady=(4, 8))
        for txt, col in [
            (f"✅ 答对 {correct_cnt}", "#10B981"),
            (f"❌ 答错 {wrong_cnt}", "#EF4444"),
            (f"📊 正确率 {rate}%", "#6366F1"),
        ]:
            tk.Label(stats, text=txt, font=("Arial", 14, "bold"),
                     bg=PALETTE["lavender"], fg=col).pack(side=tk.LEFT, padx=14)

        # ═══ 中部: 题目表格 ═══
        mid = tk.Frame(dlg, bg=PALETTE["bg"]); mid.pack(fill=tk.BOTH, expand=True, padx=16, pady=4)

        # Treeview 表格
        style_tree = ttk.Style()
        try:
            style_tree.theme_use("clam")
        except Exception:
            pass
        style_tree.configure("Result.Treeview",
                             font=("Arial", 12), rowheight=32,
                             background=PALETTE["white"], fieldbackground=PALETTE["white"])
        style_tree.configure("Result.Treeview.Heading",
                             font=("Arial", 13, "bold"))

        cols = ("no", "icon", "content", "student", "std", "score", "topic")
        tree = ttk.Treeview(mid, columns=cols, show="headings",
                            style="Result.Treeview", height=min(10, len(pq) + 1))
        heads = [("no", "#", 40), ("icon", "", 36),
                 ("content", "题目", 280),
                 ("student", "✍️ 学生答案", 160),
                 ("std", "✅ 标准", 120),
                 ("score", "得分", 60),
                 ("topic", "📚 知识点", 140)]
        for col, text, w in heads:
            tree.heading(col, text=text)
            tree.column(col, width=w, anchor="w" if col in ("content", "student", "std", "topic") else "center")
        # 颜色标签
        tree.tag_configure("correct", background="#D1FAE5")
        tree.tag_configure("wrong", background="#FEE2E2")
        tree.tag_configure("partial", background="#FEF3C7")

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb = ttk.Scrollbar(mid, orient="vertical", command=tree.yview)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        tree.configure(yscrollcommand=vsb.set)

        for p in pq:
            no = p.get("no", "?")
            correct = p.get("correct", False)
            if isinstance(correct, bool):
                icon = "✅" if correct else "❌"
                tag = "correct" if correct else "wrong"
            elif isinstance(correct, str) and correct == "partial":
                icon = "⚠️"
                tag = "partial"
            else:
                icon = "❌"; tag = "wrong"

            content = (p.get("content") or "")[:60]
            student = p.get("student_answer") or p.get("user_answer") or ""
            std = p.get("std_answer") or ""
            score = f"{p.get('score', 0)}/{p.get('max_score', 0)}"
            topic = (p.get("knowledge_point") or "")[:12]

            tree.insert("", "end",
                        values=(no, icon, content, student, std, score, topic),
                        tags=(tag,))

        # 点击某题显示详情
        def _on_select(_e):
            sel = tree.selection()
            if not sel: return
            idx = tree.index(sel[0])
            if idx >= len(pq): return
            p = pq[idx]
            # 更新详情面板
            detail_text.delete("1.0", "end")
            correct = p.get("correct", False)
            emoji = "✅" if correct else "❌"
            detail_text.insert("end", f"【第{p.get('no')}题】{emoji} {p.get('score')}/{p.get('max_score')}分\n", "d_title")
            if p.get("content"):
                detail_text.insert("end", f"📖 题目: {p['content']}\n\n")
            if p.get("student_answer"):
                detail_text.insert("end", f"✍️ 学生: {p['student_answer']}\n")
            if p.get("std_answer"):
                detail_text.insert("end", f"✅ 标准: {p['std_answer']}\n")
            if p.get("why_wrong") and not correct:
                detail_text.insert("end", f"\n🧐 错因: {p['why_wrong']}\n", "d_wrong")
            if p.get("easy_trap"):
                detail_text.insert("end", f"⚠️ 陷阱: {p['easy_trap']}\n", "d_trap")
            if p.get("teacher_tip"):
                detail_text.insert("end", f"\n👨‍🏫 {p['teacher_tip']}\n", "d_tip")

        tree.bind("<<TreeviewSelect>>", _on_select)

        # ─── 底部: 详情面板 + 总结 ───
        bottom = tk.Frame(dlg, bg=PALETTE["bg"]); bottom.pack(fill=tk.BOTH, expand=False, padx=16, pady=(6, 10))

        # 左: 点击表格行 → 显示详情
        detail_frame = tk.LabelFrame(bottom, text="💡 点击上方表格行查看详情",
                                     bg=PALETTE["bg"], font=PALETTE["body_bold"],
                                     fg=PALETTE["sky_dark"], padx=6, pady=4)
        detail_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))

        detail_text = scrolledtext.ScrolledText(detail_frame, height=8, wrap="word",
                                                 font=("Arial", 11),
                                                 bg=PALETTE["white"], padx=8, pady=6)
        detail_text.pack(fill=tk.BOTH, expand=True)
        detail_text.tag_config("d_title", font=("Arial", 13, "bold"), foreground="#374151")
        detail_text.tag_config("d_wrong", foreground="#EF4444")
        detail_text.tag_config("d_trap", foreground="#F59E0B")
        detail_text.tag_config("d_tip", font=("Arial", 11, "bold"), foreground="#8B5CF6")

        # 右: 总结面板
        sum_frame = tk.LabelFrame(bottom, text="📝 老师总评 & 下一步",
                                   bg=PALETTE["bg"], font=PALETTE["body_bold"],
                                   fg=PALETTE["pink_dark"], padx=6, pady=4, width=280)
        sum_frame.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(8, 0))
        sum_frame.pack_propagate(False)

        sum_text = scrolledtext.ScrolledText(sum_frame, height=8, wrap="word",
                                              font=("Arial", 11),
                                              bg=PALETTE["white"], padx=8, pady=6)
        sum_text.pack(fill=tk.BOTH, expand=True)
        sum_text.insert("1.0", summary + "\n\n" + suggestion)

        # 薄弱知识点标签
        if weak:
            tk.Label(dlg,
                     text="🎯 薄弱点: " + "  |  ".join(weak[:5]),
                     font=("Arial", 11, "bold"),
                     bg=PALETTE["bg"], fg="#F59E0B").pack(pady=(0, 6))

        # 降级提示
        if result.get("_note"):
            tk.Label(dlg, text=f"💡 {result['_note']}",
                     font=("Arial", 10), bg=PALETTE["bg"], fg="#6B7280").pack()

        # 先默认显示第一题详情
        if pq:
            dlg.after(100, lambda: tree.selection_set(tree.get_children()[0]))

    # ═══ 底部按钮区 ═══
    btn_row_ocr = tk.Frame(tab_ocr, bg=PALETTE["bg"]); btn_row_ocr.pack(pady=6)
    _mk_color_button(btn_row_ocr, "📷 批量选图", PALETTE["sky"],
                    _select_images_batch, width=14).pack(side=tk.LEFT, padx=4)
    _mk_color_button(btn_row_ocr, "📋 刷新题目", PALETTE["sun"],
                    _build_answer_cards, width=12).pack(side=tk.LEFT, padx=4)
    _mk_color_button(btn_row_ocr, "📖 看标准答案", PALETTE["white"],
                    _show_answer_key, width=12).pack(side=tk.LEFT, padx=4)
    _mk_color_button(btn_row_ocr, "✅ 批改出分", PALETTE["mint"],
                    _grade_by_input, width=12).pack(side=tk.LEFT, padx=4)
    _ai_btn_ocr = _mk_color_button(btn_row_ocr, "🤖 AI名师", PALETTE["pink"],
                                   _ai_grade_teacher, width=12)
    _ai_btn_ocr.pack(side=tk.LEFT, padx=4)
    if not HAS_AI:
        _ai_btn_ocr.config(state=tk.DISABLED)

    # 自动构建答题卡片 (如果已有试卷)
    _build_answer_cards()

    # ═══ 子 Tab 4: 📊 薄弱点分析 ═══
    tab_analysis = tk.Frame(exam_tabs, bg=PALETTE["bg"])
    exam_tabs.add(tab_analysis, text="📊 薄弱点分析")

    tk.Label(tab_analysis, text="📊 学习薄弱点雷达图 & 知识补漏",
             font=PALETTE["title_font"],
             bg=PALETTE["bg"], fg=PALETTE["mint_dark"]).pack(pady=(14, 4))

    analysis_body = tk.Frame(tab_analysis, bg=PALETTE["bg"]); analysis_body.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # 左侧: 雷达图
    radar_frame = tk.LabelFrame(analysis_body, text="🎯 知识点掌握雷达图",
                                font=PALETTE["body_bold"],
                                bg=PALETTE["bg"], fg=PALETTE["lavender_dark"],
                                padx=6, pady=6)
    radar_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

    # 右侧: 建议 & 历史
    right_analysis = tk.Frame(analysis_body, bg=PALETTE["bg"]); right_analysis.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0))

    suggest_frame = tk.LabelFrame(right_analysis, text="💡 针对性复习建议",
                                  font=PALETTE["body_bold"],
                                  bg=PALETTE["bg"], fg=PALETTE["pink_dark"],
                                  padx=6, pady=6)
    suggest_frame.pack(fill=tk.BOTH, expand=True)

    suggest_txt = scrolledtext.ScrolledText(suggest_frame, font=PALETTE["body_font"],
                                            bg=PALETTE["white"], fg=PALETTE["text"],
                                            relief="flat", bd=0, wrap="word",
                                            padx=10, pady=10, height=14)
    _reg_font(suggest_txt, PALETTE["body_font"])
    suggest_txt.pack(fill=tk.BOTH, expand=True)

    def _draw_radar():
        # 清空
        for w in radar_frame.winfo_children():
            w.destroy()
        progress = _load_progress()
        topic_scores = progress.get("topic_scores", {})
        if not topic_scores:
            tk.Label(radar_frame,
                     text="暂无数据~\n\n先到「📋出题器」出题\n→ 「✍️在线答题」或「📷拍照批改」\n→ 回来看看进步!",
                     font=PALETTE["body_font"],
                     bg=PALETTE["bg"], fg=PALETTE["text_light"],
                     justify="center").pack(pady=40)
            suggest_txt.delete("1.0", "end")
            suggest_txt.insert("1.0", "🎯 开始你的第一次练习吧~\n\n数据会自动保存到 ~/.tutor_helper/\n下次打开就有进步曲线啦!")
            return
        # 取 TOP 8 薄弱知识点 (按 total 排序)
        sorted_topics = sorted(topic_scores.items(),
                               key=lambda x: x[1]["total"], reverse=True)[:8]
        labels = [t[0] for t in sorted_topics]
        values = [t[1]["correct"] / t[1]["total"] * 100 for t in sorted_topics]
        values_clamped = [max(5, min(100, v)) for v in values]  # 雷达图最小值5

        if HAS_MATPLOTLIB:
            fig = plt.figure(figsize=(6, 5), facecolor=PALETTE["bg"])
            ax = fig.add_subplot(111, polar=True)
            angles = [n / float(len(labels)) * 2 * 3.14159 for n in range(len(labels))]
            angles += angles[:1]
            values_clamped += values_clamped[:1]
            ax.plot(angles, values_clamped, "o-", linewidth=2, color=PALETTE["lavender_dark"])
            ax.fill(angles, values_clamped, alpha=0.3, color=PALETTE["lavender"])
            ax.set_xticks(angles[:-1])
            ax.set_xticklabels(labels, fontsize=10, color=PALETTE["text"])
            ax.set_ylim(0, 100)
            ax.set_yticks([20, 40, 60, 80, 100])
            ax.set_yticklabels(["20%", "40%", "60%", "80%", "100%"], fontsize=8)
            ax.set_title("🎯 知识点掌握程度", fontsize=14, pad=15, color=PALETTE["lavender_dark"])
            fig.tight_layout()
            canvas = FigureCanvasTkAgg(fig, master=radar_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        else:
            # 降级: 纯文本条形图
            tk.Label(radar_frame, text="📊 知识点掌握 (条形图):",
                     font=PALETTE["body_bold"],
                     bg=PALETTE["bg"], fg=PALETTE["lavender_dark"]).pack(pady=4)
            for tp, v in sorted(zip(labels, values), key=lambda x: x[1]):
                bar = "█" * int(v / 5) + "░" * (20 - int(v / 5))
                color = PALETTE["mint_dark"] if v >= 70 else (PALETTE["sun_dark"] if v >= 50 else PALETTE["pink_dark"])
                tk.Label(radar_frame, text=f"{tp:12s} {bar} {v:.0f}%",
                         font=("Menlo", 12), bg=PALETTE["bg"], fg=color).pack(anchor="w", padx=10)

        # 生成薄弱点建议
        suggest_txt.delete("1.0", "end")
        weak_topics = [(labels[i], values[i]) for i in range(len(labels)) if values[i] < 70]
        suggest_lines = ["💡 薄弱点分析 & 复习建议", "─" * 40, ""]
        if weak_topics:
            suggest_lines.append(f"发现 {len(weak_topics)} 个需要加强的知识点:\n")
            for tp, v in sorted(weak_topics, key=lambda x: x[1]):
                level = "🔥 紧急" if v < 40 else ("⚠️ 注意" if v < 60 else "📚 巩固")
                suggest_lines.append(f"  [{level}] {tp} — 正确率 {v:.0f}%")
                # 推荐对应 Tab
                for key, (tab_name, knowledge_key) in TOPIC_TO_KNOWLEDGE.items():
                    if key in tp:
                        suggest_lines.append(f"      → 建议: 打开「{tab_name}」Tab → 学习「{knowledge_key}」")
                        break
                else:
                    suggest_lines.append(f"      → 建议: 回到知识点 Tab 查找对应章节复习")
                suggest_lines.append("")
        else:
            suggest_lines.append("🎉 太棒了! 所有知识点正确率都超过 70%!")
            suggest_lines.append("继续保持, 尝试更难的题目挑战自己吧!\n")

        # 历史成绩趋势
        history = progress.get("exams", [])[-5:]  # 最近5次
        if history:
            suggest_lines.append("─" * 40)
            suggest_lines.append("📈 最近 5 次练习成绩:")
            for rec in history:
                time_str = rec.get("time", "")[5:16].replace("T", " ")
                accuracy = rec.get("accuracy", 0)
                bar = "█" * int(accuracy / 5) + "░" * (20 - int(accuracy / 5))
                suggest_lines.append(f"  {time_str}  {rec['subject']} {rec['total_score']}/{rec['max_score']}  {bar}")
        suggest_txt.insert("1.0", "\n".join(suggest_lines))

    def _show_history():
        progress = _load_progress()
        exams = progress.get("exams", [])
        if not exams:
            messagebox.showinfo("暂无历史", "还没有练习记录哦~")
            return
        win = tk.Toplevel(tab_analysis)
        win.title("📚 全部历史记录")
        win.configure(bg=PALETTE["bg"])
        win.geometry("700x500")
        txt = scrolledtext.ScrolledText(win, font=PALETTE["body_font"],
                                        bg=PALETTE["white"], fg=PALETTE["text"],
                                        relief="flat", bd=0, wrap="word",
                                        padx=14, pady=14)
        _reg_font(txt, PALETTE["body_font"])
        txt.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        lines = ["📚 全部练习历史", "═" * 40, ""]
        for i, rec in enumerate(reversed(exams), 1):
            lines.append(f"#{i}  {rec.get('time', '').replace('T', ' ')}")
            lines.append(f"    {rec.get('grade','')} {rec.get('subject','')}")
            lines.append(f"    得分: {rec['total_score']}/{rec['max_score']}  正确率: {rec['accuracy']}%")
            lines.append("")
        txt.insert("1.0", "\n".join(lines))

    def _clear_history():
        if messagebox.askyesno("确认", "确定要清空所有练习历史吗?"):
            _save_progress({"exams": [], "topic_scores": {}})
            _draw_radar()
            messagebox.showinfo("已清空", "历史记录已清除!")

    btn_row_analysis = tk.Frame(tab_analysis, bg=PALETTE["bg"]); btn_row_analysis.pack(pady=6)
    _mk_color_button(btn_row_analysis, "🔄 刷新分析", PALETTE["mint"],
                    _draw_radar, width=14).pack(side=tk.LEFT, padx=6)
    _mk_color_button(btn_row_analysis, "📚 全部历史", PALETTE["sky"],
                    _show_history, width=14).pack(side=tk.LEFT, padx=6)
    _mk_color_button(btn_row_analysis, "🗑️ 清空历史", PALETTE["pink"],
                    _clear_history, width=14).pack(side=tk.LEFT, padx=6)

    # 首次加载时画一下
    _draw_radar()

    # 切换到分析Tab时自动刷新
    def _on_exam_tab_changed(_evt=None):
        idx = exam_tabs.index(exam_tabs.select())
        if idx == 4:  # 📊 薄弱点分析 (index 4)
            _draw_radar()
        elif idx == 3:  # 📷 拍照批改 (index 3)
            _refresh_cards_if_exam_changed()

    exam_tabs.bind("<<NotebookTabChanged>>", _on_exam_tab_changed)

    # ═══════════════════════════════════════
    # 子 Tab 5: 📚 题库管理 (CRUD + 导入)
    # ═══════════════════════════════════════
    tab_kb = tk.Frame(exam_tabs, bg=PALETTE["bg"])
    exam_tabs.add(tab_kb, text="📚 题库管理")

    # 初始化 DB
    if HAS_EXAM_DB:
        try:
            init_db()
        except Exception as e:
            messagebox.showwarning("DB 初始化", f"题库 DB 初始化: {e}")

    # 顶部统计条
    stats_bar = tk.Frame(tab_kb, bg=PALETTE["bg"]); stats_bar.pack(fill=tk.X, padx=10, pady=8)
    stat_labels = {}
    if HAS_EXAM_DB:
        st = get_stats()
        label_data = [
            ("total_questions", "📝 总题数", PALETTE["mint_dark"]),
            ("total_knowledge", "🧩 知识点", PALETTE["sky_dark"]),
            ("total_exams", "📄 试卷", PALETTE["lavender_dark"]),
        ]
        for key, text, color in label_data:
            lbl = tk.Label(stats_bar, text=f"{text}: {st.get(key, 0)}",
                          font=PALETTE["body_bold"],
                          bg=PALETTE["bg"], fg=color)
            lbl.pack(side=tk.LEFT, padx=10)
            _reg_font(lbl, PALETTE["body_bold"])
            stat_labels[key] = lbl

    # 筛选栏
    filter_bar = tk.Frame(tab_kb, bg=PALETTE["bg"]); filter_bar.pack(fill=tk.X, padx=10, pady=4)

    tk.Label(filter_bar, text="🎓 年级:", font=PALETTE["body_bold"],
             bg=PALETTE["bg"], fg=PALETTE["text"]).pack(side=tk.LEFT)
    kb_grade_var = tk.StringVar(value="全部")
    kb_grade_cb = ttk.Combobox(filter_bar, textvariable=kb_grade_var, state="readonly",
                                values=["全部"] + (get_all_grades() if HAS_EXAM_DB else []),
                                width=12, font=PALETTE["body_font"])
    kb_grade_cb.pack(side=tk.LEFT, padx=4)

    tk.Label(filter_bar, text="📚 学科:", font=PALETTE["body_bold"],
             bg=PALETTE["bg"], fg=PALETTE["text"]).pack(side=tk.LEFT, padx=(10, 0))
    kb_subject_var = tk.StringVar(value="全部")
    kb_subject_cb = ttk.Combobox(filter_bar, textvariable=kb_subject_var, state="readonly",
                                 values=["全部"] + (get_all_subjects() if HAS_EXAM_DB else []),
                                 width=10, font=PALETTE["body_font"])
    kb_subject_cb.pack(side=tk.LEFT, padx=4)

    tk.Label(filter_bar, text="🧩 知识点:", font=PALETTE["body_bold"],
             bg=PALETTE["bg"], fg=PALETTE["text"]).pack(side=tk.LEFT, padx=(10, 0))
    kb_topic_var = tk.StringVar(value="全部")
    kb_topic_cb = ttk.Combobox(filter_bar, textvariable=kb_topic_var, state="readonly",
                               values=["全部"], width=18, font=PALETTE["body_font"])
    kb_topic_cb.pack(side=tk.LEFT, padx=4)

    # 搜索框
    tk.Label(filter_bar, text="🔍 搜索:", font=PALETTE["body_bold"],
             bg=PALETTE["bg"], fg=PALETTE["text"]).pack(side=tk.LEFT, padx=(10, 0))
    kb_search_var = tk.StringVar()
    kb_search_entry = tk.Entry(filter_bar, textvariable=kb_search_var,
                               font=PALETTE["body_font"], width=18,
                               bg=PALETTE["white"], fg=PALETTE["text"],
                               relief="flat", bd=0)
    kb_search_entry.pack(side=tk.LEFT, padx=4)

    # Treeview 表格
    table_frame = tk.Frame(tab_kb, bg=PALETTE["bg"]); table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=6)

    style2 = ttk.Style()
    try:
        style2.theme_use("clam")
    except Exception:
        pass
    style2.configure("KBT.Treeview", font=PALETTE["body_font"], rowheight=32)
    style2.configure("KBT.Treeview.Heading", font=PALETTE["body_bold"])

    columns = ("id", "grade", "subject", "topic", "q_type", "content", "answer", "score")
    kb_tree = ttk.Treeview(table_frame, columns=columns, show="headings",
                           style="KBT.Treeview", selectmode="browse")
    heads = [("id", "ID", 50), ("grade", "年级", 70), ("subject", "学科", 60),
             ("topic", "知识点", 120), ("q_type", "类型", 55),
             ("content", "题干", 450), ("answer", "答案", 120), ("score", "分值", 50)]
    for col, text, w in heads:
        kb_tree.heading(col, text=text)
        kb_tree.column(col, width=w, anchor="w")
    kb_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    vsb = ttk.Scrollbar(table_frame, orient="vertical", command=kb_tree.yview)
    vsb.pack(side=tk.RIGHT, fill=tk.Y)
    kb_tree.configure(yscrollcommand=vsb.set)

    def _refresh_kb_topics(*_):
        if not HAS_EXAM_DB: return
        g = None if kb_grade_var.get() == "全部" else kb_grade_var.get()
        s = None if kb_subject_var.get() == "全部" else kb_subject_var.get()
        topics = ["全部"] + db_get_topics(g, s)
        kb_topic_cb["values"] = topics
        kb_topic_var.set("全部")

    def _refresh_kb_list():
        """刷新列表"""
        for item in kb_tree.get_children():
            kb_tree.delete(item)
        if not HAS_EXAM_DB: return
        g = None if kb_grade_var.get() == "全部" else kb_grade_var.get()
        s = None if kb_subject_var.get() == "全部" else kb_subject_var.get()
        t = None if kb_topic_var.get() == "全部" else kb_topic_var.get()
        kw = kb_search_var.get().strip() or None
        rows = get_questions(grade=g, subject=s, topic=t, keyword=kw, limit=300)
        for r in rows:
            content_short = r["content"][:80] + ("..." if len(r["content"]) > 80 else "")
            ans = r["answer"]
            if r.get("q_type") == "choice" and r.get("options") and isinstance(r["options"], list):
                try: ans = f"{chr(65+r['answer'])}. {r['options'][r['answer']]}"
                except: pass
            kb_tree.insert("", "end", iid=str(r["id"]),
                           values=(r["id"], r["grade"], r["subject"], r["topic"],
                                   r["q_type"], content_short, ans, r.get("score", 5)))
        # 更新统计
        st = get_stats()
        stat_labels["total_questions"].config(text=f"📝 总题数: {st['total_questions']}")

    kb_grade_var.trace_add("write", lambda *_: (_refresh_kb_topics(), _refresh_kb_list()))
    kb_subject_var.trace_add("write", lambda *_: (_refresh_kb_topics(), _refresh_kb_list()))
    kb_topic_var.trace_add("write", lambda *_: _refresh_kb_list())
    kb_search_var.trace_add("write", lambda *_: _refresh_kb_list())

    # 按钮区
    btn_frame_kb = tk.Frame(tab_kb, bg=PALETTE["bg"]); btn_frame_kb.pack(pady=8)
    _mk_color_button(btn_frame_kb, "🔄 刷新", PALETTE["mint"], _refresh_kb_list, width=10).pack(side=tk.LEFT, padx=4)
    _mk_color_button(btn_frame_kb, "➕ 手动添加", PALETTE["pink"],
                    lambda: _kb_add_dialog(tab_kb, on_save=_refresh_kb_list), width=14).pack(side=tk.LEFT, padx=4)
    _mk_color_button(btn_frame_kb, "✏️ 编辑选中", PALETTE["sky"],
                    lambda: _kb_edit_dialog(tab_kb, kb_tree, on_save=_refresh_kb_list), width=14).pack(side=tk.LEFT, padx=4)
    _mk_color_button(btn_frame_kb, "🗑️ 删除选中", PALETTE["pink_dark"],
                    lambda: _kb_delete(kb_tree, on_save=_refresh_kb_list), width=14).pack(side=tk.LEFT, padx=4)
    _mk_color_button(btn_frame_kb, "📥 导入JSON", PALETTE["lavender"],
                    lambda: _kb_import_json(on_done=_refresh_kb_list), width=14).pack(side=tk.LEFT, padx=4)
    _mk_color_button(btn_frame_kb, "📄 导入Word", PALETTE["lavender"],
                    lambda: _kb_import_word(on_done=_refresh_kb_list), width=14).pack(side=tk.LEFT, padx=4)
    _mk_color_button(btn_frame_kb, "📁 扫描导入文件夹", PALETTE["sun"],
                    lambda: _kb_scan_folder(on_done=_refresh_kb_list), width=18).pack(side=tk.LEFT, padx=4)

    # 初始加载
    _refresh_kb_topics()
    _refresh_kb_list()
    # 切换到题库管理 Tab 时也刷新
    def _on_kb_tab_show(_evt=None):
        try:
            idx = exam_tabs.index(exam_tabs.select())
            if idx >= 0:
                _refresh_kb_topics()
                _refresh_kb_list()
        except Exception:
            pass
    exam_tabs.bind("<<NotebookTabChanged>>", lambda e: (_on_exam_tab_changed(e), _on_kb_tab_show()))

    # ── 题库操作对话框 ──
    def _kb_add_dialog(parent, on_save=None):
        if not HAS_EXAM_DB:
            messagebox.showwarning("提示", "题库 DB 模块不可用"); return
        dlg = tk.Toplevel(parent); dlg.title("➕ 添加题目")
        dlg.configure(bg=PALETTE["bg"]); dlg.geometry("620x580")
        dlg.transient(parent); dlg.grab_set()
        _kb_form(dlg, None, on_save)

    def _kb_edit_dialog(parent, tree, on_save=None):
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请先选一道题~"); return
        if not HAS_EXAM_DB: return
        qid = int(sel[0])
        rows = get_questions()
        row = next((r for r in rows if r["id"] == qid), None)
        if not row: return
        dlg = tk.Toplevel(parent); dlg.title("✏️ 编辑题目")
        dlg.configure(bg=PALETTE["bg"]); dlg.geometry("620x580")
        dlg.transient(parent); dlg.grab_set()
        _kb_form(dlg, row, on_save, editing_id=qid)

    def _kb_form(dlg, row, on_save, editing_id=None):
        """题库添加/编辑共用表单"""
        def _row(label, key, widget_class=tk.Entry, **kw):
            r = tk.Frame(dlg, bg=PALETTE["bg"]); r.pack(fill=tk.X, padx=12, pady=4)
            tk.Label(r, text=label, font=PALETTE["body_bold"], width=10, anchor="w",
                     bg=PALETTE["bg"], fg=PALETTE["text"]).pack(side=tk.LEFT)
            var = kw.pop("textvariable", tk.StringVar(value=(row or {}).get(key, "")))
            w = widget_class(r, textvariable=var, font=PALETTE["body_font"],
                             bg=PALETTE["white"], fg=PALETTE["text"],
                             relief="flat", bd=0, **kw)
            w.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4)
            return var, w

        grade_var, _ = _row("🎓 年级", "grade", ttk.Combobox,
                            values=["三上","三下","四上","四下","五上","五下"])
        if row: grade_var.set(row["grade"])
        subject_var, _ = _row("📚 学科", "subject", ttk.Combobox,
                              values=["语文","数学","英语","科学"])
        if row: subject_var.set(row["subject"])
        topic_var, _ = _row("🧩 知识点", "topic")
        if row: topic_var.set(row["topic"])
        type_var, _ = _row("📋 类型", "q_type", ttk.Combobox,
                           values=["fill", "choice"])
        if row: type_var.set(row.get("q_type", "fill"))

        # 题干 (多行)
        tr = tk.Frame(dlg, bg=PALETTE["bg"]); tr.pack(fill=tk.X, padx=12, pady=4)
        tk.Label(tr, text="❓ 题干", font=PALETTE["body_bold"],
                 bg=PALETTE["bg"], fg=PALETTE["text"]).pack(anchor="w")
        content_txt = scrolledtext.ScrolledText(dlg, font=PALETTE["body_font"],
                                                bg=PALETTE["white"], fg=PALETTE["text"],
                                                relief="flat", bd=0, wrap="word",
                                                height=5, padx=8, pady=6)
        content_txt.pack(fill=tk.BOTH, expand=True, padx=12, pady=2)
        _reg_font(content_txt, PALETTE["body_font"])
        content_txt.insert("1.0", (row or {}).get("content", (row or {}).get("q", "")))

        # 选项 (仅 choice 类型)
        opt_frame = tk.LabelFrame(dlg, text="🔤 选项 (选择题用, 每行一个)",
                                  font=PALETTE["body_bold"],
                                  bg=PALETTE["bg"], fg=PALETTE["text"], padx=6, pady=4)
        opt_frame.pack(fill=tk.X, padx=12, pady=4)
        opt_txt = scrolledtext.ScrolledText(opt_frame, font=PALETTE["small_font"],
                                            bg=PALETTE["white"], fg=PALETTE["text"],
                                            relief="flat", bd=0, height=4,
                                            padx=6, pady=4)
        opt_txt.pack(fill=tk.X)
        _reg_font(opt_txt, PALETTE["small_font"])
        if row and row.get("options"):
            if isinstance(row["options"], list):
                opt_txt.insert("1.0", "\n".join(row["options"]))

        # 答案
        ans_var, _ = _row("✅ 答案", "answer")
        if row: ans_var.set(row["answer"])

        # 解析
        ar = tk.Frame(dlg, bg=PALETTE["bg"]); ar.pack(fill=tk.X, padx=12, pady=4)
        tk.Label(ar, text="💡 解析/易错点", font=PALETTE["body_bold"],
                 bg=PALETTE["bg"], fg=PALETTE["text"]).pack(anchor="w")
        ana_txt = scrolledtext.ScrolledText(dlg, font=PALETTE["small_font"],
                                            bg=PALETTE["white"], fg=PALETTE["text"],
                                            relief="flat", bd=0, height=3,
                                            padx=6, pady=4)
        ana_txt.pack(fill=tk.BOTH, expand=True, padx=12, pady=2)
        _reg_font(ana_txt, PALETTE["small_font"])
        ana_txt.insert("1.0", (row or {}).get("analysis", ""))

        score_var, _ = _row("💯 分值", "score")
        if row: score_var.set(str(row.get("score", 5)))

        def _save():
            content = content_txt.get("1.0", "end").strip()
            if not content or not grade_var.get() or not subject_var.get():
                messagebox.showwarning("缺少信息", "年级/学科/题干必填"); return
            opts_text = opt_txt.get("1.0", "end").strip()
            opts = [l.strip() for l in opts_text.split("\n") if l.strip()] or None
            q = {
                "grade": grade_var.get(), "subject": subject_var.get(),
                "topic": topic_var.get() or "未分类",
                "q_type": type_var.get(),
                "content": content, "options": opts,
                "answer": ans_var.get().strip(),
                "analysis": ana_txt.get("1.0", "end").strip(),
                "score": int(score_var.get() or 5),
            }
            if editing_id:
                update_question(editing_id, q)
            else:
                add_question(q)
            dlg.destroy()
            if on_save: on_save()

        btn_r = tk.Frame(dlg, bg=PALETTE["bg"]); btn_r.pack(pady=8)
        _mk_color_button(btn_r, "💾 保存", PALETTE["mint"], _save, width=12).pack(side=tk.LEFT, padx=6)
        _mk_color_button(btn_r, "🆗 取消", PALETTE["white"], dlg.destroy, width=12).pack(side=tk.LEFT, padx=6)

    def _kb_delete(tree, on_save=None):
        sel = tree.selection()
        if not sel: return
        if not messagebox.askyesno("确认", f"删除 {len(sel)} 道题?"): return
        for sid in sel:
            delete_question(int(sid))
        if on_save: on_save()

    def _kb_import_json(on_done=None):
        if not HAS_EXAM_DB: return
        path = filedialog.askopenfilename(title="选择 JSON 文件",
                                          filetypes=[("JSON", "*.json")])
        if not path: return
        try:
            n = import_from_json_file(path)
            messagebox.showinfo("导入成功", f"✅ 导入了 {n} 道题!")
            if on_done: on_done()
        except Exception as e:
            messagebox.showerror("导入失败", str(e))

    def _kb_import_word(on_done=None):
        if not HAS_EXAM_DB: return
        path = filedialog.askopenfilename(title="选择 Word 文件",
                                          filetypes=[("Word", "*.docx *.doc")])
        if not path: return
        try:
            n = import_from_word_file(path)
            messagebox.showinfo("导入成功", f"✅ 从 Word 导入了 {n} 道题!")
            if on_done: on_done()
        except Exception as e:
            messagebox.showerror("导入失败", str(e))

    def _kb_scan_folder(on_done=None):
        if not HAS_EXAM_DB: return
        folder = os.path.join(os.path.expanduser("~/.tutor_helper"), "import_folder")
        if not os.path.isdir(folder):
            os.makedirs(folder, exist_ok=True)
        files = scan_import_folder()
        if not files:
            messagebox.showinfo("📂 导入文件夹",
                                f"还没有可导入的文件~\n\n"
                                f"请把 .json / .docx 文件拷贝到:\n📁 {folder}\n\n"
                                f"JSON 格式示例:\n"
                                f'[{{"grade":"四下","subject":"数学","topic":"运算定律","q_type":"fill",'
                                f'"content":"计算: 125×32=?","answer":"4000","score":5}}]')
            os.system(f'open "{folder}"')
            return
        total, errs = do_import_folder()
        msg = f"✅ 成功导入 {total} 道题!\n"
        if errs:
            msg += f"\n⚠️ {len(errs)} 个文件有错误:\n" + "\n".join(errs[:5])
        messagebox.showinfo("扫描完成", msg)
        if on_done: on_done()

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
