#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI教师助手系统启动脚本
"""

import os
import sys
import subprocess
import time
import logging
from pathlib import Path

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_environment():
    """检查环境配置"""
    logger.info("检查环境配置...")
    
    # 检查Python版本
    if sys.version_info < (3, 8):
        logger.error("需要Python 3.8或更高版本")
        return False
    
    # 检查必要的包
    required_packages = [
        'fastapi', 'uvicorn', 'python-pptx', 'matplotlib', 
        'pillow', 'sympy', 'httpx', 'openai'
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        logger.error(f"缺少必要的包: {', '.join(missing_packages)}")
        logger.info("请运行: pip install -r requirements.txt")
        return False
    
    # 检查环境变量
    env_vars = {
        'OPENAI_API_KEY': 'OpenAI API密钥',
        'OPENAI_BASE_URL': 'OpenAI API地址'
    }
    
    missing_vars = []
    for var, desc in env_vars.items():
        if not os.getenv(var):
            missing_vars.append(f"{var} ({desc})")
    
    if missing_vars:
        logger.warning(f"未设置环境变量: {', '.join(missing_vars)}")
        logger.info("系统将使用默认配置运行")
    
    return True

def create_directories():
    """创建必要的目录"""
    logger.info("创建必要的目录...")
    
    directories = [
        'outputs/ppt',
        'outputs/videos', 
        'outputs/audio',
        'temp',
        'uploads'
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        logger.info(f"创建目录: {directory}")

def start_backend():
    """启动后端服务"""
    logger.info("启动后端服务...")
    
    try:
        # 启动FastAPI服务
        cmd = [
            sys.executable, '-m', 'uvicorn', 
            'main:app', 
            '--host', '0.0.0.0', 
            '--port', '7878', 
            '--reload'
        ]
        
        logger.info(f"执行命令: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)
        
    except subprocess.CalledProcessError as e:
        logger.error(f"后端启动失败: {e}")
        return False
    except KeyboardInterrupt:
        logger.info("后端服务已停止")
        return True

def main():
    """主函数"""
    logger.info("=" * 50)
    logger.info("AI教师助手系统启动")
    logger.info("=" * 50)
    
    # 检查环境
    if not check_environment():
        logger.error("环境检查失败，请修复问题后重试")
        sys.exit(1)
    
    # 创建目录
    create_directories()
    
    # 启动后端
    logger.info("准备启动后端服务...")
    logger.info("后端服务将在 http://localhost:7878 启动")
    logger.info("按 Ctrl+C 停止服务")
    logger.info("-" * 50)
    
    try:
        start_backend()
    except KeyboardInterrupt:
        logger.info("系统已停止")
    except Exception as e:
        logger.error(f"系统启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

