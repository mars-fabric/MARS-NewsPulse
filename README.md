# MARS-NewsPulse

AI-powered industry news intelligence platform that generates executive-level sentiment analysis reports through automated web research.

## What It Does

MARS-NewsPulse runs a 4-stage pipeline to discover, analyze, and synthesize market news into professional PDF reports:

1. **Setup & Config** — Capture industry, companies, region, time window, and LLM preferences
2. **News Discovery** — AI-driven web search (DuckDuckGo) for raw news collection
3. **Deep Analysis** — Sentiment analysis and trend extraction
4. **Final Report** — 12-section executive report with sentiment dashboards + PDF export

### Key Features

- Real-time WebSocket console streaming during execution
- Multi-provider LLM support (OpenAI, Anthropic, Google Gemini, Azure, AWS Bedrock)
- Human-in-the-loop (HITL) review between stages
- PDF report generation with charts and sentiment dashboards
- Session management and task history tracking
- Credential management UI

## Tech Stack

| Layer    | Technologies                                                  |
| -------- | ------------------------------------------------------------- |
| Backend  | Python, FastAPI, LangGraph, LangChain, WeasyPrint, SQLite     |
| Frontend | Next.js 16, React 18, TypeScript, Tailwind CSS, Socket.IO     |
| AI/ML    | cmbagent framework, multi-provider LLM orchestration          |
| Search   | DuckDuckGo Search (ddgs)                                      |

## Project Structure

```
MARS-NewsPulse/
├── backend/
│   ├── routers/           # API endpoints (newspulse, credentials, providers, models)
│   ├── task_framework/    # AI agents, phases, prompts, and helpers
│   ├── core/              # App factory, config, logging
│   ├── services/          # Session manager, credential vault, PDF extractor
│   ├── models/            # Pydantic schemas
│   ├── execution/         # Stream capture, cost tracking
│   ├── websocket/         # Real-time communication
│   ├── main.py            # Entry point
│   ├── run.py             # Dev server launcher
│   └── requirements.txt
├── frontend/
│   ├── app/               # Next.js App Router pages
│   ├── components/        # React components (newspulse, sessions, console, workflow)
│   ├── hooks/             # Custom React hooks
│   ├── lib/               # Utilities
│   ├── types/             # TypeScript type definitions
│   └── package.json
├── .env.example           # Environment template
└── README.md
```

## Getting Started

### Prerequisites

- Python 3.8+
- Node.js 18+
- API key for at least one LLM provider (OpenAI, Anthropic, Google Gemini, or Azure)

### 1. Clone & Configure

```bash
git clone https://github.com/mars-fabric/MARS-NewsPulse.git
cd MARS-NewsPulse
cp .env.example .env
```

Edit `.env` and add your API keys:

```env
OPENAI_API_KEY=your-key-here
# and/or
ANTHROPIC_API_KEY=your-key-here
GEMINI_API_KEY=your-key-here
```

### 2. Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python run.py
```

Backend starts at `http://localhost:6970`. API docs available at `http://localhost:6970/docs`.

### 3. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Frontend starts at `http://localhost:3000`.

## Configuration

Key environment variables:

| Variable                        | Description                          | Default                    |
| ------------------------------- | ------------------------------------ | -------------------------- |
| `OPENAI_API_KEY`                | OpenAI API key                       | —                          |
| `ANTHROPIC_API_KEY`             | Anthropic API key                    | —                          |
| `GEMINI_API_KEY`                | Google Gemini API key                | —                          |
| `PORT`                          | Backend server port                  | `6970`                     |
| `CMBAGENT_DEFAULT_WORK_DIR`     | Working directory for task outputs   | `./mars_newspulse_cmbdir`  |
| `CMBAGENT_CORS_ORIGINS`         | Allowed CORS origins                 | `http://localhost:3000`    |
| `LOG_LEVEL`                     | Logging level                        | `INFO`                     |

## API Overview

| Endpoint                                              | Method | Description                     |
| ----------------------------------------------------- | ------ | ------------------------------- |
| `/api/health`                                         | GET    | Health check                    |
| `/api/newspulse/create`                               | POST   | Create a new task               |
| `/api/newspulse/{task_id}/stages/{stage}/execute`     | POST   | Execute a pipeline stage        |
| `/api/newspulse/{task_id}`                             | GET    | Get task state                  |
| `/api/newspulse/{task_id}/stages/{stage}/content`     | GET    | Get stage output                |
| `/api/newspulse/{task_id}/stages/{stage}/refine`      | POST   | Refine stage output with AI     |
| `/api/newspulse/recent`                               | GET    | List recent tasks               |
| `/api/providers`                                      | GET    | List LLM providers              |
| `/api/models/available`                               | GET    | List available models           |
| `/api/credentials/test-all`                           | GET    | Test all configured credentials |
| `WS /ws/newspulse/{task_id}/{stage}`                  | WS     | Real-time execution streaming   |

Full API documentation is available at `/docs` when the backend is running.

## License

Proprietary — MARS Fabric
