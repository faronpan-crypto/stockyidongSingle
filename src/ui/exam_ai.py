# -*- coding: utf-8 -*-
"""🤖 AI 试卷评分 + 名师风格解析
复用主程序 ai_config.json 里的 deepseek API key
"""
import base64
import json
import os
import re
import ssl
import mimetypes
import urllib.request
import urllib.error
from typing import Dict, List, Optional, Any

# macOS 自签名证书兼容
_SSL_CTX = ssl.create_default_context()
try:
    _SSL_CTX.check_hostname = False
    _SSL_CTX.verify_mode = ssl.CERT_NONE
except Exception:
    pass

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "config", "ai_config.json")


def _get_ai_config() -> Dict:
    """从主程序配置读取 deepseek 参数"""
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH) as f:
                cfg = json.load(f)
            prov = cfg.get("providers", {}).get("deepseek", {})
            return {
                "api_key": prov.get("api_key", ""),
                "base_url": prov.get("base_url", "https://api.deepseek.com/v1"),
                "model": prov.get("model", "deepseek-chat"),
                "timeout": 60,
            }
    except Exception:
        pass
    # Fallback — 从环境变量读 (主程序已 export)
    return {
        "api_key": os.environ.get("DEEPSEEK_API_KEY", ""),
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "timeout": 60,
    }


def call_deepseek(system_prompt: str, user_prompt: str,
                  temperature: float = 0.6, max_tokens: int = 2000) -> str:
    """调用 deepseek-chat，返回文本。失败返回 None"""
    cfg = _get_ai_config()
    if not cfg["api_key"]:
        return None

    url = f"{cfg['base_url'].rstrip('/')}/chat/completions"
    body = {
        "model": cfg["model"],
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {cfg['api_key']}")

    try:
        with urllib.request.urlopen(req, timeout=cfg["timeout"], context=_SSL_CTX) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result["choices"][0]["message"]["content"].strip()
    except urllib.error.HTTPError as e:
        print(f"[AI] HTTP {e.code}: {e.read().decode()[:200]}")
        return None
    except Exception as e:
        print(f"[AI] Error: {e}")
        return None


def _robust_json_extract(text: str) -> Optional[Dict]:
    """
    🛡️ 从 AI 返回中健壮地提取 JSON
    优先级:
    1. ```json ... ``` 代码块
    2. ``` ... ``` 代码块
    3. 首个 { 到末个 } 之间 (花括号匹配)
    4. 正则捕获 "per_question" 存在性后再找
    返回解析后的 dict，失败返回 None
    """
    if not text:
        return None
    text = text.strip()

    # 1. ```json ... ```
    if "```json" in text.lower():
        m = re.search(r"```json\s*\n?(.*?)```", text, re.DOTALL | re.IGNORECASE)
        if m:
            try:
                return json.loads(m.group(1).strip())
            except Exception:
                text = m.group(1).strip()  # 继续 fallback

    # 2. ``` ... ```
    if "```" in text:
        m = re.search(r"```\s*\n?(.*?)```", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1).strip())
            except Exception:
                text = m.group(1).strip()

    # 3. 从首个 { 到末个 }
    open_idx = text.find("{")
    close_idx = text.rfind("}")
    if open_idx >= 0 and close_idx > open_idx:
        candidate = text[open_idx:close_idx + 1]
        try:
            return json.loads(candidate)
        except Exception:
            pass

    # 4. 找第一个包含 "per_question" 的 JSON 对象
    pq_pos = text.find("\"per_question\"")
    if pq_pos >= 0:
        # 往前找 {
        brace_start = text.rfind("{", 0, pq_pos)
        brace_end = text.find("}", pq_pos)
        # 找到匹配的闭合 } — 简单做法: 从 pq_pos 往后找最后一个 }
        last_brace = text.rfind("}")
        if brace_start >= 0 and last_brace > brace_start:
            candidate = text[brace_start:last_brace + 1]
            try:
                return json.loads(candidate)
            except Exception:
                pass

    return None


