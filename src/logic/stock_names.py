try:
    import jieba
except ImportError:
    jieba = None
# 迁移自 stockyidong mac003.py ranges=[(1007, 1024), (1025, 1029), (1030, 1235), (1236, 1361), (1362, 1382), (1383, 1392), (1393, 1438), (1439, 1490)]
import os
import sys
import re
import json
import time
import sqlite3
from collections import Counter
from utils.config import D_DATA_DIR, STOCK_NAMES_SET, STOCK_CODES_DICT, STOCK_NAME_TO_CODE, ETF_CACHE_REFRESHED, STOCK_NAMES_LOAD_LOCK, AKSHARE_AVAILABLE

def _register_stock_entry(code, name):
    """将股票代码与名称写入全局缓存"""
    global STOCK_NAMES_SET, STOCK_CODES_DICT, STOCK_NAME_TO_CODE
    if STOCK_NAMES_SET is None:
        STOCK_NAMES_SET = set()
    if STOCK_CODES_DICT is None:
        STOCK_CODES_DICT = {}
    if STOCK_NAME_TO_CODE is None:
        STOCK_NAME_TO_CODE = {}
    if code is None or name is None:
        return
    code_str = str(code).strip()
    name_str = str(name).strip()
    if not code_str or not name_str:
        return
    STOCK_NAMES_SET.add(name_str)
    STOCK_CODES_DICT[code_str] = name_str
    STOCK_NAME_TO_CODE[name_str] = code_str

def load_stock_names():
    """延迟加载A股股票名称集合和代码字典,包括科创板、ETF,支持本地缓存"""
    global STOCK_NAMES_SET, STOCK_CODES_DICT, STOCK_NAME_TO_CODE, ETF_CACHE_REFRESHED
    with STOCK_NAMES_LOAD_LOCK:
        return _load_stock_names_impl()

