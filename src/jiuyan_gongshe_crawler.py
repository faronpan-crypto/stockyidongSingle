import argparse
import json
import os
import sys
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

# 与同目录下的 parse_nuxt.py 一并分发；运行目录非 src 时也能导入
_SRC_DIR = os.path.dirname(os.path.abspath(__file__))
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)
from parse_nuxt import parse_nuxt_from_text

BASE_URL = "https://www.jiuyangongshe.com"
ESSENCE_URL = f"{BASE_URL}/"
HOME_URL = f"{BASE_URL}/"
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": BASE_URL,
    "Connection": "keep-alive",
}


def ensure_utf8_output() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if not stream:
            continue
        encoding = getattr(stream, "encoding", "") or ""
        try:
            if encoding.lower() != "utf-8":
                stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def fetch_html(session: requests.Session, url: str) -> str:
    response = session.get(url, timeout=12)
    response.raise_for_status()
    response.encoding = "utf-8"
    return response.text


def normalise_html_content(html_text: str | None) -> tuple[str, str]:
    if not html_text:
        return "", ""
    soup = BeautifulSoup(html_text, "html.parser")
    text = soup.get_text("\n", strip=True)
    return text, soup.prettify()


def extract_posts(nuxt_payload: dict, limit: int | None = None) -> list[dict]:
    posts = []
    records = nuxt_payload.get("data", [{}])[0].get("list", [])
    for item in records[: limit or None]:
        content_text, content_html = normalise_html_content(item.get("content"))
        stock_list = item.get("stock_list") or []
        stock_names = ", ".join(stock.get("name", "") for stock in stock_list if stock.get("name"))
        stock_codes = ", ".join(stock.get("code", "") for stock in stock_list if stock.get("code"))
        user = item.get("user") or {}
        posts.append(
            {
                "文章标题": item.get("title", ""),
                "作者昵称": user.get("nickname", ""),
                "作者ID": user.get("user_id", ""),
                "作者风格": user.get("style_str", ""),
                "作者勋章数": user.get("medal_count", 0),
                "帖子地区": item.get("area", ""),
                "帖子发布时间": item.get("create_time", ""),
                "帖子ID": item.get("article_id", ""),
                "帖子链接": f"{BASE_URL}/a/{item.get('article_id', '')}",
                "点赞数": item.get("like_count", 0),
                "收藏数": item.get("collect_count", 0),
                "评论数": item.get("comment_count", 0),
                "转发数": item.get("forward_count", 0),
                "阅读积分": item.get("read_integral", 0),
                "相关股票": stock_names,
                "股票代码": stock_codes,
                "内容": content_text,
                "原始HTML": content_html,
            }
        )
    return posts


def extract_hot_keywords(nuxt_payload: dict) -> list[str]:
    hot_search = nuxt_payload.get("state", {}).get("rankList", {}).get("hot_search_list", [])
    return [item.get("keyword", "") for item in hot_search if item.get("keyword")]


def extract_hot_articles(nuxt_payload: dict) -> list[dict]:
    hot_articles = nuxt_payload.get("state", {}).get("rankList", {}).get("hot_article_list", [])
    rows = []
    for item in hot_articles:
        rows.append(
            {
                "热门帖子标题": item.get("title", ""),
                "作者ID": item.get("user_id", ""),
                "帖子ID": item.get("article_id", ""),
                "帖子链接": f"{BASE_URL}/a/{item.get('article_id', '')}",
            }
        )
    return rows


def build_hot_stock_table(keywords: Sequence[str], posts: Sequence[dict]) -> pd.DataFrame:
    rows = []
    for keyword in keywords:
        matched = [post for post in posts if keyword and (keyword in post["相关股票"] or keyword in post["内容"] or keyword in post["文章标题"])]
        rows.append(
            {
                "热门关键词": keyword,
                "相关精华帖数量": len(matched),
                "相关精华帖标题": "; ".join(post["文章标题"] for post in matched),
                "相关文章链接": "; ".join(post["帖子链接"] for post in matched),
            }
        )
    return pd.DataFrame(rows)


def save_to_excel(posts: list[dict], hot_keywords: Sequence[str], hot_articles: Sequence[dict], output_path: Path) -> None:
    posts_df = pd.DataFrame(posts)
    hot_df = build_hot_stock_table(hot_keywords, posts)
    hot_articles_df = pd.DataFrame(hot_articles)

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        posts_df.to_excel(writer, sheet_name="精华帖", index=False)
        hot_df.to_excel(writer, sheet_name="热门股", index=False)
        if not hot_articles_df.empty:
            hot_articles_df.to_excel(writer, sheet_name="热门文章", index=False)


