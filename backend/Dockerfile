# backend/Dockerfile
# Auteur Felix NZIKO
FROM python:3.12-slim

LABEL org.opencontainers.image.title="GANDAL-AI" \
      org.opencontainers.image.description="RAG navigation du projet GANDAL GI27" \
      org.opencontainers.image.authors="Felix NZIKO"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr tesseract-ocr-fra tesseract-ocr-eng \
        libreoffice-writer libreoffice-calc libreoffice-impress fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini .
COPY migrations migrations
COPY app app
RUN useradd --create-home gandal && mkdir -p /app/data && chown gandal:gandal /app/data
USER gandal
VOLUME /app/data

EXPOSE 8090
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8090"]
