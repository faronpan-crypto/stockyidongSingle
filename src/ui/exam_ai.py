# -*- coding: utf-8 -*-
"""🤖 AI 试卷评分 + 名师风格解析
复用主程序 ai_config.json 里的 deepseek API key
"""
import json
import os
import ssl
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
