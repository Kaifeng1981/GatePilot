@echo off
:: [Core Command]: Force switch to the current batch file's directory to prevent path loss
:: 【核心救命指令】：强制切换到当前批处理文件所在的物理目录，绝对防止路径迷失！
cd /d "%~dp0"

:: Force console encoding to UTF-8 to prevent garbled text
:: 强制将命令行编码设置为 UTF-8，防止中文乱码
chcp 65001 >nul

echo ===================================================
echo   🧹 Step 1: Cleaning up historical build caches...
echo      (第一步：正在清理历史打包残留...)
echo ===================================================

:: Check and silently delete 'build' folder / 检查并静默删除 build 文件夹
if exist "build" rmdir /s /q "build"
:: Check and silently delete 'dist' folder / 检查并静默删除 dist 文件夹
if exist "dist" rmdir /s /q "dist"
:: Check and silently delete '.spec' config file / 检查并静默删除 spec 配置文件
if exist "*.spec" del /f /q "*.spec"

echo   ✅ Clean up completed, environment is absolutely pure!
echo      (历史残留已清空，环境绝对纯净！)
echo.

echo ===================================================
echo   🛡️ Step 2: Packaging GatePilot standalone executable...
echo      (第二步：正在为您打包 GatePilot 独立程序...)
echo   [Compressing files and injecting resources, please wait 1-3 mins]
echo   (正在压缩文件并注入资源，请耐心等待 1-3 分钟)
echo ===================================================

:: Execute the packaging command / 执行打包命令
python -m PyInstaller -F -w --icon="logo.ico" --add-data "logo.ico;." --add-data "tray.ico;." "gatepilot.py"

echo.
echo ===================================================
echo   🎉 Packaging process finished! (打包过程结束！)
echo   1. Please scroll up to check if there are any red Error messages.
echo      (请向上滚动一下，确认有没有红色的 Error 报错。)
echo   2. If no errors, please check the auto-generated [dist] folder,
echo      (如果没有报错，请进入自动生成的【dist】文件夹，)
echo      you will find the fresh executable inside!
echo      (里面就是您新鲜出炉的程序！)
echo ===================================================
pause