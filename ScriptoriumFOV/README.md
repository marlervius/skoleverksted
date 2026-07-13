# Scriptorium

En webapp som genererer PDF-læringsark for voksne innvandrere som lærer norsk, tilpasset fag og språknivå (CEFR, inkl. undernivå).

## Project Structure

```
Scriptorium/
├── backend/          # Python FastAPI backend
│   ├── main.py       # FastAPI application
│   ├── requirements.txt
│   └── .env.example
├── frontend/         # Next.js 14 frontend
│   ├── app/          # App Router pages
│   ├── package.json
│   └── ...
└── README.md
```

## Getting Started

### Backend Setup

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   ```

3. Activate the virtual environment:
   - Windows: `venv\Scripts\activate`
   - macOS/Linux: `source venv/bin/activate`

4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

5. Copy `.env.example` to `.env` and add your API keys:
   ```bash
   cp .env.example .env
   ```

6. Run the development server:
   ```bash
   uvicorn main:app --reload
   ```

The API will be available at `http://localhost:8000`

### Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Run the development server:
   ```bash
   npm run dev
   ```

The frontend will be available at `http://localhost:3000`

## API Endpoints

- `GET /` – Health check
- `GET /health` – Status + `progress_store` (`memory` or `redis`)
- `GET /docs` – OpenAPI (Swagger UI)
- `GET /auth/config` – `{ "password_required": bool }` (no secret leaked)
- `POST /auth/verify` – JSON `{ "password": "..." }` – 200 if password matches (when `APP_PASSWORD` is set)
- `POST /generate-lesson` – Start PDF generation (JSON body; `Authorization: Bearer …` if `APP_PASSWORD` set)
- `POST /generate-lesson-json` – Preview: JSON only (poll + `GET /download-json/{id}`)
- `POST /generate-pdf-from-json` – PDF from preview payload
- `POST /generate-dual-lesson` – Two CEFR PDFs as ZIP
- `POST /generate-lesson-with-image` – Multipart form + image file
- `GET /generation-status/{id}` – Poll step / message
- `GET /download-pdf/{id}` / `GET /download-zip/{id}` / `GET /download-json/{id}` – Fetch result

See [DEPLOYMENT.md](DEPLOYMENT.md) for env vars (including optional `REDIS_URL`).

## Troubleshooting: Gemini `429` / quota

If you see **RESOURCE_EXHAUSTED** or **quota exceeded** for `gemini-2.0-flash`:

- **Free tier** has low per-minute and per-day limits. Features that run **several generations in parallel** (e.g. multi-level ZIP, dual nabonivå) use more quota quickly.
- **Mitigations:** wait for the limit window to reset; enable **billing** in [Google AI Studio](https://aistudio.google.com/) for higher limits; temporarily use a single PDF instead of multi-level/dual.
- **Model:** set `GOOGLE_MODEL` to another model your project still has quota for (check [rate limits](https://ai.google.dev/gemini-api/docs/rate-limits)), e.g. `gemini-2.0-flash-lite` or `gemini-1.5-flash` if available.

The backend retries rate-limited calls a few times using the API’s suggested delay when present.

## Tech Stack

### Backend
- **FastAPI** - Modern Python web framework
- **CrewAI** - AI agent orchestration
- **LangChain Google GenAI** - Google Gemini integration
- **Typst** - PDF generation

### Frontend
- **Next.js 14** - React framework with App Router
- **TypeScript** - Type-safe JavaScript
- **Tailwind CSS** - Utility-first CSS framework

## CEFR Levels Supported

- A1 - Beginner
- A2 - Elementary
- B1 - Intermediate
- B2 - Upper Intermediate
