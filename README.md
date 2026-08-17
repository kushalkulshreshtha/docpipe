# DocPipe — LLM-Powered Invoice Processing Pipeline

> An end-to-end document processing pipeline that ingests PDF invoices, extracts structured data using OpenAI, validates and enriches the output, and stores everything in PostgreSQL. Orchestrated with Prefect Cloud and deployed on Render.

[![Live API](https://img.shields.io/badge/Live%20API-Render-46E3B7?style=flat-square)](https://docpipe.onrender.com/docs)
[![Prefect Dashboard](https://img.shields.io/badge/Prefect-Dashboard-3E50E1?style=flat-square)](https://app.prefect.cloud)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python)](https://python.org)

---

## What It Does

Upload a PDF invoice → get back structured JSON with:
- Vendor name, address, invoice number
- Line items with quantities and prices
- Category classification (e.g. Software/SaaS, Travel, Consulting)
- USD-normalized totals (live exchange rates)
- Overdue flag and anomaly detection
- Natural language summary

All pipeline steps are visible in the **Prefect Cloud dashboard** in real-time.

---

## Architecture

```
                    ┌──────────────────────────────────────────┐
                    │         Prefect Cloud (Free)             │
                    │      Dashboard + Orchestration           │
                    └──────────────────┬───────────────────────┘
                                       │ monitors
                                       ▼
┌──────────────────────────────────────────────────────────────┐
│                      Render (Free Tier)                      │
│                                                              │
│  PDF Upload → Parse → Extract → Classify → Validate →       │
│               Summarize → Enrich → Store → API Response      │
│                                                              │
│                     FastAPI + Prefect Worker                 │
└──────────────────────────────┬───────────────────────────────┘
                               │ reads/writes
                               ▼
                   ┌───────────────────────┐
                   │     Neon (Free)       │
                   │     PostgreSQL        │
                   └───────────────────────┘
```

## Tech Stack

| Layer | Tool |
|---|---|
| Language | Python 3.11+ |
| LLM | OpenAI GPT-4o-mini (JSON mode) |
| PDF Parsing | pdfplumber + pytesseract (OCR fallback) |
| Validation | Pydantic v2 |
| Database | PostgreSQL (Neon, free tier) |
| ORM | SQLAlchemy 2.0 (async) |
| API | FastAPI |
| Orchestration | Prefect Cloud (free tier) |
| Hosting | Render (free tier) |
| Containerization | Docker |

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/documents/upload` | Upload a PDF invoice |
| `GET` | `/documents` | List all processed documents |
| `GET` | `/documents/{id}` | Get document + extracted data |
| `GET` | `/analytics/by-category` | Spend by expense category |
| `GET` | `/analytics/by-vendor` | Spend by vendor (top 20) |
| `GET` | `/health` | Health check |

Interactive docs: **`/docs`** (Swagger UI)

---

## Quick Start (Local)

### Prerequisites
- Docker & Docker Compose
- [uv](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- An [OpenAI API key](https://platform.openai.com)

### 1. Clone and configure

```bash
git clone https://github.com/your-username/docpipe.git
cd docpipe
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

### 2. Install dependencies

```bash
uv sync
```

### 3. Start the stack

```bash
docker-compose up --build
```

This starts:
- **FastAPI** on http://localhost:8000
- **PostgreSQL** on localhost:5432
- Swagger docs at http://localhost:8000/docs

### 3. Upload an invoice

```bash
curl -X POST http://localhost:8000/documents/upload \
  -F "file=@data/sample_invoices/sample_invoice.pdf"
```

### 4. Check the result

```bash
# List all processed documents
curl http://localhost:8000/documents

# Get structured data for a specific document
curl http://localhost:8000/documents/<document-id>

# Analytics
curl http://localhost:8000/analytics/by-category
```

---

## Cloud Deployment

### Services to set up (all free)

| Service | Signup | Purpose |
|---|---|---|
| [Neon](https://neon.tech) | Free | PostgreSQL database |
| [Prefect Cloud](https://app.prefect.cloud) | Free | Pipeline orchestration dashboard |
| [Render](https://render.com) | Free | App hosting |

### Deploy to Render

1. **Fork this repo** to your GitHub account

2. **Neon**: Create a project → copy the connection string (use the asyncpg URL format)

3. **Prefect Cloud**: Sign up → create a workspace → Settings → API Keys → generate key

4. **Render**:
   - New → Blueprint → connect your repo
   - Set environment variables:
     ```
     OPENAI_API_KEY=sk-...
     DATABASE_URL=postgresql+asyncpg://...@ep-xxx.neon.tech/docpipe?sslmode=require
     PREFECT_API_URL=https://api.prefect.cloud/api/accounts/.../workspaces/...
     PREFECT_API_KEY=pnu_...
     ```
   - Deploy → live in ~2 minutes

5. **Run migrations** (one-time):
   ```bash
   # After deploying, open Render shell or run locally against Neon:
   DATABASE_URL=<neon-url> alembic upgrade head
   ```

---

## Running Tests

```bash
# Run all tests with coverage
uv run pytest tests/ -v --cov=src --cov-report=term-missing
```

---

## Project Structure

```
docpipe/
├── src/
│   ├── config.py               # Settings via pydantic-settings
│   ├── models.py               # SQLAlchemy models
│   ├── schemas.py              # Pydantic schemas
│   ├── ingestion/
│   │   └── pdf_parser.py       # PDF text extraction + OCR fallback
│   ├── processing/
│   │   ├── prompts.py          # LLM prompt templates
│   │   ├── extractor.py        # Field extraction via OpenAI
│   │   ├── classifier.py       # Expense category classification
│   │   ├── summarizer.py       # Natural language summary
│   │   └── enricher.py         # USD normalization + anomaly detection
│   ├── validation/
│   │   └── validator.py        # Business rule validation
│   ├── storage/
│   │   └── repository.py       # Async DB CRUD + analytics queries
│   ├── pipeline/
│   │   └── orchestrator.py     # Prefect flow + tasks
│   └── api/
│       └── main.py             # FastAPI app + endpoints
├── tests/                      # pytest test suite
├── alembic/                    # Database migrations
├── data/sample_invoices/       # Sample PDFs for testing
├── Dockerfile
├── docker-compose.yml
└── render.yaml                 # Render deployment config
```

---

## Design Decisions

- **JSON mode over function calling**: OpenAI's `response_format: json_object` provides reliable structured output without the overhead of defining function schemas
- **OCR fallback**: Automatically detects image-based PDFs (< 50 chars of extractable text) and falls back to pytesseract
- **Documents are always stored**: Even failed extractions are stored with error metadata — useful for debugging and reprocessing
- **Async throughout**: SQLAlchemy 2.0 async + FastAPI async = handles concurrent uploads without blocking
- **Tenacity retries**: LLM calls are retried up to 3× with exponential backoff — essential for production reliability

---

## Sample Output

```json
{
  "vendor_name": "Acme Software Inc.",
  "invoice_number": "INV-2024-0142",
  "invoice_date": "2024-01-15",
  "due_date": "2024-02-14",
  "total": "2450.00",
  "total_usd": "2450.00",
  "currency": "USD",
  "category": "Software/SaaS",
  "category_confidence": 0.97,
  "summary": "$2,450 invoice from Acme Software Inc. for 3 months of cloud hosting services, due February 14, 2024.",
  "is_overdue": false,
  "days_until_due": 12,
  "anomaly_flags": {},
  "validation_status": "valid",
  "line_items": [
    {
      "description": "Cloud Hosting — Starter Plan (3 months)",
      "quantity": 3,
      "unit_price": "750.00",
      "total": "2250.00"
    },
    {
      "description": "Setup Fee",
      "quantity": 1,
      "unit_price": "200.00",
      "total": "200.00"
    }
  ]
}
```

---

## License

MIT
