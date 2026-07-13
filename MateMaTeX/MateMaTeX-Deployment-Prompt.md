# MateMaTeX 2.0 — Deployment: Vercel + Render (+ valgfri PostgreSQL)

> **Merk:** Kodebasen bruker ikke lenger Supabase. Database er valgfri generell PostgreSQL; auth er valgfri `MATE_API_KEY` på backend og evt. `NEXT_PUBLIC_MATE_API_KEY` på frontend.

Du skal gjøre MateMaTeX 2.0 produksjonsklar og deploye til:
- **Frontend:** Vercel (Next.js)
- **Backend:** Render (FastAPI i Docker)
- **Database:** Valgfri (f.eks. Neon, Railway Postgres, eller lokal PostgreSQL)

**Les gjennom hele den eksisterende kodebasen før du begynner.** Mange filer trenger små justeringer for å fungere i produksjon.

---

## KONTEKST: EKSISTERENDE ARKITEKTUR

```
MateMaTex/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI
│   │   ├── config.py            # Pydantic-settings
│   │   ├── models/llm.py        # LLM-interface
│   │   ├── pipeline/            # LangGraph agents
│   │   ├── verification/        # SymPy + LaTeX checker
│   │   ├── exercises/           # Oppgavebank
│   │   ├── editor/              # LaTeX-editor backend
│   │   ├── differentiation/     # Differensiering + hint
│   │   ├── export/              # PDF/Word/PPTX
│   │   ├── sharing/             # Delbare lenker
│   │   ├── collaboration/       # Skolens bank
│   │   ├── curriculum/lk20.py   # LK20-data
│   │   └── latex/               # Preamble + compiler
│   ├── tests/
│   ├── requirements.txt
│   └── schema.sql               # PostgreSQL + pgvector
├── frontend/
│   ├── src/
│   │   ├── app/                 # Next.js App Router pages
│   │   ├── components/          # UI-komponenter
│   │   └── lib/                 # Zustand store, API-klient
│   ├── package.json
│   └── tailwind.config.ts
```

---

## STEG 1: SUPABASE DATABASE

### 1.1 — Migreringsfil

Opprett `backend/migrations/001_initial.sql` basert på eksisterende `schema.sql`, men tilpasset Supabase:

```sql
-- Aktiver pgvector (Supabase har det forhåndsinstallert, men trenger enabling)
create extension if not exists vector;

-- Aktiver pg_trgm for fulltekstsøk
create extension if not exists pg_trgm;
```

Deretter hele skjemaet fra `schema.sql`. Gjør følgende justeringer:
- Erstatt eventuelle `SERIAL` med `uuid` primærnøkler (Supabase-konvensjon): `id uuid default gen_random_uuid() primary key`
- Legg til `created_at timestamptz default now()` og `updated_at timestamptz default now()` på alle tabeller
- Legg til en trigger for automatisk `updated_at`:
```sql
create or replace function update_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;
```
- Apliser triggeren på alle tabeller

### 1.2 — Row Level Security (RLS)

Aktiver RLS på ALLE tabeller og opprett policies:

```sql
-- Eksempel for exercises-tabellen:
alter table exercises enable row level security;

-- Brukere kan kun se egne oppgaver + oppgaver delt med skolen
create policy "Users see own exercises"
  on exercises for select
  using (auth.uid() = user_id);

create policy "Users see school exercises"
  on exercises for select
  using (
    is_published = true
    and school_id = (select school_id from users where id = auth.uid())
  );

create policy "Users insert own exercises"
  on exercises for insert
  with check (auth.uid() = user_id);

create policy "Users update own exercises"
  on exercises for update
  using (auth.uid() = user_id);

create policy "Users soft-delete own exercises"
  on exercises for update
  using (auth.uid() = user_id)
  with check (deleted_at is not null);
```

Lag tilsvarende policies for: `generations`, `generation_versions`, `templates`, `folders`, `tags`, `shared_links`, `comments`, `exercise_bank_school`.

### 1.3 — Supabase Auth

