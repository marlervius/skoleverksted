# Deployment

## Primary setup (Render)

The canonical production configuration lives in `backend/render.yaml` (Docker build, env vars).

Set at least:

- `GOOGLE_API_KEY` – Gemini / LiteLLM
- `GOOGLE_MODEL` – e.g. `gemini-3.5-flash`
- `APP_PASSWORD` – **required in production**: shared password; frontend sends `Authorization: Bearer <APP_PASSWORD>`. If unset, the API does not require a password (local dev only).
- `ALLOWED_ORIGINS` – comma-separated frontend URLs (not `*` in production)

### Optional: Redis (`REDIS_URL`)

Generation status and PDF/ZIP bytes are stored in **process memory** by default. If you run **more than one** API instance, set `REDIS_URL` so all workers see the same job state (e.g. Render Redis or any `redis://` URL).

## Frontend (Vercel or other)

- `NEXT_PUBLIC_API_URL` – public URL of the FastAPI backend

## Removed configs

Alternative PaaS configs (`railway.json`, `fly.toml`, `Procfile`) were removed to avoid confusion. Recover them from git history if you need Railway, Fly.io, or Heroku-style `Procfile` again.

## API documentation

Interactive OpenAPI docs: `{API_URL}/docs`
