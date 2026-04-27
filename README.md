# AI 教师助手系统（ai-teach）

一个面向教学场景的智能教学平台，支持知识库检索增强（RAG）、AI 教师助手、PPT 生成、练习题生成、学习反馈与学情分析。

## 1. 项目架构说明（重点）

本项目是**前后端分离 + 双后端并行架构**：

- 前端：`frontend`（Vue3 + Vite，默认端口 `5173`）
- Python 后端：`PPTbackend-master`（FastAPI，默认端口 `7878`）
- Java 后端：`backend`（Spring Boot，默认端口 `8080`）

### 当前运行事实

- 系统默认主链路通常为：`frontend -> FastAPI(7878)`  
- 同时，`backend` 目录并非空壳，包含完整 Spring Boot 三层结构（Controller/Service/Repository/Entity），可独立运行并提供接口能力。

换句话说：**项目确实采用并实现了 Spring Boot 架构**，只是当前默认前端请求主要对接 FastAPI。

---

## 2. 核心功能

- AI 教师助手：问题解析、讲稿生成、逐页讲解、练习题、教学建议
- 知识库管理：知识库 CRUD、文档上传、检索、chunk 纠偏
- PPT 与媒体：PPT 生成、文件预览/下载、视频/语音相关能力
- 学情分析：提问日志、聚合统计、报告生成与落库
- 管理能力：角色、登录日志、系统配置、专业信息、教学设计、试卷管理

---

## 3. 技术栈

- 前端：Vue 3、Vite、Element Plus、Vue Router、Axios、ECharts、PWA
- FastAPI 后端：FastAPI、SQLAlchemy、MySQL、OpenAI 兼容 API、RAGFlow SDK
- Spring Boot 后端：Spring Boot 2.7.18、Spring Data JPA、MySQL
- 知识库链路：RAGFlow（独立服务）+ MinIO（PDF 链路按需）

---

## 4. 目录结构

```text
ai-teach/
├── frontend/                 # 前端应用（默认 5173）
├── PPTbackend-master/        # FastAPI 后端（默认 7878）
├── backend/                  # Spring Boot 后端（默认 8080）         
├── ragflow/                  # RAGFlow 源码/部署资料（必选）
├── mem0-main/                # mem0 源码（可选增强）
└── README.md
```
---

## 5. 快速开始（推荐主链路）

> 目标：先跑通“前端 + FastAPI 主后端”。

### 5.1 环境要求

- Node.js 16+
- Python 3.10+
- MySQL 8.0+（或 Docker）

### 5.2 启动 FastAPI 后端（7878）

```bash
cd PPTbackend-master
python -m venv venv

# Windows
venv\Scripts\activate
# Linux/macOS
# source venv/bin/activate

pip install -r requirements.txt
copy env.example .env
```

编辑 `.env`，至少配置：

- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `DATABASE_URL`

启动：

```bash
python main.py
```

### 5.3 启动前端（5173）

```bash
cd frontend
npm install
npm run dev
```

前端默认请求基址：

- `VITE_API_BASE_URL`（优先）
- 未配置时默认：`http://localhost:7878/api`

---

## 6. 启动 Spring Boot 后端（可并行）

如需启用 Java 后端能力，可单独启动：

```bash
cd backend
mvn clean install
mvn spring-boot:run
```

或 Windows 运行：

```bash
backend\start.bat
```

默认端口：`8080`。  
数据库配置见：`backend/src/main/resources/application.yml`。

---

## 7. 完整功能（知识库）启动说明

若要启用知识库上传/检索（RAG）能力，还需要可用的 RAGFlow 服务：

1. 启动 RAGFlow（本地或远程）
2. 在 `PPTbackend-master/.env` 配置：
   - `RAGFLOW_BASE_URL`
   - `RAGFLOW_API_KEY`

文档上传当前支持：

- `.pdf`（Marker + MinIO + RAGFlow）
- `.md/.markdown/.txt`（baseline 分片后入 RAGFlow）

仅上传 PDF 时，MinIO 链路是必需的。

---

## 8. 主要接口（按后端划分）

### 8.1 FastAPI（7878）

- 健康检查：`GET /api/health`
- 知识库：`/api/rag/*`
- AI 教师助手：`/api/ai_teacher/*`
- 学情分析：`/api/learning-analytics/*`
- 教学设计/试卷：`/api/teach-designs/*`、`/api/papers/*`
- 系统管理：`/api/system/*`、`/api/roles/*`、`/api/login-logs/*`

### 8.2 Spring Boot（8080）

- 健康与信息：`/api/health`、`/api/info`
- 试卷管理：`/api/paper-manage/*`
- 教学设计：`/api/teach-design/*`

---

## 9. 示例账号（数据库初始化后）

