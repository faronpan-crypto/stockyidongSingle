set "REPO_ROOT=%~dp0..\.."

cd /d "%REPO_ROOT%"

chcp 65001 >nul
echo ========================================
echo   股票移动分析器 - 可执行文件构建脚本
echo ========================================
echo.

REM 检查 PyInstaller 是否安装
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo [错误] PyInstaller 未安装！
    echo [提示] 正在安装 PyInstaller...
    python -m pip install pyinstaller
    if errorlevel 1 (
        echo [错误] PyInstaller 安装失败！
        pause
        exit /b 1
    )
)

echo [信息] 开始构建可执行文件...
echo.

REM 若正在运行 股票移动分析器，先结束进程，避免 dist 下文件被占用导致拒绝访问
tasklist /FI "IMAGENAME eq 股票移动分析器.exe" 2>nul | find /I "股票移动分析器.exe" >nul
if not errorlevel 1 (
    echo [提示] 检测到 股票移动分析器 正在运行，正在结束进程...
    taskkill /F /IM "股票移动分析器.exe" >nul 2>&1
    timeout /t 3 /nobreak >nul
)

REM 清理 dist 下的输出目录（避免 PyInstaller 清理时因文件被占用而报错）
set "OUTDIR=dist\股票移动分析器"
if exist "%OUTDIR%" (
    echo [提示] 正在尝试清理 %OUTDIR% ...
    taskkill /F /IM "股票移动分析器.exe" >nul 2>&1
    timeout /t 2 /nobreak >nul
    rmdir /s /q "%OUTDIR%" 2>nul
    if exist "%OUTDIR%" (
        echo [错误] 无法删除 %OUTDIR%，可能被占用。
        echo [提示] 请先关闭 股票移动分析器.exe，并关闭该文件夹的 Explorer 窗口，再重新运行本脚本。
        pause
        exit /b 1
    )
)

REM 清理 build 和 __pycache__
if exist build rmdir /s /q build 2>nul
if exist __pycache__ rmdir /s /q __pycache__ 2>nul

REM 使用 spec 文件构建
echo [信息] 使用 spec 文件进行构建...
pyinstaller --clean --noconfirm stockyidong.spec

if errorlevel 1 (
    echo [错误] 构建失败！
    echo [提示] 若报错 拒绝访问 或 PermissionError，请先关闭正在运行的 股票移动分析器 及 dist 文件夹窗口，再重新运行本脚本。
    pause
    exit /b 1
)

REM 若 _internal 中缺少 python313.dll，从当前 Python 安装目录复制（避免 "Failed to load Python DLL"）
set "OUTDIR=dist\股票移动分析器"
set "INTERNAL=%OUTDIR%\_internal"
if not exist "%INTERNAL%\python313.dll" (
    echo [提示] 正在将 Python 运行时 DLL 复制到 _internal ...
    python -c "import sys, os, shutil; d=os.path.dirname(sys.executable); v=sys.version_info; name='python%d%d.dll'%%(v.major,v.minor); src=os.path.join(d, name); dst_dir=os.path.join('dist', '股票移动分析器', '_internal'); os.makedirs(dst_dir, exist_ok=True); dst=os.path.join(dst_dir, name); shutil.copy2(src, dst) if os.path.exists(src) else None; print('已复制', name) if os.path.exists(dst) else print('未找到', name)"
)

echo.
echo ========================================
echo   构建完成！
echo ========================================
echo.
echo [信息] 可执行程序位置: %OUTDIR%\股票移动分析器.exe
echo [提示] 请将整个文件夹 "%OUTDIR%" 一起复制使用
echo [提示] 已打包：按钮功能、爬虫程序、分析程序、tushare/akshare/同花顺接口、初始化配置等
echo [提示] 可把该文件夹快捷方式放到桌面，运行 股票移动分析器.exe 即可
echo.
pause
