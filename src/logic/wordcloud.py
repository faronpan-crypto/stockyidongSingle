# 迁移自 stockyidong mac003.py ranges=[(2105, 2181), (2182, 2277), (2278, 2423), (2424, 2682)]
import os
import sys
import re
import io
import base64
import threading
import warnings
from collections import Counter
try:
    import jieba
except ImportError:
    jieba = None
try:
    import matplotlib
    matplotlib.use('TkAgg')
    import matplotlib.pyplot as plt
except ImportError:
    plt = None
try:
    import numpy as np
except ImportError:
    np = None
try:
    import pandas as pd
except ImportError:
    pd = None
try:
    from wordcloud import WordCloud
except ImportError:
    WordCloud = None
try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = None

def analyze_text_dimensions(text):
    """多维度文本分析 - 情绪、市场焦点、风险识别等"""
    try:
        # 情绪分析关键词
        positive_words = ['上涨', '涨停', '突破', '利好', '买入', '推荐', '看好', '机会',
                         '强势', '拉升', '反弹', '上涨', '增长', '盈利', '收益', '成功']
        negative_words = ['下跌', '跌停', '回调', '利空', '卖出', '看空', '风险', '亏损',
                         '弱势', '打压', '洗盘', '出货', '下跌', '下降', '失败', '亏损']
        neutral_words = ['震荡', '整理', '横盘', '观望', '中性', '平衡']
        # 市场焦点关键词
        market_focus_keywords = ['热点', '概念', '题材', '板块', '龙头', '跟风', '补涨',
                                '补跌', '轮动', '切换', '主线', '支线']
        # 风险识别关键词
        risk_keywords = ['风险', '警告', '谨慎', '注意', '警惕', '危险', '不利', '负面',
                        '利空', '减持', '解禁', '停牌', '退市', 'ST', '退市风险']
        # 热门主题关键词
        theme_keywords = ['人工智能', 'AI', '芯片', '半导体', '新能源', '光伏', '风电',
                         '储能', '锂电池', '新能源汽车', '5G', '云计算', '大数据',
                         '区块链', '元宇宙', 'VR', 'AR', '消费', '医药', '军工']
        # 市场状况关键词
        market_status_keywords = {
            '恐慌': ['恐慌', '恐慌性', '恐慌情绪', '恐慌抛售', '恐慌性下跌'],
            '乐观': ['乐观', '乐观情绪', '乐观预期', '乐观态度', '乐观展望'],
            '谨慎': ['谨慎', '谨慎态度', '谨慎观望', '谨慎操作', '谨慎乐观'],
            '狂热': ['狂热', '狂热情绪', '狂热追捧', '狂热买入', '狂热上涨']
        }
        # 统计关键词出现次数
        text_lower = text.lower()
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)
        neutral_count = sum(1 for word in neutral_words if word in text_lower)
        market_focus_count = sum(1 for word in market_focus_keywords if word in text_lower)
        risk_count = sum(1 for word in risk_keywords if word in text_lower)
        theme_counts = {theme: text_lower.count(theme.lower()) for theme in theme_keywords}
        theme_counts = {k: v for k, v in theme_counts.items() if v > 0}
        # 判断情绪倾向
        total_sentiment = positive_count + negative_count + neutral_count
        if total_sentiment > 0:
            positive_ratio = positive_count / total_sentiment
            negative_ratio = negative_count / total_sentiment
            if positive_ratio > 0.6:
                sentiment = "积极"
            elif negative_ratio > 0.6:
                sentiment = "消极"
            elif positive_ratio > negative_ratio:
                sentiment = "偏积极"
            elif negative_ratio > positive_ratio:
                sentiment = "偏消极"
            else:
                sentiment = "中性"
        else:
            sentiment = "中性"
        # 判断市场状况
        market_status = "正常"
        for status, keywords in market_status_keywords.items():
            if any(kw in text_lower for kw in keywords):
                market_status = status
                break
        # 构建分析结果
        analysis_result = {
            'sentiment': sentiment,
            'sentiment_details': {
                'positive': positive_count,
                'negative': negative_count,
                'neutral': neutral_count
            },
            'market_focus': market_focus_count > 0,
            'market_focus_count': market_focus_count,
            'risk_level': 'high' if risk_count > 5 else 'medium' if risk_count > 2 else 'low',
            'risk_count': risk_count,
            'hot_themes': sorted(theme_counts.items(), key=lambda x: x[1], reverse=True)[:5],
            'market_status': market_status
        }
        return analysis_result
    except Exception as e:
        print(f"多维度文本分析失败: {e}")
        return None

