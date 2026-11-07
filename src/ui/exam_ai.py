# -*- coding: utf-8 -*-
"""🤖 AI 试卷评分 + 名师风格解析
复用主程序 ai_config.json 里的 deepseek API key
"""
import base64
import json
import os
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
    # Fallback — 硬编码 key (和主程序一致)
    return {
        "api_key": "sk-255db1f6651a465b9e8daac02ebb2b25",
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

    # 优先用多模态 (直接看图)
    if use_vision and image_paths:
        result_text = call_deepseek_vision(
            system_prompt=system,
            user_prompt=user_prompt,
            image_paths=image_paths,
            model="deepseek-flash",
            max_tokens=3500,
        )
        if not result_text:
            # 降级到纯文字模式 (AI 不看图片，需要手动输入答案)
            result_text = call_deepseek(
                system_prompt=system,
                user_prompt=user_prompt + "\n\n(注意: 当前是纯文字模式, 我还需要把学生答案告诉你)",
                temperature=0.5,
                max_tokens=3500,
            )
    else:
        result_text = call_deepseek(system, user_prompt, temperature=0.5, max_tokens=3500)

    if not result_text:
        return {"error": "AI 调用失败 (检查 API key 余额或网络)"}

    # 解析 JSON
    try:
        if "```json" in result_text:
            json_str = result_text.split("```json")[1].split("```")[0].strip()
        elif "```" in result_text:
            json_str = result_text.split("```")[1].split("```")[0].strip()
        else:
            json_str = result_text
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        return {"error": f"AI 返回不是合法 JSON: {e}", "raw_text": result_text}


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

    # 解析 JSON
    try:
        # 提取 ```json ... ``` 块
        if "```json" in result_text:
            json_str = result_text.split("```json")[1].split("```")[0].strip()
        elif "```" in result_text:
            json_str = result_text.split("```")[1].split("```")[0].strip()
        else:
            json_str = result_text

        return json.loads(json_str)
    except json.JSONDecodeError as e:
        # JSON 解析失败，返回原始文本让用户自己看
        return {
            "error": f"AI 返回不是合法 JSON ({e})",
            "raw_text": result_text,
        }


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
