# 迁移自 stockyidong mac003.py ranges=[(1493, 1533), (1534, 1546), (1547, 1559), (1562, 1576), (1578, 1592), (1593, 1625), (1626, 1646), (1647, 1666), (1668, 1713), (2016, 2034), (2036, 2038), (2039, 2041), (2042, 2044), (2045, 2104), (2683, 2776)]
import os
import sys
import re
import time
try:
    import akshare as ak
except ImportError:
    ak = None
try:
    import tushare as ts
except ImportError:
    ts = None

def get_hot_stocks(limit=50):
    """获取最热门的股票"""
    try:
        # 定义热门股票代码和名称(备用数据)
        hot_stocks_backup = [
            {'代码': '000001', '名称': '平安银行', '最新价': 0, '涨跌幅': 0, '成交量': 0},
            {'代码': '000002', '名称': '万科A', '最新价': 0, '涨跌幅': 0, '成交量': 0},
            {'代码': '000858', '名称': '五粮液', '最新价': 0, '涨跌幅': 0, '成交量': 0},
            {'代码': '000876', '名称': '新希望', '最新价': 0, '涨跌幅': 0, '成交量': 0},
            {'代码': '002415', '名称': '海康威视', '最新价': 0, '涨跌幅': 0, '成交量': 0},
            {'代码': '002594', '名称': '比亚迪', '最新价': 0, '涨跌幅': 0, '成交量': 0},
            {'代码': '300059', '名称': '东方财富', '最新价': 0, '涨跌幅': 0, '成交量': 0},
            {'代码': '300750', '名称': '宁德时代', '最新价': 0, '涨跌幅': 0, '成交量': 0},
            {'代码': '600036', '名称': '招商银行', '最新价': 0, '涨跌幅': 0, '成交量': 0},
            {'代码': '600519', '名称': '贵州茅台', '最新价': 0, '涨跌幅': 0, '成交量': 0},
            {'代码': '600887', '名称': '伊利股份', '最新价': 0, '涨跌幅': 0, '成交量': 0},
            {'代码': '601318', '名称': '中国平安', '最新价': 0, '涨跌幅': 0, '成交量': 0},
            {'代码': '601398', '名称': '工商银行', '最新价': 0, '涨跌幅': 0, '成交量': 0},
            {'代码': '601939', '名称': '建设银行', '最新价': 0, '涨跌幅': 0, '成交量': 0},
            {'代码': '601988', '名称': '中国银行', '最新价': 0, '涨跌幅': 0, '成交量': 0},
            {'代码': '000166', '名称': '申万宏源', '最新价': 0, '涨跌幅': 0, '成交量': 0},
            {'代码': '000725', '名称': '京东方A', '最新价': 0, '涨跌幅': 0, '成交量': 0},
            {'代码': '002304', '名称': '洋河股份', '最新价': 0, '涨跌幅': 0, '成交量': 0},
            {'代码': '002456', '名称': '欧菲光', '最新价': 0, '涨跌幅': 0, '成交量': 0},
            {'代码': '300015', '名称': '爱尔眼科', '最新价': 0, '涨跌幅': 0, '成交量': 0},
        ]
        # 尝试获取实时股票数据
        try:
            stock_data = ak.stock_zh_a_spot_em()
            if not stock_data.empty:
                # 按成交量降序排列,取前limit个
                hot_stocks = stock_data.nlargest(limit, '成交量')
                return hot_stocks[['代码', '名称', '最新价', '涨跌幅', '成交量']].to_dict('records')
        except Exception as e:
            print(f"获取实时股票数据失败: {e}")
        # 如果实时数据获取失败,返回备用数据
        print("使用备用热门股票数据")
        return hot_stocks_backup[:limit]
    except Exception as e:
        print(f"获取热门股票失败: {e}")
        return []

def get_stock_20day_change(stock_code):
    """获取股票20日涨跌幅"""
    try:
        hist_data = ak.stock_zh_a_hist(symbol=stock_code, period="daily", adjust="qfq")
        if not hist_data.empty and len(hist_data) >= 20:
            current_price = hist_data.iloc[-1]['收盘']
            twenty_days_ago_price = hist_data.iloc[-20]['收盘']
            twenty_day_change = ((current_price - twenty_days_ago_price) / twenty_days_ago_price) * 100
            return round(float(twenty_day_change), 2)
        return 0.0
    except Exception as e:
        print(f"获取 {stock_code} 20日涨跌幅失败: {e}")
        return 0.0

