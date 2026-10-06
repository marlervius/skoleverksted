# Deploy backend on Render

The repository contains a Render Blueprint in `render.yaml`. It creates one
Docker web service in Frankfurt with a 512 MB Starter instance and a 1 GB persistent disk.
The disk is required because projects, the shared job index and generated files
must survive restarts and deploys.

## Create the service

1. In Render, choose **New > Blueprint**.
2. Connect `marlervius/skoleverksted` and select `render.yaml`.
3. Enter the requested secrets:
   - `GOOGLE_API_KEY`: Gemini API key used by all generation workflows.
   - `APP_PASSWORD`: the shared access code that protects every API route during the
     closed pilot. Use a long random value. Changing it signs every teacher out
     (all outstanding tokens stop working), so it is also the revocation switch.
     Without it a production backend refuses all requests and `/health/ready`
     reports `norsk_access` as missing.
   - `FRONTEND_URL`: exact public frontend origin, for example `https://skoleverksted.no`.
   - `ALLOWED_ORIGINS`: same origin. Multiple origins can be comma-separated.
4. Create the Blueprint and wait for `/health/ready` to pass.

The checked-in Blueprint sets `LATEX_ENGINE=pdflatex`. Keep this setting on the
512 MB Starter service: the shared process can exceed the memory limit when
LuaLaTeX is selected by the application's `auto` mode.

Render generates `MATE_API_KEY`. Copy its value from the backend service to the
frontend host as `MATE_API_KEY`; it is used only by the server-side frontend
proxy. Configure the frontend with:

```env
NEXT_PUBLIC_API_URL=https://skoleverksted-api.onrender.com
BACKEND_INTERNAL_URL=https://skoleverksted-api.onrender.com
MATE_API_KEY=<same value as the Render backend>
```

Replace the example hostname if Render assigns another service slug.
For the Vercel Hobby flow, follow `VERCEL_DEPLOYMENT.md` after the backend has a
public hostname.

## Verify the deployment

The production smoke workflow does this after every merge and daily. It needs no
setup to prove that anonymous callers are refused. To also exercise the
signed-in path, add the access code as the GitHub Actions repository secret
`SMOKE_ACCESS_CODE` and update it whenever `APP_PASSWORD` changes. A stale value
fails the smoke test once and is never retried, so it cannot lock teachers out.

Open these URLs after the first deploy:

- `/health` — liveness and SQLite access
- `/health/ready` — required AI, storage and PDF dependencies
- `/docs` — shared platform API
- `/api/fag/docs`, `/api/norsk/docs`, `/api/matematikk/docs` — domain APIs

Only `/`, `/health`, `/health/ready` and the login/status endpoints answer
without the access code, so the documentation pages need a token too: sign in
with `POST /api/platform/access/login` (`{"code": "..."}`) and send the returned
token as `Authorization: Bearer <token>`.

`/health/ready` returns HTTP 503 and a `missing` list if a required dependency is
unavailable. It never returns API keys, the access code or Redis credentials; the
`access_gate` field only says whether the gate is enforced and a code exists.

## Operational notes

- The Blueprint deploys only after GitHub checks pass.
- A persistent disk limits this SQLite version to one service instance and
  causes a short interruption during deploys.
- The platform store uses SQLite on the mounted disk by default. Set
  `DATABASE_URL=postgresql://...` to use PostgreSQL instead; the same schema is
  created automatically on startup and generated files still use `OUTPUT_DIR`.
- Set `REDIS_URL` when running more than one backend instance. It enables a
  distributed job-capacity lease while the durable job ledger remains in the
  platform store. `REDIS_JOB_LEASE_SECONDS` defaults to one hour.
- For higher traffic, move generated files and images to object storage and run
  generation in a dedicated worker before scaling beyond a single web service.
- Generated files and the SQLite database live below `/var/data`.
- The Docker image pins Typst CLI 0.14.2 and installs TeX Live with the
  language, science and font packages used by the templates, plus `pdftotext`.
