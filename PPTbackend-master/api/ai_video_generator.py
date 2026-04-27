import os
import logging
import httpx
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any
import json

logger = logging.getLogger(__name__)

class AIVideoGenerator:
    """AI视频生成器 - 使用第三方AI视频生成API"""
    
    def __init__(self):
        self.output_dir = "outputs/videos"
        self._ensure_output_dir()
        
        # 支持的AI视频生成服务
        self.services = {
            "runway": {
                "api_key": os.getenv("RUNWAY_API_KEY"),
                "base_url": "https://api.runwayml.com/v1"
            },
            "pika": {
                "api_key": os.getenv("PIKA_API_KEY"), 
                "base_url": "https://api.pika.art/v1"
            },
            "stable_video": {
                "api_key": os.getenv("STABILITY_API_KEY"),
                "base_url": "https://api.stability.ai/v2beta"
            }
        }
    
    def _ensure_output_dir(self):
        """确保输出目录存在"""
        os.makedirs(self.output_dir, exist_ok=True)
    
    async def create_video_from_text(
        self, 
        topic: str, 
        content: str,
        style: str = "educational",
        duration: int = 30,
        service: str = "runway"
    ) -> str:
        """
        从文本内容生成视频
        
        Args:
            topic: 视频主题
            content: 视频内容
            style: 视频风格
            duration: 视频时长（秒）
            service: 使用的AI服务
            
        Returns:
            生成的视频文件名
        """
        try:
            # 优化文本内容为视频提示词
            video_prompt = self._create_video_prompt(topic, content, style)
            
            # 根据选择的服务生成视频
            if service == "runway":
                video_url = await self._generate_with_runway(video_prompt, duration)
            elif service == "pika":
                video_url = await self._generate_with_pika(video_prompt, duration)
            elif service == "stable_video":
                video_url = await self._generate_with_stable_video(video_prompt, duration)
            else:
                raise ValueError(f"不支持的服务: {service}")
            
            # 下载视频文件
            video_filename = await self._download_video(video_url, topic)
            
            logger.info(f"AI视频生成成功: {video_filename}")
            return video_filename
            
        except Exception as e:
            logger.error(f"AI视频生成失败: {e}", exc_info=True)
            raise
    
    def _create_video_prompt(self, topic: str, content: str, style: str) -> str:
        """将文本内容转换为视频生成提示词"""
        
        # 根据风格选择不同的提示词模板
        style_templates = {
            "educational": f"Educational video about {topic}. Professional teaching style with clear explanations, diagrams, and examples. Clean, modern presentation with good lighting.",
            "animated": f"Animated educational video about {topic}. Colorful animations, smooth transitions, engaging visuals that explain concepts clearly.",
            "documentary": f"Documentary-style video about {topic}. Professional narration, real-world examples, interviews, and visual storytelling.",
            "presentation": f"Professional presentation video about {topic}. Clean slides, clear typography, smooth transitions, and engaging visuals."
        }
        
        base_prompt = style_templates.get(style, style_templates["educational"])
        
        # 添加内容摘要
        content_summary = content[:200] + "..." if len(content) > 200 else content
        full_prompt = f"{base_prompt} Content: {content_summary}"
        
        return full_prompt
    
    async def _generate_with_runway(self, prompt: str, duration: int) -> str:
        """使用Runway ML生成视频"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.services['runway']['base_url']}/generations",
                headers={
                    "Authorization": f"Bearer {self.services['runway']['api_key']}",
                    "Content-Type": "application/json"
                },
                json={
                    "text_prompt": prompt,
                    "duration": min(duration, 10),  # Runway限制最长10秒
                    "resolution": "1280x720",
                    "fps": 24
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                return result["generation"]["url"]
            else:
                raise Exception(f"Runway API错误: {response.text}")
    
    async def _generate_with_pika(self, prompt: str, duration: int) -> str:
        """使用Pika Labs生成视频"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.services['pika']['base_url']}/generate",
                headers={
                    "Authorization": f"Bearer {self.services['pika']['api_key']}",
                    "Content-Type": "application/json"
                },
                json={
                    "prompt": prompt,
                    "duration": min(duration, 4),  # Pika限制最长4秒
                    "aspect_ratio": "16:9",
                    "motion": "medium"
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                return result["video_url"]
            else:
                raise Exception(f"Pika API错误: {response.text}")
    
    async def _generate_with_stable_video(self, prompt: str, duration: int) -> str:
        """使用Stability AI生成视频"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.services['stable_video']['base_url']}/image-to-video",
                headers={
                    "Authorization": f"Bearer {self.services['stable_video']['api_key']}",
                    "Content-Type": "application/json"
                },
                json={
                    "image": self._generate_thumbnail_from_prompt(prompt),
                    "prompt": prompt,
                    "duration": min(duration, 5),  # Stability限制最长5秒
                    "fps": 6
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                return result["video_url"]
            else:
                raise Exception(f"Stability API错误: {response.text}")
    
    def _generate_thumbnail_from_prompt(self, prompt: str) -> str:
        """从提示词生成缩略图（用于Stability Video）"""
        # 这里可以集成DALL-E或其他图像生成API
        # 简化实现，返回一个占位符
        return "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
    
    async def _download_video(self, video_url: str, topic: str) -> str:
        """下载生成的视频文件"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"ai_video_{self._clean_topic(topic)}_{timestamp}.mp4"
        filepath = os.path.join(self.output_dir, filename)
        
        async with httpx.AsyncClient() as client:
            async with client.stream("GET", video_url) as response:
                response.raise_for_status()
                with open(filepath, "wb") as f:
                    async for chunk in response.aiter_bytes():
                        f.write(chunk)
        
        return filename
    
    def _clean_topic(self, topic: str) -> str:
        """清理主题名称用于文件名"""
        import re
        return re.sub(r'[^a-zA-Z0-9_]', '', topic.replace(" ", "_"))
    
    async def get_video_info(self, filename: str) -> Dict[str, Any]:
        """获取视频文件信息"""
        file_path = os.path.join(self.output_dir, filename)
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"视频文件不存在: {filename}")
        
        stat = os.stat(file_path)
        return {
            "filename": filename,
            "size": stat.st_size,
            "created_time": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "modified_time": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "type": "ai_generated"
        }








