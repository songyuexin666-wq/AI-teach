@echo off
echo 启动Spring Boot后端服务...
echo.

REM 检查Maven是否安装
mvn --version >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误: Maven未安装或未配置到PATH环境变量中
    echo 请先安装Maven: https://maven.apache.org/download.cgi
    pause
    exit /b 1
)

REM 检查Java是否安装
java -version >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误: Java未安装或未配置到PATH环境变量中
    echo 请先安装Java 11或更高版本
    pause
    exit /b 1
)

echo 正在编译和启动Spring Boot应用...
echo.

REM 清理并编译项目
mvn clean compile

REM 启动Spring Boot应用
mvn spring-boot:run

pause










