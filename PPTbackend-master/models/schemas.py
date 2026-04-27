from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from enum import Enum

class PPTLength(str, Enum):
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"

class VideoStyle(str, Enum):
    MATHEMATICAL = "mathematical"
    PRESENTATION = "presentation"
    ANIMATION = "animation"
    DIAGRAM = "diagram"

class TTSLanguage(str, Enum):
    CHINESE = "zh"
    ENGLISH = "en"

class PPTRequest(BaseModel):
    topic: str
    kb_id: List[str] = ["368452a45bbf11f08bcd0242ac110007"]
    prompt: Optional[str] = None
    template: str = "modern" 
    length: PPTLength = PPTLength.MEDIUM
    scene: Optional[str] = None
    audience: Optional[str] = None
    lang: str = "zh"

class RAGQueryRequest(BaseModel):
    query: str
    kb_ids: List[str]
    top_k: int = 5
    threshold: float = 0.2
    vector_similarity_weight: float = 0.3

class VideoGenerationRequest(BaseModel):
    topic: str
    content: str
    ppt_content: Optional[Dict] = None  # PPT内容结构
    script_content: Optional[str] = None  # 讲稿内容
    style: VideoStyle = VideoStyle.PRESENTATION
    duration: Optional[int] = None  # 自动计算，可选覆盖
    resolution: str = "1920x1080"
    method: str = "auto"  # auto, manim, ai


class LectureSlide(BaseModel):
    """自动讲解播放器：单页配置"""
    page: int
    title: Optional[str] = None
    text: Optional[str] = None
    audio_filename: str
    audio_url: Optional[str] = None


class LectureScriptRequest(BaseModel):
    """
    自动讲解脚本生成请求：
    基于 PPT 内容（文本为主，可选讲稿）为每一页生成讲解语音。
    """
    topic: str
    ppt_content: Dict[str, Any]
    script_content: Optional[str] = None
    language: TTSLanguage = TTSLanguage.CHINESE
    voice: Optional[str] = None
    speed: float = 1.0

class TTSRequest(BaseModel):
    text: str
    language: TTSLanguage = TTSLanguage.CHINESE
    voice: Optional[str] = None
    speed: float = 1.0

class CreateKBRequest(BaseModel):
    name: str
    description: Optional[str] = None


class ChunkUpdateRequest(BaseModel):
    """更新 chunk 内容/关键词/可用状态，用于教师纠偏"""
    content: Optional[str] = None
    important_keywords: Optional[List[str]] = None
    available: Optional[bool] = None

class RAGResult(BaseModel):
    content: str
    id: str
    dataset_id: str
    document_id: str

class APIResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Any] = None
    error: Optional[str] = None


class CreateChatAssistantRequest(BaseModel):
    name: str
    dataset_ids: List[str]

class DeleteChatAssistantsRequest(BaseModel):
    assistant_ids: List[str]

class CreateSessionRequest(BaseModel):
    session_name: Optional[str] = "New session"

class DeleteSessionsRequest(BaseModel):
    session_ids: List[str]

class AskQuestionRequest(BaseModel):
    question: str
    stream: bool = True


class SimpleChatMessage(BaseModel):
    role: str  # "user" | "assistant" | "system"
    content: str


class SimpleCompletionRequest(BaseModel):
    """AI 聊天助手简单对话：传入历史消息列表，返回助手回复。用于前端持久化聊天记录场景。"""
    messages: List[SimpleChatMessage]

class ListTemplatesRequest(BaseModel):
    page: int = 1
    size: int = 10
    template_type: int = 1
    category: Optional[str] = "教育培训"
    style: Optional[str] = None
    theme_color: Optional[str] = None
    lang: Optional[str] = "zh"

class RandomTemplatesRequest(BaseModel):
    size: int = 10
    template_type: int = 1
    category: Optional[str] = None
    style: Optional[str] = None
    theme_color: Optional[str] = None
    exclude_ids: Optional[List[str]] = None
    lang: Optional[str] = None

class GenerateContentRequest(BaseModel):
    length: PPTLength = PPTLength.MEDIUM
    lang: str = "zh"
    scene: Optional[str] = None
    audience: Optional[str] = None
    prompt: Optional[str] = None
    stream: bool = False

class GeneratePptxRequest(BaseModel):
    markdown: str
    template_id: str

class TTSBatchRequest(BaseModel):
    texts: List[str]
    language: TTSLanguage = TTSLanguage.CHINESE

class TTSSSMLRequest(BaseModel):
    ssml: str
    language: TTSLanguage = TTSLanguage.CHINESE


# --- 课程-知识库映射 (RAGFlow 边界) ---
class KbMappingCreate(BaseModel):
    course_id: Optional[str] = None
    subject: Optional[str] = None
    grade: Optional[str] = None
    teacher_id: Optional[str] = None
    ragflow_dataset_id: str
    dataset_type: str = "教材库"
    name: Optional[str] = None


class KbMappingUpdate(BaseModel):
    course_id: Optional[str] = None
    subject: Optional[str] = None
    grade: Optional[str] = None
    teacher_id: Optional[str] = None
    ragflow_dataset_id: Optional[str] = None
    dataset_type: Optional[str] = None
    name: Optional[str] = None


# --- 场景 → chat_id 配置 ---
class ChatSceneCreate(BaseModel):
    scene_key: str
    scene_name: str
    ragflow_chat_id: str
    description: Optional[str] = None


class ChatSceneUpdate(BaseModel):
    scene_name: Optional[str] = None
    ragflow_chat_id: Optional[str] = None
    description: Optional[str] = None


# ---------- 学情分析 ----------
class LogQuestionRequest(BaseModel):
    """前端可选：主动上报一条提问（若后端在 kb_qa/chat 中已自动记录则可不调）"""
    question_type: str  # kb_qa | chat | ai_teacher | quick_qa
    question_content: str
    course: Optional[str] = None
    kb_ids: Optional[List[str]] = None


class GenerateReportRequest(BaseModel):
    """生成学情分析报告请求"""
    major: str
    course: Optional[str] = None
    time_range_start: Optional[str] = None  # ISO datetime
    time_range_end: Optional[str] = None
