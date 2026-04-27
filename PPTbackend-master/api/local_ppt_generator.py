import os
import logging
import openai
from datetime import datetime
from typing import Optional, Dict, Any, List, Union
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor

logger = logging.getLogger(__name__)

class LocalPPTGenerator:
    """本地PPT生成器 - 支持多种生成模式"""
    
    def __init__(self, openai_client=None, ai_model: str = "qwen-long"):
        self.openai_client = openai_client
        self.ai_model = ai_model
        self.output_dir = "outputs/ppt"
        self._ensure_output_dir()
        
        # 导入增强版生成器
        try:
            from .enhanced_ppt_generator import EnhancedPPTGenerator
            
            self.enhanced_generator = EnhancedPPTGenerator(openai_client, ai_model)
            self.has_enhanced_generator = True
            logger.info("增强版PPT生成器加载成功")
        except ImportError as e:
            self.has_enhanced_generator = False
            logger.warning(f"增强版生成器加载失败: {e}")
    
    def _ensure_output_dir(self):
        """确保输出目录存在"""
        os.makedirs(self.output_dir, exist_ok=True)
    
    async def generate_ppt(
        self, 
        topic: str, 
        template: str = "professional",
        length: Union[int, str] = 10,
        scene: str = "教学课件",
        audience: str = "学生",
        lang: str = "zh",
        kb_id: Optional[list] = None,
        prompt: Optional[str] = None,
        mode: str = "auto",  # auto, enhanced, standard
        rag_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """生成PPT内容 - 支持多种模式；可选传入知识库检索上下文（增强模式会结合生成）"""
        try:
            # 自动选择最佳生成模式
            if mode == "auto":
                mode = self._select_best_mode(length, prompt)
            
            logger.info(f"使用 {mode} 模式生成PPT")
            
            # 根据选择模式生成PPT（简化版）
            if mode == "enhanced" and self.has_enhanced_generator:
                return await self.enhanced_generator.generate_enhanced_ppt(
                    topic, template, length, scene, audience, lang, kb_id, prompt, rag_context=rag_context
                )
            else:
                # 使用标准模式（原始的两步生成；标准模式内部自行根据 kb_id 检索）
                return await self._generate_ppt_standard(
                    topic, template, length, scene, audience, lang, kb_id, prompt
                )
            
        except Exception as e:
            logger.error(f"PPT生成失败: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"PPT生成失败: {str(e)}",
                "data": None
            }
    
    def _select_best_mode(self, length: Union[int, str], prompt: Optional[str]) -> str:
        """自动选择最佳生成模式（简化版）"""
        
        # 转换长度为数字
        if isinstance(length, str):
            length_map = {"short": 8, "medium": 15, "long": 25}
            length = length_map.get(length.lower(), 15)
        
        # 检查是否需要增强功能（数学公式、图片）
        needs_enhanced = self._needs_enhanced_features(prompt)
        
        if needs_enhanced and self.has_enhanced_generator:
            return "enhanced"
        else:
            # 使用标准模式
            return "standard"
    
    def _needs_enhanced_features(self, prompt: Optional[str]) -> bool:
        """检查是否需要增强功能"""
        if not prompt:
            return False
        
        # 检查关键词
        enhanced_keywords = [
            '公式', '数学', '物理', '化学', '图像', '图片', '图表', 
            '函数', '方程', '计算', '推导', '证明', 'LaTeX'
        ]
        
        prompt_lower = prompt.lower()
        return any(keyword in prompt_lower for keyword in enhanced_keywords)
    
    async def _generate_ppt_standard(
        self,
        topic: str,
        template: str,
        length: Union[int, str],
        scene: str,
        audience: str,
        lang: str,
        kb_id: Optional[list],
        prompt: Optional[str]
    ) -> Dict[str, Any]:
        """标准PPT生成模式（原始的两步生成）"""
        # 转换长度参数为整数
        if isinstance(length, str):
            length_map = {
                "short": 8,
                "medium": 15,
                "long": 25
            }
            length = length_map.get(length.lower(), 15)
        
        # 生成PPT内容大纲
        outline = await self._generate_outline(topic, length, scene, audience, prompt)
        
        # 生成详细内容
        content = await self._generate_content(outline, topic, scene, audience)
        
        # 创建PPT文件
        ppt_filename = self._create_ppt_file(topic, content, template)
        
        return {
            "success": True,
            "data": {
                "filename": ppt_filename,
                "content": content,
                "outline": outline,
                "download_url": f"/api/media/files/ppt/{ppt_filename}/download",
                "cover_url": None,
                "created_time": datetime.now().isoformat()
            },
            "message": "PPT生成成功"
        }
    
    async def _generate_outline(self, topic: str, length: int, scene: str, audience: str, prompt: Optional[str] = None) -> List[Dict[str, Any]]:
        """生成PPT大纲"""
        if not self.openai_client:
            return self._get_fallback_outline(topic, length)
        
        try:
            system_prompt = f"""你是一位专业的PPT内容规划师，擅长为{audience}设计{scene}。
请为以下主题生成一个包含{length}个幻灯片的PPT大纲。"""
            
            user_prompt = f"""
主题：{topic}
场景：{scene}
受众：{audience}
幻灯片数量：{length}
额外要求：{prompt or "无"}

请生成一个结构化的PPT大纲，每个幻灯片单独一行标题，格式必须为“第N页：标题”或“N. 标题”（N为数字），例如：第1页：概述、2. 核心概念。标题下一行写3-5个要点和视觉元素建议。使用中文，结构清晰，适合{audience}理解。
"""
            
            response = self.openai_client.chat.completions.create(
                model=self.ai_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=2000,
                temperature=0.7
            )
            
            outline_text = response.choices[0].message.content.strip()
            return self._parse_outline(outline_text, length)
            
        except Exception as e:
            logger.error(f"大纲生成失败: {e}")
            return self._get_fallback_outline(topic, length)
    
    async def _generate_content(self, outline: List[Dict[str, Any]], topic: str, scene: str, audience: str) -> str:
        """基于大纲生成详细内容"""
        if not self.openai_client:
            return self._get_fallback_content(topic, outline)
        
        try:
            outline_text = "\n".join([f"{i+1}. {slide['title']}: {slide['content']}" for i, slide in enumerate(outline)])
            
            prompt = f"""
基于以下PPT大纲，生成详细的幻灯片内容：

主题：{topic}
场景：{scene}
受众：{audience}

大纲：
{outline_text}

请为每个幻灯片生成详细的内容，包括：
1. 具体的文字内容
2. 关键概念解释
3. 示例和案例
4. 总结要点

重要格式要求（必须遵守，否则无法正确分页）：
- 每一页幻灯片必须用单独一行开头作为该页标题，格式只能为以下之一：
  “第N页：标题” 或 “N. 标题”（N 为数字），例如：第1页：概述、2. 核心概念
- 标题行下一行开始写该页正文，直到下一个“第X页：”或“X. ”标题行为止
- 不要使用“## 标题”或“第一部分”等作为分页，请统一用“第N页：”或“N. ”

要求：
- 内容准确、专业
- 语言适合{audience}理解
- 结构清晰，逻辑性强
- 包含具体的教学要点
"""
            
            response = self.openai_client.chat.completions.create(
                model=self.ai_model,
                messages=[
                    {"role": "system", "content": "你是一位经验丰富的教师，擅长编写教学课件内容。"},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=3000,
                temperature=0.7
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"内容生成失败: {e}")
            return self._get_fallback_content(topic, outline)
    
    def _create_ppt_file(self, topic: str, content: str, template: str) -> str:
        """创建PPT文件"""
        try:
            # 创建新的演示文稿
            prs = Presentation()
            
            # 设置幻灯片尺寸
            prs.slide_width = Inches(13.33)
            prs.slide_height = Inches(7.5)
            
            # 添加标题页
            title_slide = prs.slides.add_slide(prs.slide_layouts[0])
            title = title_slide.shapes.title
            subtitle = title_slide.placeholders[1]
            
            title.text = topic
            subtitle.text = "AI教师助手生成"
            
            # 设置标题样式
            title.text_frame.paragraphs[0].font.size = Pt(44)
            title.text_frame.paragraphs[0].font.color.rgb = RGBColor(0, 51, 102)
            subtitle.text_frame.paragraphs[0].font.size = Pt(24)
            subtitle.text_frame.paragraphs[0].font.color.rgb = RGBColor(102, 102, 102)
            
            # 解析内容并添加幻灯片
            slides_content = self._parse_content_to_slides(content)
            
            for slide_content in slides_content:
                # 添加内容幻灯片
                content_slide = prs.slides.add_slide(prs.slide_layouts[1])
                title_shape = content_slide.shapes.title
                content_shape = content_slide.placeholders[1]
                
                title_shape.text = slide_content.get('title', '')
                content_shape.text = slide_content.get('content', '')
                
                # 设置样式
                title_shape.text_frame.paragraphs[0].font.size = Pt(32)
                title_shape.text_frame.paragraphs[0].font.color.rgb = RGBColor(0, 51, 102)
                
                for paragraph in content_shape.text_frame.paragraphs:
                    paragraph.font.size = Pt(18)
                    paragraph.font.color.rgb = RGBColor(51, 51, 51)
            
            # 保存文件
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"presentation_{self._clean_filename(topic)}_{timestamp}.pptx"
            filepath = os.path.join(self.output_dir, filename)
            
            prs.save(filepath)
            logger.info(f"PPT文件已保存: {filepath}")
            
            return filename
            
        except Exception as e:
            logger.error(f"PPT文件创建失败: {e}")
            raise
    
    def _parse_outline(self, outline_text: str, length: int) -> List[Dict[str, Any]]:
        """解析大纲文本为结构化数据，支持多种标题格式"""
        slides = []
        lines = outline_text.split('\n')
        current_slide = {}

        def _is_outline_header(l: str) -> bool:
            s = l.strip()
            if not s:
                return False
            if s.startswith(('第', 'Slide', '幻灯片')):
                return True
            if len(s) >= 2 and s[0].isdigit() and s[1] in '.．。、':
                return True
            if s.startswith('##'):
                return True
            if len(s) >= 2 and s[0] in '一二三四五六七八九十' and s[1] in '、．.。':
                return True
            return False

        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue

            if _is_outline_header(line_stripped):
                if current_slide:
                    slides.append(current_slide)
                if line_stripped.startswith('##'):
                    title = line_stripped.lstrip('#').strip()
                elif len(line_stripped) >= 2 and line_stripped[0].isdigit() and line_stripped[1] in '.．。、':
                    title = line_stripped[line_stripped.index(line_stripped[1]) + 1:].strip() or line_stripped
                elif len(line_stripped) >= 2 and line_stripped[0] in '一二三四五六七八九十' and line_stripped[1] in '、．.。':
                    title = line_stripped[2:].strip() or line_stripped
                else:
                    title = line_stripped
                current_slide = {'title': title, 'content': '', 'visual_elements': []}
            elif current_slide:
                current_slide['content'] += line + '\n'

        if current_slide:
            slides.append(current_slide)

        while len(slides) < length:
            slides.append({
                'title': f'补充内容 {len(slides) + 1}',
                'content': '相关内容待补充',
                'visual_elements': []
            })
        return slides[:length]
    
    def _parse_content_to_slides(self, content: str) -> List[Dict[str, str]]:
        """将内容解析为幻灯片数据，支持多种标题格式避免解析不到导致无内容"""
        slides = []
        lines = content.split('\n')
        current_title = None
        current_content = []

        def _is_slide_title(line: str) -> bool:
            s = line.strip()
            if not s:
                return False
            # 第X页 / 第X部分 / Slide X / 幻灯片 X
            if s.startswith(('第', 'Slide', '幻灯片')):
                return True
            # 1. 标题 / 2. 标题
            if len(s) >= 2 and s[0].isdigit() and s[1] in '.．。、':
                return True
            # ## Markdown 标题
            if s.startswith('##'):
                return True
            # 一、 二、
            if len(s) >= 2 and s[0] in '一二三四五六七八九十' and s[1] in '、．.。':
                return True
            return False

        def _flush_slide():
            if current_title is not None:
                body = '\n'.join(current_content).strip()
                slides.append({'title': current_title, 'content': body or ''})

        for line in lines:
            if _is_slide_title(line):
                _flush_slide()
                # 去掉 ##、数字. 等前缀，保留可读标题
                raw = line.strip()
                if raw.startswith('##'):
                    current_title = raw.lstrip('#').strip()
                elif len(raw) >= 2 and raw[0].isdigit() and raw[1] in '.．。、':
                    current_title = raw[raw.index(raw[1]) + 1:].strip() or raw
                elif len(raw) >= 2 and raw[0] in '一二三四五六七八九十' and raw[1] in '、．.。':
                    current_title = raw[2:].strip() or raw
                else:
                    current_title = raw
                current_content = []
            else:
                if current_title is None:
                    # 第一块没有明确标题时，用首段作为第一页标题
                    if line.strip() and not slides:
                        current_title = line.strip()[:50]
                        current_content = []
                        continue
                current_content.append(line)

        _flush_slide()
        # 若解析不到任何页，用整段内容作为一页，避免只有封面
        if not slides and content.strip():
            slides.append({'title': topic + ' - 内容', 'content': content.strip()[:3000]})
        return slides
    
    def _get_fallback_outline(self, topic: str, length: int) -> List[Dict[str, Any]]:
        """获取默认大纲"""
        slides = [
            {
                'title': f'{topic} - 概述',
                'content': f'• 什么是{topic}\n• 为什么重要\n• 学习目标',
                'visual_elements': ['图表', '图标']
            },
            {
                'title': f'{topic} - 核心概念',
                'content': '• 基本定义\n• 关键特征\n• 重要原则',
                'visual_elements': ['概念图', '流程图']
            },
            {
                'title': f'{topic} - 实际应用',
                'content': '• 应用场景\n• 案例分析\n• 最佳实践',
                'visual_elements': ['案例图', '示例']
            },
            {
                'title': f'{topic} - 总结',
                'content': '• 要点回顾\n• 关键收获\n• 延伸思考',
                'visual_elements': ['总结图', '思维导图']
            }
        ]
        
        # 扩展到指定长度
        while len(slides) < length:
            slides.append({
                'title': f'{topic} - 补充内容 {len(slides) + 1}',
                'content': '• 相关内容\n• 详细说明\n• 实例演示',
                'visual_elements': ['相关图表']
            })
        
        return slides[:length]
    
    def _get_fallback_content(self, topic: str, outline: List[Dict[str, Any]]) -> str:
        """获取默认内容"""
        content = f"# {topic} 教学课件\n\n"
        
        for i, slide in enumerate(outline, 1):
            content += f"## 第{i}部分：{slide['title']}\n\n"
            content += f"{slide['content']}\n\n"
            content += f"**教学要点：**\n"
            content += f"- 重点概念解释\n"
            content += f"- 实际应用示例\n"
            content += f"- 学生互动环节\n\n"
        
        return content
    
    def _clean_filename(self, filename: str) -> str:
        """清理文件名"""
        import re
        # 移除特殊字符，只保留中文、英文、数字和连字符
        clean_name = re.sub(r'[^\w\u4e00-\u9fff-]', '_', filename)
        return clean_name[:50]  # 限制长度