def get_stock_60day_change(stock_code):
    """获取股票60日涨跌幅"""
    try:
        hist_data = ak.stock_zh_a_hist(symbol=stock_code, period="daily", adjust="qfq")
        if not hist_data.empty and len(hist_data) >= 60:
            current_price = hist_data.iloc[-1]['收盘']
            sixty_days_ago_price = hist_data.iloc[-60]['收盘']
            sixty_day_change = ((current_price - sixty_days_ago_price) / sixty_days_ago_price) * 100
            return round(float(sixty_day_change), 2)
        return 0.0
    except Exception as e:
        print(f"获取 {stock_code} 60日涨跌幅失败: {e}")
        return 0.0

def get_stock_weekly_change(stock_name):
    """获取股票周涨跌幅"""
    try:
        stock_code = get_stock_code_by_name(stock_name)
        if stock_code:
            hist_data = ak.stock_zh_a_hist(symbol=stock_code, period="daily", adjust="qfq")
            if not hist_data.empty and len(hist_data) >= 5:
                current_price = hist_data.iloc[-1]['收盘']
                week_ago_price = hist_data.iloc[-5]['收盘']
                weekly_change = ((current_price - week_ago_price) / week_ago_price) * 100
                return float(weekly_change)
        return 0.0
    except Exception as e:
        print(f"获取 {stock_name} 周涨跌幅失败: {e}")
        return 0.0

def get_stock_10day_change(stock_name):
    """获取股票10日涨跌幅"""
    try:
        stock_code = get_stock_code_by_name(stock_name)
        if stock_code:
            hist_data = ak.stock_zh_a_hist(symbol=stock_code, period="daily", adjust="qfq")
            if not hist_data.empty and len(hist_data) >= 10:
                current_price = hist_data.iloc[-1]['收盘']
                ten_days_ago_price = hist_data.iloc[-10]['收盘']
                ten_day_change = ((current_price - ten_days_ago_price) / ten_days_ago_price) * 100
                return round(float(ten_day_change), 2)
        return 0.0
    except Exception as e:
        print(f"获取 {stock_name} 10日涨跌幅失败: {e}")
        return 0.0

def get_stock_recent_10day_daily_changes(stock_code):
    """获取股票最近10个交易日的每日涨跌幅,以及当前价与10日均线的百分比距离。
    返回 (daily_changes, ma10_distance_pct):
    - daily_changes: 长度为10的列表(近1日~近10日),失败为 None
    - ma10_distance_pct: (当前价-10日均线)/10日均线*100,保留2位小数,失败为 None"""
    if not AKSHARE_AVAILABLE or not stock_code:
        return None, None
    try:
        hist_data = ak.stock_zh_a_hist(symbol=stock_code, period="daily", adjust="qfq")
        if hist_data.empty or len(hist_data) < 11:
            return None, None
        hist_data = hist_data.tail(11)
        closes = hist_data['收盘'].astype(float).tolist()
        daily_changes = []
        for i in range(1, len(closes)):
            if closes[i - 1] and closes[i - 1] != 0:
                pct = round((closes[i] - closes[i - 1]) / closes[i - 1] * 100, 2)
                daily_changes.append(pct)
            else:
                daily_changes.append(0.0)
        # 取最近10个交易日的日涨跌幅
        changes_10 = daily_changes[-10:] if len(daily_changes) >= 10 else None
        # 10日均线 = 最近10日收盘价均值,当前价 = 最后一根收盘价;距离% = (当前价 - MA10) / MA10 * 100
        ma10_dist_pct = None
        if len(closes) >= 10:
            last_close = closes[-1]
            ma10 = sum(closes[-10:]) / 10
            if ma10 and ma10 != 0:
                ma10_dist_pct = round((last_close - ma10) / ma10 * 100, 2)
        return changes_10, ma10_dist_pct
    except Exception as e:
        print(f"获取 {stock_code} 最近10日涨跌幅/距10日线失败: {e}")
        return None, None

