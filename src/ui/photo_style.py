# -*- coding: utf-8 -*-
"""
📸 照片风格化 — 阿里通义万相 API
独立模块, 启动时不加载, 点按钮才 import

功能:
  上传照片 → 选大师风格/艺术介质 → 调 wanx API 生成 → 显示+保存

作者列表 / 介质列表 / prompt 模板都在这里集中管理, 方便扩展
"""

import os as _os
import sys as _sys
import json as _json
import base64 as _b64
import threading as _th
import tkinter as _tk
from tkinter import ttk as _ttk, filedialog as _fd, messagebox as _mb

# ===== 风格库 (改这里就能加新风格) =====

MASTER_STYLES = {
    "无": "",
    "毕加索": "in the style of Pablo Picasso, cubist, bold geometric shapes, fragmented forms",
    "莫奈": "in the style of Claude Monet, impressionist, soft light, broken color, garden landscape",
    "张大千": "in the style of Zhang Daqian, Chinese ink wash painting, splash-ink, traditional landscape",
    "齐白石": "in the style of Qi Baishi, Chinese ink painting, simple strokes, natural charm",
    "梵高": "in the style of Vincent van Gogh, post-impressionist, swirling brushstrokes, vivid colors",
    "八大山人": "in the style of Bada Shanren, minimal Chinese ink, solitary birds, poetic emptiness",
    "浮世绘": "in the style of Ukiyo-e, Japanese woodblock print, flat color blocks, wave patterns",
    "徐悲鸿": "in the style of Xu Beihong, Chinese ink with western perspective, powerful horses",
}

MEDIUM_STYLES = {
    "无": "",
    "水彩": "watercolor painting, transparent washes, paper texture, delicate edges",
    "油画": "oil painting, rich impasto, visible brush strokes, canvas texture",
    "水墨画": "Chinese ink wash painting, rice paper, ink gradients, minimalist",
    "素描": "pencil sketch, hatching lines, graphite shading, white paper background",
    "赛博朋克": "cyberpunk, neon lights, rainy streets, futuristic, purple and cyan",
    "像素画": "pixel art, 16-bit, retro game style, limited color palette",
    "卡通": "cartoon style, clean lines, flat colors, Pixar-like",
    "波普艺术": "pop art, bold primary colors, halftone dots, Warhol style",
    "极简主义": "minimalist, geometric abstraction, negative space, muted tones",
}

# ===== API 配置 =====

# 用户提供的 Key (硬编码, 也可改成读文件)
API_KEY = _os.getenv("WANX_API_KEY", "sk-ws-H.PEMPPHE.d7ri.MEYCIQCFuM8krdWxrTROZSTTv9rcA65njblSKTKnGh1wWQcYgAIhAKNzelp79BXDnxUOE4OwN9z8cBLAlrbmzEIaFHhezq55")

# 同步接口 (wanx2.1 老版, DashScope 通用 endpoint)
API_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/image2image/image-synthesis"


def _img_to_base64(path, max_size=4*1024*1024):
    """图片文件 → base64 data URI, 自动缩放到 <= max_size"""
    import PIL.Image as Image
    import io as _io
    img = Image.open(path)
    w, h = img.size
    # 长边缩到 768, 但短边不得 < 512 (万相模型要求 512-4096)
    long_side = max(w, h)
    short_side = min(w, h)
    target_long = 768
    if long_side > target_long:
        ratio = target_long / long_side
        img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
    # 短边补到 512 (如果被缩得太小)
    w2, h2 = img.size
    short2 = min(w2, h2)
    if short2 < 512:
        ratio = 512 / short2
        img = img.resize((int(w2 * ratio), int(h2 * ratio)), Image.LANCZOS)
    # PNG → base64
    buf = _io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    data = buf.getvalue()
    if len(data) > max_size:
        ratio = (max_size / len(data)) ** 0.7
        img = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.LANCZOS)
        buf = _io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        data = buf.getvalue()
    b64 = _b64.b64encode(data).decode()
    return f"data:image/png;base64,{b64}"


