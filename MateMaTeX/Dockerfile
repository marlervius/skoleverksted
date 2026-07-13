# Use full Debian (not slim) to ensure apt works correctly
FROM python:3.12-bookworm

WORKDIR /app

# Install TeX Live (using Debian's packaged version which is more reliable)
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
        texlive-latex-base \
        texlive-latex-extra \
        texlive-fonts-recommended \
        texlive-lang-european \
        texlive-pictures \
        texlive-science \
    && rm -rf /var/lib/apt/lists/*

# Verify pdflatex is available
RUN pdflatex --version

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create output directory
RUN mkdir -p output && chmod 777 output

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port", "8501", "--server.address", "0.0.0.0"]