Vi bruker Supabase Auth for brukerautentisering:
- Aktiver email/passord-innlogging
- Opprett en `users`-profiltabell som kobles til `auth.users`:
```sql
create table public.profiles (
  id uuid references auth.users on delete cascade primary key,
  full_name text,
  school_id uuid references schools(id),
  default_grade text,
  default_language_level text default 'standard',
  preferred_model text default 'gemini-2.0-flash',
  onboarding_completed boolean default false,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- Automatisk opprett profil ved registrering
create or replace function handle_new_user()
returns trigger as $$
begin
  insert into public.profiles (id, full_name)
  values (new.id, new.raw_user_meta_data->>'full_name');
  return new;
end;
$$ language plpgsql security definer;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function handle_new_user();
```

---

## STEG 2: BACKEND FOR RENDER

### 2.1 — Dockerfile

Opprett `backend/Dockerfile` optimalisert for Render (multi-stage build for å holde image-størrelsen nede):

```dockerfile
# Stage 1: TeX Live (cached layer — dette endres sjelden)
FROM python:3.12-slim AS texlive

RUN apt-get update && apt-get install -y --no-install-recommends \
    texlive-base \
    texlive-latex-recommended \
    texlive-latex-extra \
    texlive-fonts-recommended \
    texlive-fonts-extra \
    texlive-science \
    texlive-pictures \
    texlive-lang-european \
    latexmk \
    cm-super \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Stage 2: Python dependencies (cached layer)
FROM texlive AS dependencies

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 3: Application code (changes frequently)
FROM dependencies AS app

COPY . .

# Render bruker PORT-miljøvariabelen
ENV PORT=10000
EXPOSE ${PORT}

# Healthcheck for Render
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT}/health')"

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
```

**VIKTIG:** Render sin gratis tier har 512 MB RAM. TeX Live er tungt. Bruk `--no-install-recommends` og installer KUN de TeX-pakkene vi faktisk bruker. Sjekk at LaTeX-preamble i `app/latex/` ikke krever eksotiske pakker.

### 2.2 — Oppdater `config.py`

Endre `config.py` til å lese fra miljøvariabler som Render setter:

```python
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # Database (Supabase)
    database_url: str  # Supabase connection string
    supabase_url: str  # Supabase project URL (for auth)
    supabase_anon_key: str  # Supabase anon key (for auth)
    supabase_service_role_key: str  # For server-side operations
    
    # LLM API keys
    google_api_key: str = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    
    # App config
    default_model: str = "gemini-2.0-flash"
    environment: str = "production"  # "development" | "production"
    
    # CORS
    frontend_url: str = "http://localhost:3000"  # Overskrives i prod
    
    # Render-specific
    port: int = 10000
    
    class Config:
        env_file = ".env"

@lru_cache()
def get_settings() -> Settings:
    return Settings()
```

### 2.3 — Oppdater `main.py`

Legg til / verifiser at følgende er på plass:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings

settings = get_settings()

app = FastAPI(
    title="MateMaTeX API",
    docs_url="/docs" if settings.environment == "development" else None,
    redoc_url=None,
)

# CORS — tillat frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_url,
        "http://localhost:3000",  # Lokal utvikling
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Healthcheck
@app.get("/health")
async def health():
    return {"status": "ok", "environment": settings.environment}
```

### 2.4 — Database-tilkobling

Opprett `backend/app/db.py` for Supabase-tilkobling:

```python
import asyncpg
from app.config import get_settings

# Connection pool
_pool = None

async def get_pool():
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = await asyncpg.create_pool(
            settings.database_url,
            min_size=2,
            max_size=10,
            command_timeout=30,
        )
    return _pool

async def get_db():
    pool = await get_pool()
    async with pool.acquire() as conn:
        yield conn
```

### 2.5 — Supabase Auth middleware

Opprett `backend/app/auth.py` for å verifisere JWT fra Supabase:

```python
from fastapi import Depends, HTTPException, Header
from jose import jwt, JWTError
from app.config import get_settings

