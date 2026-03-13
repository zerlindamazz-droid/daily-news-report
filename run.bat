@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 正在生成每日报告，请稍候...
python main.py
echo.
if errorlevel 1 (
    echo [!] 报告生成遇到错误，请查看 logs\report.log
) else (
    echo [✓] 完成！报告保存在 output\ 目录，邮件已发送
)
pause
