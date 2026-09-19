"""Auto-extracted WordcloudMixin"""
import os, sys, re, json, base64, threading, io
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

class WordcloudMixin:
    """WordcloudMixin"""

    def export_analysis_and_wordcloud(self):
        """导出股票分析结果和词云为长图格式"""
        try:
            # 检查是否有分析结果和词云
            if not hasattr(self, 'last_analysis_result') or not self.last_analysis_result:
                messagebox.showwarning("警告", "请先进行股票分析")
                return
            # 选择导出目录
            export_dir = filedialog.askdirectory(
                title="选择导出目录",
                initialdir=self.export_dir if hasattr(self, 'export_dir') and self.export_dir else D_EXPORT_DIR
            )
            if not export_dir:
                return
            # 更新导出目录
            self.export_dir = export_dir
            # 在后台线程中执行导出
            def run_export():
                try:
                    # 生成时间戳
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"股票分析结果_{timestamp}.png"
                    filepath = os.path.join(export_dir, filename)
                    # 创建长图
                    self.create_long_image(filepath)
                    # 显示成功消息
                    if hasattr(self, 'root') and self.root.winfo_exists():
                        self.root.after(0, lambda: messagebox.showinfo(
                            "导出成功",
                            f"已成功导出到:\n{filepath}"
                        ))
                except Exception as e:
                    if hasattr(self, 'root') and self.root.winfo_exists():
                        self.root.after(0, lambda e=e: messagebox.showerror(
                            "导出失败",
                            f"导出失败:{e!s}"
                        ))
            export_thread = threading.Thread(target=run_export, daemon=True)
            export_thread.start()
        except Exception as e:
            messagebox.showerror("错误", f"导出失败:{e!s}")


    def generate_wordcloud_ui(self):
        """生成词云UI"""
        text = self.get_current_text()
        if not text:
            messagebox.showwarning("警告", "请输入文本内容")
            return
        # 获取标签页名称和时间
        tab_name = self.get_active_text_title()
        time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # 在后台线程中生成词云
        def run_wordcloud():
            try:
                # 提取股票信息用于词云(保存股票数据)
                stock_names, _ = extract_stock_names(text)
                wordcloud_stocks = []
                current_date = datetime.now().strftime('%Y-%m-%d')
                for stock_name in stock_names:
                    # 提取股票逻辑
                    logic = get_stock_logic(text, stock_name)
                    if not logic or logic == "未找到明确逻辑":
                        # 尝试从上下文中提取
                        context = extract_stock_context(text, [stock_name])
                        contexts = context.get(stock_name, [])
                        if contexts and contexts[0] != "未找到相关内容":
                            logic = contexts[0][:200]  # 限制长度
                        else:
                            logic = "无详细逻辑"
                    wordcloud_stocks.append({
                        'name': stock_name,
                        'logic': logic,
                        'date': current_date,
                        'source': '词云分析'
                    })
                # 保存词云股票数据
                self.wordcloud_stocks_data = wordcloud_stocks
                generate_wordcloud(text, self.wordcloud_callback, tab_name=tab_name, time_str=time_str)
            except Exception as e:
                if hasattr(self, 'root') and self.root.winfo_exists():
                    self.root.after(0, lambda e=e: messagebox.showerror("错误", f"生成词云失败: {e}"))
        wordcloud_thread = threading.Thread(target=run_wordcloud, daemon=True)
        wordcloud_thread.start()


    def wordcloud_callback(self, message):
        """词云生成回调"""
        if message.startswith("词云生成完成"):
            try:
                # 新建结果标签页名称:左边标签页前五个字 + "词云"
                try:
                    src_title = self.get_active_text_title()
                    prefix = (src_title or "未命名")[:5]
                    wc_tab_title = f"{prefix}词云"
                    wc_tab_id = self.create_result_tab(wc_tab_title)
                    wc_widget = self.result_tabs[wc_tab_id]['widget']
                    if wc_widget:
                        wc_widget.insert("1.0", f"词云生成完成({datetime.now().strftime('%H:%M:%S')})\n")
                except Exception:
                    pass
                # 加载词云图片
                image = Image.open("wordcloud.png")
                # 调整图片大小以适应显示区域(缩小到60%)
                image = image.resize((300, 240), Image.Resampling.LANCZOS)  # 500*0.6=300, 400*0.6=240
                photo = ImageTk.PhotoImage(image)
                # 更新词云显示
                if hasattr(self, 'wordcloud_label') and self.wordcloud_label.winfo_exists():
                    self.wordcloud_label.configure(image=photo, text="")
                    self.wordcloud_label.image = photo
                    # 绑定点击事件,弹出大图
                    self.wordcloud_label.bind("<Button-1>", self.show_wordcloud_large)
                # 将词云图片添加到词云标签页(按照时间顺序,最新的在下面)
                try:
                    if hasattr(self, 'wordcloud_tab_widget') and self.wordcloud_tab_widget.winfo_exists():
                        # 获取当前时间
                        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        # 在词云标签页末尾插入时间戳和图片
                        # 先插入分隔线和时间
                        self.wordcloud_tab_widget.insert(tk.END, f"\n{'='*50}\n")
                        self.wordcloud_tab_widget.insert(tk.END, f"生成时间: {current_time}\n")
                        # 插入词云图片(使用更大的尺寸以便查看)
                        display_image = Image.open("wordcloud.png")
                        # 调整到合适大小(宽度600,保持比例)
                        original_width, original_height = display_image.size
                        aspect_ratio = original_height / original_width
                        new_width = 600
                        new_height = int(new_width * aspect_ratio)
                        display_image = display_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                        display_photo = ImageTk.PhotoImage(display_image)
                        # 在文本框中插入图片
                        self.wordcloud_tab_widget.image_create(tk.END, image=display_photo)
                        self.wordcloud_tab_widget.insert(tk.END, "\n")
                        # 保存图片引用,防止被垃圾回收
                        if not hasattr(self, 'wordcloud_images'):
                            self.wordcloud_images = []
                        self.wordcloud_images.append(display_photo)
                        # 滚动到底部显示最新词云
                        self.wordcloud_tab_widget.see(tk.END)
                        # 切换到词云标签页
                        if hasattr(self, 'wordcloud_tab_id'):
                            tab_info = self.text_widgets.get(self.wordcloud_tab_id)
                            if tab_info:
                                self.text_notebook.select(tab_info['frame'])
                except Exception as e:
                    print(f"添加词云到标签页失败: {e}")
                    import traceback
                    traceback.print_exc()
                # 同时显示股票分析结果
                text = self.get_current_text()
                if text:
                    try:
                        result = analyze_stock_keywords_local(text)
                        if hasattr(self, 'root') and self.root.winfo_exists():
                            self.root.after(0, lambda: self.update_result_text(result))
                    except Exception as e:
                        print(f"显示分析结果失败: {e}")
                if hasattr(self, 'root') and self.root.winfo_exists():
                    self.root.after(0, lambda: messagebox.showinfo("成功", "词云生成完成"))
            except Exception as e:
                if hasattr(self, 'root') and self.root.winfo_exists():
                    error_msg = str(e)
                    self.root.after(0, lambda: messagebox.showerror("错误", f"显示词云失败: {error_msg}"))
        else:
            if hasattr(self, 'root') and self.root.winfo_exists():
                self.root.after(0, lambda: messagebox.showwarning("警告", message))


    def show_wordcloud_large(self, event=None):
        """点击词云时弹出2倍大小的词云图片,不超过屏幕三分之二,保持原始宽高比"""
        try:
            wordcloud_path = "wordcloud.png"
            if not os.path.exists(wordcloud_path):
                messagebox.showwarning("警告", "词云图片不存在,请先生成词云")
                return
            # 获取屏幕尺寸
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            max_width = int(screen_width * 2 / 3)
            max_height = int(screen_height * 2 / 3)
            # 加载词云图片
            image = Image.open(wordcloud_path)
            original_width = image.width
            original_height = image.height
            original_ratio = original_width / original_height  # 保持原始宽高比
            # 放大2倍
            new_width = original_width * 2
            new_height = original_height * 2
            # 如果超过屏幕三分之二,则按比例缩小(保持宽高比)
            if new_width > max_width or new_height > max_height:
                width_ratio = max_width / new_width
                height_ratio = max_height / new_height
                ratio = min(width_ratio, height_ratio)  # 使用较小的比例以确保两个方向都不超过
                new_width = int(new_width * ratio)
                new_height = int(new_height * ratio)
            # 确保宽高比与原始图片一致(防止因整数舍入导致的偏差)
            # 重新计算以保持精确的宽高比
            if new_width / new_height != original_ratio:
                # 以宽度为准,调整高度
                new_height = int(new_width / original_ratio)
                # 如果调整后的高度超过限制,则以高度为准
                if new_height > max_height:
                    new_height = max_height
                    new_width = int(new_height * original_ratio)
            # 调整图片大小,保持宽高比
            large_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(large_image)
            # 创建新窗口,窗口大小要包含按钮的高度
            button_height = 50  # 为关闭按钮预留空间
            window_width = new_width
            window_height = new_height + button_height
            large_window = self._toplevel(self.root)
            large_window.title("词云大图")
            large_window.geometry(f"{window_width}x{window_height}")
            # 创建画布用于显示图片(使用画布可以更好地控制显示)
            canvas = tk.Canvas(large_window, width=new_width, height=new_height, highlightthickness=0)
            canvas.pack(pady=10)
            canvas.create_image(new_width // 2, new_height // 2, image=photo, anchor=tk.CENTER)
            canvas.image = photo  # 保持引用,防止被垃圾回收
            # 添加关闭按钮
            close_button = ttk.Button(large_window, text="关闭", command=large_window.destroy)
            close_button.pack(pady=10)
        except Exception as e:
            messagebox.showerror("错误", f"显示词云大图失败: {e}")


__all__ = ["WordcloudMixin"]