def get_stock_logic(text, stock_name):
    """提取股票相关的投资逻辑"""
    logic_keywords = [
        '涨停', '跌停', '突破', '回调', '反弹', '利好', '利空', '业绩', '重组',
        '并购', '分红', '增持', '减持', '解禁', '停牌', '复牌', '上涨', '下跌',
        '买入', '卖出', '推荐', '看好', '看空', '机会', '风险', '概念', '热点',
        '龙头', '跟风', '补涨', '补跌', '强势', '弱势', '放量', '缩量', '换手',
        '主力', '资金', '流入', '流出', '拉升', '打压', '洗盘', '出货'
    ]
    # 查找包含股票名称和逻辑关键词的句子
    sentences = re.split(r'[。!?\n]', text)
    logic_sentences = []
    for sentence in sentences:
        if stock_name in sentence:
            for keyword in logic_keywords:
                if keyword in sentence:
                    logic_sentences.append(sentence.strip())
                    break
    if logic_sentences:
        return " | ".join(logic_sentences[:3])
    return "未找到明确逻辑"

def extract_stock_context(text, stock_names):
    """提取股票相关的文本内容"""
    context_dict = {}
    for stock_name in stock_names:
        pattern = f".{{0,150}}{re.escape(stock_name)}.{{0,150}}"
        matches = re.findall(pattern, text)
        if matches:
            clean_contexts = []
            for match in matches:
                clean_match = re.sub(r'<[^>]+>', '', match)
                clean_match = re.sub(r'\s+', ' ', clean_match.strip())
                if len(clean_match) > 20:
                    clean_contexts.append(clean_match)
            if clean_contexts:
                context_dict[stock_name] = clean_contexts[:3]
            else:
                context_dict[stock_name] = ["未找到相关内容"]
        else:
            context_dict[stock_name] = ["未找到相关内容"]
    return context_dict

def get_stock_technical_indicators(stock_name):
    """获取股票技术指标"""
    try:
        # 获取股票代码
        stock_info = ak.stock_info_a_code_name()
        stock_code = None
        for _, row in stock_info.iterrows():
            if row['name'] == stock_name:
                stock_code = row['code']
                break
        if not stock_code:
            return None
        # 获取历史数据
        hist_data = ak.stock_zh_a_hist(symbol=stock_code, period="daily", adjust="qfq")
        if hist_data.empty or len(hist_data) < 30:
            return None
        # 计算技术指标
        close_prices = hist_data['收盘'].values
        high_prices = hist_data['最高'].values
        low_prices = hist_data['最低'].values
        # 计算涨跌幅
        if len(close_prices) >= 2:
            daily_change = ((close_prices[-1] - close_prices[-2]) / close_prices[-2]) * 100
        else:
            daily_change = 0
        # 计算MACD
        macd_value, macd_signal, macd_hist = calculate_macd(close_prices)
        # 计算KDJ
        k_value, d_value, j_value = calculate_kdj(high_prices, low_prices, close_prices)
        # 计算WR
        wr_value = calculate_wr(high_prices, low_prices, close_prices)
        # 计算BIAS
        bias_value = calculate_bias(close_prices)
        return {
            'daily_change': daily_change,
            'macd': macd_value,
            'macd_signal': macd_signal,
            'macd_hist': macd_hist,
            'kdj_k': k_value,
            'kdj_d': d_value,
            'kdj_j': j_value,
            'wr': wr_value,
            'bias': bias_value
        }
    except Exception:
        return None

def get_cached_stock_data(stock_name, data_type, fetch_func, cache_duration=300):
    """获取缓存的股票数据,避免重复网络请求"""
    import time
    cache_key = f"{stock_name}_{data_type}"
    current_time = time.time()
    # 检查缓存是否有效
    if (cache_key in _stock_data_cache and
        cache_key in _cache_timestamp and
        current_time - _cache_timestamp[cache_key] < cache_duration):
        return _stock_data_cache[cache_key]
    # 获取新数据
    try:
        data = fetch_func(stock_name)
        _stock_data_cache[cache_key] = data
        _cache_timestamp[cache_key] = current_time
        return data
    except Exception as e:
        print(f"获取 {stock_name} {data_type} 数据失败: {e}")
        return None

