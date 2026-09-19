@echo off
chcp 65001 >nul
title 股票移动分析器 - 打包程序
color 0A

echo.
echo ========================================
echo   股票移动分析器 - 打包成可执行程序
echo ========================================
echo.

cd /d "%~dp0"

echo [步骤 1/3] 清理旧的打包文件...
if exist build (
    echo     正在删除 build 目录...
    rmdir /s /q build 2>nul
    echo     ✓ 已删除 build 目录
) else (
    echo     ✓ build 目录不存在，跳过
)

if exist dist (
    echo     正在删除 dist 目录...
    rmdir /s /q dist 2>nul
    echo     ✓ 已删除 dist 目录
) else (
    echo     ✓ dist 目录不存在，跳过
)
echo     清理完成！
echo.

echo [步骤 2/3] 检查打包环境...
if not exist ".venv\Scripts\python.exe" (
    echo     ✗ [错误] 虚拟环境不存在！
    echo     请先创建虚拟环境
    echo.
    pause
    exit /b 1
)
echo     ✓ Python 环境正常

if not exist "stockyidong.py" (
    echo     ✗ [错误] 主程序文件不存在！
    echo.
    pause
    exit /b 1
)
echo     ✓ 主程序文件存在

if not exist "stockyidong.spec" (
    echo     ✗ [错误] 打包配置文件不存在！
    echo.
    pause
    exit /b 1
)
echo     ✓ 打包配置文件存在
echo.

echo [步骤 3/3] 开始打包...
echo.
echo     ⏳ 正在执行打包命令...
echo     这可能需要 5-15 分钟，请耐心等待...
echo     （打包过程中会显示详细信息）
echo.
echo     ========================================
echo.

.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm stockyidong.spec

if errorlevel 1 (
    echo.
    echo     ========================================
    echo.
    echo     ✗ [错误] 打包失败！
    echo     请检查上面的错误信息
    echo.
    pause
    exit /b 1
)

echo.
echo     ========================================
echo.
echo     ✓✓✓ 打包成功完成！ ✓✓✓
echo.
echo ========================================
echo   打包结果
echo ========================================
echo.

set "EXE_PATH=dist\股票移动分析器\股票移动分析器.exe"

if exist "%EXE_PATH%" (
    echo [成功] 可执行文件已生成！
    echo.
    echo [文件信息]
    echo     文件路径: %CD%\%EXE_PATH%
    echo.
    for %%F in ("%EXE_PATH%") do (
        set size=%%~zF
        set /a sizeMB=%%~zF/1048576
        echo     文件大小: !sizeMB! MB (约)
        echo     修改时间: %%~tF
    )
    echo.
    echo [使用说明]
    echo     1. 打开 dist\股票移动分析器\ 文件夹
    echo     2. 双击 股票移动分析器.exe 即可运行
    echo     3. 可以将整个"股票移动分析器"文件夹复制到任何位置使用
    echo.
    echo [提示] 
    echo     - 首次运行可能需要几秒钟加载
    echo     - 建议将整个文件夹放在固定位置，不要只复制exe文件
    echo     - 如需分发，请将整个文件夹一起打包压缩
    echo.
) else (
    echo [警告] 未找到可执行文件，请检查打包日志
    echo.
)

echo ========================================
echo.
pause
