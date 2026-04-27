#!/bin/bash

echo "启动Spring Boot后端服务..."
echo

# 检查Maven是否安装
if ! command -v mvn &> /dev/null; then
    echo "错误: Maven未安装或未配置到PATH环境变量中"
    echo "请先安装Maven: https://maven.apache.org/download.cgi"
    exit 1
fi

# 检查Java是否安装
if ! command -v java &> /dev/null; then
    echo "错误: Java未安装或未配置到PATH环境变量中"
    echo "请先安装Java 11或更高版本"
    exit 1
fi

echo "正在编译和启动Spring Boot应用..."
echo

# 清理并编译项目
mvn clean compile

# 启动Spring Boot应用
mvn spring-boot:run










