"""
批量安装问财 SkillHub 技能（通过 aime-skillhub-cli + 同花顺网关）。

说明：官方未提供公开的全量技能 ID 列表接口，本脚本使用公开介绍中出现的技能名
及常见「问财选* / *查询」类名称作为候选；名称与广场不完全一致时，下载会失败，脚本会跳过并继续。

用法：
  python iwencai_skillhub_batch_install.py
  python iwencai_skillhub_batch_install.py --dry-run
  python iwencai_skillhub_batch_install.py --extra path/to/more_names.txt
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# 候选技能名：来自问财 SkillHub 公开介绍、分类示例及常见官方数据技能（去重）
DEFAULT_SLUGS = [
    # 社区 / 方法论（文章示例）
    "彼得林奇选股法",
    "索罗斯反身性战法",
    "费雪成长股猎手",
    "邓普顿逆向投资",
    "霍华德·马克斯周期投资",
    "霍华德马克斯周期投资",
    "利弗莫尔交易哲学",
    "《股票大作手》交易哲学",
    "量化因子选股",
    "小盘成长股挖掘",
    "高分红股挑选",
    "低估值好股搜寻",
    "投资组合诊断",
    "风险收益优化配置",
    "投资者风险评估",
    "交易心理通关秘籍",
    "富爸爸财商课",
    "投资委员会备忘录",
    "投资委员会备忘录起草",
    "尽职调查清单",
    "尽职调查清单生成",
    "LBO模型",
    "LBO模型构建",
    "DCF模型",
    "现金流折现估值模型",
    "可比公司分析",
    "Comps分析",
    "市场情绪偏离分析",
    "卖方流程文档",
    "Teaser",
    "CIM",
    # 官方 / 数据类（名称可能因广场更新而变化，仅供尝试）
    "问财选A股",
    "问财选港股",
    "问财选美股",
    "问财选基金",
    "问财选ETF",
    "问财选基金经理",
    "问财选可转债",
    "宏观数据查询",
    "财务数据查询",
    "行情数据查询",
    "新闻搜索",
    "公告搜索",
    "研报搜索",
    "董秘问答搜索",
    "产业链解读",
    "资讯搜索",
]

WIN_CLI = Path.home() / ".local" / "bin" / "aime-skillhub-cli.cmd"


def _load_extra(path: Path) -> list[str]:
    if not path.is_file():
        return []
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            lines.append(s)
    return lines


def main() -> int:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    ap = argparse.ArgumentParser(description="Batch install iwencai SkillHub skills via aime-skillhub-cli.")
    ap.add_argument("--dry-run", action="store_true", help="Only print names, do not install.")
    ap.add_argument("--extra", type=Path, help="Text file: one skill name per line (UTF-8).")
    ap.add_argument(
        "--dir",
        type=Path,
        default=Path.home() / ".aime-skillhub" / "skills",
        help="Install root (default: ~/.aime-skillhub/skills for stockyidong 扫描目录)",
    )
    ap.add_argument("--force", action="store_true", help="Overwrite existing skill folders (passes --force to CLI).")
    args = ap.parse_args()

    names: list[str] = []
    seen: set[str] = set()
    combined = list(DEFAULT_SLUGS)
    if args.extra:
        combined.extend(_load_extra(args.extra))
    for n in combined:
        if n not in seen:
            seen.add(n)
            names.append(n)

    install_root = args.dir.expanduser().resolve()
    install_root.mkdir(parents=True, exist_ok=True)

    if sys.platform == "win32" and WIN_CLI.is_file():
        base_cmd = [str(WIN_CLI)]
    else:
        base_cmd = [sys.executable, str(Path.home() / ".aime-skillhub" / "aime_skillhub_cli.py")]

    ok, fail = 0, 0
    for i, name in enumerate(names, 1):
        print(f"\n[{i}/{len(names)}] {name}")
        if args.dry_run:
            continue
        # aime-skillhub-cli：全局参数 --dir 须在子命令 install 之前
        cmd = base_cmd + ["--dir", str(install_root), "install", name]
        if args.force:
            cmd.append("--force")
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        out = (r.stdout or "") + (r.stderr or "")
        if "Installed:" in out:
            ok += 1
            print(out.strip()[-400:] if len(out) > 400 else out.strip())
        else:
            fail += 1
            tail = out.strip()[-500:] if out else "(no output)"
            print(f"  skipped/failed: {tail}")

    print(f"\nDone. success={ok} failed_or_skipped={fail} total={len(names)} install_root={install_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
