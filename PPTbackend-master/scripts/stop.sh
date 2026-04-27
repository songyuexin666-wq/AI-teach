#!/bin/bash

# AI教师助手系统停止脚本

echo "🛑 停止AI教师助手系统..."

# 停止Docker服务
if command -v docker-compose &> /dev/null; then
    echo "🐳 停止Docker服务..."
    docker-compose down
    echo "✅ Docker服务已停止"
fi

# 查找并停止Python进程
echo "🐍 查找Python进程..."
PYTHON_PIDS=$(pgrep -f "python.*main.py" || true)

if [ -n "$PYTHON_PIDS" ]; then
    echo "🔄 停止Python进程: $PYTHON_PIDS"
    kill $PYTHON_PIDS
    sleep 2
    
    # 强制停止（如果还在运行）
    PYTHON_PIDS=$(pgrep -f "python.*main.py" || true)
    if [ -n "$PYTHON_PIDS" ]; then
        echo "⚡ 强制停止Python进程: $PYTHON_PIDS"
        kill -9 $PYTHON_PIDS
    fi
    
    echo "✅ Python进程已停止"
else
    echo "ℹ️ 未找到运行中的Python进程"
fi

# 清理临时文件
echo "🧹 清理临时文件..."
find . -name "*.pyc" -delete
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

echo "✅ 系统已停止"









