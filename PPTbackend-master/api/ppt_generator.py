import os
import httpx
import asyncio
import base64
import gzip
import json
from datetime import datetime
import logging
from typing import Optional, Dict, Any, List, AsyncGenerator, Union, cast
from api.rag_service import RAGService

logger = logging.getLogger(__name__)

class PPTGenerator:
    """
    使用 docmee.cn API 生成PPT演示文稿。
    """
    def __init__(self):
        """
        初始化PPTGenerator。
        从环境变量加载 DOCMEE_API_KEY 和 DOCMEE_API_BASE_URL。
        """
        self.api_key = os.getenv("DOCMEE_API_KEY")

        if not self.api_key:
            logger.warning("DOCMEE_API_KEY 环境变量未设置，PPT生成功能将无法使用。")
        
        self.base_url = os.getenv("DOCMEE_API_BASE_URL", "https://open.docmee.cn/api/ppt/v2")
    
    def _get_headers(self) -> Dict[str, str]:
        """
        获取请求头，包含认证信息。
        
        Raises:
            ValueError: 如果 DOCMEE_API_KEY 未设置。
        """
        if not self.api_key:
            raise ValueError("API key 未配置，无法发送请求。")
        return {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

    async def create_rag_ppt(self, 
                         topic: str,
                         kb_id: List[str] = ["368452a45bbf11f08bcd0242ac110007"], 
                         prompt: Optional[str] = None, 
                         template: str = "modern", 
                         length: str = "medium",
                         scene: Optional[str] = None,
                         audience: Optional[str] = None,
                         lang: str = "zh") -> Dict[str, Any]:
        """
        1. 创建一个PPT生成任务，获取 `task_id`。
        2. 使用 `task_id` 调用内容生成接口，获取Markdown格式的PPT大纲和内容。
        3. 使用 `task_id`、Markdown内容和指定的模板，调用PPTX生成接口。
        4. API返回PPTX文件的base64编码数据。
        5. 解码并保存为 `.pptx` 文件到 `outputs/ppt` 目录下。

        Args:
            topic: PPT主题，也即用于在知识库中检索的查询词。
            kb_id: 知识库ID。
            prompt: 用户的额外要求。
            template: 模板ID。
            length: 篇幅长度：short/medium/long。
            scene: 演示场景。
            audience: 受众。
            lang: 语言。

        Returns:
            {
                'id': '1942481641276575744', # 任务ID
                'name': '质点运动学', # 任务名称
                'subject': '质点运动学', # 任务主题
                'coverUrl': 'https://chatmee.cn/api/public/oss/meta-doc/ppt/133735/xxxxx',
                'fileUrl': 'https://chatmee.cn/api/public/oss/meta-doc/ppt/133735/xxxxx',
                'templateId': '1862040730604896256', # 模板ID
                'pptxProperty': None, # PPTX数据
                'userId': '133735', # 用户ID
                'userName': '133735', 
                'companyId': 133735,
                'updateTime': '2025-07-08 15:11:49',
                'createTime': '2025-07-08 15:11:49',
                'extInfo': {},
                'totalPage': 19, # 总页数
                'genType': None,
                'createUser': None,
                'updateUser': None
            }
        """
        async with httpx.AsyncClient(timeout=300.0) as client:
            try:
                # 步骤 0: 尝试使用RAG服务获取知识库内容，如果失败则使用默认内容
                rag_content = ""
                try:
                    rag_service = RAGService()
                    rag_data = {
                        "query": topic,
                        "kb_ids": kb_id,
                        "top_k": 5,
                        "similarity_threshold": 0.5,
                        "vector_similarity_weight": 0.3
                    }
                    rag_content = await asyncio.to_thread(rag_service.search, **rag_data)
                    rag_content = "\n".join([item["content"] for item in rag_content])
                    logger.info("成功从知识库检索到内容")
                except Exception as e:
                    logger.warning(f"RAG服务连接失败，使用默认内容: {e}")
                    # 使用默认内容，不依赖知识库
                    rag_content = f"关于{topic}的基础知识和概念"
                
                # 构建内容
                if prompt:
                    content = f'''生成一份全面的{topic}的markdown大纲, 要求包括完整例题和详细解释。额外要求：{prompt}'''
                else:
                    content = f'''生成一份全面的{topic}的markdown大纲, 要求包括完整例题和详细解释。'''
                
                # 步骤 1: 创建任务 (通过markdown生成大纲型)
                task_id = await self.create_task(client, task_type=7, content=content)
                logger.info(f"成功创建PPT任务，任务ID: {task_id}")

                # 步骤 2.1: 生成新内容 (Markdown)
                markdown_content = await self.generate_content(
                    client, task_id, length=length, lang=lang, scene=scene, audience=audience, prompt=prompt
                )
                logger.info(f"为任务 {task_id} 生成Markdown内容成功。")


                # 步骤 3: 根据模板ID, markdown内容  生成 PPTX
                template_id = self.get_template_id(template)
                
                ppt_info = await self.generate_pptx(client, task_id, cast(Dict[str, Any], markdown_content)['text'], template_id)
                logger.info(f"收到任务 {task_id} 的pptInfo。")

                # 步骤 4: 直接返回包含 fileUrl 的 ppt_info
                # 不再依赖 pptxProperty, 而是检查 fileUrl
                if not ppt_info.get("fileUrl"):
                    raise Exception("API响应中未包含 'fileUrl'。")

                return ppt_info

            except httpx.HTTPStatusError as e:
                response_text = e.response.text
                logger.error(f"PPT生成过程中发生HTTP错误: {e.request.url} - {e.response.status_code} - {response_text}")
                try:
                    # 尝试解析JSON错误信息
                    error_data = json.loads(response_text)
                    message = error_data.get("message", "未知错误")
                    raise Exception(f"PPT生成失败: {message}")
                except json.JSONDecodeError:
                    raise Exception(f"PPT生成失败，HTTP状态码: {e.response.status_code}")
            except Exception as e:
                logger.error(f"PPT生成过程中发生未知错误: {e}")
                raise Exception(f"PPT生成失败: {str(e)}")

    async def create_task(self, client: httpx.AsyncClient, task_type: int, content: Optional[str] = None, files: Optional[List[str]] = None) -> str:
        """
        创建任务。

        Args:
            client: httpx.AsyncClient 实例。
            task_type: 类型：1. 智能生成（主题、要求）
                            2. 上传文件生成
                            3. 上传思维导图生成
                            4. 通过 Word 精准转 PPT
                            5. 通过网页链接生成
                            6. 粘贴文本内容生成
                            7. Markdown 大纲生成
            content: 内容：type=1 用户输入主题或要求（不超过 1000 字符）
                            type=2、4 不传
                            type=3 幕布等分享链接
                            type=5 网页链接地址（http/https）
                            type=6 粘贴文本内容（不超过 20000 字符）
                            type=7 大纲内容（markdown）
            files: 文件列表（文件数不超过 5 个，总大小不超过 50M）：
                            type=1 上传参考文件（非必传，支持多个）
                            type=2 上传文件（支持多个）
                            type=3 上传思维导图（xmind/mm/md，仅支持一个）
                            type=4 上传 word 文件（仅支持一个）
                            type=5、6、7 不传
        支持格式：doc/docx/pdf/ppt/pptx/txt/md/xls/xlsx/csv/html/epub/mobi/xmind/mm

        Returns:
            任务ID。
        """
        # --- 参数校验 ---
        if not 1 <= task_type <= 7:
            raise ValueError("task_type 必须是 1 到 7 之间的整数。")

        # 通用文件校验
        MAX_FILES = 5
        MAX_TOTAL_SIZE = 50 * 1024 * 1024  # 50MB
        SUPPORTED_FORMATS = ['.doc', '.docx', '.pdf', '.ppt', '.pptx', '.txt', '.md', '.xls', '.xlsx', '.csv', '.html', '.epub', '.mobi', '.xmind', '.mm']

        if files:
            if len(files) > MAX_FILES:
                raise ValueError(f"文件数量不能超过 {MAX_FILES} 个。")

            total_size = 0
            for file_path in files:
                if not os.path.exists(file_path):
                    raise FileNotFoundError(f"文件未找到: {file_path}")
                
                ext = os.path.splitext(file_path)[1].lower()
                if ext not in SUPPORTED_FORMATS:
                    raise ValueError(f"不支持的文件格式: {ext}。支持的格式为: {', '.join(SUPPORTED_FORMATS)}")
                
                total_size += os.path.getsize(file_path)

            if total_size > MAX_TOTAL_SIZE:
                raise ValueError(f"文件总大小不能超过 {MAX_TOTAL_SIZE / 1024 / 1024:.0f}MB。")

        # 按类型校验
        if task_type == 1:  # 智能生成
            if not content or len(content) > 1000:
                raise ValueError("对于类型1（智能生成），'content' 是必需的，且长度不能超过 1000 字符。")
        elif task_type == 2:  # 上传文件生成
            if content:
                raise ValueError("对于类型2（上传文件生成），不应提供 'content'。")
            if not files:
                raise ValueError("对于类型2（上传文件生成），'files' 是必需的。")
        elif task_type == 3:  # 上传思维导图生成
            if not content and not files:
                 raise ValueError("对于类型3（上传思维导图生成），必须提供 'content' (分享链接) 或 'files' (思维导图文件)。")
            if files:
                if len(files) > 1:
                    raise ValueError("对于类型3（上传思维导图生成），只能上传一个文件。")
                ext = os.path.splitext(files[0])[1].lower()
                if ext not in ['.xmind', '.mm', '.md']:
                    raise ValueError("对于类型3，上传的文件必须是 xmind, mm, 或 md 格式。")
        elif task_type == 4:  # Word 精准转 PPT
            if content:
                raise ValueError("对于类型4（Word转PPT），不应提供 'content'。")
            if not files:
                raise ValueError("对于类型4（Word转PPT），'files' 是必需的。")
            if len(files) > 1:
                raise ValueError("对于类型4（Word转PPT），只能上传一个 Word 文件。")
            ext = os.path.splitext(files[0])[1].lower()
            if ext not in ['.doc', '.docx']:
                raise ValueError("对于类型4，上传的文件必须是 doc 或 docx 格式。")
        elif task_type == 5:  # 网页链接生成
            if not content or not (content.startswith('http://') or content.startswith('https://')):
                raise ValueError("对于类型5（网页链接生成），'content' 必须是有效的 http/https 链接。")
            if files:
                raise ValueError("对于类型5（网页链接生成），不应提供 'files'。")
        elif task_type == 6:  # 粘贴文本内容生成
            if not content or len(content) > 20000:
                 raise ValueError("对于类型6（粘贴文本），'content' 是必需的，且长度不能超过 20000 字符。")
            if files:
                raise ValueError("对于类型6（粘贴文本），不应提供 'files'。")
        elif task_type == 7:  # Markdown 大纲生成
            if not content:
                raise ValueError("对于类型7（Markdown大纲），'content' 是必需的。")
            if files:
                raise ValueError("对于类型7（Markdown大纲），不应提供 'files'。")

        url = f"{self.base_url}/createTask"
        headers = self._get_headers()
        headers.pop('Content-Type', None)

        data = {'type': str(task_type)}
        if content:
            data['content'] = content

        opened_files = []
        try:
            # 如果有文件需要上传
            if files:
                file_payload = []
                # 准备文件以 multipart/form-data 格式上传
                for file_path in files:
                    f = open(file_path, 'rb')
                    opened_files.append(f)
                    # 构建 httpx 需要的 files 格式
                    file_payload.append(('file', (os.path.basename(file_path), f, 'application/octet-stream')))
                # 发送带文件的POST请求
                response = await client.post(url, data=data, files=file_payload, headers=headers)
            else:
                # 发送不带文件的POST请求 (Content-Type: application/x-www-form-urlencoded)
                response = await client.post(url, data=data, headers=headers)

            response.raise_for_status()
            response_data = response.json()

            if response_data.get("code") != 0:
                raise Exception(f"创建任务失败: {response_data.get('message', '未知错误')}")

            task_id = response_data.get("data", {}).get("id")
            if not task_id:
                raise Exception("API响应中缺少任务ID (task_id)。")
            return task_id
        finally:
            for f in opened_files:
                f.close()

    async def get_options(self, client: httpx.AsyncClient, lang: Optional[str] = None) -> Dict[str, Any]:
        """
        获取生成选项，如语种、场景、受众等。

        调用此接口来获得调用 `generate_content` 需要使用的相关选项。
        该接口支持国际化，URL 携带 `lang` 参数可获取指定语种的选项。

        Args:
            client: httpx.AsyncClient 实例。
            lang: 语言代码 (e.g., "zh", "en")。如果为 None，则返回默认语言的选项。

        Returns:
            一个包含 'lang', 'scene', 'audience' 列表的字典。
            例如:
            {
              "lang": [
                { "name": "简体中文", "value": "zh" },
                ...
              ],
              "scene": [
                { "name": "通用场景", "value": "通用场景" },
                ...
              ],
              "audience": [
                { "name": "大众", "value": "大众" },
                ...
              ]
            }
        
        Raises:
            Exception: 当API调用失败或返回错误时。
        """
        url = f"{self.base_url}/options"
        headers = self._get_headers()
        # GET 请求不需要 Content-Type
        headers.pop('Content-Type', None) 
        
        params = {}
        if lang:
            params["lang"] = lang
        
        response = await client.get(url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()

        if data.get("code") != 0:
            raise Exception(f"获取选项失败: {data.get('message', '未知错误')}")
        
        return data.get("data", {})

    async def _generate_content_streaming(self, client: httpx.AsyncClient, task_id: str, length: str, lang: str, scene: Optional[str], audience: Optional[str], prompt: Optional[str]) -> AsyncGenerator[Dict[str, Any], None]:
        """
        处理流式生成内容。
        这是一个内部辅助方法，被 `generate_content` 在 `stream=True` 时调用。

        它会发送一个 POST 请求到 `generateContent` 端点，并设置 `stream=True`。
        然后，它会异步迭代响应行，解析 Server-Sent Events (SSE) 格式的数据。

        Args:
            client: httpx.AsyncClient 实例。
            task_id: 任务ID。
            length: 篇幅长度。
            lang: 语言。
            scene: 演示场景。
            audience: 受众。
            prompt: 用户的额外要求。

        Yields:
            一个字典，代表从流中接收到的一个数据块 (chunk)。
        """
        url = f"{self.base_url}/generateContent"
        payload = {
            "id": task_id,
            "stream": True,
            "length": length,
            "lang": lang,
        }
        if scene:
            payload["scene"] = scene
        if audience:
            payload["audience"] = audience
        if prompt:
            payload["prompt"] = prompt

        async with client.stream("POST", url, json=payload, headers=self._get_headers(), timeout=300.0) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                # SSE 消息以 "data:" 开头
                if line.startswith("data:"):
                    try:
                        # 移除 "data:" 前缀并去除空白
                        chunk_str = line[len("data:"):].strip()
                        if chunk_str:
                            # 解析 JSON 数据块
                            chunk = json.loads(chunk_str)
                            yield chunk
                    except json.JSONDecodeError:
                        logger.warning(f"无法解析收到的流式数据块: {line}")

    async def generate_content(self, 
                             client: httpx.AsyncClient, 
                             task_id: str, 
                             *,
                             stream: bool = False,
                             length: str = "medium", 
                             lang: str = "zh", 
                             scene: Optional[str] = None, 
                             audience: Optional[str] = None, 
                             prompt: Optional[str] = None) -> Union[Dict[str, Any], AsyncGenerator[Dict[str, Any], None]]:
        """
        调用生成大纲及内容API。此方法支持流式和非流式两种模式。

        Args:
            client: httpx.AsyncClient 实例。
            task_id: 任务ID，由 `create_task` 方法返回。
            stream: 是否流式返回。
                    - `True`: 返回一个异步生成器，用于逐块接收内容。
                    - `False`: (默认) 一次性返回完整内容。
            length: 篇幅长度。可选值为 "short", "medium", "long"，分别对应约 10-15页, 20-30页, 25-35页。
            lang: 目标语言。支持的语言代码如: "zh", "zh-Hant", "en", "ja", "ko", "ar", "de", "fr", "it", "pt", "es", "ru"。
            scene: 演示场景。例如: "通用场景", "教学课件", "工作总结" 等。可以传递任意自定义场景类型。
            audience: 受众。例如: "大众", "学生", "上级领导" 等。可以传递任意自定义受众类型。
            prompt: 用户的额外要求，对生成内容进行指导（小于50字）。

        Returns:
            - 如果 `stream=False` (默认), 在 await 后返回一个包含 'text' (Markdown内容) 和 'result' (结果元数据) 的字典。
            - 如果 `stream=True`, 返回一个异步生成器，用于逐块产生内容。
        """
        if stream:
            return self._generate_content_streaming(client, task_id, length, lang, scene, audience, prompt)

        url = f"{self.base_url}/generateContent"
        payload = {
            "id": task_id,
            "stream": False,
            "length": length,
            "lang": lang,
        }
        # 添加可选参数
        if scene:
            payload["scene"] = scene
        if audience:
            payload["audience"] = audience
        if prompt:
            payload["prompt"] = prompt

        response = await client.post(url, json=payload, headers=self._get_headers())
        response.raise_for_status()
        data = response.json()

        if data.get("code") != 0:
            raise Exception(f"生成内容失败: {data.get('message', '未知错误')}")
        
        content_data = data.get("data")
        if not content_data or ("text" not in content_data and "result" not in content_data):
            raise Exception("API响应中缺少 'data' 或 'data' 中缺少 'text'/'result'。")
        return content_data

    # async def update_content(self, client: httpx.AsyncClient, task_id: str, markdown: str, question: str) -> str:
    #     """
    #     根据用户指令修改大纲内容。

    #     Args:
    #         client: httpx.AsyncClient 实例。
    #         task_id: 任务ID。
    #         markdown: 当前的大纲内容。
    #         question: 用户修改建议。

    #     Returns:
    #         修改后的Markdown格式大纲内容。
    #     """
    #     url = f"{self.base_url}/updateContent"
    #     payload = {
    #         "id": task_id,
    #         "stream": False,
    #         "markdown": markdown,
    #         "question": question
    #     }
    #     response = await client.post(url, json=payload, headers=self._get_headers())
    #     response.raise_for_status()
    #     data = response.json()

    #     if data.get("code") != 0:
    #         raise Exception(f"更新内容失败: {data.get('message', '未知错误')}")
        
    #     updated_markdown = data.get("data", {}).get("text")
    #     if not updated_markdown:
    #         raise Exception("API响应中缺少更新后的Markdown内容。")
    #     return updated_markdown

    async def generate_pptx(self, client: httpx.AsyncClient, task_id: str, markdown: str, template_id: str) -> Dict[str, Any]:
        """
        调用生成PPTX API，将 Markdown 内容转换为 PPTX 文件。

        Args:
            client: httpx.AsyncClient 实例。
            task_id: 任务ID。
            markdown: 用于生成PPT的Markdown内容，通常由 `generate_content` 方法返回。
            template_id: 模板ID，可以通过 `get_template_id` 方法或查询模板列表API获取。

        Returns:
            {
                'id': '1942481641276575744', # 任务ID
                'name': '质点运动学', # 任务名称
                'subject': '质点运动学', # 任务主题
                'coverUrl': 'https://chatmee.cn/api/public/oss/meta-doc/ppt/133735/xxxxx',
                'fileUrl': 'https://chatmee.cn/api/public/oss/meta-doc/ppt/133735/xxxxx',
                'templateId': '1862040730604896256', # 模板ID
                'pptxProperty': None, # PPTX数据
                'userId': '133735', # 用户ID
                'userName': '133735', 
                'companyId': 133735,
                'updateTime': '2025-07-08 15:11:49',
                'createTime': '2025-07-08 15:11:49',
                'extInfo': {},
                'totalPage': 19, # 总页数
                'genType': None,
                'createUser': None,
                'updateUser': None
            }

        """
        url = f"{self.base_url}/generatePptx"
        payload = {
            "id": task_id,
            "templateId": template_id,
            "markdown": markdown
        }
        response = await client.post(url, json=payload, headers=self._get_headers())
        response.raise_for_status()
        data = response.json()

        if data.get("code") != 0:
            raise Exception(f"生成PPTX失败: {data.get('message', '未知错误')}")
        
        print(f"AIPPT返回数据: {data}")
        ppt_info = data.get("data", {}).get("pptInfo")
        if not ppt_info:
            raise Exception("API响应中缺少pptInfo。")
        return ppt_info

    async def get_template_options(self, client: httpx.AsyncClient, lang: Optional[str] = None) -> Dict[str, Any]:
        """
        获取模板的过滤选项，如类目、风格、主题颜色等。

        Args:
            client: httpx.AsyncClient 实例。
            lang: 语言代码 (e.g., "zh-CN", "en")。

        Returns:
            一个包含 'category', 'style', 'themeColor' 列表的字典。
        
        Raises:
            Exception: 当API调用失败或返回错误时。
        """
        template_api_base = self.base_url.rsplit('/', 1)[0]
        url = f"{template_api_base}/template/options"
        
        headers = self._get_headers()
        headers.pop('Content-Type', None)

        params = {}
        if lang:
            params["lang"] = lang

        response = await client.get(url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()

        if data.get("code") != 0:
            raise Exception(f"获取模板选项失败: {data.get('message', '未知错误')}")
        
        return data.get("data", {})

    async def list_templates(
        self, 
        client: httpx.AsyncClient,
        page: int = 1,
        size: int = 10,
        template_type: int = 1,
        category: Optional[str] = "教育培训",
        style: Optional[str] = None,
        theme_color: Optional[str] = None,
        lang: Optional[str] = "zh"
    ) -> Dict[str, Any]:
        """
        分页查询 PPT 模板。

        Args:
            client: httpx.AsyncClient 实例。
            page: 页码。
            size: 每页数量。
            template_type: 模板类型（必传）：1系统模板、4用户自定义模板。
            category: 类目筛选。
            style: 风格筛选。
            theme_color: 主题颜色筛选，格式为'#RRGGBB'。
            lang: 语言代码。

        Returns:
            包含模板列表和总数的字典: {'data': [...], 'total': ...}。
        
        Raises:
            Exception: 当API调用失败或返回错误时。
        """
        template_api_base = self.base_url.rsplit('/', 1)[0]
        url = f"{template_api_base}/templates"
        
        params = {}
        if lang:
            params["lang"] = lang

        filters: Dict[str, Any] = {"type": template_type}
        if category:
            filters["category"] = category
        if style:
            filters["style"] = style
        if theme_color:
            filters["themeColor"] = theme_color

        payload = {
            "page": page,
            "size": size,
            "filters": filters
        }

        response = await client.post(url, params=params, json=payload, headers=self._get_headers())
        response.raise_for_status()
        data = response.json()

        if data.get("code") != 0:
            raise Exception(f"查询PPT模板列表失败: {data.get('message', '未知错误')}")
        
        templates_list = data.get('data', [])
        if self.api_key and templates_list:
            for t in templates_list:
                if t.get('coverUrl'):
                    t['coverUrl'] = f"{t['coverUrl']}?token={self.api_key}"

        return {
            "data": templates_list,
            "total": data.get("total", 0)
        }

    async def get_random_templates(
        self, 
        client: httpx.AsyncClient,
        size: int = 10,
        template_type: int = 1,
        category: Optional[str] = None,
        style: Optional[str] = None,
        theme_color: Optional[str] = None,
        exclude_ids: Optional[List[str]] = None,
        lang: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        随机获取若干数量的 PPT 模版。

        Args:
            client: httpx.AsyncClient 实例。
            size: 数量。
            template_type: 模板类型（必传）：1系统模板、4用户自定义模板。
            category: 类目筛选。
            style: 风格筛选。
            theme_color: 主题颜色筛选，格式为'#RRGGBB'。
            exclude_ids: 排除的模板ID列表。
            lang: 语言代码。

        Returns:
            包含模板列表和总数的字典: {'data': [...], 'total': ...}。
        
        Raises:
            Exception: 当API调用失败或返回错误时。
        """
        template_api_base = self.base_url.rsplit('/', 1)[0]
        url = f"{template_api_base}/randomTemplates"
        
        params = {}
        if lang:
            params["lang"] = lang

        filters: Dict[str, Any] = {"type": template_type}
        if category:
            filters["category"] = category
        if style:
            filters["style"] = style
        if theme_color:
            filters["themeColor"] = theme_color
        if exclude_ids:
            filters["neq_id"] = exclude_ids

        payload = {
            "size": size,
            "filters": filters
        }

        response = await client.post(url, params=params, json=payload, headers=self._get_headers())
        response.raise_for_status()
        data = response.json()

        if data.get("code") != 0:
            raise Exception(f"获取随机PPT模板失败: {data.get('message', '未知错误')}")
        
        templates_list = data.get('data', [])
        if self.api_key and templates_list:
            for t in templates_list:
                if t.get('coverUrl'):
                    t['coverUrl'] = f"{t['coverUrl']}?token={self.api_key}"

        return {
            "data": templates_list,
            "total": data.get("total", 0)
        }

    def get_template_id(self, template_name: str) -> str:
        """
        它返回一个硬编码的默认模板ID。为了获取动态的、符合特定需求的模板ID，
        建议使用 `list_templates` 或 `get_random_templates` 方法来查询可用模板。

        Args:
            template_name: 模板的名称 (e.g., "modern", "classic")。

        Returns:
            一个默认的模板ID字符串。
        """

        logger.warning(
            f"Using hardcoded default template ID for '通用教育模板'. "
            f"For production, please use list_templates() or get_random_templates() to fetch dynamic template IDs."
        )
        return "1862040730604896256"




