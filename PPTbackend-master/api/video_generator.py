import os
import logging
import openai
import asyncio
import subprocess
import tempfile
from datetime import datetime
from typing import Optional, Dict, Any
import uuid

logger = logging.getLogger(__name__)

class VideoGenerator:
    """视频生成器 - 支持多种生成方式"""
    
    def __init__(self, openai_client=None, ai_model: str = "qwen-long"):
        self.openai_client = openai_client
        self.ai_model = ai_model
        self.output_dir = "outputs/videos"
        self._ensure_output_dir()
        
        # 导入AI视频生成器
        try:
            from .ai_video_generator import AIVideoGenerator
            self.ai_generator = AIVideoGenerator()
            self.has_ai_generator = True
        except ImportError:
            self.has_ai_generator = False
            logger.warning("AI视频生成器未安装")
        
        # 导入TTS服务
        try:
            from .text_to_speech import TextToSpeechService
            self.tts_service = TextToSpeechService()
            self.has_tts_service = True
        except ImportError:
            self.has_tts_service = False
            logger.warning("TTS服务未安装")
    
    def _ensure_output_dir(self):
        """确保输出目录存在"""
        os.makedirs(self.output_dir, exist_ok=True)
    
    async def create_video(
        self, 
        topic: str, 
        content: str,
        ppt_content: Optional[Dict] = None,
        script_content: Optional[str] = None,
        style: str = "presentation",
        duration: Optional[int] = None,
        resolution: str = "1920x1080",
        method: str = "auto"  # auto, manim, ai
    ) -> str:
        """
        创建教学视频 - 基于PPT和讲稿的翻页讲解
        
        Args:
            topic: 视频主题
            content: 视频内容
            ppt_content: PPT内容结构（包含幻灯片信息）
            script_content: 讲稿内容
            style: 视频风格
            duration: 视频时长（秒），None时自动计算
            resolution: 视频分辨率
            method: 生成方法 (auto/manim/ai)
            
        Returns:
            生成的视频文件名
        """
        try:
            # 自动计算视频时长（基于PPT页数）
            if duration is None:
                duration = self._calculate_duration_from_ppt(ppt_content, script_content)
            
            # 自动选择最佳生成方法
            if method == "auto":
                method = self._select_best_method(duration, content)
            
            logger.info(f"使用 {method} 方法生成视频，时长: {duration}秒")
            
            # 根据选择的方法生成视频
            if method == "ai" and self.has_ai_generator:
                try:
                    video_filename = await self.ai_generator.create_video_from_text(
                        topic, content, style, duration
                    )
                except Exception as e:
                    logger.warning(f"AI视频生成失败，回退到Manim: {e}")
                    # AI生成失败，回退到Manim
                    manim_code = await self._generate_ppt_manim_code(
                        topic, content, ppt_content, script_content, duration
                    )
                    video_filename = await self._execute_manim_code(manim_code, topic)
                    
                    # 如果有讲稿内容，生成语音并合成到视频中
                    if script_content and self.has_tts_service:
                        video_filename = await self._add_voice_to_video(
                            video_filename, script_content, topic
                        )
            else:
                # 使用Manim方法 - 基于PPT和讲稿生成翻页讲解视频
                manim_code = await self._generate_ppt_manim_code(
                    topic, content, ppt_content, script_content, duration
                )
                video_filename = await self._execute_manim_code(manim_code, topic)
                
                # 如果有讲稿内容，生成语音并合成到视频中
                if script_content and self.has_tts_service:
                    video_filename = await self._add_voice_to_video(
                        video_filename, script_content, topic
                    )
            
            logger.info(f"视频生成成功: {video_filename}")
            return video_filename
            
        except Exception as e:
            logger.error(f"视频生成失败: {e}", exc_info=True)
            raise
    
    def _select_best_method(self, duration: int, content: str) -> str:
        """自动选择最佳的视频生成方法"""
        
        # 根据内容长度和时长选择方法
        content_length = len(content)
        
        if duration <= 30 and content_length < 500:
            # 短内容，优先使用AI生成
            if self.has_ai_generator:
                return "ai"
        
        # 默认使用Manim
        return "manim"
    
    def _calculate_duration_from_ppt(self, ppt_content: Optional[Dict], script_content: Optional[str]) -> int:
        """根据PPT页数和讲稿内容自动计算视频时长"""
        base_duration = 60  # 基础时长60秒
        
        if script_content:
            # 根据讲稿长度计算语音时长（中文平均每分钟200字）
            script_length = len(script_content)
            # 语音时长 = 字数 / 200 * 60秒
            voice_duration = (script_length / 200) * 60
            base_duration = max(voice_duration, 30)  # 最少30秒
        
        if ppt_content and isinstance(ppt_content, dict):
            # 根据PPT页数调整时长
            slides = ppt_content.get('slides', [])
            if slides:
                # 每页PPT至少需要一定时间展示
                min_slide_duration = len(slides) * 5  # 每页最少5秒
                base_duration = max(base_duration, min_slide_duration)
        
        # 限制在合理范围内
        return min(max(base_duration, 30), 600)  # 30秒到10分钟
    
    async def _generate_ppt_manim_code(
        self, 
        topic: str, 
        content: str, 
        ppt_content: Optional[Dict], 
        script_content: Optional[str], 
        duration: int
    ) -> str:
        """基于PPT和讲稿生成Manim翻页讲解代码"""
        if not self.openai_client:
            return self._get_fallback_ppt_manim_code(topic, ppt_content, script_content)
        
        try:
            class_name = self._clean_class_name(topic)
            
            # 构建PPT结构信息
            ppt_info = self._extract_ppt_info(ppt_content)
            
            prompt = f"""
            Generate Manim animation code for a PPT presentation video about "{topic}".
            
            PPT STRUCTURE:
            {ppt_info}
            
            SCRIPT CONTENT:
            {script_content or content}
            
            REQUIREMENTS FOR {duration} SECOND VIDEO:
            1. Create a slide-by-slide presentation with smooth transitions
            2. Each slide should have appropriate timing based on content complexity
            3. Include slide transitions: FadeOut/FadeIn or Transform
            4. Add slide numbers and progress indicators
            5. Use professional presentation layout
            6. Include title slide, content slides, and conclusion slide
            7. Add visual elements like bullet points, diagrams, and formulas
            8. Ensure smooth narration flow with the script
            9. IMPORTANT: The video will have voice narration, so timing should match the script length
            10. Use self.wait() calls to match the voice timing (approximately {duration} seconds total)
            
            The code must be a single Manim scene with slide-based structure.
            Format:
            ```python
            from manim import *
            
            class {class_name}(Scene):
                def construct(self):
                    # Title slide
                    # Content slides (with transitions)
                    # Conclusion slide
            ```
            """
            
            logger.info(f"正在生成PPT翻页讲解的Manim代码")
            response = self.openai_client.chat.completions.create(
                model=self.ai_model,
                messages=[
                    {"role": "system", "content": "You are a professional Manim presentation code generator. Create slide-by-slide animations with smooth transitions."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=4000,
                temperature=0.7,
                extra_body={"enable_thinking": False},
            )
            
            manim_code = response.choices[0].message.content.strip()
            
            # 清理代码
            if manim_code.startswith("```python"):
                manim_code = manim_code[9:]
            if manim_code.endswith("```"):
                manim_code = manim_code[:-3]
            
            logger.info("PPT翻页讲解Manim代码生成完成")
            return manim_code.strip()
            
        except Exception as e:
            logger.error(f"生成PPT Manim代码失败: {e}")
            return self._get_fallback_ppt_manim_code(topic, ppt_content, script_content)
    
    def _extract_ppt_info(self, ppt_content: Optional[Dict]) -> str:
        """提取PPT结构信息"""
        if not ppt_content or not isinstance(ppt_content, dict):
            return "No PPT structure available"
        
        slides = ppt_content.get('slides', [])
        if not slides:
            return "No slides found in PPT"
        
        ppt_info = f"Total slides: {len(slides)}\n"
        for i, slide in enumerate(slides[:5]):  # 只显示前5页
            title = slide.get('title', f'Slide {i+1}')
            content = slide.get('content', '')
            ppt_info += f"Slide {i+1}: {title}\n"
            if content:
                ppt_info += f"  Content: {content[:100]}...\n"
        
        if len(slides) > 5:
            ppt_info += f"... and {len(slides) - 5} more slides\n"
        
        return ppt_info
    
    def _get_fallback_ppt_manim_code(self, topic: str, ppt_content: Optional[Dict], script_content: Optional[str]) -> str:
        """PPT翻页讲解的后备Manim代码"""
        class_name = self._clean_class_name(topic)
        
        # 提取幻灯片信息
        slides = []
        if ppt_content and isinstance(ppt_content, dict):
            slides = ppt_content.get('slides', [])
        
        if not slides:
            # 如果没有PPT结构，使用简单的内容分割
            content = script_content or "教学内容"
            slides = [{"title": f"第{i+1}部分", "content": part} for i, part in enumerate(content.split('\n\n')[:3])]
        
        # 生成简单的幻灯片动画代码
        slide_code = ""
        for i, slide in enumerate(slides):
            title = slide.get('title', f'第{i+1}页')
            content = slide.get('content', '')[:50]
            
            slide_code += f'''
        # 第{i+1}页: {title}
        slide_title_{i} = Text("{title}", font_size=36, color=GREEN)
        slide_title_{i}.next_to(title, DOWN, buff=1)
        self.play(FadeIn(slide_title_{i}))
        self.wait(1)
        
        slide_content_{i} = Text("{content}...", font_size=24)
        slide_content_{i}.next_to(slide_title_{i}, DOWN, buff=1)
        self.play(Write(slide_content_{i}))
        self.wait(3)
        
        # 翻页过渡
        if {i} < {len(slides) - 1}:
            self.play(FadeOut(slide_title_{i}), FadeOut(slide_content_{i}))
            self.wait(0.5)
'''
        
        return f'''from manim import *

class {class_name}(Scene):
    def construct(self):
        # 标题页
        title = Text("{topic}", font_size=48, color=BLUE)
        title.to_edge(UP)
        self.play(Write(title))
        self.wait(2)
        
        subtitle = Text("AI教师助手生成", font_size=24, color=GRAY)
        subtitle.next_to(title, DOWN, buff=0.5)
        self.play(Write(subtitle))
        self.wait(2)
        
        # 幻灯片内容
        {slide_code}
        
        # 结束页
        self.play(FadeOut(title), FadeOut(subtitle))
        thanks = Text("感谢观看！", font_size=32, color=GOLD)
        self.play(Write(thanks))
        self.wait(3)
        self.play(FadeOut(thanks))
'''
    
    def _generate_slide_animations(self, slides: list) -> str:
        """生成幻灯片动画代码"""
        if not slides:
            return ""
        
        animations = ""
        for i, slide in enumerate(slides):
            title = slide.get('title', f'第{i+1}页')
            content = slide.get('content', '')
            
            # 清理内容，避免引号问题
            clean_title = title.replace('"', '\\"')
            clean_content = content[:50].replace('"', '\\"').replace('\n', ' ')
            
            animations += f'''
        # 第{i+1}页: {clean_title}
        slide_title_{i} = Text("{clean_title}", font_size=36, color=GREEN)
        slide_title_{i}.next_to(title, DOWN, buff=1)
        self.play(FadeIn(slide_title_{i}))
        self.wait(1)
        
        slide_content_{i} = Text("{clean_content}...", font_size=24)
        slide_content_{i}.next_to(slide_title_{i}, DOWN, buff=1)
        self.play(Write(slide_content_{i}))
        self.wait(3)
        
        # 翻页过渡
        if {i} < {len(slides) - 1}:
            self.play(FadeOut(slide_title_{i}), FadeOut(slide_content_{i}))
            self.wait(0.5)
'''
        
        return animations
    
    async def _add_voice_to_video(self, video_filename: str, script_content: str, topic: str) -> str:
        """为视频添加语音讲解"""
        try:
            logger.info("开始为视频添加语音讲解")
            
            # 生成语音文件
            audio_filename = await self.tts_service.generate_speech(
                text=script_content,
                language="zh",
                voice="zh-CN-XiaoxiaoNeural",  # 使用中文女声
                speed=1.0
            )
            
            if not audio_filename:
                logger.warning("语音生成失败，返回原视频")
                return video_filename
            
            # 合成音频和视频
            final_video_filename = await self._merge_audio_video(
                video_filename, audio_filename, topic
            )
            
            # 清理临时音频文件
            try:
                os.remove(audio_filename)
            except:
                pass
            
            logger.info(f"语音合成完成: {final_video_filename}")
            return final_video_filename
            
        except Exception as e:
            logger.error(f"添加语音失败: {e}")
            return video_filename  # 返回原视频
    
    async def _merge_audio_video(self, video_filename: str, audio_filename: str, topic: str) -> str:
        """使用FFmpeg合并音频和视频"""
        try:
            import subprocess
            
            # 生成最终视频文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            final_name = f"video_with_voice_{self._clean_class_name(topic)}_{timestamp}.mp4"
            final_path = os.path.join(self.output_dir, final_name)
            
            # 构建FFmpeg命令
            cmd = [
                "ffmpeg",
                "-i", os.path.join(self.output_dir, video_filename),  # 输入视频
                "-i", audio_filename,  # 输入音频
                "-c:v", "copy",  # 视频编码器：复制（不重新编码）
                "-c:a", "aac",   # 音频编码器：AAC
                "-shortest",     # 以最短的流为准
                "-y",            # 覆盖输出文件
                final_path
            ]
            
            logger.info(f"执行FFmpeg命令: {' '.join(cmd)}")
            
            # 执行FFmpeg命令
            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )
            
            if result.returncode != 0:
                logger.error(f"FFmpeg执行失败: {result.stderr}")
                return video_filename  # 返回原视频
            
            logger.info("音频视频合成成功")
            return final_name
            
        except FileNotFoundError:
            logger.error("FFmpeg未安装，无法合成音频视频")
            return video_filename
        except Exception as e:
            logger.error(f"音频视频合成失败: {e}")
            return video_filename
    
    async def _generate_manim_code(self, topic: str, content: str, duration: int) -> str:
        """生成Manim动画代码"""
        if not self.openai_client:
            return self._get_fallback_manim_code(topic, content)
        
        try:
            class_name = self._clean_class_name(topic)
            prompt = f"""
            Generate Manim animation code for a video about "{topic}".
            
            The content should cover: {content}
            
            CRITICAL REQUIREMENTS FOR {duration} SECOND VIDEO:
            1. The video MUST be {duration} seconds long
            2. Add extensive self.wait() calls between animations (5-15 seconds each)
            3. Include at least 8-12 major sections with detailed explanations
            4. Use multiple animation types: Write, FadeIn, FadeOut, Transform, Create, DrawBorderThenFill, etc.
            5. Add mathematical formulas, diagrams, and visual examples
            6. Include step-by-step explanations with pauses for comprehension
            7. Add interactive elements and visual demonstrations
            8. Use colors, shapes, and complex animations
            9. Include multiple examples and case studies
            10. Add transitions between major topics
            
            The code must be a single Manim scene.
            Please provide only the Python code, formatted like this:
            ```python
            from manim import *

            class {class_name}(Scene):
                def construct(self):
                    # Your comprehensive {duration} second Manim animation code here
                    # Remember to add extensive self.wait() calls for {duration} second duration
                    pass
            ```
            """
            
            logger.info(f"正在向AI请求为主题 '{topic}' 生成Manim代码。")
            response = self.openai_client.chat.completions.create(
                model=self.ai_model,
                messages=[
                    {"role": "system", "content": "You are a professional Manim animation code generator. Generate clean Python code without explanations."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=4000,
                temperature=0.7,
                extra_body={"enable_thinking": False},
            )
            
            manim_code = response.choices[0].message.content.strip()
            
            # 清理代码，移除markdown标记
            if manim_code.startswith("```python"):
                manim_code = manim_code[9:]
            if manim_code.endswith("```"):
                manim_code = manim_code[:-3]
            
            logger.info("AI生成的Manim代码已接收。")
            return manim_code.strip()
            
        except Exception as e:
            logger.error(f"AI生成Manim代码失败: {e}")
            return self._get_fallback_manim_code(topic, content)
    
    def _clean_class_name(self, topic: str) -> str:
        """清理主题名称以用作类名"""
        import re
        clean_name = re.sub(r'[^a-zA-Z0-9_]', '', topic.replace(" ", ""))
        class_name = f"{clean_name}Scene" if clean_name else "DefaultScene"
        logger.debug(f"将主题 '{topic}' 清理为类名: {class_name}")
        return class_name
    
    def _get_fallback_manim_code(self, topic: str, content: str) -> str:
        """提供一个简短的Manim代码模板作为后备（约2-3分钟）"""
        class_name = self._clean_class_name(topic)
        
        return f'''from manim import *

class {class_name}(Scene):
    def construct(self):
        # 标题页 (15秒)
        title = Text("{topic}", font_size=48, color=BLUE)
        title.to_edge(UP)
        self.play(Write(title))
        self.wait(3)
        
        # 副标题
        subtitle = Text("AI教师助手生成", font_size=24, color=GRAY)
        subtitle.next_to(title, DOWN, buff=0.5)
        self.play(Write(subtitle))
        self.wait(2)
        
        # 第一部分：介绍 (30秒)
        self.play(FadeOut(subtitle))
        intro_title = Text("第一部分：基本概念", font_size=36, color=GREEN)
        intro_title.next_to(title, DOWN, buff=1)
        self.play(Write(intro_title))
        self.wait(2)
        
        intro_content = Text("让我们来学习基本概念和原理", font_size=28)
        intro_content.next_to(intro_title, DOWN, buff=1)
        self.play(Write(intro_content))
        self.wait(5)
        
        # 第二部分：核心内容 (45秒)
        self.play(FadeOut(intro_title), FadeOut(intro_content))
        core_title = Text("第二部分：核心内容", font_size=36, color=ORANGE)
        core_title.next_to(title, DOWN, buff=1)
        self.play(Write(core_title))
        self.wait(2)
        
        # 添加一些图形元素
        circle = Circle(radius=1, color=YELLOW)
        circle.next_to(core_title, DOWN, buff=1)
        self.play(Create(circle))
        self.wait(3)
        
        # 添加文字说明
        explanation = Text("这是核心概念的可视化表示", font_size=24)
        explanation.next_to(circle, DOWN, buff=1)
        self.play(Write(explanation))
        self.wait(5)
        
        # 第三部分：应用示例 (30秒)
        self.play(FadeOut(core_title), FadeOut(circle), FadeOut(explanation))
        app_title = Text("第三部分：应用示例", font_size=36, color=PURPLE)
        app_title.next_to(title, DOWN, buff=1)
        self.play(Write(app_title))
        self.wait(2)
        
        # 简单的图表
        axes = Axes(
            x_range=[-3, 3, 1],
            y_range=[-3, 3, 1],
            x_length=4,
            y_length=4,
            axis_config={{"color": WHITE}},
        ).next_to(app_title, DOWN, buff=1)
        
        graph = axes.plot(lambda x: x**2, color=YELLOW)
        self.play(Create(axes))
        self.wait(2)
        self.play(Create(graph))
        self.wait(5)
        
        # 总结 (15秒)
        self.play(FadeOut(app_title), FadeOut(axes), FadeOut(graph))
        summary = Text("总结", font_size=36, color=RED)
        summary.next_to(title, DOWN, buff=1)
        self.play(Write(summary))
        self.wait(2)
        
        summary_content = Text("通过这个视频，我们学习了基本概念、核心内容和应用示例", font_size=24)
        summary_content.next_to(summary, DOWN, buff=1)
        self.play(Write(summary_content))
        self.wait(5)
        
        # 结束
        self.play(FadeOut(title), FadeOut(summary), FadeOut(summary_content))
        self.wait(2)
        
        # 感谢观看
        thanks = Text("感谢观看！", font_size=32, color=GOLD)
        self.play(Write(thanks))
        self.wait(3)
        self.play(FadeOut(thanks))
        self.wait(1)
'''
    
    async def _execute_manim_code(self, manim_code: str, topic: str) -> str:
        """在临时目录中执行Manim代码以生成视频"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        video_name = f"video_{self._clean_class_name(topic)}_{timestamp}.mp4"
        
        # 检查Manim是否安装
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                ["manim", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                raise FileNotFoundError("Manim not found")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            logger.warning("Manim未安装，使用简化视频生成")
            return await self._create_simple_video(topic, manim_code)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # 写入Manim代码到临时文件
            scene_file = os.path.join(temp_dir, "scene.py")
            with open(scene_file, 'w', encoding='utf-8') as f:
                f.write(manim_code)
            
            # 执行Manim命令
            cmd = ["manim", "scene.py", "DefaultScene", "-qm", "--disable_caching"]
            
            try:
                logger.info(f"正在执行Manim命令: {' '.join(cmd)}")
                logger.info(f"工作目录: {temp_dir}")
                
                # 使用subprocess.run在asyncio中执行
                result = await asyncio.to_thread(
                    subprocess.run,
                    cmd,
                    cwd=temp_dir,
                    capture_output=True,
                    text=True,
                    timeout=600  # 10分钟超时
                )
                
                logger.info(f"Manim stdout: {result.stdout}")
                if result.stderr:
                    logger.warning(f"Manim stderr: {result.stderr}")
                
                if result.returncode != 0:
                    error_msg = result.stderr if result.stderr else "Unknown error"
                    logger.error(f"Manim执行失败: {error_msg}")
                    # 回退到简化视频生成
                    return await self._create_simple_video(topic, manim_code)
                
                # 查找生成的视频文件 - 尝试多个可能的路径
                possible_paths = [
                    os.path.join(temp_dir, "media", "videos", "scene", "720p30"),
                    os.path.join(temp_dir, "media", "videos", "scene", "1080p60"),
                    os.path.join(temp_dir, "media", "videos", "scene", "480p15"),
                    os.path.join(temp_dir, "media", "videos", "scene"),
                ]
                
                video_found = False
                for media_dir in possible_paths:
                    if os.path.exists(media_dir):
                        logger.info(f"检查目录: {media_dir}")
                        for file in os.listdir(media_dir):
                            if file.endswith('.mp4'):
                                source_path = os.path.join(media_dir, file)
                                target_path = os.path.join(self.output_dir, video_name)
                                
                                # 复制视频文件到输出目录
                                import shutil
                                shutil.copy2(source_path, target_path)
                                
                                logger.info(f"视频文件已保存: {target_path}")
                                video_found = True
                                return video_name
                
                if not video_found:
                    logger.warning("未找到Manim生成的视频文件，使用简化视频生成")
                    return await self._create_simple_video(topic, manim_code)
                
            except Exception as e:
                logger.error(f"执行Manim代码时出错: {e}")
                logger.warning("回退到简化视频生成")
                return await self._create_simple_video(topic, manim_code)
    
    async def _create_simple_video(self, topic: str, content: str) -> str:
        """创建简化的视频文件（使用FFmpeg生成静态图片视频）"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            video_name = f"video_{self._clean_class_name(topic)}_{timestamp}.mp4"
            video_path = os.path.join(self.output_dir, video_name)
            
            # 创建临时图片
            import matplotlib.pyplot as plt
            import matplotlib
            matplotlib.use('Agg')
            
            fig, ax = plt.subplots(figsize=(16, 9))
            ax.set_facecolor('#f0f0f0')
            ax.text(0.5, 0.7, topic, fontsize=48, ha='center', va='center', 
                   color='#003366', weight='bold', transform=ax.transAxes)
            ax.text(0.5, 0.5, "AI教师助手生成", fontsize=24, ha='center', va='center',
                   color='#666666', transform=ax.transAxes)
            ax.text(0.5, 0.3, "教学视频", fontsize=32, ha='center', va='center',
                   color='#409EFF', transform=ax.transAxes)
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            ax.axis('off')
            
            # 保存图片
            temp_image = os.path.join(self.output_dir, f"temp_{timestamp}.png")
            plt.savefig(temp_image, dpi=150, bbox_inches='tight')
            plt.close(fig)
            
            # 使用FFmpeg创建视频
            # 注意：libx264 在 yuv420p 像素格式下要求宽高必须为偶数，这里通过 scale 滤镜强制取偶数，避免 height not divisible by 2 报错
            cmd = [
                "ffmpeg",
                "-loop", "1",
                "-i", temp_image,
                "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
                "-c:v", "libx264",
                "-t", "10",  # 10秒视频
                "-pix_fmt", "yuv420p",
                "-y",
                video_path
            ]
            
            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            # 清理临时图片
            try:
                os.remove(temp_image)
            except:
                pass
            
            if result.returncode == 0:
                logger.info(f"简化视频生成成功: {video_name}")
                return video_name
            else:
                logger.error(f"FFmpeg执行失败: {result.stderr}")
                raise Exception("视频生成失败")
                
        except FileNotFoundError:
            logger.error("FFmpeg未安装，无法生成视频")
            raise Exception("FFmpeg未安装，请先安装FFmpeg")
        except Exception as e:
            logger.error(f"简化视频生成失败: {e}")
            raise
    
    async def get_video_info(self, filename: str) -> Dict[str, Any]:
        """获取视频文件信息"""
        file_path = os.path.join(self.output_dir, filename)
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"视频文件不存在: {filename}")
        
        stat = os.stat(file_path)
        
        return {
            "filename": filename,
            "size_bytes": stat.st_size,
            "created_time": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "modified_time": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "file_path": file_path
        }
