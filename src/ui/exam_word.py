# -*- coding: utf-8 -*-
"""📝 Word 试卷导出 (python-docx)
生成可直接打印的中文试卷, 支持:
  - 标准试卷格式 (标题/考试信息/答题区)
  - 题干+选项排版 (选择题 ABCD 对齐)
  - 答案单独成页 (家长用)
  - 解析/易错点提示
"""

import os
import json
from datetime import datetime
from typing import List, Dict, Optional

try:
    from docx import Document
    from docx.shared import Pt, Cm, Inches, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.oxml.ns import qn, nsdecls
    from docx.oxml import parse_xml
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False


# 中文字体 (macOS 可用)
_FONT_CN = "微软雅黑"   # Word 里显示好, macOS TextEdit 也能渲染
_FONT_EN = "Arial"


def _set_run_cn(run, font_size=12, bold=False, color=None):
    """设置 run 的中文字体"""
    run.font.name = _FONT_EN
    run._element.rPr.rFonts.set(qn("w:eastAsia"), _FONT_CN)
    run.font.size = Pt(font_size)
    run.font.bold = bold
    if color:
        run.font.color.rgb = RGBColor(*color)


def _add_cn_font(doc):
    """给 document 默认样式注入中文字体"""
    style = doc.styles["Normal"]
    style.font.name = _FONT_EN
    style.font.size = Pt(12)
    style.element.rPr.rFonts.set(qn("w:eastAsia"), _FONT_CN)


def _add_heading(doc, text, level=1):
    h = doc.add_heading(text, level=level)
    for run in h.runs:
        run.font.name = _FONT_EN
        run._element.rPr.rFonts.set(qn("w:eastAsia"), _FONT_CN)
    return h


# ═══════════════════════════════════════════════
# 📄 生成试卷文档 (学生版)
# ═══════════════════════════════════════════════

