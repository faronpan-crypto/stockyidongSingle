@echo off

chcp 65001 >nul

set "REPO_ROOT=%~dp0..\.."

cd /d "%REPO_ROOT%"

chcp 65001 >nul
title 检查打包状态
color 0E

cls
echo.
echo ========================================
echo   检查打包状态
echo ========================================
echo.

set "EXE_PATH=dist\股票移动分析器\股票移动分析器.exe"

if exist "%EXE_PATH%" (
    echo [状态] ✓ 可执行文件已生成！
    echo.
    echo [文件信息]
    for %%F in ("%EXE_PATH%") do (
        set /a sizeMB=%%~zF/1048576
        echo     文件路径: %%~fF
        echo     文件大小: !sizeMB! MB (约 %%~zF 字节)
        echo     修改时间: %%~tF
    )
    echo.
    echo [提示] 
    echo     ✓ 如果修改时间是刚才的时间，说明打包已完成！
    echo     ✓ 可以直接双击运行 股票移动分析器.exe
    echo     ✓ 程序位置: %CD%\%EXE_PATH%
    echo.
) else (
    echo [状态] ⏳ 打包还在进行中或打包失败
    echo.
    echo [检查] 正在检查打包进程...
    tasklist | findstr /i "python.exe" >nul
    if errorlevel 1 (
        echo     ⚠ 未发现 Python 打包进程
        echo     可能打包已完成、失败或未启动
        echo.
        echo [建议] 
        echo     1. 检查 dist 文件夹是否存在
        echo     2. 查看是否有错误信息
        echo     3. 尝试重新运行打包脚本
    ) else (
        echo     ✓ 发现 Python 进程正在运行
        echo     ⏳ 打包可能还在进行中，请稍候...
        echo.
        echo [提示] 打包通常需要 5-15 分钟
        echo        请等待完成后再次运行此脚本检查
    )
)

echo.
echo ========================================
echo.
echo [操作提示]
echo     1. 如果打包完成，去 dist\股票移动分析器\ 文件夹运行exe
echo     2. 如果打包失败，检查错误信息后重新打包
echo     3. 运行 "重新打包.bat" 可以重新开始打包
echo.
pause