def _call_wanx_image2image(img_path, master_prompt, medium_prompt, strength=0.6):
    """
    调用万相图生图风格化
    model: wanx2.1-i2i-v1 (异步) / wanx-style-transfer
    strength: 风格强度 0-1, 默认 0.6
    """
    import requests

    if master_prompt and medium_prompt:
        style_text = f"{master_prompt}, {medium_prompt}"
    else:
        style_text = master_prompt or medium_prompt or "artistic style"

    base64_img = _img_to_base64(img_path)

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "X-DashScope-Async": "enable",  # 异步
    }

    data = {
        "model": "wanx2.1-imageedit",
        "input": {
            "function": "description_edit",
            "prompt": style_text,
            "base_image_url": base64_img,
        },
        "parameters": {
            "size": "1024*1024",
            "n": 1,
        }
    }

    # Step 1: 创建异步任务
    r = requests.post(API_URL, headers=headers, json=data, timeout=30)
    if r.status_code != 200:
        raise Exception(f"创建任务失败 HTTP {r.status_code}: {r.text[:200]}")

    result = r.json()
    task_id = result.get("output", {}).get("task_id")
    if not task_id:
        raise Exception(f"无 task_id: {_json.dumps(result, ensure_ascii=False)[:200]}")

    # Step 2: 轮询结果
    query_url = f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"
    for i in range(60):  # 最多等 60 * 2 = 120s
        import time
        time.sleep(2)  # ← 从 3s 改 2s, 更快拿到结果
        qr = requests.get(query_url, headers={"Authorization": f"Bearer {API_KEY}"}, timeout=15)
        qj = qr.json()
        status = qj.get("output", {}).get("task_status", "")
        if status == "SUCCEEDED":
            urls = qj["output"].get("results", [])
            if urls:
                return urls[0]["url"]
            raise Exception(f"任务成功但无结果: {qj}")
        elif status in ("FAILED", "UNKNOWN"):
            raise Exception(f"任务失败: {qj.get('message', qj)}")
        yield f"⏳ 生成中... ({i*2}s, {status})"

    raise Exception("生成超时 (120s)")


def _call_wanx_text2image(prompt, size="1024*1024"):
    """纯文生图 (备选, 风格化失败时可用) — 异步"""
    import requests, time as _time
    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "X-DashScope-Async": "enable",
    }
    data = {
        "model": "wanx2.1-t2i-turbo",
        "input": {"prompt": prompt},
        "parameters": {"size": size, "n": 1}
    }
    r = requests.post(url, headers=headers, json=data, timeout=30)
    if r.status_code != 200:
        raise Exception(f"文生图创建失败 HTTP {r.status_code}: {r.text[:200]}")
    j = r.json()
    task_id = j.get("output", {}).get("task_id")
    if not task_id:
        raise Exception(f"无 task_id: {j}")
    # 轮询
    qurl = f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"
    for i in range(60):
        _time.sleep(2)
        qr = requests.get(qurl, headers={"Authorization": f"Bearer {API_KEY}"}, timeout=15)
        qj = qr.json()
        st = qj.get("output", {}).get("task_status", "")
        if st == "SUCCEEDED":
            return qj["output"]["results"][0]["url"]
        if st in ("FAILED", "UNKNOWN"):
            raise Exception(f"文生图失败: {qj.get('message', qj)}")
    raise Exception("文生图超时")


# ===== GUI 弹窗 =====

