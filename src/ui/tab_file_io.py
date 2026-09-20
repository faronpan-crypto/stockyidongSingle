"""文件保存/加载/导入导出/缓存"""
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


class FileIoMixin:
    """文件保存/加载/导入导出/缓存"""

    def _load_chrome_config(self):
        """从配置文件加载Chrome路径"""
        try:
            config_file = os.path.join(_APP_CONFIG_DIR, "chrome_config.json")
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    chrome_path = config.get('chrome_path', '').strip()
                    if chrome_path and os.path.exists(chrome_path):
                        self.chrome_path_config = chrome_path
        except Exception as e:
            print(f"加载Chrome配置失败: {e}")
            self.chrome_path_config = None

    def _save_chrome_config(self, chrome_path):
        """保存Chrome路径到配置文件"""
        try:
            config_file = os.path.join(_APP_CONFIG_DIR, "chrome_config.json")
            config = {'chrome_path': chrome_path}
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            self.chrome_path_config = chrome_path
        except Exception as e:
            print(f"保存Chrome配置失败: {e}")

    def _save_long_image(img_path, title="长图"):
        """把已生成的长图保存到用户选的路径。"""
        import os
        import shutil
        from tkinter import filedialog, messagebox
        if not img_path or not os.path.exists(img_path):
            messagebox.showwarning("提示", "长图还没生成好，请稍等再试")
            return
        save_path = filedialog.asksaveasfilename(
            title="保存长图",
            defaultextension=".png",
            filetypes=[("PNG 图片", "*.png"), ("所有文件", "*.*")],
            initialfile=f"{title.replace(' ', '_')}.png")
        if not save_path:
            return
        try:
            shutil.copy(img_path, save_path)
            messagebox.showinfo("✅", f"长图已保存到：\n{save_path}")
        except Exception as e:
            messagebox.showerror("❌", f"保存失败：{e}")

    def get_image_save_directory(self):
        """获取图片保存目录(按日期组织)"""
        today = datetime.now().strftime("%Y-%m-%d")
        image_dir = os.path.join(D_IMAGES_DIR, today)
        os.makedirs(image_dir, exist_ok=True)
        return image_dir

    def _load_excel_files(self, file_paths):
        """加载Excel文件内容(内部方法)"""
        if not file_paths:
            return
        # 颜色映射表(Excel颜色代码到Tkinter颜色标签,6种颜色循环)
        color_mapping = {
            'FFE6E6': 'red', 'FFF0E6': 'orange', 'E6FFE6': 'green',
            'E6F3FF': 'blue', 'F0E6FF': 'purple', 'F5F5F5': 'black',
            'E6FFFF': 'blue', 'FFFFE6': 'orange', 'FFE6F0': 'red',
            'E6F0FF': 'blue', 'F0FFE6': 'green', 'FFE6CC': 'orange',
            'E6E6FF': 'purple', 'CCFFE6': 'green', 'FFCCE6': 'red',
            'E6FFCC': 'green', 'CCE6FF': 'blue', 'FFE6B3': 'orange',
            'B3E6FF': 'blue', 'E6B3FF': 'purple', 'B3FFE6': 'green',
        }
        # 支持多文件上传,每个文件一个标签页
        for file_path in file_paths:
            try:
                # 创建新标签页,标题为文件名
                file_name = os.path.basename(file_path)
                tab_id = self.create_text_tab(file_name)
                text_widget = self.text_widgets[tab_id]['widget']
                # 使用openpyxl读取Excel文件以获取颜色信息
                try:
                    from openpyxl import load_workbook
                    wb = load_workbook(file_path, data_only=True)
                    ws = wb.active
                    # 读取Excel内容并保持颜色
                    current_pos = "1.0"
                    for row in ws.iter_rows():
                        row_text = ""
                        row_colors = []
                        for cell in row:
                            if cell.value is not None:
                                cell_text = str(cell.value)
                                row_text += cell_text + "\t"
                                # 获取单元格背景颜色
                                if cell.fill and cell.fill.start_color and cell.fill.start_color.rgb:
                                    color_code = cell.fill.start_color.rgb[2:]  # 去掉'FF'前缀
                                    if color_code in color_mapping:
                                        row_colors.append(color_mapping[color_code])
                                    else:
                                        row_colors.append("black")
                                else:
                                    row_colors.append("black")
                        if row_text.strip():
                            # 插入行文本
                            text_widget.insert(current_pos, row_text.rstrip('\t') + "\n")
                            # 应用颜色(简化处理:整行使用第一个单元格的颜色)
                            if row_colors and row_colors[0] != "black":
                                start_pos = current_pos
                                end_pos = text_widget.index(tk.INSERT)
                                text_widget.tag_add(row_colors[0], start_pos, end_pos)
                            current_pos = text_widget.index(tk.INSERT)
                    # 检查是否有内容
                    if not text_widget.get("1.0", tk.END).strip():
                        raise Exception("openpyxl读取内容为空")
                except Exception as e:
                    # 回退到pandas方式
                    print(f"openpyxl读取失败,使用pandas: {e}")
                    df = pd.read_excel(file_path)
                    # 尝试找到包含文本的列
                    text_content = ""
                    for col in df.columns:
                        if df[col].dtype == 'object':  # 文本类型列
                            text_content += df[col].astype(str).str.cat(sep='\n') + '\n'
                    if not text_content.strip():
                        # 如果没有找到文本列,使用整个DataFrame
                        text_content = df.to_string(index=False)
                    text_widget.delete("1.0", tk.END)
                    text_widget.insert("1.0", text_content)
            except Exception as e:
                print(f"加载Excel文件失败: {e}")
                messagebox.showerror("错误", f"加载Excel文件失败: {file_path}\n{e!s}")
        if len(file_paths) == 1:
            messagebox.showinfo("成功", f"从Excel文件加载内容成功: {os.path.basename(file_paths[0])}")
        else:
            messagebox.showinfo("成功", f"成功加载 {len(file_paths)} 个Excel文件,每个文件一个标签页")

    def _save_excel_file_to_config(self, file_path, source="unknown"):
        """保存Excel文件路径到配置文件"""
        try:
            config = {}
            if os.path.exists(EXCEL_FILES_CONFIG_FILE):
                with open(EXCEL_FILES_CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            if 'excel_files' not in config:
                config['excel_files'] = []
            # 检查是否已存在
            file_path_abs = os.path.abspath(file_path)
            existing = False
            for file_info in config['excel_files']:
                if os.path.abspath(file_info.get('path', '')) == file_path_abs:
                    # 更新时间和来源
                    file_info['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    file_info['source'] = source
                    existing = True
                    break
            if not existing:
                # 添加新记录
                config['excel_files'].append({
                    'path': file_path_abs,
                    'source': source,
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
            # 限制最多保存50条记录
            if len(config['excel_files']) > 50:
                # 按时间排序,保留最新的50条
                config['excel_files'].sort(key=lambda x: x.get('timestamp', ''), reverse=True)
                config['excel_files'] = config['excel_files'][:50]
            # 保存配置
            with open(EXCEL_FILES_CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存Excel文件配置失败: {e}")

    def _load_a_share_index_constituent_code_sets(self):
        """沪深300 / 中证500 / 科创50 成份股 6 位代码集合(需 AKShare)。"""
        hs300, zz500, kc50 = set(), set(), set()
        if not AKSHARE_AVAILABLE:
            return hs300, zz500, kc50
        import akshare as ak
        for sym, target in (
            ("000300", hs300),
            ("000905", zz500),
            ("000688", kc50),
        ):
            try:
                df = ak.index_stock_cons(symbol=sym)
                if df is None or getattr(df, "empty", True):
                    continue
                col = "品种代码" if "品种代码" in df.columns else None
                if not col:
                    continue
                for v in df[col].astype(str):
                    c6 = self._normalize_stock_code_6(v)
                    if c6:
                        target.add(c6)
            except Exception:
                continue
        return hs300, zz500, kc50

    def _import_stocks_from_file(self, text_widget, parent_window):
        """从文件导入股票"""
        filename = filedialog.askopenfilename(
            title="选择股票文件",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
        )
        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    content = f.read()
                text_widget.delete("1.0", tk.END)
                text_widget.insert("1.0", content)
            except Exception as e:
                messagebox.showerror("错误", f"导入失败: {e}", parent=parent_window)

    def _load_top_list_data(self, status_var, tree_widget):
        """后台获取并显示龙虎榜数据"""
        def worker():
            try:
                status_var.set("正在向Tushare请求龙虎榜数据...")
                client = self._ensure_tushare_client()
                today = datetime.now()
                date_candidates = [
                    today.strftime('%Y%m%d'),
                    (today - timedelta(days=1)).strftime('%Y%m%d'),
                    (today - timedelta(days=2)).strftime('%Y%m%d')
                ]
                used_date = None
                df = None
                for trade_date in date_candidates:
                    df = client.top_list(trade_date=trade_date)
                    if df is not None and not df.empty:
                        used_date = trade_date
                        break
                if df is None or df.empty or used_date is None:
                    raise ValueError("未获取到龙虎榜数据,请确认Tushare积分(>=2000)或稍后再试")
                records = df.to_dict('records')
                records.sort(key=lambda x: x.get('net_amount') or 0, reverse=True)
                saved_rows = 0
                if not has_lhb_records(used_date):
                    saved_rows = save_lhb_records(records)
                today_str = today.strftime('%Y%m%d')
                status_msg = f"数据日期:{used_date}"
                if used_date != today_str:
                    status_msg += "(非今日数据,已自动回退)"
                if saved_rows > 0:
                    status_msg += f" | 已写入数据库 {saved_rows} 条"
                else:
                    status_msg += " | 数据已存在数据库"
                def update_ui():
                    try:
                        status_var.set(status_msg)
                        tree_widget.delete(*tree_widget.get_children())
                        def fmt(value, digits=2, suffix=""):
                            if value is None or value == "":
                                return "--"
                            try:
                                return f"{float(value):,.{digits}f}{suffix}"
                            except Exception:
                                return str(value)
                        def fmt_pct(value):
                            if value is None or value == "":
                                return "--"
                            try:
                                return f"{float(value):+.2f}%"
                            except Exception:
                                return str(value)
                        def fmt_large(value):
                            if value is None or value == "":
                                return "--"
                            try:
                                v = float(value)
                                if abs(v) >= 1e8:
                                    return f"{v/1e8:.2f}亿"
                                if abs(v) >= 1e4:
                                    return f"{v/1e4:.2f}万"
                                return f"{v:,.0f}"
                            except Exception:
                                return str(value)
                        for row in records:
                            trade_date = row.get('trade_date', used_date)
                            net_amount = row.get('net_amount') or 0
                            tags = []
                            if trade_date != today_str:
                                tags.append("non_today")
                            if net_amount > 0:
                                tags.append("net_positive")
                            elif net_amount < 0:
                                tags.append("net_negative")
                            values = (
                                trade_date,
                                row.get('ts_code', ''),
                                row.get('name', ''),
                                fmt(row.get('close')),
                                fmt_pct(row.get('pct_change')),
                                fmt_pct(row.get('turnover_rate')),
                                fmt_large(row.get('amount')),
                                fmt_large(row.get('l_amount')),
                                fmt_large(net_amount),
                                fmt_pct(row.get('net_rate')),
                                fmt_pct(row.get('amount_rate')),
                                fmt_large(row.get('float_values')),
                                row.get('reason', '')
                            )
                            tree_widget.insert("", tk.END, values=values, tags=tags)
                    except Exception as ui_err:
                        status_var.set(f"展示龙虎榜数据时发生错误: {ui_err}")
                self.root.after(0, update_ui)
            except Exception as e:
                self.root.after(0, lambda e=e: status_var.set(f"获取龙虎榜数据失败: {e}"))
        threading.Thread(target=worker, daemon=True).start()

    def _load_margin_summary_data(self, status_var, tree_widget, trade_date, exchange_id):
        """后台获取并显示融资融券汇总数据"""
        def worker():
            try:
                status_var.set("正在获取融资融券汇总数据...")
                client = self._ensure_tushare_client()
                # 如果今日无数据,尝试前几个交易日
                date_candidates = [trade_date]
                if trade_date == datetime.now().strftime('%Y%m%d'):
                    for i in range(1, 4):
                        date_candidates.append((datetime.now() - timedelta(days=i)).strftime('%Y%m%d'))
                df = None
                used_date = None
                for date_str in date_candidates:
                    try:
                        if exchange_id:
                            df = client.margin(trade_date=date_str, exchange_id=exchange_id)
                        else:
                            df = client.margin(trade_date=date_str)
                        if df is not None and not df.empty:
                            used_date = date_str
                            break
                    except:
                        continue
                if df is None or df.empty:
                    raise ValueError("未获取到融资融券汇总数据,请确认Tushare积分(>=2000)或稍后再试")
                def update_ui():
                    try:
                        status_var.set(f"数据日期:{used_date} | 共{len(df)}条记录")
                        tree_widget.delete(*tree_widget.get_children())
                        def fmt_large(value):
                            if pd.isna(value) or value is None:
                                return "--"
                            try:
                                v = float(value)
                                if abs(v) >= 1e8:
                                    return f"{v/1e8:.2f}亿"
                                if abs(v) >= 1e4:
                                    return f"{v/1e4:.2f}万"
                                return f"{v:,.0f}"
                            except:
                                return str(value)
                        def fmt_exchange(ex_id):
                            exchange_map = {"SSE": "上交所", "SZSE": "深交所", "BSE": "北交所"}
                            return exchange_map.get(ex_id, ex_id)
                        for _, row in df.iterrows():
                            values = (
                                row.get('trade_date', ''),
                                fmt_exchange(row.get('exchange_id', '')),
                                fmt_large(row.get('rzye')),
                                fmt_large(row.get('rzmre')),
                                fmt_large(row.get('rzche')),
                                fmt_large(row.get('rqye')),
                                fmt_large(row.get('rqmcl')),
                                fmt_large(row.get('rzrqye')),
                                fmt_large(row.get('rqyl'))
                            )
                            tree_widget.insert("", tk.END, values=values)
                    except Exception as ui_err:
                        status_var.set(f"显示数据时发生错误: {ui_err}")
                self.root.after(0, update_ui)
            except Exception as e:
                self.root.after(0, lambda e=e: status_var.set(f"获取数据失败: {e}"))
        threading.Thread(target=worker, daemon=True).start()

    def _load_margin_detail_data(self, status_var, tree_widget, trade_date, ts_code):
        """后台获取并显示融资融券明细数据"""
        def worker():
            try:
                status_var.set("正在获取融资融券明细数据...")
                client = self._ensure_tushare_client()
                # 如果今日无数据,尝试前几个交易日
                date_candidates = [trade_date]
                if trade_date == datetime.now().strftime('%Y%m%d'):
                    for i in range(1, 4):
                        date_candidates.append((datetime.now() - timedelta(days=i)).strftime('%Y%m%d'))
                df = None
                used_date = None
                for date_str in date_candidates:
                    try:
                        if ts_code:
                            df = client.margin_detail(trade_date=date_str, ts_code=ts_code)
                        else:
                            df = client.margin_detail(trade_date=date_str)
                        if df is not None and not df.empty:
                            used_date = date_str
                            break
                    except:
                        continue
                if df is None or df.empty:
                    raise ValueError("未获取到融资融券明细数据,请确认Tushare积分(>=2000)或稍后再试")
                # 按融资融券余额排序
                if 'rzrqye' in df.columns:
                    df = df.sort_values('rzrqye', ascending=False)
                def update_ui():
                    try:
                        status_var.set(f"数据日期:{used_date} | 共{len(df)}条记录")
                        tree_widget.delete(*tree_widget.get_children())
                        def fmt_large(value):
                            if pd.isna(value) or value is None:
                                return "--"
                            try:
                                v = float(value)
                                if abs(v) >= 1e8:
                                    return f"{v/1e8:.2f}亿"
                                if abs(v) >= 1e4:
                                    return f"{v/1e4:.2f}万"
                                return f"{v:,.0f}"
                            except:
                                return str(value)
                        for _, row in df.iterrows():
                            values = (
                                row.get('trade_date', ''),
                                row.get('ts_code', ''),
                                row.get('name', '') or '--',
                                fmt_large(row.get('rzye')),
                                fmt_large(row.get('rqye')),
                                fmt_large(row.get('rzmre')),
                                fmt_large(row.get('rqyl')),
                                fmt_large(row.get('rzche')),
                                fmt_large(row.get('rqchl')),
                                fmt_large(row.get('rqmcl')),
                                fmt_large(row.get('rzrqye'))
                            )
                            tree_widget.insert("", tk.END, values=values)
                    except Exception as ui_err:
                        status_var.set(f"显示数据时发生错误: {ui_err}")
                self.root.after(0, update_ui)
            except Exception as e:
                self.root.after(0, lambda e=e: status_var.set(f"获取数据失败: {e}"))
        threading.Thread(target=worker, daemon=True).start()

    def _parse_market_nav_import_data(self, raw_text):
        """解析外部导航数据,返回规范化字典"""
        if not raw_text:
            return {}
        raw_text = raw_text.strip()
        if not raw_text:
            return {}
        # 1. 尝试 JSON
        try:
            data = json.loads(raw_text)
            normalized = self._normalize_market_nav_data(data)
            if normalized:
                return normalized
        except Exception:
            pass
        # 2. 逐行解析
        return self._parse_market_nav_lines(raw_text)

    def _load_managed_stocks_from_file(self):
        try:
            if os.path.exists(MANAGED_STOCKS_FILE):
                with open(MANAGED_STOCKS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    cleaned = []
                    for entry in data:
                        if isinstance(entry, dict) and entry.get("name"):
                            cleaned.append(entry)
                    self.managed_stocks = cleaned[-100:]
                    self._update_managed_stock_cache()
        except Exception as e:
            print(f"加载自选股配置失败: {e}")

    def _save_managed_stocks_to_file(self):
        try:
            os.makedirs(os.path.dirname(MANAGED_STOCKS_FILE), exist_ok=True)
            with open(MANAGED_STOCKS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.managed_stocks[-100:], f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存自选股配置失败: {e}")

    def _save_ai_staff_docx(self, path, text):
        from docx import Document
        from docx.shared import RGBColor
        seg_to_rgb = {
            "kw_pressure": (0xC0, 0x39, 0x2B),
            "kw_support": (0x14, 0x8F, 0x77),
            "kw_position": (0x28, 0x74, 0xA6),
            "kw_risk": (0x7D, 0x3C, 0x98),
        }
        doc = Document()
        p = doc.add_paragraph()
        for seg, tgn in self._segment_text_ai_staff_keywords(text):
            if not seg:
                continue
            run = p.add_run(seg)
            if tgn and tgn in seg_to_rgb:
                r, g, b = seg_to_rgb[tgn]
                run.font.color.rgb = RGBColor(r, g, b)
        doc.save(path)

    def _save_ai_staff_xlsx(self, path, text):
        from openpyxl import Workbook
        from openpyxl.cell.rich_text import CellRichText, TextBlock
        from openpyxl.styles import Alignment, Font
        seg_to_color = {
            "kw_pressure": "C0392B",
            "kw_support": "148F77",
            "kw_position": "2874A6",
            "kw_risk": "7D3C98",
        }
        base_font = Font(name="微软雅黑", size=11, color="000000")
        wb = Workbook()
        ws = wb.active
        ws.title = "AI报告"
        if not (text or "").strip():
            ws.cell(row=1, column=1, value="(空)")
            wb.save(path)
            return
        rich = CellRichText()
        for seg, tgn in self._segment_text_ai_staff_keywords(text):
            if not seg:
                continue
            if tgn and tgn in seg_to_color:
                rich.append(
                    TextBlock(Font(name="微软雅黑", size=11, color=seg_to_color[tgn]), seg)
                )
            else:
                rich.append(TextBlock(base_font, seg))
        cell = ws.cell(row=1, column=1, value=rich)
        cell.alignment = Alignment(wrap_text=True, vertical="top")
        ws.column_dimensions["A"].width = 110
        try:
            ws.row_dimensions[1].height = min(409.0, 24.0 + text.count("\n") * 14.0)
        except Exception:
            pass
        wb.save(path)

    def _save_ai_staff_content(self, parent, text_widget, default_title="AI员工报告"):
        """保存当前页内容:根据扩展名保存为 TXT / Word / Excel;Word 与 Excel 保留关键词颜色。"""
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = filedialog.asksaveasfilename(
            parent=parent,
            defaultextension=".txt",
            filetypes=[
                ("文本 TXT", "*.txt"),
                ("Word", "*.docx"),
                ("Excel", "*.xlsx"),
            ],
            initialfile=f"{default_title}_{stamp}.txt",
        )
        if not path:
            return
        text = text_widget.get("1.0", "end-1c")
        ext = os.path.splitext(path)[1].lower()
        try:
            if ext == ".txt":
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text)
            elif ext == ".docx":
                self._save_ai_staff_docx(path, text)
            elif ext == ".xlsx":
                self._save_ai_staff_xlsx(path, text)
            else:
                messagebox.showwarning("提示", f"请使用 .txt、.docx 或 .xlsx 扩展名。\n当前:{ext}", parent=parent)
                return
            messagebox.showinfo("成功", f"已保存:\n{path}", parent=parent)
        except Exception as e:
            messagebox.showerror("错误", f"保存失败:{e}", parent=parent)

    def _auto_import_leader_stocks(self):
        """自动导入同花顺板块龙头股到持仓标签1-8(每2个板块各10个龙头股,共20个股票)"""
        try:
            from tkinter import messagebox

            import akshare as ak
            # 获取所有板块列表
            all_sectors = []
            for sector_name in self.sector_index_list:
                # 判断是概念板块还是行业板块
                sector_type = "概念"  # 默认
                try:
                    concept_df = safe_call(ak.stock_board_concept_name_ths, fallback=pd.DataFrame(), label="ak.stock_board_concept_name_ths")
                    if not concept_df.empty and sector_name in concept_df['板块名称'].tolist():
                        sector_type = "概念"
                    else:
                        industry_df = safe_call(ak.stock_board_industry_name_ths, fallback=pd.DataFrame(), label="ak.stock_board_industry_name_ths")
                        if not industry_df.empty and sector_name in industry_df['板块名称'].tolist():
                            sector_type = "行业"
                except:
                    pass
                all_sectors.append((sector_name, sector_type))
            if not all_sectors:
                messagebox.showwarning("提示", "请先在板块指数下拉框中添加板块", parent=self.root)
                return
            # 确认对话框
            result = messagebox.askyesno("确认",
                f"将自动导入 {len(all_sectors)} 个板块的龙头股到持仓标签1-8\n"
                f"每2个板块各取10个龙头股(共20个)导入到一个标签\n"
                f"标签页名称为两个板块首字组合(2个字)\n"
                f"是否继续?",
                parent=self.root)
            if not result:
                return
            # 在后台线程中执行导入
            def import_stocks():
                try:
                    imported_count = 0
                    # 存储每个标签对应的板块名称,用于更新标签页名称
                    tab_names = {}  # {group_index: "首字1首字2"}
                    # 每2个板块为一组,导入到持仓标签7-14(持仓1-持仓8)
                    for group_idx in range(8):  # 8个持仓标签
                        target_group_index = 7 + group_idx  # 持仓7-14对应持仓1-8
                        sector_start_idx = group_idx * 2
                        sector_end_idx = min(sector_start_idx + 2, len(all_sectors))
                        if sector_start_idx >= len(all_sectors):
                            break
                        # 记录这两个板块的名称
                        sector_names = []
                        for i in range(sector_start_idx, sector_end_idx):
                            if i < len(all_sectors):
                                sector_name, _ = all_sectors[i]
                                sector_names.append(sector_name)
                        # 生成标签页名称(两个板块首字组合,共2个字)
                        if len(sector_names) == 2:
                            # 取两个板块名称的第一个字组合
                            first_char_1 = sector_names[0][0] if sector_names[0] else ""
                            first_char_2 = sector_names[1][0] if sector_names[1] else ""
                            tab_names[target_group_index] = f"{first_char_1}{first_char_2}"
                        elif len(sector_names) == 1:
                            # 只有一个板块时,取前两个字
                            tab_names[target_group_index] = sector_names[0][:2] if len(sector_names[0]) >= 2 else sector_names[0]
                        # 获取这2个板块的龙头股(每个板块取10个)
                        stocks_for_group = []
                        for i in range(sector_start_idx, sector_end_idx):
                            sector_name, sector_type = all_sectors[i]
                            try:
                                # 获取板块成分股
                                if sector_type == "概念":
                                    stock_list = ak.stock_board_concept_cons_em(symbol=sector_name)
                                else:
                                    stock_list = ak.stock_board_industry_cons_em(symbol=sector_name)
                                if stock_list is not None and not stock_list.empty:
                                    # 获取名称和代码列
                                    name_col = None
                                    code_col = None
                                    pct_col = None
                                    for col in stock_list.columns:
                                        col_str = str(col).lower()
                                        if name_col is None and ('名称' in str(col) or 'name' in col_str):
                                            name_col = col
                                        if code_col is None and ('代码' in str(col) or 'code' in col_str):
                                            code_col = col
                                        if pct_col is None and ('涨跌幅' in str(col) or 'pct' in col_str or 'change' in col_str):
                                            pct_col = col
                                    if name_col and code_col:
                                        # 按涨跌幅排序(如果有涨跌幅列)
                                        if pct_col:
                                            sorted_stocks = stock_list.sort_values(pct_col, ascending=False)
                                        else:
                                            sorted_stocks = stock_list
                                        # 每个板块取前10只龙头股
                                        sector_stock_count = 0
                                        for _, row in sorted_stocks.iterrows():
                                            if sector_stock_count >= 10:
                                                break
                                            stock_name = str(row.get(name_col, '')).strip()
                                            stock_code = str(row.get(code_col, '')).strip()
                                            if stock_name and stock_code:
                                                # 确保代码是6位
                                                stock_code = str(stock_code).zfill(6)
                                                stocks_for_group.append((stock_name, stock_code))
                                                sector_stock_count += 1
                            except Exception as e:
                                print(f"获取板块 {sector_name} 龙头股失败: {e}")
                                continue
                        # 导入到对应的持仓标签(最多20个)
                        if stocks_for_group:
                            holding_stocks, holding_labels, _holding_kelly_results, _holding_low_diff_results = self._get_holding_group_data(target_group_index)
                            # 清空该组的持仓股
                            for i in range(len(holding_stocks)):
                                holding_stocks[i] = None
                            # 导入股票(最多20个)
                            import_count = min(len(stocks_for_group), 20)
                            for i in range(import_count):
                                holding_stocks[i] = stocks_for_group[i]
                                imported_count += 1
                            # 更新显示
                            for i in range(import_count):
                                if i < len(holding_labels):
                                    self._update_holding_label(i, target_group_index)
                            # 保存到配置文件
                            self._save_holdings_to_config(target_group_index)
                            print(f"已导入 {import_count} 个股票到持仓{group_idx+1}(组索引{target_group_index})")
                    # 在主线程中更新标签页名称并显示完成消息
                    def show_complete():
                        # 更新标签页名称
                        # Notebook标签页顺序:仓位(0), 交易(1), 持仓(2), 龙头股(3), etf成分股(4), Main(5), 持仓历史股(6),
                        # AI(7), 持仓1(8), 持仓2(9), ..., 持仓8(15)
                        # group_index 7-14 对应 notebook索引 8-15(group_index + 1)
                        for group_index, new_tab_name in tab_names.items():
                            try:
                                # group_index到notebook_index的映射:
                                # group_index 7 -> notebook_index 8 (持仓1)
                                # group_index 8 -> notebook_index 9 (持仓2)
                                # ...依此类推
                                notebook_index = group_index + 1
                                # 更新标签页名称
                                self.position_trading_notebook.tab(notebook_index, text=new_tab_name)
                                print(f"已更新标签页 group_index={group_index} notebook_index={notebook_index} 名称为: {new_tab_name}")
                            except Exception as e:
                                print(f"更新标签页 {group_index} 名称失败: {e}")
                        # 保存标签页名称到配置文件(将键转换为字符串以便JSON存储)
                        try:
                            tab_names_str_keys = {str(k): v for k, v in tab_names.items()}
                            self.ai_config_manager.config["holding_tab_names"] = tab_names_str_keys
                            self.ai_config_manager.save_config()
                            print("已保存标签页名称到配置文件")
                        except Exception as e:
                            print(f"保存标签页名称失败: {e}")
                        messagebox.showinfo("完成",
                            f"自动导入完成!\n"
                            f"共导入 {imported_count} 个股票到持仓标签1-8\n"
                            f"标签页名称已更新为板块首字组合\n"
                            f"正在执行持仓检测...",
                            parent=self.root)
                        # 自动执行所有导入组的持仓检测,并筛选33%仓位股票到持仓标签页
                        def run_all_checks_and_filter():
                            try:
                                import time
                                # 第一步:执行所有持仓组的检测
                                for group_index in tab_names:
                                    try:
                                        print(f"正在检测持仓组 {group_index}...")
                                        # 直接执行检测逻辑(不使用线程,因为已经在后台线程中)
                                        holding_stocks, _holding_labels, holding_kelly_results, _holding_low_diff_results = self._get_holding_group_data(group_index)
                                        for i, holding in enumerate(holding_stocks):
                                            if holding and i < 20:  # 只检测前20个
                                                stock_name, stock_code = holding
                                                try:
                                                    detection_result = self._three_dimensional_detection(stock_name, stock_code)
                                                    if detection_result['success']:
                                                        kelly_result = detection_result['position']
                                                        ma_status = detection_result['technical']['ma_status']
                                                        is_golden = False
                                                        try:
                                                            is_golden = bool(self._check_golden_stock_recent_20d(stock_code, stock_name or ''))
                                                        except Exception:
                                                            pass
                                                        near_buy, near_sell = False, False
                                                        try:
                                                            near_buy, near_sell = self._holding_sr_buy_sell_from_daily_kline(stock_code)
                                                        except Exception:
                                                            pass
                                                        red_star = False
                                                        try:
                                                            red_star = bool(self._holding_red_star_signal_5d_low_ma1(stock_code))
                                                        except Exception:
                                                            pass
                                                        holding_kelly_results[i] = {
                                                            'ratio': kelly_result['kelly_ratio'],
                                                            'b': kelly_result['b'],
                                                            'p': kelly_result['p'],
                                                            'ma_status': ma_status.copy(),
                                                            'is_golden_stock': is_golden,
                                                            'near_support_buy': near_buy,
                                                            'near_resistance_sell': near_sell,
                                                            'red_star_signal': red_star,
                                                        }
                                                    time.sleep(0.5)  # 避免请求过快
                                                except Exception as e:
                                                    print(f"检测 {stock_name} 失败: {e}")
                                    except Exception as e:
                                        print(f"检测持仓组 {group_index} 失败: {e}")
                                print("所有持仓组检测完成,开始筛选33%仓位股票...")
                                # 第二步:筛选仓位约为33%的股票(0.30-0.36范围)
                                stocks_33_percent = []
                                for group_index in tab_names:
                                    holding_stocks, _, holding_kelly_results, _ = self._get_holding_group_data(group_index)
                                    for i, holding in enumerate(holding_stocks):
                                        if holding and i < 20:
                                            stock_name, stock_code = holding
                                            kelly_result = holding_kelly_results[i] if i < len(holding_kelly_results) else None
                                            if kelly_result:
                                                ratio = kelly_result.get('ratio', 0)
                                                # 筛选仓位约为33%的股票(0.30-0.36范围)
                                                if 0.30 <= ratio <= 0.36:
                                                    stocks_33_percent.append({
                                                        'name': stock_name,
                                                        'code': stock_code,
                                                        'ratio': ratio,
                                                        'group_index': group_index,
                                                        'position_index': i
                                                    })
                                print(f"找到 {len(stocks_33_percent)} 只仓位约33%的股票")
                                # 第三步:将筛选出的股票导入到持仓标签页(group_index=1)
                                if stocks_33_percent:
                                    # 清空持仓标签页
                                    for i in range(len(self.holding_stocks)):
                                        self.holding_stocks[i] = None
                                        self.holding_kelly_results[i] = None
                                    # 导入股票(最多80个)
                                    import_count = min(len(stocks_33_percent), 80)
                                    for i in range(import_count):
                                        stock = stocks_33_percent[i]
                                        self.holding_stocks[i] = (stock['name'], stock['code'])
                                        # 复制凯利结果
                                        _src_holding_stocks, _, src_kelly_results, _ = self._get_holding_group_data(stock['group_index'])
                                        if stock['position_index'] < len(src_kelly_results):
                                            self.holding_kelly_results[i] = src_kelly_results[stock['position_index']]
                                    # 在主线程中更新UI
                                    def update_holding_ui():
                                        # 更新持仓标签页显示
                                        for i in range(import_count):
                                            if i < len(self.holding_labels):
                                                self._update_holding_label(i, check_conditions=True, group_index=1)
                                        # 保存到配置文件
                                        self._save_holdings_to_config(1)
                                        print(f"已导入 {import_count} 只33%仓位股票到持仓标签页")
                                        # 显示完成消息
                                        messagebox.showinfo("筛选完成",
                                            f"持仓检测完成!\n"
                                            f"找到 {len(stocks_33_percent)} 只仓位约33%的股票\n"
                                            f"已导入 {import_count} 只到持仓标签页",
                                            parent=self.root)
                                    self.root.after(0, update_holding_ui)
                                else:
                                    def show_no_result():
                                        messagebox.showinfo("筛选完成",
                                            "持仓检测完成!\n未找到仓位约33%的股票",
                                            parent=self.root)
                                    self.root.after(0, show_no_result)
                            except Exception as e:
                                import traceback
                                print(f"持仓检测失败: {e}\n{traceback.format_exc()}")
                        # 延迟执行持仓检测,避免阻塞UI
                        self.root.after(500, lambda: threading.Thread(target=run_all_checks_and_filter, daemon=True).start())
                    self.root.after(0, show_complete)
                except Exception as e:
                    import traceback
                    error_msg = f"自动导入失败: {e!s}\n{traceback.format_exc()}"
                    print(error_msg)
                    def show_error():
                        messagebox.showerror("错误", error_msg, parent=self.root)
                    self.root.after(0, show_error)
            # 启动后台线程
            threading.Thread(target=import_stocks, daemon=True).start()
        except Exception as e:
            import traceback
            error_msg = f"自动导入失败: {e!s}\n{traceback.format_exc()}"
            print(error_msg)
            messagebox.showerror("错误", error_msg, parent=self.root)

    def _save_crawler_checkbox_state(self, key, state):
        """保存爬取按钮选择框状态"""
        self.crawler_checkbox_states[key] = state
        self.ai_config_manager.config["crawler_checkbox_states"] = self.crawler_checkbox_states
        self.ai_config_manager.save_config()

    def _save_market_nav_checkbox_state(self, key, state):
        """保存市场导航选择框状态"""
        self.market_nav_checkbox_states[key] = state
        self.ai_config_manager.config["market_nav_checkbox_states"] = self.market_nav_checkbox_states
        self.ai_config_manager.save_config()

    def _load_excel_file(self, file_path):
        """加载Excel文件到富媒体编辑器,返回标签页ID"""
        try:
            import pandas as pd
            # 读取Excel文件
            df = pd.read_excel(file_path)
            # 转换为文本
            text_content = df.to_string(index=False)
            # 创建新标签页
            tab_id = self.create_text_tab(f"Excel_{os.path.basename(file_path)}")
            # 插入内容
            if tab_id in self.text_widgets:
                text_widget = self.text_widgets[tab_id]['widget']
                text_widget.insert(tk.END, f"\n{'='*80}\n")
                text_widget.insert(tk.END, f"文件: {os.path.basename(file_path)}\n")
                text_widget.insert(tk.END, f"{'='*80}\n\n")
                text_widget.insert(tk.END, text_content)
                text_widget.see(tk.END)
            return tab_id
        except Exception as e:
            print(f"[加载Excel文件] 失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _save_engine_report(self, stock_var, result_text, win):
        """保存引擎分析报告"""
        import re
        raw = stock_var.get().strip()
        stock_code = ""
        stock_name = raw
        m = re.search(r"(\d{6})", raw)
        if m:
            stock_code = m.group(1)
            stock_name = raw.replace(stock_code, "").replace("(", "").replace(")", "").strip()
        text = result_text.get("1.0", tk.END).strip()
        if not text:
            messagebox.showinfo("提示", "报告为空", parent=win)
            return
        filepath = self._save_analysis_report(stock_code, stock_name, text, "统一分析引擎")
        if filepath:
            messagebox.showinfo("成功", f"报告已保存:\n{filepath}", parent=win)

    def _load_scheduled_skills(self):
        """从 ~/.qclaw/skill_schedule.json 恢复定时任务"""
        import json as _json
        try:
            if not os.path.isfile(self._skill_schedule_path):
                return
            with open(self._skill_schedule_path, "r", encoding="utf-8", errors="ignore") as f:
                data = _json.load(f)
            if isinstance(data, dict) and isinstance(data.get("tasks"), list):
                self._scheduled_skills = data["tasks"]
                # 清空 last_fired(跨天或重启都重置)
                for t in self._scheduled_skills:
                    if "last_fired" not in t or not isinstance(t.get("last_fired"), dict):
                        t["last_fired"] = {}
                    t["last_run"] = t.get("last_run") or ""
            self._log_skill_scheduler(f"已恢复 {len(self._scheduled_skills)} 个定时任务")
        except Exception as e:
            self._log_skill_scheduler(f"定时任务恢复失败: {e}")
            self._scheduled_skills = []

    def _save_scheduled_skills(self):
        """持久化定时任务到 ~/.qclaw/skill_schedule.json"""
        import json as _json
        try:
            payload = {"version": 1, "tasks": self._scheduled_skills, "updated_at": __import__("datetime").datetime.now().isoformat()}
            with open(self._skill_schedule_path, "w", encoding="utf-8") as f:
                _json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"_save_scheduled_skills 失败: {e}")

    def _save_skill_output(self, text_widget, fmt, parent_win):
        """保存Skill运行结果为TXT/Word/图片"""
        from tkinter import filedialog
        text = text_widget.get("1.0", tk.END).strip()
        if not text:
            messagebox.showinfo("提示", "结果为空", parent=parent_win)
            return
        from datetime import datetime as _dt
        ts = _dt.now().strftime("%Y%m%d_%H%M%S")
        if fmt == "txt":
            filepath = filedialog.asksaveasfilename(
                parent=parent_win, defaultextension=".txt",
                initialfile=f"skill结果_{ts}.txt",
                filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
            )
            if not filepath:
                return
            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(text)
                messagebox.showinfo("成功", f"已保存:\n{filepath}", parent=parent_win)
            except Exception as e:
                messagebox.showerror("错误", f"保存失败: {e}", parent=parent_win)
        elif fmt == "docx":
            filepath = filedialog.asksaveasfilename(
                parent=parent_win, defaultextension=".docx",
                initialfile=f"skill结果_{ts}.docx",
                filetypes=[("Word文档", "*.docx")]
            )
            if not filepath:
                return
            try:
                from docx import Document
                doc = Document()
                for line in text.split("\n"):
                    doc.add_paragraph(line)
                doc.save(filepath)
                messagebox.showinfo("成功", f"已保存:\n{filepath}", parent=parent_win)
            except ImportError:
                messagebox.showerror("错误", "python-docx未安装,无法保存Word", parent=parent_win)
            except Exception as e:
                messagebox.showerror("错误", f"保存失败: {e}", parent=parent_win)
        elif fmt == "image":
            filepath = filedialog.asksaveasfilename(
                parent=parent_win, defaultextension=".png",
                initialfile=f"skill结果_{ts}.png",
                filetypes=[("PNG图片", "*.png"), ("JPEG图片", "*.jpg")]
            )
            if not filepath:
                return
            try:

                from PIL import Image, ImageDraw, ImageFont
                img_width = 1080
                padding = 50
                content_width = img_width - padding * 2
                font_size = 26
                line_spacing = 8
                bg_color = (250, 250, 250)
                text_color = (51, 51, 51)
                font_paths = [
                    "/System/Library/Fonts/PingFang.ttc",
                    "/System/Library/Fonts/STHeiti Medium.ttc",
                    "/Library/Fonts/Songti.ttc",
                    "/System/Library/Fonts/Hiragino Sans GB.ttc",
                ]
                font = None
                for fp in font_paths:
                    try:
                        font = ImageFont.truetype(fp, font_size)
                        break
                    except Exception:
                        continue
                if font is None:
                    font = ImageFont.load_default()
                draw_temp = ImageDraw.Draw(Image.new("RGB", (1, 1)))
                wrapped_lines = []
                for raw_line in text.split("\n"):
                    if not raw_line.strip():
                        wrapped_lines.append("")
                        continue
                    current = ""
                    for ch in raw_line:
                        bbox = draw_temp.textbbox((0, 0), current + ch, font=font)
                        if bbox[2] - bbox[0] > content_width:
                            wrapped_lines.append(current)
                            current = ch
                        else:
                            current += ch
                    if current:
                        wrapped_lines.append(current)
                line_height = font_size + line_spacing
                total_height = padding * 2 + len(wrapped_lines) * line_height
                img = Image.new("RGB", (img_width, total_height), bg_color)
                draw = ImageDraw.Draw(img)
                y = padding
                for line in wrapped_lines:
                    draw.text((padding, y), line, fill=text_color, font=font)
                    y += line_height
                img.save(filepath, "PNG")
                img.close()
                try:
                    import subprocess as _sp
                    _sp.run(["osascript", "-e", f'set the clipboard to (read POSIX file "{filepath}")'], timeout=5)
                except Exception:
                    pass
                messagebox.showinfo("成功", f"图片已保存:\n{filepath}\n(已复制到剪贴板)", parent=parent_win)
            except Exception as e:
                messagebox.showerror("错误", f"生成图片失败: {e}", parent=parent_win)


__all__ = ["FileIoMixin"]
