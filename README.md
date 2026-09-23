# AI Teacher Assistant

<p align="center">
  <b>RAG-powered teaching assistant with knowledge-base retrieval, PPT generation, exercise generation, and learning analytics</b>
</p>

AI Teacher Assistant is a full-stack intelligent teaching platform built for course preparation, classroom assistance, and learning analytics. The system combines a **Vue 3 frontend**, a **FastAPI AI/RAG service**, and a **Spring Boot business backend**, with RAGFlow and MySQL providing the core knowledge and persistence layers.

---

## Core Capabilities

- **AI Teaching Assistant** — question answering, lecture-note generation, page-by-page explanations, teaching suggestions
- **Knowledge Base / RAG** — document upload, retrieval, chunk management, knowledge-base CRUD
- **PPT Generation** — generate teaching presentations and supporting materials
- **Exercise Generation** — create practice questions and teaching tasks from course content
- **Learning Analytics** — interaction logs, aggregated statistics, report generation
- **Teaching Management** — teaching designs, papers, roles, login logs, and system configuration
- **Document Support** — PDF, Markdown, and text ingestion through the knowledge pipeline

---

## Architecture

```text
                         ┌──────────────────────┐
                         │      Vue 3 UI        │
                         │      :5173           │
                         └──────────┬───────────┘
                                    │
                   ┌────────────────┴────────────────┐
                   │                                 │
        ┌──────────▼───────────┐          ┌──────────▼───────────┐
        │ FastAPI AI Backend   │          │ Spring Boot Backend  │
        │       :7878          │          │       :8080          │
        │ AI / RAG / Analytics │          │ Business APIs / JPA  │
        └──────────┬───────────┘          └──────────┬───────────┘
                   │                                 │
          ┌────────┴────────┐                       │
          │                 │                       │
   ┌──────▼──────┐   ┌──────▼──────┐        ┌──────▼──────┐
   │   RAGFlow   │   │    MinIO    │        │    MySQL    │
   │  Retrieval  │   │ PDF storage │        │ Persistence │
   └─────────────┘   └─────────────┘        └─────────────┘
```

The primary runtime path is typically:

```text
Frontend → FastAPI → RAGFlow / MySQL
```

The Spring Boot backend provides an additional independently runnable business-service layer.

---

## Tech Stack

| Layer | Technologies |
| --- | --- |
| Frontend | Vue 3, Vite, Element Plus, Vue Router, Axios, ECharts |
| AI Backend | FastAPI, SQLAlchemy, OpenAI-compatible API |
| Business Backend | Spring Boot 2.7, Spring Data JPA |
| Retrieval | RAGFlow |
| Storage | MySQL, MinIO |
| Other | PWA, document parsing, learning analytics |

---

## Repository Structure

```text
AI-teach/
├── frontend/                 # Vue 3 frontend
├── PPTbackend-master/        # FastAPI AI/RAG backend
├── backend/                  # Spring Boot backend
├── LICENSE
└── README.md
```

---

## Quick Start

### Requirements

- Node.js 16+
- Python 3.10+
- MySQL 8.0+
- RAGFlow for knowledge-base features
- MinIO when using the PDF upload pipeline

### 1. Start the FastAPI backend

```bash
cd PPTbackend-master

python -m venv venv

# Windows
venv\Scripts\activate

# Linux / macOS
# source venv/bin/activate

pip install -r requirements.txt
```

Create a local `.env` from the provided example and configure the required services.

Example:

```env
OPENAI_API_KEY=your_key
OPENAI_BASE_URL=your_openai_compatible_endpoint
DATABASE_URL=mysql+pymysql://user:password@localhost:3306/ai_teacher
RAGFLOW_BASE_URL=http://localhost:9380
RAGFLOW_API_KEY=your_ragflow_key
```

For PDF ingestion:

```env
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=your_access_key
MINIO_SECRET_KEY=your_secret_key
MINIO_BUCKET_NAME=ai-teacher
```

Start the service:

```bash
python main.py
```

### 2. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Default frontend URL:

```text
http://localhost:5173
```

The frontend reads `VITE_API_BASE_URL` when configured and otherwise uses the project's default FastAPI endpoint.

### 3. Optional: start the Spring Boot backend

```bash
cd backend
mvn clean install
mvn spring-boot:run
```

Default port:

```text
8080
```

---

## Service Dependencies

| Feature | MySQL | RAGFlow | MinIO |
| --- | :---: | :---: | :---: |
| User / role / system management | ✓ |  |  |
| AI teaching assistant | ✓ | ✓ |  |
| Learning analytics | ✓ | ✓ |  |
| Knowledge-base retrieval | ✓ | ✓ |  |
| PDF ingestion | ✓ | ✓ | ✓ |
| Markdown / text ingestion | ✓ | ✓ |  |

---

## Main API Groups

### FastAPI

- `GET /api/health`
- `/api/rag/*`
- `/api/ai_teacher/*`
- `/api/learning-analytics/*`
- `/api/teach-designs/*`
- `/api/papers/*`
- `/api/system/*`
- `/api/roles/*`
- `/api/login-logs/*`

### Spring Boot

- `/api/health`
- `/api/info`
- `/api/paper-manage/*`
- `/api/teach-design/*`

---

## Security Notes

- Do **not** commit real API keys, database passwords, or MinIO credentials.
- Keep local secrets in `.env` or another environment-specific secret store.
- For production deployment, add HTTPS, reverse proxying, access control, logging, monitoring, and security auditing.
- Create test accounts locally rather than publishing reusable default credentials in a public repository.

---

## Troubleshooting

### `OPENAI_API_KEY not set`

Check that `PPTbackend-master/.env` exists and contains the required model configuration, then restart the FastAPI service.

### RAG endpoint returns 503

Verify that RAGFlow is running and that `RAGFLOW_BASE_URL` and `RAGFLOW_API_KEY` are correct.

### MySQL connection fails

Confirm that MySQL is running and that `DATABASE_URL` points to an accessible database.

### Core features are unavailable after startup

The full AI/RAG workflow requires both **MySQL and RAGFlow**. PDF ingestion additionally requires **MinIO**.

---

## License

See [LICENSE](LICENSE) for details.
