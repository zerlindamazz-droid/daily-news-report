@echo off
chcp 65001 >nul
echo.
echo ╔══════════════════════════════════════════════════════╗
echo ║         每日全球要闻快报 — 首次安装配置               ║
echo ╚══════════════════════════════════════════════════════╝
echo.

:: 切换到脚本所在目录
cd /d "%~dp0"

echo [1/3] 安装 Python 依赖包...
pip install -r requirements.txt
if errorlevel 1 (
    echo [错误] pip install 失败，请确认 Python 已安装并加入 PATH
    pause
    exit /b 1
)

echo.
echo [2/3] 安装 Playwright Chromium 浏览器（用于 PDF 生成）...
playwright install chromium
if errorlevel 1 (
    echo [警告] Playwright Chromium 安装失败，PDF 功能将不可用
    echo        可稍后手动运行: playwright install chromium
)

echo.
echo [3/3] 安装完成！
echo.
echo ══════════════════════════════════════════════════════
echo  请编辑 config.json 填写以下信息：
echo.
echo  "sender"    : 你的 Gmail 地址
echo  "password"  : Gmail App Password（16位，见说明）
echo  "recipient" : 收件人邮箱（可与 sender 相同）
echo.
echo  Gmail App Password 获取步骤：
echo    1. 打开 myaccount.google.com
echo    2. 安全 → 两步验证（开启）
echo    3. 安全 → 应用专用密码 → 生成
echo    4. 将 16 位密码粘贴到 config.json
echo ══════════════════════════════════════════════════════
echo.
echo 配置完成后：
echo   手动生成报告: 双击 run.bat
echo   启动每日调度: 双击 start_scheduler.vbs
echo.
pause