def show_photo_style_dialog(parent=None):
    """照片风格化主弹窗 (对外入口)"""
    win = _tk.Toplevel(parent) if parent else _tk.Tk()
    win.title("📸 照片风格化 · 阿里通义万相")
    win.geometry("900x650")
    win.configure(bg="#1a1a2e")

    # ---- 左侧: 控制面板 ----
    left = _tk.Frame(win, bg="#1a1a2e", width=340)
    left.pack(side=_tk.LEFT, fill=_tk.Y, padx=8, pady=8)
    left.pack_propagate(False)

    # 1. 上传
    upload_frame = _tk.LabelFrame(left, text="① 上传照片", bg="#1a1a2e", fg="#eee",
                                  font=("", 11, "bold"))
    upload_frame.pack(fill=_tk.X, pady=(0, 10))

    file_path_var = _tk.StringVar(value="")
    img_preview_var = _tk.StringVar(value="未选择图片")

    def _choose_file():
        fp = _fd.askopenfilename(
            filetypes=[("图片", "*.jpg *.jpeg *.png *.bmp *.webp")])
        if fp:
            file_path_var.set(fp)
            img_preview_var.set(_os.path.basename(fp))
            # 更新缩略图
            try:
                from PIL import Image, ImageTk
                img = Image.open(fp)
                img.thumbnail((160, 160))
                photo = ImageTk.PhotoImage(img)
                thumb_label.config(image=photo, text="")
                thumb_label.image = photo  # 防 GC
            except Exception as e:
                thumb_label.config(image="", text=f"⚠️ 预览失败: {e}", fg="orange")

    _tk.Button(upload_frame, text="📁 选择照片", command=_choose_file,
               bg="#4a90d9", fg="white", font=("", 10), pady=4).pack(pady=5)
    thumb_label = _tk.Label(upload_frame, text=img_preview_var.get(),
                            bg="#16213e", fg="#aaa", width=22, height=8)
    thumb_label.pack(pady=5)

    # 2. 大师风格
    master_frame = _tk.LabelFrame(left, text="② 大师风格", bg="#1a1a2e", fg="#eee",
                                  font=("", 11, "bold"))
    master_frame.pack(fill=_tk.X, pady=(0, 10))

    master_var = _tk.StringVar(value="梵高")
    master_cb = _ttk.Combobox(master_frame, textvariable=master_var,
                              values=list(MASTER_STYLES.keys()), state="readonly",
                              width=15)
    master_cb.pack(pady=5)

    # 3. 艺术介质
    medium_frame = _tk.LabelFrame(left, text="③ 艺术介质", bg="#1a1a2e", fg="#eee",
                                  font=("", 11, "bold"))
    medium_frame.pack(fill=_tk.X, pady=(0, 10))

    medium_var = _tk.StringVar(value="油画")
    medium_cb = _ttk.Combobox(medium_frame, textvariable=medium_var,
                              values=list(MEDIUM_STYLES.keys()), state="readonly",
                              width=15)
    medium_cb.pack(pady=5)

    # 4. 风格强度
    strength_frame = _tk.LabelFrame(left, text="④ 风格强度", bg="#1a1a2e", fg="#eee",
                                    font=("", 11, "bold"))
    strength_frame.pack(fill=_tk.X, pady=(0, 10))

    strength_var = _tk.DoubleVar(value=0.6)
    _tk.Scale(strength_frame, from_=0.3, to=0.9, resolution=0.05,
              orient=_tk.HORIZONTAL, variable=strength_var,
              bg="#1a1a2e", fg="#eee", highlightthickness=0).pack(fill=_tk.X, padx=5)

    # 5. 生成按钮
    status_var = _tk.StringVar(value="")
    gen_btn = _tk.Button(left, text="🎨 开始生成", bg="#e94560", fg="white",
                         font=("", 12, "bold"), pady=8, width=18)
    gen_btn.pack(pady=5)
    _tk.Label(left, textvariable=status_var, bg="#1a1a2e", fg="#888",
              wraplength=320, justify="left").pack(pady=5)

    # ---- 右侧: 结果展示 ----
    right = _tk.Frame(win, bg="#16213e")
    right.pack(side=_tk.LEFT, fill=_tk.BOTH, expand=True, padx=8, pady=8)

    result_header = _tk.Label(right, text="🎨 生成结果 (点击图片保存)",
                              bg="#16213e", fg="#eee", font=("", 11, "bold"))
    result_header.pack(pady=(5, 5))

    result_canvas = _tk.Label(right, text="⏳ 上传照片并选择风格\n点击「开始生成」",
                              bg="#0f3460", fg="#aaa",
                              width=60, height=25)
    result_canvas.pack(fill=_tk.BOTH, expand=True, padx=5, pady=5)

    # 保存图片引用
    result_img_holder = {"photo": None, "pil": None, "url": None}

    def _save_result():
        if result_img_holder["pil"] is None:
            _mb.showinfo("提示", "还没有生成结果")
            return
        fp = _fd.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg")],
            initialfile=f"styled_{master_var.get()}_{medium_var.get()}.png")
        if fp:
            result_img_holder["pil"].save(fp)
            _mb.showinfo("保存成功", f"已保存到:\n{fp}")

    save_btn = _tk.Button(right, text="💾 保存图片", command=_save_result,
                          bg="#0f3460", fg="#eee", font=("", 10), pady=4)
    save_btn.pack(pady=5)

    # ---- 生成逻辑 ----
    def _on_generate():
        fp = file_path_var.get()
        if not fp or not _os.path.exists(fp):
            _mb.showwarning("提示", "请先选择照片")
            return
        gen_btn.config(state=_tk.DISABLED, text="⏳ 生成中...")
        status_var.set("准备中...")

        master_name = master_var.get()
        medium_name = medium_var.get()
        master_prompt = MASTER_STYLES.get(master_name, "")
        medium_prompt = MEDIUM_STYLES.get(medium_name, "")
        strength = strength_var.get()

        def _run():
            try:
                url = None
                for progress in _call_wanx_image2image(fp, master_prompt, medium_prompt, strength):
                    win.after(0, lambda p=progress: status_var.set(p))
            except Exception as e1:
                win.after(0, lambda: status_var.set(f"图生图失败, 尝试文生图..."))
                try:
                    prompt = f"Photo of the subject from the uploaded image, {master_prompt}, {medium_prompt}, high quality, detailed"
                    url = _call_wanx_text2image(prompt)
                except Exception as e2:
                    win.after(0, lambda: _on_fail(f"{e1}\n\n文生图也失败: {e2}"))
                    return

            if url:
                win.after(0, lambda u=url: _on_ok(u))

        def _on_fail(msg):
            gen_btn.config(state=_tk.NORMAL, text="🎨 开始生成")
            status_var.set(f"❌ 失败: {msg[:80]}")
            _mb.showerror("生成失败", msg)

        def _download_and_show(url):
            """在后台线程下载, 切回主线程显示"""
            import requests as _rq
            try:
                win.after(0, lambda: status_var.set("⬇️ 下载结果图..."))
                r = _rq.get(url, timeout=30)
                import io as _io2
                from PIL import Image, ImageTk as _ITk
                pil = Image.open(_io2.BytesIO(r.content))
                display = pil.copy()
                display.thumbnail((500, 450))
                photo = _ITk.PhotoImage(display)
                win.after(0, lambda: _show_result(photo, pil, url))
            except Exception as e:
                win.after(0, lambda: _on_fail(f"下载结果失败: {e}"))

        def _show_result(photo, pil, url):
            result_canvas.config(image=photo, text="", width=60, height=25)
            result_canvas.image = photo
            result_img_holder["photo"] = photo
            result_img_holder["pil"] = pil
            result_img_holder["url"] = url
            status_var.set(f"✅ 完成! 点💾保存 ({pil.size[0]}x{pil.size[1]})")
            gen_btn.config(state=_tk.NORMAL, text="🎨 开始生成")

        def _on_ok(url):
            _th.Thread(target=_download_and_show, args=(url,), daemon=True).start()

        _th.Thread(target=_run, daemon=True).start()

    gen_btn.config(command=_on_generate)
    win.focus_set()
    return win


# ===== 独立运行测试 =====
if __name__ == "__main__":
    show_photo_style_dialog()
