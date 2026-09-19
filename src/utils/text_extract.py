# 迁移自 stockyidong mac003.py ranges=[(2777, 2780), (2781, 2787), (2788, 2817), (2819, 2857), (2858, 2887), (2888, 2908), (2910, 2949), (2950, 2984), (2985, 3009)]
import os
import re
import io
import shutil
import tempfile
import zipfile
from datetime import datetime
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

def clean_html(html_content):
    """清理HTML标签"""
    clean = re.compile('<.*?>')
    return re.sub(clean, '', html_content)

def extract_text_from_html(html_content):
    """从HTML中提取文本"""
    # 清理HTML标签
    text = clean_html(html_content)
    # 清理多余的空白字符
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def is_valid_text(text):
    """检查文本是否有效,过滤乱码"""
    try:
        if not text or len(text.strip()) < 2:
            return False
        # 检查是否包含有效字符
        valid_chars = 0
        total_chars = len(text)
        for char in text:
            if (char.isalnum() or
                '\u4e00' <= char <= '\u9fff' or  # 中文字符
                char in '.,!?;:()[]{}"\'+-*/=<>%$#@& '):  # 常用标点符号
                valid_chars += 1
        # 如果有效字符比例超过70%,认为文本有效
        if total_chars > 0 and valid_chars / total_chars > 0.7:
            return True
        # 检查是否包含明显的乱码模式
        garbled_patterns = [
            r'[aeiou]{3,}',  # 连续元音
            r'[bcdfghjklmnpqrstvwxyz]{4,}',  # 连续辅音
            r'[A-Z]{5,}',  # 连续大写字母
            r'[a-z]{5,}',  # 连续小写字母
        ]
        for pattern in garbled_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return False
        return False
    except Exception as e:
        print(f"文本验证失败: {e}")
        return False

def extract_text_from_docx(docx_path):
    """从Word文档中提取文字,支持中文路径"""
    try:
        if not DOCX_AVAILABLE:
            return "Word文档读取功能不可用,请安装python-docx库"
        # 检查文件是否存在
        if not os.path.exists(docx_path):
            return f"Word文档文件不存在: {docx_path}"
        # 使用临时文件处理中文路径问题
        import shutil
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix='.docx') as temp_file:
            shutil.copy2(docx_path, temp_file.name)
            temp_path = temp_file.name
        try:
            # 读取Word文档
            doc = Document(temp_path)
            text_content = []
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text_content.append(paragraph.text.strip())
            # 读取表格内容
            for table in doc.tables:
                for row in table.rows:
                    row_text = []
                    for cell in row.cells:
                        if cell.text.strip():
                            row_text.append(cell.text.strip())
                    if row_text:
                        text_content.append('\t'.join(row_text))
            return '\n'.join(text_content)
        finally:
            # 清理临时文件
            try:
                os.remove(temp_path)
            except:
                pass
    except Exception as e:
        return f"Word文档读取失败: {e!s}\n\n可能的原因:\n1. 文件损坏或格式不支持\n2. 文件被其他程序占用\n3. 权限不足"

def extract_text_from_excel(excel_path):
    """从Excel文件中提取文字,支持中文路径"""
    try:
        # 检查文件是否存在
        if not os.path.exists(excel_path):
            return f"Excel文件不存在: {excel_path}"
        # 使用临时文件处理中文路径问题
        import shutil
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as temp_file:
            shutil.copy2(excel_path, temp_file.name)
            temp_path = temp_file.name
        try:
            # 读取Excel文件
            df = pd.read_excel(temp_path, sheet_name=None)  # 读取所有工作表
            text_content = []
            for sheet_name, sheet_df in df.items():
                if not sheet_df.empty:
                    # 将DataFrame转换为文本
                    sheet_text = sheet_df.to_string(index=False)
                    text_content.append(f"工作表: {sheet_name}\n{sheet_text}")
            return '\n\n'.join(text_content)
        finally:
            # 清理临时文件
            try:
                os.remove(temp_path)
            except:
                pass
    except Exception as e:
        return f"Excel文件读取失败: {e!s}\n\n可能的原因:\n1. 文件损坏或格式不支持\n2. 文件被其他程序占用\n3. 权限不足"

def extract_text_from_txt(txt_path):
    """从TXT文件中提取文字,支持中文路径和多种编码"""
    try:
        # 检查文件是否存在
        if not os.path.exists(txt_path):
            return f"TXT文件不存在: {txt_path}"
        # 尝试多种编码读取文件
        encodings = ['utf-8', 'gbk', 'gb2312', 'utf-16', 'latin-1']
        content = None
        for encoding in encodings:
            try:
                with open(txt_path, 'r', encoding=encoding) as f:
                    content = f.read()
                break
            except UnicodeDecodeError:
                continue
        if content is None:
            return "无法读取TXT文件,请检查文件编码"
        return content.strip() if content.strip() else "TXT文件为空"
    except Exception as e:
        return f"TXT文件读取失败: {e!s}\n\n可能的原因:\n1. 文件损坏或格式不支持\n2. 文件被其他程序占用\n3. 权限不足"

