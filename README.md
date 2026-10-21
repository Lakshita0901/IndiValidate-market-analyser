# IndiValidate — AI-Powered Multi-Persona Market Validation System

IndiValidate is an empirical market validation platform designed to stress-test early stage business ideas. It combines official government microdata (Census 2011, PLFS 2025), community forum sentiment (Reddit via Kaggle dataset), and relative search interest (Google Trends) with multi-agent synthetic persona simulations and an LLM-native fallback answering engine.

---

## Architecture Overview

1. **Preprocessing & Routing**: Categorizes the idea, extracts research keywords, and determines regional vs national context.
2. **Founder Intake (Optional)**: 5-question intake capturing customer category, description, problem, launch geography/alternatives, and monetization model.
3. **Multi-Source Empirical Research**: Gathers demography from Census 2011, labour indicators from PLFS 2025, qualitative sentiment from Reddit, and search interest from Google Trends.
4. **Vector Storage & Semantic Retrieval**: Chunked and indexed in ChromaDB for traceable grounding.
5. **Synthetic Persona Generation**: Generates 10 diverse persona archetypes.
6. **Bounded Multi-Agent Evaluation**: Evaluates interest, purchase intent, perceived value, affordability, and adoption barriers with bounded concurrency (default 3 concurrent workers).
7. **Market Analysis & Evidence Audit**: Measures empirical evidence coverage ratio and tracks contradictions.
8. **LLM-Native Fallback Engine**: When research sources return no data, independently answers core validation questions using domain reasoning tagged as `model_knowledge` rather than forcing "no data available".
9. **Structured Report Synthesis**: Assembles executive summary, findings, segment comparison, feature prioritization, pricing assessment, evidence audit, and recommended experiments.

---

## FastAPI Backend

### Startup Command
From the project root:
```powershell
uvicorn api:app --host 127.0.0.1 --port 8000 --reload
# Or directly:
py api.py
```

### Endpoints
- `GET /health` -> Lightweight health check (instant 200, zero external LLM/scraper calls).
- `POST /api/analyze` -> Runs the complete LangGraph market validation pipeline.
- `GET /docs` -> Interactive Swagger API documentation.

### Request Payload (`POST /api/analyze`)
```json
{
  "idea": "Smart EV fleet charging hub and reservation software in Ahmedabad",
  "founder_context": {
    "customer_category": "Commercial EV fleet operators",
    "customer_description": "Fleet owners running 5 to 50 vehicles",
    "problem_description": "Frequent charger queues causing delivery delays",
    "launch_geography": "Ahmedabad",
    "geographic_scope": "local_city",
    "known_alternatives": ["Public charging stations", "Diesel generators"],
    "pricing_model": "subscription",
    "expected_price": "INR 3,000/month per vehicle",
    "validation_stage": "interviews_or_surveys",
    "validation_notes": "Spoke with 6 fleet managers",
    "validation_sample_size": 6
  },
  "persona_count": 10,
  "evaluation_concurrency": 3
}
```

---

## Frontend Web Application

The frontend is a clean, light analytics dashboard built with **React 19**, **TypeScript**, **Vite**, **Tailwind CSS v4**, and **Recharts**.

### Frontend Installation & Setup
```powershell
cd frontend
npm install
npm run dev
```
Open [http://localhost:5173](http://localhost:5173) in your browser. The Vite dev server proxies `/api` and `/health` requests to `http://127.0.0.1:8000`.

### Production Build & Type-Check
```powershell
cd frontend
npm run build
```

### Frontend Environment Configuration
Optional environment variables in `frontend/.env` (see `frontend/.env.example`):
```env
# Leave empty to use the Vite proxy (recommended for local development)
VITE_API_BASE_URL=
# Or specify explicit URL:
# VITE_API_BASE_URL=http://127.0.0.1:8000
```

### Frontend Pages
1. **Overview**: Executive summary, key metric cards (evaluated personas, evidence coverage %, risks, promising findings), quick-launch input.
2. **New Analysis**: Business proposal input, optional 5-question founder intake form, and advanced execution sliders (persona count & concurrency).
3. **Live Progress**: Real-time elapsed duration timer, synchronous pipeline telemetry, cancellation, and error handling.
4. **Personas & Segments**: Recharts bar chart comparing segment evaluation scores, segment profile cards, intended use-case narratives, and synthetic persona disclaimers.
5. **Market Insights**: Core Research Questions Analysis with color-coded epistemic basis badges (`retrieved_evidence`, `mixed`, `model_knowledge`), evidence coverage audit, feature prioritization tiers, and PLFS wage benchmarks.
6. **Full Report & Export**: Complete structured 9-section report view with JSON and Markdown export/download and clipboard copy.

---

## Running Automated Tests

Run backend tests:
```powershell
py -m pytest tests/test_fallback_answer.py tests/test_api.py -v
```

Run frontend build check:
```powershell
cd frontend
npm run build
```
