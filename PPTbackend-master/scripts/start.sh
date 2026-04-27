#!/bin/bash

# AI教师助手系统启动脚本

set -e

echo "🚀 启动AI教师助手系统..."

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "❌ 虚拟环境不存在，请先运行 setup.sh"
    exit 1
fi

# 激活虚拟环境
source venv/bin/activate

# 检查环境变量文件
if [ ! -f ".env" ]; then
    echo "❌ .env 文件不存在，请先配置环境变量"
    exit 1
fi

# 检查OpenAI API密钥
if ! grep -q "OPENAI_API_KEY=sk-" .env; then
    echo "⚠️ 警告: 未检测到有效的OpenAI API密钥"
    echo "请编辑 .env 文件，设置正确的 OPENAI_API_KEY"
fi

# 创建必要目录
mkdir -p outputs/ppt outputs/videos outputs/audio uploads logs

# 启动服务
echo "🌟 启动FastAPI服务..."
echo "📍 服务地址: http://localhost:7878"
echo "📖 API文档: http://localhost:7878/docs"
echo ""
echo "按 Ctrl+C 停止服务"
echo "================================"

# 启动应用
python main.py