def analyze_stock_keywords_local(text):
    """本地分析股票关键词 - 优化版本(移除外部API调用,加快速度)"""
    try:
        # 提取股票名称
        stock_names, _ = extract_stock_names(text)
        # 多维度文本分析
        dimension_analysis = analyze_text_dimensions(text)
        # 在分析结果开头添加所有识别出的股票名称列表
        analysis_results = []
        # 添加分析说明
        quick_analysis_note = "⚡ **快速股票分析模式** - 纯本地分析,无外部API调用\n"
        quick_analysis_note += "📊 分析内容:股票识别 + 多维度文本分析(情绪、市场焦点、风险识别等)\n"
        quick_analysis_note += "🚀 分析速度:快速(无网络请求)\n"
        quick_analysis_note += f"{'='*50}\n\n"
        analysis_results.append(quick_analysis_note)
        # 添加多维度文本分析结果
        if dimension_analysis:
            dimension_summary = "📊 **多维度文本分析结果**\n"
            dimension_summary += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            dimension_summary += f"😊 情绪倾向:{dimension_analysis['sentiment']}\n"
            dimension_summary += f"   - 积极词汇:{dimension_analysis['sentiment_details']['positive']} 个\n"
            dimension_summary += f"   - 消极词汇:{dimension_analysis['sentiment_details']['negative']} 个\n"
            dimension_summary += f"   - 中性词汇:{dimension_analysis['sentiment_details']['neutral']} 个\n"
            dimension_summary += f"\n🎯 市场焦点:{'是' if dimension_analysis['market_focus'] else '否'} (关键词出现 {dimension_analysis['market_focus_count']} 次)\n"
            dimension_summary += f"⚠️ 风险等级:{dimension_analysis['risk_level']} (风险关键词出现 {dimension_analysis['risk_count']} 次)\n"
            dimension_summary += f"📈 市场状况:{dimension_analysis['market_status']}\n"
            if dimension_analysis['hot_themes']:
                dimension_summary += "\n🔥 热门主题:\n"
                for theme, count in dimension_analysis['hot_themes']:
                    dimension_summary += f"   - {theme}: {count} 次\n"
            dimension_summary += f"\n{'='*50}\n\n"
            analysis_results.append(dimension_summary)
        if not stock_names:
            # 即使没有股票名称,也返回多维度分析结果
            if dimension_analysis:
                return "".join(analysis_results) + "\n未找到股票名称,但已完成多维度文本分析"
            return "未找到股票名称"
        print(f"🔍 识别出 {len(stock_names)} 只股票,开始快速分析...")
        # 只进行本地文本分析,不调用外部API
        _log(f"📊 开始本地文本分析,识别出 {len(stock_names)} 只股票...")
        # 添加股票名称汇总
        stock_summary = "🔍 **识别出的股票名称汇总**\n"
        stock_summary += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        stock_summary += f"📋 共识别出 {len(stock_names)} 只股票:\n\n"
        # 分类显示股票名称
        stock_codes_with_names = []
        stock_names_only = []
        for stock in stock_names:
            if '(' in stock and ')' in stock:  # 股票代码(名称)格式
                stock_codes_with_names.append(stock)
            else:  # 纯股票名称
                stock_names_only.append(stock)
        if stock_codes_with_names:
            stock_summary += f"📊 **股票代码及名称 ({len(stock_codes_with_names)} 只):**\n"
            for i, stock in enumerate(stock_codes_with_names, 1):
                stock_summary += f"   {i:2d}. {stock}\n"
            stock_summary += "\n"
        if stock_names_only:
            stock_summary += f"📈 **纯股票名称 ({len(stock_names_only)} 只):**\n"
            for i, stock in enumerate(stock_names_only, 1):
                stock_summary += f"   {i:2d}. {stock}\n"
            stock_summary += "\n"
        stock_summary += f"{'='*50}\n\n"
        analysis_results.append(stock_summary)
        # 分析所有识别出的股票(仅本地文本分析,不调用外部API)
        print(f"🚀 开始分析 {len(stock_names)} 只股票(本地文本分析)...")
        for i, stock_name in enumerate(stock_names, 1):
            try:
                # 仅进行本地文本分析
                logic = get_stock_logic(text, stock_name)
                context = extract_stock_context(text, [stock_name])
                # 获取股票代码(本地查找,不调用API)
                stock_code = get_stock_code_by_name(stock_name)
                code_display = f"({stock_code})" if stock_code else ""
                # 构建分析结果
                result = f"📊 **{stock_name}{code_display}** 分析报告(本地文本分析)\n"
                result += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                if logic and logic != "未找到明确逻辑":
                    result += f"💡 投资逻辑:{logic}\n"
                contexts = context.get(stock_name, [])
                if contexts and contexts[0] != "未找到相关内容":
                    result += "📝 相关讨论:\n"
                    for j, ctx in enumerate(contexts[:2], 1):  # 只显示前2个相关内容
                        result += f"   {j}. {ctx}\n"
                result += f"\n{'='*50}\n\n"
                analysis_results.append(result)
                # 每10只股票显示一次进度
                if i % 10 == 0:
                    print(f"   已分析 {i}/{len(stock_names)} 只股票...")
            except Exception as e:
                error_result = f"❌ **{stock_name}** 分析失败:{e!s}\n"
                error_result += f"{'='*50}\n\n"
                analysis_results.append(error_result)
        return "".join(analysis_results)
    except Exception as e:
        return f"分析过程中发生错误:{e!s}"