def _load_stock_names_impl():
    """load_stock_names 的实际逻辑(在锁内调用)"""
    global STOCK_NAMES_SET, STOCK_CODES_DICT, STOCK_NAME_TO_CODE, ETF_CACHE_REFRESHED
    if STOCK_NAMES_SET is None or STOCK_CODES_DICT is None or STOCK_NAME_TO_CODE is None:
        # 缓存文件路径
        cache_file = os.path.join(D_DATA_DIR, "stock_names_cache.json")
        # 首先尝试从缓存文件加载
        if os.path.exists(cache_file):
            try:
                print("正在从本地缓存加载股票名称数据...")
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    STOCK_NAMES_SET = set(cache_data.get('stock_names', []))
                    STOCK_CODES_DICT = cache_data.get('stock_codes_dict', {})
                    STOCK_NAME_TO_CODE = cache_data.get('stock_name_to_code', {})
                    cache_count = len(STOCK_NAMES_SET)
                    # 检查缓存数据是否完整(A股市场应该有4000+只股票)
                    MIN_STOCK_COUNT = 4000
                    if cache_count > 0 and cache_count < MIN_STOCK_COUNT:
                        print(f"⚠️ 警告: 缓存中只有 {cache_count} 个股票名称,数据可能不完整")
                        print(f"   正常应该有 {MIN_STOCK_COUNT}+ 个股票,将重新从网络加载完整数据...")
                        # 清空缓存数据,强制从网络重新加载
                        STOCK_NAMES_SET = None
                        STOCK_CODES_DICT = None
                        STOCK_NAME_TO_CODE = None
                    elif STOCK_NAMES_SET and STOCK_CODES_DICT:
                        print(f"✓ 从缓存成功加载 {cache_count} 个股票名称")
                        # 将所有股票名称添加到jieba自定义词典,提高识别率
                        try:
                            for stock_name in STOCK_NAMES_SET:
                                jieba.add_word(stock_name, freq=1000, tag='n')
                            print(f"✓ 已将 {cache_count} 个股票名称添加到jieba自定义词典")
                        except Exception as e:
                            print(f"添加到jieba自定义词典失败: {e}")
                        return STOCK_NAMES_SET, STOCK_CODES_DICT, STOCK_NAME_TO_CODE
            except Exception as e:
                print(f"从缓存加载失败: {e},将尝试从网络获取")
        # 如果缓存不存在或加载失败,尝试从网络获取
        if not AKSHARE_AVAILABLE:
            print("错误: akshare库不可用,无法加载股票数据")
            print("提示: 请确保已安装akshare库,并且网络连接正常")
            STOCK_NAMES_SET = set()
            STOCK_CODES_DICT = {}
            STOCK_NAME_TO_CODE = {}
            ETF_CACHE_REFRESHED = False
            return STOCK_NAMES_SET, STOCK_CODES_DICT, STOCK_NAME_TO_CODE
        print("正在从网络加载A股股票名称列表(包括主板、中小板、创业板、科创板、ETF),请稍候...")
        print("说明:A股市场约有5000+只股票,首次加载需要一些时间,这是正常现象。")
        print("提示:如果网络连接失败,程序将尝试使用缓存数据")
        try:
            STOCK_NAMES_SET = set()
            STOCK_CODES_DICT = {}
            STOCK_NAME_TO_CODE = {}
            # 加载主板、中小板、创业板股票
            main_count = 0
            try:
                print("正在加载主板、中小板、创业板股票...")
                stock_info = ak.stock_info_a_code_name()
                if stock_info is not None and not stock_info.empty:
                    for _, row in stock_info.iterrows():
                        code = row.get('code')
                        name = row.get('name')
                        if code and name:
                            _register_stock_entry(code, name)
                            main_count += 1
                    print(f"✓ 成功加载主板/中小板/创业板股票 {main_count} 个")
                else:
                    print("⚠️ 主板/中小板/创业板股票数据为空")
            except Exception as e:
                _log(f"❌ 加载主板/中小板/创业板股票失败: {e}")
            # 加载科创板股票
            kcb_count = 0
            try:
                print("正在加载科创板股票...")
                kcb_stock_info = ak.stock_info_kcb_name_code()
                if kcb_stock_info is not None and not kcb_stock_info.empty:
                    for _, row in kcb_stock_info.iterrows():
                        code = row.get('SECURITY_CODE_A')
                        name = row.get('SECURITY_NAME_A')
                        if code and name:
                            _register_stock_entry(code, name)
                        kcb_count += 1
                    print(f"✓ 成功加载科创板股票 {kcb_count} 个")
                else:
                    print("⚠️ 科创板股票数据为空")
            except Exception as e:
                _log(f"❌ 加载科创板股票失败: {e}")
            # 加载ETF(可选,如果不需要可以跳过)
            etf_count = 0
            try:
                print("正在加载ETF基金...")
                etf_info = ak.fund_etf_spot_em()
                if etf_info is not None and not etf_info.empty:
                    for _, row in etf_info.iterrows():
                        code = row.get('代码')
                        name = row.get('名称')
                        if code and name:
                            _register_stock_entry(code, name)
                        etf_count += 1
                    ETF_CACHE_REFRESHED = True
                    print(f"✓ 成功加载ETF {etf_count} 个")
                else:
                    print("⚠️ ETF基金数据为空")
                    ETF_CACHE_REFRESHED = False
            except Exception as e:
                _log(f"❌ 加载ETF失败: {e}")
                ETF_CACHE_REFRESHED = False
            total_count = len(STOCK_NAMES_SET)
            if total_count > 0:
                # 检查数据完整性
                MIN_EXPECTED_COUNT = 4000
                if total_count < MIN_EXPECTED_COUNT:
                    print(f"⚠️ 警告: 只加载了 {total_count} 个股票名称,可能数据不完整")
                    print(f"   正常应该有 {MIN_EXPECTED_COUNT}+ 个股票")
                    print("   建议检查网络连接,或手动删除缓存文件后重新加载")
                else:
                    print(f"✓ 成功加载 {total_count} 个A股股票名称(包括科创板、ETF)")
                    print("  说明:这是A股市场的正常数量,包括主板、中小板、创业板、科创板股票和ETF基金")
                # 将所有股票名称添加到jieba自定义词典,提高识别率
                try:
                    for stock_name in STOCK_NAMES_SET:
                        jieba.add_word(stock_name, freq=1000, tag='n')
                    print(f"✓ 已将 {total_count} 个股票名称添加到jieba自定义词典")
                except Exception as e:
                    print(f"添加到jieba自定义词典失败: {e}")
                # 保存到缓存文件
                try:
                    cache_data = {
                        'stock_names': list(STOCK_NAMES_SET),
                        'stock_codes_dict': STOCK_CODES_DICT,
                        'stock_name_to_code': STOCK_NAME_TO_CODE,
                        'cache_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'total_count': total_count
                    }
                    with open(cache_file, 'w', encoding='utf-8') as f:
                        json.dump(cache_data, f, ensure_ascii=False, indent=2)
                    print(f"✓ 股票数据已保存到缓存文件: {cache_file}")
                except Exception as e:
                    print(f"保存缓存文件失败: {e}")
            else:
                print("警告: 未能加载任何股票数据")
                # 如果网络加载失败,再次尝试从缓存加载
                if os.path.exists(cache_file):
                    try:
                        print("网络加载失败,尝试从缓存加载...")
                        with open(cache_file, 'r', encoding='utf-8') as f:
                            cache_data = json.load(f)
                            STOCK_NAMES_SET = set(cache_data.get('stock_names', []))
                            STOCK_CODES_DICT = cache_data.get('stock_codes_dict', {})
                            STOCK_NAME_TO_CODE = cache_data.get('stock_name_to_code', {})
                            cache_count = len(STOCK_NAMES_SET)
                            if STOCK_NAMES_SET and STOCK_CODES_DICT:
                                if cache_count < 4000:
                                    print(f"⚠️ 从缓存加载了 {cache_count} 个股票名称,但数据可能不完整(正常应该有4000+个)")
                                else:
                                    print(f"✓ 从缓存成功加载 {cache_count} 个股票名称")
                                # 将所有股票名称添加到jieba自定义词典,提高识别率
                                try:
                                    for stock_name in STOCK_NAMES_SET:
                                        jieba.add_word(stock_name, freq=1000, tag='n')
                                    print(f"✓ 已将 {cache_count} 个股票名称添加到jieba自定义词典")
                                except Exception as e:
                                    print(f"添加到jieba自定义词典失败: {e}")
                    except Exception as e:
                        print(f"从缓存加载也失败: {e}")
        except Exception as e:
            print(f"加载股票名称失败: {e}")
            print("提示: 可能是网络连接问题,程序将尝试使用缓存数据")
            # 最后尝试从缓存加载
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        cache_data = json.load(f)
                        STOCK_NAMES_SET = set(cache_data.get('stock_names', []))
                        STOCK_CODES_DICT = cache_data.get('stock_codes_dict', {})
                        STOCK_NAME_TO_CODE = cache_data.get('stock_name_to_code', {})
                        cache_count = len(STOCK_NAMES_SET)
                        if STOCK_NAMES_SET and STOCK_CODES_DICT:
                            if cache_count < 4000:
                                print(f"⚠️ 从缓存加载了 {cache_count} 个股票名称,但数据可能不完整(正常应该有4000+个)")
                            else:
                                print(f"✓ 从缓存成功加载 {cache_count} 个股票名称")
                            # 将所有股票名称添加到jieba自定义词典,提高识别率
                            try:
                                for stock_name in STOCK_NAMES_SET:
                                    jieba.add_word(stock_name, freq=1000, tag='n')
                                print(f"✓ 已将 {cache_count} 个股票名称添加到jieba自定义词典")
                            except Exception as e:
                                print(f"添加到jieba自定义词典失败: {e}")
                        else:
                            STOCK_NAMES_SET = set()
                            STOCK_CODES_DICT = {}
                            STOCK_NAME_TO_CODE = {}
                            ETF_CACHE_REFRESHED = False
                except Exception as e2:
                    print(f"从缓存加载失败: {e2}")
                    STOCK_NAMES_SET = set()
                    STOCK_CODES_DICT = {}
                    STOCK_NAME_TO_CODE = {}
                    ETF_CACHE_REFRESHED = False
            else:
                STOCK_NAMES_SET = set()
                STOCK_CODES_DICT = {}
                STOCK_NAME_TO_CODE = {}
                ETF_CACHE_REFRESHED = False
    return STOCK_NAMES_SET, STOCK_CODES_DICT, STOCK_NAME_TO_CODE

