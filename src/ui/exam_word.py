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
    import subprocess
    try:
        subprocess.Popen(["open", "-a", "Microsoft Word", path],
                         stderr=subprocess.DEVNULL)
    except Exception:
        pass


# ═══════════════════════════════════════════════
# 📊 AI 批改综合分析报告 Word 导出
# ═══════════════════════════════════════════════

def generate_analysis_report(ai_result: Dict, grade_hint="", subject_hint="",
                             output_dir: Optional[str] = None,
                             options: Optional[Dict] = None) -> str:
    """
    📊 生成 AI 批改综合分析报告 Word 文档
    返回输出文件路径

    options 排版选项:
      {
        "font_size": 10-14,        # 字号
        "include_correct": True,   # 是否显示答对的题
        "include_wrong_detail": True, # 是否详细展开错题
        "compact": False,          # 紧凑模式 (减少空行)
        "color_output": True,      # 彩色输出
      }
    """
    if not HAS_DOCX:
        raise RuntimeError("需要安装 python-docx: pip install python-docx")

    opts = options or {}
    font_size = opts.get("font_size", 11)
    include_correct = opts.get("include_correct", True)
    include_wrong_detail = opts.get("include_wrong_detail", True)
    compact = opts.get("compact", False)
    color_output = opts.get("color_output", True)

    out_dir = output_dir or os.path.join(os.path.expanduser("~/.tutor_helper"), "print_output")
    os.makedirs(out_dir, exist_ok=True)

    doc = Document()
    _add_cn_font(doc)

    # A4
    section = doc.sections[0]
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.left_margin = Cm(2.2)
    section.right_margin = Cm(2.2)
    section.top_margin = Cm(1.8)
    section.bottom_margin = Cm(1.8)

    pq = ai_result.get("per_question", [])
    total = ai_result.get("total_score", 0)
    max_t = ai_result.get("max_total", 0) or 1
    rate = ai_result.get("accuracy_rate", 0)
    weak = ai_result.get("weak_topics", [])
    summary = ai_result.get("teacher_summary", "")
    suggestion = ai_result.get("next_step_suggestion", "")
    correct_cnt = sum(1 for p in pq if p.get("correct"))
    wrong_cnt = len(pq) - correct_cnt

    # ═══ 封面区 ═══
    title_p = doc.add_paragraph()
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title_p.add_run("📊 AI 智能批改分析报告")
    _set_run_cn(run, 24, bold=True, color=(99, 102, 241) if color_output else None)

    sub_p = doc.add_paragraph()
    sub_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub_text = f"{grade_hint} {subject_hint}".strip()
    if sub_text:
        run = sub_p.add_run(sub_text + "   ")
        _set_run_cn(run, 12, color=(100, 100, 100))
    run = sub_p.add_run(f"📅 {datetime.now().strftime('%Y年%m月%d日 %H:%M')}")
    _set_run_cn(run, 12, color=(150, 150, 150))

    # ── 分数卡 (表格) ──
    doc.add_paragraph()
    score_table = doc.add_table(rows=1, cols=4)
    score_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell_w = [Cm(4.0), Cm(4.5), Cm(4.5), Cm(4.0)]
    score_cells = [
        ("💯 总分", f"{total} / {max_t}", (37, 199, 104) if rate >= 80 else (245, 158, 11) if rate >= 60 else (239, 68, 68)),
        ("📊 正确率", f"{rate}%", (99, 102, 241)),
        ("✅ 答对", f"{correct_cnt} 题", (16, 185, 129)),
        ("❌ 答错", f"{wrong_cnt} 题", (239, 68, 68)),
    ]
    for i, (label, val, col) in enumerate(score_cells):
        cell = score_table.rows[0].cells[i]
        cell.width = cell_w[i]
        # 背景色
        shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="F3F4F6"/>')
        cell._tc.get_or_add_tcPr().append(shading)
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(label)
        _set_run_cn(run, 10, color=(100, 100, 100))
        p2 = doc.add_paragraph() if i == 0 else cell.add_paragraph()
        p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run2 = p2.add_run(val)
        _set_run_cn(run2, 18, bold=True, color=col if color_output else None)

    doc.add_paragraph()

    # ═══ 一、题目逐题分析 ═══
    _add_heading(doc, "一、📖 逐题分析", level=1)

    for idx, p in enumerate(pq, 1):
        correct = p.get("correct", False)
        if isinstance(correct, bool):
            emoji = "✅" if correct else "❌"
        else:
            emoji = "⚠️"

        # 答对的题可选跳过 (只列题号)
        if correct and not include_correct:
            continue

        # 题号标题行
        h = doc.add_paragraph()
        score = p.get("score", 0); max_s = p.get("max_score", 0)
        topic = p.get("knowledge_point", "")
        run = h.add_run(f"{emoji} 第{p.get('no', idx)}题")
        _set_run_cn(run, font_size + 1, bold=True,
                     color=(37, 199, 104) if correct and color_output else (239, 68, 68) if color_output else None)
        run = h.add_run(f"  得分 {score}/{max_s}")
        _set_run_cn(run, font_size,
                     color=(37, 199, 104) if correct and color_output else (239, 68, 68) if color_output else None)
        if topic:
            run = h.add_run(f"   📚 {topic}")
            _set_run_cn(run, font_size - 1, color=(150, 150, 150))

        # 题目
        content = p.get("content", "(题目未识别)")
        cp = doc.add_paragraph()
        run = cp.add_run("📖 题干: ")
        _set_run_cn(run, font_size - 1, bold=True)
        run = cp.add_run(content)
        _set_run_cn(run, font_size)

        # 三列对比 (学生 vs 标准)
        stu = p.get("student_answer") or p.get("user_answer") or "(未识别)"
        std = p.get("std_answer") or "(AI 未给出)"

        ans_table = doc.add_table(rows=1, cols=2)
        ans_table.alignment = WD_TABLE_ALIGNMENT.LEFT
        ans_table.columns[0].width = Cm(8.5)
        ans_table.columns[1].width = Cm(8.5)

        # 学生答案
        c0 = ans_table.rows[0].cells[0]
        if color_output:
            c0._tc.get_or_add_tcPr().append(parse_xml(f'<w:shd {nsdecls("w")} w:fill="DBEAFE"/>'))
        p0 = c0.paragraphs[0]
        run = p0.add_run("✍️ 学生答案")
        _set_run_cn(run, font_size - 1, bold=True, color=(29, 78, 216) if color_output else None)
        p0 = c0.add_paragraph()
        run = p0.add_run(str(stu))
        _set_run_cn(run, font_size, bold=True)

        # 标准答案
        c1 = ans_table.rows[0].cells[1]
        if color_output:
            c1._tc.get_or_add_tcPr().append(parse_xml(f'<w:shd {nsdecls("w")} w:fill="D1FAE5"/>'))
        p1 = c1.paragraphs[0]
        run = p1.add_run("✅ 标准答案")
        _set_run_cn(run, font_size - 1, bold=True, color=(5, 150, 105) if color_output else None)
        p1 = c1.add_paragraph()
        run = p1.add_run(str(std))
        _set_run_cn(run, font_size, bold=True, color=(5, 150, 105) if color_output else None)

        # 错题详情
        if not correct and include_wrong_detail:
            # 错因
            if p.get("why_wrong"):
                wp = doc.add_paragraph()
                run = wp.add_run("🧐 错因分析: ")
                _set_run_cn(run, font_size - 1, bold=True, color=(185, 28, 28) if color_output else None)
                run = wp.add_run(p["why_wrong"])
                _set_run_cn(run, font_size, color=(185, 28, 28) if color_output else None)

            # 易踩陷阱
            if p.get("easy_trap"):
                tp = doc.add_paragraph()
                run = tp.add_run("⚠️ 易踩陷阱: ")
                _set_run_cn(run, font_size - 1, bold=True, color=(180, 83, 9) if color_output else None)
                run = tp.add_run(p["easy_trap"])
                _set_run_cn(run, font_size, color=(180, 83, 9) if color_output else None)

        # 名师点拨
        if p.get("teacher_tip"):
            tip_p = doc.add_paragraph()
            run = tip_p.add_run("👨‍🏫 名师点拨: ")
            _set_run_cn(run, font_size - 1, bold=True, color=(124, 58, 237) if color_output else None)
            run = tip_p.add_run(p["teacher_tip"])
            _set_run_cn(run, font_size)

        if not compact:
            doc.add_paragraph()

    # ═══ 二、薄弱知识点分析 ═══
    doc.add_page_break()
    _add_heading(doc, "二、🎯 薄弱知识点分析", level=1)

    # 统计错题知识点
    topic_wrong_count = {}
    for p in pq:
        if not p.get("correct"):
            tp = p.get("knowledge_point") or "其他"
            topic_wrong_count[tp] = topic_wrong_count.get(tp, 0) + 1

    if topic_wrong_count:
        rank_p = doc.add_paragraph()
        run = rank_p.add_run("📌 错题知识点排行:")
        _set_run_cn(run, font_size, bold=True)
        doc.add_paragraph()

        # 表格显示
        weak_table = doc.add_table(rows=1 + len(topic_wrong_count), cols=3)
        weak_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        for i, h in enumerate(["排名", "知识点", "错题数"]):
            cell = weak_table.rows[0].cells[i]
            cell.width = Cm(2) if i == 0 else Cm(8) if i == 1 else Cm(3)
            cell._tc.get_or_add_tcPr().append(parse_xml(f'<w:shd {nsdecls("w")} w:fill="FEE2E2"/>'))
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run(h)
            _set_run_cn(run, font_size, bold=True, color=(185, 28, 28))

        sorted_topics = sorted(topic_wrong_count.items(), key=lambda x: -x[1])
        for row_idx, (tp, cnt) in enumerate(sorted_topics, 1):
            row = weak_table.rows[row_idx]
            row.cells[0].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = row.cells[0].paragraphs[0].add_run(f"#{row_idx}")
            _set_run_cn(run, font_size, bold=True,
                         color=(239, 68, 68) if row_idx <= 3 else None)
            row.cells[1].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.LEFT
            run = row.cells[1].paragraphs[0].add_run(tp)
            _set_run_cn(run, font_size)
            row.cells[2].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = row.cells[2].paragraphs[0].add_run(f"{cnt} 题")
            _set_run_cn(run, font_size, bold=True,
                         color=(239, 68, 68) if cnt >= 2 else None)
    elif weak:
        for w in weak:
            p = doc.add_paragraph()
            run = p.add_run(f"• {w}")
            _set_run_cn(run, font_size, color=(239, 68, 68))
    else:
        p = doc.add_paragraph()
        run = p.add_run("🎉 暂未发现明显薄弱知识点, 继续保持!")
        _set_run_cn(run, font_size, color=(5, 150, 105))

    # ═══ 三、老师总评 & 下一步建议 ═══
    _add_heading(doc, "三、📝 老师总评 & 下一步建议", level=1)

    if summary:
        _add_heading(doc, "👨‍🏫 老师总评", level=2)
        sp = doc.add_paragraph()
        run = sp.add_run(summary)
        _set_run_cn(run, font_size + 1)

    if suggestion:
        _add_heading(doc, "🚀 下一步建议", level=2)
        sg = doc.add_paragraph()
        run = sg.add_run(suggestion)
        _set_run_cn(run, font_size + 1)

    # 页脚
    doc.add_paragraph()
    foot = doc.add_paragraph()
    foot.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = foot.add_run("— 本报告由 家教辅导小助手 AI 自动生成 —")
    _set_run_cn(run, 10, color=(180, 180, 180))

    # 保存
    fname = f"批改分析报告_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
    out_path = os.path.join(out_dir, fname)
    doc.save(out_path)
    return out_path


