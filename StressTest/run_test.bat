@echo off
REM FastAPI 压力测试快速启动脚本
REM Quick Start Script for Stress Testing

echo ========================================
echo FastAPI 压力测试工具
echo ========================================
echo.

REM 检查依赖
echo [1/4] 检查依赖...
python -c "import locust" 2>nul
if errorlevel 1 (
    echo ✗ 未安装 locust
    echo 正在安装依赖...
    pip install locust psutil
) else (
    echo ✓ locust 已安装
)

python -c "import psutil" 2>nul
if errorlevel 1 (
    echo ✗ 未安装 psutil
    echo 正在安装依赖...
    pip install psutil
) else (
    echo ✓ psutil 已安装
)

echo.
echo [2/4] 配置检查...
if not exist config.py (
    echo ✗ 找不到 config.py
    echo 请先配置 config.py 文件
    pause
    exit /b 1
)
echo ✓ 配置文件存在

echo.
echo [3/4] 选择测试模式...
echo.
echo 请选择测试模式:
echo   1. Web UI 模式（推荐 - 可视化界面）
echo   2. 快速测试（50 用户，5 分钟）
echo   3. 压力测试（100 用户，10 分钟）
echo   4. 极限测试（200 用户，10 分钟）
echo   5. 自定义参数
echo.
set /p choice="请输入选项 (1-5): "

if "%choice%"=="1" goto webui
if "%choice%"=="2" goto quick
if "%choice%"=="3" goto stress
if "%choice%"=="4" goto extreme
if "%choice%"=="5" goto custom
goto invalid

:webui
echo.
echo [4/4] 启动 Web UI 模式...
echo.
echo 浏览器将打开 http://localhost:8089
echo 在界面中设置并发用户数和启动速率
echo 按 Ctrl+C 停止测试
echo.
timeout /t 3
start http://localhost:8089
locust -f locustfile.py --host http://localhost:5000
goto end

:quick
echo.
echo [4/4] 启动快速测试...
echo 参数: 50 用户, 每秒启动 5 个, 运行 5 分钟
echo.
timeout /t 2
locust -f locustfile.py --host http://localhost:5000 --headless -u 50 -r 5 -t 5m --html report_quick.html
echo.
echo ✓ 测试完成！报告已保存到 report_quick.html
goto end

:stress
echo.
echo [4/4] 启动压力测试...
echo 参数: 100 用户, 每秒启动 10 个, 运行 10 分钟
echo.
timeout /t 2
locust -f locustfile.py --host http://localhost:5000 --headless -u 100 -r 10 -t 10m --html report_stress.html
echo.
echo ✓ 测试完成！报告已保存到 report_stress.html
goto end

:extreme
echo.
echo ⚠️  警告: 极限测试可能导致服务器过载！
set /p confirm="确认继续? (y/n): "
if /i not "%confirm%"=="y" goto end

echo.
echo [4/4] 启动极限测试...
echo 参数: 200 用户, 每秒启动 20 个, 运行 10 分钟
echo.
timeout /t 2
locust -f locustfile.py --host http://localhost:5000 --headless -u 200 -r 20 -t 10m --html report_extreme.html
echo.
echo ✓ 测试完成！报告已保存到 report_extreme.html
goto end

:custom
echo.
echo [4/4] 自定义测试参数...
set /p users="并发用户数: "
set /p rate="每秒启动用户数: "
set /p duration="测试时长（如 5m, 10m, 1h）: "
set /p host="服务器地址（默认 http://localhost:5000）: "

if "%host%"=="" set host=http://localhost:5000

echo.
echo 启动测试: %users% 用户, 启动速率 %rate%/s, 时长 %duration%
echo 目标: %host%
echo.
timeout /t 2
locust -f locustfile.py --host %host% --headless -u %users% -r %rate% -t %duration% --html report_custom.html
echo.
echo ✓ 测试完成！报告已保存到 report_custom.html
goto end

:invalid
echo.
echo ✗ 无效的选项
goto end

:end
echo.
echo ========================================
echo 测试结束
echo ========================================
echo.
echo 提示:
echo   - 查看 HTML 报告了解详细结果
echo   - 使用 monitor.py 监控系统资源
echo   - 阅读 README.md 了解更多用法
echo.
pause