def generate_wordcloud(text, callback, tab_name=None, time_str=None):
    """生成词云(基于情绪分析着色)
    Args:
        text: 输入文本
        callback: 回调函数
        tab_name: 标签页名称
        time_str: 时间字符串(如果标签页名称已包含时间,则不需要)
    """
    try:
        # 提取股票名称
        stock_names, _ = extract_stock_names(text)
        # 多维度文本分析(用于情绪着色)
        dimension_analysis = analyze_text_dimensions(text)
        # 构建词频字典
        word_freq = {}
        # 如果有股票名称,优先使用股票名称
        if stock_names:
            for stock_name in stock_names:
                # 基础权重
                word_freq[stock_name] = 10
        else:
            # 如果没有股票名称,基于文本关键词生成词云
            try:
                import jieba.analyse
                # 使用TF-IDF提取关键词(最多50个)
                keywords = jieba.analyse.extract_tags(text, topK=50, withWeight=True)
                for keyword, weight in keywords:
                    # 权重转换为整数(放大1000倍)
                    word_freq[keyword] = int(weight * 1000)
            except Exception as e:
                print(f"关键词提取失败,使用分词结果: {e}")
                # 如果TF-IDF失败,使用简单的分词和词频统计
                try:
                    words = jieba.lcut(text)
                    # 过滤掉停用词和单字词
                    from collections import Counter
                    filtered_words = [w for w in words if len(w) > 1 and w.strip()]
                    word_counter = Counter(filtered_words)
                    # 取前50个高频词
                    for word, count in word_counter.most_common(50):
                        word_freq[word] = count * 5  # 基础权重
                except Exception as e2:
                    print(f"分词失败: {e2}")
                    callback("文本处理失败,无法生成词云")
                    return
        if not word_freq:
            callback("没有有效的股票数据生成词云")
            return
        # 自定义颜色函数(基于情绪分析)
        def color_func(word, font_size, position, orientation, random_state=None, **kwargs):
            try:
                # 基于多维度分析结果确定颜色
                if dimension_analysis:
                    sentiment = dimension_analysis.get('sentiment', '中性')
                    if sentiment in ['积极', '偏积极']:
                        return "red"  # 积极用红色
                    elif sentiment in ['消极', '偏消极']:
                        return "green"  # 消极用绿色
                    else:
                        return "blue"  # 中性用蓝色
                else:
                    # 如果没有分析结果,使用默认颜色
                    return "gray"
            except:
                return "gray"
        # 生成词云
        wordcloud = WordCloud(
            width=480, height=360,  # 缩小到60% (800*0.6=480, 600*0.6=360)
            background_color='white',
            font_path='C:/Windows/Fonts/simhei.ttf',
            max_words=100,
            min_font_size=20,
            max_font_size=80,
            margin=15,
            scale=1.2,
            color_func=color_func
        ).generate_from_frequencies(word_freq)
        # 保存词云图片
        wordcloud_path = os.path.join(D_OUTPUT_DIR, "wordcloud.png")
        wordcloud.to_file(wordcloud_path)
        # 在词云图片上添加标签页名称和时间
        try:
            img = Image.open(wordcloud_path)
            # 确保图片是RGB格式
            if img.mode != 'RGB':
                img = img.convert('RGB')
            # 尝试加载中文字体
            try:
                font_path = 'C:/Windows/Fonts/simhei.ttf'
                font = ImageFont.truetype(font_path, 20)
            except:
                try:
                    font = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 20)
                except:
                    try:
                        font = ImageFont.truetype('C:/Windows/Fonts/simsun.ttc', 20)
                    except:
                        font = ImageFont.load_default()
            # 准备要显示的文本
            display_text = ""
            if tab_name:
                display_text = tab_name
                # 检查标签页名称是否包含时间(格式:YYYY-MM-DD 或 YYYY/MM/DD 或 HH:MM:SS)
                has_date = re.search(r'\d{4}[-/]\d{1,2}[-/]\d{1,2}', tab_name) or re.search(r'\d{1,2}:\d{1,2}:\d{1,2}', tab_name)
                if not has_date and time_str:
                    display_text += f"  {time_str}"
            elif time_str:
                display_text = time_str
            # 在左上角绘制文本(带背景)
            if display_text:
                # 转换为RGBA以便添加半透明背景
                img_rgba = img.convert('RGBA')
                overlay = Image.new('RGBA', img_rgba.size, (255, 255, 255, 0))
                overlay_draw = ImageDraw.Draw(overlay)
                # 计算文本尺寸
                try:
                    bbox = overlay_draw.textbbox((0, 0), display_text, font=font)
                    text_width = bbox[2] - bbox[0]
                    text_height = bbox[3] - bbox[1]
                except:
                    # 如果textbbox不可用,使用textsize(旧版本PIL)
                    try:
                        text_width, text_height = overlay_draw.textsize(display_text, font=font)
                    except:
                        text_width, text_height = 200, 20
                # 绘制半透明背景
                padding = 5
                bg_box = [10, 10, 10 + text_width + padding * 2, 10 + text_height + padding * 2]
                overlay_draw.rectangle(bg_box, fill=(255, 255, 255, 200))
                # 合并overlay和原图
                img_rgba = Image.alpha_composite(img_rgba, overlay)
                img = img_rgba.convert('RGB')
                draw = ImageDraw.Draw(img)
                # 绘制文本
                draw.text((10 + padding, 10 + padding), display_text, fill='black', font=font)
            # 保存修改后的图片
            img.save(wordcloud_path)
        except Exception as e:
            print(f"添加标签页名称和时间到词云失败: {e}")
            import traceback
            traceback.print_exc()
        # 生成交互式HTML词云(支持鼠标浮窗)
        generate_interactive_wordcloud(word_freq, callback, text)
        callback("词云生成完成")
    except Exception as e:
        callback(f"词云生成失败: {e!s}")

