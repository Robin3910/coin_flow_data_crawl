@echo off
echo [%date% %time%] 监控脚本已启动

:: 检查程序是否在运行
echo [%date% %time%] 检查程序是否在运行...
netstat -aon | findstr ":80" > nul
if errorlevel 1 (
    echo [%date% %time%] 程序未运行，正在启动...
    cd %USERPROFILE%\Desktop\coin_flow_data_crawl
    start python app.py
    echo [%date% %time%] Python 程序已启动，等待60秒...
    timeout /t 60 /nobreak > nul
) else (
    echo [%date% %time%] 程序已在运行
)

:loop



:: 获取当前时间
set /a min=%time:~3,2%
echo [%date% %time%] 当前分钟数: %min%

:: 检查是否是40分钟或者10分钟
if %min%==10 || %min%==40 (
    echo [%date% %time%] 到达指定时间，开始执行重启操作
    
    :: 查找并关闭80端口的进程
    echo [%date% %time%] 正在查找并关闭80端口进程...
    for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":80"') do (
        echo [%date% %time%] 正在终止进程 PID: %%a
        taskkill /F /PID %%a
    )
    
    :: 切换到指定目录并运行python脚本
    echo [%date% %time%] 切换到脚本目录并启动 Python 程序
    cd %USERPROFILE%\Desktop\coin_flow_data_crawl
    start python app.py
    
    echo [%date% %time%] Python 程序已启动，等待60秒...
    timeout /t 60 /nobreak > nul
)

echo [%date% %time%] 等待30秒后继续检查...
timeout /t 30 /nobreak > nul
goto loop 