def get_stock_10day_change_cached(stock_name):
    """获取缓存的10日涨跌幅"""
    return get_cached_stock_data(stock_name, "10day", get_stock_10day_change)

def get_stock_20day_change_cached(stock_name):
    """获取缓存的20日涨跌幅"""
    return get_cached_stock_data(stock_name, "20day", get_stock_20day_change)

def get_stock_weekly_change_cached(stock_name):
    """获取缓存的周涨跌幅"""
    return get_cached_stock_data(stock_name, "weekly", get_stock_weekly_change)

def get_stock_30day_data_and_calculate_changes(stock_name):
    """下载股票30日数据并计算各种涨跌幅 - 高效版本"""
    import time
    cache_key = f"{stock_name}_30day_calculated"
    current_time = time.time()
    # 检查缓存是否有效(5分钟)
    if (cache_key in _stock_data_cache and
        cache_key in _cache_timestamp and
        current_time - _cache_timestamp[cache_key] < 300):
        return _stock_data_cache[cache_key]
    try:
        # 获取股票代码
        stock_code = get_stock_code_by_name(stock_name)
        if not stock_code:
            return None
        # 获取30日历史数据
        import akshare as ak
        hist_data = ak.stock_zh_a_hist(symbol=stock_code, period="daily",
                                      start_date="", end_date="", adjust="qfq")
        if hist_data.empty or len(hist_data) < 30:
            return None
        # 取最近30日数据
        recent_30days = hist_data.tail(30)
        # 计算各种涨跌幅
        daily_changes = []
        for i in range(len(recent_30days)):
            if i == 0:
                # 第一天没有前一日数据,设为0
                daily_changes.append(0.0)
            else:
                prev_close = recent_30days.iloc[i-1]['收盘']
                curr_close = recent_30days.iloc[i]['收盘']
                change_pct = ((curr_close - prev_close) / prev_close) * 100
                daily_changes.append(round(change_pct, 2))
        # 计算各种总计涨跌幅
        last_5_days = daily_changes[-5:] if len(daily_changes) >= 5 else daily_changes
        last_10_days = daily_changes[-10:] if len(daily_changes) >= 10 else daily_changes
        last_20_days = daily_changes[-20:] if len(daily_changes) >= 20 else daily_changes
        five_day_total = round(sum(last_5_days), 2)
        ten_day_total = round(sum(last_10_days), 2)
        twenty_day_total = round(sum(last_20_days), 2)
        # 周涨跌幅(最近5个交易日)
        weekly_change = five_day_total
        result = {
            'daily_changes_5days': last_5_days,
            'five_day_total': five_day_total,
            'ten_day_total': ten_day_total,
            'twenty_day_total': twenty_day_total,
            'weekly_change': weekly_change,
            'all_daily_changes': daily_changes,
            'stock_code': stock_code
        }
        # 缓存结果
        _stock_data_cache[cache_key] = result
        _cache_timestamp[cache_key] = current_time
        print(f"✅ {stock_name} 30日数据下载完成,计算涨跌幅成功")
        return result
    except Exception as e:
        _log(f"❌ {stock_name} 30日数据下载失败: {e}")
        return None

