#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import datetime
import time
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from ragflow_sdk import RAGFlow, DataSet
from minio import Minio
import logging

logger = logging.getLogger(__name__)

# 将项目根目录添加到sys.path，以便导入processpdf模块
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from processpdf.PyMuPDF import process_pdf_with_marker
except ImportError:
    # 如果导入失败，尝试相对路径的方式
    if '..' not in sys.path:
        sys.path.insert(0, '..')
    from processpdf.PyMuPDF import process_pdf_with_marker


# 从.env文件加载环境变量
load_dotenv()

class RAGService:
    """
    一个完整的服务，用于管理RAGFlow知识库，包括创建、删除、文档上传和检索。
    它使用marker处理PDF，将图片存储在MinIO中，并将Markdown上传到RAGFlow。
    """
    def __init__(self):
        """
        初始化RAGService，建立与RAGFlow和MinIO的连接。
        所有配置均从环境变量加载。
        """
        # --- RAGFlow 配置 ---
        self.ragflow_api_key = os.getenv("RAGFLOW_API_KEY")
        self.ragflow_base_url = os.getenv("RAGFLOW_BASE_URL", "http://localhost:9380")

        # --- MinIO 配置 ---
        self.minio_endpoint = self._clean_env_var(os.getenv("MINIO_ENDPOINT"))
        self.minio_access_key = self._clean_env_var(os.getenv("MINIO_ACCESS_KEY"))
        self.minio_secret_key = self._clean_env_var(os.getenv("MINIO_SECRET_KEY"))
        self.minio_bucket_name = self._clean_env_var(os.getenv("MINIO_BUCKET_NAME"))
        minio_secure_str = os.getenv("MINIO_SECURE", "false")
        self.minio_secure = minio_secure_str.lower() == "true"
        self.minio_image_prefix = "images/"

        self._validate_config()

        self.rag_client = self._init_ragflow_client()
        self.minio_client = self._init_minio_client()

    def _clean_env_var(self, value: Optional[str]) -> Optional[str]:
        """清理从.env文件中读取的环境变量字符串，去除注释和多余的引号。"""
        if not value:
            return None
        value = value.strip()
        comment_index = value.find('#')
        if comment_index != -1:
            value = value[:comment_index].strip()
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        elif value.startswith("'") and value.endswith("'"):
            value = value[1:-1]
        return value

    def _validate_config(self):
        """验证所有必要的环境变量是否都已设置。"""
        required_vars = {
            "RAGFLOW_API_KEY": self.ragflow_api_key,
            "MINIO_ENDPOINT": self.minio_endpoint,
            "MINIO_ACCESS_KEY": self.minio_access_key,
            "MINIO_SECRET_KEY": self.minio_secret_key,
            "MINIO_BUCKET_NAME": self.minio_bucket_name,
        }
        missing_vars = [name for name, value in required_vars.items() if not value]
        if missing_vars:
            raise ValueError(f"错误: 缺少必要的环境变量: {', '.join(missing_vars)}")

    def _init_ragflow_client(self) -> RAGFlow:
        """初始化并返回RAGFlow客户端。"""
        try:
            logger.info(f"正在连接 RAGFlow: {self.ragflow_base_url}...")
            client = RAGFlow(api_key=self.ragflow_api_key, base_url=self.ragflow_base_url)
            client.list_datasets(page=1, page_size=1) # 简单测试连接
            logger.info("RAGFlow 客户端连接成功。")
            return client
        except Exception as e:
            logger.error(f"错误: 连接 RAGFlow 失败: {e}")
            raise

    def _init_minio_client(self) -> Minio:
        """初始化并返回MinIO客户端。"""
        # _validate_config 方法会确保这些值不为None，但我们在此处添加断言以帮助静态分析工具。
        assert isinstance(self.minio_endpoint, str), "MINIO_ENDPOINT 未设置"
        assert isinstance(self.minio_access_key, str), "MINIO_ACCESS_KEY 未设置"
        assert isinstance(self.minio_secret_key, str), "MINIO_SECRET_KEY 未设置"
        assert isinstance(self.minio_bucket_name, str), "MINIO_BUCKET_NAME 未设置"
        try:
            logger.info(f"正在连接 MinIO: {self.minio_endpoint}...")
            client = Minio(
                self.minio_endpoint,
                access_key=self.minio_access_key,
                secret_key=self.minio_secret_key,
                secure=self.minio_secure
            )
            if not client.bucket_exists(self.minio_bucket_name):
                raise ValueError(f"MinIO存储桶 '{self.minio_bucket_name}' 不存在或无法访问。")
            logger.info(f"MinIO 客户端连接成功，存储桶: '{self.minio_bucket_name}'.")
            return client
        except Exception as e:
            logger.error(f"错误: 连接 MinIO 失败: {e}")
            raise

    # --- 知识库 (DataSet) 管理 ---

    def create_knowledge_base(self, name: str, description: str = "", embedding_model: Optional[str] = None) -> Dict[str, Any]:
        """
        在RAGFlow中创建一个新的知识库 (DataSet)。

        Args:
            name: 知识库的名称。
            description: 知识库的描述。
            embedding_model: 使用的嵌入模型。若为 None 则从环境变量 RAGFLOW_EMBEDDING_MODEL 读取；
                未设置时使用与 Docker TEI 默认一致的 Qwen/Qwen3-Embedding-0.6B（需与 RAGFlow Web 中已配置的模型一致）。

        Returns:
            包含新知识库详情的字典。
        """
        # RAGFlow 要求 embedding 为 <model_name>@<provider> 格式；本地 TEI 对应 Builtin
        if embedding_model is None or not embedding_model.strip():
            embedding_model = os.getenv("RAGFLOW_EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-0.6B@Builtin").strip()
        else:
            embedding_model = embedding_model.strip()
        if not embedding_model:
            embedding_model = "Qwen/Qwen3-Embedding-0.6B@Builtin"
        if "@" not in embedding_model:
            embedding_model = f"{embedding_model}@Builtin"
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_name = f"{name}_{timestamp}"
            
            if not description:
                description = f"知识库 '{name}' 创建于 {datetime.datetime.now().isoformat()}"

            try:
                dataset = self.rag_client.create_dataset(
                    name=unique_name,
                    description=description,
                    embedding_model=embedding_model
                )
            except Exception as first_err:
                err_msg = str(first_err)
                # 若报 Unsupported model，尝试从已有数据集中取当前环境实际使用的 embedding_model 再试一次
                if "Unsupported model" in err_msg or "not authorized" in err_msg.lower():
                    try:
                        existing = self.rag_client.list_datasets(page=1, page_size=1)
                        if existing and getattr(existing[0], "embedding_model", None):
                            fallback_model = existing[0].embedding_model
                            logger.info(f"创建知识库使用备用 embedding 模型: {fallback_model}")
                            dataset = self.rag_client.create_dataset(
                                name=unique_name,
                                description=description,
                                embedding_model=fallback_model
                            )
                        else:
                            raise first_err
                    except Exception as retry_err:
                        if retry_err is not first_err:
                            logger.warning(f"使用备用 embedding 模型仍失败: {retry_err}")
                        raise first_err
                else:
                    raise first_err
            logger.info(f"成功创建知识库 '{unique_name}'，ID: {dataset.id}")
            
            # 设置推荐的解析器配置，以获得更好的PDF处理效果
            dataset.update({
                "parser_config": {
                    "chunk_token_num": 1000,
                    "layout_recognize": "DeepDOC", 
                    "raptor": {"use_raptor": False}
                }
            })
            logger.info(f"已为知识库 '{unique_name}' 设置解析器配置。")

            return {"id": dataset.id, "name": dataset.name, "description": dataset.description}
        except Exception as e:
            logger.error(f"错误: 创建知识库失败: {e}")
            raise

    def list_knowledge_bases(
        self,
        page: int = 1,
        page_size: int = 30,
        orderby: str = "create_time",
        desc: bool = True,
        id: Optional[str] = None,
        name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        列出所有可用的知识库，支持分页和过滤。

        Args:
            page (int): 指定数据集将显示的页码。默认为 1。
            page_size (int): 每页数据集的数量。默认为 30。
            orderby (str): 用于对数据集进行排序的字段。可用选项: "create_time" (默认), "update_time"。
            desc (bool): 指示检索到的数据集是否应按降序排序。默认值为 True。
            id (str, optional): 要获取的数据集的 ID。默认为 None。
            name (str, optional): 获取数据集的名称。默认为 None。

        Returns:
            一个包含知识库详情的字典列表。
        """
        try:
            datasets = self.rag_client.list_datasets(
                page=page,
                page_size=page_size,
                orderby=orderby,
                desc=desc,
                id=id,
                name=name
            )
            # 为了与create_knowledge_base的返回保持一致，此处也返回description
            return [{"id": ds.id, "name": ds.name, "description": ds.description} for ds in datasets]
        except Exception as e:
            logger.error(f"错误: 列出知识库失败: {e}")
            raise

    def delete_knowledge_base(self, kb_id: str) -> bool:
        """
        通过ID删除一个知识库。

        Args:
            kb_id: 要删除的知识库的ID。

        Returns:
            如果删除成功返回 True。
        """
        try:
            self.rag_client.delete_datasets(ids=[kb_id])
            logger.info(f"成功删除知识库，ID: {kb_id}")
            return True
        except Exception as e:
            logger.error(f"错误: 删除知识库 {kb_id} 失败: {e}")
            raise

    def get_knowledge_base_by_id(self, kb_id: str) -> Optional[DataSet]:
        """通过ID检索一个DataSet对象。"""
        try:
            datasets = self.rag_client.list_datasets(id=kb_id)
            if datasets:
                return datasets[0]
            logger.warning(f"警告: 未找到ID为 '{kb_id}' 的知识库。")
            return None
        except Exception as e:
            logger.error(f"错误: 检索知识库 {kb_id} 失败: {e}")
            return None

    # --- 文档管理 ---

    def _upload_document_direct_to_ragflow(self, kb_id: str, file_path: str) -> Optional[Dict[str, Any]]:
        """
        将 PDF 原样上传到 RAGFlow，由 RAGFlow 服务端解析（无需本地 Marker/MinIO）。
        适用：不想在本地下载/运行 Marker 模型时。
        """
        dataset = self.get_knowledge_base_by_id(kb_id)
        if not dataset:
            raise ValueError(f"错误: 未找到ID为 '{kb_id}' 的知识库。")
        display_name = os.path.basename(file_path)
        with open(file_path, "rb") as f:
            blob = f.read()
        logger.info(f"正在将 PDF 直接上传到 RAGFlow 知识库 '{dataset.name}'（由 RAGFlow 解析）: {display_name}")
        dataset.upload_documents([{"display_name": display_name, "blob": blob}])
        found_doc = None
        for i in range(5):
            docs = dataset.list_documents(keywords=display_name, page_size=1, orderby="create_time", desc=True)
            if docs and (docs[0].name == display_name or getattr(docs[0], "display_name", None) == display_name):
                found_doc = docs[0]
                break
            time.sleep(2)
        if not found_doc:
            raise Exception(f"上传后在知识库中未找到文档: {display_name}")
        doc_ids = [found_doc.id]
        dataset.async_parse_documents(doc_ids)
        start_time = time.time()
        max_wait_time = 900
        while (time.time() - start_time) < max_wait_time:
            all_done = True
            for doc_id in doc_ids:
                docs_check = dataset.list_documents(id=doc_id)
                if docs_check and len(docs_check) > 0:
                    if docs_check[0].run != "DONE":
                        all_done = False
                        break
                else:
                    all_done = False
                    break
            if all_done:
                logger.info("RAGFlow 文档解析完成。")
                return {"id": found_doc.id, "name": getattr(found_doc, "name", None) or found_doc.display_name or display_name}
            logger.info("文档解析中，等待 10 秒...")
            time.sleep(10)
        logger.warning("解析等待超时，部分文档可能仍在处理。")
        return {"id": found_doc.id, "name": getattr(found_doc, "name", None) or display_name}

    def upload_document(self, kb_id: str, file_path: str) -> Optional[Dict[str, Any]]:
        """
        处理一个PDF文档并上传到指定的知识库。
        若环境变量 PDF_USE_DIRECT_RAGFLOW=true：将 PDF 直接上传 RAGFlow，由 RAGFlow 解析（无需本地模型）。
        否则：PDF -> Marker 处理 -> Markdown+图片 -> 图片上传 MinIO -> Markdown 上传 RAGFlow。
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"错误: 文件未找到: {file_path}")

        lower = file_path.lower()
        is_pdf = lower.endswith(".pdf")
        is_md = lower.endswith(".md") or lower.endswith(".markdown") or lower.endswith(".txt")
        if not (is_pdf or is_md):
            raise ValueError("错误: 目前仅支持上传 PDF 或 Markdown(.md/.markdown/.txt) 文件。")

        dataset = self.get_knowledge_base_by_id(kb_id)
        if not dataset:
            raise ValueError(f"错误: 未找到ID为 '{kb_id}' 的知识库。")

        # Markdown / text：直接上传到 RAGFlow，由 RAGFlow 解析并生成 chunks
        if is_md:
            display_name = os.path.basename(file_path)
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                md_text = f.read()

            def _preprocess_markdown_for_ragflow(text: str) -> str:
                # 基线策略：将相对/本地图片引用降级为文本，避免 RAGFlow 抓取失败导致解析 FAIL/CONSTANT
                out_lines: list[str] = []
                for line in (text or "").splitlines():
                    s = line.strip()
                    if s.startswith("![](") and s.endswith(")"):
                        out_lines.append(f"[IMAGE] {s[4:-1]}")
                        continue
                    out_lines.append(line)
                return "\n".join(out_lines)

            def _split_markdown_baseline(text: str, *, max_chars: int = 6000, overlap: int = 200) -> list[str]:
                # 按标题与段落做“软切分”，保证每片大小可控，方便解析与召回
                lines = (text or "").splitlines()
                chunks: list[str] = []
                buf: list[str] = []

                def flush():
                    if not buf:
                        return
                    chunk = "\n".join(buf).strip()
                    if chunk:
                        chunks.append(chunk)
                    buf.clear()

                for line in lines:
                    is_heading = line.lstrip().startswith("#")
                    if is_heading and buf:
                        flush()
                    buf.append(line)
                    if sum(len(x) + 1 for x in buf) >= max_chars:
                        flush()

                flush()

                if overlap > 0 and len(chunks) > 1:
                    overlapped: list[str] = []
                    for i, c in enumerate(chunks):
                        if i == 0:
                            overlapped.append(c)
                            continue
                        prev_tail = chunks[i - 1][-overlap:]
                        overlapped.append((prev_tail + "\n\n" + c).strip())
                    chunks = overlapped
                return chunks

            md_text = _preprocess_markdown_for_ragflow(md_text)
            parts = _split_markdown_baseline(md_text)

            # 若文档很短则不切片，保持原名；否则用统一前缀批量上传
            base = os.path.splitext(display_name)[0]
            prefix = f"{base}__baseline__"
            docs_payload: list[dict] = []
            if len(parts) <= 1:
                docs_payload = [{"display_name": display_name, "blob": parts[0].encode("utf-8")}]
            else:
                for idx, part in enumerate(parts, 1):
                    part_name = f"{prefix}{idx:04d}.md"
                    docs_payload.append({"display_name": part_name, "blob": part.encode("utf-8")})

            logger.info(
                "正在将 Markdown baseline 切片上传到 RAGFlow 知识库 '%s': %s (parts=%d)",
                dataset.name,
                display_name,
                len(docs_payload),
            )
            dataset.upload_documents(docs_payload)

            found_doc = None
            found_docs: list[Any] = []
            keywords = prefix if len(parts) > 1 else display_name
            for _ in range(8):
                docs = dataset.list_documents(keywords=keywords, page=1, page_size=50, orderby="create_time", desc=True)
                if docs:
                    # 过滤出刚上传的文档名
                    want_names = {d["display_name"] for d in docs_payload}
                    matched = [d for d in docs if (d.name in want_names or getattr(d, "display_name", None) in want_names)]
                    if matched:
                        found_docs = matched
                        break
                time.sleep(2)

            if not found_docs:
                raise Exception(f"上传后在知识库中未找到文档(关键词={keywords}): {display_name}")

            doc_ids = [d.id for d in found_docs if getattr(d, "id", None)]
            if doc_ids:
                dataset.async_parse_documents(doc_ids)
            logger.info("Markdown baseline 上传成功，已触发 RAGFlow 异步解析（docs=%d）。", len(doc_ids))

            return {
                "mode": "markdown_baseline_chunks",
                "original_name": display_name,
                "uploaded": [{"id": d.id, "name": getattr(d, "name", None)} for d in found_docs],
            }

        use_direct = os.getenv("PDF_USE_DIRECT_RAGFLOW", "").strip().lower() in ("1", "true", "yes")
        if use_direct:
            return self._upload_document_direct_to_ragflow(kb_id, file_path)

        logger.info(f"正在为知识库 '{dataset.name}' 使用 Marker 处理 PDF '{os.path.basename(file_path)}'...")
        try:
            minio_endpoint_for_url = f"{'https://' if self.minio_secure else 'http://'}{self.minio_endpoint}"
            markdown_text, uploaded_images = process_pdf_with_marker(
                pdf_path=file_path,
                minio_client=self.minio_client,
                bucket_name=self.minio_bucket_name,
                image_prefix=self.minio_image_prefix,
                minio_endpoint_for_url=minio_endpoint_for_url
            )
            logger.info(f"PDF处理完成。提取了Markdown，并上传了 {len(uploaded_images)} 张图片到 MinIO。")
            
            # 步骤 2: 将处理后的Markdown上传到RAGFlow
            base_pdf_name = os.path.splitext(os.path.basename(file_path))[0]
            markdown_filename = f"{base_pdf_name}_marker.md"
            markdown_bytes = markdown_text.encode('utf-8')

            logger.info(f"正在以上传文件名 '{markdown_filename}' 将Markdown内容上传到RAGFlow...")
            dataset.upload_documents([{
                "display_name": markdown_filename,
                "blob": markdown_bytes
            }])
            logger.info("文档上传请求已发送。现在查找该文档以获取ID...")

            # 轮询查找文档
            found_doc = None
            max_retries = 5
            retry_delay = 2  # seconds
            for i in range(max_retries):
                docs = dataset.list_documents(keywords=markdown_filename, page_size=1, orderby="create_time", desc=True)
                if docs and docs[0].name == markdown_filename:
                    found_doc = docs[0]
                    break
                logger.info(f"未找到文档 '{markdown_filename}'，{retry_delay}秒后重试... ({i+1}/{max_retries})")
                time.sleep(retry_delay)

            if not found_doc:
                raise Exception(f"上传文档后，在知识库中找不到名为 '{markdown_filename}' 的文档。")

            doc = found_doc
            logger.info(f"文档找到，ID: {doc.id}。正在启动解析流程...")
            
            # 步骤 3: 异步开始解析
            doc_ids = [doc.id]
            logger.info(f"开始解析文档，ID: {doc_ids}")
            dataset.async_parse_documents(doc_ids)

            # 等待文档解析完成
            all_done = False
            max_wait_time = 900  # 最长等待15分钟
            start_time = time.time()
            
            while not all_done and (time.time() - start_time) < max_wait_time:
                all_done = True
                for doc_id in doc_ids:
                    docs_check = dataset.list_documents(id=doc_id)
                    if docs_check and len(docs_check) > 0:
                        doc_status = docs_check[0].run
                        logger.info(f"文档 {doc_id} 状态: {doc_status}")
                        if doc_status not in ["DONE"]:
                            all_done = False
                            break
                    else:
                        logger.warning(f"无法获取文档 {doc_id} 的状态")
                        all_done = False
                        break
                
                if not all_done:
                    logger.info("文档仍在解析中，等待10秒...")
                    time.sleep(10)
            
            if all_done:
                logger.info("文档解析完成！")
                total_chunks = 0
                for doc_id in doc_ids:
                    docs_check = dataset.list_documents(id=doc_id)
                    if docs_check and len(docs_check) > 0:
                        chunk_count = docs_check[0].chunk_count
                        total_chunks += chunk_count
                        logger.info(f"文档 {doc_id} 解析出 {chunk_count} 个分块")
                if total_chunks == 0:
                    logger.warning("警告：文档解析完成但没有生成分块，可能解析失败")
                    return None
            else:
                logger.warning(f"等待超时（{max_wait_time}秒），部分文档可能仍在解析中")
                success_count = 0
                for doc_id in doc_ids:
                    docs_check = dataset.list_documents(id=doc_id)
                    if docs_check and len(docs_check) > 0 and docs_check[0].run == "DONE":
                        success_count += 1
                if success_count == 0:
                    logger.error("没有文档解析成功，无法创建助手")
                    return None
                else:
                    logger.info(f"有 {success_count}/{len(doc_ids)} 个文档解析成功")
            
            return {"id": doc.id, "name": doc.name}
            
        except Exception as e:
            logger.error(f"错误: 文档上传和处理过程中发生错误: {e}")
            raise


    def list_documents(
        self,
        kb_id: str,
        doc_id: Optional[str] = None,
        keywords: Optional[str] = None,
        page: int = 1,
        page_size: int = 30,
        orderby: str = "create_time",
        desc: bool = True
    ) -> List[Dict[str, Any]]:
        """
        列出指定知识库中的所有文档，支持分页和过滤。

        Args:
            kb_id (str): 知识库的 ID。
            doc_id (str, optional): 要检索的文档的 ID。默认为 None。
            keywords (str, optional): 用于匹配文档标题的关键字。默认为 None。
            page (int): 指定文档将显示的页面。默认为 1。
            page_size (int): 每页显示的最大文档数量。默认为 30。
            orderby (str): 文档排序的字段 ("create_time" 或 "update_time")。默认为 "create_time"。
            desc (bool): 是否按降序排序。默认为 True。

        Returns:
            一个包含文档详情的字典列表。
        """
        dataset = self.get_knowledge_base_by_id(kb_id)
        if not dataset:
            raise ValueError(f"错误: 未找到ID为 '{kb_id}' 的知识库。")
        
        try:
            documents = dataset.list_documents(
                id=doc_id,
                keywords=keywords,
                page=page,
                page_size=page_size,
                orderby=orderby,
                desc=desc
            )
            
            results = []
            for doc in documents:
                results.append({
                    "id": doc.id,
                    "name": doc.name,
                    "status": doc.run,
                    "chunk_count": doc.chunk_count,
                    "size": doc.size,
                    "token_count": doc.token_count,
                    "progress": doc.progress,
                    "progress_msg": doc.progress_msg,
                    "process_duration": doc.process_duation
                })
            return results
        except Exception as e:
            logger.error(f"错误: 列出知识库 {kb_id} 中的文档失败: {e}")
            raise

    def delete_document(self, kb_id: str, doc_id: str) -> bool:
        """
        从知识库中删除一个文档。

        Args:
            kb_id: 包含文档的知识库ID。
            doc_id: 要删除的文档ID。

        Returns:
            如果删除成功返回 True。
        """
        dataset = self.get_knowledge_base_by_id(kb_id)
        if not dataset:
            raise ValueError(f"错误: 未找到ID为 '{kb_id}' 的知识库。")
        
        try:
            dataset.delete_documents(ids=[doc_id])
            logger.info(f"成功从知识库 {kb_id} 中删除文档 {doc_id}。")
            return True
        except Exception as e:
            logger.error(f"错误: 删除文档 {doc_id} 失败: {e}")
            raise

    # --- 检索 ---

    def _extract_keywords(self, query: str) -> List[str]:
        """从查询中提取关键词（轻量规则版）。"""
        q = (query or "").strip()
        if not q:
            return []
        # 统一分隔符
        for ch in [",", "，", ".", "。", "？", "?", "！", "!", "；", ";", ":", "：", "(", ")", "（", "）", "\n", "\t"]:
            q = q.replace(ch, " ")
        tokens = [t.strip() for t in q.split(" ") if t.strip()]
        # 简单去重，保留有信息量的 token
        seen = set()
        out: List[str] = []
        for t in tokens:
            if len(t) < 2:
                continue
            if t not in seen:
                seen.add(t)
                out.append(t)
        return out[:8]

    def search(self, query: str, kb_ids: List[str], top_k: int = 5, similarity_threshold: float = 0.2, vector_similarity_weight: Optional[float] = 0.3) -> List[Dict[str, Any]]:
        """
        在指定的知识库中检索相关的文本片段 (chunks)。

        Args:
            query: 检索的查询词。
            kb_ids: 用于检索的知识库ID列表。
            top_k: 返回结果的数量。
            similarity_threshold: 结果的最低相似度得分。
            vector_similarity_weight: 向量相似度的权重。

        Returns:
            List[Dict[str, Any]]: 包含检索结果的字典列表，每个字典包含以下内容：
                - content (str): 检索到的文本片段内容。
                - source_document (str): 片段来源的文档名称。
                - source_document_id (str): 片段来源的文档ID。
                - metadata (dict): 片段的元数据信息。
        """
        if not kb_ids:
            raise ValueError("错误: 必须提供至少一个知识库ID进行检索。")
        
        try:
            # 双通道检索融合：
            # - 句子通道（原 query）权重 0.7
            # - 关键词通道（提取关键词）权重 0.3
            sentence_weight = 0.7
            keyword_weight = 0.3
            vector_w = 0.3 if vector_similarity_weight is None else float(vector_similarity_weight)
            keywords = self._extract_keywords(query)
            keyword_query = " ".join(keywords)
            logger.info(
                "RAG 检索: query_len=%d kb_ids=%d top_k=%d threshold=%.3f sentence_w=%.2f keyword_w=%.2f keyword_count=%d",
                len(query or ""),
                len(kb_ids or []),
                top_k,
                similarity_threshold,
                sentence_weight,
                keyword_weight,
                len(keywords),
            )

            sentence_chunks = self.rag_client.retrieve(
                question=query,
                dataset_ids=kb_ids,
                page_size=top_k,
                similarity_threshold=similarity_threshold,
                vector_similarity_weight=vector_w,
                top_k=1024,
            )
            keyword_chunks = []
            if keyword_query:
                keyword_chunks = self.rag_client.retrieve(
                    question=keyword_query,
                    dataset_ids=kb_ids,
                    page_size=top_k,
                    similarity_threshold=max(0.0, similarity_threshold - 0.1),
                    vector_similarity_weight=vector_w,
                    top_k=1024,
                )

            # 按 rank 融合打分后去重
            merged_map: Dict[str, Dict[str, Any]] = {}

            def add_chunk(chunk, channel: str, weight: float, rank: int):
                cid = str(getattr(chunk, "id", "") or "")
                if not cid:
                    return
                base_score = weight / float(rank + 1)
                if cid not in merged_map:
                    merged_map[cid] = {
                        "id": chunk.id,
                        "content": chunk.content,
                        "dataset_id": chunk.dataset_id,
                        "document_id": chunk.document_id,
                        "retrieval_mode": "hybrid_sentence_keyword",
                        "_score": 0.0,
                        "_channels": set(),
                    }
                merged_map[cid]["_score"] += base_score
                merged_map[cid]["_channels"].add(channel)

            for idx, c in enumerate(sentence_chunks):
                add_chunk(c, "sentence", sentence_weight, idx)
            for idx, c in enumerate(keyword_chunks):
                add_chunk(c, "keyword", keyword_weight, idx)

            merged = sorted(merged_map.values(), key=lambda x: x["_score"], reverse=True)
            results = []
            for item in merged[:top_k]:
                item["retrieval_channels"] = sorted(list(item.pop("_channels", set())))
                item.pop("_score", None)
                results.append(item)
            logger.info(
                "RAG 检索返回: sentence_hits=%d keyword_hits=%d merged_hits=%d",
                len(sentence_chunks),
                len(keyword_chunks),
                len(results),
            )

            # 命中为 0 时做一次自适应兜底：
            # 1) 先放宽阈值到 0（仍保留原 vector_weight）
            # 2) 若仍为 0，再降级为 BM25（vector_weight=0）
            if len(results) == 0:
                if similarity_threshold > 0:
                    logger.info("RAG 命中为 0，放宽阈值重试: threshold=0.0")
                    chunks2 = self.rag_client.retrieve(
                        question=query,
                        dataset_ids=kb_ids,
                        page_size=top_k,
                        similarity_threshold=0.0,
                        vector_similarity_weight=vector_similarity_weight,
                        top_k=1024,
                    )
                    results2 = [
                        {
                            "id": c.id,
                            "content": c.content,
                            "dataset_id": c.dataset_id,
                            "document_id": c.document_id,
                            "retrieval_mode": "threshold_relaxed",
                        }
                        for c in chunks2
                    ]
                    logger.info("RAG(阈值放宽) 检索返回: hits=%d", len(results2))
                    if results2:
                        return results2

                if vector_similarity_weight != 0.0:
                    logger.info("RAG 命中仍为 0，降级为 BM25 重试: vector_w=0.0")
                    chunks3 = self.rag_client.retrieve(
                        question=query,
                        dataset_ids=kb_ids,
                        page_size=top_k,
                        similarity_threshold=0.0,
                        vector_similarity_weight=0.0,
                        top_k=1024,
                    )
                    results3 = [
                        {
                            "id": c.id,
                            "content": c.content,
                            "dataset_id": c.dataset_id,
                            "document_id": c.document_id,
                            "retrieval_mode": "bm25_on_zero_hits",
                        }
                        for c in chunks3
                    ]
                    logger.info("RAG(BM25 zero-hit) 检索返回: hits=%d", len(results3))
                    if results3:
                        return results3
            
            return results
        except Exception as e:
            err_text = str(e)
            # 常见：RAGFlow embedding 模型未授权，导致向量检索失败
            # 兜底：降级为纯关键词检索（vector_similarity_weight=0），保证知识库仍可用
            if "not authorized" in err_text.lower() or "unsupported model" in err_text.lower():
                logger.warning("向量检索不可用（%s），降级为关键词检索(BM25)。", err_text)
                try:
                    chunks = self.rag_client.retrieve(
                        question=query,
                        dataset_ids=kb_ids,
                        page_size=top_k,
                        similarity_threshold=0.0,
                        vector_similarity_weight=0.0,
                        top_k=1024,
                    )
                    logger.info("RAG(BM25) 检索返回: hits=%d", len(chunks))
                    return [
                        {
                            "id": c.id,
                            "content": c.content,
                            "dataset_id": c.dataset_id,
                            "document_id": c.document_id,
                            "retrieval_mode": "bm25_fallback",
                        }
                        for c in chunks
                    ]
                except Exception as e2:
                    logger.error("关键词检索兜底也失败: %s", e2)
                    raise
            logger.error(f"错误: 检索过程中发生错误: {e}")
            raise

    # --- Chunk 管理（教师纠偏、关键词等）---

    def list_chunks(
        self,
        kb_id: str,
        doc_id: str,
        keywords: Optional[str] = None,
        page: int = 1,
        page_size: int = 30,
        chunk_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        列出指定文档下的 chunk，支持分页与关键词筛选。
        用于教师查看、纠偏知识点切分。
        """
        dataset = self.get_knowledge_base_by_id(kb_id)
        if not dataset:
            raise ValueError(f"错误: 未找到ID为 '{kb_id}' 的知识库。")
        docs = dataset.list_documents(id=doc_id)
        if not docs:
            raise ValueError(f"错误: 未找到ID为 '{doc_id}' 的文档。")
        doc = docs[0]
        try:
            chunks = doc.list_chunks(keywords=keywords, page=page, page_size=page_size, id=chunk_id)
            return [
                {
                    "id": c.id,
                    "content": getattr(c, "content", ""),
                    "important_keywords": getattr(c, "important_keywords", []) or [],
                    "available": getattr(c, "available", True),
                }
                for c in chunks
            ]
        except Exception as e:
            logger.error(f"错误: 列出文档 {doc_id} 的 chunk 失败: {e}")
            raise

    def update_chunk(
        self,
        kb_id: str,
        doc_id: str,
        chunk_id: str,
        content: Optional[str] = None,
        important_keywords: Optional[List[str]] = None,
        available: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        更新指定 chunk 的内容、关键词或可用状态。
        用于教师纠偏、补关键词、禁用错误 chunk。
        """
        dataset = self.get_knowledge_base_by_id(kb_id)
        if not dataset:
            raise ValueError(f"错误: 未找到ID为 '{kb_id}' 的知识库。")
        docs = dataset.list_documents(id=doc_id)
        if not docs:
            raise ValueError(f"错误: 未找到ID为 '{doc_id}' 的文档。")
        doc = docs[0]
        chunks = doc.list_chunks(id=chunk_id, page=1, page_size=1)
        if not chunks:
            raise ValueError(f"错误: 未找到ID为 '{chunk_id}' 的 chunk。")
        chunk = chunks[0]
        update_msg = {}
        if content is not None:
            update_msg["content"] = content
        if important_keywords is not None:
            update_msg["important_keywords"] = important_keywords
        if available is not None:
            update_msg["available"] = available
        if not update_msg:
            return {"id": chunk.id, "content": getattr(chunk, "content", "")}
        try:
            chunk.update(update_msg)
            return {
                "id": chunk.id,
                "content": content if content is not None else getattr(chunk, "content", ""),
                "important_keywords": important_keywords if important_keywords is not None else getattr(chunk, "important_keywords", []),
                "available": available if available is not None else getattr(chunk, "available", True),
            }
        except Exception as e:
            logger.error(f"错误: 更新 chunk {chunk_id} 失败: {e}")
            raise
