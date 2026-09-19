@echo off

chcp 65001 >nul

cd /d "%~dp0..\src"

chcp 65001
title 淘股吧100个帖子爬取工具

echo.
echo ========================================
echo        淘股吧100个帖子爬取工具
echo ========================================
echo.

echo 正在启动爬虫...
python taoguba_100_posts_crawler.py

if errorlevel 1 (
    echo.
    echo 启动失败，请检查Python环境和依赖库
    echo 请确保已安装以下库：
    echo   - requests
    echo   - pandas
    echo   - beautifulsoup4
    echo   - openpyxl
    echo.
    echo 可以使用以下命令安装：
    echo   pip install requests pandas beautifulsoup4 openpyxl
    echo.
    pause
) else (
    echo.
    echo 程序已正常退出
)

pause


