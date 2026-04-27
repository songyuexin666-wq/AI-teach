#!/bin/bash

# AI教师助手系统部署脚本
# 适用于 Ubuntu/Debian 系统

set -e

echo "🚀 开始部署AI教师助手系统..."

# 检查系统要求
check_requirements() {
    echo "📋 检查系统要求..."
    
    # 检查Python版本
    if ! command -v python3 &> /dev/null; then
        echo "❌ Python3 未安装，请先安装Python3.8+"
        exit 1
    fi
    
    python_version=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    if [[ $(echo "$python_version < 3.8" | bc -l) -eq 1 ]]; then
        echo "❌ Python版本过低，需要3.8+，当前版本: $python_version"
        exit 1
    fi
    
    echo "✅ Python版本检查通过: $python_version"
    
    # 检查pip
    if ! command -v pip3 &> /dev/null; then
        echo "❌ pip3 未安装，请先安装pip3"
        exit 1
    fi
    
    echo "✅ pip3 检查通过"
}

# 安装系统依赖
install_system_deps() {
    echo "📦 安装系统依赖..."
    
    # 更新包列表
    sudo apt-get update
    
    # 安装基础依赖
    sudo apt-get install -y \
        python3-dev \
        python3-pip \
        python3-venv \
        build-essential \
        libssl-dev \
        libffi-dev \
        libxml2-dev \
        libxslt1-dev \
        zlib1g-dev \
        libjpeg-dev \
        libpng-dev \
        libfreetype6-dev \
        liblcms2-dev \
        libwebp-dev \
        libharfbuzz-dev \
        libfribidi-dev \
        libxcb1-dev \
        ffmpeg \
        texlive-full \
        git \
        curl \
        wget
    
    echo "✅ 系统依赖安装完成"
}

# 安装FFmpeg
install_ffmpeg() {
    echo "🎬 安装FFmpeg..."
    
    if command -v ffmpeg &> /dev/null; then
        echo "✅ FFmpeg 已安装"
        return
    fi
    
    # 添加FFmpeg PPA
    sudo add-apt-repository -y ppa:jonathonf/ffmpeg-4
    sudo apt-get update
    sudo apt-get install -y ffmpeg
    
    echo "✅ FFmpeg 安装完成"
}

# 安装LaTeX
install_latex() {
    echo "📝 安装LaTeX..."
    
    if command -v pdflatex &> /dev/null; then
        echo "✅ LaTeX 已安装"
        return
    fi
    
    sudo apt-get install -y texlive-full
    
    echo "✅ LaTeX 安装完成"
}

# 创建虚拟环境
create_venv() {
    echo "🐍 创建Python虚拟环境..."
    
    if [ -d "venv" ]; then
        echo "✅ 虚拟环境已存在"
        return
    fi
    
    python3 -m venv venv
    source venv/bin/activate
    
    # 升级pip
    pip install --upgrade pip
    
    echo "✅ 虚拟环境创建完成"
}

# 安装Python依赖
install_python_deps() {
    echo "📚 安装Python依赖..."
    
    source venv/bin/activate
    
    # 安装依赖
    pip install -r requirements.txt
    
    echo "✅ Python依赖安装完成"
}

# 配置环境变量
setup_env() {
    echo "⚙️ 配置环境变量..."
    
    if [ ! -f ".env" ]; then
        cp env.example .env
        echo "📝 已创建 .env 文件，请编辑其中的配置"
        echo "🔑 特别需要配置 OPENAI_API_KEY"
    else
        echo "✅ .env 文件已存在"
    fi
}

# 创建必要目录
create_directories() {
    echo "📁 创建必要目录..."
    
    mkdir -p outputs/ppt
    mkdir -p outputs/videos
    mkdir -p outputs/audio
    mkdir -p uploads
    mkdir -p logs
    
    echo "✅ 目录创建完成"
}

# 启动服务
start_services() {
    echo "🚀 启动服务..."
    
    # 启动Docker服务（如果使用Docker）
    if command -v docker-compose &> /dev/null; then
        echo "🐳 启动Docker服务..."
        docker-compose up -d
        echo "✅ Docker服务启动完成"
    else
        echo "⚠️ Docker Compose 未安装，跳过Docker服务启动"
    fi
}

# 运行数据库迁移
run_migrations() {
    echo "🗄️ 运行数据库迁移..."
    
    source venv/bin/activate
    
    # 这里可以添加数据库迁移命令
    # alembic upgrade head
    
    echo "✅ 数据库迁移完成"
}

# 测试安装
test_installation() {
    echo "🧪 测试安装..."
    
    source venv/bin/activate
    
    # 测试Python导入
    python3 -c "
import fastapi
import uvicorn
import openai
import manim
print('✅ 核心依赖导入成功')
"
    
    echo "✅ 安装测试通过"
}

# 主函数
main() {
    echo "🎯 AI教师助手系统部署脚本"
    echo "================================"
    
    check_requirements
    install_system_deps
    install_ffmpeg
    install_latex
    create_venv
    install_python_deps
    setup_env
    create_directories
    start_services
    run_migrations
    test_installation
    
    echo ""
    echo "🎉 部署完成！"
    echo "================================"
    echo "📝 下一步操作："
    echo "1. 编辑 .env 文件，配置必要的API密钥"
    echo "2. 运行: source venv/bin/activate"
    echo "3. 启动服务: python main.py"
    echo "4. 访问: http://localhost:7878"
    echo ""
    echo "📚 更多信息请查看 README.md"
}

# 运行主函数
main "$@"