def _sanitize_ai_result(result: Dict) -> Dict:
    """
    🧼 AI 返回的 JSON 清洗 — 把空字符串、None、缺失值都修成安全类型
    避免 UI 里做算术运算时崩掉
    """
    if not isinstance(result, dict):
        return result

    # 顶层字段
    result["total_score"] = int(result.get("total_score") or 0)
    result["max_total"] = int(result.get("max_total") or 0)
    result["accuracy_rate"] = int(result.get("accuracy_rate") or 0)
    result.setdefault("weak_topics", [])
    result.setdefault("teacher_summary", "")
    result.setdefault("next_step_suggestion", "")

    # 每题
    pq = result.get("per_question", [])
    for p in pq:
        if not isinstance(p, dict):
            continue
        p["no"] = int(p.get("no") or 0)
        # max_score / score 可能是 "" 空字符串
        try:
            p["score"] = int(float(p.get("score") or 0))
        except (ValueError, TypeError):
            p["score"] = 0
        try:
            ms = p.get("max_score")
            if ms in ("", None, 0):
                p["max_score"] = p["score"] if p["score"] > 0 else 5
            else:
                p["max_score"] = int(float(ms))
        except (ValueError, TypeError):
            p["max_score"] = 5
        # correct 可能是字符串
        cor = p.get("correct")
        if isinstance(cor, str):
            p["correct"] = cor.lower() in ("true", "对", "yes")
        elif cor is None:
            p["correct"] = p["score"] > 0
        # 字符串字段确保有值
        for k in ["content", "student_answer", "std_answer",
                  "why_wrong", "knowledge_point", "easy_trap", "teacher_tip", "type"]:
            p.setdefault(k, "")
            if p[k] is None:
                p[k] = ""

    # 重算总分 (防止 AI 算错)
    if pq:
        actual_total = sum(p.get("score", 0) for p in pq)
        actual_max = sum(p.get("max_score", 0) for p in pq)
        result["total_score"] = actual_total
        result["max_total"] = actual_max
        if actual_max > 0:
            result["accuracy_rate"] = round(actual_total / actual_max * 100)

    return result


def _looks_like_refusal(text: str) -> bool:
    """
    检测 AI 是否返回了自然语言拒绝/闲聊而不是 JSON
    典型信号: "没看到", "无法", "请你", "我来帮你" 等
    """
    if not text:
        return True
    lower = text.lower()
    # 已经是 JSON 的肯定不是 refusal
    if text.strip().startswith("{") and text.strip().endswith("}"):
        return False
    signals = [
        "没看到", "未看到", "没有看到", "没收到",
        "无法辨认", "看不清", "无法识别",
        "请你", "请重新", "请上传", "请告诉我",
        "我来帮你", "我会帮你", "我可以帮",
        "暂时无法", "目前还没有",
    ]
    hit = sum(1 for s in signals if s in text)
    # 同时检测 JSON 关键字是否存在
    json_kw = sum(1 for kw in ["per_question", "total_score", "max_total"] if kw in lower)
    return hit >= 2 or (hit >= 1 and json_kw == 0)


def _image_to_base64(image_path: str) -> str:
    """图片文件转 base64 字符串"""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def call_deepseek_vision(system_prompt: str, user_prompt: str,
                          image_paths: List[str],
                          model: str = "deepseek-flash",
                          max_tokens: int = 3000) -> Optional[str]:
    """
    🖼️ DeepSeek 多模态视觉模型
    直接上传图片让 AI 看 — 不需要 OCR!
    """
    cfg = _get_ai_config()
    if not cfg.get("api_key"):
        return None

    url = f"{cfg['base_url'].rstrip('/')}/chat/completions"

    # 构造 content: 先放文本 prompt，再放多张图片
    content = []
    content.append({"type": "text", "text": user_prompt})

    for img_path in image_paths:
        if not os.path.exists(img_path):
            continue
        mime, _ = mimetypes.guess_type(img_path)
        if not mime:
            mime = "image/png"
        b64 = _image_to_base64(img_path)
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{b64}"}
        })

    body = {
        "model": model,   # deepseek-vision
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content},
        ],
        "max_tokens": max_tokens,
    }
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {cfg['api_key']}")

    try:
        with urllib.request.urlopen(req, timeout=cfg["timeout"] * 2, context=_SSL_CTX) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result["choices"][0]["message"]["content"].strip()
    except urllib.error.HTTPError as e:
        body_text = e.read().decode()[:300]
        print(f"[VISION] HTTP {e.code}: {body_text}")
        # 如果 vision 模型不存在，自动降级到 deepseek-chat
        if "model_not_found" in body_text or "invalid" in body_text.lower():
            print("[VISION] deepseek-vision 不可用, 降级到 deepseek-chat (文字模式)")
            return None
        return None
    except Exception as e:
        print(f"[VISION] Error: {e}")
        return None