async def get_current_user(authorization: str = Header(...)):
    """Verifiser Supabase JWT og returner user_id."""
    settings = get_settings()
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Invalid authorization header")
    
    token = authorization.removeprefix("Bearer ")
    
    try:
        # Supabase bruker JWT med HMAC-SHA256
        payload = jwt.decode(
            token,
            settings.supabase_anon_key,  # Eller JWT secret fra Supabase dashboard
            algorithms=["HS256"],
            audience="authenticated",
        )
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(401, "Invalid token")
        return user_id
    except JWTError:
        raise HTTPException(401, "Invalid or expired token")
```

Bruk som dependency i routere:
```python
@router.get("/exercises")
async def list_exercises(user_id: str = Depends(get_current_user)):
    ...
```

### 2.6 — Oppdater alle routere

Gå gjennom ALLE routere i `app/` og:
1. Erstatt dummy/in-memory lagring med faktiske database-kall via `get_db()`
2. Legg til `Depends(get_current_user)` på alle endepunkter som krever auth
3. Bruk `user_id` for å filtrere data (RLS gjør dette også, men defense in depth)
4. Håndter database-feil med try/except og returner passende HTTP-statuskoder

### 2.7 — Render-konfigurasjon

Opprett `backend/render.yaml` (Infrastructure as Code):

```yaml
services:
  - type: web
    name: matematex-api
    runtime: docker
    dockerfilePath: ./Dockerfile
    dockerContext: .
    plan: free
    region: frankfurt  # Nærmest Norge
    healthCheckPath: /health
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: matematex-db
          property: connectionString
      - key: SUPABASE_URL
        sync: false
      - key: SUPABASE_ANON_KEY
        sync: false
      - key: SUPABASE_SERVICE_ROLE_KEY
        sync: false
      - key: GOOGLE_API_KEY
        sync: false
      - key: FRONTEND_URL
        sync: false
      - key: ENVIRONMENT
        value: production
```

**Merk:** Vi bruker IKKE Render sin database (vi bruker Supabase), men Render-yaml trenger `envVars` uansett. Sett `DATABASE_URL` manuelt til Supabase sin connection string.

---

## STEG 3: FRONTEND FOR VERCEL

### 3.1 — Miljøvariabler

Opprett `frontend/.env.local` (for lokal utvikling) og dokumenter hva som trengs i Vercel:

```bash
# .env.local (lokal utvikling)
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_URL=https://xxxxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJxxxxx

# I Vercel dashboard, sett:
# NEXT_PUBLIC_API_URL=https://matematex-api.onrender.com
# NEXT_PUBLIC_SUPABASE_URL=https://xxxxx.supabase.co
# NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJxxxxx
```

### 3.2 — Supabase-klient

Opprett `frontend/src/lib/supabase.ts`:

```typescript
import { createBrowserClient } from '@supabase/ssr'

export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  )
}
```

Installer: `npm install @supabase/ssr @supabase/supabase-js`

### 3.3 — Auth-sider

Opprett login/registrerings-sider:

**`app/login/page.tsx`:**
- Email + passord-felt
- "Logg inn"-knapp
- "Opprett konto"-lenke
- Bruk Supabase `signInWithPassword`
- Redirect til dashboard etter innlogging
- Design: Sentrert kort på mørk bakgrunn, MateMaTeX-logo øverst, serif-heading

**`app/register/page.tsx`:**
- Fullt navn + email + passord + bekreft passord
- "Opprett konto"-knapp
- Bruk Supabase `signUp` med `data: { full_name }`
- Redirect til onboarding-wizard

**`app/auth/callback/route.ts`:**
- Håndter Supabase auth callback (for email-bekreftelse)

### 3.4 — Auth middleware

Opprett `frontend/src/middleware.ts`:

```typescript
import { createServerClient } from '@supabase/ssr'
import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

