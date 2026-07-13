FROM python:3.12-slim AS backend
ARG TYPST_VERSION=0.14.2
ARG TARGETARCH=amd64
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    OUTPUT_DIR=/var/data/output \
    SKOLEVERKSTED_DB_PATH=/var/data/platform/skoleverksted.sqlite3 \
    TYPST_PATH=/usr/local/bin/typst \
    PDFLATEX_PATH=/usr/bin/pdflatex
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates perl ghostscript poppler-utils xz-utils \
    lmodern texlive-latex-base texlive-latex-recommended texlive-latex-extra \
    texlive-fonts-recommended texlive-lang-european texlive-science \
    && rm -rf /var/lib/apt/lists/*
RUN set -eux; \
    case "${TARGETARCH}" in \
      amd64) typst_arch="x86_64" ;; \
      arm64) typst_arch="aarch64" ;; \
      *) echo "Unsupported architecture: ${TARGETARCH}" >&2; exit 1 ;; \
    esac; \
    archive="typst-${typst_arch}-unknown-linux-musl"; \
    curl -fsSL "https://github.com/typst/typst/releases/download/v${TYPST_VERSION}/${archive}.tar.xz" -o /tmp/typst.tar.xz; \
    tar -xJf /tmp/typst.tar.xz -C /tmp; \
    install -m 0755 "/tmp/${archive}/typst" /usr/local/bin/typst; \
    typst --version; \
    rm -rf /tmp/typst.tar.xz "/tmp/${archive}"
COPY Skoleverksted/backend/requirements.txt /app/Skoleverksted/backend/requirements.txt
COPY VGS_KI/backend/requirements.txt /app/VGS_KI/backend/requirements.txt
COPY ScriptoriumFOV/backend/requirements.txt /app/ScriptoriumFOV/backend/requirements.txt
COPY MateMaTeX/backend/requirements.txt /app/MateMaTeX/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/Skoleverksted/backend/requirements.txt
COPY . /app
RUN mkdir -p /var/data/output /var/data/platform \
    && typst --version \
    && pdflatex --version
EXPOSE 8000
CMD ["sh", "-c", "uvicorn Skoleverksted.backend.main:app --host 0.0.0.0 --port ${PORT}"]