def grade_exam_from_images(image_paths: List[str],
                           questions: List[Dict],
                           grade: str = "",
                           subject: str = "",
                           style: str = "encourage",
                           use_vision: bool = True) -> Dict:
    """
    📷 直接上传答题纸图片让 AI 批改 (多模态)
    把试卷的标准答案和评分标准告诉 AI，让它看图片里的手写答案打分
    """
    cfg = _get_ai_config()
    if not cfg.get("api_key"):
        return {"error": "未配置 deepseek API key"}

    teacher = TEACHER_STYLES.get(style, TEACHER_STYLES["encourage"])

    # 把题目和标准答案整理成 JSON 给 AI 参考
    qs_json = []
    for i, q in enumerate(questions):
        qs_json.append({
            "no": i + 1,
            "type": q.get("type", "fill"),
            "content": q.get("content", ""),
            "options": q.get("options", []),
            "std_answer": q.get("answer", ""),
            "score": q.get("score", 5),
            "topic": q.get("topic", ""),
        })

    system = f"""{teacher['system']}

现在你需要作为阅卷老师，直接查看学生的答题纸照片并批改。
请逐一比对每道题的"标准答案"和学生在照片上的"手写答案"，给出评分。

**评分规则:**
1. 填空题: 答案完全一致给满分，相似或接近给部分分 (0.5分取整)
2. 选择题: 选对了给满分，选错给0分
3. 注意识别手写体 (包括潦草的字、模糊的数字)
4. 如果看不清，标注"无法辨认"，给0分并建议重拍

**输出格式**: 严格按 JSON 返回，外层用 ```json 包裹
{{
  "per_question": [
    {{
      "no": 1,
      "correct": true/false,
      "score": 5,
      "max_score": 5,
      "user_answer": "识别到的学生答案 (无法辨认则写'???')",
      "why_wrong": "错因分析 (对的写'')",
      "knowledge_point": "关联知识点",
      "easy_trap": "易踩陷阱",
      "teacher_tip": "👨‍🏫 名师一句话"
    }}
  ],
  "total_score": 42,
  "max_total": 50,
  "accuracy_rate": 84,
  "weak_topics": ["知识点1", "知识点2", "知识点3"],
  "teacher_summary": "总体评价 80-150字",
  "next_step_suggestion": "下一步学习建议"
}}"""

    user_prompt = f"""学生是 {grade} {subject} 的学生, 请批改他/她的答题纸。

📋 本次试卷 ({len(qs_json)}题):
{json.dumps(qs_json, ensure_ascii=False, indent=2)}

请查看我上传的 {len(image_paths)} 张答题纸照片, 识别手写答案并逐题评分。
如果一张图有多个题, 请按顺序对应到题号。"""

    result_text = None
    used_fallback = False

    # 优先用多模态 (直接看图) — chat 优先, flash 备选
    if use_vision and image_paths:
        for try_model in ["deepseek-chat", "deepseek-flash"]:
            result_text = call_deepseek_vision(
                system_prompt=system,
                user_prompt=user_prompt,
                image_paths=image_paths,
                model=try_model,
                max_tokens=3500,
            )
            if result_text and not _looks_like_refusal(result_text):
                break
            used_fallback = True
            if result_text and _looks_like_refusal(result_text):
                print(f"[VISION] {try_model} refusal, 换模型")
            else:
                print(f"[VISION] {try_model} None, 换模型")

        # 还是不行 → 降级到纯文字 (假设答案空白)
        if not result_text or _looks_like_refusal(result_text):
            used_fallback = True
            result_text = call_deepseek(
                system_prompt=system,
                user_prompt=user_prompt + "\n\n(注意: 当前是纯文字模式, 请假设学生答案都是空白)",
                temperature=0.5,
                max_tokens=3500,
            )
    else:
        result_text = call_deepseek(system, user_prompt, temperature=0.5, max_tokens=3500)

    if not result_text:
        return {"error": "AI 调用失败 (检查 API key 余额或网络)"}

    # 用健壮提取器
    parsed = _robust_json_extract(result_text)
    if parsed:
        if used_fallback:
            parsed["_note"] = "AI 视觉未能识别图片, 已降级处理"
        return _sanitize_ai_result(parsed)

    # 二次 retry: 让 AI 重新输出纯 JSON, 不允许任何自然语言
    retry_prompt = (
        "你刚才的回复不是纯 JSON 格式, 我无法解析。"
        "请忽略所有闲聊文字, 严格只输出一个 JSON 对象,"
        "用 ```json 和 ``` 包裹, 不要有任何其他文字。"
        f"\n\n你的上一轮回复是: {result_text[:300]}"
    )
    retry_text = call_deepseek(system, retry_prompt, temperature=0.3, max_tokens=3500)
    if retry_text:
        parsed = _robust_json_extract(retry_text)
        if parsed:
            if used_fallback:
                parsed["_note"] = "AI 视觉未能识别图片, 已降级处理"
            return _sanitize_ai_result(parsed)

    # 彻底失败 — 返回原始文本让用户看到
    return {"error": f"AI 返回不是合法 JSON", "raw_text": result_text}