def extract_stock_names(text):
    """从文本中提取股票名称和代码"""
    global STOCK_NAMES_SET, STOCK_CODES_DICT
    # 检查输入文本是否为空
    if not text or not text.strip():
        return [], []
    # 确保股票数据已加载
    if STOCK_NAMES_SET is None or STOCK_CODES_DICT is None:
        try:
            STOCK_NAMES_SET, STOCK_CODES_DICT, _ = load_stock_names()
        except Exception as e:
            print(f"加载股票名称数据失败: {e}")
            return [], []
    # 检查数据是否加载成功
    if not STOCK_NAMES_SET or not STOCK_CODES_DICT:
        error_msg = "警告: 股票名称数据为空,无法提取股票信息\n"
        error_msg += "可能原因:\n"
        error_msg += "1. 网络连接失败,无法从akshare获取数据\n"
        error_msg += "2. akshare库未正确安装或配置\n"
        error_msg += "3. 缓存文件不存在或已损坏\n"
        error_msg += "建议:\n"
        error_msg += "1. 检查网络连接\n"
        error_msg += "2. 确保程序有网络访问权限\n"
        error_msg += "3. 重新运行程序,让程序从网络获取并缓存数据\n"
        print(error_msg)
        return [], []
    # 过滤股票名称和代码
    stock_names = []
    stock_codes_found = []
    stock_code_positions = []  # 记录股票代码在文本中的位置
    found_positions = set()  # 记录已找到的位置,避免重复匹配
    # 1. 用正则表达式直接查找6位数字(股票代码)
    # 这样可以避免jieba分词把股票代码分割的问题
    stock_code_pattern = r'(\d{6})'
    stock_codes_in_text = re.findall(stock_code_pattern, text)
    for code in stock_codes_in_text:
        if code in STOCK_CODES_DICT:
            stock_name = STOCK_CODES_DICT[code]
            stock_codes_found.append(f"{code}({stock_name})")
            # 同时添加到股票名称列表(如果还没有的话)
            if stock_name not in stock_names:
                stock_names.append(stock_name)
            # 记录股票代码在文本中的位置
            start_pos = text.find(code)
            if start_pos != -1:
                stock_code_positions.append({
                    'code': code,
                    'name': stock_name,
                    'start': start_pos,
                    'end': start_pos + 6
                })
                # 标记这段位置已被占用
                found_positions.add((start_pos, start_pos + 6))
    # 2. 直接在文本中搜索股票名称(按长度从长到短排序,优先匹配长名称)
    # 这样可以避免短名称误匹配长名称的一部分
    sorted_stock_names = sorted(STOCK_NAMES_SET, key=len, reverse=True)
    for stock_name in sorted_stock_names:
        # 跳过已经在股票代码中找到的股票名称
        if stock_name in stock_names:
            continue
        # 在文本中搜索股票名称
        start_pos = 0
        while True:
            pos = text.find(stock_name, start_pos)
            if pos == -1:
                break
            # 检查这个位置是否已被其他匹配占用
            is_overlap = False
            for found_start, found_end in found_positions:
                if not (pos + len(stock_name) <= found_start or pos >= found_end):
                    is_overlap = True
                    break
            if not is_overlap:
                # 检查股票名称前后是否是有效的边界(避免部分匹配)
                before_char = text[pos - 1] if pos > 0 else ''
                after_char = text[pos + len(stock_name)] if pos + len(stock_name) < len(text) else ''
                # 判断是否是中文字符
                def is_chinese_char(char):
                    """判断是否是中文字符"""
                    if not char:
                        return False
                    return '\u4e00' <= char <= '\u9fff'
                # 判断是否是有效的边界字符(标点、空格等)
                def is_valid_boundary_char(char):
                    """判断是否是有效的边界字符(标点、空格等)"""
                    if not char:
                        return True
                    # 允许的边界:标点符号、空格、换行、制表符等
                    boundary_chars = ' \n\t\r,。!?;:、""''()【】《》〈〉「」『』〔〕...-·'
                    return char in boundary_chars or not (char.isalnum() or is_chinese_char(char))
                # 检查前边界:文本开头、边界字符、或前后字符类型不同
                valid_before = (pos == 0 or
                               is_valid_boundary_char(before_char) or
                               (is_chinese_char(stock_name[0]) and not is_chinese_char(before_char)) or
                               (not is_chinese_char(stock_name[0]) and not before_char.isalnum()))
                # 检查后边界:文本结尾、边界字符、或前后字符类型不同
                valid_after = (pos + len(stock_name) == len(text) or
                              is_valid_boundary_char(after_char) or
                              (is_chinese_char(stock_name[-1]) and not is_chinese_char(after_char)) or
                              (not is_chinese_char(stock_name[-1]) and not after_char.isalnum()))
                if valid_before and valid_after:
                    stock_names.append(stock_name)
                    found_positions.add((pos, pos + len(stock_name)))
                    break  # 每个股票名称只匹配一次,避免重复
            start_pos = pos + 1
    # 3. 使用jieba分词作为补充(处理jieba能正确识别的情况)
    try:
        words = jieba.lcut(text)
        for word in words:
            if word in STOCK_NAMES_SET and word not in stock_names:
                # 检查是否与已找到的位置重叠
                word_pos = text.find(word)
                if word_pos != -1:
                    is_overlap = False
                    for found_start, found_end in found_positions:
                        if not (word_pos + len(word) <= found_start or word_pos >= found_end):
                            is_overlap = True
                            break
                    if not is_overlap:
                        stock_names.append(word)
                        found_positions.add((word_pos, word_pos + len(word)))
    except Exception as e:
        print(f"分词失败: {e}")
    # 合并结果
    all_stocks = stock_names + stock_codes_found
    return list(set(all_stocks)), stock_code_positions

