# AI Academic Orientation Agent - Institut Universitaire de la Côte (IUC)

An intelligent chatbot system that provides personalized academic guidance to students of IUC, using Mistral-7B LLM with FastAPI backend, n8n workflow automation, and responsive web interface.

## Table of Contents
- [Features](#features)
- [System Architecture](#system-architecture)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [API Endpoints](#api-endpoints)
- [Workflow Diagram](#workflow-diagram)
- [Troubleshooting](#troubleshooting)


## Features

**Intelligent Academic Advisory**
- Personalized program recommendations based on educational background
- Supports 50+ Francophone (BAC/BT) and Anglophone (GCE/TVE) series
- Validates subject combinations against IUC program requirements
- Career pathway mapping from high school to graduate studies

**Multi-language Support**
- Automatic French/English language detection
- Context-aware responses in user's preferred language
- Program names preserved in original language (no translation)
- Education system recognition (Francophone vs Anglophone)

**Smart Data Processing**
- Real-time IUC API integration with intelligent caching
- HTML content extraction and summarization (3000+ chars → ~600 chars)
- 7-day TTL cache with automatic refresh
- "STAFF" entry filtering and data cleaning

**Performance Optimized**
- Content summarization reduces token usage by 70-80%
- CPU-optimized Mistral-7B inference
- Batch processing for efficient LLM operations
- Mobile-responsive web interface


## System Architecture
```diagram
┌─────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│   Web Interface │    │   n8n Workflow   │    │  FastAPI Backend │
│  (HTML/CSS/JS)  │◄──►│  (Orchestration) │◄──►│ (Python + LLM)   │
└─────────────────┘    └──────────────────┘    └──────────────────┘
         │                       │                       │
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│   Student       │    │ Mistral Cloud    │    │   IUC API        │
│   Interactions  │    │     AI           │    │   Data Source    │
└─────────────────┘    └──────────────────┘    └──────────────────┘
```


## Installation

**Prerequisites**
- Python 3.10+
- Node.js 22 (for n8n)
- Mistral API access on n8n
- IUC API credentials
- 8GB RAM (for Mistral-7B CPU inference)

**Setup**
1. Clone and Setup Backend
```bash
git clone https://github.com/your-repo/iuc-orientation-agent.git
cd iuc-orientation-agent
```

**Install Python dependencies**
```bash
pip install fastapi uvicorn llama-cpp-python httpx python-multipart
```
**Download Mistral model**
```bash
wget https://huggingface.co/mistral-7b-instruct-v0.1.Q4_K_M.gguf -O models/
```

2. Configure Environment
```bash
export MODEL_PATH="models/mistral-7b-instruct-v0.1.Q4_K_M.gguf"
export API_BASE_URL="https://iuc-api-aca.bitang.net/api"
export ApiKey="your_iuc_api_key_here"
```

3. Start Services
```bash
# Terminal 1 - Start FastAPI backend
python mist_with_api3.py
or 
uvicorn mist_with_api3:app --host 0.0.0.0 --port 8000

# Terminal 2 - Serve web interface
python -m http.server 3000

### Terminal 3 - Start n8n (if using local n8n)
n8n start
```

## Configuration

### Environment Variables
Create .env file:

ini
MODEL_PATH=models/mistral-7b-instruct-v0.1.Q4_K_M.gguf
API_BASE_URL=https://iuc-api-aca.bitang.net/api
API_KEY=your_iuc_api_key_here
CACHE_TTL=604800

### n8n Workflow Setup
Import Workflow JSON into your n8n instance

### Configure Credentials:
- Mistral Cloud API key
- Webhook URLs

### Update Endpoints:
- Backend API URL (http://localhost:8000)
- Webhook response URL

### Model Configuration
```python
MODEL_CONFIG = {
    "n_ctx": 8192,        # Context window size
    "n_threads": 4,       # CPU threads for inference
    "n_gpu_layers": 0,    # CPU-only mode
    "use_mmap": True,     # Memory mapping for efficiency
    "low_vram": True,     # Optimized memory usage
    "n_batch": 512,       # Batch processing
    "verbose": False
}
```

## Usage
### Student Interactions
- Francophone Example:
```text
Student: "J'ai fait la série D au bac, quels programmes me conseillez-vous ?"

Assistant: "Avec votre baccalauréat série D (Mathématiques, Sciences de la vie et de la terre), 
voici des programmes adaptés à l'IUC:
• Licence en Biologie
• BTS en Analyses Biologiques  
• Prépa Santé
• Licence en Environnement"
```

- Anglophone Example:
```text
Student: "I completed GCE A-Level S3, what can I study?"

Assistant: "With your GCE A-Level S3 (Biology, Chemistry, Mathematics), 
here are suitable IUC programs:
• BSc in Biological Sciences
• HND in Laboratory Technology
• BSc in Biochemistry
• Pre-Medical Foundation"
```

### Supported Education Systems
- Francophone:
BAC Series: A1, A2, A3, A4, A5, ABI, SH, AC, C, D, E, TI, etc
BT Series: Hôtellerie, Tourisme, Agriculture, Techniques Industrielles
BTS Programs

- Anglophone:
GCE A-Level: S1-S8 (Science), A1-A5 (Arts & Social Sciences)
TVE A-Level: C1-C4 (Commercial), T1-T3 (Technical), CS1-CS2 (Computer Science)
HND Programs


## API Endpoints
  |  Endpoint	           |   Method	|    Description
  -----------------------|----------|--------------------------------------------
  | /health	             |   GET	  | System status and cache information
  | /api/context	       |   GET	  | Get cached academic data (n8n integration)
  | /api/specialities	   |   GET	  | List all processed academic programs
  | /api/raw-data	       |   GET	  | Debug endpoint for raw API data
  | /api/processed-data	 |   GET	  | Debug endpoint for processed data
  | /webhook/orientation |	 POST	  | Main chat endpoint (from web interface)

- Sample Request:

```json
{
  "chatInput": "What programs are available for BAC série D students?",
  "sessionId": "sess-abc123"
}
```
- Sample Response:

```json
{
  "output": "With your BAC série D background, here are suitable programs...",
  "sessionId": "sess-abc123",
  "timestamp": "2024-01-15T10:30:00Z"
}
```


## Workflow Diagram 
```Code
sequenceDiagram
    participant Student
    participant WebUI
    participant n8n
    participant Backend
    participant Mistral
    participant IUCAPI

    Student->>WebUI: Submit Query
    WebUI->>n8n: POST /orientation
    n8n->>Backend: GET /api/context
    Backend->>IUCAPI: Fetch Academic Data
    IUCAPI-->>Backend: Return Programs
    Backend-->>n8n: Structured Data
    n8n->>Mistral: AI Processing
    Mistral-->>n8n: Generated Response
    n8n-->>WebUI: Formatted Answer
    WebUI-->>Student: Display Results
```

## Troubleshooting
### Common Issues & Solution
```text
- Issue: Model fails to load
- Solution: Verify MODEL_PATH and file permissions
            Check available RAM (minimum 4GB)

- Issue: API connectivity errors
- Solution: Verify IUC API credentials
            Check network connectivity to iuc-api-aca.bitang.net

- Issue: n8n workflow timeouts
- Solution: Increase timeout in HTTP nodes (default: 30s)
            Check webhook URL configurations

- Issue: CORS errors in web interface
- Solution: Verify CORS headers in n8n RespondToWebhook node
            Check backend CORS middleware configuration

- Issue: Cache not updating
- Solution: Manual cache reset via server restart
            Check TTL configuration (default: 7 days)
```

###  Debug Endpoints
Use these endpoints for troubleshooting:
- Check system health
```bash
curl http://localhost:8000/health
```

- View raw API data
```bash
curl http://localhost:8000/api/raw-data
```

- Check processed specialities
```bash
curl http://localhost:8000/api/specialities
```

- Test chat functionality
```bash
curl -X POST http://localhost:8000/webhook/orientation \
  -H "Content-Type: application/json" \
  -d '{"chatInput": "test query"}'
```

### Performance Monitoring
- Backend: Check /health endpoint for cache status and uptime
- n8n: Monitor workflow executions in n8n dashboard
- Frontend: Browser console for JavaScript errors
- API: Response times and error rates