def generate_interactive_wordcloud(word_freq, callback, text=None):
    """生成交互式HTML词云,支持鼠标浮窗显示股票详细信息
    Args:
        word_freq: 词频字典
        callback: 回调函数
        text: 原始文本,用于提取股票逻辑
    """
    try:
        from datetime import datetime
        # 从文本中提取股票逻辑
        stock_logics = {}
        if text:
            for stock_name in word_freq:
                try:
                    logic = get_stock_logic(text, stock_name)
                    if logic and logic != "未找到明确逻辑":
                        stock_logics[stock_name] = logic[:500]  # 限制长度
                    else:
                        # 尝试从上下文中提取
                        context = extract_stock_context(text, [stock_name])
                        contexts = context.get(stock_name, [])
                        if contexts and contexts[0] != "未找到相关内容":
                            stock_logics[stock_name] = contexts[0][:500]
                        else:
                            stock_logics[stock_name] = "无详细逻辑"
                except Exception as e:
                    print(f"提取股票 {stock_name} 逻辑失败: {e}")
                    stock_logics[stock_name] = "无详细逻辑"
        # 获取股票详细信息
        stock_details = {}
        for stock_name in word_freq:
            try:
                # 获取股票基本信息
                stock_info = get_stock_basic_info(stock_name)
                if stock_info:
                    stock_details[stock_name] = stock_info
            except Exception as e:
                print(f"获取股票 {stock_name} 信息失败: {e}")
                continue
        # 生成HTML内容
        html_content = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>股票词云 - 交互式</title>
    <style>
        body {{
            font-family: 'Microsoft YaHei', Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(45deg, #2196F3, #21CBF3);
            color: white;
            padding: 20px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 28px;
            font-weight: 300;
        }}
        .wordcloud-container {{
            padding: 40px;
            text-align: center;
            min-height: 600px;
            position: relative;
        }}
        .word {{
            display: inline-block;
            margin: 5px;
            padding: 8px 15px;
            border-radius: 25px;
            cursor: pointer;
            transition: all 0.3s ease;
            position: relative;
            font-weight: bold;
            text-decoration: none;
            color: inherit;
        }}
        .word:hover {{
            transform: scale(1.05);
            box-shadow: 0 3px 10px rgba(0,0,0,0.2);
        }}
        .positive {{
            color: #4CAF50;
        }}
        .negative {{
            color: #F44336;
        }}
        .neutral {{
            color: #FF9800;
        }}
        .footer {{
            background: #f5f5f5;
            padding: 20px;
            text-align: center;
            color: #666;
        }}
        .stats {{
            display: flex;
            justify-content: space-around;
            margin: 20px 0;
            flex-wrap: wrap;
        }}
        .stat-item {{
            text-align: center;
            margin: 10px;
        }}
        .stat-number {{
            font-size: 24px;
            font-weight: bold;
            color: #2196F3;
        }}
        .stat-label {{
            color: #666;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 股票词云分析 - 交互式</h1>
            <p>鼠标悬停查看股票详细信息</p>
        </div>
        <div class="stats">
            <div class="stat-item">
                <div class="stat-number">{len(word_freq)}</div>
                <div class="stat-label">识别股票数</div>
            </div>
            <div class="stat-item">
                <div class="stat-number">{len(stock_details)}</div>
                <div class="stat-label">获取详情数</div>
            </div>
            <div class="stat-item">
                <div class="stat-number">{datetime.now().strftime('%Y-%m-%d')}</div>
                <div class="stat-label">生成日期</div>
            </div>
        </div>
        <div class="wordcloud-container">
"""
        # 添加股票词汇
        for i, (stock_name, frequency) in enumerate(word_freq.items()):
            # 获取股票详细信息
            stock_info = stock_details.get(stock_name, {})
            # 确定颜色
            weekly_change = stock_info.get('weekly_change', 0)
            if weekly_change > 5:
                color = "#F44336"  # 红色
            elif weekly_change > 0:
                color = "#FF9800"  # 橙色
            elif weekly_change > -5:
                color = "#2196F3"  # 蓝色
            else:
                color = "#4CAF50"  # 绿色
            # 计算字体大小
            font_size = max(16, min(48, 20 + frequency * 2))
            # 获取股票逻辑
            stock_logic = stock_logics.get(stock_name, "无详细逻辑")
            # 转义HTML特殊字符
            stock_logic_escaped = stock_logic.replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;').replace('&', '&amp;')
            html_content += f"""
            <span class="word"
                  style="font-size: {font_size}px; color: {color};"
                  data-stock="{stock_name}"
                  data-logic="{stock_logic_escaped}"
                  data-index="{i}"
                  title="{stock_logic_escaped[:100]}">
                {stock_name}
            </span>
"""
        # 添加JavaScript和工具提示
        html_content += """
        </div>
        <div class="footer">
            <p>📊 股票词云展示 - 鼠标悬停查看股票逻辑</p>
            <p>📈 包含:股票名称、涨跌幅颜色标识</p>
        </div>
    </div>
    <script>
        // 添加鼠标悬停显示股票逻辑的功能
        document.addEventListener('DOMContentLoaded', function() {
            const words = document.querySelectorAll('.word');
            words.forEach(function(word) {
                const stockName = word.getAttribute('data-stock');
                const logic = word.getAttribute('data-logic');
                // 创建tooltip元素
                const tooltip = document.createElement('div');
                tooltip.className = 'tooltip';
                tooltip.style.cssText = `
                    position: absolute;
                    background: rgba(0, 0, 0, 0.9);
                    color: white;
                    padding: 10px;
                    border-radius: 5px;
                    max-width: 400px;
                    z-index: 1000;
                    display: none;
                    font-size: 12px;
                    line-height: 1.5;
                    pointer-events: none;
                    word-wrap: break-word;
                `;
                tooltip.innerHTML = `<strong>${stockName}</strong><br><br>${logic}`;
                document.body.appendChild(tooltip);
                // 鼠标悬停事件
                word.addEventListener('mouseenter', function(e) {
                    tooltip.style.display = 'block';
                    updateTooltipPosition(e, tooltip);
                });
                word.addEventListener('mousemove', function(e) {
                    updateTooltipPosition(e, tooltip);
                });
                word.addEventListener('mouseleave', function() {
                    tooltip.style.display = 'none';
                });
            });
            function updateTooltipPosition(e, tooltip) {
                const x = e.clientX + 10;
                const y = e.clientY + 10;
                tooltip.style.left = x + 'px';
                tooltip.style.top = y + 'px';
                // 确保tooltip不超出屏幕
                const rect = tooltip.getBoundingClientRect();
                if (rect.right > window.innerWidth) {
                    tooltip.style.left = (window.innerWidth - rect.width - 10) + 'px';
                }
                if (rect.bottom > window.innerHeight) {
                    tooltip.style.top = (window.innerHeight - rect.height - 10) + 'px';
                }
            }
            console.log('股票词云已加载,共显示 ' + words.length + ' 个股票');
        });
    </script>
</body>
</html>
"""
        # 保存HTML文件
        html_file = "wordcloud_interactive.html"
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        callback(f"交互式词云已生成: {html_file}")
    except Exception as e:
        callback(f"生成交互式词云失败: {e!s}")
        import traceback
        traceback.print_exc()

__all__ = ['analyze_stock_keywords_local', 'analyze_text_dimensions', 'generate_interactive_wordcloud', 'generate_wordcloud']