export async function middleware(request: NextRequest) {
  const response = NextResponse.next()
  
  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll: () => request.cookies.getAll(),
        setAll: (cookies) => {
          cookies.forEach(({ name, value, options }) => {
            response.cookies.set(name, value, options)
          })
        },
      },
    }
  )
  
  const { data: { user } } = await supabase.auth.getUser()
  
  // Redirect uautentiserte brukere til login
  const publicPaths = ['/login', '/register', '/auth/callback', '/shared']
  const isPublic = publicPaths.some(p => request.nextUrl.pathname.startsWith(p))
  
  if (!user && !isPublic) {
    return NextResponse.redirect(new URL('/login', request.url))
  }
  
  if (user && (request.nextUrl.pathname === '/login' || request.nextUrl.pathname === '/register')) {
    return NextResponse.redirect(new URL('/', request.url))
  }
  
  return response
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
}
```

### 3.5 — Oppdater API-klienten

Oppdater `frontend/src/lib/api.ts` til å:
1. Bruke `NEXT_PUBLIC_API_URL` i stedet for hardkodet URL
2. Inkludere Supabase JWT i alle requests:
```typescript
import { createClient } from './supabase'

const API_URL = process.env.NEXT_PUBLIC_API_URL

async function getAuthHeaders(): Promise<Record<string, string>> {
  const supabase = createClient()
  const { data: { session } } = await supabase.auth.getSession()
  
  if (!session?.access_token) {
    throw new Error('Not authenticated')
  }
  
  return {
    'Authorization': `Bearer ${session.access_token}`,
    'Content-Type': 'application/json',
  }
}

// Oppdater alle API-kall til å bruke getAuthHeaders()
export async function generateContent(params: GenerateParams) {
  const headers = await getAuthHeaders()
  const response = await fetch(`${API_URL}/generate`, {
    method: 'POST',
    headers,
    body: JSON.stringify(params),
  })
  // ...
}
```

### 3.6 — Vercel-konfigurasjon

Opprett `frontend/vercel.json`:

```json
{
  "framework": "nextjs",
  "regions": ["arn1"],
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        { "key": "X-Frame-Options", "value": "DENY" },
        { "key": "X-Content-Type-Options", "value": "nosniff" },
        { "key": "Referrer-Policy", "value": "strict-origin-when-cross-origin" }
      ]
    }
  ]
}
```

`"regions": ["arn1"]` = Stockholm — nærmeste Vercel-region til Trondheim.

---

## STEG 4: KEEP-ALIVE FOR RENDER

Render sin gratis tier spinner ned etter 15 minutter uten trafikk. Cold start med TeX Live kan ta 30–60 sekunder. Løsninger:

### 4.1 — Vercel Cron Job

Opprett `frontend/app/api/keep-alive/route.ts`:

```typescript
export const runtime = 'edge'
export const dynamic = 'force-dynamic'