def extract_text_from_docx(docx_path):
    """从Word文档中提取文字,支持中文路径"""
    try:
        if not DOCX_AVAILABLE:
            return "Word文档读取功能不可用,请安装python-docx库"
        # 检查文件是否存在
        if not os.path.exists(docx_path):
            return f"Word文档文件不存在: {docx_path}"
        # 使用临时文件处理中文路径问题
        import shutil
        import tempfile
        temp_dir = tempfile.mkdtemp()
        temp_docx_path = os.path.join(temp_dir, "temp_doc.docx")
        try:
            # 复制文件到临时目录
            shutil.copy2(docx_path, temp_docx_path)
            doc = Document(temp_docx_path)
            text_content = []
            # 提取段落文字
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text_content.append(paragraph.text.strip())
            # 提取表格文字
            for table in doc.tables:
                for row in table.rows:
                    row_text = []
                    for cell in row.cells:
                        if cell.text.strip():
                            row_text.append(cell.text.strip())
                    if row_text:
                        text_content.append(" | ".join(row_text))
            return "\n".join(text_content) if text_content else "Word文档中没有找到文字内容"
        finally:
            # 清理临时文件
            try:
                shutil.rmtree(temp_dir)
            except:
                pass
    except Exception as e:
        return f"Word文档读取失败: {e!s}\n\n可能的原因:\n1. 文件损坏或格式不支持\n2. 文件被其他程序占用\n3. 权限不足"

def extract_text_from_excel(excel_path):
    """从Excel文件中提取文字,支持中文路径"""
    try:
        # 检查文件是否存在
        if not os.path.exists(excel_path):
            return f"Excel文件不存在: {excel_path}"
        # 使用临时文件处理中文路径问题
        import shutil
        import tempfile
        temp_dir = tempfile.mkdtemp()
        temp_excel_path = os.path.join(temp_dir, "temp_excel.xlsx")
        try:
            # 复制文件到临时目录
            shutil.copy2(excel_path, temp_excel_path)
            # 读取Excel文件
            df = pd.read_excel(temp_excel_path)
            text_content = []
            # 提取所有文本内容
            for col in df.columns:
                if df[col].dtype == 'object':  # 文本类型列
                    col_text = df[col].astype(str).str.cat(sep='\n')
                    if col_text.strip():
                        text_content.append(f"【{col}】\n{col_text}")
            # 如果没有找到文本列,使用整个DataFrame
            if not text_content:
                text_content.append(df.to_string(index=False))
            return "\n\n".join(text_content) if text_content else "Excel文件中没有找到文字内容"
        finally:
            # 清理临时文件
            try:
                shutil.rmtree(temp_dir)
            except:
                pass
    except Exception as e:
        return f"Excel文件读取失败: {e!s}\n\n可能的原因:\n1. 文件损坏或格式不支持\n2. 文件被其他程序占用\n3. 权限不足"

def extract_text_from_txt(txt_path):
    """从TXT文件中提取文字,支持中文路径和多种编码"""
    try:
        # 检查文件是否存在
        if not os.path.exists(txt_path):
            return f"TXT文件不存在: {txt_path}"
        # 尝试多种编码读取文件
        encodings = ['utf-8', 'gbk', 'gb2312', 'utf-16', 'latin-1']
        content = None
        for encoding in encodings:
            try:
                with open(txt_path, 'r', encoding=encoding) as f:
                    content = f.read()
                print(f"成功使用 {encoding} 编码读取TXT文件")
                break
            except UnicodeDecodeError:
                continue
            except Exception as e:
                print(f"使用 {encoding} 编码读取失败: {e}")
                continue
        if content is None:
            return "TXT文件读取失败:无法识别文件编码\n\n支持的编码:UTF-8, GBK, GB2312, UTF-16, Latin-1"
        return content.strip() if content.strip() else "TXT文件为空"
    except Exception as e:
        return f"TXT文件读取失败: {e!s}\n\n可能的原因:\n1. 文件损坏或格式不支持\n2. 文件被其他程序占用\n3. 权限不足"

__all__ = ['clean_html', 'extract_text_from_docx', 'extract_text_from_excel', 'extract_text_from_html', 'extract_text_from_txt', 'is_valid_text']