def get_stock_basic_info(stock_name):
    """获取股票基本信息,包括财务、价格及筹码成本"""
    try:
        stock_code = get_stock_code_by_name(stock_name)
        if not stock_code:
            return None
        info = {'stock_code': stock_code}
        def safe_float(value):
            if value is None or value == '':
                return None
            try:
                return float(str(value).replace(',', ''))
            except Exception:
                return None
        spot_row = get_realtime_spot_row(stock_code)
        if spot_row is not None:
            info['current_price'] = safe_float(spot_row.get('最新价'))
            info['change_pct'] = safe_float(spot_row.get('涨跌幅'))
            info['turnover_rate'] = safe_float(spot_row.get('换手率'))
            info['pe'] = safe_float(spot_row.get('市盈率-动态') or spot_row.get('市盈率'))
            info['pb'] = safe_float(spot_row.get('市净率'))
            info['market_cap'] = safe_float(spot_row.get('总市值') or spot_row.get('市值'))
        hist = None
        try:
            hist = ak.stock_zh_a_hist(symbol=stock_code, period="daily", adjust="qfq")
        except Exception as err:
            print(f"获取 {stock_name} 历史数据失败: {err}")
            hist = None
        if hist is not None and not hist.empty:
            closes = pd.to_numeric(hist['收盘'], errors='coerce').dropna()
            opens = pd.to_numeric(hist['开盘'], errors='coerce').dropna()
            highs = pd.to_numeric(hist['最高'], errors='coerce').dropna()
            lows = pd.to_numeric(hist['最低'], errors='coerce').dropna()
            volumes = pd.to_numeric(hist['成交量'], errors='coerce').dropna()
            dates = hist['日期'].tolist() if '日期' in hist.columns else []
            if not closes.empty:
                info.setdefault('current_price', float(closes.iloc[-1]))
                if info.get('change_pct') is None and len(closes) >= 2:
                    prev_price = closes.iloc[-2]
                    if prev_price:
                        info['change_pct'] = round((closes.iloc[-1] - prev_price) / prev_price * 100, 2)
                # 最近5天的涨跌幅
                if len(closes) >= 5:
                    recent_5_days = []
                    for i in range(min(5, len(closes))):
                        idx = len(closes) - 1 - i
                        if idx > 0:
                            prev_close = closes.iloc[idx - 1]
                            curr_close = closes.iloc[idx]
                            if prev_close and curr_close:
                                change_pct = round((curr_close - prev_close) / prev_close * 100, 2)
                                date_str = dates[idx] if idx < len(dates) else f"第{i+1}天前"
                                recent_5_days.append({
                                    'date': date_str,
                                    'close': round(float(curr_close), 2),
                                    'change_pct': change_pct
                                })
                    info['recent_5_days'] = list(reversed(recent_5_days))  # 按时间正序
                    # 5日前涨跌幅
                    week_close = closes.iloc[-5]
                    if week_close:
                        info['weekly_change'] = round((closes.iloc[-1] - week_close) / week_close * 100, 2)
                # 筹码成本均价(20日均价)
                if len(closes) >= 20:
                    info['chip_cost'] = round(float(closes.tail(20).mean()), 2)
                elif len(closes) >= 5:
                    info['chip_cost'] = round(float(closes.tail(5).mean()), 2)
                # 日K线数据(最近30天)
                if len(closes) >= 1:
                    kline_data = []
                    for i in range(min(30, len(closes))):
                        idx = len(closes) - 1 - i
                        kline_item = {
                            'date': dates[idx] if idx < len(dates) else f"第{i+1}天前",
                            'open': round(float(opens.iloc[idx]), 2) if idx < len(opens) else None,
                            'high': round(float(highs.iloc[idx]), 2) if idx < len(highs) else None,
                            'low': round(float(lows.iloc[idx]), 2) if idx < len(lows) else None,
                            'close': round(float(closes.iloc[idx]), 2),
                            'volume': round(float(volumes.iloc[idx]), 0) if idx < len(volumes) else None
                        }
                        kline_data.append(kline_item)
                    info['kline_data'] = list(reversed(kline_data))  # 按时间正序
        if 'weekly_change' not in info or info.get('weekly_change') is None:
            try:
                info['weekly_change'] = round(get_stock_weekly_change_cached(stock_name) or 0, 2)
            except Exception:
                info['weekly_change'] = None
        if info.get('chip_cost') is None and info.get('current_price') is not None:
            info['chip_cost'] = info['current_price']
        info['update_time'] = datetime.now().strftime("%Y-%m-%d %H:%M")
        return info
    except Exception as e:
        print(f"获取股票 {stock_name} 基本信息失败: {e}")
        return None

__all__ = ['extract_stock_context', 'get_cached_stock_data', 'get_hot_stocks', 'get_stock_10day_change', 'get_stock_10day_change_cached', 'get_stock_20day_change', 'get_stock_20day_change_cached', 'get_stock_30day_data_and_calculate_changes', 'get_stock_60day_change', 'get_stock_basic_info', 'get_stock_logic', 'get_stock_recent_10day_daily_changes', 'get_stock_technical_indicators', 'get_stock_weekly_change', 'get_stock_weekly_change_cached']