def grade_pure_from_images(image_paths: List[str],
                           grade_hint: str = "",
                           subject_hint: str = "",
                           style: str = "encourage") -> Dict:
    """
    📷📷📷 纯图片批改 — 不依赖出题器试卷
    AI 自己从图片里识别题目、学生手写答案，并给出标准答案 + 评分
    适用于: 直接拍了一张练习册/试卷/作业本照片就想批改
    """
    cfg = _get_ai_config()
    if not cfg.get("api_key"):
        return {"error": "未配置 deepseek API key"}

    teacher = TEACHER_STYLES.get(style, TEACHER_STYLES["encourage"])

    system = f"""{teacher['system']}

# ⛔⛔⛔ 核心原则 — 必须看图片，不能瞎编 ⛔⛔⛔
1. 你**必须**直接读取我上传的答题纸照片中的内容，**严禁编造图片中不存在的题目或答案**
2. 如果图片中的内容你看不清楚，请在 student_answer 里写"???"，绝对不要瞎编
3. 图片已经通过 API 上传给你了，不需要让我重新发

现在开始批改任务:
- 从图片中识别每一道题的**原始题干** (content)，一字不差照抄图片里的
- 识别学生的**手写答案** (student_answer)，包括潦草字、圈选、打钩等所有标记
- 作为老师给出**标准答案** (std_answer)
- 比对打分 (score/max_score)

**JSON 输出格式 (必须严格遵守，每个字段都不能省):**
```json
{{
  "per_question": [
    {{
      "no": 1,
      "content": "图片里真实存在的题干原文，绝对不能编",
      "type": "fill 或 choice 或 calc 或 essay",
      "student_answer": "图片里学生写的答案，看不清就写???",
      "std_answer": "你给出的正确标准答案",
      "correct": true 或 false 或 "partial",
      "score": 5,
      "max_score": 5,
      "why_wrong": "错因，答对了就写空字符串",
      "knowledge_point": "关联知识点",
      "easy_trap": "易踩陷阱",
      "teacher_tip": "名师一句话"
    }}
  ],
  "total_score": 42,
  "max_total": 50,
  "accuracy_rate": 84,
  "weak_topics": ["知识点1", "知识点2"],
  "teacher_summary": "80-150字总体评价",
  "next_step_suggestion": "下一步建议"
}}
```"""

    grade_hint_line = f"(学生大概是 {grade_hint} {subject_hint} 水平)" if (grade_hint or subject_hint) else ""
    user_prompt = f"""我上传了 {len(image_paths)} 张答题纸/练习册照片 {grade_hint_line}。

⚠️ 最后提醒: 图片里有什么就识别什么，不要编口诀、不要编教材知识!
如果图片里只有第8题到第15题，就只返回这几题!

开始批改吧。"""

    # ⚠️ deepseek-flash 现在 vision 不稳定, 直接用 chat, flash 当备选
    result_text = None
    for try_model in ["deepseek-chat", "deepseek-flash"]:
        result_text = call_deepseek_vision(
            system_prompt=system,
            user_prompt=user_prompt,
            image_paths=image_paths,
            model=try_model,
            max_tokens=4000,
        )
        # None 也视为失败, 继续换模型
        if result_text and not _looks_like_refusal(result_text):
            break
        if result_text and _looks_like_refusal(result_text):
            print(f"[PURE_GRADE] {try_model} refusal, 换模型")
        else:
            print(f"[PURE_GRADE] {try_model} 返回 {result_text!r}, 换模型")

    if not result_text:
        return {"error": "AI 调用失败 — 两个模型都没返回结果"}

    # 检测 refusal —— chat retry (flash 已经试过了)
    if result_text and _looks_like_refusal(result_text):
        retry_system = system + "\n\n**再次强调: 图片已经上传到本次对话中了! 你必须自己看图片，不要让我再发一次!**"
        result_text = call_deepseek_vision(
            system_prompt=retry_system,
            user_prompt=user_prompt + "\n\n(请直接看图，不要再让我重新上传!)",
            image_paths=image_paths,
            model="deepseek-chat",
            max_tokens=4000,
        )

    if not result_text:
        return {"error": "AI 调用失败"}

    parsed = _robust_json_extract(result_text)
    if parsed:
        return _sanitize_ai_result(parsed)

    # 文字 retry
    retry_prompt = (
        "你刚才的回复不是纯 JSON 格式。"
        "请忽略所有闲聊文字，严格只输出一个 JSON 对象，"
        "用 ```json 和 ``` 包裹，不要有任何其他文字。"
    )
    retry_text = call_deepseek(system, retry_prompt, temperature=0.3, max_tokens=4000)
    if retry_text:
        parsed = _robust_json_extract(retry_text)
        if parsed:
            return _sanitize_ai_result(parsed)

    return {"error": "AI 返回不是合法 JSON", "raw_text": result_text}