- `admin / admin123`
- `teacher / teacher123`
- `test / test123`

---

## 10. 提交与精简建议

用于课程/比赛提交时，建议主源码包保留：

- `frontend/`
- `PPTbackend-master/`
- `backend/`（如需体现双后端架构建议保留）
- `docs/`
- `README.md`

可按需剔除大型第三方源码目录（如 `ragflow/`、`mem0-main/`、`OpenMAIC-main/`）并单独说明依赖。

---

## 11. 说明

- 本项目用于教学与研究场景。
- 生产部署建议补充：反向代理与 HTTPS、配置分环境管理、日志监控、安全审计。

---

## 12. 作品安装包说明（评审用）

```text
作品编号-源代码/
├── frontend/
├── PPTbackend-master/
├── backend/            
└── README.md
```

素材包中建议仅保留代表性输入/输出样本（图片、视频、音频、示例文档），并控制总体体积（建议 500MB 以内）。

---

## 13. 评审快速复现（严格可运行版）

> 按当前系统实现，完整核心功能运行必须具备：**MySQL + RAGFlow**。  
> 若你要上传 PDF 到知识库，还必须配置 **MinIO**。

### 第一步：解压并进入项目根目录

```bash
cd ai-teach
```

### 第二步：启动依赖服务（必须）

请先启动并确认：

- MySQL（必须）
- RAGFlow（必须）
- MinIO（仅 PDF 上传链路必须）

建议先自检：

- MySQL 可连接（`DATABASE_URL` 对应库可访问）
- RAGFlow 可访问（`RAGFLOW_BASE_URL`）
- RAGFlow API Key 已配置（`RAGFLOW_API_KEY`）

### 第三步：启动 FastAPI 主后端（必须）

```bash
cd PPTbackend-master
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy env.example .env
python main.py
```

### 第四步：启动前端（必须）

```bash
cd frontend
npm install
npm run dev
```

### 第五步：访问地址

- 前端：`http://localhost:5173`
- FastAPI 健康检查：`http://localhost:7878/api/health`
---
## 14. 运行网址与测试账号

### 本地运行网址
- 前端主页：`http://localhost:5173`
- FastAPI：`http://localhost:7878`
- Spring Boot（可选）：`http://localhost:8080`

### 测试账号（数据库已初始化时）

- `admin / admin123`
- `teacher / teacher123`
- `test / test123`

---

## 15. 功能可用性矩阵（严格依赖）

| 功能 | 需要 MySQL | 需要 RAGFlow | 需要 MinIO |
|---|---|---|---|
| 用户登录/权限/系统管理 | ✅ | ❌ | ❌ |
| AI 教师助手（完整链路） | ✅ | ✅ | ❌ |
| 学情分析（日志+报告） | ✅ | ✅ | ❌ |
| 知识库创建/检索 | ✅ | ✅ | ❌ |
| PDF 上传入知识库 | ✅ | ✅ | ✅ |
| Markdown/TXT 上传入知识库 | ✅ | ✅ | ❌ |

结论：**完整核心功能 = MySQL + RAGFlow（PDF 上传再加 MinIO）**。

---
## 16. 环境变量配置（重点）

配置文件位置：
- `PPTbackend-master/.env`（由 `env.example` 复制得到）
### 必填（完整核心功能运行）

```env
OPENAI_API_KEY=你的模型API密钥
OPENAI_BASE_URL=你的OpenAI兼容网关地址
DATABASE_URL=mysql+pymysql://用户名:密码@localhost:3306/ai_teacher
RAGFLOW_BASE_URL=http://localhost:9380
RAGFLOW_API_KEY=你的RAGFlow密钥
```

### 上传 PDF 时必填配置

```env
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=xxx
MINIO_SECRET_KEY=xxx
MINIO_BUCKET_NAME=ai-teacher
```
---

## 17. 常见问题排查

### Q1：启动后提示 `OPENAI_API_KEY not set`

- 原因：`PPTbackend-master/.env` 未配置或未生效。
- 处理：
  1. 确认 `PPTbackend-master/.env` 中已填写 `OPENAI_API_KEY`
  2. 重启后端进程 `python main.py`

### Q2：知识库接口报 503 / RAG 不可用

- 原因：RAGFlow 未启动，或 `RAGFLOW_BASE_URL` / `RAGFLOW_API_KEY` 不正确。
- 处理：先确认 RAGFlow 可访问，再检查 `.env`。

### Q3：MySQL 连接失败

- 原因：`DATABASE_URL` 不正确或数据库未启动。
- 处理：启动 MySQL 并修正连接串后重启后端。

### Q4：系统可启动但核心功能不完整

- 原因：MySQL 或 RAGFlow 缺失（或配置错误）。
- 处理：先按第 13 节启动依赖服务，再启动后端与前端。

