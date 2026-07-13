# =============================================================================
# MateMaTeX 2.0 — Backend Dockerfile (optimized for Render)
# =============================================================================

# Stage 1: TeX Live (cached layer — changes rarely)
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
    texlive-luatex \
    texlive-xetex \
    fonts-lato \
    fonts-libertinus \
    latexmk \
    cm-super \
    lmodern \
    && apt-get clean && rm -rf /var/lib/apt/lists/* \
    && luaotfload-tool --update || true

# Stage 2: Python dependencies (cached layer)
FROM texlive AS dependencies

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 3: Application code (changes frequently)
FROM dependencies AS app

COPY . .

# Render uses PORT env var
ENV PORT=10000
EXPOSE ${PORT}

# Healthcheck for Render
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT}/health')"

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
