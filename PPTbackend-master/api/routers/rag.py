import asyncio
import logging
import os
import shutil
import tempfile
from typing import Optional, List

from fastapi import (APIRouter, Depends, File, HTTPException, Query, Request,
                     UploadFile)

from api.rag_service import RAGService
from models.schemas import CreateKBRequest, RAGQueryRequest, ChunkUpdateRequest

logger = logging.getLogger(__name__)

# Dependency: use app.state.rag_service; if None, try lazy init once (e.g. RAGFlow started after backend)
def get_rag_service(request: Request) -> RAGService:
    rag_service = getattr(request.app.state, "rag_service", None)
    if rag_service is not None:
        return rag_service
    # Lazy init: RAGFlow might have been started after backend
    try:
        request.app.state.rag_service = RAGService()
        logger.info("RAGService lazy init success")
        return request.app.state.rag_service
    except Exception as e:
        logger.warning(f"RAGService lazy init failed: {e}")
        bucket = os.getenv("MINIO_BUCKET_NAME", "ai-teacher").strip()
        base_url = os.getenv("RAGFLOW_BASE_URL", "http://localhost:9380").strip()
        # RAGFlow Web 端口：业务后端可选配 RAGFLOW_WEB_PORT（与 ragflow/docker/.env 的 SVR_WEB_HTTP_PORT 一致），默认 80
        web_port = os.getenv("RAGFLOW_WEB_PORT", "80").strip()
        web_url = f"http://localhost:{web_port}" if web_port != "80" else "http://localhost"
        raise HTTPException(
            status_code=503,
            detail={
                "message": "RAG服务不可用",
                "reason": str(e),
                "check": [
                    f"1) 启动 RAGFlow：运行 ragflow/docker/启动RAGFlow.bat 或 docker compose -f ragflow/docker/docker-compose.yml up -d",
                    f"2) 在 RAGFlow Web 创建 API Key 并填入 .env 的 RAGFLOW_API_KEY。Web 地址：{web_url}（端口来自 ragflow/docker/.env 的 SVR_WEB_HTTP_PORT，默认 80；若改为 8080 则用 http://localhost:8080）",
                    f"3) 检查 .env：RAGFLOW_BASE_URL（当前 {base_url}）、MINIO_*；MinIO 桶 '{bucket}' 需存在：http://localhost:9001 或执行 python scripts/ensure_minio_bucket.py",
                ],
            },
        )

router = APIRouter(
    prefix="/api/rag",
    tags=["RAG and Knowledge Base"],
    responses={404: {"description": "Not found"}},
)

# --- Search Endpoint ---
@router.post("/search", summary="RAG知识库检索")
async def rag_search(
    request: RAGQueryRequest,
    rag_service: RAGService = Depends(get_rag_service)
):
    try:
        results = await asyncio.to_thread(
            rag_service.search,
            query=request.query,
            kb_ids=request.kb_ids,
            top_k=request.top_k,
            similarity_threshold=request.threshold, 
            vector_similarity_weight=request.vector_similarity_weight
        )
        return {"success": True, "results": results}
    
    except Exception as e:
        logger.error(f"RAG检索失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"检索失败: {str(e)}")

# --- Knowledge Base Endpoints ---
@router.post("/kbs", summary="创建知识库", status_code=201)
async def create_kb(
    request: CreateKBRequest,
    rag_service: RAGService = Depends(get_rag_service)
):
    try:
        kb = await asyncio.to_thread(
            rag_service.create_knowledge_base,
            name=request.name,
            description=request.description or ""
        )
        return {"success": True, "data": kb, "message": f"知识库 '{request.name}' 创建成功"}
    except Exception as e:
        logger.error(f"创建知识库失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail={
                "message": "创建知识库失败（RAGFlow 可能不可用或 embedding 模型配置不正确）",
                "reason": str(e),
                "check": [
                    "1) 确认 RAGFlow 已启动且 RAGFLOW_BASE_URL 可访问",
                    "2) 确认已在 RAGFlow Web 创建 API Key 并填写 RAGFLOW_API_KEY",
                    "3) 确认 RAGFLOW_EMBEDDING_MODEL 与 RAGFlow 实际可用模型一致",
                ],
            },
        )

@router.get("/kbs", summary="列出所有知识库")
async def list_kbs(
    name: Optional[str] = Query(None, description="按名称筛选知识库"),
    rag_service: RAGService = Depends(get_rag_service)
):
    try:
        kbs = await asyncio.to_thread(rag_service.list_knowledge_bases, name=name)
        return {"success": True, "data": kbs}
    except Exception as e:
        logger.error(f"列出知识库失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail={
                "message": "知识库服务不可用（RAGFlow/MinIO 可能未启动或配置不正确）",
                "reason": str(e),
                "check": [
                    "1) 确认已启动 RAGFlow（docker compose up -d）",
                    "2) 确认 RAGFlow Web 已创建 API Key，并正确填写后端 .env 的 RAGFLOW_API_KEY",
                    "3) 确认 MinIO 可访问且已创建桶（MINIO_BUCKET_NAME）",
                    "4) 检查 .env：RAGFLOW_BASE_URL、MINIO_ENDPOINT 等是否与你的实际端口一致",
                ],
            },
        )