def get_stock_sector(stock_name):
    """获取股票所属板块"""
    try:
        # 先获取股票代码
        stock_info = ak.stock_info_a_code_name()
        stock_code = None
        for _, row in stock_info.iterrows():
            if row['name'] == stock_name:
                stock_code = row['code']
                break
        if stock_code:
            # 使用股票代码获取详细信息
            individual_info = ak.stock_individual_info_em(symbol=stock_code)
            if not individual_info.empty:
                for _, row in individual_info.iterrows():
                    if row['item'] == '所处行业':
                        return row['value']
        return "未知板块"
    except Exception as e:
        print(f"获取 {stock_name} 板块信息失败: {e}")
        return "未知板块"

def get_stock_theme(stock_name):
    """获取股票相关题材"""
    try:
        concept_info = ak.stock_board_concept_cons_ths(symbol=stock_name)
        if not concept_info.empty:
            concepts = concept_info['概念名称'].head(5).tolist()
            return ", ".join(concepts)
        return "未知题材"
    except Exception:
        return "未知题材"

def get_stock_code_by_name(stock_name):
    """根据股票名称获取股票代码,包括ETF"""
    global STOCK_NAMES_SET, STOCK_CODES_DICT, STOCK_NAME_TO_CODE, ETF_CACHE_REFRESHED
    if not stock_name:
        return None
    try:
        if STOCK_NAMES_SET is None or STOCK_CODES_DICT is None or STOCK_NAME_TO_CODE is None:
            load_stock_names()
        # 处理格式:允许传入"代码(名称)"或直接代码
        clean_stock_name = str(stock_name).strip()
        if not clean_stock_name:
            return None
        if '(' in clean_stock_name and ')' in clean_stock_name:
            clean_stock_name = clean_stock_name.split('(')[0].strip() or clean_stock_name.split('(')[1].rstrip(')')
        if re.fullmatch(r"\d{6}", clean_stock_name):
            return clean_stock_name
        # 先使用缓存做精确匹配
        cached_code = STOCK_NAME_TO_CODE.get(clean_stock_name)
        if cached_code:
            return cached_code
        # 其次尝试模糊匹配
        for name, code in STOCK_NAME_TO_CODE.items():
            if clean_stock_name in name or name in clean_stock_name:
                return code
        # 如果仍未找到,尝试补充ETF缓存(仅重试一次,避免频繁请求)
        if not ETF_CACHE_REFRESHED:
            try:
                etf_info = ak.fund_etf_spot_em()
                if etf_info is not None and not etf_info.empty:
                    for _, row in etf_info.iterrows():
                        _register_stock_entry(row.get('代码'), row.get('名称'))
                ETF_CACHE_REFRESHED = True
            except Exception as e:
                ETF_CACHE_REFRESHED = True
                print(f"从ETF中查找 {stock_name} 失败: {e}")
            # 重试匹配
            cached_code = STOCK_NAME_TO_CODE.get(clean_stock_name)
            if cached_code:
                return cached_code
            for name, code in STOCK_NAME_TO_CODE.items():
                if clean_stock_name in name or name in clean_stock_name:
                    return code
        return None
    except Exception as e:
        print(f"获取 {stock_name} 股票代码失败: {e}")
        return None

