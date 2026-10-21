# IndiValidate — Frontend Analytics Dashboard

Modern, light analytics dashboard for **IndiValidate — AI-Powered Multi-Persona Market Validation System**. Built with React 19, TypeScript, Vite, Tailwind CSS v4, Lucide Icons, and Recharts.

---

## Features & Pages

1. **Overview Dashboard (`/`)**:
   - Executive briefing of the evaluated business idea.
   - Core validation metrics: Synthetic Personas Evaluated, Empirical Evidence Coverage %, Identified Risks, and Promising Value Propositions.
   - Quick-start input for direct validation.
   - Grounded empirical signals vs model knowledge notice.

2. **New Analysis (`/new-analysis`)**:
   - Business concept input.
   - Optional 5-Question Founder Intake matching backend Pydantic schemas:
     1. Customer Category & Profile
     2. Core Customer Problem
     3. Launch Geography & Scope
     4. Known Alternatives & Competitors
     5. Monetization Model, Expected Price, and Prior Validation
   - Configurable Persona Count (1-25, default 10) and Evaluation Concurrency (1-10, default 3).
   - Client-side validation with actionable error feedback.

3. **Live Progress Telemetry (`/progress`)**:
   - Real-time elapsed duration counter (no fabricated completion percentages).
   - Multi-stage LangGraph workflow visualization (Preprocessing, Retrieval, Archetype Calibration, Multi-Agent Evaluation, Report Synthesis).
   - AbortController cancellation and error recovery.

4. **Personas & Segments (`/personas`)**:
   - Recharts comparative bar chart across Interest, Purchase Intent, Perceived Value, Affordability, and Adoption Barrier.
   - Segment-by-segment audit cards with evaluated vs allocated persona counts.
   - Intended persona workflow narratives from proposal synthesis.
   - Epistemic disclaimer: strictly separates synthetic multi-agent simulations from real customer interviews.

5. **Market Insights (`/market-insights`)**:
   - **Core Research Questions Analysis**: Color-coded epistemic basis badges:
     - `retrieved_evidence` (Emerald): Strictly grounded in retrieved empirical evidence.
     - `mixed` (Amber): Combines empirical data with domain reasoning.
     - `model_knowledge` (Indigo): Independent LLM reasoning fallback when sources return no data.
   - External validation requirements and confidence assessments.
   - Evidence coverage audit ratio with breakdown (supported, contradicted, mixed, insufficient).
   - Feature prioritization tiers (`High Priority Candidate`, `Controversial`, `Secondary`).
   - Macroeconomic labour wage benchmarks from PLFS 2025.

6. **Full Report & Export (`/reports`)**:
   - Complete 9-section structured audit document.
   - One-click **Markdown Export** (`.md`) matching the backend schema format.
   - One-click **JSON Export** (`.json`) containing the complete `MarketValidationReport`.
   - Copy Markdown to clipboard and browser print support.

---

## Local Development & Setup

### Prerequisites
- Node.js v18+ (tested on Node v24.13.1)
- Python 3.10+ with FastAPI and LangGraph backend installed

### 1. Start the FastAPI Backend
In your backend terminal (from repository root):
```powershell
uvicorn api:app --host 127.0.0.1 --port 8000 --reload
# Or directly:
py api.py
```
Verify backend health:
`http://127.0.0.1:8000/health` -> `{"status":"ok","service":"IndiValidate"}`

### 2. Start the Frontend Dev Server
In a separate terminal:
```powershell
cd frontend
npm install
npm run dev
```
Open your browser at `http://localhost:5173`. The Vite proxy will automatically forward API requests to `http://127.0.0.1:8000`.

### 3. Build & Type-Check
```powershell
cd frontend
npm run build
```
Generates production bundle in `frontend/dist/`.
