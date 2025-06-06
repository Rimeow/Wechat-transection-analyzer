@echo off
chcp 65001 > nul
setlocal
echo.
echo 微信流水分析工具 - 独立环境部署
echo ================================
echo.
:: 检查Python是否安装
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [❌ ERROR] 未检测到Python，请先安装Python！
    pause
    exit /b 1
)
:: 创建虚拟环境（带完整标准库副本）
echo === 创建独立虚拟环境 ===
python -m venv venv --copies  &:: （关键参数：--copies 复制完整Python环境）
if not exist venv\Scripts\activate.bat (
    echo [❌ ERROR] 虚拟环境创建失败！
    pause
    exit /b 1
)

:: 激活虚拟环境
call venv\Scripts\activate.bat
echo [✔️ OK] 虚拟环境已激活（独立模式）

:: 安装依赖
echo.
echo === 安装项目依赖 ===
pip install --upgrade pip
pip install -r requirements.txt

:: 检查标准库是否独立
echo.
echo === 验证环境独立性 ===
python -c "
import sys, os
print(f'Python路径: {sys.executable}')
print(f'标准库路径: {os.path.dirname(os.__file__)}')
assert 'venv' in sys.executable, '未运行在虚拟环境中！'
"

:: 创建项目目录
echo.
echo === 初始化项目目录 ===
set "DIRS=uploads output logs database static/css static/js static/images"
for %%d in (%DIRS%) do (
    if not exist "%%d" mkdir "%%d"
    echo [✔️ OK] 目录已就绪: %%d
)

echo.
echo [✔️ 部署完成！]
echo 使用以下命令激活环境：
echo    venv\Scripts\activate
echo.
pause