def generate_exam_word(questions: List[Dict], meta: Dict,
                        output_dir: str, include_answer_page=False) -> str:
    """生成 Word 试卷, 返回输出文件路径"""
    if not HAS_DOCX:
        raise RuntimeError("需要安装 python-docx: pip install python-docx")
    os.makedirs(output_dir, exist_ok=True)

    doc = Document()
    _add_cn_font(doc)

    # 🖨️ A4 纸张 + 页边距 (解决国内打印机纸张不匹配!)
    section = doc.sections[0]
    section.page_width = Cm(21.0)    # A4 宽 210mm
    section.page_height = Cm(29.7)   # A4 高 297mm
    section.left_margin = Cm(2.5)
    section.right_margin = Cm(2.5)
    section.top_margin = Cm(2.0)
    section.bottom_margin = Cm(2.0)

    # ── 标题 ──
    grade = meta.get("grade", "")
    subject = meta.get("subject", "")
    total_score = meta.get("total_score", sum(q.get("score", 5) for q in questions))
    time_limit = meta.get("time_limit", 30)
    topic = meta.get("topic", "")

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run(f"{grade} {subject} 练习卷")
    _set_run_cn(run, 22, bold=True)

    # ── 考试信息 ──
    info = doc.add_paragraph()
    info.alignment = WD_ALIGN_PARAGRAPH.CENTER
    info_text = f"⏰ 考试时间: {time_limit} 分钟    💯 满分: {total_score} 分"
    if topic and topic != "全部":
        info_text += f"    📚 范围: {topic}"
    run = info.add_run(info_text)
    _set_run_cn(run, 12)

    line = doc.add_paragraph()
    line.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = line.add_run("—" * 30)
    _set_run_cn(run, 10, color=(200, 200, 200))

    # ── 考生信息表 ──
    table = doc.add_table(rows=1, cols=4)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    headers = ["姓名:", "班级:", "学号:", "得分:"]
    widths = [Cm(3.5), Cm(3.5), Cm(3.5), Cm(3.5)]
    for i, h in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.width = widths[i]
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        run = p.add_run(h)
        _set_run_cn(run, 12, bold=True)
        # 底部横线
        cell.text = ""
        run = p.add_run("_" * 15)
        _set_run_cn(run, 12, color=(150, 150, 150))
    doc.add_paragraph()

    # ── 题目 ──
    for idx, q in enumerate(questions, 1):
        # 题干行
        p = doc.add_paragraph()
        run = p.add_run(f"【第 {idx} 题 · {q.get('score', 5)} 分】")
        _set_run_cn(run, 12, bold=True, color=(99, 102, 241))  # 紫色标注
        if q.get("topic"):
            run = p.add_run(f"  ({q['topic']})")
            _set_run_cn(run, 10, color=(150, 150, 150))

        # 题干内容 (可能多行)
        content = q.get("content", q.get("q", ""))
        content_parts = content.split("\n")
        for i, part in enumerate(content_parts):
            if i == 0:
                run = p.add_run(f"  {part}")
            else:
                p2 = doc.add_paragraph()
                run = p2.add_run(f"  {part}")
            _set_run_cn(run, 12)

        # 选项 (选择题)
        if q.get("options") and q.get("q_type") == "choice":
            for j, opt in enumerate(q["options"]):
                op = doc.add_paragraph()
                run = op.add_run(f"    {chr(65+j)}. {opt}")
                _set_run_cn(run, 12)

        # 答题区
        if q.get("q_type") == "fill":
            ap = doc.add_paragraph()
            run = ap.add_run("  答题区: " + "____" * 8)
            _set_run_cn(run, 11, color=(180, 180, 180))

        doc.add_paragraph()

    # ── 页脚日期 ──
    footer_p = doc.add_paragraph()
    footer_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = footer_p.add_run(f"📅 {datetime.now().strftime('%Y年%m月%d日')}")
    _set_run_cn(run, 10, color=(180, 180, 180))

    # ── 答案页 ──
    if include_answer_page:
        doc.add_page_break()
        ans_title = doc.add_paragraph()
        ans_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = ans_title.add_run(f"{grade} {subject} 答案解析 (家长用)")
        _set_run_cn(run, 18, bold=True, color=(220, 38, 38))

        ans_line = doc.add_paragraph()
        ans_line.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = ans_line.add_run("—" * 30)
        _set_run_cn(run, 10, color=(200, 200, 200))

        for idx, q in enumerate(questions, 1):
            p = doc.add_paragraph()
            run = p.add_run(f"第 {idx} 题: ")
            _set_run_cn(run, 12, bold=True)

            ans = q.get("answer", "")
            if q.get("options") and q.get("q_type") == "choice":
                try:
                    ans = q["options"][q["answer"]]
                    ans = f"{chr(65+q['answer'])}. {ans}"
                except (IndexError, TypeError):
                    pass
            run = p.add_run(f"✅ {ans}")
            _set_run_cn(run, 12, color=(37, 199, 104))

            # 解析
            analysis = q.get("analysis", "") or q.get("tip", "")
            if analysis:
                p2 = doc.add_paragraph()
                run = p2.add_run(f"  💡 {analysis}")
                _set_run_cn(run, 11, color=(100, 100, 100))

    # 保存
    fname = f"{grade}_{subject}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
    out_path = os.path.join(output_dir, fname)
    doc.save(out_path)
    return out_path


def save_exam_docx(questions: List[Dict], meta: Dict,
                   output_dir: Optional[str] = None) -> str:
    """便捷入口: 默认保存到 ~/.tutor_helper/print_output"""
    out_dir = output_dir or os.path.join(os.path.expanduser("~/.tutor_helper"), "print_output")
    return generate_exam_word(questions, meta, out_dir, include_answer_page=True)


# ═══════════════════════════════════════════════
# 🖨️ 打开 Word / 调用系统打印
# ═══════════════════════════════════════════════

def open_word_for_print(path: str):
    """macOS: 用 Word 或 TextEdit 打开, 方便直接打印"""
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    os.system(f'open "{path}"')
    # 尝试直接唤起 Word (如果装了)
    import subprocess
    try:
        subprocess.Popen(["open", "-a", "Microsoft Word", path],
                         stderr=subprocess.DEVNULL)
    except Exception:
        pass
