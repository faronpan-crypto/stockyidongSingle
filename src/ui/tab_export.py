"""导出"""
import os, sys, re, json, time, threading, traceback, hashlib, urllib.parse
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog, scrolledtext
try:
    import numpy as np
except ImportError: np = None
try:
    import pandas as pd
except ImportError: pd = None
try:
    import akshare as ak
except ImportError: ak = None
try:
    import tushare as ts
except ImportError: ts = None
try:
    import requests
except ImportError: requests = None
from utils.network import safe_call
from utils.config import *  # 路径/配置/Token
from data.snapshot import *  # get_news_stocks_* 函数

from datetime import datetime, timedelta
import re
import os
import time
import threading
import traceback
import hashlib
from urllib.parse import urljoin

class ExportMixin:
    """导出"""

    def export_to_excel_ui(self):
        """导出分析结果和词云数据到Excel"""
        try:
            # 检查是否有分析结果
            if not hasattr(self, 'last_analysis_result') or not self.last_analysis_result:
                messagebox.showwarning("警告", "请先进行股票分析,然后再导出结果")
                return
            # 选择保存路径,不设置初始文件名,让用户自由命名
            filepath = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[
                    ("Excel files", "*.xlsx"),
                    ("CSV files", "*.csv"),
                    ("All files", "*.*")
                ],
                initialdir=D_EXPORT_DIR,
                title="保存分析结果文件"
            )
            if filepath:
                # 显示导出进度
                progress_window = self._toplevel(self.root)
                progress_window.title("导出中...")
                progress_window.geometry("300x100")
                progress_window.resizable(False, False)
                # 居中显示
                progress_window.transient(self.root)
                progress_window.grab_set()
                # 进度标签
                progress_label = ttk.Label(progress_window, text="正在导出分析结果...", font=("Arial", 10))
                progress_label.pack(pady=20)
                # 进度条
                progress_bar = ttk.Progressbar(progress_window, mode='indeterminate')
                progress_bar.pack(pady=10, padx=20, fill=tk.X)
                progress_bar.start()
                def run_excel_export():
                    try:
                        print(f"开始导出到: {filepath}")
                        success = self.export_to_excel(filepath)
                        # 关闭进度窗口
                        if hasattr(self, 'root') and self.root.winfo_exists():
                            self.root.after(0, progress_window.destroy)
                        if success:
                            # 检查是否实际生成了文件
                            if os.path.exists(filepath):
                                self.root.after(0, lambda: messagebox.showinfo(
                                    "导出成功",
                                    f"分析结果已成功导出到:\n{filepath}\n\n文件大小: {os.path.getsize(filepath)} 字节"
                                ))
                            else:
                                # 检查是否有CSV文件
                                csv_filepath = filepath.replace('.xlsx', '.csv')
                                if os.path.exists(csv_filepath):
                                    self.root.after(0, lambda: messagebox.showinfo(
                                        "导出成功",
                                        f"分析结果已导出为CSV文件:\n{csv_filepath}\n\n文件大小: {os.path.getsize(csv_filepath)} 字节"
                                    ))
                                else:
                                    self.root.after(0, lambda: messagebox.showerror("导出失败", "文件未生成,请检查错误信息"))
                        else:
                            self.root.after(0, lambda: messagebox.showerror("导出失败", "导出过程中发生错误,请查看控制台输出"))
                    except Exception as e:
                        print(f"导出线程异常: {e}")
                        import traceback
                        traceback.print_exc()
                        if hasattr(self, 'root') and self.root.winfo_exists():
                            self.root.after(0, progress_window.destroy)
                            self.root.after(0, lambda e=e: messagebox.showerror("导出错误", f"导出失败:{e!s}"))
                # 在后台线程中执行导出
                export_thread = threading.Thread(target=run_excel_export, daemon=True)
                export_thread.start()
        except Exception as e:
            print(f"导出UI异常: {e}")
            import traceback
            traceback.print_exc()
            messagebox.showerror("错误", f"导出失败:{e!s}")

    def export_to_excel(self, filepath):
        """导出分析结果到Excel文件,保留文字格式"""
        try:
            print(f"开始导出Excel文件到: {filepath}")
            # 获取股票分析结果框的所有文字内容
            result_text = ""
            result_widget = self.get_active_result_widget()
            if result_widget:
                result_text = result_widget.get("1.0", tk.END).strip()
            # 如果没有结果文字,使用分析结果
            if not result_text and hasattr(self, 'last_analysis_result') and self.last_analysis_result:
                result_text = self.last_analysis_result
            if not result_text:
                print("没有分析结果可导出")
                return False
            # 将结果文字按行分割,便于在Excel中显示
            result_lines = result_text.split('\n')
            # 创建更详细的数据结构,使用多列来更好地组织内容
            export_data = []
            # 添加标题行
            export_data.append(['股票分析结果导出', '', '', ''])
            export_data.append(['导出时间', datetime.now().strftime("%Y-%m-%d %H:%M:%S"), '', ''])
            export_data.append(['导出工具', '股票分析工具', '', ''])
            export_data.append(['文件版本', 'v1.0', '', ''])
            export_data.append(['', '', '', ''])  # 空行
            # 添加分析结果内容标题
            export_data.append(['分析结果内容:', '', '', ''])
            export_data.append(['', '', '', ''])  # 空行
            # 将每一行结果添加到数据中,保持原有格式
            for line in result_lines:
                if line.strip():  # 只添加非空行
                    # 检查是否是表格行(包含多个空格分隔的数据)
                    if '  ' in line and not line.startswith('#'):
                        # 尝试按多个空格分割表格数据
                        import re
                        # 使用正则表达式按多个空格分割
                        parts = re.split(r'\s{2,}', line.strip())
                        if len(parts) > 1:
                            # 表格行,使用多列显示
                            row_data = parts[:4]  # 最多4列
                            while len(row_data) < 4:
                                row_data.append('')
                            export_data.append(row_data)
                        else:
                            # 普通行
                            export_data.append([line, '', '', ''])
                    else:
                        # 普通行,保持原有的缩进和格式
                        export_data.append([line, '', '', ''])
                else:
                    export_data.append(['', '', '', ''])  # 保留空行
            # 转换为DataFrame,使用多列来更好地显示内容
            df = pd.DataFrame(export_data, columns=['内容', '列2', '列3', '列4'])
            # 尝试不同的导出方法
            try:
                # 方法1: 使用openpyxl
                print("尝试使用openpyxl引擎导出...")
                with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                    # 创建股票分析结果工作表
                    df.to_excel(writer, sheet_name='股票分析结果', index=False)
                    # 如果有词云图片,将图片拷贝到第二个sheet
                    wordcloud_path = os.path.join(D_OUTPUT_DIR, "wordcloud.png")
                    if os.path.exists(wordcloud_path):
                        print("发现词云图片,正在添加到Excel...")
                        try:
                            from openpyxl.drawing.image import Image
                            from openpyxl.utils import get_column_letter
                            # 创建词云工作表
                            wordcloud_sheet = writer.book.create_sheet("词云图片")
                            # 添加词云图片
                            img = Image(wordcloud_path)
                            # 调整图片大小以适应Excel
                            img.width = 400
                            img.height = 300
                            wordcloud_sheet.add_image(img, 'A1')
                            # 添加图片信息
                            wordcloud_sheet['A15'] = '词云图片信息'
                            wordcloud_sheet['A16'] = f'生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
                            wordcloud_sheet['A17'] = f'图片文件: {wordcloud_path}'
                            wordcloud_sheet['A18'] = f'图片路径: {os.path.abspath(wordcloud_path)}'
                            print("词云图片已成功添加到Excel")
                        except Exception as img_error:
                            print(f"添加词云图片失败: {img_error}")
                            # 如果图片添加失败,创建词云信息sheet
                            wordcloud_info = {
                                '词云信息': [
                                    '词云图片已生成',
                                    f'生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
                                    '词云图片文件: wordcloud.png',
                                    '图片路径: ' + os.path.abspath("wordcloud.png"),
                                    f'图片添加失败: {img_error!s}'
                                ]
                            }
                            wordcloud_df = pd.DataFrame(wordcloud_info)
                            wordcloud_df.to_excel(writer, sheet_name='词云信息', index=False)
                    else:
                        print("未找到词云图片文件")
                print("Excel文件导出成功!")
                return True
            except ImportError as e:
                print(f"openpyxl不可用: {e}")
                try:
                    # 方法2: 使用xlsxwriter
                    print("尝试使用xlsxwriter引擎导出...")
                    with pd.ExcelWriter(filepath, engine='xlsxwriter') as writer:
                        df.to_excel(writer, sheet_name='股票分析结果', index=False)
                        # 如果有词云图片,添加词云信息
                        wordcloud_path = "wordcloud.png"
                        if os.path.exists(wordcloud_path):
                            print("发现词云图片,正在添加词云信息...")
                            wordcloud_info = {
                                '词云信息': [
                                    '词云图片已生成',
                                    f'生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
                                    '词云图片文件: wordcloud.png',
                                    '图片路径: ' + os.path.abspath("wordcloud.png"),
                                    '注意: xlsxwriter不支持直接插入图片,请查看wordcloud.png文件'
                                ]
                            }
                            wordcloud_df = pd.DataFrame(wordcloud_info)
                            wordcloud_df.to_excel(writer, sheet_name='词云信息', index=False)
                    print("Excel文件导出成功!")
                    return True
                except ImportError as e2:
                    print(f"xlsxwriter也不可用: {e2}")
                    try:
                        # 方法3: 使用默认引擎
                        print("尝试使用默认引擎导出...")
                        df.to_excel(filepath, sheet_name='股票分析结果', index=False)
                        print("Excel文件导出成功!")
                        return True
                    except Exception as e3:
                        print(f"默认引擎也失败: {e3}")
                        # 方法4: 导出为CSV作为备选
                        print("尝试导出为CSV文件...")
                        csv_filepath = filepath.replace('.xlsx', '.csv')
                        df.to_csv(csv_filepath, index=False, encoding='utf-8-sig')
                        print(f"已导出为CSV文件: {csv_filepath}")
                        return True
            except Exception as e:
                print(f"Excel导出过程中出错: {e}")
                # 最后的备选方案:导出为CSV
                try:
                    print("尝试导出为CSV文件作为备选...")
                    csv_filepath = filepath.replace('.xlsx', '.csv')
                    df.to_csv(csv_filepath, index=False, encoding='utf-8-sig')
                    print(f"已导出为CSV文件: {csv_filepath}")
                    return True
                except Exception as csv_e:
                    print(f"CSV导出也失败: {csv_e}")
                    return False
        except Exception as e:
            print(f"导出Excel失败: {e}")
            import traceback
            traceback.print_exc()
            return False


__all__ = ["ExportMixin"]
