# 智能PPT与多媒体生成系统 - 开发者文档

本系统是一个基于Python FastAPI构建的、功能强大的智能PPT与多媒体内容生成平台。它深度整合了先进的RAG（检索增强生成）技术、AI对话服务、PPTX文档生成、文本转语音（TTS）以及教学视频制作等功能，旨在为开发者提供一个稳定、可扩展、功能全面的内容自动化解决方案。

本文档为开发者提供详细的系统架构、环境配置、启动说明和API参考。

## 目录
- [智能PPT与多媒体生成系统 - 开发者文档](#智能ppt与多媒体生成系统---开发者文档)
  - [目录](#目录)
  - [系统架构](#系统架构)
    - [架构图](#架构图)
    - [核心组件](#核心组件)
    - [服务与端口依赖](#服务与端口依赖)
  - [环境配置与启动](#环境配置与启动)
    - [1. 环境要求](#1-环境要求)
    - [2. 依赖服务](#2-依赖服务)
    - [3. 安装项目依赖](#3-安装项目依赖)
    - [4. 环境变量配置 (`.env`)](#4-环境变量配置-env)
    - [5. 启动服务](#5-启动服务)
  - [API接口参考](#api接口参考)
    - [知识库 (RAG) API](#知识库-rag-api)
    - [聊天服务 API](#聊天服务-api)
    - [PPT生成 API](#ppt生成-api)
    - [媒体与文件 API](#媒体与文件-api)

## 系统架构


### 核心组件

- **`main.py`**: FastAPI应用的入口，负责初始化服务、中间件和路由。
- **`api/routers/`**: API路由层，按功能 (`rag`, `chat`, `ppt`, `media`) 划分模块，定义所有HTTP接口。
- **`api/` (服务层)**:
  - `rag_service.py`: 封装与RAGFlow和MinIO的交互，负责知识库管理、文档上传和检索。
  - `chat_service.py`: 封装与RAGFlow的交互，提供聊天助手和多会话管理。
  - `local_ppt_generator.py`: 本地PPT生成器，支持多种生成模式。
  - `enhanced_ppt_generator.py`: 增强版PPT生成器，支持数学公式和图片。
  - `video_generator.py` / `text_to_speech.py`: 对接LLM或TTS服务，生成视频和音频。
  - `ai_video_generator.py`: AI视频生成器，支持第三方AI服务。
- **`models/schemas.py`**: 定义所有API请求和响应的Pydantic数据模型。
- **`outputs/`**: 存放所有生成文件（PPT、视频、音频）的默认目录。

### 服务与端口依赖

为了使系统完整运行，需要启动以下服务并确保网络端口可用：

| 服务 | 默认端口 | `..env` 配置项 | 描述 |
| :--- | :--- | :--- | :--- |
| **本应用 (FastAPI)** | **`7878`** | (硬编码于 `main.py`) | 提供所有API服务的主应用。 |
| **RAGFlow** | **`8080`** | `RAGFLOW_BASE_URL` | 核心依赖，用于RAG和聊天功能。 |
| **MinIO** | **`9000`** | `MINIO_ENDPOINT` | 核心依赖，用于存储RAGFlow所需的文档和图片。 |

## 环境配置与启动

### 1. 环境要求
- Python 3.10+
- Docker (推荐，用于快速启动RAGFlow和MinIO)

### 2. 依赖服务
在启动主应用前，必须先运行RAGFlow和MinIO。

> **注意**: 请确保您的RAGFlow和MinIO服务已正确配置并正在运行。它们的配置（如API Key, Access Key等）必须与下方`.env`文件中的配置完全一致。

### 3. 安装项目依赖
```bash
# (推荐) 创建并激活Python虚拟环境
python -m venv venv
# Windows: venv\Scripts\activate
# Linux/macOS: source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 4. 环境变量配置 (`.env`)

在项目**根目录**下创建 `.env` 文件。这是系统所有外部服务和关键配置的入口。请根据您的实际环境修改。

**`.env` 文件模板:**
```env
# RAGFlow API 配置 (用于知识库和RAG检索)
# 必须与您运行的RAGFlow实例配置一致
RAGFLOW_API_KEY="your-ragflow-api-key"
# RAGFlow服务地址，代码中默认端口为8080
RAGFLOW_BASE_URL="http://127.0.0.1:8080" 

# MinIO 配置 (RAGFlow依赖的文件存储)
# 必须与您运行的MinIO实例配置一致
MINIO_ENDPOINT="127.0.0.1:9000"
MINIO_ACCESS_KEY="rag_flow"
MINIO_SECRET_KEY="infini_rag_flow"
MINIO_BUCKET_NAME="ragflow-public-assets"
MINIO_SECURE=false

# 大语言模型 API 配置
# 用于内容生成、视频脚本等。支持任何兼容OpenAI接口的服务
OPENAI_API_KEY="your-llm-api-key"
OPENAI_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
AI_MODEL="qwen-long" # 使用的具体模型

# PPT在线生成服务 (Docmee) API 配置
# 如果不使用 /api/ppt/task/** 系列接口，可以不填
DOCMEE_API_KEY="your-docmee-api-key"
DOCMEE_API_BASE_URL="https://open.docmee.cn/api/ppt/v2"

# 应用服务器配置 (仅供参考，实际端口在main.py中指定)
HOST=0.0.0.0
PORT=7878 

# 文件存储配置
OUTPUT_DIR=outputs
```

### 5. 启动服务

- **通过脚本 (推荐)**:
  - Windows: 双击运行 `start.bat`。
  - Linux/macOS: `chmod +x start.sh && ./start.sh`

- **手动启动**:
  ```bash
  uvicorn main:app --host 0.0.0.0 --port 7878 --reload
  ```

服务启动后，API交互文档将托管在 [http://localhost:7878/docs](http://localhost:7878/docs)。

## API接口参考

以下是系统核心API的详细说明。所有接口的基路径为 `/`。

---
### 知识库 (RAG) API
**路由前缀**: `/api/rag`

本模块负责与RAGFlow服务进行交互，提供知识库的完整生命周期管理，包括创建、文档上传、解析、检索和删除。

---
#### 1. 创建知识库
- **POST** `/kbs`
- **摘要**: 创建一个新的知识库 (DataSet)。
- **描述**: 此接口用于在RAGFlow中创建一个新的知识库（在RAGFlow中称为"DataSet"）。每个知识库都是一个隔离的文档集合，拥有独立的设置。创建时，系统会自动为知识库名称附加时间戳以确保唯一性，并配置推荐的PDF解析设置。
- **请求体**: `application/json`
  ```json
  {
    "name": "大学物理习题集",
    "description": "包含各章节的重点习题和解析"
  }
  ```
- **请求体详解**:
  - `name` (str, **必需**): 知识库的名称。
  - `description` (str, 可选): 对知识库的详细描述。
- **成功响应 (201 Created)**:
  ```json
  {
    "success": true,
    "data": {
      "id": "ds-8a7e2bcf3d1a4f0c8e4d9f2a7b1c0e3a",
      "name": "大学物理习题集_20231101_102030",
      "description": "包含各章节的重点习题和解析"
    },
    "message": "知识库 '大学物理习题集' 创建成功"
  }
  ```
- **失败响应 (500)**: 如果RAGFlow服务连接失败或发生内部错误。

---
#### 2. 列出所有知识库
- **GET** `/kbs`
- **摘要**: 列出所有可用的知识库。
- **描述**: 检索系统中所有已创建的知识库，支持按名称进行模糊筛选。
- **查询参数**:
  - `name` (str, 可选): 根据知识库名称进行筛选。
- **成功响应 (200 OK)**:
  ```json
  {
    "success": true,
    "data": [
      {
        "id": "ds-8a7e2bcf3d1a4f0c8e4d9f2a7b1c0e3a",
        "name": "大学物理习题集_20231101_102030",
        "description": "包含各章节的重点习题和解析"
      },
      {
        "id": "ds-f1b9c8d7a6e54321b0a9e8d7c6b5a4f3",
        "name": "项目文档_20231102_154500",
        "description": "存放所有项目相关的技术和需求文档"
      }
    ]
  }
  ```
- **失败响应 (500)**: 如果RAGFlow服务连接失败。

---
#### 3. 获取知识库详情
- **GET** `/kbs/{kb_id}`
- **摘要**: 获取指定知识库的详细信息。
- **路径参数**:
  - `kb_id` (str, **必需**): 知识库的ID。
- **成功响应 (200 OK)**:
  ```json
  {
    "success": true,
    "data": {
      "id": "ds-8a7e2bcf3d1a4f0c8e4d9f2a7b1c0e3a",
      "name": "大学物理习题集_20231101_102030",
      "description": "包含各章节的重点习题和解析",
      "embedding_model": "BAAI/bge-large-zh-v1.5@BAAI"
    }
  }
  ```
- **失败响应 (404 Not Found)**: 如果指定的 `kb_id` 不存在。

---
#### 4. 删除知识库
- **DELETE** `/kbs/{kb_id}`
- **摘要**: 删除一个知识库。
- **描述**: 根据ID永久删除一个知识库及其包含的所有文档。此操作不可逆。
- **路径参数**:
  - `kb_id` (str, **必需**): 要删除的知识库的ID。
- **成功响应 (200 OK)**:
  ```json
  {
    "success": true,
    "message": "知识库 ds-8a7e2bcf3d1a4f0c8e4d9f2a7b1c0e3a 删除成功"
  }
  ```
- **失败响应 (500)**: 如果删除过程中发生错误。

---
#### 5. 上传文档到知识库
- **POST** `/kbs/{kb_id}/documents`
- **摘要**: 向指定的知识库上传一个或多个文档。
- **描述**:
  这是一个核心功能接口，用于上传文件并将其内容加入知识库。**当前版本主要优化了对PDF文件的处理。**
  **后端处理流程**:
    1. **PDF处理**: 使用`marker`工具对上传的PDF文件进行深度处理，将其转换为Markdown格式的文本，并提取其中的所有图片。
    2. **图片存储**: 提取出的图片被上传到在`.env`中配置的MinIO对象存储桶中。
    3. **内容入库**: 生成的Markdown文本（其中图片链接已替换为MinIO的URL）被上传到RAGFlow中，作为知识库的一个新文档。
    4. **异步解析**: API会触发RAGFlow对新上传的文档进行**异步解析**（包括文本切块、向量化等）。此接口会**同步等待**解析任务完成，因此对于大型文档，调用耗时可能会较长。
- **路径参数**:
  - `kb_id` (str, **必需**): 文档将要上传到的知识库ID。
- **请求**: `multipart/form-data`
  - `files` (List[file], **必需**): 一个或多个要上传的文件。
- **成功响应 (200 OK)**:
  ```json
  {
    "success": true,
    "results": [
      {
        "filename": "大学物理第一章.pdf",
        "success": true,
        "data": {
          "id": "doc-a1b2c3d4e5f6",
          "name": "大学物理第一章_marker.md"
        }
      }
    ],
    "message": "所有文件处理完成"
  }
  ```
- **失败响应**:
  - **400 Bad Request**: 如果没有提供任何文件。
  - **500 Internal Server Error**: 如果在PDF处理、MinIO上传或RAGFlow交互的任何环节出错。

---
#### 6. 列出知识库中的文档
- **GET** `/kbs/{kb_id}/documents`
- **摘要**: 列出指定知识库中的所有文档。
- **描述**: 获取一个知识库中所有文档的列表及其状态。这对于跟踪文档解析进度非常有用。
- **路径参数**:
  - `kb_id` (str, **必需**): 知识库的ID。
- **成功响应 (200 OK)**:
  ```json
  {
    "success": true,
    "data": [
      {
        "id": "doc-a1b2c3d4e5f6",
        "name": "大学物理第一章_marker.md",
        "status": "DONE",
        "chunk_count": 152,
        "size": 78643,
        "token_count": 35000,
        "progress": 1.0,
        "progress_msg": "Completed",
        "process_duration": 120.5
      }
    ]
  }
  ```
  - **关键字段说明**:
    - `status`: 文档处理状态。`DONE`表示成功，`RUNNING`表示正在处理，`FAIL`表示失败。
    - `chunk_count`: 文档被切分成的文本块数量，是RAG检索的基础。
    - `process_duration`: 文档处理耗时（秒）。

---
#### 7. 删除文档
- **DELETE** `/kbs/{kb_id}/documents/{doc_id}`
- **摘要**: 从知识库中删除一个文档。
- **路径参数**:
  - `kb_id` (str, **必需**): 知识库的ID。
  - `doc_id` (str, **必需**): 要删除的文档ID（可从"列出文档"接口获取）。
- **成功响应 (200 OK)**:
  ```json
  {
    "success": true,
    "message": "文档 doc-a1b2c3d4e5f6 删除成功"
  }
  ```

---
#### 8. RAG知识库检索
- **POST** `/search`
- **摘要**: 在一个或多个知识库中执行RAG检索。
- **描述**: 针对一个或多个知识库，执行语义相似度检索，找出与查询最相关的文本片段(chunks)。
- **请求体**: `application/json`
  ```json
  {
    "query": "什么是牛顿第一定律？",
    "kb_ids": ["ds-8a7e2bcf3d1a4f0c8e4d9f2a7b1c0e3a"],
    "top_k": 3,
    "threshold": 0.2,
    "vector_similarity_weight": 0.3
  }
  ```
- **请求体详解**:
  - `query` (str, **必需**): 检索的查询语句。
  - `kb_ids` (List[str], **必需**): 一个或多个要检索的知识库ID列表。
  - `top_k` (int, 可选): 返回最相关结果的数量。默认: `5`。
  - `threshold` (float, 可选): 相似度阈值，低于此分数的将被过滤。默认: `0.2`。
  - `vector_similarity_weight` (float, 可选): 向量相似度的权重。默认: `0.3`。
- **成功响应 (200 OK)**:
  ```json
  {
    "success": true,
    "results": [
      {
        "id": "chunk-xyz123",
        "content": "牛顿第一定律，也称为惯性定律，指出...",
        "dataset_id": "ds-8a7e2bcf3d1a4f0c8e4d9f2a7b1c0e3a",
        "document_id": "doc-a1b2c3d4e5f6"
      }
    ]
  }
  ```
- **失败响应 (500)**: 如果检索过程中发生错误。

---
### 聊天服务 API
**路由前缀**: `/api/chat`

本模块构建于RAGFlow的聊天功能之上，提供了一套完整的、用于创建和管理多租户、多会话聊天机器人的接口。您可以创建绑定特定知识库的"助手"，并为每个助手开启多个独立的对话"会话"。

---
#### 1. 创建聊天助手
- **POST** `/assistants`
- **摘要**: 创建一个聊天机器人助手。
- **描述**: 助手是聊天功能的核心实体，它与一个或多个知识库（Datasets）绑定。所有与该助手的对话都将基于其绑定的知识库内容进行回答。
- **请求体**: `application/json`
  ```json
  {
    "name": "物理学助教",
    "dataset_ids": ["ds-8a7e2bcf3d1a4f0c8e4d9f2a7b1c0e3a"]
  }
  ```
- **请求体详解**:
  - `name` (str, **必需**): 助手的名称，建议具有唯一性以便于识别。
  - `dataset_ids` (List[str], **必需**): 一个或多个知识库ID的列表。助手将从这些知识库中检索信息来回答问题。
- **成功响应 (200 OK)**:
  ```json
  {
    "success": true,
    "data": {
      "id": "asst-f9b8e7d6c5b4a321",
      "name": "物理学助教"
    },
    "message": "聊天助手创建成功"
  }
  ```
- **失败响应 (500 Internal Server Error)**: 如果RAGFlow服务连接失败或发生内部错误。

---
#### 2. 列出所有聊天助手
- **GET** `/assistants`
- **摘要**: 获取所有已创建的聊天助手列表。
- **描述**: 检索系统中的所有助手，支持通过名称进行模糊查询。
- **查询参数**:
  - `name` (str, 可选): 根据助手名称进行筛选。如果提供，将返回名称包含此字符串的所有助手。
- **成功响应 (200 OK)**:
  ```json
  {
    "success": true,
    "data": [
      {
        "id": "asst-f9b8e7d6c5b4a321",
        "name": "物理学助教",
        "description": ""
      },
      {
        "id": "asst-a1b2c3d4e5f6g7h8",
        "name": "项目文档问答机器人",
        "description": ""
      }
    ]
  }
  ```
- **失败响应 (500 Internal Server Error)**: 如果RAGFlow服务连接失败。

---
#### 3. 删除聊天助手
- **DELETE** `/assistants`
- **摘要**: 批量删除一个或多个聊天助手。
- **描述**: 根据提供的助手ID列表，永久删除这些助手。这是一个批量操作，请谨慎使用。
- **请求体**: `application/json`
  ```json
  {
    "assistant_ids": ["asst-f9b8e7d6c5b4a321", "asst-a1b2c3d4e5f6g7h8"]
  }
  ```
- **请求体详解**:
  - `assistant_ids` (List[str], **必需**): 要删除的聊天助手的ID列表。
- **成功响应 (200 OK)**:
  ```json
  {
    "success": true,
    "message": "聊天助手删除成功"
  }
  ```
- **失败响应 (500 Internal Server Error)**: 如果删除过程中发生错误。

---
#### 4. 创建会话
- **POST** `/assistants/{assistant_id}/sessions`
- **摘要**: 为指定的助手创建一个新的聊天会话。
- **描述**: 会话（Session）是具体的一次对话。每个助手可以拥有多个独立的会话，它们之间的聊天历史互不影响。这对于实现多用户同时与一个助手对话非常关键。
- **路径参数**:
  - `assistant_id` (str, **必需**): 助手ID。
- **请求体**: `application/json`
  ```json
  {
    "session_name": "关于牛顿定律的讨论"
  }
  ```
- **请求体详解**:
  - `session_name` (str, 可选): 为会话指定一个名称，便于后续识别。如果未提供，默认为 `"New session"`。
- **成功响应 (200 OK)**:
  ```json
  {
    "success": true,
    "data": {
      "id": "sess-abc123def456",
      "name": "关于牛顿定律的讨论"
    },
    "message": "会话创建成功"
  }
  ```
- **失败响应 (500 Internal Server Error)**: 如果助手ID不存在或服务出错。

---
#### 5. 列出所有会话
- **GET** `/assistants/{assistant_id}/sessions`
- **摘要**: 分页列出指定助手的所有会话。
- **描述**: 获取一个助手下所有会话的列表，支持分页。
- **路径参数**:
  - `assistant_id` (str, **必需**): 助手ID。
- **查询参数**:
  - `page` (int, 可选): 页码，从1开始。默认: `1`。
  - `page_size` (int, 可选): 每页的项目数。默认: `30`，最大: `100`。
- **成功响应 (200 OK)**:
  ```json
  {
    "success": true,
    "data": [
      {
        "id": "sess-abc123def456",
        "name": "关于牛顿定律的讨论"
      },
      {
        "id": "sess-xyz789uvw012",
        "name": "光的衍射问题"
      }
    ]
  }
  ```
- **失败响应 (500 Internal Server Error)**: 如果助手ID不存在或服务出错。

---
#### 6. 删除会话
- **DELETE** `/assistants/{assistant_id}/sessions`
- **摘要**: 批量删除指定助手的会话。
- **描述**: 根据提供的会话ID列表，永久删除这些会话。这是一个批量操作。
- **路径参数**:
  - `assistant_id` (str, **必需**): 拥有这些会话的助手ID。
- **请求体**: `application/json`
  ```json
  {
    "session_ids": ["sess-abc123def456"]
  }
  ```
- **请求体详解**:
  - `session_ids` (List[str], **必需**): 要删除的会话ID列表。
- **成功响应 (200 OK)**:
  ```json
  {
    "success": true,
    "message": "会话删除成功"
  }
  ```
- **失败响应 (500 Internal Server Error)**: 如果助手ID或会话ID不正确，或服务出错。

---
#### 7. 向会话提问
- **POST** `/assistants/{assistant_id}/sessions/{session_id}/ask`
- **摘要**: 在指定会话中向助手提问，获取回答。
- **描述**: 这是实现聊天功能的核心接口。它支持流式（Server-Sent Events）和非流式两种响应模式，以适应不同客户端的需求。
- **路径参数**:
  - `assistant_id` (str, **必需**): 助手ID。
  - `session_id` (str, **必需**): 会话ID。
- **查询参数**:
  - `assistant_name` (str, 可选): 助手的名称，此参数主要用于内部记录或特定逻辑，通常不需要用户提供。
  - `session_name` (str, 可选): 会话的名称，此参数主要用于内部记录或特定逻辑，通常不需要用户提供。
- **请求体**: `application/json`
  ```json
  {
    "question": "请解释一下加速度的概念。",
    "stream": true
  }
  ```
- **请求体详解**:
  - `question` (str, **必需**): 用户提出的问题。
  - `stream` (bool, 可选): 是否使用流式响应。默认为 `true`。
    - `true`: 服务器将以 `text/event-stream` 的形式持续推送生成的文本块。
    - `false`: 服务器将在完全生成好答案后，一次性返回完整的JSON响应。
- **成功响应**:
  - **当 `stream: true` 时 (200 OK, Content-Type: `text/event-stream`)**:
    响应体将是一系列Server-Sent Events。每个事件代表一部分生成的答案。客户端需要监听这些事件并拼接内容。
    ```
    data: {"content":"加","role":"assistant","id":null}

    data: {"content":"速度","role":"assistant","id":null}

    data: {"content":"是","role":"assistant","id":null}

    data: {"content":"描述","role":"assistant","id":null}
    
    ...

    ```
    如果发生错误，流中可能会推送一个包含`error`字段的事件：
    ```
    data: {"error": "流式响应生成错误: ..."}
    ```
  - **当 `stream: false` 时 (200 OK, Content-Type: `application/json`)**:
    返回一个包含完整答案的JSON对象。
    ```json
    {
      "success": true,
      "data": {
        "content": "加速度是描述物体速度变化快慢的物理量，通常用 a 表示。它是速度对时间的变化率。",
        "role": "assistant"
      }
    }
    ```
- **失败响应 (500 Internal Server Error)**: 如果提问过程中发生严重错误。

---
### PPT生成 API
**路由前缀**: `/api/ppt`

本模块提供了从内容生成到最终PPTX文件导出的一整套解决方案。您可以选择使用高级接口一键完成，也可以通过标准分步流程精细控制每一步。

---
#### 1. 一键生成RAG PPT (高级接口)
- **POST** `/generate`
- **描述**: 这是一个高级封装接口，专门用于结合现有知识库（RAG）内容，全自动生成一份完整的PPTX文件。它会在后端自动执行创建任务、生成大纲、检索知识库内容、合成PPT等一系列操作。
- **请求体**: `PPTRequest`
  ```json
  {
    "topic": "质点运动学",
    "kb_id": "ds-8a7e2bcf3d1a4f0c8e4d9f2a7b1c0e3a",
    "prompt": "内容要详实，公式要清晰，并为每个知识点都加上例题。",
    "template": "modern",
    "length": "medium",
    "scene": "教学课件",
    "audience": "学生",
    "lang": "zh"
  }
  ```
- **请求体详解**:
  - `topic` (str, **必需**): PPT的主题。该主题将用于在RAGFlow中查找同名知识库。
  - `kb_id` (str, **必需**): 用于RAG检索的知识库ID。
  - `prompt` (str, 可选): 对AI的额外要求，用于指导内容生成。
  - `template` (str, 可选): 目前为无用字段，后端会使用一个默认模板。默认值: `"modern"`。
  - `length` (str, 可选): PPT篇幅。可选值: `"short"` (10-15页), `"medium"` (20-30页), `"long"` (25-35页)。默认值: `"medium"`。
  - `scene` (str, 可选): 演示场景，如 "通用场景","教学课件", "工作总结","工作计划","项目汇报","解决方案","研究报告","会议材料","产品介绍","公司介绍","商业计划书","科普宣传","公众演讲"。
  - `audience` (str, 可选): 目标受众，如 "大众", "学生","老师", "上级领导", "下属","面试官" ,"同事"。
  - `lang` (str, 可选): 生成语言。默认值: `"zh"`。
- **成功响应 (200)**: 返回完整的PPT信息。
  ```json
  {
    "success": true,
    "data": {
        "id": "1942481641276575744",
        "name": "质点运动学",
        "subject": "质点运动学",
        "coverUrl": "https://chatmee.cn/api/public/oss/meta-doc/ppt/133735/xxxxx",
        "fileUrl": "https://chatmee.cn/api/public/oss/meta-doc/ppt/133735/xxxxx.pptx",
        "templateId": "1862040730604896256",
        "pptxProperty": null,
        "userId": "133735",
        "userName": "133735",
        "companyId": 133735,
        "updateTime": "2025-07-08 15:11:49",
        "createTime": "2025-07-08 15:11:49",
        "extInfo": {},
        "totalPage": 19,
        "genType": null,
        "createUser": null,
        "updateUser": null
    },
    "message": "PPT生成成功"
  }
  ```

---
#### 2. 标准分步生成流程
此流程将PPT生成分解为三个主要步骤，可进行更精细的调整。

##### 2.1. 步骤一：创建PPT生成任务
- **POST** `/task`
- **描述**: 这是所有PPT生成流程的起点。根据不同的`task_type`，您可以通过主题、文本、文件、URL等多种方式来初始化一个PPT生成任务，并获得一个唯一的 `task_id`, task_id是后续操作必须值。
- **请求**: `multipart/form-data`
- **表单字段**:
  - `task_type` (int, **必需**): 任务类型，决定了`content`和`files`字段的用途。
    - `1`: **智能生成**: 根据`content`中的主题或要求，并可结合`files`中的参考文件，生成PPT。
    - `2`: **文件上传**: 将`files`中上传的一个或多个文件（PDF, Docx等）内容转换为PPT。
    - `3`: **思维导图**: `content`为分享链接，或`files`为`xmind`/`mm`/`md`文件。
    - `4`: **Word转PPT**: `files`中必须包含一个Word文件 (`doc`/`docx`)。
    - `5`: **网页转PPT**: `content`中提供一个网页URL。
    - `6`: **文本转PPT**: `content`中粘贴大段文本。
    - `7`: **Markdown转PPT**: `content`中提供Markdown格式的大纲。
  - `content` (str, 可选): 文本内容，其含义由`task_type`决定。
  - `files` (List[UploadFile], 可选): 上传的文件列表。
- **请求示例**:
  - **类型1 (智能生成)**:
    ```
    task_type: 1
    content: "量子力学入门"
    ```
  - **类型2 (文件上传)**:
    ```
    task_type: 2
    files: [file1.pdf, file2.docx]
    ```
  - **类型7 (Markdown)**:
    ```
    task_type: 7
    content: "# 量子力学\n\n## 1. 波粒二象性\n\n- 介绍..."
    ```
- **成功响应 (200)**: 返回用于后续步骤的 `task_id`。
  ```json
  {
    "success": true,
    "task_id": "653b3a3e6a4b2a0001e4a3b1",
    "message": "任务创建成功"
  }
  ```

##### 2.2. 步骤二：生成大纲和内容
- **POST** `/task/{task_id}/content`
- **描述**: 基于第一步创建的任务，调用AI生成PPT的详细大纲和每一页的具体内容（Markdown格式）。支持流式和非流式两种返回方式。
- **路径参数**: `task_id: str` (**必需**)
- **请求体**: `GenerateContentRequest`
  ```json
  {
    "length": "medium",
    "lang": "zh",
    "scene": "教学课件",
    "audience": "学生",
    "prompt": "请确保概念解释清晰，并适当引用相关实验。",
    "stream": false
  }
  ```
- **请求体详解**:
  - `length` (str, 可选): 篇幅，可选值同上。默认: `"medium"`。
  - `lang` (str, 可选): 语言。默认: `"zh"`。
  - `scene` (str, 可选): 演示场景。
  - `audience` (str, 可选): 目标受众。
  - `prompt` (str, 可选): 额外要求。
  - `stream` (bool, 可选): 是否流式返回。`true`返回SSE事件流，`false`返回完整JSON。默认: `false`。
- **成功响应**:
  - `stream: false`: **(200 `application/json`)**
    ```json
    {
      "success": true,
      "data": {
        "text": "# PPT标题\n\n---\n\n## 页面1\n\n- 内容点1\n- 内容点2",
        "result": { "...(元数据)..." }
      }
    }
    ```
  - `stream: true`: **(200 `text/event-stream`)** 将会持续推送 `data: {...}` 格式的JSON块。

##### 2.3. 步骤三：生成PPTX文件
- **POST** `/task/{task_id}/pptx`
- **描述**: 将第二步生成的Markdown内容与指定的PPT模板结合，最终生成并保存`.pptx`格式的物理文件到服务器。
- **路径参数**: `task_id: str` (**必需**)
- **请求体**: `GeneratePptxRequest`
  ```json
  {
    "markdown": "# 标题\n\n---\n\n## 页面1\n\n- Point 1\n- Point 2",
    "template_id": "1862040730604896256"
  }
  ```
- **请求体详解**:
  - `markdown` (str, **必需**): 从上一步获取或用户自行修改的完整PPT Markdown内容。
  - `template_id` (str, **必需**): 模板ID，可通过模板查询接口获取。
- **成功响应 (200)**: 返回完整的PPT信息。文件保存在第三方服务，通过`fileUrl`访问。
  ```json
  {
    "success": true,
    "data": {
        "id": "1942481641276575744",
        "name": "质点运动学",
        "subject": "质点运动学",
        "coverUrl": "https://chatmee.cn/api/public/oss/meta-doc/ppt/133735/xxxxx",
        "fileUrl": "https://chatmee.cn/api/public/oss/meta-doc/ppt/133735/xxxxx.pptx",
        "templateId": "1862040730604896256",
        "pptxProperty": null,
        "userId": "133735",
        "userName": "133735",
        "companyId": 133735,
        "updateTime": "2025-07-08 15:11:49",
        "createTime": "2025-07-08 15:11:49",
        "extInfo": {},
        "totalPage": 19,
        "genType": null,
        "createUser": null,
        "updateUser": null
    },
    "message": "PPTX文件生成成功"
  }
  ```

---
#### 3. 模板与选项
用于查询和筛选PPT模板，以及获取内容生成的可用选项。

##### 3.1. 查询PPT模板
- **POST** `/templates`
- **描述**: 根据类目、风格、颜色等条件分页查询可用的PPT模板。
- **请求体**: `ListTemplatesRequest`
  ```json
  {
    "page": 1,
    "size": 12,
    "template_type": 1,
    "category": "教育培训",
    "style": "简约",
    "theme_color": null,
    "lang": "zh"
  }
  ```
- **成功响应 (200)**: 返回模板列表和总数。
  ```json
  {
    "success": true,
    "data": {
      "data": [
        {
          "id": "1862040730604896256",
          "name": "通用教育模板",
          "coverUrl": "https://...",
          "lang": "zh",
          "...": "..."
        }
      ],
      "total": 1
    }
  }
  ```

##### 3.2. 随机获取PPT模板
- **POST** `/random-templates`
- **描述**: 随机获取指定数量的模板，支持过滤条件。
- **请求体**: `RandomTemplatesRequest`
  ```json
  {
    "size": 4,
    "template_type": 1,
    "category": "科技",
    "exclude_ids": ["1862040730604896256"]
  }
  ```
- **成功响应 (200)**: 返回随机模板列表。

##### 3.3. 获取PPT模板过滤选项
- **GET** `/template-options`
- **描述**: 获取用于筛选模板的可用选项，如所有可用的`category` (类目), `style` (风格), `themeColor` (主题色)。
- **查询参数**: `lang: Optional[str]` (e.g., 'zh-CN', 'en')
- **成功响应 (200)**:
  ```json
  {
    "success": true,
    "data": {
      "category": [{"label": "教育培训", "value": "教育培训"}, ...],
      "style": [{"label": "简约", "value": "简约"}, ...],
      "themeColor": [...]
    }
  }
  ```

##### 3.4. 获取PPT内容生成选项
- **GET** `/options`
- **描述**: 获取在调用"生成大纲和内容"接口时，可用的`lang` (语种), `scene` (场景), `audience` (受众) 等选项。
- **查询参数**: `lang: Optional[str]` (e.g., 'zh', 'en')
- **成功响应 (200)**:
  ```json
  {
    "success": true,
    "data": {
      "lang": [{"name": "简体中文", "value": "zh"}, ...],
      "scene": [{"name": "通用场景", "value": "通用场景"}, ...],
      "audience": [{"name": "大众", "value": "大众"}, ...]
    }
  }
  ```

---
### 媒体与文件 API
**路由前缀**: `/api/media`

#### 1. 文本转语音 (TTS)
- **POST** `/tts`
- **描述**: 将一段文本转换为语音文件。
- **请求体**: `TTSRequest`
  ```json
  {
    "text": "欢迎使用智能PPT生成系统",
    "language": "zh",
    "voice": "alloy",
    "speed": 1.0
  }
  ```
- **成功响应 (200)**: 返回音频文件名。

#### 2. 生成教学视频
- **POST** `/videos`
- **描述**: 根据主题和内容脚本生成一个教学视频。
- **请求体**: `VideoGenerationRequest`
- **成功响应 (200)**: 返回视频文件名。

#### 3. 列出生成的文件
- **GET** `/files/{file_type}`
- **描述**: 列出指定类型的所有已生成文件。
- **路径参数**: `file_type: str` (有效值: `ppt`, `videos`, `audio`)
- **成功响应 (200)**: 返回文件信息列表。

#### 4. 下载文件
- **GET** `/files/{file_type}/{filename}/download`
- **描述**: 下载一个已生成的文件。
- **路径参数**: `file_type: str`, `filename: str`
- **成功响应 (200)**: 返回文件流 (`FileResponse`)。
