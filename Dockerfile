FROM python:3.12-slim AS backend
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000 OUTPUT_DIR=/data/output
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates perl ghostscript \
    texlive-latex-base texlive-latex-recommended texlive-latex-extra texlive-fonts-recommended \
    && rm -rf /var/lib/apt/lists/*
COPY Skoleverksted/backend/requirements.txt /app/Skoleverksted/backend/requirements.txt
COPY VGS_KI/backend/requirements.txt /app/VGS_KI/backend/requirements.txt
COPY ScriptoriumFOV/backend/requirements.txt /app/ScriptoriumFOV/backend/requirements.txt
COPY MateMaTeX/backend/requirements.txt /app/MateMaTeX/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/Skoleverksted/backend/requirements.txt
COPY . /app
RUN mkdir -p /data/output
EXPOSE 8000
CMD ["sh", "-c", "uvicorn Skoleverksted.backend.main:app --host 0.0.0.0 --port ${PORT}"]
