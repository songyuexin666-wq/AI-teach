import logging
import os
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse

from api.text_to_speech import TextToSpeechService
from api.response import APIResponse
from models.schemas import (
    TTSBatchRequest,
    TTSRequest,
    TTSSSMLRequest,
    LectureScriptRequest,
)

logger = logging.getLogger(__name__)

# Dependencies
def get_tts_service(request: Request) -> TextToSpeechService:
    return request.app.state.tts_service

router = APIRouter(
    prefix="/api/media",
    tags=["Media Generation"],
    responses={404: {"description": "Not found"}},
)

@router.post(
    "/lecture_script",
    summary="生成自动讲解播放器脚本（每页语音 + 元信息）",
)
async def generate_lecture_script(
    request: LectureScriptRequest,
    tts_service: TextToSpeechService = Depends(get_tts_service),
):
    """
    根据 PPT 内容为每一页生成讲解语音，并返回前端可直接使用的 slides 配置。

    约定 ppt_content 结构：
    {
      "slides": [
        { "title": "...", "content": "..." },
        ...
      ]
    }
    """
    ppt = request.ppt_content or {}
    slides = ppt.get("slides") or []
    if not isinstance(slides, list) or not slides:
        raise HTTPException(status_code=400, detail="ppt_content.slides 不能为空")

    generated = []
    for idx, slide in enumerate(slides, start=1):
        title = (slide or {}).get("title") or f"第 {idx} 页"
        text = (slide or {}).get("content") or ""

        # 若提供了整体讲稿，可选：将对应片段拼接在一起；这里基线版本仅使用该页内容。
        if not text and request.script_content:
            text = request.script_content

        # 文本为空时不生成语音，前端可仅显示 PPT
        audio_filename = None
        audio_url = None
        if text and text.strip():
            try:
                audio_filename = await tts_service.generate_speech(
                    text=text,
                    language=request.language.value,
                    voice=request.voice,
                    speed=request.speed,
                )
                audio_url = f"/api/media/files/audio/{audio_filename}/preview"
            except Exception as e:
                logger.warning("为第 %s 页生成语音失败：%s", idx, e)

        generated.append(
            {
                "page": idx,
                "title": title,
                "text": text,
                "audio_filename": audio_filename,
                "audio_url": audio_url,
            }
        )

    return APIResponse.success(
        data={"slides": generated, "topic": request.topic},
        message="自动讲解脚本生成完成",
    )

@router.post("/tts", summary="文本转语音")
async def text_to_speech(
    request: TTSRequest,
    tts_service: TextToSpeechService = Depends(get_tts_service),
):
    try:
        audio_filename = await tts_service.generate_speech(
            text=request.text,
            language=request.language.value,
            voice=request.voice,
            speed=request.speed
        )
        return {"success": True, "filename": audio_filename, "message": "语音生成成功"}
    except Exception as e:
        logger.error(f"语音生成失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"语音生成失败: {str(e)}")

@router.post("/tts/batch", summary="批量文本转语音")
async def batch_text_to_speech(
    request: TTSBatchRequest,
    tts_service: TextToSpeechService = Depends(get_tts_service),
):
    try:
        filenames = await tts_service.generate_batch_speech(
            texts=request.texts,
            language=request.language.value
        )
        return {"success": True, "filenames": filenames, "message": "批量语音生成任务完成"}
    except Exception as e:
        logger.error(f"批量语音生成失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"批量语音生成失败: {str(e)}")

@router.post("/tts/ssml", summary="使用SSML进行文本转语音")
async def ssml_text_to_speech(
    request: TTSSSMLRequest,
    tts_service: TextToSpeechService = Depends(get_tts_service),
):
    try:
        filename = await tts_service.text_to_speech_with_ssml(
            ssml_text=request.ssml,
            language=request.language.value,
        )
        return {"success": True, "filename": filename, "message": "SSML语音生成成功"}
    except Exception as e:
        logger.error(f"SSML语音生成失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"SSML语音生成失败: {str(e)}")

@router.get("/tts/languages", summary="获取支持的TTS语言")
async def get_supported_languages(
    tts_service: TextToSpeechService = Depends(get_tts_service),
):
    try:
        languages = tts_service.get_supported_languages()
        return {"success": True, "data": languages}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取支持语言失败: {e}")

@router.get("/audio/{filename}/info", summary="获取音频文件信息")
async def get_audio_info(
    filename: str,
    tts_service: TextToSpeechService = Depends(get_tts_service),
):
    try:
        info = await tts_service.get_audio_info(filename)
        return {"success": True, "data": info}
    except Exception as e:
        logger.error(f"获取音频信息失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取音频信息失败: {str(e)}")

@router.get("/files/{file_type}", summary="列出指定类型的文件")
async def list_files(file_type: str):
    """列出指定类型的所有已生成文件 (ppt, videos, audio)"""
    if file_type not in ["ppt", "videos", "audio"]:
        raise HTTPException(status_code=400, detail="无效的文件类型。有效类型: ppt, videos, audio")
    
    directory = os.path.join("outputs", file_type)
    if not os.path.exists(directory):
        return {"success": True, "data": []}
    
    files_list = []
    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        if os.path.isfile(file_path):
            stat = os.stat(file_path)
            files_list.append({
                "filename": filename,
                "size_bytes": stat.st_size,
                "created_time": datetime.fromtimestamp(stat.st_ctime).isoformat()
            })
            
    sorted_files = sorted(files_list, key=lambda x: x['created_time'], reverse=True)
    return {"success": True, "data": sorted_files}


@router.get("/files/{file_type}/{filename}/download", summary="下载生成的文件")
async def download_file(file_type: str, filename: str):
    """下载一个已生成的文件 (ppt, videos, audio)"""
    if file_type not in ["ppt", "videos", "audio"]:
        raise HTTPException(status_code=400, detail="无效的文件类型。有效类型: ppt, videos, audio")
        
    file_path = os.path.join("outputs", file_type, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")
        
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type='application/octet-stream'
    )

@router.get("/files/{file_type}/{filename}/preview", summary="预览生成的文件")
async def preview_file(file_type: str, filename: str):
    """预览一个已生成的文件 (ppt, videos, audio)"""
    if file_type not in ["ppt", "videos", "audio"]:
        raise HTTPException(status_code=400, detail="无效的文件类型。有效类型: ppt, videos, audio")
        
    file_path = os.path.join("outputs", file_type, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    
    # 根据文件类型设置不同的媒体类型
    media_types = {
        "ppt": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "videos": "video/mp4",
        "audio": "audio/mpeg",
    }

    media_type = media_types.get(file_type, 'application/octet-stream')
    if file_type == "audio":
        ext = os.path.splitext(filename)[1].lower()
        if ext == ".wav":
            media_type = "audio/wav"
        elif ext == ".mp3":
            media_type = "audio/mpeg"
    
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type=media_type
    ) 