@router.get("/kbs/{kb_id}", summary="获取知识库详情")
async def get_kb_details(
    kb_id: str,
    rag_service: RAGService = Depends(get_rag_service)
):
    try:
        # get_knowledge_base_by_id returns a DataSet object or None
        kb_dataset = await asyncio.to_thread(rag_service.get_knowledge_base_by_id, kb_id=kb_id)
        if kb_dataset:
            # Convert DataSet object to a dict for JSON response
            kb_details = {
                "id": kb_dataset.id,
                "name": kb_dataset.name,
                "description": kb_dataset.description,
                "embedding_model": kb_dataset.embedding_model
            }
            return {"success": True, "data": kb_details}
        else:
            raise HTTPException(status_code=404, detail=f"未找到ID为 '{kb_id}' 的知识库")
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"获取知识库 {kb_id} 详情失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取知识库详情失败: {str(e)}")

@router.delete("/kbs/{kb_id}", summary="删除知识库")
async def delete_kb(
    kb_id: str,
    rag_service: RAGService = Depends(get_rag_service)
):
    try:
        await asyncio.to_thread(rag_service.delete_knowledge_base, kb_id=kb_id)
        return {"success": True, "message": f"知识库 {kb_id} 删除成功"}
    except Exception as e:
        logger.error(f"删除知识库 {kb_id} 失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除知识库失败: {str(e)}")

# --- Document Endpoints ---
@router.post("/kbs/{kb_id}/documents", summary="上传文档到知识库")
async def upload_document(
    kb_id: str,
    files: List[UploadFile] = File(...),
    rag_service: RAGService = Depends(get_rag_service)
):
    temp_dir = tempfile.mkdtemp()
    results = []
    try:
        for file in files:
            if not file.filename:
                # Skip if a file without a name is somehow sent
                continue
            
            tmp_path = os.path.join(temp_dir, file.filename)
            try:
                with open(tmp_path, "wb") as f:
                    shutil.copyfileobj(file.file, f)
                
                doc_info = await asyncio.to_thread(rag_service.upload_document, kb_id, tmp_path)
                if doc_info:
                    results.append({"filename": file.filename, "success": True, "data": doc_info})
                else:
                    results.append({"filename": file.filename, "success": False, "detail": "文档上传后未能获取信息"})
            
            except Exception as e:
                logger.error(f"处理文件 {file.filename} 失败: {e}", exc_info=True)
                results.append({"filename": file.filename, "success": False, "detail": str(e)})
            finally:
                file.file.close()

        if not results:
             raise HTTPException(status_code=400, detail="没有提供有效的文件进行上传")

        return {"success": True, "results": results, "message": "所有文件处理完成"}

    finally:
        shutil.rmtree(temp_dir)


@router.get("/kbs/{kb_id}/documents", summary="列出知识库中的文档")
async def list_documents(
    kb_id: str,
    rag_service: RAGService = Depends(get_rag_service)
):
    try:
        docs = await asyncio.to_thread(rag_service.list_documents, kb_id)
        return {"success": True, "data": docs}
    except Exception as e:
        logger.error(f"列出知识库 {kb_id} 中的文档失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"列出文档失败: {e}")

@router.delete("/kbs/{kb_id}/documents/{doc_id}", summary="删除文档")
async def delete_document(
    kb_id: str, doc_id: str,
    rag_service: RAGService = Depends(get_rag_service)
):
    try:
        await asyncio.to_thread(rag_service.delete_document, kb_id, doc_id)
        return {"success": True, "message": f"文档 {doc_id} 删除成功"}
    except Exception as e:
        logger.error(f"删除文档 {doc_id} 从知识库 {kb_id} 失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除文档失败: {e}")


# --- Chunk 管理（教师纠偏）---
@router.get("/kbs/{kb_id}/documents/{doc_id}/chunks", summary="列出文档的 chunk")
async def list_chunks(
    kb_id: str,
    doc_id: str,
    keywords: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    rag_service: RAGService = Depends(get_rag_service),
):
    try:
        chunks = await asyncio.to_thread(
            rag_service.list_chunks,
            kb_id=kb_id,
            doc_id=doc_id,
            keywords=keywords,
            page=page,
            page_size=page_size,
        )
        return {"success": True, "data": chunks}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"列出 chunk 失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/kbs/{kb_id}/documents/{doc_id}/chunks/{chunk_id}", summary="更新 chunk（内容/关键词/可用状态）")
async def update_chunk(
    kb_id: str,
    doc_id: str,
    chunk_id: str,
    body: ChunkUpdateRequest,
    rag_service: RAGService = Depends(get_rag_service),
):
    try:
        updated = await asyncio.to_thread(
            rag_service.update_chunk,
            kb_id=kb_id,
            doc_id=doc_id,
            chunk_id=chunk_id,
            content=body.content,
            important_keywords=body.important_keywords,
            available=body.available,
        )
        return {"success": True, "data": updated, "message": "chunk 已更新"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"更新 chunk 失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) 