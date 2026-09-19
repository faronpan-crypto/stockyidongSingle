# 股票移动分析器 - 打包说明

## 打包方式

在项目根目录执行：

```bat
build_stockyidong_exe.bat
```

或手动执行：

```bat
pyinstaller --clean --noconfirm stockyidong.spec
```

## 说明

- **首次打包** 可能需 **15～30 分钟**（依赖 akshare、torch 等较多）。
- 生成结果在：`dist\股票移动分析器\`
  - 主程序：`dist\股票移动分析器\股票移动分析器.exe`
  - 需**整份文件夹**一起使用（内含爬虫脚本、配置与依赖），不要只复制 exe。
- 可将 `dist\股票移动分析器` 整个文件夹复制到任意位置，或为其创建快捷方式到桌面。

## 已包含功能

- 爬虫：淘股吧、九言公社、东方财富热股、雪球日报、OCR 识别、一键爬虫等。
- 股票：akshare/tushare 数据、问财电梯、批量分析、持仓计算器（stockchichang.py）等。
- 配置：`market_nav_config.json`、`crawler_config.json`、`iwencai_condition_options.json`、`ocr_images_config.json` 等若存在会一并打包。

## 运行环境

- 打包后的 exe 在 **Windows** 下运行，无需单独安装 Python。
- 数据目录默认使用 `D:\StockAnalyzer`（数据库、导出等），首次运行会自动创建。