def generate_output_path(target: str | None) -> Path:
    if target:
        path = Path(target)
        if path.is_dir():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            return path / f"jiuyang_gongshe_{timestamp}.xlsx"
        return path
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path.cwd() / f"jiuyang_gongshe_{timestamp}.xlsx"


def main(limit: int | None, output: str | None) -> None:
    ensure_utf8_output()
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)

    print("正在获取精华帖列表…")
    try:
        essence_html = fetch_html(session, ESSENCE_URL)
        if not essence_html or len(essence_html) < 100:
            raise ValueError(f"获取的HTML内容过短或为空 (长度: {len(essence_html) if essence_html else 0})")
        
        # 检查是否包含NUXT数据
        if '__NUXT__' not in essence_html:
            raise ValueError("HTML中未找到__NUXT__数据，网站结构可能已变化")
        
        essence_data = parse_nuxt_from_text(essence_html)
        posts = extract_posts(essence_data, limit=limit)
        print(f"成功获取 {len(posts)} 篇精华帖")
    except ValueError as e:
        print(f"获取精华帖列表失败 (值错误): {e}", file=sys.stderr)
        print("提示: 网站结构可能已变化，请检查网站是否可访问", file=sys.stderr)
        raise
    except json.JSONDecodeError as e:
        print(f"JSON解析失败: {e}", file=sys.stderr)
        print(f"错误位置: line {e.lineno}, column {e.colno}", file=sys.stderr)
        print("提示: 网站返回的数据格式可能已变化", file=sys.stderr)
        raise
    except Exception as e:
        print(f"获取精华帖列表失败: {type(e).__name__}: {e}", file=sys.stderr)
        import traceback
        print(f"详细错误: {traceback.format_exc()}", file=sys.stderr)
        raise

    print("正在获取热门股信息…")
    try:
        home_html = fetch_html(session, HOME_URL)
        if not home_html or len(home_html) < 100:
            print("警告: 获取的首页HTML内容过短，跳过热门股信息", file=sys.stderr)
            hot_keywords = []
            hot_articles = []
        else:
            home_data = parse_nuxt_from_text(home_html)
            hot_keywords = extract_hot_keywords(home_data)
            hot_articles = extract_hot_articles(home_data)
            print(f"成功获取 {len(hot_keywords)} 个热门关键词和 {len(hot_articles)} 篇热门文章")
    except Exception as e:
        print(f"获取热门股信息失败: {type(e).__name__}: {e}", file=sys.stderr)
        print("继续执行，使用空数据", file=sys.stderr)
        # 备用方案：返回空数据，不影响主流程
        hot_keywords = []
        hot_articles = []

    if not posts:
        raise RuntimeError("未能获取到任何精华帖数据。请检查网站是否可访问或网站结构是否发生变化。")

    output_path = generate_output_path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    save_to_excel(posts, hot_keywords, hot_articles, output_path)

    print(f"已保存 {len(posts)} 篇精华帖到 {output_path}")
    print(f"热门股关键词数量: {len(hot_keywords)}")
    
    # 保存到配置文件（勿在 main 内再次 import json，否则会遮蔽模块名导致 UnboundLocalError）
    try:
        config_file = Path("D:/StockAnalyzer/excel_files_config.json")
        config_file.parent.mkdir(parents=True, exist_ok=True)

        config = {}
        if config_file.exists():
            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f)

        if "excel_files" not in config:
            config["excel_files"] = []

        file_path_abs = str(output_path.absolute())
        existing = False
        for file_info in config["excel_files"]:
            if os.path.abspath(file_info.get("path", "")) == file_path_abs:
                file_info["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                file_info["source"] = "韭研公社"
                existing = True
                break

        if not existing:
            config["excel_files"].append({
                "path": file_path_abs,
                "source": "韭研公社",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            })

        if len(config["excel_files"]) > 50:
            config["excel_files"].sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            config["excel_files"] = config["excel_files"][:50]

        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"保存配置文件失败: {e}")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="爬取韭研公社精华帖与热门股信息，并导出为Excel")
    parser.add_argument("--limit", type=int, default=None, help="限制精华帖数量（默认全部）")
    parser.add_argument("--output", type=str, default=None, help="指定输出Excel文件路径或目录")
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = parse_args()
    try:
        main(limit=args.limit, output=args.output)
    except Exception as exc:  # noqa: BLE001
        ensure_utf8_output()
        print(f"运行失败: {exc}", file=sys.stderr)
        sys.exit(1)
