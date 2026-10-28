# backend/Dockerfile
# Auteur Felix NZIKO
FROM python:3.12-slim

LABEL org.opencontainers.image.title="GANDAL-AI" \
      org.opencontainers.image.description="RAG navigation du projet GANDAL GI27" \
      org.opencontainers.image.authors="Felix NZIKO"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app app
RUN useradd --create-home gandal
USER gandal

EXPOSE 8090
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8090"]