# ═══════════════════════════════════════════════
# 📅 批改历史记录管理 (自动保存 + 列表 + 回看)
# ═══════════════════════════════════════════════

HISTORY_DIR = os.path.join(os.path.expanduser("~/.tutor_helper"), "grading_history")


def _ensure_history_dir():
    os.makedirs(HISTORY_DIR, exist_ok=True)


def save_grading_record(ai_result: Dict, image_paths: List[str],
                        grade_hint="", subject_hint="",
                        style_name="鼓励风格",
                        exam_meta: Optional[Dict] = None) -> str:
    """
    💾 保存一次批改结果 + 图片副本为历史记录
    返回保存路径 (一个 .json)

    目录结构:
      ~/.tutor_helper/grading_history/
        ├── 20261107_213318_四年级数学/
        │   ├── record.json          ← 元数据 + AI 批改结果
        │   ├── images/              ← 图片副本
        │   │   ├── 01.jpg
        │   │   └── 02.jpg
        │   └── report.docx          ← 如果生成过报告
        └── ...
    """
    _ensure_history_dir()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder_name = f"{ts}_{grade_hint}{subject_hint}".strip("_")
    folder_path = os.path.join(HISTORY_DIR, folder_name)
    os.makedirs(os.path.join(folder_path, "images"), exist_ok=True)

    # 1. 复制图片到 images/
    saved_images = []
    for i, src in enumerate(image_paths or []):
        if not os.path.exists(src):
            continue
        ext = os.path.splitext(src)[1].lower() or ".jpg"
        dst = os.path.join(folder_path, "images", f"{i+1:02d}{ext}")
        try:
            import shutil
            shutil.copy2(src, dst)
            saved_images.append(dst)
        except Exception:
            saved_images.append(src)  # 复制失败就记原路径

    # 2. 保存 record.json
    record = {
        "id": folder_name,
        "timestamp": ts,
        "saved_at": datetime.now().isoformat(),
        "grade_hint": grade_hint,
        "subject_hint": subject_hint,
        "style_name": style_name,
        "exam_meta": exam_meta or {},
        "images": saved_images,
        "ai_result": ai_result,  # 完整 AI 返回 (含 per_question)
        "report_path": None,  # 生成 Word 报告时填入
    }

    json_path = os.path.join(folder_path, "record.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)

    return json_path


def list_grading_records() -> List[Dict]:
    """
    📋 列出所有历史批改记录 (倒序, 新→旧)
    返回简化列表 (不含完整 ai_result)
    """
    _ensure_history_dir()
    records = []
    for folder in sorted(os.listdir(HISTORY_DIR), reverse=True):
        fpath = os.path.join(HISTORY_DIR, folder, "record.json")
        if not os.path.exists(fpath):
            continue
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                r = json.load(f)
            ai = r.get("ai_result", {})
            records.append({
                "id": r.get("id", folder),
                "timestamp": r.get("saved_at", ""),
                "ts_short": folder.split("_")[0] if "_" in folder else folder,
                "grade": r.get("grade_hint", ""),
                "subject": r.get("subject_hint", ""),
                "style": r.get("style_name", ""),
                "total_score": ai.get("total_score", 0),
                "max_total": ai.get("max_total", 0),
                "accuracy_rate": ai.get("accuracy_rate", 0),
                "num_questions": len(ai.get("per_question", [])),
                "num_images": len(r.get("images", [])),
                "report_path": r.get("report_path"),
                "folder": os.path.join(HISTORY_DIR, folder),
                "json_path": fpath,
            })
        except Exception:
            continue
    return records


def load_grading_record(json_path: str) -> Optional[Dict]:
    """📂 加载一条历史记录 (完整)"""
    if not os.path.exists(json_path):
        return None
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def delete_grading_record(json_path: str) -> bool:
    """🗑️ 删除一条历史记录 (连同整个文件夹)"""
    if not os.path.exists(json_path):
        return False
    try:
        import shutil
        folder = os.path.dirname(json_path)
        shutil.rmtree(folder)
        return True
    except Exception:
        return False


def save_report_to_record(json_path: str, report_path: str):
    """记录里关联生成的 Word 报告路径"""
    if not os.path.exists(json_path):
        return
    with open(json_path, "r", encoding="utf-8") as f:
        r = json.load(f)
    r["report_path"] = report_path
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False, indent=2)