# ═══════════════════════════════════════════════
# 🎓 名师风格 Prompt 库
# ═══════════════════════════════════════════════

TEACHER_STYLES = {
    "strict": {
        "name": "严师风格",
        "emoji": "👔",
        "system": "你是一位严谨、治学认真的中学特级教师。语言犀利、直击要害。"
                  "对错误毫不留情，但会指出根本原因。语气像中考/高考阅卷组长。"
    },
    "encourage": {
        "name": "鼓励风格",
        "emoji": "🌸",
        "system": "你是一位温柔鼓励型老师，擅长发现学生的闪光点。"
                  "先肯定优点，再委婉指出问题，给出具体可操作的改进建议。"
                  "适合小学生和初中生。"
    },
    "mentor": {
        "name": "竞赛名师",
        "emoji": "🏆",
        "system": "你是一位奥赛金牌教练。擅长从命题者角度分析。"
                  "讲解举一反三，给出一题多解思路。适合学有余力的学生。"
    },
    "quick": {
        "name": "一句话点评",
        "emoji": "⚡",
        "system": "你是一位干练的教学组长。只说最核心的结论，用短句，不啰嗦。"
                  "每题1-2句话。"
    },
}


def grade_exam_with_ai(questions: List[Dict],
                       user_answers: List[str],
                       grade: str = "",
                       subject: str = "",
                       style: str = "encourage") -> Dict:
    """
    AI 批量评分 + 名师点评
    questions: [{"content": "题干", "answer": "正确答案", "topic": "知识点", "analysis": "标准解析"}]
    user_answers: ["学生作答文本", ...] (长度与 questions 对应)
    返回 {"total_score": ..., "max_score": ..., "per_question": [...], "teacher_comment": "...", "weak_topics": [...]}
    """
    cfg = _get_ai_config()
    if not cfg.get("api_key"):
        return {"error": "未配置 API key"}

    teacher = TEACHER_STYLES.get(style, TEACHER_STYLES["encourage"])

    # 构造题目 + 学生作答
    qas = []
    for i, q in enumerate(questions):
        ua = user_answers[i] if i < len(user_answers) else "(未作答)"
        qas.append({
            "no": i + 1,
            "topic": q.get("topic", ""),
            "content": q.get("content", ""),
            "std_answer": q.get("answer", ""),
            "std_analysis": q.get("analysis", ""),
            "user_answer": ua,
            "score": q.get("score", 5),
        })

    user_prompt = f"""请作为 {grade or '学生'} {subject or ''} 科目老师，批改以下{len(qas)}道题。

{json.dumps(qas, ensure_ascii=False, indent=2)}

请严格按 JSON 格式返回 (外层用 ```json 包裹):
```json
{{
  "per_question": [
    {{
      "no": 1,
      "correct": true/false,
      "score": 5,          // 本题得分为 0~满分
      "max_score": 5,
      "why_wrong": "...",  // 如果错了，分析错在哪里
      "knowledge_point": "...",  // 关联的知识点名称
      "easy_trap": "...", // 这题容易错在哪里
      "teacher_tip": "👨‍🏫 名师一句话点拨"
    }}
  ],
  "total_score": 42,
  "max_total": 50,
  "accuracy_rate": 84,
  "weak_topics": ["小数乘法", "运算定律"],  // 薄弱知识点TOP3
  "teacher_summary": "老师总体评价一段话 (80-150字)",
  "next_step_suggestion": "下一步应该先补什么，再练什么"
}}
```"""

    result_text = call_deepseek(teacher["system"], user_prompt, temperature=0.5, max_tokens=3000)

    if not result_text:
        return {"error": "AI 调用失败 (检查网络或API key)"}

    # 用健壮提取器
    parsed = _robust_json_extract(result_text)
    if parsed:
        return _sanitize_ai_result(parsed)

    # 二次 retry
    retry_prompt = (
        "你刚才的回复不是纯 JSON 格式, 我无法解析。"
        "请忽略所有闲聊文字, 严格只输出一个 JSON 对象,"
        "用 ```json 和 ``` 包裹, 不要有任何其他文字。"
        f"\n\n你的上一轮回复是: {result_text[:300]}"
    )
    retry_text = call_deepseek(teacher["system"], retry_prompt, temperature=0.3, max_tokens=3000)
    if retry_text:
        parsed = _robust_json_extract(retry_text)
        if parsed:
            return _sanitize_ai_result(parsed)

    return {"error": f"AI 返回不是合法 JSON", "raw_text": result_text}


def generate_knowledge_explanation(topic_name: str, grade: str = "", subject: str = "") -> str:
    """AI 生成某个知识点的讲解"""
    teacher = TEACHER_STYLES["mentor"]
    user_prompt = f"""请给 {grade or ''} {subject or ''} 知识点 "{topic_name}" 讲解。
要求:
1. 用通俗语言解释是什么
2. 核心公式/规律 (如有)
3. 典型例题 1 道 + 详细步骤
4. 容易做错的地方 (2-3个陷阱)
5. 快速记忆口诀/技巧

格式用 Markdown。"""
    return call_deepseek(teacher["system"], user_prompt, temperature=0.7, max_tokens=1500) or "(AI 暂时不可用)"
