import asyncio
import logging
import json
from typing import Optional, List, cast, Dict, Any, AsyncGenerator
import os
import base64
import gzip
from datetime import datetime

import httpx
from fastapi import (
    APIRouter, Depends, HTTPException, Query, Request, UploadFile, File, Form
)
from fastapi.responses import StreamingResponse

from api.local_ppt_generator import LocalPPTGenerator
from api.rag_service import RAGService
from models.schemas import (
    ListTemplatesRequest, PPTRequest, RandomTemplatesRequest,
    GenerateContentRequest, GeneratePptxRequest
)

logger = logging.getLogger(__name__)

# 依赖项，用于从应用状态中获取服务实例
def get_ppt_generator(request: Request) -> LocalPPTGenerator:
    return request.app.state.ppt_generator

def get_http_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.http_client


def get_rag_service_optional(request: Request):
    """可选 RAG 服务：未配置时返回 None，用于 PPT 增强模式知识库检索"""
    return getattr(request.app.state, "rag_service", None)

router = APIRouter(
    prefix="/api/ppt",
    tags=["PPT Generation"],
    responses={404: {"description": "Not found"}},
)

@router.post("/generate", summary="通过RAG生成PPT")
async def generate_ppt(
    request_data: PPTRequest,
    ppt_generator: LocalPPTGenerator = Depends(get_ppt_generator),
    rag_service=Depends(get_rag_service_optional),
):
    """
    **通过RAG生成PPT**
    
    结合知识库内容，生成包含相关例题的PPT。返回完整pptinfo信息
    return:
    {
        "success": True, 
        "data": {
                'id': '1942481641276575744', # 任务ID
                'name': '质点运动学', # 任务名称
                'subject': '质点运动学', # 任务主题
                'coverUrl': 'https://chatmee.cn/api/public/oss/meta-doc/ppt/133735/xxxxx', # 封面图片URL
                'fileUrl': 'https://chatmee.cn/api/public/oss/meta-doc/ppt/133735/xxxxx', # 文件URL
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
            },
        "message": "PPT生成成功",
    }
    """
    try:
        # 若传了知识库且 RAG 可用，先检索再生成（增强模式会结合检索结果）
        rag_context = None
        if request_data.kb_id and rag_service:
            try:
                search_results = await asyncio.to_thread(
                    rag_service.search,
                    query=request_data.topic,
                    kb_ids=request_data.kb_id,
                    top_k=10,
                    similarity_threshold=0.2,
                )
                rag_context = "\n\n".join(r.get("content", "") for r in search_results if r.get("content"))
            except Exception as e:
                logger.warning(f"PPT 生成前 RAG 检索跳过: {e}")
        result = await ppt_generator.generate_ppt(
            topic=request_data.topic,
            template=request_data.template,
            length=request_data.length.value,
            scene=request_data.scene or "教学课件",
            audience=request_data.audience or "学生",
            lang=request_data.lang,
            kb_id=request_data.kb_id,
            prompt=request_data.prompt,
            mode="enhanced",
            rag_context=rag_context,
        )
        return result
        
    except Exception as e:
        logger.error(f"PPT生成失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"PPT生成失败: {str(e)}")

@router.post("/generate/enhanced", summary="生成增强版PPT（支持数学公式和图片）")
async def generate_enhanced_ppt(
    request_data: PPTRequest,
    ppt_generator: LocalPPTGenerator = Depends(get_ppt_generator),
    rag_service=Depends(get_rag_service_optional),
):
    """
    **生成增强版PPT**
    
    支持数学公式渲染和图片插入；若传 kb_id 则结合知识库检索结果生成。
    """
    try:
        rag_context = None
        if request_data.kb_id and rag_service:
            try:
                search_results = await asyncio.to_thread(
                    rag_service.search,
                    query=request_data.topic,
                    kb_ids=request_data.kb_id,
                    top_k=10,
                    similarity_threshold=0.2,
                )
                rag_context = "\n\n".join(r.get("content", "") for r in search_results if r.get("content"))
            except Exception as e:
                logger.warning(f"增强 PPT 前 RAG 检索跳过: {e}")
        result = await ppt_generator.generate_ppt(
            topic=request_data.topic,
            template=request_data.template,
            length=request_data.length.value,
            scene=request_data.scene or "教学课件",
            audience=request_data.audience or "学生",
            lang=request_data.lang,
            kb_id=request_data.kb_id,
            prompt=request_data.prompt,
            mode="enhanced",
            rag_context=rag_context,
        )
        return result
        
    except Exception as e:
        logger.error(f"增强版PPT生成失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"增强版PPT生成失败: {str(e)}")

@router.post("/task", summary="创建PPT生成任务")
async def create_ppt_task(
    task_type: int = Form(..., description="任务类型 (1-7)"),
    content: Optional[str] = Form(None, description="根据类型不同的内容"),
    files: Optional[List[UploadFile]] = File(None, description="上传的文件"),
    ppt_generator: LocalPPTGenerator = Depends(get_ppt_generator),
    http_client: httpx.AsyncClient = Depends(get_http_client),
):
    """
    **创建PPT生成任务**

    根据不同的类型创建任务，支持多种输入方式。
    - **task_type**: 任务类型
        - 1: 智能生成
        - 2: 上传文件生成
        - 3: 思维导图生成
        - 4: Word转PPT
        - 5: 网页链接生成
        - 6: 粘贴文本生成
        - 7: Markdown大纲生成
    - **content**: 文本内容，根据 `task_type` 的不同而变化。
    - **files**: 上传的文件列表。
    """
    temp_file_paths = []
    try:
        if files:
            # 将上传的文件保存到临时位置
            temp_dir = "temp_uploads"
            os.makedirs(temp_dir, exist_ok=True)
            for file in files:
                if file.filename:
                    temp_path = os.path.join(temp_dir, file.filename)
                    with open(temp_path, "wb") as f:
                        f.write(await file.read())
                    temp_file_paths.append(temp_path)

        task_id = await ppt_generator.create_task(
            client=http_client,
            task_type=task_type,
            content=content,
            files=temp_file_paths
        )
        return {"success": True, "task_id": task_id, "message": "任务创建成功"}

    except Exception as e:
        logger.error(f"创建PPT任务失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建PPT任务失败: {str(e)}")
    finally:
        # 清理临时文件
        for path in temp_file_paths:
            os.remove(path)


@router.post("/task/{task_id}/content", summary="生成大纲和内容")
async def generate_ppt_content(
    task_id: str,
    request_data: GenerateContentRequest,
    ppt_generator: LocalPPTGenerator = Depends(get_ppt_generator),
    http_client: httpx.AsyncClient = Depends(get_http_client),
):
    """
    **为指定任务生成PPT大纲和内容**

    此接口支持流式（stream=True）和非流式返回。
    """
    try:
        if request_data.stream:
            # 流式返回
            async def stream_generator():
                streamer_result = await ppt_generator.generate_content(
                    client=http_client,
                    task_id=task_id,
                    stream=True,
                    **request_data.dict(exclude={"stream"})
                )
                # 显式转换类型以帮助linter
                streamer = cast(AsyncGenerator[Dict[str, Any], None], streamer_result)
                async for chunk in streamer:
                    yield f"data: {json.dumps(chunk)}\n\n"
            return StreamingResponse(stream_generator(), media_type="text/event-stream")
        else:
            # 非流式返回
            content_result = await ppt_generator.generate_content(
                client=http_client,
                task_id=task_id,
                stream=False,
                **request_data.dict(exclude={"stream"})
            )
            content = cast(Dict[str, Any], content_result)
            return {"success": True, "data": content}
    except Exception as e:
        logger.error(f"为任务 {task_id} 生成内容失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"为任务 {task_id} 生成内容失败: {str(e)}")


@router.post("/task/{task_id}/pptx", summary="生成PPTX文件")
async def generate_pptx_file(
    task_id: str,
    request_data: GeneratePptxRequest,
    ppt_generator: LocalPPTGenerator = Depends(get_ppt_generator),
    http_client: httpx.AsyncClient = Depends(get_http_client),
):
    """
    **使用Markdown内容和模板生成最终的PPTX文件**

    生成成功后，返回pptinfo信息。
    return:
    {
        "success": True, 
        "data":  {
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
        },
        "message": "PPTX文件生成成功",
    }
    """
    try:
        ppt_info = await ppt_generator.generate_pptx(
            client=http_client,
            task_id=task_id,
            markdown=request_data.markdown,
            template_id=request_data.template_id
        )
        print(f"完整ppt_info: {ppt_info}")

        if not ppt_info.get("fileUrl"):
            raise Exception("API响应中未包含 'fileUrl'。")

        logger.info(f"PPT for task {task_id} 生成成功。")
        return {"success": True, "data": ppt_info, "message": "PPTX文件生成成功"}

    except Exception as e:
        logger.error(f"为任务 {task_id} 生成PPTX失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"为任务 {task_id} 生成PPTX失败: {str(e)}")


@router.post("/templates", summary="查询PPT模板")
async def list_ppt_templates(
    request_data: ListTemplatesRequest,
    ppt_generator: LocalPPTGenerator = Depends(get_ppt_generator),
    http_client: httpx.AsyncClient = Depends(get_http_client),
):
    try:
        templates_data = await ppt_generator.list_templates(
            client=http_client,
            **request_data.dict()
        )
        return {"success": True, "data": templates_data}
    except Exception as e:
        logger.error(f"查询PPT模板失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询PPT模板失败: {str(e)}")


@router.get("/options", summary="获取PPT生成选项")
async def get_ppt_options(
    lang: Optional[str] = Query(None, description="语言代码 (e.g., 'zh', 'en')"),
    ppt_generator: LocalPPTGenerator = Depends(get_ppt_generator),
    http_client: httpx.AsyncClient = Depends(get_http_client),
):
    try:
        options = await ppt_generator.get_options(client=http_client, lang=lang)
        return {"success": True, "data": options}
    except Exception as e:
        logger.error(f"获取PPT选项失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取PPT选项失败: {e}")


@router.get("/template-options", summary="获取PPT模板过滤选项")
async def get_ppt_template_options(
    lang: Optional[str] = Query(None, description="语言代码 (e.g., 'zh-CN', 'en')"),
    ppt_generator: LocalPPTGenerator = Depends(get_ppt_generator),
    http_client: httpx.AsyncClient = Depends(get_http_client),
):
    try:
        options = await ppt_generator.get_template_options(client=http_client, lang=lang)
        return {"success": True, "data": options}
    except Exception as e:
        logger.error(f"获取模板选项失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取模板选项失败: {e}")


@router.post("/random-templates", summary="随机获取PPT模板")
async def get_random_ppt_templates(
    request_data: RandomTemplatesRequest,
    ppt_generator: LocalPPTGenerator = Depends(get_ppt_generator),
    http_client: httpx.AsyncClient = Depends(get_http_client),
):
    try:
        templates_data = await ppt_generator.get_random_templates(
            client=http_client,
            **request_data.dict()
        )
        return {"success": True, "data": templates_data}
    except Exception as e:
        logger.error(f"获取随机模板失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取随机模板失败: {str(e)}") 