# Legacy MateMaTeX 1.0 (`src/`)

The `src/` directory at the repository root contains **MateMaTeX 1.0** — an earlier
Streamlit-based prototype with tools, agents, and UI code.

**MateMaTeX 2.0** lives in:

- `backend/` — FastAPI API, AI pipeline, LaTeX compilation
- `frontend/` — Next.js web application

Do not add new features under `src/`. It is kept for reference until fully archived.

To run v2 locally:

```bash
# Backend
cd backend && uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend && npm run dev
```
