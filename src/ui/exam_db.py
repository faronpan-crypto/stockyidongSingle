# -*- coding: utf-8 -*-
"""📚 智能题库 SQLite 数据库层
数据表:
  questions    — 试题表 (题干/选项/答案/知识点/难度/来源)
  knowledge    — 知识点表 (标签树)
  exams        — 试卷表 (组卷记录)
  exam_questions — 试卷-试题关联表
"""

import sqlite3
import os
import json
import re
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple

DB_DIR = os.path.expanduser("~/.tutor_helper")
DB_PATH = os.path.join(DB_DIR, "question_bank.db")
IMPORT_DIR = os.path.join(DB_DIR, "import_folder")  # 用户可拷贝文件到此


def _conn():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """初始化数据库表结构 + 导入内置题库"""
    os.makedirs(IMPORT_DIR, exist_ok=True)
    conn = _conn()
    c = conn.cursor()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS questions (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        grade       TEXT NOT NULL,              -- 年级: 三上/三下/四上/四下/五上/五下
        subject     TEXT NOT NULL,              -- 学科: 语文/数学/英语/科学
        topic       TEXT NOT NULL,              -- 知识点标签 (如: 小数乘法)
        q_type      TEXT NOT NULL DEFAULT 'fill', -- fill/choice/judge
        content     TEXT NOT NULL,              -- 题干
        options     TEXT,                       -- 选项 JSON (choice题)
        answer      TEXT NOT NULL,              -- 正确答案
        analysis    TEXT,                       -- 解析/易错点提示
        score       INTEGER DEFAULT 5,
        difficulty  INTEGER DEFAULT 3,          -- 1-5
        source      TEXT,                       -- 来源: builtin/import/manual
        created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at  TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS knowledge (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        grade       TEXT NOT NULL,
        subject     TEXT NOT NULL,
        name        TEXT NOT NULL,              -- 知识点名
        parent      TEXT,                       -- 父知识点
        UNIQUE(grade, subject, name)
    );

    CREATE TABLE IF NOT EXISTS exams (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT NOT NULL,
        grade       TEXT NOT NULL,
        subject     TEXT NOT NULL,
        topic       TEXT,
        time_limit  INTEGER DEFAULT 30,
        total_score INTEGER DEFAULT 100,
        created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
        created_by  TEXT DEFAULT 'system'
    );

    CREATE TABLE IF NOT EXISTS exam_questions (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        exam_id     INTEGER NOT NULL,
        question_id INTEGER NOT NULL,
        seq         INTEGER NOT NULL,
        FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE,
        FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_q_grade_subj ON questions(grade, subject);
    CREATE INDEX IF NOT EXISTS idx_q_topic       ON questions(topic);
    CREATE INDEX IF NOT EXISTS idx_q_type       ON questions(q_type);
    CREATE INDEX IF NOT EXISTS idx_knowledge     ON knowledge(grade, subject);
    """)
    conn.commit()

    # 检查是否需要导入内置题库
    c.execute("SELECT COUNT(*) FROM questions WHERE source='builtin'")
    if c.fetchone()[0] == 0:
        _import_builtin_bank(conn)
    conn.close()


def _import_builtin_bank(conn: sqlite3.Connection):
    """把 tutor_helper.py 里的 EXAM_BANK 导入数据库"""
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        from ui.tutor_helper import EXAM_BANK
    except ImportError:
        return

    c = conn.cursor()
    for grade, subjects in EXAM_BANK.items():
        for subject, topics in subjects.items():
            for topic, qs in topics.items():
                # 写入知识点
                c.execute("INSERT OR IGNORE INTO knowledge(grade,subject,name) VALUES(?,?,?)",
                          (grade, subject, topic))
                for q in qs:
                    opts = json.dumps(q.get("options"), ensure_ascii=False) if q.get("options") else None
                    c.execute("""INSERT INTO questions
                        (grade,subject,topic,q_type,content,options,answer,analysis,score,difficulty,source)
                        VALUES(?,?,?,?,?,?,?,?,?,?, 'builtin')""",
                        (grade, subject, topic, q["type"], q["q"], opts,
                         q["answer"], q.get("tip", ""), q.get("score", 5), 3))
    conn.commit()


# ═══════════════════════════════════════════════
# 🔍 查询接口
# ═══════════════════════════════════════════════

def get_questions(grade=None, subject=None, topic=None, q_type=None,
                  keyword=None, limit=500, offset=0) -> List[Dict]:
    """多条件查询试题"""
    sql = "SELECT * FROM questions WHERE 1=1"
    params = []
    if grade:
        sql += " AND grade=?"; params.append(grade)
    if subject:
        sql += " AND subject=?"; params.append(subject)
    if topic:
        sql += " AND topic=?"; params.append(topic)
    if q_type:
        sql += " AND q_type=?"; params.append(q_type)
    if keyword:
        sql += " AND (content LIKE ? OR answer LIKE ? OR topic LIKE ?)"
        kw = f"%{keyword}%"
        params.extend([kw, kw, kw])
    sql += " ORDER BY grade, subject, topic, id LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    conn = _conn()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def count_questions(grade=None, subject=None, topic=None) -> int:
    sql = "SELECT COUNT(*) FROM questions WHERE 1=1"
    params = []
    if grade: sql += " AND grade=?"; params.append(grade)
    if subject: sql += " AND subject=?"; params.append(subject)
    if topic: sql += " AND topic=?"; params.append(topic)
    conn = _conn()
    n = conn.execute(sql, params).fetchone()[0]
    conn.close()
    return n


def get_all_grades() -> List[str]:
    conn = _conn()
    rows = conn.execute("SELECT DISTINCT grade FROM questions ORDER BY grade").fetchall()
    conn.close()
    return [r[0] for r in rows]


def get_all_subjects() -> List[str]:
    conn = _conn()
    rows = conn.execute("SELECT DISTINCT subject FROM questions ORDER BY subject").fetchall()
    conn.close()
    return [r[0] for r in rows]


def get_topics(grade=None, subject=None) -> List[str]:
    sql = "SELECT DISTINCT topic FROM questions WHERE 1=1"
    params = []
    if grade: sql += " AND grade=?"; params.append(grade)
    if subject: sql += " AND subject=?"; params.append(subject)
    sql += " ORDER BY topic"
    conn = _conn()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [r[0] for r in rows]


def get_stats() -> Dict:
    conn = _conn()
    stats = {
        "total_questions": conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0],
        "total_knowledge": conn.execute("SELECT COUNT(*) FROM knowledge").fetchone()[0],
        "total_exams": conn.execute("SELECT COUNT(*) FROM exams").fetchone()[0],
        "by_source": dict(conn.execute("SELECT source, COUNT(*) FROM questions GROUP BY source").fetchall()),
        "by_subject": dict(conn.execute("SELECT subject, COUNT(*) FROM questions GROUP BY subject").fetchall()),
        "by_grade": dict(conn.execute("SELECT grade, COUNT(*) FROM questions GROUP BY grade").fetchall()),
    }
    conn.close()
    return stats


# ═══════════════════════════════════════════════
# ✏️ CRUD 接口
# ═══════════════════════════════════════════════

def add_question(q: Dict) -> int:
    """添加一道题, 返回新 ID"""
    opts = json.dumps(q.get("options"), ensure_ascii=False) if q.get("options") else None
    conn = _conn()
    cur = conn.execute("""INSERT INTO questions
        (grade,subject,topic,q_type,content,options,answer,analysis,score,difficulty,source)
        VALUES(?,?,?,?,?,?,?,?,?,?, 'manual')""",
        (q["grade"], q["subject"], q["topic"], q.get("q_type", "fill"),
         q["content"], opts, q["answer"], q.get("analysis", ""),
         q.get("score", 5), q.get("difficulty", 3)))
    qid = cur.lastrowid
    conn.commit()
    # 同时 upsert knowledge
    conn.execute("INSERT OR IGNORE INTO knowledge(grade,subject,name) VALUES(?,?,?)",
                 (q["grade"], q["subject"], q["topic"]))
    conn.commit()
    conn.close()
    return qid


def update_question(qid: int, q: Dict):
    """更新试题"""
    conn = _conn()
    fields, vals = [], []
    for k in ["grade", "subject", "topic", "q_type", "content", "answer",
              "analysis", "score", "difficulty"]:
        if k in q:
            fields.append(f"{k}=?"); vals.append(q[k])
    if "options" in q:
        fields.append("options=?")
        vals.append(json.dumps(q["options"], ensure_ascii=False) if q["options"] else None)
    fields.append("updated_at=CURRENT_TIMESTAMP")
    vals.append(qid)
    conn.execute(f"UPDATE questions SET {','.join(fields)} WHERE id=?", vals)
    conn.commit()
    conn.close()


def delete_question(qid: int):
    conn = _conn()
    conn.execute("DELETE FROM questions WHERE id=?", (qid,))
    conn.commit()
    conn.close()


def _row_to_dict(row) -> Dict:
    d = dict(row)
    if d.get("options"):
        try: d["options"] = json.loads(d["options"])
        except: d["options"] = None
    return d


# ═══════════════════════════════════════════════
# 🎲 随机组卷
# ═══════════════════════════════════════════════

def _diff_range(difficulty: str) -> Tuple[int, int]:
    """UI 难度代号 → (最低难度, 最高难度)"""
    return {
        "easy":    (1, 2),
        "medium":  (2, 3),
        "hard":    (3, 4),
        "expert":  (4, 5),
        "easy_mix": (1, 3),
        "hard_mix": (2, 5),
        "mixed":   (1, 5),
    }.get(difficulty, (1, 5))


def pick_random_questions(grade: str, subject: str, topics: List[str],
                          num: int, exclude_ids=None,
                          difficulty: str = "mixed") -> List[Dict]:
    """
    🎲 随机组卷 — 支持难度等级
    difficulty: "easy"(1-2) / "medium"(3) / "hard"(4) / "expert"(5) / "mixed"(不限)
    """
    exclude_ids = exclude_ids or []
    conn = _conn()

    real_topics = [t.strip() for t in (topics or []) if t and t != "全部" and t.strip()]

    sql = "SELECT * FROM questions WHERE grade=? AND subject=?"
    params = [grade, subject]

    # ── 难度过滤 ──
    diff_map = {
        "easy":    (1, 2),
        "medium":  (2, 3),
        "hard":    (3, 4),
        "expert":  (4, 5),
    }
    if difficulty in diff_map:
        lo, hi = diff_map[difficulty]
        sql += " AND difficulty BETWEEN ? AND ?"
        params.extend([lo, hi])
    elif difficulty == "easy_mix":   # 简单为主 + 少量中等
        sql += " AND difficulty BETWEEN 1 AND 3"
    elif difficulty == "hard_mix":   # 中等为主 + 少量难
        sql += " AND difficulty BETWEEN 2 AND 5"
    # "mixed" / 其他 → 不限难度

    if real_topics:
        like_clauses = []
        for t in real_topics:
            like_clauses.append("topic LIKE ?")
            params.append(f"%{t}%")
        sql += " AND (" + " OR ".join(like_clauses) + ")"

    if exclude_ids:
        ph = ",".join("?" * len(exclude_ids))
        sql += f" AND id NOT IN ({ph})"
        params.extend(exclude_ids)

    sql += " ORDER BY RANDOM() LIMIT ?"
    params.append(num)
    rows = conn.execute(sql, params).fetchall()

    # 如果按难度筛选后不够，降级重试
    if len(rows) < num and difficulty != "mixed":
        params2 = [grade, subject]
        sql2 = "SELECT * FROM questions WHERE grade=? AND subject=?"
        if real_topics:
            like_clauses = []
            for t in real_topics:
                like_clauses.append("topic LIKE ?")
                params2.append(f"%{t}%")
            sql2 += " AND (" + " OR ".join(like_clauses) + ")"
        sql2 += " ORDER BY RANDOM() LIMIT ?"
        params2.append(num)
        rows = conn.execute(sql2, params2).fetchall()

    conn.close()
    return [_row_to_dict(r) for r in rows]


def save_exam(name: str, grade: str, subject: str, topics: List[str],
              time_limit: int, questions: List[Dict]) -> int:
    """保存组卷记录"""
    total = sum(q.get("score", 5) for q in questions)
    conn = _conn()
    cur = conn.execute("""INSERT INTO exams(name,grade,subject,topic,time_limit,total_score)
        VALUES(?,?,?,?,?,?)""", (name, grade, subject, ",".join(topics), time_limit, total))
    exam_id = cur.lastrowid
    for seq, q in enumerate(questions, 1):
        conn.execute("INSERT INTO exam_questions(exam_id,question_id,seq) VALUES(?,?,?)",
                     (exam_id, q["id"], seq))
    conn.commit()
    conn.close()
    return exam_id


def get_exams() -> List[Dict]:
    conn = _conn()
    rows = conn.execute("SELECT * FROM exams ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_exam(exam_id: int):
    conn = _conn()
    conn.execute("DELETE FROM exams WHERE id=?", (exam_id,))
    conn.execute("DELETE FROM exam_questions WHERE exam_id=?", (exam_id,))
    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════
# 📥 批量导入 (JSON / Word)
# ═══════════════════════════════════════════════

def import_from_json_file(path: str) -> int:
    """从 JSON 文件批量导入题目
    支持两种格式:
    1. 数组: [ {grade, subject, topic, q, type, answer, score, ...}, ... ]
    2. 嵌套: { "grade": { "subject": { "topic": [...] } } }  (和 EXAM_BANK 一样)
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    count = 0

    def _add_one(q, grade=None, subject=None, topic=None):
        nonlocal count
        item = {
            "grade": q.get("grade", grade),
            "subject": q.get("subject", subject),
            "topic": q.get("topic", topic) or q.get("topic_name", "未分类"),
            "q_type": q.get("type", q.get("q_type", "fill")),
            "content": q.get("q", q.get("content", "")),
            "options": q.get("options"),
            "answer": q.get("answer", ""),
            "analysis": q.get("analysis", q.get("tip", "")),
            "score": q.get("score", 5),
        }
        if item["grade"] and item["subject"] and item["content"]:
            add_question(item)
            count += 1

    if isinstance(data, list):
        for q in data:
            _add_one(q)
    elif isinstance(data, dict):
        # 判断是嵌套 EXAM_BANK 格式还是扁平 dict
        first_val = next(iter(data.values()), None)
        if isinstance(first_val, dict):
            for grade, subjects in data.items():
                for subject, topics in subjects.items():
                    for topic, qs in topics.items():
                        for q in qs:
                            _add_one(q, grade, subject, topic)
        else:
            _add_one(data)
    return count


def import_from_word_file(path: str) -> int:
    """从 Word 文档导入 — 支持简单格式识别
    识别规则:
      题干: 以 '1.' '2.' 'Q1:' '第1题' 开头
      选项: A. B. C. D. 开头
      答案: 以 '答案:' '参考答案:' 开头
    """
    try:
        from docx import Document
    except ImportError:
        raise RuntimeError("需要 python-docx: pip install python-docx")

    doc = Document(path)
    lines = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    # 也收集表格
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for line in cell.text.split("\n"):
                    if line.strip():
                        lines.append(line.strip())

    count = 0
    current_q = None
    current_opts = []
    current_ans = None

    def _flush():
        nonlocal current_q, current_opts, current_ans, count
        if current_q:
            grade = _guess_from_context(path, current_q)
            add_question({
                "grade": grade,
                "subject": _guess_subject(path),
                "topic": "从Word导入",
                "q_type": "choice" if current_opts else "fill",
                "content": current_q,
                "options": current_opts if current_opts else None,
                "answer": current_ans or "",
                "analysis": "",
                "score": 5,
            })
            count += 1
        current_q = None
        current_opts = []
        current_ans = None

    q_start = re.compile(r"^(\d+[\.、\)）:：]|Q\d+[:：]|第\d+题[\.、]?)\s*(.*)")
    opt_start = re.compile(r"^([A-D])[\.、\)）:：]\s*(.*)", re.I)
    ans_start = re.compile(r"^(参考答案|答案|Correct Answer|Answer)[:：]\s*(.*)", re.I)

    for line in lines:
        # 检测新题干
        m = q_start.match(line)
        if m:
            _flush()
            current_q = m.group(2) or line
            continue
        # 检测选项
        m = opt_start.match(line)
        if m and current_q:
            letter = m.group(1).upper()
            text = m.group(2)
            idx = ord(letter) - ord("A")
            while len(current_opts) <= idx:
                current_opts.append("")
            current_opts[idx] = text
            continue
        # 检测答案
        m = ans_start.match(line)
        if m and current_q:
            ans_text = m.group(2).strip()
            # 提取选项字母
            letters = re.findall(r"[A-D]", ans_text.upper())
            if letters:
                current_ans = ord(letters[0]) - ord("A")
            else:
                current_ans = ans_text
            continue
        # 如果当前有题干但没遇到选项或答案, 追加到题干
        if current_q and not current_opts and not current_ans:
            # 检查这行是不是答案 (独立一行的纯字母)
            if re.match(r"^[A-D][\.、]?$", line.upper()):
                current_ans = ord(line.upper()[0]) - ord("A")
            else:
                current_q += " " + line

    _flush()
    return count


def _guess_subject(filename: str) -> str:
    lower = filename.lower()
    if any(k in lower for k in ["数学", "math"]): return "数学"
    if any(k in lower for k in ["英语", "english"]): return "英语"
    if any(k in lower for k in ["科学", "science"]): return "科学"
    return "语文"


def _guess_from_context(path: str, content: str) -> str:
    """从文件名和内容猜测年级"""
    fname = os.path.basename(path)
    for g in ["三上", "三下", "四上", "四下", "五上", "五下", "三年级", "四年级", "五年级"]:
        if g in fname:
            return g
    return "四下"


def scan_import_folder() -> List[Dict]:
    """扫描 ~/.tutor_helper/import_folder 目录, 返回可导入文件列表"""
    if not os.path.isdir(IMPORT_DIR):
        return []
    results = []
    for name in sorted(os.listdir(IMPORT_DIR)):
        path = os.path.join(IMPORT_DIR, name)
        if not os.path.isfile(path):
            continue
        size = os.path.getsize(path)
        ext = os.path.splitext(name)[1].lower()
        results.append({
            "name": name, "path": path, "size": size, "ext": ext,
            "can_import": ext in [".json", ".docx", ".doc", ".txt"],
        })
    return results


def do_import_folder() -> Tuple[int, List[str]]:
    """批量导入 import_folder 目录, 返回 (成功数量, 错误信息列表)"""
    files = scan_import_folder()
    total = 0
    errors = []
    for f in files:
        try:
            if f["ext"] == ".json":
                n = import_from_json_file(f["path"])
            elif f["ext"] in [".docx", ".doc"]:
                n = import_from_word_file(f["path"])
            else:
                continue
            total += n
        except Exception as e:
            errors.append(f"{f['name']}: {e}")
    return total, errors
