@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 请先在飞书群里添加“自定义机器人”，复制它的 Webhook 地址。
echo.
set /p WEBHOOK=粘贴飞书 Webhook 后回车:
if "%WEBHOOK%"=="" (
  echo 未输入 Webhook，已取消。
  pause
  exit /b 1
)
> "%~dp0feishu_webhook.txt" echo %WEBHOOK%
echo.
set /p SECRET=如果机器人开启了签名校验，请粘贴签名密钥；没有就直接回车:
if not "%SECRET%"=="" (
  > "%~dp0feishu_sign_secret.txt" echo %SECRET%
)
echo.
echo 已保存。请重新启动 run_fu2609_dashboard.cmd，或让我帮你重启当前服务。
pause