def get_stock_name_by_code(stock_code):
    """根据股票代码获取股票名称"""
    global STOCK_CODES_DICT, STOCK_NAME_TO_CODE
    if not stock_code:
        return None
    try:
        if STOCK_CODES_DICT is None or STOCK_NAME_TO_CODE is None:
            load_stock_names()
        # 先尝试从STOCK_CODES_DICT获取
        if STOCK_CODES_DICT and stock_code in STOCK_CODES_DICT:
            return STOCK_CODES_DICT[stock_code]
        # 从STOCK_NAME_TO_CODE反向查找
        if STOCK_NAME_TO_CODE:
            for name, code in STOCK_NAME_TO_CODE.items():
                if code == stock_code:
                    return name
        # 如果还没找到,尝试从akshare获取
        if AKSHARE_AVAILABLE:
            try:
                # 方法1: 从stock_info_a_code_name获取
                stock_info = ak.stock_info_a_code_name()
                if not stock_info.empty:
                    matched = stock_info[stock_info['code'] == stock_code]
                    if not matched.empty:
                        stock_name = matched.iloc[0]['name']
                        if stock_name:
                            # 缓存结果
                            if STOCK_CODES_DICT is None:
                                STOCK_CODES_DICT = {}
                            STOCK_CODES_DICT[stock_code] = stock_name
                            return stock_name
            except:
                pass
            try:
                # 方法2: 从stock_individual_info_em获取
                stock_info = ak.stock_individual_info_em(symbol=stock_code)
                if not stock_info.empty:
                    name_row = stock_info[stock_info['item'] == '股票简称']
                    if not name_row.empty:
                        stock_name = name_row.iloc[0]['value']
                        if stock_name:
                            # 缓存结果
                            if STOCK_CODES_DICT is None:
                                STOCK_CODES_DICT = {}
                            STOCK_CODES_DICT[stock_code] = stock_name
                            return stock_name
            except:
                pass
        return None
    except Exception as e:
        print(f"获取 {stock_code} 股票名称失败: {e}")
        return None

__all__ = ['_load_stock_names_impl', '_register_stock_entry', 'extract_stock_names', 'get_stock_code_by_name', 'get_stock_name_by_code', 'get_stock_sector', 'get_stock_theme', 'load_stock_names']
