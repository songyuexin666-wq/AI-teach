import os
import io
import re
import shutil
import logging
import tempfile
from datetime import datetime
from typing import Optional, Dict, Any, List, Union, Tuple
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # 使用非交互式后端
from sympy import latex, symbols, sympify
from PIL import Image
import requests
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class EnhancedPPTGenerator:
    """增强的PPT生成器 - 支持数学公式和图片"""
    
    def __init__(self, openai_client=None, ai_model: str = "qwen-long"):
        self.openai_client = openai_client
        self.ai_model = ai_model
        self.output_dir = "outputs/ppt"
        self.temp_dir = "temp"
        self._ensure_directories()
        
        # 数学公式配置
        self.math_config = {
            'font_size': 16,
            'dpi': 300,
            'format': 'png',
            'transparent': True
        }
        
        # 图片配置
        self.image_config = {
            'max_width': Inches(8),
            'max_height': Inches(6),
            'quality': 95
        }
        self.image_download_max_bytes = 5 * 1024 * 1024
    
    def _ensure_directories(self):
        """确保输出目录存在"""
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.temp_dir, exist_ok=True)

    @staticmethod
    def _is_http_url(s: str) -> bool:
        t = (s or "").strip()
        return t.startswith("http://") or t.startswith("https://")

    def _public_backend_base(self) -> str:
        """用于把 /api/... 相对图片地址拼成可请求的绝对 URL（服务端下载用）。"""
        base = (os.getenv("PUBLIC_BACKEND_URL") or os.getenv("BACKEND_PUBLIC_URL") or "").strip().rstrip("/")
        if not base:
            port = (os.getenv("PORT") or "7878").strip()
            base = f"http://127.0.0.1:{port}"
        return base

    def _resolve_absolute_image_url(self, url: str) -> str:
        u = (url or "").strip()
        if not u:
            return ""
        if self._is_http_url(u):
            return u
        if u.startswith("//"):
            return "https:" + u
        if u.startswith("/"):
            return self._public_backend_base() + u
        return u

    def _extract_markdown_image_urls(self, text: str) -> List[str]:
        if not text:
            return []
        return [u.strip() for u in re.findall(r"!\[[^\]]*\]\(([^)]+)\)", text) if u.strip()]

    def _extract_all_image_urls(self, text: str) -> List[str]:
        """收集本页可能出现的配图 URL：Markdown 图、[IMAGE:url]、正文中的裸图片链接。"""
        if not text:
            return []
        found: List[str] = []
        seen = set()
        for u in self._extract_markdown_image_urls(text):
            u = u.strip()
            if u and u not in seen:
                seen.add(u)
                found.append(u)
        for m in re.finditer(r"\[IMAGE:\s*([^\]]+)\]", text):
            inner = (m.group(1) or "").strip()
            if self._is_http_url(inner) or inner.startswith("/"):
                if inner not in seen:
                    seen.add(inner)
                    found.append(inner)
        for m in re.finditer(
            r"(https?://[^\s<>\[\]()\"'{}|\\^`]+?\.(?:png|jpe?g|gif|webp)(?:\?[^\s<>\[\]()\"'{}|\\^`]*)?)",
            text,
            flags=re.IGNORECASE,
        ):
            u = m.group(1).strip().rstrip(").,;，。）】")
            if u not in seen:
                seen.add(u)
                found.append(u)
        return found

    def _strip_image_syntax_from_text(self, text: str) -> str:
        """去掉已单独插入 PPT 的配图标记，避免正文重复显示。"""
        if not text:
            return text
        lines_out: List[str] = []
        for line in text.split("\n"):
            s = line.strip()
            if re.match(r"^!\[[^\]]*\]\([^)]+\)\s*$", s):
                continue
            if re.match(r"^\[IMAGE:\s*https?://[^\]]+\]\s*$", s):
                continue
            if re.match(r"^\[IMAGE:\s*/[^\]]+\]\s*$", s):
                continue
            if self._is_http_url(s) and re.search(r"\.(png|jpe?g|gif|webp)(\?|$)", s, re.I):
                continue
            if s.startswith("/") and re.search(r"\.(png|jpe?g|gif|webp)(\?|$)", s, re.I):
                continue
            # 独占一行的 [IMAGE:...]（含占位描述），右侧已插图则不再重复正文
            if re.match(r"^\[IMAGE:\s*[^\]]+\]\s*$", s):
                continue
            lines_out.append(line)
        out = "\n".join(lines_out)
        out = re.sub(r"!\[[^\]]*\]\([^)]+\)\s*", "", out)
        out = re.sub(r"\[IMAGE:\s*https?://[^\]]+\]\s*", "", out)
        out = re.sub(r"\[IMAGE:\s*/[^\]]+\]\s*", "", out)
        return out.strip()

    def _download_image_from_url(self, url: str) -> Optional[str]:
        """下载远程图片到本地临时文件，供 python-pptx 插入。失败返回 None。"""
        url = self._resolve_absolute_image_url((url or "").strip())
        if not self._is_http_url(url):
            return None
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https"):
                return None
            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; AI-Teach-PPT/1.0)",
                "Accept": "image/*,*/*;q=0.8",
            }
            resp = requests.get(url, timeout=25, headers=headers)
            resp.raise_for_status()
            body = resp.content
            if not body or len(body) > self.image_download_max_bytes:
                logger.warning("图片过大或为空，跳过: %s", url[:80])
                return None
            ct = (resp.headers.get("content-type") or "").lower()
            if "svg" in ct or url.lower().endswith(".svg"):
                logger.warning("暂不支持 SVG 配图: %s", url[:80])
                return None
            ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            raw_path = os.path.join(self.temp_dir, f"dl_{ts}_raw")
            with open(raw_path, "wb") as f:
                f.write(body)
            try:
                im = Image.open(raw_path)
                im.verify()
            except Exception as e:
                logger.warning("下载内容不是有效图片: %s — %s", url[:80], e)
                try:
                    os.remove(raw_path)
                except OSError:
                    pass
                return None
            im = Image.open(raw_path)
            if im.mode in ("RGBA", "P"):
                im = im.convert("RGBA")
                png_path = os.path.join(self.temp_dir, f"dl_{ts}.png")
                im.save(png_path, format="PNG")
                try:
                    os.remove(raw_path)
                except OSError:
                    pass
                return png_path
            rgb = im.convert("RGB")
            png_path = os.path.join(self.temp_dir, f"dl_{ts}.png")
            rgb.save(png_path, format="PNG")
            try:
                os.remove(raw_path)
            except OSError:
                pass
            return png_path
        except Exception as e:
            logger.warning("下载配图失败 %s: %s", (url or "")[:100], e)
            return None

    def _try_set_slide_image_from_urls(self, slide_dict: Dict[str, Any], urls: List[str]) -> None:
        for u in urls:
            path = self._download_image_from_url(u)
            if path:
                slide_dict["has_image"] = True
                slide_dict["image_path"] = path
                return
    
    async def generate_enhanced_ppt(
        self, 
        topic: str, 
        template: str = "professional",
        length: Union[int, str] = 10,
        scene: str = "教学课件",
        audience: str = "学生",
        lang: str = "zh",
        kb_id: Optional[list] = None,
        prompt: Optional[str] = None,
        rag_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """生成增强版PPT - 支持公式和图片；可选结合知识库检索上下文"""
        try:
            # 转换长度参数
            if isinstance(length, str):
                length_map = {"short": 8, "medium": 15, "long": 25}
                length = length_map.get(length.lower(), 15)
            
            # 生成PPT内容（包含公式和图片标记；若有知识库检索结果则一并传入）
            content = await self._generate_enhanced_content(
                topic, length, scene, audience, prompt, rag_context=rag_context
            )
            
            # 创建增强版PPT文件
            ppt_filename = self._create_enhanced_ppt_file(topic, content, template)
            
            return {
                "success": True,
                "data": {
                    "filename": ppt_filename,
                    "content": content,
                    "download_url": f"/api/media/files/ppt/{ppt_filename}/download",
                    "cover_url": None,
                    "created_time": datetime.now().isoformat(),
                    "features": ["数学公式", "图片支持", "增强布局"]
                },
                "message": "增强版PPT生成成功"
            }
            
        except Exception as e:
            logger.error(f"增强版PPT生成失败: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"增强版PPT生成失败: {str(e)}",
                "data": None
            }
    
    async def _generate_enhanced_content(
        self, 
        topic: str, 
        length: int, 
        scene: str, 
        audience: str, 
        prompt: Optional[str] = None,
        rag_context: Optional[str] = None,
    ) -> str:
        """生成包含公式和图片标记的内容；可选结合知识库检索上下文"""
        if not self.openai_client:
            return self._get_fallback_enhanced_content(topic, length)
        
        try:
            # 定义数学公式示例（避免在f-string中使用反斜杠）
            math_examples = """
数学公式示例：
- 简单公式：$E = mc^2$
- 复杂公式：$$\\int_{-\\infty}^{\\infty} e^{-x^2} dx = \\sqrt{\\pi}$$
- 矩阵：$$\\begin{pmatrix} a & b \\\\ c & d \\end{pmatrix}$$"""

            image_examples = """
图片标记（优先使用可公开访问的 http/https 图片 URL，便于插入真实配图）：
- Markdown：![](https://upload.wikimedia.org/wikipedia/commons/thumb/.../xxx.png)
- 或：[IMAGE:https://example.com/diagram.png]
- 若无合适 URL，再用文字描述占位：[IMAGE:函数图像示意图]"""

            system_prompt = f"""你是一位专业的{scene}内容规划师，擅长为{audience}设计包含数学公式和图片的教学内容。

请为以下主题生成一个包含{length}个幻灯片的PPT内容，要求：
1. 内容专业、准确
2. 包含数学公式（使用LaTeX格式，用$$包围）
3. 需要配图时优先使用 Markdown 图片 ![](https://...) 或 [IMAGE:https://...]；若无 URL 再用 [IMAGE:描述]
4. 结构清晰，适合{audience}理解

{math_examples}

{image_examples}"""
            
            rag_section = ""
            if rag_context and rag_context.strip():
                rag_section = f"""
以下为知识库检索到的相关材料，请结合这些内容生成PPT（可引用、概括或拓展）：
---
{rag_context[:8000]}
---
"""
            user_prompt = f"""
主题：{topic}
场景：{scene}
受众：{audience}
幻灯片数量：{length}
额外要求：{prompt or "无"}
{rag_section}

请生成详细的PPT内容，每个幻灯片包含：标题、主要内容（可含数学公式和[IMAGE:描述]）、重点强调。

重要格式要求（必须遵守）：
- 每一页必须以单独一行作为该页标题，格式只能为“第N页：标题”或“N. 标题”（N为数字），例如：第1页：概述、2. 核心概念
- 标题下一行开始写该页正文，直到下一个“第X页：”或“X. ”标题行
- 使用中文；可包含$$公式$$、![](图片URL) 或 [IMAGE:URL/描述]；内容适合{audience}理解
- 至少 2 页请给出可公开访问的 https 配图（整页一行即可）：![](https://...) 或 [IMAGE:https://...]，便于插入真实图片；其余页可无图或用文字 [IMAGE:示意图说明]
"""
            
            response = self.openai_client.chat.completions.create(
                model=self.ai_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=4000,
                temperature=0.7
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"增强内容生成失败: {e}")
            return self._get_fallback_enhanced_content(topic, length)
    
    def _create_enhanced_ppt_file(self, topic: str, content: str, template: str) -> str:
        """创建增强版PPT文件"""
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
            subtitle.text = "AI教师助手生成 - 增强版"
            
            # 设置标题样式
            title.text_frame.paragraphs[0].font.size = Pt(44)
            title.text_frame.paragraphs[0].font.color.rgb = RGBColor(0, 51, 102)
            subtitle.text_frame.paragraphs[0].font.size = Pt(24)
            subtitle.text_frame.paragraphs[0].font.color.rgb = RGBColor(102, 102, 102)
            
            # 解析内容并添加幻灯片
            slides_content = self._parse_enhanced_content_to_slides(content, topic=topic)
            
            for slide_content in slides_content:
                self._add_enhanced_slide(prs, slide_content)
            
            # 保存文件
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"enhanced_presentation_{self._clean_filename(topic)}_{timestamp}.pptx"
            filepath = os.path.join(self.output_dir, filename)
            
            prs.save(filepath)
            logger.info(f"增强版PPT文件已保存: {filepath}")
            
            return filename
            
        except Exception as e:
            logger.error(f"增强版PPT文件创建失败: {e}")
            raise
    
    def _add_enhanced_slide(self, prs: Presentation, slide_content: Dict[str, Any]):
        """添加增强版幻灯片 - 优化排版和样式"""
        # 从文本中提取公式图片 token，后续作为独立图片插入
        cleaned_content, math_images = self._extract_math_images(slide_content.get('content', ''))
        slide_content = {**slide_content, "content": cleaned_content}

        # 选择布局
        if slide_content.get('has_image', False):
            # 有图片的布局 - 使用空白布局自定义排版
            slide_layout = prs.slide_layouts[6]  # 空白布局
            slide = prs.slides.add_slide(slide_layout)
            
            # 添加背景色
            background = slide.background
            fill = background.fill
            fill.solid()
            fill.fore_color.rgb = RGBColor(248, 249, 250)  # 浅灰色背景
            
            # 添加标题区域背景
            title_bg = slide.shapes.add_shape(
                MSO_SHAPE.RECTANGLE, 
                Inches(0.5), Inches(0.3), Inches(12.3), Inches(1.2)
            )
            title_bg.fill.solid()
            title_bg.fill.fore_color.rgb = RGBColor(0, 51, 102)  # 深蓝色
            title_bg.line.fill.background()
            
            # 添加标题
            title_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.5), Inches(11.5), Inches(0.8))
            title_frame = title_box.text_frame
            title_frame.text = slide_content.get('title', '')
            title_frame.paragraphs[0].font.size = Pt(28)
            title_frame.paragraphs[0].font.color.rgb = RGBColor(255, 255, 255)  # 白色文字
            title_frame.paragraphs[0].font.bold = True
            title_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
            
            # 添加内容区域背景
            content_bg = slide.shapes.add_shape(
                MSO_SHAPE.RECTANGLE, 
                Inches(0.5), Inches(1.8), Inches(6), Inches(4.5)
            )
            content_bg.fill.solid()
            content_bg.fill.fore_color.rgb = RGBColor(255, 255, 255)  # 白色背景
            content_bg.line.color.rgb = RGBColor(200, 200, 200)
            content_bg.line.width = Pt(1)
            
            # 添加内容
            content_box = slide.shapes.add_textbox(Inches(0.8), Inches(2.1), Inches(5.4), Inches(3.9))
            content_frame = content_box.text_frame
            content_frame.text = slide_content.get('content', '')
            content_frame.margin_left = Inches(0.2)
            content_frame.margin_right = Inches(0.2)
            content_frame.margin_top = Inches(0.2)
            content_frame.margin_bottom = Inches(0.2)
            
            # 设置内容样式
            for paragraph in content_frame.paragraphs:
                paragraph.font.size = Pt(16)
                paragraph.font.color.rgb = RGBColor(51, 51, 51)
                paragraph.space_after = Pt(6)

            # 插入公式图片（放在内容区域下方，避免影响正文排版）
            if math_images:
                x = Inches(0.9)
                y = Inches(6.35)
                w = Inches(5.2)
                h = Inches(0.9)
                for idx, img_path in enumerate(math_images[:3]):  # 避免一页塞太多导致遮挡
                    try:
                        slide.shapes.add_picture(img_path, x, y + Inches(0.95) * idx, width=w, height=h)
                    except Exception as e:
                        logger.warning(f"添加公式图片失败: {e}")
            
            # 添加图片区域背景
            image_bg = slide.shapes.add_shape(
                MSO_SHAPE.RECTANGLE, 
                Inches(7), Inches(1.8), Inches(5.8), Inches(4.5)
            )
            image_bg.fill.solid()
            image_bg.fill.fore_color.rgb = RGBColor(255, 255, 255)  # 白色背景
            image_bg.line.color.rgb = RGBColor(200, 200, 200)
            image_bg.line.width = Pt(1)
            
            # 添加图片
            if slide_content.get('image_path'):
                try:
                    slide.shapes.add_picture(
                        slide_content['image_path'], 
                        Inches(7.2), Inches(2.1), 
                        Inches(5.4), Inches(3.9)
                    )
                except Exception as e:
                    logger.warning(f"添加图片失败: {e}")
                    # 不添加占位符，直接跳过图片
                    logger.info("跳过图片添加，继续处理其他内容")
        else:
            # 普通内容布局 - 优化样式
            content_slide = prs.slides.add_slide(prs.slide_layouts[1])
            
            # 添加背景色
            background = content_slide.background
            fill = background.fill
            fill.solid()
            fill.fore_color.rgb = RGBColor(248, 249, 250)  # 浅灰色背景
            
            title_shape = content_slide.shapes.title
            content_shape = content_slide.placeholders[1]
            
            # 设置标题样式
            title_shape.text = slide_content.get('title', '')
            title_shape.text_frame.paragraphs[0].font.size = Pt(32)
            title_shape.text_frame.paragraphs[0].font.color.rgb = RGBColor(0, 51, 102)
            title_shape.text_frame.paragraphs[0].font.bold = True
            title_shape.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
            
            # 添加标题背景
            title_bg = content_slide.shapes.add_shape(
                MSO_SHAPE.RECTANGLE, 
                Inches(0.5), Inches(0.3), Inches(12.3), Inches(1.2)
            )
            title_bg.fill.solid()
            title_bg.fill.fore_color.rgb = RGBColor(0, 51, 102)
            title_bg.line.fill.background()
            title_bg.z_order = -1  # 置于底层
            
            # 设置内容样式
            content_shape.text = slide_content.get('content', '')
            content_shape.text_frame.margin_left = Inches(0.5)
            content_shape.text_frame.margin_right = Inches(0.5)
            content_shape.text_frame.margin_top = Inches(0.3)
            content_shape.text_frame.margin_bottom = Inches(0.3)
            
            for paragraph in content_shape.text_frame.paragraphs:
                paragraph.font.size = Pt(18)
                paragraph.font.color.rgb = RGBColor(51, 51, 51)
                paragraph.space_after = Pt(8)
                paragraph.line_spacing = 1.2

            # 插入公式图片（放在内容占位符底部区域）
            if math_images:
                x = Inches(1.0)
                y = Inches(6.15)
                w = Inches(11.3)
                h = Inches(1.0)
                for idx, img_path in enumerate(math_images[:2]):
                    try:
                        content_slide.shapes.add_picture(img_path, x, y + Inches(1.05) * idx, width=w, height=h)
                    except Exception as e:
                        logger.warning(f"添加公式图片失败: {e}")
    
    def _parse_enhanced_content_to_slides(self, content: str, topic: str = "") -> List[Dict[str, Any]]:
        """解析增强内容为幻灯片数据"""
        slides = []
        lines = content.split('\n')
        current_slide = {}
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 检测幻灯片标题（多种格式，避免解析不到导致无内容）
            def _is_header(l: str) -> bool:
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

            if _is_header(line):
                if current_slide:
                    slides.append(self._process_slide_content(current_slide))
                raw = line.strip()
                if raw.startswith('##'):
                    title = raw.lstrip('#').strip()
                elif len(raw) >= 2 and raw[0].isdigit() and raw[1] in '.．。、':
                    title = raw[raw.index(raw[1]) + 1:].strip() or raw
                elif len(raw) >= 2 and raw[0] in '一二三四五六七八九十' and raw[1] in '、．.。':
                    title = raw[2:].strip() or raw
                else:
                    title = raw
                current_slide = {
                    'title': title,
                    'content': '',
                    'has_image': False,
                    'image_path': None
                }
            elif current_slide:
                # 正文中的 Markdown 图片 ![](url) / 裸链 / [IMAGE:url] → 尝试下载真实配图
                self._try_set_slide_image_from_urls(current_slide, self._extract_all_image_urls(line))

                processed_line = self._process_content_line(line)
                current_slide['content'] += processed_line + '\n'

                # [IMAGE: ...]：支持冒号后空格；http(s) 或 /api/... 相对路径则下载；否则占位图
                if '[IMAGE:' in line:
                    current_slide['has_image'] = True
                    m_img = re.search(r"\[IMAGE:\s*([^\]]+)\]", line)
                    inner = (m_img.group(1) or "").strip() if m_img else ""
                    resolved = self._resolve_absolute_image_url(inner)
                    if self._is_http_url(resolved) or inner.startswith("/"):
                        path = self._download_image_from_url(inner)
                        if path:
                            current_slide['image_path'] = path
                        elif not current_slide.get('image_path'):
                            current_slide['image_path'] = self._generate_placeholder_image(line)
                    else:
                        if not current_slide.get('image_path'):
                            current_slide['image_path'] = self._generate_placeholder_image(line)
        
        if current_slide:
            slides.append(self._process_slide_content(current_slide))

        # 若解析不到任何页，用整段内容作为一页，避免只有封面
        if not slides and content.strip():
            slides.append(self._process_slide_content({
                'title': (topic or '课件') + ' - 内容',
                'content': content.strip()[:3000],
                'has_image': False,
                'image_path': None
            }))
        return slides
    
    def _process_content_line(self, line: str) -> str:
        """处理内容行：将 LaTeX 公式替换为图片 token

        说明：python-pptx 不支持将图片真正“内联”到文本 run 中，所以我们先生成图片并在文本中放置 token，
        在真正写入 PPTX 时再把 token 对应的图片作为独立图片插入到内容区域下方。
        """
        # 查找数学公式
        math_pattern = r'\$\$(.*?)\$\$'
        # 行内公式：避免把 "$$"（块公式分隔符）当成行内公式
        inline_math_pattern = r'(?<!\$)\$([^$\n]+?)\$(?!\$)'
        
        # 处理块级公式
        def replace_block_math(match):
            formula = (match.group(1) or "").strip()
            if not formula:
                # 空块公式，直接移除，避免渲染 "$$" 触发解析错误
                return ""
            try:
                # 生成公式图片
                image_path = self._render_math_formula(formula, is_block=True)
                return f"[[MATHIMG:{image_path}]]"
            except Exception as e:
                logger.warning(f"公式渲染失败: {e}")
                return f"[公式: {formula}]"
        
        # 处理行内公式
        def replace_inline_math(match):
            formula = (match.group(1) or "").strip()
            if not formula:
                return "$"
            try:
                # 生成公式图片
                image_path = self._render_math_formula(formula, is_block=False)
                return f"[[MATHIMG:{image_path}]]"
            except Exception as e:
                logger.warning(f"公式渲染失败: {e}")
                return f"[公式: {formula}]"
        
        # 替换公式
        line = re.sub(math_pattern, replace_block_math, line)
        line = re.sub(inline_math_pattern, replace_inline_math, line)
        
        return line
    
    def _render_math_formula(self, formula: str, is_block: bool = False) -> str:
        """渲染数学公式为图片

        - 优先使用 LaTeX（系统有 pdflatex 时，matplotlib usetex=True），效果更接近“用 LaTeX 编译”
        - 若环境没有 LaTeX，则回退到 matplotlib mathtext（支持子集，但保证可用）
        """
        try:
            if not (formula or "").strip():
                raise ValueError("空公式，跳过渲染")
            has_pdflatex = shutil.which("pdflatex") is not None
            # 设置matplotlib
            plt.rcParams['mathtext.fontset'] = 'stix'
            plt.rcParams['font.family'] = 'STIXGeneral'
            
            # 创建图形
            fig, ax = plt.subplots(figsize=(8, 2) if is_block else (4, 1))
            ax.axis('off')
            
            # 渲染公式
            if has_pdflatex:
                plt.rcParams['text.usetex'] = True
                tex = formula.strip()
                if is_block:
                    tex = r"\displaystyle " + tex
                ax.text(
                    0.5, 0.5, f"${tex}$",
                    fontsize=self.math_config['font_size'],
                    ha='center', va='center',
                    transform=ax.transAxes
                )
            else:
                plt.rcParams['text.usetex'] = False
                ax.text(
                    0.5, 0.5, f'${formula}$',
                    fontsize=self.math_config['font_size'],
                    ha='center', va='center',
                    transform=ax.transAxes
                )
            
            # 保存图片
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filename = f"math_formula_{timestamp}.png"
            filepath = os.path.join(self.temp_dir, filename)
            
            plt.savefig(filepath, 
                       dpi=self.math_config['dpi'],
                       format=self.math_config['format'],
                       transparent=self.math_config['transparent'],
                       bbox_inches='tight')
            plt.close(fig)
            
            return filepath
            
        except Exception as e:
            logger.error(f"数学公式渲染失败: {e}")
            raise

    def _extract_math_images(self, text: str) -> Tuple[str, List[str]]:
        """从内容文本中提取 [[MATHIMG:...]] token，返回清理后的文本与图片路径列表。"""
        if not text:
            return text, []
        images: List[str] = []

        def _repl(m):
            p = (m.group(1) or "").strip()
            if p:
                images.append(p)
            return "（公式见下）"

        cleaned = re.sub(r"\[\[MATHIMG:(.*?)\]\]", _repl, text)
        return cleaned, images
    
    def _generate_placeholder_image(self, description: str) -> str:
        """生成占位图片"""
        try:
            # 创建占位图片
            fig, ax = plt.subplots(figsize=(8, 6))
            ax.axis('off')
            
            # 添加描述文本
            ax.text(0.5, 0.5, f"图片占位符\n{description}", 
                   fontsize=16, ha='center', va='center',
                   transform=ax.transAxes,
                   bbox=dict(boxstyle="round,pad=0.3", facecolor="lightgray"))
            
            # 保存图片
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filename = f"placeholder_{timestamp}.png"
            filepath = os.path.join(self.temp_dir, filename)
            
            plt.savefig(filepath, dpi=150, bbox_inches='tight')
            plt.close(fig)
            
            return filepath
            
        except Exception as e:
            logger.error(f"占位图片生成失败: {e}")
            return None
    
    def _process_slide_content(self, slide: Dict[str, Any]) -> Dict[str, Any]:
        """处理幻灯片内容"""
        slide['content'] = (slide.get('content') or '').strip()

        # 整页再扫一遍：Markdown / [IMAGE:url] / 裸图片 URL（避免只出现在多行拼接里）
        if not slide.get('image_path'):
            self._try_set_slide_image_from_urls(slide, self._extract_all_image_urls(slide['content']))

        if '[IMAGE:' in slide['content']:
            slide['has_image'] = True
        # 仅有 Markdown 图链且已成功下载时，也要走「带图」布局
        if slide.get('image_path') and not slide.get('has_image'):
            slide['has_image'] = True

        # 已插入配图（含占位图）时去掉正文中的配图标记，避免与右侧图重复
        if slide.get('image_path'):
            slide['content'] = self._strip_image_syntax_from_text(slide['content'])

        return slide
    
    def _clean_filename(self, filename: str) -> str:
        """清理文件名"""
        # 移除或替换非法字符
        illegal_chars = r'[<>:"/\\|?*]'
        cleaned = re.sub(illegal_chars, '_', filename)
        return cleaned[:50]  # 限制长度
    
    def _get_fallback_enhanced_content(self, topic: str, length: int) -> str:
        """获取回退的增强内容"""
        return f"""
第1页：{topic}概述
• 基本概念介绍
• 学习目标
• 课程大纲

第2页：核心理论
• 理论基础
• 重要公式：$E = mc^2$
• 应用场景

第3页：配图示例（真实图片）
• 以下为公开可访问示意图（用于验证配图插入）
![](https://upload.wikimedia.org/wikipedia/commons/thumb/4/47/PNG_transparency_demonstration_1.png/320px-PNG_transparency_demonstration_1.png)

第4页：实例分析
• 典型例题
• 解题步骤
• 注意事项

第5页：总结
• 知识点回顾
• 重点强调
• 下节课预告
"""