export async function GET() {
  try {
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/health`, {
      signal: AbortSignal.timeout(10000),
    })
    const data = await res.json()
    return Response.json({ ok: true, backend: data })
  } catch {
    return Response.json({ ok: false, error: 'Backend unreachable' }, { status: 503 })
  }
}
```

Opprett `frontend/vercel.json` (oppdatert med cron):

```json
{
  "framework": "nextjs",
  "regions": ["arn1"],
  "crons": [
    {
      "path": "/api/keep-alive",
      "schedule": "*/14 7-17 * * 1-5"
    }
  ]
}
```

Dette pinger backenden hvert 14. minutt, mandag–fredag kl. 07–17 (norsk arbeidstid). Utenfor arbeidstid sparer vi ressurser.

**Merk:** Vercel gratis tier inkluderer cron jobs (maks 2, daglig kjøring). For hvert 14. minutt-kjøring trenger du **Vercel Pro** ($20/mnd) ELLER bruk en gratis ekstern cron-tjeneste:

### 4.2 — Alternativ: Ekstern cron (gratis)

Bruk **cron-job.org** (helt gratis) eller **UptimeRobot** (gratis, 5 min intervall):
- URL: `https://matematex-api.onrender.com/health`
- Intervall: Hvert 14. minutt
- Tidsperiode: 07:00–17:00 CET, mandag–fredag

Dette er enklere og gratis. Hopp over Vercel cron i så fall.

---

## STEG 5: LOKAL UTVIKLINGSMILJØ

### 5.1 — Docker Compose for lokal utvikling

Opprett `docker-compose.yml` i prosjektets rot:

```yaml
version: '3.8'

services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    env_file:
      - ./backend/.env
    environment:
      - ENVIRONMENT=development
      - PORT=8000
      - FRONTEND_URL=http://localhost:3000
    volumes:
      - ./backend/app:/app/app  # Hot reload
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  # Frontend kjøres lokalt med npm (raskere HMR enn Docker)
  # cd frontend && npm run dev
```

### 5.2 — Backend `.env`

Opprett `backend/.env.example`:

```bash
# Database (Supabase)
DATABASE_URL=postgresql://postgres:xxxxx@db.xxxxx.supabase.co:5432/postgres
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_ANON_KEY=eyJxxxxx
SUPABASE_SERVICE_ROLE_KEY=eyJxxxxx

# LLM API keys (minst én påkrevd)
GOOGLE_API_KEY=
ANTHROPIC_API_KEY=
OPENAI_API_KEY=

# App
ENVIRONMENT=development
FRONTEND_URL=http://localhost:3000
DEFAULT_MODEL=gemini-2.0-flash
```

---

## STEG 6: DEPLOY-SJEKKLISTE

Etter at all kode er på plass, gå gjennom denne sjekklisten:

### Supabase
- [ ] Opprett nytt Supabase-prosjekt
- [ ] Kjør `001_initial.sql` i SQL Editor
- [ ] Aktiver Email auth i Authentication → Providers
- [ ] Kopier Project URL, anon key, service role key og connection string

### Render
- [ ] Opprett ny Web Service → koble til GitHub repo → velg `backend/` som root directory
- [ ] Sett Docker som runtime
- [ ] Legg til alle miljøvariabler (DATABASE_URL, SUPABASE_*, GOOGLE_API_KEY, FRONTEND_URL)
- [ ] Sett `FRONTEND_URL` til Vercel-URLen (settes etter Vercel-deploy)
- [ ] Deploy og verifiser at `/health` returnerer `{"status": "ok"}`
- [ ] Verifiser at `/docs` IKKE er tilgjengelig (production mode)

### Vercel
- [ ] Importer GitHub repo → velg `frontend/` som root directory
- [ ] Legg til miljøvariabler: `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- [ ] Deploy og verifiser at login-siden vises
- [ ] Gå tilbake til Render og oppdater `FRONTEND_URL` med den faktiske Vercel-URLen

### Integrasjonstest
- [ ] Registrer en bruker via frontend
- [ ] Logg inn
- [ ] Generer et arbeidsark (sjekk at pipeline-visualiseringen fungerer)
- [ ] Verifiser at PDF genereres og kan lastes ned
- [ ] Sjekk at oppgavebanken mottar oppgaver
- [ ] Test deling av en generering

### Keep-alive
- [ ] Sett opp cron-job.org eller UptimeRobot for backend-ping

---

## SIKKERHET — VIKTIG

- [ ] **Aldri** commit `.env`-filer. Verifiser at `.gitignore` inkluderer: `.env`, `.env.local`, `.env.production`
- [ ] `SUPABASE_SERVICE_ROLE_KEY` skal ALDRI eksponeres til frontend (ingen `NEXT_PUBLIC_` prefix)
- [ ] Render dashboard: Marker sensitive env vars som "secret"
- [ ] Verifiser at CORS kun tillater din Vercel-URL i production
- [ ] Fjern `/docs` i production (allerede håndtert i `main.py`)

---

*Begynn med Steg 1: Opprett Supabase-migreringsfilen basert på eksisterende `schema.sql`, med UUID-primærnøkler, RLS-policies og auth-trigger. Vis meg den komplette SQL-filen.*
